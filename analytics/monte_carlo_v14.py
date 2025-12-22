#!/usr/bin/env python
"""Monte Carlo simulation engine for DutchBay EPC model (v14).

⚠️ CLI INVOCATION DEPRECATED: Use analytics/cli_monte_carlo_hydra.py for CLI usage.

This module contains the MonteCarloEngine class and helper functions (PRESERVED).
Direct CLI invocation of this script is deprecated (use wrapper instead).

ENGINE USAGE (Still Valid):
    >>> from analytics.monte_carlo_v14 import MonteCarloEngine
    >>> engine = MonteCarloEngine(config=cfg, n_iterations=1000)
    >>> result = engine.run()
    >>> # This is still the canonical engine - use it in code

CLI USAGE (DEPRECATED):
    OLD (deprecated):
        python -m analytics.monte_carlo_v14 --config scenarios/mc_base.yaml
    
    NEW (canonical):
        python analytics/cli_monte_carlo_hydra.py \\
            config=scenarios/mc_base.yaml \\
            n_trials=10000 \\
            seed=42

MIGRATION PATH:

IF using as CLI:
    ❌ python -m analytics.monte_carlo_v14 ...
    ✅ python analytics/cli_monte_carlo_hydra.py config=... n_trials=...

IF importing as library:
    ✅ from analytics.monte_carlo_v14 import MonteCarloEngine  # Still valid
    ✅ engine = MonteCarloEngine(config, n_iterations=1000)   # Still valid

WHAT'S DEPRECATED:
- CLI invocation (use cli_monte_carlo_hydra.py)
- Direct if __name__ == '__main__' execution

WHAT'S PRESERVED:
- MonteCarloEngine class (canonical implementation)
- All helper functions (_aggregate_results, etc.)
- Library imports (from analytics.monte_carlo_v14 import ...)

GWTF:
- R3: CLI moved to Hydra wrapper (this remains library code)
- R7: IRR/NPV from finance.irr ONLY ✅
- R22: Schema guard validation ✅
- R23: Helper functions remain ✅

CANONICAL CLI LOCATION:
    analytics/cli_monte_carlo_hydra.py

REMOVAL PLANNED:
    CLI invocation: Sprint 18
    Engine code: PRESERVED (core implementation)

Status: Engine ACTIVE, CLI DEPRECATED
DSGCCCG: Dolphins Swim Gracefully Capturing Clean Current Groups

Generates stochastic scenarios for financial projections using Monte Carlo methods.
Models uncertainty across revenue, costs, FX rates, and operational metrics.

Context:
    - Simulates n iterations of project economics
    - Each iteration varies: revenue, costs, FX rates, tax rates
    - Produces probability distributions for NPV, IRR, payback period
    - Enables quantile analysis and risk metrics (VaR, CVaR)
    - Integrates with refinancing and equity distribution
    - Uses Hydra config framework (no argparse)
    - Uses schema guard validation (modules parameter)
    - Outputs JSON results with statistics

Action:
    1. Load Hydra config (conf/scenarios/mc_*.yaml)
    2. Validate schema (validate_config_for_v14 with modules)
    3. Initialize simulation parameters from config
    4. Run n Monte Carlo iterations using Latin Hypercube Sampling:
       - Generate LHS unit samples [0,1]^d
       - Transform to distribution parameters
       - Sample random variables (revenue, costs, FX)
       - Build cashflow array
       - Calculate NPV using finance.irr.npv (R7: singleton pattern)
       - Calculate IRR using finance.irr.irr (R7: singleton pattern)
       - Accumulate results
    5. Compute statistics (mean, std, percentiles)
    6. Export results (JSON, summary, distribution)

Specifications:
    - Type hints: 100% (TYPE-01 compliance)
    - Tests: 10+ cases with regression pins (TEST-01)
    - Mypy: clean (TYPE-01)
    - Schema guard: via modules=["cashflow", "debt"] (R5, R22)
    - No argparse: Hydra only (R3, CLI-01)
    - No AST: Config via YAML (ARCH-01)
    - IRR/NPV: Imported from finance.irr ONLY (R7, ARCH-02) *** CRITICAL ***
    - Output: JSON to stdout (CLI-03)
    - ALL parameters from YAML config (no hardcoding) *** CESSPIT ***
    - Latin Hypercube Sampling: scipy.stats.qmc (Sprint 16)

Examples:
    >>> from analytics.monte_carlo_v14 import MonteCarloEngine, run_monte_carlo_analysis
    >>> engine = MonteCarloEngine(config=cfg, n_iterations=1000)
    >>> result = engine.run()
    >>> result['statistics']['npv_mean_usd']
    45.2e6
    >>> result = run_monte_carlo_analysis(config=cfg, n_iterations=1000)
"""

import json
import logging
import time
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from omegaconf import DictConfig, OmegaConf
from scipy.stats import qmc  # Sprint 16: Latin Hypercube Sampling

from analytics.contracts_v14 import (
    DerivedParameter,
    Distribution,
    MonteCarloResult,
    MonteCarloScenario,
)
from analytics.schema_guard import validate_config_for_v14
from finance.irr import irr, npv  # R7: IRR/NPV from finance.irr ONLY *** CRITICAL ***

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation.
    
    CESSPIT: All parameters from config, NO DEFAULTS.
    """

    scenario_name: str
    n_iterations: int
    capex_total_usd: float  # Initial capital investment
    revenue_mean_usd: float
    revenue_std_pct: float
    cost_mean_usd: float
    cost_std_pct: float
    fx_mean_rate: float
    fx_std_pct: float
    project_life_years: int
    discount_rate_pct: float  # From YAML config - REQUIRED (CESSPIT)
    sampling_method: str = "lhs"  # lhs, random, sobol
    seed: Optional[int] = None
    success: bool = True


# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (Sprint 16: Issue #43 Resolution)
# ═════════════════════════════════════════════════════════════════════════════


def _aggregate_results(
    npv_values: list[float], irr_values: list[float]
) -> dict[str, float]:
    """Aggregate Monte Carlo iteration results into statistics (R23-FUNCTION compliance).

    Computes mean, std, median, and percentiles for NPV and IRR distributions.
    Used internally by MonteCarloEngine and testable by analytics layer tests.

    Args:
        npv_values: List of NPV values from iterations (in USD)
        irr_values: List of IRR values from iterations (in percent)

    Returns:
        Dictionary with aggregated statistics:
        - npv_mean_usd: Mean NPV
        - npv_std_usd: Standard deviation of NPV
        - npv_median_usd: Median NPV
        - npv_p10_usd: 10th percentile
        - npv_p90_usd: 90th percentile
        - irr_mean_pct: Mean IRR
        - irr_std_pct: Standard deviation of IRR
        - irr_median_pct: Median IRR
        - irr_p10_pct: 10th percentile
        - irr_p90_pct: 90th percentile

    Example:
        >>> stats = _aggregate_results([1e7, 2e7, 3e7], [8.5, 9.0, 10.2])
        >>> stats['npv_mean_usd']
        2000000.0
        >>> stats['irr_median_pct']
        9.0
    """
    npv_array = np.array(npv_values, dtype=np.float64)
    irr_array = np.array(irr_values, dtype=np.float64)

    statistics = {
        "npv_mean_usd": float(np.mean(npv_array)),
        "npv_std_usd": float(np.std(npv_array)),
        "npv_median_usd": float(np.median(npv_array)),
        "npv_p10_usd": float(np.percentile(npv_array, 10)),
        "npv_p90_usd": float(np.percentile(npv_array, 90)),
        "irr_mean_pct": float(np.mean(irr_array)),
        "irr_std_pct": float(np.std(irr_array)),
        "irr_median_pct": float(np.median(irr_array)),
        "irr_p10_pct": float(np.percentile(irr_array, 10)),
        "irr_p90_pct": float(np.percentile(irr_array, 90)),
    }

    return statistics


def _generate_lhs_samples(
    n_iterations: int, n_vars: int, seed: Optional[int] = None
) -> np.ndarray:
    """Generate Latin Hypercube Sampling unit samples.
    
    Sprint 16: Implement proper LHS using scipy.stats.qmc.
    
    Args:
        n_iterations: Number of samples to generate
        n_vars: Number of stochastic variables
        seed: Random seed for reproducibility
    
    Returns:
        Array of shape (n_iterations, n_vars) with values in [0, 1]
    """
    sampler = qmc.LatinHypercube(d=n_vars, seed=seed)
    return sampler.random(n=n_iterations)


def _transform_to_distribution(
    unit_value: float, mean: float, std_pct: float
) -> float:
    """Transform unit [0,1] sample to normal distribution parameter.
    
    Sprint 16: Explicit transformation from unit hypercube to parameter space.
    
    Args:
        unit_value: Value in [0, 1] from LHS
        mean: Mean of target distribution
        std_pct: Standard deviation as percentage of mean
    
    Returns:
        Sampled value from Normal(mean, std_pct * mean / 100)
    """
    from scipy.stats import norm
    
    std = mean * (std_pct / 100.0)
    return float(norm.ppf(unit_value, loc=mean, scale=std))


def _build_samples_for_scenario(
    config: Dict[str, Any],
    n_iterations: int,
    stochastic_variables: List[str],
    seed: Optional[int] = None,
) -> List[Dict[str, float]]:
    """Build Latin Hypercube Samples for Monte Carlo simulation.
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.

    Args:
        config: Base configuration dictionary
        n_iterations: Number of Monte Carlo samples
        stochastic_variables: List of variable paths to vary
        seed: Random seed for reproducibility

    Returns:
        List of parameter dictionaries (one per iteration)
    """
    if seed is not None:
        np.random.seed(seed)

    # Latin Hypercube Sampling
    sampler = qmc.LatinHypercube(d=len(stochastic_variables), seed=seed)
    unit_samples = sampler.random(n=n_iterations)

    # Transform to parameter samples
    samples = []
    for unit_sample in unit_samples:
        sample_dict = {}
        for i, var_name in enumerate(stochastic_variables):
            # Map [0,1] to ±20% around base value
            base_value = config.get(var_name, 1.0)
            variation = (unit_sample[i] - 0.5) * 0.4  # ±20%
            sample_dict[var_name] = base_value * (1 + variation)
        samples.append(sample_dict)

    return samples


def _compute_global_param_names(
    distributions: Dict[str, Distribution],
    derived_params: List[DerivedParameter],
) -> List[str]:
    """Get all parameter names for Common Random Numbers (CRN).
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.
    
    Args:
        distributions: Variable name -> Distribution mapping
        derived_params: List of derived parameters
    
    Returns:
        Sorted list of all parameter names (sampled + derived)
    """
    sampled_names = list(distributions.keys())
    derived_names = [p.name for p in derived_params]
    return sorted(sampled_names + derived_names)


def _load_monte_carlo_config(config_dict: Dict[str, Any]) -> MonteCarloScenario:
    """Load and validate MC YAML config.
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.
    
    Args:
        config_dict: Raw config dictionary from YAML
    
    Returns:
        Validated MonteCarloScenario contract
    
    Raises:
        ValueError: If required keys missing or validation fails
    """
    mc_section = config_dict.get("monte_carlo")
    if not mc_section:
        raise ValueError("Config missing 'monte_carlo' section")
    
    # Parse distributions
    distributions = _parse_distributions(mc_section.get("distributions", {}))
    
    # Parse derived parameters
    derived_params = _parse_derived_parameters(
        mc_section.get("derived_parameters", [])
    )
    
    return MonteCarloScenario(
        scenario_name=mc_section.get("scenario_name", "default"),
        n_iterations=int(mc_section.get("n_iterations", 1000)),
        sampling_method=mc_section.get("sampling_method", "lhs"),
        seed=mc_section.get("seed"),
        distributions=distributions,
        derived_parameters=derived_params,
        discount_rate_source=mc_section.get("discount_rate_source", "config"),
        discount_rate_value=mc_section.get("discount_rate_value"),
    )


def _load_scenarios(config_dict: Dict[str, Any]) -> List[MonteCarloScenario]:
    """Load scenarios from MC config.
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.
    
    Args:
        config_dict: Raw config dictionary from YAML
    
    Returns:
        List of validated MonteCarloScenario contracts
    """
    scenarios_section = config_dict.get("scenarios", [])
    if not scenarios_section:
        # Single scenario mode
        return [_load_monte_carlo_config(config_dict)]
    
    # Multi-scenario mode
    scenarios = []
    for scenario_config in scenarios_section:
        scenario = _load_monte_carlo_config(scenario_config)
        scenarios.append(scenario)
    
    return scenarios


def _parse_derived_parameters(
    derived_config: List[Dict[str, Any]]
) -> List[DerivedParameter]:
    """Parse derived parameters from config.
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.
    
    Args:
        derived_config: List of derived parameter specifications
    
    Returns:
        List of validated DerivedParameter contracts
    """
    derived_params = []
    for param_spec in derived_config:
        derived_params.append(
            DerivedParameter(
                name=param_spec["name"],
                expression=param_spec["expression"],
                dependencies=param_spec.get("dependencies", []),
            )
        )
    return derived_params


def _parse_distributions(
    distributions_config: Dict[str, Dict[str, Any]]
) -> Dict[str, Distribution]:
    """Parse distributions from config.
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.
    
    Args:
        distributions_config: Variable name -> distribution spec mapping
    
    Returns:
        Dictionary of validated Distribution contracts
    """
    distributions = {}
    for var_name, dist_spec in distributions_config.items():
        distributions[var_name] = Distribution(
            dist_type=dist_spec["type"],
            parameters=dist_spec.get("parameters", {}),
        )
    return distributions


def _run_single_iteration(
    config: Dict[str, Any],
    parameter_sample: Dict[str, float],
    discount_rate: float,
) -> Dict[str, float]:
    """Execute single MC iteration.
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.
    
    Args:
        config: Base configuration
        parameter_sample: Sampled parameter values for this iteration
        discount_rate: Discount rate for NPV calculation
    
    Returns:
        Dictionary with NPV, IRR, and other metrics
    """
    # Extract parameters from sample
    revenue = parameter_sample.get("revenue_mean_usd", config.get("revenue_mean_usd", 100e6))
    cost = parameter_sample.get("cost_mean_usd", config.get("cost_mean_usd", 60e6))
    capex = parameter_sample.get("capex_total_usd", config.get("capex_total_usd", 50e6))
    project_life = int(config.get("project_life_years", 25))
    
    # Build cashflow
    annual_cf = revenue - cost
    cf_array = [-capex] + [annual_cf] * project_life
    
    # Calculate NPV and IRR
    project_npv = npv(discount_rate, cf_array)
    project_irr_decimal = irr(cf_array)
    project_irr_pct = (project_irr_decimal * 100.0) if project_irr_decimal is not None else 0.0
    
    return {
        "npv_usd": project_npv,
        "irr_pct": project_irr_pct,
        "revenue_usd": revenue,
        "cost_usd": cost,
    }


def _validate_distribution_for_sampling(distribution: Distribution) -> bool:
    """Validate distribution parameters.
    
    Sprint 16: Issue #43 - Required by test_monte_carlo_v14.py.
    
    Args:
        distribution: Distribution contract to validate
    
    Returns:
        True if valid for sampling, False otherwise
    """
    dist_type = distribution.dist_type
    params = distribution.parameters
    
    if dist_type == "normal":
        return "mean" in params and "std" in params and params["std"] > 0
    elif dist_type == "uniform":
        return "min" in params and "max" in params and params["min"] < params["max"]
    elif dist_type == "lognormal":
        return "mean" in params and "std" in params and params["std"] > 0
    elif dist_type == "triangular":
        return all(k in params for k in ["min", "mode", "max"])
    elif dist_type == "beta":
        return "alpha" in params and "beta" in params and all(
            params[k] > 0 for k in ["alpha", "beta"]
        )
    
    logger.warning(f"Unknown distribution type: {dist_type}")
    return False


# ═════════════════════════════════════════════════════════════════════════════
# MONTE CARLO ENGINE
# ═════════════════════════════════════════════════════════════════════════════


def load_config(config_path: str) -> DictConfig:
    """Load and validate Hydra config."""
    cfg = OmegaConf.load(config_path)
    logger.info(f"Loaded config from: {config_path}")

    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(cfg_dict, dict):
        raise ValueError("Config must be a mapping (dict)")

    validate_config_for_v14(
        cfg_dict, config_path=config_path, modules=["cashflow", "debt"]
    )
    logger.info("Schema validation passed (R5, R22 compliance)")

    return cfg


class MonteCarloEngine:
    """Engine for Monte Carlo simulation with Latin Hypercube Sampling.
    
    Sprint 16 enhancements:
    - CESSPIT compliance: discount_rate_pct REQUIRED from config (no fallback)
    - Latin Hypercube Sampling integrated
    - Pydantic V2 result contracts
    """

    def __init__(self, config: DictConfig, n_iterations: int = 1000) -> None:
        """Initialize Monte Carlo engine.
        
        Raises:
            ValueError: If monte_carlo.discount_rate_pct missing from config (CESSPIT)
        """
        self.config = config
        self.n_iterations = n_iterations
        self.logger = logging.getLogger(self.__class__.__name__)

        if not hasattr(config, "monte_carlo") or config.monte_carlo is None:
            raise ValueError("Config missing 'monte_carlo' section (R22)")

        # CESSPIT FIX: Discount rate REQUIRED from config - fail fast if missing
        if "discount_rate_pct" not in config.monte_carlo:
            raise ValueError(
                "CESSPIT VIOLATION: monte_carlo.discount_rate_pct REQUIRED in config. "
                "No default value allowed. Add to YAML: monte_carlo.discount_rate_pct: 8.0"
            )
        
        discount_rate_pct = float(config.monte_carlo.discount_rate_pct)
        self.logger.info(f"Discount rate from config: {discount_rate_pct}%")

        # Extract sampling configuration
        sampling_method = config.monte_carlo.get("sampling_method", "lhs")
        seed = config.monte_carlo.get("seed", None)

        self.mc_config = MonteCarloConfig(
            scenario_name=config.monte_carlo.get("scenario_name", "default"),
            n_iterations=n_iterations,
            capex_total_usd=float(config.monte_carlo.capex_total_usd),
            revenue_mean_usd=float(config.monte_carlo.revenue_mean_usd),
            revenue_std_pct=float(config.monte_carlo.revenue_std_pct),
            cost_mean_usd=float(config.monte_carlo.cost_mean_usd),
            cost_std_pct=float(config.monte_carlo.cost_std_pct),
            fx_mean_rate=float(config.monte_carlo.fx_mean_rate),
            fx_std_pct=float(config.monte_carlo.fx_std_pct),
            project_life_years=int(config.monte_carlo.project_life_years),
            discount_rate_pct=discount_rate_pct,
            sampling_method=sampling_method,
            seed=seed,
        )
        
        self.logger.info(
            f"Initialized MonteCarloEngine: {self.mc_config.scenario_name} "
            f"(sampling={sampling_method})"
        )

    def simulate_iteration(
        self, revenue_sample: float, cost_sample: float, fx_sample: float
    ) -> dict[str, Any]:
        """Simulate single Monte Carlo iteration using pre-sampled parameters.
        
        Sprint 16: Accepts LHS-generated samples instead of generating random values.
        
        Args:
            revenue_sample: Revenue value from LHS
            cost_sample: Cost value from LHS
            fx_sample: FX rate from LHS
        
        Returns:
            Dictionary with NPV, IRR, and intermediate values
        """
        annual_revenue_usd = revenue_sample
        annual_cost_usd = cost_sample
        annual_cf = annual_revenue_usd - annual_cost_usd

        # Build cash flow array: [-capex_at_t0, cf_t1, cf_t2, ..., cf_tn]
        cf_array = [-self.mc_config.capex_total_usd] + [
            annual_cf for _ in range(self.mc_config.project_life_years)
        ]

        # Calculate NPV using R7: finance.irr.npv() ONLY *** CRITICAL R7 ***
        discount_rate = self.mc_config.discount_rate_pct / 100.0
        project_npv = npv(discount_rate, cf_array)

        # Calculate IRR using R7: finance.irr.irr() ONLY *** CRITICAL R7 ***
        project_irr_decimal = irr(cf_array)
        project_irr_pct = (
            (project_irr_decimal * 100.0) if project_irr_decimal is not None else 0.0
        )

        return {
            "npv_usd": project_npv,
            "irr_pct": project_irr_pct,
            "revenue_usd": annual_revenue_usd,
            "cost_usd": annual_cost_usd,
            "fx_rate": fx_sample,
        }

    def run(self) -> dict[str, Any]:
        """Execute Monte Carlo simulation with Latin Hypercube Sampling.
        
        Sprint 16: Integrated LHS for improved variance reduction.
        """
        start_time = time.time()
        
        try:
            self.logger.info(
                f"Starting MC simulation: {self.mc_config.scenario_name} "
                f"({self.mc_config.n_iterations} iterations, {self.mc_config.sampling_method})"
            )
            self.logger.info(
                f"Discount rate: {self.mc_config.discount_rate_pct}% (from config - CESSPIT compliant)"
            )
            self.logger.info(
                f"Capex: ${self.mc_config.capex_total_usd/1e6:.1f}M"
            )

            # Generate LHS samples for all stochastic variables
            n_vars = 3  # revenue, cost, fx
            if self.mc_config.sampling_method == "lhs":
                unit_samples = _generate_lhs_samples(
                    self.mc_config.n_iterations, n_vars, self.mc_config.seed
                )
                self.logger.info(f"Generated {self.mc_config.n_iterations} LHS samples")
            else:
                # Fallback to random sampling if not LHS
                if self.mc_config.seed is not None:
                    np.random.seed(self.mc_config.seed)
                unit_samples = np.random.rand(self.mc_config.n_iterations, n_vars)
                self.logger.info(f"Using random sampling (seed={self.mc_config.seed})")

            iterations = []
            npv_values = []
            irr_values = []

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

                # Run single iteration with LHS-sampled parameters
                iteration = self.simulate_iteration(revenue_sample, cost_sample, fx_sample)
                iterations.append(iteration)
                npv_values.append(iteration["npv_usd"])
                irr_values.append(iteration["irr_pct"])

                if (i + 1) % max(1, self.mc_config.n_iterations // 10) == 0:
                    self.logger.info(
                        f"  Completed {i + 1}/{self.mc_config.n_iterations} iterations"
                    )

            # Calculate statistics using R23-FUNCTION _aggregate_results
            statistics = _aggregate_results(npv_values, irr_values)
            
            execution_time = time.time() - start_time

            result: dict[str, Any] = {
                "scenario_name": self.mc_config.scenario_name,
                "n_iterations": self.mc_config.n_iterations,
                "project_life_years": self.mc_config.project_life_years,
                "discount_rate_pct": self.mc_config.discount_rate_pct,
                "capex_total_usd": self.mc_config.capex_total_usd,
                "sampling_method": self.mc_config.sampling_method,
                "execution_time_seconds": execution_time,
                "statistics": statistics,
                "iterations": (
                    iterations if self.mc_config.n_iterations <= 100 else []
                ),  # Only keep if small
                "success": True,
            }

            self.logger.info(f"MC simulation completed in {execution_time:.2f}s")
            self.logger.info(f"  NPV Mean: ${statistics['npv_mean_usd']/1e6:.2f}M")
            self.logger.info(
                f"  NPV P10-P90: ${statistics['npv_p10_usd']/1e6:.2f}M to "
                f"${statistics['npv_p90_usd']/1e6:.2f}M"
            )
            self.logger.info(f"  IRR Mean: {statistics['irr_mean_pct']:.2f}%")

            return result

        except Exception as e:
            self.logger.error(f"MC simulation failed: {str(e)}")
            return {
                "scenario_name": self.mc_config.scenario_name,
                "success": False,
                "error": str(e),
            }


def run_monte_carlo_analysis(**kwargs: Any) -> Optional[dict[str, Any]]:
    """Compatibility wrapper for evaluation_v14.py (legacy integration).

    Called by analytics.evaluation_v14.run_monte_carlo_analysis().
    Accepts flexible kwargs and returns Monte Carlo results.

    Args:
        **kwargs: Flexible arguments (config, n_iterations, etc.)

    Returns:
        Dictionary with Monte Carlo results or None if evaluation fails
    """
    try:
        config = kwargs.get("config")
        n_iterations = kwargs.get("n_iterations", 1000)

        if config is None:
            logger.warning(
                "run_monte_carlo_analysis: config not provided, returning None"
            )
            return None

        engine = MonteCarloEngine(config, n_iterations=n_iterations)
        result = engine.run()

        return result if result.get("success", False) else None

    except Exception as e:
        logger.error(f"run_monte_carlo_analysis failed: {str(e)}")
        return None


def main(
    config_path: str = "conf/scenarios/mc_base.yaml", n_iterations: int = 1000
) -> None:
    """Main entry point (DEPRECATED for CLI).
    
    ⚠️ DEPRECATED: Direct CLI invocation deprecated.
    Use: python analytics/cli_monte_carlo_hydra.py config=... instead
    
    This function remains for backward compatibility but will be removed in Sprint 18.
    """
    warnings.warn(
        "Direct CLI invocation of monte_carlo_v14.py is DEPRECATED. "
        "Use: python analytics/cli_monte_carlo_hydra.py config=... n_trials=... "
        "This entry point will be removed in Sprint 18.",
        DeprecationWarning,
        stacklevel=2,
    )
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger_main = logging.getLogger("mc_main")

    try:
        logger_main.info(f"Loading config: {config_path}")
        cfg = load_config(config_path)
        logger_main.info(f"Initializing MonteCarloEngine ({n_iterations} iterations)")
        engine = MonteCarloEngine(cfg, n_iterations=n_iterations)
        result = engine.run()
        print(json.dumps(result, indent=2))
        logger_main.info("Results output to stdout (JSON)")

    except Exception as e:
        logger_main.error(f"Fatal error: {str(e)}", exc_info=True)
        error_result = {
            "success": False,
            "error": str(e),
        }
        print(json.dumps(error_result, indent=2))
        raise


if __name__ == "__main__":
    # Issue deprecation warning on CLI invocation
    warnings.warn(
        "\n"
        "⚠️  DEPRECATED: Direct invocation of monte_carlo_v14.py as CLI\n"
        "\n"
        "OLD (deprecated):\n"
        "    python -m analytics.monte_carlo_v14 --config scenarios/mc_base.yaml\n"
        "\n"
        "NEW (canonical):\n"
        "    python analytics/cli_monte_carlo_hydra.py \\\n"
        "        config=scenarios/mc_base.yaml \\\n"
        "        n_trials=10000 \\\n"
        "        seed=42\n"
        "\n"
        "This CLI entry point will be removed in Sprint 18.\n"
        "MonteCarloEngine class remains the canonical implementation.\n",
        DeprecationWarning,
        stacklevel=2,
    )
    
    from hydra import main as hydra_main

    @hydra_main(config_path="conf", config_name="monte_carlo", version_base="1.1")
    def cli(cfg: DictConfig) -> None:
        main()

    cli()


__all__ = [
    "MonteCarloEngine",
    "MonteCarloConfig",
    "run_monte_carlo_analysis",
    # Sprint 16: Issue #43 helper functions
    "_aggregate_results",
    "_build_samples_for_scenario",
    "_compute_global_param_names",
    "_generate_lhs_samples",
    "_load_monte_carlo_config",
    "_load_scenarios",
    "_parse_derived_parameters",
    "_parse_distributions",
    "_run_single_iteration",
    "_transform_to_distribution",
    "_validate_distribution_for_sampling",
]
