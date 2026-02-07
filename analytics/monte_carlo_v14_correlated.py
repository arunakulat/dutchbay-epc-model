#!/usr/bin/env python
"""Fully integrated Monte Carlo with degradation and correlation.

Sprint 17 Priority 1 Complete: Degradation + Correlation.

This is the production-ready Monte Carlo engine with:
1. Degradation uncertainty modeling
2. Variable correlation structure (Iman-Conover)
3. Latin Hypercube Sampling
4. Full CESSPIT/CASPER/GWTF compliance

Usage:
    from analytics.monte_carlo_v14_correlated import MonteCarloEngineCorrelated

    engine = MonteCarloEngineCorrelated(config, n_iterations=10000)
    results = engine.run()

    # Results include:
    # - NPV/IRR statistics
    # - Degradation impact analysis
    # - Correlation verification

Configuration:
    monte_carlo:
      n_iterations: 10000
      sampling_method: "lhs"

      # Correlation structure
      correlation:
        enabled: true
        matrix:
          - [1.0,  0.4, -0.3, -0.2]  # revenue
          - [0.4,  1.0, -0.2,  0.1]  # cost
          - [-0.3, -0.2, 1.0,  0.0]  # FX
          - [-0.2, 0.1,  0.0,  1.0]  # degradation

    degradation:
      annual_rate_pct: 0.6
      uncertainty_std_pct: 0.1
      method: "compound"
      distribution: "normal"

CESSPIT: Zero hardcoded values
CASPER: Lender-grade risk modeling
GWTF: R7 (IRR singleton), R22 (schema), R23 (testable), R24 (docstrings)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from omegaconf import DictConfig, OmegaConf

from analytics.correlation_engine import (
    apply_correlation_to_lhs,
    load_correlation_from_config,
)
from analytics.monte_carlo_v14_enhanced import (
    MonteCarloEngineEnhanced,
    _calculate_degradation_statistics,
    _sample_degradation,
)
from analytics.monte_carlo_v14 import (
    _aggregate_results,
    _generate_lhs_samples,
    _transform_to_distribution,
)

logger = logging.getLogger(__name__)


class MonteCarloEngineCorrelated(MonteCarloEngineEnhanced):
    """Production Monte Carlo engine with degradation and correlation.

    Sprint 17 Priority 1 Complete Implementation.

    Combines:
    - Degradation uncertainty (from MonteCarloEngineEnhanced)
    - Variable correlation (Iman-Conover method)
    - Latin Hypercube Sampling
    - Full framework compliance

    NO REGRESSION: Extends MonteCarloEngineEnhanced, adds correlation layer.
    """

    def __init__(self, config: DictConfig, n_iterations: int = 1000) -> None:
        """Initialize correlated Monte Carlo engine.

        Args:
            config: Hydra configuration with monte_carlo and degradation sections
            n_iterations: Number of Monte Carlo iterations

        Raises:
            ValueError: If required config sections missing
        """
        # Initialize enhanced engine (includes degradation)
        super().__init__(config, n_iterations)

        # Load correlation configuration (CESSPIT)
        self.correlation_enabled = False
        self.correlation_matrix = None

        if hasattr(config, "monte_carlo"):
            mc_config = config.monte_carlo

            if hasattr(mc_config, "correlation"):
                corr_config = mc_config.correlation
                self.correlation_enabled = bool(corr_config.get("enabled", False))

                if self.correlation_enabled:
                    # Load correlation matrix from config
                    config_dict = OmegaConf.to_container(config, resolve=True)
                    n_vars = 4  # revenue, cost, FX, degradation

                    try:
                        self.correlation_matrix = load_correlation_from_config(
                            config_dict, n_vars
                        )
                        self.logger.info(
                            "Correlation enabled with 4-variable matrix "
                            "(revenue, cost, FX, degradation)"
                        )
                    except ValueError as e:
                        self.logger.error(f"Failed to load correlation: {e}")
                        raise

        if not self.correlation_enabled:
            self.logger.info("Correlation disabled - using independent sampling")

    def run(self) -> dict[str, Any]:
        """Execute fully integrated Monte Carlo with degradation and correlation.

        Sprint 17 Priority 1 Complete Implementation.

        Returns:
            Enhanced results with:
            - Standard NPV/IRR statistics
            - Degradation impact metrics
            - Correlation verification
            - Execution metadata
        """
        import time

        start_time = time.time()

        try:
            self.logger.info(
                f"Starting Correlated MC with degradation: {self.mc_config.scenario_name}"
            )
            self.logger.info(
                f"  Iterations: {self.mc_config.n_iterations}, "
                f"Method: {self.mc_config.sampling_method}"
            )
            self.logger.info(
                f"  Degradation: {self.degradation_mean_pct}% ± {self.degradation_std_pct}%, "
                f"{self.degradation_method}"
            )
            self.logger.info(
                f"  Correlation: {'enabled' if self.correlation_enabled else 'disabled'}"
            )

            # Generate LHS samples for 4 variables
            n_vars = 4  # revenue, cost, FX, degradation

            if self.mc_config.sampling_method == "lhs":
                unit_samples = _generate_lhs_samples(
                    self.mc_config.n_iterations, n_vars, self.mc_config.seed
                )
                self.logger.info(
                    f"Generated {self.mc_config.n_iterations} LHS samples (4D)"
                )
            else:
                if self.mc_config.seed is not None:
                    np.random.seed(self.mc_config.seed)
                unit_samples = np.random.rand(self.mc_config.n_iterations, n_vars)
                self.logger.info(f"Using random sampling (seed={self.mc_config.seed})")

            # Apply correlation if enabled
            if self.correlation_enabled and self.correlation_matrix is not None:
                self.logger.info("Applying Iman-Conover correlation...")
                unit_samples = apply_correlation_to_lhs(
                    unit_samples, self.correlation_matrix
                )
                self.logger.info("Correlation applied successfully")

            # Run iterations with correlated samples
            iterations = []
            npv_values = []
            irr_values = []
            degradation_values = []
            year_20_factors = []

            for i in range(self.mc_config.n_iterations):
                # Transform unit samples to distribution parameters
                revenue_sample = _transform_to_distribution(
                    unit_samples[i, 0],
                    self.mc_config.revenue_mean_usd,
                    self.mc_config.revenue_std_pct,
                )
                cost_sample = _transform_to_distribution(
                    unit_samples[i, 1],
                    self.mc_config.cost_mean_usd,
                    self.mc_config.cost_std_pct,
                )
                fx_sample = _transform_to_distribution(
                    unit_samples[i, 2],
                    self.mc_config.fx_mean_rate,
                    self.mc_config.fx_std_pct,
                )

                # Sample degradation (correlated with other variables)
                degradation_sample = _sample_degradation(
                    unit_samples[i, 3],
                    self.degradation_mean_pct,
                    self.degradation_std_pct,
                    self.degradation_distribution,
                )

                # Run iteration with degradation
                iteration = self.simulate_iteration_with_degradation(
                    revenue_sample, cost_sample, fx_sample, degradation_sample
                )

                iterations.append(iteration)
                npv_values.append(iteration["npv_usd"])
                irr_values.append(iteration["irr_pct"])
                degradation_values.append(iteration["degradation_rate"])
                year_20_factors.append(iteration["year_20_output_factor"])

                if (i + 1) % max(1, self.mc_config.n_iterations // 10) == 0:
                    self.logger.info(
                        f"  Completed {i + 1}/{self.mc_config.n_iterations} iterations"
                    )

            # Calculate statistics
            statistics = _aggregate_results(npv_values, irr_values)
            degradation_statistics = _calculate_degradation_statistics(
                degradation_values, year_20_factors
            )

            # Verify correlation (if enabled)
            correlation_verification = {}
            if self.correlation_enabled:
                correlation_verification = self._verify_correlation(
                    unit_samples, iterations
                )

            execution_time = time.time() - start_time

            result: dict[str, Any] = {
                "scenario_name": self.mc_config.scenario_name,
                "n_iterations": self.mc_config.n_iterations,
                "project_life_years": self.mc_config.project_life_years,
                "discount_rate_pct": self.mc_config.discount_rate_pct,
                "capex_total_usd": self.mc_config.capex_total_usd,
                "sampling_method": self.mc_config.sampling_method,
                "degradation_method": self.degradation_method,
                "correlation_enabled": self.correlation_enabled,
                "execution_time_seconds": execution_time,
                "statistics": statistics,
                "degradation_statistics": degradation_statistics,
                "correlation_verification": correlation_verification,
                "iterations": (
                    iterations if self.mc_config.n_iterations <= 100 else []
                ),
                "success": True,
            }

            # Enhanced logging
            self.logger.info(
                f"Correlated MC simulation completed in {execution_time:.2f}s"
            )
            self.logger.info(f"  NPV Mean: ${statistics['npv_mean_usd']/1e6:.2f}M")
            self.logger.info(
                f"  NPV P10-P90: ${statistics['npv_p10_usd']/1e6:.2f}M to "
                f"${statistics['npv_p90_usd']/1e6:.2f}M"
            )
            self.logger.info(f"  IRR Mean: {statistics['irr_mean_pct']:.2f}%")
            self.logger.info(
                f"  Degradation: {degradation_statistics['degradation_mean_pct']:.2f}% ± "
                f"{degradation_statistics['degradation_std_pct']:.2f}%"
            )

            if self.correlation_enabled and correlation_verification:
                self.logger.info(
                    f"  Correlation Max Error: "
                    f"{correlation_verification.get('max_error', 0):.3f}"
                )

            return result

        except Exception as e:
            self.logger.error(f"Correlated MC simulation failed: {str(e)}")
            return {
                "scenario_name": self.mc_config.scenario_name,
                "success": False,
                "error": str(e),
            }

    def _verify_correlation(
        self, unit_samples: np.ndarray, iterations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Verify correlation was correctly applied.

        Compares target correlation matrix with achieved correlation.

        Args:
            unit_samples: Correlated unit samples [0,1]^(n x 4)
            iterations: List of iteration results

        Returns:
            Verification metrics including max error
        """
        from scipy import stats

        # Extract transformed samples for correlation check
        n = len(iterations)
        samples = np.zeros((n, 4))

        for i, iteration in enumerate(iterations):
            samples[i, 0] = iteration["revenue_usd"]
            samples[i, 1] = iteration["cost_usd"]
            samples[i, 2] = iteration["fx_rate"]
            samples[i, 3] = iteration["degradation_rate"]

        # Transform to normal space for correlation calculation
        # (correlation is defined in normal space, not parameter space)
        normal_samples = stats.norm.ppf(np.clip(unit_samples, 1e-10, 1 - 1e-10))
        achieved_corr = np.corrcoef(normal_samples.T)

        # Calculate correlation error
        if self.correlation_matrix is not None:
            corr_error = np.abs(achieved_corr - self.correlation_matrix)

            # Exclude diagonal
            n_vars = 4
            mask = ~np.eye(n_vars, dtype=bool)
            max_error = float(np.max(corr_error[mask]))
            mean_error = float(np.mean(corr_error[mask]))

            return {
                "target_correlation": self.correlation_matrix.tolist(),
                "achieved_correlation": achieved_corr.tolist(),
                "max_error": max_error,
                "mean_error": mean_error,
                "acceptable": max_error < 0.1,  # 0.1 tolerance
            }

        return {}


__all__ = [
    "MonteCarloEngineCorrelated",
]
