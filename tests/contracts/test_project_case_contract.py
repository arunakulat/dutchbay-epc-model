"""Hostile and web-shape controls for the pure ProjectCase v1 contract."""

from __future__ import annotations

import ast
import copy
import json
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext
from fractions import Fraction
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
    ResolvedValue,
)
from analytics.feasibility_report_contract import project_case as project_case_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_CASE_MODULE = (
    REPO_ROOT / "analytics" / "feasibility_report_contract" / "project_case.py"
)
MIN_PROJECT_DECIMAL = "0." + ("0" * 35) + "1"
MAX_PROJECT_INTEGER = str((10**36) - 1)


def _resolved(
    value: str | int | float,
    unit: str,
    *,
    kind: str = "source",
    reference_id: str = "source:project-basis",
) -> dict[str, Any]:
    return {
        "state": "resolved",
        "value": str(value),
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
        "value": str(value),
        "unit": "count",
        "bindings": [{"kind": kind, "reference_id": reference_id}],
    }


def _missing_value(missing_input_id: str, unit: str) -> dict[str, Any]:
    return {
        "state": "missing",
        "unit": unit,
        "missing_input_id": missing_input_id,
    }


def _missing_record(
    missing_input_id: str, field_path: str, expected_unit: str
) -> dict[str, Any]:
    return {
        "missing_input_id": missing_input_id,
        "field_path": field_path,
        "expected_unit": expected_unit,
        "reason": "The bounded rereview fixture omits this input.",
        "consequence": "The affected arithmetic remains incomplete.",
        "remedy": "Supply a value in the declared ProjectCase numeric domain.",
    }


def _bind_missing(
    payload: dict[str, Any],
    target: dict[str, Any],
    field: str,
    missing_input_id: str,
    unit: str,
    field_path: str,
) -> None:
    target[field] = _missing_value(missing_input_id, unit)
    payload["missing_inputs"].append(
        _missing_record(missing_input_id, field_path, unit)
    )


def _configure_missing_opex_chain(
    payload: dict[str, Any],
    *,
    missing_operands: tuple[str, ...],
    reporting_amount: int,
    fx_rate: int | None,
) -> None:
    line = payload["costs"]["lines"][1]
    line["quantity"] = _resolved(1, "year")
    line["unit_rate_native"] = _resolved(1, "LKR/year")
    operand_units = {"quantity": "year", "unit_rate_native": "LKR/year"}
    for field in missing_operands:
        _bind_missing(
            payload,
            line,
            field,
            f"missing:opex-{field}",
            operand_units[field],
            f"/costs/lines/1/{field}",
        )
    line["amount"].update(
        {
            "native_minor_unit_places": 0,
            "reporting_amount": _resolved(reporting_amount, "USD"),
            "reporting_minor_unit_places": 0,
        }
    )
    _bind_missing(
        payload,
        line["amount"],
        "native_amount",
        "missing:opex-native",
        "LKR",
        "/costs/lines/1/amount/native_amount",
    )
    conversion = payload["costs"]["currency_conversions"][0]
    if fx_rate is None:
        _bind_missing(
            payload,
            conversion,
            "rate",
            "missing:fx-rate",
            "USD/LKR",
            "/costs/currency_conversions/0/rate",
        )
    else:
        conversion["rate"] = _resolved(fx_rate, "USD/LKR")
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"


def _make_conversion_rate_missing(
    payload: dict[str, Any], *, quote_precision: int
) -> None:
    conversion = payload["costs"]["currency_conversions"][0]
    conversion["quote_precision"] = quote_precision
    _bind_missing(
        payload,
        conversion,
        "rate",
        "missing:fx-rate",
        "USD/LKR",
        "/costs/currency_conversions/0/rate",
    )
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"


def _configure_fx_consumer(
    payload: dict[str, Any],
    line_index: int,
    *,
    native_amount: str,
    reporting_amount: str | None,
    native_minor_unit_places: int,
    reporting_minor_unit_places: int,
    infer_native: bool = False,
) -> None:
    line = payload["costs"]["lines"][line_index]
    line["quantity"] = _resolved("1", "year")
    line["unit_rate_native"] = _resolved(native_amount, "LKR/year")
    line["amount"]["native_minor_unit_places"] = native_minor_unit_places
    if infer_native:
        _bind_missing(
            payload,
            line["amount"],
            "native_amount",
            f"missing:native:{line_index}",
            "LKR",
            f"/costs/lines/{line_index}/amount/native_amount",
        )
    else:
        line["amount"]["native_amount"] = _resolved(native_amount, "LKR")
    line["amount"]["reporting_minor_unit_places"] = reporting_minor_unit_places
    if reporting_amount is None:
        _bind_missing(
            payload,
            line["amount"],
            "reporting_amount",
            f"missing:reporting:{line_index}",
            "USD",
            f"/costs/lines/{line_index}/amount/reporting_amount",
        )
    else:
        line["amount"]["reporting_amount"] = _resolved(reporting_amount, "USD")


def _append_fx_consumer(
    payload: dict[str, Any],
    *,
    suffix: str,
    native_amount: str,
    reporting_amount: str | None,
    native_minor_unit_places: int,
    reporting_minor_unit_places: int,
    infer_native: bool = False,
) -> None:
    line_index = len(payload["costs"]["lines"])
    line = copy.deepcopy(payload["costs"]["lines"][1])
    line["line_id"] = f"cost:opex:{suffix}"
    line["description"] = f"FX consumer {suffix}"
    allocation_id = f"allocation:opex:{suffix}:wind"
    line["allocation_ids"] = [allocation_id]
    payload["costs"]["lines"].append(line)
    payload["costs"]["allocations"].append(
        {
            "allocation_id": allocation_id,
            "cost_line_id": line["line_id"],
            "asset_id": "asset:wind-block-01",
            "share": _resolved("1", "fraction"),
        }
    )
    _configure_fx_consumer(
        payload,
        line_index,
        native_amount=native_amount,
        reporting_amount=reporting_amount,
        native_minor_unit_places=native_minor_unit_places,
        reporting_minor_unit_places=reporting_minor_unit_places,
        infer_native=infer_native,
    )


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
                "support_status": "declared",
                "contract_pack_id": "contract-pack:fic-site",
                "contract_pack_version": "1.0.0",
            }
        ],
        "technology_bindings": [
            {
                "binding_id": "technology:wind:generation",
                "technology_id": "wind",
                "asset_class": "generation",
                "support_status": "declared",
                "contract_pack_id": "contract-pack:wind-generation",
                "contract_pack_version": "1.0.0",
            },
            {
                "binding_id": "technology:bess:storage",
                "technology_id": "bess",
                "asset_class": "storage",
                "support_status": "declared",
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
                    "electrical_basis": "not_applicable",
                    "capacity_basis": "nameplate",
                    "unit_count": _resolved_count(2),
                    "unit_power_capacity": _resolved(5.0, "MW"),
                    "total_power_capacity": _resolved(10.0, "MW"),
                },
            },
            {
                "kind": "storage",
                "asset_id": "asset:bess-01",
                "name": "BESS 01",
                "technology_id": "bess",
                "technology_binding_id": "technology:bess:storage",
                "jurisdiction_codes": ["FIC"],
                "power_capacity": {
                    "value": _resolved(2.5, "MW"),
                    "electrical_basis": "ac",
                    "capacity_basis": "usable",
                },
                "energy_capacity": {
                    "value": _resolved(10.0, "MWh"),
                    "electrical_basis": "ac",
                    "capacity_basis": "usable",
                },
                "duration": {
                    "value": _resolved(4.0, "hour"),
                    "electrical_basis": "ac",
                    "capacity_basis": "usable",
                },
                "charging_source": {
                    "kind": "asset",
                    "asset_id": "asset:wind-block-01",
                },
            },
            {
                "kind": "shared_infrastructure",
                "asset_id": "asset:poi-01",
                "name": "Shared point of interconnection",
                "infrastructure_role": "grid_interconnection",
                "jurisdiction_codes": ["FIC"],
                "capacity": _resolved(10.0, "MW"),
            },
        ],
        "topology": {
            "topology_id": "topology:fictional-hybrid",
            "kind": "hybrid",
            "interconnection_arrangement": "common_shared",
            "common_interconnection_asset_id": "asset:poi-01",
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
                    "bindings": [
                        {
                            "kind": "source",
                            "reference_id": "source:project-basis",
                        }
                    ],
                }
            ],
            "currency_conversions": [
                {
                    "conversion_id": "fx:lkr-to-usd:2026-08-29",
                    "from_currency": "LKR",
                    "to_currency": "USD",
                    "rate": _resolved(0.0025, "USD/LKR"),
                    "quote_precision": 6,
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
                        "native_minor_unit_places": 2,
                        "reporting_amount": _resolved(10_000_000.0, "USD"),
                        "reporting_currency": "USD",
                        "reporting_minor_unit_places": 2,
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
                        "native_minor_unit_places": 2,
                        "reporting_amount": _resolved(1_000_000.0, "USD"),
                        "reporting_currency": "USD",
                        "reporting_minor_unit_places": 2,
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
        "value": "2",
        "unit": "count",
        "bindings": [{"kind": "source", "reference_id": "source:project-basis"}],
    }
    assert payload["costs"]["lines"][0]["cost_kind"] == "capex"
    assert payload["costs"]["lines"][1]["cost_kind"] == "opex"
    assert payload["costs"]["reconciliation_status"] == "complete"
    assert payload["assets"][1]["power_capacity"]["value"]["value"] == "2.5"
    assert ProjectCase.model_validate_json(case.model_dump_json()) == case

    schema = ProjectCase.model_json_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(payload)
    assert {"schema_id", "contract_version"} <= set(schema["required"])
    decimal_schema = schema["$defs"]["ResolvedValue"]["properties"]["value"]
    assert decimal_schema == {
        "maxLength": 74,
        "minLength": 1,
        "pattern": (
            r"^[+-]?(?:(?:[0-9]{1,36})(?:\.[0-9]{1,36})?|\.[0-9]{1,36})" r"(?![\s\S])"
        ),
        "title": "Value",
        "type": "string",
    }
    count_schema = schema["$defs"]["ResolvedCount"]["properties"]["value"]
    assert count_schema == {
        "maxLength": 36,
        "minLength": 1,
        "pattern": r"^[1-9][0-9]{0,35}(?![\s\S])",
        "title": "Value",
        "type": "string",
    }


@pytest.mark.parametrize("field", ["schema_id", "contract_version"])
def test_schema_identity_and_version_are_mandatory(field: str) -> None:
    payload = _case_payload()
    del payload[field]
    error = _error(payload, "Field required")
    assert error.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_id", "dutchbay.project_case.v2"),
        ("contract_version", "2.0.0"),
    ],
)
def test_unknown_or_future_schema_version_is_rejected(field: str, value: str) -> None:
    payload = _case_payload()
    payload[field] = value
    error = _error(payload, "literal_error")
    assert error.errors()[0]["loc"] == (field,)


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
        "declared",
    }
    fields = ProjectCase.model_fields
    assert "achieved_grade" not in fields
    assert "release_status" not in fields
    assert "run_mode" not in fields
    assert "contract_reviewed" not in PROJECT_CASE_MODULE.read_text(encoding="utf-8")


@pytest.mark.parametrize("status", ["registered", "derived", "disputed"])
def test_complete_boundary_states_are_explicit(status: str) -> None:
    payload = _case_payload()
    payload["location"]["boundary_status"] = status
    case = _validate(payload)
    assert case.location.boundary_status.value == status
    if status == "disputed":
        assert case.location.boundary_status.value not in {"surveyed", "contractual"}


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
    power_value = payload["assets"][1]["power_capacity"]["value"]
    duplicate = copy.deepcopy(power_value["bindings"][0])
    power_value["bindings"].append(duplicate)
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
        ("latitude_degrees", "91.0", "latitude_degrees requires degree unit"),
        ("longitude_degrees", "181.0", "longitude_degrees requires degree unit"),
    ],
)
def test_coordinates_have_explicit_global_bounds(
    field: str, value: str, pattern: str
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
            "support_status": "declared",
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


def test_every_storage_asset_requires_charging_source_disposition() -> None:
    payload = _case_payload()
    del payload["assets"][1]["charging_source"]
    error = _error(payload, "Field required")
    assert error.errors()[0]["loc"][:4] == (
        "assets",
        1,
        "storage",
        "charging_source",
    )


def test_storage_asset_source_requires_reciprocal_charges_from_link() -> None:
    payload = _case_payload()
    payload["topology"]["links"] = [
        item for item in payload["topology"]["links"] if item["kind"] != "charges_from"
    ]
    _error(payload, "charging source/link reciprocity is broken")


def test_common_interconnection_requires_grid_role() -> None:
    payload = _case_payload()
    payload["assets"][2]["infrastructure_role"] = "access_road"
    _error(payload, "common interconnection must name a grid-interconnection asset")


def test_dedicated_hybrid_without_shared_facility_is_valid() -> None:
    payload = _case_payload()
    payload["assets"] = payload["assets"][:2]
    payload["topology"].update(
        {
            "interconnection_arrangement": "dedicated_separate",
            "common_interconnection_asset_id": None,
            "links": [
                item
                for item in payload["topology"]["links"]
                if item["kind"] == "charges_from"
            ],
        }
    )
    case = _validate(payload)
    assert case.topology.interconnection_arrangement.value == "dedicated_separate"
    assert case.topology.common_interconnection_asset_id is None


def test_missing_charging_source_is_explicit_and_reciprocal() -> None:
    payload = _case_payload()
    payload["assets"][1]["charging_source"] = {
        "kind": "missing",
        "missing_input_id": "missing:bess-charging-source",
    }
    payload["topology"]["links"] = [
        item for item in payload["topology"]["links"] if item["kind"] != "charges_from"
    ]
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:bess-charging-source",
            "field_path": "/assets/1/charging_source",
            "expected_unit": "charging_source",
            "reason": "The charging supply has not been nominated.",
            "consequence": "Storage charging topology is unresolved.",
            "remedy": "Declare the governed charging supply.",
        }
    ]
    case = _validate(payload)
    storage = case.assets[1]
    assert storage.kind == "storage"
    assert storage.charging_source.kind == "missing"


def test_governed_non_asset_charging_source_is_explicit() -> None:
    payload = _case_payload()
    payload["assets"][1]["charging_source"] = {
        "kind": "governed_source",
        "source_id": "source:project-basis",
    }
    payload["topology"]["links"] = [
        item for item in payload["topology"]["links"] if item["kind"] != "charges_from"
    ]
    case = _validate(payload)
    storage = case.assets[1]
    assert storage.kind == "storage"
    assert storage.charging_source.kind == "governed_source"


@pytest.mark.parametrize(
    ("mutate", "pattern"),
    [
        (
            lambda value: value["topology"].update({"kind": "storage_only"}),
            "topology kind does not match asset composition",
        ),
        (
            lambda value: value["topology"].update(
                {"common_interconnection_asset_id": "asset:wind-block-01"}
            ),
            "must name a grid-interconnection asset",
        ),
        (
            lambda value: value["topology"].update(
                {"common_interconnection_asset_id": None}
            ),
            "common interconnection must name a grid-interconnection asset",
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
    _error(payload, "every technology asset must use the declared common")


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
    _error(payload, "asset asset:bess-01 must belong to the single ProjectCase v1 site")


def test_second_physical_site_cannot_exist_without_site_geometry() -> None:
    payload = _case_payload()
    payload["jurisdiction_bindings"].append(
        {
            "binding_id": "jurisdiction:lka:site",
            "jurisdiction_code": "LKA",
            "subject": "site",
            "support_status": "declared",
            "contract_pack_id": "contract-pack:lka-site",
            "contract_pack_version": "1.0.0",
        }
    )
    payload["assets"][1]["jurisdiction_codes"] = ["LKA"]
    _error(payload, "ProjectCase v1 requires exactly one site jurisdiction")


@pytest.mark.parametrize("second_share", [0.1, 0.3])
def test_under_or_over_allocation_fails_closed(second_share: float) -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][1]["share"] = _resolved(second_share, "fraction")
    _error(payload, "allocations must sum exactly to 1")


def test_zero_share_allocation_is_rejected_as_degenerate() -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][1]["share"] = _resolved(0.0, "fraction")
    _error(payload, r"range \(0, 1\]")


def test_partial_allocation_must_have_a_feasible_positive_remainder() -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][0]["share"] = _resolved(1, "fraction")
    payload["costs"]["allocations"][1]["share"] = {
        "state": "missing",
        "unit": "fraction",
        "missing_input_id": "missing:capex-bess-share",
    }
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:capex-bess-share",
            "field_path": "/costs/allocations/1/share",
            "expected_unit": "fraction",
            "reason": "The BESS allocation is not confirmed.",
            "consequence": "CAPEX allocation is incomplete.",
            "remedy": "Supply a positive BESS allocation.",
        }
    ]
    _error(payload, "missing allocation share is infeasible")


def test_partial_allocation_with_positive_remainder_is_valid() -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][1]["share"] = {
        "state": "missing",
        "unit": "fraction",
        "missing_input_id": "missing:capex-bess-share",
    }
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:capex-bess-share",
            "field_path": "/costs/allocations/1/share",
            "expected_unit": "fraction",
            "reason": "The BESS allocation is not confirmed.",
            "consequence": "CAPEX allocation is incomplete.",
            "remedy": "Supply a positive BESS allocation not exceeding 0.2.",
        }
    ]
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_complete_allocation_requires_exact_rational_closure() -> None:
    payload = _case_payload()
    payload["costs"]["allocations"][0]["share"] = _resolved(1, "fraction")
    payload["costs"]["allocations"][1]["share"] = _resolved(
        "0." + ("0" * 35) + "1", "fraction"
    )
    _error(payload, "allocations must sum exactly to 1")


@pytest.mark.parametrize(
    ("resolved_share", "accepted"),
    [
        ("0." + ("9" * 36), False),
        ("0." + ("9" * 35) + "8", True),
    ],
)
def test_partial_allocation_remainder_uses_exact_grid_feasibility(
    resolved_share: str, accepted: bool
) -> None:
    payload = _case_payload()
    allocations = payload["costs"]["allocations"]
    line = payload["costs"]["lines"][0]
    allocations[0]["share"] = _resolved(resolved_share, "fraction")
    allocations[1]["share"] = _missing_value("missing:capex-bess-share", "fraction")
    allocations.append(
        {
            "allocation_id": "allocation:capex:shared",
            "cost_line_id": "cost:capex:plant",
            "asset_id": "asset:poi-01",
            "share": _missing_value("missing:capex-shared-share", "fraction"),
        }
    )
    line["allocation_ids"].append("allocation:capex:shared")
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record(
            "missing:capex-bess-share",
            "/costs/allocations/1/share",
            "fraction",
        ),
        _missing_record(
            "missing:capex-shared-share",
            "/costs/allocations/4/share",
            "fraction",
        ),
    ]
    if accepted:
        assert _validate(payload).costs.reconciliation_status.value == (
            "incomplete_missing_input"
        )
    else:
        _error(payload, "missing allocation share is infeasible")


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


def test_price_basis_requires_exact_provenance_binding() -> None:
    payload = _case_payload()
    payload["costs"]["price_bases"][0].update(
        {
            "valuation_date": "2099-12-31",
            "price_level": "Arbitrary future nominal basis",
            "nominality": "nominal",
            "bindings": [],
        }
    )
    payload["costs"]["currency_conversions"][0]["valuation_date"] = "2099-12-31"
    _error(payload, "price basis requires source/assumption binding")


def test_price_basis_binding_must_cover_allocated_cost_scope() -> None:
    payload = _case_payload()
    payload["sources"].append(
        {
            "source_id": "source:wind-price-basis",
            "title": "Wind-only cost basis",
            "locator": "fixture:wind-only-price-basis",
            "jurisdiction_codes": ["FIC"],
            "technology_ids": ["wind"],
        }
    )
    payload["costs"]["price_bases"][0]["bindings"] = [
        {"kind": "source", "reference_id": "source:wind-price-basis"}
    ]
    _error(payload, r"wrong scope for /costs/price_bases/0")


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


def test_missing_positive_quantity_cannot_hide_zero_rate_contradiction() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _missing_value("missing:capex-quantity", "item")
    line["unit_rate_native"] = _resolved(0, "USD/item")
    line["amount"]["native_amount"] = _resolved("1.00", "USD")
    line["amount"]["reporting_amount"] = _resolved("1.00", "USD")
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record("missing:capex-quantity", "/costs/lines/0/quantity", "item")
    ]
    _error(payload, "zero factor cannot yield non-zero amount")


def test_missing_positive_quantity_is_accepted_when_product_is_feasible() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _missing_value("missing:capex-quantity", "item")
    line["unit_rate_native"] = _resolved("2.00", "USD/item")
    line["amount"]["native_amount"] = _resolved("1.00", "USD")
    line["amount"]["reporting_amount"] = _resolved("1.00", "USD")
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record("missing:capex-quantity", "/costs/lines/0/quantity", "item")
    ]
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_missing_nonnegative_unit_rate_is_accepted_when_product_is_feasible() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(2, "item")
    line["unit_rate_native"] = _missing_value("missing:capex-unit-rate", "USD/item")
    line["amount"]["native_amount"] = _resolved("4.00", "USD")
    line["amount"]["reporting_amount"] = _resolved("4.00", "USD")
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record(
            "missing:capex-unit-rate",
            "/costs/lines/0/unit_rate_native",
            "USD/item",
        )
    ]
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_missing_native_amount_cannot_conflict_with_same_currency_inference() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(1, "item")
    line["unit_rate_native"] = _resolved("2.00", "USD/item")
    line["amount"]["native_amount"] = _missing_value("missing:capex-native", "USD")
    line["amount"]["reporting_amount"] = _resolved("1.00", "USD")
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record(
            "missing:capex-native",
            "/costs/lines/0/amount/native_amount",
            "USD",
        )
    ]
    _error(payload, r"native amount must equal quantity \* unit_rate_native")


def test_missing_native_amount_is_accepted_when_equalities_are_feasible() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(1, "item")
    line["unit_rate_native"] = _resolved("2.00", "USD/item")
    line["amount"]["native_amount"] = _missing_value("missing:capex-native", "USD")
    line["amount"]["reporting_amount"] = _resolved("2.00", "USD")
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record(
            "missing:capex-native",
            "/costs/lines/0/amount/native_amount",
            "USD",
        )
    ]
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_missing_positive_fx_rate_cannot_map_zero_to_nonzero() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][1]
    line["quantity"] = _resolved(1, "year")
    line["unit_rate_native"] = _resolved(0, "LKR/year")
    line["amount"]["native_amount"] = _resolved("0.00", "LKR")
    line["amount"]["reporting_amount"] = _resolved("1.00", "USD")
    payload["costs"]["currency_conversions"][0]["rate"] = _missing_value(
        "missing:fx-rate", "USD/LKR"
    )
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record(
            "missing:fx-rate", "/costs/currency_conversions/0/rate", "USD/LKR"
        )
    ]
    _error(payload, "no feasible positive missing FX rate")


def test_missing_positive_fx_rate_is_accepted_for_nonzero_amounts() -> None:
    payload = _case_payload()
    payload["costs"]["currency_conversions"][0]["rate"] = _missing_value(
        "missing:fx-rate", "USD/LKR"
    )
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        _missing_record(
            "missing:fx-rate", "/costs/currency_conversions/0/rate", "USD/LKR"
        )
    ]
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_shared_missing_fx_rate_rejects_disjoint_consumer_intervals() -> None:
    maximum_rate = (10 ** (36 + 6)) - 1
    assert project_case_contract._grid_input_interval_for_exact_output(
        100,
        minimum_input=1,
        maximum_input=maximum_rate,
        input_decimal_places=6,
        factor=Decimal("100.00"),
        output_decimal_places=2,
    ) == (9950, 10050)
    assert project_case_contract._grid_input_interval_for_exact_output(
        200,
        minimum_input=1,
        maximum_input=maximum_rate,
        input_decimal_places=6,
        factor=Decimal("100.00"),
        output_decimal_places=2,
    ) == (19950, 20050)

    payload = _case_payload()
    _make_conversion_rate_missing(payload, quote_precision=6)
    _configure_fx_consumer(
        payload,
        1,
        native_amount="100.00",
        reporting_amount="1.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    _append_fx_consumer(
        payload,
        suffix="disjoint",
        native_amount="100.00",
        reporting_amount="2.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    _error(payload, "has no common positive missing FX rate")


def test_shared_missing_fx_rate_accepts_one_common_consumer_witness() -> None:
    payload = _case_payload()
    _make_conversion_rate_missing(payload, quote_precision=6)
    _configure_fx_consumer(
        payload,
        1,
        native_amount="100.00",
        reporting_amount="1.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    _append_fx_consumer(
        payload,
        suffix="common",
        native_amount="100.00",
        reporting_amount="1.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_shared_missing_fx_rate_uses_inferable_native_amounts() -> None:
    payload = _case_payload()
    _make_conversion_rate_missing(payload, quote_precision=6)
    _configure_fx_consumer(
        payload,
        1,
        native_amount="100.00",
        reporting_amount="1.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    _append_fx_consumer(
        payload,
        suffix="inferable-disjoint",
        native_amount="100.00",
        reporting_amount="2.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
        infer_native=True,
    )
    _error(payload, "has no common positive missing FX rate")


@pytest.mark.parametrize("forced_reporting", ["1", "2"])
def test_shared_missing_fx_rate_enforces_missing_report_output_domain(
    forced_reporting: str,
) -> None:
    payload = _case_payload()
    _make_conversion_rate_missing(payload, quote_precision=1)
    _configure_fx_consumer(
        payload,
        1,
        native_amount="1",
        reporting_amount=forced_reporting,
        native_minor_unit_places=0,
        reporting_minor_unit_places=0,
    )
    _append_fx_consumer(
        payload,
        suffix="maximum-native-missing-report",
        native_amount=MAX_PROJECT_INTEGER,
        reporting_amount=None,
        native_minor_unit_places=0,
        reporting_minor_unit_places=0,
    )
    if forced_reporting == "1":
        assert _validate(payload).costs.reconciliation_status.value == (
            "incomplete_missing_input"
        )
    else:
        _error(payload, "has no common positive missing FX rate")


def test_shared_missing_fx_rate_accepts_zero_native_zero_report_constraint() -> None:
    payload = _case_payload()
    _make_conversion_rate_missing(payload, quote_precision=4)
    _configure_fx_consumer(
        payload,
        1,
        native_amount="100.00",
        reporting_amount="1.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    _append_fx_consumer(
        payload,
        suffix="zero",
        native_amount="0.00",
        reporting_amount="0.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_three_consumers_with_different_money_precision_share_one_fx_rate() -> None:
    payload = _case_payload()
    _make_conversion_rate_missing(payload, quote_precision=4)
    _configure_fx_consumer(
        payload,
        1,
        native_amount="100.00",
        reporting_amount="1.00",
        native_minor_unit_places=2,
        reporting_minor_unit_places=2,
    )
    _append_fx_consumer(
        payload,
        suffix="three-decimal-report",
        native_amount="1.000",
        reporting_amount="0.010",
        native_minor_unit_places=3,
        reporting_minor_unit_places=3,
    )
    _append_fx_consumer(
        payload,
        suffix="one-decimal-report",
        native_amount="10",
        reporting_amount="0.1",
        native_minor_unit_places=0,
        reporting_minor_unit_places=1,
    )
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


@pytest.mark.parametrize("missing_fx", [False, True])
def test_underdetermined_native_and_missing_report_fail_closed(
    missing_fx: bool,
) -> None:
    payload = _case_payload()
    if missing_fx:
        _make_conversion_rate_missing(payload, quote_precision=6)
    line = payload["costs"]["lines"][1]
    _bind_missing(
        payload,
        line,
        "quantity",
        "missing:underdetermined-quantity",
        "year",
        "/costs/lines/1/quantity",
    )
    _bind_missing(
        payload,
        line,
        "unit_rate_native",
        "missing:underdetermined-rate",
        "LKR/year",
        "/costs/lines/1/unit_rate_native",
    )
    _bind_missing(
        payload,
        line["amount"],
        "native_amount",
        "missing:underdetermined-native",
        "LKR",
        "/costs/lines/1/amount/native_amount",
    )
    _bind_missing(
        payload,
        line["amount"],
        "reporting_amount",
        "missing:underdetermined-reporting",
        "USD",
        "/costs/lines/1/amount/reporting_amount",
    )
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    _error(
        payload, "requires an inferable native amount when reporting amount is missing"
    )


@pytest.mark.parametrize(
    ("native", "reporting", "reporting_places", "quote_places"),
    [
        ("1", "1", 0, 1),
        ("2", "1", 0, 1),
        ("100", "1.00", 2, 4),
        ("3.5", "0.04", 2, 3),
    ],
)
def test_missing_fx_interval_matches_independent_bounded_oracle(
    native: str,
    reporting: str,
    reporting_places: int,
    quote_places: int,
) -> None:
    payload = _case_payload()
    _make_conversion_rate_missing(payload, quote_precision=quote_places)
    native_exponent = Decimal(native).as_tuple().exponent
    assert isinstance(native_exponent, int)
    _configure_fx_consumer(
        payload,
        1,
        native_amount=native,
        reporting_amount=reporting,
        native_minor_unit_places=min(2, max(0, -native_exponent)),
        reporting_minor_unit_places=reporting_places,
    )
    case = _validate(payload)
    line = case.costs.lines[1]
    conversion = case.costs.currency_conversions[0]
    actual_interval = project_case_contract._missing_conversion_rate_interval(
        line, conversion
    )
    target = int(Fraction(Decimal(reporting)) * (10**reporting_places))
    witnesses: list[int] = []
    for quote_integer in range(1, 501):
        exact_output = (
            Fraction(Decimal(native))
            * Fraction(quote_integer, 10**quote_places)
            * (10**reporting_places)
        )
        quotient, remainder = divmod(exact_output.numerator, exact_output.denominator)
        if remainder * 2 < exact_output.denominator:
            rounded = quotient
        elif remainder * 2 > exact_output.denominator:
            rounded = quotient + 1
        else:
            rounded = quotient if quotient % 2 == 0 else quotient + 1
        if rounded == target:
            witnesses.append(quote_integer)

    actual_bounded = [
        value
        for value in range(1, 501)
        if actual_interval[0] <= value <= actual_interval[1]
    ]
    assert actual_bounded == witnesses


@pytest.mark.parametrize("missing_operand", ["unit_rate_native", "quantity"])
def test_joint_cost_fx_chain_rejects_incompatible_native_grid(
    missing_operand: str,
) -> None:
    payload = _case_payload()
    _configure_missing_opex_chain(
        payload,
        missing_operands=(missing_operand,),
        reporting_amount=1,
        fx_rate=2,
    )
    _error(payload, "connected cost/FX chain has no joint bounded completion")


@pytest.mark.parametrize("missing_operand", ["unit_rate_native", "quantity"])
def test_joint_cost_fx_chain_accepts_nearby_native_grid_solution(
    missing_operand: str,
) -> None:
    payload = _case_payload()
    _configure_missing_opex_chain(
        payload,
        missing_operands=(missing_operand,),
        reporting_amount=2,
        fx_rate=2,
    )
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_joint_cost_fx_chain_accepts_two_missing_product_operands() -> None:
    payload = _case_payload()
    _configure_missing_opex_chain(
        payload,
        missing_operands=("quantity", "unit_rate_native"),
        reporting_amount=2,
        fx_rate=2,
    )
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_native_grid_interval_solver_matches_an_independent_bounded_oracle() -> None:
    checked = 0
    for factor in map(Decimal, ("0.5", "1", "1.5", "2")):
        for input_places in range(2):
            for output_places in range(2):
                outputs = {
                    value: project_case_contract._rounded_linear_grid_output(
                        value,
                        input_decimal_places=input_places,
                        factor=factor,
                        output_decimal_places=output_places,
                    )
                    for value in range(21)
                }
                for target in range(max(outputs.values()) + 2):
                    witnesses = [
                        value for value, output in outputs.items() if output == target
                    ]
                    expected = (witnesses[0], witnesses[-1]) if witnesses else None
                    actual = (
                        project_case_contract._grid_input_interval_for_exact_output(
                            target,
                            minimum_input=0,
                            maximum_input=20,
                            input_decimal_places=input_places,
                            factor=factor,
                            output_decimal_places=output_places,
                        )
                    )
                    assert actual == expected
                    checked += 1
    assert checked == 1242


def test_inferable_native_amount_can_join_a_missing_fx_rate() -> None:
    payload = _case_payload()
    _configure_missing_opex_chain(
        payload, missing_operands=(), reporting_amount=1, fx_rate=None
    )
    assert _validate(payload).costs.reconciliation_status.value == (
        "incomplete_missing_input"
    )


def test_unbound_native_and_fx_chain_fails_closed_without_sampling() -> None:
    payload = _case_payload()
    _configure_missing_opex_chain(
        payload,
        missing_operands=("unit_rate_native",),
        reporting_amount=1,
        fx_rate=None,
    )
    _error(payload, "requires a resolved FX rate or an inferable native amount")


def test_decimal_identity_is_preserved_beyond_binary_float_range() -> None:
    payload = _case_payload()
    exact_integer = 9_007_199_254_740_993
    payload["assets"][2]["capacity"] = _resolved(exact_integer, "MW")
    case = _validate(payload)
    shared = case.assets[2]
    assert shared.kind == "shared_infrastructure"
    assert shared.capacity.state == "resolved"
    assert str(shared.capacity.value) == str(exact_integer)
    dumped = case.model_dump(mode="json")
    assert dumped["assets"][2]["capacity"]["value"] == str(exact_integer)


def test_high_precision_generation_is_independent_of_ambient_context() -> None:
    payload = _case_payload()
    exact_count = 10_000_000_000_000_000_000_000_000_001
    capacity = payload["assets"][0]["capacity"]
    capacity["unit_count"] = _resolved_count(exact_count)
    capacity["unit_power_capacity"] = _resolved(1, "MW")
    capacity["total_power_capacity"] = _resolved(str(exact_count), "MW")
    with localcontext() as context:
        context.prec = 6
        case = _validate(payload)
    dumped = case.model_dump(mode="json")
    assert dumped["assets"][0]["capacity"]["kind"] == "unitized"
    assert dumped["assets"][0]["capacity"]["unit_count"]["value"] == str(exact_count)


def test_high_precision_bess_is_independent_of_ambient_context() -> None:
    payload = _case_payload()
    basis_value = "100000000000000.00000000000001"
    exact_product = "10000000000000000000000000002.0000000000000000000000000001"
    storage = payload["assets"][1]
    storage["power_capacity"]["value"] = _resolved(basis_value, "MW")
    storage["duration"]["value"] = _resolved(basis_value, "hour")
    storage["energy_capacity"]["value"] = _resolved(exact_product, "MWh")
    with localcontext() as context:
        context.prec = 6
        case = _validate(payload)
    dumped = case.model_dump(mode="json")
    assert dumped["assets"][1]["kind"] == "storage"
    assert dumped["assets"][1]["energy_capacity"]["value"]["value"] == exact_product


def test_high_precision_money_is_independent_of_ambient_context() -> None:
    payload = _case_payload()
    exact_amount = "1234567890123456789012345678.90"
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(1, "item")
    line["unit_rate_native"] = _resolved(exact_amount, "USD/item")
    line["amount"]["native_amount"] = _resolved(exact_amount, "USD")
    line["amount"]["reporting_amount"] = _resolved(exact_amount, "USD")
    with localcontext() as context:
        context.prec = 6
        case = _validate(payload)
    dumped = case.model_dump(mode="json")
    assert dumped["costs"]["lines"][0]["amount"]["native_amount"]["value"] == (
        exact_amount
    )


def test_high_precision_fx_is_independent_of_ambient_context() -> None:
    payload = _case_payload()
    native_amount = "1234567890123456789012345678.90"
    reporting_amount = "1234567890123456790246913569.02"
    line = payload["costs"]["lines"][1]
    line["quantity"] = _resolved(1, "year")
    line["unit_rate_native"] = _resolved(native_amount, "LKR/year")
    line["amount"]["native_amount"] = _resolved(native_amount, "LKR")
    line["amount"]["reporting_amount"] = _resolved(reporting_amount, "USD")
    conversion = payload["costs"]["currency_conversions"][0]
    conversion["rate"] = _resolved("1.000000000000000001", "USD/LKR")
    conversion["quote_precision"] = 18
    with localcontext() as context:
        context.prec = 6
        case = _validate(payload)
    dumped = case.model_dump(mode="json")
    assert dumped["costs"]["lines"][1]["amount"]["reporting_amount"]["value"] == (
        reporting_amount
    )


@pytest.mark.parametrize(
    ("unit_rate", "amount"), [("1.005", "1.00"), ("1.015", "1.02")]
)
def test_money_rounding_is_explicit_half_even(unit_rate: str, amount: str) -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(1, "item")
    line["unit_rate_native"] = _resolved(unit_rate, "USD/item")
    line["amount"]["native_amount"] = _resolved(amount, "USD")
    line["amount"]["reporting_amount"] = _resolved(amount, "USD")
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_UP
        assert _validate(payload).costs.lines[0].line_id == "cost:capex:plant"


def test_money_rejects_non_half_even_tie_result() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(1, "item")
    line["unit_rate_native"] = _resolved("1.005", "USD/item")
    line["amount"]["native_amount"] = _resolved("1.01", "USD")
    line["amount"]["reporting_amount"] = _resolved("1.01", "USD")
    _error(payload, r"native amount must equal quantity \* unit_rate_native")


def test_numeric_domain_rejects_excess_integer_digits_as_validation_error() -> None:
    payload = _case_payload()
    payload["assets"][2]["capacity"] = _resolved("1e36", "MW")
    error = _error(payload, "plain notation")
    assert error.errors()[0]["type"] == "value_error"


def test_numeric_domain_rejects_excess_decimal_places_as_validation_error() -> None:
    payload = _case_payload()
    payload["assets"][2]["capacity"] = _resolved("1e-37", "MW")
    error = _error(payload, "plain notation")
    assert error.errors()[0]["type"] == "value_error"


@pytest.mark.parametrize(
    ("value", "use_shared_capacity"),
    [
        (("9" * 37), True),
        (("9" * 36) + "." + ("9" * 37), True),
        ("0." + ("9" * 37), False),
        ("0." + ("9" * 73), False),
        ("0." + ("9" * 100), False),
        ("0." + ("9" * 500), False),
        ("0." + ("0" * 37), False),
        ("0." + ("0" * 500), False),
        ("0e-37", False),
        ("0e-1000000", False),
        ("-0e-999999", False),
        ("1e-3", True),
        ("١.٢", True),
        (" 1.25", True),
        ("1\n", False),
        ("1\r", False),
        ("1\r\n", False),
        ("1\u2028", False),
        ("1\u2029", False),
    ],
)
def test_decimal_string_runtime_and_schema_reject_the_same_hostile_inputs(
    value: str, use_shared_capacity: bool
) -> None:
    schema = ProjectCase.model_json_schema()
    validator = jsonschema.Draft202012Validator(schema)
    payload = _validate(_case_payload()).model_dump(mode="json")
    if use_shared_capacity:
        payload["assets"][2]["capacity"]["value"] = value
    else:
        payload["location"]["latitude_degrees"]["value"] = value

    for precision, rounding in (
        (3, ROUND_DOWN),
        (28, ROUND_UP),
        (100, ROUND_DOWN),
    ):
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            with pytest.raises(ValidationError):
                ProjectCase.model_validate_json(json.dumps(payload))
            with pytest.raises(jsonschema.ValidationError):
                validator.validate(payload)


@pytest.mark.parametrize(
    ("value", "use_shared_capacity"),
    [
        (("9" * 36) + "." + ("9" * 36), True),
        ("0." + ("0" * 36), False),
        ("." + ("1" * 36), True),
    ],
)
def test_decimal_string_runtime_and_schema_accept_exact_boundaries(
    value: str, use_shared_capacity: bool
) -> None:
    schema = ProjectCase.model_json_schema()
    validator = jsonschema.Draft202012Validator(schema)
    payload = _validate(_case_payload()).model_dump(mode="json")
    if use_shared_capacity:
        payload["assets"][2]["capacity"]["value"] = value
    else:
        payload["location"]["latitude_degrees"]["value"] = value

    for precision, rounding in ((3, ROUND_UP), (28, ROUND_DOWN), (100, ROUND_UP)):
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            assert ProjectCase.model_validate_json(json.dumps(payload)).schema_id == (
                PROJECT_CASE_SCHEMA_ID
            )
            validator.validate(payload)


def test_boolean_is_not_a_decimal_in_runtime_or_schema() -> None:
    schema = ProjectCase.model_json_schema()
    validator = jsonschema.Draft202012Validator(schema)
    payload = _validate(_case_payload()).model_dump(mode="json")
    payload["location"]["latitude_degrees"]["value"] = True
    with pytest.raises(ValidationError, match="requires an exact plain-ASCII string"):
        ProjectCase.model_validate_json(json.dumps(payload))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)


def test_sub_grid_json_number_is_rejected_by_runtime_and_schema() -> None:
    schema = ProjectCase.model_json_schema()
    validator = jsonschema.Draft202012Validator(schema)
    payload = _validate(_case_payload()).model_dump(mode="json")
    payload["location"]["latitude_degrees"]["value"] = 1e-37
    with pytest.raises(ValidationError, match="requires an exact plain-ASCII string"):
        ProjectCase.model_validate_json(json.dumps(payload))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize(
    "raw_token",
    [
        "3e-36",
        "6.9999999999999999999999999999999999999e-36",
        "7.0000000000000000000000000000000000001e-36",
        "1.23456789012345678901234567890123456",
        "1.0000000000000000000000000000000000001",
        "1000000000000000000000000000000000000",
        "-1000000000000000000000000000000000000",
        ("9" * 36) + "." + ("9" * 36),
    ],
)
def test_raw_json_decimal_tokens_are_rejected_without_identity_loss(
    raw_token: str,
) -> None:
    marker = "__raw_decimal_token__"
    payload = _case_payload()
    payload["location"]["latitude_degrees"]["value"] = marker
    raw_json = json.dumps(payload).replace(json.dumps(marker), raw_token, 1)
    parsed_payload = json.loads(raw_json)

    for precision, rounding in ((3, ROUND_DOWN), (100, ROUND_UP)):
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            with pytest.raises(
                ValidationError, match="requires an exact plain-ASCII string"
            ):
                ProjectCase.model_validate_json(raw_json)
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.Draft202012Validator(
                    ProjectCase.model_json_schema()
                ).validate(parsed_payload)


@pytest.mark.parametrize(
    "raw_token",
    [
        "1",
        "1.0",
        "1e0",
        "999999999999999999999999999999999999",
        "1000000000000000000000000000000000000",
    ],
)
def test_raw_json_count_tokens_are_rejected_by_runtime_and_schema(
    raw_token: str,
) -> None:
    marker = "__raw_count_token__"
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"]["value"] = marker
    raw_json = json.dumps(payload).replace(json.dumps(marker), raw_token, 1)
    parsed_payload = json.loads(raw_json)
    with pytest.raises(ValidationError, match="JSON count requires"):
        ProjectCase.model_validate_json(raw_json)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(ProjectCase.model_json_schema()).validate(
            parsed_payload
        )


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        ("1", True),
        ("999999999999999999999999999999999999", True),
        ("0", False),
        ("-1", False),
        ("+1", False),
        ("01", False),
        ("1.0", False),
        ("1e0", False),
        ("1000000000000000000000000000000000000", False),
        (" 1", False),
        ("١", False),
        ("1\n", False),
        ("1\r", False),
        ("1\r\n", False),
        ("1\u2028", False),
        ("1\u2029", False),
    ],
)
def test_json_count_string_runtime_and_schema_are_lexically_equivalent(
    value: str, accepted: bool
) -> None:
    payload = _case_payload()
    capacity = payload["assets"][0]["capacity"]
    capacity["unit_count"]["value"] = value
    if accepted:
        capacity["unit_power_capacity"] = _resolved("1", "MW")
        capacity["total_power_capacity"] = _resolved(value, "MW")

    schema_validator = jsonschema.Draft202012Validator(ProjectCase.model_json_schema())
    if accepted:
        case = ProjectCase.model_validate_json(json.dumps(payload))
        schema_validator.validate(payload)
        generation = case.assets[0]
        assert generation.kind == "generation"
        assert generation.capacity.kind == "unitized"
        assert generation.capacity.unit_count.state == "resolved"
        assert generation.capacity.unit_count.value == int(value)
        assert (
            case.model_dump(mode="json")["assets"][0]["capacity"]["unit_count"]["value"]
            == value
        )
    else:
        with pytest.raises(ValidationError, match="JSON count requires"):
            ProjectCase.model_validate_json(json.dumps(payload))
        with pytest.raises(jsonschema.ValidationError):
            schema_validator.validate(payload)


def test_native_count_serializes_to_exact_json_string_and_reingresses() -> None:
    native_payload = _validate(_case_payload()).model_dump(mode="python")
    count = native_payload["assets"][0]["capacity"]["unit_count"]
    assert count["value"] == 2

    for precision, rounding in ((3, ROUND_UP), (100, ROUND_DOWN)):
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            case = ProjectCase.model_validate(native_payload)
            dumped = case.model_dump(mode="json")
            assert dumped["assets"][0]["capacity"]["unit_count"]["value"] == "2"
            jsonschema.Draft202012Validator(ProjectCase.model_json_schema()).validate(
                dumped
            )
            assert ProjectCase.model_validate_json(case.model_dump_json()) == case

    for invalid in ("2", 2.0, True):
        hostile = copy.deepcopy(native_payload)
        hostile["assets"][0]["capacity"]["unit_count"]["value"] = invalid
        with pytest.raises(ValidationError):
            ProjectCase.model_validate(hostile)


@pytest.mark.parametrize(
    ("value", "use_shared_capacity", "accepted"),
    [
        (Decimal(("9" * 36) + "." + ("9" * 36)), True, True),
        (Decimal("0." + ("0" * 36)), False, True),
        (Decimal("0E-36"), False, True),
        (Decimal("1E-3"), True, True),
        (Decimal("9" * 37), True, False),
        (Decimal("0." + ("9" * 37)), False, False),
        (Decimal("0E-37"), False, False),
        (Decimal("0E-1000000"), False, False),
    ],
)
def test_python_decimal_mode_uses_the_same_tuple_domain_without_context(
    value: Decimal, use_shared_capacity: bool, accepted: bool
) -> None:
    payload = _validate(_case_payload()).model_dump(mode="python")
    if use_shared_capacity:
        payload["assets"][2]["capacity"]["value"] = value
    else:
        payload["location"]["latitude_degrees"]["value"] = value

    for precision, rounding in ((3, ROUND_DOWN), (100, ROUND_UP)):
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            if accepted:
                assert ProjectCase.model_validate(payload).schema_id == (
                    PROJECT_CASE_SCHEMA_ID
                )
            else:
                with pytest.raises(ValidationError, match="numeric domain"):
                    ProjectCase.model_validate(payload)


@pytest.mark.parametrize(
    ("value", "serialized", "use_shared_capacity"),
    [
        (Decimal("0E+36"), "0", False),
        (Decimal("-0E+36"), "-0", False),
        (Decimal("1E+3"), "1000", True),
        (Decimal("0E-36"), "0." + ("0" * 36), False),
    ],
)
def test_python_decimal_serializes_to_schema_valid_plain_json(
    value: Decimal, serialized: str, use_shared_capacity: bool
) -> None:
    case_schema = jsonschema.Draft202012Validator(ProjectCase.model_json_schema())
    value_schema = jsonschema.Draft202012Validator(ResolvedValue.model_json_schema())
    native_payload = _validate(_case_payload()).model_dump(mode="python")
    if use_shared_capacity:
        native_payload["assets"][2]["capacity"]["value"] = value
    else:
        native_payload["location"]["latitude_degrees"]["value"] = value
    resolved_payload = _validate(_case_payload()).location.latitude_degrees.model_dump(
        mode="python"
    )
    resolved_payload["value"] = value

    for precision, rounding in ((3, ROUND_UP), (100, ROUND_DOWN)):
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            case = ProjectCase.model_validate(native_payload)
            dumped = case.model_dump(mode="json")
            if use_shared_capacity:
                assert dumped["assets"][2]["capacity"]["value"] == serialized
            else:
                assert dumped["location"]["latitude_degrees"]["value"] == serialized
            assert "e" not in serialized.lower()
            case_schema.validate(dumped)
            round_trip = ProjectCase.model_validate_json(case.model_dump_json())
            assert round_trip == case

            resolved = ResolvedValue.model_validate(resolved_payload)
            resolved_dump = resolved.model_dump(mode="json")
            assert resolved_dump["value"] == serialized
            value_schema.validate(resolved_dump)
            resolved_round_trip = ResolvedValue.model_validate_json(
                resolved.model_dump_json()
            )
            assert resolved_round_trip.value == value
            if value.is_zero():
                assert (
                    resolved_round_trip.value.as_tuple().sign == value.as_tuple().sign
                )
            if value.as_tuple().exponent == -36:
                assert resolved_round_trip.value.as_tuple().exponent == -36


@pytest.mark.parametrize(
    "value",
    [
        "1.25",
        "1e-3",
        "0." + ("0" * 36),
        "0e-37",
    ],
)
def test_python_mode_refuses_json_strings_until_a_transport_adapter_normalizes_them(
    value: str,
) -> None:
    payload = _validate(_case_payload()).model_dump(mode="python")
    payload["location"]["latitude_degrees"]["value"] = value
    with pytest.raises(ValidationError, match="Decimal"):
        ProjectCase.model_validate(payload)


def test_material_count_domain_rejects_a_37_digit_count() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"] = _resolved_count(10**36)
    error = _error(payload, "at most 36 digits")
    assert error.errors()[0]["type"] == "value_error"


def test_out_of_domain_intermediate_is_a_controlled_validation_error() -> None:
    payload = _case_payload()
    maximum_scale_operand = "100000000000000000000000000000000000"
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(maximum_scale_operand, "item")
    line["unit_rate_native"] = _resolved(maximum_scale_operand, "USD/item")
    line["amount"]["native_amount"] = _resolved(maximum_scale_operand, "USD")
    line["amount"]["reporting_amount"] = _resolved(maximum_scale_operand, "USD")
    error = _error(payload, "inferred value .* exceeds the ProjectCase numeric domain")
    assert error.errors()[0]["type"] == "value_error"


def test_large_money_gap_is_not_hidden_by_relative_tolerance() -> None:
    payload = _case_payload()
    line = payload["costs"]["lines"][0]
    line["quantity"] = _resolved(1, "item")
    line["unit_rate_native"] = _resolved(1_000_000_000_000, "USD/item")
    declared = _resolved(999_999_999_001, "USD")
    line["amount"]["native_amount"] = declared
    line["amount"]["reporting_amount"] = copy.deepcopy(declared)
    _error(payload, r"native amount must equal quantity \* unit_rate_native")


def test_fx_rate_cannot_exceed_declared_quote_precision() -> None:
    payload = _case_payload()
    payload["costs"]["currency_conversions"][0]["rate"] = _resolved(
        "0.0025001", "USD/LKR"
    )
    _error(payload, "currency conversion rate exceeds declared decimal precision 6")


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


def test_wind_only_fx_source_is_valid_in_wind_bess_case() -> None:
    payload = _case_payload()
    opex_line = payload["costs"]["lines"][1]
    opex_line["allocation_ids"] = ["allocation:opex:wind"]
    payload["costs"]["allocations"][2]["share"] = _resolved(1, "fraction")
    del payload["costs"]["allocations"][3]
    payload["sources"].append(
        {
            "source_id": "source:wind-fx",
            "title": "Wind-only fictional FX source",
            "locator": "fixture:wind-only-fx",
            "jurisdiction_codes": ["FIC"],
            "technology_ids": ["wind"],
        }
    )
    payload["costs"]["currency_conversions"][0]["rate"] = _resolved(
        "0.0025", "USD/LKR", reference_id="source:wind-fx"
    )
    assert _validate(payload).costs.currency_conversions[0].conversion_id == (
        "fx:lkr-to-usd:2026-08-29"
    )


def test_bess_only_source_cannot_support_wind_only_fx_conversion() -> None:
    payload = _case_payload()
    opex_line = payload["costs"]["lines"][1]
    opex_line["allocation_ids"] = ["allocation:opex:wind"]
    payload["costs"]["allocations"][2]["share"] = _resolved(1, "fraction")
    del payload["costs"]["allocations"][3]
    payload["sources"].append(
        {
            "source_id": "source:bess-fx",
            "title": "BESS-only fictional FX source",
            "locator": "fixture:bess-only-fx",
            "jurisdiction_codes": ["FIC"],
            "technology_ids": ["bess"],
        }
    )
    payload["costs"]["currency_conversions"][0]["rate"] = _resolved(
        "0.0025", "USD/LKR", reference_id="source:bess-fx"
    )
    _error(
        payload,
        r"source source:bess-fx has wrong scope for "
        r"/costs/currency_conversions/0/rate",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("power_capacity", "-2.5"),
        ("energy_capacity", "nan"),
        ("duration", "inf"),
    ],
)
def test_storage_rejects_negative_or_non_finite_numbers(field: str, value: str) -> None:
    payload = _case_payload()
    payload["assets"][1][field]["value"]["value"] = value
    _error(payload, "plain notation|positive")


def test_shared_capacity_zero_cannot_stand_for_missing() -> None:
    payload = _case_payload()
    payload["assets"][2]["capacity"] = _resolved(0.0, "MW")
    error = _error(payload, "shared infrastructure capacity must be positive")
    assert error.errors()[0]["loc"][:3] == (
        "assets",
        2,
        "shared_infrastructure",
    )


def test_solar_pv_dc_nameplate_capacity_is_preserved() -> None:
    payload = _case_payload()
    payload["technology_bindings"][0].update(
        {
            "binding_id": "technology:solar-pv:generation",
            "technology_id": "solar-pv",
            "contract_pack_id": "contract-pack:solar-pv-generation",
        }
    )
    payload["assets"][0].update(
        {
            "asset_id": "asset:solar-block-01",
            "name": "Solar PV block 01",
            "technology_id": "solar-pv",
            "technology_binding_id": "technology:solar-pv:generation",
            "capacity": {
                "kind": "aggregate",
                "electrical_basis": "dc",
                "capacity_basis": "nameplate",
                "total_power_capacity": _resolved(100, "MWdc"),
            },
        }
    )
    payload["assets"][1]["charging_source"]["asset_id"] = "asset:solar-block-01"
    for link in payload["topology"]["links"]:
        if link["from_asset_id"] == "asset:wind-block-01":
            link["from_asset_id"] = "asset:solar-block-01"
        if link["to_asset_id"] == "asset:wind-block-01":
            link["to_asset_id"] = "asset:solar-block-01"
    for allocation in payload["costs"]["allocations"]:
        if allocation["asset_id"] == "asset:wind-block-01":
            allocation["asset_id"] = "asset:solar-block-01"
    payload["sources"][0]["technology_ids"] = ["solar-pv", "bess"]
    case = _validate(payload)
    generation = case.assets[0]
    assert generation.kind == "generation"
    assert generation.capacity.electrical_basis.value == "dc"
    assert generation.capacity.total_power_capacity.unit == "MWdc"


def test_generation_electrical_basis_and_unit_must_be_compatible() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["electrical_basis"] = "dc"
    _error(payload, "requires one of units: MWdc, MWp")


@pytest.mark.parametrize(
    ("field", "basis_field", "basis_value"),
    [
        ("energy_capacity", "capacity_basis", "nameplate"),
        ("energy_capacity", "electrical_basis", "dc"),
    ],
)
def test_storage_power_energy_duration_bases_must_match(
    field: str, basis_field: str, basis_value: str
) -> None:
    payload = _case_payload()
    payload["assets"][1][field][basis_field] = basis_value
    _error(payload, "storage power, energy, and duration require compatible bases")


def test_bess_power_energy_duration_must_reconcile() -> None:
    payload = _case_payload()
    payload["assets"][1]["duration"]["value"] = _resolved(3.0, "hour")
    error = _error(payload, r"storage energy must equal power \* duration")
    assert error.errors()[0]["loc"][:3] == ("assets", 1, "storage")


def test_unitized_generation_count_capacity_must_reconcile() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["total_power_capacity"] = _resolved(11.0, "MW")
    error = _error(payload, r"unit_count \* unit_power_capacity")
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
        "electrical_basis": "not_applicable",
        "capacity_basis": "nameplate",
        "total_power_capacity": _resolved(10.0, "MW"),
    }
    case = _validate(payload)
    generation = case.assets[0]
    assert generation.kind == "generation"
    assert generation.capacity.kind == "aggregate"


def test_missing_unit_rating_defers_generation_arithmetic() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_power_capacity"] = {
        "state": "missing",
        "unit": "MW",
        "missing_input_id": "missing:wind-unit-rating",
    }
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:wind-unit-rating",
            "field_path": "/assets/0/capacity/unit_power_capacity",
            "expected_unit": "MW",
            "reason": "The turbine model is not selected.",
            "consequence": "Unitized generation arithmetic is incomplete.",
            "remedy": "Provide the selected turbine rating.",
        }
    ]
    assert _validate(payload).missing_inputs[0].expected_unit == "MW"


@pytest.mark.parametrize("value", ["0", "-1", "2.5"])
def test_resolved_unit_count_requires_positive_integer(value: str) -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"]["value"] = value
    _error(payload, "positive unsigned decimal string")


def test_resolved_unit_count_requires_provenance_binding() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"]["bindings"] = []
    _error(payload, "resolved material count requires source/assumption binding")


def test_material_value_without_provenance_binding_fails_closed() -> None:
    payload = _case_payload()
    payload["assets"][1]["power_capacity"]["value"]["bindings"] = []
    _error(payload, "requires source/assumption binding")


def test_material_value_with_dangling_source_binding_fails_closed() -> None:
    payload = _case_payload()
    power_value = payload["assets"][1]["power_capacity"]["value"]
    power_value["bindings"][0]["reference_id"] = "source:missing"
    _error(payload, "dangling source reference")


def test_dangling_assumption_and_unreferenced_source_fail_closed() -> None:
    payload = _case_payload()
    payload["assets"][1]["power_capacity"]["value"]["bindings"] = [
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


def test_missing_unit_count_must_admit_an_integer_solution() -> None:
    payload = _case_payload()
    payload["assets"][0]["capacity"]["unit_count"] = {
        "state": "missing",
        "unit": "count",
        "missing_input_id": "missing:wind-unit-count",
    }
    payload["assets"][0]["capacity"]["total_power_capacity"] = _resolved(11, "MW")
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:wind-unit-count",
            "field_path": "/assets/0/capacity/unit_count",
            "expected_unit": "count",
            "reason": "Final turbine count has not been selected.",
            "consequence": "Unitized capacity arithmetic is incomplete.",
            "remedy": "Provide a positive integer count reconciling 11 MW / 5 MW.",
        }
    ]
    _error(payload, "missing unit_count cannot reconcile resolved total/unit capacity")


def test_missing_bess_duration_defers_only_capacity_arithmetic() -> None:
    payload = _case_payload()
    payload["assets"][1]["duration"]["value"] = {
        "state": "missing",
        "unit": "hour",
        "missing_input_id": "missing:bess-duration",
    }
    payload["missing_inputs"] = [
        {
            "missing_input_id": "missing:bess-duration",
            "field_path": "/assets/1/duration/value",
            "expected_unit": "hour",
            "reason": "The selected dispatch duration is not confirmed.",
            "consequence": "BESS capacity reconciliation is incomplete.",
            "remedy": "Provide the approved storage duration.",
        }
    ]
    case = _validate(payload)
    storage = case.assets[1]
    assert storage.kind == "storage"
    assert storage.duration.value.state == "missing"


@pytest.mark.parametrize("unit_power", [MAX_PROJECT_INTEGER, MIN_PROJECT_DECIMAL])
def test_missing_generation_total_requires_bounded_product(unit_power: str) -> None:
    payload = _case_payload()
    capacity = payload["assets"][0]["capacity"]
    capacity["unit_count"] = _resolved_count((10**36) - 1)
    capacity["unit_power_capacity"] = _resolved(unit_power, "MW")
    _bind_missing(
        payload,
        capacity,
        "total_power_capacity",
        "missing:wind-total",
        "MW",
        "/assets/0/capacity/total_power_capacity",
    )
    if unit_power == MIN_PROJECT_DECIMAL:
        assert _validate(payload).assets[0].kind == "generation"
    else:
        _error(payload, "missing total_power_capacity has no bounded grid completion")


@pytest.mark.parametrize("total_power", [MIN_PROJECT_DECIMAL, "1"])
def test_missing_generation_unit_rating_requires_grid_solution(
    total_power: str,
) -> None:
    payload = _case_payload()
    capacity = payload["assets"][0]["capacity"]
    capacity["unit_count"] = _resolved_count((10**36) - 1)
    capacity["total_power_capacity"] = _resolved(total_power, "MW")
    _bind_missing(
        payload,
        capacity,
        "unit_power_capacity",
        "missing:wind-unit-rating",
        "MW",
        "/assets/0/capacity/unit_power_capacity",
    )
    if total_power == "1":
        assert _validate(payload).assets[0].kind == "generation"
    else:
        _error(payload, "missing unit_power_capacity has no bounded grid completion")


@pytest.mark.parametrize("duration", [MAX_PROJECT_INTEGER, MIN_PROJECT_DECIMAL])
def test_missing_storage_energy_requires_bounded_product(duration: str) -> None:
    payload = _case_payload()
    storage = payload["assets"][1]
    storage["power_capacity"]["value"] = _resolved(MAX_PROJECT_INTEGER, "MW")
    storage["duration"]["value"] = _resolved(duration, "hour")
    _bind_missing(
        payload,
        storage["energy_capacity"],
        "value",
        "missing:bess-energy",
        "MWh",
        "/assets/1/energy_capacity/value",
    )
    if duration == MIN_PROJECT_DECIMAL:
        assert _validate(payload).assets[1].kind == "storage"
    else:
        _error(payload, "missing storage energy has no bounded grid completion")


@pytest.mark.parametrize("energy", [MIN_PROJECT_DECIMAL, "1"])
def test_missing_storage_power_requires_grid_solution(energy: str) -> None:
    payload = _case_payload()
    storage = payload["assets"][1]
    storage["energy_capacity"]["value"] = _resolved(energy, "MWh")
    storage["duration"]["value"] = _resolved(MAX_PROJECT_INTEGER, "hour")
    _bind_missing(
        payload,
        storage["power_capacity"],
        "value",
        "missing:bess-power",
        "MW",
        "/assets/1/power_capacity/value",
    )
    if energy == "1":
        assert _validate(payload).assets[1].kind == "storage"
    else:
        _error(payload, "missing storage power has no bounded grid completion")


@pytest.mark.parametrize("energy", [MIN_PROJECT_DECIMAL, "1"])
def test_missing_storage_duration_requires_grid_solution(energy: str) -> None:
    payload = _case_payload()
    storage = payload["assets"][1]
    storage["power_capacity"]["value"] = _resolved(MAX_PROJECT_INTEGER, "MW")
    storage["energy_capacity"]["value"] = _resolved(energy, "MWh")
    _bind_missing(
        payload,
        storage["duration"],
        "value",
        "missing:bess-duration",
        "hour",
        "/assets/1/duration/value",
    )
    if energy == "1":
        assert _validate(payload).assets[1].kind == "storage"
    else:
        _error(payload, "missing storage duration has no bounded grid completion")


def test_two_missing_generation_values_require_a_constructive_completion() -> None:
    payload = _case_payload()
    capacity = payload["assets"][0]["capacity"]
    capacity["unit_count"] = _resolved_count((10**36) - 1)
    capacity["unit_power_capacity"] = _missing_value("missing:wind-unit-rating", "MW")
    capacity["total_power_capacity"] = _missing_value("missing:wind-total", "MW")
    payload["missing_inputs"] = [
        _missing_record(
            "missing:wind-unit-rating",
            "/assets/0/capacity/unit_power_capacity",
            "MW",
        ),
        _missing_record(
            "missing:wind-total",
            "/assets/0/capacity/total_power_capacity",
            "MW",
        ),
    ]
    assert _validate(payload).assets[0].kind == "generation"


def test_two_missing_storage_values_require_a_constructive_completion() -> None:
    payload = _case_payload()
    storage = payload["assets"][1]
    storage["power_capacity"]["value"] = _resolved(str((10**36) - 1), "MW")
    storage["energy_capacity"]["value"] = _missing_value("missing:bess-energy", "MWh")
    storage["duration"]["value"] = _missing_value("missing:bess-duration", "hour")
    payload["missing_inputs"] = [
        _missing_record(
            "missing:bess-energy", "/assets/1/energy_capacity/value", "MWh"
        ),
        _missing_record("missing:bess-duration", "/assets/1/duration/value", "hour"),
    ]
    assert _validate(payload).assets[1].kind == "storage"


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
    _error(payload, r"wrong scope for /costs/price_bases/0")


def test_source_cannot_cross_jurisdiction_scope() -> None:
    payload = _case_payload()
    payload["jurisdiction_bindings"].append(
        {
            "binding_id": "jurisdiction:lka:site",
            "jurisdiction_code": "LKA",
            "subject": "corporate",
            "support_status": "declared",
            "contract_pack_id": "contract-pack:lka-site",
            "contract_pack_version": "1.0.0",
        }
    )
    payload["sources"][0]["jurisdiction_codes"] = ["LKA"]
    _error(payload, r"wrong scope for /location/boundary_binding")


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
    payload["assets"][1]["power_capacity"]["value"]["bindings"] = [
        {"kind": "assumption", "reference_id": "assumption:wind-only"}
    ]
    _error(payload, r"wrong scope for /assets/1/power_capacity/value")


def test_assumption_cannot_cross_jurisdiction_scope() -> None:
    payload = _case_payload()
    payload["jurisdiction_bindings"].append(
        {
            "binding_id": "jurisdiction:lka:site",
            "jurisdiction_code": "LKA",
            "subject": "corporate",
            "support_status": "declared",
            "contract_pack_id": "contract-pack:lka-site",
            "contract_pack_version": "1.0.0",
        }
    )
    payload["assumptions"] = [
        {
            "assumption_id": "assumption:fic-bess-only",
            "statement": "Fictionland-only BESS assumption.",
            "basis": "Fictional BESS fixture.",
            "replacement_action": "Replace with multi-jurisdiction evidence.",
            "jurisdiction_codes": ["LKA"],
            "technology_ids": ["bess"],
        }
    ]
    payload["assets"][1]["power_capacity"]["value"]["bindings"] = [
        {"kind": "assumption", "reference_id": "assumption:fic-bess-only"}
    ]
    _error(payload, r"wrong scope for /assets/1/power_capacity/value")


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
