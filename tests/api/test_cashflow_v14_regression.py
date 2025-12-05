import copy

import pytest

from finance.cashflow_v14 import build_annual_cfads, build_annual_rows

BASE_CONFIG: dict = {
    "project": {
        "project_life_years": 5,
        "capacity_mw": 150.0,
        "capacity_factor_pct": 40.0,  # percent-style input, engine handles it
        "degradation_pct": 0.5,  # percent/year
        "grid_loss_pct": 2.0,  # percent
        "corporate_tax_rate_pct": 24.0,
    },
    "tariff": {
        "lkr_per_kwh": 20.30,
    },
    "opex": {
        "usd_per_year": 4_000_000.0,
    },
    "statutory": {
        # Use decimals, NOT 1.0/0.25 which mean 100%/25%
        "success_fee_pct": 0.01,  # 1%
        "env_surcharge_pct": 0.0025,  # 0.25%
        "social_levy_pct": 0.0025,  # 0.25%
    },
    "tax": {
        "depreciation_years": 20,
        "holiday_years": 5,
        "holiday_start_year": 1,
        "enhanced_capital_allowance_pct": 100.0,
    },
    "risk": {
        "haircut_pct": 10.0,  # 10% -> engine turns into 0.10
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
    Monotonic sanity: higher tariff -> higher *pretax* CFADS in each year.

    We test this on the engine's core cashflow (revenue - statutory - opex),
    which should be strictly increasing in tariff given the config.
    """
    base_cfg = copy.deepcopy(BASE_CONFIG)
    high_tariff_cfg = copy.deepcopy(BASE_CONFIG)
    high_tariff_cfg["tariff"]["lkr_per_kwh"] = 25.0  # strictly higher

    rows_base = build_annual_rows(base_cfg)
    rows_high = build_annual_rows(high_tariff_cfg)

    assert len(rows_base) == len(rows_high) > 0

    base_series = [row["pretax_cfads"] for row in rows_base]
    high_series = [row["pretax_cfads"] for row in rows_high]

    for a, b in zip(base_series, high_series):
        # Higher tariff should strictly increase pretax CFADS
        assert b > a
        assert b == pytest.approx(b, rel=1e-6)


def test_cfads_decreases_when_opex_increases() -> None:
    """
    Monotonic sanity: higher opex -> lower final CFADS in each year.

    Here we keep the higher-level overlay (tax holiday + haircut) in place
    and assert that higher opex still reduces the lender-facing CFADS stream.
    """
    base_cfg = copy.deepcopy(BASE_CONFIG)
    high_opex_cfg = copy.deepcopy(BASE_CONFIG)
    high_opex_cfg["opex"]["usd_per_year"] = 6_000_000.0  # strictly higher opex

    cfads_base = build_annual_cfads(base_cfg)
    cfads_high_opex = build_annual_cfads(high_opex_cfg)

    assert len(cfads_base) == len(cfads_high_opex) > 0

    for a, b in zip(cfads_base, cfads_high_opex):
        # b = CFADS with higher opex, should be strictly lower
        assert b < a
        assert b == pytest.approx(b, rel=1e-6)
