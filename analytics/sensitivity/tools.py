"""
tools.py – Utility Tools for Advanced Sensitivity Analytics (v14+)

PURPOSE:
    - Rank tornado outputs by business-driven criteria (e.g. parameter volatility, scenario probability) for reporting.
    - Automatically compare tornado rankings across scenarios to surface shifting risk priorities.

USAGE:
    from analytics.sensitivity.tools import top_drivers_with_confidence, compare_tornadoes

    # Example: Confidence/risk-weighted "top 5" for presentation/reporting:
    top5_df = top_drivers_with_confidence(suite, input_conf_map)

    # Example: IC/board scenario-delta (base vs stress), for waterfall or table:
    delta_df = compare_tornadoes(base_tornado_suite, stress_tornado_suite)

INPUTS:
    - suite, suite_a, suite_b: SensitivitySuite as defined in contracts_v14.
    - input_conf_map: dict[str, float] mapping param variable name → float weighting (volatility, scenario probability, etc.).
"""

import pandas as pd

from analytics.contracts_v14 import SensitivitySuite
from analytics.sensitivity_export import tornado_suite_to_dataframe


def top_drivers_with_confidence(
    suite: SensitivitySuite, input_conf_map: dict[str, float]
) -> pd.DataFrame:
    """
    Weights each tornado driver by confidence/uncertainty/prioritization factor.
    Higher weight means bigger risk or concern.
    """
    df = tornado_suite_to_dataframe(suite)
    df["WeightedImpact"] = df["Impact"] * df["Variable"].map(input_conf_map).fillna(1.0)
    # Sorted by most concerning risk, not just largest numerical impact
    return df.sort_values("WeightedImpact", ascending=False)


def compare_tornadoes(
    suite_a: SensitivitySuite, suite_b: SensitivitySuite
) -> pd.DataFrame:
    """
    Produces a DataFrame showing how tornado impact shifts between scenarios (base vs stress etc.).
    Useful for board, IC, or DFI "what changed?" summaries.
    Columns: [Variable, Impact_A, Impact_B, ImpactDelta ...]
    """
    df_a = tornado_suite_to_dataframe(suite_a).set_index("Variable")
    df_b = tornado_suite_to_dataframe(suite_b).set_index("Variable")
    delta = (df_b["Impact"] - df_a["Impact"]).rename("ImpactDelta")
    joint = df_a.join(df_b, lsuffix="_A", rsuffix="_B", how="outer").fillna(0)
    joint["ImpactDelta"] = delta
    return joint.reset_index()
