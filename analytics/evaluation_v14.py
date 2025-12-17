from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, cast

from analytics.contracts_v14 import (
    CasperResult,
    DebtCovenantSnapshot,
)
from analytics.contracts_v14 import ScenarioResult as ScenarioResultContract
from analytics.contracts_v14 import (
    SensitivitySuite,
    TrancheDebtProfile,
    WaccComponents,
    WaccResult,
)

# from analytics.monte_carlo_v14 import run_monte_carlo_analysis
from analytics.pipeline_v14 import run_v14_pipeline
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

Tagline:
    Single entry point. Contractually frozen. Tail-risk ready.

This module provides a SINGLE, typed entry point for analytics layers
(sensitivity, Monte Carlo, optimization):

    - evaluate_with_overrides(config_path, overrides)
    - evaluate_scenario_from_dict(config, overrides)
    - evaluate_with_casper_tail_risk(...)

Responsibilities
----------------
- Load YAML scenario config from disk
- Deep-merge any in-memory overrides (nested dict)
- Run the v14 pipeline with proper validation
- Return a flat KPI dict with numeric values (floats)
- Orchestrate CASPER runs (pipeline + Monte Carlo + tail-risk summaries)

Important
---------
Only THIS module is allowed to call:
  - analytics.scenario_loader.load_scenario_config
  - analytics.pipeline_v14.run_v14_pipeline

Analytics modules (sensitivity_v14, monte_carlo_v14, etc.) must
import and use evaluate_with_overrides() instead of touching the
pipeline directly.

Sprint 10 Notes
---------------
- v14.2.2 (Sprint 10 Monte Carlo Integration Fix):
  * Directly imports and uses run_monte_carlo_analysis from
    analytics.monte_carlo_v14 instead of any indirection.
  * Stabilizes scenario-name resolution for Monte Carlo:
      1) base_config["scenario_result"]["scenario_name"]
      2) base_config["scenario"]["scenario_name"]
      3) filename stem as final fallback
  * Produces CASPER-ready metadata["tail_risk"] and
    metadata["tail_risk_summary"] surfaces for lender-facing usage.

Author: CESSPIT Integration Team
Date: 2025-12-11
Version: 14.2.2 (Sprint 10 Monte Carlo Integration Fix)
"""

# ══════════════════════════════════════════════════════════════════════════════
# Configuration Deep-Merge (CESSPIT Standard)
# ══════════════════════════════════════════════════════════════════════════════


def run_monte_carlo_analysis(*args: Any, **kwargs: Any) -> Any:
    """
    Lazy proxy for the v14 Monte Carlo engine.

    - Real implementation lives in analytics.monte_carlo_v14.run_monte_carlo_analysis.
    - This wrapper exists so:
        * evaluation_v14 does not hard-import monte_carlo_v14 at module load time, and
        * tests can monkeypatch `evaluation_v14.run_monte_carlo_analysis`.
    """
    from analytics.monte_carlo_v14 import run_monte_carlo_analysis as _real_run_mc

    return _real_run_mc(*args, **kwargs)


def _deep_merge_config(
    base: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Recursively deep-merge two configuration dictionaries.

    Values from `overrides` replace or extend values in `base`.
    Nested dicts are merged; other types are overwritten.

    This is the CANONICAL config merge function used throughout the v14 stack
    to ensure Monte Carlo parameter overrides are properly applied.
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
            # Recursive merge for nested dictionaries
            result[key] = _deep_merge_config(base_mapping, override_mapping)
        else:
            # Direct replacement for scalars and lists
            result[key] = override_value

    return result


# ══════════════════════════════════════════════════════════════════════════════
# KPI Normalization
# ══════════════════════════════════════════════════════════════════════════════


def normalize_kpi_dict(raw_kpis: Mapping[str, Any]) -> dict[str, float]:
    """
    Normalize KPI dict to {str -> float}.

    All values that can be converted to float are kept; non-numeric
    values are skipped to allow label/metadata fields (e.g. scenario_name).
    """
    kpis: dict[str, float] = {}

    for key, value in raw_kpis.items():
        try:
            kpis[key] = float(value)
        except (TypeError, ValueError):
            # Allow non-numeric KPIs like scenario_name; skip them.
            logger.debug(
                "normalize_kpi_dict: skipping non-numeric KPI %r=%r (type=%s)",
                key,
                value,
                type(value).__name__,
            )
            continue

    return kpis


# ══════════════════════════════════════════════════════════════════════════════
# Pipeline Execution (Internal)
# ══════════════════════════════════════════════════════════════════════════════


def _run_pipeline_with_config(
    config: Mapping[str, Any],
    validation_modules: list[str] | None = None,
) -> dict[str, float]:
    """
    Internal helper: run v14 pipeline and extract normalized KPI dict.

    Assumes run_v14_pipeline returns a payload containing a 'kpis' key
    holding a mapping of KPI name -> numeric value.
    """
    if validation_modules is None:
        validation_modules = ["cashflow", "debt"]
        logger.debug(
            "_run_pipeline_with_config: using default validation_modules=%s",
            validation_modules,
        )
    else:
        logger.debug(
            "_run_pipeline_with_config: using explicit validation_modules=%s",
            validation_modules,
        )

    payload: Mapping[str, Any] = run_v14_pipeline(
        config=config,
        validation_mode="strict",
        validation_modules=validation_modules,
    )

    try:
        raw_kpis = payload["kpis"]
    except KeyError as exc:
        available_keys = list(payload.keys())
        raise KeyError(
            "run_v14_pipeline payload does not contain 'kpis' key. "
            f"Available keys: {available_keys}"
        ) from exc

    if not isinstance(raw_kpis, Mapping):
        raise TypeError(
            "Expected 'kpis' to be a mapping, " f"got {type(raw_kpis).__name__}"
        )

    return normalize_kpi_dict(raw_kpis)


# ══════════════════════════════════════════════════════════════════════════════
# Public Evaluation APIs
# ══════════════════════════════════════════════════════════════════════════════


def evaluate_scenario_from_dict(
    config: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """
    Evaluate a scenario given an in-memory configuration dict.
    """
    merged_config: Mapping[str, Any]
    if overrides:
        logger.debug(
            "evaluate_scenario_from_dict: applying %d top-level overrides",
            len(overrides),
        )
        merged_config = _deep_merge_config(config, overrides)
    else:
        logger.debug("evaluate_scenario_from_dict: no overrides provided")
        merged_config = config

    return _run_pipeline_with_config(merged_config)


def evaluate_with_overrides(
    config_path: str | Path,
    overrides: Mapping[str, Any] | None = None,
    *,
    validation_modules: list[str] | None = None,
) -> dict[str, float]:
    """
    Run a single scenario evaluation through the v14 pipeline.

    This is the CANONICAL entry point for analytics layers:
      - sensitivity_v14
      - monte_carlo_v14
      - any future evaluation-based tools
    """
    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    base_config = load_scenario_config(cfg_path)
    if not isinstance(base_config, Mapping):
        raise TypeError(
            "Expected load_scenario_config to return Mapping, "
            f"got {type(base_config).__name__}"
        )

    logger.info("evaluate_with_overrides: loaded config from %s", cfg_path)

    merged_config: Mapping[str, Any]
    if overrides:
        logger.debug(
            "evaluate_with_overrides: applying %d top-level overrides",
            len(overrides),
        )
        merged_config = _deep_merge_config(base_config, overrides)
    else:
        logger.debug("evaluate_with_overrides: no overrides provided")
        merged_config = base_config

    if validation_modules is None:
        validation_modules = ["cashflow", "debt"]
        logger.debug(
            "evaluate_with_overrides: using default validation_modules=%s",
            validation_modules,
        )
    else:
        logger.debug(
            "evaluate_with_overrides: using explicit validation_modules=%s",
            validation_modules,
        )

    return _run_pipeline_with_config(
        merged_config,
        validation_modules=validation_modules,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CASPER Orchestrator (Tail-Risk Integration)
# ══════════════════════════════════════════════════════════════════════════════


def evaluate_with_casper_tail_risk(
    *,
    config_path: str,
    monte_carlo_config_path: str,
    sensitivity_suite: SensitivitySuite | None = None,
    metric: str = "project_irr",
    confidence: float = 0.9,
    validation_mode: str = "strict",
    validation_modules: Sequence[str] | None = None,
) -> CasperResult:
    """
    High-level CASPER orchestrator for v14 (GWTF-compliant).
    """
    # ──────────────────────────────────────────────────────────────────────────
    # Validation: Check both config files exist
    # ──────────────────────────────────────────────────────────────────────────

    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    if monte_carlo_config_path is None:
        mc_cfg_path = Path("config/monte_carlo_defaults.yaml")
    else:
        mc_cfg_path = Path(monte_carlo_config_path)

    if not mc_cfg_path.is_file():
        raise FileNotFoundError(
            f"Monte Carlo config not found: {mc_cfg_path}\n"
            f"Resolved path: {mc_cfg_path.resolve()}\n"
            "Hint: Ensure the monte_carlo/ directory contains YAML files "
            "matching your scenario naming convention."
        )

    logger.info(
        "CASPER evaluation: config_path=%s, mc_config=%s",
        config_path,
        monte_carlo_config_path,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Run v14 lender pipeline on the loaded config (single source of truth)
    # ──────────────────────────────────────────────────────────────────────────

    base_config = load_scenario_config(cfg_path)
    if not isinstance(base_config, Mapping):
        raise TypeError(
            "Expected load_scenario_config to return Mapping, "
            f"got {type(base_config).__name__}"
        )

    logger.info("Step 1/4: Running v14 pipeline...")

    pipeline_result: Mapping[str, Any] = run_v14_pipeline(
        config=base_config,
        validation_mode=validation_mode,
        validation_modules=(
            list(validation_modules) if validation_modules is not None else None
        ),
    )

    # Extract KPIs before logging to ensure baseline_kpis is defined
    kpis_raw = pipeline_result.get("kpis", {})
    if isinstance(kpis_raw, Mapping):
        baseline_kpis = normalize_kpi_dict(kpis_raw)
    else:
        baseline_kpis = {}
        logger.warning(
            "CASPER: pipeline kpis block is not a Mapping (type=%s); "
            "baseline_kpis will be empty",
            type(kpis_raw).__name__,
        )

    scenario_result_dict = pipeline_result.get("scenario_result")
    if not isinstance(scenario_result_dict, Mapping):
        msg = (
            "run_v14_pipeline did not return a 'scenario_result' mapping. "
            f"Got type={type(scenario_result_dict)!r}."
        )
        raise ValueError(msg)

    # Rehydrate canonical contracts_v14 ScenarioResult
    sr_dict: Dict[str, Any] = dict(scenario_result_dict)

    dp_raw = sr_dict.get("debt_profile")
    if isinstance(dp_raw, Mapping):
        try:
            sr_dict["debt_profile"] = TrancheDebtProfile(**dp_raw)
        except Exception as exc:
            logger.debug(
                "CASPER: failed to rehydrate TrancheDebtProfile from %r (%s)",
                dp_raw,
                exc,
            )

    cov_raw = sr_dict.get("debt_covenants")
    if isinstance(cov_raw, Mapping):
        try:
            sr_dict["debt_covenants"] = DebtCovenantSnapshot(**cov_raw)
        except Exception as exc:
            logger.debug(
                "CASPER: failed to rehydrate DebtCovenantSnapshot from %r (%s)",
                cov_raw,
                exc,
            )

    wacc_raw = sr_dict.get("wacc")
    if isinstance(wacc_raw, Mapping):
        base_raw = wacc_raw.get("base")
        base_components: WaccComponents | None = None

        if isinstance(base_raw, Mapping):
            try:
                base_components = WaccComponents(**base_raw)
            except Exception as exc:
                logger.debug(
                    "CASPER: failed to rehydrate WaccComponents from %r (%s)",
                    base_raw,
                    exc,
                )
        elif isinstance(base_raw, WaccComponents):
            base_components = base_raw

        if base_components is not None:
            try:
                sr_dict["wacc"] = WaccResult(
                    base=base_components,
                    prudential_rate=wacc_raw.get("prudential_rate"),
                )
            except Exception as exc:
                logger.debug(
                    "CASPER: failed to rehydrate WaccResult from %r (%s)",
                    wacc_raw,
                    exc,
                )

    scenario = ScenarioResultContract(**sr_dict)
    logger.info(
        "  ✓ Pipeline complete: scenario=%s, baseline_irr=%.2f%%",
        scenario.scenario_name,
        baseline_kpis.get("project_irr", 0.0) * 100.0,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Run Monte Carlo for the same config/scenario
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("Step 2/4: Running Monte Carlo analysis...")

    scenario_name_for_mc: str | None = None

    scenario_result_block = base_config.get("scenario_result")
    if isinstance(scenario_result_block, Mapping):
        name = scenario_result_block.get("scenario_name")
        if isinstance(name, str):
            scenario_name_for_mc = name

    if not scenario_name_for_mc:
        scenario_block = base_config.get("scenario")
        if isinstance(scenario_block, Mapping):
            name = scenario_block.get("scenario_name")
            if isinstance(name, str):
                scenario_name_for_mc = name

    if not scenario_name_for_mc or scenario_name_for_mc == "<inline_config>":
        scenario_name_for_mc = cfg_path.stem
        logger.debug(
            "CASPER: falling back to filename stem for scenario_name_for_mc=%s",
            scenario_name_for_mc,
        )

    logger.info(
        "  Resolved scenario name for MC: '%s' (will use for result lookup)",
        scenario_name_for_mc,
    )

    # Load Monte Carlo config and run engine
    from omegaconf import OmegaConf
    mc_config = OmegaConf.load(monte_carlo_config_path)
    
    mc_kwargs: Dict[str, Any] = {
        "config": mc_config,
        "n_iterations": mc_config.monte_carlo.get("n_iterations", 1000),
    }

    # Call via the local proxy so tests can monkeypatch
    mc_result = run_monte_carlo_analysis(**mc_kwargs)

    if mc_result is None or not mc_result.get("success", False):
        msg = (
            f"run_monte_carlo_analysis failed for scenario '{scenario_name_for_mc}'. "
            f"Result: {mc_result}"
        )
        raise ValueError(msg)

    # Extract Monte Carlo result - handle both direct result and dict-by-scenario format
    monte_carlo = None
    if isinstance(mc_result, dict):
        # Check if it's a dict of scenarios or a single result
        if "statistics" in mc_result:
            # Direct result format
            from analytics.contracts_v14 import MonteCarloResult
            monte_carlo = MonteCarloResult(
                scenario_name=mc_result.get("scenario_name", scenario_name_for_mc),
                n_iterations=mc_result.get("n_iterations", 1000),
                project_irr_p10=mc_result["statistics"].get("irr_p10_pct", 0.0) / 100.0,
                project_irr_p50=mc_result["statistics"].get("irr_median_pct", 0.0) / 100.0,
                project_irr_p90=mc_result["statistics"].get("irr_p90_pct", 0.0) / 100.0,
                npv_p10=mc_result["statistics"].get("npv_p10_usd", 0.0),
                npv_p50=mc_result["statistics"].get("npv_median_usd", 0.0),
                npv_p90=mc_result["statistics"].get("npv_p90_usd", 0.0),
            )
        elif scenario_name_for_mc in mc_result:
            monte_carlo = mc_result[scenario_name_for_mc]

    if monte_carlo is None:
        msg = (
            "run_monte_carlo_analysis did not produce a usable result for "
            f"scenario '{scenario_name_for_mc}'. Got: {mc_result!r}"
        )
        raise ValueError(msg)

    logger.info(
        "  ✓ Monte Carlo complete: P50_IRR=%.2f%%, P10=%.2f%%, P90=%.2f%%",
        monte_carlo.project_irr_p50 * 100.0,
        monte_carlo.project_irr_p10 * 100.0,
        monte_carlo.project_irr_p90 * 100.0,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Optional tail-risk enrichment (SensitivitySuite + MC → full table)
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("Step 3/4: Building tail-risk enrichments...")
    tail_risk_block: Dict[str, Any] | None = None
    if sensitivity_suite is not None:
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
        logger.info("  ✓ Tornado enriched with %d tail-risk rows", len(tail_df))

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3b: Tail-risk summary snapshots for key metrics (MC → TailRiskSnapshot)
    # ──────────────────────────────────────────────────────────────────────────

    tail_risk_snapshots: Dict[str, Any] = build_tail_risk_snapshots_for_metrics(
        mc_result=monte_carlo,
        metrics=("project_irr", "dscr_min"),
        confidence=confidence,
    )
    logger.info(
        "  ✓ Built tail-risk snapshots for %d metrics", len(tail_risk_snapshots)
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Build CASPER result surface
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("Step 4/4: Assembling CASPER result...")
    metadata: Dict[str, Any] = {}
    if tail_risk_block is not None:
        metadata["tail_risk"] = tail_risk_block

    if tail_risk_snapshots:
        metadata["tail_risk_summary"] = tail_risk_snapshots
    if sensitivity_suite is not None:
        metadata["sensitivities"] = sensitivity_suite

    casper_result = CasperResult(
        scenario=scenario,
        baseline_kpis=baseline_kpis,
        sensitivities=sensitivity_suite,
        monte_carlo=monte_carlo,
        multi_tech_generation_breakdown=None,
        metadata=metadata,
    )

    logger.info("  ✓ CASPER result complete")
    return casper_result


# ══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility
# ══════════════════════════════════════════════════════════════════════════════

evaluate_scenario = evaluate_with_overrides

__all__ = [
    "evaluate_with_overrides",
    "evaluate_scenario",  # Alias for backward compatibility
    "evaluate_scenario_from_dict",
    "normalize_kpi_dict",
    "evaluate_with_casper_tail_risk",
]

# EOF
