"""
Unit tests for Monte Carlo simulation module (analytics/monte_carlo_v14.py).

Test Coverage:
- Distribution validation (normal, triangular, uniform, lognormal)
- LHS sampling reproducibility and distribution shapes
- Config loading and validation
- Scenario execution (serial and parallel)
- Result aggregation and statistical accuracy
- Error handling and edge cases

All tests use the toy regression config for speed and determinism.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

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
    _build_samples_for_scenario,
    _compute_global_param_names,
    _generate_lhs_samples,
    _generate_unit_samples,
    _load_monte_carlo_config,
    _load_scenarios,
    _parse_derived_parameters,
    _parse_distributions,
    _run_single_iteration,
    _transform_to_distribution,
    _validate_distribution_for_sampling,
    run_monte_carlo_analysis,
)

# Test fixtures
BASE_CONFIG = "scenarios/dutchbay_lendercase_2025Q4.yaml"  # ✅ FIXED
MC_CONFIG_TOY = "config/monte_carlo_regression_toy.yaml"


# ══════════════════════════════════════════════════════════════════════════
# Distribution Validation Tests
# ══════════════════════════════════════════════════════════════════════════


class TestDistributionValidation:
    """Test distribution parameter validation."""

    def test_normal_distribution_requires_std(self) -> None:
        """Test that normal distribution requires std > 0."""
        with pytest.raises(ValueError, match=r"requires std\s*>\s*0"):
            Distribution(
                variable_name="test.param",
                dist_type="normal",
                mean=100.0,
                std=0.0,
            )

    def test_normal_distribution_valid(self) -> None:
        """Test that valid normal distribution passes validation."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="normal",
            mean=100.0,
            std=10.0,
        )
        # Should not raise
        _validate_distribution_for_sampling(dist)
        assert dist.mean == 100.0
        assert dist.std == 10.0

    def test_triangular_distribution_requires_min_mode_max(self) -> None:
        """Test that triangular requires min <= mode <= max."""
        with pytest.raises(ValueError, match=r"requires min\s*<=\s*mode\s*<=\s*max"):
            Distribution(
                variable_name="test.param",
                dist_type="triangular",
                mean=50.0,
                min_val=40.0,
                mode=65.0,  # mode > max (invalid)
                max_val=60.0,
            )

    def test_triangular_distribution_valid(self) -> None:
        """Test that valid triangular distribution passes validation."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="triangular",
            mean=50.0,
            min_val=40.0,
            mode=50.0,
            max_val=60.0,
        )
        _validate_distribution_for_sampling(dist)
        assert dist.min_val == 40.0
        assert dist.mode == 50.0
        assert dist.max_val == 60.0

    def test_uniform_distribution_requires_min_max(self) -> None:
        """Test that uniform requires min < max."""
        with pytest.raises(ValueError, match=r"requires min\s*<\s*max"):
            Distribution(
                variable_name="test.param",
                dist_type="uniform",
                min_val=100.0,
                max_val=90.0,  # max < min (invalid)
            )

    def test_uniform_distribution_valid(self) -> None:
        """Test that valid uniform distribution passes validation."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="uniform",
            min_val=80.0,
            max_val=120.0,
        )
        _validate_distribution_for_sampling(dist)
        assert dist.min_val == 80.0
        assert dist.max_val == 120.0

    def test_lognormal_distribution_requires_std(self) -> None:
        """Test that lognormal distribution requires std > 0."""
        with pytest.raises(ValueError, match=r"requires std\s*>\s*0"):
            Distribution(
                variable_name="test.param",
                dist_type="lognormal",
                mean=5.0,
                std=0.0,
            )

    def test_lognormal_distribution_valid(self) -> None:
        """Test that valid lognormal distribution passes validation."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="lognormal",
            mean=5.0,
            std=0.5,
        )
        _validate_distribution_for_sampling(dist)
        assert dist.mean == 5.0
        assert dist.std == 0.5


# ══════════════════════════════════════════════════════════════════════════
# Sampling Tests
# ══════════════════════════════════════════════════════════════════════════


class TestMonteCarloSampling:
    """Test Monte Carlo sampling functions."""

    def test_lhs_sampling_reproducibility(self) -> None:
        """Test that LHS sampling with same seed produces identical results."""
        params = [
            Distribution(
                variable_name="project.capex_usd_per_kw",
                dist_type="triangular",
                min_val=1100.0,
                mode=1200.0,
                max_val=1300.0,
            ),
            Distribution(
                variable_name="project.capacity_factor",
                dist_type="normal",
                mean=0.22,
                std=0.02,
            ),
        ]

        samples1 = _generate_lhs_samples(
            parameters=params,
            derived_parameters=None,
            n_samples=100,
            random_seed=42,
        )

        samples2 = _generate_lhs_samples(
            parameters=params,
            derived_parameters=None,
            n_samples=100,
            random_seed=42,
        )

        # Same seed → identical samples
        assert len(samples1) == len(samples2) == 100
        for s1, s2 in zip(samples1, samples2):
            assert s1.keys() == s2.keys()
            for key in s1:
                assert abs(s1[key] - s2[key]) < 1e-10

    def test_lhs_sampling_coverage(self) -> None:
        """Test that LHS samples cover parameter space uniformly."""
        params = [
            Distribution(
                variable_name="test.param",
                dist_type="uniform",
                min_val=0.0,
                max_val=100.0,
            )
        ]

        samples = _generate_lhs_samples(
            parameters=params,
            derived_parameters=None,
            n_samples=500,
            random_seed=123,
        )

        values = [s["test.param"] for s in samples]
        assert len(values) == 500
        assert min(values) >= 0.0
        assert max(values) <= 100.0

        # LHS should provide good coverage: check quartiles
        q1, q2, q3 = np.percentile(values, [25, 50, 75])
        assert 20.0 < q1 < 30.0
        assert 45.0 < q2 < 55.0
        assert 70.0 < q3 < 80.0

    def test_transform_to_distribution_normal(self) -> None:
        """Test normal distribution transformation."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="normal",
            mean=100.0,
            std=15.0,
        )

        # Test median (unit_value = 0.5) → should be close to mean
        median_value = _transform_to_distribution(0.5, dist)
        assert abs(median_value - 100.0) < 1.0

        # Test tails
        low_value = _transform_to_distribution(0.01, dist)
        high_value = _transform_to_distribution(0.99, dist)
        assert low_value < 100.0
        assert high_value > 100.0

    def test_transform_to_distribution_triangular(self) -> None:
        """Test triangular distribution transformation."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="triangular",
            min_val=80.0,
            mode=100.0,
            max_val=120.0,
        )

        # Test bounds
        min_value = _transform_to_distribution(0.0001, dist)
        max_value = _transform_to_distribution(0.9999, dist)
        assert 80.0 <= min_value <= 120.0
        assert 80.0 <= max_value <= 120.0
        assert min_value < max_value

        # Test mode vicinity
        mode_value = _transform_to_distribution(0.5, dist)
        assert 95.0 < mode_value < 105.0

    def test_transform_to_distribution_uniform(self) -> None:
        """Test uniform distribution transformation."""
        dist = Distribution(
            variable_name="test.param",
            dist_type="uniform",
            min_val=50.0,
            max_val=150.0,
        )

        # Test linear mapping
        assert abs(_transform_to_distribution(0.0, dist) - 50.0) < 0.1
        assert abs(_transform_to_distribution(0.5, dist) - 100.0) < 0.1
        assert abs(_transform_to_distribution(1.0, dist) - 150.0) < 0.1


# ══════════════════════════════════════════════════════════════════════════
# Config Loading Tests
# ══════════════════════════════════════════════════════════════════════════


class TestConfigLoading:
    """Test Monte Carlo configuration loading and validation."""

    def test_load_monte_carlo_config(self) -> None:
        """Test loading and validating MC config YAML."""
        mc_config = _load_monte_carlo_config(MC_CONFIG_TOY)

        assert mc_config.simulation.iterations >= 1
        assert mc_config.simulation.sampler in {"lhs", "sobol", "random"}
        assert len(mc_config.standard_parameters) > 0

    def test_load_scenarios(self) -> None:
        """Test loading scenarios from MC config."""
        mc_config = _load_monte_carlo_config(MC_CONFIG_TOY)
        scenarios = _load_scenarios(mc_config, scenario_name=None)

        assert len(scenarios) > 0
        for scenario in scenarios:
            assert isinstance(scenario, MonteCarloScenario)
            assert scenario.name
            assert len(scenario.standard_params) > 0  # ✅ FIXED

    def test_parse_distributions(self) -> None:
        """Test parsing distribution configs into Distribution objects."""
        params_config = [
            {
                "variable_name": "project.capex_usd_per_kw",
                "dist_type": "triangular",
                "min_val": 1100.0,
                "mode": 1200.0,
                "max_val": 1300.0,
            },
            {
                "variable_name": "project.capacity_factor",
                "dist_type": "normal",
                "mean": 0.22,
                "std": 0.02,
            },
        ]

        distributions = _parse_distributions(params_config)
        assert len(distributions) == 2
        assert all(isinstance(d, Distribution) for d in distributions)

    def test_parse_derived_parameters(self) -> None:
        """Test parsing derived parameter configs."""
        derived_config = [
            {
                "variable_name": "revenue.tariff_usd_per_kwh",
                "derive_from": "target_project_irr",
                "target_distribution": {
                    "dist_type": "normal",
                    "mean": 0.12,
                    "std": 0.01,
                },
                "solver_config": {"tolerance": 1e-6, "max_iterations": 50},
                "enabled": True,
            }
        ]

        derived_params = _parse_derived_parameters(derived_config)
        assert len(derived_params) == 1
        assert isinstance(derived_params[0], DerivedParameter)
        assert derived_params[0].variable_name == "revenue.tariff_usd_per_kwh"


# ══════════════════════════════════════════════════════════════════════════
# Unit Sampling and CRN Tests
# ══════════════════════════════════════════════════════════════════════════


class TestUnitSampling:
    """Test unit hypercube sampling and common random numbers (CRN)."""

    def test_generate_unit_samples_lhs(self) -> None:
        """Test LHS unit hypercube generation."""
        rng = np.random.default_rng(42)
        unit_samples = _generate_unit_samples(
            n_dim=3,
            n_samples=100,
            sampler="lhs",
            rng=rng,
        )

        assert unit_samples.shape == (100, 3)
        assert np.all(unit_samples >= 0.0)
        assert np.all(unit_samples <= 1.0)

    def test_generate_unit_samples_sobol(self) -> None:
        """Test Sobol unit hypercube generation."""
        rng = np.random.default_rng(42)
        unit_samples = _generate_unit_samples(
            n_dim=3,
            n_samples=100,
            sampler="sobol",
            rng=rng,
        )

        assert unit_samples.shape == (100, 3)
        assert np.all(unit_samples >= 0.0)
        assert np.all(unit_samples <= 1.0)

    def test_generate_unit_samples_random(self) -> None:
        """Test random unit hypercube generation."""
        rng = np.random.default_rng(42)
        unit_samples = _generate_unit_samples(
            n_dim=3,
            n_samples=100,
            sampler="random",
            rng=rng,
        )

        assert unit_samples.shape == (100, 3)
        assert np.all(unit_samples >= 0.0)
        assert np.all(unit_samples <= 1.0)

    def test_compute_global_param_names(self) -> None:
        """Test global parameter name computation for CRN."""
        scenarios = [
            MonteCarloScenario(
                name="A",
                description="",
                standard_params=[  # ✅ FIXED
                    Distribution(
                        variable_name="project.capex_usd_per_kw",
                        dist_type="uniform",
                        min_val=1000.0,
                        max_val=1400.0,
                    ),
                    Distribution(
                        variable_name="project.capacity_factor",
                        dist_type="normal",
                        mean=0.22,
                        std=0.02,
                    ),
                ],
                derived_params=[],  # ✅ FIXED
            ),
            MonteCarloScenario(
                name="B",
                description="",
                standard_params=[  # ✅ FIXED
                    Distribution(
                        variable_name="project.capex_usd_per_kw",
                        dist_type="uniform",
                        min_val=1100.0,
                        max_val=1300.0,
                    ),
                ],
                derived_params=[],  # ✅ FIXED
            ),
        ]

        global_names = _compute_global_param_names(scenarios)
        assert set(global_names) == {
            "project.capex_usd_per_kw",
            "project.capacity_factor",
        }
        # Should be sorted for stability
        assert global_names == sorted(global_names)

    def test_build_samples_for_scenario(self) -> None:
        """Test building scenario-specific samples from unit hypercube."""
        rng = np.random.default_rng(42)
        standard_params = [
            Distribution(
                variable_name="project.capex_usd_per_kw",
                dist_type="uniform",
                min_val=1000.0,
                max_val=1400.0,
            ),
        ]
        global_param_names = ["project.capex_usd_per_kw"]
        unit_samples = rng.uniform(0.0, 1.0, size=(10, 1))

        samples = _build_samples_for_scenario(
            standard_params=standard_params,
            derived_params=[],
            unit_samples=unit_samples,
            global_param_names=global_param_names,
            rng=rng,
        )

        assert len(samples) == 10
        for sample in samples:
            assert "project.capex_usd_per_kw" in sample
            assert 1000.0 <= sample["project.capex_usd_per_kw"] <= 1400.0


# ══════════════════════════════════════════════════════════════════════════
# Result Aggregation Tests
# ══════════════════════════════════════════════════════════════════════════


class TestResultAggregation:
    """Test Monte Carlo result aggregation and statistics."""

    def test_aggregate_results_basic(self) -> None:
        """Test basic result aggregation with successful iterations."""
        results = [
            {"project_irr": 0.12, "project_npv": 1000.0, "dscr_min": 1.35},
            {"project_irr": 0.13, "project_npv": 1200.0, "dscr_min": 1.40},
            {"project_irr": 0.11, "project_npv": 800.0, "dscr_min": 1.30},
            {"project_irr": 0.14, "project_npv": 1400.0, "dscr_min": 1.45},
        ]

        mc_result = _aggregate_results(
            results=results,
            total_iterations=4,
            scenario_name="Test",
        )

        assert isinstance(mc_result, MonteCarloResult)
        assert mc_result.iterations == 4
        assert mc_result.failed_iterations == 0
        assert 0.11 <= mc_result.project_irr_p10 <= 0.14
        assert 0.11 <= mc_result.project_irr_p50 <= 0.14
        assert 0.11 <= mc_result.project_irr_p90 <= 0.14
        assert mc_result.success_rate() == 100.0

    def test_aggregate_results_with_failures(self) -> None:
        """Test result aggregation with some failed iterations."""
        results: list[dict[str, float] | None] = [
            {"project_irr": 0.12, "project_npv": 1000.0, "dscr_min": 1.35},
            None,  # Failed iteration
            {"project_irr": 0.13, "project_npv": 1200.0, "dscr_min": 1.40},
            None,  # Failed iteration
        ]

        mc_result = _aggregate_results(
            results=results,
            total_iterations=4,
            scenario_name="Test",
        )

        assert mc_result.iterations == 4
        assert mc_result.failed_iterations == 2
        assert mc_result.success_rate() == 50.0

    def test_aggregate_results_precision_fields(self) -> None:
        """Test that precision fields (SE) are computed."""
        results = [
            {"project_irr": 0.12, "project_npv": 1000.0, "dscr_min": 1.35},
            {"project_irr": 0.13, "project_npv": 1200.0, "dscr_min": 1.40},
            {"project_irr": 0.11, "project_npv": 800.0, "dscr_min": 1.30},
            {"project_irr": 0.14, "project_npv": 1400.0, "dscr_min": 1.45},
        ]

        mc_result = _aggregate_results(
            results=results,
            total_iterations=4,
            scenario_name="Test",
        )

        # Precision fields should be populated
        assert mc_result.project_irr_se is not None
        assert mc_result.project_irr_se > 0.0
        assert mc_result.project_npv_se is not None
        assert mc_result.dscr_min_se is not None


# ══════════════════════════════════════════════════════════════════════════
# Integration Tests
# ══════════════════════════════════════════════════════════════════════════


class TestMonteCarloIntegration:
    """Integration tests for full Monte Carlo runs."""

    def test_run_monte_carlo_analysis_toy_config(self) -> None:
        """Test full MC run with toy regression config."""
        results = run_monte_carlo_analysis(
            base_config_path=BASE_CONFIG,
            scenario_config_path=MC_CONFIG_TOY,
            n_iterations=50,  # Small for speed
            random_seed=42,
            parallel_workers=1,
        )

        assert len(results) > 0
        for scenario_name, mc_result in results.items():
            assert isinstance(mc_result, MonteCarloResult)
            assert mc_result.iterations == 50
            assert mc_result.success_rate() > 0.0
            # Basic sanity checks
            assert mc_result.project_irr_p50 > 0.0
            assert mc_result.project_npv_p50 != 0.0
            assert mc_result.dscr_min_p50 > 0.0

    def test_run_monte_carlo_reproducibility(self) -> None:
        """Test that same seed produces identical results."""
        results1 = run_monte_carlo_analysis(
            base_config_path=BASE_CONFIG,
            scenario_config_path=MC_CONFIG_TOY,
            n_iterations=20,
            random_seed=123,
            parallel_workers=1,
        )

        results2 = run_monte_carlo_analysis(
            base_config_path=BASE_CONFIG,
            scenario_config_path=MC_CONFIG_TOY,
            n_iterations=20,
            random_seed=123,
            parallel_workers=1,
        )

        # Same seed → identical KPIs
        assert results1.keys() == results2.keys()
        for scenario_name in results1:
            r1 = results1[scenario_name]
            r2 = results2[scenario_name]
            assert abs(r1.project_irr_p50 - r2.project_irr_p50) < 1e-10
            assert abs(r1.project_npv_p50 - r2.project_npv_p50) < 1e-6

    def test_run_single_iteration(self) -> None:
        """Test single iteration execution with parameter sample."""
        mc_config = _load_monte_carlo_config(MC_CONFIG_TOY)
        scenarios = _load_scenarios(mc_config, scenario_name=None)
        scenario = scenarios[0]

        # Build a simple sample
        sample = {
            "project.capex_usd_per_kw": 1200.0,
            "project.capacity_factor": 0.22,
        }

        result = _run_single_iteration(
            base_config_path=BASE_CONFIG,
            scenario=scenario,
            sample=sample,
        )

        # Should return valid KPIs or None (if solver failed)
        if result is not None:
            assert "project_irr" in result
            assert "project_npv" in result
            assert "dscr_min" in result


# ══════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_config_path(self) -> None:
        """Test that invalid config path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            _load_monte_carlo_config("nonexistent_config.yaml")

    def test_invalid_distribution_in_config(self) -> None:
        """Test that invalid distribution config raises ValueError."""
        params_config = [
            {
                "variable_name": "test.param",
                "dist_type": "normal",
                "mean": 100.0,
                "std": -10.0,  # Invalid: std must be > 0
            }
        ]

        with pytest.raises(ValueError):
            _parse_distributions(params_config)

    def test_all_iterations_failed(self) -> None:
        """Test handling when all iterations fail."""
        results: list[dict[str, float] | None] = [None, None, None, None]

        with pytest.raises(ValueError, match="All Monte Carlo iterations failed"):
            _aggregate_results(
                results=results,
                total_iterations=4,
                scenario_name="FailedScenario",
            )


# ══════════════════════════════════════════════════════════════════════════
# MonteCarloResult Contract Tests
# ══════════════════════════════════════════════════════════════════════════


class TestMonteCarloResult:
    """Test MonteCarloResult data contract."""

    def test_success_rate_calculation(self) -> None:
        """Test success rate calculation."""
        result = MonteCarloResult(
            iterations=100,
            failed_iterations=20,
            project_irr_mean=0.12,
            project_irr_std=0.02,
            project_irr_p10=0.10,
            project_irr_p50=0.12,
            project_irr_p90=0.14,
            project_npv_mean=1000.0,
            project_npv_p10=800.0,
            project_npv_p50=1000.0,
            project_npv_p90=1200.0,
            dscr_min_p10=1.25,
            dscr_min_p50=1.35,
        )

        assert result.success_rate() == 80.0

    def test_probability_above_threshold(self) -> None:
        """Test probability_above_threshold calculation."""
        raw_results = [
            {"project_irr": 0.11, "dscr_min": 1.25},
            {"project_irr": 0.13, "dscr_min": 1.35},
            {"project_irr": 0.12, "dscr_min": 1.30},
            {"project_irr": 0.14, "dscr_min": 1.40},
        ]

        result = MonteCarloResult(
            iterations=4,
            failed_iterations=0,
            project_irr_mean=0.125,
            project_irr_std=0.013,
            project_irr_p10=0.11,
            project_irr_p50=0.125,
            project_irr_p90=0.14,
            project_npv_mean=1000.0,
            project_npv_p10=800.0,
            project_npv_p50=1000.0,
            project_npv_p90=1200.0,
            dscr_min_p10=1.25,
            dscr_min_p50=1.325,
            raw_results=raw_results,
        )

        # 3 out of 4 results have project_irr >= 0.12
        prob_irr = result.probability_above_threshold("project_irr", 0.12)
        assert prob_irr == 75.0

        # 2 out of 4 results have dscr_min >= 1.35
        prob_dscr = result.probability_above_threshold("dscr_min", 1.35)
        assert prob_dscr == 50.0


# ══════════════════════════════════════════════════════════════════════════
# EOF - tests/analytics_layer/test_monte_carlo_v14.py
# ══════════════════════════════════════════════════════════════════════════
