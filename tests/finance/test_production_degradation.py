"""Tests for Wind Turbine Performance Degradation.

Validates degradation calculations against industry research:
- Staffell & Green (2014): UK wind farms
- NREL (2019): US modern turbines
- Kim et al. (2025): Performance quantification
- IEC 61400-12-1:2022: Monitoring standards

Author: Dutch Bay EPC Model Team
Date: December 2025
Version: 1.0.0
"""

import numpy as np
import pytest

from finance.cashflow_v14_production import apply_degradation_profile


class TestWindDegradation:
    """Test suite for wind turbine performance degradation."""

    def test_degradation_reduces_production_monotonically(self):
        """Verify degradation causes monotonic production decline."""
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 0.65  # 0.65%/year

        production = apply_degradation_profile(aep_base, years, degradation_rate)

        # Production should decrease every year
        for i in range(1, years):
            assert (
                production[i] < production[i - 1]
            ), f"Production increased from year {i} to {i+1}"

    def test_year_1_equals_base_production(self):
        """First year should equal base production (no degradation yet)."""
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 0.65

        production = apply_degradation_profile(aep_base, years, degradation_rate)

        # Year 1 (index 0) should equal base
        assert production[0] == pytest.approx(aep_base, rel=1e-6)

    def test_year_10_degradation_matches_industry_data(self):
        """Year 10 should show ~6.5% decline with 0.65%/year degradation.

        Calculation: (1 - 0.0065)^9 = 0.9431 ≈ 5.7% loss
        Industry data: NREL reports 5-7% loss over 10 years.
        """
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 0.65

        production = apply_degradation_profile(aep_base, years, degradation_rate)

        # Year 10 = index 9
        expected_year_10 = aep_base * (1 - 0.0065) ** 9
        assert production[9] == pytest.approx(expected_year_10, rel=0.002)

        # Should be approximately 94% of base (6% loss)
        loss_pct = (1 - production[9] / aep_base) * 100
        assert (
            5.0 <= loss_pct <= 7.0
        ), f"Year 10 loss {loss_pct:.1f}% outside expected range [5%, 7%]"

    def test_year_25_cumulative_degradation(self):
        """Year 25 should show ~15% cumulative decline.

        Calculation: (1 - 0.0065)^24 = 0.8557 ≈ 14.4% loss
        Industry: Staffell & Green report 10-20% over 20 years.
        """
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 0.65

        production = apply_degradation_profile(aep_base, years, degradation_rate)

        # Year 25 = index 24
        expected_year_25 = aep_base * (1 - 0.0065) ** 24
        assert production[24] == pytest.approx(expected_year_25, rel=0.002)

        # Should be approximately 85% of base (15% loss)
        loss_pct = (1 - production[24] / aep_base) * 100
        assert (
            13.0 <= loss_pct <= 17.0
        ), f"Year 25 loss {loss_pct:.1f}% outside expected range [13%, 17%]"

    def test_zero_degradation_flat_production(self):
        """Zero degradation should yield flat production profile.

        Backward compatibility: Existing models with no degradation.
        """
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 0.0  # No degradation

        production = apply_degradation_profile(aep_base, years, degradation_rate)

        # All years should equal base
        for year_idx in range(years):
            assert production[year_idx] == pytest.approx(
                aep_base, rel=1e-6
            ), f"Year {year_idx + 1} production differs from base with 0% degradation"

    def test_commissioning_delay_degradation_start(self):
        """Commissioning years should have no degradation.

        Some projects model Year 1-2 as commissioning with no degradation.
        """
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 0.65
        start_year = 3  # Degradation starts Year 3

        production = apply_degradation_profile(
            aep_base, years, degradation_rate, start_year=start_year
        )

        # Years 1-2 should equal base (no degradation)
        assert production[0] == pytest.approx(aep_base, rel=1e-6)
        assert production[1] == pytest.approx(aep_base, rel=1e-6)

        # Convention: start_year is the reference year and degradation accrues
        # the year AFTER it — so year 3 (= start_year) is still at base, and
        # decline begins in year 4. (Consistent with the default start_year=1
        # case, where year 1 == base.)
        assert production[2] == pytest.approx(aep_base, rel=1e-6)
        assert production[3] < aep_base
        assert production[4] < production[3]

    def test_exponential_vs_linear_degradation(self):
        """Exponential and linear methods are distinct but close for small rates.

        Exponential: exp(-rate * t) - faster initial decline
        Linear: (1 - rate)^t - more gradual (conservative)
        """
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 0.65

        linear = apply_degradation_profile(
            aep_base, years, degradation_rate, method="linear"
        )
        exponential = apply_degradation_profile(
            aep_base, years, degradation_rate, method="exponential"
        )

        # Both should start at base
        assert linear[0] == pytest.approx(aep_base, rel=1e-6)
        assert exponential[0] == pytest.approx(aep_base, rel=1e-6)

        # exp(-r·t) and (1-r)^t nearly coincide for small annual rates (they
        # differ ~0.02% at 0.65%/yr), with exponential degrading marginally LESS
        # (exp(-r·t) >= (1-r)^t for r in (0,1)). Assert distinct + ordered, not
        # a fixed >=1% gap.
        assert linear[9] != exponential[9], "Methods should produce distinct profiles"
        assert exponential[9] >= linear[9]
        assert exponential[24] >= linear[24]

    def test_high_degradation_rate_validation(self):
        """Very high degradation rates should still produce valid results.

        Edge case: Old turbines with 1.6%/year (Staffell & Green max).
        """
        aep_base = 350_000  # MWh/year
        years = 25
        degradation_rate = 1.6  # High rate (old turbines)

        production = apply_degradation_profile(aep_base, years, degradation_rate)

        # Should still be monotonically decreasing
        for i in range(1, years):
            assert production[i] < production[i - 1]

        # Year 25 should be significantly lower (>30% loss)
        loss_pct = (1 - production[24] / aep_base) * 100
        assert (
            loss_pct > 30.0
        ), f"High degradation (1.6%/year) should cause >30% loss by Year 25"

    def test_degradation_profile_length(self):
        """Output list should have exactly 'years' elements."""
        aep_base = 350_000

        for years in [10, 20, 25, 30]:
            production = apply_degradation_profile(aep_base, years, 0.65)
            assert (
                len(production) == years
            ), f"Expected {years} elements, got {len(production)}"

    def test_degradation_with_low_base_aep(self):
        """Degradation should work with small AEP values.

        Edge case: Small test projects.
        """
        aep_base = 1000.0  # Small project
        years = 10
        degradation_rate = 0.65

        production = apply_degradation_profile(aep_base, years, degradation_rate)

        # Should still degrade correctly
        assert production[0] == pytest.approx(aep_base, rel=1e-6)
        assert production[9] < aep_base
        assert production[9] == pytest.approx(aep_base * (1 - 0.0065) ** 9, rel=0.002)


class TestDegradationIntegration:
    """Integration tests with cashflow model."""

    def test_degradation_reduces_npv(self):
        """Degradation should reduce project NPV.

        Without degradation: Flat revenue stream
        With degradation: Declining revenue stream
        NPV(degraded) < NPV(flat)
        """
        aep_base = 350_000  # MWh/year
        years = 20
        tariff = 68.0  # $/MWh
        discount_rate = 0.08

        # Calculate NPV without degradation
        flat_revenue = [aep_base * tariff for _ in range(years)]
        npv_flat = sum(
            rev / (1 + discount_rate) ** (i + 1) for i, rev in enumerate(flat_revenue)
        )

        # Calculate NPV with degradation
        degraded_aep = apply_degradation_profile(aep_base, years, 0.65)
        degraded_revenue = [aep * tariff for aep in degraded_aep]
        npv_degraded = sum(
            rev / (1 + discount_rate) ** (i + 1)
            for i, rev in enumerate(degraded_revenue)
        )

        # NPV with degradation should be lower
        assert npv_degraded < npv_flat

        # With 0.65%/yr degradation over 20 yrs AND an 8% discount rate, the
        # discounted NPV reduction is ~4.4%: discounting front-loads value into
        # the early, barely-degraded years, so it sits well below the
        # undiscounted ~6.5% terminal loss. (The old [7-13%] band ignored
        # discounting.)
        npv_reduction_pct = (1 - npv_degraded / npv_flat) * 100
        assert (
            3.5 <= npv_reduction_pct <= 5.5
        ), f"NPV reduction {npv_reduction_pct:.1f}% outside expected [3.5%, 5.5%]"


if __name__ == "__main__":
    # Run with: pytest tests/finance/test_production_degradation.py -v
    pytest.main([__file__, "-v", "--tb=short"])
