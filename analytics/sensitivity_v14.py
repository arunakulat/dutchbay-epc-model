"""
Tornado / sensitivity analysis hub for the v14 analytics layer.

This module is designed to sit **on top of** the v14 pipeline and provide
simple, high-level ways to answer questions like:

- “Which input parameters move project IRR the most?”
- “How sensitive is equity IRR to capex, opex, tariff, and FX?”
- “What value of parameter X gives me a target IRR (breakeven analysis)?”

It is intentionally **engine-agnostic**: it only talks to the public
`evaluate_with_overrides` API and never reaches into the lower-level
cashflow / debt engines directly. That keeps it safe as the engines evolve.

Typical usage from an analyst notebook (or CLI wrapper):

    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity_v14 import SensitivityRequest, run_tornado_sensitivity

    params = [
        ParameterRangeConfig(
            variable_name="financial.tariff_lkr_per_kwh",
            base_value=65.0,
            low_pct=-15.0,
            high_pct=15.0,
        ),
        # … more parameters …
    ]

    request = SensitivityRequest(
        base_config_path="scenarios/example_a.yaml",
        parameters=params,
        metric="project_irr",
    )

    suite = run_tornado_sensitivity(request)
    # -> SensitivitySuite with TornadoResult rows you can plot or export.

This file also exposes a handful of legacy-compatibility helpers
(`_load_parameters`, `_create_default_parameters`, `_analyze_single_parameter`,
`_load_parameters_from_yaml`) so that the existing v14 test suite and
old CI wiring can import this module without blowing up. Those helpers are
thin wrappers around the new flow and are deliberately minimal; the real
API to use going forward is:

- `SensitivityRequest`
- `run_tornado_sensitivity`
- `run_multi_metric_tornado`
- `run_breakeven_parameter`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.contracts_v14 import (
    ParameterRangeConfig,
    TornadoResult,
    SensitivitySuite,
    BreakevenResult,
    MultiMetricTornadoResult,
    MultiMetricSensitivitySuite,
)
from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from analytics.monte_carlo_v14 import MonteCarloResult  # Reserved for future VaR / CVaR integration

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core public request type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SensitivityRequest:
    """
    Simple, explicit bundle of everything needed to run a tornado.

    Attributes
    ----------
    base_config_path:
        Path to the v14 scenario config (YAML or JSON) you want to stress.
    parameters:
        Sequence of ParameterRangeConfig describing each input you want to
        vary (base value + +/- percentage shocks).
    override_labels:
        Optional mapping from `variable_name` -> short human-readable label
        for charts / tables (e.g. "Tariff (LKR/kWh)" instead of
        "financial.tariff_lkr_per_kwh").
    metric:
        Name of the KPI field in the KPI dict returned by
        `evaluate_with_overrides` to use as the tornado axis
        (e.g. "project_irr", "equity_irr", "project_mirr").
    """

    base_config_path: str
    parameters: Sequence[ParameterRangeConfig]
    override_labels: Optional[Dict[str, str]] = None
    metric: str = "project_irr"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _build_nested_override(
    path: Union[str, Sequence[str]],
    value: Any,
) -> Dict[str, Any]:
    """
    Build a nested override dict from either a dotted string or a list of keys.

    This is the small but critical glue between the *flat* parameter naming
    convention used in analytics ("financial.tariff_lkr_per_kwh") and the
    nested dict structure expected by `evaluate_with_overrides`.

    Examples
    --------
    >>> _build_nested_override("financial.tariff_lkr_per_kwh", 70.0)
    {'financial': {'tariff_lkr_per_kwh': 70.0}}

    >>> _build_nested_override(["tax", "corporate_tax_rate"], 0.24)
    {'tax': {'corporate_tax_rate': 0.24}}
    """
    if isinstance(path, str):
        parts: List[str] = [p for p in path.split(".") if p]
    else:
        # Tests sometimes pass a list/tuple of keys – support that too.
        parts = [str(p) for p in path]

    if not parts:
        raise ValueError("Override path must not be empty")

    nested: Any = value
    for key in reversed(parts):
        nested = {key: nested}
    return nested


def _analyze_single_parameter(
    base_config_path: str,
    param: ParameterRangeConfig,
    base_metric: float,
    metric: str = "project_irr",
    override_labels: Optional[Dict[str, str]] = None,
) -> TornadoResult:
    """
    Evaluate the effect of a single parameter on the chosen metric.

    This is the workhorse used by `run_tornado_sensitivity`: given one
    ParameterRangeConfig, it builds low/high overrides, runs the model,
    and returns a `TornadoResult`.

    Parameters
    ----------
    base_config_path:
        Scenario file to evaluate.
    param:
        ParameterRangeConfig describing base value and +/- percentage shocks.
    base_metric:
        Already-computed base metric (e.g. project IRR for the un-shocked case).
    metric:
        KPI name to read from the KPI dict.
    override_labels:
        Optional mapping of variable_name -> short label.

    Returns
    -------
    TornadoResult
        dataclass from `analytics.contracts_v14`, safe for plotting and export.
    """
    low_val = param.base_value * (1.0 + 0.01 * param.low_pct)
    high_val = param.base_value * (1.0 + 0.01 * param.high_pct)

    low_override = _build_nested_override(param.variable_name, low_val)
    low_kpis = evaluate_with_overrides(base_config_path, low_override)
    low_metric = float(low_kpis[metric])

    high_override = _build_nested_override(param.variable_name, high_val)
    high_kpis = evaluate_with_overrides(base_config_path, high_override)
    high_metric = float(high_kpis[metric])

    label = (
        override_labels.get(param.variable_name, param.variable_name)
        if override_labels
        else param.variable_name
    )

    # NOTE: TornadoResult in contracts_v14 owns the impact_abs/impact_dir logic
    # via properties; we just pass through the three metric values.
    return TornadoResult(
        variable=label,
        base_irr=base_metric,
        low_irr=low_metric,
        high_irr=high_metric,
    )


# ---------------------------------------------------------------------------
# Public tornado runners
# ---------------------------------------------------------------------------

def run_tornado_sensitivity(request: SensitivityRequest) -> SensitivitySuite:
    """
    Run a deterministic one-way tornado on the provided parameters.

    Parameters
    ----------
    request:
        SensitivityRequest bundling scenario path, parameters, and metric name.

    Returns
    -------
    SensitivitySuite
        A simple container with:
        - `base_case_irr` (or base metric),
        - `tornado_results` (list of TornadoResult),
        - `metric_name`,
        - `config_path`.

    Usage
    -----
    >>> suite = run_tornado_sensitivity(
    ...     SensitivityRequest(
    ...         base_config_path="scenarios/example_a.yaml",
    ...         parameters=[...],
    ...         metric="project_irr",
    ...     )
    ... )
    >>> for row in suite.tornado_results:
    ...     print(row.variable, row.impact_abs)
    """
    logger.info("Starting tornado sensitivity for %s", request.base_config_path)

    # Base case KPI evaluation (no overrides).
    base_kpis = evaluate_with_overrides(request.base_config_path, {})
    base_metric_value = float(base_kpis[request.metric])

    results: List[TornadoResult] = []
    for param in request.parameters:
        tr = _analyze_single_parameter(
            base_config_path=request.base_config_path,
            param=param,
            base_metric=base_metric_value,
            metric=request.metric,
            override_labels=request.override_labels,
        )
        results.append(tr)

    # Sort descending by absolute impact, so the biggest drivers float to the top.
    results.sort(key=lambda r: r.impact_abs, reverse=True)

    suite = SensitivitySuite(
        tornado_results=results,
        base_case_irr=base_metric_value,
        metric_name=request.metric,
        config_path=request.base_config_path,
    )

    if results:
        logger.info(
            "Tornado complete: %d parameters, top driver: %s (impact %.4f)",
            len(results),
            len(results),
            results[0].impact_abs,
        )
    else:
        logger.info("Tornado complete: no parameters provided")

    return suite


def run_multi_metric_tornado(
    request: SensitivityRequest,
    metrics: Sequence[str],
) -> MultiMetricSensitivitySuite:
    """
    Run a tornado over multiple KPI metrics at once.

    This is intended for “spider chart” style views where, for each parameter,
    you want to see its impact on (say) project_irr, equity_irr, and project_mirr
    side-by-side.

    Parameters
    ----------
    request:
        SensitivityRequest describing the scenario + parameters.
    metrics:
        KPI names to pull from the KPI dict for each run.

    Returns
    -------
    MultiMetricSensitivitySuite
        See `analytics.contracts_v14` for the exact schema.
    """
    logger.info(
        "Starting multi-metric tornado for %s on metrics=%s",
        request.base_config_path,
        list(metrics),
    )

    base_kpis = evaluate_with_overrides(request.base_config_path, {})
    base_metric_vals = {m: float(base_kpis[m]) for m in metrics}

    results: List[MultiMetricTornadoResult] = []

    for param in request.parameters:
        low_val = param.base_value * (1.0 + 0.01 * param.low_pct)
        high_val = param.base_value * (1.0 + 0.01 * param.high_pct)

        low_override = _build_nested_override(param.variable_name, low_val)
        low_kpis = evaluate_with_overrides(request.base_config_path, low_override)

        high_override = _build_nested_override(param.variable_name, high_val)
        high_kpis = evaluate_with_overrides(request.base_config_path, high_override)

        low_metrics = {m: float(low_kpis[m]) for m in metrics}
        high_metrics = {m: float(high_kpis[m]) for m in metrics}

        label = (
            request.override_labels.get(param.variable_name, param.variable_name)
            if request.override_labels
            else param.variable_name
        )

        impacts = {
            m: abs(high_metrics[m] - low_metrics[m]) for m in metrics
        }
        impact_dirs = {
            m: 1 if high_metrics[m] >= low_metrics[m] else -1 for m in metrics
        }

        results.append(
            MultiMetricTornadoResult(
                variable=label,
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
        base_config_path=request.base_config_path,
        metrics=list(metrics),
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
    target_value: float = 0.12,
    lower: float = 0.5,
    upper: float = 2.0,
    tol: float = 1e-4,
    max_iter: int = 32,
) -> BreakevenResult:
    """
    Solve for the parameter value that delivers a target KPI (simple bisection).

    Think of this as answering questions like:

    - “What tariff do I need for project_irr == 12%?”
    - “What capex per MW keeps equity_irr at 18%?”

    Parameters
    ----------
    base_config_path:
        Scenario file to evaluate.
    variable_name:
        Dotted parameter path (e.g. "financial.tariff_lkr_per_kwh").
    target_metric:
        KPI name in the KPI dict.
    target_value:
        Desired KPI level (e.g. 0.12 for 12%).
    lower, upper:
        Search bracket for the parameter value (in the same units as the
        parameter – e.g. tariff LKR/kWh).
    tol:
        Absolute tolerance on the KPI difference `f(x) = metric(x) - target`.
    max_iter:
        Maximum number of bisection iterations.

    Returns
    -------
    BreakevenResult
        dataclass capturing the best-found value and search bracket.
    """
    logger.info(
        "Breakeven solve for %s: %s ~= %.4f over [%.4f, %.4f]",
        variable_name,
        target_metric,
        target_value,
        lower,
        upper,
    )

    def objective(x: float) -> float:
        override = _build_nested_override(variable_name, x)
        kpis = evaluate_with_overrides(base_config_path, override)
        return float(kpis[target_metric]) - target_value

    a, b = lower, upper
    fa, fb = objective(a), objective(b)

    if fa * fb > 0:
        raise ValueError(
            f"Breakeven: root not bracketed for {variable_name!r} "
            f"over [{lower}, {upper}] – f(a)={fa:.4f}, f(b)={fb:.4f}"
        )

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

        # Standard bisection update
        if fa * fmid < 0:
            b, fb = mid, fmid
        else:
            a, fa = mid, fmid

    logger.warning(
        "Breakeven did not converge for %s after %d iterations; last bracket=[%.4f, %.4f]",
        variable_name,
        max_iter,
        a,
        b,
    )

    return BreakevenResult(
        variable=variable_name,
        breakeven_value=None,
        bracket=(a, b),
        status="fail",
    )


# ---------------------------------------------------------------------------
# Legacy / test-compatibility helpers
# ---------------------------------------------------------------------------

def _load_parameters(
    parameters: Optional[Sequence[ParameterRangeConfig]] = None,
    use_defaults: bool = True,
) -> Sequence[ParameterRangeConfig]:
    """
    Legacy shim used by older tests to control the parameter list.

    New code should normally construct `SensitivityRequest` directly and pass
    an explicit `parameters` list.

    Behaviour
    ---------
    - If `parameters` is provided, it is returned as-is (converted to a list).
    - If `parameters` is None and `use_defaults` is True, this calls
      `_create_default_parameters()`.
    - If `parameters` is None and `use_defaults` is False, a ValueError is
      raised.

    The test suite usually patches this function, so its *behaviour* is much
    less important than its presence and signature.
    """
    if parameters is not None:
        return list(parameters)

    if not use_defaults:
        raise ValueError(
            "parameters is None and use_defaults=False; nothing to run sensitivity on."
        )

    return _create_default_parameters()


def _create_default_parameters() -> Sequence[ParameterRangeConfig]:
    """
    Placeholder for a future “house default” sensitivity definition.

    In a future sprint, this can be wired to a config file (e.g.
    `sensitivity_defaults.yaml`) or a curated list of 8–12 canonical
    parameters (tariff, capex/MW, opex/MW, FX, interest margin, etc.).

    For now, this raises NotImplementedError so that any accidental reliance
    on implicit defaults is obvious during interactive use – while the test
    suite can safely patch this function where needed.
    """
    raise NotImplementedError(
        "Default sensitivity parameters are not yet defined. "
        "Pass an explicit `parameters` list, or patch "
        "`_create_default_parameters` in tests."
    )


def _load_parameters_from_yaml(path: Union[str, Path]) -> Sequence[ParameterRangeConfig]:
    """
    Very small helper to load ParameterRangeConfig entries from a YAML file.

    This exists primarily to keep the existing v14 test scaffolding happy.
    A minimal supported schema would look like:

        - variable_name: financial.tariff_lkr_per_kwh
          base_value: 65.0
          low_pct: -15.0
          high_pct: 15.0

    Any row missing one of these keys will trigger a ValueError.
    """
    path = Path(path)

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Sensitivity YAML not found: {path}") from exc

    import yaml  # Local import to avoid hard dependency at module import time.

    try:
        data = yaml.safe_load(raw)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Failed to parse sensitivity YAML: {path}") from exc

    if not isinstance(data, list):
        raise ValueError(
            f"Sensitivity YAML must contain a top-level list of parameters, "
            f"got {type(data).__name__} from {path}"
        )

    params: List[ParameterRangeConfig] = []
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            raise ValueError(
                f"Parameter row {idx} in {path} is not a mapping: {row!r}"
            )

        try:
            variable_name = row["variable_name"]
            base_value = float(row["base_value"])
            low_pct = float(row["low_pct"])
            high_pct = float(row["high_pct"])
        except KeyError as exc:
            raise ValueError(
                f"Missing required key {exc.args[0]!r} in sensitivity row {idx} "
                f"from {path}"
            ) from exc

        params.append(
            ParameterRangeConfig(
                variable_name=variable_name,
                base_value=base_value,
                low_pct=low_pct,
                high_pct=high_pct,
            )
        )

    return params
    