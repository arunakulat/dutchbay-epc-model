from __future__ import annotations

import hashlib
import importlib.resources
import subprocess
import sys
from dataclasses import replace
from decimal import Context, localcontext
from typing import Any
from zoneinfo import reset_tzpath

import pytest

import analytics.operational.normalization as operational_normalization
from analytics.operational.contracts import (
    OperationalColumnBinding,
    OperationalDatasetEvidence,
)
from analytics.operational.normalization import (
    OPERATIONAL_AGGREGATION_SCHEMA,
    OPERATIONAL_NORMALIZATION_SCHEMA,
    OperationalAggregationSpec,
    OperationalColumnExclusion,
    OperationalGroupUniverse,
    OperationalNormalizationError,
    OperationalNormalizationResult,
    OperationalRowExclusion,
    OperationalTimezoneRules,
    aggregate_operational_series,
    normalize_operational_csv,
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _asset_group_universe(*asset_ids: str) -> OperationalGroupUniverse:
    data = (
        "asset,rated\n" + "".join(f"{asset_id},5000\n" for asset_id in asset_ids)
    ).encode()
    evidence = OperationalDatasetEvidence(
        logical_id="assets.primary",
        kind="asset",
        source_class="declared_asset",
        timezone_treatment="not_applicable",
        source_timezone=None,
        ambiguous_time_policy="not_applicable",
        nonexistent_time_policy="not_applicable",
        observation_status="declared_metadata",
        lineage_source_sha256=(),
        derivation_method_sha256=None,
        source_locator="evidence/assets.csv",
        source_sha256=_digest(data),
        coverage_start_utc="2025-01-01T00:00:00Z",
        coverage_end_utc="2025-01-02T00:00:00Z",
        interval_basis="not_applicable",
        interval_seconds=None,
        row_count=len(asset_ids),
        columns=(
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("rated_power_kw", "rated", "kW"),
        ),
    )
    return OperationalGroupUniverse(normalize_operational_csv(data, evidence))


def _normalize_scada(
    data: bytes,
    evidence: OperationalDatasetEvidence,
    *,
    expected_assets: tuple[str, ...] = ("T01",),
    **kwargs: Any,
) -> OperationalNormalizationResult:
    return normalize_operational_csv(
        data,
        evidence,
        group_universe=_asset_group_universe(*expected_assets),
        **kwargs,
    )


def _timezone_rules(zone: str = "Europe/London") -> OperationalTimezoneRules:
    resource = importlib.resources.files("tzdata.zoneinfo").joinpath(*zone.split("/"))
    return OperationalTimezoneRules(
        source_timezone=zone,
        tzif_bytes=resource.read_bytes(),
        source_locator=f"python-package:tzdata/{zone}",
    )


def _unterminated_tzif2_payload() -> bytes:
    counts = (0, 0, 0, 0, 1, 4)
    header = (
        b"TZif2"
        + b"\x00" * 15
        + b"".join(value.to_bytes(4, "big", signed=True) for value in counts)
    )
    block = b"\x00" * 6 + b"UTC\x00"
    return header + block + header + block + b"\nUTC0"


def _tzif1_payload(
    *, utc_offset: int = 0, leap_records: tuple[tuple[int, int], ...] = ()
) -> bytes:
    counts = (0, 0, len(leap_records), 0, 1, 4)
    header = (
        b"TZif\x00"
        + b"\x00" * 15
        + b"".join(value.to_bytes(4, "big", signed=True) for value in counts)
    )
    local_time_type = utc_offset.to_bytes(4, "big", signed=True) + b"\x00\x00"
    leaps = b"".join(
        instant.to_bytes(4, "big", signed=True)
        + correction.to_bytes(4, "big", signed=True)
        for instant, correction in leap_records
    )
    return header + local_time_type + b"UTC\x00" + leaps


def _scada_evidence(
    data: bytes,
    *,
    row_count: int = 4,
    start: str = "2025-01-01T00:00:00Z",
    end: str = "2025-01-01T00:30:00Z",
    interval: int = 600,
    timezone_treatment: str = "source_utc",
    source_timezone: str | None = None,
    ambiguous: str = "not_applicable",
    nonexistent: str = "not_applicable",
    columns: tuple[OperationalColumnBinding, ...] | None = None,
) -> OperationalDatasetEvidence:
    return OperationalDatasetEvidence(
        logical_id="scada.primary",
        kind="scada",
        source_class="observed_plant",
        timezone_treatment=timezone_treatment,  # type: ignore[arg-type]
        source_timezone=source_timezone,
        ambiguous_time_policy=ambiguous,  # type: ignore[arg-type]
        nonexistent_time_policy=nonexistent,  # type: ignore[arg-type]
        observation_status="observed",
        lineage_source_sha256=(),
        derivation_method_sha256=None,
        source_locator="evidence/scada.csv",
        source_sha256=_digest(data),
        coverage_start_utc=start,
        coverage_end_utc=end,
        interval_basis="fixed_seconds",
        interval_seconds=interval,
        row_count=row_count,
        columns=columns
        or (
            OperationalColumnBinding("timestamp_utc", "timestamp", "iso8601_utc"),
            OperationalColumnBinding("asset_id", "turbine", "1"),
            OperationalColumnBinding("power_kw", "power", "kW"),
        ),
    )


@pytest.fixture
def scada_csv() -> bytes:
    return (
        b"timestamp,turbine,power\n"
        b"2025-01-01T00:00:00Z,T01,1.00\n"
        b"2025-01-01T00:10:00Z,T01,2e0\n"
        b"2025-01-01T00:20:00Z,T01,3.000\n"
        b"2025-01-01T00:30:00Z,T01,4\n"
    )


def test_normalizes_deterministically_and_preserves_source_bytes(
    scada_csv: bytes,
) -> None:
    evidence = _scada_evidence(scada_csv)
    first = _normalize_scada(scada_csv, evidence)
    second = _normalize_scada(scada_csv, evidence)

    assert first == second
    assert first.source_bytes is scada_csv
    assert first.normalized_csv_bytes == (
        b"timestamp_utc,asset_id,power_kw\n"
        b"2025-01-01T00:00:00Z,T01,1\n"
        b"2025-01-01T00:10:00Z,T01,2\n"
        b"2025-01-01T00:20:00Z,T01,3\n"
        b"2025-01-01T00:30:00Z,T01,4\n"
    )
    assert first.receipt.schema == OPERATIONAL_NORMALIZATION_SCHEMA
    assert first.receipt.source_sha256 == _digest(scada_csv)
    assert first.receipt.normalized_sha256 == _digest(first.normalized_csv_bytes)
    assert first.receipt.column_bindings[2].unit == "kW"
    assert first.receipt.timezone_treatment == "source_utc"
    assert first.receipt.quality_passed is True
    assert first.receipt.canonical_finance_eligible is False
    assert first.receipt.bankable is False


def test_requires_exact_source_digest(scada_csv: bytes) -> None:
    evidence = replace(_scada_evidence(scada_csv), source_sha256="0" * 64)
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(scada_csv, evidence)
    assert raised.value.code == "SOURCE_DIGEST_MISMATCH"
    assert raised.value.receipt is None


def test_requires_complete_explicit_column_accounting(scada_csv: bytes) -> None:
    data = (
        scada_csv.replace(b"power\n", b"power,comment\n")
        .replace(b",1.00\n", b",1.00,a\n")
        .replace(b",2e0\n", b",2e0,b\n")
        .replace(b",3.000\n", b",3.000,c\n")
        .replace(b",4\n", b",4,d\n")
    )
    evidence = _scada_evidence(data)
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence)
    assert raised.value.code == "COLUMN_ACCOUNTING_FAILED"

    result = _normalize_scada(
        data,
        evidence,
        column_exclusions=(OperationalColumnExclusion("comment", "operator note"),),
    )
    assert result.receipt.source_columns[-1] == "comment"
    assert result.receipt.column_exclusions[0].reason == "operator note"


@pytest.mark.parametrize(
    ("data", "expected_code"),
    [
        (b"\xef\xbb\xbftimestamp,turbine,power\n", "INVALID_CSV"),
        (b"timestamp,timestamp,power\n", "COLUMN_ACCOUNTING_FAILED"),
        (b"timestamp,turbine,power\n2025-01-01T00:00:00Z,T01\n", "INVALID_CSV"),
    ],
)
def test_rejects_hostile_csv_shape(data: bytes, expected_code: str) -> None:
    evidence = _scada_evidence(data, row_count=max(1, data.count(b"\n") - 1))
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence)
    assert raised.value.code == expected_code


def test_row_exclusion_is_hashed_and_quality_failure_is_receipted(
    scada_csv: bytes,
) -> None:
    evidence = _scada_evidence(scada_csv)
    with pytest.raises(OperationalNormalizationError) as raised:
        _normalize_scada(
            scada_csv,
            evidence,
            row_exclusions=(OperationalRowExclusion(2, "sensor maintenance"),),
        )
    receipt = raised.value.receipt
    assert raised.value.code == "QUALITY_CHECK_FAILED"
    assert receipt is not None
    assert receipt.excluded_row_count == 1
    assert receipt.row_exclusions[0].source_row_number == 2
    assert len(receipt.row_exclusions[0].parsed_row_sha256) == 64
    assert receipt.gap_count == 1


@pytest.mark.parametrize(
    ("replacement", "field", "count"),
    [
        (
            (b"2025-01-01T00:20:00Z", b"2025-01-01T00:10:00Z"),
            "duplicate_key_count",
            1,
        ),
        (
            (b"2025-01-01T00:20:00Z", b"2025-01-01T00:30:00Z"),
            "gap_count",
            1,
        ),
        (
            (b"2025-01-01T00:20:00Z", b"2025-01-01T00:25:00Z"),
            "interval_drift_count",
            1,
        ),
        ((b"3.000", b"NaN"), "nonfinite_value_count", 1),
        ((b"3.000", b"not-a-number"), "invalid_value_count", 1),
    ],
)
def test_quality_defects_fail_with_deterministic_receipt(
    scada_csv: bytes,
    replacement: tuple[bytes, bytes],
    field: str,
    count: int,
) -> None:
    data = scada_csv.replace(*replacement)
    evidence = _scada_evidence(data)
    with pytest.raises(OperationalNormalizationError) as raised:
        _normalize_scada(data, evidence)
    receipt = raised.value.receipt
    assert raised.value.code == "QUALITY_CHECK_FAILED"
    assert receipt is not None
    assert getattr(receipt, field) == count
    assert receipt.quality_passed is False
    if field.endswith("value_count"):
        assert receipt.normalized_sha256 is None


def test_coverage_is_recomputed_not_trusted(scada_csv: bytes) -> None:
    evidence = _scada_evidence(scada_csv, end="2025-01-01T00:40:00Z")
    with pytest.raises(OperationalNormalizationError) as raised:
        _normalize_scada(scada_csv, evidence)
    assert raised.value.receipt is not None
    assert raised.value.receipt.coverage_mismatch_count == 1
    assert raised.value.receipt.actual_coverage_end_utc == "2025-01-01T00:30:00Z"


def test_coverage_compares_utc_instants_not_string_spelling(scada_csv: bytes) -> None:
    evidence = _scada_evidence(
        scada_csv,
        start="2025-01-01T00:00:00.000Z",
        end="2025-01-01T00:30:00.000000Z",
    )
    result = _normalize_scada(scada_csv, evidence)
    assert result.receipt.coverage_mismatch_count == 0


def test_named_zone_ambiguous_fold_is_explicit_and_tzdb_is_receipted() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-10-26T00:30:00,T01,1\n"
        b"2025-10-26T01:30:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        start="2025-10-25T23:30:00Z",
        end="2025-10-26T01:30:00Z",
        interval=7200,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="fold_1",
        nonexistent="reject",
    )
    result = _normalize_scada(data, evidence, timezone_rules=_timezone_rules())
    assert result.normalized_rows[1][0] == "2025-10-26T01:30:00Z"
    assert result.receipt.ambiguous_time_resolution_count == 1
    assert result.receipt.timezone_database is not None
    assert result.receipt.timezone_database.startswith("tzif-sha256:")


def test_named_zone_ambiguous_rejects() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-10-26T00:30:00,T01,1\n"
        b"2025-10-26T01:30:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        start="2025-10-25T23:30:00Z",
        end="2025-10-26T01:30:00Z",
        interval=7200,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        _normalize_scada(data, evidence, timezone_rules=_timezone_rules())
    assert raised.value.receipt is not None
    assert raised.value.receipt.invalid_value_count == 1


def test_named_zone_nonexistent_shift_is_explicit() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-03-30T00:30:00,T01,1\n"
        b"2025-03-30T01:30:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        start="2025-03-30T00:30:00Z",
        end="2025-03-30T01:30:00Z",
        interval=3600,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="shift_forward",
    )
    result = _normalize_scada(data, evidence, timezone_rules=_timezone_rules())
    assert result.normalized_rows[1][0] == "2025-03-30T01:30:00Z"
    assert result.receipt.nonexistent_time_resolution_count == 1


def test_named_zone_fold_zero_and_shift_backward_are_explicit() -> None:
    fold_data = (
        b"timestamp,turbine,power\n"
        b"2025-10-26T00:30:00,T01,1\n"
        b"2025-10-26T01:30:00,T01,2\n"
    )
    fold_evidence = _scada_evidence(
        fold_data,
        row_count=2,
        start="2025-10-25T23:30:00Z",
        end="2025-10-26T00:30:00Z",
        interval=3600,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="fold_0",
        nonexistent="reject",
    )
    folded = _normalize_scada(
        fold_data, fold_evidence, timezone_rules=_timezone_rules()
    )
    assert folded.normalized_rows[1][0] == "2025-10-26T00:30:00Z"

    gap_data = (
        b"timestamp,turbine,power\n"
        b"2025-03-30T01:30:00,T01,1\n"
        b"2025-03-30T02:30:00,T01,2\n"
    )
    gap_evidence = _scada_evidence(
        gap_data,
        row_count=2,
        start="2025-03-30T00:30:00Z",
        end="2025-03-30T01:30:00Z",
        interval=3600,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="shift_backward",
    )
    shifted = _normalize_scada(gap_data, gap_evidence, timezone_rules=_timezone_rules())
    assert shifted.normalized_rows[0][0] == "2025-03-30T00:30:00Z"
    assert shifted.receipt.nonexistent_time_resolution_count == 1


def test_non_hour_dst_gap_uses_supplied_tzif_rules() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-10-05T02:15:00,T01,1\n"
        b"2025-10-05T03:15:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        start="2025-10-04T15:45:00Z",
        end="2025-10-04T16:15:00Z",
        interval=1800,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Australia/Lord_Howe",
        ambiguous="reject",
        nonexistent="shift_forward",
    )
    result = _normalize_scada(
        data,
        evidence,
        timezone_rules=_timezone_rules("Australia/Lord_Howe"),
    )
    assert result.normalized_rows[0][0] == "2025-10-04T15:45:00Z"
    assert result.receipt.nonexistent_time_resolution_count == 1


def test_malformed_tzif_is_rejected_at_construction_and_normalization() -> None:
    with pytest.raises(ValueError, match="complete, structurally valid TZif"):
        OperationalTimezoneRules(
            source_timezone="Etc/UTC",
            tzif_bytes=b"TZif0",
            source_locator="hostile:truncated",
        )

    forged = object.__new__(OperationalTimezoneRules)
    object.__setattr__(forged, "source_timezone", "Europe/London")
    object.__setattr__(forged, "tzif_bytes", b"TZif0")
    object.__setattr__(forged, "source_locator", "hostile:bypassed-constructor")
    data = b"when,energy\n2025-01-01T00:00:00,1\n2025-01-01T00:01:00,2\n"
    evidence = _meter_evidence(
        data,
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T00:01:00Z",
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=60,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence, timezone_rules=forged)
    assert raised.value.code == "TIMEZONE_NORMALIZATION_FAILED"


def test_unterminated_tzif2_footer_rejects_within_subprocess_bound() -> None:
    payload_hex = _unterminated_tzif2_payload().hex()
    script = f"""
from analytics.operational.normalization import OperationalTimezoneRules
try:
    OperationalTimezoneRules('Etc/UTC', bytes.fromhex('{payload_hex}'), 'hostile:footer')
except ValueError:
    raise SystemExit(0)
raise SystemExit(1)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        timeout=3,
    )
    assert completed.returncode == 0, completed.stderr.decode()


@pytest.mark.parametrize(
    "leap_records",
    (
        pytest.param(((100, 1), (50, 2)), id="decreasing-instants"),
        pytest.param(((100, 1), (200, 3)), id="correction-jump"),
    ),
)
def test_invalid_tzif_leap_semantics_are_rejected(
    leap_records: tuple[tuple[int, int], ...],
) -> None:
    with pytest.raises(ValueError, match="complete, structurally valid TZif"):
        OperationalTimezoneRules(
            source_timezone="Etc/UTC",
            tzif_bytes=_tzif1_payload(leap_records=leap_records),
            source_locator="hostile:leap-records",
        )


def test_runtime_incompatible_rfc_offset_is_timezone_failure() -> None:
    rules = OperationalTimezoneRules(
        source_timezone="Etc/UTC",
        tzif_bytes=_tzif1_payload(utc_offset=86_400),
        source_locator="hostile:rfc-offset-outside-python-datetime",
    )
    data = b"when,energy\n2025-01-01T00:00:00,1\n2025-01-01T00:01:00,2\n"
    evidence = _meter_evidence(
        data,
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T00:01:00Z",
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=60,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Etc/UTC",
        ambiguous="reject",
        nonexistent="reject",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence, timezone_rules=rules)
    assert raised.value.code == "TIMEZONE_NORMALIZATION_FAILED"
    assert raised.value.receipt is None


@pytest.mark.parametrize(
    "invalid_locator",
    (7, "", " leading", "line\nbreak"),
)
def test_forged_timezone_locator_fails_closed_at_consumption(
    invalid_locator: object,
) -> None:
    valid = _timezone_rules()
    forged = object.__new__(OperationalTimezoneRules)
    object.__setattr__(forged, "source_timezone", valid.source_timezone)
    object.__setattr__(forged, "tzif_bytes", valid.tzif_bytes)
    object.__setattr__(forged, "source_locator", invalid_locator)
    data = b"when,energy\n2025-01-01T00:00:00,1\n2025-01-01T00:01:00,2\n"
    evidence = _meter_evidence(
        data,
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T00:01:00Z",
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=60,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence, timezone_rules=forged)
    assert raised.value.code == "TIMEZONE_NORMALIZATION_FAILED"
    assert raised.value.receipt is None


@pytest.mark.parametrize(
    ("zone", "first", "second", "start", "end"),
    (
        (
            "Asia/Kathmandu",
            "0001-01-01T00:00:00",
            "0001-01-01T00:01:00",
            "0001-01-01T00:00:00Z",
            "0001-01-01T00:01:00Z",
        ),
        (
            "America/New_York",
            "9999-12-31T23:00:00",
            "9999-12-31T23:01:00",
            "9999-12-31T23:00:00Z",
            "9999-12-31T23:01:00Z",
        ),
    ),
)
def test_named_zone_datetime_boundary_is_timezone_failure(
    zone: str, first: str, second: str, start: str, end: str
) -> None:
    data = f"when,energy\n{first},1\n{second},2\n".encode()
    evidence = _meter_evidence(
        data,
        start=start,
        end=end,
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=60,
        timezone_treatment="named_zone_to_utc",
        source_timezone=zone,
        ambiguous="reject",
        nonexistent="reject",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence, timezone_rules=_timezone_rules(zone))
    assert raised.value.code == "TIMEZONE_NORMALIZATION_FAILED"
    assert raised.value.receipt is None


def _meter_evidence(
    data: bytes,
    *,
    start: str,
    end: str,
    row_count: int,
    interval_basis: str,
    interval_seconds: int | None,
    timezone_treatment: str = "source_utc",
    source_timezone: str | None = None,
    ambiguous: str = "not_applicable",
    nonexistent: str = "not_applicable",
) -> OperationalDatasetEvidence:
    return OperationalDatasetEvidence(
        logical_id="meter.primary",
        kind="revenue_meter",
        source_class="observed_plant",
        timezone_treatment=timezone_treatment,  # type: ignore[arg-type]
        source_timezone=source_timezone,
        ambiguous_time_policy=ambiguous,  # type: ignore[arg-type]
        nonexistent_time_policy=nonexistent,  # type: ignore[arg-type]
        observation_status="observed",
        lineage_source_sha256=(),
        derivation_method_sha256=None,
        source_locator="evidence/meter.csv",
        source_sha256=_digest(data),
        coverage_start_utc=start,
        coverage_end_utc=end,
        interval_basis=interval_basis,  # type: ignore[arg-type]
        interval_seconds=interval_seconds,
        row_count=row_count,
        columns=(
            OperationalColumnBinding("timestamp_utc", "when", "iso8601_utc"),
            OperationalColumnBinding("energy_kwh", "energy", "kWh"),
        ),
    )


def test_calendar_month_uses_calendar_progression_not_31_days() -> None:
    data = (
        b"when,energy\n"
        b"2024-01-01T00:00:00Z,10\n"
        b"2024-02-01T00:00:00Z,11\n"
        b"2024-03-01T00:00:00Z,12\n"
    )
    evidence = _meter_evidence(
        data,
        start="2024-01-01T00:00:00Z",
        end="2024-03-01T00:00:00Z",
        row_count=3,
        interval_basis="calendar_month",
        interval_seconds=None,
    )
    result = normalize_operational_csv(data, evidence)
    assert result.receipt.gap_count == 0
    assert result.receipt.interval_drift_count == 0


def test_calendar_month_gap_is_receipted() -> None:
    data = b"when,energy\n2024-01-01T00:00:00Z,10\n2024-03-01T00:00:00Z,12\n"
    evidence = _meter_evidence(
        data,
        start="2024-01-01T00:00:00Z",
        end="2024-03-01T00:00:00Z",
        row_count=2,
        interval_basis="calendar_month",
        interval_seconds=None,
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence)
    assert raised.value.receipt is not None
    assert raised.value.receipt.gap_count == 1


def test_named_zone_calendar_month_uses_source_wall_calendar() -> None:
    data = (
        b"when,energy\n"
        b"2025-04-01T00:00:00,10\n"
        b"2025-05-01T00:00:00,11\n"
        b"2025-06-01T00:00:00,12\n"
    )
    evidence = _meter_evidence(
        data,
        start="2025-03-31T23:00:00Z",
        end="2025-05-31T23:00:00Z",
        row_count=3,
        interval_basis="calendar_month",
        interval_seconds=None,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    result = normalize_operational_csv(data, evidence, timezone_rules=_timezone_rules())
    assert result.receipt.coverage_mismatch_count == 0
    assert result.receipt.gap_count == 0
    assert result.receipt.interval_drift_count == 0


def test_named_zone_lower_year_fixed_cadence_renders_four_digit_utc_year() -> None:
    data = b"when,energy\n0001-01-01T00:00:00,10\n0001-01-01T00:01:00,11\n"
    evidence = _meter_evidence(
        data,
        start="0001-01-01T00:01:15Z",
        end="0001-01-01T00:02:15Z",
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=60,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    result = normalize_operational_csv(data, evidence, timezone_rules=_timezone_rules())
    assert result.normalized_rows == (
        ("0001-01-01T00:01:15Z", "10"),
        ("0001-01-01T00:02:15Z", "11"),
    )


def test_named_zone_lower_year_calendar_range_failure_is_closed() -> None:
    data = b"when,energy\n0001-01-01T00:00:00,10\n0001-02-01T00:00:00,11\n"
    evidence = _meter_evidence(
        data,
        start="0001-01-01T00:00:00Z",
        end="0001-02-01T00:01:15Z",
        row_count=2,
        interval_basis="calendar_month",
        interval_seconds=None,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence, timezone_rules=_timezone_rules())
    assert raised.value.code == "TIMEZONE_NORMALIZATION_FAILED"
    assert raised.value.receipt is None


def test_declared_coverage_and_row_count_are_bound_to_receipt_and_method() -> None:
    data = b"when,energy\n2025-01-01T00:00:00Z,1\n2025-01-01T00:00:01Z,2\n"
    first_evidence = _meter_evidence(
        data,
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T00:00:01Z",
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=1,
    )
    second_evidence = replace(
        first_evidence,
        coverage_start_utc="2025-01-01T00:00:00.0Z",
        coverage_end_utc="2025-01-01T00:00:01.000000Z",
    )
    first = normalize_operational_csv(data, first_evidence)
    second = normalize_operational_csv(data, second_evidence)
    assert first.receipt.coverage_start_utc == first_evidence.coverage_start_utc
    assert first.receipt.coverage_end_utc == first_evidence.coverage_end_utc
    assert first.receipt.declared_row_count == first_evidence.row_count
    assert first.receipt.method_sha256 != second.receipt.method_sha256


def test_energy_aggregation_is_an_explicit_sum() -> None:
    data = (
        b"when,energy\n"
        b"2025-01-01T00:00:00Z,1\n"
        b"2025-01-01T00:15:00Z,2\n"
        b"2025-01-01T00:30:00Z,3\n"
        b"2025-01-01T00:45:00Z,4\n"
    )
    evidence = _meter_evidence(
        data,
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T00:45:00Z",
        row_count=4,
        interval_basis="fixed_seconds",
        interval_seconds=900,
    )
    normalized = normalize_operational_csv(data, evidence)
    result = aggregate_operational_series(
        normalized,
        OperationalAggregationSpec(
            value_role="energy_kwh",
            method="sum",
            target_interval_seconds=3600,
            anchor_utc="2025-01-01T00:00:00Z",
            source_timestamp_position="interval_start",
            value_basis="interval_energy",
            arithmetic_policy="exact_decimal_sum_v1",
            rounding_decimal_places=None,
        ),
    )
    assert result.rows == (("2025-01-01T00:00:00Z", "10"),)
    assert result.receipt.schema == OPERATIONAL_AGGREGATION_SCHEMA
    assert result.receipt.utc_elapsed_time_basis is True
    assert result.receipt.canonical_finance_eligible is False


def test_power_aggregation_across_dst_offsets_uses_utc_elapsed_time() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-10-26T00:00:00+01:00,T01,1\n"
        b"2025-10-26T01:00:00+01:00,T01,3\n"
        b"2025-10-26T01:00:00+00:00,T01,5\n"
        b"2025-10-26T02:00:00+00:00,T01,7\n"
    )
    evidence = _scada_evidence(
        data,
        start="2025-10-25T23:00:00Z",
        end="2025-10-26T02:00:00Z",
        interval=3600,
        timezone_treatment="offset_aware_to_utc",
    )
    normalized = _normalize_scada(data, evidence)
    result = aggregate_operational_series(
        normalized,
        OperationalAggregationSpec(
            value_role="power_kw",
            method="mean",
            target_interval_seconds=14400,
            anchor_utc="2025-10-25T23:00:00Z",
            source_timestamp_position="interval_start",
            value_basis="interval_average_power",
            arithmetic_policy="half_even_power_mean_v1",
            rounding_decimal_places=12,
        ),
    )
    assert result.rows == (("2025-10-25T23:00:00Z", "T01", "4"),)
    assert result.receipt.input_row_count == 4
    assert result.receipt.output_row_count == 1


def test_aggregation_rejects_partial_bucket(scada_csv: bytes) -> None:
    normalized = _normalize_scada(scada_csv, _scada_evidence(scada_csv))
    with pytest.raises(OperationalNormalizationError) as raised:
        aggregate_operational_series(
            normalized,
            OperationalAggregationSpec(
                value_role="power_kw",
                method="mean",
                target_interval_seconds=3600,
                anchor_utc="2025-01-01T00:00:00Z",
                source_timestamp_position="interval_start",
                value_basis="interval_average_power",
                arithmetic_policy="half_even_power_mean_v1",
                rounding_decimal_places=12,
            ),
        )
    assert raised.value.code == "AGGREGATION_CONTRACT_FAILED"


@pytest.mark.parametrize(
    ("role", "method"),
    [("energy_kwh", "mean"), ("power_kw", "sum")],
)
def test_aggregation_spec_refuses_dimensionally_wrong_method(
    role: str, method: str
) -> None:
    with pytest.raises(ValueError):
        OperationalAggregationSpec(
            value_role=role,  # type: ignore[arg-type]
            method=method,  # type: ignore[arg-type]
            target_interval_seconds=3600,
            anchor_utc="2025-01-01T00:00:00Z",
            source_timestamp_position="interval_start",
            value_basis=(
                "interval_energy" if role == "energy_kwh" else "interval_average_power"
            ),
            arithmetic_policy=(
                "exact_decimal_sum_v1"
                if role == "energy_kwh"
                else "half_even_power_mean_v1"
            ),
            rounding_decimal_places=None if role == "energy_kwh" else 12,
        )


def test_aggregation_spec_requires_explicit_value_semantics() -> None:
    with pytest.raises(ValueError, match="interval_average_power"):
        OperationalAggregationSpec(
            value_role="power_kw",
            method="mean",
            target_interval_seconds=3600,
            anchor_utc="2025-01-01T00:00:00Z",
            source_timestamp_position="interval_start",
            value_basis="interval_energy",
            arithmetic_policy="half_even_power_mean_v1",
            rounding_decimal_places=12,
        )


def test_quality_receipt_refuses_authority_laundering(scada_csv: bytes) -> None:
    result = _normalize_scada(scada_csv, _scada_evidence(scada_csv))
    with pytest.raises(ValueError, match="canonical_finance_eligible"):
        replace(result.receipt, canonical_finance_eligible=True)


def test_asset_metadata_rejects_duplicate_asset_keys() -> None:
    data = b"asset,rated\nT01,5000\nT01,5000\n"
    evidence = OperationalDatasetEvidence(
        logical_id="assets.primary",
        kind="asset",
        source_class="declared_asset",
        timezone_treatment="not_applicable",
        source_timezone=None,
        ambiguous_time_policy="not_applicable",
        nonexistent_time_policy="not_applicable",
        observation_status="declared_metadata",
        lineage_source_sha256=(),
        derivation_method_sha256=None,
        source_locator="evidence/assets.csv",
        source_sha256=_digest(data),
        coverage_start_utc="2025-01-01T00:00:00Z",
        coverage_end_utc="2025-01-02T00:00:00Z",
        interval_basis="not_applicable",
        interval_seconds=None,
        row_count=2,
        columns=(
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("rated_power_kw", "rated", "kW"),
        ),
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence)
    assert raised.value.receipt is not None
    assert raised.value.receipt.duplicate_key_count == 1


def test_method_digest_binds_explicit_exclusions() -> None:
    data = (
        b"timestamp,turbine,power,note\n"
        b"2025-01-01T00:00:00Z,T01,1,a\n"
        b"2025-01-01T00:10:00Z,T01,2,b\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        end="2025-01-01T00:10:00Z",
    )
    first = _normalize_scada(
        data,
        evidence,
        column_exclusions=(OperationalColumnExclusion("note", "not analytical"),),
    )
    second = _normalize_scada(
        data,
        evidence,
        column_exclusions=(OperationalColumnExclusion("note", "operator narrative"),),
    )
    assert first.normalized_csv_bytes == second.normalized_csv_bytes
    assert first.receipt.method_sha256 != second.receipt.method_sha256


def test_derived_evidence_rehashes_and_preserves_complete_lineage() -> None:
    data = b"when,loss\n2025-01-01T00:00:00Z,1\n2025-01-01T01:00:00Z,2\n"
    upstream = b"immutable upstream meter bytes"
    method = b"versioned curtailment derivation method"
    evidence = OperationalDatasetEvidence(
        logical_id="curtailment.derived",
        kind="curtailment",
        source_class="observed_plant",
        timezone_treatment="source_utc",
        source_timezone=None,
        ambiguous_time_policy="not_applicable",
        nonexistent_time_policy="not_applicable",
        observation_status="derived_estimate",
        lineage_source_sha256=(_digest(upstream),),
        derivation_method_sha256=_digest(method),
        source_locator="evidence/curtailment-derived.csv",
        source_sha256=_digest(data),
        coverage_start_utc="2025-01-01T00:00:00Z",
        coverage_end_utc="2025-01-01T01:00:00Z",
        interval_basis="fixed_seconds",
        interval_seconds=3600,
        row_count=2,
        columns=(
            OperationalColumnBinding("timestamp_utc", "when", "iso8601_utc"),
            OperationalColumnBinding("curtailment_loss_kwh", "loss", "kWh"),
        ),
    )

    with pytest.raises(OperationalNormalizationError) as missing:
        normalize_operational_csv(data, evidence)
    assert missing.value.code == "LINEAGE_DIGEST_MISMATCH"

    with pytest.raises(OperationalNormalizationError) as wrong_method:
        normalize_operational_csv(
            data,
            evidence,
            lineage_source_bytes=(upstream,),
            derivation_method_bytes=b"different method",
        )
    assert wrong_method.value.code == "LINEAGE_DIGEST_MISMATCH"

    result = normalize_operational_csv(
        data,
        evidence,
        lineage_source_bytes=(upstream,),
        derivation_method_bytes=method,
    )
    assert result.lineage_source_bytes == (upstream,)
    assert result.derivation_method_bytes == method
    assert result.receipt.lineage_verified is True
    assert result.receipt.lineage_source_sha256 == (_digest(upstream),)


def test_decimal_normalization_is_independent_of_decimal_context() -> None:
    data = (
        b"when,energy\n"
        b"2025-01-01T00:00:00Z,1.2300e+2\n"
        b"2025-01-01T00:00:01Z,0.0000000000000000000000001\n"
    )
    evidence = _meter_evidence(
        data,
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T00:00:01Z",
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=1,
    )
    with localcontext(Context(prec=2)):
        low_precision = normalize_operational_csv(data, evidence)
    with localcontext(Context(prec=50)):
        high_precision = normalize_operational_csv(data, evidence)
    assert low_precision.normalized_csv_bytes == high_precision.normalized_csv_bytes
    assert low_precision.normalized_rows == (
        ("2025-01-01T00:00:00Z", "123"),
        ("2025-01-01T00:00:01Z", "0.0000000000000000000000001"),
    )


def test_energy_sum_is_exact_under_long_decimal_cancellation() -> None:
    data = (
        b"when,energy\n"
        b"2025-01-01T00:00:00Z,99999999999999999999.999999999999\n"
        b"2025-01-01T00:00:01Z,-99999999999999999999.999999999998\n"
    )
    normalized = normalize_operational_csv(
        data,
        _meter_evidence(
            data,
            start="2025-01-01T00:00:00Z",
            end="2025-01-01T00:00:01Z",
            row_count=2,
            interval_basis="fixed_seconds",
            interval_seconds=1,
        ),
    )
    result = aggregate_operational_series(
        normalized,
        OperationalAggregationSpec(
            value_role="energy_kwh",
            method="sum",
            target_interval_seconds=2,
            anchor_utc="2025-01-01T00:00:00Z",
            source_timestamp_position="interval_start",
            value_basis="interval_energy",
            arithmetic_policy="exact_decimal_sum_v1",
            rounding_decimal_places=None,
        ),
    )
    assert result.rows == (("2025-01-01T00:00:00Z", "0.000000000001"),)


@pytest.mark.parametrize(
    ("second_value", "expected"),
    [
        ("0.000000000001", "0"),
        ("0.000000000003", "0.000000000002"),
        ("-0.000000000003", "-0.000000000002"),
    ],
)
def test_power_mean_uses_bounded_signed_half_even_oracle(
    second_value: str, expected: str
) -> None:
    data = (
        "timestamp,turbine,power\n"
        "2025-01-01T00:00:00Z,T01,0\n"
        f"2025-01-01T00:00:01Z,T01,{second_value}\n"
    ).encode()
    normalized = _normalize_scada(
        data,
        _scada_evidence(
            data,
            row_count=2,
            end="2025-01-01T00:00:01Z",
            interval=1,
        ),
    )
    result = aggregate_operational_series(
        normalized,
        OperationalAggregationSpec(
            value_role="power_kw",
            method="mean",
            target_interval_seconds=2,
            anchor_utc="2025-01-01T00:00:00Z",
            source_timestamp_position="interval_start",
            value_basis="interval_average_power",
            arithmetic_policy="half_even_power_mean_v1",
            rounding_decimal_places=12,
        ),
    )
    assert result.rows == (("2025-01-01T00:00:00Z", "T01", expected),)


@pytest.mark.parametrize(
    ("role", "policy", "places"),
    [
        ("energy_kwh", "half_even_power_mean_v1", 12),
        ("power_kw", "exact_decimal_sum_v1", None),
        ("power_kw", "half_even_power_mean_v1", 7),
    ],
)
def test_aggregation_spec_rejects_contradictory_arithmetic_policy(
    role: str, policy: str, places: int | None
) -> None:
    with pytest.raises(ValueError, match="arithmetic_policy"):
        OperationalAggregationSpec(
            value_role=role,  # type: ignore[arg-type]
            method="sum" if role == "energy_kwh" else "mean",
            target_interval_seconds=3600,
            anchor_utc="2025-01-01T00:00:00Z",
            source_timestamp_position="interval_start",
            value_basis=(
                "interval_energy" if role == "energy_kwh" else "interval_average_power"
            ),
            arithmetic_policy=policy,  # type: ignore[arg-type]
            rounding_decimal_places=places,
        )


def test_cadence_population_counts_are_order_independent() -> None:
    ordered = (
        b"timestamp,turbine,power\n"
        b"2025-01-01T00:00:00Z,T01,1\n"
        b"2025-01-01T00:10:00Z,T01,2\n"
        b"2025-01-01T00:20:00Z,T01,3\n"
        b"2025-01-01T00:30:00Z,T01,4\n"
    )
    reversed_rows = (
        b"timestamp,turbine,power\n"
        + b"\n".join(reversed(ordered.splitlines()[1:]))
        + b"\n"
    )
    ordered_result = _normalize_scada(ordered, _scada_evidence(ordered))
    with pytest.raises(OperationalNormalizationError) as reversed_error:
        _normalize_scada(reversed_rows, _scada_evidence(reversed_rows))
    receipt = reversed_error.value.receipt
    assert receipt is not None
    assert (
        receipt.duplicate_key_count,
        receipt.gap_count,
        receipt.interval_drift_count,
    ) == (
        ordered_result.receipt.duplicate_key_count,
        ordered_result.receipt.gap_count,
        ordered_result.receipt.interval_drift_count,
    )
    assert receipt.source_order_violation_count == 3


def test_duplicate_off_grid_rows_are_counted_by_occurrence_despite_bad_value() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-01-01T00:00:00Z,T01,1\n"
        b"2025-01-01T00:05:00Z,T01,NaN\n"
        b"2025-01-01T00:05:00Z,T01,3\n"
        b"2025-01-01T00:30:00Z,T01,4\n"
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        _normalize_scada(data, _scada_evidence(data))
    receipt = raised.value.receipt
    assert receipt is not None
    assert receipt.duplicate_key_count == 1
    assert receipt.interval_drift_count == 2
    assert receipt.gap_count == 2
    assert receipt.nonfinite_value_count == 1


def test_calendar_gaps_are_derived_from_declared_population_edges() -> None:
    data = b"when,energy\n2024-02-01T00:00:00Z,11\n"
    evidence = _meter_evidence(
        data,
        start="2024-01-01T00:00:00Z",
        end="2024-03-01T00:00:00Z",
        row_count=1,
        interval_basis="calendar_month",
        interval_seconds=None,
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(data, evidence)
    assert raised.value.receipt is not None
    assert raised.value.receipt.gap_count == 2


def test_group_universe_detects_absent_unexpected_and_truncated_assets() -> None:
    absent = (
        b"timestamp,turbine,power\n"
        b"2025-01-01T00:00:00Z,T01,1\n"
        b"2025-01-01T00:10:00Z,T01,2\n"
    )
    with pytest.raises(OperationalNormalizationError) as missing:
        _normalize_scada(
            absent,
            _scada_evidence(absent, row_count=2, end="2025-01-01T00:10:00Z"),
            expected_assets=("T01", "T02"),
        )
    assert missing.value.receipt is not None
    assert missing.value.receipt.missing_group_keys == ("T02",)

    unexpected = absent.replace(b"T01,2", b"T02,2")
    with pytest.raises(OperationalNormalizationError) as extra:
        _normalize_scada(
            unexpected,
            _scada_evidence(unexpected, row_count=2, end="2025-01-01T00:10:00Z"),
        )
    assert extra.value.receipt is not None
    assert extra.value.receipt.unexpected_group_keys == ("T02",)

    truncated = (
        b"timestamp,turbine,power\n"
        b"2025-01-01T00:00:00Z,T01,1\n"
        b"2025-01-01T00:10:00Z,T01,2\n"
        b"2025-01-01T00:00:00Z,T02,3\n"
    )
    with pytest.raises(OperationalNormalizationError) as short:
        _normalize_scada(
            truncated,
            _scada_evidence(truncated, row_count=3, end="2025-01-01T00:10:00Z"),
            expected_assets=("T01", "T02"),
        )
    assert short.value.receipt is not None
    t02 = next(
        group
        for group in short.value.receipt.group_receipts
        if group.group_key == "T02"
    )
    assert t02.coverage_mismatch_count == 1
    assert t02.gap_count == 1


def test_grouped_timeseries_requires_verified_asset_universe(scada_csv: bytes) -> None:
    with pytest.raises(OperationalNormalizationError) as raised:
        normalize_operational_csv(scada_csv, _scada_evidence(scada_csv))
    assert raised.value.code == "GROUP_UNIVERSE_FAILED"


def test_all_rows_excluded_and_forged_empty_success_fail_closed(
    scada_csv: bytes,
) -> None:
    with pytest.raises(OperationalNormalizationError) as excluded:
        _normalize_scada(
            scada_csv,
            _scada_evidence(scada_csv),
            row_exclusions=tuple(
                OperationalRowExclusion(number, "test exclusion")
                for number in range(1, 5)
            ),
        )
    receipt = excluded.value.receipt
    assert receipt is not None
    assert receipt.empty_dataset_count == 1
    assert receipt.included_row_count == 0
    with pytest.raises(ValueError, match="quality_passed|passing QA requires"):
        replace(
            receipt,
            quality_passed=True,
            normalized_sha256="0" * 64,
        )


def test_named_zone_rules_are_host_independent_and_explicitly_attested() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-07-01T12:00:00,T01,1\n"
        b"2025-07-01T13:00:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        start="2025-07-01T11:00:00Z",
        end="2025-07-01T12:00:00Z",
        interval=3600,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    rules = _timezone_rules()
    original_tzpath = __import__("zoneinfo").TZPATH
    try:
        reset_tzpath(())
        result = _normalize_scada(data, evidence, timezone_rules=rules)
    finally:
        reset_tzpath(original_tzpath)
    assert result.normalized_rows[0][0] == "2025-07-01T11:00:00Z"
    assert result.receipt.timezone_rule_attestation == "caller_attested_zone_payload"
    assert result.receipt.timezone_source_locator == rules.source_locator
    assert result.receipt.timezone_database == rules.identity


def test_timezone_payload_and_locator_are_bound_but_zone_semantics_are_attested() -> (
    None
):
    data = (
        b"timestamp,turbine,power\n"
        b"2025-07-01T12:00:00,T01,1\n"
        b"2025-07-01T13:00:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        start="2025-07-01T12:00:00Z",
        end="2025-07-01T13:00:00Z",
        interval=3600,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    utc_bytes = (
        importlib.resources.files("tzdata.zoneinfo").joinpath("Etc/UTC").read_bytes()
    )
    labelled_utc = OperationalTimezoneRules(
        source_timezone="Europe/London",
        tzif_bytes=utc_bytes,
        source_locator="attested:test/utc-labelled-london",
    )
    first = _normalize_scada(data, evidence, timezone_rules=labelled_utc)
    second = _normalize_scada(
        data,
        evidence,
        timezone_rules=replace(labelled_utc, source_locator="attested:test/copy"),
    )
    assert first.receipt.timezone_rule_attestation == "caller_attested_zone_payload"
    assert first.receipt.method_sha256 != second.receipt.method_sha256


@pytest.mark.parametrize(
    "bad_rules",
    [
        pytest.param(b"not-tzif", id="bad-magic"),
        pytest.param(b"TZif" + b"0" * 1_048_573, id="oversized"),
    ],
)
def test_timezone_rule_envelope_rejects_invalid_bytes(bad_rules: bytes) -> None:
    with pytest.raises(ValueError, match="TZif|1 MiB"):
        OperationalTimezoneRules("Europe/London", bad_rules, "test:bad")


def test_failed_receipt_rejects_malformed_tzif_identity() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-10-26T00:30:00,T01,1\n"
        b"2025-10-26T01:30:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        start="2025-10-25T23:30:00Z",
        end="2025-10-26T01:30:00Z",
        interval=7200,
        timezone_treatment="named_zone_to_utc",
        source_timezone="Europe/London",
        ambiguous="reject",
        nonexistent="reject",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        _normalize_scada(data, evidence, timezone_rules=_timezone_rules())
    assert raised.value.receipt is not None
    with pytest.raises(ValueError, match="hash-bound"):
        replace(
            raised.value.receipt,
            timezone_database="tzif-sha256:not-a-digest",
        )
    for invalid_locator in (7, "", " padded", "line\nbreak"):
        with pytest.raises(ValueError, match="closed timezone provenance"):
            replace(
                raised.value.receipt,
                timezone_source_locator=invalid_locator,
            )


def test_unknown_negative_zero_offset_fails_with_receipt() -> None:
    data = (
        b"timestamp,turbine,power\n"
        b"2025-01-01T00:00:00-00:00,T01,1\n"
        b"2025-01-01T00:10:00-00:00,T01,2\n"
    )
    evidence = _scada_evidence(
        data,
        row_count=2,
        end="2025-01-01T00:10:00Z",
        timezone_treatment="offset_aware_to_utc",
    )
    with pytest.raises(OperationalNormalizationError) as raised:
        _normalize_scada(data, evidence)
    assert raised.value.receipt is not None
    assert raised.value.receipt.invalid_value_count == 2


def test_normalization_result_rejects_method_and_row_substitution(
    scada_csv: bytes,
) -> None:
    result = _normalize_scada(scada_csv, _scada_evidence(scada_csv))
    with pytest.raises(ValueError, match="constructed by"):
        replace(result, receipt=replace(result.receipt, method_sha256="0" * 64))
    forged_rows = result.normalized_rows[:-1] + (
        ("2025-01-01T00:30:00Z", "T01", "999"),
    )
    forged_bytes = (
        b"timestamp_utc,asset_id,power_kw\n"
        + b"\n".join(",".join(row).encode() for row in forged_rows)
        + b"\n"
    )
    with pytest.raises(ValueError, match="constructed by"):
        replace(
            result,
            normalized_rows=forged_rows,
            normalized_csv_bytes=forged_bytes,
            receipt=replace(result.receipt, normalized_sha256=_digest(forged_bytes)),
        )
    with pytest.raises(ValueError, match="does not reproduce from retained source"):
        replace(
            result,
            normalized_rows=forged_rows,
            normalized_csv_bytes=forged_bytes,
            receipt=replace(result.receipt, normalized_sha256=_digest(forged_bytes)),
            _factory_token=operational_normalization._NORMALIZATION_RESULT_TOKEN,
        )


def test_public_apis_close_invalid_runtime_types() -> None:
    data = b"when,energy\n2025-01-01T00:00:00Z,1\n2025-01-01T00:00:01Z,2\n"
    evidence = _meter_evidence(
        data,
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T00:00:01Z",
        row_count=2,
        interval_basis="fixed_seconds",
        interval_seconds=1,
    )
    normalized = normalize_operational_csv(data, evidence)
    spec = OperationalAggregationSpec(
        value_role="energy_kwh",
        method="sum",
        target_interval_seconds=2,
        anchor_utc="2025-01-01T00:00:00Z",
        source_timestamp_position="interval_start",
        value_basis="interval_energy",
        arithmetic_policy="exact_decimal_sum_v1",
        rounding_decimal_places=None,
    )
    with pytest.raises(OperationalNormalizationError) as bad_evidence:
        normalize_operational_csv(data, None)  # type: ignore[arg-type]
    assert bad_evidence.value.code == "INVALID_VALUE"
    with pytest.raises(OperationalNormalizationError) as bad_normalized:
        aggregate_operational_series(None, spec)  # type: ignore[arg-type]
    assert bad_normalized.value.code == "AGGREGATION_CONTRACT_FAILED"
    with pytest.raises(OperationalNormalizationError) as bad_spec:
        aggregate_operational_series(normalized, None)  # type: ignore[arg-type]
    assert bad_spec.value.code == "AGGREGATION_CONTRACT_FAILED"


def test_aggregation_result_rejects_source_method_and_row_substitution() -> None:
    data = b"when,energy\n2025-01-01T00:00:00Z,1\n2025-01-01T00:00:01Z,2\n"
    normalized = normalize_operational_csv(
        data,
        _meter_evidence(
            data,
            start="2025-01-01T00:00:00Z",
            end="2025-01-01T00:00:01Z",
            row_count=2,
            interval_basis="fixed_seconds",
            interval_seconds=1,
        ),
    )
    result = aggregate_operational_series(
        normalized,
        OperationalAggregationSpec(
            value_role="energy_kwh",
            method="sum",
            target_interval_seconds=2,
            anchor_utc="2025-01-01T00:00:00Z",
            source_timestamp_position="interval_start",
            value_basis="interval_energy",
            arithmetic_policy="exact_decimal_sum_v1",
            rounding_decimal_places=None,
        ),
    )
    for forged_receipt in (
        replace(result.receipt, source_normalized_sha256="0" * 64),
        replace(result.receipt, method_sha256="0" * 64),
    ):
        with pytest.raises(ValueError, match="constructed by"):
            replace(result, receipt=forged_receipt)
    with pytest.raises(ValueError, match="constructed by"):
        replace(result, rows=(("2025-01-01T00:00:00Z", "999"),))

    with pytest.raises(ValueError, match="input count"):
        replace(
            result,
            receipt=replace(result.receipt, input_row_count=999),
            _factory_token=operational_normalization._AGGREGATION_RESULT_TOKEN,
        )
    forged_interval = 2
    forged_method = operational_normalization._aggregation_method_sha(
        result.normalized, result.spec, forged_interval
    )
    with pytest.raises(ValueError, match="source interval"):
        replace(
            result,
            receipt=replace(
                result.receipt,
                source_interval_seconds=forged_interval,
                method_sha256=forged_method,
            ),
            _factory_token=operational_normalization._AGGREGATION_RESULT_TOKEN,
        )


def test_resource_bounds_fail_with_closed_errors() -> None:
    too_wide = b"when,energy\n2025-01-01T00:00:00Z,1\n2025-02-02T00:00:01Z,2\n"
    with pytest.raises(OperationalNormalizationError) as wide:
        normalize_operational_csv(
            too_wide,
            _meter_evidence(
                too_wide,
                start="2025-01-01T00:00:00Z",
                end="2025-02-02T00:00:01Z",
                row_count=2,
                interval_basis="fixed_seconds",
                interval_seconds=31 * 86_400 + 1,
            ),
        )
    assert wide.value.code == "QUALITY_CHECK_FAILED"

    two_points = b"when,energy\n2025-01-01T00:00:00Z,1\n2025-01-01T00:00:01Z,2\n"
    normalized = normalize_operational_csv(
        two_points,
        _meter_evidence(
            two_points,
            start="2025-01-01T00:00:00Z",
            end="2025-01-01T00:00:01Z",
            row_count=2,
            interval_basis="fixed_seconds",
            interval_seconds=1,
        ),
    )
    with pytest.raises(OperationalNormalizationError) as oversized_bucket:
        aggregate_operational_series(
            normalized,
            OperationalAggregationSpec(
                value_role="energy_kwh",
                method="sum",
                target_interval_seconds=100_001,
                anchor_utc="2025-01-01T00:00:00Z",
                source_timestamp_position="interval_start",
                value_basis="interval_energy",
                arithmetic_policy="exact_decimal_sum_v1",
                rounding_decimal_places=None,
            ),
        )
    assert oversized_bucket.value.code == "AGGREGATION_CONTRACT_FAILED"


def test_aggregation_closes_date_overflow_and_oversized_result() -> None:
    late = b"when,energy\n9999-12-30T00:00:00Z,1\n9999-12-31T00:00:00Z,2\n"
    late_normalized = normalize_operational_csv(
        late,
        _meter_evidence(
            late,
            start="9999-12-30T00:00:00Z",
            end="9999-12-31T00:00:00Z",
            row_count=2,
            interval_basis="fixed_seconds",
            interval_seconds=86_400,
        ),
    )
    with pytest.raises(OperationalNormalizationError) as late_error:
        aggregate_operational_series(
            late_normalized,
            OperationalAggregationSpec(
                value_role="energy_kwh",
                method="sum",
                target_interval_seconds=366 * 86_400,
                anchor_utc="0001-01-01T00:00:00Z",
                source_timestamp_position="interval_start",
                value_basis="interval_energy",
                arithmetic_policy="exact_decimal_sum_v1",
                rounding_decimal_places=None,
            ),
        )
    assert late_error.value.code == "AGGREGATION_CONTRACT_FAILED"

    huge = "9" * 4_096
    huge_data = (
        f"when,energy\n2025-01-01T00:00:00Z,{huge}\n2025-01-01T00:00:01Z,{huge}\n"
    ).encode()
    huge_normalized = normalize_operational_csv(
        huge_data,
        _meter_evidence(
            huge_data,
            start="2025-01-01T00:00:00Z",
            end="2025-01-01T00:00:01Z",
            row_count=2,
            interval_basis="fixed_seconds",
            interval_seconds=1,
        ),
    )
    with pytest.raises(OperationalNormalizationError) as huge_error:
        aggregate_operational_series(
            huge_normalized,
            OperationalAggregationSpec(
                value_role="energy_kwh",
                method="sum",
                target_interval_seconds=2,
                anchor_utc="2025-01-01T00:00:00Z",
                source_timestamp_position="interval_start",
                value_basis="interval_energy",
                arithmetic_policy="exact_decimal_sum_v1",
                rounding_decimal_places=None,
            ),
        )
    assert huge_error.value.code == "AGGREGATION_CONTRACT_FAILED"
