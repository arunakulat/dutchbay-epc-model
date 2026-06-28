"""Regression pin for the committed hybrid wind+solar scenario (M3b).

Asserts the live pipeline runs the 209.6 MW hybrid (159.6 MW wind + 50 MW solar)
end-to-end with per-tech generation flowing through the cashflow, and that the
multi-tech reporting splits the run by technology. KPIs are the engine's HONEST
output — value-destructive at these illustrative assumptions (projIRR < WACC).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.portfolio.generation_aggregator import build_multi_tech_from_run
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]
HYBRID = str(REPO_ROOT / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml")


def test_hybrid_scenario_runs_and_pins_economics() -> None:
    kpis = run_v14_pipeline(config=HYBRID, validation_mode="strict")["kpis"]
    # Honest engine output (per-tech wind 0.6% / solar 0.4% degradation through the
    # cashflow). Value-destructive: projIRR below the ~8% build-up WACC.
    # Re-baselined by the 5.9% FX-drift re-baseline (fx.annual_depr 0.03 -> 0.0589,
    # data-derived BIS 2005-2026 LKR depreciation) and a 2% pre-construction P50
    # over-prediction haircut on the wind resource (wind AEP 473.8 -> 464.3 GWh):
    # the steeper LKR slide plus lower wind energy erode the flat-LKR-tariff revenue
    # in USD terms, dropping projIRR and flipping equity_irr NEGATIVE (-2.09%).
    # projIRR/npv/cfads all shift with the FX drift and the AEP haircut.
    assert kpis["project_irr"] == pytest.approx(0.019756869718573305, rel=1e-6)
    assert kpis["equity_irr"] == pytest.approx(-0.02085129211592429, rel=1e-6)
    assert kpis["project_npv"] == pytest.approx(-77112608.1424778, rel=1e-6)  # 5.9% FX-drift + 2% AEP haircut
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=1e-6)
    assert kpis["total_cfads_usd"] == pytest.approx(238151680.98955458, rel=1e-6)


def test_hybrid_reports_per_technology_split() -> None:
    kpis = run_v14_pipeline(config=HYBRID, validation_mode="strict")["kpis"]
    cfg = load_scenario_config(HYBRID)
    gen, breakdown = build_multi_tech_from_run(kpis, cfg)
    assert gen is not None and breakdown is not None
    assert set(gen.technologies) == {"wind", "solar"}
    rows = {r.technology: r for r in breakdown}
    # wind 464.3 (post 2% haircut) / 551.9 = 84.1% ; solar 87.6 / 551.9 = 15.9%
    assert rows["wind"].share_of_aep_pct == pytest.approx(84.1, abs=0.2)
    assert rows["solar"].share_of_aep_pct == pytest.approx(15.9, abs=0.2)
    # wind 159.6 / 199.6 = 80% ; solar 40 / 199.6 = 20%
    assert rows["wind"].share_of_capex_pct == pytest.approx(80.0, abs=0.2)
    assert rows["solar"].share_of_capex_pct == pytest.approx(20.0, abs=0.2)
