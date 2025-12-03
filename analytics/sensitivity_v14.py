from __future__ import annotations

# fmt: off
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
from analytics.scenario_loader import load_scenario_config
from run_full_pipeline_v14 import run_v14_pipeline

#!/usr/bin/env python3


# fmt: on

logger = logging.getLogger(__name__)
"""
analytics.sensitivity_v14

Tornado and sensitivity analysis hub for the v14 analytics layer.

This module sits on top of the v14 pipeline and provides high-level APIs
to answer questions like:

- Which input parameters move project IRR the most?
- How sensitive is equity IRR to capex, opex, tariff, and FX?
- What value of parameter X gives me a target IRR (breakeven analysis)?

The module is intentionally engine-agnostic: it only talks to the public
``evaluate_with_overrides`` API and never reaches into lower-level
cashflow/debt engines directly. This keeps it safe as the engines evolve.

Typical usage
-------------
From an analyst notebook or CLI wrapper::

    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity_v14 import (
        SensitivityRequest,
        run_tornado_sensitivity,
    )

    request = SensitivityRequest(
        base_config_path="scenarios/example_a.yaml",
        parameters=[
            ParameterRangeConfig(
                variable_name="financial.tariff_lkr_per_kwh",
                low_pct=-0.10,
                high_pct=0.10,
            ),
        ],
        metric="project_irr",
    )

    suite = run_tornado_sensitivity(request)
    # -> SensitivitySuite with TornadoResult rows for plotting or export

Legacy compatibility
--------------------
This file exposes helper functions (``_load_parameters``,
``_load_parameters_from_yaml``, ``_analyze_single_parameter``) for
backward compatibility with existing v14 test suites and old CI wiring.
These are thin wrappers around the new flow and are deliberately minimal.

The real API surface is:

- ``SensitivityRequest`` dataclass
- ``run_tornado_sensitivity()``
- ``run_multi_metric_tornado()``
- ``run_breakeven_parameter()``
- ``tornado_suite_to_dataframe()``
- ``multi_metric_suite_to_dataframe()``
- ``plot_tornado_chart()``
- ``plot_spider_chart()``
- ``enrich_tornado_with_tail_risk()``
- ``optimize_from_sensitivity_insights()``
- ``run_two_way_sensitivity()``
- ``plot_two_way_heatmap()``
"""

# ═══════════════════════════════════════════════════════════════════════
# Core public request type
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SensitivityRequest:
    """
    Bundle of everything needed to run a tornado sensitivity analysis.

    Parameters
    ----------
    base_config_path : str
        Path to the v14 scenario config (YAML or JSON) to stress-test.
    parameters : list[ParameterRangeConfig]
        List of input parameters to vary (each with base value + shocks).
    override_labels : dict[str, str] or None, optional
        Mapping from ``variable_name`` to human-readable label for
        charts/tables (e.g. "Tariff (LKR/kWh)" instead of
        "financial.tariff_lkr_per_kwh").
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
    """
    Deep merge override dict into base config, preserving nested structure.

    This is needed because sensitivity analysis perturbs specific nested
    parameters (e.g. "finance.tariff") while keeping the rest of the
    config intact.

    Parameters
    ----------
    base : dict[str, Any]
        Base configuration dictionary (from YAML).
    override : dict[str, Any]
        Override dictionary with nested structure (from _build_nested_override).

    Returns
    -------
    dict[str, Any]
        New config dict with overrides applied.

    Examples
    --------
    >>> base = {"finance": {"capex": 100, "tariff": 0.10}, "debt": {}}
    >>> override = {"finance": {"tariff": 0.12}}
    >>> result = _deep_merge_config(base, override)
    >>> result["finance"]["tariff"]
    0.12
    >>> result["finance"]["capex"]  # Preserved
    100
    """
    result = copy.deepcopy(base)

    def _merge(target: dict[str, Any], source: dict[str, Any]) -> None:
        """Recursive merge helper."""
        for key, value in source.items():
            if (
                isinstance(value, dict)
                and key in target
                and isinstance(target[key], dict)
            ):
                # Recurse into nested dicts
                _merge(target[key], value)
            else:
                # Overwrite leaf value
                target[key] = value

    _merge(result, override)
    return result


def _build_nested_override(
    path: str | list[str],
    value: Any,
) -> dict[str, Any]:
    """
    Build nested override dict from dotted string or list of keys.

    Bridge between flat parameter names ("financial.tariff_lkr_per_kwh")
    and the nested dict structure expected by ``evaluate_with_overrides``.

    Parameters
    ----------
    path : str or list[str]
        Dotted parameter path or list of keys.
    value : Any
        Value to set at the end of the path.

    Returns
    -------
    dict[str, Any]
        Nested dictionary with value at leaf.
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
    """
    Centralized debug helper showing what tornado engine is about to run.

    Parameters
    ----------
    where : str
        Calling function name for context.
    base_config_path : str
        Base scenario configuration path.
    metric_names : list[str]
        Metric names being analyzed.
    params : list[ParameterRangeConfig]
        Parameters to vary in sensitivity analysis.
    """
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
            "Check test wiring / SensitivityRequest.parameters.",
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

    This is the core inner-loop helper used by ``run_tornado_sensitivity``.
    Now uses the canonical v14 pipeline (run_v14_pipeline) instead of the
    deprecated evaluate_with_overrides wrapper.

    Parameters
    ----------
    base_config_path : str
        Base scenario configuration path.
    base_metric_value : float
        Base case metric value.
    metric_name : str
        KPI metric name to track (e.g. "project_irr").
    param : ParameterRangeConfig
        Parameter configuration with shock percentages.
    override_labels : dict[str, str] or None, optional
        Custom labels for parameters.

    Returns
    -------
    TornadoResult
        Result with impact analysis for this parameter.
    """
    variable_name = param.variable_name
    low_pct = param.low_pct
    high_pct = param.high_pct

    overrides_low = _build_nested_override(variable_name, (1.0 + low_pct))
    overrides_high = _build_nested_override(variable_name, (1.0 + high_pct))

    logger.debug(
        "_analyze_single_parameter: variable=%s low_pct=%s high_pct=%s",
        variable_name,
        low_pct,
        high_pct,
    )

    # Load base config and apply overrides
    base_config = load_scenario_config(base_config_path)
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

    # Extract KPIs from pipeline results
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

    # Use keyword args to match TornadoResult signature
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
    """
    Run deterministic one-way tornado on provided parameters.

    Two supported calling styles (for compatibility):

    1. New, canonical API (preferred)::

        req = SensitivityRequest(
            base_config_path="scenarios/example_a.yaml",
            parameters=[...],
            metric="project_irr",
        )
        suite = run_tornado_sensitivity(req)

    2. Legacy style (kept for tests/old CI wiring)::

        suite = run_tornado_sensitivity(
            "scenarios/example_a.yaml",
            parameters=[...],
            metric="project_irr",
        )

    Parameters
    ----------
    request : SensitivityRequest or str
        Either a SensitivityRequest instance (preferred) or the base
        config path as a string.
    parameters : list[ParameterRangeConfig] or None, optional
        Optional explicit ParameterRangeConfig sequence. Only used when
        ``request`` is a string; ignored when ``request`` is a
        SensitivityRequest. If omitted, falls back to ``_load_parameters()``.
    metric : str or None, optional
        Name of the metric to use. Only used when ``request`` is a string;
        ignored when ``request`` is a SensitivityRequest (which already
        carries its own metric).

    Returns
    -------
    SensitivitySuite
        Bundle of TornadoResult rows plus base metadata.

    Raises
    ------
    KeyError
        If the requested metric is not found in the KPI dict.
    ValueError
        If parameters or metrics cannot be resolved.
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

    # Evaluate base scenario once using v14 pipeline
    base_config = load_scenario_config(base_config_path)
    base_pipeline_result = run_v14_pipeline(
        config=base_config,
        validation_mode="strict",
    )

    # Extract KPIs from pipeline result
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
        "run_tornado_sensitivity: completed with %d tornado rows; " "top_impact=%f",
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
        low_pct = param.low_pct
        high_pct = param.high_pct

        overrides_low = _build_nested_override(variable_name, (1.0 + low_pct))
        overrides_high = _build_nested_override(variable_name, (1.0 + high_pct))

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

    Parameters
    ----------
    base_config_path : str
        Path to the base v14 scenario config.
    variable_name : str
        Name of the parameter to vary (e.g. "financial.tariff_lkr_per_kwh").
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

    lower = base_param_value * (1.0 + low_pct)
    upper = base_param_value * (1.0 + high_pct)

    logger.info(
        "Breakeven search for %s on %s target=%s bracket=[%s, %s]",
        variable_name,
        target_metric,
        target_value,
        lower,
        upper,
    )

    def objective(x: float) -> float:
        overrides = _build_nested_override(variable_name, x / base_param_value)

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
            "Breakeven objective for %s: param=%s metric=%s value=%s target=%s",
            variable_name,
            x,
            target_metric,
            value,
            target_value,
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
    for _ in range(max_iter):
        mid = 0.5 * (a + b)
        fmid = objective(mid)

        if abs(fmid) < tol:
            logger.info(
                "Breakeven solved for %s: %.6f (residual %.3e)",
                variable_name,
                mid,
                fmid,
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
    """
    Legacy compatibility: load default parameters from YAML file.

    This is intentionally a thin wrapper left in place so old tests
    and CI wiring can continue to import it. New code should construct
    ParameterRangeConfig lists explicitly.

    Returns
    -------
    list[ParameterRangeConfig]
        Parsed parameter configurations, or empty list if file not found.
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
    yaml.YAMLError
        If the YAML file is malformed.
    """
    import yaml

    logger.debug("_load_parameters_from_yaml: loading from %s", path)

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

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

        # Extract base_value (required by ParameterRangeConfig)
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

        # Extract shock percentages with defaults
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

    logger.debug(
        "_load_parameters_from_yaml: loaded %d/%d parameters from %s",
        len(params),
        len(data),
        path,
    )
    return params


# ═══════════════════════════════════════════════════════════════════════
# Public export helpers
# ═══════════════════════════════════════════════════════════════════════


def tornado_suite_to_dataframe(suite: SensitivitySuite) -> pd.DataFrame:
    """
    Convert a one-way tornado SensitivitySuite to a DataFrame.

    Parameters
    ----------
    suite : SensitivitySuite
        Object with ``tornado_results`` attribute containing iterable
        of TornadoResult rows. Each row exposes attributes ``variable``,
        ``base_irr``, ``low_irr``, ``high_irr``, and ``impact_abs``.

    Returns
    -------
    pd.DataFrame
        Tidy table suitable for plotting or regression tests, with one
        row per tornado bar.
    """
    rows: list[dict[str, Any]] = []

    results = suite.tornado_results
    for row in results:
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


def multi_metric_suite_to_dataframe(
    suite: MultiMetricSensitivitySuite,
) -> pd.DataFrame:
    """
    Flatten a multi-metric tornado suite into a long-form DataFrame.

    Parameters
    ----------
    suite : MultiMetricSensitivitySuite
        Object with attributes:

        * ``tornado_results`` – iterable of multi-metric tornado rows
        * ``metrics`` – sequence of metric names (str)
        * ``base_metrics`` – mapping metric -> base metric value

        Each tornado row exposes dictionaries keyed by metric name:
        ``low_values``, ``high_values``, ``impacts``, ``impact_dirs``.

    Returns
    -------
    pd.DataFrame
        One row per (parameter, metric) pair with columns: ``variable``,
        ``label``, ``metric``, ``base_value``, ``low_value``,
        ``high_value``, ``impact``, ``impact_dir``.
    """
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
    """
    Plot tornado chart from sensitivity suite.

    TODO: Implement visualization using matplotlib/plotly.

    Parameters
    ----------
    suite : SensitivitySuite
        Tornado sensitivity results.
    **kwargs : Any
        Additional plotting options.

    Returns
    -------
    Any
        Matplotlib figure or plotly chart.

    Raises
    ------
    NotImplementedError
        Always, pending implementation.
    """
    raise NotImplementedError(
        "plot_tornado_chart not yet implemented. "
        "Use tornado_suite_to_dataframe() and plot manually."
    )


def plot_spider_chart(suite: MultiMetricSensitivitySuite, **kwargs: Any) -> Any:
    """
    Plot spider/radar chart from multi-metric suite.

    TODO: Implement visualization.

    Parameters
    ----------
    suite : MultiMetricSensitivitySuite
        Multi-metric tornado results.
    **kwargs : Any
        Additional plotting options.

    Returns
    -------
    Any
        Matplotlib figure or plotly chart.

    Raises
    ------
    NotImplementedError
        Always, pending implementation.
    """
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
    """
    Enrich tornado with tail risk metrics.

    TODO: Implement tail risk enrichment (VaR, CVaR, etc.).

    Parameters
    ----------
    suite : SensitivitySuite
        Base tornado sensitivity suite.
    confidence_level : float, default 0.95
        Confidence level for tail risk calculation (95%, 99%, etc.).
    **kwargs : Any
        Additional options.

    Returns
    -------
    SensitivitySuite
        Enhanced suite with tail risk metrics.

    Raises
    ------
    NotImplementedError
        Always, pending implementation.
    """
    raise NotImplementedError("enrich_tornado_with_tail_risk not yet implemented")


def optimize_from_sensitivity_insights(
    suite: SensitivitySuite,
    objective: str = "maximize_irr",
    constraints: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Optimize parameters from sensitivity analysis insights.

    TODO: Implement optimization based on tornado results.

    Parameters
    ----------
    suite : SensitivitySuite
        Tornado sensitivity results.
    objective : str, default "maximize_irr"
        Optimization objective (maximize_irr, minimize_cost, etc.).
    constraints : dict[str, Any] or None, optional
        Optimization constraints.
    **kwargs : Any
        Additional options.

    Returns
    -------
    dict[str, Any]
        Optimized parameter values and results.

    Raises
    ------
    NotImplementedError
        Always, pending implementation.
    """
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
    """
    Run two-way sensitivity analysis on two parameters.

    TODO: Implement 2D sensitivity surface analysis.

    Parameters
    ----------
    base_config_path : str
        Path to base scenario config.
    variable1 : str
        First parameter to vary.
    variable2 : str
        Second parameter to vary.
    param1 : ParameterRangeConfig or None, optional
        Configuration for first parameter.
    param2 : ParameterRangeConfig or None, optional
        Configuration for second parameter.
    metric : str, default "project_irr"
        Metric to track.
    **kwargs : Any
        Additional options.

    Returns
    -------
    dict[str, Any]
        Two-way sensitivity matrix and results.

    Raises
    ------
    NotImplementedError
        Always, pending implementation.
    """
    raise NotImplementedError("run_two_way_sensitivity not yet implemented")


def plot_two_way_heatmap(
    results: dict[str, Any],
    cmap: str = "viridis",
    **kwargs: Any,
) -> Any:
    """
    Plot two-way sensitivity as heatmap.

    TODO: Implement heatmap visualization.

    Parameters
    ----------
    results : dict[str, Any]
        Two-way sensitivity results.
    cmap : str, default "viridis"
        Matplotlib colormap name.
    **kwargs : Any
        Additional plotting options.

    Returns
    -------
    Any
        Matplotlib figure or plotly chart.

    Raises
    ------
    NotImplementedError
        Always, pending implementation.
    """
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
