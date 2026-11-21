"""The Blue Whale wind scenario's Monte Carlo block (#1822).

Each band is re-derived here from the source the scenario names beside it, so a band that
drifts from its basis, or one with no basis, fails. The block must pass the engine's
pre-sampling checks (#1629 dry run, dead-key and base-inside-band checks), run through the
lender guards with the toy fallback off, and leave the deterministic result unchanged.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/blue_whale_wind_lot5b_2026.yaml"
YIELD_SUMMARY = ROOT / "docs/blue_whale/met_mast_transfer_summary.json"
CAPEX_SUMMARY = ROOT / "docs/blue_whale/capex_blend_summary.json"
Z975 = 1.959963984540054  # the engine reads a normal band's low/high as a 95% interval


def _cfg() -> dict[str, Any]:
    return yaml.safe_load(SCENARIO.read_text(encoding="utf-8"))


def _params(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["name"]: p for p in cfg["monte_carlo"]["parameters"]}


def test_the_block_is_lender_shaped() -> None:
    mc = _cfg()["monte_carlo"]
    assert mc["allow_toy_fallback"] is False
    assert mc["fixed_debt_stress"] is True
    assert {10, 90} <= set(mc["percentiles"])
    # Only the drivers with a declared band are swept; no correlation is declared.
    assert set(_params(_cfg())) == {
        "project.capacity_factor",
        "capex.usd_total",
        "opex.usd_per_year",
        "fx.start_lkr_per_usd",
    }
    assert "correlation" not in mc


def test_yield_band_is_the_lifetime_sigma_from_the_met_mast_summary() -> None:
    cfg = _cfg()
    band = _params(cfg)["project.capacity_factor"]
    sigma = json.loads(YIELD_SUMMARY.read_text())["uncertainty"]["sigma_life_pct"] / 100
    base = cfg["project"]["capacity_factor"]
    assert band["distribution"] == "normal"
    assert band["low"] == pytest.approx(base * (1 - Z975 * sigma), abs=5e-7)
    assert band["high"] == pytest.approx(base * (1 + Z975 * sigma), abs=5e-7)
    # The project CF is the wind block's (the only technology), so the engine's coupling
    # moves the per-technology CF with it.
    assert cfg["generation"]["technologies"]["wind"]["capacity_factor"] == base


def test_capex_band_is_the_blend_range_plus_the_held_b26_line() -> None:
    cfg = _cfg()
    band = _params(cfg)["capex.usd_total"]
    wind = cfg["generation"]["technologies"]["wind"]
    per_kw = json.loads(CAPEX_SUMMARY.read_text())["wind_usd_per_kw"]
    kw = wind["capacity_mw"] * 1000
    b26 = cfg["capex"]["usd_total"] - wind["capex_usd"]  # the 2.0M placeholder line
    assert b26 == pytest.approx(2_000_000)
    assert band["distribution"] == "triangular"
    assert band["low"] == pytest.approx(
        per_kw["low"]["all_in_usd_per_kw"] * kw + b26, abs=0.01
    )
    assert band["high"] == pytest.approx(
        per_kw["high"]["all_in_usd_per_kw"] * kw + b26, abs=0.01
    )
    # The blend's mode is the scenario's wind capex (rounded to the dollar there).
    assert per_kw["mode"]["all_in_usd_per_kw"] * kw == pytest.approx(
        wind["capex_usd"], abs=10
    )


def test_opex_band_is_the_3_to_4_percent_benchmark_plus_the_held_overhead_line() -> (
    None
):
    cfg = _cfg()
    band = _params(cfg)["opex.usd_per_year"]
    turbine_capex = cfg["generation"]["technologies"]["wind"]["capex_usd"]
    lines = {
        c["name"]: c["usd_per_year"]
        for c in cfg["opex"]["currency_split"]["components"]
    }
    held = cfg["opex"]["usd_per_year"] - lines["wind_om"]
    assert held == lines["insurance_land_spv"]
    assert band["distribution"] == "uniform"
    assert band["low"] == pytest.approx(0.03 * turbine_capex + held, abs=0.01)
    assert band["high"] == pytest.approx(0.04 * turbine_capex + held, abs=0.01)


def test_fx_band_is_the_declared_fx_uncertainty() -> None:
    cfg = _cfg()
    band = _params(cfg)["fx.start_lkr_per_usd"]
    spot, move = cfg["fx"]["start_lkr_per_usd"], cfg["fx"]["uncertainty_pct"]
    assert band["distribution"] == "uniform"
    assert band["low"] == pytest.approx(spot * (1 - move), abs=1e-4)
    assert band["high"] == pytest.approx(spot * (1 + move), abs=1e-4)


def test_engine_accepts_the_block_before_sampling() -> None:
    from analytics.mc.engine import MonteCarloEngine

    engine = MonteCarloEngine(_cfg())  # #1629 dry run and #1793 guard pass
    assert engine._dead_param_names == []
    assert engine._base_outside_bounds == []


def test_a_short_run_with_the_fallback_off_moves_every_irr() -> None:
    from analytics.mc.engine import run_monte_carlo_analysis

    result = run_monte_carlo_analysis(base_config=_cfg(), n_trials=24, seed=42)
    assert result.failed_iterations == 0
    assert result.metadata["toy_fallback_count"] == 0
    assert result.metadata["allow_toy_fallback"] is False
    assert not result.metadata.get("degenerate_sweep")
    for metric in ("project_irr", "equity_irr"):
        summary = result.summary[metric]
        assert summary["defined_count"] == 24
        assert summary["std"] > 0


def test_the_lender_guard_refuses_a_thin_tail(tmp_path: Path) -> None:
    from app.reports.capital_risk_emit import build_capital_risk_report_for_scenario

    with pytest.raises(ValueError, match="needs >= 1000 trials"):
        build_capital_risk_report_for_scenario(SCENARIO, tmp_path, n_trials=999)


def test_the_deterministic_result_ignores_the_block(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from analytics.evaluation_v14 import evaluate_with_overrides

    caplog.set_level(logging.CRITICAL)
    with_block = _cfg()
    without = copy.deepcopy(with_block)
    without.pop("monte_carlo")
    a = evaluate_with_overrides(raw_config=with_block, return_full_result=True)
    b = evaluate_with_overrides(raw_config=without, return_full_result=True)
    for part in ("kpis", "annual_rows", "debt_result", "equity_distribution"):
        assert a[part] == b[part], part
