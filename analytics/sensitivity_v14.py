#!/usr/bin/env python3
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

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np  # noqa: F401 - reserved for future use
import pandas as pd  # noqa: F401 - reserved for future export helpers

from analytics.contracts_v14 import (
    BreakevenResult,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
    ParameterRangeConfig,
    SensitivitySuite,
    TornadoResult,
)
from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.monte_carlo_v14 import (  # noqa: F401; Reserved for future VaR / CVaR integration
    MonteCarloResult,
)

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
# Internal helpers
# ---------------------------------------------------------------------------


def _build_nested_override(
    path: Union[str, Sequence[str]],
    value: Any,
) -> Dict[str, Any]:
    """
    Build a nested override dict from either a dotted string or a list of keys.

    Bridge between flat parameter names ("financial.tariff_lkr_per_kwh")
    and the nested dict structure expected by `evaluate_with_overrides`.
    """
    if isinstance(path, str):
        parts: List[str] = [p for p in path.split(".") if p]
    else:
        parts = [str(p) for p in path]

    if not parts:
        raise ValueError("Override path must not be empty")

    nested: Any = value
    for key in reversed(parts):
        nested = {key: nested}
    return nested


def _debug_log_parameters(
    *,
    where: str,
    base_config_path: str,
    metric_names: Sequence[str],
    params: Sequence[ParameterRangeConfig],
) -> None:
    """
    Centralised debug helper so we can see what the tornado engine *thinks*
    it's about to run.
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
            "%s: param[%d]: variable=%s base=%.6f low_pct=%.3f high_pct=%.3f",
            where,
            idx,
            p.variable_name,
            p.base_value,
            p.low_pct,
            p.high_pct,
        )


def _analyze_single_parameter(
    base_config_path: str,
    param: ParameterRangeConfig,
    base_metric_value: float,
    metric: str = "project_irr",
    override_labels: Optional[Dict[str, str]] = None,
) -> TornadoResult:
    """
    Evaluate the effect of a single parameter on the chosen metric.

    We return a TornadoResult that matches the contracts_v14 signature:
    (label, base_value, low_value, high_value, impact_abs, impact_dir).
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

    # Absolute and directional impact on the KPI (not on the raw parameter).
    impact_low = abs(low_metric - base_metric_value)
    impact_high = abs(high_metric - base_metric_value)
    impact_abs = max(impact_low, impact_high)

    # Direction: +1 if the high shock is >= base, else -1.
    impact_dir = 1 if high_metric >= base_metric_value else -1

    logger.debug(
        "analyze_single_parameter: label=%s base=%.6f low=%.6f high=%.6f "
        "impact_abs=%.6e impact_dir=%d metric=%s",
        label,
        base_metric_value,
        low_metric,
        high_metric,
        impact_abs,
        impact_dir,
        metric,
    )

    # IMPORTANT: arguments here must match TornadoResult.__init__ signature.
    return TornadoResult(
        label,
        base_metric_value,
        low_metric,
        high_metric,
        impact_abs,
        impact_dir,
    )


# ---------------------------------------------------------------------------
# Public tornado runners
# ---------------------------------------------------------------------------


def run_tornado_sensitivity(
    request: Union[SensitivityRequest, str],
    parameters: Optional[Sequence[ParameterRangeConfig]] = None,
    metric: Optional[str] = None,
) -> SensitivitySuite:
    """
    Run a deterministic one-way tornado on the provided parameters.

    Two supported calling styles (for compatibility):

    1) New, canonical API (preferred):
        >>> req = SensitivityRequest(
        ...     base_config_path="scenarios/example_a.yaml",
        ...     parameters=[...],
        ...     metric="project_irr",
        ... )
        >>> suite = run_tornado_sensitivity(req)

    2) Legacy API (string + optional parameters):
        >>> suite = run_tornado_sensitivity(
        ...     "scenarios/example_a.yaml",
        ...     parameters=my_params,
        ...     metric="project_irr",
        ... )
    """
    if isinstance(request, SensitivityRequest):
        base_config_path = request.base_config_path
        params: Sequence[ParameterRangeConfig] = list(request.parameters)
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

    # Fallback if tests hand us an empty parameter list.
    if not params:
        logger.warning(
            "run_tornado_sensitivity[request]: resolved empty parameters for %s; "
            "falling back to _load_parameters() defaults.",
            base_config_path,
        )
        params = list(_load_parameters())

    logger.info("Starting tornado sensitivity for %s", base_config_path)
    _debug_log_parameters(
        where="run_tornado_sensitivity[request]",
        base_config_path=base_config_path,
        metric_names=[metric_name],
        params=params,
    )

    base_kpis = evaluate_with_overrides(base_config_path, {})
    base_metric_value = float(base_kpis[metric_name])

    logger.debug(
        "run_tornado_sensitivity[request]: base KPI metric=%s value=%f",
        metric_name,
        base_metric_value,
    )

    results: List[TornadoResult] = []
    for param in params:
        tr = _analyze_single_parameter(
            base_config_path=base_config_path,
            param=param,
            base_metric_value=base_metric_value,
            metric=metric_name,
            override_labels=override_labels,
        )
        results.append(tr)

    # Sort descending by absolute impact, so the biggest drivers float to the top.
    results.sort(key=lambda r: getattr(r, "impact_abs", 0.0), reverse=True)

    top_impact = results[0].impact_abs if results else 0.0
    logger.debug(
        "run_tornado_sensitivity[request]: completed with %d tornado rows; "
        "top_impact=%f",
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
            results[0].impact_abs,
        )
    else:
        logger.info("Tornado complete: no parameters provided")

    return suite


def run_multi_metric_tornado(
    request: Union[SensitivityRequest, str],
    metrics: Sequence[str],
    parameters: Optional[Sequence[ParameterRangeConfig]] = None,
) -> MultiMetricSensitivitySuite:
    """
    Run a tornado over multiple KPI metrics at once.

    New, preferred style:

        >>> req = SensitivityRequest(
        ...     base_config_path="scenarios/example_a.yaml",
        ...     parameters=[...],
        ... )
        >>> suite = run_multi_metric_tornado(req, metrics=["project_irr", "equity_irr"])

    Legacy style (kept for compatibility):

        >>> suite = run_multi_metric_tornado(
        ...     "scenarios/example_a.yaml",
        ...     metrics=["project_irr", "equity_irr"],
        ...     parameters=my_params,
        ... )
    """
    if isinstance(request, SensitivityRequest):
        base_config_path = request.base_config_path
        params: Sequence[ParameterRangeConfig] = list(request.parameters)
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
            "run_multi_metric_tornado[request]: resolved empty parameters for %s; "
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
        where="run_multi_metric_tornado[request]",
        base_config_path=base_config_path,
        metric_names=list(metrics),
        params=params,
    )

    base_kpis = evaluate_with_overrides(base_config_path, {})
    base_metric_vals = {m: float(base_kpis[m]) for m in metrics}

    logger.debug(
        "run_multi_metric_tornado[request]: base KPI metrics=%s values=%s",
        list(metrics),
        base_metric_vals,
    )

    results: List[MultiMetricTornadoResult] = []

    for param in params:
        low_val = param.base_value * (1.0 + 0.01 * param.low_pct)
        high_val = param.base_value * (1.0 + 0.01 * param.high_pct)

        low_override = _build_nested_override(param.variable_name, low_val)
        low_kpis = evaluate_with_overrides(base_config_path, low_override)

        high_override = _build_nested_override(param.variable_name, high_val)
        high_kpis = evaluate_with_overrides(base_config_path, high_override)

        low_metrics = {m: float(low_kpis[m]) for m in metrics}
        high_metrics = {m: float(high_kpis[m]) for m in metrics}

        label = (
            override_labels.get(param.variable_name, param.variable_name)
            if override_labels
            else param.variable_name
        )

        impacts = {m: abs(high_metrics[m] - low_metrics[m]) for m in metrics}
        impact_dirs = {
            m: 1 if high_metrics[m] >= low_metrics[m] else -1 for m in metrics
        }

        logger.debug(
            "run_multi_metric_tornado[request]: label=%s low=%s high=%s impacts=%s",
            label,
            low_metrics,
            high_metrics,
            impacts,
        )

        # IMPORTANT: arguments here must match MultiMetricTornadoResult signature.
        results.append(
            MultiMetricTornadoResult(
                label,
                base_metric_vals.copy(),
                low_metrics,
                high_metrics,
                impacts,
                impact_dirs,
            )
        )

    suite = MultiMetricSensitivitySuite(
        tornado_results=results,
        base_metrics=base_metric_vals,
        base_config_path=base_config_path,
        metrics=list(metrics),
    )

    logger.debug(
        "run_multi_metric_tornado[request]: completed with %d tornado rows; metrics=%s",
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
        value = float(kpis[target_metric])
        logger.debug(
            "breakeven objective: var=%s x=%.6f metric=%s value=%.6f target=%.6f",
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
    """
    if parameters is not None:
        logger.debug(
            "_load_parameters: using explicit parameters (n=%d)", len(parameters)
        )
        return list(parameters)

    if not use_defaults:
        raise ValueError(
            "parameters is None and use_defaults=False; nothing to run sensitivity on."
        )

    defaults = _create_default_parameters()
    logger.debug("_load_parameters: using default parameters (n=%d)", len(defaults))
    return defaults


def _create_default_parameters() -> Sequence[ParameterRangeConfig]:
    """
    Small, safe “house default” sensitivity definition.

    This is intentionally simple and scenario-agnostic so that legacy calls
    (including tests that forgot to pass parameters) still get a non-empty
    tornado, but nothing here is relied upon for production analytics.
    """
    return [
        ParameterRangeConfig(
            variable_name="financial.tariff_lkr_per_kwh",
            base_value=65.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
        ParameterRangeConfig(
            variable_name="capex.total_capex_lkr",
            base_value=150_000_000.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
        ParameterRangeConfig(
            variable_name="opex.fixed_opex_lkr_per_year",
            base_value=10_000_000.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
    ]


def _load_parameters_from_yaml(
    path: Union[str, Path],
) -> Sequence[ParameterRangeConfig]:
    """
    Very small helper to load ParameterRangeConfig entries from a YAML file.

    Minimal supported schema:

        - variable_name: financial.tariff_lkr_per_kwh
          base_value: 65.0
          low_pct: -15.0
          high_pct: 15.0
    """
    path = Path(path)

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Sensitivity YAML not found: {path}") from exc

    import yaml  # type: ignore[import]

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
            raise ValueError(f"Parameter row {idx} in {path} is not a mapping: {row!r}")

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

    logger.debug(
        "_load_parameters_from_yaml: loaded %d parameters from %s",
        len(params),
        path,
    )
    return params


# EOF
