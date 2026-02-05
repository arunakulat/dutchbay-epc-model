from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union, cast

from analytics.contracts_v14 import CasperResult, MonteCarloResult
from analytics.contracts_v14 import ScenarioResult as ScenarioResultContract
from analytics.contracts_v14 import SensitivitySuite

# CRITICAL FIX: Import lender-grade pipeline (was: analytics.pipeline_v14)
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

# CRITICAL P1 FIX: NO imports from analytics.sensitivity at module level
# All sensitivity/tail-risk imports are LAZY (inside functions only)
# This breaks: evaluation_v14 → sensitivity_tail_risk → sensitivity.engine → evaluation_v14

logger = logging.getLogger(__name__)

# -*- coding: utf-8 -*-
"""
analytics.evaluation_v14

Canonical evaluation gateway for the v14 finance stack.
CESSPIT v14 / CASPER-GWTF Compliant

This module provides a SINGLE, typed entry point for analytics layers
(sensitivity, Monte Carlo, optimization):

    - evaluate_with_overrides(config_path, overrides, raw_config)
    - evaluate_scenario_from_dict(config, overrides)
    - evaluate_with_casper_tail_risk(...)

GWTF RULE: Evaluation gateway must be import-safe.
- NO imports from analytics.sensitivity, analytics.mc at module scope
- All enrichment imports are LAZY (inside functions)

Revision History:
- v14.4.2 (2025-12-23): P1 hotfix - Full lazy loading (no TYPE_CHECKING)
  - Remove all sensitivity imports from module scope
  - Tail-risk functions only imported inside evaluate_with_casper_tail_risk
- v14.4.1 (2025-12-23): P1 hotfix - Break circular import with sensitivity
  - Use TYPE_CHECKING for sensitivity_tail_risk imports
  - Add lazy loading for tail risk functions
- v14.4.0 (2025-12-23): Hardened for sensitivity/MC integration
  - Added raw_config parameter support
  - Fixed return type flexibility (full result vs KPIs)
  - Enhanced null safety for MC raw_results
"""


def run_monte_carlo_analysis(*args: Any, **kwargs: Any) -> Any:
    """
    Lazy proxy for the v14 Monte Carlo engine.
    """
    from analytics.monte_carlo_v14 import run_monte_carlo_analysis as _real_run_mc

    return _real_run_mc(*args, **kwargs)


def _deep_merge_config(
    base: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Recursively deep-merge two configuration dictionaries.

    Args:
        base: Base configuration mapping
        overrides: Override values to merge into base

    Returns:
        Merged configuration dict

    Example:
        >>> base = {"finance": {"capex_usd": 1000}, "project": {"name": "test"}}
        >>> overrides = {"finance": {"capex_usd": 1100}}
        >>> merged = _deep_merge_config(base, overrides)
        >>> merged["finance"]["capex_usd"]
        1100
        >>> merged["project"]["name"]
        'test'
    """
    result: dict[str, Any] = dict(base)

    for key, override_value in overrides.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(override_value, Mapping)
        ):
            base_mapping = cast(Mapping[str, Any], result[key])
            override_mapping = cast(Mapping[str, Any], override_value)
            result[key] = _deep_merge_config(base_mapping, override_mapping)
        else:
            result[key] = override_value

    return result


def normalize_kpi_dict(raw_kpis: Mapping[str, Any]) -> dict[str, float]:
    """
    Normalize KPI dict to {str -> float}.

    Filters out non-numeric values and logs warnings for skipped entries.

    Args:
        raw_kpis: Raw KPI mapping from pipeline result

    Returns:
        Normalized dict with only numeric (float-convertible) values

    Example:
        >>> kpis = {"project_irr": 0.145, "name": "test", "min_dscr": "1.45"}
        >>> normalized = normalize_kpi_dict(kpis)
        >>> normalized
        {'project_irr': 0.145, 'min_dscr': 1.45}
    """
    kpis: dict[str, float] = {}

    for key, value in raw_kpis.items():
        try:
            kpis[key] = float(value)
        except (TypeError, ValueError):
            logger.debug(
                "normalize_kpi_dict: skipping non-numeric KPI %r=%r (type=%s)",
                key,
                value,
                type(value).__name__,
            )
            continue

    return kpis


def _run_pipeline_with_config(
    config: Mapping[str, Any],
    validation_modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Internal helper: run v14 pipeline and return full result.

    Args:
        config: Complete scenario configuration
        validation_modules: Modules to validate (defaults to cashflow, debt)

    Returns:
        Full pipeline result dict with keys: status, kpis, annual_rows, debt_result, etc.

    Raises:
        TypeError: If pipeline result is malformed
    """
    if validation_modules is None:
        validation_modules = ["cashflow", "debt"]

    payload: Mapping[str, Any] = run_v14_pipeline(
        config=config,
        validation_mode="strict",
        validation_modules=validation_modules,
    )

    if not isinstance(payload, Mapping):
        raise TypeError(
            f"Expected pipeline result to be a mapping, got {type(payload).__name__}"
        )

    return dict(payload)


def evaluate_scenario_from_dict(
    config: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """
    Evaluate a scenario given an in-memory configuration dict.

    Args:
        config: Base configuration mapping
        overrides: Optional override values

    Returns:
        Normalized KPI dict {metric_name: float_value}

    Example:
        >>> config = load_scenario_config("scenarios/base.yaml")
        >>> kpis = evaluate_scenario_from_dict(config, {"finance.capex_usd": 1100})
        >>> kpis["project_irr"]
        0.142
    """
    merged_config = _deep_merge_config(config, overrides or {})
    result = _run_pipeline_with_config(merged_config)

    raw_kpis = result.get("kpis")
    if not isinstance(raw_kpis, Mapping):
        raise TypeError(
            f"Expected 'kpis' to be a mapping, got {type(raw_kpis).__name__}"
        )

    return normalize_kpi_dict(raw_kpis)


def evaluate_with_overrides(
    config_path: Optional[str | Path] = None,
    overrides: Mapping[str, Any] | None = None,
    *,
    raw_config: Optional[Mapping[str, Any]] = None,
    validation_modules: list[str] | None = None,
    return_full_result: bool = False,
) -> Union[dict[str, float], dict[str, Any]]:
    """
    Run a single scenario evaluation through the v14 pipeline.

    This is the canonical gateway for sensitivity and optimization engines.

    Args:
        config_path: Path to scenario YAML file (required if raw_config not provided)
        overrides: Override values to merge into config
        raw_config: In-memory config dict (alternative to config_path)
        validation_modules: Modules to validate (defaults to cashflow, debt)
        return_full_result: If True, return full pipeline result; if False, return KPIs only

    Returns:
        - If return_full_result=False: Normalized KPI dict {metric_name: float}
        - If return_full_result=True: Full pipeline result with kpis, annual_rows, debt_result, etc.

    Raises:
        ValueError: If neither config_path nor raw_config provided
        FileNotFoundError: If config_path doesn't exist

    Example:
        >>> # Sensitivity analysis (KPIs only)
        >>> kpis = evaluate_with_overrides(
        ...     config_path="scenarios/base.yaml",
        ...     overrides={"finance.capex_usd": 1100}
        ... )
        >>> kpis["project_irr"]
        0.142
        >>>
        >>> # Optimization (full result)
        >>> result = evaluate_with_overrides(
        ...     raw_config=config_dict,
        ...     overrides={"finance.capex_usd": 1100},
        ...     return_full_result=True
        ... )
        >>> result["kpis"]["project_irr"]
        0.142
        >>> result["debt_result"]["min_dscr"]
        1.45
    """
    # Validate inputs
    if config_path is None and raw_config is None:
        raise ValueError(
            "Either config_path or raw_config must be provided to evaluate_with_overrides()"
        )

    # Load or use provided config
    if raw_config is not None:
        base_config = dict(raw_config)
    else:
        cfg_path = Path(config_path)  # type: ignore[arg-type]
        if not cfg_path.is_file():
            raise FileNotFoundError(f"Scenario config not found: {cfg_path}")
        base_config = load_scenario_config(cfg_path)

    # Merge overrides
    merged_config = _deep_merge_config(base_config, overrides or {})

    # Run pipeline
    full_result = _run_pipeline_with_config(
        merged_config,
        validation_modules=validation_modules,
    )

    # Return based on requested format
    if return_full_result:
        return full_result
    else:
        # Backward compatibility: return KPIs only
        raw_kpis = full_result.get("kpis")
        if not isinstance(raw_kpis, Mapping):
            raise TypeError(
                f"Expected 'kpis' to be a mapping, got {type(raw_kpis).__name__}"
            )
        return normalize_kpi_dict(raw_kpis)


def evaluate_with_casper_tail_risk(
    *,
    config_path: str,
    monte_carlo_config_path: str | None = None,
    sensitivity_suite: SensitivitySuite | None = None,
    metric: str = "project_irr",
    confidence: float = 0.9,
    validation_mode: str = "strict",
    validation_modules: Sequence[str] | None = None,
) -> CasperResult:
    """
    High-level CASPER orchestrator for v14 (GWTF-compliant).

    Integrates baseline scenario, Monte Carlo, and sensitivity analysis with tail risk.

    CRITICAL: This is the ONLY function that imports tail-risk modules.
    All imports are lazy to avoid circular dependencies.

    Args:
        config_path: Path to base scenario config
        monte_carlo_config_path: Optional path to MC config
        sensitivity_suite: Optional pre-computed sensitivity suite
        metric: Target metric for tail risk analysis
        confidence: Confidence level for VaR/CVaR (default 0.9 = 90%)
        validation_mode: Schema validation mode
        validation_modules: Modules to validate

    Returns:
        CasperResult with scenario, sensitivities, monte_carlo, and tail risk metadata

    Example:
        >>> result = evaluate_with_casper_tail_risk(
        ...     config_path="scenarios/base.yaml",
        ...     monte_carlo_config_path="scenarios/mc_config.yaml",
        ...     metric="project_irr",
        ...     confidence=0.9
        ... )
        >>> result.baseline_kpis["project_irr"]
        0.145
        >>> result.monte_carlo.project_irr_p10
        0.120
    """
    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    base_config = load_scenario_config(cfg_path)

    logger.info("Step 1/4: Running v14 pipeline...")
    pipeline_result: Mapping[str, Any] = run_v14_pipeline(
        config=base_config,
        validation_mode=validation_mode,
        validation_modules=(
            list(validation_modules) if validation_modules is not None else None
        ),
    )

    kpis_raw = pipeline_result.get("kpis", {})
    baseline_kpis = normalize_kpi_dict(kpis_raw)

    scenario_result_dict = pipeline_result.get("scenario_result")
    if not isinstance(scenario_result_dict, Mapping):
        raise ValueError(
            f"run_v14_pipeline did not return a 'scenario_result' mapping. "
            f"Got type={type(scenario_result_dict).__name__}."
        )

    sr_dict: Dict[str, Any] = dict(scenario_result_dict)
    scenario = ScenarioResultContract(**sr_dict)

    logger.info("Step 2/4: Running Monte Carlo analysis...")
    monte_carlo = None
    tail_risk_block = None
    tail_risk_snapshots: dict[str, Any] = {}
    raw_results: list[dict[str, Any]] = []

    if monte_carlo_config_path:
        from omegaconf import OmegaConf

        mc_config = OmegaConf.load(monte_carlo_config_path)
        scenario_name_for_mc = base_config.get("project", {}).get("name", cfg_path.stem)

        # HARDENING: MC config key standardization
        mc_iterations = 1000  # default
        try:
            if hasattr(mc_config, "monte_carlo"):
                if hasattr(mc_config.monte_carlo, "iterations"):
                    mc_iterations = int(mc_config.monte_carlo.iterations)
                    logger.info(
                        "MC iterations from config: %d (using 'iterations' key)",
                        mc_iterations,
                    )
                elif hasattr(mc_config.monte_carlo, "n_iterations"):
                    mc_iterations = int(mc_config.monte_carlo.n_iterations)
                    logger.info(
                        "MC iterations from config: %d (using 'n_iterations' key)",
                        mc_iterations,
                    )
                else:
                    logger.warning(
                        "No 'iterations' or 'n_iterations' in config; using default %d",
                        mc_iterations,
                    )
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(
                "Could not extract iterations from MC config (%s); using default %d",
                str(e),
                mc_iterations,
            )

        mc_result = run_monte_carlo_analysis(
            config=mc_config, n_iterations=mc_iterations
        )

        if not mc_result or not mc_result.get("success"):
            raise ValueError(
                f"run_monte_carlo_analysis failed for scenario '{scenario_name_for_mc}'. "
                f"Result: {mc_result}"
            )

        stats = mc_result.get("statistics", {})

        # HARDENING: MC raw_results null safety
        raw_results_candidate = mc_result.get("raw_results") or mc_result.get(
            "iterations", []
        )

        if not raw_results_candidate or len(raw_results_candidate) == 0:
            logger.error(
                "MC raw_results empty or missing; tail risk analysis will be skipped"
            )
            raw_results = []
        elif not isinstance(raw_results_candidate, list):
            logger.error(
                "MC raw_results not a list; got %s; tail risk analysis will be skipped",
                type(raw_results_candidate).__name__,
            )
            raw_results = []
        elif len(raw_results_candidate) > 0 and not isinstance(
            raw_results_candidate[0], dict
        ):
            logger.error(
                "MC raw_results entries not dicts; tail risk analysis will be skipped"
            )
            raw_results = []
        else:
            # Valid raw_results
            raw_results = list(raw_results_candidate)

        monte_carlo = MonteCarloResult(
            scenario_name=mc_result.get("scenario_name", scenario_name_for_mc),
            iterations=mc_result.get("n_iterations", 0),
            failed_iterations=mc_result.get("failed_iterations", 0),
            raw_results=raw_results if raw_results else None,
            project_irr_mean=stats.get("irr_mean_pct", 0.0) / 100.0,
            project_irr_std=stats.get("irr_std_pct", 0.0) / 100.0,
            project_irr_p10=stats.get("irr_p10_pct", 0.0) / 100.0,
            project_irr_p50=stats.get("irr_median_pct", 0.0) / 100.0,
            project_irr_p90=stats.get("irr_p90_pct", 0.0) / 100.0,
            project_npv_mean=stats.get("npv_mean_usd", 0.0),
            project_npv_p10=stats.get("npv_p10_usd", 0.0),
            project_npv_p50=stats.get("npv_median_usd", 0.0),
            project_npv_p90=stats.get("npv_p90_usd", 0.0),
            dscr_min_p10=stats.get("dscr_min_p10", 0.0),
            dscr_min_p50=stats.get("dscr_min_p50", 0.0),
        )

    logger.info("Step 3/4: Building tail-risk enrichments...")

    # LAZY IMPORT: Only import tail-risk functions when actually needed
    if (sensitivity_suite and monte_carlo and raw_results) or (
        monte_carlo and raw_results
    ):
        try:
            from analytics.sensitivity_tail_risk import (
                build_tail_risk_snapshots_for_metrics,
                enrich_tornado_with_tail_risk,
            )
        except ImportError as e:
            logger.warning(
                "Could not import tail-risk functions: %s; skipping enrichment", str(e)
            )
        else:
            # Enrich tornado if we have sensitivity suite
            if sensitivity_suite and monte_carlo and raw_results:
                try:
                    tail_df = enrich_tornado_with_tail_risk(
                        tornado_suite=sensitivity_suite,
                        mc_result=monte_carlo,
                        metric=metric,
                        confidence=confidence,
                    )
                    tail_risk_block = {
                        "metric": metric,
                        "confidence": confidence,
                        "rows": tail_df.to_dict(orient="records"),
                    }
                except (ValueError, KeyError) as e:
                    logger.warning(
                        "Could not enrich tornado with tail risk: %s; skipping", str(e)
                    )

            # Build tail risk snapshots
            if monte_carlo and raw_results:
                try:
                    tail_risk_snapshots = build_tail_risk_snapshots_for_metrics(
                        mc_result=monte_carlo,
                        metrics=("project_irr", "dscr_min"),
                        confidence=confidence,
                    )
                except (ValueError, KeyError) as e:
                    logger.warning(
                        "Could not build tail risk snapshots: %s; skipping", str(e)
                    )
                    tail_risk_snapshots = {}

    logger.info("Step 4/4: Assembling CASPER result...")
    metadata: Dict[str, Any] = {}
    if tail_risk_block:
        metadata["tail_risk"] = tail_risk_block
    if tail_risk_snapshots:
        metadata["tail_risk_summary"] = tail_risk_snapshots

    return CasperResult(
        scenario=scenario,
        baseline_kpis=baseline_kpis,
        sensitivities=sensitivity_suite,
        monte_carlo=monte_carlo,
        metadata=metadata,
    )


evaluate_scenario = evaluate_with_overrides

__all__ = [
    "evaluate_with_overrides",
    "evaluate_scenario",
    "evaluate_scenario_from_dict",
    "normalize_kpi_dict",
    "evaluate_with_casper_tail_risk",
]
