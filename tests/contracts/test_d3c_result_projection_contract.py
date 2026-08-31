"""Hostile and independent-oracle controls for the D3C-1a result projection."""

from __future__ import annotations

import ast
import copy
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
from pydantic import ValidationError

import analytics.evaluation_v14 as evaluation_v14
import analytics.feasibility_execution as execution
import analytics.feasibility_result_projection as projection_module
from analytics.contracts_v14 import D3BExecutionSuccess
from analytics.feasibility_report_contract import (
    D3C_INSPECTED_LAYER_KEYS,
    D3C_RESULT_FIELD_ROUTES,
    CarriedResultObservation,
    D3CResultProjection,
    EngineManifestProjection,
    ExcludedResultField,
    ProjectionLimitation,
    ResultCarryPredicate,
    ResultFieldRoute,
    ResultObservationClass,
    ResultObservationState,
    ResultScalarKind,
    ResultUnknownKeyType,
    ResultValueType,
    SectionResultProjection,
    UnavailableResultObservation,
    UnrecognizedUpstreamKey,
)
from analytics.feasibility_result_projection import (
    ResultProjectionError,
    project_d3b_result,
)
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
    result: D3BExecutionSuccess, mutator: Callable[[dict[Any, Any]], None]
) -> D3BExecutionSuccess:
    payload = copy.deepcopy(result.model_dump()["full_result"])
    mutator(payload)
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
    assert projection.unrecognized_keys


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


def test_exact_mirror_mismatch_is_not_representable(
    accepted_result: D3BExecutionSuccess,
) -> None:
    result = _replace_result(
        accepted_result,
        lambda payload: _set_project_irr(payload, 0.25, 0.5),
    )
    observation = _observation(project_d3b_result(result), "route:kpis.project_irr")
    assert observation.state is ResultObservationState.NOT_REPRESENTABLE
    assert "mirror mismatch" in observation.missing_item


@pytest.mark.parametrize(
    ("mutation", "expected_state"),
    [
        (
            lambda payload: payload["kpis"].pop("project_irr"),
            ResultObservationState.NOT_COMPUTED,
        ),
        (
            lambda payload: payload["kpis"].__setitem__("project_irr", None),
            ResultObservationState.UPSTREAM_NONE,
        ),
        (
            lambda payload: payload["kpis"].__setitem__("project_irr", 1),
            ResultObservationState.NOT_REPRESENTABLE,
        ),
    ],
)
def test_absent_none_and_wrong_scalar_type_remain_distinct(
    accepted_result: D3BExecutionSuccess,
    mutation: Callable[[dict[Any, Any]], None],
    expected_state: ResultObservationState,
) -> None:
    observation = _observation(
        project_d3b_result(_replace_result(accepted_result, mutation)),
        "route:kpis.project_irr",
    )
    assert observation.state is expected_state
    assert not hasattr(observation, "value_text")


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
        assert observation.state is ResultObservationState.NOT_COMPUTED
        assert "ProjectCase/request context" in observation.missing_item


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
    with pytest.raises(ResultProjectionError, match="projection_contract_invalid"):
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
    degraded = replace(
        accepted_result,
        warnings=("bounded warning",),
        fx_degraded=True,
        outcome="degraded_success",
    )
    projection = project_d3b_result(degraded)
    assert projection.source_outcome == "degraded_success"
    assert projection.returned_warnings == ("bounded warning",)
    assert projection.fx_degraded is True
    assert projection.limitations[0].code == "upstream_warning_channel_not_exhaustive"


def test_known_exclusions_disclose_presence(
    accepted_result: D3BExecutionSuccess,
) -> None:
    projection = project_d3b_result(accepted_result)
    annual_rows = next(
        item
        for item in projection.excluded_fields
        if item.source_path == ("full_result", "annual_rows")
    )
    refused_fx = next(
        item
        for item in projection.excluded_fields
        if item.source_path == ("full_result", "kpis", "fx_match_ratio")
    )
    assert annual_rows.state is ResultObservationState.ARTIFACT_ONLY
    assert annual_rows.observed_present is True
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
        (("x" * 65_537,), "text bound"),
    ):
        payload["returned_warnings"] = warnings
        with pytest.raises(ValidationError, match=message):
            D3CResultProjection.model_validate(payload)


def test_missing_mirror_and_blocked_intermediate_are_explicit(
    accepted_result: D3BExecutionSuccess,
) -> None:
    missing_mirror = _replace_result(
        accepted_result,
        lambda payload: payload["scenario_result"].pop("project_irr"),
    )
    observation = _observation(
        project_d3b_result(missing_mirror), "route:kpis.project_irr"
    )
    assert observation.state is ResultObservationState.NOT_REPRESENTABLE
    assert "missing exact mirror" in observation.missing_item

    blocked = _replace_result(
        accepted_result,
        lambda payload: payload.__setitem__("scenario_result", "opaque"),
    )
    observation = _observation(project_d3b_result(blocked), "route:kpis.project_irr")
    assert observation.state is ResultObservationState.NOT_REPRESENTABLE


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

    avg_dscr = _observation(
        project_d3b_result(_replace_result(accepted_result, no_series)),
        "route:kpis.avg_dscr",
    )
    assert avg_dscr.state is ResultObservationState.NOT_COMPUTED

    def no_live_debt(payload: dict[Any, Any]) -> None:
        payload["debt_result"]["avg_debt_rate"] = 0.05
        payload["debt_result"]["debt_total"] = 0.0

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
    assert balloon.state is ResultObservationState.NOT_COMPUTED

    wrong_integer = _replace_result(
        accepted_result,
        lambda payload: payload["debt_result"].__setitem__("construction_years", 2.0),
    )
    construction = _observation(
        project_d3b_result(wrong_integer),
        "route:debt_result.construction_years",
    )
    assert construction.state is ResultObservationState.NOT_REPRESENTABLE


def test_empty_annual_artifact_is_not_computed(
    accepted_result: D3BExecutionSuccess,
) -> None:
    def mutate(payload: dict[Any, Any]) -> None:
        payload["kpis"]["total_cfads_usd"] = 123.0
        payload["annual_rows"] = []

    observation = _observation(
        project_d3b_result(_replace_result(accepted_result, mutate)),
        "route:kpis.total_cfads_usd",
    )
    assert observation.state is ResultObservationState.NOT_COMPUTED
    assert "absent or empty" in observation.missing_item


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

    assert (
        _observation(
            project_d3b_result(_replace_result(accepted_result, non_sequence_rows)),
            "route:kpis.total_cfads_usd",
        ).state
        is ResultObservationState.NOT_COMPUTED
    )

    def non_mapping_row(payload: dict[Any, Any]) -> None:
        payload["kpis"]["total_cfads_usd"] = 10.0
        payload["annual_rows"] = [1.0]

    assert (
        _observation(
            project_d3b_result(_replace_result(accepted_result, non_mapping_row)),
            "route:kpis.total_cfads_usd",
        ).state
        is ResultObservationState.NOT_REPRESENTABLE
    )


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
