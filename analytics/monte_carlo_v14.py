from __future__ import annotations

import logging
import math
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List, cast

import multiprocess as mp
import numpy as np
import yaml
from pydantic import BaseModel, Field, ValidationError
from SALib.sample import latin as lhs
from SALib.sample import sobol

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

# Suppress numpy warnings during parallel execution
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ===========================================================================
# Pydantic config models (schema guard for YAML)
# ===========================================================================


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

    iterations: int = Field(default=MONTE_CARLO_ITERATIONS, ge=1)
    random_seed: int | None = None
    parallel_workers: int | None = Field(default=None, ge=1)
    sampler: str = Field(default="lhs")

    class Config:
        extra = "ignore"


class MonteCarloConfig(BaseModel):
    """
    Top-level Monte Carlo configuration schema.

    Expected YAML structure (Sprint 9):

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
      - variable_name: financial.tariff_lkr_per_kwh
        derive_from: target_project_irr
        target_distribution: { ... }
        solver_config: { ... }

    scenarios:
      - name: base_case
        description: "Base case"
        enabled: true
        parameter_overrides:
          standard_parameters: [ ... ]
          derived_parameters: [ ... ]

    correlations:      # optional, currently accepted but not applied
      enabled: false
      method: cholesky
      matrix: [...]

    output:            # optional, for future VaR/CVaR/custom metrics handling
      save_path: ...
      save_raw_results: true
      risk_metrics: { ... }
      custom_metrics: [ ... ]

    regression_expectations:
      scenario_name: base_case
      metrics: { ... }   # used only by tests, ignored by engine
    """

    simulation: SimulationConfig
    standard_parameters: list[dict[str, Any]]
    derived_parameters: list[dict[str, Any]] = Field(default_factory=list)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    correlations: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    regression_expectations: dict[str, Any] | None = None

    class Config:
        extra = "ignore"


# ===========================================================================
# Validation helpers (used by tests + runtime)
# ===========================================================================


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


def _merge_param_dicts(
    base_list: list[dict[str, Any]],
    overrides: list[dict[str, Any]] | None,
    *,
    key: str = "variable_name",
) -> list[dict[str, Any]]:
    """Merge base + overrides keyed by `key`.

    - Base list provides default entries.
    - Overrides update matching entries by `variable_name`.
    - For derived parameters, nested `target_distribution` and
      `solver_config` dicts are merged rather than blindly replaced.
    """
    if not overrides:
        return list(base_list)

    merged: Dict[str, dict[str, Any]] = {}

    # Start with base entries
    for item in base_list:
        name = item.get(key)
        if not name:
            continue
        merged[name] = dict(item)

    # Apply overrides
    for over in overrides:
        name = over.get(key)
        if not name:
            continue

        base_entry = merged.get(name, {})
        new_entry = dict(base_entry)

        for field_name, value in over.items():
            if field_name in {"target_distribution", "solver_config"} and isinstance(
                value, dict
            ):
                base_sub = base_entry.get(field_name, {})
                if isinstance(base_sub, dict):
                    combined = {**base_sub, **value}
                else:
                    combined = value
                new_entry[field_name] = combined
            else:
                new_entry[field_name] = value

        merged[name] = new_entry

    # Preserve original base order, followed by any new names at the end
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in base_list:
        name = item.get(key)
        if not name or name not in merged:
            continue
        ordered.append(merged[name])
        seen.add(name)

    for name, item in merged.items():
        if name not in seen:
            ordered.append(item)

    return ordered


# ===========================================================================
# Public entry points
# ===========================================================================


def run_monte_carlo(
    *,
    mc_config_path: str,
    base_config_path: str,
    scenario_name: str | None = None,
    n_iterations: int | None = None,
    random_seed: int | None = None,
    parallel_workers: int | None = None,
) -> dict[str, MonteCarloResult]:
    """
    Canonical Sprint 9 public API for the v14 Monte Carlo engine.

    This is the front door for:
      - Tests (including the toy regression harness),
      - CLI wrappers,
      - Notebooks / analytics layers.

    Parameters
    ----------
    mc_config_path:
        Path to MC configuration YAML
        (e.g. config/monte_carlo_defaults.yaml or
              config/monte_carlo_regression_toy.yaml).
    base_config_path:
        Path to the base v14 scenario YAML
        (e.g. scenarios/dutchbay_lendercase_2025Q4.yaml).
    scenario_name:
        Optional specific scenario name to evaluate. None = all enabled.
    n_iterations:
        Optional override for the iteration count in the MC config.
    random_seed:
        Optional override for the random seed.
    parallel_workers:
        Optional override for parallel workers.

    Returns
    -------
    Dict[str, MonteCarloResult]
        Mapping from scenario_name -> MonteCarloResult.
    """
    return run_monte_carlo_analysis(
        base_config_path=base_config_path,
        scenario_config_path=mc_config_path,
        scenario_name=scenario_name,
        n_iterations=n_iterations,
        random_seed=random_seed,
        parallel_workers=parallel_workers,
    )


def run_monte_carlo_analysis(
    base_config_path: str,
    scenario_config_path: str = "config/monte_carlo_defaults.yaml",
    scenario_name: str | None = None,
    n_iterations: int | None = None,
    random_seed: int | None = None,
    parallel_workers: int | None = None,
) -> dict[str, MonteCarloResult]:
    """
    Backwards-compatible front door for the v14 Monte Carlo engine.

    New code should prefer `run_monte_carlo`, which calls this function.

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
    """
    logger.info("Starting Monte Carlo analysis: %s", base_config_path)

    # Load + validate Monte Carlo configuration
    mc_config = _load_monte_carlo_config(scenario_config_path)

    # Simulation settings
    sim_cfg = mc_config.simulation
    iterations = int(n_iterations or sim_cfg.iterations)

    seed = random_seed if random_seed is not None else sim_cfg.random_seed
    workers = parallel_workers or sim_cfg.parallel_workers or mp.cpu_count()
    sampler = (sim_cfg.sampler or "lhs").strip().lower()

    logger.info(
        "Simulation: %s iterations, seed=%s, workers=%s, sampler=%s",
        iterations,
        seed,
        workers,
        sampler,
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
                standard_params=scenario.standard_parameters,
                derived_params=scenario.derived_parameters,
                unit_samples=unit_samples,
                global_param_names=global_param_names,
                rng=rng,
            )

            result = _run_single_scenario(
                base_config_path=base_config_path,
                scenario=scenario,
                samples=scenario_samples,
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


# ===========================================================================
# Config loading
# ===========================================================================


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
        mc_config = MonteCarloConfig.parse_obj(raw)
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

        overrides = scenario_dict.get("parameter_overrides", {}) or {}

        standard_over = overrides.get("standard_parameters", []) or []
        derived_over = overrides.get("derived_parameters", []) or []

        standard_params_cfg = _merge_param_dicts(
            base_standard_cfg, standard_over, key="variable_name"
        )
        derived_params_cfg = _merge_param_dicts(
            base_derived_cfg, derived_over, key="variable_name"
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


# ===========================================================================
# Parsing distributions and derived parameters
# ===========================================================================


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
        # Strip cosmetic / non-schema fields that the Distribution model
        # does not know about (e.g. description), so that the YAML can
        # remain human-readable without breaking the strict schema.
        cleaned: dict[str, Any] = dict(param_dict)
        cleaned.pop("description", None)

        try:
            dist = Distribution(**cleaned)
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
            # Pull out the target_distribution spec and make it compatible
            # with the Distribution schema:
            #  - inject a variable_name if missing (use the parent variable_name)
            #  - strip cosmetic fields like description that Distribution
            #    does not accept.
            td_raw = param_dict["target_distribution"]
            if not isinstance(td_raw, dict):
                raise ValueError("target_distribution must be a mapping")

            td_clean: dict[str, Any] = dict(td_raw)
            td_clean.pop("description", None)

            if "variable_name" not in td_clean:
                td_clean["variable_name"] = param_dict.get(
                    "variable_name", "_target_param"
                )

            target_dist = Distribution(**td_clean)
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


# ===========================================================================
# Sampling: common random numbers (CRN) + samplers
# ===========================================================================


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
        for p in scenario.standard_parameters:
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
    Transform unit hypercube value [0, 1] to an actual draw from the
    specified Distribution.

    This is the *only* place where raw Distribution objects are turned into
    numeric samples, so we keep the parameter checks tight and explicit.

    Raises:
        ValueError: if required parameters are missing or inconsistent.
    """
    # Always run the shared validator so tests calling this directly see
    # the same semantics as the parsing helpers.
    _validate_distribution_for_sampling(distribution)

    dist_type = _normalise_dist_type(getattr(distribution, "dist_type", None))

    # --- Normal -------------------------------------------------------------
    if dist_type == "normal":
        from scipy.stats import norm

        mean_raw = getattr(distribution, "mean", None)
        std_raw = getattr(distribution, "std", None)

        if mean_raw is None:
            raise ValueError("normal distribution requires 'mean' to be set")
        if std_raw is None:
            raise ValueError("normal distribution requires 'std' to be set")

        mean = float(mean_raw)
        std = float(std_raw)

        return float(norm.ppf(unit_value, loc=mean, scale=std))

    # --- Lognormal ----------------------------------------------------------
    if dist_type == "lognormal":
        from scipy.stats import lognorm

        mean_raw = getattr(distribution, "mean", None)
        std_raw = getattr(distribution, "std", None)

        if mean_raw is None:
            raise ValueError("lognormal distribution requires 'mean' to be set")
        if std_raw is None:
            raise ValueError("lognormal distribution requires 'std' to be set")

        mean = float(mean_raw)
        std = float(std_raw)

        # Using exp(mean) as the scale parameter; std as shape (sigma)
        return float(
            lognorm.ppf(
                unit_value,
                s=std,
                scale=float(np.exp(mean)),
            )
        )

    # --- Triangular ---------------------------------------------------------
    if dist_type == "triangular":
        from scipy.stats import triang

        min_raw = getattr(distribution, "min_val", None)
        mode_raw = getattr(distribution, "mode", None)
        max_raw = getattr(distribution, "max_val", None)

        if min_raw is None or mode_raw is None or max_raw is None:
            raise ValueError(
                "triangular distribution requires min_val, mode and max_val"
            )

        min_val = float(min_raw)
        mode = float(mode_raw)
        max_val = float(max_raw)

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

    # --- Uniform ------------------------------------------------------------
    if dist_type == "uniform":
        min_raw = getattr(distribution, "min_val", None)
        max_raw = getattr(distribution, "max_val", None)

        if min_raw is None or max_raw is None:
            raise ValueError("uniform distribution requires min_val and max_val")

        min_val = float(min_raw)
        max_val = float(max_raw)
        span = max_val - min_val
        if span <= 0:
            raise ValueError("uniform distribution requires max_val > min_val")

        return float(min_val + unit_value * span)

    # --- Fallback -----------------------------------------------------------
    raise ValueError(f"Unsupported distribution type: {dist_type!r}")


# ===========================================================================
# Scenario execution
# ===========================================================================


def _run_single_scenario(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    parallel_workers: int,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for a single scenario.
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
        )
    else:
        results = _run_serial_iterations(
            base_config_path=base_config_path,
            scenario=scenario,
            samples=samples,
        )

    return _aggregate_results(results, iterations, scenario.name)


def _run_parallel_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    n_workers: int,
) -> list[dict[str, Any] | None]:
    """
    Run Monte Carlo iterations in parallel using multiprocessing.
    """
    args_iter = ((base_config_path, scenario, sample) for sample in samples)

    with mp.Pool(processes=n_workers) as pool:
        raw_results = pool.map(_iteration_worker, args_iter)

    # pool.map returns list[Any]; we know the worker returns dict[str, Any] | None.
    results = cast(List[dict[str, Any] | None], list(raw_results))
    return results


def _iteration_worker(
    args: tuple[str, MonteCarloScenario, dict[str, Any]],
) -> dict[str, float] | None:
    """
    Top-level worker for multiprocessing. Required to avoid nested function
    pickling issues on some platforms.
    """
    base_config_path, scenario, sample = args
    return _run_single_iteration(base_config_path, scenario, sample)


def _run_serial_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations serially (single-threaded).
    """
    results: list[dict[str, float] | None] = []
    total = len(samples)
    for idx, sample in enumerate(samples, start=1):
        if idx % 100 == 0 or idx == total:
            logger.info("  Progress: %d/%d iterations", idx, total)
        result = _run_single_iteration(base_config_path, scenario, sample)
        results.append(result)
    return results


def _run_single_iteration(
    base_config_path: str,
    scenario: MonteCarloScenario,
    sample: dict[str, Any],
) -> dict[str, Any] | None:
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
        # kpis is a dict[str, Any]; that matches the annotated return type.
        return kpis

    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Iteration failed: %s", exc)
        return None


# ===========================================================================
# Overrides + aggregation
# ===========================================================================


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
    results: list[dict[str, Any] | None],
    total_iterations: int,
    scenario_name: str,
) -> MonteCarloResult:
    """
    Aggregate iteration results into statistical summary.

    Also computes simple convergence / precision estimates for key metrics:
    standard errors (SE = std / sqrt(N_success)) for project_irr,
    project_npv and dscr_min.
    """
    successful_results: list[dict[str, Any]] = [r for r in results if r is not None]
    failed_count = total_iterations - len(successful_results)

    if not successful_results:
        raise ValueError(
            "All Monte Carlo iterations failed. Check solver configuration."
        )

    logger.info("Aggregating %d successful iterations", len(successful_results))

    project_irr = np.array(
        [float(r["project_irr"]) for r in successful_results],
        dtype=float,
    )
    project_npv = np.array(
        [float(r["project_npv"]) for r in successful_results],
        dtype=float,
    )
    dscr_min = np.array(
        [float(r["dscr_min"]) for r in successful_results],
        dtype=float,
    )

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

    # Standard errors (precision estimates)
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
    "_generate_unit_samples",
    "_build_samples_for_scenario",
    "_transform_to_distribution",
    "_build_overrides_from_sample",
    "_aggregate_results",
]
# EOF
