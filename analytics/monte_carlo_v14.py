"""Monte Carlo risk analysis coordinator with flexible parameter system.

This module is a COORDINATOR ONLY - it does not reimplement finance math.

Architecture:
- Loads parameter distributions and scenarios from YAML
- Generates samples using Latin Hypercube Sampling (LHS) for efficiency
- Calls evaluate_with_overrides() gateway for each iteration
- Handles derived parameters via solver registry
- Aggregates results into statistical summaries
- NO direct imports of finance.irr or finance.wacc_v14

Frozen Surfaces Used:
- analytics.contracts_v14 (Distribution, MonteCarloResult, etc.)
- analytics.evaluate_scenario (evaluate_with_overrides gateway)
- analytics.parameter_solvers (solver registry for derived params)
- constants (MONTE_CARLO_ITERATIONS)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import warnings

import numpy as np
import yaml
from SALib.sample import latin as lhs
import multiprocess as mp
from pydantic import ValidationError

from analytics.contracts_v14 import (
    Distribution,
    DerivedParameter,
    MonteCarloResult,
    MonteCarloScenario,
)
from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.parameter_solvers import get_solver
from constants import MONTE_CARLO_ITERATIONS

logger = logging.getLogger(__name__)

# Suppress numpy warnings during parallel execution
warnings.filterwarnings('ignore', category=RuntimeWarning)


def run_monte_carlo_analysis(
    base_config_path: str,
    scenario_config_path: str = "config/monte_carlo_defaults.yaml",
    scenario_name: str | None = None,
    n_iterations: int | None = None,
    random_seed: int | None = None,
    parallel_workers: int | None = None
) -> dict[str, MonteCarloResult]:
    """
    Run Monte Carlo simulation with flexible parameter system.
    
    Supports:
    - Standard parameters (direct config overrides with distributions)
    - Derived parameters (calculated from target constraints)
    - Multiple scenarios (comparative risk analysis)
    - Parallel execution for speed
    - Graceful error handling (isolated iteration failures)
    
    Args:
        base_config_path: Path to base scenario YAML
        scenario_config_path: Path to Monte Carlo configuration YAML
        scenario_name: Specific scenario to run (None = all enabled scenarios)
        n_iterations: Override default iteration count
        random_seed: Override default random seed for reproducibility
        parallel_workers: Number of CPU cores (None = auto-detect)
    
    Returns:
        Dict mapping scenario names to MonteCarloResult objects
    
    Raises:
        FileNotFoundError: If config files not found
        ValidationError: If MC configuration invalid
    
    Example:
        >>> results = run_monte_carlo_analysis(
        ...     "scenarios/dutchbay_master_config_v14.yaml",
        ...     scenario_name="base_case",
        ...     n_iterations=1000
        ... )
        >>> base_result = results["base_case"]
        >>> print(f"P50 IRR: {base_result.project_irr_p50:.2%}")
    """
    logger.info(f"Starting Monte Carlo analysis: {base_config_path}")
    
    # Load Monte Carlo configuration
    mc_config = _load_monte_carlo_config(scenario_config_path)
    
    # Override simulation settings if provided
    iterations = n_iterations or mc_config["simulation"]["iterations"]
    seed = random_seed if random_seed is not None else mc_config["simulation"].get("random_seed")
    workers = parallel_workers or mc_config["simulation"].get("parallel_workers") or mp.cpu_count()
    
    logger.info(f"Simulation: {iterations} iterations, seed={seed}, workers={workers}")
    
    # Load scenarios
    scenarios = _load_scenarios(mc_config, scenario_name)
    logger.info(f"Loaded {len(scenarios)} scenario(s) to run")
    
    # Run each scenario
    results = {}
    for scenario in scenarios:
        logger.info(f"Running scenario: {scenario.name}")
        
        try:
            result = _run_single_scenario(
                base_config_path=base_config_path,
                scenario=scenario,
                iterations=iterations,
                random_seed=seed,
                parallel_workers=workers
            )
            results[scenario.name] = result
            
            logger.info(
                f"  Completed {scenario.name}: "
                f"P50 IRR={result.project_irr_p50:.2%}, "
                f"Success rate={result.success_rate():.1f}%"
            )
            
        except Exception as e:
            logger.error(f"  Failed scenario {scenario.name}: {e}")
            continue
    
    logger.info(f"Monte Carlo analysis complete: {len(results)} scenario(s)")
    return results


def _load_monte_carlo_config(config_path: str) -> dict[str, Any]:
    """
    Load and validate Monte Carlo configuration from YAML.
    
    Args:
        config_path: Path to monte_carlo_defaults.yaml
    
    Returns:
        Validated configuration dict
    
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If YAML structure invalid
    """
    yaml_file = Path(config_path)
    if not yaml_file.exists():
        raise FileNotFoundError(f"Monte Carlo config not found: {config_path}")
    
    with open(yaml_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Validate required sections
    required = ["simulation", "standard_parameters"]
    missing = [s for s in required if s not in config]
    if missing:
        raise ValueError(f"Monte Carlo config missing required sections: {missing}")
    
    logger.info(f"Loaded Monte Carlo config from {config_path}")
    return config


def _load_scenarios(
    mc_config: dict[str, Any],
    scenario_name: str | None
) -> list[MonteCarloScenario]:
    """
    Load scenario configurations from MC config.
    
    Args:
        mc_config: Full Monte Carlo configuration dict
        scenario_name: Specific scenario to load (None = all enabled)
    
    Returns:
        List of MonteCarloScenario objects
    
    Raises:
        ValueError: If scenario_name specified but not found
    """
    scenarios_config = mc_config.get("scenarios", [])
    
    # If no scenarios defined, create default from standard parameters
    if not scenarios_config:
        logger.info("No scenarios defined, using default from standard parameters")
        standard_params = _parse_distributions(mc_config["standard_parameters"])
        derived_params = _parse_derived_parameters(mc_config.get("derived_parameters", []))
        
        return [MonteCarloScenario(
            name="default",
            description="Default scenario from standard parameters",
            standard_parameters=standard_params,
            derived_parameters=derived_params,
            enabled=True
        )]
    
    # Parse scenarios
    scenarios = []
    for scenario_dict in scenarios_config:
        # Skip disabled scenarios
        if not scenario_dict.get("enabled", True):
            continue
        
        # Filter by name if specified
        if scenario_name and scenario_dict["name"] != scenario_name:
            continue
        
        # Parse parameters (apply overrides if present)
        standard_params = _parse_distributions(
            scenario_dict.get("parameter_overrides", {}).get(
                "standard_parameters",
                mc_config["standard_parameters"]
            )
        )
        
        derived_params = _parse_derived_parameters(
            scenario_dict.get("parameter_overrides", {}).get(
                "derived_parameters",
                mc_config.get("derived_parameters", [])
            )
        )
        
        scenario = MonteCarloScenario(
            name=scenario_dict["name"],
            description=scenario_dict.get("description", ""),
            standard_parameters=standard_params,
            derived_parameters=derived_params,
            enabled=True
        )
        scenarios.append(scenario)
    
    if scenario_name and not scenarios:
        raise ValueError(f"Scenario '{scenario_name}' not found or disabled")
    
    return scenarios


def _parse_distributions(params_config: list[dict]) -> list[Distribution]:
    """
    Parse distribution configurations into Distribution objects.
    
    Args:
        params_config: List of parameter dicts from YAML
    
    Returns:
        List of validated Distribution objects
    
    Raises:
        ValidationError: If any distribution invalid
    """
    distributions = []
    for param_dict in params_config:
        try:
            dist = Distribution(**param_dict)
            distributions.append(dist)
        except (ValidationError, ValueError) as e:
            logger.error(f"Invalid distribution: {param_dict}")
            raise ValueError(f"Distribution validation failed: {e}") from e
    
    return distributions


def _parse_derived_parameters(params_config: list[dict]) -> list[DerivedParameter]:
    """
    Parse derived parameter configurations into DerivedParameter objects.
    
    Args:
        params_config: List of derived parameter dicts from YAML
    
    Returns:
        List of validated DerivedParameter objects (only enabled ones)
    
    Raises:
        ValidationError: If any derived parameter invalid
    """
    derived_params = []
    for param_dict in params_config:
        # Skip disabled derived parameters
        if not param_dict.get("enabled", True):
            continue
        
        try:
            # Parse target distribution
            target_dist = Distribution(**param_dict["target_distribution"])
            
            derived = DerivedParameter(
                variable_name=param_dict["variable_name"],
                derive_from=param_dict["derive_from"],
                target_distribution=target_dist,
                solver_config=param_dict["solver_config"],
                enabled=True,
                description=param_dict.get("description", "")
            )
            derived_params.append(derived)
            
        except (ValidationError, ValueError, KeyError) as e:
            logger.error(f"Invalid derived parameter: {param_dict}")
            raise ValueError(f"Derived parameter validation failed: {e}") from e
    
    return derived_params


def _run_single_scenario(
    base_config_path: str,
    scenario: MonteCarloScenario,
    iterations: int,
    random_seed: int | None,
    parallel_workers: int
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for a single scenario.
    
    Args:
        base_config_path: Path to base scenario YAML
        scenario: MonteCarloScenario configuration
        iterations: Number of MC iterations
        random_seed: Random seed for reproducibility
        parallel_workers: Number of parallel processes
    
    Returns:
        MonteCarloResult with statistical summary
    """
    # Generate samples using Latin Hypercube Sampling
    logger.info("Generating LHS samples...")
    samples = _generate_lhs_samples(
        scenario.standard_parameters,
        scenario.derived_parameters,
        iterations,
        random_seed
    )
    
    logger.info(f"Running {iterations} iterations with {parallel_workers} workers...")
    
    # Run iterations in parallel
    if parallel_workers > 1:
        results = _run_parallel_iterations(
            base_config_path,
            scenario,
            samples,
            parallel_workers
        )
    else:
        results = _run_serial_iterations(
            base_config_path,
            scenario,
            samples
        )
    
    # Aggregate results
    return _aggregate_results(results, iterations, scenario.name)

def _generate_lhs_samples(
    standard_params: list[Distribution],
    derived_params: list[DerivedParameter],
    n_samples: int,
    random_seed: int | None
) -> list[dict[str, Any]]:
    
    """
    Generate Latin Hypercube Samples for Monte Carlo iteration.
    
    LHS provides better coverage of parameter space than pure random
    sampling, requiring fewer iterations for same accuracy.
    
    Args:
        standard_params: List of standard parameter distributions
        derived_params: List of derived parameter configs
        n_samples: Number of samples to generate
        random_seed: Random seed for reproducibility
    
    Returns:
        List of dicts, each containing sampled parameter values
    """
    if random_seed is not None:
        np.random.seed(random_seed)
    
    samples = []
    
    # Generate LHS samples for standard parameters
    if standard_params:
        # Create problem definition for SALib
        problem = {
            'num_vars': len(standard_params),
            'names': [p.variable_name for p in standard_params],
            'bounds': [[0, 1]] * len(standard_params)  # Unit hypercube
        }
        
        # Generate LHS samples in [0, 1] unit hypercube
        unit_samples = lhs.sample(problem, n_samples, seed=random_seed)
        
        # Transform from [0, 1] to actual parameter distributions
        for i in range(n_samples):
            sample = {}
            
            for j, param in enumerate(standard_params):
                unit_value = unit_samples[i, j]
                actual_value = _transform_to_distribution(unit_value, param)
                sample[param.variable_name] = actual_value
            
            samples.append(sample)
    else:
        # No standard parameters, create empty samples
        samples = [{} for _ in range(n_samples)]
    
    # Generate samples for derived parameter targets
    for derived_param in derived_params:
        target_dist = derived_param.target_distribution
        
        for i in range(n_samples):
            # Sample from target distribution
            unit_value = np.random.uniform(0, 1)
            target_value = _transform_to_distribution(unit_value, target_dist)
            
            # Store as "_target_{variable_name}"
            target_key = f"_target_{derived_param.variable_name}"
            samples[i][target_key] = target_value
    
    logger.info(f"Generated {len(samples)} LHS samples")
    return samples


def _transform_to_distribution(
    unit_value: float,
    distribution: Distribution
) -> float:
    """
    Transform unit hypercube value [0, 1] to actual distribution.
    
    Args:
        unit_value: Value in [0, 1] from LHS
        distribution: Target distribution specification
    
    Returns:
        Transformed value from specified distribution
    """
    if distribution.dist_type == "normal":
        # Normal distribution: inverse CDF
        from scipy.stats import norm
        return norm.ppf(unit_value, loc=distribution.mean, scale=distribution.std)
    
    elif distribution.dist_type == "lognormal":
        # Lognormal distribution: inverse CDF
        from scipy.stats import lognorm
        # lognorm parameterization: s=std, scale=exp(mean)
        return lognorm.ppf(unit_value, s=distribution.std, scale=np.exp(distribution.mean))
    
    elif distribution.dist_type == "triangular":
        # Triangular distribution: inverse CDF
        from scipy.stats import triang
        # triang parameterization: c = (mode - min) / (max - min)
        c = (distribution.mode - distribution.min_val) / (distribution.max_val - distribution.min_val)
        return triang.ppf(
            unit_value,
            c,
            loc=distribution.min_val,
            scale=distribution.max_val - distribution.min_val
        )
    
    elif distribution.dist_type == "uniform":
        # Uniform distribution: simple linear transform
        return distribution.min_val + unit_value * (distribution.max_val - distribution.min_val)
    
    else:
        raise ValueError(f"Unsupported distribution type: {distribution.dist_type}")


def _run_parallel_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    n_workers: int
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations in parallel using multiprocessing.
    
    Args:
        base_config_path: Path to base scenario YAML
        scenario: MonteCarloScenario configuration
        samples: List of parameter samples
        n_workers: Number of parallel processes
    
    Returns:
        List of iteration results (None for failed iterations)
    """
    # Create worker function with fixed arguments
    def worker(sample: dict[str, Any]) -> dict[str, float] | None:
        return _run_single_iteration(base_config_path, scenario, sample)
    
    # Run in parallel
    with mp.Pool(processes=n_workers) as pool:
        results = pool.map(worker, samples)
    
    return results


def _run_serial_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]]
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations serially (single-threaded).
    
    Useful for debugging or when parallel overhead not worth it.
    
    Args:
        base_config_path: Path to base scenario YAML
        scenario: MonteCarloScenario configuration
        samples: List of parameter samples
    
    Returns:
        List of iteration results (None for failed iterations)
    """
    results = []
    for i, sample in enumerate(samples):
        if (i + 1) % 100 == 0:
            logger.info(f"  Progress: {i+1}/{len(samples)} iterations")
        
        result = _run_single_iteration(base_config_path, scenario, sample)
        results.append(result)
    
    return results


def _run_single_iteration(
    base_config_path: str,
    scenario: MonteCarloScenario,
    sample: dict[str, Any]
) -> dict[str, float] | None:
    """
    Run a single Monte Carlo iteration with given parameter sample.
    
    Args:
        base_config_path: Path to base scenario YAML
        scenario: MonteCarloScenario configuration
        sample: Dict of sampled parameter values
    
    Returns:
        Dict of output KPIs (project_irr, project_npv, dscr_min, etc.)
        None if iteration failed
    """
    try:
        # Build overrides dict from standard parameters
        overrides = _build_overrides_from_sample(sample, scenario.standard_parameters)
        
        # Handle derived parameters (solve for values given targets)
        for derived_param in scenario.derived_parameters:
            if not derived_param.enabled:
                continue
            
            # Get target value from sample
            target_key = f"_target_{derived_param.variable_name}"
            target_value = sample.get(target_key)
            
            if target_value is None:
                logger.warning(f"Missing target for derived parameter: {derived_param.variable_name}")
                continue
            
            # Solve for derived parameter value
            try:
                solver = get_solver(derived_param.derive_from)
                derived_value = solver(
                    base_config_path=base_config_path,
                    base_overrides=overrides,
                    target_irr=target_value if "irr" in derived_param.derive_from else None,
                    target_dscr=target_value if "dscr" in derived_param.derive_from else None,
                    **derived_param.solver_config
                )
                
                # Add derived value to overrides
                path_parts = derived_param.variable_name.split(".")
                _set_nested_value(overrides, path_parts, derived_value)
                
            except Exception as e:
                logger.warning(
                    f"Solver failed for {derived_param.variable_name}: {e}. "
                    f"Skipping this iteration."
                )
                return None
        
        # Evaluate scenario with all parameter values
        kpis = evaluate_with_overrides(base_config_path, overrides)
        
        return kpis
        
    except Exception as e:
        logger.debug(f"Iteration failed: {e}")
        return None


def _build_overrides_from_sample(
    sample: dict[str, Any],
    standard_params: list[Distribution]
) -> dict[str, Any]:
    """
    Build nested override dict from flat sample dict.
    
    Converts flat keys like "project.capex_usd_per_kw" to nested
    dicts like {"project": {"capex_usd_per_kw": 850.0}}.
    
    Args:
        sample: Flat dict with variable_name keys
        standard_params: List of standard parameter distributions
    
    Returns:
        Nested override dict for evaluate_with_overrides()
    """
    overrides: dict[str, Any] = {}
    
    for param in standard_params:
        value = sample.get(param.variable_name)
        if value is None:
            continue
        
        # Split "project.capex_usd_per_kw" into ["project", "capex_usd_per_kw"]
        path_parts = param.variable_name.split(".")
        _set_nested_value(overrides, path_parts, value)
    
    return overrides


def _set_nested_value(
    d: dict[str, Any],
    path: list[str],
    value: Any
) -> None:
    """
    Set value in nested dict using path list.
    
    Args:
        d: Dict to modify (in-place)
        path: List of keys (e.g., ["project", "capex_usd_per_kw"])
        value: Value to set
    
    Example:
        >>> d = {}
        >>> _set_nested_value(d, ["project", "capex"], 850.0)
        >>> d
        {"project": {"capex": 850.0}}
    """
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def _aggregate_results(
    results: list[dict[str, float] | None],
    total_iterations: int,
    scenario_name: str
) -> MonteCarloResult:
    """
    Aggregate iteration results into statistical summary.
    
    Args:
        results: List of KPI dicts from each iteration (None = failed)
        total_iterations: Total iterations attempted
        scenario_name: Identifier for this scenario
    
    Returns:
        MonteCarloResult with percentiles and statistics
    """
    # Filter out failed iterations
    successful_results = [r for r in results if r is not None]
    failed_count = total_iterations - len(successful_results)
    
    if not successful_results:
        raise ValueError("All Monte Carlo iterations failed. Check solver configuration.")
    
    logger.info(f"Aggregating {len(successful_results)} successful iterations")
    
    # Extract arrays for each metric
    project_irr = np.array([r["project_irr"] for r in successful_results])
    project_npv = np.array([r["project_npv"] for r in successful_results])
    dscr_min = np.array([r["dscr_min"] for r in successful_results])
    
    # Calculate percentiles
    return MonteCarloResult(
        iterations=total_iterations,
        project_irr_mean=float(np.mean(project_irr)),
        project_irr_std=float(np.std(project_irr)),
        project_irr_p10=float(np.percentile(project_irr, 10)),
        project_irr_p50=float(np.percentile(project_irr, 50)),
        project_irr_p90=float(np.percentile(project_irr, 90)),
        project_npv_mean=float(np.mean(project_npv)),
        project_npv_p10=float(np.percentile(project_npv, 10)),
        project_npv_p50=float(np.percentile(project_npv, 50)),
        project_npv_p90=float(np.percentile(project_npv, 90)),
        dscr_min_p10=float(np.percentile(dscr_min, 10)),
        dscr_min_p50=float(np.percentile(dscr_min, 50)),
        failed_iterations=failed_count,
        raw_results=successful_results,
        scenario_name=scenario_name
    )


