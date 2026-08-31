"""Hostile zero/one-call controls for the held Dolphin 3B-1 executor."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable

import pytest

import analytics.evaluation_v14 as evaluation_v14
import analytics.feasibility_execution as execution
from analytics.aep_provenance import AepProvenanceError
from analytics.contracts_v14 import (
    AuthoredScenarioPathAuthority,
    AuthoredScenarioPathBinding,
    D3BAuthoredNumericValue,
    D3BAuthorizedJurisdictionDomain,
    D3BAuthorizedTechnologyBinding,
    D3BExecutionFailure,
    D3BExecutionPhase,
    D3BExecutionSuccess,
    D3BFailureCode,
    D3BNumericProjectionReceipt,
)
from analytics.feasibility_report_contract import (
    EvaluationRequest,
    JurisdictionSubject,
    JurisdictionSubjectAssertion,
    MaterialDispositionKind,
    ProjectCase,
    ProjectCaseMaterialCategory,
    resolved_config_sha256,
)
from analytics.scenario_loader import ScenarioConfigError, load_scenario_config
from tests.contracts.test_assessment_scope_contract import (
    _add_storage_technology,
    _replace_wind_with_solar_dc,
    _request_payload,
)
from tests.contracts.test_project_case_contract import _case_payload

_MODULE = Path(execution.__file__).resolve()
_AUTHORITY_ID = "authority:d3b1-test"


@dataclass(frozen=True)
class _Bundle:
    project_case: ProjectCase
    request: EvaluationRequest
    authority: AuthoredScenarioPathAuthority
    source_path: Path
    authored_config: dict[str, Any]


def _project_case(
    *,
    capacity: str = "100",
    include_storage: bool = False,
    solar_dc: bool = False,
    missing_field: str | None = None,
    opex_periodicity: str = "annual",
    storage_only: bool = False,
    legacy_turbine_shape: bool = False,
) -> ProjectCase:
    if storage_only:
        include_storage = True
    if include_storage and solar_dc:
        raise ValueError("test fixture does not combine solar DC and storage")
    payload = _case_payload()
    storage = payload["assets"][1]
    shared = payload["assets"][2]
    payload["identity"] = {
        "project_id": "project:fictionland-hybrid",
        "case_id": "case:screening-base",
        "case_name": "Fictionland Hybrid Screening",
        "revision": 1,
    }
    payload["location"].update(
        {
            "site_name": "Fictional Coast",
            "description": " Fictional coast site ",
            "site_jurisdiction_binding_id": "jurisdiction-binding:site",
        }
    )
    payload["jurisdiction_bindings"] = [
        {
            "binding_id": "jurisdiction-binding:site",
            "jurisdiction_code": "FIC",
            "subject": "site",
            "support_status": "declared",
            "contract_pack_id": "contract-pack:fic-site",
            "contract_pack_version": "1.0.0",
        },
        {
            "binding_id": "jurisdiction-binding:tax",
            "jurisdiction_code": "FIC",
            "subject": "tax",
            "support_status": "declared",
            "contract_pack_id": "contract-pack:fic-tax",
            "contract_pack_version": "1.0.0",
        },
        {
            "binding_id": "jurisdiction-binding:contract",
            "jurisdiction_code": "FIC",
            "subject": "contract",
            "support_status": "declared",
            "contract_pack_id": "contract-pack:fic-contract",
            "contract_pack_version": "1.0.0",
        },
        {
            "binding_id": "jurisdiction-binding:financing",
            "jurisdiction_code": "FIC",
            "subject": "financing",
            "support_status": "declared",
            "contract_pack_id": "contract-pack:fic-financing",
            "contract_pack_version": "1.0.0",
        },
    ]
    generation_binding_id = (
        "technology-binding:solar" if solar_dc else "technology-binding:wind"
    )
    generation_technology_id = "solar_pv" if solar_dc else "wind"
    generation_asset_id = "asset:solar-01" if solar_dc else "asset:wind-01"
    generation_allocation_label = "solar" if solar_dc else "wind"
    payload["technology_bindings"] = [
        {
            "binding_id": generation_binding_id,
            "technology_id": generation_technology_id,
            "asset_class": "generation",
            "support_status": "declared",
            "contract_pack_id": (
                "contract-pack:solar-generation"
                if solar_dc
                else "contract-pack:wind-generation"
            ),
            "contract_pack_version": "1.0.0",
        }
    ]
    if include_storage:
        payload["technology_bindings"].append(
            {
                "binding_id": "technology-binding:bess",
                "technology_id": "bess",
                "asset_class": "storage",
                "support_status": "declared",
                "contract_pack_id": "contract-pack:bess-storage",
                "contract_pack_version": "1.0.0",
            }
        )
    if storage_only:
        payload["technology_bindings"] = [payload["technology_bindings"][1]]
    wind = payload["assets"][0]
    wind.update(
        {
            "asset_id": generation_asset_id,
            "technology_id": generation_technology_id,
            "technology_binding_id": generation_binding_id,
        }
    )
    if solar_dc:
        wind["capacity"] = {
            "kind": "aggregate",
            "electrical_basis": "dc",
            "capacity_basis": "nameplate",
            "total_power_capacity": {
                "state": "resolved",
                "value": capacity,
                "unit": "MWdc",
                "bindings": [
                    {"kind": "source", "reference_id": "source:project-basis"}
                ],
            },
        }
    else:
        wind["capacity"].update(
            {
                "capacity_basis": ("nameplate" if legacy_turbine_shape else "net"),
                "unit_count": {
                    "state": "resolved",
                    "value": "2",
                    "unit": "count",
                    "bindings": [
                        {"kind": "source", "reference_id": "source:project-basis"}
                    ],
                },
                "unit_power_capacity": {
                    "state": "resolved",
                    "value": str(Decimal(capacity) / 2),
                    "unit": "MW",
                    "bindings": [
                        {"kind": "source", "reference_id": "source:project-basis"}
                    ],
                },
                "total_power_capacity": {
                    "state": "resolved",
                    "value": capacity,
                    "unit": "MW",
                    "bindings": [
                        {"kind": "source", "reference_id": "source:project-basis"}
                    ],
                },
            }
        )
    if storage_only:
        storage.update(
            {
                "technology_binding_id": "technology-binding:bess",
                "charging_source": {
                    "kind": "governed_source",
                    "source_id": "source:project-basis",
                },
            }
        )
        payload["assets"] = [storage]
        payload["topology"] = {
            "topology_id": "topology:fictionland-bess",
            "kind": "storage_only",
            "interconnection_arrangement": "dedicated_separate",
            "common_interconnection_asset_id": None,
            "links": [],
        }
    elif include_storage:
        storage.update(
            {
                "technology_binding_id": "technology-binding:bess",
                "charging_source": {"kind": "asset", "asset_id": "asset:wind-01"},
            }
        )
        payload["assets"] = [wind, storage, shared]
        payload["topology"] = {
            "topology_id": "topology:fictionland-wind-bess",
            "kind": "hybrid",
            "interconnection_arrangement": "common_shared",
            "common_interconnection_asset_id": "asset:poi-01",
            "links": [
                {
                    "link_id": "link:wind-to-poi",
                    "kind": "uses_shared_infrastructure",
                    "from_asset_id": "asset:wind-01",
                    "to_asset_id": "asset:poi-01",
                },
                {
                    "link_id": "link:bess-to-poi",
                    "kind": "uses_shared_infrastructure",
                    "from_asset_id": "asset:bess-01",
                    "to_asset_id": "asset:poi-01",
                },
                {
                    "link_id": "link:bess-charges-from-wind",
                    "kind": "charges_from",
                    "from_asset_id": "asset:bess-01",
                    "to_asset_id": "asset:wind-01",
                },
            ],
        }
    else:
        payload["assets"] = [wind]
        payload["topology"] = {
            "topology_id": (
                "topology:fictionland-solar"
                if solar_dc
                else "topology:fictionland-wind"
            ),
            "kind": "single_technology",
            "interconnection_arrangement": "dedicated_separate",
            "common_interconnection_asset_id": None,
            "links": [],
        }
    for line in payload["costs"]["lines"]:
        prefix = "capex" if line["cost_kind"] == "capex" else "opex"
        line["allocation_ids"] = (
            [f"allocation:{prefix}:bess"]
            if storage_only
            else [f"allocation:{prefix}:{generation_allocation_label}"]
        )
        if include_storage and not storage_only:
            line["allocation_ids"].append(f"allocation:{prefix}:bess")
    wind_share = "0.8" if include_storage else "1"
    payload["costs"]["allocations"] = (
        []
        if storage_only
        else [
            {
                "allocation_id": f"allocation:capex:{generation_allocation_label}",
                "cost_line_id": "cost:capex:plant",
                "asset_id": generation_asset_id,
                "share": {
                    "state": "resolved",
                    "value": wind_share,
                    "unit": "fraction",
                    "bindings": [
                        {"kind": "source", "reference_id": "source:project-basis"}
                    ],
                },
            },
            {
                "allocation_id": f"allocation:opex:{generation_allocation_label}",
                "cost_line_id": "cost:opex:annual",
                "asset_id": generation_asset_id,
                "share": {
                    "state": "resolved",
                    "value": wind_share,
                    "unit": "fraction",
                    "bindings": [
                        {"kind": "source", "reference_id": "source:project-basis"}
                    ],
                },
            },
        ]
    )
    if include_storage:
        storage_share = "1" if storage_only else "0.2"
        payload["costs"]["allocations"].extend(
            [
                {
                    "allocation_id": "allocation:capex:bess",
                    "cost_line_id": "cost:capex:plant",
                    "asset_id": "asset:bess-01",
                    "share": {
                        "state": "resolved",
                        "value": storage_share,
                        "unit": "fraction",
                        "bindings": [
                            {
                                "kind": "source",
                                "reference_id": "source:project-basis",
                            }
                        ],
                    },
                },
                {
                    "allocation_id": "allocation:opex:bess",
                    "cost_line_id": "cost:opex:annual",
                    "asset_id": "asset:bess-01",
                    "share": {
                        "state": "resolved",
                        "value": storage_share,
                        "unit": "fraction",
                        "bindings": [
                            {
                                "kind": "source",
                                "reference_id": "source:project-basis",
                            }
                        ],
                    },
                },
            ]
        )
    payload["costs"]["price_bases"][0].update(
        {
            "price_basis_id": "price-basis:2026-usd",
            "valuation_date": "2026-08-01",
            "price_level": "2026 nominal United States dollars",
            "nominality": "nominal",
        }
    )
    payload["costs"]["lines"][0]["price_basis_id"] = "price-basis:2026-usd"
    payload["costs"]["lines"][1]["price_basis_id"] = "price-basis:2026-usd"
    payload["costs"]["lines"][1]["periodicity"] = opex_periodicity
    payload["costs"]["currency_conversions"][0].update(
        {
            "valuation_date": "2026-08-01",
            "price_basis_id": "price-basis:2026-usd",
        }
    )
    payload["sources"][0].update(
        {
            "jurisdiction_codes": ["FIC"],
            "technology_ids": (
                ["bess"]
                if storage_only
                else (
                    ["wind", "bess"] if include_storage else [generation_technology_id]
                )
            ),
        }
    )
    if missing_field is not None:
        missing_id = f"missing:{missing_field}"
        if missing_field == "capex_quantity":
            target = payload["costs"]["lines"][0]
            key = "quantity"
            field_path = "/costs/lines/0/quantity"
            unit = "MW"
            payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
        elif missing_field == "generation_capacity":
            target = wind["capacity"]
            key = "total_power_capacity"
            field_path = "/assets/0/capacity/total_power_capacity"
            unit = "MWdc" if solar_dc else "MW"
        else:
            raise ValueError("unknown test missing field")
        target[key] = {
            "state": "missing",
            "missing_input_id": missing_id,
            "unit": unit,
        }
        payload["missing_inputs"].append(
            {
                "missing_input_id": missing_id,
                "field_path": field_path,
                "expected_unit": unit,
                "reason": "Controlled D3B missing-input fixture.",
                "consequence": "The selected proposition is unavailable.",
                "remedy": "Supply a governed source-bound value.",
            }
        )
    return ProjectCase.model_validate_json(json.dumps(payload))


def _request(
    *,
    source_digest: str,
    resolved_digest: str,
    include_storage: bool = False,
    solar_dc: bool = False,
    multi_financing_jurisdiction: bool = False,
    reverse_subject_authorities: bool = False,
    storage_only: bool = False,
    legacy_turbine_shape: bool = False,
) -> EvaluationRequest:
    if storage_only:
        include_storage = True
    payload = _request_payload()
    if include_storage:
        _add_storage_technology(payload)
    if solar_dc:
        _replace_wind_with_solar_dc(payload)
    if legacy_turbine_shape:
        payload["binding_policy"]["assertions"] = [
            item
            for item in payload["binding_policy"]["assertions"]
            if item.get("assertion_id")
            not in {"assertion:project-capacity", "assertion:wind-capacity"}
        ]
        payload["binding_policy"]["assertions"].extend(
            [
                {
                    "kind": "generation_capacity_assertion",
                    "assertion_id": "assertion:turbine-count",
                    "category": "generation_capacity",
                    "asset_id": "asset:wind-01",
                    "base_config_key": "wind",
                    "project_case_selector": "unit_count",
                    "base_selector": "turbine_count",
                    "expected_unit": "count",
                    "electrical_basis": "not_applicable",
                    "capacity_basis": "nameplate",
                    "authored_technology_kind": "wind_turbine",
                },
                {
                    "kind": "generation_capacity_assertion",
                    "assertion_id": "assertion:turbine-rated-power",
                    "category": "generation_capacity",
                    "asset_id": "asset:wind-01",
                    "base_config_key": "wind",
                    "project_case_selector": "unit_rated_power",
                    "base_selector": "turbine_rated_power_mw",
                    "expected_unit": "MW",
                    "electrical_basis": "not_applicable",
                    "capacity_basis": "nameplate",
                    "authored_technology_kind": "wind_turbine",
                },
                {
                    "kind": "generation_capacity_assertion",
                    "assertion_id": "assertion:turbine-total-capacity",
                    "category": "generation_capacity",
                    "asset_id": "asset:wind-01",
                    "base_config_key": "wind",
                    "project_case_selector": "total_power_capacity",
                    "base_selector": "turbine_total_capacity_mw",
                    "expected_unit": "MW",
                    "electrical_basis": "not_applicable",
                    "capacity_basis": "nameplate",
                    "authored_technology_kind": "wind_turbine",
                },
            ]
        )
    payload["base_scenario"]["source_file_sha256"] = source_digest
    payload["base_scenario"]["resolved_config_sha256"] = resolved_digest
    validation_receipt = payload["base_scenario"]["validation_receipt"]
    validation_receipt["resolved_config_sha256"] = resolved_digest

    extra_subjects = (
        (
            "jurisdiction-binding:contract",
            "contract",
            "source:fictionland-authored-base",
        ),
        (
            "jurisdiction-binding:financing",
            "financing",
            "source:fictionland-authored-base",
        ),
    )
    for binding_id, subject, authority_source_id in extra_subjects:
        payload["scope"]["jurisdiction_scope"].append(
            {
                "jurisdiction_binding_id": binding_id,
                "jurisdiction_code": "FIC",
                "subject": subject,
            }
        )
        payload["base_scenario"]["subject_authorities"].append(
            {
                "jurisdiction_binding_id": binding_id,
                "jurisdiction_code": "FIC",
                "subject": subject,
                "authority_source_id": authority_source_id,
            }
        )
    if multi_financing_jurisdiction:
        payload["scope"]["jurisdiction_scope"].append(
            {
                "jurisdiction_binding_id": "jurisdiction-binding:financing-alt",
                "jurisdiction_code": "ALT",
                "subject": "financing",
            }
        )
        payload["base_scenario"]["subject_authorities"].append(
            {
                "jurisdiction_binding_id": "jurisdiction-binding:financing-alt",
                "jurisdiction_code": "ALT",
                "subject": "financing",
                "authority_source_id": "source:fictionland-authored-base",
            }
        )
    domains = {
        item["domain"]: item for item in payload["base_scenario"]["domain_dispositions"]
    }
    retained = {
        "project_lifecycle_timeline": (
            "jurisdiction-binding:site",
            None,
        ),
        "revenue_tariff": ("jurisdiction-binding:contract", None),
        "fx": ("jurisdiction-binding:financing", None),
        "financing_debt": (
            (
                "jurisdiction-binding:financing-alt"
                if multi_financing_jurisdiction
                else "jurisdiction-binding:financing"
            ),
            None,
        ),
    }
    for domain, (jurisdiction_id, technology_id) in retained.items():
        domains[domain].update(
            {
                "disposition": "retained_authored_authority",
                "authority_routes": [
                    {
                        "authority_source_id": "source:fictionland-authored-base",
                        "jurisdiction_binding_id": jurisdiction_id,
                        "technology_binding_id": technology_id,
                    }
                ],
            }
        )

    payload["binding_policy"]["assertions"].extend(
        [
            {
                "kind": "jurisdiction_subject_assertion",
                "assertion_id": "assertion:site-lifecycle-jurisdiction",
                "category": "jurisdiction_subject",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "jurisdiction_code": "FIC",
                "subject": "site",
                "base_domain": "project_lifecycle_timeline",
            },
            {
                "kind": "jurisdiction_subject_assertion",
                "assertion_id": "assertion:contract-jurisdiction",
                "category": "jurisdiction_subject",
                "jurisdiction_binding_id": "jurisdiction-binding:contract",
                "jurisdiction_code": "FIC",
                "subject": "contract",
                "base_domain": "revenue_tariff",
            },
            {
                "kind": "jurisdiction_subject_assertion",
                "assertion_id": "assertion:fx-jurisdiction",
                "category": "jurisdiction_subject",
                "jurisdiction_binding_id": "jurisdiction-binding:financing",
                "jurisdiction_code": "FIC",
                "subject": "financing",
                "base_domain": "fx",
            },
            {
                "kind": "jurisdiction_subject_assertion",
                "assertion_id": "assertion:debt-jurisdiction",
                "category": "jurisdiction_subject",
                "jurisdiction_binding_id": (
                    "jurisdiction-binding:financing-alt"
                    if multi_financing_jurisdiction
                    else "jurisdiction-binding:financing"
                ),
                "jurisdiction_code": ("ALT" if multi_financing_jurisdiction else "FIC"),
                "subject": "financing",
                "base_domain": "financing_debt",
            },
        ]
    )
    if reverse_subject_authorities:
        payload["scope"]["jurisdiction_scope"].reverse()
        payload["base_scenario"]["subject_authorities"].reverse()
    if storage_only:
        payload["scope"]["technology_scope"] = [payload["scope"]["technology_scope"][1]]
        payload["base_scenario"]["technology_authorities"] = [
            payload["base_scenario"]["technology_authorities"][1]
        ]
        for domain in ("project_resource", "technology_resource"):
            domains[domain]["authority_routes"] = [
                route
                for route in domains[domain]["authority_routes"]
                if route["technology_binding_id"] == "technology-binding:bess"
            ]
        payload["binding_policy"]["assertions"] = [
            item
            for item in payload["binding_policy"]["assertions"]
            if item.get("asset_id") != "asset:wind-01"
        ]
        generation_disposition = next(
            item
            for item in payload["binding_policy"]["material_dispositions"]
            if item["category"] == "generation_capacity"
        )
        generation_disposition["disposition"] = "explicitly_out_of_v1"
        generation_disposition["action"] = "exclude_from_v1_no_fallback"
    return EvaluationRequest.model_validate_json(json.dumps(payload))


def _authored_config(
    *,
    scenario_name: bool = True,
    legacy_run_alias: bool = False,
    capacity: int | float = 100,
    include_storage: bool = False,
    solar_dc: bool = False,
    bess_energy_mwh: int | float = 10,
    canonical_run_mode: bool = False,
    tariff_jurisdiction: str = "FIC",
    debt_jurisdiction: str = "FIC",
    storage_only: bool = False,
    legacy_turbine_shape: bool = False,
) -> dict[str, Any]:
    if storage_only:
        include_storage = True
    config: dict[str, Any] = {
        "meta": {"source_path": "scenarios/d3b1_fixture.json"},
        "project": {
            "name": "Non-authoritative display name",
            "location": "Fictional coast site",
            "jurisdiction_code": "FIC",
            "capacity_mw": capacity,
            "capacity_factor_pct": 35,
            "project_life_years": 25,
        },
        "generation": {
            "technologies": {"wind": {"capacity_mw": capacity, "capacity_factor": 0.35}}
        },
        "tariff": {
            "lkr_per_kwh": 24,
            "jurisdiction_code": tariff_jurisdiction,
        },
        "capex": {"usd_total": 10_000_000},
        "opex": {"usd_per_year": 1_000_000},
        "tax": {
            "jurisdiction_code": "FIC",
            "corporate_tax_rate": 0.28,
            "depreciation_method": "straight_line",
            "depreciation_start_year": 1,
            "depreciation_years": 15,
            "enhanced_allowance_applies": False,
            "enhanced_capital_allowance_multiple": 1,
            "loss_carryforward_years": 25,
            "tax_holiday_start_year": 1,
            "tax_holiday_years": 0,
            "wht_on_interest_to_nonresidents": 0,
            "wht_on_interest_enabled": False,
            "wht_gross_up": False,
        },
        "fx": {
            "jurisdiction_code": "FIC",
            "start_lkr_per_usd": 300,
            "annual_depr": 0.02,
        },
        "debt": {
            "jurisdiction_code": debt_jurisdiction,
            "target_dscr": 1.4,
            "interest_rate_pct": 6,
            "term_years": 18,
        },
    }
    if include_storage:
        config["generation"]["technologies"]["bess"] = {
            "power_mw": 2.5,
            "energy_mwh": bess_energy_mwh,
            "duration_h": 4,
        }
    if storage_only:
        config["generation"]["technologies"] = {
            "bess": config["generation"]["technologies"]["bess"]
        }
    if legacy_turbine_shape:
        config.pop("generation")
        config["turbine"] = {
            "n_turbines": 2,
            "rated_power_mw": capacity / 2,
            "total_capacity_mw": capacity,
        }
    if solar_dc:
        config["generation"]["technologies"] = {"solar": {}}
        config["resource"] = {"solar": {"dc_capacity_mw": capacity}}
    if scenario_name:
        config["scenario_name"] = "Fictionland Hybrid Screening"
    if legacy_run_alias:
        config["run_mode"] = "screening"
    if canonical_run_mode:
        config["run"] = {"mode": "screening"}
    return config


def _bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scenario_name: bool = True,
    legacy_run_alias: bool = False,
    project_capacity: str = "100",
    authored_capacity: int | float = 100,
    include_storage: bool = False,
    solar_dc: bool = False,
    bess_energy_mwh: int | float = 10,
    missing_field: str | None = None,
    opex_periodicity: str = "annual",
    canonical_run_mode: bool = False,
    tariff_jurisdiction: str = "FIC",
    debt_jurisdiction: str = "FIC",
    storage_only: bool = False,
    legacy_turbine_shape: bool = False,
) -> _Bundle:
    if storage_only:
        include_storage = True
    root = tmp_path.resolve()
    scenarios = root / "scenarios"
    scenarios.mkdir()
    source_path = scenarios / "d3b1_fixture.json"
    authored = _authored_config(
        scenario_name=scenario_name,
        legacy_run_alias=legacy_run_alias,
        capacity=authored_capacity,
        include_storage=include_storage,
        solar_dc=solar_dc,
        bess_energy_mwh=bess_energy_mwh,
        canonical_run_mode=canonical_run_mode,
        tariff_jurisdiction=tariff_jurisdiction,
        debt_jurisdiction=debt_jurisdiction,
        storage_only=storage_only,
        legacy_turbine_shape=legacy_turbine_shape,
    )
    raw = json.dumps(authored, sort_keys=True).encode("utf-8")
    source_path.write_bytes(raw)
    source_digest = hashlib.sha256(raw).hexdigest()
    loaded = load_scenario_config(source_path)
    project_case = _project_case(
        capacity=project_capacity,
        include_storage=include_storage,
        solar_dc=solar_dc,
        missing_field=missing_field,
        opex_periodicity=opex_periodicity,
        storage_only=storage_only,
        legacy_turbine_shape=legacy_turbine_shape,
    )
    request = _request(
        source_digest=source_digest,
        resolved_digest=resolved_config_sha256(loaded),
        include_storage=include_storage,
        solar_dc=solar_dc,
        storage_only=storage_only,
        legacy_turbine_shape=legacy_turbine_shape,
    )
    jurisdiction_domains = tuple(
        sorted(
            (
                D3BAuthorizedJurisdictionDomain(
                    jurisdiction_binding_id=item.jurisdiction_binding_id,
                    jurisdiction_code=item.jurisdiction_code,
                    subject=item.subject.value,
                    base_domain=item.base_domain.value,
                )
                for item in request.binding_policy.assertions
                if type(item) is JurisdictionSubjectAssertion
            ),
            key=lambda item: (
                item.subject,
                item.base_domain,
                item.jurisdiction_binding_id,
            ),
        )
    )
    technology_scope = {
        item.technology_binding_id: item for item in request.scope.technology_scope
    }
    technology_bindings = tuple(
        sorted(
            (
                D3BAuthorizedTechnologyBinding(
                    technology_binding_id=item.technology_binding_id,
                    technology_id=item.technology_id,
                    asset_class=technology_scope[
                        item.technology_binding_id
                    ].asset_class.value,
                    base_config_key=item.base_config_key,
                    authored_technology_kind=item.authored_technology_kind.value,
                )
                for item in request.base_scenario.technology_authorities
            ),
            key=lambda item: item.technology_binding_id,
        )
    )
    binding = AuthoredScenarioPathBinding(
        config_id=request.base_scenario.config_id,
        config_version=request.base_scenario.config_version,
        authority_source_id=request.base_scenario.authority_source_id,
        repository_relative_path="scenarios/d3b1_fixture.json",
        source_file_sha256=source_digest,
        resolved_config_sha256=request.base_scenario.resolved_config_sha256,
        project_case_sha256=resolved_config_sha256(
            project_case.model_dump(mode="json")
        ),
        evaluation_request_sha256=resolved_config_sha256(
            request.model_dump(mode="json")
        ),
        jurisdiction_domains=jurisdiction_domains,
        technology_bindings=technology_bindings,
        evidence_cutoff=request.scope.evidence_cutoff,
        evidence_cutoff_authority_source_id="source:project-basis",
        valuation_date=request.scope.valuation_date,
        valuation_authority_source_id="source:project-basis",
        price_basis_id=request.scope.price_basis_id,
        price_nominality=request.scope.price_nominality.value,
        reporting_currency=request.scope.reporting_currency,
    )
    authority = AuthoredScenarioPathAuthority(
        authority_id=_AUTHORITY_ID,
        repository_root=str(root),
        bindings=(binding,),
    )
    monkeypatch.setattr(
        execution,
        "_AUTHORED_SCENARIO_AUTHORITIES",
        MappingProxyType({_AUTHORITY_ID: authority}),
    )
    return _Bundle(project_case, request, authority, source_path, authored)


def _gateway_result(
    raw_config: dict[str, Any], overrides: dict[str, Any], *, degraded: bool = False
) -> dict[str, Any]:
    evaluated = copy.deepcopy(raw_config)
    if overrides:
        evaluated.setdefault("run", {}).update(overrides["run"])
    manifest = {
        "config_sha256": resolved_config_sha256(evaluated),
        "engine_version": "15.4.0",
        "git_sha": "a" * 40,
        "generated_at": "2026-08-31T00:00:00+00:00",
        "seed": None,
        "validation_mode": "strict",
        "manifest_schema_version": "1.0",
    }
    kpis = {
        "project_irr": 0.1,
        "project_npv": 1_000.0,
        "min_dscr": 1.2,
        "max_debt_usd": 100.0,
    }
    annual_rows = [{"year": 1.0, "nullable": None}]
    debt_result = {
        "debt_total": 100.0,
        "min_dscr": 1.2,
        "dscr_by_year": {1.0: 1.2},
    }
    scenario_result = {
        "scenario_name": evaluated["scenario_name"],
        "config_path": "<inline>",
        "project_npv": 1_000.0,
        "project_irr": 0.1,
        "dscr_series": [1.2],
        "min_dscr": 1.2,
        "max_debt_usd": 100.0,
        "validation_mode": "strict",
        "config": evaluated,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "kpis": kpis,
        "metadata": {"oracle": "controlled"},
        "nullable": None,
    }
    return {
        "status": "success",
        "config_path": "<inline>",
        "validation_mode": "strict",
        "scenario_result": scenario_result,
        "kpis": kpis,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "equity_distribution": {"status": "disabled"},
        "metrics": {},
        "fx_integration": {
            "attempted": True,
            "succeeded": not degraded,
            "warning": "bounded warning" if degraded else None,
            "degraded": degraded,
            "degraded_reasons": ["pinned fallback"] if degraded else [],
        },
        "run_manifest": manifest,
    }


def _install_gateway(
    monkeypatch: pytest.MonkeyPatch,
    implementation: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return implementation(**kwargs)

    monkeypatch.setattr(evaluation_v14, "evaluate_with_overrides", spy)
    return calls


def test_constructive_path_is_one_call_and_returns_immutable_complete_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    emitted: list[dict[str, Any]] = []

    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        emitted.append(result)
        return result

    calls = _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )

    assert type(result) is D3BExecutionSuccess
    assert result.outcome == "success"
    authority_binding = bundle.authority.bindings[0]
    assert result.project_case_sha256 == authority_binding.project_case_sha256
    assert (
        result.evaluation_request_sha256 == authority_binding.evaluation_request_sha256
    )
    assert result.model_dump()["project_case_sha256"] == (
        authority_binding.project_case_sha256
    )
    assert result.model_dump()["evaluation_request_sha256"] == (
        authority_binding.evaluation_request_sha256
    )
    assert len(calls) == 1
    assert calls[0]["overrides"] == {"run": {"mode": "screening"}}
    assert calls[0]["validation_modules"] == ["cashflow", "debt"]
    assert calls[0]["return_full_result"] is True
    assert "config_path" not in calls[0]
    assert calls[0]["raw_config"]["meta"]["source_path"] == (
        "scenarios/d3b1_fixture.json"
    )
    assert result.full_result["annual_rows"][0]["nullable"] is None
    assert (
        result.full_result["annual_rows"]
        is result.full_result["scenario_result"]["annual_rows"]
    )
    assert result.full_result["debt_result"]["dscr_by_year"][1.0] == 1.2
    assert 1.0 in result.model_dump()["full_result"]["debt_result"]["dscr_by_year"]
    assert result.full_result["run_manifest"] is result.run_manifest
    receipt_ids = {item.assertion_id for item in result.numeric_projection_receipts}
    assert receipt_ids == {
        "assertion:project-capacity",
        "assertion:wind-capacity",
        "assertion:capex",
        "assertion:opex",
    }
    assert all(
        item.authored_values
        and all(
            value.binary64_hex == item.projected_binary64_hex
            for value in item.authored_values
        )
        for item in result.numeric_projection_receipts
    )

    emitted[0]["annual_rows"][0]["nullable"] = "mutated"
    emitted[0]["run_manifest"]["engine_version"] = "mutated"
    assert result.full_result["annual_rows"][0]["nullable"] is None
    assert result.run_manifest["engine_version"] == "15.4.0"
    with pytest.raises(TypeError):
        result.full_result["new"] = "forbidden"  # type: ignore[index]
    with pytest.raises(ValueError, match="recursively frozen"):
        replace(
            result,
            full_result=result.model_dump()["full_result"],
            run_manifest=result.model_dump()["run_manifest"],
        )
    with pytest.raises(ValueError, match="closed request vocabulary"):
        replace(result, validation_modules=("cashflow", "debt", "rogue"))
    with pytest.raises(ValueError, match="closed request vocabulary"):
        replace(result, validation_modules=("cashflow", "debt", "x" * 1_000_001))
    with pytest.raises(ValueError, match="must be canonical"):
        replace(
            result,
            numeric_projection_receipts=(result.numeric_projection_receipts[0],)
            * 1_025,
        )


def test_success_constructor_detaches_caller_owned_proxy_backings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1

    retained_backings: dict[tuple[Any, ...], dict[Any, Any]] = {}

    def caller_freeze(value: Any, path: tuple[Any, ...] = ()) -> Any:
        if type(value) is dict:
            backing: dict[Any, Any] = {}
            retained_backings[path] = backing
            proxy = MappingProxyType(backing)
            for key, item in value.items():
                backing[key] = caller_freeze(item, path + (key,))
            return proxy
        if type(value) is list:
            return tuple(
                caller_freeze(item, path + (index,)) for index, item in enumerate(value)
            )
        return value

    caller_full_result = caller_freeze(result.model_dump()["full_result"])
    assert isinstance(caller_full_result, MappingProxyType)
    caller_run_manifest = caller_full_result["run_manifest"]
    assert isinstance(caller_run_manifest, MappingProxyType)

    detached = replace(
        result,
        full_result=caller_full_result,
        run_manifest=caller_run_manifest,
    )
    before = detached.model_dump()
    assert detached.full_result is not caller_full_result
    assert detached.run_manifest is not caller_run_manifest
    assert detached.full_result["run_manifest"] is detached.run_manifest

    retained_backings[("annual_rows", 0)]["nullable"] = "MUTATED_AFTER_VALIDATION"
    retained_backings[("run_manifest",)]["engine_version"] = "MUTATED_AFTER_VALIDATION"
    retained_backings[()]["run_manifest"] = MappingProxyType(
        {"engine_version": "REPLACED_AFTER_VALIDATION"}
    )

    assert detached.model_dump() == before
    assert detached.full_result["annual_rows"][0]["nullable"] is None
    assert detached.run_manifest["engine_version"] == "15.4.0"
    assert detached.full_result["run_manifest"] is detached.run_manifest


def test_success_constructor_preserves_safe_aliases_and_refuses_proxy_cycles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess

    shared_backing = {"value": 1.0}
    caller_shared = MappingProxyType(shared_backing)
    manifest_backing = {"seed": 42}
    caller_manifest = MappingProxyType(manifest_backing)
    full_backing = {
        "first": caller_shared,
        "second": caller_shared,
        "run_manifest": caller_manifest,
    }
    caller_full = MappingProxyType(full_backing)
    detached = replace(
        result,
        full_result=caller_full,
        run_manifest=caller_manifest,
    )
    assert detached.full_result["first"] is detached.full_result["second"]
    shared_backing["value"] = 2.0
    assert detached.full_result["first"]["value"] == 1.0

    cyclic_manifest_backing: dict[str, Any] = {"seed": 42}
    cyclic_manifest = MappingProxyType(cyclic_manifest_backing)
    cyclic_full_backing = {"run_manifest": cyclic_manifest}
    cyclic_full = MappingProxyType(cyclic_full_backing)
    cyclic_manifest_backing["cycle"] = cyclic_full
    with pytest.raises(ValueError, match="recursively frozen"):
        replace(
            result,
            full_result=cyclic_full,
            run_manifest=cyclic_manifest,
        )


def test_decimal_to_binary64_projection_is_exact_and_disclosed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(
        tmp_path,
        monkeypatch,
        project_capacity="0.1",
        authored_capacity=0.1,
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    capacity_receipts = tuple(
        item
        for item in result.numeric_projection_receipts
        if item.assertion_id
        in {"assertion:project-capacity", "assertion:wind-capacity"}
    )
    assert len(capacity_receipts) == 2
    assert {item.project_decimal for item in capacity_receipts} == {"0.1"}
    assert {item.projected_binary64_hex for item in capacity_receipts} == {
        float(0.1).hex()
    }
    assert all(
        value.json_type == "binary64"
        for item in capacity_receipts
        for value in item.authored_values
    )
    assert len(calls) == 1


def test_adjacent_binary64_value_is_zero_call_compatibility_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(
        tmp_path,
        monkeypatch,
        project_capacity="0.1",
        authored_capacity=math.nextafter(0.1, 1.0),
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.COMPATIBILITY_MISMATCH
    assert result.failure.gateway_call_count == 0
    assert calls == []


@pytest.mark.parametrize("periodicity", ["monthly", "per_event"])
def test_nonannual_opex_is_zero_call_dimension_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, periodicity: str
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, opex_periodicity=periodicity)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.COMPATIBILITY_MISMATCH
    assert result.failure.gateway_call_count == 0
    assert calls == []


@pytest.mark.parametrize(
    ("json_type", "authored_value", "binary64_hex"),
    [
        ("integer", "999", float(1).hex()),
        ("integer", "01", float(1).hex()),
        ("integer", "-0", float(-0.0).hex()),
        ("binary64", "1.00", float(1).hex()),
        ("binary64", "1e9999", float("inf").hex()),
        ("binary64", "-0.0", float(0.0).hex()),
    ],
)
def test_authored_numeric_disclosure_refuses_false_or_noncanonical_text(
    json_type: str, authored_value: str, binary64_hex: str
) -> None:
    with pytest.raises(ValueError):
        D3BAuthoredNumericValue(
            json_type=json_type,  # type: ignore[arg-type]
            authored_value=authored_value,
            binary64_hex=binary64_hex,
        )


def test_numeric_projection_receipt_refuses_forged_authored_value() -> None:
    with pytest.raises(ValueError):
        D3BNumericProjectionReceipt(
            assertion_id="assertion:forged",
            project_decimal="1",
            projected_binary64_hex=float(1).hex(),
            authored_values=(
                D3BAuthoredNumericValue(
                    json_type="integer",
                    authored_value="2",
                    binary64_hex=float(2).hex(),
                ),
            ),
        )


def test_numeric_projection_receipt_is_bounded_and_dumps_plain_values() -> None:
    authored = D3BAuthoredNumericValue(
        json_type="integer",
        authored_value="1",
        binary64_hex=float(1).hex(),
    )
    receipt = D3BNumericProjectionReceipt(
        assertion_id="assertion:bounded-dump",
        project_decimal="1",
        projected_binary64_hex=float(1).hex(),
        authored_values=(authored,),
    )
    dumped = receipt.model_dump()
    assert dumped["authored_values"] == [
        {
            "json_type": "integer",
            "authored_value": "1",
            "binary64_hex": float(1).hex(),
        }
    ]
    assert type(dumped["authored_values"]) is list
    assert type(dumped["authored_values"][0]) is dict

    with pytest.raises(ValueError, match="authored numeric values"):
        D3BNumericProjectionReceipt(
            assertion_id="assertion:too-many-authored-values",
            project_decimal="1",
            projected_binary64_hex=float(1).hex(),
            authored_values=(authored, authored, authored),
        )


def test_numeric_projection_helper_refuses_every_unrepresentable_shape() -> None:
    class OverflowingDecimal:
        def __float__(self) -> float:
            raise OverflowError("controlled projection overflow")

    assert (
        execution._numeric_projection_receipt(
            "assertion:overflow",
            OverflowingDecimal(),  # type: ignore[arg-type]
            [1.0],
        )
        is None
    )
    assert (
        execution._numeric_projection_receipt(
            "assertion:nonfinite", Decimal("1e999999"), [1.0]
        )
        is None
    )
    assert (
        execution._numeric_projection_receipt(
            "assertion:underflow", Decimal("1e-999999"), [0.0]
        )
        is None
    )
    assert (
        execution._numeric_projection_receipt(
            "assertion:integer-mismatch", Decimal("1"), [2]
        )
        is None
    )
    assert (
        execution._numeric_projection_receipt(
            "assertion:unsupported", Decimal("1"), [object()]
        )
        is None
    )
    assert (
        execution._numeric_projection_receipt("assertion:absent", Decimal("1"), [])
        is None
    )


def test_low_level_exact_helpers_fail_closed_on_hostile_types() -> None:
    assert execution._rational("1") is None
    assert execution._all_equal_exact([]) is False
    assert execution._all_equal_exact(["same", "same"]) is True
    assert execution._all_equal_exact(["same", 1]) is False
    with pytest.raises(TypeError, match="non-canonical material value"):
        execution._material_decimal(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="non-canonical material value"):
        execution._material_unit(object())  # type: ignore[arg-type]

    long_named_error = type("X" * 161, (Exception,), {})()
    failure = execution._failure(
        None,
        D3BFailureCode.INVALID_INPUT_TYPE,
        D3BExecutionPhase.REQUEST,
        cause=long_named_error,
    )
    assert failure.failure.cause_type == "ExternalError"


@pytest.mark.parametrize(
    ("project_decimal", "json_type", "authored_value", "binary64_hex"),
    [
        ("1E-1000", "binary64", "0.0", float(0.0).hex()),
        ("-1E-1000", "binary64", "-0.0", float(-0.0).hex()),
        (
            "9007199254740993",
            "integer",
            "9007199254740992",
            float(9007199254740992).hex(),
        ),
        ("0", "binary64", "-0.0", float(-0.0).hex()),
    ],
)
def test_numeric_projection_contract_refuses_semantic_binary64_collapse(
    project_decimal: str,
    json_type: str,
    authored_value: str,
    binary64_hex: str,
) -> None:
    authored = D3BAuthoredNumericValue(
        json_type=json_type,  # type: ignore[arg-type]
        authored_value=authored_value,
        binary64_hex=binary64_hex,
    )
    with pytest.raises(ValueError):
        D3BNumericProjectionReceipt(
            assertion_id="assertion:semantic-collapse",
            project_decimal=project_decimal,
            projected_binary64_hex=binary64_hex,
            authored_values=(authored,),
        )


@pytest.mark.parametrize("binary64_hex", [None, "0x1p+9999999", "x" * 257])
def test_numeric_projection_hex_parser_has_bounded_typed_refusals(
    binary64_hex: Any,
) -> None:
    with pytest.raises(ValueError):
        D3BNumericProjectionReceipt(
            assertion_id="assertion:invalid-hex",
            project_decimal="1",
            projected_binary64_hex=binary64_hex,
            authored_values=(
                D3BAuthoredNumericValue(
                    json_type="integer",
                    authored_value="1",
                    binary64_hex=float(1).hex(),
                ),
            ),
        )
    with pytest.raises(ValueError):
        D3BAuthoredNumericValue(
            json_type="integer",
            authored_value="1",
            binary64_hex=binary64_hex,
        )


def test_common_poi_wind_bess_reconciles_without_revenue_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, include_storage=True)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1
    assert calls[0]["raw_config"]["generation"]["technologies"]["bess"] == {
        "power_mw": 2.5,
        "energy_mwh": 10,
        "duration_h": 4,
    }
    assert (
        "revenue_stream"
        not in calls[0]["raw_config"]["generation"]["technologies"]["bess"]
    )
    assert {item.assertion_id for item in result.numeric_projection_receipts} >= {
        "assertion:bess-power",
        "assertion:bess-energy",
        "assertion:bess-duration",
    }


def test_storage_only_case_is_constructively_reconciled_without_generation_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, storage_only=True)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1
    assert set(calls[0]["raw_config"]["generation"]["technologies"]) == {"bess"}
    assert {item.assertion_id for item in result.numeric_projection_receipts} >= {
        "assertion:bess-power",
        "assertion:bess-energy",
        "assertion:bess-duration",
    }
    assert not any(
        item.assertion_id.startswith("assertion:wind")
        for item in result.numeric_projection_receipts
    )


def test_legacy_single_wind_turbine_shape_is_explicitly_reconciled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, legacy_turbine_shape=True)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1
    assert "generation" not in calls[0]["raw_config"]
    assert calls[0]["raw_config"]["turbine"] == {
        "n_turbines": 2,
        "rated_power_mw": 50.0,
        "total_capacity_mw": 100,
    }
    assert {item.assertion_id for item in result.numeric_projection_receipts} >= {
        "assertion:turbine-count",
        "assertion:turbine-rated-power",
        "assertion:turbine-total-capacity",
    }


def test_solar_dc_capacity_does_not_collapse_to_project_ac_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, solar_dc=True)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1
    assert calls[0]["raw_config"]["resource"]["solar"]["dc_capacity_mw"] == 100
    assert {item.assertion_id for item in result.numeric_projection_receipts} >= {
        "assertion:wind-capacity"
    }
    assert "assertion:project-capacity" not in {
        item.assertion_id for item in result.numeric_projection_receipts
    }


def test_storage_power_duration_energy_mismatch_is_zero_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(
        tmp_path,
        monkeypatch,
        include_storage=True,
        bess_energy_mwh=9,
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.AUTHORED_REDUNDANCY_MISMATCH
    assert result.failure.gateway_call_count == 0
    assert calls == []


def test_unrelated_declared_missing_input_remains_outside_v1_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, missing_field="capex_quantity")
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1


def test_compatibility_selected_missing_input_is_typed_zero_call_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, missing_field="generation_capacity")
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.MISSING_MATERIAL_VALUE
    assert result.failure.gateway_call_count == 0
    assert calls == []


def test_degraded_success_preserves_warning_none_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(
            kwargs["raw_config"], kwargs["overrides"], degraded=True
        ),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert result.outcome == "degraded_success"
    assert result.fx_degraded is True
    assert result.warnings == ("bounded warning", "pinned fallback")
    assert result.full_result["scenario_result"]["nullable"] is None
    assert len(calls) == 1


def test_real_public_gateway_oracle_preserves_full_current_v14_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert result.gateway_call_count == 1
    assert result.run_manifest["config_sha256"] == result.evaluated_config_sha256
    assert result.run_manifest["validation_mode"] == "strict"
    assert len(result.full_result["annual_rows"]) == 25
    assert result.full_result["debt_result"]["dscr_by_year"]
    assert type(next(iter(result.full_result["debt_result"]["dscr_by_year"]))) is float
    scenario_result = result.full_result["scenario_result"]
    assert scenario_result["metadata"]["equity_distribution_status"] == "computed"
    assert scenario_result["cashflow"] is None
    assert scenario_result["wacc"] is None


@pytest.mark.parametrize(
    ("scenario_name", "legacy_run_alias", "expected"),
    [
        (False, False, D3BFailureCode.COMPATIBILITY_MISMATCH),
        (True, True, D3BFailureCode.RUN_POSTURE_INVALID),
    ],
)
def test_identity_fallback_and_legacy_run_alias_are_zero_call_refusals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario_name: bool,
    legacy_run_alias: bool,
    expected: D3BFailureCode,
) -> None:
    bundle = _bundle(
        tmp_path,
        monkeypatch,
        scenario_name=scenario_name,
        legacy_run_alias=legacy_run_alias,
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is expected
    assert result.failure.gateway_call_count == 0
    assert calls == []


def test_matching_canonical_run_mode_uses_empty_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, canonical_run_mode=True)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1
    assert calls[0]["overrides"] == {}


def test_code_owned_authority_facts_cannot_be_replaced_by_request_digest_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    original = bundle.authority.bindings[0]
    first_domain, *remaining = original.jurisdiction_domains
    wrong_binding = replace(
        original,
        jurisdiction_domains=(
            replace(first_domain, jurisdiction_code="LKA"),
            *remaining,
        ),
    )
    wrong_authority = replace(bundle.authority, bindings=(wrong_binding,))
    monkeypatch.setattr(
        execution,
        "_AUTHORED_SCENARIO_AUTHORITIES",
        MappingProxyType({_AUTHORITY_ID: wrong_authority}),
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.SCENARIO_AUTHORITY_MISMATCH
    assert result.failure.gateway_call_count == 0
    assert calls == []


@pytest.mark.parametrize(
    "jurisdiction_overrides",
    [
        {"tariff_jurisdiction": "LKA"},
        {"debt_jurisdiction": "LKA"},
    ],
)
def test_non_site_authored_jurisdiction_mismatch_is_zero_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    jurisdiction_overrides: dict[str, str],
) -> None:
    bundle = _bundle(tmp_path, monkeypatch, **jurisdiction_overrides)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.COMPATIBILITY_MISMATCH
    assert result.failure.gateway_call_count == 0
    assert calls == []


@pytest.mark.parametrize("reverse", [False, True])
def test_multi_jurisdiction_same_subject_is_binding_keyed_and_order_independent(
    reverse: bool,
) -> None:
    config = _authored_config(debt_jurisdiction="ALT")
    digest = resolved_config_sha256(config)
    request = _request(
        source_digest="a" * 64,
        resolved_digest=digest,
        multi_financing_jurisdiction=True,
        reverse_subject_authorities=reverse,
    )
    assert execution._authored_jurisdictions_match(config, request) is True


@pytest.mark.parametrize(
    "path",
    [
        "scenarios//d3b1_fixture.yaml",
        "scenarios/./d3b1_fixture.yaml",
        "scenarios/d3b1_fixture.YAML",
        "outside/d3b1_fixture.yaml",
    ],
)
def test_authority_path_requires_exact_normalized_scenario_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="normalized relative path"):
        replace(bundle.authority.bindings[0], repository_relative_path=path)


def test_authority_lookup_and_path_resolution_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    binding = bundle.authority.bindings[0]
    wrong_source = replace(binding, authority_source_id="source:wrong-authority")
    wrong_authority = replace(bundle.authority, bindings=(wrong_source,))
    assert execution._binding_for_request(bundle.request, wrong_authority) is None

    class EmptyAuthority:
        bindings: tuple[Any, ...] = ()

    assert execution._binding_for_request(bundle.request, EmptyAuthority()) is None  # type: ignore[arg-type]

    root = Path(bundle.authority.repository_root)
    root_link = tmp_path / "root-link"
    root_link.symlink_to(root, target_is_directory=True)
    linked_authority = replace(bundle.authority, repository_root=str(root_link))
    with pytest.raises(ValueError, match="exact real path"):
        execution._resolve_authorized_file(linked_authority, binding)

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "fixture.json").write_text("{}", encoding="utf-8")
    inner_link = root / "scenarios" / "linked"
    inner_link.symlink_to(outside, target_is_directory=True)
    linked_binding = replace(
        binding, repository_relative_path="scenarios/linked/fixture.json"
    )
    with pytest.raises(ValueError, match="symbolic link"):
        execution._resolve_authorized_file(bundle.authority, linked_binding)

    directory_as_json = root / "scenarios" / "directory.json"
    directory_as_json.mkdir()
    directory_binding = replace(
        binding, repository_relative_path="scenarios/directory.json"
    )
    with pytest.raises(ValueError, match="not a file"):
        execution._resolve_authorized_file(bundle.authority, directory_binding)


def test_descriptor_open_refuses_relative_path_and_missing_platform_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="absolute file path"):
        execution._open_no_follow(Path("relative.json"))
    monkeypatch.setattr(execution.os, "O_NOFOLLOW", None)
    with pytest.raises(OSError, match="lacks descriptor-anchored"):
        execution._open_no_follow(Path("/tmp/scenario.json"))


def test_authority_subject_vocabulary_is_exhaustive() -> None:
    assert {item.value for item in JurisdictionSubject} == {
        "site",
        "corporate",
        "contract",
        "grid",
        "permit",
        "tax",
        "accounting",
        "financing",
        "supply",
    }
    for subject in JurisdictionSubject:
        value = D3BAuthorizedJurisdictionDomain(
            jurisdiction_binding_id=f"jurisdiction-binding:{subject.value}",
            jurisdiction_code="FIC",
            subject=subject.value,  # type: ignore[arg-type]
            base_domain="project_lifecycle_timeline",
        )
        assert value.subject == subject.value


def test_authority_matching_exception_is_typed_zero_call_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    cause = ValueError("SECRET AUTHORITY DETAIL")
    monkeypatch.setattr(
        execution,
        "_authority_binding_matches",
        lambda *args, **kwargs: (_ for _ in ()).throw(cause),
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.SCENARIO_AUTHORITY_MISMATCH
    assert result.failure.gateway_call_count == 0
    assert result.cause is cause
    assert "SECRET" not in json.dumps(result.model_dump())
    assert calls == []


@pytest.mark.parametrize(
    ("target", "expected_code", "expected_phase"),
    [
        (
            "_project_case_reference_matches",
            D3BFailureCode.PROJECT_CASE_IDENTITY_MISMATCH,
            D3BExecutionPhase.REQUEST,
        ),
        (
            "_binding_for_request",
            D3BFailureCode.SCENARIO_AUTHORITY_NOT_FOUND,
            D3BExecutionPhase.AUTHORITY,
        ),
        (
            "_authority_binding_matches",
            D3BFailureCode.SCENARIO_AUTHORITY_MISMATCH,
            D3BExecutionPhase.AUTHORITY,
        ),
        (
            "_resolve_authorized_file",
            D3BFailureCode.SCENARIO_PATH_INVALID,
            D3BExecutionPhase.AUTHORITY,
        ),
        (
            "_nested",
            D3BFailureCode.RESOLVED_CONFIG_DIGEST_MISMATCH,
            D3BExecutionPhase.CONFIG_LOAD,
        ),
        (
            "_live_material_counts",
            D3BFailureCode.COMPATIBILITY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
        ),
        (
            "_live_element_sets_match",
            D3BFailureCode.PROJECT_CASE_ELEMENT_SET_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
        ),
        (
            "_authored_redundancies_match",
            D3BFailureCode.AUTHORED_REDUNDANCY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
        ),
        (
            "_compatibility_receipts",
            D3BFailureCode.COMPATIBILITY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
        ),
    ],
)
def test_preflight_memory_failures_are_typed_zero_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    expected_code: D3BFailureCode,
    expected_phase: D3BExecutionPhase,
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    cause = MemoryError(f"simulated {target} allocation failure")
    monkeypatch.setattr(
        execution,
        target,
        lambda *args, **kwargs: (_ for _ in ()).throw(cause),
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is expected_code
    assert result.failure.phase is expected_phase
    assert result.failure.gateway_call_count == 0
    assert result.cause is cause
    assert calls == []


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("invalid_input", D3BFailureCode.INVALID_INPUT_TYPE),
        ("missing_authority", D3BFailureCode.SCENARIO_AUTHORITY_NOT_FOUND),
        ("identity_mismatch", D3BFailureCode.PROJECT_CASE_IDENTITY_MISMATCH),
        ("binding_missing", D3BFailureCode.SCENARIO_AUTHORITY_NOT_FOUND),
        ("path_error", D3BFailureCode.SCENARIO_PATH_INVALID),
        ("source_digest", D3BFailureCode.SOURCE_FILE_DIGEST_MISMATCH),
        ("second_read", D3BFailureCode.CONFIG_LOAD_FAILED),
        ("loaded_digest", D3BFailureCode.RESOLVED_CONFIG_DIGEST_MISMATCH),
        ("source_path", D3BFailureCode.RESOLVED_CONFIG_DIGEST_MISMATCH),
        ("unbound", D3BFailureCode.UNBOUND_MATERIAL_PRESENT),
        ("element_set", D3BFailureCode.PROJECT_CASE_ELEMENT_SET_MISMATCH),
        ("redundancy", D3BFailureCode.AUTHORED_REDUNDANCY_MISMATCH),
        ("snapshot", D3BFailureCode.RESULT_SNAPSHOT_FAILED),
    ],
)
def test_executor_fail_closed_branches_are_typed_and_zero_or_one_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_code: D3BFailureCode,
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    authority_id = _AUTHORITY_ID
    project_case: Any = bundle.project_case
    request = bundle.request
    original_nested = execution._nested
    original_receipt = execution._file_receipt

    if mode == "invalid_input":
        project_case = object()
    elif mode == "missing_authority":
        authority_id = "authority:missing"
    elif mode == "identity_mismatch":
        monkeypatch.setattr(
            execution, "_project_case_reference_matches", lambda *args: False
        )
    elif mode == "binding_missing":
        monkeypatch.setattr(execution, "_binding_for_request", lambda *args: None)
    elif mode == "path_error":
        monkeypatch.setattr(
            execution,
            "_resolve_authorized_file",
            lambda *args: (_ for _ in ()).throw(ValueError("controlled path error")),
        )
    elif mode == "source_digest":
        source_bytes = bundle.source_path.read_bytes()
        monkeypatch.setattr(
            execution,
            "_file_receipt",
            lambda path: (source_bytes, "0" * 64, (1, 1, len(source_bytes), 1)),
        )
    elif mode == "second_read":
        receipt_calls = 0

        def fail_second_receipt(
            path: Path,
        ) -> tuple[bytes, str, tuple[int, int, int, int]]:
            nonlocal receipt_calls
            receipt_calls += 1
            if receipt_calls == 2:
                raise ValueError("controlled second read failure")
            return original_receipt(path)

        monkeypatch.setattr(execution, "_file_receipt", fail_second_receipt)
    elif mode == "loaded_digest":
        drifted = copy.deepcopy(bundle.authored_config)
        drifted["controlled_drift"] = True
        monkeypatch.setattr(
            "analytics.scenario_loader.load_scenario_config",
            lambda *args, **kwargs: drifted,
        )
    elif mode == "source_path":

        def wrong_source_path(config: Any, *path: str) -> Any:
            if path == ("meta", "source_path"):
                return "scenarios/wrong.json"
            return original_nested(config, *path)

        monkeypatch.setattr(execution, "_nested", wrong_source_path)
    elif mode == "unbound":
        dispositions = list(request.binding_policy.material_dispositions)
        dispositions[0] = dispositions[0].model_copy(
            update={"disposition": MaterialDispositionKind.REFUSE_UNBOUND}
        )
        request = request.model_copy(
            update={
                "binding_policy": request.binding_policy.model_copy(
                    update={"material_dispositions": tuple(dispositions)}
                )
            }
        )
        monkeypatch.setattr(execution, "_authority_binding_matches", lambda *args: True)
        monkeypatch.setattr(
            execution,
            "_live_material_counts",
            lambda project_case: dict.fromkeys(ProjectCaseMaterialCategory, 1),
        )
    elif mode == "element_set":
        monkeypatch.setattr(execution, "_live_element_sets_match", lambda *args: False)
    elif mode == "redundancy":
        monkeypatch.setattr(
            execution,
            "_authored_redundancies_match",
            lambda *args: (_ for _ in ()).throw(ValueError("controlled mismatch")),
        )
    elif mode == "snapshot":
        monkeypatch.setattr(
            execution,
            "D3BExecutionSuccess",
            lambda **kwargs: (_ for _ in ()).throw(ValueError("controlled snapshot")),
        )
    else:  # pragma: no cover - parametrization is closed above
        raise AssertionError(mode)

    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=project_case,
        request=request,
        scenario_authority_id=authority_id,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is expected_code
    assert result.failure.gateway_call_count == (1 if mode == "snapshot" else 0)
    assert len(calls) == (1 if mode == "snapshot" else 0)


def test_verified_loader_bytes_bind_parsing_to_the_hashed_source(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "scenario.json"
    original = _authored_config()
    original["meta"]["source_path"] = "scenarios/d3b1_fixture.json"
    verified_bytes = json.dumps(original, sort_keys=True).encode("utf-8")
    source_path.write_bytes(b'{"wrong": "replacement"}')
    loaded = load_scenario_config(
        source_path,
        verified_bytes=verified_bytes,
        allow_external_approved_sources=False,
    )
    assert loaded["scenario_name"] == original["scenario_name"]
    assert loaded["project"] == original["project"]


def test_d3b_loader_refuses_external_manifest_before_global_registration(
    tmp_path: Path,
) -> None:
    from analytics.loader.aep_loader import APPROVED_SOURCES

    source_path = tmp_path / "scenario.json"
    authored = _authored_config()
    authored.setdefault("resource", {})["power_curve"] = {
        "approved_sources_yaml": "/tmp/unbound-approved-sources.yaml"
    }
    verified_bytes = json.dumps(authored, sort_keys=True).encode("utf-8")
    source_path.write_bytes(verified_bytes)
    before = copy.deepcopy(APPROVED_SOURCES)
    with pytest.raises(ScenarioConfigError, match="external approved-sources"):
        load_scenario_config(
            source_path,
            verified_bytes=verified_bytes,
            allow_external_approved_sources=False,
        )
    assert APPROVED_SOURCES == before


def test_d3b_loader_does_not_inherit_ambient_registered_aep_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from analytics.loader.aep_loader import APPROVED_SOURCES

    rogue_source_id = "ROGUE_SOURCE_REGISTERED_BY_AN_EARLIER_CALL"
    monkeypatch.setitem(
        APPROVED_SOURCES,
        rogue_source_id,
        {
            "type": "OEM",
            "description": "Ambient process-global source",
            "iec_standard": "61400-12-1:2022",
        },
    )
    source_path = tmp_path / "scenario.json"
    authored = _authored_config()
    authored.setdefault("resource", {})["power_curve"] = {"source_id": rogue_source_id}
    verified_bytes = json.dumps(authored, sort_keys=True).encode("utf-8")
    source_path.write_bytes(verified_bytes)

    with pytest.raises(AepProvenanceError, match="not lender-grade"):
        load_scenario_config(
            source_path,
            verified_bytes=verified_bytes,
            allow_external_approved_sources=False,
        )


def test_loader_exception_is_typed_zero_call_and_exact_bytes_are_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    cause = ValueError("SECRET LOADER DETAIL")

    def rejecting_loader(path: Path, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["verified_bytes"] == bundle.source_path.read_bytes()
        assert kwargs["allow_external_approved_sources"] is False
        raise cause

    monkeypatch.setattr(
        "analytics.scenario_loader.load_scenario_config", rejecting_loader
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.CONFIG_LOAD_FAILED
    assert result.failure.gateway_call_count == 0
    assert result.cause is cause
    assert "SECRET" not in json.dumps(result.model_dump())
    assert calls == []


def test_source_read_memory_failure_is_typed_zero_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    cause = MemoryError("simulated bounded source-read failure")
    monkeypatch.setattr(
        execution,
        "_file_receipt",
        lambda path: (_ for _ in ()).throw(cause),
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.SCENARIO_FILE_UNAVAILABLE
    assert result.failure.gateway_call_count == 0
    assert result.cause is cause
    assert calls == []


def test_oversized_authored_source_is_typed_zero_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    with bundle.source_path.open("r+b") as file_obj:
        file_obj.truncate(execution._MAX_AUTHORED_SCENARIO_BYTES + 1)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.SCENARIO_FILE_UNAVAILABLE
    assert result.failure.gateway_call_count == 0
    assert calls == []


def test_final_component_symlink_swap_before_open_is_typed_zero_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    original_resolver = execution._resolve_authorized_file

    def swapping_resolver(*args: Any, **kwargs: Any) -> Path:
        source_path = original_resolver(*args, **kwargs)
        target_path = source_path.with_name("same-bytes-target.json")
        source_path.replace(target_path)
        source_path.symlink_to(target_path.name)
        return source_path

    monkeypatch.setattr(execution, "_resolve_authorized_file", swapping_resolver)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.SCENARIO_FILE_UNAVAILABLE
    assert result.failure.gateway_call_count == 0
    assert calls == []


def test_intermediate_directory_symlink_swap_before_open_is_typed_zero_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    original_resolver = execution._resolve_authorized_file

    def swapping_resolver(*args: Any, **kwargs: Any) -> Path:
        source_path = original_resolver(*args, **kwargs)
        scenarios_path = source_path.parent
        target_path = scenarios_path.with_name("same-files-target")
        scenarios_path.replace(target_path)
        scenarios_path.symlink_to(target_path.name)
        return source_path

    monkeypatch.setattr(execution, "_resolve_authorized_file", swapping_resolver)
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.SCENARIO_FILE_UNAVAILABLE
    assert result.failure.gateway_call_count == 0
    assert calls == []


def test_path_replacement_after_verified_load_is_typed_zero_call_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    original_loader = load_scenario_config

    def replacing_loader(path: Path, **kwargs: Any) -> dict[str, Any]:
        loaded = original_loader(path, **kwargs)
        path.write_bytes(b'{"replacement": true}')
        return loaded

    monkeypatch.setattr(
        "analytics.scenario_loader.load_scenario_config", replacing_loader
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.CONFIG_CHANGED_DURING_LOAD
    assert result.failure.gateway_call_count == 0
    assert calls == []


def test_schema_failure_is_typed_zero_call_and_preserves_nonserialized_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    secret = "SECRET CONFIG BODY"
    cause = ValueError(secret)
    monkeypatch.setattr(
        "analytics.schema_guard.validate_config_for_v14",
        lambda *args, **kwargs: (_ for _ in ()).throw(cause),
    )
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.CONFIG_VALIDATION_FAILED
    assert result.failure.gateway_call_count == 0
    assert result.cause is cause
    assert secret not in json.dumps(result.model_dump())
    assert result.model_dump()["failure"]["code"] == "config_validation_failed"
    assert calls == []


def test_gateway_exception_is_one_call_no_retry_and_cause_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    cause = RuntimeError("SECRET ENGINE DETAIL")

    def gateway(**kwargs: Any) -> dict[str, Any]:
        raise cause

    calls = _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.GATEWAY_FAILED
    assert result.failure.gateway_call_count == 1
    assert result.cause is cause
    assert "SECRET" not in json.dumps(result.model_dump())
    assert len(calls) == 1


def test_result_snapshot_memory_failure_is_typed_one_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    cause = MemoryError("simulated bounded result-snapshot failure")
    calls = _install_gateway(
        monkeypatch,
        lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"]),
    )
    monkeypatch.setattr(
        execution,
        "_validate_gateway_result",
        lambda *args, **kwargs: (_ for _ in ()).throw(cause),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.GATEWAY_PROTOCOL_INVALID
    assert result.failure.gateway_call_count == 1
    assert result.cause is cause
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda result: result.update(status="partial"),
        lambda result: result.pop("kpis"),
        lambda result: result["scenario_result"].update(project_npv=1000),
        lambda result: result["run_manifest"].update(validation_mode="relaxed"),
        lambda result: result["run_manifest"].update(config_sha256="0" * 64),
        lambda result: result["run_manifest"].update(config_sha256="not-a-sha"),
        lambda result: result["run_manifest"].update(engine_version=""),
        lambda result: result["run_manifest"].update(git_sha="unknown"),
        lambda result: result["run_manifest"].update(generated_at=""),
        lambda result: result["run_manifest"].update(manifest_schema_version=""),
        lambda result: result["run_manifest"].pop("seed"),
        lambda result: result["fx_integration"].update(attempted=False, succeeded=True),
        lambda result: result.update(
            scenario_result={}, kpis={}, annual_rows=[], debt_result={}
        ),
        lambda result: result.update(annual_rows=[[[[]]]]),
        lambda result: result["scenario_result"].update(
            config={"scenario_name": "conflicting evaluated config"}
        ),
        lambda result: result["scenario_result"].update(annual_rows=[{"year": 999.0}]),
        lambda result: result["scenario_result"].update(
            debt_result={"debt_total": -999.0}
        ),
        lambda result: result["scenario_result"].update(
            kpis={**result["kpis"], "unknown_conflict": -999.0}
        ),
        lambda result: result["scenario_result"].update(config_path="conflict"),
        lambda result: result["scenario_result"].update(validation_mode="relaxed"),
        lambda result: result["scenario_result"].update(project_npv=999.0),
        lambda result: result.update(
            debt_result={
                "debt_total": 100,
                "min_dscr": 1.2,
                "dscr_by_year": {1.0: 1.2},
            },
            scenario_result={
                **result["scenario_result"],
                "debt_result": {
                    "debt_total": 100,
                    "min_dscr": 1.2,
                    "dscr_by_year": {1.0: 1.2},
                },
            },
        ),
        lambda result: result.pop("run_manifest"),
        lambda result: result["run_manifest"].update(engine_version=1),
        lambda result: result["run_manifest"].update(
            generated_at="2026-08-31T00:00:00+05:30"
        ),
        lambda result: result.pop("fx_integration"),
        lambda result: result["fx_integration"].update(attempted=1),
        lambda result: result["fx_integration"].update(warning=1),
        lambda result: result["fx_integration"].update(degraded_reasons=1),
        lambda result: result.update(warnings=[1]),
    ],
)
def test_malformed_gateway_protocol_is_one_call_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, Any]], Any],
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        mutation(result)
        return result

    calls = _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.gateway_call_count == 1
    assert result.failure.code in {
        D3BFailureCode.GATEWAY_PROTOCOL_INVALID,
        D3BFailureCode.RUN_MANIFEST_DIGEST_MISMATCH,
    }
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda result: (
            result["scenario_result"].update(
                annual_rows=copy.deepcopy(result["annual_rows"])
            ),
            result["scenario_result"]["annual_rows"][0].update(year=True),
        ),
        lambda result: (
            result["scenario_result"].update(
                debt_result=copy.deepcopy(result["debt_result"])
            ),
            result["scenario_result"]["debt_result"].update(debt_total=100),
        ),
        lambda result: (
            result["scenario_result"].update(kpis=copy.deepcopy(result["kpis"])),
            result["scenario_result"]["kpis"].update(project_npv=1000),
        ),
        lambda result: (
            result["scenario_result"].update(kpis=copy.deepcopy(result["kpis"])),
            result["kpis"].update(extra_zero=0.0),
            result["scenario_result"]["kpis"].update(extra_zero=-0.0),
        ),
        lambda result: (
            result["scenario_result"].update(
                debt_result=copy.deepcopy(result["debt_result"])
            ),
            result["scenario_result"]["debt_result"].update(dscr_by_year={1: 1.2}),
        ),
    ],
)
def test_gateway_duplicate_surfaces_require_exact_type_and_binary64_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, Any]], Any],
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        mutation(result)
        return result

    calls = _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.GATEWAY_PROTOCOL_INVALID
    assert result.failure.gateway_call_count == 1
    assert len(calls) == 1


def test_gateway_distinct_exact_duplicate_containers_are_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        result["scenario_result"].update(
            annual_rows=copy.deepcopy(result["annual_rows"]),
            debt_result=copy.deepcopy(result["debt_result"]),
            kpis=copy.deepcopy(result["kpis"]),
        )
        return result

    calls = _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(calls) == 1


def test_gateway_requires_canonical_inline_origin_even_when_duplicates_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        result["config_path"] = "scenarios/rogue.yaml"
        result["scenario_result"]["config_path"] = "scenarios/rogue.yaml"
        return result

    calls = _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.GATEWAY_PROTOCOL_INVALID
    assert result.failure.gateway_call_count == 1
    assert len(calls) == 1


def test_result_freezer_refuses_depth_before_python_recursion_limit() -> None:
    nested: Any = None
    for _ in range(2000):
        nested = [nested]
    with pytest.raises(ValueError, match="maximum JSON depth"):
        execution._freeze_json(nested)


def test_result_freezer_preserves_shared_legacy_alias_but_refuses_cycle() -> None:
    shared: list[Any] = [(1.0, 2.0)]
    frozen = execution._freeze_json({"first": shared, "second": shared})
    assert frozen["first"] is frozen["second"]
    assert frozen["first"] == ((1.0, 2.0),)

    cyclic: list[Any] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="cyclic sequence"):
        execution._freeze_json(cyclic)

    cyclic_mapping: dict[str, Any] = {}
    cyclic_mapping["self"] = cyclic_mapping
    with pytest.raises(ValueError, match="cyclic mapping"):
        execution._freeze_json(cyclic_mapping)


def test_result_freezer_enforces_mapping_specific_volume_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(execution, "_MAX_RESULT_CONTAINERS", 1)
    with pytest.raises(ValueError, match="container count"):
        execution._freeze_json({"child": {}})

    monkeypatch.setattr(execution, "_MAX_RESULT_TEXT_CODEPOINTS", 1)
    with pytest.raises(ValueError, match="text volume"):
        execution._freeze_json({"ab": None})


def test_exact_numeric_equality_and_authority_digest_failure_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert execution._all_equal_exact((1, 1.0)) is True
    assert execution._recognized_values(
        {"outer": {"value": 1}}, (("outer", "value"), ("absent",))
    ) == (1,)

    bundle = _bundle(tmp_path, monkeypatch)
    unknown_price_basis = replace(
        bundle.authority.bindings[0],
        price_basis_id="price-basis:not-authored",
    )
    assert (
        execution._authority_binding_matches(
            unknown_price_basis,
            bundle.project_case,
            bundle.request,
        )
        is False
    )

    def fail_digest(_value: Any) -> str:
        raise ValueError("simulated canonical digest failure")

    monkeypatch.setattr(execution, "resolved_config_sha256", fail_digest)
    assert (
        execution._authority_binding_matches(
            bundle.authority.bindings[0],
            bundle.project_case,
            bundle.request,
        )
        is False
    )


def test_internal_config_projection_helpers_reject_ambiguous_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    assert execution._copy_json(({"value": 1},)) == [{"value": 1}]
    with pytest.raises(TypeError, match="authored scalar selector"):
        execution._assertion_config_values(object(), {})

    with pytest.raises(ValueError, match="unknown run posture"):
        execution._run_mode_plan({"run": {"rogue": True}}, bundle.request)
    overrides, evaluated = execution._run_mode_plan({"run": {}}, bundle.request)
    assert overrides == {"run": {"mode": "screening"}}
    assert evaluated["run"] == {"mode": "screening"}
    with pytest.raises(ValueError, match="conflicting run posture"):
        execution._run_mode_plan({"run": {"mode": "full"}}, bundle.request)

    wrong_technology_config = copy.deepcopy(bundle.authored_config)
    wrong_technology_config["generation"]["technologies"]["rogue"] = {}
    assert (
        execution._compatibility_receipts(
            bundle.project_case,
            bundle.request,
            wrong_technology_config,
        )
        is None
    )


def test_alias_rich_result_is_one_call_bounded_snapshot_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        shared: list[Any] = [None]
        for _ in range(16):
            shared = [shared, shared]
        result["alias_dag"] = shared
        return result

    calls = _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionFailure
    assert result.failure.code is D3BFailureCode.GATEWAY_PROTOCOL_INVALID
    assert result.failure.gateway_call_count == 1
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("value", "pattern"),
    [
        ([[] for _ in range(10_001)], "container count"),
        ([None] * 100_001, "scalar count"),
        ("x" * 1_000_001, "text volume"),
        (1 << 4097, "bit length"),
        (object(), "non-JSON-native"),
        ({True: "unsupported"}, "unsupported mapping key"),
    ],
)
def test_result_freezer_enforces_container_scalar_and_text_volume(
    value: Any, pattern: str
) -> None:
    with pytest.raises(ValueError, match=pattern):
        execution._freeze_json(value)


def test_occurrence_guard_refuses_depth_cycles_and_each_volume_axis() -> None:
    with pytest.raises(ValueError, match="maximum JSON depth"):
        execution._assert_frozen_occurrence_bounds(None, depth=129)

    backing: dict[str, Any] = {}
    cyclic_mapping = MappingProxyType(backing)
    backing["self"] = cyclic_mapping
    with pytest.raises(ValueError, match="mapping cycle"):
        execution._assert_frozen_occurrence_bounds(cyclic_mapping)

    empty_tuple: tuple[Any, ...] = ()
    with pytest.raises(ValueError, match="sequence cycle"):
        execution._assert_frozen_occurrence_bounds(
            empty_tuple, active={id(empty_tuple)}
        )
    with pytest.raises(ValueError, match="bounded volume"):
        execution._assert_frozen_occurrence_bounds(
            MappingProxyType({}), counts=[10_000, 0, 0]
        )
    with pytest.raises(ValueError, match="bounded volume"):
        execution._assert_frozen_occurrence_bounds((), counts=[10_000, 0, 0])
    with pytest.raises(ValueError, match="bounded volume"):
        execution._assert_frozen_occurrence_bounds(None, counts=[0, 100_000, 0])
    with pytest.raises(ValueError, match="bounded volume"):
        execution._assert_frozen_occurrence_bounds("x", counts=[0, 0, 1_000_000])


def test_exact_comparator_rejects_unsupported_keys_and_bounds_repeated_pairs() -> None:
    unsupported = MappingProxyType({True: "value"})
    assert execution._bounded_exact_equal(unsupported, unsupported) is False

    left = MappingProxyType({"key": (1.0,)})
    right = MappingProxyType({"other": (1.0,)})
    assert execution._bounded_exact_equal(left, right) is False
    assert (
        execution._bounded_exact_equal(left, left, compared={(id(left), id(left))})
        is True
    )

    left_tuple = (1.0,)
    assert (
        execution._bounded_exact_equal(
            left_tuple,
            left_tuple,
            compared={(id(left_tuple), id(left_tuple))},
        )
        is True
    )
    assert execution._bounded_exact_equal(1, 1.0) is False
    assert execution._bounded_exact_equal(1, 1, depth=129) is False


def test_executor_has_one_public_function_local_gateway_call_and_no_finance_import() -> (
    None
):
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "evaluate_with_overrides"
    ]
    assert len(calls) == 1
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "analytics.evaluation_v14"
        and any(alias.name == "evaluate_with_overrides" for alias in node.names)
    ]
    assert len(imports) == 1
    assert isinstance(
        imports[0].parent if hasattr(imports[0], "parent") else None, type(None)
    )
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "execute_evaluation_request"
    )
    assert imports[0] in list(ast.walk(function))
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            any(alias.name.startswith("finance") for alias in node.names)
            if isinstance(node, ast.Import)
            else (node.module or "").startswith("finance")
            or "pipeline_v14" in (node.module or "")
        )
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize(
    "imports",
    [
        "import analytics.feasibility_execution; import analytics.evaluation_v14",
        "import analytics.evaluation_v14; import analytics.feasibility_execution",
        (
            "from analytics.contracts_v14 import D3BExecutionSuccess as before; "
            "import analytics.feasibility_execution; "
            "from analytics.contracts_v14 import D3BExecutionSuccess as after; "
            "assert before is after"
        ),
    ],
)
def test_fresh_interpreter_import_orders_are_cycle_safe(imports: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", imports],
        cwd=_MODULE.parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
