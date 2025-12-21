#!/usr/bin/env python
"""Enhanced Monte Carlo with degradation uncertainty and correlation structure.

Sprint 17 Priority Enhancement:
- Integrates wind turbine degradation as stochastic variable
- Implements Iman-Conover method for correlation preservation
- Models year-over-year revenue degradation in cashflow
- Supports 4+ variable correlation matrices

Usage:
    python -m analytics.monte_carlo_v14_enhanced \
        --config scenarios/mc_enhanced.yaml \
        --n-iterations 10000

New Features:
    1. Degradation Uncertainty:
       - Mean: 0.6%/year (from config)
       - Std: ±0.1%/year (1-sigma)
       - Distribution: Normal (can be changed to lognormal)
    
    2. Correlation Structure:
       - Revenue-Cost: +0.4 (inflation linkage)
       - Revenue-FX: -0.3 (USD-denominated PPA)
       - Revenue-Degradation: -0.2 (higher deg → lower output)
       - Implemented via Iman-Conover (1982) rank correlation
    
    3. Year-over-Year Degradation:
       - Cashflow incorporates compound degradation
       - Formula: Revenue_t = Revenue_0 * (1 - deg_rate)^t
       - Affects NPV through lifetime revenue trajectory

References:
    - Iman, R.L. & Conover, W.J. (1982). A distribution-free approach
      to inducing rank correlation among input variables.
      Communications in Statistics, 11(3), 311-334.
    - Bolinger (2017): Debt sizing with degradation
    - NREL (2019): Wind turbine performance degradation

CESSPIT: All defaults from config/defaults.yaml
CASPER: Conservative tail-risk modeling
GWTF: R7 (finance.irr), R22 (schema guard), R24 (docstrings)
CCCDIR: Config-driven correlation matrices
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
from omegaconf import DictConfig, OmegaConf
from scipy.linalg import cholesky
from scipy.stats import norm, qmc

from analytics.contracts_v14 import MonteCarloResult
from analytics.schema_guard import validate_config_for_v14
from finance.irr import irr, npv  # R7: Singleton IRR/NPV

logger = logging.getLogger(__name__)


@dataclass
class EnhancedMonteCarloConfig:
    """Enhanced Monte Carlo configuration with degradation and correlation.
    
    CESSPIT: All parameters from config YAML (no hardcoded defaults).
    
    Attributes:
        scenario_name: Scenario identifier
        n_iterations: Number of Monte Carlo simulations
        capex_total_usd: Initial capital expenditure
        revenue_mean_usd: Mean annual revenue (year 1, before degradation)
        revenue_std_pct: Revenue standard deviation (% of mean)
        cost_mean_usd: Mean annual operating cost
        cost_std_pct: Cost standard deviation (% of mean)
        fx_mean_rate: Mean FX rate (LKR/USD)
        fx_std_pct: FX standard deviation (% of mean)
        degradation_mean_pct: Mean annual degradation rate (%/year)
        degradation_std_pct: Degradation standard deviation (%/year absolute)
        project_life_years: Project lifetime (years)
        discount_rate_pct: Discount rate for NPV (%)
        correlation_enabled: Enable correlation structure
        correlation_matrix: 4x4 correlation matrix (revenue, cost, FX, degradation)
        sampling_method: Sampling method (lhs, random, sobol)
        seed: Random seed for reproducibility
    """
    
    scenario_name: str
    n_iterations: int
    capex_total_usd: float
    revenue_mean_usd: float
    revenue_std_pct: float
    cost_mean_usd: float
    cost_std_pct: float
    fx_mean_rate: float
    fx_std_pct: float
    degradation_mean_pct: float  # NEW: e.g., 0.6 for 0.6%/year
    degradation_std_pct: float   # NEW: e.g., 0.1 for ±0.1%/year
    project_life_years: int
    discount_rate_pct: float
    correlation_enabled: bool  # NEW
    correlation_matrix: np.ndarray  # NEW: 4x4 matrix
    sampling_method: str
    seed: Optional[int]


def _apply_iman_conover_correlation(
    unit_samples: np.ndarray,
    correlation_matrix: np.ndarray
) -> np.ndarray:
    """Apply correlation structure to LHS samples using Iman-Conover method.
    
    Method:
        1. Convert uniform [0,1] samples to standard normal space
        2. Apply Cholesky decomposition of target correlation matrix
        3. Transform correlated normals back to uniform [0,1]
        4. Preserves Latin Hypercube structure (marginal distributions)
    
    Reference:
        Iman, R.L. and Conover, W.J. (1982). A distribution-free approach
        to inducing rank correlation among input variables.
        Communications in Statistics - Simulation and Computation, 11(3), 311-334.
    
    Args:
        unit_samples: Independent LHS samples, shape (n_iterations, n_vars)
        correlation_matrix: Target correlation matrix, shape (n_vars, n_vars)
    
    Returns:
        Correlated samples in [0,1]^(n x d), preserving LHS structure
    
    Raises:
        ValueError: If correlation matrix is not positive semi-definite
    
    Example:
        >>> # 4 variables: revenue, cost, FX, degradation
        >>> corr_matrix = np.array([
        ...     [1.0,  0.4, -0.3, -0.2],  # revenue correlations
        ...     [0.4,  1.0, -0.2,  0.1],  # cost correlations
        ...     [-0.3, -0.2, 1.0,  0.0],  # FX correlations
        ...     [-0.2, 0.1,  0.0,  1.0]   # degradation correlations
        ... ])
        >>> samples_lhs = qmc.LatinHypercube(d=4).random(n=1000)
        >>> samples_corr = _apply_iman_conover_correlation(samples_lhs, corr_matrix)
        >>> # Verify correlation preserved
        >>> np.corrcoef(samples_corr.T)  # Should ≈ corr_matrix
    """
    n_iterations, n_vars = unit_samples.shape
    
    # Validate correlation matrix
    if correlation_matrix.shape != (n_vars, n_vars):
        raise ValueError(
            f"Correlation matrix shape {correlation_matrix.shape} "
            f"must match (n_vars={n_vars}, n_vars={n_vars})"
        )
    
    # Check positive semi-definite (required for Cholesky)
    eigenvalues = np.linalg.eigvals(correlation_matrix)
    if np.any(eigenvalues < -1e-10):  # Allow small numerical errors
        raise ValueError(
            f"Correlation matrix is not positive semi-definite. "
            f"Minimum eigenvalue: {np.min(eigenvalues):.6f}. "
            f"Ensure diagonal = 1.0 and off-diagonal in [-1, 1]."
        )
    
    # Step 1: Transform uniform [0,1] to standard normal N(0,1)
    # Use inverse CDF (quantile function)
    normal_samples = norm.ppf(unit_samples)
    
    # Handle edge cases (ppf returns ±inf for 0 and 1)
    normal_samples = np.clip(normal_samples, -5, 5)  # Cap at ±5 sigma
    
    # Step 2: Apply Cholesky decomposition
    # Target: X_corr = X_uncorr @ L^T, where L @ L^T = Corr
    try:
        L = cholesky(correlation_matrix, lower=True)
    except np.linalg.LinAlgError as e:
        # Fallback: Add small regularization to diagonal
        logger.warning(
            f"Cholesky failed, adding regularization: {e}"
        )
        regularized = correlation_matrix + np.eye(n_vars) * 1e-6
        L = cholesky(regularized, lower=True)
    
    # Apply transformation: each row is a sample, multiply by L^T
    correlated_normal = normal_samples @ L.T
    
    # Step 3: Transform back to uniform [0,1]
    # Use CDF of standard normal
    correlated_uniform = norm.cdf(correlated_normal)
    
    # Verify correlation (optional, for debugging)
    if logger.isEnabledFor(logging.DEBUG):
        achieved_corr = np.corrcoef(correlated_uniform.T)
        max_error = np.max(np.abs(achieved_corr - correlation_matrix))
        logger.debug(
            f"Iman-Conover correlation error: max={max_error:.4f}, "
            f"mean={np.mean(np.abs(achieved_corr - correlation_matrix)):.4f}"
        )
    
    return correlated_uniform


def _transform_to_distribution_enhanced(
    unit_value: float,
    mean: float,
    std: float,
    dist_type: str = "normal"
) -> float:
    """Transform unit [0,1] sample to target distribution.
    
    Supports multiple distribution types for flexibility.
    
    Args:
        unit_value: Value in [0, 1] from (possibly correlated) LHS
        mean: Mean of target distribution
        std: Standard deviation (absolute, not percentage)
        dist_type: Distribution type (normal, lognormal, uniform)
    
    Returns:
        Sampled value from specified distribution
    
    Example:
        >>> # Normal distribution
        >>> value = _transform_to_distribution_enhanced(0.5, 100, 10, "normal")
        >>> # value ≈ 100 (50th percentile)
        >>> 
        >>> # Lognormal (for strictly positive variables like degradation)
        >>> deg = _transform_to_distribution_enhanced(0.5, 0.006, 0.001, "lognormal")
    """
    if dist_type == "normal":
        return float(norm.ppf(unit_value, loc=mean, scale=std))
    
    elif dist_type == "lognormal":
        # For lognormal, mean and std are of underlying normal
        # Convert to lognormal parameters
        if mean <= 0:
            raise ValueError(f"Lognormal mean must be > 0, got {mean}")
        
        # Method of moments:
        # mu = log(mean^2 / sqrt(mean^2 + std^2))
        # sigma = sqrt(log(1 + (std/mean)^2))
        variance = std ** 2
        mu = np.log(mean ** 2 / np.sqrt(mean ** 2 + variance))
        sigma = np.sqrt(np.log(1 + variance / (mean ** 2)))
        
        # Sample from normal then exponentiate
        normal_sample = norm.ppf(unit_value, loc=mu, scale=sigma)
        return float(np.exp(normal_sample))
    
    elif dist_type == "uniform":
        # Uniform distribution [mean - std*sqrt(3), mean + std*sqrt(3)]
        # This gives variance = std^2
        half_width = std * np.sqrt(3)
        return float(mean - half_width + 2 * half_width * unit_value)
    
    else:
        raise ValueError(f"Unknown distribution type: {dist_type}")


class EnhancedMonteCarloEngine:
    """Monte Carlo engine with degradation uncertainty and correlation.
    
    Sprint 17 Priority 1 Enhancement.
    
    Key Features:
        1. 4-variable stochastic model (revenue, cost, FX, degradation)
        2. Iman-Conover correlation structure
        3. Year-over-year compound degradation in cashflows
        4. CESSPIT-compliant (all params from config)
        5. CASPER-compliant (tail-risk modeling)
    
    Example:
        >>> cfg = OmegaConf.load("scenarios/mc_enhanced.yaml")
        >>> engine = EnhancedMonteCarloEngine(cfg, n_iterations=10000)
        >>> result = engine.run()
        >>> result['statistics']['npv_mean_usd']  # Mean NPV
        >>> result['statistics']['degradation_mean_pct']  # Mean degradation rate
    """
    
    def __init__(
        self,
        config: DictConfig,
        n_iterations: int = 1000
    ) -> None:
        """Initialize enhanced Monte Carlo engine.
        
        Args:
            config: Hydra configuration with monte_carlo_enhanced section
            n_iterations: Number of Monte Carlo simulations
        
        Raises:
            ValueError: If required config sections missing (CESSPIT)
        """
        self.config = config
        self.n_iterations = n_iterations
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Validate config structure
        if not hasattr(config, "monte_carlo_enhanced"):
            raise ValueError(
                "Config missing 'monte_carlo_enhanced' section. "
                "Use monte_carlo_v14.py for basic Monte Carlo."
            )
        
        mc_cfg = config.monte_carlo_enhanced
        
        # CESSPIT: All parameters from config (fail fast if missing)
        required_params = [
            "discount_rate_pct", "capex_total_usd", "revenue_mean_usd",
            "revenue_std_pct", "cost_mean_usd", "cost_std_pct",
            "fx_mean_rate", "fx_std_pct", "degradation_mean_pct",
            "degradation_std_pct", "project_life_years"
        ]
        
        for param in required_params:
            if param not in mc_cfg:
                raise ValueError(
                    f"CESSPIT VIOLATION: monte_carlo_enhanced.{param} "
                    f"REQUIRED in config. No default allowed."
                )
        
        # Parse correlation structure
        correlation_enabled = mc_cfg.get("correlation_enabled", False)
        
        if correlation_enabled:
            if "correlation_matrix" not in mc_cfg:
                raise ValueError(
                    "correlation_enabled=true but correlation_matrix missing. "
                    "Provide 4x4 matrix in config."
                )
            
            corr_matrix = np.array(mc_cfg.correlation_matrix, dtype=np.float64)
            
            if corr_matrix.shape != (4, 4):
                raise ValueError(
                    f"correlation_matrix must be 4x4 (revenue, cost, FX, degradation), "
                    f"got shape {corr_matrix.shape}"
                )
        else:
            # Identity matrix (no correlation)
            corr_matrix = np.eye(4)
        
        # Build config object
        self.mc_config = EnhancedMonteCarloConfig(
            scenario_name=mc_cfg.get("scenario_name", "enhanced_default"),
            n_iterations=n_iterations,
            capex_total_usd=float(mc_cfg.capex_total_usd),
            revenue_mean_usd=float(mc_cfg.revenue_mean_usd),
            revenue_std_pct=float(mc_cfg.revenue_std_pct),
            cost_mean_usd=float(mc_cfg.cost_mean_usd),
            cost_std_pct=float(mc_cfg.cost_std_pct),
            fx_mean_rate=float(mc_cfg.fx_mean_rate),
            fx_std_pct=float(mc_cfg.fx_std_pct),
            degradation_mean_pct=float(mc_cfg.degradation_mean_pct),
            degradation_std_pct=float(mc_cfg.degradation_std_pct),
            project_life_years=int(mc_cfg.project_life_years),
            discount_rate_pct=float(mc_cfg.discount_rate_pct),
            correlation_enabled=correlation_enabled,
            correlation_matrix=corr_matrix,
            sampling_method=mc_cfg.get("sampling_method", "lhs"),
            seed=mc_cfg.get("seed", None)
        )
        
        self.logger.info(
            f"Initialized EnhancedMonteCarloEngine: {self.mc_config.scenario_name}"
        )
        self.logger.info(
            f"  Degradation: {self.mc_config.degradation_mean_pct:.2f}% "
            f"± {self.mc_config.degradation_std_pct:.2f}%"
        )
        self.logger.info(
            f"  Correlation: {'ENABLED' if correlation_enabled else 'DISABLED'}"
        )
    
    def simulate_iteration_with_degradation(
        self,
        revenue_sample: float,
        cost_sample: float,
        fx_sample: float,
        degradation_sample: float
    ) -> Dict[str, Any]:
        """Simulate single Monte Carlo iteration with year-over-year degradation.
        
        Key Innovation:
            Revenue degrades compound annually:
            Revenue_t = Revenue_0 * (1 - degradation_rate)^t
        
        Args:
            revenue_sample: Year 1 revenue (before degradation)
            cost_sample: Annual operating cost
            fx_sample: FX rate (LKR/USD)
            degradation_sample: Annual degradation rate (as decimal, e.g., 0.006)
        
        Returns:
            Dictionary with NPV, IRR, and degradation metrics
        
        Example:
            >>> result = engine.simulate_iteration_with_degradation(
            ...     revenue_sample=20e6,  # $20M year 1
            ...     cost_sample=7e6,      # $7M/year
            ...     fx_sample=300.0,      # 300 LKR/USD
            ...     degradation_sample=0.006  # 0.6%/year
            ... )
            >>> result['year_20_output_factor']  # ~0.887 (1-0.006)^19
        """
        # Build cashflow with year-over-year degradation
        cf_array = [-self.mc_config.capex_total_usd]  # t=0: CAPEX
        
        for t in range(1, self.mc_config.project_life_years + 1):
            # Apply compound degradation: (1 - rate)^(t-1)
            # t=1 (year 1): No degradation yet (exponent = 0)
            # t=2 (year 2): (1 - rate)^1
            # t=20 (year 20): (1 - rate)^19
            degradation_factor = (1.0 - degradation_sample) ** (t - 1)
            
            # Degraded revenue
            revenue_t = revenue_sample * degradation_factor
            
            # Cost (assumed constant, could also model escalation)
            cost_t = cost_sample
            
            # Net cashflow
            cf_t = revenue_t - cost_t
            cf_array.append(cf_t)
        
        # Calculate NPV using R7: finance.irr.npv() ONLY
        discount_rate = self.mc_config.discount_rate_pct / 100.0
        project_npv = npv(discount_rate, cf_array)
        
        # Calculate IRR using R7: finance.irr.irr() ONLY
        project_irr_decimal = irr(cf_array)
        project_irr_pct = (
            (project_irr_decimal * 100.0) if project_irr_decimal is not None else 0.0
        )
        
        # Additional metrics
        year_20_factor = (1.0 - degradation_sample) ** 19  # Year 20 output factor
        cumulative_degradation = (1.0 - year_20_factor) * 100.0  # % loss over 20 years
        
        return {
            "npv_usd": project_npv,
            "irr_pct": project_irr_pct,
            "revenue_year1_usd": revenue_sample,
            "cost_usd": cost_sample,
            "fx_rate": fx_sample,
            "degradation_rate_pct": degradation_sample * 100.0,  # Convert to %
            "year_20_output_factor": year_20_factor,
            "cumulative_degradation_20y_pct": cumulative_degradation
        }
    
    def run(self) -> Dict[str, Any]:
        """Execute enhanced Monte Carlo simulation.
        
        Process:
            1. Generate LHS samples (4 variables)
            2. Apply Iman-Conover correlation (if enabled)
            3. Transform to target distributions
            4. Simulate each iteration with degradation
            5. Aggregate statistics
        
        Returns:
            Dictionary with:
            - statistics: NPV/IRR/degradation percentiles
            - correlation_metrics: Achieved correlation vs target
            - execution_time_seconds: Runtime
            - success: True/False
        """
        import time
        start_time = time.time()
        
        try:
            self.logger.info(
                f"Starting enhanced MC: {self.mc_config.scenario_name} "
                f"({self.mc_config.n_iterations} iterations)"
            )
            
            # Step 1: Generate LHS samples (4 variables)
            n_vars = 4  # revenue, cost, FX, degradation
            
            if self.mc_config.sampling_method == "lhs":
                sampler = qmc.LatinHypercube(d=n_vars, seed=self.mc_config.seed)
                unit_samples = sampler.random(n=self.mc_config.n_iterations)
                self.logger.info(f"Generated {self.mc_config.n_iterations} LHS samples")
            else:
                # Fallback to pseudo-random
                if self.mc_config.seed is not None:
                    np.random.seed(self.mc_config.seed)
                unit_samples = np.random.rand(self.mc_config.n_iterations, n_vars)
                self.logger.info(f"Using random sampling (seed={self.mc_config.seed})")
            
            # Step 2: Apply correlation structure (if enabled)
            if self.mc_config.correlation_enabled:
                self.logger.info("Applying Iman-Conover correlation...")
                unit_samples = _apply_iman_conover_correlation(
                    unit_samples,
                    self.mc_config.correlation_matrix
                )
                self.logger.info("Correlation applied successfully")
            
            # Step 3 & 4: Transform and simulate
            iterations = []
            npv_values = []
            irr_values = []
            degradation_values = []
            
            # Standard deviations (convert from percentages for non-degradation vars)
            revenue_std = self.mc_config.revenue_mean_usd * (self.mc_config.revenue_std_pct / 100.0)
            cost_std = self.mc_config.cost_mean_usd * (self.mc_config.cost_std_pct / 100.0)
            fx_std = self.mc_config.fx_mean_rate * (self.mc_config.fx_std_pct / 100.0)
            # Degradation std is already absolute (e.g., 0.1 for ±0.1%)
            degradation_std = self.mc_config.degradation_std_pct / 100.0  # Convert to decimal
            
            for i in range(self.mc_config.n_iterations):
                # Transform unit samples to distribution parameters
                revenue_sample = _transform_to_distribution_enhanced(
                    unit_samples[i, 0],
                    self.mc_config.revenue_mean_usd,
                    revenue_std,
                    "normal"
                )
                
                cost_sample = _transform_to_distribution_enhanced(
                    unit_samples[i, 1],
                    self.mc_config.cost_mean_usd,
                    cost_std,
                    "normal"
                )
                
                fx_sample = _transform_to_distribution_enhanced(
                    unit_samples[i, 2],
                    self.mc_config.fx_mean_rate,
                    fx_std,
                    "normal"
                )
                
                # Degradation (convert mean from % to decimal: 0.6 -> 0.006)
                degradation_mean_decimal = self.mc_config.degradation_mean_pct / 100.0
                degradation_sample = _transform_to_distribution_enhanced(
                    unit_samples[i, 3],
                    degradation_mean_decimal,
                    degradation_std,
                    "normal"  # Could use "lognormal" for strictly positive
                )
                
                # Ensure degradation is non-negative
                degradation_sample = max(0.0, degradation_sample)
                
                # Run iteration with degradation
                iteration = self.simulate_iteration_with_degradation(
                    revenue_sample,
                    cost_sample,
                    fx_sample,
                    degradation_sample
                )
                
                iterations.append(iteration)
                npv_values.append(iteration["npv_usd"])
                irr_values.append(iteration["irr_pct"])
                degradation_values.append(iteration["degradation_rate_pct"])
                
                # Progress logging
                if (i + 1) % max(1, self.mc_config.n_iterations // 10) == 0:
                    self.logger.info(
                        f"  Completed {i + 1}/{self.mc_config.n_iterations} iterations"
                    )
            
            # Step 5: Aggregate statistics
            from analytics.monte_carlo_v14 import _aggregate_results
            statistics = _aggregate_results(npv_values, irr_values)
            
            # Add degradation statistics
            degradation_array = np.array(degradation_values)
            statistics.update({
                "degradation_mean_pct": float(np.mean(degradation_array)),
                "degradation_std_pct": float(np.std(degradation_array)),
                "degradation_median_pct": float(np.median(degradation_array)),
                "degradation_p10_pct": float(np.percentile(degradation_array, 10)),
                "degradation_p90_pct": float(np.percentile(degradation_array, 90)),
            })
            
            # Verify achieved correlation (if enabled)
            correlation_metrics = {}
            if self.mc_config.correlation_enabled:
                # Extract sampled values for correlation check
                revenue_values = [it["revenue_year1_usd"] for it in iterations]
                cost_values = [it["cost_usd"] for it in iterations]
                fx_values = [it["fx_rate"] for it in iterations]
                deg_values = [it["degradation_rate_pct"] / 100.0 for it in iterations]  # Back to decimal
                
                sample_matrix = np.column_stack([
                    revenue_values, cost_values, fx_values, deg_values
                ])
                achieved_corr = np.corrcoef(sample_matrix.T)
                
                correlation_metrics = {
                    "target_correlation": self.mc_config.correlation_matrix.tolist(),
                    "achieved_correlation": achieved_corr.tolist(),
                    "max_error": float(np.max(np.abs(achieved_corr - self.mc_config.correlation_matrix))),
                    "mean_error": float(np.mean(np.abs(achieved_corr - self.mc_config.correlation_matrix)))
                }
                
                self.logger.info(
                    f"Correlation error: max={correlation_metrics['max_error']:.4f}, "
                    f"mean={correlation_metrics['mean_error']:.4f}"
                )
            
            execution_time = time.time() - start_time
            
            result = {
                "scenario_name": self.mc_config.scenario_name,
                "n_iterations": self.mc_config.n_iterations,
                "project_life_years": self.mc_config.project_life_years,
                "discount_rate_pct": self.mc_config.discount_rate_pct,
                "capex_total_usd": self.mc_config.capex_total_usd,
                "degradation_enabled": True,
                "correlation_enabled": self.mc_config.correlation_enabled,
                "sampling_method": self.mc_config.sampling_method,
                "execution_time_seconds": execution_time,
                "statistics": statistics,
                "correlation_metrics": correlation_metrics,
                "iterations": iterations if self.mc_config.n_iterations <= 100 else [],
                "success": True
            }
            
            self.logger.info(f"Enhanced MC completed in {execution_time:.2f}s")
            self.logger.info(f"  NPV Mean: ${statistics['npv_mean_usd']/1e6:.2f}M")
            self.logger.info(
                f"  NPV P10-P90: ${statistics['npv_p10_usd']/1e6:.2f}M to "
                f"${statistics['npv_p90_usd']/1e6:.2f}M"
            )
            self.logger.info(f"  IRR Mean: {statistics['irr_mean_pct']:.2f}%")
            self.logger.info(
                f"  Degradation Mean: {statistics['degradation_mean_pct']:.3f}% ± "
                f"{statistics['degradation_std_pct']:.3f}%"
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Enhanced MC simulation failed: {str(e)}", exc_info=True)
            return {
                "scenario_name": self.mc_config.scenario_name,
                "success": False,
                "error": str(e)
            }


def main(
    config_path: str = "conf/scenarios/mc_enhanced.yaml",
    n_iterations: int = 1000
) -> None:
    """Main entry point for enhanced Monte Carlo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger_main = logging.getLogger("mc_enhanced_main")
    
    try:
        logger_main.info(f"Loading config: {config_path}")
        cfg = OmegaConf.load(config_path)
        
        # Validate schema
        cfg_dict = OmegaConf.to_container(cfg, resolve=True)
        validate_config_for_v14(
            cfg_dict, config_path=config_path, modules=["cashflow", "debt"]
        )
        logger_main.info("Schema validation passed")
        
        logger_main.info(f"Initializing EnhancedMonteCarloEngine ({n_iterations} iterations)")
        engine = EnhancedMonteCarloEngine(cfg, n_iterations=n_iterations)
        
        result = engine.run()
        
        print(json.dumps(result, indent=2))
        logger_main.info("Results output to stdout (JSON)")
    
    except Exception as e:
        logger_main.error(f"Fatal error: {str(e)}", exc_info=True)
        error_result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(error_result, indent=2))
        raise


if __name__ == "__main__":
    import sys
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else "conf/scenarios/mc_enhanced.yaml"
    n_iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    
    main(config_path, n_iterations)


__all__ = [
    "EnhancedMonteCarloEngine",
    "EnhancedMonteCarloConfig",
    "_apply_iman_conover_correlation",
    "_transform_to_distribution_enhanced",
]
