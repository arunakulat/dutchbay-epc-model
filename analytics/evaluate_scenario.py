from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from analytics.contracts_v14 import ScenarioResult
from analytics.evaluation_v14 import _expand_dotted_overrides
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

logger = logging.getLogger(__name__)

"""
analytics.evaluate_scenario

Coordinator-only entry point for evaluating a single v14 scenario.

Responsibilities
----------------
- Load a base v14 config (YAML/JSON) via analytics.scenario_loader.
- Apply nested overrides (used by Monte Carlo, sensitivity, what-if tools).
- Call analytics.pipeline_v14_enhanced.run_v14_pipeline(config=...) once per evaluation.
- Normalise engine outputs into a flat KPI dict for analytics layers.

Non-responsibilities
--------------------
- No direct cashflow/debt/WACC calculations.
- No CLI / Hydra concerns (those live in run_full_pipeline_v14.py).
- No file I/O beyond base config loading.

Public API
----------
evaluate_with_overrides(base_config_path, overrides=None, *, validation_mode="strict",
                        validation_modules=None) -> dict[str, Any]

_helper functions:
- _merge_engine_kpis(pipeline_result_or_scenario_result) -> dict[str, Any]
- _normalise_kpi_result(obj) -> dict[str, Any]
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def evaluate_with_overrides(
    base_config_path: str | Path,
    overrides: dict[str, Any] | None = None,
    *,
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Evaluate a single v14 scenario with optional nested overrides.

    Parameters
    ----------
    base_config_path :
        Path to the base v14 scenario file (YAML/JSON).
    overrides :
        Nested dict of overrides in the same shape as the v14 config, e.g.:

        {
            "project": {"capex_usd_per_kw": 900.0},
            "financial": {"tariff_lkr_per_kwh": 70.0},
        }

        Used by Monte Carlo, sensitivity tools, and parameter_solvers.
    validation_mode :
        Passed through to run_v14_pipeline (e.g. "strict" or "off").
    validation_modules :
        Optional list of modules to validate (["cashflow", "debt"], etc.).

    Returns
    -------
    dict[str, Any]
        Flat KPI dict suitable for analytics layers, containing at least:
        - scenario_name
        - project_irr
        - project_npv
        - min_dscr
        - dscr_min (alias for min_dscr)
        - max_debt_usd (if available)
        - discount_rate_used (if available)
        - wacc_label (if available)
        - wacc_is_real (if available)
    """
    base_path = Path(base_config_path)
    logger.info("Evaluating scenario via v14 pipeline: %s", base_path)

    # 1. Load base v14 config via the canonical loader.
    raw_cfg = load_scenario_config(base_path)

    # 2. Apply overrides (if any). Expand flat *dotted* keys
    #    ("capex.usd_total": 5e8) into nested dicts FIRST, using the SAME expander as
    #    evaluation_v14.evaluate_with_overrides, so both gateways share one override
    #    contract. Without this, _deep_merge_dicts treated a dotted key as a literal
    #    top-level key and silently dropped it — the phantom-solver footgun where a
    #    solver sweeping "capex.usd_total" through this gateway no-ops while the
    #    optimizer's gateway honours it. Nested-dict overrides pass through unchanged.
    merged_cfg = (
        _deep_merge_dicts(raw_cfg, _expand_dotted_overrides(overrides))
        if overrides
        else raw_cfg
    )

    # 3. Call the canonical v14 pipeline.
    pipeline_result = run_v14_pipeline(
        config=merged_cfg,
        validation_mode=validation_mode,
        validation_modules=validation_modules or ["cashflow", "debt"],
    )

    # 4. Flatten / normalise KPIs for analytics consumers.
    kpi_dict = _merge_engine_kpis(pipeline_result)

    # 5. Logging: lender-friendly one-liner.
    scenario_name = kpi_dict.get("scenario_name", base_path.stem)
    logger.info(
        "Scenario evaluated: %s | IRR=%s | NPV=%s | DSCR_min=%s",
        scenario_name,
        kpi_dict.get("project_irr"),
        kpi_dict.get("project_npv"),
        kpi_dict.get("dscr_min"),
    )

    return kpi_dict


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _deep_merge_dicts(
    base: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Deep-merge two nested mappings, returning a new dict.

    - Values from `overrides` win over `base`.
    - Dicts are merged recursively.
    - Non-dict leaves are replaced outright.

    This is used to apply MC / sensitivity overrides on top of a loaded
    v14 config before feeding it into run_v14_pipeline.
    """
    result: dict[str, Any] = dict(base)
    for key, override_value in overrides.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(override_value, Mapping)
        ):
            result[key] = _deep_merge_dicts(result[key], override_value)
        else:
            result[key] = override_value
    return result


# ---------------------------------------------------------------------------
# KPI normalisation
# ---------------------------------------------------------------------------


def _merge_engine_kpis(obj: Mapping[str, Any] | ScenarioResult) -> dict[str, Any]:
    """
    Merge v14 engine outputs into a lender-friendly KPI dict.

    Accepts either:
    - The full pipeline result dict returned by run_v14_pipeline, or
    - A ScenarioResult dataclass instance.

    Behaviour:
    - Start from engine 'kpis' block if present.
    - Overlay scenario_name and core metrics from scenario-level fields:
      project_irr, project_npv, min_dscr, max_debt_usd.
    - Expose metadata (discount_rate_used, wacc_label, wacc_is_real) if set.
    - Provide a dscr_min alias for min_dscr to stabilise analytics callers.
    """
    # If we get a dataclass, convert to a mapping first.
    if isinstance(obj, ScenarioResult):
        struct = asdict(obj)
        pipeline_like: dict[str, Any] = {
            "kpis": struct.get("kpis") or {},
            "scenario_result": struct,
        }
    else:
        pipeline_like = dict(obj)

    kpis: dict[str, Any] = dict(pipeline_like.get("kpis") or {})

    # Scenario-level metadata
    scenario_meta = pipeline_like.get("scenario_result") or pipeline_like

    scenario_name = scenario_meta.get("scenario_name")
    if scenario_name is not None:
        kpis.setdefault("scenario_name", scenario_name)

    # Core metrics: fill from scenario_result if missing in kpis.
    for field in ("project_irr", "project_npv", "min_dscr", "max_debt_usd"):
        if field not in kpis and field in scenario_meta:
            kpis[field] = scenario_meta[field]

    # Metadata: discount rate / WACC flavour.
    if (
        "discount_rate_used" in scenario_meta
        and scenario_meta["discount_rate_used"] is not None
    ):
        kpis.setdefault("discount_rate_used", scenario_meta["discount_rate_used"])

    if "wacc_label" in scenario_meta and scenario_meta["wacc_label"] is not None:
        kpis.setdefault("wacc_label", scenario_meta["wacc_label"])

    if "wacc_is_real" in scenario_meta and scenario_meta["wacc_is_real"] is not None:
        kpis.setdefault("wacc_is_real", scenario_meta["wacc_is_real"])

    # Alias: dscr_min for min_dscr (many analytics bits expect dscr_min).
    if "dscr_min" not in kpis and "min_dscr" in kpis:
        kpis["dscr_min"] = kpis["min_dscr"]

    return kpis


def _normalise_kpi_result(obj: Any) -> dict[str, Any]:
    """
    Normalise different KPI container types into a flat dict.

    Accepted inputs:
    - ScenarioResult dataclass → flattened via _merge_engine_kpis(...)
    - Mapping (e.g. already-merged KPIs) → shallow-copied dict

    Anything else raises TypeError to keep failures loud and early.
    """
    if isinstance(obj, ScenarioResult):
        return _merge_engine_kpis(obj)

    if isinstance(obj, Mapping):
        return dict(obj)

    raise TypeError(
        f"Unsupported KPI result type for _normalise_kpi_result: {type(obj)!r}"
    )


__all__ = ["evaluate_with_overrides", "_merge_engine_kpis", "_normalise_kpi_result"]
# EOF
