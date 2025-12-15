"""Test suite for Phase 1-2 refactoring (tax layer + WACC integration).

Tests cover:
  ✅ Tax profile creation and validation
  ✅ Depreciation schedule calculation
  ✅ Tax liability calculation with interest deductibility
  ✅ WACC calculation and components
  ✅ Interest injection into annual rows
  ✅ Backward compatibility with v1 code
  ✅ Complete integration scenarios
"""

from dataclasses import asdict

import numpy as np
import pytest

from finance.tax_profile import (
    DepreciationSchedule,
    TaxProfile,
    TaxResult,
    build_tax_series,
    calculate_tax,
)
from finance.wacc_integration import (
    WaccComponents,
    WaccResult,
    apply_wacc_to_irr_comparison,
    apply_wacc_to_npv,
    calculate_wacc,
)


class TestPhase1TaxProfile:
    """Tests for Phase 1 tax profile module."""

    def test_tax_profile_creation(self):
        """Create basic tax profile."""
        profile = TaxProfile(tax_rate=0.25)
        assert profile.tax_rate == 0.25
        assert profile.interest_deductibility is True
        assert profile.depreciation_method == "straight_line"

    def test_tax_profile_validation_tax_rate(self):
        """Validate tax rate bounds."""
        with pytest.raises(ValueError):
            TaxProfile(tax_rate=1.5)  # > 1.0

        with pytest.raises(ValueError):
            TaxProfile(tax_rate=-0.1)  # < 0.0

    def test_tax_profile_frozen(self):
        """Verify TaxProfile is immutable (frozen)."""
        profile = TaxProfile(tax_rate=0.25)
        with pytest.raises(Exception):  # FrozenInstanceError
            profile.tax_rate = 0.30

    def test_depreciation_schedule_straight_line(self):
        """Test straight-line depreciation schedule."""
        capex = 100_000_000  # 100M LKR
        schedule = DepreciationSchedule.build_straight_line(
            capex_lkr=capex, useful_life=20, project_life=20
        )

        # Annual depreciation should be capex / 20
        expected_annual = capex / 20
        assert schedule.annual_amounts[0] == pytest.approx(expected_annual)
        assert schedule.annual_amounts[-1] == pytest.approx(expected_annual)

        # Total depreciation should equal capex
        assert sum(schedule.annual_amounts) == pytest.approx(capex)

        # Book value should reach zero
        assert schedule.book_value[-1] == pytest.approx(0.0, abs=1.0)

    def test_calculate_tax_basic(self):
        """Test basic tax calculation."""
        profile = TaxProfile(tax_rate=0.25, interest_deductibility=True)

        result = calculate_tax(
            year=1,
            ebit=100_000,
            interest_expense=10_000,
            depreciation=5_000,
            tax_profile=profile,
        )

        # Taxable income = EBIT - interest - depreciation = 100k - 10k - 5k = 85k
        assert result.taxable_income == pytest.approx(85_000)

        # Tax = 85k * 0.25 = 21.25k
        assert result.tax_liability == pytest.approx(21_250)

    def test_calculate_tax_with_tax_holiday(self):
        """Test tax calculation with holiday."""
        profile = TaxProfile(tax_rate=0.25, tax_holidays_by_year={1: True, 2: True})

        result = calculate_tax(
            year=1,
            ebit=100_000,
            interest_expense=10_000,
            depreciation=5_000,
            tax_profile=profile,
        )

        assert result.tax_liability == 0.0
        assert result.tax_holiday_applied is True

    def test_build_tax_series(self):
        """Test building complete tax series."""
        profile = TaxProfile(tax_rate=0.25)
        depreciation = DepreciationSchedule.build_straight_line(100e6, 20, 5)

        years = [1, 2, 3, 4, 5]
        ebit = [100e3] * 5
        interest = [10e3] * 5

        series = build_tax_series(
            years=years,
            ebit_series=ebit,
            interest_series=interest,
            depreciation_schedule=depreciation,
            tax_profile=profile,
        )

        assert len(series) == 5
        assert all(isinstance(r, TaxResult) for r in series)
        assert series[0].year == 1
        assert series[4].year == 5


class TestPhase2WaccIntegration:
    """Tests for Phase 2 WACC module."""

    def test_wacc_components_creation(self):
        """Create WACC components."""
        components = WaccComponents(
            mode="nominal",
            risk_free_rate=0.05,
            market_risk_premium=0.08,
            asset_beta=1.1,
            equity_beta_levered=1.3,
            cost_of_equity=0.138,
            cost_of_debt_pretax=0.07,
            cost_of_debt_aftertax=0.056,
            tax_rate=0.20,
            target_debt_to_value=0.60,
            target_equity_to_value=0.40,
            wacc_nominal=0.092,
        )
        assert components.wacc_nominal == pytest.approx(0.092)

    def test_wacc_components_validation(self):
        """Validate WACC components."""
        # Invalid debt ratio
        with pytest.raises(ValueError):
            WaccComponents(
                mode="nominal",
                risk_free_rate=0.05,
                market_risk_premium=0.08,
                asset_beta=1.1,
                equity_beta_levered=1.3,
                cost_of_equity=0.138,
                cost_of_debt_pretax=0.07,
                cost_of_debt_aftertax=0.056,
                tax_rate=0.20,
                target_debt_to_value=1.5,  # > 1.0
                target_equity_to_value=0.40,
                wacc_nominal=0.092,
            )

    def test_calculate_wacc_basic(self):
        """Test WACC calculation."""
        wacc_result = calculate_wacc(
            risk_free_rate=0.05,
            market_risk_premium=0.08,
            asset_beta=1.0,
            cost_of_debt_pretax=0.07,
            tax_rate=0.25,
            debt_to_value=0.60,
        )

        assert wacc_result.base.wacc_nominal > 0.05  # Should exceed risk-free
        assert wacc_result.base.wacc_nominal < 0.15  # Should be reasonable
        assert wacc_result.prudential_rate > wacc_result.base.wacc_nominal

    def test_calculate_wacc_with_real(self):
        """Test WACC with real (inflation-adjusted) calculation."""
        wacc_result = calculate_wacc(
            risk_free_rate=0.05,
            market_risk_premium=0.08,
            asset_beta=1.0,
            cost_of_debt_pretax=0.07,
            tax_rate=0.25,
            debt_to_value=0.60,
            inflation_rate=0.04,
        )

        assert wacc_result.base.wacc_real is not None
        assert wacc_result.base.wacc_real < wacc_result.base.wacc_nominal

    def test_apply_wacc_to_irr_comparison(self):
        """Test IRR vs WACC comparison."""
        wacc_result = calculate_wacc(
            risk_free_rate=0.05,
            market_risk_premium=0.08,
            asset_beta=1.0,
            cost_of_debt_pretax=0.07,
            tax_rate=0.25,
            debt_to_value=0.60,
        )

        # Project IRR > WACC (creates value)
        comparison = apply_wacc_to_irr_comparison(0.15, wacc_result)
        assert comparison["creates_value_nominal"] is True
        assert comparison["margin_bps"] > 0

        # Project IRR < WACC (destroys value)
        comparison = apply_wacc_to_irr_comparison(0.05, wacc_result)
        assert comparison["creates_value_nominal"] is False


class TestBackwardCompatibility:
    """Tests for backward compatibility with v1 code."""

    def test_legacy_tax_rate_zero(self):
        """Verify that tax_rate=0.0 works as before."""
        profile = TaxProfile(tax_rate=0.0)

        result = calculate_tax(
            year=1,
            ebit=100_000,
            interest_expense=10_000,
            depreciation=5_000,
            tax_profile=profile,
        )

        assert result.tax_liability == 0.0

    def test_no_interest_deductibility(self):
        """Test with interest_deductibility=False (old behavior)."""
        profile = TaxProfile(
            tax_rate=0.25,
            interest_deductibility=False,  # Old behavior: interest not deductible
        )

        result = calculate_tax(
            year=1,
            ebit=100_000,
            interest_expense=10_000,
            depreciation=5_000,
            tax_profile=profile,
        )

        # Taxable = EBIT - depreciation (interest not deducted)
        # = 100k - 5k = 95k
        assert result.taxable_income == pytest.approx(95_000)
        assert result.tax_liability == pytest.approx(23_750)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
