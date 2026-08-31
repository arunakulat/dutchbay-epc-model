"""Hostile and independent-oracle controls for the D3C-1a result projection."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import logging
import os
import struct
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import analytics.evaluation_v14 as evaluation_v14
import analytics.feasibility_execution as execution
import analytics.feasibility_result_projection as projection_module
from analytics.contracts_v14 import D3BExecutionSuccess
from analytics.feasibility_report_contract import (
    D3C_INSPECTED_LAYER_KEYS,
    D3C_RESULT_FIELD_ROUTES,
    D3C_RESULT_PATH_DISPOSITIONS,
    AuthoredNumericProjection,
    CarriedResultObservation,
    D3CResultProjection,
    EngineManifestProjection,
    ExcludedResultField,
    FxIntegrationProjection,
    NumericProjectionReceiptProjection,
    OriginInvariantProjection,
    ProjectionLimitation,
    ResultCarryPredicate,
    ResultFieldRoute,
    ResultObservationClass,
    ResultObservationState,
    ResultPathDisposition,
    ResultScalarKind,
    ResultUnknownKeyType,
    ResultValueType,
    ResultZeroPolicy,
    SectionResultProjection,
    UnavailableResultObservation,
    UnrecognizedUpstreamKey,
)
from analytics.feasibility_report_contract.engine_identity import (
    ENGINE_VERSION_IDENTITY,
    ENGINE_VERSION_SOURCE_PATH,
    ENGINE_VERSION_SOURCE_SHA256,
    MANIFEST_SCHEMA_SOURCE_PATH,
    MANIFEST_SCHEMA_SOURCE_SHA256,
    MANIFEST_SCHEMA_VERSION_IDENTITY,
)
from analytics.feasibility_report_contract.taxonomy_identity import (
    FEASIBILITY_SECTION_IDS,
    FEASIBILITY_TAXONOMY_SOURCE_PATH,
    FEASIBILITY_TAXONOMY_SOURCE_SHA256,
)
from analytics.feasibility_result_projection import (
    ResultProjectionError,
    project_d3b_result,
)
from analytics.feasibility_sections import load_feasibility_taxonomy
from tests.contracts.test_d3b_execution_contract import (
    _AUTHORITY_ID,
    _bundle,
    _gateway_result,
    _install_gateway,
)

_MODULE = Path(inspect.getfile(project_d3b_result)).resolve()
_CONTRACT_MODULE = Path(inspect.getfile(D3CResultProjection)).resolve()


@pytest.fixture
def accepted_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> D3BExecutionSuccess:
    """Return a controlled accepted D3B outcome without relying on facade code."""

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
    return result


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _replace_result(
    result: D3BExecutionSuccess,
    mutator: Callable[[dict[Any, Any]], None],
    *,
    reconcile_origins: bool = True,
) -> D3BExecutionSuccess:
    payload = copy.deepcopy(result.model_dump()["full_result"])
    mutator(payload)
    scenario = payload.get("scenario_result")
    if reconcile_origins and type(scenario) is dict:
        for name in ("annual_rows", "debt_result", "kpis"):
            if name in payload:
                scenario[name] = copy.deepcopy(payload[name])
    frozen = _freeze(payload)
    return replace(
        result,
        full_result=frozen,
        run_manifest=frozen["run_manifest"],
    )


def _observation(projection: D3CResultProjection, route_id: str) -> Any:
    return next(
        item for item in projection.route_observations if item.route_id == route_id
    )


def _set_project_irr(payload: dict[Any, Any], value: Any, mirror: Any = None) -> None:
    payload["kpis"]["project_irr"] = value
    payload["scenario_result"]["project_irr"] = value if mirror is None else mirror


def test_real_public_gateway_is_an_independent_lossless_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)
    logging.disable(logging.CRITICAL)
    try:
        result = execution.execute_evaluation_request(
            project_case=bundle.project_case,
            request=bundle.request,
            scenario_authority_id=_AUTHORITY_ID,
        )
    finally:
        logging.disable(logging.NOTSET)
    assert type(result) is D3BExecutionSuccess

    projection = project_d3b_result(result)

    assert len(projection.sections) == 20
    assert len(projection.route_observations) == len(D3C_RESULT_FIELD_ROUTES) == 23
    project_irr = _observation(projection, "route:kpis.project_irr")
    assert project_irr.state is ResultObservationState.CARRIED
    assert (
        float.fromhex(project_irr.binary64_hex).hex()
        == result.full_result["kpis"]["project_irr"].hex()
    )
    assert bytes.fromhex(project_irr.binary64_bytes_hex) == struct.pack(
        ">d", result.full_result["kpis"]["project_irr"]
    )
    assert project_irr.value_text == str(
        Decimal.from_float(result.full_result["kpis"]["project_irr"])
    )
    assert projection.returned_warnings == result.warnings
    assert projection.fx_degraded is result.fx_degraded
    assert projection.limitations[0].code == "upstream_warning_channel_not_exhaustive"
    assert projection.engine_manifest.config_sha256 == result.evaluated_config_sha256
    assert projection.origin_invariants.gateway_call_count == 1
    assert projection.origin_invariants.duplicated_origins_exact is True
    assert projection.fx_integration.succeeded is True
    assert len(projection.numeric_projection_receipts) == len(
        result.numeric_projection_receipts
    )
    assert projection.unrecognized_keys == ()


def test_projection_has_no_gateway_or_finance_call(
    accepted_result: D3BExecutionSuccess, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def forbidden(**_: Any) -> dict[str, Any]:
        calls.append("gateway")
        raise AssertionError("projection attempted a gateway call")

    monkeypatch.setattr(evaluation_v14, "evaluate_with_overrides", forbidden)
    projection = project_d3b_result(accepted_result)
    assert projection.source_outcome == "success"
    assert calls == []

    source = _MODULE.read_text()
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(
        name.startswith(
            (
                "analytics.evaluation_v14",
                "finance",
                "app",
                "api",
            )
        )
        for name in imported
    )


def test_projection_accepts_exact_success_only() -> None:
    with pytest.raises(ResultProjectionError, match="invalid_input_type at /"):
        project_d3b_result(None)  # type: ignore[arg-type]


@pytest.mark.parametrize("zero", [0.0, -0.0])
def test_binary64_zero_is_explicitly_default_ambiguous(
    accepted_result: D3BExecutionSuccess, zero: float
) -> None:
    result = _replace_result(
        accepted_result, lambda payload: _set_project_irr(payload, zero)
    )
    observation = _observation(project_d3b_result(result), "route:kpis.project_irr")
    assert observation.state is ResultObservationState.AMBIGUOUS_DEFAULT
    assert observation.observed_binary64_hex == zero.hex()
    assert observation.observed_binary64_bytes_hex in {
        "0000000000000000",
        "8000000000000000",
    }
    assert observation.observed_scalar_text == (
        "-0" if zero.hex().startswith("-") else "0"
    )


def test_finite_binary64_subnormal_is_carried_without_loss(
    accepted_result: D3BExecutionSuccess,
) -> None:
    subnormal = float.fromhex("0x0.0000000000001p-1022")
    result = _replace_result(
        accepted_result,
        lambda payload: _set_project_irr(payload, subnormal),
    )
    observation = _observation(project_d3b_result(result), "route:kpis.project_irr")
    assert observation.state is ResultObservationState.CARRIED
    assert observation.binary64_hex == "0x0.0000000000001p-1022"
    assert observation.binary64_bytes_hex == "0000000000000001"
    assert float(observation.value_text).hex() == observation.binary64_hex


def test_required_kpi_mirror_mismatch_is_an_origin_refusal(
    accepted_result: D3BExecutionSuccess,
) -> None:
    result = _replace_result(
        accepted_result,
        lambda payload: _set_project_irr(payload, 0.25, 0.5),
    )
    with pytest.raises(ResultProjectionError, match="kpi_origin_mismatch"):
        project_d3b_result(result)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["kpis"].pop("project_irr"),
        lambda payload: payload["kpis"].__setitem__("project_irr", None),
        lambda payload: payload["kpis"].__setitem__("project_irr", 1),
    ],
)
def test_required_kpi_absent_none_and_wrong_type_refuse_origin(
    accepted_result: D3BExecutionSuccess,
    mutation: Callable[[dict[Any, Any]], None],
) -> None:
    with pytest.raises(ResultProjectionError, match="kpi_origin_mismatch"):
        project_d3b_result(_replace_result(accepted_result, mutation))


def test_total_cfads_requires_rows_but_never_recomputes(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["kpis"]["total_cfads_usd"] = 123.0
        payload["annual_rows"] = [{"year": 1.0}]

    observation = _observation(
        project_d3b_result(_replace_result(accepted_result, mutate)),
        "route:kpis.total_cfads_usd",
    )
    assert observation.state is ResultObservationState.NOT_REPRESENTABLE
    assert "cfads_usd" in observation.missing_item


def test_fx_candidates_stay_unavailable_without_project_context(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["debt_result"].update(
            {"fx_min": 300.0, "fx_max": 320.0, "fx_avg": 310.0}
        )

    projection = project_d3b_result(_replace_result(accepted_result, mutate))
    for route_id in (
        "route:debt_result.fx_min",
        "route:debt_result.fx_max",
        "route:debt_result.fx_avg",
    ):
        observation = _observation(projection, route_id)
        assert observation.state is ResultObservationState.NOT_REPRESENTABLE
        assert (
            "present but governed ProjectCase/request context"
            in observation.missing_item
        )


def test_unknown_string_integer_and_binary64_keys_are_surfaced_exactly(
    accepted_result: D3BExecutionSuccess,
) -> None:
    subnormal = float.fromhex("0x0.0000000000001p-1022")

    def mutate(payload: dict[Any, Any]) -> None:
        payload["novel"] = "value-must-not-be-copied"
        payload[7] = "integer-key-value"
        payload[subnormal] = "float-key-value"

    projection = project_d3b_result(_replace_result(accepted_result, mutate))
    records = {
        (item.container_path, item.key_type, item.key_identity): item
        for item in projection.unrecognized_keys
    }
    assert (
        ("full_result",),
        ResultUnknownKeyType.STRING,
        "novel",
    ) in records
    assert (("full_result",), ResultUnknownKeyType.INTEGER, "7") in records
    floating = records[
        (
            ("full_result",),
            ResultUnknownKeyType.BINARY64,
            "0x0.0000000000001p-1022",
        )
    ]
    assert floating.binary64_bytes_hex == "0000000000000001"
    assert "value-must-not-be-copied" not in projection.model_dump_json()


def test_boolean_unknown_key_identity_is_distinct_at_contract_boundary() -> None:
    record = UnrecognizedUpstreamKey(
        state=ResultObservationState.UNRECOGNIZED,
        observation_id="unrecognized:bool",
        container_path=("full_result",),
        key_type=ResultUnknownKeyType.BOOLEAN,
        key_identity="true",
        binary64_hex=None,
        binary64_bytes_hex=None,
        consequence=(
            "The present upstream key has no reviewed D3C-1a route and was not carried."
        ),
        remedy=(
            "Review and add an explicit versioned route or an explicit refusal before use."
        ),
    )
    assert record.key_type is ResultUnknownKeyType.BOOLEAN
    with pytest.raises(ValidationError, match="boolean unknown key"):
        record.model_copy(update={"key_identity": "1"}).__class__(
            **{**record.model_dump(), "key_identity": "1"}
        )


def test_unknown_key_order_is_insertion_order_independent(
    accepted_result: D3BExecutionSuccess,
) -> None:
    keys = ["zeta", 9, float.fromhex("0x0.0000000000001p-1022"), "alpha"]

    def with_order(order: list[object]) -> D3BExecutionSuccess:
        def mutate(payload: dict[Any, Any]) -> None:
            for key in order:
                payload[key] = "opaque"

        return _replace_result(accepted_result, mutate)

    left = project_d3b_result(with_order(keys)).unrecognized_keys
    right = project_d3b_result(with_order(list(reversed(keys)))).unrecognized_keys
    assert tuple(item.model_dump() for item in left) == tuple(
        item.model_dump() for item in right
    )


def test_unrepresentable_unknown_key_refuses_with_bounded_error(
    accepted_result: D3BExecutionSuccess,
) -> None:
    result = _replace_result(
        accepted_result,
        lambda payload: payload.__setitem__("bad\x00key", "opaque"),
    )
    with pytest.raises(ResultProjectionError, match="unrepresentable_unknown_key"):
        project_d3b_result(result)


def test_unrecognized_key_limit_fails_closed(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        for key in range(1_000, 1_513):
            payload[key] = None

    result = _replace_result(accepted_result, mutate)
    with pytest.raises(ResultProjectionError, match="unrecognized_key_limit_exceeded"):
        project_d3b_result(result)


def test_manifest_fields_are_exact_and_digest_bound(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    assert (
        projection.engine_manifest.config_sha256 == projection.evaluated_config_sha256
    )

    bad = _replace_result(
        accepted_result,
        lambda payload: payload["run_manifest"].__setitem__("config_sha256", "f" * 64),
    )
    with pytest.raises(ResultProjectionError, match="manifest_digest_mismatch"):
        project_d3b_result(bad)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("config_sha256", "A" * 64),
        ("git_sha", "not-a-commit"),
        ("generated_at", "2026-08-31T06:00:00+06:00"),
        ("seed", True),
    ],
)
def test_manifest_projection_rejects_malformed_exact_fields(
    accepted_result: D3BExecutionSuccess, field: str, value: object
) -> None:
    bad = _replace_result(
        accepted_result,
        lambda payload: payload["run_manifest"].__setitem__(field, value),
    )
    with pytest.raises(ResultProjectionError, match="manifest_field_invalid"):
        project_d3b_result(bad)


def test_exact_prevalidators_reject_string_subclasses(
    accepted_result: D3BExecutionSuccess,
) -> None:
    class SneakyString(str):
        pass

    payload = project_d3b_result(accepted_result).engine_manifest.model_dump()
    payload["config_sha256"] = SneakyString(payload["config_sha256"])
    with pytest.raises(ValidationError, match="exact lowercase SHA-256"):
        EngineManifestProjection.model_validate(payload)

    route_payload = D3C_RESULT_FIELD_ROUTES[0].model_dump()
    route_payload["route_id"] = SneakyString(route_payload["route_id"])
    with pytest.raises(ValidationError, match="exact stable identifier"):
        ResultFieldRoute.model_validate(route_payload)


def test_contracts_are_frozen_and_forbid_unknown_fields(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    with pytest.raises(ValidationError, match="frozen"):
        projection.fx_degraded = True  # type: ignore[misc]
    payload = projection.model_dump()
    payload["grade"] = "bankable"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        D3CResultProjection.model_validate(payload)


def test_schema_identity_and_json_roundtrip_are_closed(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    assert (
        D3CResultProjection.model_validate_json(projection.model_dump_json())
        == projection
    )
    schema = D3CResultProjection.model_json_schema()
    assert schema["additionalProperties"] is False
    for field, value in (
        ("schema_id", "future.schema"),
        ("contract_version", "2.0.0"),
        ("authority_status", "authoritative"),
    ):
        payload = projection.model_dump()
        payload[field] = value
        with pytest.raises(ValidationError):
            D3CResultProjection.model_validate(payload)


def test_warning_and_degradation_facts_are_preserved(
    accepted_result: D3BExecutionSuccess,
) -> None:
    degraded = _replace_result(
        accepted_result,
        lambda payload: payload.__setitem__("warnings", ["bounded warning"]),
    )
    object.__setattr__(degraded, "warnings", ("bounded warning",))
    object.__setattr__(degraded, "fx_degraded", True)
    object.__setattr__(degraded, "outcome", "degraded_success")
    projection = project_d3b_result(degraded)
    assert projection.source_outcome == "degraded_success"
    assert projection.returned_warnings == ("bounded warning",)
    assert projection.gateway_warnings == ("bounded warning",)
    assert projection.fx_integration.degraded is False
    assert projection.fx_degraded is True
    assert projection.limitations[0].code == "upstream_warning_channel_not_exhaustive"


def test_known_exclusions_disclose_presence(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    metrics = next(
        item
        for item in projection.excluded_fields
        if item.source_path == ("full_result", "metrics")
    )
    refused_fx = next(
        item
        for item in projection.excluded_fields
        if item.source_path == ("full_result", "kpis", "fx_match_ratio")
    )
    assert metrics.state is ResultObservationState.ARTIFACT_ONLY
    assert metrics.observed_present is True
    assert refused_fx.state is ResultObservationState.KNOWN_REFUSED
    assert refused_fx.observed_present is False


def test_all_route_paths_have_closed_container_catalogues() -> None:
    for route in D3C_RESULT_FIELD_ROUTES:
        for path in (route.source_path, *route.mirror_paths):
            assert path[:-1] in D3C_INSPECTED_LAYER_KEYS
            assert path[-1] in D3C_INSPECTED_LAYER_KEYS[path[:-1]]


def test_contract_package_keeps_engine_import_direction_outward() -> None:
    source = _CONTRACT_MODULE.read_text()
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "analytics.contracts_v14" not in imported
    assert "analytics.evaluation_v14" not in imported
    assert not any(name.startswith("finance") for name in imported)


def test_projection_shape_cannot_express_package_or_release_authority() -> None:
    schema_text = json.dumps(D3CResultProjection.model_json_schema(), sort_keys=True)
    for forbidden in (
        "FeasibilityReportPackage",
        "SectionRecord",
        "achieved_grade",
        "release_status",
        "lender_accepted",
        "board_approved",
    ):
        assert forbidden not in schema_text
    assert "run_manifest" not in D3CResultProjection.model_fields
    assert tuple(inspect.signature(project_d3b_result).parameters) == ("result",)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("engine_version", "", "bounded nonempty text"),
        ("engine_version", "bad\x00text", "forbidden control"),
        ("generated_at", "", "bounded UTC timestamp"),
        ("generated_at", "not-a-time", "ISO-8601"),
        ("generated_at", "2026-08-31T00:00:00", "explicit UTC offset"),
        ("generated_at", "2026-08-31T06:00:00+06:00", "timestamp must use UTC"),
    ],
)
def test_exact_text_and_timestamp_validators_fire(
    accepted_result: D3BExecutionSuccess, field: str, value: object, message: str
) -> None:
    payload = project_d3b_result(accepted_result).engine_manifest.model_dump()
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        EngineManifestProjection.model_validate(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload.__setitem__(
                "mirror_paths", (payload["source_path"],)
            ),
            "source cannot also be a mirror",
        ),
        (
            lambda payload: payload.__setitem__(
                "mirror_paths", (payload["mirror_paths"][0],) * 2
            ),
            "duplicate mirror paths",
        ),
        (
            lambda payload: payload.__setitem__(
                "section_ids", (payload["section_ids"][0],) * 2
            ),
            "duplicate section IDs",
        ),
        (
            lambda payload: payload.__setitem__(
                "unresolved_dependency_ids", ("dependency:x", "dependency:x")
            ),
            "duplicate dependencies",
        ),
        (
            lambda payload: payload.update(
                scalar_kind=ResultScalarKind.INTEGER,
                value_type=ResultValueType.DECIMAL_TEXT,
                meaningful_precision=1,
            ),
            "integer route requires",
        ),
        (
            lambda payload: payload.__setitem__(
                "value_type", ResultValueType.INTEGER_TEXT
            ),
            "binary64 route requires",
        ),
        (
            lambda payload: payload.update(
                carry_predicate=ResultCarryPredicate.PROJECT_CONTEXT_REQUIRED,
                unresolved_dependency_ids=(),
            ),
            "context-required route",
        ),
    ],
)
def test_static_route_coherence_guards(
    mutation: Callable[[dict[str, Any]], None], message: str
) -> None:
    payload = D3C_RESULT_FIELD_ROUTES[0].model_dump()
    mutation(payload)
    with pytest.raises(ValidationError, match=message):
        ResultFieldRoute.model_validate(payload)


def test_carried_observation_identity_guards(
    accepted_result: D3BExecutionSuccess,
) -> None:
    carried = _observation(
        project_d3b_result(accepted_result), "route:kpis.project_irr"
    )
    assert type(carried) is CarriedResultObservation
    for field, value, message in (
        ("route_id", "route:unknown", "unknown static route"),
        ("observation_id", "observation:wrong", "differs from its static route"),
        ("binary64_hex", None, "requires both exact identities"),
        ("value_text", "0.2", "does not preserve binary64 identity"),
        ("value_text", "not-decimal", "decimal projection is invalid"),
        ("binary64_bytes_hex", "0000000000000000", "does not preserve"),
    ):
        payload = carried.model_dump()
        payload[field] = value
        with pytest.raises(ValidationError, match=message):
            CarriedResultObservation.model_validate(payload)

    integer_route = next(
        route
        for route in D3C_RESULT_FIELD_ROUTES
        if route.scalar_kind is ResultScalarKind.INTEGER
    )
    integer = CarriedResultObservation(
        state=ResultObservationState.CARRIED,
        observation_id=f"observation:{integer_route.route_id}",
        route_id=integer_route.route_id,
        source_path=integer_route.source_path,
        section_ids=integer_route.section_ids,
        source_scalar_kind=ResultScalarKind.INTEGER,
        value_type=ResultValueType.INTEGER_TEXT,
        value_text="2",
        unit=integer_route.unit,
        meaningful_precision=0,
        precision_policy=integer_route.precision_policy,
        output_class=ResultObservationClass.ENGINE_RESULT_OBSERVATION,
        binary64_hex=None,
        binary64_bytes_hex=None,
    )
    for field, value in (
        ("value_text", "02"),
        ("binary64_hex", "0x1.0000000000000p+1"),
    ):
        payload = integer.model_dump()
        payload[field] = value
        with pytest.raises(ValidationError, match="integer observation requires"):
            CarriedResultObservation.model_validate(payload)


def test_unavailable_observation_identity_guards(
    accepted_result: D3BExecutionSuccess,
) -> None:
    unavailable = _observation(
        project_d3b_result(accepted_result), "route:kpis.equity_irr"
    )
    assert type(unavailable) is UnavailableResultObservation
    for mutation, message in (
        (
            lambda payload: payload.__setitem__("route_id", "route:unknown"),
            "unknown static route",
        ),
        (
            lambda payload: payload.__setitem__("observation_id", "observation:wrong"),
            "differs from its static route",
        ),
        (
            lambda payload: payload.__setitem__(
                "unresolved_dependency_ids", ("dependency:x", "dependency:x")
            ),
            "duplicate dependencies",
        ),
        (
            lambda payload: payload.update(
                state=ResultObservationState.AMBIGUOUS_DEFAULT,
                observed_scalar_text="1",
                observed_binary64_hex="0x1.0000000000000p+0",
                observed_binary64_bytes_hex="3ff0000000000000",
            ),
            "must preserve exact binary64 zero",
        ),
        (
            lambda payload: payload.update(
                observed_scalar_text="0",
                observed_binary64_hex="0x0.0p+0",
                observed_binary64_bytes_hex="0000000000000000",
            ),
            "only ambiguous-default",
        ),
    ):
        payload = unavailable.model_dump()
        mutation(payload)
        with pytest.raises(ValidationError, match=message):
            UnavailableResultObservation.model_validate(payload)


def test_unknown_key_contract_identity_guards() -> None:
    base = {
        "state": ResultObservationState.UNRECOGNIZED,
        "observation_id": "unrecognized:test",
        "container_path": ("full_result",),
        "key_type": ResultUnknownKeyType.BINARY64,
        "key_identity": "0x1.0000000000000p+0",
        "binary64_hex": "0x1.0000000000000p+0",
        "binary64_bytes_hex": "3ff0000000000000",
        "consequence": (
            "The present upstream key has no reviewed D3C-1a route and was not carried."
        ),
        "remedy": (
            "Review and add an explicit versioned route or an explicit refusal before use."
        ),
    }
    assert UnrecognizedUpstreamKey.model_validate(base).key_identity.startswith("0x1")
    for updates, message in (
        ({"binary64_bytes_hex": None}, "requires both exact identities"),
        (
            {
                "key_type": ResultUnknownKeyType.STRING,
                "key_identity": "key",
            },
            "non-binary64 unknown key forbids",
        ),
        (
            {
                "key_type": ResultUnknownKeyType.INTEGER,
                "key_identity": "01",
                "binary64_hex": None,
                "binary64_bytes_hex": None,
            },
            "canonical integer text",
        ),
        (
            {
                "key_type": ResultUnknownKeyType.BOOLEAN,
                "key_identity": "1",
                "binary64_hex": None,
                "binary64_bytes_hex": None,
            },
            "exact boolean identity",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            UnrecognizedUpstreamKey.model_validate({**base, **updates})


def test_section_and_exclusion_local_guards(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    section = projection.sections[0]
    for field, value, message in (
        ("section_id", "not_a_section", "unknown taxonomy section"),
        (
            "candidate_route_ids",
            ("route:x", "route:x"),
            "duplicate route IDs",
        ),
        (
            "unresolved_dependency_ids",
            ("dependency:x", "dependency:x"),
            "duplicate dependencies",
        ),
    ):
        payload = section.model_dump()
        payload[field] = value
        with pytest.raises(ValidationError, match=message):
            SectionResultProjection.model_validate(payload)

    excluded = projection.excluded_fields[0]
    payload = excluded.model_dump()
    payload["observation_id"] = "excluded:wrong"
    with pytest.raises(ValidationError, match="identity must derive"):
        ExcludedResultField.model_validate(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload.update(
                source_outcome="success", returned_warnings=("warning",)
            ),
            "success projection cannot hide",
        ),
        (
            lambda payload: payload.update(
                source_outcome="degraded_success",
                returned_warnings=(),
                fx_degraded=False,
            ),
            "degraded projection requires",
        ),
        (
            lambda payload: payload.__setitem__(
                "sections", tuple(reversed(payload["sections"]))
            ),
            "taxonomy SSOT order",
        ),
        (
            lambda payload: payload["sections"][0].__setitem__(
                "candidate_route_ids", ("route:wrong",)
            ),
            "candidate routes differ",
        ),
        (
            lambda payload: payload["sections"][0].__setitem__(
                "unresolved_dependency_ids", ("dependency:wrong",)
            ),
            "section dependencies differ",
        ),
        (
            lambda payload: payload.__setitem__(
                "route_observations", tuple(reversed(payload["route_observations"]))
            ),
            "ordered observation",
        ),
        (
            lambda payload: payload.__setitem__(
                "excluded_fields", payload["excluded_fields"][:-1]
            ),
            "excluded fields differ",
        ),
        (
            lambda payload: payload.__setitem__(
                "validation_modules", ("cashflow", "debt", "cashflow")
            ),
            "validation modules must be unique",
        ),
    ],
)
def test_projection_graph_guards(
    accepted_result: D3BExecutionSuccess,
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    payload = project_d3b_result(accepted_result).model_dump()
    mutation(payload)
    with pytest.raises(ValidationError, match=message):
        D3CResultProjection.model_validate(payload)


def test_returned_warning_python_ingress_is_exact_and_bounded(
    accepted_result: D3BExecutionSuccess,
) -> None:
    payload = project_d3b_result(accepted_result).model_dump()
    for warnings, message in (
        ([], "exact tuple"),
        ((1,), "exact strings"),
        (("x" * 1_000_001,), "text bound"),
    ):
        payload["returned_warnings"] = warnings
        with pytest.raises(ValidationError, match=message):
            D3CResultProjection.model_validate(payload)


def test_required_scenario_mirror_and_container_tampering_refuse_origin(
    accepted_result: D3BExecutionSuccess,
) -> None:
    missing_mirror = _replace_result(
        accepted_result,
        lambda payload: payload["scenario_result"].pop("project_irr"),
    )
    with pytest.raises(ResultProjectionError, match="scenario_origin_invalid"):
        project_d3b_result(missing_mirror)

    blocked = _replace_result(
        accepted_result,
        lambda payload: payload.__setitem__("scenario_result", "opaque"),
    )
    with pytest.raises(ResultProjectionError, match="origin_surface_invalid"):
        project_d3b_result(blocked)

    empty_scenario_name = _replace_result(
        accepted_result,
        lambda payload: payload["scenario_result"].__setitem__("scenario_name", ""),
    )
    with pytest.raises(ResultProjectionError, match="scenario_origin_invalid"):
        project_d3b_result(empty_scenario_name)


def test_equity_and_prudential_status_predicates_fail_closed(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def equity_not_computed(payload: dict[Any, Any]) -> None:
        payload["kpis"]["equity_irr"] = 0.4
        payload["scenario_result"]["equity_performance"] = {"equity_irr": 0.4}
        payload["equity_distribution"]["status"] = "disabled"

    equity = _observation(
        project_d3b_result(_replace_result(accepted_result, equity_not_computed)),
        "route:kpis.equity_irr",
    )
    assert equity.state is ResultObservationState.NOT_COMPUTED
    assert "status" in equity.missing_item

    def prudential_without_rate(payload: dict[Any, Any]) -> None:
        payload["kpis"]["project_npv_prudential"] = 10.0
        payload["scenario_result"]["wacc"] = {"prudential_npv": 10.0}

    prudential = _observation(
        project_d3b_result(_replace_result(accepted_result, prudential_without_rate)),
        "route:kpis.project_npv_prudential",
    )
    assert prudential.state is ResultObservationState.NOT_COMPUTED
    assert "prudential_rate_used" in prudential.missing_item


def test_series_debt_balloon_and_integer_predicates_fail_closed(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def no_series(payload: dict[Any, Any]) -> None:
        payload["kpis"]["avg_dscr"] = 1.2
        payload["scenario_result"]["dscr_series"] = []

    no_series_projection = project_d3b_result(
        _replace_result(accepted_result, no_series)
    )
    assert (
        _observation(no_series_projection, "route:kpis.min_dscr").state
        is ResultObservationState.NOT_COMPUTED
    )
    assert (
        _observation(no_series_projection, "route:kpis.avg_dscr").state
        is ResultObservationState.NOT_COMPUTED
    )

    def no_live_debt(payload: dict[Any, Any]) -> None:
        payload["debt_result"]["avg_debt_rate"] = 0.05
        payload["debt_result"]["debt_total"] = 0.0
        payload["kpis"]["max_debt_usd"] = 0.0
        payload["scenario_result"]["max_debt_usd"] = 0.0

    debt_rate = _observation(
        project_d3b_result(_replace_result(accepted_result, no_live_debt)),
        "route:debt_result.avg_debt_rate",
    )
    assert debt_rate.state is ResultObservationState.NOT_COMPUTED

    def no_balloon_basis(payload: dict[Any, Any]) -> None:
        payload["debt_result"]["balloon_pct"] = 0.1
        payload["debt_result"].pop("balloon_remaining", None)

    balloon = _observation(
        project_d3b_result(_replace_result(accepted_result, no_balloon_basis)),
        "route:debt_result.balloon_pct",
    )
    assert balloon.state is ResultObservationState.NOT_REPRESENTABLE

    wrong_integer = _replace_result(
        accepted_result,
        lambda payload: payload["debt_result"].__setitem__("construction_years", 2.0),
    )
    construction = _observation(
        project_d3b_result(wrong_integer),
        "route:debt_result.construction_years",
    )
    assert construction.state is ResultObservationState.NOT_REPRESENTABLE


def test_empty_annual_artifact_refuses_the_accepted_origin(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["kpis"]["total_cfads_usd"] = 123.0
        payload["annual_rows"] = []

    with pytest.raises(ResultProjectionError, match="origin_protocol_invalid"):
        project_d3b_result(_replace_result(accepted_result, mutate))


def test_prudential_predicate_and_annual_container_edges(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def complete_prudential(payload: dict[Any, Any]) -> None:
        payload["kpis"].update(
            project_npv_prudential=10.0,
            prudential_rate_used=0.12,
        )
        payload["scenario_result"]["wacc"] = {"prudential_npv": 10.0}

    prudential = _observation(
        project_d3b_result(_replace_result(accepted_result, complete_prudential)),
        "route:kpis.project_npv_prudential",
    )
    assert prudential.state is ResultObservationState.CARRIED

    def non_sequence_rows(payload: dict[Any, Any]) -> None:
        payload["kpis"]["total_cfads_usd"] = 10.0
        payload["annual_rows"] = None

    with pytest.raises(ResultProjectionError, match="origin_surface_invalid"):
        project_d3b_result(_replace_result(accepted_result, non_sequence_rows))

    def non_mapping_row(payload: dict[Any, Any]) -> None:
        payload["kpis"]["total_cfads_usd"] = 10.0
        payload["annual_rows"] = [1.0]

    with pytest.raises(ResultProjectionError, match="origin_protocol_invalid"):
        project_d3b_result(_replace_result(accepted_result, non_mapping_row))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("binary64_hex", "", "bounded binary64 hex"),
        ("binary64_hex", "not-hex", "binary64 hex text"),
        ("binary64_hex", "nan", "canonical finite"),
        ("binary64_hex", "0X1.0P+0", "canonical finite"),
        ("binary64_bytes_hex", "XYZ", "exact 8-byte"),
    ],
)
def test_binary64_identity_lexemes_are_strict(
    accepted_result: D3BExecutionSuccess,
    field: str,
    value: str,
    message: str,
) -> None:
    carried = _observation(
        project_d3b_result(accepted_result), "route:kpis.project_irr"
    )
    payload = carried.model_dump()
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        CarriedResultObservation.model_validate(payload)


def test_projection_global_identity_guards(
    accepted_result: D3BExecutionSuccess,
) -> None:
    payload = project_d3b_result(accepted_result).model_dump()
    assert len(payload["unrecognized_keys"]) >= 2

    duplicate_id = copy.deepcopy(payload)
    duplicate_id["unrecognized_keys"][0]["observation_id"] = duplicate_id[
        "route_observations"
    ][0]["observation_id"]
    with pytest.raises(ValidationError, match="globally unique"):
        D3CResultProjection.model_validate(duplicate_id)

    duplicate_location = copy.deepcopy(payload)
    duplicate_location["unrecognized_keys"][1].update(
        container_path=duplicate_location["unrecognized_keys"][0]["container_path"],
        key_type=duplicate_location["unrecognized_keys"][0]["key_type"],
        key_identity=duplicate_location["unrecognized_keys"][0]["key_identity"],
        binary64_hex=duplicate_location["unrecognized_keys"][0]["binary64_hex"],
        binary64_bytes_hex=duplicate_location["unrecognized_keys"][0][
            "binary64_bytes_hex"
        ],
    )
    with pytest.raises(ValidationError, match="locations must be unique"):
        D3CResultProjection.model_validate(duplicate_location)

    invalid_limitation = copy.deepcopy(payload)
    original = project_d3b_result(accepted_result).limitations[0]
    invalid_limitation["limitations"] = (
        ProjectionLimitation.model_construct(
            **{**original.model_dump(), "code": "caller_constructed_substitute"}
        ),
    )
    with pytest.raises(ValidationError, match="warning-channel limitation"):
        D3CResultProjection.model_validate(invalid_limitation)


def test_public_origin_invariant_guards_reject_postconstruction_tampering(
    accepted_result: D3BExecutionSuccess,
) -> None:
    not_frozen = copy.copy(accepted_result)
    object.__setattr__(not_frozen, "full_result", {})
    with pytest.raises(ResultProjectionError, match="result_not_frozen"):
        project_d3b_result(not_frozen)

    different_manifest = copy.copy(accepted_result)
    root = dict(accepted_result.full_result)
    root["run_manifest"] = MappingProxyType(dict(accepted_result.run_manifest))
    object.__setattr__(different_manifest, "full_result", MappingProxyType(root))
    with pytest.raises(ResultProjectionError, match="manifest_identity_mismatch"):
        project_d3b_result(different_manifest)

    mutable_manifest = copy.copy(accepted_result)
    manifest_dict = dict(accepted_result.run_manifest)
    root = dict(accepted_result.full_result)
    root["run_manifest"] = manifest_dict
    object.__setattr__(mutable_manifest, "full_result", MappingProxyType(root))
    object.__setattr__(mutable_manifest, "run_manifest", manifest_dict)
    with pytest.raises(ResultProjectionError, match="manifest_not_frozen"):
        project_d3b_result(mutable_manifest)


def test_missing_manifest_field_is_a_deterministic_refusal(
    accepted_result: D3BExecutionSuccess,
) -> None:
    missing = _replace_result(
        accepted_result,
        lambda payload: payload["run_manifest"].pop("engine_version"),
    )
    with pytest.raises(ResultProjectionError, match="manifest_field_missing"):
        project_d3b_result(missing)


def test_private_exact_helpers_cover_upstream_invariant_edges() -> None:
    with pytest.raises(ResultProjectionError, match="invalid_static_path"):
        projection_module._lookup(MappingProxyType({}), ("not_full_result",))
    assert projection_module._exact_scalar_equal(1, 1)
    assert not projection_module._exact_scalar_equal(1, 1.0)
    assert not projection_module._exact_scalar_equal("1", "1")
    assert projection_module._unknown_key_parts(True)[:2] == (
        ResultUnknownKeyType.BOOLEAN,
        "true",
    )
    with pytest.raises(ResultProjectionError, match="unsupported_unknown_key_type"):
        projection_module._unknown_key_parts(("unsupported",))


def test_hash_seed_does_not_change_first_projection_error() -> None:
    script = """
from analytics.feasibility_report_contract import EngineManifestProjection
try:
    EngineManifestProjection(
        config_sha256='A' * 64,
        engine_version='1',
        git_sha='bad',
        generated_at='bad',
        seed=None,
        validation_mode='strict',
        manifest_schema_version='1',
    )
except Exception as exc:
    print(str(exc).splitlines()[1])
"""
    outputs = []
    for seed in ("1", "17", "8675309"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_MODULE.parents[1],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert len(set(outputs)) == 1


def test_taxonomy_identity_leaf_is_checksum_guarded_and_import_safe() -> None:
    source = _MODULE.parents[1] / FEASIBILITY_TAXONOMY_SOURCE_PATH
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        FEASIBILITY_TAXONOMY_SOURCE_SHA256
    )
    assert load_feasibility_taxonomy().section_names == FEASIBILITY_SECTION_IDS


def test_engine_identity_leaf_is_checksum_guarded_and_source_exact() -> None:
    root = _MODULE.parents[1]
    version_source = root / ENGINE_VERSION_SOURCE_PATH
    manifest_source = root / MANIFEST_SCHEMA_SOURCE_PATH
    assert hashlib.sha256(version_source.read_bytes()).hexdigest() == (
        ENGINE_VERSION_SOURCE_SHA256
    )
    assert hashlib.sha256(manifest_source.read_bytes()).hexdigest() == (
        MANIFEST_SCHEMA_SOURCE_SHA256
    )
    assert version_source.read_text(encoding="utf-8").strip() == (
        ENGINE_VERSION_IDENTITY
    )
    from analytics.run_manifest import MANIFEST_SCHEMA_VERSION

    assert MANIFEST_SCHEMA_VERSION == MANIFEST_SCHEMA_VERSION_IDENTITY


def test_result_projection_import_and_call_do_not_read_or_write_taxonomy_files() -> (
    None
):
    script = r"""
import importlib
import logging
import tempfile
from pathlib import Path
from pydantic import BaseModel
from pytest import MonkeyPatch

class _PydanticPluginPrime(BaseModel):
    value: int

_PydanticPluginPrime(value=1)
_PydanticPluginPrime.model_json_schema()

original_read_text = Path.read_text
original_read_bytes = Path.read_bytes
original_write_text = Path.write_text
original_write_bytes = Path.write_bytes

def denied(*args, **kwargs):
    raise AssertionError('pure D3C-1a path attempted filesystem I/O')

Path.read_text = denied
Path.read_bytes = denied
Path.write_text = denied
Path.write_bytes = denied
module = importlib.import_module('analytics.feasibility_result_projection')

Path.read_text = original_read_text
Path.read_bytes = original_read_bytes
Path.write_text = original_write_text
Path.write_bytes = original_write_bytes

import analytics.feasibility_execution as execution
from tests.contracts.test_d3b_execution_contract import (
    _AUTHORITY_ID,
    _bundle,
    _gateway_result,
    _install_gateway,
)

with tempfile.TemporaryDirectory() as tmp:
    monkeypatch = MonkeyPatch()
    try:
        bundle = _bundle(Path(tmp), monkeypatch)
        _install_gateway(
            monkeypatch,
            lambda **kwargs: _gateway_result(kwargs['raw_config'], kwargs['overrides']),
        )
        result = execution.execute_evaluation_request(
            project_case=bundle.project_case,
            request=bundle.request,
            scenario_authority_id=_AUTHORITY_ID,
        )
        Path.read_text = denied
        Path.read_bytes = denied
        Path.write_text = denied
        Path.write_bytes = denied
        projection = module.project_d3b_result(result)
        print(projection.schema_id)
    finally:
        Path.read_text = original_read_text
        Path.read_bytes = original_read_bytes
        Path.write_text = original_write_text
        Path.write_bytes = original_write_bytes
        logging.disable(logging.NOTSET)
        monkeypatch.undo()
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_MODULE.parents[1],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "dutchbay.section_result_facade.v1"


def test_both_draft_202012_schema_modes_validate_canonical_json_and_are_fresh(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    payload = projection.model_dump(mode="json")
    originals: dict[str, dict[str, Any]] = {}
    for mode in ("validation", "serialization"):
        schema = D3CResultProjection.model_json_schema(mode=mode)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(payload)
        originals[mode] = copy.deepcopy(schema)
        schema["title"] = "caller-mutated"
        schema.setdefault("properties", {})["schema_id"] = {}
        assert D3CResultProjection.model_json_schema(mode=mode) == originals[mode]
    assert (
        D3CResultProjection.model_validate_json(projection.model_dump_json())
        == projection
    )


@pytest.mark.parametrize(
    "order",
    [
        (
            "analytics.feasibility_report_contract.result_facade",
            "analytics.feasibility_result_projection",
            "analytics.contracts_v14",
        ),
        (
            "analytics.contracts_v14",
            "analytics.feasibility_result_projection",
            "analytics.feasibility_report_contract.result_facade",
        ),
        (
            "analytics.feasibility_result_projection",
            "analytics.feasibility_report_contract",
            "analytics.contracts_v14",
        ),
    ],
)
def test_cold_import_orders_are_cycle_free(order: tuple[str, ...]) -> None:
    script = "\n".join(f"import {module}" for module in order)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_MODULE.parents[1],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_path_disposition_catalogue_is_total_for_every_inspected_container(
    accepted_result: D3BExecutionSuccess,
) -> None:
    assert D3C_RESULT_PATH_DISPOSITIONS
    assert all(
        type(item) is ResultPathDisposition
        for item in D3C_RESULT_PATH_DISPOSITIONS.values()
    )
    for container, keys in D3C_INSPECTED_LAYER_KEYS.items():
        assert keys
        for key in keys:
            assert (*container, key) in D3C_RESULT_PATH_DISPOSITIONS

    projection = project_d3b_result(accepted_result)
    unknown_locations = {
        (item.container_path, item.key_type, item.key_identity)
        for item in projection.unrecognized_keys
    }
    for (
        actual_container,
        container,
        expected_keys,
    ) in projection_module._inspected_containers(accepted_result.full_result):
        catalogue_container = actual_container
        if actual_container[-1].startswith("row:"):
            catalogue_container = (*actual_container[:-1], "*")
        for key in container:
            if type(key) is str and key in expected_keys:
                assert (*catalogue_container, key) in D3C_RESULT_PATH_DISPOSITIONS
                continue
            key_type, identity, _, _ = projection_module._unknown_key_parts(key)
            assert (actual_container, key_type, identity) in unknown_locations


def test_only_project_irr_and_project_npv_declare_ambiguous_zero_policy() -> None:
    ambiguous = tuple(
        route.route_id
        for route in D3C_RESULT_FIELD_ROUTES
        if route.zero_policy is ResultZeroPolicy.AMBIGUOUS_DEFAULT
    )
    assert ambiguous == ("route:kpis.project_irr", "route:kpis.project_npv")
    assert all(
        route.zero_policy is ResultZeroPolicy.ALLOW_EXACT
        for route in D3C_RESULT_FIELD_ROUTES
        if route.route_id not in ambiguous
    )


def test_route_authorized_zero_families_are_carried_with_exact_sign(
    accepted_result: D3BExecutionSuccess,
) -> None:
    negative_zero = -0.0

    def mutate(payload: dict[Any, Any]) -> None:
        payload["kpis"].update(
            equity_irr=0.0,
            total_cfads_usd=0.0,
            avg_dscr=0.0,
        )
        payload["scenario_result"]["equity_performance"] = {"equity_irr": 0.0}
        payload["equity_distribution"]["status"] = "computed"
        payload["annual_rows"] = [{"year": 1.0, "cfads_usd": 0.0}]
        payload["debt_result"].update(
            principal_by_tranche={"lkr": negative_zero, "usd": 100.0, "dfi": 0.0},
            total_idc=0.0,
            balloon_remaining=0.0,
            balloon_pct=0.0,
        )

    projection = project_d3b_result(_replace_result(accepted_result, mutate))
    for route_id in (
        "route:kpis.equity_irr",
        "route:kpis.total_cfads_usd",
        "route:kpis.avg_dscr",
        "route:debt_result.principal_by_tranche.lkr",
        "route:debt_result.principal_by_tranche.dfi",
        "route:debt_result.total_idc",
        "route:debt_result.balloon_remaining",
        "route:debt_result.balloon_pct",
    ):
        assert (
            _observation(projection, route_id).state is ResultObservationState.CARRIED
        )
    lkr = _observation(projection, "route:debt_result.principal_by_tranche.lkr")
    assert lkr.binary64_hex == "-0x0.0p+0"
    assert lkr.binary64_bytes_hex == "8000000000000000"


@pytest.mark.parametrize("tranche", ["lkr", "usd", "dfi"])
def test_each_zero_principal_tranche_is_carried_not_default_ambiguous(
    accepted_result: D3BExecutionSuccess,
    tranche: str,
) -> None:
    principals = {"lkr": 100.0, "usd": 100.0, "dfi": 100.0}
    principals[tranche] = 0.0

    def mutate(payload: dict[Any, Any]) -> None:
        payload["debt_result"]["principal_by_tranche"] = principals

    observation = _observation(
        project_d3b_result(_replace_result(accepted_result, mutate)),
        f"route:debt_result.principal_by_tranche.{tranche}",
    )
    assert observation.state is ResultObservationState.CARRIED
    assert observation.binary64_hex == "0x0.0p+0"


@pytest.mark.parametrize(
    ("principal", "remaining", "balloon_pct", "expected_state"),
    [
        ({"lkr": 100.0, "usd": 0.0, "dfi": 0.0}, 0.0, 0.0, "carried"),
        ({"lkr": 100.0, "usd": 0.0, "dfi": 0.0}, 10.0, 0.1, "carried"),
        ({"lkr": 100.0, "usd": 0.0, "dfi": 0.0}, 10.0, 0.2, "not_representable"),
        (
            {"lkr": 100.0, "usd": 0.0, "dfi": 0.0},
            -10.0,
            -0.1,
            "not_representable",
        ),
        ({"lkr": 0.0, "usd": 0.0, "dfi": 0.0}, 0.0, 0.0, "not_representable"),
        ({"lkr": -1.0, "usd": 101.0, "dfi": 0.0}, 10.0, 0.1, "not_representable"),
    ],
)
def test_balloon_pct_binds_the_idc_inclusive_principal_basis(
    accepted_result: D3BExecutionSuccess,
    principal: dict[str, float],
    remaining: float,
    balloon_pct: float,
    expected_state: str,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["debt_result"].update(
            principal_by_tranche=principal,
            balloon_remaining=remaining,
            balloon_pct=balloon_pct,
        )

    observation = _observation(
        project_d3b_result(_replace_result(accepted_result, mutate)),
        "route:debt_result.balloon_pct",
    )
    assert observation.state.value == expected_state


def test_balloon_pct_refuses_a_missing_idc_inclusive_basis(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["debt_result"].update(balloon_remaining=10.0, balloon_pct=0.1)
        payload["debt_result"].pop("principal_by_tranche", None)

    observation = _observation(
        project_d3b_result(_replace_result(accepted_result, mutate)),
        "route:debt_result.balloon_pct",
    )
    assert observation.state is ResultObservationState.NOT_REPRESENTABLE
    assert "IDC-inclusive" in observation.missing_item


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ResultObservationState.UPSTREAM_NONE),
        ("310", ResultObservationState.NOT_REPRESENTABLE),
        (310.0, ResultObservationState.NOT_REPRESENTABLE),
    ],
)
def test_fx_route_distinguishes_none_wrong_type_and_present_unbound_context(
    accepted_result: D3BExecutionSuccess,
    value: object,
    expected: ResultObservationState,
) -> None:
    result = _replace_result(
        accepted_result,
        lambda payload: payload["debt_result"].__setitem__("fx_min", value),
    )
    observation = _observation(project_d3b_result(result), "route:debt_result.fx_min")
    assert observation.state is expected


def test_structured_fx_origin_and_aggregate_warning_order_are_lossless(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["warnings"] = ["gateway-warning"]
        payload["fx_integration"] = {
            "attempted": True,
            "succeeded": False,
            "warning": "fx-warning",
            "degraded": True,
            "degraded_reasons": ["fallback-a", "fallback-b"],
        }

    result = _replace_result(accepted_result, mutate)
    warnings = ("gateway-warning", "fx-warning", "fallback-a", "fallback-b")
    object.__setattr__(result, "warnings", warnings)
    object.__setattr__(result, "fx_degraded", True)
    object.__setattr__(result, "outcome", "degraded_success")
    projection = project_d3b_result(result)
    assert projection.gateway_warnings == ("gateway-warning",)
    assert projection.returned_warnings == warnings
    assert projection.fx_integration == FxIntegrationProjection(
        attempted=True,
        succeeded=False,
        warning="fx-warning",
        degraded=True,
        degraded_reasons=("fallback-a", "fallback-b"),
    )


def test_empty_fx_warning_is_preserved_as_an_exact_warning_occurrence(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["fx_integration"].update(
            succeeded=False,
            warning="",
        )

    result = _replace_result(accepted_result, mutate)
    object.__setattr__(result, "warnings", ("",))
    object.__setattr__(result, "fx_degraded", True)
    object.__setattr__(result, "outcome", "degraded_success")
    projection = project_d3b_result(result)
    assert projection.fx_integration.warning == ""
    assert projection.returned_warnings == ("",)


def test_numeric_projection_receipts_are_ordered_unique_and_byte_exact(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    assert tuple(
        item.assertion_id for item in projection.numeric_projection_receipts
    ) == tuple(
        item.assertion_id for item in accepted_result.numeric_projection_receipts
    )
    for source, projected in zip(
        accepted_result.numeric_projection_receipts,
        projection.numeric_projection_receipts,
        strict=True,
    ):
        assert type(projected) is NumericProjectionReceiptProjection
        assert projected.project_decimal == source.project_decimal
        assert projected.projected_binary64_hex == source.projected_binary64_hex
        assert (
            projected.projected_binary64_bytes_hex
            == struct.pack(">d", float.fromhex(source.projected_binary64_hex)).hex()
        )
        assert all(
            type(item) is AuthoredNumericProjection
            for item in projected.authored_values
        )

    tampered_receipt = copy.copy(accepted_result.numeric_projection_receipts[0])
    object.__setattr__(
        tampered_receipt, "projected_binary64_hex", "0x1.0000000000000p+0"
    )
    tampered = copy.copy(accepted_result)
    object.__setattr__(
        tampered,
        "numeric_projection_receipts",
        (tampered_receipt, *accepted_result.numeric_projection_receipts[1:]),
    )
    with pytest.raises(ResultProjectionError, match="numeric_receipt_invalid"):
        project_d3b_result(tampered)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda payload: payload.__setitem__("status", "failed"),
            "origin_protocol_invalid",
        ),
        (
            lambda payload: payload.__setitem__("config_path", "/caller.yaml"),
            "origin_protocol_invalid",
        ),
        (
            lambda payload: payload.__setitem__("validation_mode", "permissive"),
            "origin_protocol_invalid",
        ),
        (
            lambda payload: payload["scenario_result"].__setitem__(
                "annual_rows", [{"year": 2.0}]
            ),
            "duplicated_origin_mismatch",
        ),
        (
            lambda payload: payload["scenario_result"]["kpis"].__setitem__(
                "project_irr", -0.0
            ),
            "duplicated_origin_mismatch",
        ),
        (
            lambda payload: payload["scenario_result"]["debt_result"].__setitem__(
                "debt_total", 101.0
            ),
            "duplicated_origin_mismatch",
        ),
        (
            lambda payload: payload["scenario_result"]["config"]["project"].__setitem__(
                "name", "caller-substitute"
            ),
            "evaluated_config_digest_mismatch",
        ),
    ],
)
def test_complete_origin_matrix_refuses_caller_substituted_snapshots(
    accepted_result: D3BExecutionSuccess,
    mutation: Callable[[dict[Any, Any]], None],
    code: str,
) -> None:
    result = _replace_result(
        accepted_result,
        mutation,
        reconcile_origins=False,
    )
    with pytest.raises(ResultProjectionError, match=code):
        project_d3b_result(result)


def test_gateway_module_warning_and_fx_postconstruction_tampering_is_refused(
    accepted_result: D3BExecutionSuccess,
) -> None:
    gateway = copy.copy(accepted_result)
    object.__setattr__(gateway, "gateway_call_count", 2)
    with pytest.raises(ResultProjectionError, match="gateway_call_count_invalid"):
        project_d3b_result(gateway)

    modules = copy.copy(accepted_result)
    object.__setattr__(modules, "validation_modules", ("rogue_module",))
    with pytest.raises(ResultProjectionError, match="validation_modules_invalid"):
        project_d3b_result(modules)

    warnings = copy.copy(accepted_result)
    object.__setattr__(warnings, "warnings", ("caller-warning",))
    object.__setattr__(warnings, "fx_degraded", True)
    object.__setattr__(warnings, "outcome", "degraded_success")
    with pytest.raises(ResultProjectionError, match="warning_origin_mismatch"):
        project_d3b_result(warnings)

    fx_result = _replace_result(
        accepted_result,
        lambda payload: payload["fx_integration"].__setitem__("degraded", True),
    )
    with pytest.raises(ResultProjectionError, match="fx_origin_invalid"):
        project_d3b_result(fx_result)


def test_origin_snapshot_cycle_is_refused_with_a_bounded_error(
    accepted_result: D3BExecutionSuccess,
) -> None:
    backing = dict(accepted_result.full_result)
    cycle_backing: dict[str, Any] = {}
    cycle = MappingProxyType(cycle_backing)
    cycle_backing["self"] = cycle
    backing["caller_cycle"] = cycle
    tampered = copy.copy(accepted_result)
    object.__setattr__(tampered, "full_result", MappingProxyType(backing))
    with pytest.raises(ResultProjectionError, match="origin_cycle"):
        project_d3b_result(tampered)


def test_hash_seed_stabilizes_real_projection_traversal_and_first_origin_error() -> (
    None
):
    script = r"""
import copy
import json
import tempfile
from pathlib import Path
from dataclasses import replace
from pytest import MonkeyPatch
import analytics.feasibility_execution as execution
from analytics.feasibility_result_projection import project_d3b_result
from tests.contracts.test_d3b_execution_contract import (
    _AUTHORITY_ID,
    _bundle,
    _gateway_result,
    _install_gateway,
)
from tests.contracts.test_d3c_result_projection_contract import _freeze

with tempfile.TemporaryDirectory() as tmp:
    monkeypatch = MonkeyPatch()
    try:
        bundle = _bundle(Path(tmp), monkeypatch)
        _install_gateway(
            monkeypatch,
            lambda **kwargs: _gateway_result(kwargs['raw_config'], kwargs['overrides']),
        )
        result = execution.execute_evaluation_request(
            project_case=bundle.project_case,
            request=bundle.request,
            scenario_authority_id=_AUTHORITY_ID,
        )
        payload = copy.deepcopy(result.model_dump()['full_result'])
        for key in {'zeta', 'alpha', 'middle'}:
            payload[key] = 'opaque'
        frozen = _freeze(payload)
        projected_result = replace(
            result,
            full_result=frozen,
            run_manifest=frozen['run_manifest'],
        )
        projection = project_d3b_result(projected_result)
        print(json.dumps([item.key_identity for item in projection.unrecognized_keys]))

        hostile = copy.copy(result)
        object.__setattr__(hostile, 'gateway_call_count', 2)
        object.__setattr__(hostile, 'validation_modules', ('rogue_module',))
        try:
            project_d3b_result(hostile)
        except Exception as exc:
            print(exc.code)
    finally:
        monkeypatch.undo()
"""
    outputs = []
    for seed in ("1", "17", "8675309"):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_MODULE.parents[1],
            env=dict(
                os.environ,
                PYTHONHASHSEED=seed,
                PYTHONDONTWRITEBYTECODE="1",
            ),
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert len(set(outputs)) == 1
    assert outputs[0].splitlines()[-1] == "gateway_call_count_invalid"


def test_origin_projection_contract_literals_cannot_be_forged(
    accepted_result: D3BExecutionSuccess,
) -> None:
    origin = project_d3b_result(accepted_result).origin_invariants
    assert type(origin) is OriginInvariantProjection
    payload = origin.model_dump()
    payload["duplicated_origins_exact"] = False
    with pytest.raises(ValidationError):
        OriginInvariantProjection.model_validate(payload)


def test_new_numeric_fx_and_route_models_fail_closed_on_hostile_lexemes(
    accepted_result: D3BExecutionSuccess,
) -> None:
    integer_route = next(
        route
        for route in D3C_RESULT_FIELD_ROUTES
        if route.scalar_kind is ResultScalarKind.INTEGER
    )
    route_payload = integer_route.model_dump()
    route_payload["zero_policy"] = ResultZeroPolicy.AMBIGUOUS_DEFAULT
    with pytest.raises(ValidationError, match="integer route cannot"):
        ResultFieldRoute.model_validate(route_payload)

    projection = project_d3b_result(accepted_result)
    authored = projection.numeric_projection_receipts[0].authored_values[0]
    authored_payload = authored.model_dump()
    hostile_authored = (
        ({"binary64_bytes_hex": "0000000000000000"}, "identities differ"),
        (
            {
                "json_type": "integer",
                "authored_value": "01",
            },
            "canonical JSON text",
        ),
        (
            {
                "json_type": "integer",
                "authored_value": "1" + "0" * 400,
                "binary64_hex": "0x1.0000000000000p+0",
                "binary64_bytes_hex": "3ff0000000000000",
            },
            "outside binary64",
        ),
        (
            {
                "json_type": "binary64",
                "authored_value": "not-a-number",
            },
            "binary64 text is invalid",
        ),
        (
            {
                "json_type": "binary64",
                "authored_value": "1.00",
                "binary64_hex": "0x1.0000000000000p+0",
                "binary64_bytes_hex": "3ff0000000000000",
            },
            "must be canonical",
        ),
        (
            {
                "json_type": "binary64",
                "authored_value": "1.0",
            },
            "text and binary64 identity differ",
        ),
    )
    for updates, message in hostile_authored:
        with pytest.raises(ValidationError, match=message):
            AuthoredNumericProjection.model_validate({**authored_payload, **updates})

    receipt = projection.numeric_projection_receipts[0]
    receipt_payload = receipt.model_dump()
    with pytest.raises(ValidationError, match="Decimal text is invalid"):
        NumericProjectionReceiptProjection.model_validate(
            {**receipt_payload, "project_decimal": "not-decimal"}
        )
    alternate = AuthoredNumericProjection(
        json_type="binary64",
        authored_value="1.0",
        binary64_hex="0x1.0000000000000p+0",
        binary64_bytes_hex="3ff0000000000000",
    )
    with pytest.raises(ValidationError, match="authored values disagree"):
        NumericProjectionReceiptProjection.model_validate(
            {**receipt_payload, "authored_values": (alternate,)}
        )
    rounded_integer = AuthoredNumericProjection(
        json_type="integer",
        authored_value="9007199254740992",
        binary64_hex="0x1.0000000000000p+53",
        binary64_bytes_hex="4340000000000000",
    )
    with pytest.raises(ValidationError, match="ProjectCase Decimal differ"):
        NumericProjectionReceiptProjection(
            assertion_id="assertion:rounding-hostile",
            project_decimal="9007199254740993",
            projected_binary64_hex="0x1.0000000000000p+53",
            projected_binary64_bytes_hex="4340000000000000",
            authored_values=(rounded_integer,),
        )

    for kwargs, message in (
        (
            dict(
                attempted=True,
                succeeded=False,
                warning="bad\x00warning",
                degraded=False,
                degraded_reasons=(),
            ),
            "forbidden control",
        ),
        (
            dict(
                attempted=True,
                succeeded=False,
                warning="x" * 1_000_001,
                degraded=False,
                degraded_reasons=(),
            ),
            "exact bounded string",
        ),
        (
            dict(
                attempted=True,
                succeeded=True,
                warning=None,
                degraded=False,
                degraded_reasons=[],
            ),
            "exact tuple",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            FxIntegrationProjection(**kwargs)


def test_projection_graph_rechecks_new_structured_origins(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    base = projection.model_dump()

    warning_mismatch = copy.deepcopy(base)
    warning_mismatch.update(
        source_outcome="degraded_success",
        returned_warnings=("caller",),
        fx_degraded=True,
    )
    with pytest.raises(ValidationError, match="returned warnings differ"):
        D3CResultProjection.model_validate(warning_mismatch)

    degradation_mismatch = copy.deepcopy(base)
    degradation_mismatch.update(
        source_outcome="degraded_success",
        fx_degraded=True,
    )
    with pytest.raises(ValidationError, match="FX degradation differs"):
        D3CResultProjection.model_validate(degradation_mismatch)

    manifest_mismatch = copy.deepcopy(base)
    manifest_mismatch["engine_manifest"]["config_sha256"] = "f" * 64
    with pytest.raises(ValidationError, match="manifest digest must match"):
        D3CResultProjection.model_validate(manifest_mismatch)

    duplicate_receipts = copy.deepcopy(base)
    duplicate_receipts["numeric_projection_receipts"] = (
        duplicate_receipts["numeric_projection_receipts"][0],
        duplicate_receipts["numeric_projection_receipts"][0],
    )
    with pytest.raises(ValidationError, match="receipt identities must be unique"):
        D3CResultProjection.model_validate(duplicate_receipts)


def test_manifest_identity_key_shape_and_seed_substitutions_are_refused(
    accepted_result: D3BExecutionSuccess,
) -> None:
    for mutator, code in (
        (
            lambda payload: payload["run_manifest"].__setitem__(
                "engine_version", "99.99.99"
            ),
            "manifest_identity_invalid",
        ),
        (
            lambda payload: payload["run_manifest"].__setitem__(
                "manifest_schema_version", "99.99"
            ),
            "manifest_identity_invalid",
        ),
        (
            lambda payload: payload["run_manifest"].__setitem__(7, "opaque"),
            "manifest_key_invalid",
        ),
    ):
        with pytest.raises(ResultProjectionError, match=code):
            project_d3b_result(_replace_result(accepted_result, mutator))

    seed_payload = copy.deepcopy(accepted_result.model_dump()["full_result"])
    seed_payload["run_manifest"]["seed"] = 1 << 4096
    frozen_seed_payload = _freeze(seed_payload)
    hostile_seed = copy.copy(accepted_result)
    object.__setattr__(hostile_seed, "full_result", frozen_seed_payload)
    object.__setattr__(
        hostile_seed, "run_manifest", frozen_seed_payload["run_manifest"]
    )
    with pytest.raises(ResultProjectionError, match="origin_scalar_invalid"):
        project_d3b_result(hostile_seed)

    manifest_payload = project_d3b_result(accepted_result).engine_manifest.model_dump()
    for updates, message in (
        ({"engine_version": "99.99.99"}, "current identity"),
        ({"manifest_schema_version": "99.99"}, "current identity"),
        ({"seed": 1 << 4096}, "at most 4096 bits"),
    ):
        with pytest.raises(ValidationError, match=message):
            EngineManifestProjection.model_validate({**manifest_payload, **updates})


def test_public_d3b_empty_dscr_series_projects_route_level_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    def gateway(**kwargs: Any) -> dict[str, Any]:
        payload = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        payload["scenario_result"]["dscr_series"] = []
        return payload

    _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert result.full_result["scenario_result"]["dscr_series"] == ()

    projection = project_d3b_result(result)
    assert (
        _observation(projection, "route:kpis.min_dscr").state
        is ResultObservationState.NOT_COMPUTED
    )
    assert (
        _observation(projection, "route:kpis.avg_dscr").state
        is ResultObservationState.NOT_COMPUTED
    )
    assert (
        _observation(projection, "route:kpis.project_irr").state
        is ResultObservationState.CARRIED
    )


def test_public_d3b_warning_bound_is_not_silently_narrowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path, monkeypatch)

    def gateway(**kwargs: Any) -> dict[str, Any]:
        payload = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        payload["warnings"] = [f"warning-{index}" for index in range(513)]
        return payload

    _install_gateway(monkeypatch, gateway)
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=bundle.request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    assert len(result.warnings) == 513

    projection = project_d3b_result(result)
    assert projection.gateway_warnings == result.warnings
    assert projection.returned_warnings == result.warnings


def test_d3b_numeric_receipt_bound_is_not_silently_narrowed(
    accepted_result: D3BExecutionSuccess,
) -> None:
    source = accepted_result.numeric_projection_receipts[0]
    receipts = tuple(
        replace(source, assertion_id=f"assertion:bulk-{index}") for index in range(513)
    )
    expanded = replace(accepted_result, numeric_projection_receipts=receipts)
    assert type(expanded) is D3BExecutionSuccess

    projection = project_d3b_result(expanded)
    assert tuple(
        item.assertion_id for item in projection.numeric_projection_receipts
    ) == tuple(item.assertion_id for item in receipts)


def test_project_case_revision_is_bounded_at_origin_python_json_and_dump(
    accepted_result: D3BExecutionSuccess,
) -> None:
    boundary_value = 1 << 4095
    boundary = replace(accepted_result, project_case_revision=boundary_value)
    projection = project_d3b_result(boundary)
    assert projection.project_case_revision == boundary_value
    assert D3CResultProjection.model_validate(projection.model_dump()) == projection
    assert (
        D3CResultProjection.model_validate_json(projection.model_dump_json())
        == projection
    )

    above_value = 1 << 4096
    above = replace(accepted_result, project_case_revision=above_value)
    with pytest.raises(ResultProjectionError, match="at most 4096 bits"):
        project_d3b_result(above)

    payload = projection.model_dump(mode="json")
    payload["project_case_revision"] = above_value
    with pytest.raises(ValidationError, match="at most 4096 bits"):
        D3CResultProjection.model_validate(payload)
    with pytest.raises(ValidationError, match="at most 4096 bits"):
        D3CResultProjection.model_validate_json(json.dumps(payload))


def test_origin_key_failure_is_insertion_order_independent_and_prebounded() -> None:
    huge = 1 << 4097
    nonfinite = float("nan")
    failures: list[tuple[str, str, str]] = []
    for keys in ((huge, nonfinite), (nonfinite, huge)):
        with pytest.raises(ResultProjectionError) as captured:
            projection_module._detach_frozen_occurrences(
                MappingProxyType({key: None for key in keys})
            )
        failures.append(
            (captured.value.code, captured.value.pointer, captured.value.detail)
        )
    assert (
        failures[0]
        == failures[1]
        == (
            "origin_key_invalid",
            "/full_result",
            "integer mapping key exceeds 4096 bits",
        )
    )

    unsupported_value = object()
    oversized = MappingProxyType(dict.fromkeys(range(100_001), unsupported_value))
    with pytest.raises(
        ResultProjectionError, match="mapping exceeds bounded"
    ) as captured:
        projection_module._detach_frozen_occurrences(oversized)
    assert captured.value.code == "origin_volume_exceeded"


def test_hostile_key_failure_is_hash_seed_and_insertion_order_stable() -> None:
    script = r"""
import json
from types import MappingProxyType
from analytics.feasibility_result_projection import _detach_frozen_occurrences

huge = 1 << 4097
nonfinite = float('nan')
for keys in ((huge, nonfinite), (nonfinite, huge)):
    try:
        _detach_frozen_occurrences(MappingProxyType({key: None for key in keys}))
    except Exception as exc:
        print(json.dumps([exc.code, exc.pointer, exc.detail]))
"""
    outputs: list[str] = []
    for seed in ("1", "17", "8675309"):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_MODULE.parents[1],
            env=dict(
                os.environ,
                PYTHONHASHSEED=seed,
                PYTHONDONTWRITEBYTECODE="1",
            ),
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert len(set(outputs)) == 1
    first, second = outputs[0].splitlines()
    assert first == second


def test_private_origin_helpers_cover_resource_exactness_and_config_edges() -> None:
    with pytest.raises(ResultProjectionError, match="origin_depth_exceeded"):
        projection_module._detach_frozen_occurrences(None, depth=129)
    with pytest.raises(ResultProjectionError, match="integer mapping key"):
        projection_module._detach_frozen_occurrences(MappingProxyType({2**4097: None}))
    with pytest.raises(ResultProjectionError, match="mapping key is not finite"):
        projection_module._detach_frozen_occurrences(
            MappingProxyType({float("nan"): None})
        )
    with pytest.raises(ResultProjectionError, match="unsupported exact type"):
        projection_module._detach_frozen_occurrences(MappingProxyType({True: None}))
    with pytest.raises(ResultProjectionError, match="container/entry volume"):
        projection_module._detach_frozen_occurrences(
            MappingProxyType({"a": None}), counts=[10_000, 0, 0]
        )
    with pytest.raises(ResultProjectionError, match="bounded text volume"):
        projection_module._detach_frozen_occurrences(
            MappingProxyType({"a": None}), counts=[0, 0, 1_000_000]
        )
    with pytest.raises(ResultProjectionError, match="container volume"):
        projection_module._detach_frozen_occurrences((), counts=[10_000, 0, 0])
    with pytest.raises(ResultProjectionError, match="scalar volume"):
        projection_module._detach_frozen_occurrences(None, counts=[0, 100_000, 0])
    with pytest.raises(ResultProjectionError, match="text volume"):
        projection_module._detach_frozen_occurrences("x", counts=[0, 0, 1_000_000])
    with pytest.raises(ResultProjectionError, match="unsupported or non-finite"):
        projection_module._detach_frozen_occurrences(object())

    assert not projection_module._exact_tree_equal((), [], depth=0)
    assert not projection_module._exact_tree_equal(None, None, depth=129)
    bool_key = MappingProxyType({True: None})
    assert not projection_module._exact_tree_equal(bool_key, bool_key)
    repeated: set[tuple[int, int]] = {(id(bool_key), id(bool_key))}
    assert projection_module._exact_tree_equal(bool_key, bool_key, compared=repeated)
    left_tuple = (1.0,)
    tuple_pairs = {(id(left_tuple), id(left_tuple))}
    assert projection_module._exact_tree_equal(
        left_tuple, left_tuple, compared=tuple_pairs
    )
    assert not projection_module._exact_tree_equal((1.0,), (2.0,))
    assert projection_module._exact_key_token(7) == ("integer", 7)

    with pytest.raises(ValueError, match="origin depth"):
        projection_module._thaw_json_config(None, depth=129)
    with pytest.raises(TypeError, match="exact strings"):
        projection_module._thaw_json_config(MappingProxyType({1: None}))
    assert projection_module._thaw_json_config((1, 2)) == [1, 2]
    with pytest.raises(TypeError, match="non-JSON-native"):
        projection_module._thaw_json_config(object())


def test_private_route_and_container_helpers_cover_preorigin_refusals(
    accepted_result: D3BExecutionSuccess,
) -> None:
    root = accepted_result.full_result
    project_route = next(
        route
        for route in D3C_RESULT_FIELD_ROUTES
        if route.route_id == "route:kpis.project_irr"
    )
    missing_root = MappingProxyType(
        {
            **dict(root),
            "scenario_result": MappingProxyType(
                {
                    key: value
                    for key, value in root["scenario_result"].items()
                    if key != "project_irr"
                }
            ),
        }
    )
    matches, reason = projection_module._mirrors_match(
        missing_root, project_route, root["kpis"]["project_irr"]
    )
    assert not matches and "missing exact mirror" in reason

    mismatch_root = MappingProxyType(
        {
            **dict(root),
            "scenario_result": MappingProxyType(
                {**dict(root["scenario_result"]), "project_irr": 0.5}
            ),
        }
    )
    accepted, state, _ = projection_module._predicate_result(
        mismatch_root, project_route, root["kpis"]["project_irr"]
    )
    assert not accepted and state is ResultObservationState.NOT_REPRESENTABLE

    cfads_route = next(
        route
        for route in D3C_RESULT_FIELD_ROUTES
        if route.route_id == "route:kpis.total_cfads_usd"
    )
    no_rows = MappingProxyType({**dict(root), "annual_rows": ()})
    assert projection_module._predicate_result(no_rows, cfads_route, 1.0)[1] is (
        ResultObservationState.NOT_COMPUTED
    )
    avg_route = next(
        route
        for route in D3C_RESULT_FIELD_ROUTES
        if route.route_id == "route:kpis.avg_dscr"
    )
    no_series_scenario = MappingProxyType(
        {**dict(root["scenario_result"]), "dscr_series": ()}
    )
    no_series = MappingProxyType({**dict(root), "scenario_result": no_series_scenario})
    assert projection_module._predicate_result(no_series, avg_route, 1.0)[1] is (
        ResultObservationState.NOT_COMPUTED
    )

    assert not projection_module._lookup(
        root, ("full_result", "scenario_result", "wacc", "prudential_npv")
    ).present
    assert not projection_module._lookup(
        MappingProxyType({"intermediate": 1}),
        ("full_result", "intermediate", "blocked"),
    ).present
    malformed_rows = MappingProxyType({**dict(root), "annual_rows": (1.0,)})
    containers = projection_module._inspected_containers(malformed_rows)
    assert all("row:0" not in path for path, _, _ in containers)
    without_rows = MappingProxyType(
        {key: value for key, value in root.items() if key != "annual_rows"}
    )
    assert projection_module._inspected_containers(without_rows)
    with pytest.raises(ResultProjectionError, match="manifest_not_frozen"):
        projection_module._manifest_projection({})


def test_origin_envelope_receipt_and_postorigin_contract_failures_are_deterministic(
    accepted_result: D3BExecutionSuccess,
) -> None:
    for field, value, code in (
        ("request_id", "", "origin_envelope_invalid"),
        ("project_case_revision", 0, "origin_envelope_invalid"),
        ("project_case_sha256", "bad", "origin_envelope_invalid"),
        ("evidence_cutoff", "2026-01-01", "origin_envelope_invalid"),
    ):
        tampered = copy.copy(accepted_result)
        object.__setattr__(tampered, field, value)
        with pytest.raises(ResultProjectionError, match=code):
            project_d3b_result(tampered)

    config_key = _replace_result(
        accepted_result,
        lambda payload: payload["scenario_result"]["config"].__setitem__(1, None),
        reconcile_origins=False,
    )
    with pytest.raises(ResultProjectionError, match="evaluated_config_invalid"):
        project_d3b_result(config_key)

    debt = _replace_result(
        accepted_result,
        lambda payload: payload["debt_result"].__setitem__("debt_total", 101.0),
    )
    with pytest.raises(ResultProjectionError, match="debt_origin_mismatch"):
        project_d3b_result(debt)

    gateway_warnings = _replace_result(
        accepted_result,
        lambda payload: payload.__setitem__("warnings", [1]),
    )
    with pytest.raises(ResultProjectionError, match="gateway_warnings_invalid"):
        project_d3b_result(gateway_warnings)

    degraded = copy.copy(accepted_result)
    object.__setattr__(degraded, "fx_degraded", True)
    with pytest.raises(ResultProjectionError, match="fx_degradation_mismatch"):
        project_d3b_result(degraded)

    outcome = copy.copy(accepted_result)
    object.__setattr__(outcome, "outcome", "degraded_success")
    with pytest.raises(ResultProjectionError, match="outcome_origin_mismatch"):
        project_d3b_result(outcome)

    invalid_receipts = copy.copy(accepted_result)
    object.__setattr__(invalid_receipts, "numeric_projection_receipts", [])
    with pytest.raises(ResultProjectionError, match="numeric_receipts_invalid"):
        project_d3b_result(invalid_receipts)

    wrong_receipt = copy.copy(accepted_result)
    object.__setattr__(wrong_receipt, "numeric_projection_receipts", (object(),))
    with pytest.raises(ResultProjectionError, match="numeric_receipt_type_invalid"):
        project_d3b_result(wrong_receipt)

    empty_authored_receipt = copy.copy(accepted_result.numeric_projection_receipts[0])
    object.__setattr__(empty_authored_receipt, "authored_values", ())
    empty_authored = copy.copy(accepted_result)
    object.__setattr__(
        empty_authored, "numeric_projection_receipts", (empty_authored_receipt,)
    )
    with pytest.raises(
        ResultProjectionError, match="numeric_receipt_authored_values_invalid"
    ):
        project_d3b_result(empty_authored)

    wrong_authored_receipt = copy.copy(accepted_result.numeric_projection_receipts[0])
    object.__setattr__(wrong_authored_receipt, "authored_values", (object(),))
    wrong_authored = copy.copy(accepted_result)
    object.__setattr__(
        wrong_authored, "numeric_projection_receipts", (wrong_authored_receipt,)
    )
    with pytest.raises(
        ResultProjectionError, match="numeric_authored_value_type_invalid"
    ):
        project_d3b_result(wrong_authored)

    malformed_item = copy.copy(
        accepted_result.numeric_projection_receipts[0].authored_values[0]
    )
    object.__setattr__(malformed_item, "binary64_hex", "not-hex")
    malformed_receipt = copy.copy(accepted_result.numeric_projection_receipts[0])
    object.__setattr__(malformed_receipt, "authored_values", (malformed_item,))
    malformed = copy.copy(accepted_result)
    object.__setattr__(malformed, "numeric_projection_receipts", (malformed_receipt,))
    with pytest.raises(ResultProjectionError, match="numeric_authored_value_invalid"):
        project_d3b_result(malformed)

    first = accepted_result.numeric_projection_receipts[0]
    duplicate = copy.copy(accepted_result.numeric_projection_receipts[1])
    object.__setattr__(duplicate, "assertion_id", first.assertion_id)
    duplicate_result = copy.copy(accepted_result)
    object.__setattr__(
        duplicate_result, "numeric_projection_receipts", (first, duplicate)
    )
    with pytest.raises(ResultProjectionError, match="numeric_receipt_duplicate"):
        project_d3b_result(duplicate_result)

    invalid_identifier = copy.copy(accepted_result)
    object.__setattr__(invalid_identifier, "request_id", "caller supplied spaces")
    with pytest.raises(ResultProjectionError, match="projection_contract_invalid"):
        project_d3b_result(invalid_identifier)
