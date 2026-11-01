"""Direct controls for D4 refusals missed by the original public-path suite (#1404)."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from typing import Any

import pytest

import analytics.operational.eya_bridge as bridge
from analytics.operational.aep import OperationalAEPResult, OperationalEnergyQuantity
from analytics.resource_contracts import ResourceAssessment
from tests.contracts.test_eya_actual_bridge import annual_sources  # noqa: F401
from tests.contracts.test_eya_actual_bridge import (
    _bridge_inputs,
    _complete_bridge,
)


def test_receipt_discloses_identity_and_rejects_independent_check_laundering(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
) -> None:
    result = _complete_bridge(*annual_sources)
    assert result.receipt.full_reconciliation_residual_kwh.as_fraction() == 0
    assert result.receipt.model_dump()["full_reconciliation_semantics"] == (
        "arithmetic_identity_not_independent_check"
    )
    for claimed in ("independent_check", True):
        with pytest.raises(ValueError, match="disclose arithmetic identity"):
            replace(result.receipt, full_reconciliation_semantics=claimed)  # type: ignore[arg-type]


def test_quantity_rejects_noncanonical_stored_integer_representation() -> None:
    quantity = OperationalEnergyQuantity(1)
    object.__setattr__(quantity, "numerator", True)
    with pytest.raises(ValueError, match="non-canonical stored representation"):
        bridge._exact_energy_fraction(quantity, "quantity")


@pytest.mark.parametrize("field", ["finance_proposal", "receipt"])
def test_output_projection_refuses_wrong_owned_contract_before_dispatch(
    field: str,
) -> None:
    values: dict[str, Any] = {
        "eya_net_energy_kwh": OperationalEnergyQuantity(0),
        "actual_net_energy_kwh": OperationalEnergyQuantity(0),
        "total_gap_kwh": OperationalEnergyQuantity(0),
        "category_components": (),
        "unknown_residual_kwh": OperationalEnergyQuantity(0),
        "finance_proposal": bridge.FinanceUpdateProposal("a" * 64, "b" * 64),
        "receipt": object.__new__(bridge.EYAActualBridgeReceipt),
    }
    values[field] = object()
    with pytest.raises(ValueError, match=f"{field} must use the exact D4 contract"):
        bridge._result_output_projection(**values)


def test_invalid_hex_uses_the_declared_error_instead_of_a_parser_exception() -> None:
    with pytest.raises(ValueError, match="is not valid binary64 hex text"):
        bridge._float_from_canonical_hex("invalid-hex", "energy")


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        ({"dicts": [{} for _ in range(1_001)]}, "too many containers"),
        ({"values": [0 for _ in range(10_001)]}, "too many scalar values"),
        ({"unsupported": ()}, "unsupported scalar or container"),
        ({"\u00e9" * 200_000: None}, "canonical JSON exceeds 1 MiB"),
    ],
)
def test_manifest_guards_are_reached_directly(
    manifest: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        bridge._manifest_snapshot(manifest)


def test_list_cycle_is_refused_before_recursive_descent() -> None:
    cycle: list[Any] = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="run_manifest contains a cycle"):
        bridge._manifest_snapshot({"cycle": cycle})


def test_uninitialized_exact_resource_claim_has_a_closed_error() -> None:
    malformed = object.__new__(ResourceAssessment)
    with pytest.raises(
        bridge.EYAActualBridgeError, match="claim could not be constructed"
    ):
        bridge.resource_assessment_claim_sha256(malformed)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("columns", (object(),), "columns contain a non-exact binding"),
        ("lineage_source_sha256", [], "lineage must use an exact tuple"),
    ],
)
def test_retained_d1_refusals_precede_reconstruction(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
    field: str,
    value: object,
    message: str,
) -> None:
    evidence = copy.copy(annual_sources[1].inputs.normalized_results[0].evidence)
    object.__setattr__(evidence, field, value)
    with pytest.raises(ValueError, match=message):
        bridge._reconstruct_d1_evidence(evidence)


def test_d2_active_graph_cycle_is_refused_before_replay(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
) -> None:
    normalized = annual_sources[1].inputs.normalized_results[0]
    with pytest.raises(ValueError, match="graph contains a cycle"):
        bridge._replay_d2_with_exact_bytes(normalized, active={id(normalized)})


def test_d2_nonexact_exclusion_cannot_be_filtered_silently(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
) -> None:
    normalized = copy.copy(annual_sources[1].inputs.normalized_results[0])
    receipt = copy.copy(normalized.receipt)
    object.__setattr__(receipt, "column_exclusions", (object(),))
    object.__setattr__(normalized, "receipt", receipt)
    with pytest.raises(ValueError, match="exclusions contain non-exact contracts"):
        bridge._replay_d2_with_exact_bytes(normalized, active=set())


@pytest.mark.parametrize(
    "field", ["assessments", "normalized_results", "supplemental_evidence"]
)
def test_d3_retained_containers_are_exact_tuples(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
    field: str,
) -> None:
    inputs = copy.copy(annual_sources[1].inputs)
    object.__setattr__(inputs, field, [])
    with pytest.raises(ValueError, match=f"D3 {field} must use an exact tuple"):
        bridge._reconstruct_operational_inputs(inputs)


@pytest.mark.parametrize(
    ("index", "message"),
    [
        (0, "resource snapshot type is invalid"),
        (2, "bridge spec type is invalid"),
        (3, "boundary evidence type is invalid"),
    ],
)
def test_artifact_builder_refuses_wrong_contracts_before_model_dump(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
    index: int,
    message: str,
) -> None:
    resource, operational = annual_sources
    spec, boundary = _bridge_inputs(resource, operational)
    args: list[Any] = [
        bridge._snapshot_resource_assessment(resource),
        operational,
        spec,
        boundary,
        (),
    ]
    args[index] = object()
    with pytest.raises(bridge.EYAActualBridgeError, match=message):
        bridge._build_artifacts(*args)


def test_artifact_reconstruction_refuses_mutated_provenance_with_closed_error(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
) -> None:
    resource, operational = annual_sources
    spec, boundary = _bridge_inputs(resource, operational)
    forged = copy.copy(boundary)
    object.__setattr__(forged, "source_bytes", b"substituted without updating digest")
    with pytest.raises(
        bridge.EYAActualBridgeError, match="inputs failed defensive reconstruction"
    ):
        bridge._build_artifacts(
            bridge._snapshot_resource_assessment(resource),
            operational,
            spec,
            forged,
            (),
        )


@pytest.mark.parametrize("token", ["2025-01-01", "invalidZ"])
def test_utc_refusals_are_individually_reached(token: str) -> None:
    message = "must be RFC3339" if not token.endswith("Z") else "not valid UTC"
    with pytest.raises(bridge.EYAActualBridgeError, match=message):
        bridge._parse_utc(token)


def test_decimal_type_refusal_cannot_be_replaced_by_an_attribute_error() -> None:
    with pytest.raises(
        ValueError, match="energy effects must be bounded finite decimal strings"
    ):
        bridge._fraction_from_decimal(True)


def test_provenance_size_refusal_is_not_satisfied_by_a_later_hash_error() -> None:
    source = b"x" * 1_048_577
    method = b"method"
    with pytest.raises(ValueError, match="artifacts must not exceed 1 MiB"):
        bridge._validate_provenance(
            "source",
            source,
            hashlib.sha256(source).hexdigest(),
            method,
            hashlib.sha256(method).hexdigest(),
        )


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        ([], "must be None or an exact dictionary"),
        ({1: None}, "keys must be exact strings"),
    ],
)
def test_manifest_type_refusals_precede_generic_serialization(
    manifest: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        bridge._manifest_snapshot(manifest)


def test_resource_runtime_type_refusal_precedes_field_access() -> None:
    with pytest.raises(
        bridge.EYAActualBridgeError, match="must use the exact public contract"
    ):
        bridge._snapshot_resource_assessment(object())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("capacity_mw", True, "capacity_mw must be a finite exact float"),
        ("n_turbines", 0, "n_turbines must be a positive integer"),
        ("selected_p_level", "P10", "selected P-level must be canonical"),
    ],
)
def test_resource_field_refusals_precede_defensive_reconstruction(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
    field: str,
    value: object,
    message: str,
) -> None:
    resource = copy.copy(annual_sources[0])
    object.__setattr__(resource, field, value)
    with pytest.raises(bridge.EYAActualBridgeError, match=message):
        bridge._snapshot_resource_assessment(resource)


def test_mutable_buffer_is_refused_even_when_memoryview_could_copy_it() -> None:
    with pytest.raises(ValueError, match="source must be immutable bytes"):
        bridge._exact_buffer_bytes(bytearray(b"source"), "source")


@pytest.mark.parametrize(
    ("helper", "message"),
    [
        (
            bridge._reconstruct_d1_evidence,
            "retained D1 evidence must use exact public contracts",
        ),
        (
            bridge._reconstruct_assessment,
            "retained D1 assessments must use exact public contracts",
        ),
        (
            bridge._reconstruct_timezone_rules,
            "retained timezone rules use the wrong runtime contract",
        ),
        (
            bridge._reconstruct_operational_inputs,
            "retained D3 inputs use the wrong runtime contract",
        ),
        (
            bridge._reconstruct_operational_spec,
            "retained D3 spec uses the wrong runtime contract",
        ),
    ],
)
def test_wrong_retained_contract_refusal_is_not_a_later_attribute_error(
    helper: Any, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        helper(object())


def test_wrong_d2_contract_is_refused_before_replay() -> None:
    with pytest.raises(
        ValueError, match="retained D2 result uses the wrong runtime contract"
    ):
        bridge._replay_d2_with_exact_bytes(object(), active=set())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("lineage_source_bytes", [], "lineage bytes must use an exact tuple"),
        ("group_universe", object(), "group universe uses the wrong contract"),
        ("receipt", object(), "receipt uses the wrong runtime contract"),
    ],
)
def test_d2_retained_field_refusals_are_not_later_replay_errors(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
    field: str,
    value: object,
    message: str,
) -> None:
    normalized = copy.copy(annual_sources[1].inputs.normalized_results[0])
    object.__setattr__(normalized, field, value)
    with pytest.raises(ValueError, match=message):
        bridge._replay_d2_with_exact_bytes(normalized, active=set())


def test_d2_exclusion_container_refusal_is_not_a_later_iteration_error(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
) -> None:
    normalized = copy.copy(annual_sources[1].inputs.normalized_results[0])
    receipt = copy.copy(normalized.receipt)
    object.__setattr__(receipt, "row_exclusions", [])
    object.__setattr__(normalized, "receipt", receipt)
    with pytest.raises(ValueError, match="exclusions must use exact tuples"):
        bridge._replay_d2_with_exact_bytes(normalized, active=set())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("boundary_evidence", object(), "boundary uses the wrong runtime contract"),
        (
            "supplemental_evidence",
            (object(),),
            "supplement uses the wrong runtime contract",
        ),
    ],
)
def test_d3_nested_contract_refusals_are_not_later_replay_errors(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],  # noqa: F811
    field: str,
    value: object,
    message: str,
) -> None:
    inputs = copy.copy(annual_sources[1].inputs)
    object.__setattr__(inputs, field, value)
    with pytest.raises(ValueError, match=message):
        bridge._reconstruct_operational_inputs(inputs)


def test_operational_result_type_refusal_is_not_a_generic_replay_error() -> None:
    with pytest.raises(
        bridge.EYAActualBridgeError, match="must use the exact D3 public contract"
    ):
        bridge._replay_operational_result(object())
