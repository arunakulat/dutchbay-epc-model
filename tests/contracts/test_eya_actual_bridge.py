from __future__ import annotations

import copy
import hashlib
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from fractions import Fraction
from typing import Any

import pytest

import analytics.operational.eya_bridge as bridge_module
from analytics.operational.aep import (
    OperationalAEPInput,
    OperationalAEPResult,
    OperationalAEPSpec,
    OperationalBoundaryEvidence,
    OperationalSupplementalEnergyEvidence,
    estimate_operational_aep,
)
from analytics.operational.contracts import (
    OPERATIONAL_EVIDENCE_SCHEMA,
    OperationalAssessmentInput,
    OperationalColumnBinding,
    OperationalDatasetEvidence,
)
from analytics.operational.eya_bridge import (
    EYA_GAP_CATEGORIES,
    EYAActualBoundaryEvidence,
    EYAActualBridgeError,
    EYAActualBridgeResult,
    EYAActualBridgeSpec,
    EYAGapAttributionEvidence,
    FinanceUpdateProposal,
    build_eya_actual_bridge,
    operational_aep_claim_sha256,
    resource_assessment_claim_sha256,
)
from analytics.operational.normalization import (
    OperationalGroupUniverse,
    normalize_operational_csv,
)
from analytics.resource_contracts import ResourceAssessment


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _evidence(
    logical_id: str,
    kind: str,
    data: bytes,
    columns: tuple[OperationalColumnBinding, ...],
    *,
    start: str,
    last: str,
    interval_seconds: int | None = 86_400,
    status: str = "observed",
) -> OperationalDatasetEvidence:
    source_class = (
        "declared_asset"
        if kind == "asset"
        else "reference_reanalysis" if kind == "reanalysis" else "observed_plant"
    )
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
        coverage_end_utc=last,
        interval_basis=("not_applicable" if kind == "asset" else "fixed_seconds"),  # type: ignore[arg-type]
        interval_seconds=None if kind == "asset" else interval_seconds,
        row_count=len(data.decode().strip().splitlines()) - 1,
        columns=columns,
    )


@pytest.fixture(scope="module")
def annual_sources() -> tuple[ResourceAssessment, OperationalAEPResult]:
    days = tuple(date(2025, 1, 1) + timedelta(days=index) for index in range(365))
    timestamps = tuple(f"{day.isoformat()}T00:00:00Z" for day in days)
    start = timestamps[0]
    last = timestamps[-1]
    end = "2026-01-01T00:00:00Z"

    meter_bytes = (
        "time,energy\n" + "".join(f"{stamp},23\n" for stamp in timestamps)
    ).encode()
    scada_bytes = (
        "time,asset,power\n" + "".join(f"{stamp},T01,1\n" for stamp in timestamps)
    ).encode()
    loss_bytes = (
        "time,availability,curtailment\n"
        + "".join(f"{stamp},1,0.5\n" for stamp in timestamps)
    ).encode()
    asset_bytes = b"asset,rated\nT01,1\n"
    reanalysis_bytes = (
        "time,wind,density\n" + "".join(f"{stamp},8,1.2\n" for stamp in timestamps)
    ).encode()

    meter = _evidence(
        "meter.primary",
        "revenue_meter",
        meter_bytes,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("energy_kwh", "energy", "kWh"),
        ),
        start=start,
        last=last,
    )
    assets = _evidence(
        "assets.primary",
        "asset",
        asset_bytes,
        (
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("rated_power_kw", "rated", "kW"),
        ),
        start=start,
        last=last,
        interval_seconds=None,
        status="declared_metadata",
    )
    scada = _evidence(
        "scada.primary",
        "scada",
        scada_bytes,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("asset_id", "asset", "1"),
            OperationalColumnBinding("power_kw", "power", "kW"),
        ),
        start=start,
        last=last,
    )
    losses = _evidence(
        "losses.primary",
        "curtailment",
        loss_bytes,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("availability_loss_kwh", "availability", "kWh"),
            OperationalColumnBinding("curtailment_loss_kwh", "curtailment", "kWh"),
        ),
        start=start,
        last=last,
    )
    reanalysis = _evidence(
        "reanalysis.reference",
        "reanalysis",
        reanalysis_bytes,
        (
            OperationalColumnBinding("timestamp_utc", "time", "iso8601_utc"),
            OperationalColumnBinding("wind_speed_ms", "wind", "m/s"),
            OperationalColumnBinding("air_density_kgm3", "density", "kg/m^3"),
        ),
        start=start,
        last=last,
        status="reference_reanalysis",
    )
    universe = OperationalGroupUniverse(normalize_operational_csv(asset_bytes, assets))
    meter_result = normalize_operational_csv(meter_bytes, meter)
    scada_result = normalize_operational_csv(
        scada_bytes, scada, group_universe=universe
    )
    loss_result = normalize_operational_csv(loss_bytes, losses)

    electrical = OperationalAssessmentInput(
        schema=OPERATIONAL_EVIDENCE_SCHEMA,
        project_id="dutchbay",
        assessment_id="d4-electrical",
        purpose="electrical_losses",
        assessment_start_utc=start,
        assessment_end_utc=last,
        datasets=(meter, scada),
    )
    long_term = OperationalAssessmentInput(
        schema=OPERATIONAL_EVIDENCE_SCHEMA,
        project_id="dutchbay",
        assessment_id="d4-long-term",
        purpose="long_term_aep",
        assessment_start_utc=start,
        assessment_end_utc=last,
        datasets=(meter, losses, reanalysis),
    )
    boundary_source = b"D4 common plant boundary attestation"
    boundary_method = b"D4 independent boundary review method"
    boundary = OperationalBoundaryEvidence(
        project_id="dutchbay",
        effective_start_utc=start,
        effective_end_exclusive_utc=end,
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
        source_locator="evidence/d4-boundary.txt",
        source_bytes=boundary_source,
        source_sha256=_digest(boundary_source),
        method_bytes=boundary_method,
        method_sha256=_digest(boundary_method),
    )
    resource_source = b"D4 independent annual resource gross 10000 kWh"
    resource_method = b"D4 annual resource gross method"
    wake_source = b"D4 independent annual wake performance loss 500 kWh"
    wake_method = b"D4 annual wake performance method"
    supplements = (
        OperationalSupplementalEnergyEvidence(
            evidence_id="resource.annual",
            component="resource_gross_energy",
            project_id="dutchbay",
            effective_start_utc=start,
            effective_end_exclusive_utc=end,
            value_kwh="10000",
            boundary="upstream_resource_potential",
            source_locator="evidence/resource-annual.txt",
            source_bytes=resource_source,
            source_sha256=_digest(resource_source),
            method_bytes=resource_method,
            method_sha256=_digest(resource_method),
        ),
        OperationalSupplementalEnergyEvidence(
            evidence_id="wake.annual",
            component="wake_performance_loss",
            project_id="dutchbay",
            effective_start_utc=start,
            effective_end_exclusive_utc=end,
            value_kwh="500",
            boundary="resource_to_turbine_combined_wake_performance",
            source_locator="evidence/wake-annual.txt",
            source_bytes=wake_source,
            source_sha256=_digest(wake_source),
            method_bytes=wake_method,
            method_sha256=_digest(wake_method),
        ),
    )
    operational = estimate_operational_aep(
        OperationalAEPInput(
            assessments=(electrical, long_term),
            normalized_results=(meter_result, scada_result, loss_result),
            boundary_evidence=boundary,
            supplemental_evidence=supplements,
        ),
        OperationalAEPSpec(
            project_id="dutchbay",
            assessment_id="d4.annual.fixture",
            effective_start_utc=start,
            effective_end_exclusive_utc=end,
            temporal_basis="actual_calendar_year",
            meter_logical_id="meter.primary",
            turbine_logical_id="scada.primary",
            availability_logical_id="losses.primary",
            curtailment_logical_id="losses.primary",
            absolute_tolerance_kwh="0",
        ),
    )
    eya_gwh = 0.009
    resource = ResourceAssessment(
        capacity_mw=1.0,
        n_turbines=1,
        net_aep_p50_gwh=eya_gwh,
        net_aep_p75_gwh=eya_gwh,
        net_aep_p90_gwh=eya_gwh,
        capacity_factor_p50=eya_gwh * 1_000 / 8_760,
        capacity_factor_p75=eya_gwh * 1_000 / 8_760,
        capacity_factor_p90=eya_gwh * 1_000 / 8_760,
        selected_p_level="P50",
        report_grade="pre-construction-frozen",
        run_manifest={"run": {"id": "eya-2024", "inputs": ["wind", "losses"]}},
        source_id="eya.freeze.2024",
        power_curve_key="T01-v1",
    )
    return resource, operational


def _bridge_inputs(
    resource: ResourceAssessment, operational: OperationalAEPResult
) -> tuple[EYAActualBridgeSpec, EYAActualBoundaryEvidence]:
    eya_claim = resource_assessment_claim_sha256(resource)
    operational_claim = operational_aep_claim_sha256(operational)
    spec = EYAActualBridgeSpec(
        bridge_id="dutchbay.eya-to-2025",
        eya_p_level="P50",
        expected_eya_claim_sha256=eya_claim,
        expected_operational_claim_sha256=operational_claim,
        category_partition_id="d4-gap-v1",
    )
    source = b"common EYA and actual net-export boundary review"
    method = b"independent common-boundary comparison method"
    boundary = EYAActualBoundaryEvidence(
        project_id="dutchbay",
        asset_identity="Dutch Bay / T01 / common POC",
        delivery_boundary="net_export_at_common_delivery_boundary",
        temporal_comparison="frozen_standard_year_eya_to_actual_calendar_year",
        partition_semantics="mutually_exclusive_named_net_effect_categories",
        category_partition_id="d4-gap-v1",
        eya_claim_sha256=eya_claim,
        operational_claim_sha256=operational_claim,
        source_locator="evidence/eya-actual-boundary.txt",
        source_bytes=source,
        source_sha256=_digest(source),
        method_bytes=method,
        method_sha256=_digest(method),
    )
    return spec, boundary


def _attribution(
    category: str,
    actual: str,
    spec: EYAActualBridgeSpec,
    *,
    expected: str = "0",
    evidence_id: str | None = None,
) -> EYAGapAttributionEvidence:
    source = f"paired {category} observed comparison".encode()
    method = f"paired {category} comparison method".encode()
    return EYAGapAttributionEvidence(
        evidence_id=evidence_id or f"pair.{category}",
        category=category,  # type: ignore[arg-type]
        project_id="dutchbay",
        category_partition_id=spec.category_partition_id,
        eya_claim_sha256=spec.expected_eya_claim_sha256,
        operational_claim_sha256=spec.expected_operational_claim_sha256,
        eya_expected_net_effect_kwh=expected,
        operational_actual_net_effect_kwh=actual,
        sign_convention="positive_increases_actual_vs_eya",
        source_locator=f"evidence/{category}.txt",
        source_bytes=source,
        source_sha256=_digest(source),
        method_bytes=method,
        method_sha256=_digest(method),
    )


def _complete_bridge(
    resource: ResourceAssessment, operational: OperationalAEPResult
) -> EYAActualBridgeResult:
    spec, boundary = _bridge_inputs(resource, operational)
    attributions = (
        _attribution("availability", "-365", spec),
        _attribution("curtailment", "-182.5", spec),
        _attribution("electrical", "-365", spec),
        _attribution("wake_performance", "-500", spec),
        _attribution("method_model", "0", spec),
    )
    return build_eya_actual_bridge(resource, operational, spec, boundary, attributions)


def _contains_bytes(value: object) -> bool:
    if isinstance(value, bytes):
        return True
    if isinstance(value, dict):
        return any(
            _contains_bytes(key) or _contains_bytes(item) for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_bytes(item) for item in value)
    return False


def test_exact_bridge_identity_and_independent_fraction_oracle(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources
    result = _complete_bridge(resource, operational)
    exact_eya = Fraction.from_float(resource.net_aep_p50_gwh) * 1_000_000
    actual = Fraction(8_395)
    attributed = Fraction(-2_825, 2)

    assert result.eya_net_energy_kwh.as_fraction() == exact_eya
    assert result.actual_net_energy_kwh.as_fraction() == actual
    assert result.total_gap_kwh.as_fraction() == actual - exact_eya
    assert result.unknown_residual_kwh.as_fraction() == actual - exact_eya - attributed
    assert exact_eya + attributed + result.unknown_residual_kwh.as_fraction() == actual
    assert result.receipt.full_reconciliation_residual_kwh.as_fraction() == 0

    # Negative control: the decimal-looking float does not authorize rounding to 9000.
    assert exact_eya != Fraction(9_000)
    assert result.unknown_residual_kwh.as_fraction() != actual - 9_000 - attributed


def test_missing_is_unavailable_but_evidenced_zero_is_available(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    result = _complete_bridge(*annual_sources)
    assert (
        tuple(item.category for item in result.category_components)
        == EYA_GAP_CATEGORIES
    )
    assert result.component("measurement_boundary").status == "unavailable"
    assert result.component("weather_resource").status == "unavailable"
    method = result.component("method_model")
    assert method.status == "available"
    assert method.signed_delta_kwh is not None
    assert method.signed_delta_kwh.as_fraction() == 0


def test_finance_proposal_is_structurally_inert_and_default_off(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    proposal = _complete_bridge(*annual_sources).finance_proposal
    assert proposal.default_off is True
    assert proposal.proposed_updates == ()
    assert proposal.target_scenario_id is None
    assert proposal.candidate_capacity_factor is None
    assert proposal.candidate_p50 is None
    assert proposal.candidate_p90 is None
    assert proposal.candidate_debt is None
    assert proposal.candidate_tariff is None
    assert proposal.apply_authorized is False
    assert proposal.requires_separate_r3_rebaseline is True
    assert proposal.issue_1110_state == "OPEN_HOLD"
    assert proposal.canonical_finance_eligible is False
    assert proposal.bankable is False
    assert proposal.lender_eligible is False
    assert proposal.board_eligible is False
    assert proposal.release_eligible is False
    with pytest.raises(ValueError, match="exact boolean False"):
        replace(proposal, apply_authorized=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must remain unavailable"):
        replace(proposal, candidate_p50=9_000)  # type: ignore[arg-type]


def test_source_artifacts_are_preserved_and_snapshot_is_detached(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources
    source_before = copy.deepcopy(resource.model_dump())
    operational_before = copy.deepcopy(operational.model_dump())
    result = _complete_bridge(resource, operational)
    snapshot_json = result.resource_snapshot.run_manifest_json

    assert resource.model_dump() == source_before
    assert operational.model_dump() == operational_before
    assert resource.run_manifest is not None
    resource.run_manifest["later_mutation"] = True
    assert result.resource_snapshot.run_manifest_json == snapshot_json
    assert result.receipt.original_sources_preserved is True
    assert result.receipt.canonical_mutation_performed is False

    # Restore the module-scoped source for the remaining independent tests.
    resource.run_manifest.pop("later_mutation")


def test_model_dump_excludes_all_retained_source_bytes(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    payload = _complete_bridge(*annual_sources).model_dump()
    assert not _contains_bytes(payload)
    assert "operational_result" not in payload
    assert "attribution_evidence" not in payload


@pytest.mark.parametrize(
    ("field", "code"),
    (
        ("eya", "EYA_PROVENANCE_MISMATCH"),
        ("operational", "OPERATIONAL_PROVENANCE_MISMATCH"),
    ),
)
def test_expected_digest_substitution_fails_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
    field: str,
    code: str,
) -> None:
    resource, operational = annual_sources
    spec, boundary = _bridge_inputs(resource, operational)
    if field == "eya":
        spec = replace(spec, expected_eya_claim_sha256="0" * 64)
    else:
        spec = replace(spec, expected_operational_claim_sha256="0" * 64)
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(resource, operational, spec, boundary)
    assert captured.value.code == code


def test_forged_d3_result_is_replayed_and_rejected(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources
    forged = copy.copy(operational)
    object.__setattr__(forged, "components", operational.components[:-1])
    spec, boundary = _bridge_inputs(resource, operational)
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(resource, forged, spec, boundary)
    assert captured.value.code == "OPERATIONAL_PROVENANCE_MISMATCH"


def test_boundary_project_partition_and_claim_bindings_fail_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources
    spec, boundary = _bridge_inputs(resource, operational)
    for hostile in (
        replace(boundary, project_id="other-project"),
        replace(boundary, category_partition_id="other-partition"),
        replace(boundary, eya_claim_sha256="0" * 64),
    ):
        with pytest.raises(EYAActualBridgeError) as captured:
            build_eya_actual_bridge(resource, operational, spec, hostile)
        assert captured.value.code == "BOUNDARY_MISMATCH"


def test_duplicate_category_and_cross_project_attribution_fail_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources
    spec, boundary = _bridge_inputs(resource, operational)
    first = _attribution("availability", "-365", spec, evidence_id="pair.a")
    duplicate = _attribution("availability", "-365", spec, evidence_id="pair.b")
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(
            resource, operational, spec, boundary, (first, duplicate)
        )
    assert captured.value.code == "ATTRIBUTION_MISMATCH"

    hostile = replace(first, project_id="other-project")
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(resource, operational, spec, boundary, (hostile,))
    assert captured.value.code == "ATTRIBUTION_MISMATCH"


@pytest.mark.parametrize(
    ("category", "actual"),
    (
        ("availability", "365"),
        ("curtailment", "-1"),
        ("electrical", "-364"),
        ("wake_performance", "500"),
    ),
)
def test_d3_backed_category_sign_or_value_substitution_fails_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
    category: str,
    actual: str,
) -> None:
    resource, operational = annual_sources
    spec, boundary = _bridge_inputs(resource, operational)
    hostile = _attribution(category, actual, spec)
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(resource, operational, spec, boundary, (hostile,))
    assert captured.value.code == "ATTRIBUTION_MISMATCH"


def test_observed_period_and_standard_year_mismatch_fail_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources
    observed = estimate_operational_aep(
        operational.inputs,
        replace(operational.spec, temporal_basis="observed_period_total"),
    )
    spec, boundary = _bridge_inputs(resource, observed)
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(resource, observed, spec, boundary)
    assert captured.value.code == "TEMPORAL_MISMATCH"

    mismatched = replace(
        resource,
        hours_per_year=8_000.0,
        capacity_factor_p50=resource.net_aep_p50_gwh * 1_000 / 8_000,
        capacity_factor_p75=resource.net_aep_p75_gwh * 1_000 / 8_000,
        capacity_factor_p90=resource.net_aep_p90_gwh * 1_000 / 8_000,
    )
    spec, boundary = _bridge_inputs(mismatched, operational)
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(mismatched, operational, spec, boundary)
    assert captured.value.code == "TEMPORAL_MISMATCH"


@pytest.mark.parametrize("hostile_field", ("bool", "nan", "permissive_tolerance"))
def test_hostile_resource_numeric_contracts_fail_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
    hostile_field: str,
) -> None:
    resource, _ = annual_sources
    hostile = copy.copy(resource)
    if hostile_field == "bool":
        object.__setattr__(hostile, "capacity_mw", True)
    elif hostile_field == "nan":
        object.__setattr__(hostile, "net_aep_p50_gwh", float("nan"))
    else:
        object.__setattr__(hostile, "identity_rtol", 0.5)
    with pytest.raises(EYAActualBridgeError) as captured:
        resource_assessment_claim_sha256(hostile)
    assert captured.value.code == "INVALID_INPUT"


def test_cyclic_and_unbounded_resource_manifest_fail_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, _ = annual_sources
    cyclic = copy.copy(resource)
    cycle: dict[str, Any] = {}
    cycle["self"] = cycle
    object.__setattr__(cyclic, "run_manifest", cycle)
    with pytest.raises(EYAActualBridgeError) as captured:
        resource_assessment_claim_sha256(cyclic)
    assert captured.value.code == "INVALID_INPUT"

    deep: dict[str, Any] = {}
    cursor = deep
    for index in range(40):
        nested: dict[str, Any] = {"index": index}
        cursor["next"] = nested
        cursor = nested
    overdeep = copy.copy(resource)
    object.__setattr__(overdeep, "run_manifest", deep)
    with pytest.raises(EYAActualBridgeError) as captured:
        resource_assessment_claim_sha256(overdeep)
    assert captured.value.code == "INVALID_INPUT"


def test_provenance_bytes_and_digests_are_immutable_and_verified(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources
    spec, boundary = _bridge_inputs(resource, operational)
    with pytest.raises(FrozenInstanceError):
        boundary.source_bytes = b"replacement"  # type: ignore[misc]
    with pytest.raises(ValueError, match="source bytes"):
        replace(boundary, source_sha256="0" * 64)
    evidence = _attribution("method_model", "0", spec)
    with pytest.raises(ValueError, match="method bytes"):
        replace(evidence, method_sha256="0" * 64)


def test_result_is_factory_only_and_replays_all_outputs(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    result = _complete_bridge(*annual_sources)
    with pytest.raises(ValueError, match="must be constructed"):
        replace(result)
    with pytest.raises(ValueError, match="must be constructed"):
        replace(
            result,
            unknown_residual_kwh=result.total_gap_kwh,
        )


def test_finance_constructor_rejects_hold_or_authority_laundering(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    result = _complete_bridge(*annual_sources)
    claims = {
        "eya_claim_sha256": result.receipt.eya_claim_sha256,
        "operational_claim_sha256": result.receipt.operational_claim_sha256,
    }
    with pytest.raises(ValueError, match="OPEN_HOLD"):
        FinanceUpdateProposal(**claims, issue_1110_state="CLOSED")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="exact boolean False"):
        FinanceUpdateProposal(**claims, bankable=True)  # type: ignore[arg-type]


def test_public_value_objects_reject_hostile_closed_vocabulary_states(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    result = _complete_bridge(*annual_sources)
    snapshot = result.resource_snapshot
    manifest_list = "[]"
    noncanonical_manifest = '{"z":1, "a":2}'
    snapshot_attacks = (
        {"n_turbines": 0},
        {"selected_p_level": "P10"},
        {"run_manifest_json": None, "run_manifest_sha256": "0" * 64},
        {"run_manifest_sha256": "0" * 64},
        {
            "run_manifest_json": manifest_list,
            "run_manifest_sha256": _digest(manifest_list.encode()),
        },
        {
            "run_manifest_json": noncanonical_manifest,
            "run_manifest_sha256": _digest(noncanonical_manifest.encode()),
        },
        {"capacity_mw_hex": 1},
        {"capacity_mw_hex": "not-hex"},
        {"capacity_mw_hex": "INF"},
    )
    for changes in snapshot_attacks:
        with pytest.raises(ValueError):
            replace(snapshot, **changes)  # type: ignore[arg-type]

    spec, boundary = _bridge_inputs(*annual_sources)
    for changes in (
        {"eya_p_level": "P10"},
        {"arithmetic_policy": "rounded_decimal"},
        {"bridge_id": " bad "},
        {"expected_eya_claim_sha256": "ABC"},
    ):
        with pytest.raises(ValueError):
            replace(spec, **changes)  # type: ignore[arg-type]

    for changes in (
        {"delivery_boundary": "gross"},
        {"temporal_comparison": "annualized_partial"},
        {"partition_semantics": "overlapping"},
        {"asset_identity": " bad\n"},
    ):
        with pytest.raises(ValueError):
            replace(boundary, **changes)  # type: ignore[arg-type]

    evidence = _attribution("method_model", "2", spec, expected="1")
    assert evidence.delta == 1
    for changes in (
        {"category": "other"},
        {"sign_convention": "positive_reduces_actual"},
        {"eya_expected_net_effect_kwh": "NaN"},
        {"operational_actual_net_effect_kwh": "1e9999"},
    ):
        with pytest.raises(ValueError):
            replace(evidence, **changes)  # type: ignore[arg-type]


def test_gap_component_receipt_and_proposal_invariants_are_independent(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    result = _complete_bridge(*annual_sources)
    component = result.component("method_model")
    unavailable = result.component("measurement_boundary")
    quantity = result.receipt.full_reconciliation_residual_kwh
    for changes in (
        {"category": "other"},
        {"signed_delta_kwh": None},
        {"unavailable_reason": "unexpected"},
        {"signed_delta_kwh": result.actual_net_energy_kwh},
    ):
        with pytest.raises(ValueError):
            replace(component, **changes)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cannot carry evidence"):
        replace(unavailable, signed_delta_kwh=quantity)
    with pytest.raises(ValueError, match="status"):
        replace(unavailable, status="other")  # type: ignore[arg-type]

    proposal = result.finance_proposal
    for changes in (
        {"decision": "adopt"},
        {"default_off": False},
        {"proposed_updates": ("capacity_factor",)},
        {"requires_separate_r3_rebaseline": False},
    ):
        with pytest.raises(ValueError):
            replace(proposal, **changes)  # type: ignore[arg-type]

    receipt = result.receipt
    receipt_attacks = (
        {"schema": "other"},
        {"arithmetic_policy": "rounded_decimal"},
        {"sign_convention": "positive_reduces_actual"},
        {"full_reconciliation_residual_kwh": result.actual_net_energy_kwh},
        {"original_sources_preserved": False},
        {"issue_1110_state": "CLOSED"},
        {"release_eligible": True},
    )
    for changes in receipt_attacks:
        with pytest.raises(ValueError):
            replace(receipt, **changes)  # type: ignore[arg-type]

    with pytest.raises(KeyError):
        result.component("other")  # type: ignore[arg-type]


def test_manifest_and_provenance_resource_bounds_fail_closed(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    resource, operational = annual_sources

    hostile_manifests: tuple[object, ...] = (
        ["not-a-dict"],
        {1: "non-string-key"},
        {"unsupported": (1, 2)},
        {"nonfinite": float("inf")},
        {"integer": 1 << 4_097},
        {"text": "x" * 1_000_001},
        {"containers": [[] for _ in range(1_001)]},
        {"scalars": [0 for _ in range(10_001)]},
    )
    for manifest in hostile_manifests:
        hostile = copy.copy(resource)
        object.__setattr__(hostile, "run_manifest", manifest)
        with pytest.raises(EYAActualBridgeError) as captured:
            resource_assessment_claim_sha256(hostile)
        assert captured.value.code == "INVALID_INPUT"

    for field, value in (
        ("n_turbines", 0),
        ("selected_p_level", "P10"),
        ("report_grade", ""),
        ("source_id", " bad\n"),
    ):
        hostile = copy.copy(resource)
        object.__setattr__(hostile, field, value)
        with pytest.raises(EYAActualBridgeError) as captured:
            resource_assessment_claim_sha256(hostile)
        assert captured.value.code == "INVALID_INPUT"

    with pytest.raises(EYAActualBridgeError) as captured:
        resource_assessment_claim_sha256(object())  # type: ignore[arg-type]
    assert captured.value.code == "INVALID_INPUT"
    with pytest.raises(EYAActualBridgeError) as captured:
        operational_aep_claim_sha256(object())  # type: ignore[arg-type]
    assert captured.value.code == "OPERATIONAL_PROVENANCE_MISMATCH"

    spec, boundary = _bridge_inputs(resource, operational)
    provenance_attacks = (
        {"source_bytes": b""},
        {"method_bytes": b""},
        {"source_bytes": b"x" * 1_048_577},
        {
            "method_bytes": boundary.source_bytes,
            "method_sha256": boundary.source_sha256,
        },
    )
    for changes in provenance_attacks:
        with pytest.raises(ValueError):
            replace(boundary, **changes)  # type: ignore[arg-type]

    wrong_p_level = replace(spec, eya_p_level="P75")
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(resource, operational, wrong_p_level, boundary)
    assert captured.value.code == "EYA_PROVENANCE_MISMATCH"
    with pytest.raises(EYAActualBridgeError) as captured:
        build_eya_actual_bridge(
            resource,
            operational,
            spec,
            boundary,
            [_attribution("method_model", "0", spec)],  # type: ignore[arg-type]
        )
    assert captured.value.code == "INVALID_INPUT"


def test_even_private_token_cannot_authorize_substituted_result(
    annual_sources: tuple[ResourceAssessment, OperationalAEPResult],
) -> None:
    result = _complete_bridge(*annual_sources)
    with pytest.raises(ValueError, match="does not replay"):
        EYAActualBridgeResult(
            resource_snapshot=result.resource_snapshot,
            operational_result=result.operational_result,
            spec=result.spec,
            boundary_evidence=result.boundary_evidence,
            attribution_evidence=result.attribution_evidence,
            eya_net_energy_kwh=result.eya_net_energy_kwh,
            actual_net_energy_kwh=result.actual_net_energy_kwh,
            total_gap_kwh=result.total_gap_kwh,
            category_components=result.category_components,
            unknown_residual_kwh=result.actual_net_energy_kwh,
            finance_proposal=result.finance_proposal,
            receipt=result.receipt,
            _factory_token=bridge_module._BRIDGE_RESULT_TOKEN,
        )
