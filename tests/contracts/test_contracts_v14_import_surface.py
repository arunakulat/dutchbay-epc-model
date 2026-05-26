from __future__ import annotations

from dataclasses import asdict

from analytics.contracts import ScenarioResult as PackageScenarioResult
from analytics.contracts_v14 import (
    CasperResult,
    CashflowResult,
    DebtCovenantSnapshot,
    EquityPerformance,
    MonteCarloResult,
    ParameterRangeConfig,
    ScenarioResult,
    SensitivityRequest,
    SensitivitySuite,
    TrancheDebtProfile,
    WaccComponents,
    WaccResult,
    check_covenant_breach_with_tolerance,
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


def test_contracts_v14_dolphin_enrichment_fields_are_optional_and_serializable() -> None:
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


def test_covenant_breach_tolerance_helper() -> None:
    assert check_covenant_breach_with_tolerance(1.29999, 1.30) is False
    assert check_covenant_breach_with_tolerance(1.295, 1.30) is True
    assert check_covenant_breach_with_tolerance(
        actual=4.0001,
        threshold=4.0,
        covenant_type="ceiling",
    ) is False


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
