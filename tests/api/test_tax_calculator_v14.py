#!/usr/bin/env python3
"""
Smoke + behaviour tests for dutchbay_v14chat.finance.v14.tax_calculator.

We cover:
- The free function `calculate_depreciation_schedule`
- The `TaxCalculatorV14` wrapper over config

We only assert simple invariants that are stable across refactors.
"""

from dutchbay_v14chat.finance.v14.tax_calculator import (
    calculate_depreciation_schedule,
    TaxCalculatorV14,
)


def test_calculate_depreciation_schedule_straight_line_basic():
    """
    Straight-line depreciation should:
    - Produce a list of length `operational_years`
    - Use `asset_value / years` for the first `years` entries
    - Use 0.0 for the remaining operational years
    """
    asset_value = 1_000.0
    years = 5
    operational_years = 20

    schedule = calculate_depreciation_schedule(
        asset_value=asset_value,
        method="straight_line",
        years=years,
        operational_years=operational_years,
    )

    assert isinstance(schedule, list)
    assert len(schedule) == operational_years

    expected_annual = asset_value / years
    # First `years` entries: straight-line amount
    for amt in schedule[:years]:
        assert amt == expected_annual

    # Remaining entries: zero
    for amt in schedule[years:]:
        assert amt == 0.0


def test_calculate_depreciation_schedule_unknown_method_returns_empty():
    """
    For unsupported methods, the helper should currently return an empty list.
    """
    schedule = calculate_depreciation_schedule(
        asset_value=1_000.0,
        method="declining_balance",  # not currently implemented
        years=10,
        operational_years=20,
    )
    assert schedule == []


def test_tax_calculator_defaults_from_config():
    """
    TaxCalculatorV14 should:
    - Default corporate_rate to 0.30 when not provided.
    - Use tax.depreciation_method='straight_line' and tax.depreciation_years=15
      when not overridden.
    """
    cfg = {
        "tax": {
            # intentionally leaving out corporate_tax_rate, depreciation_* keys
        }
    }

    calc = TaxCalculatorV14(cfg)
    assert calc.corporate_rate == 0.30

    asset_value = 1_500.0
    schedule = calc.calculate_depreciation(asset_value, operational_years=20)

    # With default years=15, we expect 20 entries, first 15 at asset/15, rest 0.
    assert len(schedule) == 20
    expected_annual = asset_value / 15
    for amt in schedule[:15]:
        assert amt == expected_annual
    for amt in schedule[15:]:
        assert amt == 0.0


def test_tax_calculator_respects_config_overrides():
    """
    TaxCalculatorV14 should read overrides from config['tax']:
    - corporate_tax_rate
    - depreciation_method
    - depreciation_years
    """
    cfg = {
        "tax": {
            "corporate_tax_rate": 0.24,
            "depreciation_method": "straight_line",
            "depreciation_years": 10,
        }
    }

    calc = TaxCalculatorV14(cfg)
    assert calc.corporate_rate == 0.24

    asset_value = 2_000.0
    schedule = calc.calculate_depreciation(asset_value, operational_years=15)

    # For years=10, operational_years=15:
    # - First 10 entries: asset/10
    # - Last 5 entries: 0.0
    assert len(schedule) == 15
    expected_annual = asset_value / 10
    for amt in schedule[:10]:
        assert amt == expected_annual
    for amt in schedule[10:]:
        assert amt == 0.0
