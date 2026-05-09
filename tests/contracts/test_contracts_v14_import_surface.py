from __future__ import annotations

from dataclasses import asdict

from analytics.contracts import ScenarioResult as PackageScenarioResult
from analytics.contracts_v14 import (
    CasperResult,
    DebtCovenantSnapshot,
    MonteCarloResult,
    ParameterRangeConfig,
    ScenarioResult,
    SensitivityRequest,
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
    assert casper.contract_version() == "v1.0"


def test_covenant_breach_tolerance_helper() -> None:
    assert check_covenant_breach_with_tolerance(1.29999, 1.30) is False
    assert check_covenant_breach_with_tolerance(1.295, 1.30) is True
    assert check_covenant_breach_with_tolerance(
        actual=4.0001,
        threshold=4.0,
        covenant_type="ceiling",
    ) is False
