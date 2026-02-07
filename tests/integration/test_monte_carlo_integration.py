#!/usr/bin/env python
"""Integration tests for Monte Carlo engine with degradation and correlation.

Verifies that Monte Carlo:
1. Integrates degradation as 4th stochastic variable
2. Applies correlation structure correctly
3. Produces valid NPV/IRR distributions
4. Meets performance benchmarks
5. Validates statistical outputs (P10/P50/P90)

Framework Compliance:
- TEST-01: Regression pins for MC behavior
- CASPER: Tail-risk distribution validation
- Performance: < 10s for 1K iterations

Author: DutchBay Integration Team
Date: December 2025
"""

import pytest
import time
import numpy as np
from typing import Dict, Any

# Import modules to test
try:
    from analytics.monte_carlo_v14 import MonteCarloEngine
    from omegaconf import OmegaConf
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)


class TestMonteCarloConfiguration:
    """Test Monte Carlo configuration validation."""

    def test_mc_config_includes_degradation(self, dutchbay_omegaconf_config):
        """Monte Carlo config should include degradation parameters."""
        mc_config = dutchbay_omegaconf_config.monte_carlo

        assert mc_config.enabled is True
        assert "degradation_mean_pct" in mc_config
        assert "degradation_std_pct" in mc_config

        # Values should be reasonable
        assert 0.4 <= mc_config.degradation_mean_pct <= 0.8
        assert 0.05 <= mc_config.degradation_std_pct <= 0.2

    def test_mc_config_has_correlation_matrix(self, dutchbay_omegaconf_config):
        """Monte Carlo should have 4x4 correlation matrix."""
        mc_config = dutchbay_omegaconf_config.monte_carlo

        if mc_config.correlation_enabled:
            corr_matrix = mc_config.correlation_matrix

            # Should be 4x4 (revenue, cost, FX, degradation)
            assert len(corr_matrix) == 4
            assert all(len(row) == 4 for row in corr_matrix)

            # Diagonal should be 1.0
            for i in range(4):
                assert corr_matrix[i][i] == 1.0

            # Should be symmetric
            for i in range(4):
                for j in range(4):
                    assert abs(corr_matrix[i][j] - corr_matrix[j][i]) < 1e-10


class TestMonteCarloExecution:
    """Test Monte Carlo execution and results."""

    @pytest.mark.slow
    def test_monte_carlo_runs_successfully(self, dutchbay_omegaconf_config):
        """Monte Carlo should execute without errors."""
        # Use small iteration count for speed
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 100  # Fast test

        try:
            engine = MonteCarloEngine(mc_config, n_iterations=100)
            result = engine.run()

            assert result["success"] is True
            assert result["n_iterations"] == 100
            assert "statistics" in result

        except Exception as e:
            pytest.fail(f"Monte Carlo execution failed: {e}")

    @pytest.mark.slow
    def test_monte_carlo_produces_npv_distribution(self, dutchbay_omegaconf_config):
        """Monte Carlo should produce NPV statistics."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 100

        engine = MonteCarloEngine(mc_config, n_iterations=100)
        result = engine.run()

        stats = result["statistics"]

        # Should have NPV statistics
        assert "npv_mean_usd" in stats
        assert "npv_std_usd" in stats
        assert "npv_median_usd" in stats
        assert "npv_p10_usd" in stats
        assert "npv_p90_usd" in stats

        # NPV should be reasonable
        assert stats["npv_mean_usd"] > 0, "Mean NPV should be positive"
        assert stats["npv_std_usd"] > 0, "NPV std should be positive"

    @pytest.mark.slow
    def test_monte_carlo_produces_irr_distribution(self, dutchbay_omegaconf_config):
        """Monte Carlo should produce IRR statistics."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 100

        engine = MonteCarloEngine(mc_config, n_iterations=100)
        result = engine.run()

        stats = result["statistics"]

        # Should have IRR statistics
        assert "irr_mean_pct" in stats
        assert "irr_std_pct" in stats
        assert "irr_median_pct" in stats
        assert "irr_p10_pct" in stats
        assert "irr_p90_pct" in stats

        # IRR should be reasonable
        assert (
            5.0 < stats["irr_mean_pct"] < 20.0
        ), f"Mean IRR should be 5-20%, got {stats['irr_mean_pct']:.1f}%"


class TestMonteCarloStatistics:
    """Test Monte Carlo statistical outputs."""

    @pytest.mark.slow
    def test_percentiles_ordered_correctly(self, dutchbay_omegaconf_config):
        """P10 < P50 < P90 ordering should be correct."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = (
            500  # More iterations for stable percentiles
        )

        engine = MonteCarloEngine(mc_config, n_iterations=500)
        result = engine.run()

        stats = result["statistics"]

        # NPV percentiles
        assert stats["npv_p10_usd"] < stats["npv_median_usd"] < stats["npv_p90_usd"], (
            f"NPV percentiles out of order: P10={stats['npv_p10_usd']/1e6:.1f}M, "
            f"P50={stats['npv_median_usd']/1e6:.1f}M, P90={stats['npv_p90_usd']/1e6:.1f}M"
        )

        # IRR percentiles
        assert stats["irr_p10_pct"] < stats["irr_median_pct"] < stats["irr_p90_pct"], (
            f"IRR percentiles out of order: P10={stats['irr_p10_pct']:.1f}%, "
            f"P50={stats['irr_median_pct']:.1f}%, P90={stats['irr_p90_pct']:.1f}%"
        )

    @pytest.mark.slow
    def test_median_close_to_mean(self, dutchbay_omegaconf_config):
        """Median should be reasonably close to mean for large samples."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 1000

        engine = MonteCarloEngine(mc_config, n_iterations=1000)
        result = engine.run()

        stats = result["statistics"]

        # NPV: median should be within 20% of mean
        npv_diff_pct = (
            abs(stats["npv_median_usd"] - stats["npv_mean_usd"])
            / stats["npv_mean_usd"]
            * 100
        )
        assert (
            npv_diff_pct < 20.0
        ), f"NPV median should be within 20% of mean, got {npv_diff_pct:.1f}% difference"

        # IRR: median should be within 15% of mean
        irr_diff_pct = (
            abs(stats["irr_median_pct"] - stats["irr_mean_pct"])
            / stats["irr_mean_pct"]
            * 100
        )
        assert (
            irr_diff_pct < 15.0
        ), f"IRR median should be within 15% of mean, got {irr_diff_pct:.1f}% difference"


class TestMonteCarloPerformance:
    """Test Monte Carlo performance benchmarks."""

    @pytest.mark.slow
    def test_1k_iterations_performance(
        self, dutchbay_omegaconf_config, performance_benchmarks
    ):
        """1,000 iterations should complete within performance target."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 1000

        engine = MonteCarloEngine(mc_config, n_iterations=1000)

        start_time = time.time()
        result = engine.run()
        execution_time = time.time() - start_time

        max_time = performance_benchmarks["monte_carlo_1k_max_seconds"]

        assert (
            execution_time < max_time
        ), f"1K iterations should complete in < {max_time}s, took {execution_time:.1f}s"

        # Also check result metadata
        assert result["execution_time_seconds"] < max_time

    @pytest.mark.slow
    @pytest.mark.performance
    def test_10k_iterations_performance(
        self, dutchbay_omegaconf_config, performance_benchmarks
    ):
        """10,000 iterations should complete within performance target."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 10000

        engine = MonteCarloEngine(mc_config, n_iterations=10000)

        start_time = time.time()
        result = engine.run()
        execution_time = time.time() - start_time

        max_time = performance_benchmarks["monte_carlo_10k_max_seconds"]

        assert (
            execution_time < max_time
        ), f"10K iterations should complete in < {max_time}s, took {execution_time:.1f}s"

    @pytest.mark.slow
    def test_iterations_per_second_rate(self, dutchbay_omegaconf_config):
        """Should achieve minimum iterations per second rate."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 500

        engine = MonteCarloEngine(mc_config, n_iterations=500)

        start_time = time.time()
        result = engine.run()
        execution_time = time.time() - start_time

        iterations_per_second = 500 / execution_time

        # Should achieve at least 100 iterations/second
        assert (
            iterations_per_second > 100
        ), f"Should achieve > 100 iter/s, got {iterations_per_second:.0f} iter/s"


class TestMonteCarloDegradationIntegration:
    """Test degradation integration in Monte Carlo."""

    @pytest.mark.slow
    def test_degradation_affects_npv_distribution(self, dutchbay_omegaconf_config):
        """Degradation uncertainty should widen NPV distribution."""
        mc_config = dutchbay_omegaconf_config

        # Run with degradation uncertainty
        mc_config.monte_carlo.n_iterations = 500
        mc_config.monte_carlo.degradation_std_pct = 0.1  # ±0.1%

        engine_with_deg = MonteCarloEngine(mc_config, n_iterations=500)
        result_with_deg = engine_with_deg.run()

        # Run without degradation uncertainty (zero std)
        mc_config.monte_carlo.degradation_std_pct = 0.0
        engine_no_deg = MonteCarloEngine(mc_config, n_iterations=500)
        result_no_deg = engine_no_deg.run()

        # NPV std should be higher with degradation uncertainty
        std_with_deg = result_with_deg["statistics"]["npv_std_usd"]
        std_no_deg = result_no_deg["statistics"]["npv_std_usd"]

        assert std_with_deg > std_no_deg, (
            f"Degradation uncertainty should increase NPV std: "
            f"with={std_with_deg/1e6:.1f}M, without={std_no_deg/1e6:.1f}M"
        )


class TestMonteCarloRegressionPins:
    """Regression pins for Monte Carlo integration (TEST-01 compliance)."""

    @pytest.mark.slow
    def test_npv_distribution_with_dutchbay_parameters(self, dutchbay_omegaconf_config):
        """NPV distribution should be reasonable for DutchBay parameters."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 500
        mc_config.monte_carlo.seed = 42  # Reproducible

        engine = MonteCarloEngine(mc_config, n_iterations=500)
        result = engine.run()

        stats = result["statistics"]

        # Mean NPV should be in reasonable range
        mean_npv_m = stats["npv_mean_usd"] / 1e6
        assert (
            20.0 < mean_npv_m < 80.0
        ), f"Mean NPV should be $20-80M, got ${mean_npv_m:.1f}M"

        # P10-P90 range should show reasonable uncertainty
        p10_m = stats["npv_p10_usd"] / 1e6
        p90_m = stats["npv_p90_usd"] / 1e6
        range_m = p90_m - p10_m

        assert (
            range_m > 10.0
        ), f"P10-P90 NPV range should be > $10M, got ${range_m:.1f}M"

    @pytest.mark.slow
    def test_irr_distribution_with_dutchbay_parameters(self, dutchbay_omegaconf_config):
        """IRR distribution should be reasonable for DutchBay parameters."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 500
        mc_config.monte_carlo.seed = 42

        engine = MonteCarloEngine(mc_config, n_iterations=500)
        result = engine.run()

        stats = result["statistics"]

        # Mean IRR should be in reasonable range
        mean_irr = stats["irr_mean_pct"]
        assert 7.0 < mean_irr < 15.0, f"Mean IRR should be 7-15%, got {mean_irr:.1f}%"

        # P10-P90 range should show reasonable uncertainty
        p10_irr = stats["irr_p10_pct"]
        p90_irr = stats["irr_p90_pct"]
        range_irr = p90_irr - p10_irr

        assert (
            range_irr > 3.0
        ), f"P10-P90 IRR range should be > 3%, got {range_irr:.1f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
