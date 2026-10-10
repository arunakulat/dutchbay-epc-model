from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from analytics.operational.contracts import (
    OperationalColumnBinding,
    OperationalDatasetEvidence,
)
from analytics.operational.normalization import (
    OPERATIONAL_AGGREGATION_SCHEMA,
    OPERATIONAL_NORMALIZATION_SCHEMA,
    OperationalAggregationSpec,
    OperationalColumnExclusion,
    OperationalNormalizationError,
    OperationalRowExclusion,
    aggregate_operational_series,
    normalize_operational_csv,
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    first = normalize_operational_csv(scada_csv, evidence)
    second = normalize_operational_csv(scada_csv, evidence)

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

    result = normalize_operational_csv(
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
        normalize_operational_csv(
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
            2,
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
        normalize_operational_csv(data, evidence)
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
        normalize_operational_csv(scada_csv, evidence)
    assert raised.value.receipt is not None
    assert raised.value.receipt.coverage_mismatch_count == 1
    assert raised.value.receipt.actual_coverage_end_utc == "2025-01-01T00:30:00Z"


def test_coverage_compares_utc_instants_not_string_spelling(scada_csv: bytes) -> None:
    evidence = _scada_evidence(
        scada_csv,
        start="2025-01-01T00:00:00.000Z",
        end="2025-01-01T00:30:00.000000Z",
    )
    result = normalize_operational_csv(scada_csv, evidence)
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
    result = normalize_operational_csv(data, evidence)
    assert result.normalized_rows[1][0] == "2025-10-26T01:30:00Z"
    assert result.receipt.ambiguous_time_resolution_count == 1
    assert result.receipt.timezone_database is not None
    assert result.receipt.timezone_database.startswith("tzdata:")


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
        normalize_operational_csv(data, evidence)
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
    result = normalize_operational_csv(data, evidence)
    assert result.normalized_rows[1][0] == "2025-03-30T01:30:00Z"
    assert result.receipt.nonexistent_time_resolution_count == 1


def _meter_evidence(
    data: bytes,
    *,
    start: str,
    end: str,
    row_count: int,
    interval_basis: str,
    interval_seconds: int | None,
    timezone_treatment: str = "source_utc",
) -> OperationalDatasetEvidence:
    return OperationalDatasetEvidence(
        logical_id="meter.primary",
        kind="revenue_meter",
        source_class="observed_plant",
        timezone_treatment=timezone_treatment,  # type: ignore[arg-type]
        source_timezone=None,
        ambiguous_time_policy="not_applicable",
        nonexistent_time_policy="not_applicable",
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
    normalized = normalize_operational_csv(data, evidence)
    result = aggregate_operational_series(
        normalized,
        OperationalAggregationSpec(
            value_role="power_kw",
            method="mean",
            target_interval_seconds=14400,
            anchor_utc="2025-10-25T23:00:00Z",
            source_timestamp_position="interval_start",
            value_basis="interval_average_power",
        ),
    )
    assert result.rows == (("2025-10-25T23:00:00Z", "T01", "4"),)
    assert result.receipt.input_row_count == 4
    assert result.receipt.output_row_count == 1


def test_aggregation_rejects_partial_bucket(scada_csv: bytes) -> None:
    normalized = normalize_operational_csv(scada_csv, _scada_evidence(scada_csv))
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
        )


def test_quality_receipt_refuses_authority_laundering(scada_csv: bytes) -> None:
    result = normalize_operational_csv(scada_csv, _scada_evidence(scada_csv))
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
    first = normalize_operational_csv(
        data,
        evidence,
        column_exclusions=(OperationalColumnExclusion("note", "not analytical"),),
    )
    second = normalize_operational_csv(
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
