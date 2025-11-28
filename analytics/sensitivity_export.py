#!/usr/bin/env python3
"""
Export helpers for v14 sensitivity / tornado results.

This module provides small, Pandas-based helpers to turn the core
analytics contracts into tabular DataFrames suitable for:

- Excel export
- Plots (matplotlib / seaborn / Plotly)
- Dashboards (Streamlit, Dash, etc.)

It is intentionally thin: the *semantics* live in analytics.contracts_v14
and analytics.sensitivity_v14; this file is just formatting glue.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from analytics.contracts_v14 import (
    BreakevenResult,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
    SensitivitySuite,
    TornadoResult,
)

# ---------------------------------------------------------------------------
# Tornado (single-metric) export
# ---------------------------------------------------------------------------


def _tornado_row_to_dict(row: TornadoResult) -> Dict[str, Any]:
    """
    Convert a TornadoResult into a flat dict for DataFrame construction.

    We support both the legacy field names (base_irr / low_irr / high_irr)
    and any newer, more generic naming (base_metric / low_metric / high_metric).
    """
    base = getattr(row, "base_irr", None)
    low = getattr(row, "low_irr", None)
    high = getattr(row, "high_irr", None)

    if base is None:
        base = getattr(row, "base_metric", None)
    if low is None:
        low = getattr(row, "low_metric", None)
    if high is None:
        high = getattr(row, "high_metric", None)

    impact = getattr(row, "impact_abs", None)
    if impact is None and low is not None and high is not None:
        impact = abs(high - low)

    direction = getattr(row, "impact_dir", None)
    if direction is None and low is not None and high is not None:
        direction = 1 if high >= low else -1

    return {
        "Variable": getattr(row, "variable", ""),
        "Base": base,
        "Low": low,
        "High": high,
        "Impact": impact,
        "Direction": direction,
    }


def tornado_suite_to_dataframe(suite: SensitivitySuite) -> pd.DataFrame:
    """
    Convert a SensitivitySuite (single-metric tornado) into a DataFrame.

    Columns (by design):

    - Variable   : human-readable variable label
    - Base       : base-case KPI value
    - Low        : KPI value at low shock
    - High       : KPI value at high shock
    - Impact     : absolute impact |High - Low|
    - Direction  : +1 if High >= Low, -1 otherwise

    The DataFrame is sorted descending by Impact.
    """
    rows: List[Dict[str, Any]] = [
        _tornado_row_to_dict(r) for r in suite.tornado_results
    ]

    df = pd.DataFrame(rows)

    if not df.empty:
        if "Impact" not in df.columns:
            # Defensive, but should not happen given _tornado_row_to_dict
            df["Impact"] = (df["High"] - df["Low"]).abs()
        df = df.sort_values("Impact", ascending=False).reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Multi-metric tornado export
# ---------------------------------------------------------------------------


def _multi_metric_row_to_dict(row: MultiMetricTornadoResult) -> Dict[str, Any]:
    """
    Flatten a MultiMetricTornadoResult into a dict keyed by metric name.

    The resulting dict is shaped for pivoting / plotting, e.g.:

        {
            "Variable": "Tariff (LKR/kWh)",
            "metric": "project_irr",
            "Base": 0.14,
            "Low": 0.12,
            "High": 0.16,
            "Impact": 0.04,
            "Direction": 1,
        }
    """
    out: List[Dict[str, Any]] = []

    for metric_name, base_val in row.base_values.items():
        low_val = row.low_values.get(metric_name)
        high_val = row.high_values.get(metric_name)
        impact = row.impacts.get(metric_name)
        direction = row.impact_dirs.get(metric_name)

        if impact is None and low_val is not None and high_val is not None:
            impact = abs(high_val - low_val)
        if direction is None and low_val is not None and high_val is not None:
            direction = 1 if high_val >= low_val else -1

        out.append(
            {
                "Variable": row.variable,
                "Metric": metric_name,
                "Base": base_val,
                "Low": low_val,
                "High": high_val,
                "Impact": impact,
                "Direction": direction,
            }
        )

    # For compatibility with callers expecting a flat dict per metric,
    # the caller (multi_metric_suite_to_dataframe) will flatten this list.
    # Here we just return the first element if needed.
    # This function is used as a helper; see below.
    # To keep API simple, we do not expose it directly.
    # We return the list and let the caller flatten.
    return out  # type: ignore[return-value]


def multi_metric_suite_to_dataframe(
    suite: MultiMetricSensitivitySuite,
) -> pd.DataFrame:
    """
    Convert a MultiMetricSensitivitySuite into a long-form DataFrame.

    Columns:

    - Variable   : parameter label
    - Metric     : KPI name (e.g. 'project_irr', 'equity_irr')
    - Base       : base-case KPI
    - Low        : KPI at low shock
    - High       : KPI at high shock
    - Impact     : |High - Low|
    - Direction  : +1/-1 (sign of High - Low)
    """
    rows: List[Dict[str, Any]] = []
    for r in suite.tornado_results:
        metric_rows = _multi_metric_row_to_dict(r)
        rows.extend(metric_rows)  # type: ignore[arg-type]

    df = pd.DataFrame(rows)

    if not df.empty and "Impact" in df.columns:
        df = df.sort_values(["Metric", "Impact"], ascending=[True, False]).reset_index(
            drop=True
        )

    return df


# ---------------------------------------------------------------------------
# Breakeven export
# ---------------------------------------------------------------------------


def breakeven_results_to_dataframe(results: List[BreakevenResult]) -> pd.DataFrame:
    """
    Convert a list of BreakevenResult objects into a DataFrame with columns:

    - Variable
    - BreakevenValue
    - BracketLow
    - BracketHigh
    - Status
    """
    rows: List[Dict[str, Any]] = []

    for r in results:
        low, high = r.bracket
        rows.append(
            {
                "Variable": r.variable,
                "BreakevenValue": r.breakeven_value,
                "BracketLow": low,
                "BracketHigh": high,
                "Status": r.status,
            }
        )

    return pd.DataFrame(rows)
