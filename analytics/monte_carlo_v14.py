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
from typing import Any, Dict, List, Optional

import multiprocess as mp
import numpy as np
import yaml
from SALib.sample import latin as lhs
from pydantic import ValidationError

from analytics.contracts_v14 import (
    DerivedParameter,
    Distribution,
    MonteCarloResult,
    MonteCarloScenario,
)
from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.parameter_solvers import get_solver
from constants import MONTE_CARLO_ITERATIONS

logger = logging.getLogger(__name__)

# Suppress numpy warnings during parallel execution (overflow, invalid ops, etc.)
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_monte_carlo_analysis(
    base_config_path: str,
    scenario_config_path: str = "config/monte_carlo_defaults.yaml",
    scenario_name: Optional[str] = None,
    n_iterations: Optional[int] = None,
    random_seed: Optional[int] = None,
    parallel_workers: Optional[int] = None,
) -> Dict[str, MonteCarloResult]:
    """
    Run Monte Carlo simulation with flexible parameter system.

    Supports:
    - Standard parameters (direct config overrides with distributions)
    - Derived parameters (calculated from target constraints)
    - Multiple scenarios (comparative risk analysis)
    - Parallel execution for speed
    - Graceful error handling (isolated iteration failures)

    Args:
        base_config_path:
            Path to base scenario YAML/JSON (v14 config).

        scenario_config_path:
            Path to Monte Carlo configuration YAML
            (usually config/monte_carlo_defaults.yaml).

        scenario_name:
            Specific scenario to run. If None, all enabled scenarios in the
            Monte Carlo config will be executed.

        n_iterations:
            Override for the number of iterations. If None, the value from the
            MC config's `simulation.iterations` is used, falling back to
            MONTE_CARLO_ITERATIONS if missing.

        random_seed:
            Optional random seed for reproducibility.

        parallel_workers:
            Number of CPU cores to use. If None, uses `simulation.parallel_workers`
            from the config, then falls back to `mp.cpu_count()`.

    Returns:
        Dict mapping scenario names -> MonteCarloResult.

    Raises:
        FileNotFoundError:
            If the base scenario config or MC config cannot be found.

        ValidationError / ValueError:
            If the MC configuration is invalid (e.g., malformed distributions).
    """
    logger.info("Starting Monte Carlo analysis: %s", base_config_path)

    mc_config = _load_monte_carlo_config(scenario_config_path)

    sim_cfg = mc_config.get("simulation", {})
    iterations = int(
        n_iterations
        if n_iterations is not None
        else sim_cfg.get("iterations", MONTE_CARLO_ITERATIONS)
    )
    seed = random_seed if random_seed is not None else sim_cfg.get("random_seed")
    workers = int(
        parallel_workers
        if parallel_workers is not None
        else sim_cfg.get("parallel_workers", mp.cpu_count())
    )

    logger.info(
        "Simulation settings: iterations=%s, seed=%s, workers=%s",
        iterations,
        seed,
        workers,
    )

    scenarios = _load_scenarios(mc_config, scenario_name)
    logger.info("Loaded %d Monte Carlo scenario(s)", len(scenarios))

    results: Dict[str, MonteCarloResult] = {}
    for scenario in scenarios:
        logger.info("Running Monte Carlo scenario: %s", scenario.name)
        try:
            result = _run_single_scenario(
                base_config_path=base_config_path,
                scenario=scenario,
                iterations=iterations,
                random_seed=seed,
                parallel_workers=workers,
            )
            results[scenario.name] = result

            try:
                logger.info(
                    "  Completed %s: P50 IRR=%.2f%%, Success rate=%.1f%%",
                    scenario.name,
                    result.project_irr_p50 * 100.0,
                    result.success_rate(),
                )
            except Exception:
                # If result is missing metrics, we still keep it; callers can inspect raw_results.
                logger.info("  Completed %s (summary metrics unavailable)", scenario.name)

        except Exception as exc:
            logger.error("  Monte Carlo scenario '%s' failed: %s", scenario.name, exc)
            continue

    logger.info("Monte Carlo analysis complete: %d scenario(s) with results", len(results))
    return results


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_monte_carlo_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate Monte Carlo configuration from YAML.

    Args:
        config_path:
            Path to monte_carlo_defaults.yaml

    Returns:
        Validated configuration dict.

    Raises:
        FileNotFoundError:
            If config file does not exist.

        ValueError:
            If YAML structure invalid or missing required sections.
    """
    yaml_file = Path(config_path)
    if not yaml_file.exists():
        raise FileNotFoundError(f"Monte Carlo config not found: {config_path}")

    with yaml_file.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    required_sections = ["simulation", "standard_parameters"]
    missing = [section for section in required_sections if section not in config]
    if missing:
        raise ValueError(f"Monte Carlo config missing required sections: {missing}")

    logger.info("Loaded Monte Carlo config from %s", config_path)
    return config


def _load_scenarios(
    mc_config: Dict[str, Any],
    scenario_name: Optional[str],
) -> List[MonteCarloScenario]:
    """
    Build MonteCarloScenario objects from the MC config.

    If no explicit `scenarios` block is present, we synthesize a single
    "default" scenario using the top-level standard/derived parameter blocks.
    """
    scenarios_config = mc_config.get("scenarios", [])

    # No scenarios defined -> synthesize a default one
    if not scenarios_config:
        logger.info(
            "No explicit Monte Carlo scenarios defined; using 'default' "
            "scenario from top-level standard_parameters / derived_parameters."
        )
        standard_params = _parse_distributions(mc_config["standard_parameters"])
        derived_params = _parse_derived_parameters(
            mc_config.get("derived_parameters", [])
        )
        return [
            MonteCarloScenario(
                name="default",
                description="Default Monte Carlo scenario from standard parameters",
                standard_parameters=standard_params,
                derived_parameters=derived_params,
                enabled=True,
            )
        ]

    scenarios: List[MonteCarloScenario] = []
    for scenario_dict in scenarios_config:
        if not scenario_dict.get("enabled", True):
            continue

        if scenario_name and scenario_dict.get("name") != scenario_name:
            continue

        # Apply per-scenario overrides if present
        overrides_cfg = scenario_dict.get("parameter_overrides", {})
        standard_cfg = overrides_cfg.get(
            "standard_parameters", mc_config["standard_parameters"]
        )
        derived_cfg = overrides_cfg.get(
            "derived_parameters", mc_config.get("derived_parameters", [])
        )

        standard_params = _parse_distributions(standard_cfg)
        derived_params = _parse_derived_parameters(derived_cfg)

        scenarios.append(
            MonteCarloScenario(
                name=scenario_dict["name"],
                description=scenario_dict.get("description", ""),
                standard_parameters=standard_params,
                derived_parameters=derived_params,
                enabled=True,
            )
        )

    if scenario_name and not scenarios:
        raise ValueError(f"Scenario '{scenario_name}' not found or disabled in MC config")

    return scenarios


# ---------------------------------------------------------------------------
# Distribution parsing + validation
# ---------------------------------------------------------------------------


def _parse_distributions(params_config: List[Dict[str, Any]]) -> List[Distribution]:
    """
    Parse distribution configurations into Distribution objects.

    Raises a ValueError if any distribution fails pydantic validation.
    """
    distributions: List[Distribution] = []
    for param_dict in params_config:
        try:
            dist = Distribution(**param_dict)
            distributions.append(dist)
        except (ValidationError, ValueError) as exc:
            logger.error("Invalid distribution configuration: %s", param_dict)
            raise ValueError(f"Distribution validation failed: {exc}") from exc

    return distributions


def _parse_derived_parameters(
    params_config: List[Dict[str, Any]]
) -> List[DerivedParameter]:
    """
    Parse derived parameter configurations into DerivedParameter objects.

    Disabled entries (enabled: false) are skipped.
    """
    derived_params: List[DerivedParameter] = []
    for param_dict in params_config:
        if not param_dict.get("enabled", True):
            continue

        try:
            target_dist = Distribution(**param_dict["target_distribution"])

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
            logger.error("Invalid derived parameter configuration: %s", param_dict)
            raise ValueError(f"Derived parameter validation failed: {exc}") from exc

    return derived_params


def _validate_distribution_for_sampling(distribution: Distribution) -> None:
    """
    Guardrail validation applied *before* sampling / transforms.

    This exists specifically to enforce domain constraints that are not
    captured by the pydantic model itself, and is wired to the tests in
    tests/analytics_layer/test_monte_carlo_v14.py.

    Behaviour expected by tests:
      - Normal distribution requires std > 0
      - Triangular distribution requires min <= mode <= max
    """
    dist_type = distribution.dist_type

    if dist_type == "normal":
        std = getattr(distribution, "std", None)
        if std is None or std <= 0:
            raise ValueError("Normal distribution requires std > 0")

    elif dist_type == "triangular":
        min_val = getattr(distribution, "min_val", None)
        mode = getattr(distribution, "mode", None)
        max_val = getattr(distribution, "max_val", None)

        if min_val is None or mode is None or max_val is None:
            raise ValueError("Triangular distribution requires min <= mode <= max")

        if not (min_val <= mode <= max_val):
            raise ValueError("Triangular distribution requires min <= mode <= max")

    # For uniform/lognormal we rely on the pydantic model and downstream
    # finance layer; additional checks can be added here if needed later.


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------


def _run_single_scenario(
    base_config_path: str,
    scenario: MonteCarloScenario,
    iterations: int,
    random_seed: Optional[int],
    parallel_workers: int,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for a single scenario.
    """
    logger.info(
        "Generating Latin Hypercube samples for scenario '%s' (%d iterations)",
        scenario.name,
        iterations,
    )

    samples = _generate_lhs_samples(
        standard_params=scenario.standard_parameters,
        derived_params=scenario.derived_parameters,
        n_samples=iterations,
        random_seed=random_seed,
    )

    logger.info(
        "Executing Monte Carlo iterations for '%s' with %d worker(s)",
        scenario.name,
        parallel_workers,
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
    standard_params: List[Distribution],
    derived_params: List[DerivedParameter],
    n_samples: int,
    random_seed: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Generate Latin Hypercube Samples for Monte Carlo iteration.

    LHS provides better coverage of parameter space than pure random sampling.

    Returns:
        List of sample dicts mapping `variable_name` -> sampled value.
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    samples: List[Dict[str, Any]] = []

    # Standard parameter sampling via SALib LHS
    if standard_params:
        problem = {
            "num_vars": len(standard_params),
            "names": [p.variable_name for p in standard_params],
            "bounds": [[0.0, 1.0]] * len(standard_params),
        }

        unit_samples = lhs.sample(problem, n_samples, seed=random_seed)

        for i in range(n_samples):
            sample: Dict[str, Any] = {}
            for j, param in enumerate(standard_params):
                unit_value = float(unit_samples[i, j])
                value = _transform_to_distribution(unit_value, param)
                sample[param.variable_name] = value
            samples.append(sample)
    else:
        samples = [{} for _ in range(n_samples)]

    # Derived parameter targets
    for derived_param in derived_params:
        target_dist = derived_param.target_distribution

        for i in range(n_samples):
            unit_value = float(np.random.uniform(0.0, 1.0))
            target_value = _transform_to_distribution(unit_value, target_dist)
            target_key = f"_target_{derived_param.variable_name}"
            samples[i][target_key] = target_value

    logger.info("Generated %d Latin Hypercube samples", len(samples))
    return samples


def _transform_to_distribution(unit_value: float, distribution: Distribution) -> float:
    """
    Transform a unit-hypercube value [0, 1] into a value from the given
    distribution.

    This function is the choke-point for distribution semantics and is where
    we enforce additional domain constraints expected by the tests.
    """
    # Guardrails: ensure the distribution parameters make sense
    _validate_distribution_for_sampling(distribution)

    dist_type = distribution.dist_type

    if dist_type == "normal":
        from scipy.stats import norm

        return float(norm.ppf(unit_value, loc=distribution.mean, scale=distribution.std))

    if dist_type == "lognormal":
        from scipy.stats import lognorm

        # lognorm parameterization: s = std, scale = exp(mean)
        return float(
            lognorm.ppf(
                unit_value,
                s=distribution.std,
                scale=np.exp(distribution.mean),
            )
        )

    if dist_type == "triangular":
        from scipy.stats import triang

        # triang parameterization: c = (mode - min) / (max - min)
        span = distribution.max_val - distribution.min_val
        c = (distribution.mode - distribution.min_val) / span
        return float(
            triang.ppf(
                unit_value,
                c,
                loc=distribution.min_val,
                scale=span,
            )
        )

    if dist_type == "uniform":
        return float(
            distribution.min_val
            + unit_value * (distribution.max_val - distribution.min_val)
        )

    raise ValueError(f"Unsupported distribution type: {dist_type!r}")


# ---------------------------------------------------------------------------
# Iteration runners
# ---------------------------------------------------------------------------


def _run_parallel_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: List[Dict[str, Any]],
    n_workers: int,
) -> List[Optional[Dict[str, float]]]:
    """
    Run Monte Carlo iterations in parallel using multiprocessing.
    """

    def worker(sample: Dict[str, Any]) -> Optional[Dict[str, float]]:
        return _run_single_iteration(base_config_path, scenario, sample)

    with mp.Pool(processes=n_workers) as pool:
        results: List[Optional[Dict[str, float]]] = pool.map(worker, samples)

    return results


def _run_serial_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: List[Dict[str, Any]],
) -> List[Optional[Dict[str, float]]]:
    """
    Run Monte Carlo iterations serially (single process).

    Useful for debugging or environments where multiprocessing is awkward.
    """
    results: List[Optional[Dict[str, float]]] = []
    total = len(samples)

    for idx, sample in enumerate(samples, start=1):
        if idx % 100 == 0 or idx == total:
            logger.info("  Monte Carlo progress: %d/%d iterations", idx, total)

        result = _run_single_iteration(base_config_path, scenario, sample)
        results.append(result)

    return results


def _run_single_iteration(
    base_config_path: str,
    scenario: MonteCarloScenario,
    sample: Dict[str, Any],
) -> Optional[Dict[str, float]]:
    """
    Run a single Monte Carlo iteration with the given parameter sample.

    Returns:
        A KPI dict (project_irr, project_npv, dscr_min, ...) or None if failed.
    """
    try:
        overrides = _build_overrides_from_sample(
            sample=sample,
            standard_params=scenario.standard_parameters,
        )

        # Derived parameters: solve for the actual config value from a target.
        for derived_param in scenario.derived_parameters:
            if not derived_param.enabled:
                continue

            target_key = f"_target_{derived_param.variable_name}"
            target_value = sample.get(target_key)

            if target_value is None:
                logger.warning(
                    "Missing target for derived parameter %s; skipping iteration.",
                    derived_param.variable_name,
                )
                return None

            try:
                solver = get_solver(derived_param.derive_from)
                derived_value = solver(
                    base_config_path=base_config_path,
                    base_overrides=overrides,
                    target_irr=(
                        target_value
                        if "irr" in derived_param.derive_from.lower()
                        else None
                    ),
                    target_dscr=(
                        target_value
                        if "dscr" in derived_param.derive_from.lower()
                        else None
                    ),
                    **derived_param.solver_config,
                )

                path_parts = derived_param.variable_name.split(".")
                _set_nested_value(overrides, path_parts, derived_value)

            except Exception as exc:
                logger.warning(
                    "Solver failed for derived parameter %s: %s. "
                    "Skipping this iteration.",
                    derived_param.variable_name,
                    exc,
                )
                return None

        kpis = evaluate_with_overrides(base_config_path, overrides)
        return kpis

    except Exception as exc:
        logger.debug("Monte Carlo iteration failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Overrides & aggregation
# ---------------------------------------------------------------------------


def _build_overrides_from_sample(
    sample: Dict[str, Any],
    standard_params: List[Distribution],
) -> Dict[str, Any]:
    """
    Build the nested overrides dict from a flat sample dict.

    Example:
        "project.capex_usd_per_kw" -> {"project": {"capex_usd_per_kw": 850.0}}
    """
    overrides: Dict[str, Any] = {}

    for param in standard_params:
        value = sample.get(param.variable_name)
        if value is None:
            continue

        path_parts = param.variable_name.split(".")
        _set_nested_value(overrides, path_parts, value)

    return overrides


def _set_nested_value(
    d: Dict[str, Any],
    path: List[str],
    value: Any,
) -> None:
    """
    Set a nested value in a dict using a list of keys.

    Modifies `d` in-place.
    """
    current: Dict[str, Any] = d
    for key in path[:-1]:
        current = current.setdefault(key, {})
    current[path[-1]] = value


def _aggregate_results(
    results: List[Optional[Dict[str, float]]],
    total_iterations: int,
    scenario_name: str,
) -> MonteCarloResult:
    """
    Aggregate iteration-level KPI dicts into a MonteCarloResult summary.
    """
    successful_results: List[Dict[str, float]] = [r for r in results if r is not None]
    failed_count = total_iterations - len(successful_results)

    if not successful_results:
        raise ValueError(
            f"All Monte Carlo iterations failed for scenario '{scenario_name}'. "
            "Check solver configuration and distribution ranges."
        )

    logger.info(
        "Aggregating %d successful Monte Carlo iterations (failed=%d) for '%s'",
        len(successful_results),
        failed_count,
        scenario_name,
    )

    def _extract_array(key: str) -> np.ndarray:
        values = [res[key] for res in successful_results if key in res]
        if not values:
            return np.array([], dtype=float)
        return np.asarray(values, dtype=float)

    project_irr = _extract_array("project_irr")
    project_npv = _extract_array("project_npv")
    dscr_min = _extract_array("dscr_min")

    return MonteCarloResult(
        iterations=total_iterations,
        project_irr_mean=float(project_irr.mean()) if project_irr.size else float("nan"),
        project_irr_std=float(project_irr.std()) if project_irr.size else float("nan"),
        project_irr_p10=float(np.percentile(project_irr, 10))
        if project_irr.size
        else float("nan"),
        project_irr_p50=float(np.percentile(project_irr, 50))
        if project_irr.size
        else float("nan"),
        project_irr_p90=float(np.percentile(project_irr, 90))
        if project_irr.size
        else float("nan"),
        project_npv_mean=float(project_npv.mean()) if project_npv.size else float("nan"),
        project_npv_p10=float(np.percentile(project_npv, 10))
        if project_npv.size
        else float("nan"),
        project_npv_p50=float(np.percentile(project_npv, 50))
        if project_npv.size
        else float("nan"),
        project_npv_p90=float(np.percentile(project_npv, 90))
        if project_npv.size
        else float("nan"),
        dscr_min_p10=float(np.percentile(dscr_min, 10))
        if dscr_min.size
        else float("nan"),
        dscr_min_p50=float(np.percentile(dscr_min, 50))
        if dscr_min.size
        else float("nan"),
        failed_iterations=failed_count,
        raw_results=successful_results,
        scenario_name=scenario_name,
    )


#EOF