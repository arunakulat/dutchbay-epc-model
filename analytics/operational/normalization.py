"""Deterministic operational-table normalization and QA receipts (#1332 D2).

The normalizer consumes immutable CSV bytes already described by a D1
``OperationalDatasetEvidence`` envelope.  It verifies the envelope rather than
guessing around it: every source column is mapped or explicitly excluded, units
are already canonical, timestamps follow the declared treatment, and cadence is
checked without filling, resampling, sorting, or converting measurements.

This module is deliberately dependency-free.  OpenOA remains a comparator, not
an authority or runtime dependency, and nothing here calculates operational AEP,
losses, capacity factor, or finance outputs.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from importlib import metadata
from typing import Any, Final, Literal, TypeAlias
from zoneinfo import ZoneInfo

from analytics.operational.contracts import (
    OperationalColumnBinding,
    OperationalDatasetEvidence,
)

OPERATIONAL_NORMALIZATION_SCHEMA: Final = "dutchbay.operational_normalization.v1"
OPERATIONAL_AGGREGATION_SCHEMA: Final = "dutchbay.operational_aggregation.v1"
_NORMALIZER_VERSION: Final = "operational_csv_normalizer_v1"
_AGGREGATOR_VERSION: Final = "operational_utc_aggregator_v1"
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_OFFSET_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?" r"(?:Z|[+-]\d{2}:\d{2})$"
)
_LOCAL_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

OperationalNormalizationErrorCode: TypeAlias = Literal[
    "SOURCE_DIGEST_MISMATCH",
    "LINEAGE_DIGEST_MISMATCH",
    "INVALID_CSV",
    "COLUMN_ACCOUNTING_FAILED",
    "ROW_ACCOUNTING_FAILED",
    "INVALID_VALUE",
    "TIMEZONE_NORMALIZATION_FAILED",
    "QUALITY_CHECK_FAILED",
    "AGGREGATION_CONTRACT_FAILED",
]
OperationalAggregationMethod: TypeAlias = Literal["sum", "mean"]

_NUMERIC_ROLES = frozenset(
    {
        "energy_kwh",
        "power_kw",
        "wind_speed_ms",
        "wind_direction_deg",
        "air_density_kgm3",
        "air_temperature_c",
        "availability_loss_kwh",
        "curtailment_loss_kwh",
        "rated_power_kw",
        "latitude_deg",
        "longitude_deg",
    }
)
_TEXT_ROLES = frozenset({"asset_id", "status_code"})


@dataclass(frozen=True)
class OperationalColumnExclusion:
    """An explicit decision not to carry one source column into the artifact."""

    source_column: str
    reason: str

    def __post_init__(self) -> None:
        _require_closed_text(self.source_column, "source_column")
        _require_closed_text(self.reason, "reason")

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationalRowExclusion:
    """An explicit exclusion of a one-based CSV data-row number."""

    source_row_number: int
    reason: str

    def __post_init__(self) -> None:
        if type(self.source_row_number) is not int or self.source_row_number < 1:
            raise ValueError("source_row_number must be a positive integer.")
        _require_closed_text(self.reason, "reason")

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationalExcludedRowReceipt:
    source_row_number: int
    reason: str
    parsed_row_sha256: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationalQualityReceipt:
    """Stable facts produced by one normalization attempt."""

    schema: str
    logical_id: str
    kind: str
    source_locator: str
    source_sha256: str
    observation_status: str
    lineage_source_sha256: tuple[str, ...]
    derivation_method_sha256: str | None
    lineage_verified: bool
    normalized_sha256: str | None
    method_sha256: str
    timezone_treatment: str
    source_timezone: str | None
    ambiguous_time_policy: str
    nonexistent_time_policy: str
    timezone_database: str | None
    interval_basis: str
    interval_seconds: int | None
    raw_row_count: int
    included_row_count: int
    excluded_row_count: int
    source_columns: tuple[str, ...]
    normalized_roles: tuple[str, ...]
    column_bindings: tuple[OperationalColumnBinding, ...]
    column_exclusions: tuple[OperationalColumnExclusion, ...]
    row_exclusions: tuple[OperationalExcludedRowReceipt, ...]
    actual_coverage_start_utc: str | None
    actual_coverage_end_utc: str | None
    coverage_mismatch_count: int
    duplicate_key_count: int
    gap_count: int
    interval_drift_count: int
    nonfinite_value_count: int
    invalid_value_count: int
    ambiguous_time_resolution_count: int
    nonexistent_time_resolution_count: int
    findings: tuple[str, ...]
    quality_passed: bool
    raw_evidence_only: bool = True
    canonical_finance_eligible: bool = False
    bankable: bool = False
    lender_eligible: bool = False
    board_eligible: bool = False

    def __post_init__(self) -> None:
        if self.schema != OPERATIONAL_NORMALIZATION_SCHEMA:
            raise ValueError("quality receipt schema is not supported.")
        for field_name in ("source_sha256", "method_sha256"):
            if _SHA256_RE.fullmatch(getattr(self, field_name)) is None:
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
        if (
            self.normalized_sha256 is not None
            and _SHA256_RE.fullmatch(self.normalized_sha256) is None
        ):
            raise ValueError("normalized_sha256 must be null or a lowercase digest.")
        for digest in self.lineage_source_sha256:
            if _SHA256_RE.fullmatch(digest) is None:
                raise ValueError("lineage_source_sha256 contains an invalid digest.")
        if (
            self.derivation_method_sha256 is not None
            and _SHA256_RE.fullmatch(self.derivation_method_sha256) is None
        ):
            raise ValueError("derivation_method_sha256 must be null or a digest.")
        if type(self.lineage_verified) is not bool or not self.lineage_verified:
            raise ValueError("lineage_verified must be the exact boolean True.")
        counts = (
            self.raw_row_count,
            self.included_row_count,
            self.excluded_row_count,
            self.coverage_mismatch_count,
            self.duplicate_key_count,
            self.gap_count,
            self.interval_drift_count,
            self.nonfinite_value_count,
            self.invalid_value_count,
            self.ambiguous_time_resolution_count,
            self.nonexistent_time_resolution_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("quality receipt counts must be non-negative integers.")
        if self.raw_row_count != self.included_row_count + self.excluded_row_count:
            raise ValueError("raw rows must reconcile to included plus excluded rows.")
        if self.excluded_row_count != len(self.row_exclusions):
            raise ValueError("excluded row count must match its receipt tuple.")
        defects = any(
            (
                self.coverage_mismatch_count,
                self.duplicate_key_count,
                self.gap_count,
                self.interval_drift_count,
                self.nonfinite_value_count,
                self.invalid_value_count,
            )
        )
        if type(self.quality_passed) is not bool or self.quality_passed is defects:
            raise ValueError(
                "quality_passed must be exactly the inverse of QA defects."
            )
        if self.quality_passed and self.normalized_sha256 is None:
            raise ValueError("passing QA requires a normalized artifact digest.")
        exact_flags = {
            "raw_evidence_only": True,
            "canonical_finance_eligible": False,
            "bankable": False,
            "lender_eligible": False,
            "board_eligible": False,
        }
        for field_name, expected in exact_flags.items():
            value = getattr(self, field_name)
            if type(value) is not bool or value is not expected:
                raise ValueError(
                    f"{field_name} must be the exact boolean {expected!r}."
                )

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


@dataclass(frozen=True)
class OperationalNormalizationResult:
    """Immutable source and normalized artifacts plus their QA receipt."""

    evidence: OperationalDatasetEvidence
    source_bytes: bytes
    lineage_source_bytes: tuple[bytes, ...]
    derivation_method_bytes: bytes | None
    normalized_csv_bytes: bytes
    normalized_rows: tuple[tuple[str, ...], ...]
    receipt: OperationalQualityReceipt

    def __post_init__(self) -> None:
        if not self.receipt.quality_passed:
            raise ValueError("a normalization result requires a passing QA receipt.")
        if _sha256(self.source_bytes) != self.evidence.source_sha256:
            raise ValueError("source bytes do not match the D1 evidence digest.")
        if tuple(_sha256(item) for item in self.lineage_source_bytes) != (
            self.evidence.lineage_source_sha256
        ):
            raise ValueError("lineage source bytes do not match the D1 digest tuple.")
        if self.evidence.derivation_method_sha256 is None:
            if self.derivation_method_bytes is not None:
                raise ValueError("non-derived evidence cannot retain derivation bytes.")
        elif (
            self.derivation_method_bytes is None
            or _sha256(self.derivation_method_bytes)
            != self.evidence.derivation_method_sha256
        ):
            raise ValueError("derivation method bytes do not match the D1 digest.")
        if _sha256(self.normalized_csv_bytes) != self.receipt.normalized_sha256:
            raise ValueError("normalized bytes do not match the receipt digest.")
        if len(self.normalized_rows) != self.receipt.included_row_count:
            raise ValueError("normalized row count does not match the receipt.")


@dataclass(frozen=True)
class OperationalAggregationSpec:
    """An explicit UTC aggregation contract; never applied by normalization."""

    value_role: Literal["energy_kwh", "power_kw"]
    method: OperationalAggregationMethod
    target_interval_seconds: int
    anchor_utc: str
    source_timestamp_position: Literal["interval_start"]
    value_basis: Literal["interval_energy", "interval_average_power"]

    def __post_init__(self) -> None:
        if self.value_role not in {"energy_kwh", "power_kw"}:
            raise ValueError("value_role must be 'energy_kwh' or 'power_kw'.")
        expected = "sum" if self.value_role == "energy_kwh" else "mean"
        if self.method != expected:
            raise ValueError(
                f"{self.value_role} requires method={expected!r}; got {self.method!r}."
            )
        expected_basis = (
            "interval_energy"
            if self.value_role == "energy_kwh"
            else "interval_average_power"
        )
        if self.source_timestamp_position != "interval_start":
            raise ValueError("source_timestamp_position must be 'interval_start'.")
        if self.value_basis != expected_basis:
            raise ValueError(
                f"{self.value_role} requires value_basis={expected_basis!r}; "
                f"got {self.value_basis!r}."
            )
        if (
            type(self.target_interval_seconds) is not int
            or self.target_interval_seconds < 1
        ):
            raise ValueError("target_interval_seconds must be a positive integer.")
        _parse_canonical_utc(self.anchor_utc, "anchor_utc")

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationalAggregationReceipt:
    schema: str
    logical_id: str
    source_normalized_sha256: str
    aggregate_sha256: str
    method_sha256: str
    value_role: str
    value_unit: Literal["kWh", "kW"]
    method: str
    source_interval_seconds: int
    target_interval_seconds: int
    anchor_utc: str
    source_timestamp_position: Literal["interval_start"]
    value_basis: Literal["interval_energy", "interval_average_power"]
    input_row_count: int
    output_row_count: int
    timestamp_position: Literal["interval_start"] = "interval_start"
    utc_elapsed_time_basis: Literal[True] = True
    canonical_finance_eligible: Literal[False] = False
    bankable: Literal[False] = False
    lender_eligible: Literal[False] = False
    board_eligible: Literal[False] = False

    def __post_init__(self) -> None:
        if self.schema != OPERATIONAL_AGGREGATION_SCHEMA:
            raise ValueError("aggregation receipt schema is not supported.")
        for field_name in (
            "source_normalized_sha256",
            "aggregate_sha256",
            "method_sha256",
        ):
            if _SHA256_RE.fullmatch(getattr(self, field_name)) is None:
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
        for field_name in (
            "source_interval_seconds",
            "target_interval_seconds",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{field_name} must be a positive integer.")
        for field_name in ("input_row_count", "output_row_count"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")
        for field_name in (
            "canonical_finance_eligible",
            "bankable",
            "lender_eligible",
            "board_eligible",
        ):
            value = getattr(self, field_name)
            if type(value) is not bool or value is not False:
                raise ValueError(f"{field_name} must be the exact boolean False.")
        if (
            type(self.utc_elapsed_time_basis) is not bool
            or not self.utc_elapsed_time_basis
        ):
            raise ValueError("utc_elapsed_time_basis must be the exact boolean True.")

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationalAggregationResult:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    csv_bytes: bytes
    receipt: OperationalAggregationReceipt

    def __post_init__(self) -> None:
        if _sha256(self.csv_bytes) != self.receipt.aggregate_sha256:
            raise ValueError("aggregate bytes do not match the receipt digest.")
        if len(self.rows) != self.receipt.output_row_count:
            raise ValueError("aggregate row count does not match the receipt.")


class OperationalNormalizationError(ValueError):
    """A predictable CASPER error with an optional completed QA receipt."""

    def __init__(
        self,
        code: OperationalNormalizationErrorCode,
        message: str,
        *,
        receipt: OperationalQualityReceipt | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.receipt = receipt


@dataclass(frozen=True)
class _ParsedRow:
    source_row_number: int
    values: tuple[str, ...]
    role_values: dict[str, str]
    timestamp_utc: datetime | None
    source_wall_time: datetime | None
    group_key: str


def _require_closed_text(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\n" in value
        or "\r" in value
    ):
        raise ValueError(
            f"{field_name} must be non-empty text without surrounding whitespace or "
            "line breaks."
        )
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _method_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return _sha256(encoded)


def _format_utc(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    base = value.strftime("%Y-%m-%dT%H:%M:%S")
    if value.microsecond:
        base += f".{value.microsecond:06d}".rstrip("0")
    return base + "Z"


def _parse_canonical_utc(value: str, field_name: str) -> datetime:
    if not isinstance(value, str) or _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be an RFC3339 timestamp ending in 'Z'.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid UTC timestamp.") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field_name} must resolve to UTC.")
    return parsed


def _parse_naive_iso(value: str) -> datetime:
    if _LOCAL_TIMESTAMP_RE.fullmatch(value) is None:
        raise ValueError("timestamp is not valid ISO 8601 local time")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("timestamp is not valid ISO 8601 local time") from exc
    if parsed.tzinfo is not None:
        raise ValueError("named-zone timestamps must be naive local wall times")
    return parsed


def _parse_timestamp(
    value: str, evidence: OperationalDatasetEvidence
) -> tuple[datetime, datetime, bool, bool]:
    """Return UTC, source wall time, ambiguous-resolved, nonexistent-resolved."""

    if value.strip() != value or not value:
        raise ValueError("timestamp must be non-empty without surrounding whitespace")
    if evidence.timezone_treatment == "source_utc":
        parsed = _parse_canonical_utc(value, "timestamp_utc")
        return parsed, parsed.replace(tzinfo=None), False, False
    if evidence.timezone_treatment == "offset_aware_to_utc":
        if _OFFSET_TIMESTAMP_RE.fullmatch(value) is None:
            raise ValueError("timestamp is not valid offset-aware ISO 8601")
        try:
            parsed = datetime.fromisoformat(
                value[:-1] + "+00:00" if value.endswith("Z") else value
            )
        except ValueError as exc:
            raise ValueError("timestamp is not valid offset-aware ISO 8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("offset-aware treatment requires an explicit UTC offset")
        return (
            parsed.astimezone(timezone.utc),
            parsed.replace(tzinfo=None),
            False,
            False,
        )
    if evidence.timezone_treatment != "named_zone_to_utc":
        raise ValueError("timeseries evidence has no usable timezone treatment")

    wall = _parse_naive_iso(value)
    zone = ZoneInfo(str(evidence.source_timezone))
    candidates: list[tuple[int, datetime, datetime]] = []
    for fold in (0, 1):
        utc_value = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        roundtrip = utc_value.astimezone(zone).replace(tzinfo=None)
        candidates.append((fold, utc_value, roundtrip))
    valid = [item for item in candidates if item[2] == wall]
    unique_valid = {item[1] for item in valid}
    if len(unique_valid) == 1:
        return next(iter(unique_valid)), wall, False, False
    if len(unique_valid) == 2:
        policy = evidence.ambiguous_time_policy
        if policy == "reject":
            raise ValueError("ambiguous local timestamp rejected by evidence policy")
        wanted_fold = 0 if policy == "fold_0" else 1
        selected = next(item for item in valid if item[0] == wanted_fold)
        return selected[1], wall, True, False

    nonexistent_policy = evidence.nonexistent_time_policy
    if nonexistent_policy == "reject":
        raise ValueError("nonexistent local timestamp rejected by evidence policy")
    if nonexistent_policy == "shift_forward":
        selected = max(candidates, key=lambda item: item[2])
    else:
        selected = min(candidates, key=lambda item: item[2])
    return selected[1], selected[2], False, True


def _canonical_decimal(value: str) -> str:
    if value.strip() != value or not value:
        raise ValueError(
            "numeric value must be non-empty without surrounding whitespace"
        )
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("numeric value is not a decimal") from exc
    if not number.is_finite():
        raise ArithmeticError("numeric value must be finite")
    if number == 0:
        return "0"
    return format(number.normalize(), "f")


def _encode_csv(header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    target = io.StringIO(newline="")
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return target.getvalue().encode("utf-8")


def _tzdb_identity(evidence: OperationalDatasetEvidence) -> str | None:
    if evidence.timezone_treatment != "named_zone_to_utc":
        return None
    try:
        return "tzdata:" + metadata.version("tzdata")
    except metadata.PackageNotFoundError as exc:
        raise OperationalNormalizationError(
            "TIMEZONE_NORMALIZATION_FAILED",
            "named-zone normalization requires a versioned tzdata distribution; "
            "the host timezone database is not an auditable substitute.",
        ) from exc


def _initial_receipt(
    evidence: OperationalDatasetEvidence,
    *,
    source_columns: tuple[str, ...],
    normalized_roles: tuple[str, ...],
    column_exclusions: tuple[OperationalColumnExclusion, ...],
    method_sha256: str,
    timezone_database: str | None,
    raw_row_count: int,
    row_exclusions: tuple[OperationalExcludedRowReceipt, ...],
    included_row_count: int,
    normalized_sha256: str | None,
    actual_start: str | None,
    actual_end: str | None,
    coverage_mismatch_count: int,
    duplicate_key_count: int,
    gap_count: int,
    interval_drift_count: int,
    nonfinite_value_count: int,
    invalid_value_count: int,
    ambiguous_count: int,
    nonexistent_count: int,
    findings: tuple[str, ...],
) -> OperationalQualityReceipt:
    passed = not any(
        (
            coverage_mismatch_count,
            duplicate_key_count,
            gap_count,
            interval_drift_count,
            nonfinite_value_count,
            invalid_value_count,
        )
    )
    return OperationalQualityReceipt(
        schema=OPERATIONAL_NORMALIZATION_SCHEMA,
        logical_id=evidence.logical_id,
        kind=evidence.kind,
        source_locator=evidence.source_locator,
        source_sha256=evidence.source_sha256,
        observation_status=evidence.observation_status,
        lineage_source_sha256=evidence.lineage_source_sha256,
        derivation_method_sha256=evidence.derivation_method_sha256,
        lineage_verified=True,
        normalized_sha256=normalized_sha256,
        method_sha256=method_sha256,
        timezone_treatment=evidence.timezone_treatment,
        source_timezone=evidence.source_timezone,
        ambiguous_time_policy=evidence.ambiguous_time_policy,
        nonexistent_time_policy=evidence.nonexistent_time_policy,
        timezone_database=timezone_database,
        interval_basis=evidence.interval_basis,
        interval_seconds=evidence.interval_seconds,
        raw_row_count=raw_row_count,
        included_row_count=included_row_count,
        excluded_row_count=len(row_exclusions),
        source_columns=source_columns,
        normalized_roles=normalized_roles,
        column_bindings=evidence.columns,
        column_exclusions=column_exclusions,
        row_exclusions=row_exclusions,
        actual_coverage_start_utc=actual_start,
        actual_coverage_end_utc=actual_end,
        coverage_mismatch_count=coverage_mismatch_count,
        duplicate_key_count=duplicate_key_count,
        gap_count=gap_count,
        interval_drift_count=interval_drift_count,
        nonfinite_value_count=nonfinite_value_count,
        invalid_value_count=invalid_value_count,
        ambiguous_time_resolution_count=ambiguous_count,
        nonexistent_time_resolution_count=nonexistent_count,
        findings=findings,
        quality_passed=passed,
    )


def normalize_operational_csv(
    source_bytes: bytes,
    evidence: OperationalDatasetEvidence,
    *,
    lineage_source_bytes: tuple[bytes, ...] = (),
    derivation_method_bytes: bytes | None = None,
    column_exclusions: tuple[OperationalColumnExclusion, ...] = (),
    row_exclusions: tuple[OperationalRowExclusion, ...] = (),
) -> OperationalNormalizationResult:
    """Verify and normalize one D1-bound UTF-8 CSV artifact.

    Quality failures raise ``OperationalNormalizationError`` with a completed
    receipt.  The caller therefore cannot accidentally consume a defective
    normalized artifact while retaining the evidence needed to remediate it.
    """

    if not isinstance(source_bytes, bytes):
        raise OperationalNormalizationError(
            "INVALID_CSV", "source_bytes must be bytes."
        )
    actual_source_sha = _sha256(source_bytes)
    if actual_source_sha != evidence.source_sha256:
        raise OperationalNormalizationError(
            "SOURCE_DIGEST_MISMATCH",
            f"expected {evidence.source_sha256}, got {actual_source_sha}.",
        )
    if not isinstance(lineage_source_bytes, tuple) or not all(
        isinstance(item, bytes) for item in lineage_source_bytes
    ):
        raise OperationalNormalizationError(
            "LINEAGE_DIGEST_MISMATCH", "lineage_source_bytes must be a tuple of bytes."
        )
    actual_lineage = tuple(_sha256(item) for item in lineage_source_bytes)
    if actual_lineage != evidence.lineage_source_sha256:
        raise OperationalNormalizationError(
            "LINEAGE_DIGEST_MISMATCH",
            "upstream bytes do not exactly match the ordered D1 lineage digest tuple.",
        )
    if evidence.derivation_method_sha256 is None:
        if derivation_method_bytes is not None:
            raise OperationalNormalizationError(
                "LINEAGE_DIGEST_MISMATCH",
                "non-derived evidence cannot supply derivation method bytes.",
            )
    elif (
        not isinstance(derivation_method_bytes, bytes)
        or _sha256(derivation_method_bytes) != evidence.derivation_method_sha256
    ):
        raise OperationalNormalizationError(
            "LINEAGE_DIGEST_MISMATCH",
            "derivation method bytes do not match the D1 method digest.",
        )
    if not isinstance(column_exclusions, tuple) or not all(
        isinstance(item, OperationalColumnExclusion) for item in column_exclusions
    ):
        raise OperationalNormalizationError(
            "COLUMN_ACCOUNTING_FAILED",
            "column_exclusions must be a tuple of OperationalColumnExclusion.",
        )
    if not isinstance(row_exclusions, tuple) or not all(
        isinstance(item, OperationalRowExclusion) for item in row_exclusions
    ):
        raise OperationalNormalizationError(
            "ROW_ACCOUNTING_FAILED",
            "row_exclusions must be a tuple of OperationalRowExclusion.",
        )
    try:
        decoded = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OperationalNormalizationError(
            "INVALID_CSV", "source must be strict UTF-8."
        ) from exc
    if decoded.startswith("\ufeff") or "\x00" in decoded:
        raise OperationalNormalizationError(
            "INVALID_CSV", "UTF-8 BOM and NUL bytes are not admitted."
        )
    try:
        table = list(csv.reader(io.StringIO(decoded, newline=""), strict=True))
    except csv.Error as exc:
        raise OperationalNormalizationError("INVALID_CSV", str(exc)) from exc
    if not table or not table[0]:
        raise OperationalNormalizationError("INVALID_CSV", "CSV header is required.")
    header = tuple(table[0])
    if any(not item or item.strip() != item for item in header) or len(
        set(header)
    ) != len(header):
        raise OperationalNormalizationError(
            "COLUMN_ACCOUNTING_FAILED",
            "source headers must be unique, non-empty, and free of surrounding whitespace.",
        )
    mapped = tuple(binding.source_column for binding in evidence.columns)
    excluded = tuple(item.source_column for item in column_exclusions)
    if len(set(excluded)) != len(excluded):
        raise OperationalNormalizationError(
            "COLUMN_ACCOUNTING_FAILED", "column exclusions must be unique."
        )
    if set(mapped).intersection(excluded) or set(mapped).union(excluded) != set(header):
        raise OperationalNormalizationError(
            "COLUMN_ACCOUNTING_FAILED",
            "every source column must be mapped exactly once or explicitly excluded.",
        )
    raw_rows = table[1:]
    if len(raw_rows) != evidence.row_count:
        raise OperationalNormalizationError(
            "ROW_ACCOUNTING_FAILED",
            f"evidence declares {evidence.row_count} rows; CSV contains {len(raw_rows)}.",
        )
    if any(len(row) != len(header) for row in raw_rows):
        raise OperationalNormalizationError(
            "INVALID_CSV", "every data row must have exactly the header width."
        )
    requested_exclusions = {item.source_row_number: item for item in row_exclusions}
    if len(requested_exclusions) != len(row_exclusions) or any(
        number > len(raw_rows) for number in requested_exclusions
    ):
        raise OperationalNormalizationError(
            "ROW_ACCOUNTING_FAILED",
            "row exclusions must be unique one-based data-row numbers within the CSV.",
        )
    excluded_receipts = tuple(
        OperationalExcludedRowReceipt(
            source_row_number=number,
            reason=requested_exclusions[number].reason,
            parsed_row_sha256=_sha256(
                _encode_csv(header, (tuple(raw_rows[number - 1]),))
            ),
        )
        for number in sorted(requested_exclusions)
    )
    roles = tuple(binding.role for binding in evidence.columns)
    source_index = {name: index for index, name in enumerate(header)}
    tzdb = _tzdb_identity(evidence)
    method_sha = _method_sha(
        {
            "version": _NORMALIZER_VERSION,
            "source_sha256": evidence.source_sha256,
            "lineage_source_sha256": list(evidence.lineage_source_sha256),
            "derivation_method_sha256": evidence.derivation_method_sha256,
            "logical_id": evidence.logical_id,
            "timezone_treatment": evidence.timezone_treatment,
            "source_timezone": evidence.source_timezone,
            "ambiguous_time_policy": evidence.ambiguous_time_policy,
            "nonexistent_time_policy": evidence.nonexistent_time_policy,
            "interval_basis": evidence.interval_basis,
            "interval_seconds": evidence.interval_seconds,
            "columns": [binding.model_dump() for binding in evidence.columns],
            "column_exclusions": [item.model_dump() for item in column_exclusions],
            "row_exclusions": [item.model_dump() for item in row_exclusions],
            "timezone_database": tzdb,
        }
    )

    parsed_rows: list[_ParsedRow] = []
    findings: list[str] = []
    nonfinite_count = 0
    invalid_count = 0
    ambiguous_count = 0
    nonexistent_count = 0
    for row_number, source_row in enumerate(raw_rows, start=1):
        if row_number in requested_exclusions:
            continue
        role_values: dict[str, str] = {}
        timestamp: datetime | None = None
        wall_time: datetime | None = None
        for binding in evidence.columns:
            raw_value = source_row[source_index[binding.source_column]]
            try:
                if binding.role == "timestamp_utc":
                    timestamp, wall_time, was_ambiguous, was_nonexistent = (
                        _parse_timestamp(raw_value, evidence)
                    )
                    ambiguous_count += int(was_ambiguous)
                    nonexistent_count += int(was_nonexistent)
                    normalized = _format_utc(timestamp)
                elif binding.role in _NUMERIC_ROLES:
                    normalized = _canonical_decimal(raw_value)
                elif binding.role in _TEXT_ROLES:
                    normalized = _require_closed_text(raw_value, binding.role)
                else:  # D1 owns the closed role vocabulary.
                    raise ValueError(f"unsupported role {binding.role!r}")
            except ArithmeticError:
                nonfinite_count += 1
                findings.append(f"row={row_number};role={binding.role};nonfinite")
                normalized = raw_value
            except ValueError as exc:
                invalid_count += 1
                findings.append(
                    f"row={row_number};role={binding.role};invalid={str(exc)}"
                )
                normalized = raw_value
            role_values[binding.role] = normalized
        parsed_rows.append(
            _ParsedRow(
                source_row_number=row_number,
                values=tuple(role_values[role] for role in roles),
                role_values=role_values,
                timestamp_utc=timestamp,
                source_wall_time=wall_time,
                group_key=role_values.get("asset_id", "__dataset__"),
            )
        )

    duplicate_count = 0
    gap_count = 0
    drift_count = 0
    groups: dict[str, list[_ParsedRow]] = {}
    for row in parsed_rows:
        groups.setdefault(row.group_key, []).append(row)
    if evidence.kind == "asset":
        seen_assets: set[str] = set()
        for row in parsed_rows:
            asset = row.role_values.get("asset_id", "")
            if asset in seen_assets:
                duplicate_count += 1
                findings.append(
                    f"row={row.source_row_number};duplicate_asset_id={asset}"
                )
            seen_assets.add(asset)
    elif invalid_count == 0:
        for group, rows in groups.items():
            previous: _ParsedRow | None = None
            for row in rows:
                assert row.timestamp_utc is not None
                if previous is not None:
                    assert previous.timestamp_utc is not None
                    if row.timestamp_utc == previous.timestamp_utc:
                        duplicate_count += 1
                        findings.append(
                            f"row={row.source_row_number};group={group};duplicate_timestamp"
                        )
                    elif row.timestamp_utc < previous.timestamp_utc:
                        drift_count += 1
                        findings.append(
                            f"row={row.source_row_number};group={group};nonmonotonic"
                        )
                    elif evidence.interval_basis == "fixed_seconds":
                        delta = row.timestamp_utc - previous.timestamp_utc
                        expected = int(evidence.interval_seconds or 0)
                        expected_delta = timedelta(seconds=expected)
                        elapsed_microseconds = (
                            delta.days * 86_400_000_000
                            + delta.seconds * 1_000_000
                            + delta.microseconds
                        )
                        expected_microseconds = expected * 1_000_000
                        if (
                            delta > expected_delta
                            and elapsed_microseconds % expected_microseconds == 0
                        ):
                            missing = elapsed_microseconds // expected_microseconds - 1
                            gap_count += missing
                            findings.append(
                                f"row={row.source_row_number};group={group};missing_intervals={missing}"
                            )
                        elif delta != expected_delta:
                            drift_count += 1
                            findings.append(
                                f"row={row.source_row_number};group={group};"
                                f"interval_microseconds={elapsed_microseconds}"
                            )
                    elif evidence.interval_basis == "calendar_month":
                        assert row.source_wall_time is not None
                        assert previous.source_wall_time is not None
                        current = row.source_wall_time
                        prior = previous.source_wall_time
                        shape_ok = all(
                            (
                                prior.day == 1,
                                current.day == 1,
                                prior.time() == datetime.min.time(),
                                current.time() == datetime.min.time(),
                            )
                        )
                        month_delta = (
                            (current.year - prior.year) * 12
                            + current.month
                            - prior.month
                        )
                        if shape_ok and month_delta > 1:
                            gap_count += month_delta - 1
                            findings.append(
                                f"row={row.source_row_number};group={group};missing_months={month_delta - 1}"
                            )
                        elif not shape_ok or month_delta != 1:
                            drift_count += 1
                            findings.append(
                                f"row={row.source_row_number};group={group};calendar_month_drift"
                            )
                previous = row

    valid_times = [
        row.timestamp_utc for row in parsed_rows if row.timestamp_utc is not None
    ]
    actual_start = _format_utc(min(valid_times)) if valid_times else None
    actual_end = _format_utc(max(valid_times)) if valid_times else None
    coverage_mismatch = 0
    if evidence.kind != "asset":
        if (
            actual_start is None
            or actual_end is None
            or _parse_canonical_utc(actual_start, "actual_coverage_start_utc")
            != _parse_canonical_utc(evidence.coverage_start_utc, "coverage_start_utc")
            or _parse_canonical_utc(actual_end, "actual_coverage_end_utc")
            != _parse_canonical_utc(evidence.coverage_end_utc, "coverage_end_utc")
        ):
            coverage_mismatch = 1
            findings.append(
                "coverage_mismatch="
                f"declared[{evidence.coverage_start_utc},{evidence.coverage_end_utc}];"
                f"actual[{actual_start},{actual_end}]"
            )
    normalized_rows = tuple(row.values for row in parsed_rows)
    normalized_bytes: bytes | None = None
    normalized_sha: str | None = None
    if nonfinite_count == 0 and invalid_count == 0:
        normalized_bytes = _encode_csv(roles, normalized_rows)
        normalized_sha = _sha256(normalized_bytes)
    receipt = _initial_receipt(
        evidence,
        source_columns=header,
        normalized_roles=roles,
        column_exclusions=column_exclusions,
        method_sha256=method_sha,
        timezone_database=tzdb,
        raw_row_count=len(raw_rows),
        row_exclusions=excluded_receipts,
        included_row_count=len(parsed_rows),
        normalized_sha256=normalized_sha,
        actual_start=actual_start,
        actual_end=actual_end,
        coverage_mismatch_count=coverage_mismatch,
        duplicate_key_count=duplicate_count,
        gap_count=gap_count,
        interval_drift_count=drift_count,
        nonfinite_value_count=nonfinite_count,
        invalid_value_count=invalid_count,
        ambiguous_count=ambiguous_count,
        nonexistent_count=nonexistent_count,
        findings=tuple(findings),
    )
    if not receipt.quality_passed:
        raise OperationalNormalizationError(
            "QUALITY_CHECK_FAILED",
            "normalization QA failed; inspect the attached deterministic receipt.",
            receipt=receipt,
        )
    assert normalized_bytes is not None
    return OperationalNormalizationResult(
        evidence=evidence,
        source_bytes=source_bytes,
        lineage_source_bytes=lineage_source_bytes,
        derivation_method_bytes=derivation_method_bytes,
        normalized_csv_bytes=normalized_bytes,
        normalized_rows=normalized_rows,
        receipt=receipt,
    )


def aggregate_operational_series(
    normalized: OperationalNormalizationResult,
    spec: OperationalAggregationSpec,
) -> OperationalAggregationResult:
    """Aggregate a complete fixed-cadence series by UTC elapsed-time buckets."""

    evidence = normalized.evidence
    if not normalized.receipt.quality_passed:
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED", "source normalization QA did not pass."
        )
    if evidence.interval_basis != "fixed_seconds" or evidence.interval_seconds is None:
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            "aggregation requires fixed_seconds evidence.",
        )
    source_interval = evidence.interval_seconds
    if (
        spec.target_interval_seconds < source_interval
        or spec.target_interval_seconds % source_interval != 0
    ):
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            "target interval must be an integer multiple of the source interval.",
        )
    roles = normalized.receipt.normalized_roles
    if "timestamp_utc" not in roles or spec.value_role not in roles:
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            "source artifact lacks the requested timestamp/value roles.",
        )
    timestamp_index = roles.index("timestamp_utc")
    value_index = roles.index(spec.value_role)
    asset_index = roles.index("asset_id") if "asset_id" in roles else None
    anchor = _parse_canonical_utc(spec.anchor_utc, "anchor_utc")
    expected_per_bucket = spec.target_interval_seconds // source_interval
    buckets: dict[tuple[str, int], list[tuple[datetime, Decimal]]] = {}
    for row in normalized.normalized_rows:
        timestamp = _parse_canonical_utc(row[timestamp_index], "timestamp_utc")
        delta = timestamp - anchor
        elapsed_microseconds = (
            delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
        )
        if elapsed_microseconds < 0 or elapsed_microseconds % 1_000_000:
            raise OperationalNormalizationError(
                "AGGREGATION_CONTRACT_FAILED",
                "all timestamps must be integral seconds at or after anchor_utc.",
            )
        bucket_number = elapsed_microseconds // (
            spec.target_interval_seconds * 1_000_000
        )
        asset = row[asset_index] if asset_index is not None else "__dataset__"
        buckets.setdefault((asset, bucket_number), []).append(
            (timestamp, Decimal(row[value_index]))
        )
    output: list[tuple[str, ...]] = []
    for (asset, bucket_number), points in sorted(
        buckets.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        bucket_start = anchor + timedelta(
            seconds=bucket_number * spec.target_interval_seconds
        )
        expected_times = {
            bucket_start + timedelta(seconds=index * source_interval)
            for index in range(expected_per_bucket)
        }
        actual_times = {point[0] for point in points}
        if len(points) != expected_per_bucket or actual_times != expected_times:
            raise OperationalNormalizationError(
                "AGGREGATION_CONTRACT_FAILED",
                f"partial or misaligned bucket at {_format_utc(bucket_start)} for {asset!r}.",
            )
        total = sum((point[1] for point in points), Decimal(0))
        aggregate = (
            total if spec.method == "sum" else total / Decimal(expected_per_bucket)
        )
        values = [_format_utc(bucket_start)]
        if asset_index is not None:
            values.append(asset)
        values.append(_canonical_decimal(str(aggregate)))
        output.append(tuple(values))
    header = (
        ("timestamp_utc",)
        + (("asset_id",) if asset_index is not None else ())
        + (spec.value_role,)
    )
    rows = tuple(output)
    csv_bytes = _encode_csv(header, rows)
    aggregate_sha = _sha256(csv_bytes)
    method_sha = _method_sha(
        {
            "version": _AGGREGATOR_VERSION,
            "source_normalized_sha256": normalized.receipt.normalized_sha256,
            "spec": spec.model_dump(),
            "source_interval_seconds": source_interval,
            "timestamp_position": "interval_start",
            "utc_elapsed_time_basis": True,
        }
    )
    receipt = OperationalAggregationReceipt(
        schema=OPERATIONAL_AGGREGATION_SCHEMA,
        logical_id=evidence.logical_id,
        source_normalized_sha256=str(normalized.receipt.normalized_sha256),
        aggregate_sha256=aggregate_sha,
        method_sha256=method_sha,
        value_role=spec.value_role,
        value_unit="kWh" if spec.value_role == "energy_kwh" else "kW",
        method=spec.method,
        source_interval_seconds=source_interval,
        target_interval_seconds=spec.target_interval_seconds,
        anchor_utc=spec.anchor_utc,
        source_timestamp_position=spec.source_timestamp_position,
        value_basis=spec.value_basis,
        input_row_count=len(normalized.normalized_rows),
        output_row_count=len(rows),
    )
    return OperationalAggregationResult(
        header=header, rows=rows, csv_bytes=csv_bytes, receipt=receipt
    )


__all__ = [
    "OPERATIONAL_AGGREGATION_SCHEMA",
    "OPERATIONAL_NORMALIZATION_SCHEMA",
    "OperationalAggregationMethod",
    "OperationalAggregationReceipt",
    "OperationalAggregationResult",
    "OperationalAggregationSpec",
    "OperationalColumnExclusion",
    "OperationalExcludedRowReceipt",
    "OperationalNormalizationError",
    "OperationalNormalizationErrorCode",
    "OperationalNormalizationResult",
    "OperationalQualityReceipt",
    "OperationalRowExclusion",
    "aggregate_operational_series",
    "normalize_operational_csv",
]
