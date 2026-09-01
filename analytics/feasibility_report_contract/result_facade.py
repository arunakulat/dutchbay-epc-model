"""Strict non-authoritative D3C-1a result-projection contracts.

The contracts in this module describe observations from one already accepted
``D3BExecutionSuccess``.  They deliberately cannot express final D2 records,
package authority, grade, release, evidence sufficiency, or section completion.
The translation implementation lives outside this leaf package so this module
does not acquire a dependency on the v14 evaluator or its contracts.
"""

from __future__ import annotations

import math
import re
import struct
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Annotated, Final, Literal, Mapping, TypeAlias, Union

from pydantic import (
    BeforeValidator,
    Field,
    Strict,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from .engine_identity import (
    ENGINE_VERSION_IDENTITY,
    MANIFEST_SCHEMA_VERSION_IDENTITY,
)
from .taxonomy_identity import FEASIBILITY_SECTION_IDS
from .vocabulary import StrictFrozenModel

RESULT_FACADE_SCHEMA_ID: Final = "dutchbay.section_result_facade.v1"
RESULT_FACADE_CONTRACT_VERSION: Final = "1.0.0"
RESULT_FACADE_AUTHORITY_STATUS: Final = "non_authoritative"
RESULT_FACADE_SOURCE_CONTRACT: Final = "analytics.contracts_v14.D3BExecutionSuccess"
RESULT_FACADE_WARNING_LIMITATION_CODE: Final = "upstream_warning_channel_not_exhaustive"

_MAX_RECORDS = 512
_MAX_NUMERIC_PROJECTION_RECEIPTS = 1_024
_MAX_WARNINGS = 100_000
_MAX_REVISION_BITS = 4_096
_MAX_BOUNDED_INTEGER = (1 << _MAX_REVISION_BITS) - 1
_MAX_PATH_PARTS = 16
_MAX_TEXT = 4_096
_MAX_WARNING_TEXT = 1_000_000
_BoundedRevisionSerialization: TypeAlias = Annotated[
    int, Field(ge=1, le=_MAX_BOUNDED_INTEGER)
]
_BoundedSeedSerialization: TypeAlias = Annotated[
    int, Field(ge=-_MAX_BOUNDED_INTEGER, le=_MAX_BOUNDED_INTEGER)
]
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}\Z")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}\Z")
_INTEGER_TEXT_RE = re.compile(r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")
_BINARY64_BYTES_RE = re.compile(r"^[0-9a-f]{16}\Z")


def _exact_stable_id(value: object) -> str:
    if type(value) is not str or _STABLE_ID_RE.fullmatch(value) is None:
        raise ValueError("value must be an exact stable identifier")
    return value


def _exact_text(value: object) -> str:
    if type(value) is not str or not value or len(value) > _MAX_TEXT:
        raise ValueError("value must be exact bounded nonempty text")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise ValueError("exact text contains a forbidden control character")
    if _contains_unicode_surrogate(value):
        raise ValueError("exact text contains a Unicode surrogate code point")
    return value


def _contains_unicode_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _exact_warning_text(value: object) -> str:
    if type(value) is not str or len(value) > _MAX_WARNING_TEXT:
        raise ValueError("warning text must be an exact bounded string")
    if _contains_unicode_surrogate(value):
        raise ValueError("warning text contains a Unicode surrogate code point")
    return value


def _bounded_revision(value: object) -> int:
    if type(value) is not int or value <= 0 or value > _MAX_BOUNDED_INTEGER:
        raise ValueError(
            "ProjectCase revision must be a positive exact integer of at most 4096 bits"
        )
    return value


def _bounded_seed(value: object) -> int | None:
    if value is not None and (
        type(value) is not int
        or value < -_MAX_BOUNDED_INTEGER
        or value > _MAX_BOUNDED_INTEGER
    ):
        raise ValueError("manifest seed must be an exact integer of at most 4096 bits")
    return value


def _exact_sha256(value: object) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise ValueError("value must be exact lowercase SHA-256 hex")
    return value


def _exact_git_commit(value: object) -> str:
    if type(value) is not str or _GIT_COMMIT_RE.fullmatch(value) is None:
        raise ValueError("value must be exact lowercase git commit hex")
    return value


def _exact_utc_timestamp(value: object) -> str:
    if type(value) is not str or not value or len(value) > 64:
        raise ValueError("value must be exact bounded UTC timestamp text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("value must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must carry an explicit UTC offset")
    if parsed.astimezone(UTC).utcoffset() != parsed.utcoffset():
        raise ValueError("timestamp must use UTC")
    return value


def _exact_binary64_hex(value: object) -> str:
    if type(value) is not str or not value or len(value) > 32:
        raise ValueError("value must be exact bounded binary64 hex text")
    try:
        projected = float.fromhex(value)
    except ValueError as exc:
        raise ValueError("value must be binary64 hex text") from exc
    if not math.isfinite(projected) or projected.hex() != value:
        raise ValueError("value must be canonical finite float.hex text")
    return value


def _exact_binary64_bytes(value: object) -> str:
    if type(value) is not str or _BINARY64_BYTES_RE.fullmatch(value) is None:
        raise ValueError("value must be exact 8-byte binary64 hex")
    return value


ExactStableId: TypeAlias = Annotated[str, BeforeValidator(_exact_stable_id)]
ExactText: TypeAlias = Annotated[str, BeforeValidator(_exact_text)]
ExactWarningText: TypeAlias = Annotated[str, BeforeValidator(_exact_warning_text)]
ExactSha256: TypeAlias = Annotated[str, BeforeValidator(_exact_sha256)]
ExactGitCommit: TypeAlias = Annotated[str, BeforeValidator(_exact_git_commit)]
ExactUtcTimestamp: TypeAlias = Annotated[str, BeforeValidator(_exact_utc_timestamp)]
ExactBinary64Hex: TypeAlias = Annotated[str, BeforeValidator(_exact_binary64_hex)]
ExactBinary64Bytes: TypeAlias = Annotated[str, BeforeValidator(_exact_binary64_bytes)]
ExactPath: TypeAlias = Annotated[
    tuple[ExactText, ...], Field(min_length=1, max_length=_MAX_PATH_PARTS)
]


class ResultObservationState(str, Enum):
    """Closed observation states for the result-only projection."""

    CARRIED = "carried"
    AMBIGUOUS_DEFAULT = "ambiguous_default"
    UPSTREAM_NONE = "upstream_none"
    NOT_COMPUTED = "not_computed"
    NOT_REPRESENTABLE = "not_representable"
    ARTIFACT_ONLY = "artifact_only"
    KNOWN_REFUSED = "known_refused"
    UNRECOGNIZED = "unrecognized"


class ResultScalarKind(str, Enum):
    """Exact scalar origins admitted by D3C-1a."""

    BINARY64 = "binary64"
    INTEGER = "integer"


class ResultValueType(str, Enum):
    """Local scalar vocabulary; it carries no D2 canonical-value authority."""

    DECIMAL_TEXT = "decimal_text"
    INTEGER_TEXT = "integer_text"


class ResultObservationClass(str, Enum):
    """The only D3C-1a output class: an engine-result observation."""

    ENGINE_RESULT_OBSERVATION = "engine_result_observation"


class ResultCarryPredicate(str, Enum):
    """Closed, reviewable carry predicates; no arbitrary callbacks are allowed."""

    FINITE_NONZERO_EXACT_MIRRORS = "finite_nonzero_exact_mirrors"
    EQUITY_IRR_COMPUTED = "equity_irr_computed"
    PRUDENTIAL_NPV_COMPUTED = "prudential_npv_computed"
    ANNUAL_CFADS_COMPLETE = "annual_cfads_complete"
    DSCR_SERIES_EXACT_MIRRORS = "dscr_series_exact_mirrors"
    DSCR_SERIES_PRESENT = "dscr_series_present"
    POSITIVE_DEBT_EXACT_MIRROR = "positive_debt_exact_mirror"
    MAX_DEBT_EXACT_MIRRORS = "max_debt_exact_mirrors"
    POSITIVE_DEBT_FINITE = "positive_debt_finite"
    FINITE = "finite"
    BALLOON_BASIS_PRESENT = "balloon_basis_present"
    EXACT_INTEGER = "exact_integer"
    PROJECT_CONTEXT_REQUIRED = "project_context_required"


class ResultZeroPolicy(str, Enum):
    """Per-route treatment of an exact binary64 zero."""

    ALLOW_EXACT = "allow_exact"
    AMBIGUOUS_DEFAULT = "ambiguous_default"


class ResultPathDisposition(str, Enum):
    """One reviewed purpose for every inspected upstream result path."""

    ROUTE_CANDIDATE = "route_candidate"
    EXACT_MIRROR_OPERAND = "exact_mirror_operand"
    CARRY_PREDICATE_OPERAND = "carry_predicate_operand"
    ORIGIN_INVARIANT = "origin_invariant"
    MANIFEST_PROJECTION = "manifest_projection"
    STRUCTURED_PROJECTION = "structured_projection"
    STRUCTURED_CONTAINER = "structured_container"
    OPAQUE_ARTIFACT = "opaque_artifact"
    KNOWN_REFUSED = "known_refused"


class ResultPrecisionPolicy(str, Enum):
    """Meaningful precision is metadata, never display rounding or accuracy."""

    REVIEWED_FIELD_TABLE_V1 = "reviewed_field_table_v1"


class ResultUnknownKeyType(str, Enum):
    """Exact mapping-key types surfaced without coercion."""

    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    BINARY64 = "binary64"


class ResultFieldRoute(StrictFrozenModel):
    """One immutable static candidate from a v14 result field to report sections."""

    route_id: ExactStableId
    source_path: ExactPath
    mirror_paths: Annotated[tuple[ExactPath, ...], Field(max_length=8)]
    section_ids: Annotated[tuple[ExactStableId, ...], Field(min_length=1, max_length=4)]
    scalar_kind: ResultScalarKind
    value_type: ResultValueType
    unit: ExactText
    meaningful_precision: Annotated[int, Strict(), Field(ge=0, le=18)]
    precision_policy: Literal[ResultPrecisionPolicy.REVIEWED_FIELD_TABLE_V1]
    output_class: Literal[ResultObservationClass.ENGINE_RESULT_OBSERVATION]
    carry_predicate: ResultCarryPredicate
    zero_policy: ResultZeroPolicy
    unresolved_dependency_ids: Annotated[tuple[ExactStableId, ...], Field(max_length=8)]

    @model_validator(mode="after")
    def _route_is_coherent(self) -> "ResultFieldRoute":
        if len(set(self.mirror_paths)) != len(self.mirror_paths):
            raise ValueError("result route contains duplicate mirror paths")
        if self.source_path in self.mirror_paths:
            raise ValueError("result route source cannot also be a mirror")
        if len(set(self.section_ids)) != len(self.section_ids):
            raise ValueError("result route contains duplicate section IDs")
        if len(set(self.unresolved_dependency_ids)) != len(
            self.unresolved_dependency_ids
        ):
            raise ValueError("result route contains duplicate dependencies")
        if self.scalar_kind is ResultScalarKind.INTEGER:
            if (
                self.value_type is not ResultValueType.INTEGER_TEXT
                or self.meaningful_precision != 0
            ):
                raise ValueError(
                    "integer route requires integer value type and precision 0"
                )
        elif self.value_type is not ResultValueType.DECIMAL_TEXT:
            raise ValueError("binary64 route requires exact decimal observation text")
        if (
            self.scalar_kind is ResultScalarKind.INTEGER
            and self.zero_policy is not ResultZeroPolicy.ALLOW_EXACT
        ):
            raise ValueError("integer route cannot declare binary64 zero ambiguity")
        if (
            self.carry_predicate is ResultCarryPredicate.PROJECT_CONTEXT_REQUIRED
            and not self.unresolved_dependency_ids
        ):
            raise ValueError("context-required route must name its dependencies")
        return self


_S12 = "financing_plan_debt_sizing"
_S13 = "tax_fx_inflation_accounting"
_S14 = "base_case_financial_outputs"


def _route(
    route_id: str,
    source_path: tuple[str, ...],
    section_ids: tuple[str, ...],
    unit: str,
    precision: int,
    predicate: ResultCarryPredicate,
    *,
    mirrors: tuple[tuple[str, ...], ...] = (),
    scalar_kind: ResultScalarKind = ResultScalarKind.BINARY64,
    zero_policy: ResultZeroPolicy = ResultZeroPolicy.ALLOW_EXACT,
    dependencies: tuple[str, ...] = (),
) -> ResultFieldRoute:
    return ResultFieldRoute(
        route_id=route_id,
        source_path=source_path,
        mirror_paths=mirrors,
        section_ids=section_ids,
        scalar_kind=scalar_kind,
        value_type=(
            ResultValueType.INTEGER_TEXT
            if scalar_kind is ResultScalarKind.INTEGER
            else ResultValueType.DECIMAL_TEXT
        ),
        unit=unit,
        meaningful_precision=precision,
        precision_policy=ResultPrecisionPolicy.REVIEWED_FIELD_TABLE_V1,
        output_class=ResultObservationClass.ENGINE_RESULT_OBSERVATION,
        carry_predicate=predicate,
        zero_policy=zero_policy,
        unresolved_dependency_ids=dependencies,
    )


D3C_RESULT_FIELD_ROUTES: Final[tuple[ResultFieldRoute, ...]] = (
    _route(
        "route:kpis.project_irr",
        ("full_result", "kpis", "project_irr"),
        (_S14,),
        "fraction/year",
        8,
        ResultCarryPredicate.FINITE_NONZERO_EXACT_MIRRORS,
        mirrors=(("full_result", "scenario_result", "project_irr"),),
        zero_policy=ResultZeroPolicy.AMBIGUOUS_DEFAULT,
    ),
    _route(
        "route:kpis.equity_irr",
        ("full_result", "kpis", "equity_irr"),
        (_S14,),
        "fraction/year",
        8,
        ResultCarryPredicate.EQUITY_IRR_COMPUTED,
        mirrors=(
            ("full_result", "scenario_result", "equity_performance", "equity_irr"),
        ),
    ),
    _route(
        "route:kpis.project_npv",
        ("full_result", "kpis", "project_npv"),
        (_S14,),
        "USD",
        0,
        ResultCarryPredicate.FINITE_NONZERO_EXACT_MIRRORS,
        mirrors=(("full_result", "scenario_result", "project_npv"),),
        zero_policy=ResultZeroPolicy.AMBIGUOUS_DEFAULT,
    ),
    _route(
        "route:kpis.project_npv_prudential",
        ("full_result", "kpis", "project_npv_prudential"),
        (_S14,),
        "USD",
        0,
        ResultCarryPredicate.PRUDENTIAL_NPV_COMPUTED,
        mirrors=(("full_result", "scenario_result", "wacc", "prudential_npv"),),
        dependencies=("dependency:prudential_rate_used",),
    ),
    _route(
        "route:kpis.total_cfads_usd",
        ("full_result", "kpis", "total_cfads_usd"),
        (_S14,),
        "USD",
        0,
        ResultCarryPredicate.ANNUAL_CFADS_COMPLETE,
        dependencies=("dependency:annual_rows.cfads_usd",),
    ),
    _route(
        "route:kpis.min_dscr",
        ("full_result", "kpis", "min_dscr"),
        (_S12, _S14),
        "ratio",
        4,
        ResultCarryPredicate.DSCR_SERIES_EXACT_MIRRORS,
        mirrors=(
            ("full_result", "debt_result", "min_dscr"),
            ("full_result", "scenario_result", "min_dscr"),
        ),
        dependencies=("dependency:scenario_result.dscr_series",),
    ),
    _route(
        "route:kpis.avg_dscr",
        ("full_result", "kpis", "avg_dscr"),
        (_S12, _S14),
        "ratio",
        4,
        ResultCarryPredicate.DSCR_SERIES_PRESENT,
        dependencies=("dependency:scenario_result.dscr_series",),
    ),
    _route(
        "route:kpis.llcr",
        ("full_result", "kpis", "llcr"),
        (_S12, _S14),
        "ratio",
        4,
        ResultCarryPredicate.POSITIVE_DEBT_EXACT_MIRROR,
        mirrors=(("full_result", "debt_result", "llcr"),),
    ),
    _route(
        "route:kpis.plcr",
        ("full_result", "kpis", "plcr"),
        (_S12, _S14),
        "ratio",
        4,
        ResultCarryPredicate.POSITIVE_DEBT_EXACT_MIRROR,
        mirrors=(("full_result", "debt_result", "plcr"),),
    ),
    _route(
        "route:kpis.max_debt_usd",
        ("full_result", "kpis", "max_debt_usd"),
        (_S12, _S14),
        "USD",
        0,
        ResultCarryPredicate.MAX_DEBT_EXACT_MIRRORS,
        mirrors=(
            ("full_result", "debt_result", "debt_total"),
            ("full_result", "scenario_result", "max_debt_usd"),
        ),
    ),
    *(
        _route(
            f"route:debt_result.principal_by_tranche.{tranche}",
            ("full_result", "debt_result", "principal_by_tranche", tranche),
            (_S12,),
            "USD",
            0,
            ResultCarryPredicate.FINITE,
        )
        for tranche in ("lkr", "usd", "dfi")
    ),
    _route(
        "route:debt_result.total_idc",
        ("full_result", "debt_result", "total_idc"),
        (_S12,),
        "USD",
        0,
        ResultCarryPredicate.FINITE,
    ),
    _route(
        "route:debt_result.avg_debt_rate",
        ("full_result", "debt_result", "avg_debt_rate"),
        (_S12,),
        "fraction/year",
        6,
        ResultCarryPredicate.POSITIVE_DEBT_FINITE,
    ),
    _route(
        "route:debt_result.balloon_remaining",
        ("full_result", "debt_result", "balloon_remaining"),
        (_S12,),
        "USD",
        0,
        ResultCarryPredicate.FINITE,
    ),
    _route(
        "route:debt_result.balloon_pct",
        ("full_result", "debt_result", "balloon_pct"),
        (_S12,),
        "fraction",
        6,
        ResultCarryPredicate.BALLOON_BASIS_PRESENT,
        dependencies=("dependency:debt_result.balloon_remaining",),
    ),
    *(
        _route(
            f"route:debt_result.{field_name}",
            ("full_result", "debt_result", field_name),
            (_S12,),
            unit,
            0,
            ResultCarryPredicate.EXACT_INTEGER,
            scalar_kind=ResultScalarKind.INTEGER,
        )
        for field_name, unit in (
            ("construction_years", "year"),
            ("tenor_years", "year"),
            ("timeline_periods", "count"),
        )
    ),
    *(
        _route(
            f"route:debt_result.{field_name}",
            ("full_result", "debt_result", field_name),
            (_S13,),
            "LKR/USD",
            2,
            ResultCarryPredicate.PROJECT_CONTEXT_REQUIRED,
            dependencies=(
                "dependency:project_case.currency_conversion",
                "dependency:evaluation_request.price_basis",
                "dependency:annual_rows.fx_rate",
            ),
        )
        for field_name in ("fx_min", "fx_max", "fx_avg")
    ),
)


_ROUTE_INDEX: Final[Mapping[str, ResultFieldRoute]] = MappingProxyType(
    {route.route_id: route for route in D3C_RESULT_FIELD_ROUTES}
)
if len(_ROUTE_INDEX) != len(D3C_RESULT_FIELD_ROUTES):  # pragma: no cover
    raise RuntimeError("D3C result route IDs are not unique")
_SOURCE_PATHS = tuple(route.source_path for route in D3C_RESULT_FIELD_ROUTES)
if len(set(_SOURCE_PATHS)) != len(_SOURCE_PATHS):  # pragma: no cover
    raise RuntimeError("D3C result route source paths are not unique")


_S10 = "capex_opex_contingency_procurement"
_S20 = "appendices_provenance_audit_trail"

_path_dispositions: dict[tuple[str, ...], ResultPathDisposition] = {}


def _declare_path(path: tuple[str, ...], disposition: ResultPathDisposition) -> None:
    if path in _path_dispositions:  # pragma: no cover - static authoring guard
        raise RuntimeError(f"duplicate D3C result-path disposition: {path!r}")
    _path_dispositions[path] = disposition


for _route_item in D3C_RESULT_FIELD_ROUTES:
    _declare_path(
        _route_item.source_path,
        ResultPathDisposition.ROUTE_CANDIDATE,
    )
    for _mirror_path in _route_item.mirror_paths:
        _declare_path(
            _mirror_path,
            ResultPathDisposition.EXACT_MIRROR_OPERAND,
        )

for _path, _disposition in (
    # Root and duplicated ScenarioResult origin protocol.
    (("full_result", "status"), ResultPathDisposition.ORIGIN_INVARIANT),
    (("full_result", "config_path"), ResultPathDisposition.ORIGIN_INVARIANT),
    (("full_result", "validation_mode"), ResultPathDisposition.ORIGIN_INVARIANT),
    (("full_result", "scenario_result"), ResultPathDisposition.ORIGIN_INVARIANT),
    (("full_result", "kpis"), ResultPathDisposition.ORIGIN_INVARIANT),
    (("full_result", "annual_rows"), ResultPathDisposition.ORIGIN_INVARIANT),
    (("full_result", "debt_result"), ResultPathDisposition.ORIGIN_INVARIANT),
    (
        ("full_result", "equity_distribution"),
        ResultPathDisposition.STRUCTURED_CONTAINER,
    ),
    (("full_result", "metrics"), ResultPathDisposition.OPAQUE_ARTIFACT),
    (("full_result", "fx_integration"), ResultPathDisposition.STRUCTURED_PROJECTION),
    (("full_result", "run_manifest"), ResultPathDisposition.ORIGIN_INVARIANT),
    (("full_result", "warnings"), ResultPathDisposition.STRUCTURED_PROJECTION),
    (
        ("full_result", "scenario_result", "scenario_name"),
        ResultPathDisposition.ORIGIN_INVARIANT,
    ),
    (
        ("full_result", "scenario_result", "config_path"),
        ResultPathDisposition.ORIGIN_INVARIANT,
    ),
    (
        ("full_result", "scenario_result", "validation_mode"),
        ResultPathDisposition.ORIGIN_INVARIANT,
    ),
    (
        ("full_result", "scenario_result", "config"),
        ResultPathDisposition.ORIGIN_INVARIANT,
    ),
    (
        ("full_result", "scenario_result", "annual_rows"),
        ResultPathDisposition.ORIGIN_INVARIANT,
    ),
    (
        ("full_result", "scenario_result", "debt_result"),
        ResultPathDisposition.ORIGIN_INVARIANT,
    ),
    (
        ("full_result", "scenario_result", "kpis"),
        ResultPathDisposition.ORIGIN_INVARIANT,
    ),
    (
        ("full_result", "scenario_result", "metadata"),
        ResultPathDisposition.OPAQUE_ARTIFACT,
    ),
    (
        ("full_result", "scenario_result", "dscr_series"),
        ResultPathDisposition.CARRY_PREDICATE_OPERAND,
    ),
    (
        ("full_result", "scenario_result", "wacc"),
        ResultPathDisposition.STRUCTURED_CONTAINER,
    ),
    (
        ("full_result", "scenario_result", "equity_performance"),
        ResultPathDisposition.STRUCTURED_CONTAINER,
    ),
    *(
        (
            ("full_result", "scenario_result", _name),
            ResultPathDisposition.KNOWN_REFUSED,
        )
        for _name in ("discount_rate_used", "wacc_label", "wacc_is_real")
    ),
    *(
        (
            ("full_result", "scenario_result", _name),
            ResultPathDisposition.OPAQUE_ARTIFACT,
        )
        for _name in (
            "debt_profile",
            "debt_covenants",
            "fx_block",
            "fx_curve",
            "fx_risk_profile",
            "cashflow",
        )
    ),
    # KPI aliases/statistics are known but deliberately not carried by D3C-1a.
    (
        ("full_result", "kpis", "prudential_rate_used"),
        ResultPathDisposition.CARRY_PREDICATE_OPERAND,
    ),
    *(
        (
            ("full_result", "kpis", _name),
            ResultPathDisposition.KNOWN_REFUSED,
        )
        for _name in (
            "scenario_name",
            "final_cfads_usd",
            "mean_operational_cfads_usd",
            "dscr_series",
            "dscr_min",
            "min_dscr_period",
            "dscr_max",
            "dscr_mean",
            "dscr_median",
            "dscr_p10",
            "dscr_p90",
            "dscr_std",
            "total_idc_usd",
            "npv",
            "irr",
            "discount_rate_used",
            "wacc_label",
            "wacc_is_real",
            "balloon_pct",
            "balloon_residual",
            "balloon_covenant_breach",
            "equity_distribution_status",
            "equity_npv",
            "equity_multiple",
            "equity_moic",
            "equity_payback_period_years",
            "total_equity_distributed_usd",
            "average_equity_cash_on_cash",
            "equity_covenant_locked_years",
            "fx_match_ratio",
            "hedging_coverage_pct",
            "var_95_usd_million",
            "cvar_95_usd_million",
        )
    ),
    # Debt containers, mirrors, predicates, schedules and unit-ambiguous aliases.
    (
        ("full_result", "debt_result", "principal_by_tranche"),
        ResultPathDisposition.STRUCTURED_CONTAINER,
    ),
    *(
        (
            ("full_result", "debt_result", _name),
            ResultPathDisposition.OPAQUE_ARTIFACT,
        )
        for _name in (
            "lkr",
            "usd",
            "dfi",
            "idc_by_tranche",
            "audit_status",
            "debt_outstanding",
            "debt_service_total",
            "interest_total",
            "total_service",
            "senior_fee_usd",
            "senior_fee_rate",
            "dscr_series",
            "raw_dscr_series",
            "dscr_by_year",
            "annual_row_debt_period_map",
            "cfads_bridge_debt_period",
            # F-6 period taxonomy. `bridge_debt_period` restates
            # `cfads_bridge_debt_period` above under the engine's own name and
            # `construction_periods` restates `construction_years`, so the
            # taxonomy carries no fact this facade does not already see; it is
            # dispositioned with its siblings rather than routed, which would
            # carry the same number twice under two names.
            "construction_periods",
            "bridge_debt_period",
            "first_operating_period",
            "balloon_treatment",
            "balloon_resolution",
            "balloon_residual",
            "balloon_covenant_breach",
            "max_balloon_pct",
            "debt_schedules",
            "dual_dscr",
            "funding",
            "principal_schedule",
            "interest_schedule",
        )
    ),
    (
        ("full_result", "debt_result", "total_idc_m"),
        ResultPathDisposition.KNOWN_REFUSED,
    ),
    # Equity status is a predicate; the remaining artifact stays opaque.
    (
        ("full_result", "equity_distribution", "status"),
        ResultPathDisposition.CARRY_PREDICATE_OPERAND,
    ),
    *(
        (
            ("full_result", "equity_distribution", _name),
            ResultPathDisposition.OPAQUE_ARTIFACT,
        )
        for _name in (
            "success",
            "scenario_name",
            "equity_irr",
            "distributions",
            "audit",
            "equity_cashflows_usd",
            "annual_distributions",
            "equity_summary",
            "metadata",
        )
    ),
    # Structured FX and manifest projections.
    *(
        (
            ("full_result", "fx_integration", _name),
            ResultPathDisposition.STRUCTURED_PROJECTION,
        )
        for _name in (
            "attempted",
            "succeeded",
            "warning",
            "degraded",
            "degraded_reasons",
        )
    ),
    *(
        (
            ("full_result", "run_manifest", _name),
            ResultPathDisposition.MANIFEST_PROJECTION,
        )
        for _name in (
            "config_sha256",
            "engine_version",
            "git_sha",
            "generated_at",
            "seed",
            "validation_mode",
            "manifest_schema_version",
        )
    ),
    # Optional structured ScenarioResult children.
    *(
        (
            ("full_result", "scenario_result", "wacc", _name),
            ResultPathDisposition.KNOWN_REFUSED,
        )
        for _name in ("base", "prudential_rate", "meta")
    ),
    *(
        (
            ("full_result", "scenario_result", "equity_performance", _name),
            ResultPathDisposition.KNOWN_REFUSED,
        )
        for _name in ("equity_npv", "equity_multiple", "metadata")
    ),
    # The annual artifact is inspected only for closed key drift and CFADS presence.
    *(
        (
            ("full_result", "annual_rows", "*", _name),
            (
                ResultPathDisposition.CARRY_PREDICATE_OPERAND
                if _name == "cfads_usd"
                else ResultPathDisposition.OPAQUE_ARTIFACT
            ),
        )
        for _name in (
            "year",
            "gross_kwh",
            "grid_loss",
            "net_kwh",
            "revenue_lkr",
            "generation_revenue_lkr",
            "bess_revenue_lkr",
            "success_fee_lkr",
            "env_surcharge_lkr",
            "social_levy_lkr",
            "total_statutory_deductions_lkr",
            "opex_usd",
            "fx_rate",
            "opex_lkr",
            "senior_fee_lkr",
            "ebitda_lkr",
            "pretax_cfads_lkr",
            "total_depreciation_lkr",
            "interest_expense_lkr",
            "taxable_income_lkr",
            "tax_lkr",
            "posttax_cfads_lkr",
            "risk_haircut_pct",
            "risk_haircut_amount_lkr",
            "bess_augmentation_capex_lkr",
            "cfads_final_lkr",
            "cfads_risk_adjusted_lkr",
            "revenue_usd",
            "cfads_usd",
            "effective_tax_rate",
            "tax_holiday_applied",
            "carried_forward_losses",
            "wht_on_interest",
            "cf_pre_debt",
            "debt_service_total",
            "interest_usd",
            "balloon_resolution",
            "cf_after_debt",
        )
    ),
):
    _declare_path(_path, _disposition)

D3C_RESULT_PATH_DISPOSITIONS: Final[Mapping[tuple[str, ...], ResultPathDisposition]] = (
    MappingProxyType(dict(_path_dispositions))
)

_inspected_keys: dict[tuple[str, ...], set[str]] = {}
for _known_path in D3C_RESULT_PATH_DISPOSITIONS:
    _inspected_keys.setdefault(_known_path[:-1], set()).add(_known_path[-1])
D3C_INSPECTED_LAYER_KEYS: Final[Mapping[tuple[str, ...], frozenset[str]]] = (
    MappingProxyType(
        {_container: frozenset(_keys) for _container, _keys in _inspected_keys.items()}
    )
)

D3C_ARTIFACT_ONLY_PATHS: Final[Mapping[tuple[str, ...], tuple[str, ...]]] = (
    MappingProxyType(
        {
            ("full_result", "metrics"): (_S20,),
            ("full_result", "scenario_result", "metadata"): (_S20,),
            ("full_result", "scenario_result", "fx_curve"): (_S13,),
            ("full_result", "debt_result", "dscr_by_year"): (_S12,),
            ("full_result", "debt_result", "debt_schedules"): (_S12,),
            ("full_result", "debt_result", "funding"): (_S12,),
        }
    )
)

D3C_KNOWN_REFUSED_PATHS: Final[Mapping[tuple[str, ...], tuple[str, ...]]] = (
    MappingProxyType(
        {
            ("full_result", "debt_result", "total_idc_m"): (_S12,),
            ("full_result", "kpis", "npv"): (_S14,),
            ("full_result", "kpis", "irr"): (_S14,),
            ("full_result", "kpis", "total_idc_usd"): (_S12,),
            ("full_result", "kpis", "fx_match_ratio"): (_S13,),
            ("full_result", "kpis", "hedging_coverage_pct"): (_S13,),
            ("full_result", "kpis", "var_95_usd_million"): (_S13,),
            ("full_result", "kpis", "cvar_95_usd_million"): (_S13,),
        }
    )
)

D3C_SECTION_IDS: Final[tuple[str, ...]] = FEASIBILITY_SECTION_IDS

for _declared_route in D3C_RESULT_FIELD_ROUTES:
    if any(
        section_id not in D3C_SECTION_IDS for section_id in _declared_route.section_ids
    ):  # pragma: no cover - import-time static invariant
        raise RuntimeError("D3C result route references a non-taxonomy section")
    for _declared_path in (
        _declared_route.source_path,
        *_declared_route.mirror_paths,
    ):
        _declared_container = _declared_path[:-1]
        if (
            _declared_container not in D3C_INSPECTED_LAYER_KEYS
            or _declared_path[-1] not in D3C_INSPECTED_LAYER_KEYS[_declared_container]
        ):  # pragma: no cover - import-time static invariant
            raise RuntimeError(
                "D3C result route lacks a closed inspected-container catalogue"
            )


_SECTION_DEPENDENCIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "executive_investment_thesis": ("dependency:authorized_human_conclusion",),
        "project_description_and_structure": ("dependency:project_case",),
        "site_land_permits_legal_status": ("dependency:governed_legal_permit_sources",),
        "resource_and_energy_yield": ("dependency:accepted_resource_assessment",),
        "technology_selection_design_basis": ("dependency:governed_design_basis",),
        "grid_interconnection_curtailment": ("dependency:accepted_grid_outputs",),
        "construction_logistics_plan": (
            "dependency:governed_construction_logistics_sources",
        ),
        "environmental_social_summary": (
            "dependency:governed_environmental_social_sources",
        ),
        "climate_resilience_assessment": (
            "dependency:governed_climate_resilience_sources",
        ),
        "capex_opex_contingency_procurement": (
            "dependency:project_case.costs",
            "dependency:annual_rows_artifact",
        ),
        "revenue_ppa_tariff_assumptions": (
            "dependency:governed_tariff_offtake_sources",
        ),
        "financing_plan_debt_sizing": ("dependency:d3c2_authority_binding",),
        "tax_fx_inflation_accounting": ("dependency:project_case.currency_conversion",),
        "base_case_financial_outputs": ("dependency:d3c2_authority_binding",),
        "sensitivity_downside_cases": ("dependency:accepted_sensitivity_result",),
        "monte_carlo_risk_distribution": ("dependency:accepted_monte_carlo_result",),
        "optimization_alternatives_analysis": (
            "dependency:accepted_optimization_result",
        ),
        "risk_register_and_mitigations": ("dependency:governed_risk_sources",),
        "decision_checklist_conditions_precedent": (
            "dependency:authorized_decision_records",
        ),
        "appendices_provenance_audit_trail": (
            "dependency:d3c2_complete_register_graph",
        ),
    }
)
if tuple(_SECTION_DEPENDENCIES) != D3C_SECTION_IDS:  # pragma: no cover
    raise RuntimeError("D3C section dependency order differs from the taxonomy SSOT")


class CarriedResultObservation(StrictFrozenModel):
    """One single-homed scalar observation with exact upstream numeric identity."""

    state: Literal[ResultObservationState.CARRIED]
    observation_id: ExactStableId
    route_id: ExactStableId
    source_path: ExactPath
    section_ids: tuple[ExactStableId, ...]
    source_scalar_kind: ResultScalarKind
    value_type: ResultValueType
    value_text: ExactText
    unit: ExactText
    meaningful_precision: Annotated[int, Strict(), Field(ge=0, le=18)]
    precision_policy: Literal[ResultPrecisionPolicy.REVIEWED_FIELD_TABLE_V1]
    output_class: Literal[ResultObservationClass.ENGINE_RESULT_OBSERVATION]
    binary64_hex: ExactBinary64Hex | None
    binary64_bytes_hex: ExactBinary64Bytes | None

    @model_validator(mode="after")
    def _matches_static_route(self) -> "CarriedResultObservation":
        route = _ROUTE_INDEX.get(self.route_id)
        if route is None:
            raise ValueError("carried observation references an unknown static route")
        if (
            self.observation_id != f"observation:{route.route_id}"
            or self.source_path != route.source_path
            or self.section_ids != route.section_ids
            or self.source_scalar_kind is not route.scalar_kind
            or self.value_type is not route.value_type
            or self.unit != route.unit
            or self.meaningful_precision != route.meaningful_precision
            or self.precision_policy is not route.precision_policy
            or self.output_class is not route.output_class
        ):
            raise ValueError("carried observation differs from its static route")
        if self.source_scalar_kind is ResultScalarKind.BINARY64:
            if self.binary64_hex is None or self.binary64_bytes_hex is None:
                raise ValueError("binary64 observation requires both exact identities")
            try:
                decimal_value = Decimal(self.value_text)
                projected = float(decimal_value)
            except (InvalidOperation, OverflowError, ValueError) as exc:
                raise ValueError("binary64 decimal projection is invalid") from exc
            if (
                not decimal_value.is_finite()
                or not math.isfinite(projected)
                or projected.hex() != self.binary64_hex
                or struct.pack(">d", projected).hex() != self.binary64_bytes_hex
            ):
                raise ValueError(
                    "decimal observation does not preserve binary64 identity"
                )
        elif (
            _INTEGER_TEXT_RE.fullmatch(self.value_text) is None
            or self.binary64_hex is not None
            or self.binary64_bytes_hex is not None
        ):
            raise ValueError("integer observation requires canonical integer text only")
        return self


class UnavailableResultObservation(StrictFrozenModel):
    """One explicit non-carried outcome for a declared static route candidate."""

    state: Literal[
        ResultObservationState.AMBIGUOUS_DEFAULT,
        ResultObservationState.UPSTREAM_NONE,
        ResultObservationState.NOT_COMPUTED,
        ResultObservationState.NOT_REPRESENTABLE,
    ]
    observation_id: ExactStableId
    route_id: ExactStableId
    source_path: ExactPath
    section_ids: tuple[ExactStableId, ...]
    missing_item: ExactText
    consequence: ExactText
    remedy: ExactText
    unresolved_dependency_ids: tuple[ExactStableId, ...]
    observed_scalar_text: ExactText | None
    observed_binary64_hex: ExactBinary64Hex | None
    observed_binary64_bytes_hex: ExactBinary64Bytes | None

    @model_validator(mode="after")
    def _matches_static_route(self) -> "UnavailableResultObservation":
        route = _ROUTE_INDEX.get(self.route_id)
        if route is None:
            raise ValueError(
                "unavailable observation references an unknown static route"
            )
        if (
            self.observation_id != f"observation:{route.route_id}"
            or self.source_path != route.source_path
            or self.section_ids != route.section_ids
        ):
            raise ValueError("unavailable observation differs from its static route")
        if len(set(self.unresolved_dependency_ids)) != len(
            self.unresolved_dependency_ids
        ):
            raise ValueError("unavailable observation has duplicate dependencies")
        if self.state is ResultObservationState.AMBIGUOUS_DEFAULT:
            if (
                self.observed_scalar_text not in {"0", "-0"}
                or self.observed_binary64_hex
                not in {
                    "0x0.0p+0",
                    "-0x0.0p+0",
                }
                or self.observed_binary64_bytes_hex
                not in {"0000000000000000", "8000000000000000"}
            ):
                raise ValueError(
                    "ambiguous-default observation must preserve exact binary64 zero"
                )
        elif (
            self.observed_scalar_text is not None
            or self.observed_binary64_hex is not None
            or self.observed_binary64_bytes_hex is not None
        ):
            raise ValueError(
                "only ambiguous-default observations may retain an uncarried scalar"
            )
        return self


RouteObservation: TypeAlias = Annotated[
    Union[CarriedResultObservation, UnavailableResultObservation],
    Field(discriminator="state"),
]


class ExcludedResultField(StrictFrozenModel):
    """A known field deliberately kept artifact-only or refused."""

    state: Literal[
        ResultObservationState.ARTIFACT_ONLY,
        ResultObservationState.KNOWN_REFUSED,
    ]
    observation_id: ExactStableId
    source_path: ExactPath
    section_candidate_ids: tuple[ExactStableId, ...]
    observed_present: Annotated[bool, Strict()]
    consequence: ExactText
    remedy: ExactText

    @model_validator(mode="after")
    def _identity_matches_path(self) -> "ExcludedResultField":
        if self.observation_id != "excluded:" + ".".join(self.source_path):
            raise ValueError("excluded-field identity must derive from its exact path")
        return self


class UnrecognizedUpstreamKey(StrictFrozenModel):
    """One present undeclared key, surfaced without inspecting or serializing its value."""

    state: Literal[ResultObservationState.UNRECOGNIZED]
    observation_id: ExactStableId
    container_path: ExactPath
    key_type: ResultUnknownKeyType
    key_identity: ExactText
    binary64_hex: ExactBinary64Hex | None
    binary64_bytes_hex: ExactBinary64Bytes | None
    consequence: Literal[
        "The present upstream key has no reviewed D3C-1a route and was not carried."
    ]
    remedy: Literal[
        "Review and add an explicit versioned route or an explicit refusal before use."
    ]

    @model_validator(mode="after")
    def _key_identity_is_exact(self) -> "UnrecognizedUpstreamKey":
        if self.key_type is ResultUnknownKeyType.BINARY64:
            if (
                self.binary64_hex is None
                or self.binary64_bytes_hex is None
                or self.key_identity != self.binary64_hex
                or struct.pack(">d", float.fromhex(self.binary64_hex)).hex()
                != self.binary64_bytes_hex
            ):
                raise ValueError("binary64 unknown key requires both exact identities")
        elif self.binary64_hex is not None or self.binary64_bytes_hex is not None:
            raise ValueError("non-binary64 unknown key forbids binary64 identity")
        elif self.key_type is ResultUnknownKeyType.INTEGER:
            if _INTEGER_TEXT_RE.fullmatch(self.key_identity) is None:
                raise ValueError("integer unknown key requires canonical integer text")
        elif self.key_type is ResultUnknownKeyType.BOOLEAN:
            if self.key_identity not in {"true", "false"}:
                raise ValueError("boolean unknown key requires exact boolean identity")
        return self


class SectionResultProjection(StrictFrozenModel):
    """Route candidates and unresolved dependencies only, never section status."""

    section_id: ExactStableId
    candidate_route_ids: tuple[ExactStableId, ...]
    unresolved_dependency_ids: tuple[ExactStableId, ...]

    @model_validator(mode="after")
    def _references_are_unique(self) -> "SectionResultProjection":
        if self.section_id not in D3C_SECTION_IDS:
            raise ValueError(
                "section projection references an unknown taxonomy section"
            )
        if len(set(self.candidate_route_ids)) != len(self.candidate_route_ids):
            raise ValueError("section projection contains duplicate route IDs")
        if len(set(self.unresolved_dependency_ids)) != len(
            self.unresolved_dependency_ids
        ):
            raise ValueError("section projection contains duplicate dependencies")
        return self


class OriginInvariantProjection(StrictFrozenModel):
    """Exact D3B origin facts independently revalidated before scalar mapping."""

    gateway_call_count: Literal[1]
    full_status: Literal["success"]
    full_config_path: Literal["<inline>"]
    scenario_config_path: Literal["<inline>"]
    full_validation_mode: Literal["strict"]
    scenario_validation_mode: Literal["strict"]
    duplicated_origins_exact: Literal[True]
    evaluated_config_digest_verified: Literal[True]
    manifest_identity_verified: Literal[True]
    gateway_warnings_present: Annotated[bool, Strict()]


class AuthoredNumericProjection(StrictFrozenModel):
    """Exact authored JSON-number identity retained from a D3B receipt."""

    json_type: Literal["integer", "binary64"]
    authored_value: ExactText
    binary64_hex: ExactBinary64Hex
    binary64_bytes_hex: ExactBinary64Bytes

    @model_validator(mode="after")
    def _authored_identity_is_exact(self) -> "AuthoredNumericProjection":
        projected = float.fromhex(self.binary64_hex)
        if struct.pack(">d", projected).hex() != self.binary64_bytes_hex:
            raise ValueError("authored numeric binary64 identities differ")
        if self.json_type == "integer":
            if _INTEGER_TEXT_RE.fullmatch(self.authored_value) is None:
                raise ValueError("authored integer must use canonical JSON text")
            try:
                authored_projection = float(int(self.authored_value))
            except (OverflowError, ValueError) as exc:
                raise ValueError("authored integer is outside binary64") from exc
        else:
            try:
                authored_projection = float(self.authored_value)
            except ValueError as exc:
                raise ValueError("authored binary64 text is invalid") from exc
            if repr(authored_projection) != self.authored_value:
                raise ValueError("authored binary64 text must be canonical")
        if (
            not math.isfinite(authored_projection)
            or authored_projection.hex() != self.binary64_hex
        ):
            raise ValueError("authored numeric text and binary64 identity differ")
        return self


class NumericProjectionReceiptProjection(StrictFrozenModel):
    """Non-authoritative lossless projection of one D3B numeric receipt."""

    assertion_id: ExactStableId
    project_decimal: ExactText
    projected_binary64_hex: ExactBinary64Hex
    projected_binary64_bytes_hex: ExactBinary64Bytes
    authored_values: Annotated[
        tuple[AuthoredNumericProjection, ...], Field(min_length=1, max_length=2)
    ]

    @model_validator(mode="after")
    def _receipt_identity_is_exact(self) -> "NumericProjectionReceiptProjection":
        try:
            decimal_value = Decimal(self.project_decimal)
            decimal_projection = float(decimal_value)
        except (InvalidOperation, OverflowError, ValueError) as exc:
            raise ValueError("numeric receipt Decimal text is invalid") from exc
        projected = float.fromhex(self.projected_binary64_hex)
        if (
            not decimal_value.is_finite()
            or not math.isfinite(decimal_projection)
            or decimal_projection.hex() != self.projected_binary64_hex
            or struct.pack(">d", projected).hex() != self.projected_binary64_bytes_hex
            or (decimal_value != 0 and projected == 0.0)
        ):
            raise ValueError(
                "numeric receipt does not preserve Decimal/binary64 identity"
            )
        if any(
            item.binary64_hex != self.projected_binary64_hex
            or item.binary64_bytes_hex != self.projected_binary64_bytes_hex
            for item in self.authored_values
        ):
            raise ValueError("numeric receipt authored values disagree with projection")
        if any(
            item.json_type == "integer"
            and Decimal(item.authored_value) != decimal_value
            for item in self.authored_values
        ):
            raise ValueError("authored integer and ProjectCase Decimal differ")
        return self


class FxIntegrationProjection(StrictFrozenModel):
    """Exact structured FX integration disclosure from the accepted result."""

    attempted: Annotated[bool, Strict()]
    succeeded: Annotated[bool, Strict()]
    warning: ExactWarningText | None
    degraded: Annotated[bool, Strict()]
    degraded_reasons: Annotated[
        tuple[ExactWarningText, ...], Field(max_length=_MAX_WARNINGS)
    ]

    @field_validator("degraded_reasons", mode="before")
    @classmethod
    def _reasons_are_an_exact_tuple(cls, value: object, info: ValidationInfo) -> object:
        if info.mode == "json" and type(value) is list:
            return tuple(value)
        if type(value) is not tuple:
            raise ValueError("FX degraded reasons must be an exact tuple")
        return value

    @model_validator(mode="after")
    def _fx_disclosure_is_coherent(self) -> "FxIntegrationProjection":
        if (
            not self.attempted
            or (self.succeeded and self.warning is not None)
            or (not self.succeeded and self.warning is None)
            or self.degraded != bool(self.degraded_reasons)
        ):
            raise ValueError("FX integration disclosure is internally inconsistent")
        return self


class EngineManifestProjection(StrictFrozenModel):
    """Exact observed engine fields; explicitly not the D2 package RunManifest."""

    config_sha256: ExactSha256
    engine_version: ExactText
    git_sha: ExactGitCommit
    generated_at: ExactUtcTimestamp
    seed: (
        Annotated[
            int,
            Strict(),
            Field(ge=-_MAX_BOUNDED_INTEGER, le=_MAX_BOUNDED_INTEGER),
        ]
        | None
    )
    validation_mode: Literal["strict"]
    manifest_schema_version: ExactText

    @field_validator("seed", mode="before")
    @classmethod
    def _seed_is_exact_and_bounded(cls, value: object) -> object:
        return _bounded_seed(value)

    @field_serializer("seed", return_type=_BoundedSeedSerialization | None)
    def _serialize_bounded_seed(self, value: int | None) -> int | None:
        return _bounded_seed(value)

    @model_validator(mode="after")
    def _engine_identity_is_current(self) -> "EngineManifestProjection":
        if (
            self.engine_version != ENGINE_VERSION_IDENTITY
            or self.manifest_schema_version != MANIFEST_SCHEMA_VERSION_IDENTITY
        ):
            raise ValueError(
                "engine manifest version differs from the import-safe current identity"
            )
        return self


class ProjectionLimitation(StrictFrozenModel):
    """A structural limitation that cannot be omitted from the projection."""

    code: Literal["upstream_warning_channel_not_exhaustive"]
    statement: Literal[
        "The exact D3B warning tuple and FX degradation facts are preserved, but "
        "D3C-1a cannot prove that every upstream warning channel is represented."
    ]
    consequence: Literal[
        "Absence from returned_warnings cannot be interpreted as absence of all warnings."
    ]
    remedy: Literal[
        "A later governed contract must prove exhaustive warning-channel coverage before "
        "making a completeness claim."
    ]


class D3CResultProjection(StrictFrozenModel):
    """Strict result-only observation of one accepted D3B execution success."""

    schema_id: Literal["dutchbay.section_result_facade.v1"]
    contract_version: Literal["1.0.0"]
    authority_status: Literal["non_authoritative"]
    source_contract: Literal["analytics.contracts_v14.D3BExecutionSuccess"]
    source_outcome: Literal["success", "degraded_success"]
    request_id: ExactStableId
    project_id: ExactStableId
    case_id: ExactStableId
    project_case_revision: Annotated[
        int,
        Strict(),
        Field(ge=1, le=_MAX_BOUNDED_INTEGER),
    ]
    project_case_sha256: ExactSha256
    evaluation_request_sha256: ExactSha256
    source_file_sha256: ExactSha256
    resolved_config_sha256: ExactSha256
    evaluated_config_sha256: ExactSha256
    authority_id: ExactStableId
    config_id: ExactStableId
    evidence_cutoff: date
    valuation_date: date
    validation_modules: Annotated[
        tuple[ExactText, ...], Field(min_length=1, max_length=16)
    ]
    origin_invariants: OriginInvariantProjection
    numeric_projection_receipts: Annotated[
        tuple[NumericProjectionReceiptProjection, ...],
        Field(max_length=_MAX_NUMERIC_PROJECTION_RECEIPTS),
    ]
    gateway_warnings: Annotated[tuple[str, ...], Field(max_length=_MAX_WARNINGS)]
    returned_warnings: Annotated[tuple[str, ...], Field(max_length=_MAX_WARNINGS)]
    fx_degraded: Annotated[bool, Strict()]
    fx_integration: FxIntegrationProjection
    engine_manifest: EngineManifestProjection
    sections: Annotated[
        tuple[SectionResultProjection, ...], Field(min_length=20, max_length=20)
    ]
    route_observations: Annotated[
        tuple[RouteObservation, ...],
        Field(
            min_length=len(D3C_RESULT_FIELD_ROUTES),
            max_length=len(D3C_RESULT_FIELD_ROUTES),
        ),
    ]
    excluded_fields: Annotated[
        tuple[ExcludedResultField, ...], Field(max_length=_MAX_RECORDS)
    ]
    unrecognized_keys: Annotated[
        tuple[UnrecognizedUpstreamKey, ...], Field(max_length=_MAX_RECORDS)
    ]
    limitations: Annotated[
        tuple[ProjectionLimitation, ...], Field(min_length=1, max_length=1)
    ]

    @field_validator("project_case_revision", mode="before")
    @classmethod
    def _revision_is_exact_and_bounded(cls, value: object) -> object:
        return _bounded_revision(value)

    @field_serializer(
        "project_case_revision", return_type=_BoundedRevisionSerialization
    )
    def _serialize_bounded_revision(self, value: int) -> int:
        return _bounded_revision(value)

    @field_validator("gateway_warnings", "returned_warnings", mode="before")
    @classmethod
    def _warnings_are_exact_and_bounded(
        cls, value: object, info: ValidationInfo
    ) -> object:
        if info.mode == "json" and type(value) is list:
            value = tuple(value)
        if type(value) is not tuple:
            raise ValueError("warning projections must be exact tuples")
        warnings = value
        if any(type(item) is not str for item in warnings):
            raise ValueError("warning projections must contain exact strings")
        if any(_contains_unicode_surrogate(item) for item in warnings):
            raise ValueError(
                "warning projections must contain Unicode scalar-value strings"
            )
        if sum(len(item) for item in warnings) > _MAX_WARNING_TEXT:
            raise ValueError("warning projections exceed the projection text bound")
        return value

    @model_validator(mode="after")
    def _projection_graph_is_exact(self) -> "D3CResultProjection":
        if self.source_outcome == "success" and (
            self.returned_warnings or self.fx_degraded
        ):
            raise ValueError("success projection cannot hide warning/degradation facts")
        if self.source_outcome == "degraded_success" and not (
            self.returned_warnings or self.fx_degraded
        ):
            raise ValueError("degraded projection requires warning/degradation facts")
        expected_returned_warnings = (
            *self.gateway_warnings,
            *(
                (self.fx_integration.warning,)
                if self.fx_integration.warning is not None
                else ()
            ),
            *self.fx_integration.degraded_reasons,
        )
        if self.returned_warnings != expected_returned_warnings:
            raise ValueError(
                "returned warnings differ from their exact FX/gateway origins"
            )
        expected_fx_degraded = bool(self.returned_warnings) or (
            not self.fx_integration.succeeded or self.fx_integration.degraded
        )
        if self.fx_degraded is not expected_fx_degraded:
            raise ValueError("FX degradation differs from its exact structured origins")
        if tuple(section.section_id for section in self.sections) != D3C_SECTION_IDS:
            raise ValueError("projection sections differ from the taxonomy SSOT order")
        expected_section_routes = {
            section_id: tuple(
                route.route_id
                for route in D3C_RESULT_FIELD_ROUTES
                if section_id in route.section_ids
            )
            for section_id in D3C_SECTION_IDS
        }
        for section in self.sections:
            if (
                section.candidate_route_ids
                != expected_section_routes[section.section_id]
            ):
                raise ValueError(
                    "section candidate routes differ from the static mapping"
                )
            if (
                section.unresolved_dependency_ids
                != _SECTION_DEPENDENCIES[section.section_id]
            ):
                raise ValueError("section dependencies differ from the static mapping")
        route_ids = tuple(item.route_id for item in self.route_observations)
        if route_ids != tuple(route.route_id for route in D3C_RESULT_FIELD_ROUTES):
            raise ValueError(
                "projection must contain one ordered observation per static route"
            )
        observation_ids = tuple(
            item.observation_id
            for item in (
                *self.route_observations,
                *self.excluded_fields,
                *self.unrecognized_keys,
            )
        )
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError(
                "projection observation identities must be globally unique"
            )
        expected_excluded = (
            *(
                (ResultObservationState.ARTIFACT_ONLY, path, section_ids)
                for path, section_ids in D3C_ARTIFACT_ONLY_PATHS.items()
            ),
            *(
                (ResultObservationState.KNOWN_REFUSED, path, section_ids)
                for path, section_ids in D3C_KNOWN_REFUSED_PATHS.items()
            ),
        )
        actual_excluded = tuple(
            (item.state, item.source_path, item.section_candidate_ids)
            for item in self.excluded_fields
        )
        if actual_excluded != expected_excluded:
            raise ValueError(
                "projection excluded fields differ from the static catalogue"
            )
        if self.engine_manifest.config_sha256 != self.evaluated_config_sha256:
            raise ValueError("engine manifest digest must match the evaluated config")
        if len(set(self.validation_modules)) != len(self.validation_modules):
            raise ValueError("validation modules must be unique")
        receipt_ids = tuple(
            item.assertion_id for item in self.numeric_projection_receipts
        )
        if len(set(receipt_ids)) != len(receipt_ids):
            raise ValueError("numeric projection receipt identities must be unique")
        unknown_locations = tuple(
            (item.container_path, item.key_type, item.key_identity)
            for item in self.unrecognized_keys
        )
        if len(set(unknown_locations)) != len(unknown_locations):
            raise ValueError("unrecognized upstream-key locations must be unique")
        if tuple(item.code for item in self.limitations) != (
            RESULT_FACADE_WARNING_LIMITATION_CODE,
        ):
            raise ValueError("projection must retain the warning-channel limitation")
        return self


def result_section_projections() -> tuple[SectionResultProjection, ...]:
    """Return the immutable static twenty-section route/dependency projection."""

    return tuple(
        SectionResultProjection(
            section_id=section_id,
            candidate_route_ids=tuple(
                route.route_id
                for route in D3C_RESULT_FIELD_ROUTES
                if section_id in route.section_ids
            ),
            unresolved_dependency_ids=_SECTION_DEPENDENCIES[section_id],
        )
        for section_id in D3C_SECTION_IDS
    )


__all__ = (
    "D3C_ARTIFACT_ONLY_PATHS",
    "D3C_INSPECTED_LAYER_KEYS",
    "D3C_KNOWN_REFUSED_PATHS",
    "D3C_RESULT_FIELD_ROUTES",
    "D3C_RESULT_PATH_DISPOSITIONS",
    "D3C_SECTION_IDS",
    "RESULT_FACADE_AUTHORITY_STATUS",
    "RESULT_FACADE_CONTRACT_VERSION",
    "RESULT_FACADE_SCHEMA_ID",
    "RESULT_FACADE_SOURCE_CONTRACT",
    "RESULT_FACADE_WARNING_LIMITATION_CODE",
    "AuthoredNumericProjection",
    "CarriedResultObservation",
    "D3CResultProjection",
    "EngineManifestProjection",
    "ExcludedResultField",
    "FxIntegrationProjection",
    "NumericProjectionReceiptProjection",
    "OriginInvariantProjection",
    "ProjectionLimitation",
    "ResultCarryPredicate",
    "ResultFieldRoute",
    "ResultObservationClass",
    "ResultObservationState",
    "ResultPathDisposition",
    "ResultPrecisionPolicy",
    "ResultScalarKind",
    "ResultUnknownKeyType",
    "ResultValueType",
    "ResultZeroPolicy",
    "RouteObservation",
    "SectionResultProjection",
    "UnavailableResultObservation",
    "UnrecognizedUpstreamKey",
    "result_section_projections",
)
