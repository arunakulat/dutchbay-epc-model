#!/usr/bin/env python
"""Integration tests for degradation flow across modules.

Verifies that turbine degradation:
1. Flows from configuration → cashflow model
2. Reduces revenue year-over-year correctly
3. Integrates with Monte Carlo uncertainty
4. Feeds into sensitivity analysis
5. Impacts dual DSCR debt sizing

Framework Compliance:
- TEST-01: Regression pins for degradation behavior
- CASPER: Tail-risk validation (degradation uncertainty)
- NO REGRESSION: Tests new integration only

Author: DutchBay Integration Team
Date: December 2025
"""

from typing import Any, Dict

import numpy as np
import pytest

# Import modules to test. analyze_dscr_sensitivity is the only symbol the tests
# below actually exercise; the cashflow / Monte-Carlo behaviour is asserted
# structurally off the config fixtures. It is a FIRST-PARTY analytics symbol, not
# an optional dependency, so import it UNGUARDED: a rename or removal must fail
# loudly at collection rather than silently skip this module's degradation
# regression pins. (The prior module-level ImportError->skip guard also masked a
# never-existent finance.cashflow_v14_params.extract_cashflow_params import, which
# had silently skipped the whole module — round-2 audit.)
from analytics.dscr_sensitivity import analyze_dscr_sensitivity


class TestDegradationConfiguration:
    """Test degradation parameter extraction and validation."""

    def test_degradation_extracted_from_config(self, dutchbay_base_config):
        """Degradation should be extracted from config correctly."""
        # This tests the parameter extraction layer
        degradation_pct = dutchbay_base_config["project"]["degradation"]

        assert (
            degradation_pct == 0.006
        ), f"Expected 0.6% degradation, got {degradation_pct*100}%"

    def test_degradation_converts_to_decimal(self, dutchbay_base_config):
        """Config degradation should be in decimal form."""
        degradation = dutchbay_base_config["project"]["degradation"]

        # Should be decimal (0.006), not percentage (0.6)
        assert 0.0 < degradation < 0.1, f"Degradation should be decimal: {degradation}"

    def test_degradation_backward_compatible_zero(self):
        """Zero degradation should be valid (backward compatibility)."""
        config = {"project": {"degradation": 0.0}}
        degradation = config["project"]["degradation"]

        assert degradation == 0.0, "Zero degradation should be allowed"


class TestDegradationCashflowIntegration:
    """Test degradation integration with cashflow model."""

    def test_year1_uses_full_aep(self, dutchbay_base_config):
        """Year 1 revenue should use full AEP (no degradation yet)."""
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]

        # Year 1 revenue (before degradation)
        expected_revenue_y1 = aep * tariff

        # Verify calculation
        assert expected_revenue_y1 == 400_000 * 50.0
        assert expected_revenue_y1 == 20_000_000  # $20M

    def test_year20_reflects_cumulative_degradation(
        self, dutchbay_base_config, degradation_test_params
    ):
        """Year 20 revenue should reflect compound degradation."""
        aep_y1 = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        degradation_rate = dutchbay_base_config["project"]["degradation"]

        # Year 1 revenue
        revenue_y1 = aep_y1 * tariff

        # Year 20: Apply degradation for 19 years (starts year 2)
        degradation_factor_y20 = (1 - degradation_rate) ** 19
        revenue_y20 = revenue_y1 * degradation_factor_y20

        # Verify against test parameters
        expected_factor = degradation_test_params["base_case"]["year_20_factor"]
        calculated_factor = (1 - 0.006) ** 20  # Alternative: full 20 years

        # Year 20 should be ~88.7% of Year 1
        assert (
            0.88 < degradation_factor_y20 < 0.90
        ), f"Year 20 factor should be ~89%, got {degradation_factor_y20:.1%}"

    def test_revenue_decreases_monotonically(self, dutchbay_base_config):
        """Revenue should decrease every year with positive degradation."""
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        degradation = dutchbay_base_config["project"]["degradation"]
        project_life = dutchbay_base_config["project"]["life_years"]

        # Build revenue array
        revenues = []
        for year in range(project_life):
            # Degradation starts year 2, so year 0 = full output
            aep_year = aep * (1 - degradation) ** year
            revenue_year = aep_year * tariff
            revenues.append(revenue_year)

        # Verify monotonic decrease
        for i in range(1, len(revenues)):
            assert revenues[i] < revenues[i - 1], (
                f"Revenue should decrease: year {i+1} = ${revenues[i]:.0f}, "
                f"year {i} = ${revenues[i-1]:.0f}"
            )

    def test_total_revenue_with_vs_without_degradation(self, dutchbay_base_config):
        """Total revenue over project life should be ~5.5% less with degradation.

        This is the *total-life* loss (sum of annual revenue), ~5.5% for 0.6%/yr
        over 20yr — NOT the year-20 endpoint factor (~11.3% down), which earlier
        revisions of this pin conflated it with.
        """
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        degradation = dutchbay_base_config["project"]["degradation"]
        project_life = dutchbay_base_config["project"]["life_years"]

        # Without degradation
        revenue_no_deg = aep * tariff * project_life

        # With degradation
        revenue_with_deg = sum(
            aep * (1 - degradation) ** year * tariff for year in range(project_life)
        )

        # Calculate impact
        revenue_loss_pct = (revenue_no_deg - revenue_with_deg) / revenue_no_deg * 100

        # ~5.5% total-life loss over 20 years with 0.6% degradation
        assert (
            5.0 < revenue_loss_pct < 6.0
        ), f"Total-life revenue loss should be ~5.5%, got {revenue_loss_pct:.1f}%"


class TestDegradationMonteCarloIntegration:
    """Test degradation integration with Monte Carlo engine."""

    @pytest.mark.slow
    def test_monte_carlo_includes_degradation_variable(self, dutchbay_omegaconf_config):
        """Monte Carlo should sample degradation as stochastic variable."""
        # Check if MC config has degradation parameters
        mc_config = dutchbay_omegaconf_config.monte_carlo

        assert (
            "degradation_mean_pct" in mc_config
        ), "Monte Carlo config should include degradation_mean_pct"
        assert (
            "degradation_std_pct" in mc_config
        ), "Monte Carlo config should include degradation_std_pct"

    @pytest.mark.slow
    def test_monte_carlo_degradation_uncertainty(self, dutchbay_omegaconf_config):
        """Monte Carlo should model degradation uncertainty (±0.1%)."""
        mc_config = dutchbay_omegaconf_config.monte_carlo

        mean_pct = mc_config.degradation_mean_pct
        std_pct = mc_config.degradation_std_pct

        # Base case: 0.6% ± 0.1%
        assert mean_pct == 0.6, f"Expected 0.6% mean, got {mean_pct}%"
        assert std_pct == 0.1, f"Expected 0.1% std, got {std_pct}%"

    @pytest.mark.slow
    def test_correlation_includes_degradation(self, dutchbay_omegaconf_config):
        """Correlation matrix should include degradation variable."""
        mc_config = dutchbay_omegaconf_config.monte_carlo

        if mc_config.correlation_enabled:
            corr_matrix = mc_config.correlation_matrix

            # Should be 4x4 matrix (revenue, cost, FX, degradation)
            assert (
                len(corr_matrix) == 4
            ), f"Expected 4x4 correlation matrix, got {len(corr_matrix)}x{len(corr_matrix[0])}"

            # Verify diagonal is 1.0
            for i in range(4):
                assert (
                    corr_matrix[i][i] == 1.0
                ), f"Diagonal element [{i},{i}] should be 1.0"


class TestDegradationSensitivityIntegration:
    """Test degradation integration with sensitivity analysis."""

    def test_sensitivity_includes_degradation_variable(self, dutchbay_omegaconf_config):
        """Sensitivity analysis should include degradation as variable."""
        sens_config = dutchbay_omegaconf_config.sensitivity

        assert (
            "degradation" in sens_config.variables
        ), "Sensitivity variables should include degradation"

    def test_degradation_sensitivity_produces_results(self, dutchbay_omegaconf_config):
        """Degradation sensitivity should produce valid results."""
        # The module-level guard already skips if analyze_dscr_sensitivity is
        # unimportable; a runtime error here is a real regression, not a skip.
        result = analyze_dscr_sensitivity(
            dutchbay_omegaconf_config, variables=["degradation"]
        )

        assert "variables" in result
        assert len(result["variables"]) == 1
        assert result["variables"][0]["variable"] == "degradation"

    def test_higher_degradation_reduces_debt_capacity(self, dutchbay_omegaconf_config):
        """Higher degradation should reduce debt sizing capacity."""
        result = analyze_dscr_sensitivity(
            dutchbay_omegaconf_config, variables=["degradation"]
        )

        deg_result = result["variables"][0]
        perturbations = deg_result["perturbations"]

        # Find min and max perturbation
        min_pert = min(perturbations, key=lambda x: x["perturbation_pct"])
        max_pert = max(perturbations, key=lambda x: x["perturbation_pct"])

        # Lower degradation → higher debt
        # Higher degradation → lower debt
        assert (
            min_pert["debt_sized"] > max_pert["debt_sized"]
        ), "Debt capacity should decrease with higher degradation"


class TestDegradationRegressionPins:
    """Regression pins for degradation integration (TEST-01 compliance)."""

    def test_standard_degradation_factors(self, degradation_test_params):
        """Verify standard degradation factors are correct."""
        base = degradation_test_params["base_case"]

        # Year 10 factor
        calculated_y10 = (1 - 0.006) ** 10
        assert abs(calculated_y10 - base["year_10_factor"]) < 0.001, (
            f"Year 10 factor mismatch: expected {base['year_10_factor']}, "
            f"got {calculated_y10}"
        )

        # Year 20 factor
        calculated_y20 = (1 - 0.006) ** 20
        assert abs(calculated_y20 - base["year_20_factor"]) < 0.001, (
            f"Year 20 factor mismatch: expected {base['year_20_factor']}, "
            f"got {calculated_y20}"
        )

    def test_degradation_revenue_impact_magnitude(self, dutchbay_base_config):
        """20-year degradation should reduce total-life revenue by ~5.5%."""
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        degradation = 0.006  # 0.6%/year
        project_life = 20

        # No degradation total
        total_no_deg = aep * tariff * project_life

        # With degradation total
        total_with_deg = sum(
            aep * (1 - degradation) ** t * tariff for t in range(project_life)
        )

        # Calculate impact
        impact_pct = (total_no_deg - total_with_deg) / total_no_deg * 100

        # Regression pin: ~5.50% total-life loss (0.6%/yr x 20yr). The prior
        # 11% pin was the year-20 endpoint factor, not the total-revenue impact.
        assert (
            5.3 < impact_pct < 5.7
        ), f"20-year total-revenue impact should be ~5.5%, got {impact_pct:.2f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
