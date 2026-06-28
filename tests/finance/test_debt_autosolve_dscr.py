"""Tests for the opt-in DSCR auto-sizer in the v14 debt engine (#180).

``Financing_Terms.debt_sizing: dual_dscr`` solves the gearing on the REAL schedule to hold
min DSCR at ``target_dscr`` (capped at ``debt_ratio``) and attaches the dual-DSCR (P50/P99)
capacity detail. Default (no flag) keeps the fixed ``capex * debt_ratio`` behaviour.
"""

from __future__ import annotations

import copy

import pytest

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt

SCENARIO = "scenarios/dutchbay_lendercase_2025Q4.yaml"
CAPEX = 159_600_000.0  # 15 x IEA-10MW re-model (was 150M at 23 x EN-171/6.5)


@pytest.fixture(scope="module")
def base_config():
    return load_scenario_config(SCENARIO)


def test_dual_dscr_autosolve_sizes_to_target(base_config):
    """The shipped lender scenario (debt_sizing: dual_dscr) is DSCR-bound at honest FX.

    At the corrected FX 333.79 (and the ERA5-fitted Weibull re-baseline that trims
    AEP ~2%) the USD O&M costs more in LKR and CFADS is lower, so the DSCR debt
    capacity falls BELOW the 70% gearing ceiling (it was gearing-bound under the
    stale 300 / declared Weibull). The auto-sizer therefore binds on the P50 DSCR
    (~0.590 gearing after the 5.9% FX-drift re-baseline; was ~0.628 at 3% drift),
    below the cap, and the sculpt floors min DSCR at the 1.30 target.
    """
    cfg = copy.deepcopy(base_config)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    assert res["min_dscr"] == pytest.approx(1.30, abs=0.01)  # sculpt floors at target
    assert res["debt_total"] == pytest.approx(0.590 * CAPEX, rel=3e-3)  # DSCR-solved, below cap
    detail = res["dual_dscr"]
    assert detail is not None
    assert 0.40 < detail["solved_gearing"] < 0.70  # DSCR-bound, strictly below the 0.70 cap
    assert detail["binding_constraint"] == "P50"  # DSCR-bound, not gearing-bound
    assert detail["debt_p99"] >= res["debt_total"]  # P99 capacity exceeds the P50 sizing


def test_opt_out_keeps_fixed_gearing(base_config):
    """Without the flag, debt stays fixed at capex * debt_ratio.

    At the corrected FX 333.79 (and ERA5-fitted Weibull) a fixed 70% gearing
    OVER-levers the deal: min DSCR falls to ~0.80 after the 5.9% FX-drift re-baseline
    (was ~1.17 at 3% drift), a deep sub-covenant breach of the 1.30 target. This is
    exactly why the dual_dscr auto-sizer (the shipped default) sizes debt DOWN to
    ~0.590 — the fixed-gearing path and the auto-sizer no longer coincide (they did
    under the stale 300 / declared Weibull, which flattered CFADS).
    """
    cfg = copy.deepcopy(base_config)
    cfg["Financing_Terms"].pop("debt_sizing", None)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    assert res["debt_total"] == pytest.approx(0.70 * CAPEX, rel=1e-3)  # fixed 70%
    assert res["dual_dscr"] is None
    assert res["min_dscr"] == pytest.approx(0.804, abs=0.01)  # 70% over-levers -> deep sub-covenant


def test_lower_target_adds_leverage_when_dscr_bound(base_config):
    """When the deal is DSCR-bound, a lower DSCR target unlocks MORE leverage.

    At the corrected FX 333.79 the deal is DSCR-bound (below the 70% cap), so a
    lower 1.20 target sizes MORE debt (~0.695 gearing) than the 1.30 target
    (~0.640) — the opposite of the stale-300 gearing-bound case where both targets
    sat at the same capped debt.
    """
    cfg = copy.deepcopy(base_config)  # 1.30 target
    res_130 = plan_debt(annual_rows=build_annual_rows(cfg), config=cfg)

    cfg_120 = copy.deepcopy(base_config)
    cfg_120["Financing_Terms"]["target_dscr"] = 1.20
    res_120 = plan_debt(annual_rows=build_annual_rows(cfg_120), config=cfg_120)

    assert res_120["debt_total"] > res_130["debt_total"] + 1_000_000  # lower target -> more debt
    assert res_130["min_dscr"] == pytest.approx(1.30, abs=0.01)
    assert res_120["min_dscr"] == pytest.approx(1.20, abs=0.01)  # lower DSCR floor
