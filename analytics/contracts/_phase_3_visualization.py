"""Unified tornado visualization for Phase 3 sensitivity contracts.

This module provides visualization helpers that work with Phase 3 contracts,
enabling seamless integration with Plotly, Matplotlib, and dashboard tools.

Architecture Compliance
-----------------------
CASPER:  Contract-first visualization API
CESSPIT: Type-safe data transformations
GWTF:    Full type annotations for mypy strict
CCCDIR:  Comprehensive docstrings with usage examples

Public API
----------
- to_tornado_dataframe(suite) -> pd.DataFrame
- prepare_tornado_data(suite) -> Dict[str, Any]
- create_tornado_chart(suite, **kwargs) -> Figure

Usage Example
-------------
```python
from analytics.contracts import (
    StandardShockLibrary,
    SensitivitySuite,
    to_tornado_dataframe,
)
from analytics.sensitivity_v14 import run_tornado_sensitivity

# Run sensitivity
suite = run_tornado_sensitivity(...)

# Convert to DataFrame
df = to_tornado_dataframe(suite)

# Export or visualize
df.to_excel("tornado_results.xlsx")
```
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from analytics.contracts._phase_3_sensitivity import (
    MultiScenarioSuite,
    ScenarioResult,
    SensitivitySuite,
    ShockResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Type Aliases
# ═══════════════════════════════════════════════════════════════════════════

TornadoSuite = Union[SensitivitySuite, Any]  # Any allows v14 SensitivitySuite


# ═══════════════════════════════════════════════════════════════════════════
# Core Converters: Contract → DataFrame
# ═══════════════════════════════════════════════════════════════════════════


def to_tornado_dataframe(
    suite: TornadoSuite,
    *,
    sort_by_impact: bool = True,
) -> pd.DataFrame:
    """Convert sensitivity suite to pandas DataFrame.
    
    Works with both Phase 3 and v14 SensitivitySuite contracts.
    
    Parameters
    ----------
    suite : TornadoSuite
        Phase 3 or v14 SensitivitySuite instance.
    sort_by_impact : bool, default=True
        Sort rows by absolute impact (descending).
    
    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - variable: Variable name
        - label: Display label
        - base_metric: Baseline metric value
        - low_metric: Low shock metric value
        - high_metric: High shock metric value
        - impact: Absolute impact
        - direction: Impact direction ('positive'/'negative')
        - sensitivity: Sensitivity coefficient
    
    Raises
    ------
    TypeError
        If suite is not a recognized SensitivitySuite type.
    
    Examples
    --------
    >>> df = to_tornado_dataframe(suite)
    >>> df.to_excel("tornado.xlsx", index=False)
    >>> print(df[["label", "impact"]].head())
    """
    # Check if Phase 3 SensitivitySuite
    if isinstance(suite, SensitivitySuite):
        return _phase3_suite_to_dataframe(suite, sort_by_impact=sort_by_impact)
    
    # Check if v14 SensitivitySuite (duck typing)
    if hasattr(suite, "tornado_results") and hasattr(suite, "base_metric"):
        return _v14_suite_to_dataframe(suite, sort_by_impact=sort_by_impact)
    
    raise TypeError(
        f"Unsupported suite type: {type(suite).__name__}. "
        "Expected Phase 3 or v14 SensitivitySuite."
    )


def _phase3_suite_to_dataframe(
    suite: SensitivitySuite,
    *,
    sort_by_impact: bool = True,
) -> pd.DataFrame:
    """Convert Phase 3 SensitivitySuite to DataFrame."""
    rows: List[Dict[str, Any]] = []
    
    for shock in suite.tornado_ranking:
        rows.append({
            "variable": shock.variable_name,
            "label": shock.label,
            "base_metric": shock.base_metric,
            "low_metric": shock.low_metric,
            "high_metric": shock.high_metric,
            "impact": shock.impact,
            "direction": shock.direction,
            "sensitivity": shock.sensitivity,
        })
    
    df = pd.DataFrame(rows)
    
    if sort_by_impact and not df.empty:
        df["impact_abs"] = df["impact"].abs()
        df = df.sort_values("impact_abs", ascending=False)
        df = df.drop(columns=["impact_abs"])
        df = df.reset_index(drop=True)
    
    logger.debug(
        "Converted Phase 3 SensitivitySuite to DataFrame: %d rows",
        len(df),
    )
    
    return df


def _v14_suite_to_dataframe(
    suite: Any,  # v14 SensitivitySuite
    *,
    sort_by_impact: bool = True,
) -> pd.DataFrame:
    """Convert v14 SensitivitySuite to DataFrame.
    
    Duck-typed conversion for v14 contracts.
    """
    rows: List[Dict[str, Any]] = []
    
    for tornado_result in suite.tornado_results:
        # v14 TornadoResult has different structure
        rows.append({
            "variable": tornado_result.variable,
            "label": tornado_result.label,
            "base_metric": tornado_result.base_metric,
            "low_metric": tornado_result.low_case_metric,
            "high_metric": tornado_result.high_case_metric,
            "impact": tornado_result.impact_abs,
            "direction": "positive" if tornado_result.impact_dir > 0 else "negative",
            "sensitivity": 0.0,  # v14 doesn't have sensitivity field
        })
    
    df = pd.DataFrame(rows)
    
    if sort_by_impact and not df.empty:
        df = df.sort_values("impact", ascending=False)
        df = df.reset_index(drop=True)
    
    logger.debug(
        "Converted v14 SensitivitySuite to DataFrame: %d rows",
        len(df),
    )
    
    return df


# ═══════════════════════════════════════════════════════════════════════════
# Multi-Scenario Converters
# ═══════════════════════════════════════════════════════════════════════════


def multi_scenario_to_dataframe(
    suite: MultiScenarioSuite,
    metric: str,
) -> pd.DataFrame:
    """Convert MultiScenarioSuite to comparison DataFrame.
    
    Parameters
    ----------
    suite : MultiScenarioSuite
        Multi-scenario analysis results.
    metric : str
        Metric to compare (e.g., "project_irr", "equity_irr").
    
    Returns
    -------
    pd.DataFrame
        Comparison DataFrame with columns:
        - scenario: Scenario name
        - description: Scenario description
        - baseline: Baseline metric value
        - shocked: Shocked metric value
        - impact: Impact (shocked - baseline)
        - impact_pct: Impact as percentage
    
    Examples
    --------
    >>> df = multi_scenario_to_dataframe(suite, "project_irr")
    >>> df.to_excel("scenario_comparison.xlsx", index=False)
    """
    comparison = suite.to_comparison_dict(metric)
    
    rows = comparison["scenarios"]
    df = pd.DataFrame(rows)
    
    if not df.empty:
        df = df.sort_values("impact", ascending=True)  # Worst first
        df = df.reset_index(drop=True)
    
    logger.debug(
        "Converted MultiScenarioSuite to DataFrame: %d scenarios, metric=%s",
        len(df),
        metric,
    )
    
    return df


# ═══════════════════════════════════════════════════════════════════════════
# Preparation Helpers for Visualization Libraries
# ═══════════════════════════════════════════════════════════════════════════


def prepare_tornado_data(
    suite: TornadoSuite,
    *,
    top_n: Optional[int] = None,
) -> Dict[str, Any]:
    """Prepare tornado data for visualization libraries.
    
    Parameters
    ----------
    suite : TornadoSuite
        Sensitivity suite to visualize.
    top_n : int, optional
        Limit to top N drivers by impact.
    
    Returns
    -------
    Dict[str, Any]
        Dictionary with:
        - labels: List of variable labels
        - impacts: List of impacts
        - base_metric: Baseline metric value
        - metric_name: Metric name
    
    Examples
    --------
    >>> data = prepare_tornado_data(suite, top_n=10)
    >>> import plotly.graph_objects as go
    >>> fig = go.Figure(data=go.Bar(
    ...     y=data["labels"],
    ...     x=data["impacts"],
    ...     orientation='h',
    ... ))
    """
    df = to_tornado_dataframe(suite, sort_by_impact=True)
    
    if top_n is not None and len(df) > top_n:
        df = df.head(top_n)
    
    # Extract data for plotting
    labels = df["label"].tolist()
    impacts = df["impact"].tolist()
    
    # Get metadata
    base_metric = df["base_metric"].iloc[0] if not df.empty else 0.0
    
    # Infer metric name from suite
    if isinstance(suite, SensitivitySuite):
        metric_name = suite.metric_name
    elif hasattr(suite, "metric"):
        metric_name = suite.metric
    else:
        metric_name = "metric"
    
    return {
        "labels": labels,
        "impacts": impacts,
        "base_metric": base_metric,
        "metric_name": metric_name,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Visualization Stubs (Integration Points)
# ═══════════════════════════════════════════════════════════════════════════


def create_tornado_chart(
    suite: TornadoSuite,
    **kwargs: Any,
) -> Any:
    """Create tornado chart (stub).
    
    This is a stub for future integration with:
    - analytics/sensitivity_visualization.py (Plotly)
    - analytics/dashboard/ (Streamlit)
    
    Parameters
    ----------
    suite : TornadoSuite
        Sensitivity suite to visualize.
    **kwargs
        Plotting options (library-specific).
    
    Returns
    -------
    Any
        Plotly Figure, Matplotlib Axes, or similar.
    
    Raises
    ------
    NotImplementedError
        Always raised (stub function).
    
    Notes
    -----
    Use `to_tornado_dataframe()` and plot manually with your preferred library:
    
    >>> df = to_tornado_dataframe(suite)
    >>> import plotly.express as px
    >>> fig = px.bar(df, x="impact", y="label", orientation="h")
    >>> fig.show()
    """
    raise NotImplementedError(
        "create_tornado_chart is a stub. "
        "Use to_tornado_dataframe() and plot with Plotly/Matplotlib."
    )


__all__ = [
    "to_tornado_dataframe",
    "multi_scenario_to_dataframe",
    "prepare_tornado_data",
    "create_tornado_chart",
]
