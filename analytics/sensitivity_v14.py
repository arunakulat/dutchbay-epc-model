from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.contracts_v14 import (
    BreakevenResult,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
    ParameterRangeConfig,
    SensitivitySuite,
    TornadoResult,
)
from analytics.pipeline_v14 import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

logger = logging.getLogger(__name__)
"""
analytics.sensitivity_v14

Deterministic tornado and breakeven analysis hub for the v14 analytics layer.

This module sits on top of the canonical v14 pipeline and exposes a clean,
engine-agnostic API for sensitivity work. It never reaches into lower-level
cashflow or debt internals; everything flows through:

    run_full_pipeline_v14.run_v14_pipeline

Key ideas
---------
* Single source of truth: the same v14 pipeline used by CI / lenders.
* Deterministic one-way sensitivities (no randomness here).
* Thin, well-typed contracts defined in analytics.contracts_v14.
* Backwards-compatible helpers kept for legacy tests.

Public surface
--------------
- SensitivityRequest
- run_tornado_sensitivity
- run_multi_metric_tornado
- run_breakeven_parameter
- tornado_suite_to_dataframe
- multi_metric_suite_to_dataframe
- plot_tornado_chart (stub)
- plot_spider_chart (stub)
- enrich_tornado_with_tail_risk (stub)
- optimize_from_sensitivity_insights (stub)
- run_two_way_sensitivity (stub)
- plot_two_way_heatmap (stub)
"""
# ═══════════════════════════════════════════════════════════════════════
# Core public request type
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SensitivityRequest:
    """Bundle of inputs needed to run a tornado sensitivity analysis.

    Parameters
    ----------
    base_config_path : str
        Path to the v14 scenario config (YAML or JSON) to stress-test.
    parameters : list[ParameterRangeConfig]
        Input parameters to vary (each with base value + shocks).
    override_labels : dict[str, str] or None, optional
        Mapping from ``variable_name`` to human-readable label for
        charts / tables (e.g. "Tariff (LKR/kWh)" instead of
        "finance.tariff").
    metric : str, default "project_irr"
        Name of the KPI field to use as tornado axis.
    """

    base_config_path: str
    parameters: list[ParameterRangeConfig]
    override_labels: dict[str, str] | None = None
    metric: str = "project_irr"


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════


def _deep_merge_config(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    """Deep-merge ``override`` into ``base``, preserving nested structure.

    This is needed because sensitivity analysis perturbs specific nested
    parameters (e.g. "finance.tariff") while keeping the rest of the
    config intact.
    """
    result = copy.deepcopy(base)

    def _merge(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if (
                isinstance(value, dict)
                and key in target
                and isinstance(target[key], dict)
            ):
                _merge(target[key], value)
            else:
                target[key] = value

    _merge(result, override)
    return result


def _build_nested_override(path: str | list[str], value: Any) -> dict[str, Any]:
    """Build nested override dict from dotted string or list of keys.

    Bridge between flat parameter names ("finance.tariff") and the nested
    dict structure expected by the v14 config.
    """
    if isinstance(path, str):
        parts: list[str] = [p for p in path.split(".") if p]
    else:
        parts = [str(p) for p in path]

    if not parts:
        return {}

    nested: dict[str, Any] = {parts[-1]: value}
    for key in reversed(parts[:-1]):
        nested = {key: nested}
    return nested


def _debug_log_parameters(
    *,
    where: str,
    base_config_path: str,
    metric_names: list[str],
    params: list[ParameterRangeConfig],
) -> None:
    """Centralized debug helper showing what the tornado engine will run."""
    names_str = ",".join(metric_names)
    logger.debug(
        "%s: base_config_path=%s metric(s)=%s n_params=%d",
        where,
        base_config_path,
        names_str,
        len(params),
    )

    if not params:
        logger.warning(
            "%s: no parameters provided – tornado will yield zero rows. "
            "Check SensitivityRequest.parameters or _load_parameters().",
            where,
        )
        return

    sample = list(params)[:10]
    for idx, p in enumerate(sample):
        logger.debug(
            "%s: param[%d] name=%s low_pct=%s high_pct=%s",
            where,
            idx,
            p.variable_name,
            p.low_pct,
            p.high_pct,
        )

    if len(params) > len(sample):
        logger.debug(
            "%s: ... %d additional parameter(s) not logged",
            where,
            len(params) - len(sample),
        )


def _analyze_single_parameter(
    base_config_path: str,
    base_metric_value: float,
    metric_name: str,
    param: ParameterRangeConfig,
    override_labels: dict[str, str] | None = None,
) -> TornadoResult:
    """
    Run low/high shocks for single parameter and return TornadoResult.

    Sprint 7 Phase 2B Fix:
    ----------------------
    Now correctly calculates ABSOLUTE perturbed values using param.base_value,
    not percentage multipliers that get misinterpreted by the config merger.

    Example:
        param.base_value = 10000000.0 (10M USD CAPEX)
        param.low_pct = -10.0 (means -10%, not -1000%)

        OLD (BROKEN): override = 1.0 + (-10.0) = -9.0  ❌
        NEW (CORRECT): low_value = 10M * (1 + (-0.10)) = 9M  ✅
    """
    variable_name = param.variable_name
    low_pct_decimal = (
        param.low_pct / 100.0 if abs(param.low_pct) > 1.0 else param.low_pct
    )
    high_pct_decimal = (
        param.high_pct / 100.0 if abs(param.high_pct) > 1.0 else param.high_pct
    )
    base_value = param.base_value

    # Calculate absolute perturbed values (FIX: was using multipliers)
    low_value = base_value * (1.0 + low_pct_decimal)
    high_value = base_value * (1.0 + high_pct_decimal)

    overrides_low = _build_nested_override(variable_name, low_value)
    overrides_high = _build_nested_override(variable_name, high_value)

    logger.debug(
        "_analyze_single_parameter: variable=%s base=%s "
        "low_pct=%s%% high_pct=%s%% → low_value=%s high_value=%s",
        variable_name,
        base_value,
        param.low_pct,
        param.high_pct,
        low_value,
        high_value,
    )

    # Rest of function unchanged...
    base_config = load_scenario_config(base_config_path)
    low_config = _deep_merge_config(base_config, overrides_low)
    high_config = _deep_merge_config(base_config, overrides_high)

    low_pipeline_result = run_v14_pipeline(
        config=low_config,
        validation_mode="strict",
    )
    high_pipeline_result = run_v14_pipeline(
        config=high_config,
        validation_mode="strict",
    )

    low_kpis = low_pipeline_result["kpis"]
    high_kpis = high_pipeline_result["kpis"]

    try:
        low_metric = float(low_kpis[metric_name])
        high_metric = float(high_kpis[metric_name])
    except KeyError as exc:
        raise KeyError(
            f"Metric {metric_name!r} not found in KPI dict for variable "
            f"{variable_name!r}. Available keys: {list(low_kpis.keys())}"
        ) from exc

    impact_abs = max(
        abs(low_metric - base_metric_value),
        abs(high_metric - base_metric_value),
    )
    impact_dir = 1 if high_metric >= base_metric_value else -1

    label = (
        override_labels.get(variable_name, variable_name)
        if override_labels is not None
        else variable_name
    )

    logger.debug(
        "_analyze_single_parameter: variable=%s label=%s "
        "base=%s low=%s high=%s impact=%s dir=%s",
        variable_name,
        label,
        base_metric_value,
        low_metric,
        high_metric,
        impact_abs,
        impact_dir,
    )

    return TornadoResult(
        variable=label,
        base_irr=base_metric_value,
        low_irr=low_metric,
        high_irr=high_metric,
    )


# ═══════════════════════════════════════════════════════════════════════
# Public tornado runners
# ═══════════════════════════════════════════════════════════════════════


def run_tornado_sensitivity(
    request: SensitivityRequest | str,
    parameters: list[ParameterRangeConfig] | None = None,
    metric: str | None = None,
) -> SensitivitySuite:
    """Run deterministic one-way tornado on provided parameters.

    Two supported calling styles (for compatibility):

    1. Canonical API (preferred)::

        req = SensitivityRequest(
            base_config_path="scenarios/example_a.yaml",
            parameters=[...],
            metric="project_irr",
        )
        suite = run_tornado_sensitivity(req)

    2. Legacy style (kept for tests / old CI wiring)::

        suite = run_tornado_sensitivity(
            "scenarios/example_a.yaml",
            parameters=[...],
            metric="project_irr",
        )
    """
    if isinstance(request, SensitivityRequest):
        base_config_path = request.base_config_path
        params: list[ParameterRangeConfig] = list(request.parameters)
        override_labels = request.override_labels
        metric_name = request.metric
    else:
        base_config_path = str(request)
        override_labels = None
        metric_name = metric or "project_irr"
        if parameters is not None:
            params = list(parameters)
        else:
            params = list(_load_parameters())

    # Fallback if tests hand us an empty parameter list
    if not params:
        logger.warning(
            "run_tornado_sensitivity: resolved empty parameters for %s; "
            "falling back to _load_parameters() defaults.",
            base_config_path,
        )
        params = list(_load_parameters())

    logger.info(
        "Starting tornado sensitivity for %s on metric=%s",
        base_config_path,
        metric_name,
    )
    _debug_log_parameters(
        where="run_tornado_sensitivity",
        base_config_path=base_config_path,
        metric_names=[metric_name],
        params=params,
    )

    # Evaluate base scenario once using v14 pipeline.
    # IMPORTANT: we pass the CONFIG DICT into run_v14_pipeline so that
    # tests patching run_v14_pipeline(config=...) see a mutable dict,
    # not a bare path string.
    base_config = load_scenario_config(base_config_path)
    base_pipeline_result = run_v14_pipeline(
        config=base_config,
        validation_mode="strict",
    )

    base_kpis = base_pipeline_result["kpis"]
    if metric_name not in base_kpis:
        raise KeyError(
            f"Metric {metric_name!r} not found in base KPI dict. "
            f"Available keys: {list(base_kpis.keys())}"
        )

    base_metric_value = float(base_kpis[metric_name])

    results: list[TornadoResult] = []
    for param in params:
        result = _analyze_single_parameter(
            base_config_path=base_config_path,
            base_metric_value=base_metric_value,
            metric_name=metric_name,
            param=param,
            override_labels=override_labels,
        )
        results.append(result)

    # Sort by absolute impact descending
    results.sort(key=lambda r: r.impact_abs, reverse=True)

    top_impact = results[0].impact_abs if results else 0.0
    logger.debug(
        "run_tornado_sensitivity: completed with %d tornado rows; top_impact=%f",
        len(results),
        top_impact,
    )

    suite = SensitivitySuite(
        tornado_results=results,
        base_metric=base_metric_value,
        base_config_path=base_config_path,
        metric=metric_name,
    )

    if results:
        logger.info(
            "Tornado complete: %d parameters, top driver impact=%.4f",
            len(results),
            top_impact,
        )
    else:
        logger.info("Tornado complete: no parameters, zero rows produced")

    return suite


def run_multi_metric_tornado(
    request: SensitivityRequest | str,
    metrics: list[str],
    parameters: list[ParameterRangeConfig] | None = None,
) -> MultiMetricSensitivitySuite:
    """
    Run tornado over multiple KPI metrics at once.

    New, preferred style::

        req = SensitivityRequest(
            base_config_path="scenarios/example_a.yaml",
            parameters=[...],
        )
        suite = run_multi_metric_tornado(req, metrics=["project_irr", "equity_irr"])

    Legacy style (for tests/old CI)::

        suite = run_multi_metric_tornado(
            "scenarios/example_a.yaml",
            metrics=["project_irr", "equity_irr"],
            parameters=[...],
        )

    Parameters
    ----------
    request : SensitivityRequest or str
        Either a SensitivityRequest instance or base config path string.
    metrics : list[str]
        KPI metric names to evaluate (e.g. ["project_irr", "equity_irr"]).
    parameters : list[ParameterRangeConfig] or None, optional
        Optional explicit ParameterRangeConfig sequence, used only in
        legacy mode (when ``request`` is a string). If omitted, defaults
        to ``_load_parameters()``.

    Returns
    -------
    MultiMetricSensitivitySuite
        Bundle including per-metric tornado data.

    Raises
    ------
    ValueError
        If metrics list is empty.
    KeyError
        If requested metrics not found in KPI dict.
    """
    if not metrics:
        raise ValueError("run_multi_metric_tornado: metrics must be non-empty")

    if isinstance(request, SensitivityRequest):
        base_config_path = request.base_config_path
        params: list[ParameterRangeConfig] = list(request.parameters)
        override_labels = request.override_labels
    else:
        base_config_path = str(request)
        override_labels = None
        if parameters is not None:
            params = list(parameters)
        else:
            params = list(_load_parameters())

    if not params:
        logger.warning(
            "run_multi_metric_tornado: resolved empty parameters for %s; "
            "falling back to _load_parameters() defaults.",
            base_config_path,
        )
        params = list(_load_parameters())

    logger.info(
        "Starting multi-metric tornado for %s on metrics=%s",
        base_config_path,
        list(metrics),
    )
    _debug_log_parameters(
        where="run_multi_metric_tornado",
        base_config_path=base_config_path,
        metric_names=list(metrics),
        params=params,
    )

    # Evaluate base case once for all metrics using v14 pipeline
    base_config = load_scenario_config(base_config_path)
    base_pipeline_result = run_v14_pipeline(
        config=base_config,
        validation_mode="strict",
    )

    # Extract KPIs from pipeline result
    base_kpis = base_pipeline_result["kpis"]

    missing_metrics = [m for m in metrics if m not in base_kpis]
    if missing_metrics:
        raise KeyError(
            f"Base KPI dict missing metrics {missing_metrics!r}. "
            f"Available keys: {list(base_kpis.keys())}"
        )

    base_metric_vals = {m: float(base_kpis[m]) for m in metrics}

    results: list[MultiMetricTornadoResult] = []

    for param in params:
        variable_name = param.variable_name

        # ═══════════════════════════════════════════════════════════════
        # Sprint 7 Phase 2B Fix: Convert percentages to decimals properly
        # ═══════════════════════════════════════════════════════════════
        # Handle both formats:
        #   - Test format: low_pct = -10.0 (means -10%, convert to -0.10)
        #   - Direct format: low_pct = -0.10 (already decimal, keep as is)
        # ═══════════════════════════════════════════════════════════════
        low_pct_decimal = (
            param.low_pct / 100.0 if abs(param.low_pct) > 1.0 else param.low_pct
        )
        high_pct_decimal = (
            param.high_pct / 100.0 if abs(param.high_pct) > 1.0 else param.high_pct
        )
        base_value = param.base_value

        # Calculate absolute perturbed values (NOT multipliers!)
        # Example: base_value=10M, low_pct=-10.0 → low_value=9M
        low_value = base_value * (1.0 + low_pct_decimal)
        high_value = base_value * (1.0 + high_pct_decimal)

        overrides_low = _build_nested_override(variable_name, low_value)
        overrides_high = _build_nested_override(variable_name, high_value)

        logger.debug(
            "run_multi_metric_tornado: variable=%s base=%s "
            "low_pct=%s%% high_pct=%s%% → low_value=%s high_value=%s",
            variable_name,
            base_value,
            param.low_pct,
            param.high_pct,
            low_value,
            high_value,
        )

        # Apply overrides to base config
        low_config = _deep_merge_config(base_config, overrides_low)
        high_config = _deep_merge_config(base_config, overrides_high)

        # Run v14 pipeline for low and high cases
        low_pipeline_result = run_v14_pipeline(
            config=low_config,
            validation_mode="strict",
        )
        high_pipeline_result = run_v14_pipeline(
            config=high_config,
            validation_mode="strict",
        )

        # Extract KPIs
        low_kpis = low_pipeline_result["kpis"]
        high_kpis = high_pipeline_result["kpis"]

        # Ensure all metrics exist in both low/high cases
        for m in metrics:
            if m not in low_kpis or m not in high_kpis:
                raise KeyError(
                    f"Metric {m!r} missing for variable {variable_name!r}. "
                    f"Low keys: {list(low_kpis.keys())}, "
                    f"High keys: {list(high_kpis.keys())}"
                )

        low_metrics = {m: float(low_kpis[m]) for m in metrics}
        high_metrics = {m: float(high_kpis[m]) for m in metrics}
        impacts = {m: abs(high_metrics[m] - low_metrics[m]) for m in metrics}
        impact_dirs = {
            m: 1 if high_metrics[m] >= low_metrics[m] else -1 for m in metrics
        }

        label = (
            override_labels.get(variable_name, variable_name)
            if override_labels is not None
            else variable_name
        )

        logger.debug(
            "run_multi_metric_tornado: label=%s low=%s high=%s impacts=%s",
            label,
            low_metrics,
            high_metrics,
            impacts,
        )

        # Use keyword args to match MultiMetricTornadoResult signature
        results.append(
            MultiMetricTornadoResult(
                variable=label,
                label=label,
                base_values=base_metric_vals.copy(),
                low_values=low_metrics,
                high_values=high_metrics,
                impacts=impacts,
                impact_dirs=impact_dirs,
            )
        )

    suite = MultiMetricSensitivitySuite(
        tornado_results=results,
        base_metrics=base_metric_vals,
        base_config_path=base_config_path,
        metrics=list(metrics),
    )

    logger.debug(
        "run_multi_metric_tornado: completed with %d tornado rows; metrics=%s",
        len(results),
        list(metrics),
    )
    logger.info(
        "Multi-metric tornado complete: %d parameters, %d metrics",
        len(results),
        len(metrics),
    )

    return suite


# ═══════════════════════════════════════════════════════════════════════
# Breakeven search
# ═══════════════════════════════════════════════════════════════════════


def run_breakeven_parameter(
    base_config_path: str,
    variable_name: str,
    target_metric: str = "project_irr",
    target_value: float = 0.0,
    *,
    low_pct: float = -0.5,
    high_pct: float = 0.5,
    tol: float = 1e-4,
    max_iter: int = 50,
) -> BreakevenResult:
    """
    Solve for the parameter value that yields a target metric (e.g. IRR).

    Uses simple bisection method on +/- percentage range of base
    parameter value.

    Sprint 7 Phase 2B Fix:
    ----------------------
    Now correctly applies ABSOLUTE parameter values in the objective function,
    not fractional multipliers that break config validation.

    Parameters
    ----------
    base_config_path : str
        Path to the base v14 scenario config.
    variable_name : str
        Name of the parameter to vary (e.g. "tariff.tariff_lkr_per_kwh").
    target_metric : str, default "project_irr"
        Name of the KPI metric to match (e.g. "project_irr").
    target_value : float, default 0.0
        Target value of the metric (e.g. 0.0 for breakeven IRR).
    low_pct : float, default -0.5
        Bracketing range lower bound (-50% of base).
    high_pct : float, default 0.5
        Bracketing range upper bound (+50% of base).
    tol : float, default 1e-4
        Absolute tolerance on the metric difference.
    max_iter : int, default 50
        Maximum number of bisection iterations.

    Returns
    -------
    BreakevenResult
        Dataclass with final solution and status.

    Raises
    ------
    KeyError
        If variable or metric not found in configuration.
    ValueError
        If root not bracketed in search range.
    TypeError
        If variable is not a numeric scalar.
    """
    # Get base parameter value first by evaluating base case using v14 pipeline
    base_config = load_scenario_config(base_config_path)
    base_pipeline_result = run_v14_pipeline(
        config=base_config,
        validation_mode="strict",
    )

    base_kpis = base_pipeline_result["kpis"]
    if target_metric not in base_kpis:
        raise KeyError(
            f"Target metric {target_metric!r} not found in base KPI dict. "
            f"Available keys: {list(base_kpis.keys())}"
        )

    # Fetch current parameter value from config by re-loading
    cfg = load_scenario_config(base_config_path)

    # Walk config to get base parameter value
    parts = [p for p in variable_name.split(".") if p]
    node: Any = cfg
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            raise KeyError(
                f"Variable {variable_name!r} not found in config at path {p!r}"
            )
        node = node[p]

    try:
        base_param_value = float(node)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Variable {variable_name!r} is not a numeric scalar: {node!r}"
        ) from exc

    # ═══════════════════════════════════════════════════════════════════════
    # Sprint 7 Phase 2B Fix: Convert percentages and calculate absolute bounds
    # ═══════════════════════════════════════════════════════════════════════
    # Handle both percentage formats:
    #   - low_pct = -50.0 (interpreted as -50%, convert to -0.50)
    #   - low_pct = -0.5 (already decimal, keep as is)
    # ═══════════════════════════════════════════════════════════════════════
    low_pct_decimal = low_pct / 100.0 if abs(low_pct) > 1.0 else low_pct
    high_pct_decimal = high_pct / 100.0 if abs(high_pct) > 1.0 else high_pct

    lower = base_param_value * (1.0 + low_pct_decimal)
    upper = base_param_value * (1.0 + high_pct_decimal)

    logger.info(
        "Breakeven search for %s on %s target=%s base_value=%s bracket=[%s, %s]",
        variable_name,
        target_metric,
        target_value,
        base_param_value,
        lower,
        upper,
    )

    def objective(x: float) -> float:
        """
        Objective function: returns (metric_value - target_value).

        Sprint 7 Phase 2B Fix:
        ----------------------
        Now passes ABSOLUTE parameter value x directly to override,
        not as a fraction of base_param_value.

        OLD (BROKEN): overrides = _build_nested_override(var, x / base_param_value)
        NEW (CORRECT): overrides = _build_nested_override(var, x)
        """
        # FIX: Pass absolute value x directly, not as multiplier
        overrides = _build_nested_override(variable_name, x)

        # Load base config and apply override
        base_config = load_scenario_config(base_config_path)
        override_config = _deep_merge_config(base_config, overrides)

        # Run v14 pipeline
        pipeline_result = run_v14_pipeline(
            config=override_config,
            validation_mode="strict",
        )

        # Extract KPI
        kpis = pipeline_result["kpis"]
        if target_metric not in kpis:
            raise KeyError(
                f"Target metric {target_metric!r} missing in KPI dict "
                f"during breakeven evaluation. Keys: {list(kpis.keys())}"
            )
        value = float(kpis[target_metric])
        logger.debug(
            "Breakeven objective for %s: param=%s metric=%s value=%s target=%s residual=%s",
            variable_name,
            x,
            target_metric,
            value,
            target_value,
            value - target_value,
        )
        return value - target_value

    a, b = lower, upper
    fa, fb = objective(a), objective(b)

    if fa * fb > 0:
        raise ValueError(
            f"Breakeven: root not bracketed for {variable_name!r} "
            f"over [{lower}, {upper}] – f(a)={fa:.4f}, f(b)={fb:.4f}"
        )

    mid = 0.5 * (a + b)
    for iteration in range(max_iter):
        mid = 0.5 * (a + b)
        fmid = objective(mid)

        if abs(fmid) < tol:
            logger.info(
                "Breakeven solved for %s: %.6f (residual %.3e in %d iterations)",
                variable_name,
                mid,
                fmid,
                iteration + 1,
            )
            return BreakevenResult(
                variable=variable_name,
                breakeven_value=mid,
                bracket=(a, b),
                status="success",
            )

        if fa * fmid < 0:
            b, fb = mid, fmid
        else:
            a, fa = mid, fmid

    logger.warning(
        "Breakeven did not converge for %s after %d iterations; last mid=%s",
        variable_name,
        max_iter,
        mid,
    )
    return BreakevenResult(
        variable=variable_name,
        breakeven_value=mid,
        bracket=(a, b),
        status="max_iter_exceeded",
    )


# ═══════════════════════════════════════════════════════════════════════
# Legacy / compatibility helpers
# ═══════════════════════════════════════════════════════════════════════


def _load_parameters() -> list[ParameterRangeConfig]:
    """Legacy compatibility: load default parameters from YAML.

    New code should construct ``ParameterRangeConfig`` lists explicitly.
    This helper remains for older tests and CI wiring.
    """
    default_yaml = Path("scenarios/sensitivity_parameters.yaml")
    if not default_yaml.exists():
        logger.warning(
            "_load_parameters: default YAML %s not found – returning empty list",
            default_yaml,
        )
        return []

    return list(_load_parameters_from_yaml(default_yaml))


def _load_parameters_from_yaml(path: Path) -> list[ParameterRangeConfig]:
    """
    Load ParameterRangeConfig entries from YAML.

    Parameters
    ----------
    path : Path
        Path to a YAML file containing a list of parameter configs.

    Returns
    -------
    list[ParameterRangeConfig]
        Parsed parameter configurations.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    ValueError
        If the YAML structure is not a list of dicts with the required keys.
    yaml.YAMLError
        If the YAML file is malformed.
    """
    import yaml

    logger.debug("_load_parameters_from_yaml: loading from %s", path)

    if not path.exists():
        raise FileNotFoundError(path)

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # ── Hard structural guards ──────────────────────────────────────────
    if data is None:
        raise ValueError(
            f"_load_parameters_from_yaml: YAML at {path} is empty or null; "
            "expected a non-empty list of parameter configs."
        )

    if not isinstance(data, list):
        # This is exactly your test_invalid_yaml_structure case:
        # syntactically valid YAML, but wrong top-level type.
        raise ValueError(
            f"_load_parameters_from_yaml: YAML at {path} must be a list of "
            f"parameter objects, got {type(data).__name__!r} instead."
        )

    params: list[ParameterRangeConfig] = []

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "_load_parameters_from_yaml[%d]: skipping non-dict item: %r",
                idx,
                item,
            )
            continue

        name = str(item.get("variable_name", "")).strip()
        if not name:
            logger.warning(
                "_load_parameters_from_yaml[%d]: missing variable_name, skipping",
                idx,
            )
            continue

        base_value = item.get("base_value")
        if base_value is None:
            logger.warning(
                "_load_parameters_from_yaml[%d]: missing base_value for %s, skipping",
                idx,
                name,
            )
            continue

        try:
            base_value_float = float(base_value)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "_load_parameters_from_yaml[%d]: base_value for %s not numeric (%r), skipping",
                idx,
                name,
                base_value,
                exc_info=exc,
            )
            continue

        try:
            low_pct = float(item.get("low_pct", -0.1))
            high_pct = float(item.get("high_pct", 0.1))
        except (TypeError, ValueError) as exc:
            logger.warning(
                "_load_parameters_from_yaml[%d]: invalid percentages for %s, skipping",
                idx,
                name,
                exc_info=exc,
            )
            continue

        logger.debug(
            "_load_parameters_from_yaml[%d]: loaded variable=%s base=%s "
            "low_pct=%s high_pct=%s",
            idx,
            name,
            base_value_float,
            low_pct,
            high_pct,
        )

        params.append(
            ParameterRangeConfig(
                variable_name=name,
                base_value=base_value_float,
                low_pct=low_pct,
                high_pct=high_pct,
            )
        )

    # If the YAML *looked* structurally OK (list of dicts) but produced
    # no usable parameters, treat this as structural failure as well.
    if not params:
        raise ValueError(
            f"_load_parameters_from_yaml: no valid parameters could be parsed "
            f"from {path}. Expected a list of objects with "
            "variable_name, base_value, low_pct, high_pct."
        )

    logger.debug(
        "_load_parameters_from_yaml: loaded %d parameter(s) from %s",
        len(params),
        path,
    )
    return params


# ═══════════════════════════════════════════════════════════════════════
# Public export helpers
# ═══════════════════════════════════════════════════════════════════════


def tornado_suite_to_dataframe(suite: SensitivitySuite) -> pd.DataFrame:
    """Convert a one-way tornado ``SensitivitySuite`` to a DataFrame."""
    rows: list[dict[str, Any]] = []

    for row in suite.tornado_results:
        rows.append(
            {
                "variable": row.variable,
                "base_irr": row.base_irr,
                "low_irr": row.low_irr,
                "high_irr": row.high_irr,
                "impact_abs": row.impact_abs,
            }
        )

    return pd.DataFrame(rows)


def multi_metric_suite_to_dataframe(suite: MultiMetricSensitivitySuite) -> pd.DataFrame:
    """Flatten a multi-metric tornado suite into a long-form DataFrame."""
    rows: list[dict[str, Any]] = []

    metrics = list(suite.metrics)
    base_metrics = suite.base_metrics

    for row in suite.tornado_results:
        low_values = row.low_values
        high_values = row.high_values
        impacts = row.impacts
        impact_dirs = row.impact_dirs

        variable = row.variable
        label = row.label

        for metric_name in metrics:
            base_val = base_metrics.get(metric_name)
            low_val = low_values.get(metric_name)
            high_val = high_values.get(metric_name)
            impact = impacts.get(metric_name)
            impact_dir = impact_dirs.get(metric_name)

            rows.append(
                {
                    "variable": variable,
                    "label": label,
                    "metric": metric_name,
                    "base_value": base_val,
                    "low_value": low_val,
                    "high_value": high_val,
                    "impact": impact,
                    "impact_dir": impact_dir,
                }
            )

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════
# Plotting stubs (to be implemented)
# ═══════════════════════════════════════════════════════════════════════


def plot_tornado_chart(suite: SensitivitySuite, **kwargs: Any) -> Any:
    """Plot tornado chart from sensitivity suite (stub)."""
    raise NotImplementedError(
        "plot_tornado_chart not yet implemented. "
        "Use tornado_suite_to_dataframe() and plot manually."
    )


def plot_spider_chart(suite: MultiMetricSensitivitySuite, **kwargs: Any) -> Any:
    """Plot spider/radar chart from multi-metric suite (stub)."""
    raise NotImplementedError(
        "plot_spider_chart not yet implemented. "
        "Use multi_metric_suite_to_dataframe() and plot manually."
    )


# ═══════════════════════════════════════════════════════════════════════
# Advanced sensitivity features (stubs for future implementation)
# ═══════════════════════════════════════════════════════════════════════


def enrich_tornado_with_tail_risk(
    suite: SensitivitySuite,
    confidence_level: float = 0.95,
    **kwargs: Any,
) -> SensitivitySuite:
    """Enrich tornado with tail risk metrics (stub)."""
    raise NotImplementedError("enrich_tornado_with_tail_risk not yet implemented")


def optimize_from_sensitivity_insights(
    suite: SensitivitySuite,
    objective: str = "maximize_irr",
    constraints: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Optimize parameters from sensitivity analysis insights (stub)."""
    raise NotImplementedError("optimize_from_sensitivity_insights not yet implemented")


def run_two_way_sensitivity(
    base_config_path: str,
    variable1: str,
    variable2: str,
    param1: ParameterRangeConfig | None = None,
    param2: ParameterRangeConfig | None = None,
    metric: str = "project_irr",
    **kwargs: Any,
) -> dict[str, Any]:
    """Run two-way sensitivity analysis on two parameters (stub)."""
    raise NotImplementedError("run_two_way_sensitivity not yet implemented")


def plot_two_way_heatmap(
    results: dict[str, Any],
    cmap: str = "viridis",
    **kwargs: Any,
) -> Any:
    """Plot two-way sensitivity as heatmap (stub)."""
    raise NotImplementedError("plot_two_way_heatmap not yet implemented")


__all__ = [
    "SensitivityRequest",
    "run_tornado_sensitivity",
    "run_multi_metric_tornado",
    "run_breakeven_parameter",
    "tornado_suite_to_dataframe",
    "multi_metric_suite_to_dataframe",
    "plot_tornado_chart",
    "plot_spider_chart",
    "enrich_tornado_with_tail_risk",
    "optimize_from_sensitivity_insights",
    "run_two_way_sensitivity",
    "plot_two_way_heatmap",
]

# EOF
