from __future__ import annotations

from typing import Any, Mapping

"""
analytics.sensitivity.viz

Visualization helpers for sensitivity outputs.
"""


def plot_tornado(
    *,
    table: Any,
    title: str = "Tornado Chart",
) -> Any:
    """
    Plots a tornado chart from a sensitivity results table.
    Expects columns: 'label', 'low_value', 'high_value', 'base_value'.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    # Ensure table is sorted by impact
    if hasattr(table, "copy"):
        df = table.copy()
    else:
        # Fallback for non-dataframe inputs
        return _placeholder_plot(title)

    if "impact" in df.columns:
        df["impact_abs"] = df["impact"].abs()
        df = df.sort_values("impact_abs", ascending=True)

    labels = df["label"].values
    lows = df["low_value"].values
    highs = df["high_value"].values
    base = df["base_value"].values[0] if len(df) > 0 else 0

    fig, ax = plt.subplots(figsize=(10, 6))

    # Calculate relative movements
    left_impacts = lows - base
    right_impacts = highs - base

    # Plot bars
    y_pos = np.arange(len(labels))
    ax.barh(
        y_pos, left_impacts, left=base, color="#ff9999", label="Low Case", height=0.6
    )
    ax.barh(
        y_pos, right_impacts, left=base, color="#66b3ff", label="High Case", height=0.6
    )

    # Styling
    ax.axvline(
        base, color="black", linestyle="--", alpha=0.7, label=f"Base Case ({base:.2f})"
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Value")
    ax.set_title(title, fontweight="bold", pad=20)
    ax.legend(loc="lower right")
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    plt.tight_layout()
    return fig


def _placeholder_plot(title: str):
    import matplotlib.pyplot as plt

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_title(title)
    ax.text(0.5, 0.5, "Data unavailable for plot", ha="center", va="center")
    return fig


def plot_heatmap_matrix(
    *,
    heatmap: Mapping[str, Any],
    title: str = "Sensitivity Heatmap",
) -> Any:
    """
    Plot a heatmap from heatmap dict.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    values = np.array(heatmap.get("values", []), dtype=float)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_title(title, fontweight="bold")

    if values.size == 0:
        ax.text(
            0.5, 0.5, "Empty heatmap", ha="center", va="center", transform=ax.transAxes
        )
        return fig

    im = ax.imshow(values, aspect="auto", cmap="RdYlGn")
    fig.colorbar(im, ax=ax)

    # Set labels if provided
    if "x_labels" in heatmap:
        ax.set_xticks(np.arange(len(heatmap["x_labels"])))
        ax.set_xticklabels(heatmap["x_labels"], rotation=45, ha="right")
    if "y_labels" in heatmap:
        ax.set_yticks(np.arange(len(heatmap["y_labels"])))
        ax.set_yticklabels(heatmap["y_labels"])

    plt.tight_layout()
    return fig
