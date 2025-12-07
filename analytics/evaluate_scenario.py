from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

from analytics.contracts_v14 import ScenarioResult
from run_full_pipeline_v14 import run_v14_pipeline

logger = logging.getLogger(__name__)

"""
analytics.evaluate_scenario

Central orchestrator for evaluating a full scenario (cashflow + debt + metrics)
*via* the v14 pipeline.

This module is the canonical entry point for:
- Monte Carlo (analytics.monte_carlo_v14)
- Sensitivity / tornado / Pareto (analytics.sensitivity_*)
- Parameter solvers (analytics.parameter_solvers)
- Any “single scenario + overrides” analytics.

It deliberately delegates the heavy lifting to `run_v14_pipeline` and then
normalises the KPI surface for downstream tools.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _merge_engine_kpis(pipeline_result: Mapping[str, Any]) -> dict[str, Any]:
    """
    Merge the pipeline's KPI view into a flat, analytics-friendly dict.

    Behaviour:
    - Start from the `kpis` block if present.
    - Prefer the *top-level* scenario_name when present.
    - For core metrics (IRR, NPV, DSCR, max_debt_usd), fall back to
      top-level values when the KPI block omits them.

    This function does NOT create alias fields like `dscr_min` – that is
    handled by `evaluate_with_overrides` so the tests can clearly separate
    concerns.
    """
    base: dict[str, Any] = {}

    # Start from KPI block, if provided.
    kpis = pipeline_result.get("kpis")
    if isinstance(kpis, Mapping):
        base.update(kpis)

    # Prefer the top-level scenario_name label when present.
    if "scenario_name" in pipeline_result:
        base["scenario_name"] = pipeline_result["scenario_name"]

    # Core numeric metrics we care about for most analytics flows.
    for key in ("project_irr", "project_npv", "min_dscr", "max_debt_usd"):
        if key not in base and key in pipeline_result:
            base[key] = pipeline_result[key]

    return base


def _normalise_kpi_result(obj: Any) -> dict[str, Any]:
    """
    Backwards-compatible normaliser in case callers ever pass a ScenarioResult
    (or similar) instead of a pipeline dict.

    In day-to-day v14 usage, we mostly feed `_merge_engine_kpis` with the
    raw dict returned by `run_v14_pipeline`, but keeping this helper around
    avoids surprises when refactoring.
    """
    if isinstance(obj, ScenarioResult):
        kpis: dict[str, Any] = {
            "scenario_name": obj.scenario_name,
            "project_npv": obj.project_npv,
            "project_irr": obj.project_irr,
            "min_dscr": obj.min_dscr,
            "max_debt_usd": obj.max_debt_usd,
        }
        if obj.discount_rate_used is not None:
            kpis["discount_rate_used"] = obj.discount_rate_used
        if obj.wacc_label is not None:
            kpis["wacc_label"] = obj.wacc_label
        if obj.wacc_is_real is not None:
            kpis["wacc_is_real"] = obj.wacc_is_real
        if obj.kpis:
            kpis.update(obj.kpis)
        return kpis

    if isinstance(obj, Mapping):
        return dict(obj)

    raise TypeError(
        f"Unsupported KPI result type for _normalise_kpi_result: {type(obj)!r}"
    )


# ---------------------------------------------------------------------------
# Public gateway
# ---------------------------------------------------------------------------


def evaluate_with_overrides(
    base_config_path: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Evaluate a single scenario via the v14 pipeline, with optional overrides.

    This is the canonical, engine-facing entry point for Monte Carlo,
    sensitivity, parameter solvers, and any “what-if” tooling.

    Parameters
    ----------
    base_config_path : str
        Path to the base scenario YAML.
    overrides : dict[str, Any] | None
        Nested dict of overrides applied on top of the loaded config.
        Callers are expected to have already expanded dotted paths into
        nested dicts where relevant.

    Returns
    -------
    dict[str, Any]
        Flat dict of KPI values (e.g. project_irr, project_npv, min_dscr,
        max_debt_usd, plus any extra KPIs), with a `dscr_min` alias added
        for DSCR-based workflows.

    Raises
    ------
    TypeError
        If the pipeline result is not a mapping.
    """
    config_path = Path(base_config_path)
    logger.info("Evaluating scenario via v14 pipeline: %s", config_path)

    # Delegate the heavy lifting to the canonical v14 pipeline.
    # The tests monkeypatch this symbol directly.
    pipeline_result = run_v14_pipeline(
        config=str(config_path),
        overrides=overrides or None,
    )

    if not isinstance(pipeline_result, Mapping):
        raise TypeError(
            "run_v14_pipeline must return a mapping-like result; "
            f"got {type(pipeline_result)!r}"
        )

    # Merge top-level and KPI block into a single view.
    kpi_dict = _merge_engine_kpis(pipeline_result)

    # Add a stable alias for DSCR so downstream code can rely on either name.
    if "min_dscr" in kpi_dict and "dscr_min" not in kpi_dict:
        kpi_dict["dscr_min"] = kpi_dict["min_dscr"]

    logger.info(
        "Scenario evaluated: %s | IRR=%s | NPV=%s | DSCR_min=%s",
        kpi_dict.get("scenario_name", config_path.name),
        kpi_dict.get("project_irr"),
        kpi_dict.get("project_npv"),
        kpi_dict.get("dscr_min"),
    )

    return kpi_dict


__all__ = ["evaluate_with_overrides", "_merge_engine_kpis"]
# EOF
