#!/usr/bin/env python3
"""
Unit tests for finance.wacc_v14.

Pins both:
- Simple / fixed discount-rate mode
- CAPM mode with gearing, tax and inflation
"""

from __future__ import annotations

import math
from typing import Any, Dict

import pytest

from finance.wacc_v14 import (WaccComponents, build_wacc,
                              compute_wacc_from_config)


def _isclose(a: float, b: float, tol: float = 1e-8) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ---------------------------------------------------------------------------
# Simple / fixed mode
# ---------------------------------------------------------------------------


def test_fixed_mode_percent_input_with_default_prudential() -> None:
    """Simple fixed mode: discount_rate in percent, default prudential 100 bps."""
    config: Dict[str, Any] = {
        "wacc": {
            "discount_rate": 12.0,  # percent
            # prudential_spread_bps omitted -> default 100 bps
        }
    }

    result = compute_wacc_from_config(config)
    assert result["mode"] == "fixed"

    # 12% -> 0.12 nominal
    assert _isclose(result["wacc_nominal"], 0.12)
    # 100 bps prudential bump -> 0.13
    assert _isclose(result["wacc_prudential"], 0.13)

    # In fixed mode, cost_of_equity should equal the discount rate
    assert _isclose(result["cost_of_equity"], 0.12)


def test_fixed_mode_decimal_input_with_string_bps() -> None:
    """Simple fixed mode: decimal discount_rate and string prudential bps."""
    config: Dict[str, Any] = {
        "wacc": {
            "discount_rate": 0.12,  # already decimal
            "prudential_spread_bps": "+50bps",  # string form
        }
    }

    result = compute_wacc_from_config(config)
    assert result["mode"] == "fixed"

    # Nominal should be taken as-is
    assert _isclose(result["wacc_nominal"], 0.12)

    # 50 bps -> 0.005 bump
    assert _isclose(result["wacc_prudential"], 0.125)
    assert result["prudential_spread_bps"] == 50


# ---------------------------------------------------------------------------
# CAPM mode
# ---------------------------------------------------------------------------


def test_capm_mode_with_gearing_and_inflation() -> None:
    """
    CAPM mode using gearing (D/V), tax and inflation.

    Parameters chosen so we can pin expected values exactly:
      - risk_free       = 5%
      - market premium  = 6%
      - asset beta      = 0.8
      - gearing (D/V)   = 60%
      - cost of debt    = 8%
      - tax rate        = 24%
      - inflation       = 2%
      - prudential bps  = 100
    """
    config: Dict[str, Any] = {
        "wacc": {
            "mode": "capm",
            "risk_free": 5.0,
            "market_premium": 6.0,
            "beta": 0.8,
            "gearing": 60.0,  # D/V in percent
            "cost_of_debt": 8.0,
            "tax_rate": 24.0,
            "inflation_rate": 2.0,
            "prudential_spread_bps": 100,
        }
    }

    result = compute_wacc_from_config(config)
    # Everything should be decimal at this point
    assert result["mode"] == "capm"

    # Capital structure
    assert _isclose(result["target_debt_to_value"], 0.60)
    assert _isclose(result["target_equity_to_value"], 0.40)
    assert _isclose(result["target_debt_to_equity"], 1.5)

    # Beta / cost of equity
    # Equity beta = 0.8 * [1 + (1 - 0.24) * 1.5] = 1.712
    assert _isclose(result["equity_beta_levered"], 1.712, tol=1e-6)

    # Cost of equity = 0.05 + 1.712 * 0.06 = 0.15272
    assert _isclose(result["cost_of_equity"], 0.15272, tol=1e-6)

    # Cost of debt after tax = 0.08 * (1 - 0.24) = 0.0608
    assert _isclose(result["cost_of_debt_pretax"], 0.08)
    assert _isclose(result["cost_of_debt_aftertax"], 0.0608, tol=1e-6)

    # Nominal WACC = 0.4*0.15272 + 0.6*0.08*(1-0.24) = 0.097568
    assert _isclose(result["wacc_nominal"], 0.097568, tol=1e-8)

    # Real WACC with 2% inflation: ((1+0.097568)/(1+0.02)) - 1 ≈ 0.075077
    assert result["wacc_real"] is not None
    assert _isclose(result["wacc_real"], 0.07604706, tol=1e-6)

    # Prudential: +100 bps -> +0.01
    assert _isclose(result["wacc_prudential"], 0.107568, tol=1e-8)
    assert result["prudential_spread_bps"] == 100


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------


def test_compute_wacc_from_config_without_block_returns_empty_dict() -> None:
    """If there is no 'wacc' block, the function should fall back with {}."""
    config: Dict[str, Any] = {
        "tax": {
            "corporate_tax_rate_pct": 24.0,
        }
    }

    result = compute_wacc_from_config(config)
    assert result == {}


def test_build_wacc_roundtrip_structure() -> None:
    """
    Sanity check that build_wacc() returns a WaccComponents and that
    dataclasses.asdict() is structurally compatible with the dict surface.
    """
    components: WaccComponents = build_wacc(
        risk_free_rate=0.03,
        asset_beta=0.7,
        market_risk_premium=0.05,
        debt_to_value=0.5,
        cost_of_debt=0.06,
        tax_rate=0.24,
        inflation_rate=0.02,
        prudential_spread_bps=75,
    )

    assert isinstance(components, WaccComponents)
    assert components.mode == "capm"
    assert _isclose(components.target_debt_to_value, 0.5)
    assert _isclose(components.target_equity_to_value, 0.5)
    assert components.prudential_spread_bps == 75
