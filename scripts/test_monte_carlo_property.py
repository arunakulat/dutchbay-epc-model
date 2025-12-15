#!/usr/bin/env python3
"""Property-based tests for Monte Carlo stability and bounds.

If Hypothesis is not installed, this module is skipped cleanly.
"""

import math

import pytest

try:
    from hypothesis import given
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - optional dependency
    pytest.skip(
        "Hypothesis not installed; skipping property-based tests.",
        allow_module_level=True,
    )

from dutchbay_finmodel.core import ModelConfig
from dutchbay_finmodel.monte_carlo import generate_mc_parameters, run_monte_carlo


@given(st.integers(min_value=10, max_value=300))
def test_generate_mc_parameters_bounds(n):
    cfg = ModelConfig()
    params = generate_mc_parameters(n, cfg, seed=123)

    assert len(params) == n
    assert (params["capacity_factor_p50"] >= 0.25).all()
    assert (params["capacity_factor_p50"] <= 0.55).all()
    assert (params["capex_usd_mn"] > 0.0).all()
    assert (params["fixed_opex_lkr_mn_year1"] > 0.0).all()


@given(st.integers(min_value=20, max_value=150))
def test_run_monte_carlo_outputs_sane(n):
    cfg = ModelConfig()
    results = run_monte_carlo(n, cfg, seed=999)

    # Shape
    assert len(results) == n

    # DSCR metrics are non-negative; IRR should not all be NaN / inf.
    assert (results["min_dscr"] >= 0.0).all()
    assert not results["equity_irr"].isnull().all()
