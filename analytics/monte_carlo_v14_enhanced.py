#!/usr/bin/env python
"""Enhanced Monte Carlo engine with degradation uncertainty.

Sprint 17 Priority 1: Integrates wind turbine degradation as stochastic variable.

Enhancements over monte_carlo_v14.py:
1. Degradation rate sampled from distribution (mean 0.6%, std 0.1%)
2. Year-over-year degradation applied to revenue
3. Tracking of year 20 output factor
4. Extended statistics for degradation impact

Usage:
    from analytics.monte_carlo_v14_enhanced import MonteCarloEngineEnhanced
    
    engine = MonteCarloEngineEnhanced(config, n_iterations=10000)
    results = engine.run()
    
    # Degradation statistics
    print(results['degradation_statistics'])

CESSPIT: All parameters from config (defaults.yaml or scenario override)
CASPER: Conservative degradation modeling for lender presentations
GWTF: Full rule compliance (R7, R22, R23, R24)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from omegaconf import DictConfig
from scipy.stats import norm

from analytics.monte_carlo_v14 import (
    MonteCarloEngine,
    _aggregate_results,
    _generate_lhs_samples,
    _transform_to_distribution,
)
from finance.irr import irr, npv  # R7: IRR/NPV from finance.irr ONLY

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloConfigEnhanced:
    """Enhanced configuration with degradation parameters.
    
    CESSPIT: All parameters from config/defaults.yaml.
    """

    # Base parameters (from MonteCarloConfig)
    scenario_name: str
    n_iterations: int
    capex_total_usd: float
    revenue_mean_usd: float
    revenue_std_pct: float
    cost_mean_usd: float
    cost_std_pct: float
    fx_mean_rate: float
    fx_std_pct: float
    project_life_years: int
    discount_rate_pct: float
    sampling_method: str
    seed: Optional[int]
    
    # NEW: Degradation parameters (Sprint 17)
    degradation_mean_pct: float  # From config (e.g., 0.6)
    degradation_std_pct: float   # From config (e.g., 0.1)
    degradation_method: str      # "compound" or "linear"
    degradation_distribution: str  # "normal" or "lognormal"


def _apply_degradation_to_revenue(
    base_revenue: float,
    degradation_rate: float,
    project_life: int,
    method: str = "compound"
) -> list[float]:
    """Apply year-over-year degradation to revenue stream.
    
    Industry Practice:
    - Compound degradation: Revenue_t = Revenue_0 * (1 - rate)^t
    - Linear degradation: Revenue_t = Revenue_0 * (1 - rate*t)
    
    Compound method is industry standard (NREL, DNV GL).
    Linear method is more conservative (higher degradation).
    
    Args:
        base_revenue: Year 1 revenue (USD)
        degradation_rate: Annual degradation rate (decimal, e.g., 0.006)
        project_life: Project operating years
        method: "compound" or "linear"
    
    Returns:
        List of annual revenues with degradation applied
    
    Example:
        >>> revenue = _apply_degradation_to_revenue(20e6, 0.006, 3, "compound")
        >>> revenue[0]  # Year 1
        20000000.0
        >>> revenue[2]  # Year 3: 20M * (1-0.006)^2 ≈ 19.76M
        19760720.0
    """
    revenues = []
    
    for t in range(project_life):
        if method == "compound":
            # Standard compound degradation (exponential decay)
            revenue_t = base_revenue * (1 - degradation_rate) ** t
        elif method == "linear":
            # Linear degradation (arithmetic decay) - more conservative
            revenue_t = base_revenue * max(0, (1 - degradation_rate * t))
        else:
            raise ValueError(f"Invalid degradation method: {method}")
        
        revenues.append(revenue_t)
    
    return revenues


def _sample_degradation(
    unit_value: float,
    mean_pct: float,
    std_pct: float,
    distribution: str = "normal"
) -> float:
    """Sample degradation rate from distribution.
    
    CESSPIT: Parameters from config/defaults.yaml.
    CASPER: Conservative sampling (truncate at 0.3% minimum for physical validity).
    
    Args:
        unit_value: Value in [0, 1] from LHS
        mean_pct: Mean degradation (%, e.g., 0.6)
        std_pct: Std deviation (%, e.g., 0.1)
        distribution: "normal" or "lognormal"
    
    Returns:
        Degradation rate as decimal (e.g., 0.006 for 0.6%)
    
    Example:
        >>> deg = _sample_degradation(0.5, 0.6, 0.1, "normal")
        >>> 0.003 <= deg <= 0.010  # ±3 sigma from 0.6%
        True
    """
    if distribution == "normal":
        # Normal distribution
        degradation_pct = norm.ppf(unit_value, loc=mean_pct, scale=std_pct)
        
        # CASPER: Truncate for physical validity
        # Min 0.3% (excellent turbines), Max 1.5% (poor conditions)
        degradation_pct = np.clip(degradation_pct, 0.3, 1.5)
        
    elif distribution == "lognormal":
        # Lognormal distribution (strictly positive)
        # Convert mean/std from % space to log space
        from scipy.stats import lognorm
        
        # Fit lognormal parameters
        mean_decimal = mean_pct / 100.0
        std_decimal = std_pct / 100.0
        
        # Shape and scale for lognormal
        s = np.sqrt(np.log(1 + (std_decimal / mean_decimal) ** 2))
        scale = mean_decimal / np.sqrt(1 + (std_decimal / mean_decimal) ** 2)
        
        degradation_decimal = lognorm.ppf(unit_value, s=s, scale=scale)
        degradation_pct = degradation_decimal * 100.0
        
    else:
        raise ValueError(f"Invalid distribution: {distribution}")
    
    # Convert percentage to decimal
    return degradation_pct / 100.0


def _calculate_degradation_statistics(
    degradation_values: list[float],
    year_20_factors: list[float]
) -> dict[str, float]:
    """Calculate degradation-specific statistics.
    
    Args:
        degradation_values: List of degradation rates (decimal) from iterations
        year_20_factors: List of year 20 output factors (e.g., 0.887 for 0.6% deg)
    
    Returns:
        Dictionary with degradation statistics
    """
    deg_array = np.array(degradation_values)
    y20_array = np.array(year_20_factors)
    
    return {
        "degradation_mean_pct": float(np.mean(deg_array) * 100),
        "degradation_std_pct": float(np.std(deg_array) * 100),
        "degradation_p10_pct": float(np.percentile(deg_array, 10) * 100),
        "degradation_p90_pct": float(np.percentile(deg_array, 90) * 100),
        "year_20_output_mean_pct": float(np.mean(y20_array) * 100),
        "year_20_output_p10_pct": float(np.percentile(y20_array, 10) * 100),
        "year_20_output_p90_pct": float(np.percentile(y20_array, 90) * 100),
        "cumulative_loss_20yr_mean_pct": float((1 - np.mean(y20_array)) * 100),
    }


class MonteCarloEngineEnhanced(MonteCarloEngine):
    """Enhanced Monte Carlo engine with degradation uncertainty.
    
    Sprint 17 Priority 1: Extends MonteCarloEngine with degradation modeling.
    
    NO REGRESSION: Base class methods unchanged, new functionality added.
    
    New Features:
    - Samples degradation rate from distribution
    - Applies year-over-year degradation to cashflows
    - Tracks degradation impact metrics
    - Compatible with correlation structure (Sprint 17 Part 2)
    """

    def __init__(self, config: DictConfig, n_iterations: int = 1000) -> None:
        """Initialize enhanced Monte Carlo engine.
        
        CESSPIT: All degradation parameters from config/defaults.yaml.
        
        Args:
            config: Hydra configuration
            n_iterations: Number of Monte Carlo iterations
        
        Raises:
            ValueError: If degradation parameters missing from config
        """
        # Initialize base engine
        super().__init__(config, n_iterations)
        
        # Extract degradation parameters (CESSPIT compliance)
        if not hasattr(config, "degradation"):
            raise ValueError(
                "CESSPIT VIOLATION: config.degradation section required. "
                "Add to config/defaults.yaml or scenario YAML."
            )
        
        deg_config = config.degradation
        
        # CESSPIT: All parameters from config, no defaults in code
        self.degradation_mean_pct = float(deg_config.annual_rate_pct)
        self.degradation_std_pct = float(deg_config.uncertainty_std_pct)
        self.degradation_method = str(deg_config.method)
        self.degradation_distribution = str(deg_config.distribution)
        
        self.logger.info(
            f"Degradation config: mean={self.degradation_mean_pct}%, "
            f"std={self.degradation_std_pct}%, method={self.degradation_method}"
        )
    
    def simulate_iteration_with_degradation(
        self,
        revenue_sample: float,
        cost_sample: float,
        fx_sample: float,
        degradation_sample: float
    ) -> dict[str, Any]:
        """Simulate single iteration with degradation applied.
        
        Sprint 17: Extends base simulate_iteration with degradation.
        
        Args:
            revenue_sample: Revenue value from LHS (USD/year)
            cost_sample: Cost value from LHS (USD/year)
            fx_sample: FX rate from LHS
            degradation_sample: Degradation rate from LHS (decimal, e.g., 0.006)
        
        Returns:
            Dictionary with NPV, IRR, and degradation metrics
        """
        # Apply degradation to revenue stream
        revenues_degraded = _apply_degradation_to_revenue(
            base_revenue=revenue_sample,
            degradation_rate=degradation_sample,
            project_life=self.mc_config.project_life_years,
            method=self.degradation_method
        )
        
        # Build cashflow array with degraded revenues
        cf_array = [-self.mc_config.capex_total_usd]  # Initial CAPEX
        
        for t in range(self.mc_config.project_life_years):
            annual_cf = revenues_degraded[t] - cost_sample
            cf_array.append(annual_cf)
        
        # Calculate NPV using R7: finance.irr.npv() ONLY *** CRITICAL R7 ***
        discount_rate = self.mc_config.discount_rate_pct / 100.0
        project_npv = npv(discount_rate, cf_array)
        
        # Calculate IRR using R7: finance.irr.irr() ONLY *** CRITICAL R7 ***
        project_irr_decimal = irr(cf_array)
        project_irr_pct = (
            (project_irr_decimal * 100.0) if project_irr_decimal is not None else 0.0
        )
        
        # Calculate year 20 output factor (for CASPER analysis)
        if self.degradation_method == "compound":
            year_20_factor = (1 - degradation_sample) ** 20
        else:  # linear
            year_20_factor = max(0, 1 - degradation_sample * 20)
        
        return {
            "npv_usd": project_npv,
            "irr_pct": project_irr_pct,
            "revenue_usd": revenue_sample,  # Year 1 revenue
            "cost_usd": cost_sample,
            "fx_rate": fx_sample,
            "degradation_rate": degradation_sample,  # NEW
            "degradation_rate_pct": degradation_sample * 100,  # NEW (for reporting)
            "year_20_output_factor": year_20_factor,  # NEW
            "cumulative_revenue_loss_pct": (1 - year_20_factor) * 100,  # NEW
        }
    
    def run(self) -> dict[str, Any]:
        """Execute enhanced Monte Carlo with degradation uncertainty.
        
        Sprint 17 Priority 1: Extends base run() with degradation sampling.
        
        Returns:
            Enhanced results dictionary with degradation statistics
        """
        import time
        
        start_time = time.time()
        
        try:
            self.logger.info(
                f"Starting Enhanced MC with degradation: {self.mc_config.scenario_name} "
                f"({self.mc_config.n_iterations} iterations)"
            )
            self.logger.info(
                f"Degradation: mean={self.degradation_mean_pct}%, "
                f"std={self.degradation_std_pct}%, method={self.degradation_method}"
            )
            
            # Generate LHS samples for 4 variables: revenue, cost, FX, degradation
            n_vars = 4  # Added degradation as 4th variable
            
            if self.mc_config.sampling_method == "lhs":
                unit_samples = _generate_lhs_samples(
                    self.mc_config.n_iterations, n_vars, self.mc_config.seed
                )
                self.logger.info(
                    f"Generated {self.mc_config.n_iterations} LHS samples "
                    f"(4D: revenue, cost, FX, degradation)"
                )
            else:
                if self.mc_config.seed is not None:
                    np.random.seed(self.mc_config.seed)
                unit_samples = np.random.rand(self.mc_config.n_iterations, n_vars)
                self.logger.info(f"Using random sampling (seed={self.mc_config.seed})")
            
            # Run iterations
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
                
                # NEW: Sample degradation rate
                degradation_sample = _sample_degradation(
                    unit_samples[i, 3],
                    self.degradation_mean_pct,
                    self.degradation_std_pct,
                    self.degradation_distribution
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
            
            # Calculate standard statistics
            statistics = _aggregate_results(npv_values, irr_values)
            
            # Calculate degradation-specific statistics
            degradation_statistics = _calculate_degradation_statistics(
                degradation_values, year_20_factors
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
                "execution_time_seconds": execution_time,
                "statistics": statistics,
                "degradation_statistics": degradation_statistics,  # NEW
                "iterations": (
                    iterations if self.mc_config.n_iterations <= 100 else []
                ),
                "success": True,
            }
            
            # Enhanced logging
            self.logger.info(f"Enhanced MC simulation completed in {execution_time:.2f}s")
            self.logger.info(f"  NPV Mean: ${statistics['npv_mean_usd']/1e6:.2f}M")
            self.logger.info(
                f"  NPV P10-P90: ${statistics['npv_p10_usd']/1e6:.2f}M to "
                f"${statistics['npv_p90_usd']/1e6:.2f}M"
            )
            self.logger.info(f"  IRR Mean: {statistics['irr_mean_pct']:.2f}%")
            self.logger.info(
                f"  Degradation Mean: {degradation_statistics['degradation_mean_pct']:.2f}%/year"
            )
            self.logger.info(
                f"  Year 20 Output: {degradation_statistics['year_20_output_mean_pct']:.1f}% "
                f"of Year 1 (P10-P90: {degradation_statistics['year_20_output_p10_pct']:.1f}% to "
                f"{degradation_statistics['year_20_output_p90_pct']:.1f}%)"
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Enhanced MC simulation failed: {str(e)}")
            return {
                "scenario_name": self.mc_config.scenario_name,
                "success": False,
                "error": str(e),
            }


__all__ = [
    "MonteCarloEngineEnhanced",
    "MonteCarloConfigEnhanced",
    # Helper functions for testing
    "_apply_degradation_to_revenue",
    "_sample_degradation",
    "_calculate_degradation_statistics",
]
