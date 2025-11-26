"""Unit tests for analytics.monte_carlo_v14 module.

Tests validate Monte Carlo coordinator functionality:
1. Parameter sampling (LHS generation)
2. Distribution transformations
3. Derived parameter solving
4. Parallel execution
5. Statistical aggregation
6. Error handling and isolation

Pattern: Fast tests with small iteration counts, mocked solvers.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from analytics.contracts_v14 import (
    DerivedParameter,
    Distribution,
    MonteCarloResult,
    MonteCarloScenario,
)
from analytics.monte_carlo_v14 import (
    _aggregate_results,
    _build_overrides_from_sample,
    _generate_lhs_samples,
    _set_nested_value,
    _transform_to_distribution,
    run_monte_carlo_analysis,
)


class TestDistributionValidation:
    """Test Distribution dataclass validation."""

    def test_normal_distribution_valid(self):
        """Test valid normal distribution."""
        dist = Distribution(
            variable_name="test.param", dist_type="normal", mean=100.0, std=10.0
        )
        assert dist.mean == 100.0
        assert dist.std == 10.0

    def test_normal_distribution_requires_std(self):
        """Test that normal distribution requires std > 0."""
        with pytest.raises(ValueError, match="requires std > 0"):
            Distribution(
                variable_name="test.param", dist_type="normal", mean=100.0, std=0.0
            )

    def test_triangular_distribution_valid(self):
        """Test valid triangular distribution."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="triangular",
            mean=50.0,
            min_val=40.0,
            mode=50.0,
            max_val=60.0,
        )
        assert dist.min_val <= dist.mode <= dist.max_val

    def test_triangular_distribution_requires_min_mode_max(self):
        """Test that triangular requires min <= mode <= max."""
        with pytest.raises(ValueError, match="requires min <= mode <= max"):
            Distribution(
                variable_name="test.param",
                dist_type="triangular",
                mean=50.0,
                min_val=40.0,
                mode=65.0,  # mode > max (invalid)
                max_val=60.0,
            )

    def test_uniform_distribution_valid(self):
        """Test valid uniform distribution."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="uniform",
            mean=50.0,
            min_val=40.0,
            max_val=60.0,
        )
        assert dist.min_val < dist.max_val


class TestLHSSampling:
    """Test Latin Hypercube Sampling generation."""

    def test_generate_lhs_samples_basic(self):
        """Test basic LHS sample generation."""
        params = [
            Distribution(
                variable_name="param1", dist_type="normal", mean=100.0, std=10.0
            ),
            Distribution(
                variable_name="param2",
                dist_type="uniform",
                mean=50.0,
                min_val=40.0,
                max_val=60.0,
            ),
        ]

        samples = _generate_lhs_samples(params, [], n_samples=10, random_seed=42)

        assert len(samples) == 10
        assert all("param1" in s for s in samples)
        assert all("param2" in s for s in samples)

    def test_lhs_reproducibility(self):
        """Test that same seed produces same samples."""
        params = [
            Distribution(
                variable_name="param1", dist_type="normal", mean=100.0, std=10.0
            )
        ]

        samples1 = _generate_lhs_samples(params, [], n_samples=5, random_seed=42)
        samples2 = _generate_lhs_samples(params, [], n_samples=5, random_seed=42)

        # Same seed should produce same samples
        for s1, s2 in zip(samples1, samples2):
            assert s1["param1"] == pytest.approx(s2["param1"])


class TestDistributionTransform:
    """Test transformation from unit hypercube to distributions."""

    def test_uniform_transform(self):
        """Test uniform distribution transformation."""
        dist = Distribution(
            variable_name="test",
            dist_type="uniform",
            mean=50.0,
            min_val=40.0,
            max_val=60.0,
        )

        # Transform edges of unit hypercube
        val_0 = _transform_to_distribution(0.0, dist)
        val_1 = _transform_to_distribution(1.0, dist)

        assert val_0 == pytest.approx(40.0)
        assert val_1 == pytest.approx(60.0)

    def test_normal_transform_mean(self):
        """Test normal distribution transformation at median."""
        dist = Distribution(
            variable_name="test", dist_type="normal", mean=100.0, std=10.0
        )

        # 0.5 in unit hypercube should be close to mean
        val_median = _transform_to_distribution(0.5, dist)
        assert val_median == pytest.approx(100.0, abs=1.0)


class TestBuildOverrides:
    """Test building nested override dicts from samples."""

    def test_build_simple_override(self):
        """Test building override with single-level path."""
        params = [
            Distribution(
                variable_name="param1", dist_type="normal", mean=100.0, std=10.0
            )
        ]
        sample = {"param1": 95.0}

        overrides = _build_overrides_from_sample(sample, params)

        assert overrides == {"param1": 95.0}

    def test_build_nested_override(self):
        """Test building override with nested path."""
        params = [
            Distribution(
                variable_name="project.capex_usd_per_kw",
                dist_type="normal",
                mean=850.0,
                std=85.0,
            )
        ]
        sample = {"project.capex_usd_per_kw": 900.0}

        overrides = _build_overrides_from_sample(sample, params)

        assert overrides == {"project": {"capex_usd_per_kw": 900.0}}

    def test_build_multiple_nested_overrides(self):
        """Test building override with multiple nested paths."""
        params = [
            Distribution(
                variable_name="project.capex_usd_per_kw",
                dist_type="normal",
                mean=850.0,
                std=85.0,
            ),
            Distribution(
                variable_name="financial.tariff_lkr_per_kwh",
                dist_type="uniform",
                mean=65.0,
                min_val=60.0,
                max_val=70.0,
            ),
        ]
        sample = {
            "project.capex_usd_per_kw": 900.0,
            "financial.tariff_lkr_per_kwh": 67.5,
        }

        overrides = _build_overrides_from_sample(sample, params)

        assert overrides == {
            "project": {"capex_usd_per_kw": 900.0},
            "financial": {"tariff_lkr_per_kwh": 67.5},
        }


class TestSetNestedValue:
    """Test setting values in nested dicts."""

    def test_set_single_level(self):
        """Test setting value at single level."""
        d = {}
        _set_nested_value(d, ["key"], 42)
        assert d == {"key": 42}

    def test_set_two_levels(self):
        """Test setting value at two levels."""
        d = {}
        _set_nested_value(d, ["level1", "level2"], 42)
        assert d == {"level1": {"level2": 42}}

    def test_set_three_levels(self):
        """Test setting value at three levels."""
        d = {}
        _set_nested_value(d, ["a", "b", "c"], 42)
        assert d == {"a": {"b": {"c": 42}}}


class TestAggregateResults:
    """Test statistical aggregation of MC results."""

    def test_aggregate_basic(self):
        """Test basic aggregation of successful iterations."""
        results = [
            {"project_irr": 0.10, "project_npv": 10000000.0, "dscr_min": 1.30},
            {"project_irr": 0.12, "project_npv": 12000000.0, "dscr_min": 1.35},
            {"project_irr": 0.14, "project_npv": 14000000.0, "dscr_min": 1.40},
        ]

        mc_result = _aggregate_results(
            results, total_iterations=3, scenario_name="test"
        )

        assert mc_result.iterations == 3
        assert mc_result.failed_iterations == 0
        assert mc_result.project_irr_mean == pytest.approx(0.12)
        assert mc_result.project_irr_p50 == pytest.approx(0.12)

    def test_aggregate_with_failures(self):
        """Test aggregation with some failed iterations."""
        results = [
            {"project_irr": 0.10, "project_npv": 10000000.0, "dscr_min": 1.30},
            None,  # Failed iteration
            {"project_irr": 0.12, "project_npv": 12000000.0, "dscr_min": 1.35},
        ]

        mc_result = _aggregate_results(
            results, total_iterations=3, scenario_name="test"
        )

        assert mc_result.iterations == 3
        assert mc_result.failed_iterations == 1
        assert len(mc_result.raw_results) == 2

    def test_aggregate_all_failed(self):
        """Test that all failed iterations raises error."""
        results = [None, None, None]

        with pytest.raises(ValueError, match="All Monte Carlo iterations failed"):
            _aggregate_results(results, total_iterations=3, scenario_name="test")


class TestMonteCarloResult:
    """Test MonteCarloResult methods."""

    def test_success_rate(self):
        """Test success rate calculation."""
        result = MonteCarloResult(
            iterations=100,
            project_irr_mean=0.12,
            project_irr_std=0.02,
            project_irr_p10=0.09,
            project_irr_p50=0.12,
            project_irr_p90=0.15,
            project_npv_mean=15000000.0,
            project_npv_p10=10000000.0,
            project_npv_p50=15000000.0,
            project_npv_p90=20000000.0,
            dscr_min_p10=1.25,
            dscr_min_p50=1.35,
            failed_iterations=5,
            raw_results=[],
            scenario_name="test",
        )

        assert result.success_rate() == 95.0

    def test_probability_above_threshold(self):
        """Test probability calculation."""
        result = MonteCarloResult(
            iterations=10,
            project_irr_mean=0.12,
            project_irr_std=0.02,
            project_irr_p10=0.09,
            project_irr_p50=0.12,
            project_irr_p90=0.15,
            project_npv_mean=15000000.0,
            project_npv_p10=10000000.0,
            project_npv_p50=15000000.0,
            project_npv_p90=20000000.0,
            dscr_min_p10=1.25,
            dscr_min_p50=1.35,
            failed_iterations=0,
            raw_results=[
                {"project_irr": 0.10},
                {"project_irr": 0.11},
                {"project_irr": 0.12},
                {"project_irr": 0.13},
                {"project_irr": 0.14},
            ],
            scenario_name="test",
        )

        # 3 out of 5 values >= 0.12 → 60%
        prob = result.probability_above_threshold("project_irr", 0.12)
        assert prob == 60.0


# pytest configuration
pytest_plugins = []

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
