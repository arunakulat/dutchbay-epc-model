from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from analytics.contracts_v14 import (
    CasperResult,
)
from analytics.contracts_v14 import ScenarioResult as ScenarioResultContract
from analytics.contracts_v14 import (
    SensitivitySuite,
)
from analytics.monte_carlo_v14 import run_monte_carlo_analysis
from analytics.pipeline_v14 import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity_tail_risk import (
    build_tail_risk_snapshots_for_metrics,
    enrich_tornado_with_tail_risk,
)

"""
analytics.evaluation_v14

Canonical evaluation gateway for the v14 finance stack.

This module provides a SINGLE, typed entry point for analytics layers
(sensitivity, Monte Carlo, optimization):

- evaluate_with_overrides(config_path, overrides)

Responsibilities
----------------
- Load YAML scenario config from disk
- Deep-merge any in-memory overrides (nested dict)
- Run the v14 pipeline
- Return a flat KPI dict with numeric values (floats)

Important
---------
Only THIS module is allowed to call:
- analytics.scenario_loader.load_scenario_config
- analytics.pipeline_v14.run_v14_pipeline

Analytics modules (sensitivity_v14, monte_carlo_v14, etc.) must
import and use evaluate_with_overrides() instead of touching the
pipeline directly.
"""


def _deep_merge_config(
    base: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Recursively deep-merge two configuration dictionaries.

    Values from `overrides` replace or extend values in `base`.
    Nested dicts are merged; other types are overwritten.
    """
    result: dict[str, Any] = dict(base)

    for key, override_value in overrides.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(override_value, Mapping)
        ):
            result[key] = _deep_merge_config(
                result[key],
                override_value,
            )
        else:
            result[key] = override_value

    return result


def normalize_kpi_dict(raw_kpis: Mapping[str, Any]) -> dict[str, float]:
    """
    Normalize KPI dict to {str -> float}.

    All values that can be converted to float are kept; non-numeric
    values are skipped to allow label/metadata fields (e.g. scenario_name).
    """
    kpis: dict[str, float] = {}
    logger = logging.getLogger(__name__)

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


def _run_pipeline_with_config(
    config: Mapping[str, Any],
    validation_modules: list[str] | None = None,
) -> dict[str, float]:
    """
    Internal helper: run v14 pipeline and extract normalized KPI dict.

    Assumes run_v14_pipeline returns a payload containing a 'kpis' key
    holding a mapping of KPI name -> numeric value.
    """
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


def evaluate_scenario_from_dict(
    config: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """
    Evaluate a scenario given an in-memory configuration dict.

    Parameters
    ----------
    config:
        Base configuration dictionary (already loaded from YAML).
    overrides:
        Optional nested dict of overrides to apply to `config`
        before running the pipeline.

    Returns
    -------
    dict[str, float]
        Flat KPI dictionary with numeric values.
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
    - monte_carlo_bridge_v14
    - any future evaluation-based tools

    Parameters
    ----------
    config_path:
        Path to YAML scenario configuration file.

    overrides:
        Optional nested dict for in-memory parameter overrides.

        Example
        -------
        overrides = {
            "project": {
                "capex_usd_per_kw": 1600.0,
            },
            "generation": {
                "capacity_factor_pct": 36.5,
            },
        }

    validation_modules:
        Optional list of modules to validate (e.g., ["cashflow", "debt"]).

    Returns
    -------
    dict[str, float]
        Flat KPI dict with numeric values (floats).

    Raises
    ------
    FileNotFoundError
        If the given config_path does not exist.

    KeyError
        If the pipeline payload does not contain a 'kpis' key.

    TypeError
        If load_scenario_config returns non-Mapping or raw_kpis is non-Mapping.
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
        merged_config = _deep_merge_config(base_config, overrides)
    else:
        merged_config = base_config

    return _run_pipeline_with_config(
        merged_config,
        validation_modules=validation_modules,
    )


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
      1. Runs the v14 lender pipeline (cashflow + debt + metrics).
      2. Rehydrates the ScenarioResult contract from the pipeline output.
      3. Runs Monte Carlo for the same config/scenario.
      4. Optionally enriches a SensitivitySuite with tail-risk metrics
         (VaR, CVaR, P10/P90, breach probabilities).
      5. Builds a TailRiskSnapshot summary for key metrics and stores it
         under CasperResult.metadata["tail_risk_summary"].

    Notes
    -----
    - `monte_carlo_config_path` is intentionally accepted and reserved in the
      contract, but the current engine wiring uses only `base_config_path`
      + `scenario_name`. This keeps the public API future-proof without
      lying to lenders/DFIs about what is actually used today.
    """
    # Keep parameter visible in the contract, but unused for now so we can
    # wire a dedicated MC config later without breaking callers.
    _ = monte_carlo_config_path

    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    base_config = load_scenario_config(cfg_path)
    if not isinstance(base_config, Mapping):
        raise TypeError(
            "Expected load_scenario_config to return Mapping, "
            f"got {type(base_config).__name__}"
        )

    # 1. Run v14 lender pipeline on the loaded config (single source of truth)
    pipeline_result: Mapping[str, Any] = run_v14_pipeline(
        config=base_config,
        validation_mode=validation_mode,
        validation_modules=(
            list(validation_modules) if validation_modules is not None else None
        ),
    )

    scenario_result_dict = pipeline_result.get("scenario_result")
    if not isinstance(scenario_result_dict, Mapping):
        msg = (
            "run_v14_pipeline did not return a 'scenario_result' mapping. "
            f"Got type={type(scenario_result_dict)!r}."
        )
        raise ValueError(msg)

    # Rehydrate canonical contracts_v14 ScenarioResult
    scenario = ScenarioResultContract(**scenario_result_dict)

    kpis_raw = pipeline_result.get("kpis", {})
    if isinstance(kpis_raw, Mapping):
        baseline_kpis = normalize_kpi_dict(kpis_raw)
    else:
        baseline_kpis = {}

    # 2. Run Monte Carlo for the same config/scenario
    mc_results_by_name = run_monte_carlo_analysis(
        base_config_path=config_path,
        scenario_name=scenario.scenario_name,
    )

    monte_carlo = mc_results_by_name.get(scenario.scenario_name)
    if monte_carlo is None:
        msg = (
            "run_monte_carlo_analysis did not produce a result for "
            f"scenario '{scenario.scenario_name}'. "
            f"Available keys: {list(mc_results_by_name.keys())!r}"
        )
        raise ValueError(msg)

    # 3. Optional tail-risk enrichment (SensitivitySuite + MC → full table)
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

    # 3b. Tail-risk summary snapshots for key metrics (MC → TailRiskSnapshot)
    # These are the lender-facing, CASPER-stable summaries.
    tail_risk_snapshots: Dict[str, Any] = build_tail_risk_snapshots_for_metrics(
        mc_result=monte_carlo,
        metrics=("project_irr", "dscr_min"),
        confidence=confidence,
    )

    # 4. Build CASPER result surface
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

    return casper_result


# Backward compatibility alias (defined AFTER function)
evaluate_scenario = evaluate_with_overrides

__all__ = [
    "evaluate_with_overrides",
    "evaluate_scenario",  # Alias for backward compatibility
    "evaluate_scenario_from_dict",
    "normalize_kpi_dict",
    "evaluate_with_casper_tail_risk",
]
