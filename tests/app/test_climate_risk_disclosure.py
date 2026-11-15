"""Unit tests and negative controls for bounded climate-risk disclosure (#1335, D5)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.reports.climate_risk_disclosure import (
    MANDATORY_CLIMATE_DISCLOSURE_DISCLAIMER,
    ClimateDisclosurePerimeter,
    ClimateRiskDisclosureContext,
    ClimateRiskDriver,
    ClimateScenario,
    FinancialTransmissionItem,
    TimeHorizon,
    render_climate_risk_disclosure_html,
    render_climate_risk_disclosure_partial,
)


@pytest.fixture
def valid_perimeter() -> ClimateDisclosurePerimeter:
    return ClimateDisclosurePerimeter(
        project_name="DutchBay Wind Power Project",
        jurisdiction="Sri Lanka",
        jurisdiction_iso="LK",
        reporting_boundary="Project concession boundary & 33kV substation delivery point",
        asset_lifespan_years=25,
    )


@pytest.fixture
def valid_scenarios() -> tuple[ClimateScenario, ...]:
    return (
        ClimateScenario(
            scenario_id="ssp2_45_regional",
            name="IPCC AR6 SSP2-4.5 (Regional Downscaled)",
            pathway_family="IPCC AR6 / CMIP6",
            selection_rationale="Aligned with Central Environmental Authority baseline for coastal Mannar basin infrastructure.",
            source_citation="Department of Meteorology Sri Lanka & IPCC Sixth Assessment Report (2021)",
            temperature_trajectory="~2.7°C warming by 2100",
            source_digest="a" * 64,
        ),
        ClimateScenario(
            scenario_id="ngfs_net_zero_2050",
            name="NGFS Net Zero 2050 (Orderly Transition)",
            pathway_family="NGFS Phase IV",
            selection_rationale="Evaluates Sri Lanka CEB Long-Term Generation Expansion Plan 70% renewable target.",
            source_citation="Network for Greening the Financial System (NGFS) Climate Scenarios (2023)",
            temperature_trajectory="1.5°C with limited overshoot",
        ),
    )


@pytest.fixture
def valid_time_horizons() -> tuple[TimeHorizon, ...]:
    return (
        TimeHorizon(
            kind="short_term",
            label="Short-term (2026–2030)",
            start_year=2026,
            end_year=2030,
            operational_context="EPC construction, commissioning, and initial commercial operation ramp-up.",
        ),
        TimeHorizon(
            kind="medium_term",
            label="Medium-term (2031–2045)",
            start_year=2031,
            end_year=2045,
            operational_context="Senior debt amortisation window and core commercial operation.",
        ),
        TimeHorizon(
            kind="long_term",
            label="Long-term (2046–2055)",
            start_year=2046,
            end_year=2055,
            operational_context="Post-debt equity tail, potential life-extension or repowering.",
        ),
    )


@pytest.fixture
def valid_drivers() -> tuple[ClimateRiskDriver, ...]:
    return (
        ClimateRiskDriver(
            risk_id="CR-PHYS-01",
            risk_type="physical_acute",
            title="Tropical cyclone wind gust and gust-induced blade loading",
            time_horizon="short_term",
            analysis_status="analyzed_present",
            hazard_description="Elevated 3-second gust velocities in Gulf of Mannar during northeast monsoon depressions.",
            evidence_basis="50-year ERA5 reanalysis and on-site met mast anemometer extreme value analysis.",
            mitigation_summary="Class S / IEC 61400-1 certified typhoon-resistant nacelle yaw and automated storm shutdown controls.",
            residual_severity="low",
            transmission_channels=(
                FinancialTransmissionItem(
                    channel="capital_cost",
                    description="IEC Class S design specification premium incorporated in EPC contract.",
                    modelled_impact="Included in base turbine supply line item ($142k/MW)",
                    already_modelled_in_cashflows=True,
                    wacc_adjustment_allowed=False,
                ),
            ),
        ),
        ClimateRiskDriver(
            risk_id="CR-TRANS-01",
            risk_type="transition_policy_legal",
            title="Grid curtailment risk under 70% national renewable expansion",
            time_horizon="medium_term",
            analysis_status="analyzed_present",
            hazard_description="System operator curtailment during minimum night demand conditions as solar/wind penetration increases.",
            evidence_basis="CEB LTGEP 2023-2042 dispatch modelling and transmission constraint studies.",
            mitigation_summary="20-year take-or-pay PPA deemed generation compensation clauses.",
            residual_severity="medium",
            transmission_channels=(
                FinancialTransmissionItem(
                    channel="outage_curtailment",
                    description="P50 energy assessment haircut for uncompensated curtailment allowance.",
                    modelled_impact="0.75% annual generation reduction",
                    already_modelled_in_cashflows=True,
                    wacc_adjustment_allowed=False,
                ),
            ),
        ),
        ClimateRiskDriver(
            risk_id="CR-PHYS-02",
            risk_type="physical_chronic",
            title="Coastal salinity and corrosion-induced accelerated degradation",
            time_horizon="long_term",
            analysis_status="missing_not_evaluated",
            hazard_description="Long-term exposure of substation switchgear and turbine towers to marine atmospheric salinity.",
            evidence_basis="Qualitative site inspection only; detailed ISO 9223 corrosivity category assessment pending.",
            mitigation_summary="C5-M protective coating specification proposed by balance of plant contractor.",
            residual_severity="undetermined",
            transmission_channels=(),
        ),
    )


def test_climate_risk_disclosure_positive_rendering(
    valid_perimeter: ClimateDisclosurePerimeter,
    valid_scenarios: tuple[ClimateScenario, ...],
    valid_time_horizons: tuple[TimeHorizon, ...],
    valid_drivers: tuple[ClimateRiskDriver, ...],
) -> None:
    context = ClimateRiskDisclosureContext(
        perimeter=valid_perimeter,
        scenarios=valid_scenarios,
        time_horizons=valid_time_horizons,
        drivers=valid_drivers,
    )

    assert context.missing_analyses_count == 1
    assert len(context.missing_analyses_drivers) == 1
    assert context.missing_analyses_drivers[0].risk_id == "CR-PHYS-02"

    partial_html = render_climate_risk_disclosure_partial(context)
    assert '<section class="climate-risk-disclosure">' in partial_html
    assert "DutchBay Wind Power Project" in partial_html
    assert "Sri Lanka (LK)" in partial_html
    assert "IPCC AR6 SSP2-4.5" in partial_html
    assert "Prohibited (No Double Count)" in partial_html
    assert "CR-PHYS-02" in partial_html
    assert MANDATORY_CLIMATE_DISCLOSURE_DISCLAIMER in partial_html

    standalone_html = render_climate_risk_disclosure_html(context)
    assert "<!DOCTYPE html>" in standalone_html
    assert (
        "<title>Climate-Related Risk Disclosure — DutchBay Wind Power Project</title>"
        in standalone_html
    )

    dumped = context.model_dump()
    assert dumped["perimeter"]["jurisdiction_iso"] == "LK"
    assert len(dumped["scenarios"]) == 2


def test_refuse_double_counting_parallel_wacc_markup() -> None:
    with pytest.raises(ValueError, match="Double-counting prohibited"):
        FinancialTransmissionItem(
            channel="operating_cost",
            description="Inspection and maintenance cost increase",
            already_modelled_in_cashflows=True,
            wacc_adjustment_allowed=True,
        )


def test_refuse_missing_analysis_with_resolved_severity() -> None:
    with pytest.raises(
        ValueError, match="missing analysis cannot claim resolved severity"
    ):
        ClimateRiskDriver(
            risk_id="CR-TEST-01",
            risk_type="physical_acute",
            title="Test unassessed cyclone hazard",
            time_horizon="short_term",
            analysis_status="missing_not_evaluated",
            hazard_description="Unstudied cyclone risk",
            evidence_basis="None",
            mitigation_summary="None",
            residual_severity="low",  # Invalid: missing cannot claim low
            transmission_channels=(),
        )


def test_refuse_missing_analysis_with_transmission_channels() -> None:
    with pytest.raises(
        ValueError,
        match="missing analysis cannot declare quantitative transmission channels",
    ):
        ClimateRiskDriver(
            risk_id="CR-TEST-02",
            risk_type="physical_chronic",
            title="Test unassessed flooding hazard",
            time_horizon="medium_term",
            analysis_status="missing_not_evaluated",
            hazard_description="Unstudied flood risk",
            evidence_basis="None",
            mitigation_summary="None",
            residual_severity="undetermined",
            transmission_channels=(
                FinancialTransmissionItem(
                    channel="capital_cost",
                    description="Estimated berm cost",
                    already_modelled_in_cashflows=False,
                ),
            ),
        )


@pytest.mark.parametrize(
    "prohibited_text",
    [
        "This project is IFRS S1 compliant based on technical studies.",
        "The risk analysis is IFRS S2 compliant under our model.",
        "All climate disclosures are third-party assured by an independent firm.",
        "We present an audited climate disclosure for lenders.",
    ],
)
def test_refuse_prohibited_compliance_or_assurance_claims(prohibited_text: str) -> None:
    with pytest.raises(
        ValueError, match="prohibited compliance or assurance assertion detected"
    ):
        ClimateRiskDriver(
            risk_id="CR-TEST-03",
            risk_type="transition_policy_legal",
            title="Policy compliance assessment",
            time_horizon="short_term",
            analysis_status="analyzed_present",
            hazard_description=prohibited_text,
            evidence_basis="Internal note",
            mitigation_summary="Routine review",
            residual_severity="low",
            transmission_channels=(),
        )


def test_refuse_altered_mandatory_disclaimer(
    valid_perimeter: ClimateDisclosurePerimeter,
    valid_scenarios: tuple[ClimateScenario, ...],
    valid_time_horizons: tuple[TimeHorizon, ...],
    valid_drivers: tuple[ClimateRiskDriver, ...],
) -> None:
    with pytest.raises(
        ValueError, match="MANDATORY_CLIMATE_DISCLOSURE_DISCLAIMER must not be altered"
    ):
        ClimateRiskDisclosureContext(
            perimeter=valid_perimeter,
            scenarios=valid_scenarios,
            time_horizons=valid_time_horizons,
            drivers=valid_drivers,
            disclaimer="Softer altered disclaimer without statutory caveats.",
        )


def test_refuse_unrationalized_universal_15c_40c_pair(
    valid_perimeter: ClimateDisclosurePerimeter,
    valid_time_horizons: tuple[TimeHorizon, ...],
    valid_drivers: tuple[ClimateRiskDriver, ...],
) -> None:
    generic_scenarios = (
        ClimateScenario(
            scenario_id="ssp1_19",
            name="1.5°C",
            pathway_family="Generic",
            selection_rationale="generic pair default assumption",
            source_citation="Generic text",
        ),
        ClimateScenario(
            scenario_id="ssp5_85",
            name="4.0°C",
            pathway_family="Generic",
            selection_rationale="generic pair default assumption",
            source_citation="Generic text",
        ),
    )
    with pytest.raises(
        ValueError, match="Universal hardcoded 1.5°C/4°C scenario pairs"
    ):
        ClimateRiskDisclosureContext(
            perimeter=valid_perimeter,
            scenarios=generic_scenarios,
            time_horizons=valid_time_horizons,
            drivers=valid_drivers,
        )


def test_refuse_invalid_time_horizon() -> None:
    with pytest.raises(ValueError, match="start_year 2035 exceeds end_year 2025"):
        TimeHorizon(
            kind="short_term",
            label="Inverted horizon",
            start_year=2035,
            end_year=2025,
            operational_context="Impossible timeline",
        )


def test_refuse_invalid_jurisdiction_iso() -> None:
    with pytest.raises(
        ValueError, match="jurisdiction_iso must be a 2-letter uppercase ISO code"
    ):
        ClimateDisclosurePerimeter(
            project_name="DutchBay",
            jurisdiction="Sri Lanka",
            jurisdiction_iso="lka",  # Not 2-letter uppercase
            reporting_boundary="Site",
            asset_lifespan_years=25,
        )


def test_frozen_immutability(
    valid_perimeter: ClimateDisclosurePerimeter,
    valid_scenarios: tuple[ClimateScenario, ...],
    valid_time_horizons: tuple[TimeHorizon, ...],
    valid_drivers: tuple[ClimateRiskDriver, ...],
) -> None:
    context = ClimateRiskDisclosureContext(
        perimeter=valid_perimeter,
        scenarios=valid_scenarios,
        time_horizons=valid_time_horizons,
        drivers=valid_drivers,
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        context.perimeter = object()  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        valid_drivers[0].residual_severity = "high"  # type: ignore[misc]
