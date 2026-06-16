"""
Regression tests for Tax Profile v14 Module.

Verifies tax calculations against the CURRENT-regime config in
``dutchbay_lendercase_2025Q4.yaml`` (post-2025 SL: no renewable holiday, TLCF 6yr).
Holiday-window LOGIC is tested against an explicit-holiday override fixture, since
the live lender case carries no statutory holiday.

NOTE (_v14 tax-engine consolidation): this suite exercises
``finance.tax_profile_v14_hydra`` — a SEPARATE engine from the canonical
``finance.cashflow_v14_tax`` used by the lender pipeline. The hydra engine reads
``depreciation_years`` as a single life and does NOT honour the plant/civil split
(``plant_capex_share`` / ``plant_depreciation_years`` / ``civil_depreciation_years``).
De-duplicating the two engines is a follow-up Dolphin item.

Author: DutchBay Finance Team
Date: December 16, 2025 (refreshed Jun 2026 for the post-2025 regime)
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
    """Load scenarios/dutchbay_lendercase_2025Q4.yaml (current regime: no holiday)."""
    return OmegaConf.load("scenarios/dutchbay_lendercase_2025Q4.yaml")


@pytest.fixture
def holiday_config(lender_case_config):
    """Lender case overridden with an explicit 12-year holiday.

    The live regime grants no statutory holiday, so holiday-WINDOW logic is tested
    against this explicit-holiday config (e.g. a discretionary SDP-route grant),
    independent of the scenario's actual (zero) holiday.
    """
    return OmegaConf.merge(
        lender_case_config,
        {"tax": {"tax_holiday_years": 12, "tax_holiday_start_year": 1}},
    )


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
        assert profile.tax_holiday_years == 0  # current regime: no renewable holiday

    def test_tax_profile_lender_case_regression(self, lender_case_config):
        """Regression test: lender case config produces the current-regime profile."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)
        profile = build_tax_profile(
            config_tax=tax_config,
            capex_depreciable_lkr=lender_case_config.capex.usd_total
            * lender_case_config.fx.start_lkr_per_usd,
            project_life_years=lender_case_config.returns.project_life_years,
            config_source="scenarios/dutchbay_lendercase_2025Q4.yaml",
        )

        # Regression pins — current SL regime (post-2025): no holiday, TLCF 6yr.
        assert profile.corporate_tax_rate == 0.3
        assert profile.tax_holiday_years == 0
        assert profile.tax_holiday_start_year == 1
        assert profile.depreciation_method == "straight_line"
        assert profile.loss_carryforward_years == 6
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

        with pytest.raises(Exception):  # FrozenInstanceError or similar
            profile.corporate_tax_rate = 0.5


class TestTaxCalculations:
    """Year-by-year tax calculations (holiday window via the explicit holiday_config)."""

    def test_tax_calculation_year_1_in_holiday(self, holiday_config):
        """Year 1 should be in tax holiday (tax = 0)."""
        profile = build_tax_profile(
            config_tax=extract_tax_config_from_full_config(holiday_config),
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        tax, dep = calculate_tax_for_year(
            profile,
            pretax_cfads_lkr=10_000_000_000,
            interest_expense_lkr=1_000_000_000,
            year_index=0,
        )

        assert tax == pytest.approx(0.0), f"Year 1 tax should be 0 (in holiday), got {tax}"
        assert dep > 0, f"Year 1 depreciation should be > 0, got {dep}"

    def test_tax_calculation_year_13_after_holiday(self, holiday_config):
        """Year 13 should NOT be in holiday (tax > 0)."""
        profile = build_tax_profile(
            config_tax=extract_tax_config_from_full_config(holiday_config),
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        tax, dep = calculate_tax_for_year(
            profile,
            pretax_cfads_lkr=10_000_000_000,
            interest_expense_lkr=1_000_000_000,
            year_index=12,
        )

        assert profile.is_in_tax_holiday(12) is False, "Year 13 should NOT be in holiday"
        assert tax > 0.0, f"Year 13 tax should be > 0, got {tax}"
        expected_tax = (10_000_000_000 - dep - 1_000_000_000) * 0.3
        assert tax == pytest.approx(expected_tax), f"Tax mismatch: {tax} vs {expected_tax}"

    def test_tax_calculation_depreciation_consistency(self, lender_case_config):
        """Depreciation is constant within the write-off window, then zero.

        TODO(_v14-consolidation): the hydra engine reads ``depreciation_years`` as a
        single life and IGNORES the plant/civil split — so the schedule is flat for
        ``depreciation_years`` years, then zero. The canonical ``cashflow_v14_tax``
        engine applies the true 5yr-plant / 20yr-civil split.
        """
        profile = build_tax_profile(
            config_tax=extract_tax_config_from_full_config(lender_case_config),
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        _, dep_y1 = calculate_tax_for_year(profile, 10_000_000_000, 1_000_000_000, 0)
        _, dep_y2 = calculate_tax_for_year(profile, 10_000_000_000, 1_000_000_000, 1)
        _, dep_y13 = calculate_tax_for_year(profile, 10_000_000_000, 1_000_000_000, 12)

        # Constant within the depreciation window (years 1-5)...
        assert dep_y1 == pytest.approx(dep_y2)
        assert dep_y1 > 0.0
        # ...and fully written off by year 13 (5-year single life in the hydra engine).
        assert dep_y13 == pytest.approx(0.0)

    def test_tax_calculation_interest_shield_enabled(self, holiday_config):
        """Test interest shield is applied (reduces taxable income)."""
        profile = build_tax_profile(
            config_tax=extract_tax_config_from_full_config(holiday_config),
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

        pretax_cfads = 10_000_000_000
        interest = 1_000_000_000

        tax, dep = calculate_tax_for_year(profile, pretax_cfads, interest, 12)

        expected_with_shield = (pretax_cfads - dep - interest) * 0.3
        assert tax == pytest.approx(expected_with_shield), (
            f"Tax mismatch: {tax} vs {expected_with_shield}"
        )
        expected_without_shield = (pretax_cfads - dep) * 0.3
        assert expected_without_shield > expected_with_shield
        assert tax < expected_without_shield


class TestTaxHolidayLogic:
    """Tax-holiday window calculation (12-yr holiday via the explicit holiday_config)."""

    def _profile(self, cfg):
        return build_tax_profile(
            config_tax=extract_tax_config_from_full_config(cfg),
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="test",
        )

    def test_is_in_tax_holiday_year_1(self, holiday_config):
        """Year 1 should be in holiday."""
        assert self._profile(holiday_config).is_in_tax_holiday(0) is True

    def test_is_in_tax_holiday_year_12(self, holiday_config):
        """Year 12 should still be in holiday."""
        assert self._profile(holiday_config).is_in_tax_holiday(11) is True

    def test_is_in_tax_holiday_year_13(self, holiday_config):
        """Year 13 should NOT be in holiday (after a 12-year holiday)."""
        assert self._profile(holiday_config).is_in_tax_holiday(12) is False

    def test_is_in_tax_holiday_year_20(self, holiday_config):
        """Year 20 should NOT be in holiday."""
        assert self._profile(holiday_config).is_in_tax_holiday(19) is False

    def test_live_lender_case_has_no_holiday(self, lender_case_config):
        """Current regime: the live lender case carries NO statutory holiday."""
        profile = self._profile(lender_case_config)
        assert profile.tax_holiday_years == 0
        assert all(profile.is_in_tax_holiday(y) is False for y in range(20))


class TestConfigExtraction:
    """Test config extraction from full config."""

    def test_extract_tax_config_from_full_config(self, lender_case_config):
        """Test extracting tax section from full config."""
        tax_config = extract_tax_config_from_full_config(lender_case_config)

        assert "corporate_tax_rate" in tax_config
        assert "tax_holiday_years" in tax_config
        assert tax_config.corporate_tax_rate == 0.3
        assert tax_config.tax_holiday_years == 0  # current regime


class TestSDPPathwayOverride:
    """The SDP-pathway override (scenarios/overrides/sdp_pathway.yaml) models the
    incentivized ≤10-yr holiday route, vs the no-holiday base case (dual pathway)."""

    def test_sdp_override_yields_10yr_holiday_and_enhanced(self, lender_case_config):
        sdp = OmegaConf.merge(
            lender_case_config,
            OmegaConf.load("scenarios/overrides/sdp_pathway.yaml"),
        )
        profile = build_tax_profile(
            config_tax=extract_tax_config_from_full_config(sdp),
            capex_depreciable_lkr=100_000_000 * 300,
            project_life_years=20,
            config_source="sdp",
        )
        assert profile.tax_holiday_years == 10
        assert profile.is_in_tax_holiday(0) is True   # year 1 in holiday
        assert profile.is_in_tax_holiday(9) is True    # year 10 in holiday
        assert profile.is_in_tax_holiday(10) is False  # year 11 taxed
        assert profile.enhanced_allowance_applies is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
