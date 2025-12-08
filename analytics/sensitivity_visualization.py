# analytics/sensitivity_visualization.py

"""
Sensitivity visualization routines (tornado, spider) – v14+.

Publication-quality, DFI-friendly; Matplotlib-compatible.
"""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analytics.contracts_v14 import MultiMetricSensitivitySuite, SensitivitySuite
from analytics.sensitivity_export import (
    multi_metric_suite_to_dataframe,
    tornado_suite_to_dataframe,
)


def plot_tornado_chart(
    suite: SensitivitySuite,
    top_n: int = 10,
    filename: Optional[str] = None,
    title: Optional[str] = None,
) -> None:
    """
    Plot a single-metric tornado chart.

    Args:
        suite: SensitivitySuite containing tornado_results.
        top_n: Number of top drivers to plot.
        filename: Optional path to save the figure.
        title: Optional plot title.
    """
    df = tornado_suite_to_dataframe(suite)
    if df.empty:
        return

    df = df.head(top_n)

    params = df["Variable"]
    low = df["Low"]
    base = df["Base"]
    high = df["High"]

    fig, ax = plt.subplots(figsize=(10, 0.6 * len(df) + 2))

    for i, (b, low_val, high_val) in enumerate(zip(base, low, high)):
        # Low bar (from Low to Base)
        ax.barh(
            i,
            b - low_val,
            left=low_val,
            color="#d35400",
            height=0.5,
            label="Low" if i == 0 else "",
        )
        # High bar (from Base to High)
        ax.barh(
            i,
            high_val - b,
            left=b,
            color="#2980b9",
            height=0.5,
            label="High" if i == 0 else "",
        )

    # Base reference line
    ax.axvline(float(base.iloc[0]), color="black", lw=1, linestyle="--", label="Base")

    ax.set_yticks(range(len(params)))
    ax.set_yticklabels(params)
    ax.set_title(title or f"Tornado Chart: Top {top_n} Sensitivities")
    ax.set_xlabel("Metric value (e.g. project IRR %)")
    ax.legend(frameon=False)

    fig.tight_layout()
    if filename:
        fig.savefig(filename, bbox_inches="tight", dpi=160)
    plt.close(fig)


def plot_spider_chart(
    suite: MultiMetricSensitivitySuite,
    top_n: int = 6,
    filename: Optional[str] = None,
    title: Optional[str] = None,
) -> None:
    """
    Plot a multi-metric radar (spider) chart.

    Args:
        suite: MultiMetricSensitivitySuite with multi-metric tornado results.
        top_n: Number of parameters to show.
        filename: Optional path to save the figure.
        title: Optional plot title.
    """
    metrics = list(suite.metrics)
    if not metrics:
        return

    df = multi_metric_suite_to_dataframe(suite)
    if df.empty:
        return

    # Aggregate per parameter by first metric's impact, then pick top_n
    first_metric = metrics[0]
    impact_col = "Impact"
    df_first = df[df["Metric"] == first_metric].sort_values(impact_col, ascending=False)
    top_params = df_first["Variable"].head(top_n).tolist()

    df_top = df[df["Variable"].isin(top_params)]

    # Build a matrix: rows = parameters, cols = metrics, values = Impact
    pivot = (
        df_top.pivot_table(
            index="Variable",
            columns="Metric",
            values="Impact",
            aggfunc="mean",
        )
        .reindex(index=top_params)
        .fillna(0.0)
    )

    angles = [n / float(len(metrics)) * 2.0 * np.pi for n in range(len(metrics))]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})

    for param in pivot.index:
        vals = pivot.loc[param, metrics].values.tolist()
        vals += vals[:1]
        ax.plot(angles, vals, linewidth=2, label=param)
        ax.fill(angles, vals, alpha=0.1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics)
    ax.set_title(title or f"Multi-Metric Sensitivity (Top {top_n})")
    ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1.0))
    fig.tight_layout()

    if filename:
        fig.savefig(filename, bbox_inches="tight", dpi=160)
    plt.close(fig)
