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
# #738: the engine finances the LEVY-INCLUSIVE gross — pre-levy base + the PRUDENT
# import duties (0.69 share x 7.5% = $8.2593M capitalized). Debt sizes on this.
CAPEX_GROSS = CAPEX + 8_259_300.0


@pytest.fixture(scope="module")
def base_config():
    return load_scenario_config(SCENARIO)


def test_dual_dscr_autosolve_sizes_to_target(base_config):
    """The shipped lender scenario (debt_sizing: dual_dscr) is DSCR-bound at honest FX.

    At the corrected FX 333.79 (and the ERA5-fitted Weibull re-baseline that trims
    AEP ~2%, now also incl. the 2.0% pre-construction P50 over-prediction haircut)
    the USD O&M costs more in LKR and CFADS is lower, so the DSCR debt capacity
    falls BELOW the 70% gearing ceiling (it was gearing-bound under the stale 300 /
    declared Weibull). The auto-sizer therefore binds on the P50 DSCR (~0.578
    gearing after the P50 haircut; was ~0.590 pre-haircut), below the cap, and the
    sculpt floors min DSCR at the 1.30 target.
    """
    cfg = copy.deepcopy(base_config)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    # #737: the per-period series floors at the 1.30 target fee-inclusively; the
    # headline min_dscr is the CONSERVATIVE per-year fold (year 1 carries the orphaned
    # bridge service out of fee-netted CFADS) at ~1.286 (levy-inclusive per #738) —
    # reported honestly.
    assert res["min_dscr"] == pytest.approx(1.30, abs=0.01)
    assert res["debt_total"] == pytest.approx(
        0.355 * CAPEX_GROSS, rel=3e-3
    )  # DSCR-solved, below cap (PR-B UIP LKR rate + #737 fees + #738 levies de-lever)
    detail = res["dual_dscr"]
    assert detail is not None
    assert (
        0.30 < detail["solved_gearing"] < 0.70
    )  # DSCR-bound, strictly below the 0.70 cap
    assert detail["binding_constraint"] == "P50"  # DSCR-bound, not gearing-bound
    assert (
        detail["debt_p99"] >= res["debt_total"]
    )  # P99 capacity exceeds the P50 sizing


def test_opt_out_keeps_fixed_gearing(base_config):
    """Without the flag, debt stays fixed at capex * debt_ratio.

    At the corrected FX 333.79 (ERA5-fitted Weibull incl. the 2.0% P50 haircut, PR-A's levy
    removal, then PR-B's UIP LKR debt rate 13.39%) a fixed 70% gearing OVER-levers the deal
    badly: min DSCR collapses to ~0.48 (the costlier LKR tranche balloons debt service), a deep
    sub-covenant breach of the 1.30 target. This is exactly why the dual_dscr auto-sizer (the
    shipped default) sizes debt DOWN to ~0.45 — the fixed-gearing path and the auto-sizer no
    longer coincide (they did under the stale 300 / declared Weibull, which flattered CFADS).
    """
    cfg = copy.deepcopy(base_config)
    cfg["Financing_Terms"].pop("debt_sizing", None)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    # #738: the fixed ratio applies to the LEVY-INCLUSIVE gross the engine finances.
    assert res["debt_total"] == pytest.approx(0.70 * CAPEX_GROSS, rel=1e-3)
    assert res["dual_dscr"] is None
    assert res["min_dscr"] == pytest.approx(
        0.191, abs=0.01
    )  # 70% over-levers -> deep sub-covenant (#737 fees on the sticky, never-amortising
    # balance crush late-year coverage: 0.481 pre-fee -> 0.290; #738's larger grossed
    # debt + opex VAT push it further to ~0.256)


def test_lower_target_adds_leverage_when_dscr_bound(base_config):
    """When the deal is DSCR-bound, a lower DSCR target unlocks MORE leverage.

    At the corrected FX 333.79 the deal is DSCR-bound (below the 70% cap), so a
    lower 1.20 target sizes MORE debt (~0.625 gearing) than the 1.30 target
    (~0.578) — the opposite of the stale-300 gearing-bound case where both targets
    sat at the same capped debt.
    """
    cfg = copy.deepcopy(base_config)  # 1.30 target
    res_130 = plan_debt(annual_rows=build_annual_rows(cfg), config=cfg)

    cfg_120 = copy.deepcopy(base_config)
    cfg_120["Financing_Terms"]["target_dscr"] = 1.20
    res_120 = plan_debt(annual_rows=build_annual_rows(cfg_120), config=cfg_120)

    assert (
        res_120["debt_total"] > res_130["debt_total"] + 1_000_000
    )  # lower target -> more debt
    # With operating year 1 aligned to COD, the headline minimum meets each target.
    assert res_130["min_dscr"] == pytest.approx(1.30, abs=0.01)
    assert res_120["min_dscr"] == pytest.approx(1.20, abs=0.01)
