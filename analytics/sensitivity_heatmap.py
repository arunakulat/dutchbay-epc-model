# analytics/sensitivity_heatmap.py
"""
Two-way sensitivity / heatmap analysis (v14+).

Sweeps two parameters and generates:
- A metric matrix (as a DataFrame) for Excel / further processing.
- An optional heatmap + contour plot for dashboards / slide decks.
"""

from __future__ import annotations

from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.evaluate_scenario import evaluate_with_overrides


def run_two_way_sensitivity(
    base_config_path: str,
    param_x: ParameterRangeConfig,
    param_y: ParameterRangeConfig,
    metric: str = "project_irr",
    steps: int = 8,
) -> pd.DataFrame:
    """
    Compute a two-way sensitivity grid.

    Args:
        base_config_path: Path to base scenario configuration.
        param_x: Parameter swept along the DataFrame index.
        param_y: Parameter swept along the DataFrame columns.
        metric: KPI name to extract from evaluate_with_overrides.
        steps: Number of points between low_pct and high_pct for each param.

    Returns:
        DataFrame where:
            index   = param_x values,
            columns = param_y values,
            cells   = metric values.
    """
    x_vals = param_x.base_value * (
        1.0 + np.linspace(param_x.low_pct, param_x.high_pct, steps) / 100.0
    )
    y_vals = param_y.base_value * (
        1.0 + np.linspace(param_y.low_pct, param_y.high_pct, steps) / 100.0
    )

    res = np.zeros((steps, steps), dtype=float)

    for i, xv in enumerate(x_vals):
        for j, yv in enumerate(y_vals):
            overrides: Dict[str, Any] = {}
            overrides.update(_build_nested_override(param_x.variable_name, float(xv)))
            overrides.update(_build_nested_override(param_y.variable_name, float(yv)))
            kpis = evaluate_with_overrides(base_config_path, overrides)
            res[i, j] = float(kpis[metric])

    df = pd.DataFrame(res, index=np.round(x_vals, 4), columns=np.round(y_vals, 4))
    df.index.name = param_x.variable_name
    df.columns.name = param_y.variable_name
    return df


def plot_two_way_heatmap(
    df: pd.DataFrame,
    filename: str,
    title: str = "Two-Way Sensitivity Heatmap",
    cmap: str = "coolwarm",
) -> None:
    """
    Export a heatmap + contour plot for a two-way sensitivity grid.

    Args:
        df: DataFrame produced by run_two_way_sensitivity.
        filename: Output image path.
        title: Plot title.
        cmap: Matplotlib colormap name.
    """
    fig, ax = plt.subplots(figsize=(8, 8))

    x_vals = df.columns.to_numpy(dtype=float)
    y_vals = df.index.to_numpy(dtype=float)
    z_vals = df.to_numpy(dtype=float)

    mesh = ax.pcolormesh(x_vals, y_vals, z_vals, shading="auto", cmap=cmap)
    color_label = f"{df.index.name or ''}–{df.columns.name or ''}".strip("–")
    fig.colorbar(mesh, ax=ax, label=color_label)

    # Contours overlaid on the heatmap
    cs = ax.contour(x_vals, y_vals, z_vals, colors="black", linewidths=0.8)
    ax.clabel(cs, inline=True, fmt="%.2f", fontsize=9)

    ax.set_xlabel(str(df.columns.name))
    ax.set_ylabel(str(df.index.name))
    ax.set_title(title)

    fig.tight_layout()
    fig.savefig(filename, bbox_inches="tight", dpi=160)
    plt.close(fig)


def _build_nested_override(variable_name: str, value: Any) -> Dict[str, Any]:
    """
    Convert a dot-separated variable path and value into a nested dict override.

    Example:
        "project.tariff.lkr_per_kwh", 1.05
        -> {"project": {"tariff": {"lkr_per_kwh": 1.05}}}
    """
    keys = variable_name.split(".")
    d: Any = value
    for key in reversed(keys):
        d = {key: d}
    return d
