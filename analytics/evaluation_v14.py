from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, cast

from analytics.contracts_v14 import CasperResult, MonteCarloResult
from analytics.contracts_v14 import ScenarioResult as ScenarioResultContract
from analytics.contracts_v14 import SensitivitySuite

# from analytics.monte_carlo_v14 import run_monte_carlo_analysis
# CRITICAL FIX: Import lender-grade pipeline (was: analytics.pipeline_v14)
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity_tail_risk import (
    build_tail_risk_snapshots_for_metrics,
    enrich_tornado_with_tail_risk,
)

logger = logging.getLogger(__name__)

# -*- coding: utf-8 -*-
"""
analytics.evaluation_v14

Canonical evaluation gateway for the v14 finance stack.
CESSPIT v14 / CASPER-GWTF Compliant

This module provides a SINGLE, typed entry point for analytics layers
(sensitivity, Monte Carlo, optimization):

    - evaluate_with_overrides(config_path, overrides)
    - evaluate_scenario_from_dict(config, overrides)
    - evaluate_with_casper_tail_risk(...)

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
) -> dict[str, float]:
    """
    Internal helper: run v14 pipeline and extract normalized KPI dict.
    """
    if validation_modules is None:
        validation_modules = ["cashflow", "debt"]

    payload: Mapping[str, Any] = run_v14_pipeline(
        config=config,
        validation_mode="strict",
        validation_modules=validation_modules,
    )

    raw_kpis = payload.get("kpis")
    if not isinstance(raw_kpis, Mapping):
        raise TypeError(
            f"Expected 'kpis' to be a mapping, got {type(raw_kpis).__name__}"
        )

    return normalize_kpi_dict(raw_kpis)


def evaluate_scenario_from_dict(
    config: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """
    Evaluate a scenario given an in-memory configuration dict.
    """
    merged_config = _deep_merge_config(config, overrides or {})
    return _run_pipeline_with_config(merged_config)


def evaluate_with_overrides(
    config_path: str | Path,
    overrides: Mapping[str, Any] | None = None,
    *,
    validation_modules: list[str] | None = None,
) -> dict[str, float]:
    """
    Run a single scenario evaluation through the v14 pipeline.
    """
    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    base_config = load_scenario_config(cfg_path)

    merged_config = _deep_merge_config(base_config, overrides or {})

    return _run_pipeline_with_config(
        merged_config,
        validation_modules=validation_modules,
    )


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
    # ... (rehydration logic) ...
    scenario = ScenarioResultContract(**sr_dict)

    logger.info("Step 2/4: Running Monte Carlo analysis...")
    monte_carlo = None
    if monte_carlo_config_path:
        from omegaconf import OmegaConf

        mc_config = OmegaConf.load(monte_carlo_config_path)
        scenario_name_for_mc = base_config.get("project", {}).get("name", cfg_path.stem)

        # FIX #1 (CRITICAL): MC config key standardization
        # STANDARDIZE: Always use "iterations" (not "n_iterations")
        mc_iterations = 1000  # default
        try:
            # Try monte_carlo.iterations first (standard pattern)
            if hasattr(mc_config, "monte_carlo"):
                if hasattr(mc_config.monte_carlo, "iterations"):
                    mc_iterations = int(mc_config.monte_carlo.iterations)
                    logger.info(
                        "MC iterations from config: %d (using 'iterations' key)",
                        mc_iterations,
                    )
                elif hasattr(mc_config.monte_carlo, "n_iterations"):
                    # Fallback for backward compat
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

        # FIX #2 (CRITICAL): MC raw_results None handling
        # Extract raw_results; should be list of dicts with metric keys
        raw_results = mc_result.get("raw_results") or mc_result.get("iterations", [])

        # Validate raw_results before using in tail risk analysis
        if not raw_results or len(raw_results) == 0:
            logger.error(
                "MC raw_results empty or missing; tail risk analysis will be skipped"
            )
            # Don't crash; set raw_results to empty list
            raw_results = []
            tail_risk_block = None
            tail_risk_snapshots = {}
        elif not isinstance(raw_results, list):
            logger.error(
                "MC raw_results not a list; got %s; tail risk analysis will be skipped",
                type(raw_results).__name__,
            )
            raw_results = []
            tail_risk_block = None
            tail_risk_snapshots = {}
        elif len(raw_results) > 0 and not isinstance(raw_results[0], dict):
            logger.error(
                "MC raw_results entries not dicts; tail risk analysis will be skipped"
            )
            raw_results = []
            tail_risk_block = None
            tail_risk_snapshots = {}
        else:
            # raw_results is valid; will be used in tail risk
            tail_risk_block = None
            tail_risk_snapshots = {}

        monte_carlo = MonteCarloResult(
            scenario_name=mc_result.get("scenario_name", scenario_name_for_mc),
            iterations=mc_result.get("n_iterations", 0),
            failed_iterations=mc_result.get("failed_iterations", 0),
            raw_results=raw_results if raw_results else None,  # None only if empty
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
    if tail_risk_block is None:  # Not set by MC handling above
        tail_risk_block = None

    if tail_risk_snapshots is None:  # Not set by MC handling above
        tail_risk_snapshots = {}

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

    if monte_carlo and raw_results:
        try:
            tail_risk_snapshots = build_tail_risk_snapshots_for_metrics(
                mc_result=monte_carlo,
                metrics=("project_irr", "dscr_min"),
                confidence=confidence,
            )
        except (ValueError, KeyError) as e:
            logger.warning("Could not build tail risk snapshots: %s; skipping", str(e))
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
