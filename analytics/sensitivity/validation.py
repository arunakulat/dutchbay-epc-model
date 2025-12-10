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

from typing import List

import pandas as pd

from analytics.contracts_v14 import ParameterRangeConfig


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
    from analytics.sensitivity_v14 import build_nested_override

    errors = []
    for p in parameters:
        for pct in (p.low_pct, p.high_pct):
            val = p.base_value * (1 + pct / 100)
            ovr = build_nested_override(p.variable_name, val)
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
