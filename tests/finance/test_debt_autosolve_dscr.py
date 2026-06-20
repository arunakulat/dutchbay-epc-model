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
    """The shipped lender scenario (debt_sizing: dual_dscr) is now gearing-bound.

    The higher 15x10MW AEP lifts DSCR capacity above the 70% gearing ceiling, so
    the auto-sizer binds on RATIO_CAP at the cap rather than below it; the sculpt
    still floors min DSCR at the 1.30 target.
    """
    cfg = copy.deepcopy(base_config)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    assert res["min_dscr"] == pytest.approx(1.30, abs=0.01)  # sculpt floors at target
    assert res["debt_total"] == pytest.approx(0.70 * CAPEX, rel=1e-3)  # at the gearing cap
    detail = res["dual_dscr"]
    assert detail is not None
    assert 0.40 < detail["solved_gearing"] <= 0.70  # capped at 0.70
    assert detail["binding_constraint"] == "RATIO_CAP"  # gearing-bound, not DSCR-bound
    assert detail["debt_p99"] >= res["debt_total"]  # P99 capacity exceeds the cap


def test_opt_out_keeps_fixed_gearing(base_config):
    """Without the flag, debt stays fixed at capex * debt_ratio.

    At 70% gearing the higher 10MW AEP now clears the 1.30 floor (was a 1.16
    sub-covenant under the 23 x EN-171/6.5 base), so the fixed-gearing case and
    the dual-DSCR auto-sizer coincide.
    """
    cfg = copy.deepcopy(base_config)
    cfg["Financing_Terms"].pop("debt_sizing", None)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    assert res["debt_total"] == pytest.approx(0.70 * CAPEX, rel=1e-3)  # fixed 70%
    assert res["dual_dscr"] is None
    assert res["min_dscr"] == pytest.approx(1.30, abs=0.01)  # 70% gearing now clears 1.30


def test_lower_target_is_gearing_bound_at_the_cap(base_config):
    """When the deal is gearing-bound, a lower DSCR target adds no leverage.

    The 10MW AEP lifts DSCR capacity above the 70% ceiling, so both the 1.30 and
    1.20 targets sit at the same gearing-capped debt; the lower target only
    sculpts the repayment profile to a lower DSCR floor.
    """
    cfg = copy.deepcopy(base_config)  # 1.30 target
    res_130 = plan_debt(annual_rows=build_annual_rows(cfg), config=cfg)

    cfg_120 = copy.deepcopy(base_config)
    cfg_120["Financing_Terms"]["target_dscr"] = 1.20
    res_120 = plan_debt(annual_rows=build_annual_rows(cfg_120), config=cfg_120)

    assert res_120["debt_total"] == pytest.approx(res_130["debt_total"], rel=1e-3)
    assert res_130["min_dscr"] == pytest.approx(1.30, abs=0.01)
    assert res_120["min_dscr"] == pytest.approx(1.20, abs=0.01)  # lower DSCR floor
