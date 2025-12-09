"""
Unit Tests for DutchBay Cashflow v14 Tax Module (Refactored)
============================================================

Comprehensive test suite for TaxProfile, build_tax_profile(), and
calculate_tax_for_year(). Tests cover:

- TaxProfile validation and initialization
- Tax holiday logic
- Depreciation schedule construction
- Tax calculation with and without interest shield
- Edge cases (negative income, zero rate, missing depreciation)
- Full scenario integration

Run with:
  pytest tests/finance/test_cashflow_v14_tax_refactored.py -v

Author: DutchBay Finance Team
Date: December 9, 2025
"""

from __future__ import annotations

import pytest

from finance.cashflow_v14_tax import (
    TaxProfile,
    build_tax_profile,
    calculate_tax_for_year,
)


class TestTaxProfile:
    """Tests for TaxProfile dataclass and validation."""

    def test_tax_profile_initialization_valid(self) -> None:
        """Valid TaxProfile initializes without error."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[1000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
        )
        assert profile.corporate_tax_rate == 0.24
        assert len(profile.depreciation_schedule_lkr) == 25

    def test_tax_profile_is_frozen(self) -> None:
        """TaxProfile is frozen (immutable)."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[1000.0],
            tax_holiday_years=0,
            tax_holiday_start_year=1,
        )
        with pytest.raises(AttributeError):
            profile.corporate_tax_rate = 0.30  # type: ignore

    def test_tax_profile_validation_rate_too_high(self) -> None:
        """Corporate tax rate must not exceed 1.0."""
        with pytest.raises(ValueError, match="corporate_tax_rate"):
            TaxProfile(
                corporate_tax_rate=1.5,
                depreciation_schedule_lkr=[],
                tax_holiday_years=0,
                tax_holiday_start_year=1,
            )

    def test_tax_profile_validation_rate_negative(self) -> None:
        """Corporate tax rate must not be negative."""
        with pytest.raises(ValueError, match="corporate_tax_rate"):
            TaxProfile(
                corporate_tax_rate=-0.1,
                depreciation_schedule_lkr=[],
                tax_holiday_years=0,
                tax_holiday_start_year=1,
            )

    def test_tax_profile_validation_holiday_years_negative(self) -> None:
        """Tax holiday years must be >= 0."""
        with pytest.raises(ValueError, match="tax_holiday_years"):
            TaxProfile(
                corporate_tax_rate=0.24,
                depreciation_schedule_lkr=[],
                tax_holiday_years=-1,
                tax_holiday_start_year=1,
            )

    def test_tax_profile_validation_holiday_start_year_zero(self) -> None:
        """Tax holiday start year must be >= 1 (1-based)."""
        with pytest.raises(ValueError, match="tax_holiday_start_year"):
            TaxProfile(
                corporate_tax_rate=0.24,
                depreciation_schedule_lkr=[],
                tax_holiday_years=3,
                tax_holiday_start_year=0,
            )

    def test_is_in_tax_holiday_no_holiday(self) -> None:
        """When tax_holiday_years=0, no years are in holiday."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[1000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
        )
        for year_idx in [0, 1, 5, 10, 24]:
            assert not profile.is_in_tax_holiday(year_idx)

    def test_is_in_tax_holiday_years_1_to_3(self) -> None:
        """Years 0, 1, 2 (0-based) = years 1, 2, 3 (1-based) in holiday."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[1000.0] * 25,
            tax_holiday_years=3,
            tax_holiday_start_year=1,
        )
        assert profile.is_in_tax_holiday(0)  # year 1
        assert profile.is_in_tax_holiday(1)  # year 2
        assert profile.is_in_tax_holiday(2)  # year 3
        assert not profile.is_in_tax_holiday(3)  # year 4

    def test_is_in_tax_holiday_years_5_to_8(self) -> None:
        """Holiday from year 5 to 8 (1-based) = indices 4-7 (0-based)."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[1000.0] * 25,
            tax_holiday_years=4,
            tax_holiday_start_year=5,
        )
        assert not profile.is_in_tax_holiday(3)  # year 4
        assert profile.is_in_tax_holiday(4)  # year 5
        assert profile.is_in_tax_holiday(5)  # year 6
        assert profile.is_in_tax_holiday(6)  # year 7
        assert profile.is_in_tax_holiday(7)  # year 8
        assert not profile.is_in_tax_holiday(8)  # year 9


class TestBuildTaxProfile:
    """Tests for build_tax_profile factory function."""

    def test_depreciation_schedule_length_equals_project_life(self) -> None:
        """Schedule is padded/trimmed to match project_life_years."""
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=100_000_000.0,
            depreciation_years=20,
            enhanced_capital_allowance_pct=1.0,
            project_life_years=25,
        )
        assert len(profile.depreciation_schedule_lkr) == 25

    def test_depreciation_schedule_too_short_padded(self) -> None:
        """Short depreciation horizon is padded with zeros."""
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=100_000_000.0,
            depreciation_years=10,
            enhanced_capital_allowance_pct=1.0,
            project_life_years=25,
        )
        assert len(profile.depreciation_schedule_lkr) == 25
        # First 10 items are non-zero, rest are zero
        assert all(v > 0 for v in profile.depreciation_schedule_lkr[:10])
        assert all(v == 0.0 for v in profile.depreciation_schedule_lkr[10:])

    def test_depreciation_schedule_too_long_trimmed(self) -> None:
        """Long depreciation horizon is trimmed to project life."""
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=100_000_000.0,
            depreciation_years=30,
            enhanced_capital_allowance_pct=1.0,
            project_life_years=25,
        )
        assert len(profile.depreciation_schedule_lkr) == 25

    def test_depreciation_sum_respects_capex_and_enhancement(self) -> None:
        """Sum of depreciation = capex × enhancement factor."""
        capex = 100_000_000.0
        dep_years = 20
        enhancement = 1.2

        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=capex,
            depreciation_years=dep_years,
            enhanced_capital_allowance_pct=enhancement,
            project_life_years=25,
        )

        total_dep = sum(profile.depreciation_schedule_lkr[:dep_years])
        expected = capex * enhancement
        assert total_dep == pytest.approx(expected, rel=1e-9)

    def test_depreciation_zero_when_capex_none(self) -> None:
        """If capex_depreciable_lkr is None, all depreciation is zero."""
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=None,
            depreciation_years=20,
            enhanced_capital_allowance_pct=1.0,
            project_life_years=25,
        )
        assert all(d == 0.0 for d in profile.depreciation_schedule_lkr)

    def test_depreciation_zero_when_capex_negative(self) -> None:
        """If capex_depreciable_lkr <= 0, all depreciation is zero."""
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=-100.0,
            depreciation_years=20,
            enhanced_capital_allowance_pct=1.0,
            project_life_years=25,
        )
        assert all(d == 0.0 for d in profile.depreciation_schedule_lkr)

    def test_depreciation_zero_when_years_zero(self) -> None:
        """If depreciation_years <= 0, all depreciation is zero."""
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=100_000_000.0,
            depreciation_years=0,
            enhanced_capital_allowance_pct=1.0,
            project_life_years=25,
        )
        assert all(d == 0.0 for d in profile.depreciation_schedule_lkr)


class TestCalculateTaxForYear:
    """Tests for the core calculate_tax_for_year function."""

    def test_tax_during_holiday_is_zero(self) -> None:
        """During tax holiday, tax = 0 regardless of income."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[10_000_000.0] * 25,
            tax_holiday_years=3,
            tax_holiday_start_year=1,
        )

        tax, depr = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=100_000_000.0,  # Large income
            interest_expense_lkr=5_000_000.0,
            year_index=0,  # Year 1, in holiday
        )

        assert tax == pytest.approx(0.0)
        assert depr == pytest.approx(10_000_000.0)

    def test_tax_after_holiday_is_applied(self) -> None:
        """After tax holiday ends, tax is calculated normally."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[10_000_000.0] * 25,
            tax_holiday_years=2,
            tax_holiday_start_year=1,
        )

        pretax_cfads = 100_000_000.0
        depreciation = 10_000_000.0
        interest = 5_000_000.0

        # Year 3 (index 2), after holiday
        tax, depr = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=2,
        )

        expected_taxable = pretax_cfads - depreciation - interest
        expected_tax = expected_taxable * 0.24

        assert tax == pytest.approx(expected_tax)
        assert depr == pytest.approx(depreciation)

    def test_interest_shield_enabled_reduces_tax(self) -> None:
        """With interest shield enabled, interest reduces taxable income."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[10_000_000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
            apply_interest_shield=True,
        )

        pretax_cfads = 100_000_000.0
        depreciation = 10_000_000.0
        interest = 20_000_000.0

        tax_with_shield, _ = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=5,
        )

        expected = (pretax_cfads - depreciation - interest) * 0.24
        assert tax_with_shield == pytest.approx(expected)

    def test_interest_shield_disabled_ignores_interest(self) -> None:
        """With interest shield disabled, interest is ignored."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[10_000_000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
            apply_interest_shield=False,
        )

        pretax_cfads = 100_000_000.0
        depreciation = 10_000_000.0
        interest = 20_000_000.0

        tax_without_shield, _ = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=5,
        )

        expected = (pretax_cfads - depreciation) * 0.24
        assert tax_without_shield == pytest.approx(expected)

    def test_interest_shield_comparison(self) -> None:
        """Interest shield reduces tax compared to no shield."""
        profile_with = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[10_000_000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
            apply_interest_shield=True,
        )
        profile_without = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[10_000_000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
            apply_interest_shield=False,
        )

        pretax_cfads = 100_000_000.0
        interest = 20_000_000.0

        tax_with, _ = calculate_tax_for_year(
            profile=profile_with,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=5,
        )

        tax_without, _ = calculate_tax_for_year(
            profile=profile_without,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=5,
        )

        assert tax_with < tax_without
        assert tax_without - tax_with == pytest.approx(interest * 0.24)

    def test_negative_taxable_income_floors_to_zero(self) -> None:
        """Negative taxable income results in zero tax."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[50_000_000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
            apply_interest_shield=True,
        )

        pretax_cfads = 20_000_000.0  # Small income
        depreciation = 50_000_000.0  # Large depreciation
        interest = 10_000_000.0

        tax, depr = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=0,
        )

        # Would be negative: 20M - 50M - 10M = -40M, floored to 0
        assert tax == pytest.approx(0.0)
        assert depr == pytest.approx(depreciation)

    def test_tax_rate_zero_results_in_zero_tax(self) -> None:
        """If corporate tax rate is 0, tax is always 0."""
        profile = TaxProfile(
            corporate_tax_rate=0.0,
            depreciation_schedule_lkr=[10_000_000.0] * 25,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
        )

        tax, _ = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=100_000_000.0,
            interest_expense_lkr=5_000_000.0,
            year_index=5,
        )

        assert tax == pytest.approx(0.0)

    def test_depreciation_beyond_schedule_is_zero(self) -> None:
        """If year_index >= schedule length, depreciation is 0."""
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[10_000_000.0] * 10,  # Only 10 years
            tax_holiday_years=0,
            tax_holiday_start_year=1,
        )

        # Query year 15 (beyond schedule)
        tax, depr = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=100_000_000.0,
            interest_expense_lkr=0.0,
            year_index=15,
        )

        assert depr == pytest.approx(0.0)
        assert tax == pytest.approx(100_000_000.0 * 0.24)

    def test_depreciation_returned_correctly(self) -> None:
        """Depreciation returned matches schedule value."""
        schedule = [5_000_000.0, 4_500_000.0, 4_000_000.0] + [0.0] * 22
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=schedule,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
        )

        _, depr0 = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=50_000_000.0,
            interest_expense_lkr=0.0,
            year_index=0,
        )

        _, depr1 = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=50_000_000.0,
            interest_expense_lkr=0.0,
            year_index=1,
        )

        assert depr0 == pytest.approx(5_000_000.0)
        assert depr1 == pytest.approx(4_500_000.0)


class TestIntegrationScenarios:
    """Integration tests covering realistic scenarios."""

    def test_full_scenario_3year_holiday_20year_depreciation(self) -> None:
        """
        Realistic scenario: 3-year holiday, 20-year depreciation, 25-year project.
        - Years 1-3: tax = 0
        - Years 4-20: tax applied with depreciation
        - Years 21-25: tax applied without depreciation
        """
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=100_000_000.0,
            depreciation_years=20,
            enhanced_capital_allowance_pct=1.0,
            tax_holiday_years=3,
            tax_holiday_start_year=1,
            project_life_years=25,
        )

        annual_dep = 100_000_000.0 / 20  # 5M per year
        pretax_cfads = 50_000_000.0
        interest = 10_000_000.0

        # Year 1 (index 0): in holiday
        tax_y1, depr_y1 = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=0,
        )
        assert tax_y1 == pytest.approx(0.0)
        assert depr_y1 == pytest.approx(annual_dep)

        # Year 4 (index 3): after holiday, with depreciation
        tax_y4, depr_y4 = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=3,
        )
        taxable_y4 = pretax_cfads - annual_dep - interest
        expected_tax_y4 = max(0.0, taxable_y4) * 0.24
        assert tax_y4 == pytest.approx(expected_tax_y4)
        assert depr_y4 == pytest.approx(annual_dep)

        # Year 25 (index 24): depreciation exhausted
        tax_y25, depr_y25 = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=24,
        )
        assert depr_y25 == pytest.approx(0.0)  # No depreciation left
        taxable_y25 = pretax_cfads - interest  # No depreciation
        expected_tax_y25 = max(0.0, taxable_y25) * 0.24
        assert tax_y25 == pytest.approx(expected_tax_y25)

    def test_lender_case_strong_cfads_scenario(self) -> None:
        """
        Lender case: strong CFADS throughout, interest shield material.
        Verify tax is reasonable and interest shield is applied correctly.
        """
        profile = build_tax_profile(
            corporate_tax_rate=0.24,
            capex_depreciable_lkr=500_000_000.0,
            depreciation_years=20,
            enhanced_capital_allowance_pct=1.0,
            tax_holiday_years=0,
            tax_holiday_start_year=1,
            project_life_years=25,
        )

        # Strong operating performance
        pretax_cfads = 200_000_000.0
        interest = 50_000_000.0

        tax, depr = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=5,
        )

        # Check order of magnitude
        assert tax > 0.0
        assert tax < pretax_cfads  # Tax is less than income
        assert depr == pytest.approx(500_000_000.0 / 20)

    def test_stressed_scenario_low_cfads(self) -> None:
        """
        Stressed scenario: low CFADS, high interest, depreciation exhausted.
        Verify tax floors correctly at zero.
        """
        profile = TaxProfile(
            corporate_tax_rate=0.24,
            depreciation_schedule_lkr=[0.0] * 25,  # Depreciation exhausted
            tax_holiday_years=0,
            tax_holiday_start_year=1,
            apply_interest_shield=True,
        )

        pretax_cfads = 30_000_000.0  # Weak
        interest = 25_000_000.0  # Significant

        tax, _ = calculate_tax_for_year(
            profile=profile,
            pretax_cfads_lkr=pretax_cfads,
            interest_expense_lkr=interest,
            year_index=10,
        )

        # Taxable = 30M - 0 - 25M = 5M → tax = 1.2M
        expected = 5_000_000.0 * 0.24
        assert tax == pytest.approx(expected)
