#!/usr/bin/env python3
"""Smoke tests for rebuilt Dutch Bay financial model."""

import numpy as np
from dutchbay_finmodel.core import (
    ModelConfig,
    build_financial_model,
    calculate_equity_irr,
    calculate_project_irr,
)


def test_capital_structure_sums():
    cfg = ModelConfig()
    _, _, _, cap = build_financial_model(cfg)
    total = cap["total_debt_lkr"] + cap["total_equity_lkr"]
    assert abs(total - cap["total_capex_lkr"]) < 1e-6


def test_signs_and_shapes():
    cfg = ModelConfig()
    df, proj_cf, eq_cf, cap = build_financial_model(cfg)

    assert proj_cf.shape[0] == cfg.economic_life_years + 1
    assert eq_cf.shape[0] == cfg.economic_life_years + 1
    assert (df["DSCR"] > 0).all()

    # Initial investments negative
    assert proj_cf[0] < 0
    assert eq_cf[0] < 0

    # Revenue declines slightly with degradation
    assert df["Revenue_LKR"].iloc[-1] < df["Revenue_LKR"].iloc[0]


def test_base_case_reasonable_returns():
    cfg = ModelConfig()
    eq_irr = calculate_equity_irr(cfg)
    prj_irr = calculate_project_irr(cfg)

    # Loose bands; these are sanity checks, not regulatory benchmarks
    assert -0.05 < prj_irr < 0.25
    assert -0.05 < eq_irr < 0.35
