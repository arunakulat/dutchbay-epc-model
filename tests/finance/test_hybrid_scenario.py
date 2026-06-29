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
    # #469 (dolphin 2): the financed solar P50 CF was re-baselined 0.20 -> 0.179 — the
    # pvlib-MODELLED P50 (solar_resource.pv_producer, -10.5%) now bills the cashflow
    # instead of the prior declared 0.20. Less generation lowers CFADS 242.00M -> 237.78M
    # (-1.7%), projIRR 0.02162 -> 0.01958 (-20bps), equity_irr -0.0576 -> -0.0612, and
    # NPV -87.60M -> -89.78M; min_dscr stays 1.30 (debt sculpted to the target DSCR).
    # (Prior lineage: 5.9% FX-drift re-baseline -> UIP-implied LKR debt 13.39%, which took
    # NPV -74.74M -> -87.60M and equity_irr -0.0320 -> -0.0576.)
    assert kpis["project_irr"] == pytest.approx(0.019577905010579898, rel=1e-6)
    assert kpis["equity_irr"] == pytest.approx(-0.06115322930577494, rel=1e-6)
    assert kpis["project_npv"] == pytest.approx(
        -89777992.81676231, rel=1e-6
    )  # #469 solar P50
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=1e-6)
    assert kpis["total_cfads_usd"] == pytest.approx(237778073.29042047, rel=1e-6)


def test_hybrid_reports_per_technology_split() -> None:
    kpis = run_v14_pipeline(config=HYBRID, validation_mode="strict")["kpis"]
    cfg = load_scenario_config(HYBRID)
    gen, breakdown = build_multi_tech_from_run(kpis, cfg)
    assert gen is not None and breakdown is not None
    assert set(gen.technologies) == {"wind", "solar"}
    rows = {r.technology: r for r in breakdown}
    # wind 464.3 (post 2% haircut) / 542.7 = 85.6% ; solar 78.4 (pvlib P50) / 542.7 = 14.4%
    assert rows["wind"].share_of_aep_pct == pytest.approx(85.6, abs=0.2)
    assert rows["solar"].share_of_aep_pct == pytest.approx(14.4, abs=0.2)
    # wind 159.6 / 199.6 = 80% ; solar 40 / 199.6 = 20%
    assert rows["wind"].share_of_capex_pct == pytest.approx(80.0, abs=0.2)
    assert rows["solar"].share_of_capex_pct == pytest.approx(20.0, abs=0.2)


def test_hybrid_net_p90_is_model_derived() -> None:
    """The hybrid net_aep_p90 (#469 dolphin 4c) is reproducible from the solar model.

    Proves the frozen 475.1 GWh is wind 404.4 + the pvlib-modelled solar P90-1yr (not a
    hand-maintained placeholder). Gated on the [solar] extra. P90 is reporting-only here
    (bind_downside false), so this does not touch the pinned financed KPIs above.
    """
    pytest.importorskip("pvlib")
    import yaml

    from solar_resource.pv_producer import SolarResourceConfig, compute_solar_aep

    sc = yaml.safe_load(open(HYBRID))
    res = compute_solar_aep(SolarResourceConfig.from_scenario(sc), emit_exceedance=True)
    solar_p90 = res.exceedance.p90_1yr_gwh
    declared = sc["expected_results"]["net_aep_p90_gwh"]
    # net_aep_p90 == wind 404.4 + model solar P90-1yr, within reporting rounding.
    assert declared == pytest.approx(404.4 + solar_p90, abs=0.1)
