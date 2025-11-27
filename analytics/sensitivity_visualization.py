# analytics/sensitivity_visualization.py

"""
Sensitivity Visualization Routines (tornado, spider, heatmap) – v14+
Publication-quality, DFI-friendly; fully Matplotlib/Plotly compatible
"""

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analytics.contracts_v14 import MultiMetricSensitivitySuite, SensitivitySuite


def plot_tornado_chart(
    suite: SensitivitySuite,
    top_n: int = 10,
    filename: Optional[str] = None,
    title: Optional[str] = None,
) -> None:
    """Bar chart: impact sorted, DFI style, Excel/board ready."""
    df = pd.DataFrame(
        [
            {
                "Parameter": t.label,
                "Low": t.low_metric,
                "Base": t.base_metric,
                "High": t.high_metric,
            }
            for t in suite.tornado_results[:top_n]
        ]
    )
    y = df["Parameter"]
    low, base, high = df["Low"], df["Base"], df["High"]
    [base - low_val for low_val in low]
    [h - base for h in high]
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(df) + 2))
    for i, (b, low_val, h) in enumerate(zip(base, low, high)):
        ax.barh(
            i, b - l, left=l, color="#d35400", height=0.5, label="Low" if i == 0 else ""
        )
        ax.barh(
            i,
            h - b,
            left=b,
            color="#2980b9",
            height=0.5,
            label="High" if i == 0 else "",
        )
    ax.axvline(base.iloc[0], color="black", lw=1, linestyle="--", label="Base")
    ax.set_yticks(range(len(y)))
    ax.set_yticklabels(y)
    ax.set_title(title or f"Tornado Chart: Top {top_n} Sensitivities")
    ax.set_xlabel("Metric Value (e.g. Project IRR %)")
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
    """Radar/spider: K metrics × N parameters."""

    import matplotlib.pyplot as plt

    metrics = suite.metrics
    df = multi_metric_suite_to_dataframe(suite).sort_values(
        f"Impact_{metrics[0]}", ascending=False
    )[:top_n]
    angles = [n / float(len(metrics)) * 2 * np.pi for n in range(len(metrics))]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    for idx, row in df.iterrows():
        vals = [row[f"Impact_{m}"] for m in metrics] + [row[f"Impact_{metrics[0]}"]]
        ax.plot(angles, vals, linewidth=2, label=row["Parameter"])
        ax.fill(angles, vals, alpha=0.1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics)
    ax.set_title(title or f"Multi-Metric Sensitivity (Top {top_n})")
    ax.legend(loc="upper right", bbox_to_anchor=(1.45, 1))
    fig.tight_layout()
    if filename:
        fig.savefig(filename, bbox_inches="tight", dpi=160)
    plt.close(fig)
