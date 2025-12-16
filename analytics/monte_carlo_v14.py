from __future__ import annotations

import logging
import math
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, List, Mapping

import multiprocess as mp
import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from SALib.sample import latin as lhs
from SALib.sample import sobol

from analytics.contracts_v14 import (
    DerivedParameter,
    Distribution,
    MonteCarloResult,
    MonteCarloScenario,
)
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.parameter_solvers import get_solver
from constants import MONTE_CARLO_ITERATIONS

logger = logging.getLogger(__name__)

# Suppress numpy warnings during parallel execution
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ===== P1.1 OPTIMIZATION: Config Caching =====
# Module-level cache to avoid reloading YAML files per iteration
_CONFIG_CACHE: dict[str, "MonteCarloConfig"] = {}


# ---------------------------------------------------------------------------
# Pydantic config models (schema guard for YAML)
# ---------------------------------------------------------------------------


class SimulationConfig(BaseModel):
    """
    Monte Carlo simulation-level settings.

    sampler:
        "lhs"    -> Latin Hypercube Sampling (default; good all-round choice)
        "sobol"  -> Sobol low-discrepancy sequence (quasi-random)
        "random" -> i.i.d. uniform in [0, 1]^d

    iterations:
        Number of Monte Carlo iterations per scenario.

    random_seed:
        Seed for the main numpy Generator. Same seed ⇒ same unit samples
        and derived targets, i.e. common random numbers across scenarios.

    parallel_workers:
        Number of CPU processes. None = auto-detect (mp.cpu_count()).
    """

    model_config = ConfigDict(extra="ignore")

    iterations: int = Field(default=MONTE_CARLO_ITERATIONS, ge=1)
    random_seed: int | None = None
    parallel_workers: int | None = Field(default=None, ge=1)
    sampler: str = Field(default="lhs")


class MonteCarloConfig(BaseModel):
    """
    Top-level Monte Carlo configuration schema.

    Expected YAML structure:

    simulation:
      iterations: 2000
      random_seed: 42
      parallel_workers: 4
      sampler: lhs   # or sobol / random

    standard_parameters:
      - variable_name: project.capex_usd_per_kw
        dist_type: triangular
        min_val: 1100
        mode: 1200
        max_val: 1300
        ...

    derived_parameters:
      - variable_name: debt.ratio
        derive_from: target_project_irr
        target_distribution: { ... }
        solver_config: { ... }

    scenarios:
      - name: Base
        description: "Base case"
        enabled: true
        parameter_overrides:
          standard_parameters: [ ... ]
          derived_parameters: [ ... ]
    """

    model_config = ConfigDict(extra="ignore")

    simulation: SimulationConfig
    standard_parameters: list[dict[str, Any]]
    derived_parameters: list[dict[str, Any]] = Field(default_factory=list)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)


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
# Public entry points
# ---------------------------------------------------------------------------


def run_monte_carlo(
    mc_config_path: str,
    base_config_path: str,
    scenario_name: str | None = None,
    n_iterations: int | None = None,
    random_seed: int | None = None,
    parallel_workers: int | None = None,
    write_output: bool = True,
) -> dict[str, MonteCarloResult]:
    """
    Coordinator-style public API for v14 Monte Carlo runs.

    This is the *front door* used by tests, scripts and (eventually) the
    CLI layer. It simply wires a Monte Carlo YAML config + base scenario
    into the engine, with optional runtime overrides.

    Args:
        mc_config_path:
            Path to Monte Carlo YAML (typically config/monte_carlo_defaults.yaml
            or a regression-specific variant).
        base_config_path:
            Path to the base v14 scenario YAML that will be evaluated under
            sampled overrides.
        scenario_name:
            Optional scenario label to run. If None, all enabled scenarios
            defined in the Monte Carlo config are executed.
        n_iterations:
            Optional override for the iteration count. If omitted, the value
            in the Monte Carlo config's [simulation] block is used.
        random_seed:
            Optional override for the RNG seed, useful for deterministic
            regression runs.
        parallel_workers:
            Optional override for the number of CPU processes.
        write_output:
            Whether to write CSV/JSONL output files. Default True for production,
            False for testing to skip I/O overhead.

    Returns:
        Dict mapping scenario_name -> MonteCarloResult.
    """
    return run_monte_carlo_analysis(
        base_config_path=base_config_path,
        scenario_config_path=mc_config_path,
        scenario_name=scenario_name,
        n_iterations=n_iterations,
        random_seed=random_seed,
        parallel_workers=parallel_workers,
        write_output=write_output,
    )


def run_monte_carlo_analysis(
    base_config_path: str,
    scenario_config_path: str = "config/monte_carlo_defaults.yaml",
    scenario_name: str | None = None,
    n_iterations: int | None = None,
    random_seed: int | None = None,
    parallel_workers: int | None = None,
    write_output: bool = True,
) -> dict[str, MonteCarloResult]:
    """
    Run Monte Carlo simulation with flexible parameter system.

    Supports:
    - Standard parameters (direct config overrides with distributions)
    - Derived parameters (calculated from target constraints)
    - Multiple scenarios (comparative risk analysis)
    - Parallel execution for speed
    - Graceful error handling (isolated iteration failures)

    The engine uses a *single* numpy Generator per run to ensure:
    - Reproducibility: (base_config, mc_config, seed) ⇒ deterministic results
    - Common random numbers (CRN) across scenarios:
      Shared unit hypercube samples for parameters with the same variable_name.

    Args:
        base_config_path: Path to base scenario YAML
        scenario_config_path: Path to Monte Carlo configuration YAML
        scenario_name: Specific scenario to run (None = all enabled scenarios)
        n_iterations: Override default iteration count
        random_seed: Override default random seed for reproducibility
        parallel_workers: Number of CPU cores (None = auto-detect)
        write_output: Whether to write output files (default True)

    Returns:
        Dict mapping scenario names to MonteCarloResult objects

    Raises:
        FileNotFoundError: If config files not found
        ValueError: If MC configuration invalid
    """
    logger.info("Starting Monte Carlo analysis: %s", base_config_path)

    # ===== P1.1 OPTIMIZATION: Load from cache if available =====
    if scenario_config_path in _CONFIG_CACHE:
        logger.info("Loading MC config from cache: %s", scenario_config_path)
        mc_config = _CONFIG_CACHE[scenario_config_path]
    else:
        # Load + validate Monte Carlo configuration
        mc_config = _load_monte_carlo_config(scenario_config_path)
        _CONFIG_CACHE[scenario_config_path] = mc_config

    # Simulation settings
    sim_cfg = mc_config.simulation
    iterations = int(n_iterations or sim_cfg.iterations)

    seed = random_seed if random_seed is not None else sim_cfg.random_seed
    workers = parallel_workers or sim_cfg.parallel_workers or mp.cpu_count()
    sampler = (sim_cfg.sampler or "lhs").strip().lower()

    logger.info(
        "Simulation: %s iterations, seed=%s, workers=%s, sampler=%s, write_output=%s",
        iterations,
        seed,
        workers,
        sampler,
        write_output,
    )

    # Single RNG for the whole run (LHS/Sobol seeds + derived targets).
    rng = np.random.default_rng(seed)

    # Load scenarios (validated MonteCarloScenario objects)
    scenarios = _load_scenarios(mc_config, scenario_name)
    logger.info("Loaded %d scenario(s) to run", len(scenarios))

    # Build global parameter name universe for CRN
    global_param_names = _compute_global_param_names(scenarios)
    n_dim = len(global_param_names)

    # Generate unit hypercube samples once for *all* scenarios
    unit_samples = _generate_unit_samples(
        n_dim=n_dim,
        n_samples=iterations,
        sampler=sampler,
        rng=rng,
    )

    # Run each scenario
    results: dict[str, MonteCarloResult] = {}
    for scenario in scenarios:
        logger.info("Running scenario: %s", scenario.name)

        try:
            scenario_samples = _build_samples_for_scenario(
                standard_params=scenario.standard_params,
                derived_params=scenario.derived_params,
                unit_samples=unit_samples,
                global_param_names=global_param_names,
                rng=rng,
            )

            result = _run_single_scenario(
                base_config_path=base_config_path,
                scenario=scenario,
                samples=scenario_samples,
                parallel_workers=workers,
                write_output=write_output,
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


def _load_monte_carlo_config(config_path: str) -> MonteCarloConfig:
    """
    Load and validate Monte Carlo configuration from YAML.

    Args:
        config_path: Path to monte_carlo_defaults.yaml

    Returns:
        Validated MonteCarloConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If YAML structure invalid
    """
    yaml_file = Path(config_path)
    if not yaml_file.exists():
        raise FileNotFoundError(f"Monte Carlo config not found: {config_path}")

    with yaml_file.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Monte Carlo config at {config_path} must be a mapping")

    try:
        mc_config = MonteCarloConfig.model_validate(raw)
    except ValidationError as exc:
        logger.error("Monte Carlo config validation failed: %s", exc)
        raise ValueError(f"Monte Carlo config validation failed: {exc}") from exc

    # Additional sanity: required sections
    if not mc_config.standard_parameters:
        raise ValueError(
            "Monte Carlo config missing required section: standard_parameters"
        )

    logger.info("Loaded Monte Carlo config from %s", config_path)
    return mc_config


def _load_scenarios(
    mc_config: MonteCarloConfig,
    scenario_name: str | None,
) -> list[MonteCarloScenario]:
    """
    Load scenario configurations from MC config.

    Args:
        mc_config: Validated MonteCarloConfig
        scenario_name: Specific scenario to load (None = all enabled)

    Returns:
        List of MonteCarloScenario objects

    Raises:
        ValueError: If scenario_name specified but not found
    """
    scenarios_config = mc_config.scenarios or []

    base_standard_cfg = mc_config.standard_parameters
    base_derived_cfg = mc_config.derived_parameters or []

    # If no scenarios defined, create default from standard parameters
    if not scenarios_config:
        logger.info("No scenarios defined, using default from standard parameters")
        standard_params = _parse_distributions(base_standard_cfg)
        derived_params = _parse_derived_parameters(base_derived_cfg)

        return [
            MonteCarloScenario(
                name="default",
                description="Default scenario from standard parameters",
                standard_params=standard_params,
                derived_params=derived_params,
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

        standard_params_cfg = overrides.get("standard_parameters", base_standard_cfg)
        derived_params_cfg = overrides.get("derived_parameters", base_derived_cfg)

        standard_params = _parse_distributions(standard_params_cfg)
        derived_params = _parse_derived_parameters(derived_params_cfg)

        scenario = MonteCarloScenario(
            name=scenario_dict["name"],
            description=scenario_dict.get("description", ""),
            standard_params=standard_params,
            derived_params=derived_params,
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
        except (ValidationError, ValueError, TypeError) as exc:
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
            # Parse target distribution – note: MonteCarlo YAML for derived
            # parameters usually *does not* include variable_name in the
            # target_distribution block, so we construct a Distribution
            # with a synthetic variable_name solely for sampling.
            target_dist_cfg = dict(param_dict["target_distribution"])
            target_dist_cfg.setdefault("variable_name", param_dict["variable_name"])

            target_dist = Distribution(**target_dist_cfg)
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

        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            logger.error("Invalid derived parameter: %s", param_dict)
            raise ValueError(f"Derived parameter validation failed: {exc}") from exc

    return derived_params


# ---------------------------------------------------------------------------
# Sampling: common random numbers (CRN) + samplers
# ---------------------------------------------------------------------------


def _compute_global_param_names(
    scenarios: Iterable[MonteCarloScenario],
) -> list[str]:
    """
    Compute the global set of parameter names across all scenarios.

    This is used to build a shared unit hypercube sample matrix
    so that parameters with the same variable_name share the same
    underlying random draws across scenarios (CRN).
    """
    names: set[str] = set()
    for scenario in scenarios:
        for p in scenario.standard_params:
            names.add(p.variable_name)
    # Stable ordering for reproducibility
    return sorted(names)


def _generate_unit_samples(
    n_dim: int,
    n_samples: int,
    sampler: str,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate unit hypercube samples in [0, 1]^n_dim for the MC run.

    Samplers:
      - lhs: stratified Latin Hypercube Sampling (via SALib)
      - sobol: Sobol low-discrepancy sequence (via SALib)
      - random: i.i.d. uniform

    If n_dim == 0, this returns an (n_samples, 0) array so that
    downstream code can still iterate over iterations for derived
    parameters only.
    """
    if n_dim == 0:
        return np.zeros((n_samples, 0), dtype=float)

    sampler = sampler.strip().lower()
    if sampler not in {"lhs", "sobol", "random"}:
        logger.warning("Unknown sampler '%s', falling back to 'lhs'", sampler)
        sampler = "lhs"

    problem = {
        "num_vars": n_dim,
        # Names are not used directly; distribution mapping is scenario-specific.
        "names": [f"x{i}" for i in range(n_dim)],
        "bounds": [[0.0, 1.0]] * n_dim,
    }

    if sampler == "random":
        return rng.uniform(0.0, 1.0, size=(n_samples, n_dim))

    if sampler == "lhs":
        seed_for_lhs = int(rng.integers(0, 2**32 - 1))
        unit_samples = lhs.sample(problem, n_samples, seed=seed_for_lhs)
        return np.asarray(unit_samples, dtype=float)

    # Sobol: SALib expects N as a power of 2; over-sample and slice down.
    seed_for_sobol = int(rng.integers(0, 2**32 - 1))
    n_base = 1
    while n_base < n_samples:
        n_base *= 2

    sobol_samples = sobol.sample(
        problem,
        N=n_base,
        calc_second_order=False,
        seed=seed_for_sobol,
    )
    sobol_samples = np.asarray(sobol_samples, dtype=float)
    return sobol_samples[:n_samples, :]


def _generate_lhs_samples(
    parameters: list[Distribution],
    derived_parameters: list[Any] | None,
    n_samples: int,
    random_seed: int | None = None,
) -> list[dict[str, float]]:
    """
    Backwards-compatible Latin Hypercube sampler used by legacy tests.

    This mirrors the older v14 signature so that tests like
    tests/analytics_layer/test_monte_carlo_v14.py keep working.

    - parameters: list of Distribution objects. We:
        * generate LHS draws on [0, 1]^d, then
        * map them through _transform_to_distribution per parameter.
    - derived_parameters: accepted but ignored (signature compatibility only).
    - n_samples: number of samples (rows) to generate.
    - random_seed: optional seed for reproducibility.

    Returns:
        List of dicts, one per sample:
        [
          {"param_name_1": value_1, "param_name_2": value_2, ...},
          ...
        ]
    """
    n_dim = len(parameters)
    if n_dim == 0:
        # Edge case: no parameters → still return a valid list
        return []

    problem = {
        "num_vars": n_dim,
        "names": [p.variable_name for p in parameters],
        "bounds": [[0.0, 1.0]] * n_dim,
    }

    seed = random_seed if random_seed is not None else None
    lhs_samples = lhs.sample(problem, n_samples, seed=seed)
    unit_samples = np.asarray(lhs_samples, dtype=float)

    samples: list[dict[str, float]] = []
    for i in range(n_samples):
        row: dict[str, float] = {}
        for j, dist in enumerate(parameters):
            unit_value = float(unit_samples[i, j])
            row[dist.variable_name] = float(
                _transform_to_distribution(unit_value, dist)
            )
        samples.append(row)

    return samples


def _build_samples_for_scenario(
    standard_params: list[Distribution],
    derived_params: list[DerivedParameter],
    unit_samples: np.ndarray,
    global_param_names: list[str],
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """
    Build concrete override samples for a single scenario from the shared
    unit hypercube samples + scenario-specific distributions.

    - For each standard parameter, we:
      - Find its column index in the global_param_names list
      - Transform unit_samples[:, idx] to actual values via the scenario's
        Distribution object.

    - For each derived parameter, we:
      - Draw a unit value from rng.uniform(0, 1)
      - Transform using target_distribution
      - Store under the key f"_target_{variable_name}"
    """
    n_samples = unit_samples.shape[0]
    samples: list[dict[str, Any]] = [{} for _ in range(n_samples)]

    # Map variable name -> column index once.
    name_to_idx = {name: i for i, name in enumerate(global_param_names)}

    # Standard parameters
    for param in standard_params:
        idx = name_to_idx.get(param.variable_name)
        if idx is None:
            # This scenario has a parameter that does not appear in the global
            # set (should not happen if configs are consistent), but we can
            # still generate independent draws for it.
            logger.warning(
                "Parameter %s not in global_param_names; "
                "falling back to independent random sampling.",
                param.variable_name,
            )
            for i in range(n_samples):
                unit_value = float(rng.uniform(0.0, 1.0))
                samples[i][param.variable_name] = _transform_to_distribution(
                    unit_value, param
                )
            continue

        for i in range(n_samples):
            unit_value = float(unit_samples[i, idx])
            samples[i][param.variable_name] = _transform_to_distribution(
                unit_value, param
            )

    # Derived parameter targets
    for derived_param in derived_params:
        target_dist = derived_param.target_distribution
        target_key = f"_target_{derived_param.variable_name}"

        for i in range(n_samples):
            unit_value = float(rng.uniform(0.0, 1.0))
            target_value = _transform_to_distribution(unit_value, target_dist)
            samples[i][target_key] = target_value

    logger.info(
        "Built %d concrete samples for scenario (std=%d, derived=%d)",
        len(samples),
        len(standard_params),
        len(derived_params),
    )
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
        unit_value: Value in [0, 1] from the sampler
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

        std_raw = getattr(distribution, "std", None)
        if std_raw is None:
            raise ValueError("normal distribution requires std > 0")
        std = float(std_raw)

        mean_raw = getattr(distribution, "mean", None)
        if mean_raw is None:
            raise ValueError("normal distribution requires mean to be set")
        mean = float(mean_raw)

        return float(norm.ppf(unit_value, loc=mean, scale=std))

    # --- Lognormal distribution --------------------------------------------
    if dist_type == "lognormal":
        from scipy.stats import lognorm

        std_raw = getattr(distribution, "std", None)
        if std_raw is None:
            raise ValueError("lognormal distribution requires std > 0")
        std = float(std_raw)

        mean_raw = getattr(distribution, "mean", None)
        if mean_raw is None:
            raise ValueError("lognormal distribution requires mean to be set")
        mean = float(mean_raw)

        return float(
            lognorm.ppf(
                unit_value,
                s=std,
                scale=float(np.exp(mean)),
            )
        )

    # --- Triangular distribution -------------------------------------------
    if dist_type == "triangular":
        from scipy.stats import triang

        min_val_raw = getattr(distribution, "min_val", None)
        mode_raw = getattr(distribution, "mode", None)
        max_val_raw = getattr(distribution, "max_val", None)

        if min_val_raw is None or mode_raw is None or max_val_raw is None:
            raise ValueError(
                "triangular distribution requires min_val, mode and max_val"
            )

        min_val = float(min_val_raw)
        mode = float(mode_raw)
        max_val = float(max_val_raw)

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
        min_val_raw = getattr(distribution, "min_val", None)
        max_val_raw = getattr(distribution, "max_val", None)

        if min_val_raw is None or max_val_raw is None:
            raise ValueError("uniform distribution requires min_val and max_val")

        min_val = float(min_val_raw)
        max_val = float(max_val_raw)
        span = max_val - min_val
        if span <= 0:
            raise ValueError("uniform distribution requires min < max")

        return float(min_val + unit_value * span)

    # --- Fallback for unknown/distinct types -------------------------------
    raise ValueError(f"Unsupported distribution type: {dist_type!r}")


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------


def _run_single_scenario(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    parallel_workers: int,
    write_output: bool = True,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for a single scenario.

    Args:
        base_config_path: Path to base scenario YAML
        scenario: MonteCarloScenario configuration
        samples: List of concrete parameter samples (overrides) for each iteration
        parallel_workers: Number of parallel processes
        write_output: Whether to write CSV/JSONL output files

    Returns:
        MonteCarloResult with statistical summary
    """
    iterations = len(samples)
    logger.info(
        "Running scenario '%s' with %d iterations and %d workers",
        scenario.name,
        iterations,
        parallel_workers,
    )

    if parallel_workers > 1:
        results = _run_parallel_iterations(
            base_config_path=base_config_path,
            scenario=scenario,
            samples=samples,
            n_workers=parallel_workers,
            write_output=write_output,
        )
    else:
        results = _run_serial_iterations(
            base_config_path=base_config_path,
            scenario=scenario,
            samples=samples,
            write_output=write_output,
        )

    return _aggregate_results(results, iterations, scenario.name)


# ===== P1.3 OPTIMIZATION: ThreadPoolExecutor =====
def _thread_safe_iteration_worker(
    iteration_idx: int,
    base_config_path: str,
    scenario: MonteCarloScenario,
    sample: dict[str, Any],
    write_output: bool = True,
) -> tuple[int, dict[str, float] | None]:
    """
    Thread-safe Monte Carlo iteration worker.

    Each thread:
    1. Gets unique iteration_idx
    2. Executes iteration independently
    3. Returns (iteration_idx, result) to maintain order

    Args:
        iteration_idx: Unique iteration number (0 to N-1) for determinism
        base_config_path: Path to base scenario YAML
        scenario: MonteCarloScenario configuration
        sample: Parameter sample for this iteration
        write_output: Whether to write output files

    Returns:
        Tuple of (iteration_idx, result_dict_or_none) for order preservation
    """
    try:
        result = _run_single_iteration(
            base_config_path=base_config_path,
            scenario=scenario,
            sample=sample,
            write_output=write_output,
        )
        return (iteration_idx, result)
    except Exception as exc:
        logger.debug("Thread %d failed: %s", iteration_idx, exc)
        return (iteration_idx, None)


def _run_parallel_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    n_workers: int,
    write_output: bool = True,
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations in parallel using ThreadPoolExecutor.

    ===== P1.3 OPTIMIZATION =====
    Replaced multiprocessing.Pool with concurrent.futures.ThreadPoolExecutor
    for faster task spawning and better interoperability with I/O-bound operations.
    """
    total_iterations = len(samples)
    results: list[dict[str, float] | None] = [None] * total_iterations

    logger.info(
        "Running %d iterations with %d threads (ThreadPoolExecutor)",
        total_iterations,
        n_workers,
    )

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                _thread_safe_iteration_worker,
                idx,
                base_config_path,
                scenario,
                samples[idx],
                write_output,
            ): idx
            for idx in range(total_iterations)
        }

        # Collect results as they complete
        completed = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                iteration_idx, result = future.result()
                results[iteration_idx] = result
                completed += 1

                if completed % 100 == 0 or completed == total_iterations:
                    logger.info(
                        "  Thread progress: %d/%d iterations",
                        completed,
                        total_iterations,
                    )
            except Exception as exc:
                logger.error("Thread iteration %d failed: %s", idx, exc)
                results[idx] = None

    return results


def _run_serial_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    write_output: bool = True,
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations serially (single-threaded).
    """
    results: list[dict[str, float] | None] = []
    total = len(samples)
    for idx, sample in enumerate(samples, start=1):
        if idx % 100 == 0 or idx == total:
            logger.info("  Progress: %d/%d iterations", idx, total)
        result = _run_single_iteration(base_config_path, scenario, sample, write_output)
        results.append(result)
    return results


def _run_single_iteration(
    base_config_path: str | Path,
    scenario: Any,
    sample: Mapping[str, float],
    write_output: bool = True,
) -> dict[str, float] | None:
    """
    Run a single Monte Carlo iteration.

    Contract (CCCDIR-aligned):

    - Takes a base config path, a MonteCarloScenario-like object, and a sample
      mapping (param_path -> sampled value).
    - Builds overrides by combining scenario-level overrides and the sample.
    - Optionally applies derived-parameter solvers (tariff / DSCR, etc.).
    - Evaluates the scenario via `evaluate_with_overrides`.
    - Returns a dict[str, float] of KPIs, or None if the iteration fails.
    """
    try:
        # ------------------------------------------------------------------
        # 1) Start with scenario-level base overrides (if present)
        # ------------------------------------------------------------------
        overrides: dict[str, Any] = {}

        base_overrides = getattr(scenario, "base_overrides", None)
        if isinstance(base_overrides, Mapping):
            overrides.update(base_overrides)

        # ------------------------------------------------------------------
        # 2) Apply sample overrides (param_path -> value)
        # ------------------------------------------------------------------
        for dotted_key, value in sample.items():
            path_parts = dotted_key.split(".")
            _set_nested_value(overrides, path_parts, value)

        # ------------------------------------------------------------------
        # 3) Apply derived-parameter solvers (optional)
        #    - Use either `derived_params` or legacy `derived_parameters`
        # ------------------------------------------------------------------
        derived_params = getattr(scenario, "derived_params", None)
        if derived_params is None:
            derived_params = getattr(scenario, "derived_parameters", [])

        for derived_param in derived_params:
            try:
                # Try to fetch a target value from the sample, keyed by derive_from
                raw_target = sample.get(derived_param.derive_from)
                target_value: float | None
                if raw_target is None:
                    target_value = None
                else:
                    target_value = float(raw_target)

                solver = get_solver(derived_param.derive_from)

                derived_value = solver(
                    base_config_path=base_config_path,
                    base_overrides=overrides,
                    target_irr=(
                        target_value
                        if (
                            target_value is not None
                            and "irr" in derived_param.derive_from
                        )
                        else None
                    ),
                    target_dscr=(
                        target_value
                        if (
                            target_value is not None
                            and "dscr" in derived_param.derive_from
                        )
                        else None
                    ),
                    **derived_param.solver_config,
                )

                path_parts = derived_param.variable_name.split(".")
                _set_nested_value(overrides, path_parts, derived_value)

            except Exception as exc:  # pragma: no cover - rare path
                # **IMPORTANT CHANGE**:
                # Do NOT drop the whole iteration if the solver fails.
                # Log the failure and continue with existing overrides.
                logger.warning(
                    "Solver failed for %s: %s. Continuing without derived update.",
                    getattr(derived_param, "variable_name", "<unknown>"),
                    exc,
                )
                # Break out of the derived-param loop for this iteration to
                # avoid repeated failures on the same misconfigured solver.
                break

        # ------------------------------------------------------------------
        # 4) Evaluate scenario with all parameter values via evaluation_v14
        # ------------------------------------------------------------------
        kpis = evaluate_with_overrides(base_config_path, overrides)

        # Make the type explicit and keep a shallow copy in case callers mutate it
        typed_kpis: dict[str, float] = dict(kpis)
        return typed_kpis

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
    path: List[str],
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

    Also computes simple convergence / precision estimates for key metrics:
    standard errors (SE = std / sqrt(N_success)) for project_irr,
    project_npv and dscr_min. These can be turned into approximate
    95% confidence intervals via mean ± 1.96 * SE in downstream reports.
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

    n_success = len(successful_results)

    # Means / percentiles
    irr_mean = float(np.mean(project_irr))
    irr_std = float(np.std(project_irr)) if n_success > 0 else 0.0
    irr_p10 = float(np.percentile(project_irr, 10))
    irr_p50 = float(np.percentile(project_irr, 50))
    irr_p90 = float(np.percentile(project_irr, 90))

    npv_mean = float(np.mean(project_npv))
    npv_p10 = float(np.percentile(project_npv, 10))
    npv_p50 = float(np.percentile(project_npv, 50))
    npv_p90 = float(np.percentile(project_npv, 90))

    dscr_p10 = float(np.percentile(dscr_min, 10))
    dscr_p50 = float(np.percentile(dscr_min, 50))

    # Standard errors (simple precision estimates)
    # Note: we use the population std here for continuity with existing
    # behaviour; SE is still std / sqrt(N_success).
    sqrt_n = math.sqrt(n_success) if n_success > 0 else 1.0
    irr_se = irr_std / sqrt_n if n_success > 0 else 0.0
    npv_std = float(np.std(project_npv)) if n_success > 0 else 0.0
    npv_se = npv_std / sqrt_n if n_success > 0 else 0.0
    dscr_std = float(np.std(dscr_min)) if n_success > 0 else 0.0
    dscr_se = dscr_std / sqrt_n if n_success > 0 else 0.0

    return MonteCarloResult(
        iterations=total_iterations,
        project_irr_mean=irr_mean,
        project_irr_std=irr_std,
        project_irr_p10=irr_p10,
        project_irr_p50=irr_p50,
        project_irr_p90=irr_p90,
        project_npv_mean=npv_mean,
        project_npv_p10=npv_p10,
        project_npv_p50=npv_p50,
        project_npv_p90=npv_p90,
        dscr_min_p10=dscr_p10,
        dscr_min_p50=dscr_p50,
        failed_iterations=failed_count,
        raw_results=successful_results,
        scenario_name=scenario_name,
        # New precision fields – MonteCarloResult should allow these.
        project_irr_se=irr_se,
        project_npv_se=npv_se,
        dscr_min_se=dscr_se,
    )


__all__ = [
    "run_monte_carlo",
    "run_monte_carlo_analysis",
    "_load_monte_carlo_config",
    "_load_scenarios",
    "_parse_distributions",
    "_parse_derived_parameters",
    "_compute_global_param_names",
    "_generate_unit_samples",
    "_generate_lhs_samples",
    "_build_samples_for_scenario",
    "_transform_to_distribution",
    "_thread_safe_iteration_worker",
    "_run_single_scenario",
    "_run_parallel_iterations",
    "_run_serial_iterations",
    "_run_single_iteration",
    "_build_overrides_from_sample",
    "_set_nested_value",
    "_aggregate_results",
]
# EOF
