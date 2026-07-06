from __future__ import annotations

from dataclasses import asdict

import pytest

from analytics.contracts import ScenarioResult as PackageScenarioResult
from analytics.contracts_v14 import (
    CashflowResult,
    CasperResult,
    DebtCovenantSnapshot,
    EquityPerformance,
    IrrBridgeComponent,
    MonteCarloResult,
    ParameterRangeConfig,
    ProjectEquityIrrBridge,
    ScenarioResult,
    SensitivityRequest,
    SensitivitySuite,
    TrancheDebtProfile,
    WaccComponents,
    WaccResult,
)


def test_contracts_v14_pipeline_surface_is_importable() -> None:
    wacc = WaccResult(
        base=WaccComponents(mode="capm", wacc_nominal=0.10),
        prudential_rate=0.11,
    )
    debt_profile = TrancheDebtProfile(
        construction_years=2,
        tenor_years=18,
        timeline_periods=20,
        total_debt=100.0,
        total_idc=5.0,
    )
    covenants = DebtCovenantSnapshot(
        dscr_min=1.35,
        dscr_threshold=1.30,
        years_below_threshold=0,
        first_breach_year=None,
        last_breach_year=None,
        balloon_remaining=0.0,
        balloon_flag=False,
        audit_status="PASS",
    )
    result = ScenarioResult(
        scenario_name="smoke",
        config_path="inline",
        project_npv=1.0,
        project_irr=0.12,
        dscr_series=[1.4],
        min_dscr=1.4,
        max_debt_usd=100.0,
        wacc=wacc,
        debt_profile=debt_profile,
        debt_covenants=covenants,
    )
    payload = asdict(result)
    assert payload["scenario_name"] == "smoke"
    assert payload["wacc"]["prudential_rate"] == 0.11
    assert result.model_dump()["project_irr"] == 0.12
    assert PackageScenarioResult is ScenarioResult


def test_contracts_v14_dolphin_enrichment_fields_are_optional_and_serializable() -> (
    None
):
    covenants = DebtCovenantSnapshot(
        dscr_min=1.35,
        dscr_threshold=1.30,
        years_below_threshold=0,
        first_breach_year=None,
        last_breach_year=None,
        balloon_remaining=0.0,
        balloon_flag=False,
        audit_status="PASS",
        llcr=1.55,
        plcr=1.70,
        llcr_threshold=1.40,
        plcr_threshold=1.45,
        fx_min=310.0,
        fx_max=365.0,
        fx_avg=337.5,
    )
    cashflow = CashflowResult(
        annual_rows=[{"year": 1, "cfads": 100.0}],
        metadata={"source": "test"},
    )
    equity = EquityPerformance(
        equity_irr=0.16,
        equity_npv=25.0,
        equity_multiple=1.8,
    )
    result = ScenarioResult(
        scenario_name="enriched",
        config_path="inline",
        project_npv=1.0,
        project_irr=0.12,
        dscr_series=[1.4],
        min_dscr=1.4,
        max_debt_usd=100.0,
        debt_covenants=covenants,
        wacc_is_real=True,
        cashflow=cashflow,
        equity_performance=equity,
    )

    payload = asdict(result)
    assert payload["wacc_is_real"] is True
    assert payload["cashflow"]["annual_rows"][0]["cfads"] == 100.0
    assert payload["equity_performance"]["equity_multiple"] == 1.8
    assert payload["debt_covenants"]["llcr"] == 1.55
    assert payload["debt_covenants"]["plcr_threshold"] == 1.45
    assert payload["debt_covenants"]["fx_avg"] == 337.5
    assert result.model_dump()["debt_covenants"]["fx_max"] == 365.0


def test_contracts_v14_sensitivity_and_mc_surface_is_importable() -> None:
    param = ParameterRangeConfig(
        variable_name="finance.capex_total_usd",
        base_value=200_000_000,
        low_pct=-10,
        high_pct=10,
    )
    request = SensitivityRequest(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        parameters=[param],
    )
    mc = MonteCarloResult(
        summary={"project_irr": {"mean": 0.12}},
        trials={"project_irr": [0.10, 0.12, 0.14]},
    )
    casper = CasperResult(
        scenario="smoke",
        baseline_kpis={"project_irr": 0.12},
        monte_carlo=mc,
    )
    assert request.metric == "project_irr"
    assert mc.trials["project_irr"][1] == 0.12
    # Resolved Sprint 18D, D.X+6: contract_version is now a class-level
    # frozen attribute (init=False), not a no-args method.
    assert casper.contract_version == "casper_result_v1"


def test_irr_bridge_contracts_are_importable_and_serializable() -> None:
    """Pin the #621 project→equity IRR bridge contract surface (CCCDIR, frozen)."""
    leg = IrrBridgeComponent(
        name="leverage",
        contribution=0.216,
        irr_after=0.275,
        detail="Smaller equity outlay.",
    )
    bridge = ProjectEquityIrrBridge(
        project_irr=0.058,
        equity_irr=0.030,
        total_uplift=-0.028,
        components=[leg],
        residual=-0.244,
        reconciled=True,
    )
    payload = asdict(bridge)
    assert payload["components"][0]["name"] == "leverage"
    assert payload["residual"] == -0.244
    assert bridge.model_dump()["reconciled"] is True
    assert bridge.currency == "USD"


def test_sensitivity_suite_audit_fields_are_optional_and_serializable() -> None:
    """Pin Sprint 18C ARCH-04 unification fields (issue #52)."""
    # Default construction — all new fields must be optional with defaults
    empty = SensitivitySuite()
    assert empty.base_kpis == {}
    assert empty.scenario_name is None
    assert empty.analysis_timestamp is None
    assert empty.metric == "project_irr"

    # Full construction — exercise every new field
    populated = SensitivitySuite(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        metric="project_irr",
        base_kpis={"project_irr": 0.124, "equity_irr": 0.165},
        scenario_name="dutchbay_lendercase_2025Q4",
        analysis_timestamp="2026-05-26T00:00:00Z",
    )
    assert populated.base_kpis["project_irr"] == 0.124
    assert populated.scenario_name == "dutchbay_lendercase_2025Q4"
    assert populated.analysis_timestamp == "2026-05-26T00:00:00Z"

    # MRM-02 audit trail — must round-trip through asdict + model_dump
    payload = asdict(populated)
    assert payload["base_kpis"]["equity_irr"] == 0.165
    assert payload["scenario_name"] == "dutchbay_lendercase_2025Q4"
    assert payload["analysis_timestamp"] == "2026-05-26T00:00:00Z"
    assert populated.model_dump()["base_kpis"]["project_irr"] == 0.124


def test_d3_grid_study_contracts_are_importable_and_serializable() -> None:
    """Pin the #874 D3 grid-study contract surface (frozen, advisory, CCCDIR-centralised).

    The reactive/power-flow/study result types must live ONLY in ``contracts_v14`` and be
    frozen, ``bankable=False`` advisories that round-trip through asdict / model_dump.
    """
    from analytics.contracts_v14 import (
        GridStrengthResult,
        GridStudyResult,
        PowerFlowResult,
        ReactiveCapabilityResult,
    )

    reactive = ReactiveCapabilityResult.from_screen(
        pf_required_min=-0.95,
        pf_required_max=0.95,
        mvar_required=52.5,
        mvar_available=40.0,
        pf_at_poc=0.97,
        governing_p_mw=159.6,
        governing_grid_v_pu=1.1,
    )
    # from_screen derives the shortfall + PQ-box verdict.
    assert reactive.mvar_shortfall == pytest.approx(12.5)
    assert reactive.inside_pq_box is False
    assert reactive.bankable is False

    power_flow = PowerFlowResult(
        converged=True,
        bus_voltages_pu={"GRID": 1.1, "POC": 1.08, "COLLECTOR": 1.06},
        poc_voltage_pu=1.08,
        poc_pf=0.97,
        governing_p_mw=159.6,
        governing_grid_v_pu=1.1,
    )
    assert power_flow.bankable is False

    strength = GridStrengthResult.from_screen(
        scr_min=3.5,
        fault_level_poc_min_mva=560.0,
        plant_rating_mva=160.0,
    )
    study = GridStudyResult(
        strength=strength,
        reactive=reactive,
        power_flow=power_flow,
        study_enabled=True,
        poc_bus_name="Puttalam 220kV",
    )

    # Frozen: assignment must raise FrozenInstanceError.
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        study.study_enabled = False  # type: ignore[misc]

    payload = asdict(study)
    assert payload["strength"]["scr"] == 3.5
    assert payload["reactive"]["mvar_shortfall"] == pytest.approx(12.5)
    assert payload["reactive"]["inside_pq_box"] is False
    assert payload["power_flow"]["bus_voltages_pu"]["POC"] == 1.08
    assert payload["poc_bus_name"] == "Puttalam 220kV"
    # model_dump recurses through the bundled sub-results.
    dumped = study.model_dump()
    assert dumped["study_enabled"] is True
    assert dumped["bankable"] is False
    assert dumped["reactive"]["pf_at_poc"] == 0.97
