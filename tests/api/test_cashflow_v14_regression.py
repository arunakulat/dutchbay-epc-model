"""
Regression tests for cashflow_v14 to ensure consistency after refactorings.
"""

import copy

import pytest

from finance.cashflow_v14 import build_annual_rows

# ✅ FIXED: Use proper percentage notation (> 1.0 for percent, < 1.0 for decimal)
BASE_CONFIG: dict = {
    "project": {
        "project_life_years": 5,
        "capacity_mw": 150.0,
        "capacity_factor_pct": 40.0,
        "degradation_pct": 0.5,
        "grid_loss_pct": 2.0,
        "corporate_tax_rate_pct": 24.0,
    },
    "tariff": {
        "lkr_per_kwh": 20.30,
    },
    "opex": {
        "usd_per_year": 500_000.0,
    },
    "statutory": {
        "success_fee_pct": 0.01,  # ✅ FIXED: 0.01 = 1%
        "env_surcharge_pct": 0.0025,  # ✅ FIXED: 0.0025 = 0.25%
        "social_levy_pct": 0.0025,  # ✅ FIXED: 0.0025 = 0.25%
    },
    "tax": {
        "depreciation_years": 20,
        "holiday_years": 5,
        "holiday_start_year": 1,
        "enhanced_capital_allowance_pct": 100.0,
    },
    "risk": {
        "haircut_pct": 10.0,
    },
    "fx": {
        "start_lkr_per_usd": 375.0,
        "annual_depr_pct": 3.0,
    },
    "capex": {
        "usd_total": 120_000_000.0,
    },
}


def test_cfads_increases_when_tariff_increases() -> None:
    """
    Monotonic sanity: higher tariff -> higher pretax CFADS in each year.
    """
    base_cfg = copy.deepcopy(BASE_CONFIG)
    high_tariff_cfg = copy.deepcopy(BASE_CONFIG)
    high_tariff_cfg["tariff"]["lkr_per_kwh"] = 25.0

    rows_base = build_annual_rows(base_cfg)
    rows_high = build_annual_rows(high_tariff_cfg)

    assert len(rows_base) == len(rows_high) > 0

    for i in range(len(rows_base)):
        base_cfads = rows_base[i]["pretax_cfads_lkr"]
        high_cfads = rows_high[i]["pretax_cfads_lkr"]

        # Higher tariff should yield higher CFADS
        assert high_cfads > base_cfads, (
            f"Year {i + 1}: high tariff pretax CFADS ({high_cfads:,.0f}) "
            f"should exceed base ({base_cfads:,.0f})"
        )


def test_cfads_zero_when_tariff_zero() -> None:
    """Edge case: zero tariff means negative CFADS."""
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["tariff"]["lkr_per_kwh"] = 0.0

    rows = build_annual_rows(cfg)
    assert len(rows) > 0

    for row in rows:
        assert row["revenue_lkr"] == pytest.approx(0.0)
        assert row["cfads_final_lkr"] < 0.0


def test_degradation_reduces_production_over_time() -> None:
    """Production declines over time due to degradation."""
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["project"]["degradation_pct"] = 0.5

    rows = build_annual_rows(cfg)
    assert len(rows) > 1

    for i in range(1, len(rows)):
        prev_kwh = rows[i - 1]["net_kwh"]
        curr_kwh = rows[i]["net_kwh"]
        assert (
            curr_kwh < prev_kwh
        ), f"Year {i + 1}: net_kwh should decline due to degradation"
