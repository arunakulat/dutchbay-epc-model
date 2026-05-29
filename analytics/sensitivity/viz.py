from __future__ import annotations

"""
analytics.sensitivity.viz

Visualization helpers for sensitivity outputs.

Import-safe policy:
- This module must NOT be imported by engine by default.
- It may import matplotlib lazily inside functions.

Placeholder:
- Provides tiny plot helpers that accept tables/records and return fig objects.
"""

from typing import Any, Mapping, Optional, Sequence, Union


def plot_tornado(
    *,
    table: Any,
    title: str = "Tornado",
) -> Any:
    """
    Plot a tornado chart from a sensitivity results table.

    table: typically a pandas DataFrame from analytics.sensitivity.export.suite_to_tables()["tornado_rows"]
    Returns a matplotlib Figure.
    """
    import matplotlib.pyplot as plt  # lazy import
    import numpy as np

    if table is None or (hasattr(table, "empty") and table.empty):
        fig, ax = plt.subplots()
        ax.set_title(title)
        ax.text(0.5, 0.5, "No data available", ha="center", va="center")
        return fig

    df = table.copy()
    if "impact_abs" in df.columns:
        df = df.sort_values("impact_abs", ascending=True)

    labels = df["label"].tolist()
    lows = df["low_value"].tolist()
    highs = df["high_value"].tolist()
    base_val = df["base_value"].iloc[0] if "base_value" in df.columns and not df.empty else 0.0

    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.6)))
    y_pos = np.arange(len(labels))

    for i, (l, h) in enumerate(zip(lows, highs)):
        ax.barh(y_pos[i], abs(h - l), left=min(l, h), color="skyblue", edgecolor="black", alpha=0.8)

    ax.axvline(base_val, color="red", linestyle="--", linewidth=1.5, label=f"Base ({base_val:.4f})")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_title(title)
    ax.legend()
    plt.tight_layout()
    return fig


def plot_heatmap_matrix(
    *,
    heatmap: Mapping[str, Any],
    title: str = "Sensitivity Heatmap",
) -> Any:
    """
    Plot a heatmap from heatmap dict produced by analytics.sensitivity.heatmap.suite_to_heatmap_matrix().
    """
    import matplotlib.pyplot as plt  # lazy import
    import numpy as np  # safe

    values = np.array(heatmap.get("values", []), dtype=float)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_title(title)

    if values.size == 0:
        ax.text(0.5, 0.5, "Empty heatmap", ha="center", va="center", transform=ax.transAxes)
        return fig

    im = ax.imshow(values, aspect="auto")
    fig.colorbar(im, ax=ax)
    ax.set_xlabel("Metric")
    ax.set_ylabel("Parameter/Case")
    return fig
