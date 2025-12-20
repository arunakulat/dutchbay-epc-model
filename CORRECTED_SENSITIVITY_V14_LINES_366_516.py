#!/usr/bin/env python3
"""
CORRECTED CODE: analytics/sensitivity_v14.py lines 366-516

GWTF Compliance: Phase 1 Gateway Pattern
CASPER: Single Parameter Shock Analysis
CESSPIT: Evaluation gateway, no direct pipeline imports
CCCDIR: Correct, Clean, Complete, Direct, Idiomatic, Readable

Copy-paste this code to replace lines 366-516 in analytics/sensitivity_v14.py
"""

# ═══════════════════════════════════════════════════════════════════════════
# Core Sensitivity Analysis: Single Parameter Shock
# ═══════════════════════════════════════════════════════════════════════════


def analyze_single_parameter(
    base_config_path: str | Path,
    base_metric_value: float,
    metric_name: str,
    param: ParameterRangeConfig,
    override_labels: dict[str, str] | None = None,
) -> TornadoResult:
    """
    Run low/high shocks for a single parameter and return TornadoResult.

    This function is the core of tornado sensitivity analysis. It:

    - Takes a single parameter with base value and +/- shock ranges
    - Evaluates the scenario at low and high parameter values
    - Computes impact on the chosen metric
    - Returns a TornadoResult for aggregation into a full tornado chart

    Phase 1 Key Change
    ------------------
    All scenario evaluation now flows through evaluate_with_overrides() gateway.
    No direct pipeline or config loader imports; no manual merging of configs.

    Parameters
    ----------
    base_config_path : str | Path
        Path to the base v14 scenario config.

    base_metric_value : float
        KPI value at base (unshocked) configuration.

    metric_name : str
        Name of the KPI to analyze (e.g., "project_irr").

    param : ParameterRangeConfig
        Parameter descriptor (name, base_value, low_pct, high_pct).

    override_labels : dict[str, str] | None, optional
        Optional mapping from variable_name to display label.

    Returns
    -------
    TornadoResult
        Dataclass with metric_name, base_metric, shock_results fields.

    Raises
    ------
    KeyError
        If metric_name not found in evaluated KPI dict.
    """
    variable_name = param.variable_name

    # Normalise +/- percentages; allow caller to pass 5 or 0.05.
    low_pct_decimal = (
        param.low_pct / 100.0 if abs(param.low_pct) > 1.0 else param.low_pct
    )
    high_pct_decimal = (
        param.high_pct / 100.0 if abs(param.high_pct) > 1.0 else param.high_pct
    )

    base_value = param.base_value

    # Compute absolute shocked values.
    low_value = base_value * (1.0 + low_pct_decimal)
    high_value = base_value * (1.0 + high_pct_decimal)

    # Build nested override dicts for parameter shocks.
    overrides_low = build_nested_override(variable_name, low_value)
    overrides_high = build_nested_override(variable_name, high_value)

    logger.debug(
        "analyze_single_parameter: variable=%s base=%s "
        "low_pct=%s%% high_pct=%s%% → low_value=%s high_value=%s",
        variable_name,
        base_value,
        param.low_pct,
        param.high_pct,
        low_value,
        high_value,
    )

    # ════════════════════════════════════════════════════════════════════
    # PHASE 1 KEY: All evaluation flows through evaluate_with_overrides() gateway
    # ════════════════════════════════════════════════════════════════════
    low_kpis = evaluate_with_overrides(base_config_path, overrides_low)
    high_kpis = evaluate_with_overrides(base_config_path, overrides_high)

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
        "analyze_single_parameter: variable=%s label=%s "
        "base=%s low=%s high=%s impact=%s dir=%s",
        variable_name,
        label,
        base_metric_value,
        low_metric,
        high_metric,
        impact_abs,
        impact_dir,
    )

    # ════════════════════════════════════════════════════════════════════
    # PHASE 1 PYDANTIC V2 FIX: Proper dataclass construction
    # ════════════════════════════════════════════════════════════════════
    # TornadoResult is a dataclass expecting:
    #   - metric_name: str
    #   - base_metric: float
    #   - shock_results: List[ShockResult]
    #   - low_case_metric: Optional[float]
    #   - high_case_metric: Optional[float]
    #
    # ShockResult is also a dataclass with all shock details.
    # ════════════════════════════════════════════════════════════════════

    from analytics.contracts_v14 import ShockResult

    shock = ShockResult(
        variable_name=variable_name,
        base_value=base_value,
        low_value=low_value,
        high_value=high_value,
        base_metric=base_metric_value,
        low_metric=low_metric,
        high_metric=high_metric,
        metric_name=metric_name,
        label=label,
    )

    return TornadoResult(
        metric_name=metric_name,
        base_metric=base_metric_value,
        shock_results=[shock],
        low_case_metric=low_metric,
        high_case_metric=high_metric,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Public Tornado Runners
# ═══════════════════════════════════════════════════════════════════════════
