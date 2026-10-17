from __future__ import annotations

import copy
import hashlib
import importlib.resources
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from decimal import Context, localcontext
from fractions import Fraction
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import analytics.operational.aep as aep_module
from analytics.operational.aep import (
    OPERATIONAL_AEP_SCHEMA,
    OperationalAEPError,
    OperationalAEPInput,
    OperationalAEPResult,
    OperationalAEPSourceBinding,
    OperationalAEPSpec,
    OperationalBoundaryEvidence,
    OperationalEnergyComponent,
    OperationalEnergyQuantity,
    OperationalRatio,
    OperationalSupplementalEnergyEvidence,
    estimate_operational_aep,
)
from analytics.operational.contracts import (
    OPERATIONAL_EVIDENCE_SCHEMA,
    OperationalAssessmentInput,
    OperationalColumnBinding,
    OperationalDatasetEvidence,
)
from analytics.operational.normalization import (
    OperationalGroupUniverse,
    OperationalTimezoneRules,
    normalize_operational_csv,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _evidence(
    logical_id: str,
    kind: str,
    data: bytes,
    columns: tuple[OperationalColumnBinding, ...],
    *,
    start: str = "2025-01-01T00:00:00Z",
    end: str = "2025-01-01T00:45:00Z",
    interval_basis: str = "fixed_seconds",
    interval_seconds: int | None = 900,
    status: str = "observed",
) -> OperationalDatasetEvidence:
    if kind == "asset":
        source_class = "declared_asset"
    elif kind == "reanalysis":
        source_class = "reference_reanalysis"
    else:
        source_class = "observed_plant"
    return OperationalDatasetEvidence(
        logical_id=logical_id,
        kind=kind,  # type: ignore[arg-type]
        source_class=source_class,  # type: ignore[arg-type]
        timezone_treatment=("not_applicable" if kind == "asset" else "source_utc"),  # type: ignore[arg-type]
        source_timezone=None,
        ambiguous_time_policy="not_applicable",
        nonexistent_time_policy="not_applicable",
        observation_status=status,  # type: ignore[arg-type]
        lineage_source_sha256=(),
        derivation_method_sha256=None,
        source_locator=f"evidence/{logical_id}.csv",
        source_sha256=_digest(data),
        coverage_start_utc=start,
        coverage_end_utc=end,
        interval_basis=interval_basis,  # type: ignore[arg-type]
        interval_seconds=interval_seconds,
        row_count=len(data.decode().strip().splitlines()) - 1,
        columns=columns,
    )


def _fixture(
    *,
    meter_values: tuple[str, ...] = ("237.5",) * 4,
    turbine_power: str = "500",
    availability_values: tuple[str, ...] = ("25",) * 4,
    curtailment_values: tuple[str, ...] = ("12.5",) * 4,
    interval_seconds: int = 900,
    supplements: bool = True,
    scada_energy: str | None = None,
) -> tuple[OperationalAEPInput, OperationalAEPSpec]:
    timestamps = tuple(
        f"2025-01-01T00:{minute:02d}:00Z"
        for minute in range(
            0, interval_seconds * len(meter_values) // 60, interval_seconds // 60
        )
    )
    end = timestamps[-1]
    meter_data = (
        "time,energy\n"
        + "".join(
            f"{stamp},{value}\n"
            for stamp, value in zip(timestamps, meter_values, strict=True)
        )
    ).encode()
    scada_data = (
        "time,asset,power"
        + (",energy" if scada_energy is not None else "")
        + "\n"
        + "".join(
            f"{stamp},{asset},{turbine_power}"
            + (f",{scada_energy}" if scada_energy is not None else "")
            + "\n"
            for stamp in timestamps
            for asset in ("T01", "T02")
        )
    ).encode()
    loss_data = (
        "time,availability,curtailment\n"
        + "".join(
            f"{stamp},{availability},{curtailment}\n"
            for stamp, availability, curtailment in zip(
                timestamps, availability_values, curtailment_values, strict=True
            )
        )
    ).encode()
    asset_data = b"asset,rated\nT01,500\nT02,500\n"
    reanalysis_data = (
        "time,wind,density\n" + "".join(f"{stamp},8,1.2\n" for stamp in timestamps)
    ).encode()
    meter_evidence = _evidence(
        "meter.primary",
        "revenue_meter",
        meter_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("energy_kwh", "energy", "kWh"),
        ),
        end=end,
        interval_seconds=interval_seconds,
    )
    asset_evidence = _evidence(
        "assets.primary",
        "asset",
        asset_data,
        (
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("rated_power_kw", "rated", "kW"),
        ),
        interval_basis="not_applicable",
        interval_seconds=None,
        status="declared_metadata",
    )
    asset_result = normalize_operational_csv(asset_data, asset_evidence)
    universe = OperationalGroupUniverse(asset_result)
    scada_evidence = _evidence(
        "scada.primary",
        "scada",
        scada_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("power_kw", "power", "kW"),
        )
        + (
            (OperationalColumnBinding("energy_kwh", "energy", "kWh"),)
            if scada_energy is not None
            else ()
        ),
        end=end,
        interval_seconds=interval_seconds,
    )
    loss_evidence = _evidence(
        "losses.primary",
        "curtailment",
        loss_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("availability_loss_kwh", "availability", "kWh"),
            OperationalColumnBinding("curtailment_loss_kwh", "curtailment", "kWh"),
        ),
        end=end,
        interval_seconds=interval_seconds,
    )
    reanalysis_evidence = _evidence(
        "reanalysis.reference",
        "reanalysis",
        reanalysis_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("wind_speed_ms", "wind", "m/s"),
            OperationalColumnBinding("air_density_kgm3", "density", "kg/m^3"),
        ),
        end=end,
        interval_seconds=interval_seconds,
        status="reference_reanalysis",
    )
    meter_result = normalize_operational_csv(meter_data, meter_evidence)
    scada_result = normalize_operational_csv(
        scada_data, scada_evidence, group_universe=universe
    )
    loss_result = normalize_operational_csv(loss_data, loss_evidence)
    electrical = OperationalAssessmentInput(
        schema=OPERATIONAL_EVIDENCE_SCHEMA,
        project_id="dutchbay",
        assessment_id="electrical-window",
        purpose="electrical_losses",
        assessment_start_utc=timestamps[0],
        assessment_end_utc=end,
        datasets=(meter_evidence, scada_evidence),
    )
    long_term = OperationalAssessmentInput(
        schema=OPERATIONAL_EVIDENCE_SCHEMA,
        project_id="dutchbay",
        assessment_id="loss-window",
        purpose="long_term_aep",
        assessment_start_utc=timestamps[0],
        assessment_end_utc=end,
        datasets=(meter_evidence, loss_evidence, reanalysis_evidence),
    )
    effective_end = "2025-01-01T01:00:00Z"
    if interval_seconds != 900 or len(meter_values) != 4:
        total_seconds = interval_seconds * len(meter_values)
        hour, remainder = divmod(total_seconds, 3_600)
        minute = remainder // 60
        effective_end = f"2025-01-01T{hour:02d}:{minute:02d}:00Z"
    boundary_source = b"matched plant boundary attestation v1"
    boundary_method = b"independent boundary review method v1"
    boundary = OperationalBoundaryEvidence(
        project_id="dutchbay",
        effective_start_utc=timestamps[0],
        effective_end_exclusive_utc=effective_end,
        meter_logical_id="meter.primary",
        turbine_logical_id="scada.primary",
        availability_logical_id="losses.primary",
        curtailment_logical_id="losses.primary",
        meter_energy_basis="net_export_interval_energy",
        turbine_energy_basis="complete_turbine_terminal_interval_energy",
        loss_energy_basis="non_overlapping_positive_reduction_energy",
        interval_boundary="interval_start_end_exclusive",
        excluded_flows="imports_storage_solar_and_shared_poc_excluded",
        asset_universe_basis="d2_verified_complete",
        source_locator="evidence/boundary-attestation.txt",
        source_bytes=boundary_source,
        source_sha256=_digest(boundary_source),
        method_bytes=boundary_method,
        method_sha256=_digest(boundary_method),
    )
    supplemental: tuple[OperationalSupplementalEnergyEvidence, ...] = ()
    if supplements:
        resource_source = b"independent resource gross total 1250 kWh"
        resource_method = b"resource potential method v1"
        wake_source = b"independent combined wake performance loss 80 kWh"
        wake_method = b"wake performance method v1"
        supplemental = (
            OperationalSupplementalEnergyEvidence(
                evidence_id="resource.gross",
                component="resource_gross_energy",
                project_id="dutchbay",
                effective_start_utc=timestamps[0],
                effective_end_exclusive_utc=effective_end,
                value_kwh="1250",
                boundary="upstream_resource_potential",
                source_locator="evidence/resource-gross.txt",
                source_bytes=resource_source,
                source_sha256=_digest(resource_source),
                method_bytes=resource_method,
                method_sha256=_digest(resource_method),
            ),
            OperationalSupplementalEnergyEvidence(
                evidence_id="wake.loss",
                component="wake_performance_loss",
                project_id="dutchbay",
                effective_start_utc=timestamps[0],
                effective_end_exclusive_utc=effective_end,
                value_kwh="80",
                boundary="resource_to_turbine_combined_wake_performance",
                source_locator="evidence/wake-loss.txt",
                source_bytes=wake_source,
                source_sha256=_digest(wake_source),
                method_bytes=wake_method,
                method_sha256=_digest(wake_method),
            ),
        )
    inputs = OperationalAEPInput(
        assessments=(electrical, long_term),
        normalized_results=(meter_result, scada_result, loss_result),
        boundary_evidence=boundary,
        supplemental_evidence=supplemental,
    )
    spec = OperationalAEPSpec(
        project_id="dutchbay",
        assessment_id="d3.fixture",
        effective_start_utc=timestamps[0],
        effective_end_exclusive_utc=effective_end,
        temporal_basis="observed_period_total",
        meter_logical_id="meter.primary",
        turbine_logical_id="scada.primary",
        availability_logical_id="losses.primary",
        curtailment_logical_id="losses.primary",
        absolute_tolerance_kwh="0.000001",
    )
    return inputs, spec


def _value(result: OperationalAEPResult, name: str) -> Fraction:
    component = result.component(name)  # type: ignore[arg-type]
    assert component.value is not None
    return component.value.as_fraction()


def _calendar_month_fixture() -> tuple[OperationalAEPInput, OperationalAEPSpec]:
    month_starts = ("2025-01-01T00:00:00Z", "2025-02-01T00:00:00Z")
    meter_data = b"time,energy\n2025-01-01T00:00:00Z,1400\n2025-02-01T00:00:00Z,1400\n"
    loss_data = (
        b"time,availability,curtailment\n"
        b"2025-01-01T00:00:00Z,10,6\n"
        b"2025-02-01T00:00:00Z,10,6\n"
    )
    reanalysis_data = (
        b"time,wind,density\n2025-01-01T00:00:00Z,8,1.2\n2025-02-01T00:00:00Z,8,1.2\n"
    )
    days = tuple(date(2025, 1, 1) + timedelta(days=index) for index in range(59))
    scada_data = (
        "time,asset,power\n"
        + "".join(
            f"{day.isoformat()}T00:00:00Z,{asset},1\n"
            for day in days
            for asset in ("T01", "T02")
        )
    ).encode()
    asset_data = b"asset,rated\nT01,500\nT02,500\n"
    meter = _evidence(
        "meter.primary",
        "revenue_meter",
        meter_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("energy_kwh", "energy", "kWh"),
        ),
        end=month_starts[-1],
        interval_basis="calendar_month",
        interval_seconds=None,
    )
    losses = _evidence(
        "losses.primary",
        "curtailment",
        loss_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("availability_loss_kwh", "availability", "kWh"),
            OperationalColumnBinding("curtailment_loss_kwh", "curtailment", "kWh"),
        ),
        end=month_starts[-1],
        interval_basis="calendar_month",
        interval_seconds=None,
    )
    reanalysis = _evidence(
        "reanalysis.reference",
        "reanalysis",
        reanalysis_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("wind_speed_ms", "wind", "m/s"),
            OperationalColumnBinding("air_density_kgm3", "density", "kg/m^3"),
        ),
        end=month_starts[-1],
        interval_basis="calendar_month",
        interval_seconds=None,
        status="reference_reanalysis",
    )
    assets = _evidence(
        "assets.primary",
        "asset",
        asset_data,
        (
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("rated_power_kw", "rated", "kW"),
        ),
        interval_basis="not_applicable",
        interval_seconds=None,
        status="declared_metadata",
    )
    scada = _evidence(
        "scada.primary",
        "scada",
        scada_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("power_kw", "power", "kW"),
        ),
        end="2025-02-28T00:00:00Z",
        interval_seconds=86_400,
    )
    universe = OperationalGroupUniverse(normalize_operational_csv(asset_data, assets))
    meter_result = normalize_operational_csv(meter_data, meter)
    loss_result = normalize_operational_csv(loss_data, losses)
    scada_result = normalize_operational_csv(scada_data, scada, group_universe=universe)
    electrical = OperationalAssessmentInput(
        schema=OPERATIONAL_EVIDENCE_SCHEMA,
        project_id="dutchbay",
        assessment_id="calendar-electrical",
        purpose="electrical_losses",
        assessment_start_utc=month_starts[0],
        assessment_end_utc=month_starts[-1],
        datasets=(meter, scada),
    )
    long_term = OperationalAssessmentInput(
        schema=OPERATIONAL_EVIDENCE_SCHEMA,
        project_id="dutchbay",
        assessment_id="calendar-losses",
        purpose="long_term_aep",
        assessment_start_utc=month_starts[0],
        assessment_end_utc=month_starts[-1],
        datasets=(meter, losses, reanalysis),
    )
    boundary_source = b"calendar matched boundary attestation"
    boundary_method = b"calendar boundary method"
    boundary = OperationalBoundaryEvidence(
        project_id="dutchbay",
        effective_start_utc=month_starts[0],
        effective_end_exclusive_utc="2025-03-01T00:00:00Z",
        meter_logical_id="meter.primary",
        turbine_logical_id="scada.primary",
        availability_logical_id="losses.primary",
        curtailment_logical_id="losses.primary",
        meter_energy_basis="net_export_interval_energy",
        turbine_energy_basis="complete_turbine_terminal_interval_energy",
        loss_energy_basis="non_overlapping_positive_reduction_energy",
        interval_boundary="interval_start_end_exclusive",
        excluded_flows="imports_storage_solar_and_shared_poc_excluded",
        asset_universe_basis="d2_verified_complete",
        source_locator="evidence/calendar-boundary.txt",
        source_bytes=boundary_source,
        source_sha256=_digest(boundary_source),
        method_bytes=boundary_method,
        method_sha256=_digest(boundary_method),
    )
    return (
        OperationalAEPInput(
            assessments=(electrical, long_term),
            normalized_results=(meter_result, scada_result, loss_result),
            boundary_evidence=boundary,
        ),
        OperationalAEPSpec(
            project_id="dutchbay",
            assessment_id="calendar.fixture",
            effective_start_utc=month_starts[0],
            effective_end_exclusive_utc="2025-03-01T00:00:00Z",
            temporal_basis="observed_period_total",
            meter_logical_id="meter.primary",
            turbine_logical_id="scada.primary",
            availability_logical_id="losses.primary",
            curtailment_logical_id="losses.primary",
            absolute_tolerance_kwh="0",
        ),
    )


def _named_calendar_fixture() -> tuple[OperationalAEPInput, OperationalAEPSpec]:
    """Rebind calendar inputs to retained Europe/London TZif rules."""
    inputs, spec = _calendar_month_fixture()
    resource = importlib.resources.files("tzdata.zoneinfo").joinpath("Europe", "London")
    rules = OperationalTimezoneRules(
        source_timezone="Europe/London",
        tzif_bytes=resource.read_bytes(),
        source_locator="python-package:tzdata/Europe/London",
    )
    rebound_evidence: dict[str, OperationalDatasetEvidence] = {}
    rebound_results = []
    for result in inputs.normalized_results:
        if result.evidence.interval_basis != "calendar_month":
            rebound_results.append(result)
            continue
        source_bytes = result.source_bytes.replace(b"Z", b"")
        evidence = replace(
            result.evidence,
            timezone_treatment="named_zone_to_utc",
            source_timezone="Europe/London",
            ambiguous_time_policy="fold_0",
            nonexistent_time_policy="reject",
            source_sha256=_digest(source_bytes),
        )
        rebound_evidence[evidence.logical_id] = evidence
        rebound_results.append(
            normalize_operational_csv(
                source_bytes,
                evidence,
                timezone_rules=rules,
            )
        )
    assessments = tuple(
        replace(
            assessment,
            datasets=tuple(
                rebound_evidence.get(dataset.logical_id, dataset)
                for dataset in assessment.datasets
            ),
        )
        for assessment in inputs.assessments
    )
    return (
        replace(
            inputs,
            assessments=assessments,
            normalized_results=tuple(rebound_results),
        ),
        spec,
    )


def test_hand_derived_matched_boundary_fixture() -> None:
    """Independently reproduce the four-interval OpenOA-comparator arithmetic."""
    inputs, spec = _fixture()
    result = estimate_operational_aep(inputs, spec)

    assert result.receipt.schema == OPERATIONAL_AEP_SCHEMA
    assert _value(result, "turbine_terminal_energy") == 1000
    assert _value(result, "net_meter_energy") == 950
    assert _value(result, "availability_loss") == 100
    assert _value(result, "curtailment_loss") == 50
    assert _value(result, "electrical_loss") == 50
    assert _value(result, "meter_loss_restored_gross") == 1100
    assert _value(result, "turbine_known_gross") == 1150
    assert _value(result, "resource_gross_energy") == 1250
    assert _value(result, "wake_performance_loss") == 80
    assert _value(result, "unknown_residual_loss") == 20
    assert result.ratio("electrical_loss_fraction_of_turbine").numerator == 1
    assert result.ratio("electrical_loss_fraction_of_turbine").denominator == 20
    assert result.ratio("net_fraction_of_resource_gross").numerator == 19
    assert result.ratio("net_fraction_of_resource_gross").denominator == 25
    assert result.ratio("unknown_residual_fraction_of_resource_gross").numerator == 2
    assert (
        result.ratio("unknown_residual_fraction_of_resource_gross").denominator == 125
    )
    assert result.receipt.meter_to_turbine_residual.as_fraction() == 0
    assert result.receipt.known_gross_to_net_residual.as_fraction() == 0
    assert result.receipt.full_gross_to_net_residual is not None
    assert result.receipt.full_gross_to_net_residual.as_fraction() == 0


def test_missing_components_are_unavailable_not_zero() -> None:
    inputs, spec = _fixture(supplements=False)
    result = estimate_operational_aep(inputs, spec)

    for name in (
        "resource_gross_energy",
        "wake_performance_loss",
        "unknown_residual_loss",
        "long_term_average_energy",
    ):
        component = result.component(name)  # type: ignore[arg-type]
        assert component.status == "unavailable"
        assert component.value is None
    assert result.receipt.annual_uncertainty_status == "unavailable_not_estimated"
    assert result.receipt.annual_uncertainty_basis is None
    assert result.receipt.annual_exceedance_probabilities == ()
    assert (
        result.receipt.long_term_average_uncertainty_status
        == "unavailable_not_estimated"
    )
    assert result.receipt.long_term_average_uncertainty_basis is None
    assert result.receipt.long_term_average_exceedance_probabilities == ()


def test_evidenced_zero_remains_available() -> None:
    inputs, spec = _fixture(turbine_power="475", supplements=False)
    result = estimate_operational_aep(inputs, spec)
    electrical = result.component("electrical_loss")
    assert electrical.status == "available"
    assert electrical.value == OperationalEnergyQuantity(0)
    assert electrical.evidence_ids == ("meter.primary", "scada.primary")


def test_reanalysis_presence_never_infers_resource_or_lta() -> None:
    inputs, spec = _fixture(supplements=False)
    assert any(
        dataset.kind == "reanalysis"
        for assessment in inputs.assessments
        for dataset in assessment.datasets
    )
    result = estimate_operational_aep(inputs, spec)
    assert result.component("resource_gross_energy").status == "unavailable"
    assert result.component("long_term_average_energy").status == "unavailable"


def test_input_order_and_decimal_context_do_not_change_result() -> None:
    inputs, spec = _fixture()
    baseline = estimate_operational_aep(inputs, spec)
    reordered = replace(
        inputs,
        assessments=tuple(
            replace(item, datasets=tuple(reversed(item.datasets)))
            for item in reversed(inputs.assessments)
        ),
        normalized_results=tuple(reversed(inputs.normalized_results)),
        supplemental_evidence=tuple(reversed(inputs.supplemental_evidence)),
    )
    with localcontext(Context(prec=2)):
        observed = estimate_operational_aep(reordered, spec)
    assert observed.components == baseline.components
    assert observed.ratios == baseline.ratios
    assert observed.receipt == baseline.receipt


def test_process_decimal_context_does_not_change_serialized_result() -> None:
    """Reproduce the complete receipt in a fresh low-precision interpreter."""
    inputs, spec = _fixture()
    expected = json.dumps(
        estimate_operational_aep(inputs, spec).model_dump(),
        sort_keys=True,
        separators=(",", ":"),
    )
    script = """
import json
import runpy
from decimal import getcontext
namespace = runpy.run_path('tests/contracts/test_operational_aep.py')
getcontext().prec = 2
inputs, spec = namespace['_fixture']()
result = namespace['estimate_operational_aep'](inputs, spec)
print(json.dumps(result.model_dump(), sort_keys=True, separators=(',', ':')))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == expected


def test_split_merge_intervals_preserve_exact_totals() -> None:
    quarter_inputs, quarter_spec = _fixture(supplements=False)
    half_inputs, half_spec = _fixture(
        meter_values=("475", "475"),
        availability_values=("50", "50"),
        curtailment_values=("25", "25"),
        interval_seconds=1800,
        supplements=False,
    )
    quarter = estimate_operational_aep(quarter_inputs, quarter_spec)
    half = estimate_operational_aep(half_inputs, half_spec)
    assert tuple(
        _value(quarter, item)
        for item in (
            "net_meter_energy",
            "turbine_terminal_energy",
            "availability_loss",
            "curtailment_loss",
        )
    ) == tuple(
        _value(half, item)
        for item in (
            "net_meter_energy",
            "turbine_terminal_energy",
            "availability_loss",
            "curtailment_loss",
        )
    )


def test_calendar_month_energy_and_daily_power_share_effective_bounds() -> None:
    inputs, spec = _calendar_month_fixture()
    result = estimate_operational_aep(inputs, spec)
    assert _value(result, "net_meter_energy") == 2800
    assert _value(result, "turbine_terminal_energy") == 2832
    assert _value(result, "availability_loss") == 20
    assert _value(result, "curtailment_loss") == 12
    assert _value(result, "electrical_loss") == 32
    assert _value(result, "turbine_known_gross") == 2864


def test_named_zone_calendar_month_replays_retained_tzif_rules() -> None:
    inputs, spec = _named_calendar_fixture()
    result = estimate_operational_aep(inputs, spec)
    assert _value(result, "net_meter_energy") == 2800
    assert _value(result, "turbine_terminal_energy") == 2832
    assert all(
        item.timezone_rules is not None
        for item in inputs.normalized_results
        if item.evidence.interval_basis == "calendar_month"
    )


@pytest.mark.parametrize(
    ("purpose", "start", "end"),
    [
        ("electrical_losses", "2025-01-01T00:15:00Z", "2025-01-01T00:30:00Z"),
        ("electrical_losses", "2025-01-01T00:15:00Z", "2025-01-01T00:45:00Z"),
        ("long_term_aep", "2025-01-01T00:00:00Z", "2025-01-01T00:30:00Z"),
    ],
)
def test_d1_assessment_windows_cannot_under_authorize_d3_population(
    purpose: str, start: str, end: str
) -> None:
    """Reject narrow, shifted, and disagreeing D1 authorization windows."""
    inputs, spec = _fixture()
    assessments = tuple(
        (
            replace(
                assessment,
                assessment_start_utc=start,
                assessment_end_utc=end,
            )
            if assessment.purpose == purpose
            else assessment
        )
        for assessment in inputs.assessments
    )
    with pytest.raises(OperationalAEPError, match="BOUNDARY_MISMATCH"):
        estimate_operational_aep(replace(inputs, assessments=assessments), spec)


@pytest.mark.parametrize(
    "fixture_factory", [_calendar_month_fixture, _named_calendar_fixture]
)
def test_calendar_d1_window_must_authorize_the_complete_month_population(
    fixture_factory: Any,
) -> None:
    """Map D1 inclusive month labels to the common D3 end-exclusive bound."""
    inputs, spec = fixture_factory()
    assessments = tuple(
        (
            replace(assessment, assessment_end_utc="2025-01-15T00:00:00Z")
            if assessment.purpose == "electrical_losses"
            else assessment
        )
        for assessment in inputs.assessments
    )
    with pytest.raises(OperationalAEPError, match="BOUNDARY_MISMATCH"):
        estimate_operational_aep(replace(inputs, assessments=assessments), spec)


def test_exact_scale_metamorphism() -> None:
    baseline_inputs, baseline_spec = _fixture(supplements=False)
    scaled_inputs, scaled_spec = _fixture(
        meter_values=("475",) * 4,
        turbine_power="1000",
        availability_values=("50",) * 4,
        curtailment_values=("25",) * 4,
        supplements=False,
    )
    baseline = estimate_operational_aep(baseline_inputs, baseline_spec)
    scaled = estimate_operational_aep(scaled_inputs, scaled_spec)
    for name in (
        "net_meter_energy",
        "turbine_terminal_energy",
        "availability_loss",
        "electrical_loss",
        "curtailment_loss",
        "turbine_known_gross",
    ):
        assert _value(scaled, name) == 2 * _value(baseline, name)


def _half_decimal(numerator: int) -> str:
    """Render a non-negative integer count of half-units as a decimal."""
    whole, remainder = divmod(numerator, 2)
    return str(whole) if remainder == 0 else f"{whole}.5"


@given(st.integers(min_value=1, max_value=20))
@settings(max_examples=12, deadline=None)
def test_exact_scale_property(factor: int) -> None:
    """Exact totals and loss identities scale over a bounded integer domain."""
    baseline_inputs, baseline_spec = _fixture(supplements=False)
    scaled_inputs, scaled_spec = _fixture(
        meter_values=(_half_decimal(475 * factor),) * 4,
        turbine_power=str(500 * factor),
        availability_values=(str(25 * factor),) * 4,
        curtailment_values=(_half_decimal(25 * factor),) * 4,
        supplements=False,
    )
    baseline = estimate_operational_aep(baseline_inputs, baseline_spec)
    scaled = estimate_operational_aep(scaled_inputs, scaled_spec)
    for name in (
        "net_meter_energy",
        "turbine_terminal_energy",
        "availability_loss",
        "electrical_loss",
        "curtailment_loss",
        "meter_loss_restored_gross",
        "turbine_known_gross",
    ):
        assert _value(scaled, name) == factor * _value(baseline, name)


def test_equal_meter_turbine_increment_preserves_electrical_loss() -> None:
    baseline_inputs, baseline_spec = _fixture(supplements=False)
    incremented_inputs, incremented_spec = _fixture(
        meter_values=("262.5",) * 4,
        turbine_power="550",
        supplements=False,
    )
    baseline = estimate_operational_aep(baseline_inputs, baseline_spec)
    incremented = estimate_operational_aep(incremented_inputs, incremented_spec)
    assert _value(incremented, "electrical_loss") == _value(baseline, "electrical_loss")
    assert (
        _value(incremented, "net_meter_energy")
        == _value(baseline, "net_meter_energy") + 100
    )
    assert (
        _value(incremented, "turbine_terminal_energy")
        == _value(baseline, "turbine_terminal_energy") + 100
    )


def test_named_loss_increment_changes_only_restored_gross() -> None:
    baseline_inputs, baseline_spec = _fixture(supplements=False)
    incremented_inputs, incremented_spec = _fixture(
        availability_values=("35",) * 4,
        supplements=False,
    )
    baseline = estimate_operational_aep(baseline_inputs, baseline_spec)
    incremented = estimate_operational_aep(incremented_inputs, incremented_spec)
    assert (
        _value(incremented, "availability_loss")
        == _value(baseline, "availability_loss") + 40
    )
    assert (
        _value(incremented, "meter_loss_restored_gross")
        == _value(baseline, "meter_loss_restored_gross") + 40
    )
    assert (
        _value(incremented, "turbine_known_gross")
        == _value(baseline, "turbine_known_gross") + 40
    )
    assert _value(incremented, "net_meter_energy") == _value(
        baseline, "net_meter_energy"
    )


def test_selector_ambiguity_and_unselected_results_fail_closed() -> None:
    inputs, spec = _fixture()
    duplicate = replace(
        inputs,
        normalized_results=inputs.normalized_results + (inputs.normalized_results[0],),
    )
    with pytest.raises(OperationalAEPError, match="SELECTOR_AMBIGUITY"):
        estimate_operational_aep(duplicate, spec)


def test_missing_selector_and_duplicate_assessment_fail_closed() -> None:
    inputs, spec = _fixture()
    missing = replace(inputs, normalized_results=inputs.normalized_results[1:])
    with pytest.raises(OperationalAEPError, match="SELECTOR_AMBIGUITY"):
        estimate_operational_aep(missing, spec)
    duplicate_assessment = replace(
        inputs, assessments=inputs.assessments + (inputs.assessments[0],)
    )
    with pytest.raises(OperationalAEPError, match="SELECTOR_AMBIGUITY"):
        estimate_operational_aep(duplicate_assessment, spec)


def test_partial_loss_products_cannot_borrow_completeness_from_another_product() -> (
    None
):
    inputs, spec = _fixture(supplements=False)
    timestamps = tuple(f"2025-01-01T00:{minute:02d}:00Z" for minute in (0, 15, 30, 45))
    availability_data = (
        "time,availability\n" + "".join(f"{stamp},25\n" for stamp in timestamps)
    ).encode()
    curtailment_data = (
        "time,curtailment\n" + "".join(f"{stamp},12.5\n" for stamp in timestamps)
    ).encode()
    availability_evidence = _evidence(
        "losses.availability.partial",
        "curtailment",
        availability_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("availability_loss_kwh", "availability", "kWh"),
        ),
    )
    curtailment_evidence = _evidence(
        "losses.curtailment.partial",
        "curtailment",
        curtailment_data,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("curtailment_loss_kwh", "curtailment", "kWh"),
        ),
    )
    availability_result = normalize_operational_csv(
        availability_data, availability_evidence
    )
    curtailment_result = normalize_operational_csv(
        curtailment_data, curtailment_evidence
    )
    long_term = next(
        item for item in inputs.assessments if item.purpose == "long_term_aep"
    )
    long_term = replace(
        long_term,
        datasets=long_term.datasets + (availability_evidence, curtailment_evidence),
    )
    forged_inputs = replace(
        inputs,
        assessments=(inputs.assessments[0], long_term),
        normalized_results=inputs.normalized_results[:2]
        + (availability_result, curtailment_result),
        boundary_evidence=replace(
            inputs.boundary_evidence,
            availability_logical_id=availability_evidence.logical_id,
            curtailment_logical_id=curtailment_evidence.logical_id,
        ),
    )
    forged_spec = replace(
        spec,
        availability_logical_id=availability_evidence.logical_id,
        curtailment_logical_id=curtailment_evidence.logical_id,
    )
    with pytest.raises(OperationalAEPError, match="individually complete"):
        estimate_operational_aep(forged_inputs, forged_spec)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "other-project"),
        ("effective_end_exclusive_utc", "2025-01-01T01:15:00Z"),
        ("meter_logical_id", "meter.other"),
    ],
)
def test_boundary_mismatch_fails_closed(field: str, value: str) -> None:
    inputs, spec = _fixture()
    with pytest.raises(
        OperationalAEPError, match="BOUNDARY_MISMATCH|SELECTOR_AMBIGUITY"
    ):
        estimate_operational_aep(inputs, replace(spec, **{field: value}))


def test_attested_window_cannot_override_d2_effective_bounds() -> None:
    inputs, spec = _fixture()
    end = "2025-01-01T01:15:00Z"
    inputs = replace(
        inputs,
        boundary_evidence=replace(
            inputs.boundary_evidence, effective_end_exclusive_utc=end
        ),
    )
    with pytest.raises(OperationalAEPError, match="INTERVAL_MISMATCH"):
        estimate_operational_aep(inputs, replace(spec, effective_end_exclusive_utc=end))


def test_negative_electrical_loss_is_not_tolerance_masked() -> None:
    inputs, spec = _fixture(meter_values=("251",) * 4, supplements=False)
    spec = replace(spec, absolute_tolerance_kwh="1000000")
    with pytest.raises(OperationalAEPError, match="negative electrical loss"):
        estimate_operational_aep(inputs, spec)


@pytest.mark.parametrize(
    ("availability", "curtailment"),
    [("-1", "0"), ("0", "-1")],
)
def test_negative_named_loss_is_rejected(availability: str, curtailment: str) -> None:
    inputs, spec = _fixture(
        availability_values=(availability,) * 4,
        curtailment_values=(curtailment,) * 4,
        supplements=False,
    )
    with pytest.raises(OperationalAEPError, match="positive-means-loss"):
        estimate_operational_aep(inputs, spec)


def test_negative_unknown_residual_is_not_absorbed() -> None:
    inputs, spec = _fixture()
    wake = replace(inputs.supplemental_evidence[1], value_kwh="101")
    spec = replace(spec, absolute_tolerance_kwh="1000000")
    with pytest.raises(OperationalAEPError, match="residual is negative"):
        estimate_operational_aep(
            replace(
                inputs, supplemental_evidence=(inputs.supplemental_evidence[0], wake)
            ),
            spec,
        )


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "1e4097", " 1", 1.0, True])
def test_hostile_tolerance_values_fail_closed(bad: Any) -> None:
    _, spec = _fixture()
    with pytest.raises(ValueError):
        replace(spec, absolute_tolerance_kwh=bad)


def test_provenance_digest_substitution_is_rejected() -> None:
    inputs, _ = _fixture()
    with pytest.raises(ValueError, match="source bytes do not match"):
        replace(inputs.boundary_evidence, source_bytes=b"replacement")
    with pytest.raises(ValueError, match="method bytes do not match"):
        replace(inputs.supplemental_evidence[0], method_bytes=b"replacement")


def test_d2_artifact_substitution_is_replayed_and_rejected() -> None:
    inputs, spec = _fixture()
    forged_meter = copy.deepcopy(inputs.normalized_results[0])
    forged_rows = list(forged_meter.normalized_rows)
    forged_rows[0] = forged_rows[0][:-1] + ("999",)
    object.__setattr__(forged_meter, "normalized_rows", tuple(forged_rows))
    forged_inputs = replace(
        inputs,
        normalized_results=(forged_meter,) + inputs.normalized_results[1:],
    )
    with pytest.raises(OperationalAEPError, match="PROVENANCE_MISMATCH"):
        estimate_operational_aep(forged_inputs, spec)


@pytest.mark.parametrize("nested_field", ["evidence", "receipt"])
def test_d2_nested_contract_substitution_fails_closed(nested_field: str) -> None:
    """Validate retained D2 nested contracts before any identity dereference."""
    inputs, spec = _fixture()
    forged = copy.deepcopy(inputs.normalized_results[0])
    object.__setattr__(forged, nested_field, None)
    forged_inputs = replace(
        inputs,
        normalized_results=(forged,) + inputs.normalized_results[1:],
    )
    with pytest.raises(OperationalAEPError) as error:
        estimate_operational_aep(forged_inputs, spec)
    assert error.value.code == "PROVENANCE_MISMATCH"


def test_d2_nested_column_and_row_receipt_types_fail_closed() -> None:
    """Reject adjacent malformed D1/D2 fields without leaking raw exceptions."""
    inputs, spec = _fixture()

    forged_columns = copy.deepcopy(inputs.normalized_results[0])
    forged_evidence = copy.deepcopy(forged_columns.evidence)
    object.__setattr__(forged_evidence, "columns", (object(),))
    object.__setattr__(forged_columns, "evidence", forged_evidence)

    forged_receipt = copy.deepcopy(inputs.normalized_results[0])
    receipt = copy.deepcopy(forged_receipt.receipt)
    object.__setattr__(receipt, "row_exclusions", (object(),))
    object.__setattr__(forged_receipt, "receipt", receipt)

    for forged in (forged_columns, forged_receipt):
        forged_inputs = replace(
            inputs,
            normalized_results=(forged,) + inputs.normalized_results[1:],
        )
        with pytest.raises(OperationalAEPError) as error:
            estimate_operational_aep(forged_inputs, spec)
        assert error.value.code == "PROVENANCE_MISMATCH"


def test_wrong_runtime_d2_result_fails_before_selection() -> None:
    """Reject a non-D2 object before reading a logical identifier from it."""
    inputs, spec = _fixture()
    forged_inputs = copy.deepcopy(inputs)
    object.__setattr__(
        forged_inputs,
        "normalized_results",
        (object(),) + forged_inputs.normalized_results[1:],
    )
    with pytest.raises(OperationalAEPError) as error:
        estimate_operational_aep(forged_inputs, spec)
    assert error.value.code in {"INVALID_INPUT", "PROVENANCE_MISMATCH"}


def test_factory_replay_immutability_and_authority_fences() -> None:
    inputs, spec = _fixture()
    result = estimate_operational_aep(inputs, spec)
    with pytest.raises(ValueError, match="must be constructed"):
        OperationalAEPResult(
            inputs=result.inputs,
            spec=result.spec,
            components=result.components,
            ratios=result.ratios,
            receipt=result.receipt,
        )
    substituted_receipt = replace(result.receipt, source_manifest_sha256="0" * 64)
    with pytest.raises(ValueError, match="does not replay"):
        OperationalAEPResult(
            inputs=result.inputs,
            spec=result.spec,
            components=result.components,
            ratios=result.ratios,
            receipt=substituted_receipt,
            _factory_token=aep_module._AEP_RESULT_TOKEN,
        )
    with pytest.raises(FrozenInstanceError):
        result.receipt.bankable = True  # type: ignore[misc]
    for name in (
        "canonical_finance_eligible",
        "bankable",
        "lender_eligible",
        "board_eligible",
    ):
        assert getattr(result.receipt, name) is False


def test_temporal_and_uncertainty_laundering_is_rejected() -> None:
    _, spec = _fixture()
    with pytest.raises(ValueError, match="temporal_basis"):
        replace(spec, temporal_basis="long_term_average")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="complete UTC"):
        replace(spec, temporal_basis="actual_calendar_year")
    inputs, spec = _fixture()
    result = estimate_operational_aep(inputs, spec)
    with pytest.raises(ValueError, match="uncertainty"):
        replace(result.receipt, annual_uncertainty_status="available")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="temporal_basis"):
        replace(result.receipt, temporal_basis="long_term_average")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="residual exceeds"):
        replace(
            result.receipt,
            meter_to_turbine_residual=OperationalEnergyQuantity(1),
        )


def test_complete_utc_calendar_year_label_is_admitted() -> None:
    _, spec = _fixture()
    annual = replace(
        spec,
        effective_start_utc="2024-01-01T00:00:00Z",
        effective_end_exclusive_utc="2025-01-01T00:00:00Z",
        temporal_basis="actual_calendar_year",
    )
    assert annual.temporal_basis == "actual_calendar_year"


def test_turbine_energy_column_cannot_override_required_power_role() -> None:
    inputs, spec = _fixture(scada_energy="1", supplements=False)
    result = estimate_operational_aep(inputs, spec)
    assert _value(result, "turbine_terminal_energy") == 1000
    assert _value(result, "electrical_loss") == 50


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("meter_energy_basis", "gross_import_energy"),
        ("turbine_energy_basis", "partial_turbine_energy"),
        ("loss_energy_basis", "overlapping_signed_energy"),
        ("interval_boundary", "interval_end"),
        ("excluded_flows", "imports_included"),
        ("asset_universe_basis", "caller_guess"),
    ],
)
def test_boundary_semantic_assertions_are_closed(field: str, value: str) -> None:
    inputs, _ = _fixture()
    with pytest.raises(ValueError, match=field):
        replace(inputs.boundary_evidence, **{field: value})


def test_zero_denominators_are_unavailable_while_zero_energy_is_available() -> None:
    inputs, spec = _fixture(
        meter_values=("0",) * 4,
        turbine_power="0",
        availability_values=("0",) * 4,
        curtailment_values=("0",) * 4,
    )
    zero_supplements = tuple(
        replace(item, value_kwh="0") for item in inputs.supplemental_evidence
    )
    result = estimate_operational_aep(
        replace(inputs, supplemental_evidence=zero_supplements), spec
    )
    for name in (
        "net_meter_energy",
        "turbine_terminal_energy",
        "availability_loss",
        "electrical_loss",
        "curtailment_loss",
        "resource_gross_energy",
        "wake_performance_loss",
        "unknown_residual_loss",
    ):
        assert result.component(name).status == "available"  # type: ignore[arg-type]
        assert _value(result, name) == 0
    for ratio in result.ratios:
        assert ratio.status == "unavailable"
        assert ratio.unavailable_reason == "denominator_is_zero"


def test_provenance_resource_bounds_and_binding_roles_fail_closed() -> None:
    inputs, spec = _fixture()
    oversized = b"x" * 1_048_577
    with pytest.raises(ValueError, match="1 MiB"):
        replace(
            inputs.supplemental_evidence[0],
            source_bytes=oversized,
            source_sha256=_digest(oversized),
        )
    result = estimate_operational_aep(inputs, spec)
    with pytest.raises(ValueError, match="role is not supported"):
        replace(result.receipt.source_bindings[0], role="invented")


def test_public_contract_validation_branches_fail_closed() -> None:
    """Exercise hostile public-contract states before they can reach arithmetic."""
    inputs, spec = _fixture()
    result = estimate_operational_aep(inputs, spec)

    quantity_cases = (
        lambda: OperationalEnergyQuantity(True),
        lambda: OperationalEnergyQuantity(1, 0),
        lambda: OperationalEnergyQuantity(1, unit="MWh"),  # type: ignore[arg-type]
        lambda: OperationalEnergyQuantity(1 << 16_384),
        lambda: OperationalEnergyQuantity(2, 2),
        lambda: OperationalEnergyQuantity.from_fraction("1"),  # type: ignore[arg-type]
    )
    for construct in quantity_cases:
        with pytest.raises(ValueError):
            construct()
    quantity = OperationalEnergyQuantity(3, 2)
    assert quantity.as_fraction() == Fraction(3, 2)
    assert quantity.model_dump() == {"numerator": 3, "denominator": 2, "unit": "kWh"}

    component = result.component("net_meter_energy")
    component_cases = (
        {"name": "invented"},
        {"value": None},
        {"unavailable_reason": "not unavailable"},
        {"status": "unavailable"},
        {"status": "invented"},
        {"evidence_ids": ("bad id",)},
    )
    for changes in component_cases:
        with pytest.raises(ValueError):
            replace(component, **changes)

    ratio = next(item for item in result.ratios if item.status == "available")
    ratio_cases = (
        {"numerator": None},
        {"denominator": 0},
        {"unavailable_reason": "not unavailable"},
        {"status": "unavailable"},
        {"status": "invented"},
    )
    for changes in ratio_cases:
        with pytest.raises(ValueError):
            replace(ratio, **changes)

    with pytest.raises(ValueError, match="effective interval"):
        replace(
            inputs.boundary_evidence,
            effective_end_exclusive_utc=inputs.boundary_evidence.effective_start_utc,
        )

    supplemental = inputs.supplemental_evidence[0]
    supplemental_cases = (
        {"component": "invented"},
        {"boundary": "resource_to_turbine_combined_wake_performance"},
        {"effective_end_exclusive_utc": supplemental.effective_start_utc},
        {"value_kwh": "-1"},
    )
    for changes in supplemental_cases:
        with pytest.raises(ValueError):
            replace(supplemental, **changes)

    with pytest.raises(ValueError, match="effective interval"):
        replace(spec, effective_end_exclusive_utc=spec.effective_start_utc)
    with pytest.raises(ValueError, match="assessments"):
        replace(inputs, assessments=())
    with pytest.raises(ValueError, match="boundary_evidence"):
        replace(inputs, boundary_evidence=object())
    with pytest.raises(ValueError, match="supplemental_evidence"):
        replace(inputs, supplemental_evidence=[])

    d2_binding = result.receipt.source_bindings[0]
    supplemental_binding = next(
        item
        for item in result.receipt.source_bindings
        if item.role == "resource_gross_energy"
    )
    binding_cases: tuple[tuple[OperationalAEPSourceBinding, dict[str, Any]], ...] = (
        (d2_binding, {"source_sha256": "bad"}),
        (d2_binding, {"normalized_sha256": "bad"}),
        (d2_binding, {"claim_sha256": "bad"}),
        (d2_binding, {"normalized_sha256": None}),
        (supplemental_binding, {"normalized_sha256": "0" * 64}),
    )
    for binding, changes in binding_cases:
        with pytest.raises(ValueError):
            replace(binding, **changes)

    assert isinstance(component, OperationalEnergyComponent)
    assert isinstance(ratio, OperationalRatio)


def test_resource_without_wake_does_not_infer_unknown_zero() -> None:
    inputs, spec = _fixture()
    resource_only = replace(
        inputs, supplemental_evidence=inputs.supplemental_evidence[:1]
    )
    result = estimate_operational_aep(resource_only, spec)
    assert result.component("resource_gross_energy").status == "available"
    assert result.component("wake_performance_loss").status == "unavailable"
    assert result.component("unknown_residual_loss").status == "unavailable"


def test_wake_without_resource_remains_available_but_residual_does_not() -> None:
    inputs, spec = _fixture()
    wake_only = replace(inputs, supplemental_evidence=inputs.supplemental_evidence[1:])
    result = estimate_operational_aep(wake_only, spec)
    assert result.component("resource_gross_energy").status == "unavailable"
    assert result.component("wake_performance_loss").status == "available"
    assert result.component("unknown_residual_loss").status == "unavailable"


@pytest.mark.parametrize(
    "field",
    [
        "canonical_finance_eligible",
        "bankable",
        "lender_eligible",
        "board_eligible",
    ],
)
def test_authority_flags_cannot_be_laundered(field: str) -> None:
    inputs, spec = _fixture()
    result = estimate_operational_aep(inputs, spec)
    with pytest.raises(ValueError, match="exact boolean False"):
        replace(result.receipt, **{field: True})


def test_model_dump_omits_retained_provenance_bytes() -> None:
    inputs, spec = _fixture()
    payload = estimate_operational_aep(inputs, spec).model_dump()
    rendered = repr(payload)
    assert "matched plant boundary attestation" not in rendered
    assert "independent resource gross" not in rendered
    assert payload["receipt"]["raw_operational_only"] is True
