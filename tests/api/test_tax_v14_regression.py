"""
Regression tests for Tax Profile v14 Module

Verifies tax calculations against known expected values from
dutchbay_lendercase_2025Q4.yaml configuration.

Author: DutchBay Finance Team
Date: December 16, 2025
"""

import pytest
from omegaconf import OmegaConf

from finance.tax_profile_v14_hydra import (
    TaxProfile,
    build_tax_profile,
    calculate_tax_for_year,
    extract_tax_config_from_full_config,
)


@pytest.fixture
def lender_case_config():
    """Load scenarios/dutchbay_lendercase_2025Q4.yaml."""
    return OmegaConf.load("scenarios/dutchbay_lendercase_2025Q4.yaml")


class TestTaxProfileConstruction:
    """Test TaxProfile construction and validation."""

    def test_tax_profile_creation_basic(self, lender_case_config):
        """Test basic tax profile creation from config."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,  # 100M USD @ 300 LKR/USD
            project_life_years=20,
            config_source="test",
        )

        assert isinstance(profile, TaxProfile)
        assert profile.corporate_tax_rate == 0.3
        assert profile.tax_holiday_years == 12

    def test_tax_profile_lender_case_regression(self, lender_case_config):
        """Regression test: Lender case config produces expected profile."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=lender_case_config.capex.usd_total
            * lender_case_config.fx.start_lkr_per_usd,
            project_life_years=lender_case_config.returns.project_life_years,
            config_source="scenarios/dutchbay_lendercase_2025Q4.yaml",
        )

        # Regression pins from config
        assert profile.corporate_tax_rate == 0.3
        assert profile.tax_holiday_years == 12
        assert profile.tax_holiday_start_year == 1
        assert profile.depreciation_method == "straight_line"
        assert profile.loss_carryforward_years == 25
        assert profile.config_source == "scenarios/dutchbay_lendercase_2025Q4.yaml"

    def test_tax_profile_immutable(self, lender_case_config):
        """Test that TaxProfile is immutable (frozen)."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        # Should not be able to modify
        with pytest.raises(Exception):  # FrozenInstanceError or similar
            profile.corporate_tax_rate = 0.5


class TestTaxCalculations:
    """Test year-by-year tax calculations."""

    def test_tax_calculation_year_1_in_holiday(self, lender_case_config):
        """Year 1 should be in tax holiday (tax = 0)."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        # Year 1 (index 0) should be in holiday
        # Use CFADS > depreciation so it makes sense
        tax, dep = calculate_tax_for_year(
            profile,
            pretax_cfads_lkr=10_000_000_000,  # 10B LKR (much larger)
            interest_expense_lkr=1_000_000_000,  # 1B interest
            year_index=0,
        )

        # Tax should be 0 (in holiday)
        assert tax == pytest.approx(0.0), f"Year 1 tax should be 0, got {tax}"
        # Depreciation should be consistent
        assert dep > 0, f"Year 1 depreciation should be > 0, got {dep}"

    def test_tax_calculation_year_13_after_holiday(self, lender_case_config):
        """Year 13 should NOT be in holiday (tax > 0)."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        # Year 13 (index 12) should NOT be in 12-year holiday
        # holiday_end = 1 + 12 - 1 = 12, so year 13 is outside
        tax, dep = calculate_tax_for_year(
            profile,
            pretax_cfads_lkr=10_000_000_000,  # 10B LKR
            interest_expense_lkr=1_000_000_000,  # 1B interest
            year_index=12,
        )

        # Verify year 13 is NOT in holiday
        assert profile.is_in_tax_holiday(12) is False, "Year 13 should NOT be in holiday"
        
        # Tax should be > 0 (after holiday)
        assert tax > 0.0, f"Year 13 tax should be > 0, got {tax}"
        
        # Calculation: (10B - dep - 1B) * 0.3
        expected_tax = (10_000_000_000 - dep - 1_000_000_000) * 0.3
        assert tax == pytest.approx(expected_tax), f"Tax mismatch: {tax} vs {expected_tax}"

    def test_tax_calculation_depreciation_consistency(self, lender_case_config):
        """Depreciation should be consistent across years."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        # Get depreciation for multiple years
        _, dep_y1 = calculate_tax_for_year(profile, 10_000_000_000, 1_000_000_000, 0)
        _, dep_y2 = calculate_tax_for_year(profile, 10_000_000_000, 1_000_000_000, 1)
        _, dep_y13 = calculate_tax_for_year(profile, 10_000_000_000, 1_000_000_000, 12)

        # All should be equal (straight-line depreciation)
        assert dep_y1 == pytest.approx(dep_y2)
        assert dep_y1 == pytest.approx(dep_y13)

    def test_tax_calculation_interest_shield_enabled(self, lender_case_config):
        """Test interest shield is applied (reduces taxable income)."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        # Year 13 (after holiday) with large CFADS
        pretax_cfads = 10_000_000_000  # 10B
        interest = 1_000_000_000  # 1B

        tax, dep = calculate_tax_for_year(
            profile, pretax_cfads, interest, 12  # Year 13 (index 12)
        )

        # With interest shield: (10B - dep - 1B) * 0.3
        expected_with_shield = (pretax_cfads - dep - interest) * 0.3
        assert tax == pytest.approx(expected_with_shield), f"Tax mismatch: {tax} vs {expected_with_shield}"

        # Without interest shield: (10B - dep) * 0.3 (should be larger)
        expected_without_shield = (pretax_cfads - dep) * 0.3
        assert expected_without_shield > expected_with_shield
        assert tax < expected_without_shield


class TestTaxHolidayLogic:
    """Test tax holiday window calculation."""

    def test_is_in_tax_holiday_year_1(self, lender_case_config):
        """Year 1 should be in holiday."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        assert profile.is_in_tax_holiday(0) is True  # Year 1 (index 0)

    def test_is_in_tax_holiday_year_12(self, lender_case_config):
        """Year 12 should still be in holiday."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        assert profile.is_in_tax_holiday(11) is True  # Year 12 (index 11)

    def test_is_in_tax_holiday_year_13(self, lender_case_config):
        """Year 13 should NOT be in holiday (after 12-year holiday)."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        assert profile.is_in_tax_holiday(12) is False  # Year 13 (index 12)

    def test_is_in_tax_holiday_year_20(self, lender_case_config):
        """Year 20 should NOT be in holiday."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        assert profile.is_in_tax_holiday(19) is False  # Year 20 (index 19)


class TestConfigExtraction:
    """Test config extraction from full config."""

    def test_extract_tax_config_from_full_config(self, lender_case_config):
        """Test extracting tax section from full config."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)

        # Should have tax section
        assert "corporate_tax_rate" in tax_config
        assert "tax_holiday_years" in tax_config
        assert tax_config.corporate_tax_rate == 0.3
        assert tax_config.tax_holiday_years == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
