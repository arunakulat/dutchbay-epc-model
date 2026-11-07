"""Regression pins for the Blue Whale Lot 5B scenario (v0.10, model 15.21.0).

The scenario is a screening skeleton on placeholder inputs, so these pins prove only that
the committed KPIs have not moved unnoticed. ``TEST-01`` pairs each pin with a
responsiveness guard: the year-1 generation revenue must equal the closed form
``(sum of capacity x CF x 8760) x tariff`` the engine is meant to compute, and the
project IRR must move with the wind capacity factor, the tariff, the solar + BESS unit's
CF and its BESS premium. A pipeline that returned the pinned numbers without deriving them
would fail those guards.

From v0.5 the solar + BESS unit is carried in the engine's ``solar`` and ``bess_1`` blocks
(``solar_resource.pv_bess_dispatch``). The engine's revenue, an implementation that
predates that mapping, must reproduce the hourly dispatcher's revenue: exactly in year 1
up to the YAML's rounding, and within the configured tolerance in every later year.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides

SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "blue_whale_hybrid_lot5b_2026.yaml"
)

CONF = Path(__file__).resolve().parents[2] / "conf" / "blue_whale_solar_bess.yaml"
SIZING = Path(__file__).resolve().parents[2] / "conf" / "blue_whale_pv_bess_sizing.yaml"
PRICING = (
    Path(__file__).resolve().parents[2] / "conf" / "blue_whale_pv_bess_pricing.yaml"
)
SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "run_blue_whale_solar_bess_v14.py"
)

# Pinned at 15.14.0 (v0.6: the unit sized and priced by PR 3's Monte Carlo, DC/AC 1.1 and
# 5 MW / 24 MWh). Before, at 15.13.0 (v0.5: DC/AC 1.2 and 30 MWh, placeholder capex):
# project IRR 0.03578223216261529, equity IRR 0.009208957605289392, min DSCR
# 0.8682259068634375. At 15.12.0 (v0.4): 0.03150801785651182, 0.005060003909760136,
# 0.8685883776324956. At 15.11.0 (v0.3): 0.027674815875491747, 0.0006314091936767685,
# 0.8688229918413363.
# Re-pinned at 15.16.0 for the PR 5 met-mast transfer (hybrid v0.7: wind CF 0.374256 ->
# 0.487560, tariff blend 24.786 -> 24.97218). Before, at 15.15.0 (v0.6): project IRR
# 0.042560941205600764, equity IRR 0.015846290954853348, min DSCR 0.8678660628624484.
# Re-pinned at 15.17.0 for PR 6 capex (hybrid v0.8: wind capex 12,350,000 -> 8,899,980,
# BESS capex 3,240,000 -> 3,377,760, both blended). Before, at 15.16.0 (v0.7): project IRR
# 0.06900278150431857, equity IRR 0.04331151885509987, min DSCR 0.8674143524654796.
# Re-pinned for #1398 (P2-F3-01 debt-service shortfall carried as sponsor cure in year 1,
# where min DSCR is 0.8679; before: equity IRR 0.06377186287573333).
# Re-pinned at 15.19.0 for the turbine's shadow on the PV (hybrid v0.9, input B33: solar CF
# 0.165096 -> 0.164864, tariff blend 24.97218 -> 24.97308). Before, at 15.18.0 after #1398
# (v0.8): project IRR 0.08734893167526492, equity IRR 0.06053321098433617, min DSCR
# 0.8678977848741305.
# Re-pinned at 15.21.0 for the PUCSL escalable O&M indexation (L-9, hybrid v0.10: the blended
# 4.596111 O&M part and the premium's 0.30 indexed at 3.21%/yr). Before, at 15.20.0 (v0.9):
# project IRR 0.08731517255077664, equity IRR 0.060488952949803165, min DSCR
# 0.8678177667918598 (year 1; unchanged).
PINS = {
    "project_irr": 0.09282901849371646,
    "equity_irr": 0.06792211828140893,
    "min_dscr": 0.8678177667918598,
}


def _kpis(overrides: Dict[str, Any] | None = None) -> Dict[str, float]:
    out = evaluate_with_overrides(str(SCENARIO), overrides=overrides or {})
    return {k: float(v) for k, v in out.items() if isinstance(v, (int, float))}


@pytest.fixture(scope="module")
def base() -> Dict[str, float]:
    return _kpis()


def test_blue_whale_kpi_pins(base: Dict[str, float]) -> None:
    for key, pinned in PINS.items():
        assert base[key] == pytest.approx(pinned, rel=1e-9, abs=1e-12), key


def test_year_one_generation_revenue_is_derived_from_the_wind_block() -> None:
    scen = yaml.safe_load(SCENARIO.read_text())
    techs = scen["generation"]["technologies"]
    full = evaluate_with_overrides(str(SCENARIO), overrides={}, return_full_result=True)
    assert isinstance(full, dict)
    row = full["annual_rows"][0]
    mwh = sum(
        t["capacity_mw"] * t["capacity_factor"] * 8760.0
        for name, t in techs.items()
        if name in ("wind", "solar")
    )
    assert row["generation_revenue_lkr"] == pytest.approx(
        mwh * 1000.0 * scen["tariff"]["lkr_per_kwh"], rel=1e-6
    )


def test_project_irr_moves_with_wind_cf_and_tariff(base: Dict[str, float]) -> None:
    scen = yaml.safe_load(SCENARIO.read_text())
    wind = scen["generation"]["technologies"]["wind"]
    solar = scen["generation"]["technologies"]["solar"]
    cf = wind["capacity_factor"] * 1.05
    project_cf = (
        wind["capacity_mw"] * cf + solar["capacity_mw"] * solar["capacity_factor"]
    ) / scen["project"]["capacity_mw"]
    higher_cf = _kpis(
        {
            "generation.technologies.wind.capacity_factor": cf,
            "project.capacity_factor": project_cf,
        }
    )
    assert higher_cf["project_irr"] > base["project_irr"]
    lower_tariff = _kpis({"tariff.lkr_per_kwh": scen["tariff"]["lkr_per_kwh"] * 0.9})
    assert lower_tariff["project_irr"] < base["project_irr"]


def test_project_irr_moves_with_the_solar_bess_unit(base: Dict[str, float]) -> None:
    scen = yaml.safe_load(SCENARIO.read_text())
    rev = scen["generation"]["technologies"]["bess_1"]["revenue"]
    lower_premium = _kpis(
        {
            "generation.technologies.bess_1.revenue.tariff_lkr_per_kwh": rev[
                "tariff_lkr_per_kwh"
            ]
            * 0.5
        }
    )
    assert lower_premium["project_irr"] < base["project_irr"]
    fewer_cycles = _kpis(
        {
            "generation.technologies.bess_1.revenue.cycles_per_year": rev[
                "cycles_per_year"
            ]
            * 0.8
        }
    )
    assert fewer_cycles["project_irr"] < base["project_irr"]


def test_project_npv_moves_with_the_unit_capex(base: Dict[str, float]) -> None:
    # v0.6 (PR 3) prices the unit from cited sources; the pinned KPIs must still move with
    # each capex line the sizing changed (TEST-01 responsiveness).
    scen = yaml.safe_load(SCENARIO.read_text())
    techs = scen["generation"]["technologies"]
    total = scen["capex"]["usd_total"]
    for tech in ("solar", "bess_1"):
        extra = techs[tech]["capex_usd"] * 0.2
        dearer = _kpis(
            {
                f"generation.technologies.{tech}.capex_usd": techs[tech]["capex_usd"]
                + extra,
                "capex.usd_total": total + extra,
            }
        )
        assert dearer["project_npv"] < base["project_npv"], tech
        assert dearer["project_irr"] < base["project_irr"], tech


def _om_index_rate(scen: Dict[str, Any]) -> float:
    """The yearly O&M index growth, in closed form from the scenario's inputs (L-9).

    Written out here, apart from ``finance.tariff_indexation``, so the engine answers to an
    oracle it does not share (TEST-01).
    """
    ix = scen["tariff"]["om_indexation"]
    assert ix["basis"] == "ccpi_fx_weighted"
    assert ix["lkr_usd_depreciation_pct"] == "relative_ppp"
    ccpi = ix["ccpi_inflation_pct"] / 100.0
    fx = (1.0 + ccpi) / (1.0 + ix["usd_inflation_pct"] / 100.0) - 1.0
    return ix["ccpi_weight"] * ccpi + ix["lkr_usd_weight"] * fx


def _indexed_dispatcher_revenue(out: Dict[str, Any], scen: Dict[str, Any]) -> list:
    """The hourly dispatcher's revenue with the Annex 2 escalable O&M parts indexed.

    The dispatcher's flat revenue per year is wind energy x 25.73 + unit export x 20.72 +
    priority export x 29.38. Each kWh earns ``escalable x (index - 1)`` more, with the
    Annex 2 escalable parts (wind 4.93, ground solar 2.72, and the priority rate's
    3.02 = 2.72 / 0.90, so 0.30 on the premium) and ``index = (1 + g) ** (year - 1)``.
    """
    g = _om_index_rate(scen)
    flat = out["engine"]["dispatcher_revenue_lkr"]
    indexed = []
    for year, (rev, step) in enumerate(
        zip(flat, out["degradation_path"], strict=True), start=1
    ):
        assert step["year"] == year
        wind_kwh = (rev - step["revenue_lkr"]) / 25.73
        unit_kwh = step["unit_export_mwh"] * 1000.0
        priority_kwh = step["priority_export_mwh"] * 1000.0
        uplift = (1.0 + g) ** (year - 1) - 1.0
        indexed.append(
            rev + uplift * (wind_kwh * 4.93 + unit_kwh * 2.72 + priority_kwh * 0.30)
        )
    return indexed


def test_engine_revenue_equals_the_dispatcher() -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    spec = importlib.util.spec_from_file_location("blue_whale_solar_bess_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    # From v0.6 the scenario carries PR 3's recommended size and the matched inverter's
    # efficiency; PR 2's dispatcher is run at that size.
    conf = yaml.safe_load(CONF.read_text())
    rec = yaml.safe_load(SIZING.read_text())["recommendation"]
    inverter = yaml.safe_load(PRICING.read_text())["inverter"]
    conf["array"]["dc_ac_ratio"] = rec["dc_ac_ratio"]
    conf["bess"]["energy_mwh"] = rec["bess_energy_mwh"]
    conf["pv_yield"]["resource_solar"]["inverter_eff_nom"] = inverter[
        "european_efficiency"
    ]
    out = cli.run(conf)
    # The dispatcher prices at the flat Annex 2 rates; L-9 indexes their escalable O&M
    # parts (wind 4.93, solar 2.72, priority premium 3.02 - 2.72 = 0.30) yearly.
    dispatcher = _indexed_dispatcher_revenue(out, yaml.safe_load(SCENARIO.read_text()))
    full = evaluate_with_overrides(str(SCENARIO), overrides={}, return_full_result=True)
    assert isinstance(full, dict)
    rows = full["annual_rows"]
    assert len(rows) == len(dispatcher) == 20
    engine = [r["generation_revenue_lkr"] + r["bess_revenue_lkr"] for r in rows]
    # Year 1: the only difference is the YAML's rounding of CF, cycles and tariff.
    assert engine[0] == pytest.approx(dispatcher[0], rel=1e-4)
    tol = conf["engine"]["later_year_revenue_tolerance_pct"] / 100.0
    for year, (e, d) in enumerate(zip(engine, dispatcher, strict=True), start=1):
        assert e == pytest.approx(d, rel=tol), year
    # The priority premium stops after its 15-year term, in both.
    assert rows[14]["bess_revenue_lkr"] > 0 and rows[15]["bess_revenue_lkr"] == 0
