# ruff: noqa: E402
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

from typing import Any, Mapping


def plot_tornado(
    *,
    table: Any,
    title: str = "Tornado",
) -> Any:
    """
    Minimal tornado plot helper.

    table: typically a pandas DataFrame from analytics.sensitivity.export.suite_to_tables()["tornado_rows"]
    Returns a matplotlib Figure.

    NOTE: This is a placeholder. Implement real plotting once core surfaces are stable.
    """
    import matplotlib.pyplot as plt  # lazy import

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_title(title)
    ax.set_xlabel("Value")
    ax.set_ylabel("Case")
    ax.text(0.5, 0.5, "Tornado plot placeholder", ha="center", va="center", transform=ax.transAxes)
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
