from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union, cast

from analytics.contracts_v14 import CasperResult
from analytics.contracts_v14 import ScenarioResult as ScenarioResultContract
from analytics.contracts_v14 import SensitivitySuite

# Canonical lender-grade pipeline (analytics.pipeline_v14_enhanced).
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
    from analytics.mc.engine import run_monte_carlo_analysis as _real_run_mc

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


def _expand_dotted_overrides(overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Expand flat *dotted* override keys into nested dicts before deep-merging.

    ``{"tax.corporate_tax_rate": 0.30}`` becomes
    ``{"tax": {"corporate_tax_rate": 0.30}}``. Plain keys pass through unchanged,
    and nested mappings are expanded recursively (so a dotted key nested under a
    plain parent is also handled).

    This makes the dotted override form documented on ``evaluate_with_overrides`` /
    ``evaluate_scenario_from_dict`` actually apply. Without it ``_deep_merge_config``
    treats ``"tax.corporate_tax_rate"`` as a *literal* top-level key and silently
    drops the override (it never reaches ``config["tax"]["corporate_tax_rate"]``) —
    which made every nested-parameter one-way sensitivity a silent no-op.
    """
    expanded: dict[str, Any] = {}
    for key, value in overrides.items():
        value = _expand_dotted_overrides(value) if isinstance(value, Mapping) else value
        if isinstance(key, str) and "." in key:
            parts = key.split(".")
            cursor = expanded
            for part in parts[:-1]:
                existing = cursor.get(part)
                if not isinstance(existing, dict):
                    existing = {}
                    cursor[part] = existing
                cursor = existing
            cursor[parts[-1]] = value
        else:
            existing = expanded.get(key)
            if isinstance(existing, dict) and isinstance(value, Mapping):
                expanded[key] = _deep_merge_config(existing, dict(value))
            else:
                expanded[key] = value
    return expanded


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
    merged_config = _deep_merge_config(config, _expand_dotted_overrides(overrides or {}))
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

    # Merge overrides (dotted keys like "tax.corporate_tax_rate" are expanded to
    # nested form first so they actually apply — see _expand_dotted_overrides).
    merged_config = _deep_merge_config(base_config, _expand_dotted_overrides(overrides or {}))

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
    tail_risk_block: list[dict[str, Any]] | None = None
    tail_risk_snapshots: dict[str, Any] = {}

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

        # Seed: prefer the MC config's value, else the scenario's monte_carlo block.
        mc_seed = 42
        try:
            mc_block = getattr(mc_config, "monte_carlo", None)
            if mc_block is not None and hasattr(mc_block, "seed"):
                mc_seed = int(mc_block.seed)
            elif (base_config.get("monte_carlo") or {}).get("seed") is not None:
                mc_seed = int(base_config["monte_carlo"]["seed"])
        except (AttributeError, TypeError, ValueError):
            pass

        # The canonical engine consumes the scenario's monte_carlo.parameters
        # block (base_config) and returns a contracts_v14.MonteCarloResult
        # directly — no dict munging, no rebuild. (Previously this called the
        # engine with non-existent kwargs config=/n_iterations= and then treated
        # the frozen dataclass result as a dict via .get(...), so the entire
        # CASPER tail-risk MC path was dead.)
        monte_carlo = run_monte_carlo_analysis(
            base_config=base_config,
            n_trials=mc_iterations,
            seed=mc_seed,
        )
        if monte_carlo is None or int(getattr(monte_carlo, "iterations", 0)) <= 0:
            raise ValueError(
                "Monte Carlo produced no iterations for scenario "
                f"'{scenario_name_for_mc}'."
            )

    # Tail-risk enrichment (#165 re-enable): enrich the attached sensitivity
    # suite via the live suite-centric API and surface the result on the
    # CasperResult metadata. enrich_suite_with_tail_risk is imported lazily to
    # preserve this module's import-safety invariant (no analytics.sensitivity
    # imports at module scope). The CVaR tail probability is derived from the
    # caller's `confidence` (alpha = 1 - confidence) rather than hardcoded
    # (ARCH-01 / config-first), which also makes the `confidence` argument live.
    if sensitivity_suite is not None:
        from analytics.sensitivity.tail_risk import (
            TailRiskConfig,
            enrich_suite_with_tail_risk,
        )

        enriched_suite = enrich_suite_with_tail_risk(
            suite=sensitivity_suite,
            base_config=base_config,
            run_cfg=TailRiskConfig(cvar_alpha=1.0 - confidence),
        )
        enriched_md = enriched_suite.metadata or {}
        tail_risk_block = enriched_md.get("tail_risk") or None
        tail_risk_snapshots = enriched_md.get("tail_risk_summary") or {}

    logger.info("Step 4/4: Assembling CASPER result...")
    metadata: Dict[str, Any] = {}
    if tail_risk_block:
        metadata["tail_risk"] = tail_risk_block
    if tail_risk_snapshots:
        metadata["tail_risk_summary"] = tail_risk_snapshots

    # Multi-tech generation view (de-orphans the never-fed generation contracts).
    # Built from the run's real AEP/CFADS — additive, no economics recomputation;
    # (None, None) when AEP is unresolvable. Lazy import preserves this module's
    # no-heavy-imports-at-module-scope invariant.
    from analytics.portfolio.generation_aggregator import build_multi_tech_from_run

    generation, generation_breakdown = build_multi_tech_from_run(
        baseline_kpis, base_config
    )

    return CasperResult(
        scenario=scenario,
        baseline_kpis=baseline_kpis,
        sensitivities=sensitivity_suite,
        monte_carlo=monte_carlo,
        generation=generation,
        multi_tech_generation_breakdown=generation_breakdown,
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
