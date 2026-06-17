"""
validation.py – Parameter Range QA Checker for v14+ Sensitivity Pipelines

PURPOSE:
    Quickly checks that every lift-lower parameter sweep yields
    reasonable output values. Detects config/model errors (negative IRR,
    crazy outliers) and surface issues early in tests/CI.

USAGE:
    from analytics.sensitivity.validation import validate_parameter_ranges
    problems_df = validate_parameter_ranges(config_path, params)
    if not problems_df.empty:
        print("Suspicious parameter sweeps detected:", problems_df)

RETURNS:
    DataFrame with any param/point that failed basic sanity checks.
"""

from typing import Any, List

import pandas as pd

from analytics.contracts_v14 import ParameterRangeConfig


def _nested_override(dotted_key: str, value: float) -> dict[str, Any]:
    """Expand a dotted key ('a.b.c') into a nested override dict."""
    parts = dotted_key.split(".")
    nested: dict[str, Any] = {}
    cursor = nested
    for part in parts[:-1]:
        cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value
    return nested


def validate_parameter_ranges(
    base_config_path: str,
    parameters: List[ParameterRangeConfig],
    metric: str = "project_irr",
) -> pd.DataFrame:
    """
    For every parameter, check low and high sweep points
    for suspicious outputs (negative IRR, >50%, etc.).
    """
    from analytics.evaluate_scenario import evaluate_with_overrides

    errors = []
    for p in parameters:
        for pct in (p.low_pct, p.high_pct):
            if pct is None:
                # Absolute-mode bounds (low_value/high_value) are not pct-swept here.
                continue
            val = p.base_value * (1 + pct / 100)
            ovr = _nested_override(p.variable_name, val)
            try:
                out = evaluate_with_overrides(base_config_path, ovr)
                met = out[metric]
                if met < 0 or met > 0.5:  # Typical check for IRR
                    errors.append(
                        {
                            "var": p.variable_name,
                            "input": val,
                            "output": met,
                            "pct": pct,
                        }
                    )
            except Exception as e:
                errors.append(
                    {"var": p.variable_name, "input": val, "error": str(e), "pct": pct}
                )
    return pd.DataFrame(errors)
