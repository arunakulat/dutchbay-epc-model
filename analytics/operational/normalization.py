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
from dataclasses import InitVar, asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
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
_MAX_FIXED_INTERVAL_SECONDS: Final = 31 * 86_400
_MAX_AGGREGATION_INTERVAL_SECONDS: Final = 366 * 86_400
_MAX_POINTS_PER_BUCKET: Final = 100_000
_MAX_NUMERIC_CHARACTERS: Final = 4_096
_POWER_MEAN_DECIMAL_PLACES: Final = 12
_POWER_MEAN_ROUNDING: Final = "ROUND_HALF_EVEN"
_NORMALIZATION_RESULT_TOKEN: Final = object()
_AGGREGATION_RESULT_TOKEN: Final = object()
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_OFFSET_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?" r"(?:Z|[+-]\d{2}:\d{2})$"
)
_LOCAL_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")

OperationalNormalizationErrorCode: TypeAlias = Literal[
    "SOURCE_DIGEST_MISMATCH",
    "LINEAGE_DIGEST_MISMATCH",
    "INVALID_CSV",
    "COLUMN_ACCOUNTING_FAILED",
    "ROW_ACCOUNTING_FAILED",
    "INVALID_VALUE",
    "TIMEZONE_NORMALIZATION_FAILED",
    "GROUP_UNIVERSE_FAILED",
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
class OperationalTimezoneRules:
    """Caller-supplied TZif bytes used for one declared named timezone."""

    source_timezone: str
    tzif_bytes: bytes
    source_locator: str

    def __post_init__(self) -> None:
        _require_closed_text(self.source_timezone, "source_timezone")
        _require_closed_text(self.source_locator, "source_locator")
        if not isinstance(self.tzif_bytes, bytes):
            raise ValueError("tzif_bytes must be immutable bytes.")
        if len(self.tzif_bytes) > 1_048_576:
            raise ValueError("tzif_bytes must not exceed 1 MiB.")
        try:
            _validate_tzif_payload(self.tzif_bytes)
        except ValueError as exc:
            raise ValueError(
                "tzif_bytes must contain one complete, structurally valid TZif file."
            ) from exc

    @property
    def sha256(self) -> str:
        return _sha256(self.tzif_bytes)

    @property
    def identity(self) -> str:
        return f"tzif-sha256:{self.sha256}"

    def model_dump(self) -> dict[str, Any]:
        return {
            "source_timezone": self.source_timezone,
            "source_locator": self.source_locator,
            "tzif_sha256": self.sha256,
        }


@dataclass(frozen=True)
class OperationalGroupQualityReceipt:
    """Population-exact QA facts for one asset or dataset-level time series."""

    group_key: str
    included_row_count: int
    actual_coverage_start_utc: str | None
    actual_coverage_end_utc: str | None
    coverage_mismatch_count: int
    duplicate_key_count: int
    gap_count: int
    interval_drift_count: int
    source_order_violation_count: int

    def __post_init__(self) -> None:
        _require_closed_text(self.group_key, "group_key")
        for field_name in (
            "included_row_count",
            "coverage_mismatch_count",
            "duplicate_key_count",
            "gap_count",
            "interval_drift_count",
            "source_order_violation_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")

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
    timezone_source_locator: str | None
    timezone_rule_attestation: Literal["caller_attested_zone_payload"] | None
    interval_basis: str
    interval_seconds: int | None
    coverage_start_utc: str
    coverage_end_utc: str
    declared_row_count: int
    raw_row_count: int
    included_row_count: int
    excluded_row_count: int
    empty_dataset_count: int
    source_columns: tuple[str, ...]
    normalized_roles: tuple[str, ...]
    column_bindings: tuple[OperationalColumnBinding, ...]
    column_exclusions: tuple[OperationalColumnExclusion, ...]
    row_exclusions: tuple[OperationalExcludedRowReceipt, ...]
    group_universe_normalized_sha256: str | None
    expected_group_keys: tuple[str, ...]
    missing_group_keys: tuple[str, ...]
    unexpected_group_keys: tuple[str, ...]
    group_receipts: tuple[OperationalGroupQualityReceipt, ...]
    actual_coverage_start_utc: str | None
    actual_coverage_end_utc: str | None
    coverage_mismatch_count: int
    duplicate_key_count: int
    gap_count: int
    interval_drift_count: int
    source_order_violation_count: int
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
            self.declared_row_count,
            self.included_row_count,
            self.excluded_row_count,
            self.empty_dataset_count,
            self.coverage_mismatch_count,
            self.duplicate_key_count,
            self.gap_count,
            self.interval_drift_count,
            self.source_order_violation_count,
            self.nonfinite_value_count,
            self.invalid_value_count,
            self.ambiguous_time_resolution_count,
            self.nonexistent_time_resolution_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("quality receipt counts must be non-negative integers.")
        if self.raw_row_count != self.included_row_count + self.excluded_row_count:
            raise ValueError("raw rows must reconcile to included plus excluded rows.")
        if self.raw_row_count != self.declared_row_count:
            raise ValueError("raw row count must match the D1 declared row count.")
        declared_start = _parse_canonical_utc(
            self.coverage_start_utc, "coverage_start_utc"
        )
        declared_end = _parse_canonical_utc(self.coverage_end_utc, "coverage_end_utc")
        if declared_start >= declared_end:
            raise ValueError("declared coverage start must be before its end.")
        if self.excluded_row_count != len(self.row_exclusions):
            raise ValueError("excluded row count must match its receipt tuple.")
        if sum(item.included_row_count for item in self.group_receipts) != (
            self.included_row_count
        ):
            raise ValueError("group row counts must reconcile to included rows.")
        for aggregate_name, group_name in (
            ("coverage_mismatch_count", "coverage_mismatch_count"),
            ("duplicate_key_count", "duplicate_key_count"),
            ("gap_count", "gap_count"),
            ("interval_drift_count", "interval_drift_count"),
            ("source_order_violation_count", "source_order_violation_count"),
        ):
            if getattr(self, aggregate_name) != sum(
                getattr(item, group_name) for item in self.group_receipts
            ):
                raise ValueError(f"{aggregate_name} must reconcile to group receipts.")
        if self.normalized_roles != tuple(
            binding.role for binding in self.column_bindings
        ):
            raise ValueError("normalized roles must match the ordered column bindings.")
        if len(self.source_columns) != len(set(self.source_columns)):
            raise ValueError("source columns must be unique.")
        group_keys = tuple(item.group_key for item in self.group_receipts)
        if len(group_keys) != len(set(group_keys)):
            raise ValueError("group receipt keys must be unique.")
        if tuple(sorted(self.expected_group_keys)) != self.expected_group_keys or len(
            self.expected_group_keys
        ) != len(set(self.expected_group_keys)):
            raise ValueError("expected_group_keys must be sorted and unique.")
        if tuple(sorted(self.missing_group_keys)) != self.missing_group_keys or len(
            self.missing_group_keys
        ) != len(set(self.missing_group_keys)):
            raise ValueError("missing_group_keys must be sorted and unique.")
        if tuple(
            sorted(self.unexpected_group_keys)
        ) != self.unexpected_group_keys or len(self.unexpected_group_keys) != len(
            set(self.unexpected_group_keys)
        ):
            raise ValueError("unexpected_group_keys must be sorted and unique.")
        if not set(self.missing_group_keys).issubset(self.expected_group_keys):
            raise ValueError(
                "missing groups must belong to the expected group universe."
            )
        if set(self.unexpected_group_keys).intersection(self.expected_group_keys):
            raise ValueError(
                "unexpected groups cannot belong to the expected universe."
            )
        if self.expected_group_keys:
            if (
                self.group_universe_normalized_sha256 is None
                or _SHA256_RE.fullmatch(self.group_universe_normalized_sha256) is None
            ):
                raise ValueError(
                    "grouped receipts require a normalized universe digest."
                )
        elif self.group_universe_normalized_sha256 is not None:
            raise ValueError("ungrouped receipts cannot claim a group universe digest.")
        for group in self.group_receipts:
            if group.actual_coverage_start_utc is not None:
                start = _parse_canonical_utc(
                    group.actual_coverage_start_utc, "actual_coverage_start_utc"
                )
                end = _parse_canonical_utc(
                    str(group.actual_coverage_end_utc), "actual_coverage_end_utc"
                )
                if start > end:
                    raise ValueError("group coverage start cannot be after its end.")
            elif group.actual_coverage_end_utc is not None:
                raise ValueError(
                    "group coverage bounds must both be null or both be set."
                )
        if self.timezone_treatment == "named_zone_to_utc":
            try:
                _require_closed_text(self.source_timezone, "source_timezone")
                _require_closed_text(
                    self.timezone_source_locator, "timezone_source_locator"
                )
            except ValueError as exc:
                raise ValueError(
                    "named-zone receipts require closed timezone provenance text."
                ) from exc
            if (
                self.timezone_database is None
                or re.fullmatch(r"tzif-sha256:[0-9a-f]{64}", self.timezone_database)
                is None
                or self.timezone_rule_attestation != "caller_attested_zone_payload"
            ):
                raise ValueError(
                    "named-zone receipts require hash-bound, caller-attested TZif rules."
                )
        elif any(
            item is not None
            for item in (
                self.timezone_database,
                self.timezone_source_locator,
                self.timezone_rule_attestation,
            )
        ):
            raise ValueError("non-named timezone treatments cannot claim TZif rules.")
        defects = any(
            (
                self.coverage_mismatch_count,
                self.empty_dataset_count,
                self.duplicate_key_count,
                self.gap_count,
                self.interval_drift_count,
                self.source_order_violation_count,
                self.nonfinite_value_count,
                self.invalid_value_count,
                len(self.missing_group_keys),
                len(self.unexpected_group_keys),
            )
        )
        if type(self.quality_passed) is not bool or self.quality_passed is defects:
            raise ValueError(
                "quality_passed must be exactly the inverse of QA defects."
            )
        if self.quality_passed and self.normalized_sha256 is None:
            raise ValueError("passing QA requires a normalized artifact digest.")
        if self.quality_passed and self.included_row_count == 0:
            raise ValueError("passing QA requires at least one included row.")
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
    timezone_rules: OperationalTimezoneRules | None
    group_universe: OperationalGroupUniverse | None
    normalized_csv_bytes: bytes
    normalized_rows: tuple[tuple[str, ...], ...]
    receipt: OperationalQualityReceipt
    _factory_token: InitVar[object] = None

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _NORMALIZATION_RESULT_TOKEN:
            raise ValueError(
                "normalization results must be constructed by normalize_operational_csv."
            )
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
        if (
            _encode_csv(self.receipt.normalized_roles, self.normalized_rows)
            != self.normalized_csv_bytes
        ):
            raise ValueError("normalized rows do not encode to normalized_csv_bytes.")
        evidence_receipt_pairs = (
            (self.receipt.logical_id, self.evidence.logical_id),
            (self.receipt.kind, self.evidence.kind),
            (self.receipt.source_locator, self.evidence.source_locator),
            (self.receipt.source_sha256, self.evidence.source_sha256),
            (self.receipt.observation_status, self.evidence.observation_status),
            (self.receipt.lineage_source_sha256, self.evidence.lineage_source_sha256),
            (
                self.receipt.derivation_method_sha256,
                self.evidence.derivation_method_sha256,
            ),
            (self.receipt.timezone_treatment, self.evidence.timezone_treatment),
            (self.receipt.source_timezone, self.evidence.source_timezone),
            (self.receipt.ambiguous_time_policy, self.evidence.ambiguous_time_policy),
            (
                self.receipt.nonexistent_time_policy,
                self.evidence.nonexistent_time_policy,
            ),
            (self.receipt.interval_basis, self.evidence.interval_basis),
            (self.receipt.interval_seconds, self.evidence.interval_seconds),
            (self.receipt.coverage_start_utc, self.evidence.coverage_start_utc),
            (self.receipt.coverage_end_utc, self.evidence.coverage_end_utc),
            (self.receipt.declared_row_count, self.evidence.row_count),
            (self.receipt.column_bindings, self.evidence.columns),
        )
        if any(actual != expected for actual, expected in evidence_receipt_pairs):
            raise ValueError(
                "receipt identity does not match the D1 evidence envelope."
            )
        if self.evidence.timezone_treatment == "named_zone_to_utc":
            if (
                self.timezone_rules is None
                or self.timezone_rules.source_timezone != self.evidence.source_timezone
                or self.receipt.timezone_database != self.timezone_rules.identity
                or self.receipt.timezone_source_locator
                != self.timezone_rules.source_locator
            ):
                raise ValueError(
                    "timezone rule bytes do not match the receipt/evidence."
                )
        elif self.timezone_rules is not None:
            raise ValueError("timezone rules apply only to named-zone evidence.")
        if (
            "asset_id" in self.receipt.normalized_roles
            and self.evidence.kind != "asset"
        ):
            if self.group_universe is None:
                raise ValueError("grouped time series require an asset group universe.")
            expected_keys = self.group_universe.group_keys
            universe_sha = self.group_universe.normalized_sha256
        else:
            if self.group_universe is not None:
                raise ValueError("group universes apply only to grouped time series.")
            expected_keys = ()
            universe_sha = None
        if (
            self.receipt.expected_group_keys != expected_keys
            or self.receipt.group_universe_normalized_sha256 != universe_sha
        ):
            raise ValueError("group universe does not match the normalization receipt.")
        expected_method_sha = _normalization_method_sha(
            self.evidence,
            self.receipt.column_exclusions,
            self.receipt.row_exclusions,
            self.timezone_rules,
            self.group_universe,
        )
        if self.receipt.method_sha256 != expected_method_sha:
            raise ValueError(
                "normalization method digest does not match retained inputs."
            )
        replay = _normalize_operational_csv_artifacts(
            self.source_bytes,
            self.evidence,
            lineage_source_bytes=self.lineage_source_bytes,
            derivation_method_bytes=self.derivation_method_bytes,
            timezone_rules=self.timezone_rules,
            group_universe=self.group_universe,
            column_exclusions=self.receipt.column_exclusions,
            row_exclusions=tuple(
                OperationalRowExclusion(item.source_row_number, item.reason)
                for item in self.receipt.row_exclusions
            ),
        )
        if (
            self.normalized_csv_bytes != replay.normalized_csv_bytes
            or self.normalized_rows != replay.normalized_rows
            or self.receipt != replay.receipt
        ):
            raise ValueError(
                "normalization result does not reproduce from retained source inputs."
            )


@dataclass(frozen=True)
class OperationalGroupUniverse:
    """A group universe derived from a verified normalized asset roster."""

    asset_result: OperationalNormalizationResult

    def __post_init__(self) -> None:
        if not isinstance(self.asset_result, OperationalNormalizationResult):
            raise ValueError("asset_result must be a verified normalization result.")
        if self.asset_result.evidence.kind != "asset":
            raise ValueError(
                "group universes must derive from normalized asset evidence."
            )
        if "asset_id" not in self.asset_result.receipt.normalized_roles:
            raise ValueError("asset evidence must expose an asset_id role.")
        if not self.group_keys:
            raise ValueError("group universes require at least one asset key.")

    @property
    def group_keys(self) -> tuple[str, ...]:
        index = self.asset_result.receipt.normalized_roles.index("asset_id")
        return tuple(sorted(row[index] for row in self.asset_result.normalized_rows))

    @property
    def normalized_sha256(self) -> str:
        digest = self.asset_result.receipt.normalized_sha256
        assert digest is not None
        return digest

    def model_dump(self) -> dict[str, Any]:
        return {
            "normalized_sha256": self.normalized_sha256,
            "group_keys": list(self.group_keys),
        }


@dataclass(frozen=True)
class OperationalAggregationSpec:
    """An explicit UTC aggregation contract; never applied by normalization."""

    value_role: Literal["energy_kwh", "power_kw"]
    method: OperationalAggregationMethod
    target_interval_seconds: int
    anchor_utc: str
    source_timestamp_position: Literal["interval_start"]
    value_basis: Literal["interval_energy", "interval_average_power"]
    arithmetic_policy: Literal["exact_decimal_sum_v1", "half_even_power_mean_v1"]
    rounding_decimal_places: int | None

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
        expected_arithmetic = (
            "exact_decimal_sum_v1"
            if self.value_role == "energy_kwh"
            else "half_even_power_mean_v1"
        )
        expected_places = (
            None if self.value_role == "energy_kwh" else _POWER_MEAN_DECIMAL_PLACES
        )
        if (
            self.arithmetic_policy != expected_arithmetic
            or self.rounding_decimal_places != expected_places
        ):
            raise ValueError(
                f"{self.value_role} requires arithmetic_policy="
                f"{expected_arithmetic!r} and rounding_decimal_places="
                f"{expected_places!r}."
            )
        if (
            type(self.target_interval_seconds) is not int
            or self.target_interval_seconds < 1
            or self.target_interval_seconds > _MAX_AGGREGATION_INTERVAL_SECONDS
        ):
            raise ValueError(
                "target_interval_seconds must be a positive integer no greater "
                f"than {_MAX_AGGREGATION_INTERVAL_SECONDS}."
            )
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
    arithmetic_policy: Literal["exact_decimal_sum_v1", "half_even_power_mean_v1"]
    rounding_decimal_places: int | None
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
            if type(value) is not int or value < 1:
                raise ValueError(f"{field_name} must be a positive integer.")
        if self.value_role not in {"energy_kwh", "power_kw"}:
            raise ValueError("aggregation value_role is not supported.")
        expected_method = "sum" if self.value_role == "energy_kwh" else "mean"
        expected_unit = "kWh" if self.value_role == "energy_kwh" else "kW"
        expected_basis = (
            "interval_energy"
            if self.value_role == "energy_kwh"
            else "interval_average_power"
        )
        if (
            self.method != expected_method
            or self.value_unit != expected_unit
            or self.value_basis != expected_basis
            or self.source_timestamp_position != "interval_start"
            or self.timestamp_position != "interval_start"
        ):
            raise ValueError(
                "aggregation receipt semantics are internally inconsistent."
            )
        expected_arithmetic = (
            "exact_decimal_sum_v1"
            if self.value_role == "energy_kwh"
            else "half_even_power_mean_v1"
        )
        expected_places = (
            None if self.value_role == "energy_kwh" else _POWER_MEAN_DECIMAL_PLACES
        )
        if (
            self.arithmetic_policy != expected_arithmetic
            or self.rounding_decimal_places != expected_places
        ):
            raise ValueError("aggregation arithmetic policy is inconsistent.")
        if (
            self.target_interval_seconds < self.source_interval_seconds
            or self.target_interval_seconds % self.source_interval_seconds
        ):
            raise ValueError("aggregation receipt intervals are not exact multiples.")
        _parse_canonical_utc(self.anchor_utc, "anchor_utc")
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
    normalized: OperationalNormalizationResult
    spec: OperationalAggregationSpec
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    csv_bytes: bytes
    receipt: OperationalAggregationReceipt
    _factory_token: InitVar[object] = None

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _AGGREGATION_RESULT_TOKEN:
            raise ValueError(
                "aggregation results must be constructed by aggregate_operational_series."
            )
        if self.receipt.logical_id != self.normalized.evidence.logical_id:
            raise ValueError(
                "aggregate logical_id does not match its normalized source."
            )
        if (
            self.receipt.source_normalized_sha256
            != self.normalized.receipt.normalized_sha256
        ):
            raise ValueError("aggregate source digest does not match normalized input.")
        if self.receipt.input_row_count != len(self.normalized.normalized_rows):
            raise ValueError("aggregate input count does not match normalized rows.")
        if (
            self.receipt.source_interval_seconds
            != self.normalized.evidence.interval_seconds
        ):
            raise ValueError("aggregate source interval does not match D1 evidence.")
        receipt_spec_pairs = (
            (self.receipt.value_role, self.spec.value_role),
            (self.receipt.method, self.spec.method),
            (self.receipt.target_interval_seconds, self.spec.target_interval_seconds),
            (self.receipt.anchor_utc, self.spec.anchor_utc),
            (
                self.receipt.source_timestamp_position,
                self.spec.source_timestamp_position,
            ),
            (self.receipt.value_basis, self.spec.value_basis),
            (self.receipt.arithmetic_policy, self.spec.arithmetic_policy),
            (
                self.receipt.rounding_decimal_places,
                self.spec.rounding_decimal_places,
            ),
        )
        if any(actual != expected for actual, expected in receipt_spec_pairs):
            raise ValueError("aggregation receipt does not match its retained spec.")
        if _sha256(self.csv_bytes) != self.receipt.aggregate_sha256:
            raise ValueError("aggregate bytes do not match the receipt digest.")
        if len(self.rows) != self.receipt.output_row_count:
            raise ValueError("aggregate row count does not match the receipt.")
        if _encode_csv(self.header, self.rows) != self.csv_bytes:
            raise ValueError("aggregate rows do not encode to csv_bytes.")
        expected_header = (
            ("timestamp_utc",)
            + (self.header[1:-1] if len(self.header) == 3 else ())
            + (self.receipt.value_role,)
        )
        if self.header != expected_header or (
            len(self.header) == 3 and self.header[1] != "asset_id"
        ):
            raise ValueError("aggregate header does not match receipt semantics.")
        expected_method_sha = _aggregation_method_sha(
            self.normalized, self.spec, self.receipt.source_interval_seconds
        )
        if self.receipt.method_sha256 != expected_method_sha:
            raise ValueError(
                "aggregation method digest does not match retained inputs."
            )
        expected_header, expected_rows, _ = _aggregate_rows(self.normalized, self.spec)
        if self.header != expected_header or self.rows != expected_rows:
            raise ValueError("aggregate rows do not match retained source and spec.")


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


@dataclass(frozen=True)
class _NormalizationArtifacts:
    """Internal deterministic output replayed by result construction."""

    normalized_csv_bytes: bytes
    normalized_rows: tuple[tuple[str, ...], ...]
    receipt: OperationalQualityReceipt


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


def _read_tzif_header(
    payload: bytes, cursor: int
) -> tuple[int, tuple[int, int, int, int, int, int], int]:
    """Read one bounded RFC 8536/9636 header without invoking ``zoneinfo``."""

    header_end = cursor + 44
    if header_end > len(payload) or payload[cursor : cursor + 4] != b"TZif":
        raise ValueError("TZif header is truncated or has invalid magic")
    version_octet = payload[cursor + 4 : cursor + 5]
    if version_octet == b"\x00":
        version = 1
    elif version_octet in {b"2", b"3", b"4"}:
        version = int(version_octet)
    else:
        raise ValueError("TZif version is not supported")
    if payload[cursor + 5 : cursor + 20] != b"\x00" * 15:
        raise ValueError("TZif reserved header octets must be zero")
    raw_counts = tuple(
        int.from_bytes(payload[offset : offset + 4], "big", signed=True)
        for offset in range(cursor + 20, cursor + 44, 4)
    )
    if len(raw_counts) != 6 or any(value < 0 for value in raw_counts):
        raise ValueError("TZif counts must be non-negative")
    isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = raw_counts
    counts = (isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt)
    return version, counts, header_end


def _is_utc_month_boundary(unix_seconds: int) -> bool:
    """Return whether an arbitrary-size UNIX timestamp begins a UTC month."""

    days, seconds = divmod(unix_seconds, 86_400)
    if seconds:
        return False
    shifted_days = days + 719_468
    era = shifted_days // 146_097
    day_of_era = shifted_days - era * 146_097
    year_of_era = (
        day_of_era - day_of_era // 1_460 + day_of_era // 36_524 - day_of_era // 146_096
    ) // 365
    day_of_year = day_of_era - (
        365 * year_of_era + year_of_era // 4 - year_of_era // 100
    )
    month_prime = (5 * day_of_year + 2) // 153
    day_of_month = day_of_year - (153 * month_prime + 2) // 5 + 1
    return day_of_month == 1


def _read_tzif_data_block(
    payload: bytes,
    cursor: int,
    counts: tuple[int, int, int, int, int, int],
    *,
    time_size: int,
    version: int,
) -> int:
    """Validate one complete TZif data block and return its exclusive end."""

    isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts
    if not 1 <= typecnt <= 256 or charcnt < 1:
        raise ValueError("TZif requires 1..256 local-time types and abbreviations")
    if isutcnt not in {0, typecnt} or isstdcnt not in {0, typecnt}:
        raise ValueError("TZif indicator counts must be zero or match typecnt")
    transition_bytes = timecnt * time_size
    index_start = cursor + transition_bytes
    ttinfo_start = index_start + timecnt
    abbreviation_start = ttinfo_start + typecnt * 6
    leap_start = abbreviation_start + charcnt
    isstd_start = leap_start + leapcnt * (time_size + 4)
    isut_start = isstd_start + isstdcnt
    block_end = isut_start + isutcnt
    if block_end > len(payload):
        raise ValueError("TZif data block is truncated")

    previous_transition: int | None = None
    for offset in range(cursor, index_start, time_size):
        transition = int.from_bytes(
            payload[offset : offset + time_size], "big", signed=True
        )
        if previous_transition is not None and transition <= previous_transition:
            raise ValueError("TZif transition times must be strictly increasing")
        previous_transition = transition
    transition_indices = payload[index_start:ttinfo_start]
    if any(index >= typecnt for index in transition_indices):
        raise ValueError("TZif transition references an absent local-time type")
    abbreviation_bytes = payload[abbreviation_start:leap_start]
    for item in range(typecnt):
        record = ttinfo_start + item * 6
        utc_offset = int.from_bytes(payload[record : record + 4], "big", signed=True)
        is_dst = payload[record + 4]
        abbreviation_index = payload[record + 5]
        if not -89_999 <= utc_offset <= 93_599 or is_dst not in {0, 1}:
            raise ValueError("TZif local-time type is outside RFC bounds")
        if (
            abbreviation_index >= charcnt
            or abbreviation_bytes.find(b"\x00", abbreviation_index) < 0
        ):
            raise ValueError("TZif abbreviation index is not NUL-terminated")
    if any(octet != 0 and not 0x20 <= octet <= 0x7E for octet in abbreviation_bytes):
        raise ValueError("TZif abbreviations must contain printable ASCII or NUL")
    previous_leap_time: int | None = None
    previous_correction = 0
    for item in range(leapcnt):
        record = leap_start + item * (time_size + 4)
        leap_time = int.from_bytes(
            payload[record : record + time_size], "big", signed=True
        )
        correction = int.from_bytes(
            payload[record + time_size : record + time_size + 4],
            "big",
            signed=True,
        )
        if item == 0 and leap_time < 0:
            raise ValueError("TZif first leap-second occurrence must be non-negative")
        if previous_leap_time is not None and leap_time <= previous_leap_time:
            raise ValueError("TZif leap-second times must be strictly increasing")
        if item == 0 and version == 4:
            correction_change = 1 if correction > 0 else -1
            correction_before_occurrence = correction - correction_change
        else:
            correction_change = correction - previous_correction
            correction_before_occurrence = previous_correction
        terminal_v4_expiration = (
            version == 4 and item == leapcnt - 1 and item > 0 and correction_change == 0
        )
        if correction_change not in {-1, 1} and not terminal_v4_expiration:
            raise ValueError("TZif leap corrections must change by exactly one")
        if not terminal_v4_expiration and not _is_utc_month_boundary(
            leap_time - correction_before_occurrence
        ):
            raise ValueError("TZif leap seconds must occur at a UTC month end")
        previous_leap_time = leap_time
        previous_correction = correction
    standard_indicators = (
        payload[isstd_start:isut_start] if isstdcnt else bytes(typecnt)
    )
    ut_indicators = payload[isut_start:block_end] if isutcnt else bytes(typecnt)
    if any(octet not in {0, 1} for octet in standard_indicators + ut_indicators):
        raise ValueError("TZif indicators must be zero or one")
    if any(
        ut and not standard
        for standard, ut in zip(standard_indicators, ut_indicators, strict=True)
    ):
        raise ValueError("TZif UT indicators require corresponding standard indicators")
    return block_end


def _validate_tzif_payload(payload: bytes) -> None:
    """Bound and structurally validate a complete TZif container in linear time."""

    if not isinstance(payload, bytes) or len(payload) > 1_048_576:
        raise ValueError("TZif payload must be immutable bytes no larger than 1 MiB")
    version, counts, cursor = _read_tzif_header(payload, 0)
    cursor = _read_tzif_data_block(
        payload, cursor, counts, time_size=4, version=version
    )
    if version == 1:
        if cursor != len(payload):
            raise ValueError("version-1 TZif data has trailing octets")
        return

    second_version, second_counts, cursor = _read_tzif_header(payload, cursor)
    if second_version != version:
        raise ValueError("TZif headers declare inconsistent versions")
    cursor = _read_tzif_data_block(
        payload, cursor, second_counts, time_size=8, version=second_version
    )
    if cursor >= len(payload) or payload[cursor : cursor + 1] != b"\n":
        raise ValueError("TZif v2+ footer must begin with a newline")
    if payload[-1:] != b"\n" or b"\n" in payload[cursor + 1 : -1]:
        raise ValueError("TZif v2+ POSIX footer must end with one newline")
    footer = payload[cursor + 1 : -1]
    if b"\x00" in footer:
        raise ValueError("TZif POSIX footer cannot contain NUL")
    try:
        footer.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("TZif POSIX footer must be ASCII") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _method_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return _sha256(encoded)


def _normalization_method_sha(
    evidence: OperationalDatasetEvidence,
    column_exclusions: tuple[OperationalColumnExclusion, ...],
    row_exclusions: tuple[OperationalRowExclusion | OperationalExcludedRowReceipt, ...],
    timezone_rules: OperationalTimezoneRules | None,
    group_universe: OperationalGroupUniverse | None,
) -> str:
    return _method_sha(
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
            "coverage_start_utc": evidence.coverage_start_utc,
            "coverage_end_utc": evidence.coverage_end_utc,
            "row_count": evidence.row_count,
            "columns": [binding.model_dump() for binding in evidence.columns],
            "column_exclusions": [item.model_dump() for item in column_exclusions],
            "row_exclusions": [
                {
                    "source_row_number": item.source_row_number,
                    "reason": item.reason,
                }
                for item in row_exclusions
            ],
            "timezone_rules": (
                None
                if timezone_rules is None
                else {
                    "source_timezone": timezone_rules.source_timezone,
                    "source_locator": timezone_rules.source_locator,
                    "tzif_sha256": timezone_rules.sha256,
                    "attestation": "caller_attested_zone_payload",
                }
            ),
            "group_universe": (
                None if group_universe is None else group_universe.model_dump()
            ),
            "numeric_policy": {
                "max_characters": _MAX_NUMERIC_CHARACTERS,
                "canonicalization": "decimal_tuple_lossless_v1",
            },
        }
    )


def _format_utc(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    # ``strftime("%Y")`` is platform-dependent for years below 1000.  D1
    # admits the complete RFC 3339 four-digit year range, so render every
    # component explicitly instead of relying on the host C library.
    base = (
        f"{value.year:04d}-{value.month:02d}-{value.day:02d}T"
        f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
    )
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
    value: str,
    evidence: OperationalDatasetEvidence,
    named_zone: ZoneInfo | None,
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
        if value.endswith("-00:00"):
            raise ValueError("RFC3339 unknown offset '-00:00' is not admitted")
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
    if named_zone is None:
        raise ValueError("named-zone treatment requires hash-bound TZif rules")
    zone = named_zone
    candidates: list[tuple[int, datetime, datetime]] = []
    try:
        for fold in (0, 1):
            utc_value = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
            roundtrip = utc_value.astimezone(zone).replace(tzinfo=None)
            candidates.append((fold, utc_value, roundtrip))
    except (OverflowError, ValueError) as exc:
        raise OperationalNormalizationError(
            "TIMEZONE_NORMALIZATION_FAILED",
            "supplied timezone rules cannot represent the timestamp in Python's "
            "datetime range.",
        ) from exc
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
    if len(value) > _MAX_NUMERIC_CHARACTERS:
        raise ValueError("numeric value exceeds the bounded canonical representation")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("numeric value is not a decimal") from exc
    if not number.is_finite():
        raise ArithmeticError("numeric value must be finite")
    if _DECIMAL_RE.fullmatch(value) is None:
        raise ValueError("numeric value is not a strict decimal literal")
    if number == 0:
        return "0"
    sign, digits_tuple, exponent_value = number.as_tuple()
    if not isinstance(exponent_value, int):
        raise ArithmeticError("numeric value must have a finite integer exponent")
    exponent = exponent_value
    digits = "".join(str(digit) for digit in digits_tuple)
    if exponent >= 0:
        if len(digits) + exponent > _MAX_NUMERIC_CHARACTERS:
            raise ValueError(
                "numeric value exceeds the bounded canonical representation"
            )
        integer = digits + ("0" * exponent)
        fractional = ""
    else:
        split = len(digits) + exponent
        if split > 0:
            integer = digits[:split]
            fractional = digits[split:]
        else:
            if 1 - split + len(digits) > _MAX_NUMERIC_CHARACTERS:
                raise ValueError(
                    "numeric value exceeds the bounded canonical representation"
                )
            integer = "0"
            fractional = ("0" * -split) + digits
    integer = integer.lstrip("0") or "0"
    fractional = fractional.rstrip("0")
    rendered = integer + (("." + fractional) if fractional else "")
    if sign:
        rendered = "-" + rendered
    if len(rendered) > _MAX_NUMERIC_CHARACTERS:
        raise ValueError("numeric value exceeds the bounded canonical representation")
    return rendered


def _fraction_from_canonical_decimal(value: str) -> Fraction:
    return Fraction(Decimal(value))


def _format_scaled_integer(value: int, decimal_places: int) -> str:
    negative = value < 0
    digits = str(abs(value)).rjust(decimal_places + 1, "0")
    if decimal_places:
        rendered = digits[:-decimal_places] + "." + digits[-decimal_places:]
    else:
        rendered = digits
    rendered = rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    rendered = rendered.lstrip("0") or "0"
    if rendered.startswith("."):
        rendered = "0" + rendered
    if negative and rendered != "0":
        rendered = "-" + rendered
    return rendered


def _exact_terminating_fraction(value: Fraction) -> str:
    denominator = value.denominator
    twos = 0
    fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("exact decimal sum unexpectedly became non-terminating")
    places = max(twos, fives)
    if places > _MAX_NUMERIC_CHARACTERS:
        raise ValueError("aggregate exceeds the bounded canonical representation")
    scaled = value.numerator * (2 ** (places - twos)) * (5 ** (places - fives))
    rendered = _format_scaled_integer(scaled, places)
    if len(rendered) > _MAX_NUMERIC_CHARACTERS:
        raise ValueError("aggregate exceeds the bounded canonical representation")
    return rendered


def _round_fraction_half_even(value: Fraction, decimal_places: int) -> str:
    scale = 10**decimal_places
    scaled_numerator = value.numerator * scale
    negative = scaled_numerator < 0
    quotient, remainder = divmod(abs(scaled_numerator), value.denominator)
    doubled = remainder * 2
    if doubled > value.denominator or (
        doubled == value.denominator and quotient % 2 == 1
    ):
        quotient += 1
    if negative:
        quotient = -quotient
    rendered = _format_scaled_integer(quotient, decimal_places)
    if len(rendered) > _MAX_NUMERIC_CHARACTERS:
        raise ValueError("aggregate exceeds the bounded canonical representation")
    return rendered


def _encode_csv(header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    target = io.StringIO(newline="")
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return target.getvalue().encode("utf-8")


def _resolve_timezone_rules(
    evidence: OperationalDatasetEvidence,
    timezone_rules: OperationalTimezoneRules | None,
) -> tuple[str | None, ZoneInfo | None]:
    if evidence.timezone_treatment != "named_zone_to_utc":
        if timezone_rules is not None:
            raise OperationalNormalizationError(
                "TIMEZONE_NORMALIZATION_FAILED",
                "timezone_rules apply only to named_zone_to_utc evidence.",
            )
        return None, None
    if timezone_rules is None:
        raise OperationalNormalizationError(
            "TIMEZONE_NORMALIZATION_FAILED",
            "named-zone evidence requires caller-supplied TZif bytes for the exact "
            "declared source_timezone.",
        )
    try:
        # Reconstruct the complete value at the consumption boundary so even a
        # forged/bypassed frozen dataclass cannot inject malformed provenance.
        validated_rules = OperationalTimezoneRules(
            source_timezone=timezone_rules.source_timezone,
            tzif_bytes=timezone_rules.tzif_bytes,
            source_locator=timezone_rules.source_locator,
        )
        if validated_rules.source_timezone != evidence.source_timezone:
            raise ValueError("timezone rules do not match the declared source_timezone")
        zone = ZoneInfo.from_file(
            io.BytesIO(validated_rules.tzif_bytes), key=validated_rules.source_timezone
        )
    # The stdlib parser is an implementation boundary whose documented
    # exception surface is not closed across supported Python versions.
    except Exception as exc:  # noqa: BLE001
        raise OperationalNormalizationError(
            "TIMEZONE_NORMALIZATION_FAILED", "timezone_rules contain invalid TZif data."
        ) from exc
    return validated_rules.identity, zone


def _elapsed_microseconds(delta: timedelta) -> int:
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


def _timeseries_group_quality(
    evidence: OperationalDatasetEvidence,
    group_key: str,
    rows: list[_ParsedRow],
    findings: list[str],
    named_zone: ZoneInfo | None,
) -> OperationalGroupQualityReceipt:
    valid_rows = [row for row in rows if row.timestamp_utc is not None]
    timestamps = [row.timestamp_utc for row in valid_rows]
    concrete_times = [value for value in timestamps if value is not None]
    actual_start_dt = min(concrete_times) if concrete_times else None
    actual_end_dt = max(concrete_times) if concrete_times else None
    actual_start = _format_utc(actual_start_dt) if actual_start_dt else None
    actual_end = _format_utc(actual_end_dt) if actual_end_dt else None
    declared_start = _parse_canonical_utc(
        evidence.coverage_start_utc, "coverage_start_utc"
    )
    declared_end = _parse_canonical_utc(evidence.coverage_end_utc, "coverage_end_utc")
    coverage_mismatch = int(
        actual_start_dt != declared_start or actual_end_dt != declared_end
    )
    if coverage_mismatch:
        findings.append(
            f"group={group_key};coverage_mismatch="
            f"declared[{evidence.coverage_start_utc},{evidence.coverage_end_utc}];"
            f"actual[{actual_start},{actual_end}]"
        )

    duplicate_count = 0
    seen: set[datetime] = set()
    for row in valid_rows:
        assert row.timestamp_utc is not None
        if row.timestamp_utc in seen:
            duplicate_count += 1
            findings.append(
                f"row={row.source_row_number};group={group_key};duplicate_timestamp"
            )
        seen.add(row.timestamp_utc)

    source_order_violation_count = 0
    for previous, current in zip(valid_rows, valid_rows[1:], strict=False):
        assert previous.timestamp_utc is not None
        assert current.timestamp_utc is not None
        if current.timestamp_utc < previous.timestamp_utc:
            source_order_violation_count += 1
            findings.append(
                f"row={current.source_row_number};group={group_key};source_order_violation"
            )

    gap_count = 0
    drift_count = 0
    if evidence.interval_basis == "fixed_seconds":
        interval_us = int(evidence.interval_seconds or 0) * 1_000_000
        declared_span_us = _elapsed_microseconds(declared_end - declared_start)
        if declared_span_us % interval_us:
            drift_count += 1
            findings.append(f"group={group_key};declared_coverage_off_grid")
            expected_count = None
        else:
            expected_count = declared_span_us // interval_us + 1
        on_grid: set[datetime] = set()
        for row in valid_rows:
            assert row.timestamp_utc is not None
            timestamp = row.timestamp_utc
            offset_us = _elapsed_microseconds(timestamp - declared_start)
            if (
                timestamp < declared_start
                or timestamp > declared_end
                or offset_us % interval_us
            ):
                drift_count += 1
                findings.append(
                    f"group={group_key};timestamp={_format_utc(timestamp)};off_grid"
                )
            else:
                on_grid.add(timestamp)
        if expected_count is not None:
            gap_count = max(0, expected_count - len(on_grid))
            if gap_count:
                findings.append(f"group={group_key};missing_intervals={gap_count}")
    elif evidence.interval_basis == "calendar_month":
        valid_walls = [
            row.source_wall_time
            for row in valid_rows
            if row.source_wall_time is not None
        ]
        if evidence.timezone_treatment == "named_zone_to_utc":
            if named_zone is None:
                raise OperationalNormalizationError(
                    "TIMEZONE_NORMALIZATION_FAILED",
                    "calendar-month named-zone QA requires supplied TZif rules.",
                )
            try:
                declared_start_wall = declared_start.astimezone(named_zone).replace(
                    tzinfo=None
                )
                declared_end_wall = declared_end.astimezone(named_zone).replace(
                    tzinfo=None
                )
            except (OverflowError, ValueError) as exc:
                raise OperationalNormalizationError(
                    "TIMEZONE_NORMALIZATION_FAILED",
                    "declared calendar coverage falls outside the supplied "
                    "timezone's representable datetime range.",
                ) from exc
        else:
            declared_start_wall = declared_start.replace(tzinfo=None)
            declared_end_wall = declared_end.replace(tzinfo=None)
        declared_start_index = (
            declared_start_wall.year * 12 + declared_start_wall.month - 1
        )
        declared_end_index = declared_end_wall.year * 12 + declared_end_wall.month - 1
        if (
            declared_start_wall.day != 1
            or declared_start_wall.time() != datetime.min.time()
            or declared_end_wall.day != 1
            or declared_end_wall.time() != datetime.min.time()
        ):
            drift_count += 1
            findings.append(f"group={group_key};declared_calendar_coverage_off_grid")
        month_indices: set[int] = set()
        for wall in valid_walls:
            assert wall is not None
            month_index = wall.year * 12 + wall.month - 1
            if wall.day != 1 or wall.time() != datetime.min.time():
                drift_count += 1
                findings.append(
                    f"group={group_key};wall_time={wall.isoformat()};calendar_month_drift"
                )
            month_indices.add(month_index)
        expected_months = declared_end_index - declared_start_index + 1
        in_range = {
            item
            for item in month_indices
            if declared_start_index <= item <= declared_end_index
        }
        gap_count = max(0, expected_months - len(in_range))
        if gap_count:
            findings.append(f"group={group_key};missing_months={gap_count}")

    return OperationalGroupQualityReceipt(
        group_key=group_key,
        included_row_count=len(rows),
        actual_coverage_start_utc=actual_start,
        actual_coverage_end_utc=actual_end,
        coverage_mismatch_count=coverage_mismatch,
        duplicate_key_count=duplicate_count,
        gap_count=gap_count,
        interval_drift_count=drift_count,
        source_order_violation_count=source_order_violation_count,
    )


def _initial_receipt(
    evidence: OperationalDatasetEvidence,
    *,
    source_columns: tuple[str, ...],
    normalized_roles: tuple[str, ...],
    column_exclusions: tuple[OperationalColumnExclusion, ...],
    method_sha256: str,
    timezone_database: str | None,
    timezone_source_locator: str | None,
    group_universe_normalized_sha256: str | None,
    expected_group_keys: tuple[str, ...],
    missing_group_keys: tuple[str, ...],
    unexpected_group_keys: tuple[str, ...],
    raw_row_count: int,
    row_exclusions: tuple[OperationalExcludedRowReceipt, ...],
    included_row_count: int,
    empty_dataset_count: int,
    group_receipts: tuple[OperationalGroupQualityReceipt, ...],
    normalized_sha256: str | None,
    actual_start: str | None,
    actual_end: str | None,
    coverage_mismatch_count: int,
    duplicate_key_count: int,
    gap_count: int,
    interval_drift_count: int,
    source_order_violation_count: int,
    nonfinite_value_count: int,
    invalid_value_count: int,
    ambiguous_count: int,
    nonexistent_count: int,
    findings: tuple[str, ...],
) -> OperationalQualityReceipt:
    passed = not any(
        (
            coverage_mismatch_count,
            empty_dataset_count,
            duplicate_key_count,
            gap_count,
            interval_drift_count,
            source_order_violation_count,
            nonfinite_value_count,
            invalid_value_count,
            len(missing_group_keys),
            len(unexpected_group_keys),
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
        timezone_source_locator=timezone_source_locator,
        timezone_rule_attestation=(
            "caller_attested_zone_payload" if timezone_database is not None else None
        ),
        interval_basis=evidence.interval_basis,
        interval_seconds=evidence.interval_seconds,
        coverage_start_utc=evidence.coverage_start_utc,
        coverage_end_utc=evidence.coverage_end_utc,
        declared_row_count=evidence.row_count,
        raw_row_count=raw_row_count,
        included_row_count=included_row_count,
        excluded_row_count=len(row_exclusions),
        empty_dataset_count=empty_dataset_count,
        source_columns=source_columns,
        normalized_roles=normalized_roles,
        column_bindings=evidence.columns,
        column_exclusions=column_exclusions,
        row_exclusions=row_exclusions,
        group_universe_normalized_sha256=group_universe_normalized_sha256,
        expected_group_keys=expected_group_keys,
        missing_group_keys=missing_group_keys,
        unexpected_group_keys=unexpected_group_keys,
        group_receipts=group_receipts,
        actual_coverage_start_utc=actual_start,
        actual_coverage_end_utc=actual_end,
        coverage_mismatch_count=coverage_mismatch_count,
        duplicate_key_count=duplicate_key_count,
        gap_count=gap_count,
        interval_drift_count=interval_drift_count,
        source_order_violation_count=source_order_violation_count,
        nonfinite_value_count=nonfinite_value_count,
        invalid_value_count=invalid_value_count,
        ambiguous_time_resolution_count=ambiguous_count,
        nonexistent_time_resolution_count=nonexistent_count,
        findings=findings,
        quality_passed=passed,
    )


def _normalize_operational_csv_artifacts(
    source_bytes: bytes,
    evidence: OperationalDatasetEvidence,
    *,
    lineage_source_bytes: tuple[bytes, ...] = (),
    derivation_method_bytes: bytes | None = None,
    timezone_rules: OperationalTimezoneRules | None = None,
    group_universe: OperationalGroupUniverse | None = None,
    column_exclusions: tuple[OperationalColumnExclusion, ...] = (),
    row_exclusions: tuple[OperationalRowExclusion, ...] = (),
) -> _NormalizationArtifacts:
    """Compute verified normalization artifacts without constructing a result.

    Quality failures raise ``OperationalNormalizationError`` with a completed
    receipt.  The caller therefore cannot accidentally consume a defective
    normalized artifact while retaining the evidence needed to remediate it.
    """

    if not isinstance(evidence, OperationalDatasetEvidence):
        raise OperationalNormalizationError(
            "INVALID_VALUE", "evidence must be OperationalDatasetEvidence."
        )
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
    if (
        evidence.interval_basis == "fixed_seconds"
        and evidence.interval_seconds is not None
        and evidence.interval_seconds > _MAX_FIXED_INTERVAL_SECONDS
    ):
        raise OperationalNormalizationError(
            "QUALITY_CHECK_FAILED",
            "fixed interval exceeds the bounded 31-day operational QA interval.",
        )
    if timezone_rules is not None and not isinstance(
        timezone_rules, OperationalTimezoneRules
    ):
        raise OperationalNormalizationError(
            "TIMEZONE_NORMALIZATION_FAILED",
            "timezone_rules must be OperationalTimezoneRules or None.",
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
    grouped_timeseries = "asset_id" in roles and evidence.kind != "asset"
    if grouped_timeseries:
        if not isinstance(group_universe, OperationalGroupUniverse):
            raise OperationalNormalizationError(
                "GROUP_UNIVERSE_FAILED",
                "grouped time series require a verified normalized asset universe.",
            )
    elif group_universe is not None:
        raise OperationalNormalizationError(
            "GROUP_UNIVERSE_FAILED",
            "group universes apply only to grouped time-series evidence.",
        )
    source_index = {name: index for index, name in enumerate(header)}
    timezone_database, named_zone = _resolve_timezone_rules(evidence, timezone_rules)
    method_sha = _normalization_method_sha(
        evidence,
        column_exclusions,
        row_exclusions,
        timezone_rules,
        group_universe,
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
                        _parse_timestamp(raw_value, evidence, named_zone)
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
            except OperationalNormalizationError:
                raise
            except OverflowError as exc:
                if binding.role == "timestamp_utc":
                    raise OperationalNormalizationError(
                        "TIMEZONE_NORMALIZATION_FAILED",
                        "timestamp conversion falls outside the representable "
                        "datetime range.",
                    ) from exc
                nonfinite_count += 1
                findings.append(f"row={row_number};role={binding.role};nonfinite")
                normalized = raw_value
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
        if "asset_id" not in role_values:
            asset_group = "__dataset__"
        else:
            asset_group = role_values["asset_id"]
            if (
                not asset_group
                or asset_group.strip() != asset_group
                or "\n" in asset_group
                or "\r" in asset_group
            ):
                asset_group = f"__invalid_asset_id_row_{row_number}"
        parsed_rows.append(
            _ParsedRow(
                source_row_number=row_number,
                values=tuple(role_values[role] for role in roles),
                role_values=role_values,
                timestamp_utc=timestamp,
                source_wall_time=wall_time,
                group_key=asset_group,
            )
        )

    groups: dict[str, list[_ParsedRow]] = {}
    for row in parsed_rows:
        groups.setdefault(row.group_key, []).append(row)
    empty_dataset_count = int(not parsed_rows)
    if empty_dataset_count:
        findings.append("included_dataset_is_empty")

    group_receipts: tuple[OperationalGroupQualityReceipt, ...] = ()
    duplicate_count = 0
    gap_count = 0
    drift_count = 0
    source_order_violation_count = 0
    coverage_mismatch = 0
    expected_group_keys = (
        group_universe.group_keys if group_universe is not None else ()
    )
    observed_group_keys = tuple(sorted(groups))
    missing_group_keys = tuple(
        sorted(set(expected_group_keys) - set(observed_group_keys))
    )
    unexpected_group_keys = (
        tuple(sorted(set(observed_group_keys) - set(expected_group_keys)))
        if grouped_timeseries
        else ()
    )
    if missing_group_keys:
        findings.append(f"missing_groups={','.join(missing_group_keys)}")
    if unexpected_group_keys:
        findings.append(f"unexpected_groups={','.join(unexpected_group_keys)}")
    if evidence.kind == "asset":
        asset_receipts: list[OperationalGroupQualityReceipt] = []
        for group_key in sorted(groups):
            rows = groups[group_key]
            group_duplicates = max(0, len(rows) - 1)
            duplicate_count += group_duplicates
            if group_duplicates:
                findings.append(
                    f"group={group_key};duplicate_asset_rows={group_duplicates}"
                )
            asset_receipts.append(
                OperationalGroupQualityReceipt(
                    group_key=group_key,
                    included_row_count=len(rows),
                    actual_coverage_start_utc=None,
                    actual_coverage_end_utc=None,
                    coverage_mismatch_count=0,
                    duplicate_key_count=group_duplicates,
                    gap_count=0,
                    interval_drift_count=0,
                    source_order_violation_count=0,
                )
            )
        group_receipts = tuple(asset_receipts)
    else:
        quality_group_keys = (
            tuple(sorted(set(expected_group_keys).union(observed_group_keys)))
            if grouped_timeseries
            else observed_group_keys
        )
        group_receipts = tuple(
            _timeseries_group_quality(
                evidence,
                group_key,
                groups.get(group_key, []),
                findings,
                named_zone,
            )
            for group_key in quality_group_keys
        )
        coverage_mismatch = sum(item.coverage_mismatch_count for item in group_receipts)
        duplicate_count = sum(item.duplicate_key_count for item in group_receipts)
        gap_count = sum(item.gap_count for item in group_receipts)
        drift_count = sum(item.interval_drift_count for item in group_receipts)
        source_order_violation_count = sum(
            item.source_order_violation_count for item in group_receipts
        )

    valid_times = [
        row.timestamp_utc for row in parsed_rows if row.timestamp_utc is not None
    ]
    actual_start = _format_utc(min(valid_times)) if valid_times else None
    actual_end = _format_utc(max(valid_times)) if valid_times else None
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
        timezone_database=timezone_database,
        timezone_source_locator=(
            timezone_rules.source_locator if timezone_rules is not None else None
        ),
        group_universe_normalized_sha256=(
            group_universe.normalized_sha256 if group_universe is not None else None
        ),
        expected_group_keys=expected_group_keys,
        missing_group_keys=missing_group_keys,
        unexpected_group_keys=unexpected_group_keys,
        raw_row_count=len(raw_rows),
        row_exclusions=excluded_receipts,
        included_row_count=len(parsed_rows),
        empty_dataset_count=empty_dataset_count,
        group_receipts=group_receipts,
        normalized_sha256=normalized_sha,
        actual_start=actual_start,
        actual_end=actual_end,
        coverage_mismatch_count=coverage_mismatch,
        duplicate_key_count=duplicate_count,
        gap_count=gap_count,
        interval_drift_count=drift_count,
        source_order_violation_count=source_order_violation_count,
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
    return _NormalizationArtifacts(
        normalized_csv_bytes=normalized_bytes,
        normalized_rows=normalized_rows,
        receipt=receipt,
    )


def normalize_operational_csv(
    source_bytes: bytes,
    evidence: OperationalDatasetEvidence,
    *,
    lineage_source_bytes: tuple[bytes, ...] = (),
    derivation_method_bytes: bytes | None = None,
    timezone_rules: OperationalTimezoneRules | None = None,
    group_universe: OperationalGroupUniverse | None = None,
    column_exclusions: tuple[OperationalColumnExclusion, ...] = (),
    row_exclusions: tuple[OperationalRowExclusion, ...] = (),
) -> OperationalNormalizationResult:
    """Verify and normalize one D1-bound UTF-8 CSV artifact.

    Quality failures raise ``OperationalNormalizationError`` with a completed
    receipt when tabular inspection is possible.  Successful results replay
    this deterministic computation during construction so their normalized
    measurements cannot be substituted independently of retained source bytes.
    """

    artifacts = _normalize_operational_csv_artifacts(
        source_bytes,
        evidence,
        lineage_source_bytes=lineage_source_bytes,
        derivation_method_bytes=derivation_method_bytes,
        timezone_rules=timezone_rules,
        group_universe=group_universe,
        column_exclusions=column_exclusions,
        row_exclusions=row_exclusions,
    )
    return OperationalNormalizationResult(
        evidence=evidence,
        source_bytes=source_bytes,
        lineage_source_bytes=lineage_source_bytes,
        derivation_method_bytes=derivation_method_bytes,
        timezone_rules=timezone_rules,
        group_universe=group_universe,
        normalized_csv_bytes=artifacts.normalized_csv_bytes,
        normalized_rows=artifacts.normalized_rows,
        receipt=artifacts.receipt,
        _factory_token=_NORMALIZATION_RESULT_TOKEN,
    )


def _aggregation_method_sha(
    normalized: OperationalNormalizationResult,
    spec: OperationalAggregationSpec,
    source_interval: int,
) -> str:
    return _method_sha(
        {
            "version": _AGGREGATOR_VERSION,
            "source_normalized_sha256": normalized.receipt.normalized_sha256,
            "spec": spec.model_dump(),
            "source_interval_seconds": source_interval,
            "timestamp_position": "interval_start",
            "utc_elapsed_time_basis": True,
            "numeric_policy": {
                "energy_sum": "exact_decimal_fraction_v1",
                "power_mean_decimal_places": _POWER_MEAN_DECIMAL_PLACES,
                "power_mean_rounding": _POWER_MEAN_ROUNDING,
                "max_numeric_characters": _MAX_NUMERIC_CHARACTERS,
                "max_points_per_bucket": _MAX_POINTS_PER_BUCKET,
            },
        }
    )


def _aggregate_rows(
    normalized: OperationalNormalizationResult,
    spec: OperationalAggregationSpec,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...], int]:
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
    if source_interval > _MAX_FIXED_INTERVAL_SECONDS:
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            "source interval exceeds the bounded operational interval.",
        )
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
    if expected_per_bucket > _MAX_POINTS_PER_BUCKET:
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            f"aggregation buckets may contain at most {_MAX_POINTS_PER_BUCKET} points.",
        )
    buckets: dict[tuple[str, int], list[tuple[datetime, Fraction]]] = {}
    for row in normalized.normalized_rows:
        timestamp = _parse_canonical_utc(row[timestamp_index], "timestamp_utc")
        elapsed_microseconds = _elapsed_microseconds(timestamp - anchor)
        if elapsed_microseconds < 0 or elapsed_microseconds % 1_000_000:
            raise OperationalNormalizationError(
                "AGGREGATION_CONTRACT_FAILED",
                "all timestamps must be integral seconds at or after anchor_utc.",
            )
        bucket_number = elapsed_microseconds // (
            spec.target_interval_seconds * 1_000_000
        )
        asset = row[asset_index] if asset_index is not None else "__dataset__"
        bucket = buckets.setdefault((asset, bucket_number), [])
        if len(bucket) >= _MAX_POINTS_PER_BUCKET:
            raise OperationalNormalizationError(
                "AGGREGATION_CONTRACT_FAILED",
                f"aggregation buckets may contain at most {_MAX_POINTS_PER_BUCKET} points.",
            )
        bucket.append((timestamp, _fraction_from_canonical_decimal(row[value_index])))
    if not buckets:
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            "aggregation requires at least one input row.",
        )
    output: list[tuple[str, ...]] = []
    for (asset, bucket_number), points in sorted(
        buckets.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        bucket_start = anchor + timedelta(
            seconds=bucket_number * spec.target_interval_seconds
        )
        slots: set[int] = set()
        for timestamp, _ in points:
            offset_us = _elapsed_microseconds(timestamp - bucket_start)
            source_interval_us = source_interval * 1_000_000
            if offset_us < 0 or offset_us % source_interval_us:
                raise OperationalNormalizationError(
                    "AGGREGATION_CONTRACT_FAILED",
                    f"misaligned bucket at {_format_utc(bucket_start)} for {asset!r}.",
                )
            slot = offset_us // source_interval_us
            if slot >= expected_per_bucket:
                raise OperationalNormalizationError(
                    "AGGREGATION_CONTRACT_FAILED",
                    f"misaligned bucket at {_format_utc(bucket_start)} for {asset!r}.",
                )
            slots.add(slot)
        if (
            len(points) != expected_per_bucket
            or len(slots) != expected_per_bucket
            or min(slots) != 0
            or max(slots) != expected_per_bucket - 1
        ):
            raise OperationalNormalizationError(
                "AGGREGATION_CONTRACT_FAILED",
                f"partial or misaligned bucket at {_format_utc(bucket_start)} for {asset!r}.",
            )
        total = sum((point[1] for point in points), Fraction(0))
        aggregate = (
            _exact_terminating_fraction(total)
            if spec.method == "sum"
            else _round_fraction_half_even(
                total / expected_per_bucket, int(spec.rounding_decimal_places or 0)
            )
        )
        values = [_format_utc(bucket_start)]
        if asset_index is not None:
            values.append(asset)
        values.append(aggregate)
        output.append(tuple(values))
    header = (
        ("timestamp_utc",)
        + (("asset_id",) if asset_index is not None else ())
        + (spec.value_role,)
    )
    return header, tuple(output), source_interval


def aggregate_operational_series(
    normalized: OperationalNormalizationResult,
    spec: OperationalAggregationSpec,
) -> OperationalAggregationResult:
    """Aggregate a complete fixed-cadence series by UTC elapsed-time buckets."""

    if not isinstance(normalized, OperationalNormalizationResult):
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            "normalized must be OperationalNormalizationResult.",
        )
    if not isinstance(spec, OperationalAggregationSpec):
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            "spec must be OperationalAggregationSpec.",
        )
    try:
        header, rows, source_interval = _aggregate_rows(normalized, spec)
        csv_bytes = _encode_csv(header, rows)
        receipt = OperationalAggregationReceipt(
            schema=OPERATIONAL_AGGREGATION_SCHEMA,
            logical_id=normalized.evidence.logical_id,
            source_normalized_sha256=str(normalized.receipt.normalized_sha256),
            aggregate_sha256=_sha256(csv_bytes),
            method_sha256=_aggregation_method_sha(normalized, spec, source_interval),
            value_role=spec.value_role,
            value_unit="kWh" if spec.value_role == "energy_kwh" else "kW",
            method=spec.method,
            source_interval_seconds=source_interval,
            target_interval_seconds=spec.target_interval_seconds,
            anchor_utc=spec.anchor_utc,
            source_timestamp_position=spec.source_timestamp_position,
            value_basis=spec.value_basis,
            arithmetic_policy=spec.arithmetic_policy,
            rounding_decimal_places=spec.rounding_decimal_places,
            input_row_count=len(normalized.normalized_rows),
            output_row_count=len(rows),
        )
        return OperationalAggregationResult(
            normalized=normalized,
            spec=spec,
            header=header,
            rows=rows,
            csv_bytes=csv_bytes,
            receipt=receipt,
            _factory_token=_AGGREGATION_RESULT_TOKEN,
        )
    except OperationalNormalizationError:
        raise
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise OperationalNormalizationError(
            "AGGREGATION_CONTRACT_FAILED",
            f"aggregation could not be completed safely: {exc}",
        ) from exc


__all__ = [
    "OPERATIONAL_AGGREGATION_SCHEMA",
    "OPERATIONAL_NORMALIZATION_SCHEMA",
    "OperationalAggregationMethod",
    "OperationalAggregationReceipt",
    "OperationalAggregationResult",
    "OperationalAggregationSpec",
    "OperationalColumnExclusion",
    "OperationalExcludedRowReceipt",
    "OperationalGroupQualityReceipt",
    "OperationalGroupUniverse",
    "OperationalNormalizationError",
    "OperationalNormalizationErrorCode",
    "OperationalNormalizationResult",
    "OperationalQualityReceipt",
    "OperationalRowExclusion",
    "OperationalTimezoneRules",
    "aggregate_operational_series",
    "normalize_operational_csv",
]
