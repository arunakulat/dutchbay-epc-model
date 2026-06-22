#!/usr/bin/env python
"""Tests for the stress_tests_v14 engine.

Covers the public surface of ``analytics.stress_tests_v14``:

- ``StressScenario`` enum membership/values.
- ``StressTestEngine`` base-metric initialisation (NPV/IRR via finance.irr, R7).
- The three stressor helpers (rate shock with clamping, market downturn,
  inflation stress with Fisher-equation rate adjustment).
- ``run_scenario`` for each scenario family plus ``run_all_scenarios``.
- ``StressResult.to_dict`` / ``export_to_json`` JSON serialisation (CLI-03).

All metrics are recomputed independently from ``finance.irr`` so the assertions
are deterministic.  Two former defects are now pinned as regressions (both fixed
in #308): COMBINED_SEVERE once dropped its downturn component (it now compounds a
60% downturn + 6% inflation + 500bps shock), and VaR/CVaR were placeholders
rather than real loss measures (``var_95`` is now ``max(0, base_npv -
stressed_npv)``). There is no xfail — the defects are closed.

Context:
    Coverage backfill for analytics.stress_tests_v14 (previously ~0%).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.stress_tests_v14 import (
    StressResult,
    StressScenario,
    StressTestEngine,
)
from finance.irr import irr, npv

REPO_ROOT = Path(__file__).resolve().parents[2]

# A simple, well-behaved annual cash flow profile: -100 outlay then 30/yr x5.
# NPV at 8% is positive and the IRR brackets cleanly (~15.2%).
BASE_CFS = [-100.0] + [30.0] * 5
BASE_RATE = 0.08


@pytest.fixture
def engine() -> StressTestEngine:
    return StressTestEngine(BASE_CFS, BASE_RATE)


# ---------------------------------------------------------------------------
# Enum surface
# ---------------------------------------------------------------------------


def test_scenario_enum_complete() -> None:
    """All ten documented scenarios are present with stable string values."""
    values = {s.value for s in StressScenario}
    assert len(list(StressScenario)) == 10
    assert StressScenario.RATE_SHOCK_UP_2PCT.value == "rate_shock_up_2pct"
    assert StressScenario.MARKET_DOWNTURN_60PCT.value == "market_down_60pct"
    assert StressScenario.COMBINED_SEVERE.value == "combined_severe"
    assert "inflation_4pct" in values


# ---------------------------------------------------------------------------
# Construction / base metrics (R7: finance.irr singleton)
# ---------------------------------------------------------------------------


def test_base_metrics_match_finance_irr(engine: StressTestEngine) -> None:
    assert engine.base_npv == pytest.approx(npv(BASE_RATE, BASE_CFS))
    expected_irr = irr(BASE_CFS)
    assert expected_irr is not None
    # base_irr is expressed in percent, finance.irr returns a decimal.
    assert engine.base_irr == pytest.approx(expected_irr * 100)
    assert engine.base_irr == pytest.approx(15.238237, abs=1e-4)


def test_time_periods_default() -> None:
    eng = StressTestEngine(BASE_CFS, BASE_RATE)
    assert eng.time_periods == 30
    eng2 = StressTestEngine(BASE_CFS, BASE_RATE, time_periods=25)
    assert eng2.time_periods == 25


def test_irr_none_falls_back_to_zero() -> None:
    """When IRR cannot be solved (no sign change), base_irr is coerced to 0.0."""
    all_positive = [10.0, 20.0, 30.0]
    eng = StressTestEngine(all_positive, BASE_RATE)
    # finance.irr cannot bracket a root with no sign change -> None.
    assert irr(all_positive) is None
    assert eng.base_irr == 0.0
    # NPV is still well-defined and non-zero for these flows.
    assert eng.base_npv == pytest.approx(npv(BASE_RATE, all_positive))
    assert eng.base_npv > 0


# ---------------------------------------------------------------------------
# apply_interest_rate_shock
# ---------------------------------------------------------------------------


def test_rate_shock_basis_points(engine: StressTestEngine) -> None:
    # +200 bps == +2.0% added to the 8% base => 10%.
    assert engine.apply_interest_rate_shock(200) == pytest.approx(0.10)
    # -200 bps => 6%.
    assert engine.apply_interest_rate_shock(-200) == pytest.approx(0.06)


def test_rate_shock_clamped_low(engine: StressTestEngine) -> None:
    """A large negative shock is floored at 0.1% (0.001)."""
    assert engine.apply_interest_rate_shock(-100000) == pytest.approx(0.001)


def test_rate_shock_clamped_high(engine: StressTestEngine) -> None:
    """A large positive shock is capped at 50% (0.5)."""
    assert engine.apply_interest_rate_shock(1_000_000) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# apply_market_downturn
# ---------------------------------------------------------------------------


def test_market_downturn_scales_all_flows(engine: StressTestEngine) -> None:
    out = engine.apply_market_downturn(0.20)
    assert out == [pytest.approx(cf * 0.80) for cf in BASE_CFS]
    # Original list is not mutated.
    assert engine.base_cash_flows == BASE_CFS


def test_market_downturn_zero_is_identity(engine: StressTestEngine) -> None:
    assert engine.apply_market_downturn(0.0) == BASE_CFS


# ---------------------------------------------------------------------------
# apply_inflation_stress
# ---------------------------------------------------------------------------


def test_inflation_stress_cf_and_rate(engine: StressTestEngine) -> None:
    cfs, rate = engine.apply_inflation_stress(0.04)
    # CF erosion factor is (1 - inflation*0.3).
    assert cfs == [pytest.approx(cf * (1 - 0.04 * 0.3)) for cf in BASE_CFS]
    # Fisher: discount rate += inflation.
    assert rate == pytest.approx(BASE_RATE + 0.04)


# ---------------------------------------------------------------------------
# run_scenario - single scenarios
# ---------------------------------------------------------------------------


def test_run_scenario_returns_result(engine: StressTestEngine) -> None:
    res = engine.run_scenario(StressScenario.MARKET_DOWNTURN_20PCT)
    assert isinstance(res, StressResult)
    assert res.scenario == "market_down_20pct"
    assert res.base_npv_usd == pytest.approx(engine.base_npv)
    # break_even_point is always None in the current implementation.
    assert res.break_even_point is None


def test_rate_shock_up_lowers_npv(engine: StressTestEngine) -> None:
    res = engine.run_scenario(StressScenario.RATE_SHOCK_UP_2PCT)
    expected = npv(engine.apply_interest_rate_shock(200), BASE_CFS)
    assert res.stressed_npv_usd == pytest.approx(expected)
    assert res.stressed_npv_usd < engine.base_npv
    assert res.npv_change_usd == pytest.approx(res.stressed_npv_usd - engine.base_npv)


def test_rate_shock_down_raises_npv(engine: StressTestEngine) -> None:
    res = engine.run_scenario(StressScenario.RATE_SHOCK_DOWN_2PCT)
    assert res.stressed_npv_usd > engine.base_npv
    assert res.npv_change_usd > 0


def test_market_downturn_severity_monotonic(engine: StressTestEngine) -> None:
    """Deeper downturns yield strictly lower stressed NPV."""
    d20 = engine.run_scenario(StressScenario.MARKET_DOWNTURN_20PCT).stressed_npv_usd
    d40 = engine.run_scenario(StressScenario.MARKET_DOWNTURN_40PCT).stressed_npv_usd
    d60 = engine.run_scenario(StressScenario.MARKET_DOWNTURN_60PCT).stressed_npv_usd
    assert d60 < d40 < d20 < engine.base_npv


def test_inflation_severity_monotonic(engine: StressTestEngine) -> None:
    i2 = engine.run_scenario(StressScenario.INFLATION_2PCT).stressed_npv_usd
    i4 = engine.run_scenario(StressScenario.INFLATION_4PCT).stressed_npv_usd
    i6 = engine.run_scenario(StressScenario.INFLATION_6PCT).stressed_npv_usd
    assert i6 < i4 < i2 < engine.base_npv


def test_npv_change_pct_formula(engine: StressTestEngine) -> None:
    res = engine.run_scenario(StressScenario.MARKET_DOWNTURN_40PCT)
    expected_pct = (res.npv_change_usd / abs(engine.base_npv)) * 100
    assert res.npv_change_pct == pytest.approx(expected_pct)


def test_irr_change_bps_formula(engine: StressTestEngine) -> None:
    res = engine.run_scenario(StressScenario.MARKET_DOWNTURN_20PCT)
    # A pure scaling of cash flows leaves the IRR unchanged, so the bps
    # delta is ~0.  More importantly the formula is (stressed-base)*100.
    assert res.irr_change_bps == pytest.approx(
        (res.stressed_irr_pct - res.base_irr_pct) * 100
    )
    assert res.irr_change_bps == pytest.approx(0.0, abs=1e-6)


def test_npv_change_pct_zero_base_guard() -> None:
    """A zero base NPV avoids a division error and reports 0%."""
    eng = StressTestEngine([0.0, 0.0, 0.0], BASE_RATE)
    res = eng.run_scenario(StressScenario.MARKET_DOWNTURN_20PCT)
    assert eng.base_npv == pytest.approx(0.0)
    assert res.npv_change_pct == 0


# ---------------------------------------------------------------------------
# VaR / CVaR - downside loss vs base under each stress
# ---------------------------------------------------------------------------


def test_var_is_a_real_loss_not_a_flat_npv_fraction(engine: StressTestEngine) -> None:
    """var_95 is the downside LOSS vs base, not a fixed 5% slice of NPV.

    Regression: var_95 used to be stressed_npv*0.05 (a flat fraction). It is now
    max(0, base_npv - stressed_npv) -- a non-negative stress loss -- and cvar_95
    keeps the conventional ~1.25x tail multiplier on it.
    """
    res = engine.run_scenario(StressScenario.RATE_SHOCK_UP_5PCT)
    expected_loss = max(0.0, engine.base_npv - res.stressed_npv_usd)
    assert res.var_95_usd == pytest.approx(expected_loss)
    assert res.var_95_usd > 0.0  # a rate shock erodes a profitable base NPV
    assert res.var_95_usd != pytest.approx(res.stressed_npv_usd * 0.05)
    assert res.cvar_95_usd == pytest.approx(res.var_95_usd * 1.25)


def test_var_is_zero_for_accretive_stress(engine: StressTestEngine) -> None:
    """A stress that *raises* NPV (a rate cut) yields zero downside loss."""
    res = engine.run_scenario(StressScenario.RATE_SHOCK_DOWN_2PCT)
    assert res.stressed_npv_usd >= engine.base_npv
    assert res.var_95_usd == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# COMBINED_SEVERE - compounds the worst of each single stress
# ---------------------------------------------------------------------------


def test_combined_severe_compounds_downturn_and_inflation(
    engine: StressTestEngine,
) -> None:
    """COMBINED_SEVERE applies a 60% downturn THEN 6% inflation erosion.

    Regression: the old code overwrote the downturned series with
    inflation-on-base, dropping the downturn. The cash flows are now
    base * 0.40 * (1 - 0.06*0.3) and the rate carries inflation (+6%) + 500bps.
    """
    res = engine.run_scenario(StressScenario.COMBINED_SEVERE)
    expected_cfs = [cf * 0.40 * (1 - 0.06 * 0.3) for cf in engine.base_cash_flows]
    expected_rate = min(0.5, engine.base_discount_rate + 0.06 + 0.05)
    assert res.stressed_npv_usd == pytest.approx(npv(expected_rate, expected_cfs))


def test_combined_severe_strictly_worse_than_singles(
    engine: StressTestEngine,
) -> None:
    """The compounded combined scenario dominates every single stressor."""
    combined = engine.run_scenario(StressScenario.COMBINED_SEVERE).stressed_npv_usd
    worst_single = min(
        engine.run_scenario(s).stressed_npv_usd
        for s in StressScenario
        if s is not StressScenario.COMBINED_SEVERE
    )
    assert combined <= worst_single


# ---------------------------------------------------------------------------
# run_all_scenarios
# ---------------------------------------------------------------------------


def test_run_all_scenarios_covers_every_enum(engine: StressTestEngine) -> None:
    results = engine.run_all_scenarios()
    assert len(results) == 10
    assert {r.scenario for r in results} == {s.value for s in StressScenario}
    assert all(isinstance(r, StressResult) for r in results)


# ---------------------------------------------------------------------------
# Serialisation (CLI-03)
# ---------------------------------------------------------------------------


def test_to_dict_round_trips(engine: StressTestEngine) -> None:
    res = engine.run_scenario(StressScenario.INFLATION_2PCT)
    d = res.to_dict()
    assert d["scenario"] == "inflation_2pct"
    assert set(d) == {
        "scenario",
        "base_npv_usd",
        "stressed_npv_usd",
        "npv_change_usd",
        "npv_change_pct",
        "base_irr_pct",
        "stressed_irr_pct",
        "irr_change_bps",
        "var_95_usd",
        "cvar_95_usd",
        "break_even_point",
    }
    # asdict yields JSON-native types.
    assert json.loads(json.dumps(d)) == d


def test_export_to_json_structure(engine: StressTestEngine) -> None:
    results = engine.run_all_scenarios()
    payload = json.loads(engine.export_to_json(results))
    assert set(payload) == {"base_metrics", "stress_results"}
    base = payload["base_metrics"]
    assert base["npv_usd"] == pytest.approx(engine.base_npv)
    assert base["irr_pct"] == pytest.approx(engine.base_irr)
    assert base["discount_rate"] == pytest.approx(BASE_RATE)
    assert len(payload["stress_results"]) == 10
