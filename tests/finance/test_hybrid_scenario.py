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
    # D4.6: Financing_Terms.bind_downside now makes the bankable P90 bind the gearing (debt
    # sized to clear 1.30 DSCR even at P90 production, 0.8754 x CFADS). This SHRINKS debt
    # ~13.8% (gearing 0.4225 -> 0.3675), which DE-LEVERS this negatively-levered structure
    # (13.39% LKR debt >> ~2% project return): equity_irr -0.0612 -> -0.0272 (+339bps), LLCR
    # 1.302 -> 1.497, PLCR 1.348 -> 1.550. project_irr is unlevered (UNCHANGED); min_dscr
    # holds 1.30; total_cfads_usd is debt-independent (UNCHANGED). project_npv edges down
    # -89.78M -> -91.65M (the smaller debt slice raises the build-up WACC).
    # #529 (SOLAR-6/12): the financed solar P50 CF was re-baselined 0.179 -> 0.1685 (-5.9%)
    # on a FROZEN PVGIS TMY (hourly GHI/DNI/DHI + hourly Faiman temp/wind) — real GHI 1871
    # (vs the declared 2000) + hot-hour thermal. Less solar generation (78.4 -> 73.8 GWh)
    # lowers total CFADS 237.78M -> 235.66M (-0.9%), projIRR 0.01958 -> 0.01855 (-10bps),
    # equity_irr -0.0272 -> -0.0285, and NPV -91.65M -> -92.67M; min_dscr holds 1.30.
    assert kpis["project_irr"] == pytest.approx(0.01855071204306178, rel=1e-6)
    assert kpis["equity_irr"] == pytest.approx(-0.028493280998005632, rel=1e-6)  # #529
    assert kpis["project_npv"] == pytest.approx(
        -92672410.10213006, rel=1e-6
    )  # #529 solar TMY re-baseline
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=1e-6)
    assert kpis["total_cfads_usd"] == pytest.approx(235664760.1435344, rel=1e-6)


def test_hybrid_reports_per_technology_split() -> None:
    kpis = run_v14_pipeline(config=HYBRID, validation_mode="strict")["kpis"]
    cfg = load_scenario_config(HYBRID)
    gen, breakdown = build_multi_tech_from_run(kpis, cfg)
    assert gen is not None and breakdown is not None
    assert set(gen.technologies) == {"wind", "solar"}
    rows = {r.technology: r for r in breakdown}
    # wind 464.3 / 538.1 = 86.3% ; solar 73.8 (pvlib P50, #529 TMY) / 538.1 = 13.7%
    assert rows["wind"].share_of_aep_pct == pytest.approx(86.3, abs=0.2)
    assert rows["solar"].share_of_aep_pct == pytest.approx(13.7, abs=0.2)
    # wind 159.6 / 199.6 = 80% ; solar 40 / 199.6 = 20%
    assert rows["wind"].share_of_capex_pct == pytest.approx(80.0, abs=0.2)
    assert rows["solar"].share_of_capex_pct == pytest.approx(20.0, abs=0.2)


def test_hybrid_net_p90_is_model_derived() -> None:
    """The hybrid net_aep_p90 (#469 dolphin 4c) is reproducible from the solar model.

    Proves the frozen 471.0 GWh is wind 404.4 + the pvlib-modelled solar P90-1yr (not a
    hand-maintained placeholder). Gated on the [solar] extra. This P90 now BINDS the gearing
    (bind_downside true, D4.6 — it drives the financed KPIs pinned in the economics test
    above); here we only check the AEP arithmetic that feeds it.
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
