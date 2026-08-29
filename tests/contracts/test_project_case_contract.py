"""Hostile and web-shape controls for the pure ProjectCase v1 contract."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any, Callable

import jsonschema  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

from analytics.feasibility_report_contract import (
    PROJECT_CASE_CONTRACT_VERSION,
    PROJECT_CASE_SCHEMA_ID,
    ContractSupportStatus,
    ProjectCase,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_CASE_MODULE = (
    REPO_ROOT / "analytics" / "feasibility_report_contract" / "project_case.py"
)


def _resolved(
    value: float,
    unit: str,
    *,
    kind: str = "source",
    reference_id: str = "source:project-basis",
) -> dict[str, Any]:
    return {
        "state": "resolved",
        "value": value,
        "unit": unit,
        "bindings": [{"kind": kind, "reference_id": reference_id}],
    }


def _resolved_count(
    value: int,
    *,
    kind: str = "source",
    reference_id: str = "source:project-basis",
) -> dict[str, Any]:
    return {
        "state": "resolved",
        "value": value,
        "unit": "count",
        "bindings": [{"kind": kind, "reference_id": reference_id}],
    }


def _case_payload() -> dict[str, Any]:
    """Return one fictional, non-project hybrid fixture in JSON-native shape."""
    return {
        "schema_id": "dutchbay.project_case.v1",
        "contract_version": "1.0.0",
        "identity": {
            "project_id": "project:fictional-hybrid",
            "case_id": "case:fictional-hybrid:v1",
            "case_name": "Fictional hybrid contract fixture",
            "revision": 1,
        },
        "location": {
            "site_name": "Fictional Site",
            "description": "A non-project contract fixture in Fictionland.",
            "site_jurisdiction_code": "FIC",
            "site_jurisdiction_binding_id": "jurisdiction:fic:site",
            "latitude_degrees": _resolved(1.25, "degree"),
            "longitude_degrees": _resolved(2.5, "degree"),
            "boundary_id": "boundary:fictional-site",
            "boundary_status": "indicative",
            "boundary_binding": {
                "kind": "source",
                "reference_id": "source:project-basis",
            },
        },
        "jurisdiction_bindings": [
            {
                "binding_id": "jurisdiction:fic:site",
                "jurisdiction_code": "FIC",
                "subject": "site",
                "support_status": "contract_supported",
                "contract_pack_id": "contract-pack:fic-site",
                "contract_pack_version": "1.0.0",
            }
        ],
        "technology_bindings": [
            {
                "binding_id": "technology:wind:generation",
                "technology_id": "wind",
                "asset_class": "generation",
                "support_status": "contract_reviewed",
                "contract_pack_id": "contract-pack:wind-generation",
                "contract_pack_version": "1.0.0",
            },
            {
                "binding_id": "technology:bess:storage",
                "technology_id": "bess",
                "asset_class": "storage",
                "support_status": "contract_supported",
                "contract_pack_id": "contract-pack:bess-storage",
                "contract_pack_version": "1.0.0",
            },
        ],
        "assets": [
            {
                "kind": "generation",
                "asset_id": "asset:wind-block-01",
                "name": "Wind block 01",
                "technology_id": "wind",
                "technology_binding_id": "technology:wind:generation",
                "jurisdiction_codes": ["FIC"],
                "capacity": {
                    "kind": "unitized",
                    "unit_count": _resolved_count(2),
                    "unit_capacity_mw": _resolved(5.0, "MW"),
                    "total_capacity_mw": _resolved(10.0, "MW"),
                },
            },
            {
                "kind": "storage",
                "asset_id": "asset:bess-01",
                "name": "BESS 01",
                "technology_id": "bess",
                "technology_binding_id": "technology:bess:storage",
                "jurisdiction_codes": ["FIC"],
                "power_mw": _resolved(2.5, "MW"),
                "energy_mwh": _resolved(10.0, "MWh"),
                "duration_hours": _resolved(4.0, "hour"),
            },
            {
                "kind": "shared_infrastructure",
                "asset_id": "asset:poi-01",
                "name": "Shared point of interconnection",
                "infrastructure_type": "grid-interconnection",
                "jurisdiction_codes": ["FIC"],
                "capacity": _resolved(10.0, "MW"),
            },
        ],
        "topology": {
            "topology_id": "topology:fictional-hybrid",
            "kind": "hybrid",
            "shared_interconnection_asset_id": "asset:poi-01",
            "links": [
                {
                    "link_id": "link:wind-to-poi",
                    "kind": "uses_shared_infrastructure",
                    "from_asset_id": "asset:wind-block-01",
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
                    "to_asset_id": "asset:wind-block-01",
                },
            ],
        },
        "costs": {
            "reporting_currency": "USD",
            "reconciliation_status": "complete",
            "price_bases": [
                {
                    "price_basis_id": "price-basis:2026-real-usd",
                    "valuation_date": "2026-08-29",
                    "price_level": "Real 2026-08-29 terms",
                    "nominality": "real",
                    "reporting_currency": "USD",
                }
            ],
            "currency_conversions": [
                {
                    "conversion_id": "fx:lkr-to-usd:2026-08-29",
                    "from_currency": "LKR",
                    "to_currency": "USD",
                    "rate": _resolved(0.0025, "USD/LKR"),
                    "valuation_date": "2026-08-29",
                    "price_basis_id": "price-basis:2026-real-usd",
                }
            ],
            "lines": [
                {
                    "cost_kind": "capex",
                    "line_id": "cost:capex:plant",
                    "description": "Plant capital cost",
                    "quantity": _resolved(10.0, "MW"),
                    "unit_rate_native": _resolved(1_000_000.0, "USD/MW"),
                    "amount": {
                        "native_amount": _resolved(10_000_000.0, "USD"),
                        "native_currency": "USD",
                        "reporting_amount": _resolved(10_000_000.0, "USD"),
                        "reporting_currency": "USD",
                        "conversion_id": None,
                    },
                    "price_basis_id": "price-basis:2026-real-usd",
                    "allocation_ids": [
                        "allocation:capex:wind",
                        "allocation:capex:bess",
                    ],
                    "periodicity": "one_time",
                },
                {
                    "cost_kind": "opex",
                    "line_id": "cost:opex:annual",
                    "description": "Annual operating cost",
                    "quantity": _resolved(1.0, "year"),
                    "unit_rate_native": _resolved(400_000_000.0, "LKR/year"),
                    "amount": {
                        "native_amount": _resolved(400_000_000.0, "LKR"),
                        "native_currency": "LKR",
                        "reporting_amount": _resolved(1_000_000.0, "USD"),
                        "reporting_currency": "USD",
                        "conversion_id": "fx:lkr-to-usd:2026-08-29",
                    },
                    "price_basis_id": "price-basis:2026-real-usd",
                    "allocation_ids": ["allocation:opex:wind", "allocation:opex:bess"],
                    "periodicity": "annual",
                },
            ],
            "allocations": [
                {
                    "allocation_id": "allocation:capex:wind",
                    "cost_line_id": "cost:capex:plant",
                    "asset_id": "asset:wind-block-01",
                    "share": _resolved(0.8, "fraction"),
                },
                {
                    "allocation_id": "allocation:capex:bess",
                    "cost_line_id": "cost:capex:plant",
                    "asset_id": "asset:bess-01",
                    "share": _resolved(0.2, "fraction"),
                },
                {
                    "allocation_id": "allocation:opex:wind",
                    "cost_line_id": "cost:opex:annual",
                    "asset_id": "asset:wind-block-01",
                    "share": _resolved(0.8, "fraction"),
                },
                {
                    "allocation_id": "allocation:opex:bess",
                    "cost_line_id": "cost:opex:annual",
                    "asset_id": "asset:bess-01",
                    "share": _resolved(0.2, "fraction"),
                },
            ],
        },
        "sources": [
            {
                "source_id": "source:project-basis",
                "title": "Fictional fixture basis",
                "locator": "tests/contracts/test_project_case_contract.py::_case_payload",
                "jurisdiction_codes": ["FIC"],
                "technology_ids": ["wind", "bess"],
            }
        ],
        "assumptions": [],
        "missing_inputs": [],
    }


def _validate(payload: dict[str, Any]) -> ProjectCase:
    """Validate raw JSON at the strict domain-ingress seam."""
    return ProjectCase.model_validate_json(json.dumps(payload, allow_nan=True))


def _error(payload: dict[str, Any], pattern: str) -> ValidationError:
    with pytest.raises(ValidationError, match=pattern) as caught:
        _validate(payload)
    return caught.value


def test_project_case_json_schema_round_trip_and_stable_shape() -> None:
    case = _validate(_case_payload())
    payload = case.model_dump(mode="json")
    assert payload["schema_id"] == PROJECT_CASE_SCHEMA_ID
    assert payload["contract_version"] == PROJECT_CASE_CONTRACT_VERSION
    assert payload["assets"][0]["kind"] == "generation"
    assert payload["assets"][1]["kind"] == "storage"
    assert payload["assets"][2]["kind"] == "shared_infrastructure"
    assert payload["assets"][0]["capacity"]["kind"] == "unitized"
    assert payload["assets"][0]["capacity"]["unit_count"] == {
        "state": "resolved",
        "value": 2,
        "unit": "count",
        "bindings": [{"kind": "source", "reference_id": "source:project-basis"}],
    }
    assert payload["costs"]["lines"][0]["cost_kind"] == "capex"
    assert payload["costs"]["lines"][1]["cost_kind"] == "opex"
    assert payload["costs"]["reconciliation_status"] == "complete"
    assert isinstance(payload["assets"][1]["power_mw"]["value"], float)
    assert ProjectCase.model_validate_json(case.model_dump_json()) == case

    schema = ProjectCase.model_json_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_json_native_python_payload_requires_transport_normalization() -> None:
    payload = _case_payload()
    with pytest.raises(ValidationError) as caught:
        ProjectCase.model_validate(payload)

    errors = {(item["loc"], item["type"]) for item in caught.value.errors()}
    assert (("jurisdiction_bindings",), "tuple_type") in errors
    assert (("topology", "kind"), "is_instance_of") in errors
    assert _validate(payload).schema_id == PROJECT_CASE_SCHEMA_ID


def test_contract_support_status_is_not_assurance_or_release_vocabulary() -> None:
    assert {item.value for item in ContractSupportStatus} == {
        "unsupported",
        "contract_supported",
        "contract_reviewed",
    }
    fields = ProjectCase.model_fields
    assert "achieved_grade" not in fields
    assert "release_status" not in fields
    assert "run_mode" not in fields


def test_project_case_is_deeply_immutable() -> None:
    case = _validate(_case_payload())
    with pytest.raises(ValidationError, match="frozen"):
        case.identity.case_id = "case:changed"  # type: ignore[misc]


def test_project_and_case_identity_axes_must_be_distinct() -> None:
    payload = _case_payload()
    payload["identity"]["case_id"] = payload["identity"]["project_id"]
    error = _error(payload, "project_id and case_id must be distinct")
    assert error.errors()[0]["loc"] == ("identity",)


def test_resolved_values_and_counts_refuse_duplicate_bindings() -> None:
    payload = _case_payload()
    duplicate = copy.deepcopy(payload["assets"][1]["power_mw"]["bindings"][0])
    payload["assets"][1]["power_mw"]["bindings"].append(duplicate)
    _error(payload, "resolved material value has duplicate bindings")

    payload = _case_payload()
    count_bindings = payload["assets"][0]["capacity"]["unit_count"]["bindings"]
    count_bindings.append(copy.deepcopy(count_bindings[0]))
    _error(payload, "resolved material count has duplicate bindings")


@pytest.mark.parametrize(
    ("mutate", "pattern"),
    [
        (
            lambda value: value["assets"].append(copy.deepcopy(value["assets"][0])),
            "duplicate asset_id",
        ),
        (
            lambda value: value["sources"].append(copy.deepcopy(value["sources"][0])),
            "duplicate source_id",
        ),
        (
            lambda value: value["jurisdiction_bindings"].append(
                copy.deepcopy(value["jurisdiction_bindings"][0])
            ),
            "duplicate jurisdiction binding_id",
        ),
        (
            lambda value: value["costs"]["lines"].append(
                copy.deepcopy(value["costs"]["lines"][0])
            ),
            "duplicate cost line_id",
        ),
    ],
)
def test_duplicate_ids_fail_closed(
    mutate: Callable[[dict[str, Any]], None], pattern: str
) -> None:
    payload = _case_payload()
    mutate(payload)
    _error(payload, pattern)


@pytest.mark.parametrize("invalid_id", ["", "bad id", "?unstable"])
def test_blank_or_unstable_asset_ids_are_rejected(invalid_id: str) -> None:
    payload = _case_payload()
    payload["assets"][0]["asset_id"] = invalid_id
    error = _error(payload, "string_pattern_mismatch|string_too_short")
    assert error.errors()[0]["loc"][:2] == ("assets", 0)


def test_missing_or_unbound_site_jurisdiction_fails_closed() -> None:
    payload = _case_payload()
    payload["location"]["site_jurisdiction_binding_id"] = "jurisdiction:missing"
    _error(payload, "unbound site jurisdiction")


def test_ambiguous_jurisdiction_subject_binding_fails_closed() -> None:
    payload = _case_payload()
    duplicate = copy.deepcopy(payload["jurisdiction_bindings"][0])
    duplicate["binding_id"] = "jurisdiction:fic:site:duplicate"
    payload["jurisdiction_bindings"].append(duplicate)
    _error(payload, "ambiguous duplicate jurisdiction subject")


def test_unsupported_jurisdiction_contract_fails_closed() -> None:
    payload = _case_payload()
    payload["jurisdiction_bindings"][0]["support_status"] = "unsupported"
    _error(payload, "unsupported jurisdiction/technology")


def test_non_lka_case_cannot_receive_sri_lankan_source_scope() -> None:
    payload = _case_payload()
    payload["sources"][0]["jurisdiction_codes"] = ["LKA"]
    _error(payload, "jurisdiction outside ProjectCase bindings")


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("latitude_degrees", 91.0, "latitude_degrees requires degree unit"),
        ("longitude_degrees", 181.0, "longitude_degrees requires degree unit"),
    ],
)
def test_coordinates_have_explicit_global_bounds(
    field: str, value: float, pattern: str
) -> None:
    payload = _case_payload()
    payload["location"][field]["value"] = value
    _error(payload, pattern)


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("technology_binding_id", "technology:missing", "unbound technology"),
        ("technology_id", "solar", "unbound technology"),
    ],
)
def test_unbound_or_mismatched_technology_fails_closed(
    field: str, value: str, pattern: str
) -> None:
    payload = _case_payload()
    payload["assets"][0][field] = value
    _error(payload, pattern)


def test_unsupported_technology_contract_fails_closed() -> None:
    payload = _case_payload()
    payload["technology_bindings"][0]["support_status"] = "unsupported"
    _error(payload, "unsupported jurisdiction/technology")


def test_ambiguous_or_unreferenced_technology_binding_fails_closed() -> None:
    payload = _case_payload()
    duplicate = copy.deepcopy(payload["technology_bindings"][0])
    duplicate["binding_id"] = "technology:wind:generation:duplicate"
    payload["technology_bindings"].append(duplicate)
    _error(payload, "ambiguous duplicate technology contract binding")

    payload = _case_payload()
    payload["technology_bindings"].append(
        {
            "binding_id": "technology:solar:generation",
            "technology_id": "solar",
            "asset_class": "generation",
            "support_status": "contract_supported",
            "contract_pack_id": "contract-pack:solar-generation",
            "contract_pack_version": "1.0.0",
        }
    )
    payload["sources"][0]["technology_ids"].append("solar")
    _error(payload, "technology binding register has unreferenced")


def test_asset_discriminator_mismatch_has_stable_field_location() -> None:
    payload = _case_payload()
    payload["assets"][1]["kind"] = "generation"
    error = _error(payload, "Field required|Extra inputs")
    assert error.errors()[0]["loc"][:3] == ("assets", 1, "generation")


def test_dangling_topology_reference_fails_closed() -> None:
    payload = _case_payload()
    payload["topology"]["links"][0]["to_asset_id"] = "asset:missing"
    _error(payload, "dangling asset reference")


@pytest.mark.parametrize(
    ("mutate", "pattern"),
    [
        (
            lambda value: value["topology"].update({"kind": "storage_only"}),
            "topology kind does not match asset composition",
        ),
        (
            lambda value: value["topology"].update(
                {"shared_interconnection_asset_id": "asset:wind-block-01"}
            ),
            "must name a shared asset",
        ),
        (
            lambda value: value["topology"].update(
                {"shared_interconnection_asset_id": None}
            ),
            "hybrid topology requires shared interconnection",
        ),
    ],
)
def test_topology_declaration_must_match_assets(
    mutate: Callable[[dict[str, Any]], None], pattern: str
) -> None:
    payload = _case_payload()
    mutate(payload)
    _error(payload, pattern)


def test_topology_relationships_are_unique_and_directional() -> None:
    payload = _case_payload()
    duplicate = copy.deepcopy(payload["topology"]["links"][0])
    duplicate["link_id"] = "link:duplicate-wind-to-poi"
    payload["topology"]["links"].append(duplicate)
    _error(payload, "duplicate asset topology relationship")

    payload = _case_payload()
    payload["topology"]["links"][0].update(
        {
            "from_asset_id": "asset:poi-01",
            "to_asset_id": "asset:wind-block-01",
        }
    )
    _error(payload, "uses_shared_infrastructure must point from technology asset")

    payload = _case_payload()
    payload["topology"]["links"][2].update(
        {
            "from_asset_id": "asset:wind-block-01",
            "to_asset_id": "asset:bess-01",
        }
    )
    _error(payload, "charges_from must point from storage")


def test_asset_self_link_is_rejected_before_graph_reconciliation() -> None:
    payload = _case_payload()
    payload["topology"]["links"][0]["to_asset_id"] = "asset:wind-block-01"
    _error(payload, "asset link cannot reference the same asset twice")


def test_hybrid_requires_every_asset_to_use_shared_infrastructure() -> None:
    payload = _case_payload()
    payload["topology"]["links"] = [
        item
        for item in payload["topology"]["links"]
        if item["link_id"] != "link:bess-to-poi"
    ]
    _error(payload, "hybrid assets must explicitly use shared")


def test_shared_infrastructure_requires_reciprocal_topology_use() -> None:
    payload = _case_payload()
    payload["topology"]["links"] = [
        item
        for item in payload["topology"]["links"]
        if item["kind"] != "uses_shared_infrastructure"
    ]
    _error(payload, "shared infrastructure has missing reciprocal")


def test_dangling_cost_allocation_asset_fails_closed() -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][0]["asset_id"] = "asset:missing"
    _error(payload, "dangling asset_id")


def test_asset_jurisdiction_must_have_a_site_binding() -> None:
    payload = _case_payload()
    payload["assets"][1]["jurisdiction_codes"] = ["LKA"]
    _error(payload, "asset asset:bess-01 has an unbound site jurisdiction")


@pytest.mark.parametrize("second_share", [0.1, 0.3])
def test_under_or_over_allocation_fails_closed(second_share: float) -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][1]["share"] = _resolved(second_share, "fraction")
    _error(payload, "allocations must sum to 1")


def test_zero_share_allocation_is_rejected_as_degenerate() -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][1]["share"] = _resolved(0.0, "fraction")
    _error(payload, r"range \(0, 1\]")


def test_cost_line_and_allocation_must_be_reciprocal() -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][0]["cost_line_id"] = "cost:opex:annual"
    _error(payload, "reciprocal binding is broken")


def test_unitless_cost_quantity_fails_at_exact_line_field() -> None:
    payload = _case_payload()
    payload["costs"]["lines"][0]["quantity"]["unit"] = ""
    error = _error(payload, "string_too_short|string_pattern_mismatch")
    assert error.errors()[0]["loc"][:5] == (
        "costs",
        "lines",
        0,
        "capex",
        "quantity",
    )


def test_mixed_currency_without_conversion_fails_closed() -> None:
    payload = _case_payload()
    payload["costs"]["lines"][1]["amount"]["conversion_id"] = None
    _error(payload, "mixed-currency amount requires conversion_id")


def test_mixed_currency_with_dangling_conversion_fails_closed() -> None:
    payload = _case_payload()
    payload["costs"]["lines"][1]["amount"]["conversion_id"] = "fx:missing"
    _error(payload, "dangling conversion_id")


def test_cost_line_requires_explicit_price_basis() -> None:
    payload = _case_payload()
    payload["costs"]["lines"][0]["price_basis_id"] = "price-basis:missing"
    _error(payload, "dangling price_basis_id")


def test_cost_registers_and_reporting_basis_are_closed() -> None:
    payload = _case_payload()
    payload["costs"]["price_bases"][0]["reporting_currency"] = "EUR"
    _error(payload, "price basis reporting currency does not match schedule")

    payload = _case_payload()
    payload["costs"]["lines"][1]["amount"]["reporting_currency"] = "EUR"
    payload["costs"]["lines"][1]["amount"]["reporting_amount"]["unit"] = "EUR"
    _error(payload, "cost line reporting currency does not match schedule")

    payload = _case_payload()
    payload["costs"]["lines"][0]["allocation_ids"].append("allocation:missing")
    _error(payload, "dangling allocation_id")

    payload = _case_payload()
    unused = copy.deepcopy(payload["costs"]["allocations"][0])
    unused["allocation_id"] = "allocation:unused"
    payload["costs"]["allocations"].append(unused)
    _error(payload, "cost allocation register has unreferenced records")


def test_unreferenced_price_basis_is_refused() -> None:
    payload = _case_payload()
    unused = copy.deepcopy(payload["costs"]["price_bases"][0])
    unused["price_basis_id"] = "price-basis:unused"
    payload["costs"]["price_bases"].append(unused)
    _error(payload, "price basis register has unreferenced")


def test_currency_conversion_register_and_basis_are_closed() -> None:
    payload = _case_payload()
    payload["costs"]["currency_conversions"][0]["valuation_date"] = "2026-08-28"
    _error(payload, "cost line conversion scope/basis mismatch")

    payload = _case_payload()
    unused = copy.deepcopy(payload["costs"]["currency_conversions"][0])
    unused.update(
        {
            "conversion_id": "fx:eur-to-usd:2026-08-29",
            "from_currency": "EUR",
            "rate": _resolved(1.1, "USD/EUR"),
        }
    )
    payload["costs"]["currency_conversions"].append(unused)
    _error(payload, "currency conversion register has unreferenced records")


def test_currency_and_amount_arithmetic_fail_closed() -> None:
    payload = _case_payload()
    conversion = payload["costs"]["currency_conversions"][0]
    conversion.update(
        {
            "from_currency": "USD",
            "to_currency": "USD",
            "rate": _resolved(1.0, "USD/USD"),
        }
    )
    _error(payload, "currency conversion requires different currencies")

    payload = _case_payload()
    payload["costs"]["lines"][0]["amount"]["conversion_id"] = "fx:lkr-to-usd:2026-08-29"
    _error(payload, "same-currency amount must not name a conversion")

    payload = _case_payload()
    payload["costs"]["lines"][0]["amount"]["reporting_amount"] = _resolved(
        9_000_000.0, "USD"
    )
    _error(payload, "same-currency native/reporting amounts must match")

    payload = _case_payload()
    payload["costs"]["lines"][0]["amount"]["native_amount"] = _resolved(
        9_000_000.0, "USD"
    )
    payload["costs"]["lines"][0]["amount"]["reporting_amount"] = _resolved(
        9_000_000.0, "USD"
    )
    _error(payload, r"native amount must equal quantity \* unit_rate_native")


def test_opex_periodicity_and_allocation_units_are_explicit() -> None:
    payload = _case_payload()
    payload["costs"]["lines"][1]["periodicity"] = "one_time"
    _error(payload, "opex periodicity cannot be one_time")

    payload = _case_payload()
    payload["costs"]["allocations"][0]["share"]["unit"] = "percent"
    _error(payload, "allocation share requires fraction unit")


def test_currency_conversion_must_reconcile_reporting_amount() -> None:
    payload = _case_payload()
    payload["costs"]["lines"][1]["amount"]["reporting_amount"] = _resolved(
        999_999.0, "USD"
    )
    _error(payload, "reporting amount does not reconcile")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("power_mw", -2.5),
        ("energy_mwh", float("nan")),
        ("duration_hours", float("inf")),
    ],
)
def test_storage_rejects_negative_or_non_finite_numbers(
    field: str, value: float
) -> None:
    payload = _case_payload()
    payload["assets"][1][field]["value"] = value
    _error(payload, "finite_number|positive")


def test_shared_capacity_zero_cannot_stand_for_missing() -> None:
    payload = _case_payload()
    payload["assets"][2]["capacity"] = _resolved(0.0, "MW")
    error = _error(payload, "shared infrastructure capacity must be positive")
    assert error.errors()[0]["loc"][:3] == (
        "assets",
        2,
        "shared_infrastructure",
    )


def test_bess_power_energy_duration_must_reconcile() -> None:
    payload = _case_payload()
    payload["assets"][1]["duration_hours"] = _resolved(3.0, "hour")
    error = _error(payload, "energy_mwh must equal power_mw")
    assert error.errors()[0]["loc"][:3] == ("assets", 1, "storage")


def test_unitized_generation_count_capacity_must_reconcile() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["total_capacity_mw"] = _resolved(11.0, "MW")
    error = _error(payload, r"unit_count \* unit_capacity_mw")
    assert error.errors()[0]["loc"][:5] == (
        "assets",
        0,
        "generation",
        "capacity",
        "unitized",
    )


def test_aggregate_generation_capacity_is_an_explicit_discriminator() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"] = {
        "kind": "aggregate",
        "total_capacity_mw": _resolved(10.0, "MW"),
    }
    case = _validate(payload)
    generation = case.assets[0]
    assert generation.kind == "generation"
    assert generation.capacity.kind == "aggregate"


def test_missing_unit_rating_defers_generation_arithmetic() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_capacity_mw"] = {
        "state": "missing",
        "unit": "MW",
        "missing_input_id": "missing:wind-unit-rating",
    }
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:wind-unit-rating",
            "field_path": "/assets/0/capacity/unit_capacity_mw",
            "expected_unit": "MW",
            "reason": "The turbine model is not selected.",
            "consequence": "Unitized generation arithmetic is incomplete.",
            "remedy": "Provide the selected turbine rating.",
        }
    ]
    assert _validate(payload).missing_inputs[0].expected_unit == "MW"


@pytest.mark.parametrize("value", [0, -1, 2.5])
def test_resolved_unit_count_requires_positive_integer(value: float) -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"]["value"] = value
    _error(payload, "greater_than|int_type")


def test_resolved_unit_count_requires_provenance_binding() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"]["bindings"] = []
    _error(payload, "resolved material count requires source/assumption binding")


def test_material_value_without_provenance_binding_fails_closed() -> None:
    payload = _case_payload()
    payload["assets"][1]["power_mw"]["bindings"] = []
    _error(payload, "requires source/assumption binding")


def test_material_value_with_dangling_source_binding_fails_closed() -> None:
    payload = _case_payload()
    payload["assets"][1]["power_mw"]["bindings"][0]["reference_id"] = "source:missing"
    _error(payload, "dangling source reference")


def test_dangling_assumption_and_unreferenced_source_fail_closed() -> None:
    payload = _case_payload()
    payload["assets"][1]["power_mw"]["bindings"] = [
        {"kind": "assumption", "reference_id": "assumption:missing"}
    ]
    _error(payload, "dangling assumption reference")

    payload = _case_payload()
    unused = copy.deepcopy(payload["sources"][0])
    unused["source_id"] = "source:unused"
    payload["sources"].append(unused)
    _error(payload, "source register has unreferenced records")


def test_provenance_ids_are_unique_across_register_kinds() -> None:
    payload = _case_payload()
    payload["missing_inputs"] = [
        {
            "missing_input_id": "source:project-basis",
            "field_path": "/assets/2/capacity",
            "expected_unit": "MW",
            "reason": "Hostile cross-register collision.",
            "consequence": "Ambiguous provenance identity.",
            "remedy": "Assign a unique missing-input identifier.",
        }
    ]
    _error(payload, "source/assumption/missing-input IDs must be globally unique")


def test_explicit_missing_value_must_bind_exact_missing_input() -> None:
    payload = _case_payload()
    payload["assets"][2]["capacity"] = {
        "state": "missing",
        "unit": "MW",
        "missing_input_id": "missing:poi-rating",
    }
    _error(payload, "dangling missing_input_id")

    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:poi-rating",
            "field_path": "/assets/2/capacity",
            "expected_unit": "MW",
            "reason": "No authenticated rating supplied.",
            "consequence": "Shared export capacity is unresolved.",
            "remedy": "Supply the operator-approved interconnection rating.",
        }
    ]
    case = _validate(payload)
    shared = case.assets[2]
    assert shared.kind == "shared_infrastructure"
    assert shared.capacity.state == "missing"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("field_path", "/assets/0/capacity"),
        ("expected_unit", "kW"),
    ],
)
def test_missing_input_requires_exact_json_pointer_and_unit(
    field: str, value: str
) -> None:
    payload = _case_payload()
    payload["assets"][2]["capacity"] = {
        "state": "missing",
        "unit": "MW",
        "missing_input_id": "missing:poi-rating",
    }
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:poi-rating",
            "field_path": "/assets/2/capacity",
            "expected_unit": "MW",
            "reason": "No authenticated rating supplied.",
            "consequence": "Shared export capacity is unresolved.",
            "remedy": "Supply the operator-approved interconnection rating.",
        }
    ]
    payload["missing_inputs"][0][field] = value
    _error(payload, "field_path/expected_unit does not match.*?/assets/2/capacity")


def test_missing_unit_count_is_reciprocal_and_defers_capacity_arithmetic() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"] = {
        "state": "missing",
        "unit": "count",
        "missing_input_id": "missing:wind-unit-count",
    }
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:wind-unit-count",
            "field_path": "/assets/0/capacity/unit_count",
            "expected_unit": "count",
            "reason": "Final turbine count has not been selected.",
            "consequence": "Unitized capacity arithmetic is incomplete.",
            "remedy": "Provide the selected layout and turbine count.",
        }
    ]
    case = _validate(payload)
    generation = case.assets[0]
    assert generation.kind == "generation"
    assert generation.capacity.kind == "unitized"
    assert generation.capacity.unit_count.state == "missing"


def test_missing_bess_duration_defers_only_capacity_arithmetic() -> None:
    payload = _case_payload()
    payload["assets"][1]["duration_hours"] = {
        "state": "missing",
        "unit": "hour",
        "missing_input_id": "missing:bess-duration",
    }
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:bess-duration",
            "field_path": "/assets/1/duration_hours",
            "expected_unit": "hour",
            "reason": "The selected dispatch duration is not confirmed.",
            "consequence": "BESS capacity reconciliation is incomplete.",
            "remedy": "Provide the approved storage duration.",
        }
    ]
    case = _validate(payload)
    storage = case.assets[1]
    assert storage.kind == "storage"
    assert storage.duration_hours.state == "missing"


def test_missing_cost_requires_incomplete_reconciliation_status() -> None:
    payload = _case_payload()
    payload["costs"]["lines"][0]["quantity"] = {
        "state": "missing",
        "unit": "MW",
        "missing_input_id": "missing:capex-quantity",
    }
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:capex-quantity",
            "field_path": "/costs/lines/0/quantity",
            "expected_unit": "MW",
            "reason": "Contract quantity schedule has not been supplied.",
            "consequence": "CAPEX arithmetic is incomplete.",
            "remedy": "Supply the executed contract quantity schedule.",
        }
    ]
    _error(payload, "reconciliation_status must reflect explicit missing inputs")

    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    case = _validate(payload)
    assert case.costs.reconciliation_status.value == "incomplete_missing_input"


def test_incomplete_cost_status_without_missing_value_is_rejected() -> None:
    payload = _case_payload()
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    _error(payload, "reconciliation_status must reflect explicit missing inputs")


def test_source_cannot_cross_technology_scope() -> None:
    payload = _case_payload()
    payload["sources"][0]["technology_ids"] = ["wind"]
    _error(payload, r"wrong scope for /assets/1/power_mw")


def test_source_cannot_cross_jurisdiction_scope() -> None:
    payload = _case_payload()
    payload["jurisdiction_bindings"].append(
        {
            "binding_id": "jurisdiction:lka:site",
            "jurisdiction_code": "LKA",
            "subject": "site",
            "support_status": "contract_supported",
            "contract_pack_id": "contract-pack:lka-site",
            "contract_pack_version": "1.0.0",
        }
    )
    payload["assets"][1]["jurisdiction_codes"] = ["FIC", "LKA"]
    _error(payload, r"wrong scope for /assets/1/power_mw")


def test_assumption_cannot_cross_technology_scope() -> None:
    payload = _case_payload()
    payload["assumptions"] = [
        {
            "assumption_id": "assumption:wind-only",
            "statement": "Wind-only engineering assumption.",
            "basis": "Fictional wind fixture.",
            "replacement_action": "Replace with source evidence.",
            "jurisdiction_codes": ["FIC"],
            "technology_ids": ["wind"],
        }
    ]
    payload["assets"][1]["power_mw"]["bindings"] = [
        {"kind": "assumption", "reference_id": "assumption:wind-only"}
    ]
    _error(payload, r"wrong scope for /assets/1/power_mw")


def test_assumption_cannot_cross_jurisdiction_scope() -> None:
    payload = _case_payload()
    payload["jurisdiction_bindings"].append(
        {
            "binding_id": "jurisdiction:lka:site",
            "jurisdiction_code": "LKA",
            "subject": "site",
            "support_status": "contract_supported",
            "contract_pack_id": "contract-pack:lka-site",
            "contract_pack_version": "1.0.0",
        }
    )
    payload["assets"][1]["jurisdiction_codes"] = ["FIC", "LKA"]
    payload["assumptions"] = [
        {
            "assumption_id": "assumption:fic-bess-only",
            "statement": "Fictionland-only BESS assumption.",
            "basis": "Fictional BESS fixture.",
            "replacement_action": "Replace with multi-jurisdiction evidence.",
            "jurisdiction_codes": ["FIC"],
            "technology_ids": ["bess"],
        }
    ]
    payload["assets"][1]["power_mw"]["bindings"] = [
        {"kind": "assumption", "reference_id": "assumption:fic-bess-only"}
    ]
    _error(payload, r"wrong scope for /assets/1/power_mw")


@pytest.mark.parametrize(
    ("register", "field", "value", "pattern"),
    [
        (
            "sources",
            "technology_ids",
            ["solar"],
            "technology outside ProjectCase bindings",
        ),
        (
            "assumptions",
            "jurisdiction_codes",
            ["LKA"],
            "jurisdiction outside ProjectCase bindings",
        ),
        (
            "assumptions",
            "technology_ids",
            ["solar"],
            "technology outside ProjectCase bindings",
        ),
    ],
)
def test_provenance_register_scope_cannot_exceed_case_scope(
    register: str, field: str, value: list[str], pattern: str
) -> None:
    payload = _case_payload()
    if register == "assumptions":
        payload["assumptions"] = [
            {
                "assumption_id": "assumption:scope-probe",
                "statement": "Hostile scope probe.",
                "basis": "Fixture mutation.",
                "replacement_action": "Correct the scope.",
                "jurisdiction_codes": ["FIC"],
                "technology_ids": ["wind"],
            }
        ]
    payload[register][0][field] = value
    _error(payload, pattern)


def test_unreferenced_assumption_or_missing_input_is_refused() -> None:
    payload = _case_payload()
    payload["assumptions"] = [
        {
            "assumption_id": "assumption:unused",
            "statement": "Unused assumption.",
            "basis": "Fixture mutation.",
            "replacement_action": "Remove it.",
            "jurisdiction_codes": ["FIC"],
            "technology_ids": ["wind"],
        }
    ]
    _error(payload, "assumption register has unreferenced")

    payload = _case_payload()
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:unused",
            "field_path": "/assets/2/capacity",
            "expected_unit": "MW",
            "reason": "Unused fixture record.",
            "consequence": "None because it is not referenced.",
            "remedy": "Remove it.",
        }
    ]
    _error(payload, "missing-input register has unreferenced")


def test_unknown_fields_fail_instead_of_being_discarded() -> None:
    payload = _case_payload()
    payload["location"]["country_default"] = "LKA"
    error = _error(payload, "Extra inputs are not permitted")
    assert error.errors()[0]["loc"] == ("location", "country_default")


def test_project_case_module_has_pure_import_direction() -> None:
    tree = ast.parse(PROJECT_CASE_MODULE.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden_prefixes = (
        "finance",
        "analytics.evaluation",
        "analytics.pipeline",
        "app",
        "api",
    )
    assert not any(
        item == prefix or item.startswith(f"{prefix}.")
        for item in imports
        for prefix in forbidden_prefixes
    )
    source = PROJECT_CASE_MODULE.read_text(encoding="utf-8")
    assert "evaluate_with_overrides" not in source
    assert "FastAPI" not in source
    assert "achieved_grade" not in source
    assert "release_status" not in source
    assert "sha256" not in source.lower()
