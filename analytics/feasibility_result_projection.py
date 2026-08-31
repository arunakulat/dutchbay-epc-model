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
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Final, Literal, Mapping, TypeAlias, cast

from analytics.contracts_v14 import (
    D3BAuthoredNumericValue,
    D3BExecutionSuccess,
    D3BNumericProjectionReceipt,
)
from analytics.feasibility_report_contract.assessment_scope import (
    ValidationModule,
    resolved_config_sha256,
)
from analytics.feasibility_report_contract.engine_identity import (
    ENGINE_VERSION_IDENTITY,
    MANIFEST_SCHEMA_VERSION_IDENTITY,
)
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
    ResultScalarKind,
    ResultUnknownKeyType,
    ResultZeroPolicy,
    UnavailableResultObservation,
    UnrecognizedUpstreamKey,
    result_section_projections,
)

_MAX_UNRECOGNIZED_KEYS: Final = 512
_MAX_RESULT_DEPTH: Final = 128
_MAX_RESULT_CONTAINERS: Final = 10_000
_MAX_RESULT_SCALARS: Final = 100_000
_MAX_RESULT_TEXT_CODEPOINTS: Final = 1_000_000
_ALLOWED_VALIDATION_MODULES: Final = frozenset(item.value for item in ValidationModule)
_REQUIRED_VALIDATION_MODULES: Final = frozenset(
    {ValidationModule.CASHFLOW.value, ValidationModule.DEBT.value}
)
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


@dataclass(frozen=True, slots=True)
class _ValidatedOrigin:
    full_result: Mapping[Any, Any]
    origin_invariants: OriginInvariantProjection
    numeric_projection_receipts: tuple[NumericProjectionReceiptProjection, ...]
    gateway_warnings: tuple[str, ...]
    fx_integration: FxIntegrationProjection
    engine_manifest: EngineManifestProjection


def _origin_error(code: str, pointer: str, detail: str) -> ResultProjectionError:
    return ResultProjectionError(code, pointer, detail)


def _detach_frozen_occurrences(
    value: Any,
    *,
    active: set[int] | None = None,
    depth: int = 0,
    counts: list[int] | None = None,
) -> Any:
    """Copy one exact frozen tree while bounding every serialized occurrence."""

    if depth > _MAX_RESULT_DEPTH:
        raise _origin_error(
            "origin_depth_exceeded", "/full_result", "result exceeds depth 128"
        )
    ancestors = active if active is not None else set()
    totals = counts if counts is not None else [0, 0, 0]
    if type(value) is MappingProxyType:
        marker = id(value)
        if marker in ancestors:
            raise _origin_error(
                "origin_cycle", "/full_result", "result contains a mapping cycle"
            )
        next_container_count = totals[0] + 1
        try:
            entry_count = len(value)
        except RuntimeError as exc:  # pragma: no cover - concurrent backing mutation
            raise _origin_error(
                "origin_changed", "/full_result", "result changed during detachment"
            ) from exc
        if (
            next_container_count > _MAX_RESULT_CONTAINERS
            or entry_count > _MAX_RESULT_SCALARS
        ):
            raise _origin_error(
                "origin_volume_exceeded",
                "/full_result",
                "result mapping exceeds bounded container/entry volume",
            )
        try:
            items = tuple(value.items())
        except RuntimeError as exc:  # pragma: no cover - concurrent backing mutation
            raise _origin_error(
                "origin_changed", "/full_result", "result changed during detachment"
            ) from exc
        if len(items) != entry_count:  # pragma: no cover - concurrent mutation
            raise _origin_error(
                "origin_changed", "/full_result", "result changed during detachment"
            )
        key_faults: list[str] = []
        for key, _ in items:
            if type(key) is str:
                totals[2] += len(key)
            elif type(key) is int:
                if key.bit_length() > 4096:
                    key_faults.append("integer mapping key exceeds 4096 bits")
            elif type(key) is float:
                if not math.isfinite(key):
                    key_faults.append("mapping key is not finite binary64")
            else:
                key_faults.append("mapping key has an unsupported exact type")
        if key_faults:
            raise _origin_error("origin_key_invalid", "/full_result", min(key_faults))
        totals[0] = next_container_count
        if totals[2] > _MAX_RESULT_TEXT_CODEPOINTS:
            raise _origin_error(
                "origin_volume_exceeded",
                "/full_result",
                "result exceeds bounded text volume",
            )
        backing: dict[Any, Any] = {}
        ancestors.add(marker)
        try:
            for key, item in items:
                backing[key] = _detach_frozen_occurrences(
                    item,
                    active=ancestors,
                    depth=depth + 1,
                    counts=totals,
                )
        finally:
            ancestors.remove(marker)
        return MappingProxyType(backing)
    if type(value) is tuple:
        marker = id(value)
        if marker in ancestors:  # pragma: no cover - exact tuples cannot self-cycle
            raise _origin_error(
                "origin_cycle", "/full_result", "result contains a sequence cycle"
            )
        totals[0] += 1
        if totals[0] > _MAX_RESULT_CONTAINERS:
            raise _origin_error(
                "origin_volume_exceeded",
                "/full_result",
                "result exceeds bounded container volume",
            )
        ancestors.add(marker)
        try:
            return tuple(
                _detach_frozen_occurrences(
                    item,
                    active=ancestors,
                    depth=depth + 1,
                    counts=totals,
                )
                for item in value
            )
        finally:
            ancestors.remove(marker)
    totals[1] += 1
    if totals[1] > _MAX_RESULT_SCALARS:
        raise _origin_error(
            "origin_volume_exceeded",
            "/full_result",
            "result exceeds bounded scalar volume",
        )
    if value is None or type(value) is bool:
        return value
    if type(value) is str:
        totals[2] += len(value)
        if totals[2] > _MAX_RESULT_TEXT_CODEPOINTS:
            raise _origin_error(
                "origin_volume_exceeded",
                "/full_result",
                "result exceeds bounded text volume",
            )
        return value
    if type(value) is int and value.bit_length() <= 4096:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise _origin_error(
        "origin_scalar_invalid",
        "/full_result",
        "result contains an unsupported or non-finite scalar",
    )


def _exact_key_token(key: object) -> tuple[str, object]:
    if type(key) is str:
        return "string", key
    if type(key) is int:
        return "integer", key
    if type(key) is float and math.isfinite(key):
        return "binary64", struct.pack(">d", key)
    raise ValueError("unsupported exact mapping key")


def _exact_tree_equal(
    left: object,
    right: object,
    *,
    depth: int = 0,
    compared: set[tuple[int, int]] | None = None,
) -> bool:
    """Compare frozen graphs by exact type, key identity, and binary64 bytes."""

    if depth > _MAX_RESULT_DEPTH or type(left) is not type(right):
        return False
    pairs = compared if compared is not None else set()
    if type(left) is MappingProxyType:
        left_mapping = cast(Mapping[Any, Any], left)
        right_mapping = cast(Mapping[Any, Any], right)
        pair = (id(left), id(right))
        if pair in pairs:
            return True
        pairs.add(pair)
        try:
            left_items = {
                _exact_key_token(key): item for key, item in left_mapping.items()
            }
            right_items = {
                _exact_key_token(key): item for key, item in right_mapping.items()
            }
        except ValueError:
            return False
        if (
            len(left_items) != len(left_mapping)
            or len(right_items) != len(right_mapping)
            or left_items.keys() != right_items.keys()
        ):
            return False
        return all(
            _exact_tree_equal(
                item,
                right_items[key],
                depth=depth + 1,
                compared=pairs,
            )
            for key, item in left_items.items()
        )
    if type(left) is tuple:
        left_tuple = left
        right_tuple = cast(tuple[Any, ...], right)
        pair = (id(left), id(right))
        if pair in pairs:
            return True
        pairs.add(pair)
        return len(left_tuple) == len(right_tuple) and all(
            _exact_tree_equal(
                left_item,
                right_item,
                depth=depth + 1,
                compared=pairs,
            )
            for left_item, right_item in zip(left_tuple, right_tuple, strict=True)
        )
    if type(left) is float:
        return struct.pack(">d", left) == struct.pack(">d", right)
    return bool(left == right)


def _thaw_json_config(value: object, *, depth: int = 0) -> object:
    """Return exact JSON-native containers for the public config digest primitive."""

    if depth > _MAX_RESULT_DEPTH:
        raise ValueError("config exceeds the D3C origin depth bound")
    if type(value) is MappingProxyType:
        if any(type(key) is not str for key in value):
            raise TypeError("config mapping keys must be exact strings")
        return {
            key: _thaw_json_config(item, depth=depth + 1) for key, item in value.items()
        }
    if type(value) is tuple:
        return [_thaw_json_config(item, depth=depth + 1) for item in value]
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise TypeError("config contains a non-JSON-native value")


def _project_numeric_receipts(
    result: D3BExecutionSuccess,
) -> tuple[NumericProjectionReceiptProjection, ...]:
    receipts = result.numeric_projection_receipts
    if type(receipts) is not tuple or len(receipts) > 1_024:
        raise _origin_error(
            "numeric_receipts_invalid",
            "/numeric_projection_receipts",
            "numeric receipts must be an exact bounded tuple",
        )
    projected: list[NumericProjectionReceiptProjection] = []
    for index, receipt in enumerate(receipts):
        pointer = f"/numeric_projection_receipts/{index}"
        if type(receipt) is not D3BNumericProjectionReceipt:
            raise _origin_error(
                "numeric_receipt_type_invalid",
                pointer,
                "numeric receipt has a non-canonical runtime type",
            )
        authored = receipt.authored_values
        if type(authored) is not tuple or not 1 <= len(authored) <= 2:
            raise _origin_error(
                "numeric_receipt_authored_values_invalid",
                pointer,
                "numeric receipt authored values must be an exact bounded tuple",
            )
        authored_projection: list[AuthoredNumericProjection] = []
        for authored_index, item in enumerate(authored):
            if type(item) is not D3BAuthoredNumericValue:
                raise _origin_error(
                    "numeric_authored_value_type_invalid",
                    f"{pointer}/authored_values/{authored_index}",
                    "authored numeric value has a non-canonical runtime type",
                )
            try:
                projected_float = float.fromhex(item.binary64_hex)
                authored_projection.append(
                    AuthoredNumericProjection(
                        json_type=item.json_type,
                        authored_value=item.authored_value,
                        binary64_hex=item.binary64_hex,
                        binary64_bytes_hex=struct.pack(">d", projected_float).hex(),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise _origin_error(
                    "numeric_authored_value_invalid",
                    f"{pointer}/authored_values/{authored_index}",
                    "authored numeric value violates exact projection identity",
                ) from exc
        try:
            projected_float = float.fromhex(receipt.projected_binary64_hex)
            projected.append(
                NumericProjectionReceiptProjection(
                    assertion_id=receipt.assertion_id,
                    project_decimal=receipt.project_decimal,
                    projected_binary64_hex=receipt.projected_binary64_hex,
                    projected_binary64_bytes_hex=struct.pack(
                        ">d", projected_float
                    ).hex(),
                    authored_values=tuple(authored_projection),
                )
            )
        except (TypeError, ValueError) as exc:
            raise _origin_error(
                "numeric_receipt_invalid",
                pointer,
                "numeric receipt violates exact Decimal/binary64 identity",
            ) from exc
    if len({item.assertion_id for item in projected}) != len(projected):
        raise _origin_error(
            "numeric_receipt_duplicate",
            "/numeric_projection_receipts",
            "numeric receipt assertion IDs must be unique",
        )
    return tuple(projected)


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
        principal = _lookup(
            full_result,
            ("full_result", "debt_result", "principal_by_tranche"),
        )
        if (
            not remaining.present
            or not _finite_float(remaining.value)
            or remaining.value < 0.0
            or not principal.present
            or type(principal.value) is not MappingProxyType
            or set(principal.value) != {"lkr", "usd", "dfi"}
            or any(
                not _finite_float(value) or value < 0.0
                for value in principal.value.values()
            )
        ):
            return (
                False,
                ResultObservationState.NOT_REPRESENTABLE,
                "the exact IDC-inclusive principal basis is absent or invalid",
            )
        amortizing_base = sum(principal.value.values())
        if not math.isfinite(amortizing_base) or amortizing_base <= 0.0:
            return (
                False,
                ResultObservationState.NOT_REPRESENTABLE,
                "the exact IDC-inclusive principal basis is not positive finite",
            )
        expected = remaining.value / amortizing_base
        if not _exact_scalar_equal(source, expected):
            return (
                False,
                ResultObservationState.NOT_REPRESENTABLE,
                "balloon_pct disagrees with the exact IDC-inclusive principal basis",
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
        if (
            source.value == 0.0
            and route.zero_policy is ResultZeroPolicy.AMBIGUOUS_DEFAULT
        ):
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

    if route.carry_predicate is ResultCarryPredicate.PROJECT_CONTEXT_REQUIRED:
        return _unavailable(
            route,
            ResultObservationState.NOT_REPRESENTABLE,
            "exact upstream scalar is present but governed ProjectCase/request context "
            "is outside D3C-1a",
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


def _manifest_projection(manifest: Mapping[Any, Any]) -> EngineManifestProjection:
    if type(manifest) is not MappingProxyType:
        raise ResultProjectionError(
            "manifest_not_frozen", "/run_manifest", "expected an exact mapping proxy"
        )
    if any(type(key) is not str for key in manifest):
        raise ResultProjectionError(
            "manifest_key_invalid",
            "/run_manifest",
            "every engine-manifest key must be an exact string",
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

    if (
        required("engine_version") != ENGINE_VERSION_IDENTITY
        or required("manifest_schema_version") != MANIFEST_SCHEMA_VERSION_IDENTITY
    ):
        raise ResultProjectionError(
            "manifest_identity_invalid",
            "/run_manifest",
            "engine version or manifest schema differs from the current identity",
        )

    config_sha256 = required("config_sha256")
    engine_version = required("engine_version")
    git_sha = required("git_sha")
    generated_at = required("generated_at")
    seed = required("seed")
    validation_mode = required("validation_mode")
    manifest_schema_version = required("manifest_schema_version")
    try:
        return EngineManifestProjection(
            config_sha256=cast(str, config_sha256),
            engine_version=cast(str, engine_version),
            git_sha=cast(str, git_sha),
            generated_at=cast(str, generated_at),
            seed=cast(int | None, seed),
            validation_mode=cast(Literal["strict"], validation_mode),
            manifest_schema_version=cast(str, manifest_schema_version),
        )
    except (TypeError, ValueError) as exc:
        raise ResultProjectionError(
            "manifest_field_invalid",
            "/run_manifest",
            "engine-manifest fields violate the D3C-1a exact projection contract",
        ) from exc


def _validate_origin(result: D3BExecutionSuccess) -> _ValidatedOrigin:
    """Reconcile the complete bounded D3B origin before scalar mapping begins."""

    if type(result.gateway_call_count) is not int or result.gateway_call_count != 1:
        raise _origin_error(
            "gateway_call_count_invalid",
            "/gateway_call_count",
            "accepted D3B success must disclose exactly one gateway call",
        )
    modules = result.validation_modules
    if (
        type(modules) is not tuple
        or not modules
        or len(modules) > len(_ALLOWED_VALIDATION_MODULES)
        or any(
            type(item) is not str or item not in _ALLOWED_VALIDATION_MODULES
            for item in modules
        )
        or len(set(modules)) != len(modules)
        or not _REQUIRED_VALIDATION_MODULES.issubset(modules)
    ):
        raise _origin_error(
            "validation_modules_invalid",
            "/validation_modules",
            "validation modules differ from the closed public v14 vocabulary",
        )
    for name in ("request_id", "project_id", "case_id", "authority_id", "config_id"):
        value = getattr(result, name)
        if type(value) is not str or not value or len(value) > 160:
            raise _origin_error(
                "origin_envelope_invalid",
                f"/{name}",
                "D3B origin identifier must be exact bounded text",
            )
    if (
        type(result.project_case_revision) is not int
        or result.project_case_revision <= 0
        or result.project_case_revision.bit_length() > 4096
    ):
        raise _origin_error(
            "origin_envelope_invalid",
            "/project_case_revision",
            "ProjectCase revision must be a positive exact integer of at most 4096 bits",
        )
    for name in (
        "project_case_sha256",
        "evaluation_request_sha256",
        "source_file_sha256",
        "resolved_config_sha256",
        "evaluated_config_sha256",
    ):
        value = getattr(result, name)
        if (
            type(value) is not str
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise _origin_error(
                "origin_envelope_invalid",
                f"/{name}",
                "D3B origin digest must be exact lowercase SHA-256",
            )
    if (
        type(result.evidence_cutoff) is not date
        or type(result.valuation_date) is not date
    ):
        raise _origin_error(
            "origin_envelope_invalid",
            "/evidence_cutoff",
            "D3B assessment dates must be exact date values",
        )
    if type(result.full_result) is not MappingProxyType:
        raise _origin_error(
            "result_not_frozen", "/full_result", "expected an exact mapping proxy"
        )
    if type(result.run_manifest) is not MappingProxyType:
        raise _origin_error(
            "manifest_not_frozen", "/run_manifest", "expected an exact mapping proxy"
        )
    if result.full_result.get("run_manifest", _MISSING) is not result.run_manifest:
        raise _origin_error(
            "manifest_identity_mismatch",
            "/full_result/run_manifest",
            "the engine manifest is not the exact full-result subtree",
        )

    full_result = cast(
        Mapping[Any, Any], _detach_frozen_occurrences(result.full_result)
    )
    required_root_types = {
        "status": str,
        "config_path": str,
        "validation_mode": str,
        "scenario_result": MappingProxyType,
        "kpis": MappingProxyType,
        "annual_rows": tuple,
        "debt_result": MappingProxyType,
        "equity_distribution": MappingProxyType,
        "metrics": MappingProxyType,
        "fx_integration": MappingProxyType,
        "run_manifest": MappingProxyType,
    }
    if any(
        type(full_result.get(key, _MISSING)) is not expected
        for key, expected in required_root_types.items()
    ):
        raise _origin_error(
            "origin_surface_invalid",
            "/full_result",
            "full result is missing a required exact D3B surface",
        )
    if (
        full_result["status"] != "success"
        or full_result["config_path"] != "<inline>"
        or full_result["validation_mode"] != "strict"
        or not full_result["annual_rows"]
        or any(
            type(row) is not MappingProxyType or not row
            for row in full_result["annual_rows"]
        )
    ):
        raise _origin_error(
            "origin_protocol_invalid",
            "/full_result",
            "full result violates the strict success protocol",
        )

    scenario = full_result["scenario_result"]
    required_scenario_types = {
        "scenario_name": str,
        "config_path": str,
        "project_npv": float,
        "project_irr": float,
        "dscr_series": tuple,
        "min_dscr": float,
        "max_debt_usd": float,
        "validation_mode": str,
        "config": MappingProxyType,
        "annual_rows": tuple,
        "debt_result": MappingProxyType,
        "kpis": MappingProxyType,
        "metadata": MappingProxyType,
    }
    if any(
        type(scenario.get(key, _MISSING)) is not expected
        for key, expected in required_scenario_types.items()
    ) or any(
        not math.isfinite(scenario[key])
        for key in ("project_npv", "project_irr", "min_dscr", "max_debt_usd")
    ):
        raise _origin_error(
            "scenario_origin_invalid",
            "/full_result/scenario_result",
            "ScenarioResult surface is incomplete or non-finite",
        )
    if (
        not scenario["scenario_name"]
        or scenario["config_path"] != "<inline>"
        or scenario["validation_mode"] != "strict"
        or not scenario["config"]
        or not scenario["annual_rows"]
        or not scenario["debt_result"]
        or not scenario["kpis"]
        or not scenario["metadata"]
        or any(
            type(item) is not float or not math.isfinite(item)
            for item in scenario["dscr_series"]
        )
    ):
        raise _origin_error(
            "scenario_origin_invalid",
            "/full_result/scenario_result",
            "ScenarioResult violates the strict accepted origin protocol",
        )
    if any(
        not _exact_tree_equal(scenario[name], full_result[name])
        for name in ("annual_rows", "debt_result", "kpis")
    ):
        raise _origin_error(
            "duplicated_origin_mismatch",
            "/full_result/scenario_result",
            "duplicated annual/KPI/debt origins do not reconcile exactly",
        )

    try:
        thawed_config = cast(dict[str, object], _thaw_json_config(scenario["config"]))
        scenario_digest = resolved_config_sha256(thawed_config)
    except (TypeError, ValueError) as exc:
        raise _origin_error(
            "evaluated_config_invalid",
            "/full_result/scenario_result/config",
            "ScenarioResult config cannot satisfy the public digest primitive",
        ) from exc
    if scenario_digest != result.evaluated_config_sha256:
        raise _origin_error(
            "evaluated_config_digest_mismatch",
            "/full_result/scenario_result/config",
            "ScenarioResult config digest differs from evaluated_config_sha256",
        )

    kpis = full_result["kpis"]
    for key in ("project_npv", "project_irr", "min_dscr", "max_debt_usd"):
        if (
            type(kpis.get(key, _MISSING)) is not float
            or not math.isfinite(kpis[key])
            or not _exact_tree_equal(scenario[key], kpis[key])
        ):
            raise _origin_error(
                "kpi_origin_mismatch",
                f"/full_result/kpis/{key}",
                "KPI and ScenarioResult origins do not reconcile exactly",
            )
    debt = full_result["debt_result"]
    if (
        type(debt.get("debt_total", _MISSING)) is not float
        or not math.isfinite(debt["debt_total"])
        or type(debt.get("min_dscr", _MISSING)) is not float
        or not math.isfinite(debt["min_dscr"])
        or type(debt.get("dscr_by_year", _MISSING)) is not MappingProxyType
        or not debt["dscr_by_year"]
        or not _exact_tree_equal(debt["debt_total"], kpis["max_debt_usd"])
        or not _exact_tree_equal(debt["min_dscr"], kpis["min_dscr"])
    ):
        raise _origin_error(
            "debt_origin_mismatch",
            "/full_result/debt_result",
            "debt result and KPI origins do not reconcile exactly",
        )

    manifest = full_result["run_manifest"]
    engine_manifest = _manifest_projection(manifest)
    if engine_manifest.config_sha256 != result.evaluated_config_sha256:
        raise _origin_error(
            "manifest_digest_mismatch",
            "/full_result/run_manifest/config_sha256",
            "manifest digest differs from evaluated_config_sha256",
        )

    fx = full_result["fx_integration"]
    try:
        fx_projection = FxIntegrationProjection(
            attempted=fx.get("attempted", _MISSING),
            succeeded=fx.get("succeeded", _MISSING),
            warning=fx.get("warning", _MISSING),
            degraded=fx.get("degraded", _MISSING),
            degraded_reasons=fx.get("degraded_reasons", _MISSING),
        )
    except (TypeError, ValueError) as exc:
        raise _origin_error(
            "fx_origin_invalid",
            "/full_result/fx_integration",
            "FX integration disclosure violates the exact origin protocol",
        ) from exc
    gateway_warnings = full_result.get("warnings", ())
    if (
        type(gateway_warnings) is not tuple
        or any(type(item) is not str for item in gateway_warnings)
        or len(gateway_warnings) > _MAX_RESULT_SCALARS
        or sum(len(item) for item in gateway_warnings) > _MAX_RESULT_TEXT_CODEPOINTS
    ):
        raise _origin_error(
            "gateway_warnings_invalid",
            "/full_result/warnings",
            "gateway warnings must be an exact bounded text tuple",
        )
    returned_warnings = (
        *gateway_warnings,
        *((fx_projection.warning,) if fx_projection.warning is not None else ()),
        *fx_projection.degraded_reasons,
    )
    if (
        type(result.warnings) is not tuple
        or result.warnings != returned_warnings
        or any(type(item) is not str for item in result.warnings)
    ):
        raise _origin_error(
            "warning_origin_mismatch",
            "/warnings",
            "D3B warning tuple differs from exact gateway/FX origins",
        )
    expected_fx_degraded = bool(returned_warnings) or (
        not fx_projection.succeeded or fx_projection.degraded
    )
    if (
        type(result.fx_degraded) is not bool
        or result.fx_degraded is not expected_fx_degraded
    ):
        raise _origin_error(
            "fx_degradation_mismatch",
            "/fx_degraded",
            "D3B FX degradation differs from exact structured origins",
        )
    expected_outcome = "degraded_success" if expected_fx_degraded else "success"
    if result.outcome != expected_outcome:
        raise _origin_error(
            "outcome_origin_mismatch",
            "/outcome",
            "D3B outcome differs from warning/degradation origins",
        )

    receipts = _project_numeric_receipts(result)
    return _ValidatedOrigin(
        full_result=full_result,
        origin_invariants=OriginInvariantProjection(
            gateway_call_count=1,
            full_status="success",
            full_config_path="<inline>",
            scenario_config_path="<inline>",
            full_validation_mode="strict",
            scenario_validation_mode="strict",
            duplicated_origins_exact=True,
            evaluated_config_digest_verified=True,
            manifest_identity_verified=True,
            gateway_warnings_present="warnings" in full_result,
        ),
        numeric_projection_receipts=receipts,
        gateway_warnings=cast(tuple[str, ...], gateway_warnings),
        fx_integration=fx_projection,
        engine_manifest=engine_manifest,
    )


def project_d3b_result(result: D3BExecutionSuccess) -> D3CResultProjection:
    """Project exactly one accepted D3B success without executing or recomputing it."""

    if type(result) is not D3BExecutionSuccess:
        raise ResultProjectionError(
            "invalid_input_type",
            "/",
            "D3C-1a accepts exactly D3BExecutionSuccess",
        )
    origin = _validate_origin(result)

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
            origin_invariants=origin.origin_invariants,
            numeric_projection_receipts=origin.numeric_projection_receipts,
            gateway_warnings=origin.gateway_warnings,
            returned_warnings=result.warnings,
            fx_degraded=result.fx_degraded,
            fx_integration=origin.fx_integration,
            engine_manifest=origin.engine_manifest,
            sections=result_section_projections(),
            route_observations=tuple(
                _route_observation(origin.full_result, route)
                for route in D3C_RESULT_FIELD_ROUTES
            ),
            excluded_fields=_excluded_fields(origin.full_result),
            unrecognized_keys=_unrecognized_keys(origin.full_result),
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
