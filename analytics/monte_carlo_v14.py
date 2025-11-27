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
import warnings
from pathlib import Path
from typing import Any

import multiprocess as mp
import numpy as np
import yaml
from pydantic import ValidationError
from SALib.sample import latin as lhs

from analytics.contracts_v14 import (DerivedParameter, Distribution,
                                     MonteCarloResult, MonteCarloScenario)
from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.parameter_solvers import get_solver
from constants import MONTE_CARLO_ITERATIONS

logger = logging.getLogger(__name__)

# Suppress numpy warnings during parallel execution
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ---------------------------------------------------------------------------
# Validation helpers (used by tests + runtime)
# ---------------------------------------------------------------------------


def _normalise_dist_type(dist_type: str | None) -> str:
    """Return a lowercased, stripped distribution type label."""
    if dist_type is None:
        return ""
    return str(dist_type).strip().lower()


def _validate_distribution_for_sampling(distribution: Distribution) -> None:
    """Validate a Distribution instance before sampling.

    This is deliberately strict and is exercised directly by
    tests/analytics_layer/test_monte_carlo_v14.py:

    - Normal: requires std > 0
    - Triangular: requires min <= mode <= max
    - Uniform: requires min < max

    Any violation raises ValueError with a message that matches the tests'
    expectations.
    """
    dist_type = _normalise_dist_type(getattr(distribution, "dist_type", None))

    if dist_type == "normal":
        std = getattr(distribution, "std", None)
        if std is None or std <= 0:
            # Tests expect this substring
            raise ValueError("normal distribution requires std > 0")

    elif dist_type == "triangular":
        min_val = getattr(distribution, "min_val", None)
        mode = getattr(distribution, "mode", None)
        max_val = getattr(distribution, "max_val", None)

        # Structural guard: all present and ordered
        if (
            min_val is None
            or mode is None
            or max_val is None
            or not (min_val <= mode <= max_val)
        ):
            # Tests expect this substring
            raise ValueError("triangular distribution requires min <= mode <= max")

    elif dist_type == "uniform":
        min_val = getattr(distribution, "min_val", None)
        max_val = getattr(distribution, "max_val", None)
        if min_val is None or max_val is None or not (min_val < max_val):
            raise ValueError("uniform distribution requires min < max")

    # Other distribution types can be extended here as needed.
    # If no rule applies, we simply accept the distribution.


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_monte_carlo_analysis(
    base_config_path: str,
    scenario_config_path: str = "config/monte_carlo_defaults.yaml",
    scenario_name: str | None = None,
    n_iterations: int | None = None,
    random_seed: int | None = None,
    parallel_workers: int | None = None,
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
        ValueError: If MC configuration invalid
    """
    logger.info("Starting Monte Carlo analysis: %s", base_config_path)

    # Load Monte Carlo configuration
    mc_config = _load_monte_carlo_config(scenario_config_path)

    # Override simulation settings if provided
    default_iterations = mc_config.get("simulation", {}).get(
        "iterations", MONTE_CARLO_ITERATIONS
    )
    iterations = n_iterations or default_iterations

    sim_block = mc_config.get("simulation", {})
    seed = random_seed if random_seed is not None else sim_block.get("random_seed")
    workers = parallel_workers or sim_block.get("parallel_workers") or mp.cpu_count()

    logger.info(
        "Simulation: %s iterations, seed=%s, workers=%s", iterations, seed, workers
    )

    # Load scenarios
    scenarios = _load_scenarios(mc_config, scenario_name)
    logger.info("Loaded %d scenario(s) to run", len(scenarios))

    # Run each scenario
    results: dict[str, MonteCarloResult] = {}
    for scenario in scenarios:
        logger.info("Running scenario: %s", scenario.name)

        try:
            result = _run_single_scenario(
                base_config_path=base_config_path,
                scenario=scenario,
                iterations=iterations,
                random_seed=seed,
                parallel_workers=workers,
            )
            results[scenario.name] = result

            logger.info(
                "  Completed %s: P50 IRR=%.2f%%, Success rate=%.1f%%",
                scenario.name,
                result.project_irr_p50 * 100.0,
                result.success_rate(),
            )

        except Exception as exc:  # pragma: no cover - defensive wrapper
            logger.error("  Failed scenario %s: %s", scenario.name, exc)
            continue

    logger.info("Monte Carlo analysis complete: %d scenario(s)", len(results))
    return results


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


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

    with yaml_file.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Monte Carlo config at {config_path} must be a mapping")

    # Validate required sections
    required = ["simulation", "standard_parameters"]
    missing = [section for section in required if section not in config]
    if missing:
        raise ValueError(f"Monte Carlo config missing required sections: {missing}")

    logger.info("Loaded Monte Carlo config from %s", config_path)
    return config


def _load_scenarios(
    mc_config: dict[str, Any],
    scenario_name: str | None,
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
        derived_params = _parse_derived_parameters(
            mc_config.get("derived_parameters", [])
        )

        return [
            MonteCarloScenario(
                name="default",
                description="Default scenario from standard parameters",
                standard_parameters=standard_params,
                derived_parameters=derived_params,
                enabled=True,
            )
        ]

    scenarios: list[MonteCarloScenario] = []
    for scenario_dict in scenarios_config:
        # Skip disabled scenarios
        if not scenario_dict.get("enabled", True):
            continue

        # Filter by name if specified
        if scenario_name and scenario_dict.get("name") != scenario_name:
            continue

        overrides = scenario_dict.get("parameter_overrides", {})

        standard_params_cfg = overrides.get(
            "standard_parameters", mc_config["standard_parameters"]
        )
        derived_params_cfg = overrides.get(
            "derived_parameters", mc_config.get("derived_parameters", [])
        )

        standard_params = _parse_distributions(standard_params_cfg)
        derived_params = _parse_derived_parameters(derived_params_cfg)

        scenario = MonteCarloScenario(
            name=scenario_dict["name"],
            description=scenario_dict.get("description", ""),
            standard_parameters=standard_params,
            derived_parameters=derived_params,
            enabled=True,
        )
        scenarios.append(scenario)

    if scenario_name and not scenarios:
        raise ValueError(f"Scenario '{scenario_name}' not found or disabled")

    return scenarios


# ---------------------------------------------------------------------------
# Parsing distributions and derived parameters
# ---------------------------------------------------------------------------


def _parse_distributions(params_config: list[dict[str, Any]]) -> list[Distribution]:
    """
    Parse distribution configurations into Distribution objects.

    Args:
        params_config: List of parameter dicts from YAML

    Returns:
        List of validated Distribution objects

    Raises:
        ValueError: If any distribution invalid
    """
    distributions: list[Distribution] = []
    for param_dict in params_config:
        try:
            dist = Distribution(**param_dict)
            # Validate upfront so bad configs fail early
            _validate_distribution_for_sampling(dist)
            distributions.append(dist)
        except (ValidationError, ValueError) as exc:
            logger.error("Invalid distribution: %s", param_dict)
            raise ValueError(f"Distribution validation failed: {exc}") from exc

    return distributions


def _parse_derived_parameters(
    params_config: list[dict[str, Any]],
) -> list[DerivedParameter]:
    """
    Parse derived parameter configurations into DerivedParameter objects.

    Args:
        params_config: List of derived parameter dicts

    Returns:
        List of validated DerivedParameter objects (only enabled ones)

    Raises:
        ValueError: If any derived parameter invalid
    """
    derived_params: list[DerivedParameter] = []
    for param_dict in params_config:
        # Skip disabled derived parameters
        if not param_dict.get("enabled", True):
            continue

        try:
            # Parse target distribution
            target_dist = Distribution(**param_dict["target_distribution"])
            _validate_distribution_for_sampling(target_dist)

            derived = DerivedParameter(
                variable_name=param_dict["variable_name"],
                derive_from=param_dict["derive_from"],
                target_distribution=target_dist,
                solver_config=param_dict["solver_config"],
                enabled=True,
                description=param_dict.get("description", ""),
            )
            derived_params.append(derived)

        except (ValidationError, ValueError, KeyError) as exc:
            logger.error("Invalid derived parameter: %s", param_dict)
            raise ValueError(f"Derived parameter validation failed: {exc}") from exc

    return derived_params


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------


def _run_single_scenario(
    base_config_path: str,
    scenario: MonteCarloScenario,
    iterations: int,
    random_seed: int | None,
    parallel_workers: int,
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
        random_seed,
    )

    logger.info(
        "Running %d iterations with %d workers...", iterations, parallel_workers
    )

    if parallel_workers > 1:
        results = _run_parallel_iterations(
            base_config_path=base_config_path,
            scenario=scenario,
            samples=samples,
            n_workers=parallel_workers,
        )
    else:
        results = _run_serial_iterations(
            base_config_path=base_config_path,
            scenario=scenario,
            samples=samples,
        )

    return _aggregate_results(results, iterations, scenario.name)


def _generate_lhs_samples(
    standard_params: list[Distribution],
    derived_params: list[DerivedParameter],
    n_samples: int,
    random_seed: int | None,
) -> list[dict[str, Any]]:
    """
    Generate Latin Hypercube Samples for Monte Carlo iteration.

    LHS provides better coverage of parameter space than pure random
    sampling, requiring fewer iterations for same accuracy.
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    samples: list[dict[str, Any]] = []

    # Generate LHS samples for standard parameters
    if standard_params:
        problem = {
            "num_vars": len(standard_params),
            "names": [p.variable_name for p in standard_params],
            "bounds": [[0.0, 1.0]] * len(standard_params),
        }

        unit_samples = lhs.sample(problem, n_samples, seed=random_seed)

        for i in range(n_samples):
            sample: dict[str, Any] = {}
            for j, param in enumerate(standard_params):
                unit_value = float(unit_samples[i, j])
                actual_value = _transform_to_distribution(unit_value, param)
                sample[param.variable_name] = actual_value
            samples.append(sample)
    else:
        samples = [{} for _ in range(n_samples)]

    # Generate samples for derived parameter targets
    for derived_param in derived_params:
        target_dist = derived_param.target_distribution
        for i in range(n_samples):
            unit_value = float(np.random.uniform(0.0, 1.0))
            target_value = _transform_to_distribution(unit_value, target_dist)
            target_key = f"_target_{derived_param.variable_name}"
            samples[i][target_key] = target_value

    logger.info("Generated %d LHS samples", len(samples))
    return samples


def _transform_to_distribution(
    unit_value: float,
    distribution: Distribution,
) -> float:
    """
    Transform unit hypercube value [0, 1] to actual distribution.

    This is the *only* place where raw Distribution objects are turned into
    numeric samples, so we enforce basic parameter sanity here to avoid
    sending obviously invalid configurations into SciPy.

    Args:
        unit_value: Value in [0, 1] from LHS
        distribution: Target distribution specification

    Returns:
        Transformed value from specified distribution

    Raises:
        ValueError:
            If distribution parameters are structurally invalid for the given
            dist_type (e.g. normal without positive std, triangular with
            inconsistent min/mode/max).
    """
    # Always run the shared validator so tests calling this directly see
    # the same semantics as the parsing helpers.
    _validate_distribution_for_sampling(distribution)

    dist_type = _normalise_dist_type(getattr(distribution, "dist_type", None))

    # --- Normal distribution ------------------------------------------------
    if dist_type == "normal":
        from scipy.stats import norm

        std = float(distribution.std)
        return float(norm.ppf(unit_value, loc=float(distribution.mean), scale=std))

    # --- Lognormal distribution --------------------------------------------
    if dist_type == "lognormal":
        from scipy.stats import lognorm

        std = float(distribution.std)
        return float(
            lognorm.ppf(
                unit_value,
                s=std,
                scale=float(np.exp(distribution.mean)),
            )
        )

    # --- Triangular distribution -------------------------------------------
    if dist_type == "triangular":
        from scipy.stats import triang

        min_val = float(distribution.min_val)
        mode = float(distribution.mode)
        max_val = float(distribution.max_val)

        span = max_val - min_val
        if span <= 0:
            raise ValueError("triangular distribution requires max > min (span > 0)")

        c = (mode - min_val) / span
        return float(
            triang.ppf(
                unit_value,
                c,
                loc=min_val,
                scale=span,
            )
        )

    # --- Uniform distribution ----------------------------------------------
    if dist_type == "uniform":
        min_val = float(distribution.min_val)
        max_val = float(distribution.max_val)
        span = max_val - min_val
        return float(min_val + unit_value * span)

    # --- Fallback for unknown/distinct types -------------------------------
    raise ValueError(f"Unsupported distribution type: {dist_type!r}")


# ---------------------------------------------------------------------------
# Iteration runners
# ---------------------------------------------------------------------------


def _run_parallel_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    n_workers: int,
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations in parallel using multiprocessing.
    """

    def worker(sample: dict[str, Any]) -> dict[str, float] | None:
        return _run_single_iteration(base_config_path, scenario, sample)

    with mp.Pool(processes=n_workers) as pool:
        results = pool.map(worker, samples)

    return results


def _run_serial_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations serially (single-threaded).
    """
    results: list[dict[str, float] | None] = []
    for idx, sample in enumerate(samples, start=1):
        if idx % 100 == 0:
            logger.info("  Progress: %d/%d iterations", idx, len(samples))
        result = _run_single_iteration(base_config_path, scenario, sample)
        results.append(result)
    return results


def _run_single_iteration(
    base_config_path: str,
    scenario: MonteCarloScenario,
    sample: dict[str, Any],
) -> dict[str, float] | None:
    """
    Run a single Monte Carlo iteration with given parameter sample.
    """
    try:
        overrides = _build_overrides_from_sample(sample, scenario.standard_parameters)

        # Handle derived parameters (solve for values given targets)
        for derived_param in scenario.derived_parameters:
            if not derived_param.enabled:
                continue

            target_key = f"_target_{derived_param.variable_name}"
            target_value = sample.get(target_key)
            if target_value is None:
                logger.warning(
                    "Missing target for derived parameter: %s",
                    derived_param.variable_name,
                )
                return None

            try:
                solver = get_solver(derived_param.derive_from)
                derived_value = solver(
                    base_config_path=base_config_path,
                    base_overrides=overrides,
                    target_irr=(
                        target_value if "irr" in derived_param.derive_from else None
                    ),
                    target_dscr=(
                        target_value if "dscr" in derived_param.derive_from else None
                    ),
                    **derived_param.solver_config,
                )
                path_parts = derived_param.variable_name.split(".")
                _set_nested_value(overrides, path_parts, derived_value)
            except Exception as exc:  # pragma: no cover - rare path
                logger.warning(
                    "Solver failed for %s: %s. Skipping this iteration.",
                    derived_param.variable_name,
                    exc,
                )
                return None

        # Evaluate scenario with all parameter values
        kpis = evaluate_with_overrides(base_config_path, overrides)
        return kpis  # type: ignore[return-value]

    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Iteration failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Overrides + aggregation
# ---------------------------------------------------------------------------


def _build_overrides_from_sample(
    sample: dict[str, Any],
    standard_params: list[Distribution],
) -> dict[str, Any]:
    """
    Build nested override dict from flat sample dict.

    Converts flat keys like "project.capex_usd_per_kw" to nested
    dicts like {"project": {"capex_usd_per_kw": 850.0}}.
    """
    overrides: dict[str, Any] = {}

    for param in standard_params:
        value = sample.get(param.variable_name)
        if value is None:
            continue

        path_parts = param.variable_name.split(".")
        _set_nested_value(overrides, path_parts, value)

    return overrides


def _set_nested_value(
    d: dict[str, Any],
    path: list[str],
    value: Any,
) -> None:
    """
    Set value in nested dict using path list.
    """
    current: dict[str, Any] = d
    for key in path[:-1]:
        current = current.setdefault(key, {})
    current[path[-1]] = value


def _aggregate_results(
    results: list[dict[str, float] | None],
    total_iterations: int,
    scenario_name: str,
) -> MonteCarloResult:
    """
    Aggregate iteration results into statistical summary.
    """
    successful_results = [r for r in results if r is not None]
    failed_count = total_iterations - len(successful_results)

    if not successful_results:
        raise ValueError(
            "All Monte Carlo iterations failed. Check solver configuration."
        )

    logger.info("Aggregating %d successful iterations", len(successful_results))

    project_irr = np.array([r["project_irr"] for r in successful_results], dtype=float)
    project_npv = np.array([r["project_npv"] for r in successful_results], dtype=float)
    dscr_min = np.array([r["dscr_min"] for r in successful_results], dtype=float)

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
        scenario_name=scenario_name,
    )


# EOF
