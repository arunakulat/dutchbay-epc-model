# -*- coding: utf-8 -*-
"""
analytics.evaluation_v14

Canonical evaluation gateway for the v14 finance stack.
CESSPIT v14 / CASPER-GWTF Compliant

This module provides a SINGLE, typed entry point for analytics layers
(sensitivity, Monte Carlo, optimization):
  - evaluate_with_overrides(config_path, overrides)

Responsibilities
----------------
- Load YAML scenario config from disk
- Deep-merge any in-memory overrides (nested dict)
- Run the v14 pipeline with proper validation
- Return a flat KPI dict with numeric values (floats)

Important
---------
Only THIS module is allowed to call:
  - analytics.scenario_loader.load_scenario_config
  - analytics.pipeline_v14.run_v14_pipeline

Analytics modules (sensitivity_v14, monte_carlo_v14, etc.) must
import and use evaluate_with_overrides() instead of touching the
pipeline directly.

Author: CESSPIT Integration Team
Date: 2025-12-11
Version: 14.2.1 (CCCDIR Scenario Name Fix)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

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
from analytics.pipeline_v14 import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity_tail_risk import (
    build_tail_risk_snapshots_for_metrics,
    enrich_tornado_with_tail_risk,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Configuration Deep-Merge (CESSPIT Standard)
# ══════════════════════════════════════════════════════════════════════════════


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

    Parameters
    ----------
    base : Mapping[str, Any]
        Base configuration dictionary (from YAML)
    overrides : Mapping[str, Any]
        Override values (from Monte Carlo samples, sensitivity analysis, etc.)

    Returns
    -------
    dict[str, Any]
        Deep-merged configuration dictionary

    Examples
    --------
    >>> base = {"project": {"capex_usd_per_kw": 1500}}
    >>> overrides = {"project": {"capex_usd_per_kw": 1600}}
    >>> merged = _deep_merge_config(base, overrides)
    >>> merged["project"]["capex_usd_per_kw"]
    1600
    """
    result: dict[str, Any] = dict(base)

    for key, override_value in overrides.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(override_value, Mapping)
        ):
            # Recursive merge for nested dictionaries
            result[key] = _deep_merge_config(
                result[key],
                override_value,
            )
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

    Parameters
    ----------
    raw_kpis : Mapping[str, Any]
        Raw KPI dictionary from pipeline output

    Returns
    -------
    dict[str, float]
        Normalized KPI dictionary with only numeric values

    Notes
    -----
    Non-numeric KPIs (like scenario_name, description) are silently skipped.
    This allows metadata to flow through the pipeline without breaking
    downstream analytics that expect numeric values.
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

    Parameters
    ----------
    config : Mapping[str, Any]
        Merged configuration dictionary (base + overrides)
    validation_modules : list[str] | None, optional
        List of modules to validate (e.g., ["cashflow", "debt"])
        If None, uses default validation modules

    Returns
    -------
    dict[str, float]
        Normalized KPI dictionary

    Raises
    ------
    KeyError
        If pipeline payload missing 'kpis' key
    TypeError
        If 'kpis' value is not a Mapping
    """
    # **CRITICAL FIX**: Always pass validation_modules to ensure proper
    # config validation and parameter application during Monte Carlo runs
    if validation_modules is None:
        validation_modules = ["cashflow", "debt"]

    payload = run_v14_pipeline(
        config=config,
        validation_mode="strict",
        validation_modules=validation_modules,
    )

    try:
        raw_kpis = payload["kpis"]
    except KeyError as exc:
        raise KeyError(
            "run_v14_pipeline payload does not contain 'kpis' key. "
            f"Available keys: {list(payload.keys())}"
        ) from exc

    if not isinstance(raw_kpis, Mapping):
        raise TypeError(
            f"Expected 'kpis' to be a mapping, got {type(raw_kpis).__name__}"
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

    Parameters
    ----------
    config : Mapping[str, Any]
        Base configuration dictionary (already loaded from YAML)
    overrides : Mapping[str, Any] | None, optional
        Optional nested dict of overrides to apply to `config`
        before running the pipeline

    Returns
    -------
    dict[str, float]
        Flat KPI dictionary with numeric values

    Examples
    --------
    >>> config = load_scenario_config("scenarios/base.yaml")
    >>> overrides = {"project": {"capex_usd_per_kw": 1600}}
    >>> kpis = evaluate_scenario_from_dict(config, overrides)
    """
    merged_config: Mapping[str, Any]
    if overrides:
        merged_config = _deep_merge_config(config, overrides)
    else:
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

    **CRITICAL**: This function now enforces validation_modules by default
    to ensure Monte Carlo parameter overrides are properly applied during
    config validation and pipeline execution.

    Parameters
    ----------
    config_path : str | Path
        Path to YAML scenario configuration file
    overrides : Mapping[str, Any] | None, optional
        Optional nested dict for in-memory parameter overrides
    validation_modules : list[str] | None, optional
        Optional list of modules to validate (e.g., ["cashflow", "debt"])
        If None, defaults to ["cashflow", "debt"] for proper validation

    Returns
    -------
    dict[str, float]
        Flat KPI dict with numeric values (floats)

    Raises
    ------
    FileNotFoundError
        If the given config_path does not exist
    KeyError
        If the pipeline payload does not contain a 'kpis' key
    TypeError
        If load_scenario_config returns non-Mapping or raw_kpis is non-Mapping

    Examples
    --------
    Monte Carlo parameter override:

    >>> overrides = {
    ...     "project": {"capex_usd_per_kw": 1600.0},
    ...     "generation": {"capacity_factor_pct": 36.5},
    ... }
    >>> kpis = evaluate_with_overrides(
    ...     "scenarios/dutchbay_lendercase_2025Q4.yaml",
    ...     overrides
    ... )
    >>> kpis["project_irr"]
    0.1823

    Notes
    -----
    Version 14.2 Fix:
      - Added default validation_modules=["cashflow", "debt"] to ensure
        Monte Carlo parameter overrides are properly applied
      - Without validation_modules, the pipeline may skip config merging
        and return identical results for all Monte Carlo iterations
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

    merged_config: Mapping[str, Any]
    if overrides:
        logger.debug(
            "evaluate_with_overrides: applying %d top-level overrides",
            len(overrides),
        )
        merged_config = _deep_merge_config(base_config, overrides)
    else:
        merged_config = base_config

    # **CRITICAL FIX**: Pass validation_modules with default to ensure
    # proper config validation during Monte Carlo runs
    if validation_modules is None:
        validation_modules = ["cashflow", "debt"]

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

    This function:
      1. Runs the v14 lender pipeline (cashflow + debt + metrics)
      2. Rehydrates the ScenarioResult contract from the pipeline output
      3. Runs Monte Carlo for the same config/scenario using explicit MC config
      4. Optionally enriches a SensitivitySuite with tail-risk metrics
         (VaR, CVaR, P10/P90, breach probabilities)
      5. Builds a TailRiskSnapshot summary for key metrics and stores it
         under CasperResult.metadata["tail_risk_summary"]

    Parameters
    ----------
    config_path : str
        Path to base scenario configuration YAML
    monte_carlo_config_path : str
        Path to Monte Carlo configuration YAML containing:
          - simulation settings (iterations, seed, workers, sampler)
          - standard_parameters (distributions for direct overrides)
          - derived_parameters (solver-based parameter derivations)
          - scenarios (scenario-specific parameter overrides)
    sensitivity_suite : SensitivitySuite | None, optional
        Pre-computed tornado sensitivity results to enrich with tail-risk
    metric : str, default="project_irr"
        Primary metric for tail-risk analysis
    confidence : float, default=0.9
        Confidence level for VaR/CVaR calculations (0.9 = 90%)
    validation_mode : str, default="strict"
        Validation mode for pipeline execution
    validation_modules : Sequence[str] | None, optional
        Modules to validate (e.g., ["cashflow", "debt"])

    Returns
    -------
    CasperResult
        Comprehensive result bundle with:
          - scenario: ScenarioResult contract
          - baseline_kpis: Deterministic KPI dict
          - monte_carlo: MonteCarloResult with P10/P50/P90
          - sensitivities: Optional tornado sensitivity suite
          - metadata: Tail-risk summaries and enrichments

    Raises
    ------
    FileNotFoundError
        If config_path or monte_carlo_config_path does not exist
    ValueError
        If Monte Carlo analysis fails or returns no results

    Notes
    -----
    **v14.2.1 Update (CCCDIR)**: This function now correctly resolves scenario
    names from the base config and uses that name to look up Monte Carlo results.
    The scenario name resolution follows this priority:
      1. scenario_result.scenario_name from base config
      2. scenario.scenario_name block from base config
      3. Filename stem as final fallback

    Examples
    --------
    >>> casper = evaluate_with_casper_tail_risk(
    ...     config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
    ...     monte_carlo_config_path="monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
    ... )
    >>> casper.monte_carlo.project_irr_p50
    0.1788
    """
    # ──────────────────────────────────────────────────────────────────────────
    # Validation: Check both config files exist
    # ──────────────────────────────────────────────────────────────────────────

    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    # Guard against None - use default MC config if not provided
    if monte_carlo_config_path is None:
        mc_cfg_path = Path("config/monte_carlo_defaults.yaml")
    else:
        mc_cfg_path = Path(monte_carlo_config_path)

    if not mc_cfg_path.is_file():
        raise FileNotFoundError(
            f"Monte Carlo config not found: {mc_cfg_path}\n"
            f"Expected path: {mc_cfg_path.resolve()}\n"
            f"Hint: Ensure the monte_carlo/ directory contains YAML files "
            f"matching your scenario naming convention."
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
    # Import this module to allow tests to monkeypatch run_v14_pipeline
    import analytics.evaluation_v14 as self_eval  # type: ignore[attr-defined]

    pipeline_result: Mapping[str, Any] = self_eval.run_v14_pipeline(
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

    scenario_result_dict = pipeline_result.get("scenario_result")
    if not isinstance(scenario_result_dict, Mapping):
        msg = (
            "run_v14_pipeline did not return a 'scenario_result' mapping. "
            f"Got type={type(scenario_result_dict)!r}."
        )
        raise ValueError(msg)

    # Rehydrate canonical contracts_v14 ScenarioResult
    # Convert nested dictionaries (debt_profile, debt_covenants, wacc) into
    # their respective dataclass instances before constructing the ScenarioResult.
    # Make a shallow copy so we don't mutate the original pipeline payload.
    sr_dict: Dict[str, Any] = dict(scenario_result_dict)

    dp_raw = sr_dict.get("debt_profile")
    if isinstance(dp_raw, Mapping):
        try:
            sr_dict["debt_profile"] = TrancheDebtProfile(**dp_raw)
        except Exception:
            # If the dataclass instantiation fails, leave the original mapping
            pass

    cov_raw = sr_dict.get("debt_covenants")
    if isinstance(cov_raw, Mapping):
        try:
            sr_dict["debt_covenants"] = DebtCovenantSnapshot(**cov_raw)
        except Exception:
            pass

    wacc_raw = sr_dict.get("wacc")
    if isinstance(wacc_raw, Mapping):
        base_raw = wacc_raw.get("base")
        base_obj = None
        if isinstance(base_raw, Mapping):
            try:
                base_obj = WaccComponents(**base_raw)
            except Exception:
                base_obj = base_raw
        else:
            base_obj = base_raw
        try:
            sr_dict["wacc"] = WaccResult(
                base=base_obj,
                prudential_rate=wacc_raw.get("prudential_rate"),
            )
        except Exception:
            pass

    scenario = ScenarioResultContract(**sr_dict)
    logger.info(
        "  ✓ Pipeline complete: scenario=%s, baseline_irr=%.2f%%",
        scenario.scenario_name,
        baseline_kpis.get("project_irr", 0) * 100,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Run Monte Carlo for the same config/scenario
    #         **CRITICAL CCCDIR FIX**: Correct scenario name resolution
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("Step 2/4: Running Monte Carlo analysis...")

    # Determine a stable scenario name for Monte Carlo
    # Priority:
    #   1. Explicit scenario_result.scenario_name from base config
    #   2. scenario.scenario_name block in base config
    #   3. Filename stem (e.g., "dutchbay_lendercase_2025Q4")
    scenario_name_for_mc = None

    # Check scenario_result block first
    scenario_result_block = base_config.get("scenario_result")
    if isinstance(scenario_result_block, Mapping):
        scenario_name_for_mc = scenario_result_block.get("scenario_name")

    # Fallback to scenario block
    if not scenario_name_for_mc:
        scenario_block = base_config.get("scenario")
        if isinstance(scenario_block, Mapping):
            scenario_name_for_mc = scenario_block.get("scenario_name")

    # Final fallback: ALWAYS use filename stem if nothing found or placeholder
    if not scenario_name_for_mc or scenario_name_for_mc == "<inline_config>":
        scenario_name_for_mc = cfg_path.stem

    logger.info(
        "  Resolved scenario name for MC: '%s' (will use for result lookup)",
        scenario_name_for_mc,
    )

    # Call MC via self_eval to allow tests to monkeypatch run_monte_carlo_analysis
    mc_kwargs: Dict[str, Any] = {
        "base_config_path": config_path,
        "scenario_name": scenario_name_for_mc,
    }

    # Pass Monte Carlo config path using correct parameter name
    if monte_carlo_config_path is not None:
        mc_kwargs["scenario_config_path"] = monte_carlo_config_path

    mc_results_by_name = self_eval.run_monte_carlo_analysis(**mc_kwargs)

    # **CRITICAL CCCDIR FIX**: Use scenario_name_for_mc instead of scenario.scenario_name
    monte_carlo = mc_results_by_name.get(scenario_name_for_mc)
    if monte_carlo is None:
        msg = (
            "run_monte_carlo_analysis did not produce a result for "
            f"scenario '{scenario_name_for_mc}'. "
            f"Available keys: {list(mc_results_by_name.keys())!r}\n"
            f"Hint: Check that the MC config at {monte_carlo_config_path} "
            f"contains a scenario named '{scenario_name_for_mc}' with enabled=true"
        )
        raise ValueError(msg)

    logger.info(
        "  ✓ Monte Carlo complete: P50_IRR=%.2f%%, P10=%.2f%%, P90=%.2f%%",
        monte_carlo.project_irr_p50 * 100,
        monte_carlo.project_irr_p10 * 100,
        monte_carlo.project_irr_p90 * 100,
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
    # These are the lender-facing, CASPER-stable summaries.
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
        # Full, row-wise table (tornado × MC) – useful for deep-dive UIs.
        metadata["tail_risk"] = tail_risk_block

    if tail_risk_snapshots:
        # Compact, lender-facing summary keyed by metric name.
        # Callers can pass this directly to build_casper_payload via:
        #   tail_risk_snapshots=casper.metadata["tail_risk_summary"]
        metadata["tail_risk_summary"] = tail_risk_snapshots

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

# Alias for backward compatibility (defined AFTER function)
evaluate_scenario = evaluate_with_overrides

__all__ = [
    "evaluate_with_overrides",
    "evaluate_scenario",  # Alias for backward compatibility
    "evaluate_scenario_from_dict",
    "normalize_kpi_dict",
    "evaluate_with_casper_tail_risk",
]

# EOF
