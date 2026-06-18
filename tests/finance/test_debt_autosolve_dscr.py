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
CAPEX = 150_000_000.0


@pytest.fixture(scope="module")
def base_config():
    return load_scenario_config(SCENARIO)


def test_dual_dscr_autosolve_sizes_to_target(base_config):
    """The shipped lender scenario (debt_sizing: dual_dscr) sizes debt to ~1.30 DSCR."""
    cfg = copy.deepcopy(base_config)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    assert res["min_dscr"] == pytest.approx(1.30, abs=0.01)  # sized to the target
    assert res["debt_total"] < 0.70 * CAPEX  # resized below the gearing cap
    detail = res["dual_dscr"]
    assert detail is not None
    assert 0.40 < detail["solved_gearing"] < 0.70
    assert detail["binding_constraint"] in ("P50", "P99", "RATIO_CAP")
    assert detail["debt_p99"] >= 0.0


def test_opt_out_keeps_fixed_gearing(base_config):
    """Without the flag, debt stays fixed at capex * debt_ratio (the #176 sub-covenant case)."""
    cfg = copy.deepcopy(base_config)
    cfg["Financing_Terms"].pop("debt_sizing", None)
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)

    assert res["debt_total"] == pytest.approx(0.70 * CAPEX, rel=1e-3)  # fixed 70%
    assert res["dual_dscr"] is None
    assert res["min_dscr"] == pytest.approx(1.1625, abs=0.01)  # 70% gearing -> sub-covenant


def test_lower_target_allows_more_leverage(base_config):
    """A lower DSCR target leaves more debt (less de-leveraging) than the 1.30 target."""
    cfg = copy.deepcopy(base_config)  # 1.30 target
    res_130 = plan_debt(annual_rows=build_annual_rows(cfg), config=cfg)

    cfg_120 = copy.deepcopy(base_config)
    cfg_120["Financing_Terms"]["target_dscr"] = 1.20
    res_120 = plan_debt(annual_rows=build_annual_rows(cfg_120), config=cfg_120)

    assert res_120["debt_total"] > res_130["debt_total"]
    assert res_120["min_dscr"] >= 1.20 - 0.01
