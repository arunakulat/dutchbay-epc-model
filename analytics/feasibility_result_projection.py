"""Translate one accepted D3B success into a non-authoritative D3C-1a view.

This module is deliberately pure.  It accepts exactly one already executed
``D3BExecutionSuccess`` and never imports or calls the evaluator, finance,
application, renderer, persistence, network, or filesystem layers.  It mirrors
accepted scalars byte-exactly, emits explicit absences, and leaves project-case
and assembly-authority binding to later dolphins.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Final, Literal, Mapping, TypeAlias, cast

from analytics.contracts_v14 import D3BExecutionSuccess
from analytics.feasibility_report_contract.result_facade import (
    D3C_ARTIFACT_ONLY_PATHS,
    D3C_INSPECTED_LAYER_KEYS,
    D3C_KNOWN_REFUSED_PATHS,
    D3C_RESULT_FIELD_ROUTES,
    RESULT_FACADE_AUTHORITY_STATUS,
    RESULT_FACADE_CONTRACT_VERSION,
    RESULT_FACADE_SCHEMA_ID,
    RESULT_FACADE_SOURCE_CONTRACT,
    RESULT_FACADE_WARNING_LIMITATION_CODE,
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
    UnavailableResultObservation,
    UnrecognizedUpstreamKey,
    result_section_projections,
)

_MAX_UNRECOGNIZED_KEYS: Final = 512
_MISSING = object()
_UnavailableState: TypeAlias = Literal[
    ResultObservationState.AMBIGUOUS_DEFAULT,
    ResultObservationState.UPSTREAM_NONE,
    ResultObservationState.NOT_COMPUTED,
    ResultObservationState.NOT_REPRESENTABLE,
]
_ExcludedState: TypeAlias = Literal[
    ResultObservationState.ARTIFACT_ONLY,
    ResultObservationState.KNOWN_REFUSED,
]


class ResultProjectionError(ValueError):
    """Deterministic fail-closed D3C-1a projection error."""

    def __init__(self, code: str, pointer: str, detail: str) -> None:
        self.code = code
        self.pointer = pointer
        self.detail = detail
        super().__init__(f"{code} at {pointer}: {detail}")


@dataclass(frozen=True, slots=True)
class _Lookup:
    present: bool
    value: Any = None
    blocked_at: tuple[str, ...] | None = None


def _pointer(path: tuple[str, ...]) -> str:
    """Return a deterministic RFC 6901 pointer for a reviewed string path."""

    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)


def _lookup(full_result: Mapping[Any, Any], path: tuple[str, ...]) -> _Lookup:
    """Look up a static full-result path without coercion or arbitrary traversal."""

    if not path or path[0] != "full_result":
        raise ResultProjectionError(
            "invalid_static_path",
            "/",
            "D3C-1a paths must begin at full_result",
        )
    current: Any = full_result
    traversed: tuple[str, ...] = ("full_result",)
    for part in path[1:]:
        if type(current) is not MappingProxyType:
            return _Lookup(False, blocked_at=traversed)
        if part not in current:
            return _Lookup(False, blocked_at=(*traversed, part))
        current = current[part]
        traversed = (*traversed, part)
    return _Lookup(True, current)


def _exact_float_identity(value: float) -> tuple[str, str]:
    return value.hex(), struct.pack(">d", value).hex()


def _exact_scalar_equal(left: object, right: object) -> bool:
    """Compare accepted scalar mirrors without numeric coercion or signed-zero loss."""

    if type(left) is not type(right):
        return False
    if type(left) is float:
        return struct.pack(">d", left) == struct.pack(">d", right)
    if type(left) is int:
        return left == right
    return False


def _finite_float(value: object) -> bool:
    return type(value) is float and math.isfinite(value)


def _finite_float_tuple(value: object) -> bool:
    return (
        type(value) is tuple
        and bool(value)
        and all(_finite_float(item) for item in value)
    )


def _mirrors_match(
    full_result: Mapping[Any, Any], route: ResultFieldRoute, source: object
) -> tuple[bool, str]:
    for mirror_path in route.mirror_paths:
        mirror = _lookup(full_result, mirror_path)
        if not mirror.present:
            return False, f"missing exact mirror {_pointer(mirror_path)}"
        if not _exact_scalar_equal(source, mirror.value):
            return False, f"exact mirror mismatch at {_pointer(mirror_path)}"
    return True, ""


def _predicate_result(
    full_result: Mapping[Any, Any], route: ResultFieldRoute, source: object
) -> tuple[bool, ResultObservationState, str]:
    """Apply one closed carry predicate without recomputing a financial value."""

    predicate = route.carry_predicate
    mirrors_match, mirror_reason = _mirrors_match(full_result, route, source)
    if not mirrors_match:
        return False, ResultObservationState.NOT_REPRESENTABLE, mirror_reason

    if predicate is ResultCarryPredicate.FINITE_NONZERO_EXACT_MIRRORS:
        return True, ResultObservationState.CARRIED, ""

    if predicate is ResultCarryPredicate.EQUITY_IRR_COMPUTED:
        status = _lookup(full_result, ("full_result", "equity_distribution", "status"))
        if (
            not status.present
            or type(status.value) is not str
            or status.value != "computed"
        ):
            return (
                False,
                ResultObservationState.NOT_COMPUTED,
                "equity_distribution.status is not exact 'computed'",
            )
        return True, ResultObservationState.CARRIED, ""

    if predicate is ResultCarryPredicate.PRUDENTIAL_NPV_COMPUTED:
        rate = _lookup(full_result, ("full_result", "kpis", "prudential_rate_used"))
        if not rate.present or not _finite_float(rate.value):
            return (
                False,
                ResultObservationState.NOT_COMPUTED,
                "finite prudential_rate_used is absent",
            )
        return True, ResultObservationState.CARRIED, ""

    if predicate is ResultCarryPredicate.ANNUAL_CFADS_COMPLETE:
        rows = _lookup(full_result, ("full_result", "annual_rows"))
        if not rows.present or type(rows.value) is not tuple or not rows.value:
            return (
                False,
                ResultObservationState.NOT_COMPUTED,
                "the annual-row artifact is absent or empty",
            )
        for index, row in enumerate(rows.value):
            if type(row) is not MappingProxyType or not _finite_float(
                row.get("cfads_usd", _MISSING)
            ):
                return (
                    False,
                    ResultObservationState.NOT_REPRESENTABLE,
                    f"annual row {index} lacks exact finite cfads_usd",
                )
        return True, ResultObservationState.CARRIED, ""

    if predicate in {
        ResultCarryPredicate.DSCR_SERIES_EXACT_MIRRORS,
        ResultCarryPredicate.DSCR_SERIES_PRESENT,
    }:
        series = _lookup(full_result, ("full_result", "scenario_result", "dscr_series"))
        if not series.present or not _finite_float_tuple(series.value):
            return (
                False,
                ResultObservationState.NOT_COMPUTED,
                "the exact nonempty finite DSCR series is absent",
            )
        return True, ResultObservationState.CARRIED, ""

    if predicate in {
        ResultCarryPredicate.POSITIVE_DEBT_EXACT_MIRROR,
        ResultCarryPredicate.POSITIVE_DEBT_FINITE,
    }:
        debt = _lookup(full_result, ("full_result", "debt_result", "debt_total"))
        if not debt.present or not _finite_float(debt.value) or debt.value <= 0.0:
            return (
                False,
                ResultObservationState.NOT_COMPUTED,
                "positive exact live debt is absent",
            )
        return True, ResultObservationState.CARRIED, ""

    if predicate is ResultCarryPredicate.MAX_DEBT_EXACT_MIRRORS:
        return True, ResultObservationState.CARRIED, ""

    if predicate is ResultCarryPredicate.FINITE:
        return True, ResultObservationState.CARRIED, ""

    if predicate is ResultCarryPredicate.BALLOON_BASIS_PRESENT:
        remaining = _lookup(
            full_result, ("full_result", "debt_result", "balloon_remaining")
        )
        debt = _lookup(full_result, ("full_result", "debt_result", "debt_total"))
        if (
            not remaining.present
            or not _finite_float(remaining.value)
            or not debt.present
            or not _finite_float(debt.value)
        ):
            return (
                False,
                ResultObservationState.NOT_COMPUTED,
                "the exact reciprocal balloon basis is absent",
            )
        return True, ResultObservationState.CARRIED, ""

    if predicate is ResultCarryPredicate.EXACT_INTEGER:
        return True, ResultObservationState.CARRIED, ""

    raise ResultProjectionError(  # pragma: no cover - closed-enum exhaustiveness
        "unknown_carry_predicate",
        _pointer(route.source_path),
        f"unimplemented closed predicate {predicate.value}",
    )


def _unavailable(
    route: ResultFieldRoute,
    state: ResultObservationState,
    missing_item: str,
    *,
    observed: float | None = None,
) -> UnavailableResultObservation:
    binary64_hex: str | None = None
    binary64_bytes: str | None = None
    scalar_text: str | None = None
    if observed is not None:
        scalar_text = str(int(observed)) if observed == 0.0 else str(observed)
        if math.copysign(1.0, observed) < 0.0:
            scalar_text = "-0"
        binary64_hex, binary64_bytes = _exact_float_identity(observed)
    return UnavailableResultObservation(
        state=cast(_UnavailableState, state),
        observation_id=f"observation:{route.route_id}",
        route_id=route.route_id,
        source_path=route.source_path,
        section_ids=route.section_ids,
        missing_item=missing_item,
        consequence="The field is not carried by the non-authoritative result projection.",
        remedy=(
            "Supply and verify the named exact predicate inputs in a later governed "
            "translation before using this field."
        ),
        unresolved_dependency_ids=route.unresolved_dependency_ids,
        observed_scalar_text=scalar_text,
        observed_binary64_hex=binary64_hex,
        observed_binary64_bytes_hex=binary64_bytes,
    )


def _route_observation(
    full_result: Mapping[Any, Any], route: ResultFieldRoute
) -> CarriedResultObservation | UnavailableResultObservation:
    if route.carry_predicate is ResultCarryPredicate.PROJECT_CONTEXT_REQUIRED:
        return _unavailable(
            route,
            ResultObservationState.NOT_COMPUTED,
            "governed ProjectCase/request context is outside D3C-1a",
        )

    source = _lookup(full_result, route.source_path)
    if not source.present:
        return _unavailable(
            route,
            ResultObservationState.NOT_COMPUTED,
            f"exact source {_pointer(route.source_path)} is absent",
        )
    if source.value is None:
        return _unavailable(
            route,
            ResultObservationState.UPSTREAM_NONE,
            f"exact source {_pointer(route.source_path)} is upstream None",
        )

    if route.scalar_kind is ResultScalarKind.BINARY64:
        if not _finite_float(source.value):
            return _unavailable(
                route,
                ResultObservationState.NOT_REPRESENTABLE,
                "the source is not an exact finite binary64 scalar",
            )
        if source.value == 0.0:
            return _unavailable(
                route,
                ResultObservationState.AMBIGUOUS_DEFAULT,
                "exact binary64 zero lacks a computation-status receipt",
                observed=source.value,
            )
    elif type(source.value) is not int:
        return _unavailable(
            route,
            ResultObservationState.NOT_REPRESENTABLE,
            "the source is not an exact integer scalar",
        )

    accepted, unavailable_state, reason = _predicate_result(
        full_result, route, source.value
    )
    if not accepted:
        return _unavailable(route, unavailable_state, reason)

    if route.scalar_kind is ResultScalarKind.BINARY64:
        binary64_hex, binary64_bytes = _exact_float_identity(source.value)
        value_text = str(Decimal.from_float(source.value))
    else:
        binary64_hex = None
        binary64_bytes = None
        value_text = str(source.value)
    return CarriedResultObservation(
        state=ResultObservationState.CARRIED,
        observation_id=f"observation:{route.route_id}",
        route_id=route.route_id,
        source_path=route.source_path,
        section_ids=route.section_ids,
        source_scalar_kind=route.scalar_kind,
        value_type=route.value_type,
        value_text=value_text,
        unit=route.unit,
        meaningful_precision=route.meaningful_precision,
        precision_policy=route.precision_policy,
        output_class=ResultObservationClass.ENGINE_RESULT_OBSERVATION,
        binary64_hex=binary64_hex,
        binary64_bytes_hex=binary64_bytes,
    )


def _unknown_key_parts(
    key: object,
) -> tuple[ResultUnknownKeyType, str, str | None, str | None]:
    if type(key) is str:
        if (
            not key
            or len(key) > 4_096
            or any(
                ord(character) < 32 and character not in "\t\n\r" for character in key
            )
        ):
            raise ResultProjectionError(
                "unrepresentable_unknown_key",
                "/full_result",
                "an unknown string key cannot be represented as bounded exact text",
            )
        return ResultUnknownKeyType.STRING, key, None, None
    if type(key) is bool:
        return ResultUnknownKeyType.BOOLEAN, "true" if key else "false", None, None
    if type(key) is int:
        return ResultUnknownKeyType.INTEGER, str(key), None, None
    if type(key) is float and math.isfinite(key):
        binary64_hex, binary64_bytes = _exact_float_identity(key)
        return (
            ResultUnknownKeyType.BINARY64,
            binary64_hex,
            binary64_hex,
            binary64_bytes,
        )
    raise ResultProjectionError(
        "unsupported_unknown_key_type",
        "/full_result",
        "the accepted D3B mapping contains an unsupported key type",
    )


def _unknown_sort_key(key: object) -> tuple[str, str, str]:
    key_type, identity, binary64_hex, binary64_bytes = _unknown_key_parts(key)
    return key_type.value, identity, binary64_bytes or binary64_hex or ""


def _inspected_containers(
    full_result: Mapping[Any, Any],
) -> tuple[tuple[tuple[str, ...], Mapping[Any, Any], frozenset[str]], ...]:
    containers: list[tuple[tuple[str, ...], Mapping[Any, Any], frozenset[str]]] = []
    for path, expected_keys in D3C_INSPECTED_LAYER_KEYS.items():
        if path[-1] == "*":
            rows = _lookup(full_result, path[:-1])
            if rows.present and type(rows.value) is tuple:
                for index, row in enumerate(rows.value):
                    if type(row) is MappingProxyType:
                        containers.append(
                            ((*path[:-1], f"row:{index}"), row, expected_keys)
                        )
            continue
        found = _lookup(full_result, path)
        if found.present and type(found.value) is MappingProxyType:
            containers.append((path, found.value, expected_keys))
    return tuple(containers)


def _unrecognized_keys(
    full_result: Mapping[Any, Any],
) -> tuple[UnrecognizedUpstreamKey, ...]:
    records: list[UnrecognizedUpstreamKey] = []
    for container_path, container, expected_keys in _inspected_containers(full_result):
        unknown = [
            key for key in container if type(key) is not str or key not in expected_keys
        ]
        for key in sorted(unknown, key=_unknown_sort_key):
            if len(records) >= _MAX_UNRECOGNIZED_KEYS:
                raise ResultProjectionError(
                    "unrecognized_key_limit_exceeded",
                    _pointer(container_path),
                    "more than 512 present undeclared keys were observed",
                )
            key_type, identity, binary64_hex, binary64_bytes = _unknown_key_parts(key)
            records.append(
                UnrecognizedUpstreamKey(
                    state=ResultObservationState.UNRECOGNIZED,
                    observation_id=f"unrecognized:{len(records) + 1:04d}",
                    container_path=container_path,
                    key_type=key_type,
                    key_identity=identity,
                    binary64_hex=binary64_hex,
                    binary64_bytes_hex=binary64_bytes,
                    consequence=(
                        "The present upstream key has no reviewed D3C-1a route and "
                        "was not carried."
                    ),
                    remedy=(
                        "Review and add an explicit versioned route or an explicit "
                        "refusal before use."
                    ),
                )
            )
    return tuple(records)


def _excluded_fields(
    full_result: Mapping[Any, Any],
) -> tuple[ExcludedResultField, ...]:
    records: list[ExcludedResultField] = []
    for state, catalogue, consequence, remedy in (
        (
            ResultObservationState.ARTIFACT_ONLY,
            D3C_ARTIFACT_ONLY_PATHS,
            "The field remains an opaque upstream artifact and is not interpreted here.",
            "Bind the artifact through the later governed package-authority workflow.",
        ),
        (
            ResultObservationState.KNOWN_REFUSED,
            D3C_KNOWN_REFUSED_PATHS,
            "The reviewed D3C-1a policy refuses this field as a carried observation.",
            "Admit it only through a separately reviewed versioned route and method warning.",
        ),
    ):
        for path, section_ids in catalogue.items():
            records.append(
                ExcludedResultField(
                    state=cast(_ExcludedState, state),
                    observation_id="excluded:" + ".".join(path),
                    source_path=path,
                    section_candidate_ids=section_ids,
                    observed_present=_lookup(full_result, path).present,
                    consequence=consequence,
                    remedy=remedy,
                )
            )
    return tuple(records)


def _manifest_projection(result: D3BExecutionSuccess) -> EngineManifestProjection:
    manifest = result.run_manifest
    if type(manifest) is not MappingProxyType:
        raise ResultProjectionError(
            "manifest_not_frozen", "/run_manifest", "expected an exact mapping proxy"
        )

    def required(name: str) -> object:
        value = manifest.get(name, _MISSING)
        if value is _MISSING:
            raise ResultProjectionError(
                "manifest_field_missing",
                f"/run_manifest/{name}",
                "required engine-manifest observation is absent",
            )
        return value

    try:
        return EngineManifestProjection(
            config_sha256=cast(str, required("config_sha256")),
            engine_version=cast(str, required("engine_version")),
            git_sha=cast(str, required("git_sha")),
            generated_at=cast(str, required("generated_at")),
            seed=cast(int | None, required("seed")),
            validation_mode=cast(Literal["strict"], required("validation_mode")),
            manifest_schema_version=cast(str, required("manifest_schema_version")),
        )
    except ResultProjectionError:
        raise
    except (TypeError, ValueError) as exc:
        raise ResultProjectionError(
            "manifest_field_invalid",
            "/run_manifest",
            "engine-manifest fields violate the D3C-1a exact projection contract",
        ) from exc


def project_d3b_result(result: D3BExecutionSuccess) -> D3CResultProjection:
    """Project exactly one accepted D3B success without executing or recomputing it."""

    if type(result) is not D3BExecutionSuccess:
        raise ResultProjectionError(
            "invalid_input_type",
            "/",
            "D3C-1a accepts exactly D3BExecutionSuccess",
        )
    if type(result.full_result) is not MappingProxyType:
        raise ResultProjectionError(
            "result_not_frozen", "/full_result", "expected an exact mapping proxy"
        )
    if result.full_result.get("run_manifest", _MISSING) is not result.run_manifest:
        raise ResultProjectionError(
            "manifest_identity_mismatch",
            "/full_result/run_manifest",
            "the engine manifest is not the exact full-result subtree",
        )

    try:
        return D3CResultProjection(
            schema_id=RESULT_FACADE_SCHEMA_ID,
            contract_version=RESULT_FACADE_CONTRACT_VERSION,
            authority_status=RESULT_FACADE_AUTHORITY_STATUS,
            source_contract=RESULT_FACADE_SOURCE_CONTRACT,
            source_outcome=result.outcome,
            request_id=result.request_id,
            project_id=result.project_id,
            case_id=result.case_id,
            project_case_revision=result.project_case_revision,
            project_case_sha256=result.project_case_sha256,
            evaluation_request_sha256=result.evaluation_request_sha256,
            source_file_sha256=result.source_file_sha256,
            resolved_config_sha256=result.resolved_config_sha256,
            evaluated_config_sha256=result.evaluated_config_sha256,
            authority_id=result.authority_id,
            config_id=result.config_id,
            evidence_cutoff=result.evidence_cutoff,
            valuation_date=result.valuation_date,
            validation_modules=result.validation_modules,
            returned_warnings=result.warnings,
            fx_degraded=result.fx_degraded,
            engine_manifest=_manifest_projection(result),
            sections=result_section_projections(),
            route_observations=tuple(
                _route_observation(result.full_result, route)
                for route in D3C_RESULT_FIELD_ROUTES
            ),
            excluded_fields=_excluded_fields(result.full_result),
            unrecognized_keys=_unrecognized_keys(result.full_result),
            limitations=(
                ProjectionLimitation(
                    code=RESULT_FACADE_WARNING_LIMITATION_CODE,
                    statement=(
                        "The exact D3B warning tuple and FX degradation facts are "
                        "preserved, but D3C-1a cannot prove that every upstream warning "
                        "channel is represented."
                    ),
                    consequence=(
                        "Absence from returned_warnings cannot be interpreted as absence "
                        "of all warnings."
                    ),
                    remedy=(
                        "A later governed contract must prove exhaustive warning-channel "
                        "coverage before making a completeness claim."
                    ),
                ),
            ),
        )
    except ResultProjectionError:
        raise
    except (TypeError, ValueError) as exc:
        raise ResultProjectionError(
            "projection_contract_invalid",
            "/",
            "the accepted result cannot satisfy the strict D3C-1a projection contract",
        ) from exc


__all__ = ["ResultProjectionError", "project_d3b_result"]
