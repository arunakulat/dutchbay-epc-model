"""Hostile controls for the pure Dolphin 3B-0 request contracts."""

from __future__ import annotations

import ast
import copy
import json
import math
import random
import subprocess
import sys
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

import analytics.feasibility_report_contract.assessment_scope as assessment_scope_contract
from analytics.feasibility_report_contract import (
    AssessmentScope,
    AuthoredScenarioValidationReceipt,
    BaseConfigDomain,
    BaseScenarioIdentity,
    CostCompatibilityAssertion,
    EvaluationRequest,
    GenerationCapacityAssertion,
    JurisdictionSubject,
    JurisdictionSubjectAssertion,
    ProjectCaseMaterialCategory,
    ProjectCaseMaterialDisposition,
    ProjectCaseReference,
    StorageCapacityAssertion,
    V14BindingPolicy,
    resolved_config_sha256,
)
from analytics.feasibility_report_contract.assessment_scope import (
    ASSESSMENT_SCOPE_SCHEMA_ID,
    AUTHORED_SCENARIO_VALIDATION_SCHEMA_ID,
    BASE_SCENARIO_IDENTITY_SCHEMA_ID,
    EVALUATION_REQUEST_SCHEMA_ID,
    V14_BINDING_POLICY_SCHEMA_ID,
)
from analytics.run_manifest import config_sha256

_ROOT = Path(__file__).resolve().parents[2]
_MODULE = _ROOT / "analytics/feasibility_report_contract/assessment_scope.py"

_EXPECTED_DOMAINS_WITHOUT_JURISDICTION_ROUTE = frozenset(
    {
        BaseConfigDomain.SCENARIO_IDENTITY,
        BaseConfigDomain.RUN_POSTURE,
    }
)
_EXPECTED_DOMAIN_ALLOWED_SUBJECTS = {
    BaseConfigDomain.PROJECT_IDENTITY_LOCATION: frozenset({JurisdictionSubject.SITE}),
    BaseConfigDomain.PROJECT_RESOURCE: frozenset({JurisdictionSubject.SITE}),
    BaseConfigDomain.PROJECT_LIFECYCLE_TIMELINE: frozenset(
        {
            JurisdictionSubject.SITE,
            JurisdictionSubject.PERMIT,
            JurisdictionSubject.CONTRACT,
        }
    ),
    BaseConfigDomain.TECHNOLOGY_RESOURCE: frozenset(
        {JurisdictionSubject.SITE, JurisdictionSubject.SUPPLY}
    ),
    BaseConfigDomain.REVENUE_TARIFF: frozenset(
        {JurisdictionSubject.CONTRACT, JurisdictionSubject.GRID}
    ),
    BaseConfigDomain.CAPEX: frozenset(
        {
            JurisdictionSubject.SITE,
            JurisdictionSubject.CONTRACT,
            JurisdictionSubject.ACCOUNTING,
            JurisdictionSubject.SUPPLY,
        }
    ),
    BaseConfigDomain.OPEX: frozenset(
        {
            JurisdictionSubject.SITE,
            JurisdictionSubject.CONTRACT,
            JurisdictionSubject.ACCOUNTING,
            JurisdictionSubject.SUPPLY,
        }
    ),
    BaseConfigDomain.TAX_STATUTORY: frozenset(
        {JurisdictionSubject.TAX, JurisdictionSubject.CORPORATE}
    ),
    BaseConfigDomain.FX: frozenset(
        {
            JurisdictionSubject.FINANCING,
            JurisdictionSubject.ACCOUNTING,
            JurisdictionSubject.CONTRACT,
            JurisdictionSubject.CORPORATE,
        }
    ),
    BaseConfigDomain.GRID: frozenset({JurisdictionSubject.GRID}),
    BaseConfigDomain.ACCOUNTING: frozenset(
        {JurisdictionSubject.ACCOUNTING, JurisdictionSubject.CORPORATE}
    ),
    BaseConfigDomain.FINANCING_DEBT: frozenset({JurisdictionSubject.FINANCING}),
    BaseConfigDomain.WACC: frozenset({JurisdictionSubject.FINANCING}),
}
_ALLOWED_JURISDICTION_SUBJECT_DOMAIN_CASES = tuple(
    (subject, domain)
    for domain, subjects in _EXPECTED_DOMAIN_ALLOWED_SUBJECTS.items()
    for subject in sorted(subjects, key=lambda item: item.value)
)
_INVALID_JURISDICTION_SUBJECT_DOMAIN_CASES = tuple(
    (subject, domain)
    for domain in BaseConfigDomain
    for subject in JurisdictionSubject
    if domain in _EXPECTED_DOMAINS_WITHOUT_JURISDICTION_ROUTE
    or subject not in _EXPECTED_DOMAIN_ALLOWED_SUBJECTS.get(domain, frozenset())
)


def _project_case_reference() -> dict[str, Any]:
    return {
        "schema_id": "dutchbay.project_case.v1",
        "contract_version": "1.0.0",
        "project_id": "project:fictionland-hybrid",
        "case_id": "case:screening-base",
        "revision": 1,
    }


def _material_dispositions(
    asserted: set[str] | None = None,
) -> list[dict[str, str]]:
    asserted = asserted or {
        "identity",
        "location",
        "jurisdiction_subject",
        "technology_binding",
        "generation_capacity",
        "capex",
        "opex",
        "price_basis",
    }
    dispositions: list[dict[str, str]] = []
    for category in ProjectCaseMaterialCategory:
        is_asserted = category.value in asserted
        dispositions.append(
            {
                "category": category.value,
                "disposition": (
                    "assert_exact_base_compatibility"
                    if is_asserted
                    else "explicitly_out_of_v1"
                ),
                "action": (
                    "assert_before_gateway"
                    if is_asserted
                    else "exclude_from_v1_no_fallback"
                ),
                "rationale": f"Explicit D3B v1 disposition for {category.value}",
            }
        )
    return dispositions


def _domain_dispositions() -> list[dict[str, Any]]:
    retained: dict[str, list[dict[str, str | None]]] = {
        "scenario_identity": [
            {
                "authority_source_id": "source:fictionland-authored-base",
                "jurisdiction_binding_id": None,
                "technology_binding_id": None,
            }
        ],
        "project_identity_location": [
            {
                "authority_source_id": "source:fictionland-authored-base",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "technology_binding_id": None,
            }
        ],
        "project_resource": [
            {
                "authority_source_id": "source:fictionland-wind-basis",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "technology_binding_id": "technology-binding:wind",
            }
        ],
        "technology_resource": [
            {
                "authority_source_id": "source:fictionland-wind-basis",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "technology_binding_id": "technology-binding:wind",
            }
        ],
        "capex": [
            {
                "authority_source_id": "source:fictionland-authored-base",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "technology_binding_id": None,
            }
        ],
        "opex": [
            {
                "authority_source_id": "source:fictionland-authored-base",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "technology_binding_id": None,
            }
        ],
        "tax_statutory": [
            {
                "authority_source_id": "source:fictionland-tax-basis",
                "jurisdiction_binding_id": "jurisdiction-binding:tax",
                "technology_binding_id": None,
            }
        ],
        "run_posture": [
            {
                "authority_source_id": "source:fictionland-authored-base",
                "jurisdiction_binding_id": None,
                "technology_binding_id": None,
            }
        ],
    }
    domains = [
        "scenario_identity",
        "project_identity_location",
        "project_resource",
        "project_lifecycle_timeline",
        "technology_resource",
        "revenue_tariff",
        "capex",
        "opex",
        "tax_statutory",
        "fx",
        "grid",
        "accounting",
        "financing_debt",
        "wacc",
        "run_posture",
    ]
    return [
        {
            "domain": domain,
            "disposition": (
                "retained_authored_authority"
                if domain in retained
                else "declared_absent"
            ),
            "authority_routes": retained.get(domain, []),
            "rationale": f"Explicit authored-domain disposition for {domain}",
        }
        for domain in domains
    ]


def _request_payload() -> dict[str, Any]:
    project_case = _project_case_reference()
    resolved_digest = config_sha256(
        {
            "scenario_name": "Fictionland Hybrid Screening",
            "project": {
                "location": " Fictional coast site ",
                "capacity_mw": 100.0,
            },
            "run": {"mode": "screening"},
        }
    )
    return {
        "schema_id": "dutchbay.evaluation_request.v1",
        "contract_version": "1.0.0",
        "request_id": "request:d3b-fictionland",
        "project_case": copy.deepcopy(project_case),
        "scope": {
            "schema_id": "dutchbay.assessment_scope.v1",
            "contract_version": "1.0.0",
            "scope_id": "scope:fictionland-screening",
            "project_case": copy.deepcopy(project_case),
            "project_boundary": " Fictional single-site assessment boundary ",
            "technology_scope": [
                {
                    "technology_binding_id": "technology-binding:wind",
                    "technology_id": "wind",
                    "asset_class": "generation",
                }
            ],
            "jurisdiction_scope": [
                {
                    "jurisdiction_binding_id": "jurisdiction-binding:site",
                    "jurisdiction_code": "FIC",
                    "subject": "site",
                },
                {
                    "jurisdiction_binding_id": "jurisdiction-binding:tax",
                    "jurisdiction_code": "FIC",
                    "subject": "tax",
                },
            ],
            "project_stage": "feasibility",
            "intended_audiences": [
                {
                    "audience_id": "audience:internal-committee",
                    "statement": " Internal investment committee ",
                }
            ],
            "intended_uses": [
                {
                    "use_id": "use:screening",
                    "statement": "Compare the governed base case with the stated limits",
                }
            ],
            "intended_decision": {
                "decision_id": "decision:proceed-to-study",
                "decision_question": "Proceed to the next governed study gate?",
                "decision_owner_role": "Internal investment committee",
            },
            "run_mode": "screening",
            "target_grade_request": "screening",
            "evidence_cutoff": "2026-08-01",
            "valuation_date": "2026-08-01",
            "reporting_currency": "USD",
            "price_nominality": "nominal",
            "price_basis_id": "price-basis:2026-usd",
            "price_basis_description": "2026 nominal United States dollars",
            "exclusions": [],
            "materiality_rule": {
                "rule_id": "materiality:all-unresolved",
                "statement": "Disclose every unresolved input that can alter the decision",
            },
        },
        "base_scenario": {
            "schema_id": "dutchbay.base_scenario_identity.v1",
            "contract_version": "1.0.0",
            "config_id": "config:fictionland-authored-base",
            "config_version": "1.0.0",
            "source_file_sha256": "b" * 64,
            "resolved_config_sha256": resolved_digest,
            "authority_source_id": "source:fictionland-authored-base",
            "authority_basis": "Controlled authored scenario supplied for D3B binding",
            "validation_receipt": {
                "schema_id": "dutchbay.authored_scenario_validation_receipt.v1",
                "contract_version": "1.0.0",
                "receipt_id": "validation:fictionland-authored-base",
                "receipt_scope": "declared_authored_scenario_validation",
                "resolved_config_sha256": resolved_digest,
                "validator_id": "validator:v14-authored-scenario",
                "validator_version": "1.0.0",
                "validator_control_ids": ["CESSPIT", "VAL-01", "ARCH-04"],
                "validation_modules": ["cashflow", "debt"],
                "outcome": "pass",
                "v14_schema_guard_id": "analytics.schema_guard.validate_config_for_v14",
                "v14_gateway_id": "analytics.evaluation_v14.evaluate_with_overrides",
                "authority_source_id": "source:fictionland-authored-base",
            },
            "subject_authorities": [
                {
                    "jurisdiction_binding_id": "jurisdiction-binding:site",
                    "jurisdiction_code": "FIC",
                    "subject": "site",
                    "authority_source_id": "source:fictionland-authored-base",
                },
                {
                    "jurisdiction_binding_id": "jurisdiction-binding:tax",
                    "jurisdiction_code": "FIC",
                    "subject": "tax",
                    "authority_source_id": "source:fictionland-tax-basis",
                },
            ],
            "technology_authorities": [
                {
                    "base_config_key": "wind",
                    "technology_binding_id": "technology-binding:wind",
                    "technology_id": "wind",
                    "asset_class": "generation",
                    "authored_technology_kind": "wind_turbine",
                    "authority_source_id": "source:fictionland-wind-basis",
                }
            ],
            "domain_dispositions": _domain_dispositions(),
        },
        "validation_modules": ["cashflow", "debt"],
        "binding_policy": {
            "schema_id": "dutchbay.v14_binding_policy.v1",
            "contract_version": "1.0.0",
            "policy_id": "policy:fictionland-v14-binding",
            "policy_version": "1.0.0",
            "project_case": copy.deepcopy(project_case),
            "assertions": [
                {
                    "kind": "scenario_identity_assertion",
                    "assertion_id": "assertion:scenario-name",
                    "category": "identity",
                    "project_case_selector": "identity.case_name",
                    "base_selector": "scenario_name",
                },
                {
                    "kind": "location_assertion",
                    "assertion_id": "assertion:location",
                    "category": "location",
                    "project_case_selector": "description",
                    "base_selector": "project_location",
                },
                {
                    "kind": "jurisdiction_subject_assertion",
                    "assertion_id": "assertion:site-jurisdiction",
                    "category": "jurisdiction_subject",
                    "jurisdiction_binding_id": "jurisdiction-binding:site",
                    "jurisdiction_code": "FIC",
                    "subject": "site",
                    "base_domain": "project_resource",
                },
                {
                    "kind": "jurisdiction_subject_assertion",
                    "assertion_id": "assertion:tax-jurisdiction",
                    "category": "jurisdiction_subject",
                    "jurisdiction_binding_id": "jurisdiction-binding:tax",
                    "jurisdiction_code": "FIC",
                    "subject": "tax",
                    "base_domain": "tax_statutory",
                },
                {
                    "kind": "technology_binding_assertion",
                    "assertion_id": "assertion:wind-technology",
                    "category": "technology_binding",
                    "asset_id": "asset:wind-01",
                    "technology_binding_id": "technology-binding:wind",
                    "technology_id": "wind",
                    "asset_class": "generation",
                    "authored_technology_kind": "wind_turbine",
                    "base_config_key": "wind",
                },
                {
                    "kind": "generation_capacity_assertion",
                    "assertion_id": "assertion:project-capacity",
                    "category": "generation_capacity",
                    "asset_id": "asset:wind-01",
                    "base_config_key": None,
                    "project_case_selector": "total_power_capacity",
                    "base_selector": "project_capacity_mw",
                    "expected_unit": "MW",
                    "electrical_basis": "not_applicable",
                    "capacity_basis": "net",
                    "authored_technology_kind": "wind_turbine",
                },
                {
                    "kind": "generation_capacity_assertion",
                    "assertion_id": "assertion:wind-capacity",
                    "category": "generation_capacity",
                    "asset_id": "asset:wind-01",
                    "base_config_key": "wind",
                    "project_case_selector": "total_power_capacity",
                    "base_selector": "technology_capacity_mw",
                    "expected_unit": "MW",
                    "electrical_basis": "not_applicable",
                    "capacity_basis": "net",
                    "authored_technology_kind": "wind_turbine",
                },
                {
                    "kind": "cost_compatibility_assertion",
                    "assertion_id": "assertion:capex",
                    "category": "capex",
                    "included_line_ids": ["cost:capex:plant"],
                    "price_basis_id": "price-basis:2026-usd",
                    "reporting_currency": "USD",
                    "periodicity": "one_time",
                    "base_selector": "capex_usd_total",
                },
                {
                    "kind": "cost_compatibility_assertion",
                    "assertion_id": "assertion:opex",
                    "category": "opex",
                    "included_line_ids": ["cost:opex:annual"],
                    "price_basis_id": "price-basis:2026-usd",
                    "reporting_currency": "USD",
                    "periodicity": "annual",
                    "base_selector": "opex_usd_per_year",
                },
                {
                    "kind": "price_basis_assertion",
                    "assertion_id": "assertion:price-basis",
                    "category": "price_basis",
                    "price_basis_id": "price-basis:2026-usd",
                    "valuation_date": "2026-08-01",
                    "reporting_currency": "USD",
                    "nominality": "nominal",
                },
            ],
            "material_dispositions": _material_dispositions(),
            "run_mode_policy": {
                "kind": "canonical_run_mode_only",
                "absent_canonical_mode": "add_scope_run_mode",
                "present_canonical_mode": "require_exact_scope_match",
                "legacy_alias": "refuse",
                "unknown_run_keys": "refuse",
            },
        },
    }


def _validate(payload: dict[str, Any]) -> EvaluationRequest:
    return EvaluationRequest.model_validate_json(json.dumps(payload))


def _validate_policy(payload: dict[str, Any]) -> V14BindingPolicy:
    return V14BindingPolicy.model_validate_json(json.dumps(payload["binding_policy"]))


def _assert_policy_and_request_reject(
    payload: dict[str, Any],
    match: str,
) -> None:
    for validate in (_validate_policy, _validate):
        with pytest.raises(ValidationError, match=match):
            validate(payload)


def _assertion(payload: dict[str, Any], assertion_id: str) -> dict[str, Any]:
    return next(
        item
        for item in payload["binding_policy"]["assertions"]
        if item["assertion_id"] == assertion_id
    )


def _domain_disposition(payload: dict[str, Any], domain: str) -> dict[str, Any]:
    return next(
        item
        for item in payload["base_scenario"]["domain_dispositions"]
        if item["domain"] == domain
    )


def _add_storage_technology(payload: dict[str, Any]) -> None:
    """Add one completely routed BESS technology to a request fixture."""
    payload["scope"]["technology_scope"].append(
        {
            "technology_binding_id": "technology-binding:bess",
            "technology_id": "bess",
            "asset_class": "storage",
        }
    )
    payload["base_scenario"]["technology_authorities"].append(
        {
            "base_config_key": "bess",
            "technology_binding_id": "technology-binding:bess",
            "technology_id": "bess",
            "asset_class": "storage",
            "authored_technology_kind": "storage",
            "authority_source_id": "source:fictionland-bess-basis",
        }
    )
    for domain in ("project_resource", "technology_resource"):
        _domain_disposition(payload, domain)["authority_routes"].append(
            {
                "authority_source_id": "source:fictionland-bess-basis",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "technology_binding_id": "technology-binding:bess",
            }
        )
    payload["binding_policy"]["assertions"].extend(
        [
            {
                "kind": "technology_binding_assertion",
                "assertion_id": "assertion:bess-technology",
                "category": "technology_binding",
                "asset_id": "asset:bess-01",
                "technology_binding_id": "technology-binding:bess",
                "technology_id": "bess",
                "asset_class": "storage",
                "authored_technology_kind": "storage",
                "base_config_key": "bess",
            },
            *[
                {
                    "kind": "storage_capacity_assertion",
                    "assertion_id": f"assertion:bess-{source}",
                    "category": "storage_capacity",
                    "asset_id": "asset:bess-01",
                    "base_config_key": "bess",
                    "project_case_selector": source,
                    "base_selector": target,
                    "expected_unit": unit,
                    "electrical_basis": "ac",
                    "capacity_basis": "usable",
                    "authored_technology_kind": "storage",
                }
                for source, target, unit in (
                    ("power", "technology_power_mw", "MW"),
                    ("energy", "technology_energy_mwh", "MWh"),
                    ("duration", "technology_duration_h", "hour"),
                )
            ],
        ]
    )
    storage_disposition = next(
        item
        for item in payload["binding_policy"]["material_dispositions"]
        if item["category"] == "storage_capacity"
    )
    storage_disposition["disposition"] = "assert_exact_base_compatibility"
    storage_disposition["action"] = "assert_before_gateway"


def _replace_wind_with_solar_dc(payload: dict[str, Any], *, unit: str = "MWdc") -> None:
    """Replace the wind fixture with one exactly routed solar DC proposition."""
    payload["scope"]["technology_scope"][0].update(
        {
            "technology_binding_id": "technology-binding:solar",
            "technology_id": "solar_pv",
        }
    )
    payload["base_scenario"]["technology_authorities"][0].update(
        {
            "base_config_key": "solar",
            "technology_binding_id": "technology-binding:solar",
            "technology_id": "solar_pv",
            "authored_technology_kind": "solar_pv",
            "authority_source_id": "source:fictionland-solar-basis",
        }
    )
    for domain in ("project_resource", "technology_resource"):
        route = _domain_disposition(payload, domain)["authority_routes"][0]
        route.update(
            {
                "authority_source_id": "source:fictionland-solar-basis",
                "technology_binding_id": "technology-binding:solar",
            }
        )

    technology = _assertion(payload, "assertion:wind-technology")
    technology.update(
        {
            "asset_id": "asset:solar-01",
            "technology_binding_id": "technology-binding:solar",
            "technology_id": "solar_pv",
            "authored_technology_kind": "solar_pv",
            "base_config_key": "solar",
        }
    )
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["assertion_id"] != "assertion:project-capacity"
    ]
    capacity = _assertion(payload, "assertion:wind-capacity")
    capacity.update(
        {
            "asset_id": "asset:solar-01",
            "base_config_key": "solar",
            "base_selector": "solar_resource_dc_capacity_mw",
            "expected_unit": unit,
            "electrical_basis": "dc",
            "capacity_basis": "nameplate",
            "authored_technology_kind": "solar_pv",
        }
    )


def _add_solar_technology(payload: dict[str, Any]) -> None:
    """Add one completely routed solar technology to a wind request fixture."""
    payload["scope"]["technology_scope"].append(
        {
            "technology_binding_id": "technology-binding:solar",
            "technology_id": "solar_pv",
            "asset_class": "generation",
        }
    )
    payload["base_scenario"]["technology_authorities"].append(
        {
            "base_config_key": "solar",
            "technology_binding_id": "technology-binding:solar",
            "technology_id": "solar_pv",
            "asset_class": "generation",
            "authored_technology_kind": "solar_pv",
            "authority_source_id": "source:fictionland-solar-basis",
        }
    )
    for domain in ("project_resource", "technology_resource"):
        _domain_disposition(payload, domain)["authority_routes"].append(
            {
                "authority_source_id": "source:fictionland-solar-basis",
                "jurisdiction_binding_id": "jurisdiction-binding:site",
                "technology_binding_id": "technology-binding:solar",
            }
        )
    payload["binding_policy"]["assertions"].extend(
        [
            {
                "kind": "technology_binding_assertion",
                "assertion_id": "assertion:solar-technology",
                "category": "technology_binding",
                "asset_id": "asset:solar-01",
                "technology_binding_id": "technology-binding:solar",
                "technology_id": "solar_pv",
                "asset_class": "generation",
                "authored_technology_kind": "solar_pv",
                "base_config_key": "solar",
            },
            {
                "kind": "generation_capacity_assertion",
                "assertion_id": "assertion:solar-capacity",
                "category": "generation_capacity",
                "asset_id": "asset:solar-01",
                "base_config_key": "solar",
                "project_case_selector": "total_power_capacity",
                "base_selector": "solar_resource_dc_capacity_mw",
                "expected_unit": "MWdc",
                "electrical_basis": "dc",
                "capacity_basis": "nameplate",
                "authored_technology_kind": "solar_pv",
            },
        ]
    )


def _draft_validators() -> tuple[Any, Any]:
    validation_schema = EvaluationRequest.model_json_schema(mode="validation")
    serialization_schema = EvaluationRequest.model_json_schema(mode="serialization")
    jsonschema.Draft202012Validator.check_schema(validation_schema)
    jsonschema.Draft202012Validator.check_schema(serialization_schema)
    return (
        jsonschema.Draft202012Validator(validation_schema),
        jsonschema.Draft202012Validator(serialization_schema),
    )


def _schema_property_names(node: object) -> set[str]:
    names: set[str] = set()
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            names.update(str(item) for item in properties)
        for value in node.values():
            names.update(_schema_property_names(value))
    elif isinstance(node, list):
        for value in node:
            names.update(_schema_property_names(value))
    return names


def test_json_round_trip_and_both_draft_schemas() -> None:
    request = _validate(_request_payload())
    dumped = request.model_dump(mode="json")
    validation, serialization = _draft_validators()
    validation.validate(dumped)
    serialization.validate(dumped)
    assert EvaluationRequest.model_validate_json(request.model_dump_json()) == request
    assert (
        request.scope.project_boundary == " Fictional single-site assessment boundary "
    )
    assert request.scope.intended_audiences[0].statement == (
        " Internal investment committee "
    )


@pytest.mark.parametrize(
    ("container_path", "field"),
    [
        ((), "schema_id"),
        ((), "contract_version"),
        (("scope",), "schema_id"),
        (("scope",), "contract_version"),
        (("scope",), "exclusions"),
        (("base_scenario",), "schema_id"),
        (("base_scenario",), "contract_version"),
        (("base_scenario", "validation_receipt"), "schema_id"),
        (("base_scenario", "validation_receipt"), "contract_version"),
        (("binding_policy",), "schema_id"),
        (("binding_policy",), "contract_version"),
    ],
)
def test_material_schema_and_explicit_fields_have_no_defaults(
    container_path: tuple[str, ...], field: str
) -> None:
    payload = _request_payload()
    container: dict[str, Any] = payload
    for part in container_path:
        container = container[part]
    del container[field]
    with pytest.raises(ValidationError):
        _validate(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_id",), "dutchbay.evaluation_request.v2"),
        (("scope", "contract_version"), "1.0.1"),
        (("base_scenario", "validation_receipt", "outcome"), "pending"),
        (("binding_policy", "run_mode_policy", "legacy_alias"), "accept"),
    ],
)
def test_unknown_versions_and_policy_tokens_fail_closed(
    path: tuple[str, ...], value: str
) -> None:
    payload = _request_payload()
    target: dict[str, Any] = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        _validate(payload)


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "\t\r\n",
        "\x00\x01",
        "\x1c\x1f",
        "\x85",
        "\u2003\u2028",
        "\ufeff",
    ],
)
def test_exact_assessment_text_rejects_blank_without_normalizing(text: str) -> None:
    payload = _request_payload()
    payload["scope"]["project_boundary"] = text
    for validator in _draft_validators():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
    with pytest.raises(ValidationError):
        _validate(payload)


def test_assessment_text_blank_policy_matches_actual_ecmascript() -> None:
    schema = AssessmentScope.model_json_schema(mode="validation")
    pattern = schema["properties"]["project_boundary"]["pattern"]
    values = [
        "",
        " ",
        "\t\r\n",
        "\x00\x01",
        "\x1c\x1f",
        "\x85",
        "\u2003\u2028",
        "\ufeff",
        "x",
        " \n x \t",
        "\u200b",
        "🌊" * 4096,
        "🌊" * 4097,
    ]
    script = """
const pattern = new RegExp(process.argv[1]);
const values = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(values.map(
  (value) => Array.from(value).length <= 4096 && pattern.test(value)
)));
"""
    result = subprocess.run(
        ["node", "-e", script, pattern, json.dumps(values)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == [
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        True,
        True,
        True,
        False,
    ]


def test_exact_assessment_text_bounds_and_preserves_unicode() -> None:
    payload = _request_payload()
    exact = "  Évaluation boundary — \u65e5\u672c\u8a9e  "
    payload["scope"]["project_boundary"] = exact
    request = _validate(payload)
    assert request.scope.project_boundary == exact

    payload["scope"]["project_boundary"] = "x" * 4097
    with pytest.raises(ValidationError):
        _validate(payload)

    payload = _request_payload()
    payload["scope"]["project_boundary"] = "🌊" * 4096
    for validator in _draft_validators():
        validator.validate(payload)
    assert _validate(payload).scope.project_boundary == "🌊" * 4096

    payload["scope"]["project_boundary"] = "🌊" * 4097
    for validator in _draft_validators():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
    with pytest.raises(ValidationError):
        _validate(payload)


@pytest.mark.parametrize(
    "hostile_id",
    [
        " request:d3b-fictionland",
        "request:d3b-fictionland ",
        "request:d3b-fictionland\n",
        "request:d3b-fictionland\r",
        "request:d3b-\u0661",
        "request:d3b-\u00e9",
    ],
)
def test_identity_tokens_are_exact_across_runtime_and_schemas(hostile_id: str) -> None:
    payload = _request_payload()
    payload["request_id"] = hostile_id
    for validator in _draft_validators():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
    with pytest.raises(ValidationError):
        _validate(payload)


@pytest.mark.parametrize(
    "hostile_code",
    [" FIC", "FIC ", "FIC\n", "FIC\r", "F١C", "FÍC"],
)
@pytest.mark.parametrize(
    "role",
    ["scope", "base_subject_authority", "jurisdiction_assertion"],
)
def test_jurisdiction_codes_are_exact_across_every_new_role_and_schema(
    hostile_code: str,
    role: str,
) -> None:
    payload = _request_payload()
    targets = {
        "scope": payload["scope"]["jurisdiction_scope"][0],
        "base_subject_authority": payload["base_scenario"]["subject_authorities"][0],
        "jurisdiction_assertion": payload["binding_policy"]["assertions"][2],
    }
    targets[role]["jurisdiction_code"] = hostile_code
    for validator in _draft_validators():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
    with pytest.raises(ValidationError):
        _validate(payload)


@pytest.mark.parametrize(
    "hostile_unit",
    [" MW", "MW ", "MW\n", "MW\r", "MШ", "ＭW"],
)
def test_binding_units_are_exact_in_runtime_and_both_draft_schemas(
    hostile_unit: str,
) -> None:
    payload = _request_payload()
    assertion = next(
        item
        for item in payload["binding_policy"]["assertions"]
        if item.get("assertion_id") == "assertion:project-capacity"
    )
    assertion["expected_unit"] = hostile_unit
    for validator in _draft_validators():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
    with pytest.raises(ValidationError):
        _validate(payload)


@pytest.mark.parametrize("hostile_currency", [" USD", "USD ", "USD\n", "usd", "US١"])
@pytest.mark.parametrize("role", ["scope", "cost", "price_basis"])
def test_currency_codes_are_exact_in_every_new_role_and_both_schemas(
    hostile_currency: str,
    role: str,
) -> None:
    payload = _request_payload()
    targets = {
        "scope": payload["scope"],
        "cost": _assertion(payload, "assertion:capex"),
        "price_basis": _assertion(payload, "assertion:price-basis"),
    }
    targets[role]["reporting_currency"] = hostile_currency
    for validator in _draft_validators():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
    with pytest.raises(ValidationError):
        _validate(payload)


def test_storage_binding_unit_uses_the_same_exact_transport_seam() -> None:
    payload = {
        "kind": "storage_capacity_assertion",
        "assertion_id": "assertion:bess-power",
        "category": "storage_capacity",
        "asset_id": "asset:bess-01",
        "base_config_key": "bess",
        "project_case_selector": "power",
        "base_selector": "technology_power_mw",
        "expected_unit": "MW",
        "electrical_basis": "ac",
        "capacity_basis": "usable",
        "authored_technology_kind": "storage",
    }
    assertion = StorageCapacityAssertion.model_validate_json(json.dumps(payload))
    assert assertion.expected_unit == "MW"
    for mode in ("validation", "serialization"):
        validator = jsonschema.Draft202012Validator(
            StorageCapacityAssertion.model_json_schema(mode=mode)
        )
        validator.validate(assertion.model_dump(mode="json"))
        hostile = copy.deepcopy(payload)
        hostile["expected_unit"] = "MW\n"
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(hostile)
    payload["expected_unit"] = "MW\n"
    with pytest.raises(ValidationError):
        StorageCapacityAssertion.model_validate_json(json.dumps(payload))


def test_python_mode_is_strict_while_normalized_dump_reingresses() -> None:
    payload = _request_payload()
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(payload)

    request = _validate(payload)
    assert EvaluationRequest.model_validate(request.model_dump()) == request


def test_contract_graph_is_deeply_frozen_and_tuple_backed() -> None:
    request = _validate(_request_payload())
    assert isinstance(request.scope.technology_scope, tuple)
    assert isinstance(request.binding_policy.assertions, tuple)
    assert isinstance(request.base_scenario.domain_dispositions, tuple)
    with pytest.raises(ValidationError):
        request.request_id = "request:changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        request.scope.project_boundary = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        request.scope.intended_audiences[0].statement = "changed"  # type: ignore[misc]


def test_extra_fields_are_forbidden_at_each_boundary() -> None:
    for path in [(), ("scope",), ("base_scenario",), ("binding_policy",)]:
        payload = _request_payload()
        target: dict[str, Any] = payload
        for part in path:
            target = target[part]
        target["unexpected"] = True
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            _validate(payload)


def test_scope_requires_unique_nonempty_axes_and_one_site() -> None:
    payload = _request_payload()
    payload["scope"]["technology_scope"] = []
    with pytest.raises(ValidationError, match="at least one technology"):
        _validate(payload)

    payload = _request_payload()
    payload["scope"]["intended_audiences"].append(
        copy.deepcopy(payload["scope"]["intended_audiences"][0])
    )
    with pytest.raises(ValidationError, match="duplicate audience_id"):
        _validate(payload)

    payload = _request_payload()
    payload["scope"]["jurisdiction_scope"][0]["subject"] = "grid"
    with pytest.raises(ValidationError, match="exactly one site jurisdiction"):
        _validate(payload)


def test_standalone_identity_scope_and_receipt_empty_axes_fail_closed() -> None:
    project_case = _project_case_reference()
    project_case["case_id"] = project_case["project_id"]
    with pytest.raises(ValidationError, match="must be distinct"):
        ProjectCaseReference.model_validate_json(json.dumps(project_case))

    for field, message in (
        ("jurisdiction_scope", "at least one jurisdiction subject"),
        ("intended_audiences", "intended audiences and uses"),
        ("intended_uses", "intended audiences and uses"),
    ):
        scope = copy.deepcopy(_request_payload()["scope"])
        scope[field] = []
        with pytest.raises(ValidationError, match=message):
            AssessmentScope.model_validate_json(json.dumps(scope))

    receipt = copy.deepcopy(_request_payload()["base_scenario"]["validation_receipt"])
    receipt["validator_control_ids"] = []
    with pytest.raises(ValidationError, match="requires validator_control_ids"):
        AuthoredScenarioValidationReceipt.model_validate_json(json.dumps(receipt))

    receipt = copy.deepcopy(_request_payload()["base_scenario"]["validation_receipt"])
    receipt["validation_modules"] = []
    with pytest.raises(ValidationError, match="must not be empty"):
        AuthoredScenarioValidationReceipt.model_validate_json(json.dumps(receipt))


def test_scope_does_not_infer_date_order_or_grade_from_run_mode() -> None:
    payload = _request_payload()
    payload["scope"]["evidence_cutoff"] = "2026-08-29"
    payload["scope"]["run_mode"] = "developer"
    payload["scope"]["target_grade_request"] = "lender_grade"
    request = _validate(payload)
    assert request.scope.evidence_cutoff == date(2026, 8, 29)
    assert request.scope.valuation_date == date(2026, 8, 1)
    assert request.scope.run_mode.value == "developer"
    assert request.scope.target_grade_request.value == "lender_grade"


def test_request_binds_the_same_exact_project_case_everywhere() -> None:
    for path in [
        ("scope", "project_case", "revision"),
        ("binding_policy", "project_case", "case_id"),
    ]:
        payload = _request_payload()
        target: dict[str, Any] = payload
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = 2 if path[-1] == "revision" else "case:other"
        with pytest.raises(ValidationError, match="ProjectCase reference must match"):
            _validate(payload)


def test_validation_modules_are_unique_complete_and_receipt_bound() -> None:
    payload = _request_payload()
    payload["validation_modules"] = ["cashflow"]
    with pytest.raises(ValidationError, match="include cashflow and debt"):
        _validate(payload)

    payload = _request_payload()
    payload["validation_modules"] = ["cashflow", "debt", "debt"]
    with pytest.raises(ValidationError, match="duplicate validation module"):
        _validate(payload)

    payload = _request_payload()
    payload["base_scenario"]["validation_receipt"]["validation_modules"].append("grid")
    with pytest.raises(ValidationError, match="must match authored validation receipt"):
        _validate(payload)


def test_base_validation_receipt_digest_and_authorities_are_closed() -> None:
    payload = _request_payload()
    payload["base_scenario"]["validation_receipt"]["resolved_config_sha256"] = "c" * 64
    with pytest.raises(ValidationError, match="resolved digest must match"):
        _validate(payload)

    payload = _request_payload()
    payload["base_scenario"]["subject_authorities"].append(
        copy.deepcopy(payload["base_scenario"]["subject_authorities"][0])
    )
    with pytest.raises(ValidationError, match="duplicate base subject authority"):
        _validate(payload)

    payload = _request_payload()
    payload["base_scenario"]["domain_dispositions"] = []
    with pytest.raises(ValidationError, match="disposition every authored domain"):
        _validate(payload)

    payload = _request_payload()
    validation_receipt = payload["base_scenario"]["validation_receipt"]
    validation_receipt["authority_source_id"] = "source:unrelated-validation-authority"
    with pytest.raises(ValidationError, match="authority source must match"):
        _validate(payload)

    for field, message in (
        ("subject_authorities", "requires subject authorities"),
        ("technology_authorities", "requires technology authorities"),
    ):
        base = copy.deepcopy(_request_payload()["base_scenario"])
        base[field] = []
        with pytest.raises(ValidationError, match=message):
            BaseScenarioIdentity.model_validate_json(json.dumps(base))


def test_every_authored_domain_has_one_truthful_disposition() -> None:
    payload = _request_payload()
    payload["base_scenario"]["domain_dispositions"].pop()
    with pytest.raises(ValidationError, match="disposition every authored domain"):
        _validate(payload)

    payload = _request_payload()
    retained = _domain_disposition(payload, "project_resource")
    retained["authority_routes"] = []
    with pytest.raises(ValidationError, match="retained domains require"):
        _validate(payload)

    payload = _request_payload()
    absent = _domain_disposition(payload, "project_lifecycle_timeline")
    absent["authority_routes"] = [
        {
            "authority_source_id": "source:unexpected",
            "jurisdiction_binding_id": "jurisdiction-binding:site",
            "technology_binding_id": None,
        }
    ]
    with pytest.raises(ValidationError, match="non-retained domains forbid"):
        _validate(payload)

    payload = _request_payload()
    route = _domain_disposition(payload, "project_resource")["authority_routes"][0]
    route["authority_source_id"] = "source:undeclared"
    with pytest.raises(ValidationError, match="authority source must be declared"):
        _validate(payload)


def test_standalone_base_domain_routes_are_closed_and_subject_typed() -> None:
    for domain, updates, message in (
        (
            "scenario_identity",
            {"jurisdiction_binding_id": "jurisdiction-binding:site"},
            "must be project-global",
        ),
        (
            "scenario_identity",
            {"authority_source_id": "source:fictionland-tax-basis"},
            "must use the base scenario authority source",
        ),
        (
            "project_identity_location",
            {"jurisdiction_binding_id": None},
            "requires a jurisdiction-subject route",
        ),
        (
            "project_identity_location",
            {"jurisdiction_binding_id": "jurisdiction-binding:tax"},
            "cannot govern project_identity_location",
        ),
        (
            "technology_resource",
            {"technology_binding_id": None},
            "require a technology binding",
        ),
    ):
        payload = _request_payload()
        route = _domain_disposition(payload, domain)["authority_routes"][0]
        route.update(updates)
        with pytest.raises(ValidationError, match=message):
            BaseScenarioIdentity.model_validate_json(
                json.dumps(payload["base_scenario"])
            )

    payload = _request_payload()
    tax = _domain_disposition(payload, "tax_statutory")
    tax["disposition"] = "declared_absent"
    tax["authority_routes"] = []
    with pytest.raises(ValidationError, match="every base subject authority"):
        BaseScenarioIdentity.model_validate_json(json.dumps(payload["base_scenario"]))

    payload = _request_payload()
    payload["base_scenario"]["technology_authorities"].append(
        {
            "base_config_key": "bess",
            "technology_binding_id": "technology-binding:bess",
            "technology_id": "bess",
            "asset_class": "storage",
            "authored_technology_kind": "storage",
            "authority_source_id": "source:fictionland-bess-basis",
        }
    )
    with pytest.raises(ValidationError, match="every base technology authority"):
        BaseScenarioIdentity.model_validate_json(json.dumps(payload["base_scenario"]))


@pytest.mark.parametrize(
    ("subject", "domain"),
    _ALLOWED_JURISDICTION_SUBJECT_DOMAIN_CASES,
    ids=lambda value: value.value,
)
def test_jurisdiction_assertion_accepts_every_admissible_subject_domain_pair(
    subject: JurisdictionSubject,
    domain: BaseConfigDomain,
) -> None:
    assertion = copy.deepcopy(
        _assertion(_request_payload(), "assertion:site-jurisdiction")
    )
    assertion.update({"subject": subject.value, "base_domain": domain.value})

    validated = JurisdictionSubjectAssertion.model_validate_json(json.dumps(assertion))

    assert validated.subject is subject
    assert validated.base_domain is domain


@pytest.mark.parametrize(
    ("subject", "domain"),
    _INVALID_JURISDICTION_SUBJECT_DOMAIN_CASES,
    ids=lambda value: value.value,
)
def test_jurisdiction_assertion_refuses_every_impossible_subject_domain_pair(
    subject: JurisdictionSubject,
    domain: BaseConfigDomain,
) -> None:
    payload = _request_payload()
    assertion = _assertion(payload, "assertion:site-jurisdiction")
    assertion.update({"subject": subject.value, "base_domain": domain.value})
    message = (
        f"{domain.value} authority routes must be project-global"
        if domain in _EXPECTED_DOMAINS_WITHOUT_JURISDICTION_ROUTE
        else f"jurisdiction subject {subject.value} cannot govern {domain.value}"
    )

    with pytest.raises(ValidationError, match=message):
        JurisdictionSubjectAssertion.model_validate_json(json.dumps(assertion))
    _assert_policy_and_request_reject(payload, message)


def test_assertions_require_their_corresponding_retained_authored_domains() -> None:
    for domain, message in (
        ("scenario_identity", "retained authored identity"),
        ("project_identity_location", "retained authored project location"),
        ("project_resource", "retained authority route"),
        ("technology_resource", "retained technology-resource authority route"),
        ("capex", "retained authored cost domain"),
        ("opex", "retained authored cost domain"),
    ):
        payload = _request_payload()
        disposition = _domain_disposition(payload, domain)
        disposition["disposition"] = "declared_absent"
        disposition["authority_routes"] = []
        with pytest.raises(ValidationError, match=message):
            _validate(payload)


def test_request_cross_binds_scope_base_authority_and_policy_axes() -> None:
    payload = _request_payload()
    payload["scope"]["jurisdiction_scope"][0]["jurisdiction_code"] = "ALT"
    with pytest.raises(ValidationError, match="jurisdiction-subject bindings"):
        _validate(payload)

    payload = _request_payload()
    payload["base_scenario"]["technology_authorities"][0]["technology_id"] = "solar_pv"
    with pytest.raises(ValidationError, match="technology bindings must match"):
        _validate(payload)

    payload = _request_payload()
    route = _domain_disposition(payload, "project_resource")["authority_routes"][0]
    route["jurisdiction_binding_id"] = "jurisdiction-binding:missing"
    with pytest.raises(ValidationError, match="dangling jurisdiction binding"):
        _validate(payload)

    payload = _request_payload()
    route = _domain_disposition(payload, "project_resource")["authority_routes"][0]
    route["technology_binding_id"] = "technology-binding:missing"
    with pytest.raises(ValidationError, match="dangling technology binding"):
        _validate(payload)

    payload = _request_payload()
    site_jurisdiction = _assertion(payload, "assertion:site-jurisdiction")
    site_jurisdiction["base_domain"] = "project_lifecycle_timeline"
    with pytest.raises(ValidationError, match="retained authority route"):
        _validate(payload)


def test_scope_price_axes_bind_every_cost_and_price_assertion() -> None:
    for field, value in (
        ("price_basis_id", "price-basis:other"),
        ("reporting_currency", "EUR"),
        ("price_nominality", "real"),
        ("valuation_date", "2025-08-01"),
    ):
        payload = _request_payload()
        payload["scope"][field] = value
        with pytest.raises(ValidationError, match="scope"):
            _validate(payload)


def test_scope_elements_require_exact_assertion_and_authority_coverage() -> None:
    payload = _request_payload()
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["assertion_id"] != "assertion:tax-jurisdiction"
    ]
    with pytest.raises(ValidationError, match="every scoped jurisdiction subject"):
        _validate(payload)

    payload = _request_payload()
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["assertion_id"] != "assertion:wind-capacity"
    ]
    _assert_policy_and_request_reject(payload, "per-technology capacity route")

    payload = _request_payload()
    payload["scope"]["technology_scope"].append(
        {
            "technology_binding_id": "technology-binding:bess",
            "technology_id": "bess",
            "asset_class": "storage",
        }
    )
    payload["base_scenario"]["technology_authorities"].append(
        {
            "base_config_key": "bess",
            "technology_binding_id": "technology-binding:bess",
            "technology_id": "bess",
            "asset_class": "storage",
            "authored_technology_kind": "storage",
            "authority_source_id": "source:fictionland-bess-basis",
        }
    )
    _domain_disposition(payload, "technology_resource")["authority_routes"].append(
        {
            "authority_source_id": "source:fictionland-bess-basis",
            "jurisdiction_binding_id": "jurisdiction-binding:site",
            "technology_binding_id": "technology-binding:bess",
        }
    )
    with pytest.raises(ValidationError, match="every scoped technology binding"):
        _validate(payload)


def test_hybrid_and_storage_only_request_graphs_are_element_complete() -> None:
    hybrid = _request_payload()
    _add_storage_technology(hybrid)
    hybrid_policy = _validate_policy(hybrid)
    request = _validate(hybrid)
    assert request.binding_policy == hybrid_policy
    assert {item.asset_class.value for item in request.scope.technology_scope} == {
        "generation",
        "storage",
    }

    storage_only = _request_payload()
    _add_storage_technology(storage_only)
    storage_only["scope"]["technology_scope"] = [
        storage_only["scope"]["technology_scope"][1]
    ]
    storage_only["base_scenario"]["technology_authorities"] = [
        storage_only["base_scenario"]["technology_authorities"][1]
    ]
    for domain in ("project_resource", "technology_resource"):
        disposition = _domain_disposition(storage_only, domain)
        disposition["authority_routes"] = [disposition["authority_routes"][1]]
    storage_only["binding_policy"]["assertions"] = [
        item
        for item in storage_only["binding_policy"]["assertions"]
        if item.get("asset_id") != "asset:wind-01"
    ]
    generation_disposition = next(
        item
        for item in storage_only["binding_policy"]["material_dispositions"]
        if item["category"] == "generation_capacity"
    )
    generation_disposition["disposition"] = "explicitly_out_of_v1"
    generation_disposition["action"] = "exclude_from_v1_no_fallback"
    storage_policy = _validate_policy(storage_only)
    request = _validate(storage_only)
    assert request.binding_policy == storage_policy
    assert [item.asset_class.value for item in request.scope.technology_scope] == [
        "storage"
    ]


def test_non_site_jurisdiction_remains_subject_routed_not_site_inferred() -> None:
    payload = _request_payload()
    payload["scope"]["jurisdiction_scope"][1]["jurisdiction_code"] = "LKA"
    payload["base_scenario"]["subject_authorities"][1]["jurisdiction_code"] = "LKA"
    _assertion(payload, "assertion:tax-jurisdiction")["jurisdiction_code"] = "LKA"
    request = _validate(payload)
    assert {
        (item.subject.value, item.jurisdiction_code)
        for item in request.scope.jurisdiction_scope
    } == {("site", "FIC"), ("tax", "LKA")}


def test_binding_policy_requires_one_disposition_for_every_material_category() -> None:
    payload = _request_payload()
    payload["binding_policy"]["material_dispositions"].pop()
    with pytest.raises(ValidationError, match="disposition every ProjectCase"):
        _validate(payload)

    payload = _request_payload()
    payload["binding_policy"]["material_dispositions"].append(
        copy.deepcopy(payload["binding_policy"]["material_dispositions"][0])
    )
    with pytest.raises(
        ValidationError, match="duplicate ProjectCase material category"
    ):
        _validate(payload)


def test_assertions_and_material_dispositions_must_agree() -> None:
    payload = _request_payload()
    for disposition in payload["binding_policy"]["material_dispositions"]:
        if disposition["category"] == "generation_capacity":
            disposition["disposition"] = "explicitly_out_of_v1"
            disposition["action"] = "exclude_from_v1_no_fallback"
    with pytest.raises(ValidationError, match="must agree for generation_capacity"):
        _validate(payload)

    payload = _request_payload()
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["category"] != "identity"
    ]
    with pytest.raises(ValidationError, match="must agree for identity"):
        _validate(payload)

    payload = _request_payload()
    identity = next(
        item
        for item in payload["binding_policy"]["material_dispositions"]
        if item["category"] == "identity"
    )
    identity["action"] = "refuse_before_gateway"
    with pytest.raises(ValidationError, match="execution action must agree"):
        _validate(payload)


def test_generation_capacity_selector_rules_fail_closed() -> None:
    payload = _request_payload()
    assertion = next(
        item
        for item in payload["binding_policy"]["assertions"]
        if item["kind"] == "generation_capacity_assertion"
    )
    assertion["base_config_key"] = "wind"
    with pytest.raises(ValidationError, match="must not name a technology key"):
        _validate(payload)

    payload = _request_payload()
    assertion = next(
        item
        for item in payload["binding_policy"]["assertions"]
        if item["kind"] == "generation_capacity_assertion"
    )
    assertion["project_case_selector"] = "unit_count"
    with pytest.raises(ValidationError, match="dimensions must match"):
        _validate(payload)

    hostile_routes = (
        ("total_power_capacity", "project_capacity_mw", "MWh", "expected_unit in"),
        ("unit_count", "turbine_count", "MW", "expected_unit=count"),
        (
            "total_power_capacity",
            "turbine_rated_power_mw",
            "MW",
            "dimensions must match",
        ),
    )
    for source, target, unit, message in hostile_routes:
        payload = _request_payload()
        assertion = _assertion(payload, "assertion:project-capacity")
        assertion["project_case_selector"] = source
        assertion["base_selector"] = target
        assertion["expected_unit"] = unit
        if target != "project_capacity_mw":
            assertion["base_config_key"] = "wind"
        if target.startswith("turbine_"):
            assertion["capacity_basis"] = "nameplate"
        with pytest.raises(ValidationError, match=message):
            _validate(payload)

    technology_level = copy.deepcopy(
        _assertion(_request_payload(), "assertion:wind-capacity")
    )
    technology_level["base_config_key"] = None
    with pytest.raises(ValidationError, match="requires base_config_key"):
        GenerationCapacityAssertion.model_validate_json(json.dumps(technology_level))


def test_generation_unitized_routes_accept_only_dimensional_matches() -> None:
    base = {
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
    }
    accepted = GenerationCapacityAssertion.model_validate_json(json.dumps(base))
    assert accepted.expected_unit == "count"

    rated = copy.deepcopy(base)
    rated["assertion_id"] = "assertion:turbine-rating"
    rated["project_case_selector"] = "unit_rated_power"
    rated["base_selector"] = "turbine_rated_power_mw"
    rated["expected_unit"] = "MW"
    assert GenerationCapacityAssertion.model_validate_json(json.dumps(rated))


def test_storage_capacity_selector_dimensions_are_exact() -> None:
    base = {
        "kind": "storage_capacity_assertion",
        "assertion_id": "assertion:bess-power",
        "category": "storage_capacity",
        "asset_id": "asset:bess-01",
        "base_config_key": "bess_1",
        "project_case_selector": "power",
        "base_selector": "technology_power_mw",
        "expected_unit": "MW",
        "electrical_basis": "ac",
        "capacity_basis": "usable",
        "authored_technology_kind": "storage",
    }
    accepted = StorageCapacityAssertion.model_validate_json(json.dumps(base))
    assert accepted.project_case_selector.value == "power"
    base["base_selector"] = "technology_energy_mwh"
    with pytest.raises(ValidationError, match="dimensions must match"):
        StorageCapacityAssertion.model_validate_json(json.dumps(base))

    base["base_selector"] = "technology_power_mw"
    base["expected_unit"] = "MWh"
    with pytest.raises(ValidationError, match="expected_unit in"):
        StorageCapacityAssertion.model_validate_json(json.dumps(base))


def test_cost_assertion_requires_complete_dimension_and_usd_basis() -> None:
    capex = {
        "kind": "cost_compatibility_assertion",
        "assertion_id": "assertion:capex",
        "category": "capex",
        "included_line_ids": ["cost:capex:one"],
        "price_basis_id": "price-basis:usd",
        "reporting_currency": "USD",
        "periodicity": "one_time",
        "base_selector": "capex_usd_total",
    }
    assert CostCompatibilityAssertion.model_validate_json(json.dumps(capex))

    for field, value, message in [
        ("included_line_ids", [], "requires included_line_ids"),
        ("periodicity", "annual", "must agree"),
        ("reporting_currency", "LKR", "supports authored USD totals only"),
    ]:
        hostile = copy.deepcopy(capex)
        hostile[field] = value
        with pytest.raises(ValidationError, match=message):
            CostCompatibilityAssertion.model_validate_json(json.dumps(hostile))


def test_cost_compatibility_line_membership_cannot_overlap() -> None:
    payload = _request_payload()
    capex = _assertion(payload, "assertion:capex")
    opex = _assertion(payload, "assertion:opex")
    opex["included_line_ids"] = list(capex["included_line_ids"])
    with pytest.raises(ValidationError, match="must not reuse line IDs"):
        _validate(payload)


def test_policy_refuses_empty_duplicate_routes_and_duplicate_targets() -> None:
    payload = _request_payload()
    payload["binding_policy"]["assertions"] = []
    with pytest.raises(ValidationError, match="requires compatibility assertions"):
        V14BindingPolicy.model_validate_json(json.dumps(payload["binding_policy"]))

    payload = _request_payload()
    duplicate = copy.deepcopy(_assertion(payload, "assertion:location"))
    duplicate["assertion_id"] = "assertion:location-duplicate-route"
    payload["binding_policy"]["assertions"].append(duplicate)
    with pytest.raises(ValidationError, match="duplicate compatibility source"):
        V14BindingPolicy.model_validate_json(json.dumps(payload["binding_policy"]))

    payload = _request_payload()
    duplicate = copy.deepcopy(_assertion(payload, "assertion:location"))
    duplicate["assertion_id"] = "assertion:location-second-source"
    duplicate["project_case_selector"] = "site_name"
    payload["binding_policy"]["assertions"].append(duplicate)
    with pytest.raises(
        ValidationError, match="duplicate authored compatibility target"
    ):
        V14BindingPolicy.model_validate_json(json.dumps(payload["binding_policy"]))


def test_project_case_material_cannot_bypass_assertion_with_base_retention() -> None:
    payload = _request_payload()
    identity = next(
        item
        for item in payload["binding_policy"]["material_dispositions"]
        if item["category"] == "identity"
    )
    identity["disposition"] = "retain_base_authority"
    identity["action"] = "retain_base_authority"
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["category"] != "identity"
    ]

    for validator in _draft_validators():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(payload)
    with pytest.raises(ValidationError):
        _validate(payload)
    assert "retain_base_authority" not in json.dumps(
        V14BindingPolicy.model_json_schema(), sort_keys=True
    )


def test_material_category_error_is_stable_across_hash_seeds() -> None:
    payload = _request_payload()["binding_policy"]
    payload["assertions"] = [
        item
        for item in payload["assertions"]
        if item["category"] not in {"identity", "location", "capex"}
    ]
    script = """
import json
import sys
from pydantic import ValidationError
from analytics.feasibility_report_contract import V14BindingPolicy

try:
    V14BindingPolicy.model_validate_json(sys.stdin.read())
except ValidationError as exc:
    issue = exc.errors(include_url=False)[0]
    print(json.dumps({"loc": issue["loc"], "msg": issue["msg"]}, sort_keys=True))
else:
    raise SystemExit("invalid policy accepted")
"""
    outcomes: set[str] = set()
    for seed in range(16):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_ROOT,
            env={
                **dict(__import__("os").environ),
                "PYTHONHASHSEED": str(seed),
                "PYTHONPATH": str(_ROOT),
            },
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
        )
        outcomes.add(completed.stdout.strip().splitlines()[-1])
    assert len(outcomes) == 1
    assert "identity" in outcomes.pop()


def test_domain_authority_routes_have_one_semantic_owner() -> None:
    payload = _request_payload()
    project_resource = _domain_disposition(payload, "project_resource")
    duplicate = copy.deepcopy(project_resource["authority_routes"][0])
    duplicate["authority_source_id"] = "source:fictionland-authored-base"
    project_resource["authority_routes"].append(duplicate)
    with pytest.raises(ValidationError, match="duplicate base domain authority route"):
        _validate(payload)


def test_contract_schema_and_semantic_policy_globals_are_immutable() -> None:
    before = AssessmentScope.model_json_schema(mode="validation")
    module_globals = vars(assessment_scope_contract)
    without_jurisdiction = module_globals["_DOMAINS_WITHOUT_JURISDICTION_ROUTE"]
    allowed_subjects = module_globals["_DOMAIN_ALLOWED_SUBJECTS"]
    category_order = module_globals["_PROJECT_CASE_MATERIAL_CATEGORY_ORDER"]
    assert isinstance(without_jurisdiction, frozenset)
    assert without_jurisdiction == _EXPECTED_DOMAINS_WITHOUT_JURISDICTION_ROUTE
    assert dict(allowed_subjects) == _EXPECTED_DOMAIN_ALLOWED_SUBJECTS
    assert dict(category_order) == {
        category.value: position
        for position, category in enumerate(ProjectCaseMaterialCategory)
    }
    with pytest.raises(AttributeError):
        without_jurisdiction.add("other")
    with pytest.raises(TypeError):
        allowed_subjects[next(iter(allowed_subjects))] = frozenset()
    with pytest.raises(TypeError):
        category_order[ProjectCaseMaterialCategory.IDENTITY.value] = 99
    assert not any(
        name.endswith("_JSON_SCHEMA") and isinstance(value, dict)
        for name, value in module_globals.items()
    )
    assert AssessmentScope.model_json_schema(mode="validation") == before


def test_d3b_schemas_do_not_retain_mutable_d3a_metadata() -> None:
    script = """
from pydantic import TypeAdapter

from analytics.feasibility_report_contract import EvaluationRequest
import analytics.feasibility_report_contract.project_case as project_case_contract

before = {
    mode: EvaluationRequest.model_json_schema(mode=mode)
    for mode in ("validation", "serialization")
}
project_case_contract._STABLE_IDENTIFIER_JSON_SCHEMA["maxLength"] = 999999
project_case_contract._PROJECT_CASE_SEMVER_JSON_SCHEMA["pattern"] = "^.*$"
assert TypeAdapter(project_case_contract.StableIdentifier).json_schema()["maxLength"] == 999999
assert TypeAdapter(project_case_contract.ProjectCaseSemanticVersion).json_schema()["pattern"] == "^.*$"
after = {
    mode: EvaluationRequest.model_json_schema(mode=mode)
    for mode in ("validation", "serialization")
}
assert after == before
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(_ROOT)},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("unit", ["MWdc", "MWp"])
def test_solar_dc_capacity_has_one_exact_authored_resource_route(unit: str) -> None:
    payload = _request_payload()
    _replace_wind_with_solar_dc(payload, unit=unit)
    request = _validate(payload)
    capacity = next(
        item
        for item in request.binding_policy.assertions
        if isinstance(item, GenerationCapacityAssertion)
    )
    assert capacity.expected_unit == unit
    assert capacity.base_selector.value == "solar_resource_dc_capacity_mw"
    for validator in _draft_validators():
        validator.validate(request.model_dump(mode="json"))


@pytest.mark.parametrize("unit", ["MW", "MVA", "MWh"])
def test_solar_dc_capacity_refuses_erased_or_wrong_dimensions(unit: str) -> None:
    payload = _request_payload()
    _replace_wind_with_solar_dc(payload, unit=unit)
    with pytest.raises(
        ValidationError, match="electrical basis requires expected_unit"
    ):
        _validate(payload)

    payload = _request_payload()
    _replace_wind_with_solar_dc(payload)
    capacity = _assertion(payload, "assertion:wind-capacity")
    capacity["base_selector"] = "technology_capacity_mw"
    with pytest.raises(ValidationError, match="cannot bind an authored AC/MW selector"):
        _validate(payload)


@pytest.mark.parametrize(
    ("source", "target", "unit"),
    [
        ("unit_count", "turbine_count", "count"),
        ("unit_rated_power", "turbine_rated_power_mw", "MWdc"),
        ("total_power_capacity", "turbine_total_capacity_mw", "MWdc"),
    ],
)
def test_solar_technology_cannot_target_wind_turbine_fields(
    source: str, target: str, unit: str
) -> None:
    payload = _request_payload()
    _replace_wind_with_solar_dc(payload)
    capacity = _assertion(payload, "assertion:wind-capacity")
    capacity.update(
        {
            "project_case_selector": source,
            "base_selector": target,
            "expected_unit": unit,
        }
    )
    with pytest.raises(ValidationError, match="authored_technology_kind=wind_turbine"):
        _validate(payload)


def test_policy_and_base_authority_share_exact_authored_kind() -> None:
    payload = _request_payload()
    payload["base_scenario"]["technology_authorities"][0][
        "authored_technology_kind"
    ] = "generic_generation"
    with pytest.raises(ValidationError, match="exact base technology authority"):
        _validate(payload)


def test_policy_requires_a_same_asset_generation_technology_owner() -> None:
    payload = _request_payload()
    _assertion(payload, "assertion:wind-technology")["asset_id"] = "asset:other"
    _assert_policy_and_request_reject(payload, "matching generation asset technology")


def test_policy_requires_a_same_asset_storage_technology_owner() -> None:
    payload = _request_payload()
    _add_storage_technology(payload)
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["assertion_id"] != "assertion:bess-technology"
    ]
    _assert_policy_and_request_reject(payload, "matching storage asset technology")


def test_policy_capacity_and_technology_keys_match() -> None:
    payload = _request_payload()
    _assertion(payload, "assertion:wind-capacity")["base_config_key"] = "wind-other"
    _assert_policy_and_request_reject(payload, "same base config key")


def test_policy_storage_and_technology_keys_match() -> None:
    payload = _request_payload()
    _add_storage_technology(payload)
    _assertion(payload, "assertion:bess-energy")["base_config_key"] = "bess-other"
    _assert_policy_and_request_reject(payload, "same base config key")


def test_policy_capacity_and_technology_kinds_match() -> None:
    payload = _request_payload()
    technology = _assertion(payload, "assertion:wind-technology")
    technology["authored_technology_kind"] = "generic_generation"
    payload["base_scenario"]["technology_authorities"][0][
        "authored_technology_kind"
    ] = "generic_generation"
    _assert_policy_and_request_reject(payload, "same authored technology kind")


def test_policy_technology_assertions_have_unique_physical_owners() -> None:
    payload = _request_payload()
    _add_storage_technology(payload)
    _assertion(payload, "assertion:bess-technology")["asset_id"] = "asset:wind-01"
    _assert_policy_and_request_reject(payload, "unique ProjectCase asset IDs")


def test_policy_technology_assertions_have_unique_binding_ids() -> None:
    payload = _request_payload()
    _add_storage_technology(payload)
    technology = _assertion(payload, "assertion:bess-technology")
    technology["technology_binding_id"] = "technology-binding:wind"
    _assert_policy_and_request_reject(
        payload, "one policy-owned physical asset per technology binding ID"
    )


def test_policy_technology_identity_has_one_binding_id() -> None:
    payload = _request_payload()
    _add_solar_technology(payload)
    _assertion(payload, "assertion:solar-technology")["technology_id"] = "wind"

    for assertions in (
        payload["binding_policy"]["assertions"],
        list(reversed(payload["binding_policy"]["assertions"])),
    ):
        candidate = copy.deepcopy(payload)
        candidate["binding_policy"]["assertions"] = assertions
        _assert_policy_and_request_reject(
            candidate, "duplicate technology assertion scope"
        )


def test_policy_distinct_generation_technology_identities_are_valid() -> None:
    payload = _request_payload()
    _add_solar_technology(payload)

    policy = _validate_policy(payload)
    request = _validate(payload)

    assert request.binding_policy == policy
    assert {
        (item.technology_id, item.asset_class.value)
        for item in request.scope.technology_scope
    } == {("solar_pv", "generation"), ("wind", "generation")}


def test_policy_storage_routes_are_complete() -> None:
    payload = _request_payload()
    _add_storage_technology(payload)
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["assertion_id"] != "assertion:bess-energy"
    ]
    _assert_policy_and_request_reject(payload, "power, energy, and duration routes")


def test_policy_repeated_jurisdiction_binding_keeps_one_identity() -> None:
    payload = _request_payload()
    second_route = copy.deepcopy(_assertion(payload, "assertion:site-jurisdiction"))
    second_route.update(
        {
            "assertion_id": "assertion:site-location-jurisdiction",
            "base_domain": "project_identity_location",
        }
    )
    payload["binding_policy"]["assertions"].append(second_route)
    policy = _validate_policy(payload)
    request = _validate(payload)
    assert request.binding_policy == policy

    second_route["jurisdiction_code"] = "ALT"
    _assert_policy_and_request_reject(
        payload, "share exact jurisdiction code and subject"
    )


def test_policy_jurisdiction_identity_has_one_binding_id() -> None:
    payload = _request_payload()
    aliased_route = copy.deepcopy(_assertion(payload, "assertion:site-jurisdiction"))
    aliased_route.update(
        {
            "assertion_id": "assertion:site-jurisdiction-alias",
            "jurisdiction_binding_id": "jurisdiction-binding:site-alias",
            "base_domain": "project_identity_location",
        }
    )
    payload["binding_policy"]["assertions"].append(aliased_route)

    for assertions in (
        payload["binding_policy"]["assertions"],
        list(reversed(payload["binding_policy"]["assertions"])),
    ):
        candidate = copy.deepcopy(payload)
        candidate["binding_policy"]["assertions"] = assertions
        _assert_policy_and_request_reject(
            candidate,
            "one binding ID per exact jurisdiction code and subject",
        )


@pytest.mark.parametrize(
    ("assertion_id", "field", "value"),
    [
        ("assertion:opex", "price_basis_id", "price-basis:other"),
        ("assertion:price-basis", "reporting_currency", "EUR"),
    ],
)
def test_policy_costs_and_price_assertion_share_price_identity(
    assertion_id: str,
    field: str,
    value: str,
) -> None:
    payload = _request_payload()
    _assertion(payload, assertion_id)[field] = value
    _assert_policy_and_request_reject(
        payload, "share price basis and reporting currency"
    )


def test_policy_requires_exactly_one_price_assertion() -> None:
    payload = _request_payload()
    payload["binding_policy"]["assertions"] = [
        item
        for item in payload["binding_policy"]["assertions"]
        if item["assertion_id"] != "assertion:price-basis"
    ]
    price_disposition = next(
        item
        for item in payload["binding_policy"]["material_dispositions"]
        if item["category"] == "price_basis"
    )
    price_disposition["disposition"] = "explicitly_out_of_v1"
    price_disposition["action"] = "exclude_from_v1_no_fallback"
    _assert_policy_and_request_reject(payload, "exactly one price-basis assertion")


def test_policy_basis_first_error_is_independent_of_assertion_order() -> None:
    original = _request_payload()
    _assertion(original, "assertion:wind-capacity")["capacity_basis"] = "gross"
    _add_storage_technology(original)
    _assertion(original, "assertion:bess-energy")["capacity_basis"] = "gross"
    reordered = copy.deepcopy(original)
    reordered["binding_policy"]["assertions"].sort(
        key=lambda item: item["category"] != "storage_capacity"
    )

    for validate in (_validate_policy, _validate):
        messages: list[str] = []
        for payload in (original, reordered):
            with pytest.raises(ValidationError) as exc_info:
                validate(payload)
            messages.append(exc_info.value.errors()[0]["msg"])
        assert messages[0] == messages[1]
        assert "generation capacity assertions" in messages[0]


def test_policy_child_errors_are_canonical_and_authored_order_round_trips() -> None:
    source = _request_payload()
    authored = source["binding_policy"]["assertions"]
    shuffled = copy.deepcopy(authored)
    random.Random(20260830).shuffle(shuffled)
    variants = (
        copy.deepcopy(authored),
        list(reversed(copy.deepcopy(authored))),
        copy.deepcopy(authored[4:] + authored[:4]),
        shuffled,
    )

    expected_locations = {
        _validate_policy: (
            "assertions",
            2,
            "jurisdiction_subject_assertion",
        ),
        _validate: (
            "binding_policy",
            "assertions",
            2,
            "jurisdiction_subject_assertion",
        ),
    }
    for validate, expected_location in expected_locations.items():
        first_issues: list[tuple[tuple[object, ...], str]] = []
        for assertions in variants:
            payload = _request_payload()
            payload["binding_policy"]["assertions"] = copy.deepcopy(assertions)
            site_assertion = _assertion(payload, "assertion:site-jurisdiction")
            tax_assertion = _assertion(payload, "assertion:tax-jurisdiction")
            site_assertion["base_domain"] = "tax_statutory"
            tax_assertion["base_domain"] = "project_resource"
            with pytest.raises(ValidationError) as exc_info:
                validate(payload)
            issue = exc_info.value.errors(include_url=False)[0]
            first_issues.append((tuple(issue["loc"]), issue["msg"]))

        assert len(set(first_issues)) == 1
        location, message = first_issues[0]
        assert location == expected_location
        assert message == (
            "Value error, jurisdiction subject site cannot govern tax_statutory"
        )

    for assertions in variants:
        payload = _request_payload()
        payload["binding_policy"]["assertions"] = copy.deepcopy(assertions)
        expected_ids = tuple(item["assertion_id"] for item in assertions)
        policy = _validate_policy(payload)
        request = _validate(payload)
        for validated_policy in (policy, request.binding_policy):
            assert (
                tuple(item.assertion_id for item in validated_policy.assertions)
                == expected_ids
            )
            dumped = validated_policy.model_dump(mode="json")
            assert tuple(item["assertion_id"] for item in dumped["assertions"]) == (
                expected_ids
            )


def test_policy_child_error_order_is_stable_across_hash_seeds() -> None:
    source = _request_payload()
    authored = source["binding_policy"]["assertions"]
    shuffled = copy.deepcopy(authored)
    random.Random(20260830).shuffle(shuffled)
    variants = (
        copy.deepcopy(authored),
        list(reversed(copy.deepcopy(authored))),
        copy.deepcopy(authored[4:] + authored[:4]),
        shuffled,
    )
    payloads: list[dict[str, Any]] = []
    for assertions in variants:
        payload = _request_payload()
        payload["binding_policy"]["assertions"] = copy.deepcopy(assertions)
        site_assertion = _assertion(payload, "assertion:site-jurisdiction")
        tax_assertion = _assertion(payload, "assertion:tax-jurisdiction")
        site_assertion["base_domain"] = "tax_statutory"
        tax_assertion["base_domain"] = "project_resource"
        payloads.append(payload)

    script = """
import json
import sys
from pydantic import ValidationError
from analytics.feasibility_report_contract import EvaluationRequest, V14BindingPolicy

payloads = json.loads(sys.stdin.read())
outcomes = []
for payload in payloads:
    for root in ("policy", "request"):
        try:
            if root == "policy":
                V14BindingPolicy.model_validate_json(json.dumps(payload["binding_policy"]))
            else:
                EvaluationRequest.model_validate_json(json.dumps(payload))
        except ValidationError as exc:
            issue = exc.errors(include_url=False)[0]
            outcomes.append({"root": root, "loc": issue["loc"], "msg": issue["msg"]})
        else:
            raise SystemExit("invalid child assertions accepted")
print(json.dumps(outcomes, sort_keys=True))
"""
    receipts: set[str] = set()
    for seed in range(8):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_ROOT,
            env={
                **dict(__import__("os").environ),
                "PYTHONHASHSEED": str(seed),
                "PYTHONPATH": str(_ROOT),
            },
            input=json.dumps(payloads),
            capture_output=True,
            text=True,
            check=True,
        )
        receipts.add(completed.stdout.strip().splitlines()[-1])

    assert len(receipts) == 1
    issues = json.loads(receipts.pop())
    policy_issues = [item for item in issues if item["root"] == "policy"]
    request_issues = [item for item in issues if item["root"] == "request"]
    assert policy_issues == [policy_issues[0]] * len(variants)
    assert request_issues == [request_issues[0]] * len(variants)
    assert policy_issues[0]["loc"] == [
        "assertions",
        2,
        "jurisdiction_subject_assertion",
    ]
    assert request_issues[0]["loc"] == [
        "binding_policy",
        "assertions",
        2,
        "jurisdiction_subject_assertion",
    ]


def test_policy_duplicate_id_child_errors_use_total_outcome_order() -> None:
    json_payload = _request_payload()
    python_payload = _validate(_request_payload()).model_dump()
    receipts: dict[str, list[tuple[dict[str, Any], ...]]] = {
        "policy": [],
        "request": [],
    }

    for mode, source in (("json", json_payload), ("python", python_payload)):
        for exchange_children in (False, True):
            payload = copy.deepcopy(source)
            assertions = list(payload["binding_policy"]["assertions"])
            site_index = next(
                index
                for index, item in enumerate(assertions)
                if item.get("jurisdiction_binding_id") == "jurisdiction-binding:site"
            )
            tax_index = next(
                index
                for index, item in enumerate(assertions)
                if item.get("jurisdiction_binding_id") == "jurisdiction-binding:tax"
            )
            site_assertion = assertions[site_index]
            tax_assertion = assertions[tax_index]
            tax_assertion["assertion_id"] = site_assertion["assertion_id"]
            site_assertion["base_domain"] = (
                "tax_statutory" if mode == "json" else BaseConfigDomain.TAX_STATUTORY
            )
            tax_assertion["base_domain"] = (
                "project_resource"
                if mode == "json"
                else BaseConfigDomain.PROJECT_RESOURCE
            )
            if exchange_children:
                assertions[site_index], assertions[tax_index] = (
                    assertions[tax_index],
                    assertions[site_index],
                )
            payload["binding_policy"]["assertions"] = (
                assertions if mode == "json" else tuple(assertions)
            )

            for root in ("policy", "request"):
                with pytest.raises(ValidationError) as exc_info:
                    if (mode, root) == ("json", "policy"):
                        V14BindingPolicy.model_validate_json(
                            json.dumps(payload["binding_policy"])
                        )
                    elif (mode, root) == ("json", "request"):
                        EvaluationRequest.model_validate_json(json.dumps(payload))
                    elif root == "policy":
                        V14BindingPolicy.model_validate(payload["binding_policy"])
                    else:
                        EvaluationRequest.model_validate(payload)
                errors = tuple(exc_info.value.errors(include_url=False))
                assert {error["input"] for error in errors} == {
                    "<invalid compatibility assertion>"
                }
                assert all("ctx" not in error for error in errors)
                receipts[root].append(errors)

    assert receipts["policy"] == [receipts["policy"][0]] * 4
    assert receipts["request"] == [receipts["request"][0]] * 4
    assert [tuple(issue["loc"]) for issue in receipts["policy"][0]] == [
        ("assertions", 2, "jurisdiction_subject_assertion"),
        ("assertions", 3, "jurisdiction_subject_assertion"),
    ]
    assert [issue["msg"] for issue in receipts["policy"][0]] == [
        "Value error, jurisdiction subject site cannot govern tax_statutory",
        "Value error, jurisdiction subject tax cannot govern project_resource",
    ]


def test_policy_duplicate_id_child_errors_are_hash_seed_stable() -> None:
    script = """
import copy
import json
import sys
from pydantic import ValidationError
from analytics.feasibility_report_contract import (
    BaseConfigDomain,
    EvaluationRequest,
    V14BindingPolicy,
)

json_source = json.loads(sys.stdin.read())
python_source = EvaluationRequest.model_validate_json(
    json.dumps(json_source)
).model_dump()
outcomes = []
for mode, source in (("json", json_source), ("python", python_source)):
    for exchange_children in (False, True):
        payload = copy.deepcopy(source)
        assertions = list(payload["binding_policy"]["assertions"])
        site_index = next(
            index
            for index, item in enumerate(assertions)
            if item.get("jurisdiction_binding_id") == "jurisdiction-binding:site"
        )
        tax_index = next(
            index
            for index, item in enumerate(assertions)
            if item.get("jurisdiction_binding_id") == "jurisdiction-binding:tax"
        )
        site = assertions[site_index]
        tax = assertions[tax_index]
        tax["assertion_id"] = site["assertion_id"]
        site["base_domain"] = (
            "tax_statutory"
            if mode == "json"
            else BaseConfigDomain.TAX_STATUTORY
        )
        tax["base_domain"] = (
            "project_resource"
            if mode == "json"
            else BaseConfigDomain.PROJECT_RESOURCE
        )
        if exchange_children:
            assertions[site_index], assertions[tax_index] = (
                assertions[tax_index], assertions[site_index]
            )
        payload["binding_policy"]["assertions"] = (
            assertions if mode == "json" else tuple(assertions)
        )

        for root in ("policy", "request"):
            try:
                if (mode, root) == ("json", "policy"):
                    V14BindingPolicy.model_validate_json(
                        json.dumps(payload["binding_policy"])
                    )
                elif (mode, root) == ("json", "request"):
                    EvaluationRequest.model_validate_json(json.dumps(payload))
                elif root == "policy":
                    V14BindingPolicy.model_validate(payload["binding_policy"])
                else:
                    EvaluationRequest.model_validate(payload)
            except ValidationError as exc:
                errors = exc.errors(include_url=False)
                outcomes.append({"mode": mode, "root": root, "errors": errors})
            else:
                raise SystemExit("invalid duplicate-ID children accepted")
print(json.dumps(outcomes, sort_keys=True))
"""
    receipts: set[str] = set()
    for seed in range(8):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_ROOT,
            env={
                **dict(__import__("os").environ),
                "PYTHONHASHSEED": str(seed),
                "PYTHONPATH": str(_ROOT),
            },
            input=json.dumps(_request_payload()),
            capture_output=True,
            text=True,
            check=True,
        )
        receipts.add(completed.stdout.strip().splitlines()[-1])

    assert len(receipts) == 1
    outcomes = json.loads(receipts.pop())
    for root in ("policy", "request"):
        root_receipts = [item["errors"] for item in outcomes if item["root"] == root]
        assert root_receipts == [root_receipts[0]] * 4


def test_policy_fully_tied_child_errors_have_bounded_public_surface() -> None:
    json_source = _request_payload()
    python_source = _validate(_request_payload()).model_dump()
    receipts: dict[tuple[str, str], list[dict[str, object]]] = {}

    for mode, source in (("json", json_source), ("python", python_source)):
        for scalar_children in ((1, 2), (2, 1)):
            payload = copy.deepcopy(source)
            payload["binding_policy"]["assertions"] = (
                list(scalar_children) if mode == "json" else scalar_children
            )
            for root in ("policy", "request"):
                with pytest.raises(ValidationError) as exc_info:
                    if (mode, root) == ("json", "policy"):
                        V14BindingPolicy.model_validate_json(
                            json.dumps(payload["binding_policy"])
                        )
                    elif (mode, root) == ("json", "request"):
                        EvaluationRequest.model_validate_json(json.dumps(payload))
                    elif root == "policy":
                        V14BindingPolicy.model_validate(payload["binding_policy"])
                    else:
                        EvaluationRequest.model_validate(payload)

                errors = exc_info.value.errors(include_url=False)
                receipts.setdefault((mode, root), []).append(
                    {
                        "errors": errors,
                        "text": str(exc_info.value),
                        "json": exc_info.value.json(include_url=False),
                    }
                )
                assert {error["input"] for error in errors} == {
                    "<invalid compatibility assertion>"
                }
                assert all("ctx" not in error for error in errors)

    for mode in ("json", "python"):
        for root in ("policy", "request"):
            mode_root_receipts = receipts[(mode, root)]
            assert mode_root_receipts == [mode_root_receipts[0]] * 2


def test_policy_fully_tied_child_errors_are_hash_seed_stable() -> None:
    script = """
import copy
import json
import sys
from pydantic import ValidationError
from analytics.feasibility_report_contract import EvaluationRequest, V14BindingPolicy

json_source = json.loads(sys.stdin.read())
python_source = EvaluationRequest.model_validate_json(
    json.dumps(json_source)
).model_dump()
outcomes = []
for mode, source in (("json", json_source), ("python", python_source)):
    for scalar_children in ((1, 2), (2, 1)):
        payload = copy.deepcopy(source)
        payload["binding_policy"]["assertions"] = (
            list(scalar_children) if mode == "json" else scalar_children
        )
        for root in ("policy", "request"):
            try:
                if (mode, root) == ("json", "policy"):
                    V14BindingPolicy.model_validate_json(
                        json.dumps(payload["binding_policy"])
                    )
                elif (mode, root) == ("json", "request"):
                    EvaluationRequest.model_validate_json(json.dumps(payload))
                elif root == "policy":
                    V14BindingPolicy.model_validate(payload["binding_policy"])
                else:
                    EvaluationRequest.model_validate(payload)
            except ValidationError as exc:
                outcomes.append(
                    {
                        "mode": mode,
                        "root": root,
                        "errors": exc.errors(include_url=False),
                        "text": str(exc),
                        "json": json.loads(exc.json(include_url=False)),
                    }
                )
            else:
                raise SystemExit("invalid scalar children accepted")
print(json.dumps(outcomes, sort_keys=True))
"""
    receipts: set[str] = set()
    for seed in range(8):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_ROOT,
            env={
                **dict(__import__("os").environ),
                "PYTHONHASHSEED": str(seed),
                "PYTHONPATH": str(_ROOT),
            },
            input=json.dumps(_request_payload()),
            capture_output=True,
            text=True,
            check=True,
        )
        receipts.add(completed.stdout.strip().splitlines()[-1])

    assert len(receipts) == 1
    outcomes = json.loads(receipts.pop())
    for mode in ("json", "python"):
        for root in ("policy", "request"):
            mode_root_receipts = [
                {
                    "errors": item["errors"],
                    "text": item["text"],
                    "json": item["json"],
                }
                for item in outcomes
                if item["mode"] == mode and item["root"] == root
            ]
            assert mode_root_receipts == [mode_root_receipts[0]] * 2


def test_policy_raw_key_extraction_does_not_dispatch_dict_subclasses() -> None:
    class RaisingGetDict(dict[str, object]):
        get_calls = 0

        def get(self, key: object, default: object = None) -> object:
            self.get_calls += 1
            raise RuntimeError("overridden get must not execute")

    class StatefulGetDict(dict[str, object]):
        get_calls = 0

        def get(self, key: object, default: object = None) -> object:
            self.get_calls += 1
            if key == "category":
                return "identity" if self.get_calls % 2 else "price_basis"
            return dict.get(self, key, default)

    for hostile_child in (
        RaisingGetDict(
            {
                "kind": "unknown_hostile_assertion",
                "category": "identity",
                "assertion_id": "assertion:hostile-child",
            }
        ),
        StatefulGetDict(
            {
                "kind": "unknown_hostile_assertion",
                "category": "identity",
                "assertion_id": "assertion:hostile-child",
            }
        ),
    ):
        payload = _validate(_request_payload()).model_dump()
        payload["binding_policy"]["assertions"] = (
            hostile_child,
            {
                "kind": "unknown_regular_assertion",
                "category": "location",
                "assertion_id": "assertion:regular-child",
            },
        )

        for root in ("policy", "request"):
            receipts: list[dict[str, object]] = []
            for _ in range(2):
                with pytest.raises(ValidationError) as exc_info:
                    if root == "policy":
                        V14BindingPolicy.model_validate(payload["binding_policy"])
                    else:
                        EvaluationRequest.model_validate(payload)
                receipts.append(
                    {
                        "errors": exc_info.value.errors(),
                        "text": str(exc_info.value),
                        "json": exc_info.value.json(),
                    }
                )
            assert receipts[0] == receipts[1]

        assert hostile_child.get_calls == 0


def test_policy_raw_key_type_allowlist_uses_identity_only() -> None:
    equality_calls: list[object] = []
    trusted_types = (
        assessment_scope_contract.ScenarioIdentityAssertion,
        assessment_scope_contract.LocationAssertion,
        JurisdictionSubjectAssertion,
        assessment_scope_contract.TechnologyBindingAssertion,
        GenerationCapacityAssertion,
        StorageCapacityAssertion,
        CostCompatibilityAssertion,
        assessment_scope_contract.PriceBasisAssertion,
    )

    class RaisingEqualityMeta(type):
        def __eq__(cls, other: object) -> bool:
            if any(other is trusted_type for trusted_type in trusted_types):
                equality_calls.append(other)
                raise RuntimeError("trusted-class equality must not execute")
            return cls is other

        __hash__ = type.__hash__

    class OpaqueChild(metaclass=RaisingEqualityMeta):
        pass

    payload = _validate(_request_payload()).model_dump()
    payload["binding_policy"]["assertions"] = (
        OpaqueChild(),
        {
            "kind": "unknown_regular_assertion",
            "category": "location",
            "assertion_id": "assertion:regular-child",
        },
    )

    for root in ("policy", "request"):
        receipts: list[dict[str, object]] = []
        for _ in range(2):
            with pytest.raises(ValidationError) as exc_info:
                if root == "policy":
                    V14BindingPolicy.model_validate(payload["binding_policy"])
                else:
                    EvaluationRequest.model_validate(payload)
            receipts.append(
                {
                    "errors": exc_info.value.errors(),
                    "text": str(exc_info.value),
                    "json": exc_info.value.json(),
                }
            )
        assert receipts[0] == receipts[1]

    assert equality_calls == []


def test_policy_collection_shape_is_exact_and_non_dispatching() -> None:
    class DynamicClassObject:
        class_calls = 0

        @property
        def __class__(self) -> type[object]:
            self.class_calls += 1
            raise RuntimeError("dynamic class must not execute")

    class RaisingIterationTuple(tuple[object, ...]):
        iteration_calls = 0

        def __iter__(self) -> Any:
            self.iteration_calls += 1
            raise RuntimeError("overridden iterator must not execute")

    for invalid_collection in (
        DynamicClassObject(),
        RaisingIterationTuple((1, 2)),
    ):
        payload = _validate(_request_payload()).model_dump()
        payload["binding_policy"]["assertions"] = invalid_collection

        for root in ("policy", "request"):
            receipts: list[dict[str, object]] = []
            for _ in range(2):
                with pytest.raises(ValidationError) as exc_info:
                    if root == "policy":
                        V14BindingPolicy.model_validate(payload["binding_policy"])
                    else:
                        EvaluationRequest.model_validate(payload)
                receipts.append(
                    {
                        "errors": exc_info.value.errors(),
                        "text": str(exc_info.value),
                        "json": exc_info.value.json(),
                    }
                )
                assert {error["input"] for error in exc_info.value.errors()} == {
                    "<invalid compatibility assertion collection>"
                }
            assert receipts[0] == receipts[1]

        if type(invalid_collection) is DynamicClassObject:
            assert invalid_collection.class_calls == 0
        else:
            assert invalid_collection.iteration_calls == 0


def test_policy_model_subclass_is_bounded_before_outcome_serialization() -> None:
    dump_calls: list[bool] = []

    class RaisingDumpAssertion(assessment_scope_contract.ScenarioIdentityAssertion):
        def model_dump_json(self, *args: object, **kwargs: object) -> str:
            dump_calls.append(True)
            raise RuntimeError("overridden serialization must not execute")

    policy = _validate_policy(_request_payload())
    scenario_assertion = next(
        assertion
        for assertion in policy.assertions
        if type(assertion) is assessment_scope_contract.ScenarioIdentityAssertion
    )
    subclass_child = RaisingDumpAssertion.model_validate(
        scenario_assertion.model_dump()
    )
    payload = _validate(_request_payload()).model_dump()
    payload["binding_policy"]["assertions"] = (
        subclass_child,
        *policy.assertions[1:],
    )

    for root in ("policy", "request"):
        receipts: list[dict[str, object]] = []
        for _ in range(2):
            with pytest.raises(ValidationError) as exc_info:
                if root == "policy":
                    V14BindingPolicy.model_validate(payload["binding_policy"])
                else:
                    EvaluationRequest.model_validate(payload)
            errors = exc_info.value.errors(include_url=False)
            receipts.append(
                {
                    "errors": errors,
                    "text": str(exc_info.value),
                    "json": exc_info.value.json(),
                }
            )
            assert any(
                error["type"] == "compatibility_assertion_type" for error in errors
            )
        assert receipts[0] == receipts[1]

    assert dump_calls == []


def test_policy_exact_model_non_field_state_is_bounded_before_serialization() -> None:
    dump_calls: list[bool] = []

    def raising_dump_json() -> str:
        dump_calls.append(True)
        raise RuntimeError("instance serializer shadow must not execute")

    policy = _validate_policy(_request_payload())
    scenario_assertion = next(
        assertion
        for assertion in policy.assertions
        if type(assertion) is assessment_scope_contract.ScenarioIdentityAssertion
    )
    shadowed_child = scenario_assertion.model_copy(
        update={"model_dump_json": raising_dump_json}
    )
    assert type(shadowed_child) is assessment_scope_contract.ScenarioIdentityAssertion

    assertions = tuple(
        shadowed_child if assertion is scenario_assertion else assertion
        for assertion in policy.assertions
    )
    payload = _validate(_request_payload()).model_dump()
    payload["binding_policy"]["assertions"] = assertions

    for root in ("policy", "request"):
        receipts: list[dict[str, object]] = []
        for _ in range(2):
            with pytest.raises(ValidationError) as exc_info:
                if root == "policy":
                    V14BindingPolicy.model_validate(payload["binding_policy"])
                else:
                    EvaluationRequest.model_validate(payload)
            errors = exc_info.value.errors()
            receipts.append(
                {
                    "errors": errors,
                    "text": str(exc_info.value),
                    "json": exc_info.value.json(),
                }
            )
            assert {error["type"] for error in errors} == {
                "compatibility_assertion_state"
            }
            assert {error["input"] for error in errors} == {
                "<invalid compatibility assertion>"
            }
        assert receipts[0] == receipts[1]

    assert dump_calls == []


def test_policy_hash_colliding_keys_are_opaque_to_raw_ordering() -> None:
    equality_calls: list[object] = []
    hash_calls: list[bool] = []

    class HashCollidingString(str):
        def __hash__(self) -> int:
            hash_calls.append(True)
            return str.__hash__(self)

        def __eq__(self, other: object) -> bool:
            equality_calls.append(other)
            raise RuntimeError("caller equality must not execute")

    policy = _validate_policy(_request_payload())
    scenario_assertion = next(
        assertion
        for assertion in policy.assertions
        if type(assertion) is assessment_scope_contract.ScenarioIdentityAssertion
    )
    scenario_fields = scenario_assertion.model_dump()
    scenario_category = scenario_fields.pop("category")

    constructed_child = (
        assessment_scope_contract.ScenarioIdentityAssertion.model_construct(
            **scenario_fields
        )
    )
    colliding_model_key = HashCollidingString("category")
    poisoned_model = constructed_child.model_copy(
        update={colliding_model_key: scenario_category}
    )
    assert type(poisoned_model) is assessment_scope_contract.ScenarioIdentityAssertion

    colliding_dictionary_key = HashCollidingString("category")
    poisoned_dictionary: dict[object, object] = {
        colliding_dictionary_key: scenario_category
    }
    for field_name, field_value in scenario_fields.items():
        poisoned_dictionary[field_name] = field_value
    assert type(poisoned_dictionary) is dict

    for hostile_child, expected_error_type in (
        (poisoned_model, "compatibility_assertion_state"),
        (poisoned_dictionary, "compatibility_assertion_key"),
    ):
        assertions = tuple(
            hostile_child if assertion is scenario_assertion else assertion
            for assertion in policy.assertions
        )
        payload = _validate(_request_payload()).model_dump()
        payload["binding_policy"]["assertions"] = assertions
        equality_calls.clear()
        hash_calls.clear()

        for root in ("policy", "request"):
            receipts: list[dict[str, object]] = []
            for _ in range(2):
                with pytest.raises(ValidationError) as exc_info:
                    if root == "policy":
                        V14BindingPolicy.model_validate(payload["binding_policy"])
                    else:
                        EvaluationRequest.model_validate(payload)
                errors = exc_info.value.errors()
                receipts.append(
                    {
                        "errors": errors,
                        "text": str(exc_info.value),
                        "json": exc_info.value.json(),
                    }
                )
                assert {error["type"] for error in errors} == {expected_error_type}
                assert {error["input"] for error in errors} == {
                    "<invalid compatibility assertion>"
                }
            assert receipts[0] == receipts[1]

        assert equality_calls == []
        assert hash_calls == []


def test_policy_non_builtin_mappings_are_bounded_before_adapter_dispatch() -> None:
    ledger: dict[str, list[object]] = {
        name: []
        for name in (
            "get",
            "getitem",
            "iter",
            "items",
            "len",
            "equality",
            "hash",
            "str",
            "repr",
        )
    }

    class LedgerMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            ledger["getitem"].append(key)
            raise RuntimeError("mapping item lookup must not execute")

        def __iter__(self) -> Any:
            ledger["iter"].append(True)
            raise RuntimeError("mapping iteration must not execute")

        def __len__(self) -> int:
            ledger["len"].append(True)
            raise RuntimeError("mapping length must not execute")

        def items(self) -> Any:
            ledger["items"].append(True)
            raise RuntimeError("mapping items must not execute")

        def __eq__(self, other: object) -> bool:
            ledger["equality"].append(other)
            raise RuntimeError("mapping equality must not execute")

        def __hash__(self) -> int:
            ledger["hash"].append(True)
            raise RuntimeError("mapping hashing must not execute")

        def __str__(self) -> str:
            ledger["str"].append(True)
            raise RuntimeError("mapping string conversion must not execute")

        def __repr__(self) -> str:
            ledger["repr"].append(True)
            raise RuntimeError("mapping representation must not execute")

    class RaisingGetMapping(LedgerMapping):
        def get(self, key: str, default: object = None) -> object:
            ledger["get"].append(key)
            raise RuntimeError("mapping get must be bounded")

    class InheritedGetMapping(LedgerMapping):
        pass

    class StatefulMapping(LedgerMapping):
        get_count = 0

        def get(self, key: str, default: object = None) -> object:
            ledger["get"].append(key)
            self.get_count += 1
            if key == "kind":
                return (
                    "scenario_identity_assertion"
                    if self.get_count % 2
                    else "unknown_stateful_assertion"
                )
            return default

    policy = _validate_policy(_request_payload())
    scenario_assertion = next(
        assertion
        for assertion in policy.assertions
        if type(assertion) is assessment_scope_contract.ScenarioIdentityAssertion
    )
    for hostile_child in (
        RaisingGetMapping(),
        InheritedGetMapping(),
        StatefulMapping(),
    ):
        assertions = tuple(
            hostile_child if assertion is scenario_assertion else assertion
            for assertion in policy.assertions
        )
        payload = _validate(_request_payload()).model_dump()
        payload["binding_policy"]["assertions"] = assertions
        for calls in ledger.values():
            calls.clear()

        for root in ("policy", "request"):
            receipts: list[dict[str, object]] = []
            for _ in range(2):
                with pytest.raises(ValidationError) as exc_info:
                    if root == "policy":
                        V14BindingPolicy.model_validate(payload["binding_policy"])
                    else:
                        EvaluationRequest.model_validate(payload)
                errors = exc_info.value.errors(include_url=False)
                receipts.append(
                    {
                        "errors": errors,
                        "text": str(exc_info.value),
                        "json": exc_info.value.json(include_url=False),
                    }
                )
                assert len(errors) == 1
                assert errors[0]["type"] == "compatibility_assertion_type"
                assert errors[0]["input"] == "<invalid compatibility assertion>"
                assert "ctx" not in errors[0]
            assert receipts == [receipts[0]] * 2

        assert all(not calls for calls in ledger.values())


def test_policy_non_exact_discriminators_are_bounded_before_adapter_dispatch() -> None:
    ledger: dict[str, list[object]] = {
        name: []
        for name in (
            "get",
            "getitem",
            "iter",
            "items",
            "equality",
            "hash",
            "str",
            "repr",
        )
    }

    class HostileKind(str):
        def __eq__(self, other: object) -> bool:
            ledger["equality"].append(other)
            raise RuntimeError("kind equality must not execute")

        def __hash__(self) -> int:
            ledger["hash"].append(True)
            raise RuntimeError("kind hashing must not execute")

        def __str__(self) -> str:
            ledger["str"].append(True)
            raise RuntimeError("kind string conversion must not execute")

        def __repr__(self) -> str:
            ledger["repr"].append(True)
            raise RuntimeError("kind representation must not execute")

    policy = _validate_policy(_request_payload())
    scenario_assertion = next(
        assertion
        for assertion in policy.assertions
        if type(assertion) is assessment_scope_contract.ScenarioIdentityAssertion
    )
    exact_dictionary = scenario_assertion.model_dump()
    exact_dictionary["kind"] = HostileKind("scenario_identity_assertion")
    missing_dictionary = scenario_assertion.model_dump()
    missing_dictionary.pop("kind")
    unknown_dictionary = scenario_assertion.model_dump()
    unknown_dictionary["kind"] = "unknown_compatibility_assertion"
    exact_model = scenario_assertion.model_copy(
        update={"kind": HostileKind("scenario_identity_assertion")}
    )
    unknown_model = scenario_assertion.model_copy(
        update={"kind": "unknown_compatibility_assertion"}
    )

    for hostile_child in (
        exact_dictionary,
        missing_dictionary,
        unknown_dictionary,
        exact_model,
        unknown_model,
    ):
        assertions = tuple(
            hostile_child if assertion is scenario_assertion else assertion
            for assertion in policy.assertions
        )
        payload = _validate(_request_payload()).model_dump()
        payload["binding_policy"]["assertions"] = assertions
        for calls in ledger.values():
            calls.clear()

        for root in ("policy", "request"):
            receipts: list[dict[str, object]] = []
            for _ in range(2):
                with pytest.raises(ValidationError) as exc_info:
                    if root == "policy":
                        V14BindingPolicy.model_validate(payload["binding_policy"])
                    else:
                        EvaluationRequest.model_validate(payload)
                errors = exc_info.value.errors(include_url=False)
                receipts.append(
                    {
                        "errors": errors,
                        "text": str(exc_info.value),
                        "json": exc_info.value.json(include_url=False),
                    }
                )
                assert len(errors) == 1
                assert errors[0]["type"] == "compatibility_assertion_discriminator"
                assert errors[0]["input"] == "<invalid compatibility assertion>"
                assert "ctx" not in errors[0]
            assert receipts == [receipts[0]] * 2

        assert all(not calls for calls in ledger.values())


def test_policy_canonical_child_validator_preserves_python_strictness() -> None:
    policy = _validate_policy(_request_payload())
    normalized = policy.model_dump()
    assert V14BindingPolicy.model_validate(normalized) == policy

    model_children = copy.deepcopy(normalized)
    model_children["assertions"] = policy.assertions
    assert V14BindingPolicy.model_validate(model_children) == policy

    list_children = copy.deepcopy(normalized)
    list_children["assertions"] = list(policy.assertions)
    with pytest.raises(ValidationError, match="valid tuple"):
        V14BindingPolicy.model_validate(list_children)

    non_collection = copy.deepcopy(normalized)
    non_collection["assertions"] = 1
    with pytest.raises(ValidationError):
        V14BindingPolicy.model_validate(non_collection)

    malformed_child = copy.deepcopy(normalized)
    malformed_child["assertions"][0]["category"] = 1
    with pytest.raises(ValidationError):
        V14BindingPolicy.model_validate(malformed_child)

    scalar_child = copy.deepcopy(normalized)
    scalar_child["assertions"] = (1, *policy.assertions)
    with pytest.raises(ValidationError):
        V14BindingPolicy.model_validate(scalar_child)


@pytest.mark.parametrize(
    ("assertion_id", "capacity_basis"),
    [
        ("assertion:wind-capacity", "gross"),
        ("assertion:project-capacity", "gross"),
    ],
)
def test_generation_assertions_for_one_asset_share_one_basis(
    assertion_id: str,
    capacity_basis: str,
) -> None:
    payload = _request_payload()
    _assertion(payload, assertion_id)["capacity_basis"] = capacity_basis
    for validate in (_validate_policy, _validate):
        with pytest.raises(
            ValidationError,
            match="one ProjectCase asset must share electrical and capacity bases",
        ):
            validate(payload)


def test_generation_assertions_for_one_asset_share_one_electrical_basis() -> None:
    payload = _request_payload()
    capacity = _assertion(payload, "assertion:wind-capacity")
    capacity["electrical_basis"] = "ac"
    capacity["expected_unit"] = "MWac"
    _assert_policy_and_request_reject(
        payload,
        "one ProjectCase asset must share electrical and capacity bases",
    )


def test_unitized_generation_assertions_cannot_change_the_asset_basis() -> None:
    payload = _request_payload()
    payload["binding_policy"]["assertions"].append(
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
        }
    )
    for validate in (_validate_policy, _validate):
        with pytest.raises(
            ValidationError,
            match="one ProjectCase asset must share electrical and capacity bases",
        ):
            validate(payload)


def test_all_unitized_generation_routes_accept_one_common_nameplate_basis() -> None:
    payload = _request_payload()
    for assertion_id in ("assertion:project-capacity", "assertion:wind-capacity"):
        _assertion(payload, assertion_id)["capacity_basis"] = "nameplate"
    payload["binding_policy"]["assertions"].extend(
        [
            {
                "kind": "generation_capacity_assertion",
                "assertion_id": assertion_id,
                "category": "generation_capacity",
                "asset_id": "asset:wind-01",
                "base_config_key": "wind",
                "project_case_selector": source,
                "base_selector": target,
                "expected_unit": unit,
                "electrical_basis": "not_applicable",
                "capacity_basis": "nameplate",
                "authored_technology_kind": "wind_turbine",
            }
            for assertion_id, source, target, unit in (
                ("assertion:turbine-count", "unit_count", "turbine_count", "count"),
                (
                    "assertion:turbine-rating",
                    "unit_rated_power",
                    "turbine_rated_power_mw",
                    "MW",
                ),
                (
                    "assertion:turbine-total",
                    "total_power_capacity",
                    "turbine_total_capacity_mw",
                    "MW",
                ),
            )
        ]
    )
    policy = _validate_policy(payload)
    request = _validate(payload)
    assert request.binding_policy == policy
    generation_assertions = tuple(
        assertion
        for assertion in request.binding_policy.assertions
        if isinstance(assertion, GenerationCapacityAssertion)
    )
    assert len(generation_assertions) == 5
    assert {assertion.capacity_basis.value for assertion in generation_assertions} == {
        "nameplate"
    }


def test_storage_assertions_for_one_asset_share_one_basis() -> None:
    payload = _request_payload()
    _add_storage_technology(payload)
    _assertion(payload, "assertion:bess-energy")["capacity_basis"] = "gross"
    for validate in (_validate_policy, _validate):
        with pytest.raises(
            ValidationError,
            match="one ProjectCase asset must share electrical and capacity bases",
        ):
            validate(payload)


def test_resolved_config_digest_is_the_public_v14_digest_and_moves_on_drift() -> None:
    config: dict[str, object] = {
        "project": {"capacity_mw": 100.0, "name": "Fictionland"},
        "flags": [True, None, 3],
    }
    assert resolved_config_sha256(config) == config_sha256(config)
    changed = copy.deepcopy(config)
    assert isinstance(changed["project"], dict)
    changed["project"]["capacity_mw"] = 101.0
    assert resolved_config_sha256(changed) != resolved_config_sha256(config)


@pytest.mark.parametrize(
    "invalid",
    [
        {"value": Decimal("1.0")},
        {"value": Path("scenario.yaml")},
        {"value": (1, 2)},
        {"value": math.nan},
        {"value": math.inf},
        {1: "non-string-key"},
    ],
)
def test_resolved_config_digest_refuses_default_str_and_nonfinite_seams(
    invalid: dict[object, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        resolved_config_sha256(invalid)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="root must be an exact dictionary"):
        resolved_config_sha256([{"value": 1}])  # type: ignore[arg-type]


def test_resolved_config_digest_refuses_cycles() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="shared or cyclic containers"):
        resolved_config_sha256(cyclic)


def test_resolved_config_digest_errors_are_canonical_and_path_bound() -> None:
    first = {"b": math.nan, "a": Decimal("1")}
    second = {"a": Decimal("1"), "b": math.nan}

    def outcome(config: dict[str, object]) -> tuple[type[Exception], str]:
        try:
            resolved_config_sha256(config)
        except Exception as exc:
            return type(exc), str(exc)
        raise AssertionError("invalid resolved config accepted")

    assert outcome(first) == outcome(second)
    error_type, message = outcome(first)
    assert error_type is TypeError
    assert "path /a" in message

    error_type, message = outcome({"a/b~c": Decimal("1")})
    assert error_type is TypeError
    assert "path /a~1b~0c" in message

    shared: list[object] = [1]
    error_type, message = outcome({"b": shared, "a": shared})
    assert error_type is ValueError
    assert "path /b" in message
    assert "first seen at /a" in message


def test_resolved_config_digest_rejects_scalar_subclasses_and_enum_tokens() -> None:
    class CustomString(str):
        pass

    class CustomInteger(int):
        pass

    class CustomFloat(float):
        pass

    class StringChoice(StrEnum):
        VALUE = "value"

    class IntegerChoice(IntEnum):
        VALUE = 1

    for invalid in (
        {"value": CustomString("value")},
        {"value": CustomInteger(1)},
        {"value": CustomFloat(1.0)},
        {"value": StringChoice.VALUE},
        {"value": IntegerChoice.VALUE},
        {CustomString("key"): "value"},
    ):
        with pytest.raises(TypeError):
            resolved_config_sha256(invalid)  # type: ignore[arg-type]


def test_resolved_config_digest_rejects_alias_depth_and_integer_amplification() -> None:
    shared: list[object] = [1]
    with pytest.raises(ValueError, match="shared or cyclic containers"):
        resolved_config_sha256({"left": shared, "right": shared})

    nested: list[object] = []
    for _ in range(130):
        nested = [nested]
    with pytest.raises(ValueError, match="nesting-depth limit"):
        resolved_config_sha256({"nested": nested})

    with pytest.raises(ValueError, match="integer exceeds the magnitude limit"):
        resolved_config_sha256({"integer": 10**5000})

    with pytest.raises(ValueError, match="text-size limit"):
        resolved_config_sha256({"text": "x" * 1_000_001})


def test_resolved_config_digest_translates_public_encoder_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_encoder(_config: object) -> str:
        raise ValueError("unbounded legacy encoder detail")

    monkeypatch.setattr("analytics.run_manifest.config_sha256", fail_encoder)
    with pytest.raises(
        ValueError, match="could not be encoded deterministically"
    ) as exc:
        resolved_config_sha256({"value": 1})
    assert isinstance(exc.value.__cause__, ValueError)


def test_schema_has_no_achieved_grade_review_release_or_support_fields() -> None:
    names = _schema_property_names(EvaluationRequest.model_json_schema())
    forbidden = {
        "achieved_grade",
        "grade_decision_id",
        "review_status",
        "release_status",
        "package_release",
        "hold",
        "supported",
        "assured",
    }
    assert names.isdisjoint(forbidden)
    assert "target_grade_request" in names
    assert "run_mode" in names


def test_public_schema_ids_and_exports_are_identity_preserving() -> None:
    assert ASSESSMENT_SCOPE_SCHEMA_ID == "dutchbay.assessment_scope.v1"
    assert EVALUATION_REQUEST_SCHEMA_ID == "dutchbay.evaluation_request.v1"
    assert BASE_SCENARIO_IDENTITY_SCHEMA_ID == "dutchbay.base_scenario_identity.v1"
    assert (
        AUTHORED_SCENARIO_VALIDATION_SCHEMA_ID
        == "dutchbay.authored_scenario_validation_receipt.v1"
    )
    assert V14_BINDING_POLICY_SCHEMA_ID == "dutchbay.v14_binding_policy.v1"

    from analytics import feasibility_report_contract as public

    assert public.AssessmentScope is AssessmentScope
    assert public.EvaluationRequest is EvaluationRequest
    assert public.BaseScenarioIdentity is BaseScenarioIdentity
    assert public.V14BindingPolicy is V14BindingPolicy


def test_contract_module_has_no_execution_or_application_imports() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden_prefixes = (
        "analytics.evaluation_v14",
        "analytics.pipeline",
        "finance",
        "app",
        "api",
        "fastapi",
    )
    assert not any(name.startswith(forbidden_prefixes) for name in imported), imported


def test_contract_only_cold_import_does_not_load_web_stack() -> None:
    code = """
import sys
import analytics.feasibility_report_contract as contract
assert contract.EvaluationRequest.__module__.endswith('assessment_scope')
for forbidden in ('fastapi', 'app.main', 'api.main'):
    assert forbidden not in sys.modules, forbidden
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_ROOT,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(_ROOT)},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr


def test_model_schema_required_sets_include_every_declared_scope_axis() -> None:
    schema = AssessmentScope.model_json_schema()
    properties = set(schema["properties"])
    assert set(schema["required"]) == properties
    assert {
        "project_stage",
        "intended_audiences",
        "intended_uses",
        "intended_decision",
        "run_mode",
        "target_grade_request",
        "evidence_cutoff",
        "valuation_date",
        "reporting_currency",
        "price_nominality",
        "price_basis_id",
        "exclusions",
        "materiality_rule",
    }.issubset(properties)


def test_new_contracts_are_versioned_and_extra_forbid() -> None:
    for model in (
        AssessmentScope,
        BaseScenarioIdentity,
        V14BindingPolicy,
        EvaluationRequest,
    ):
        schema = model.model_json_schema()
        assert schema["additionalProperties"] is False
        assert "schema_id" in schema["required"]
        assert "contract_version" in schema["required"]


def test_generation_assertion_json_schema_is_structural_and_strict() -> None:
    schema = GenerationCapacityAssertion.model_json_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_material_disposition_model_remains_frozen() -> None:
    disposition = ProjectCaseMaterialDisposition.model_validate_json(
        json.dumps(_material_dispositions({"identity"})[0])
    )
    with pytest.raises(ValidationError):
        disposition.rationale = "changed"  # type: ignore[misc]
