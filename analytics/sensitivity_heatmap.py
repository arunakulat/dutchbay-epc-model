# analytics/sensitivity_heatmap.py

"""
Two-Way Sensitivity/Heatmap Analysis (v14+)
- Sweeps top two parameters and generates matrix/contour for dashboard/Excel
"""

from typing import Any

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
    Returns a DataFrame with index=param_x values, columns=param_y values, cells=metric.
    """
    x_vals = param_x.base_value * (
        1 + np.linspace(param_x.low_pct, param_x.high_pct, steps) / 100
    )
    y_vals = param_y.base_value * (
        1 + np.linspace(param_y.low_pct, param_y.high_pct, steps) / 100
    )
    res = np.zeros((steps, steps), dtype=float)
    for i, xv in enumerate(x_vals):
        for j, yv in enumerate(y_vals):
            overrides = {}
            overrides.update(_build_nested_override(param_x.variable_name, xv))
            overrides.update(_build_nested_override(param_y.variable_name, yv))
            kpis = evaluate_with_overrides(base_config_path, overrides)
            res[i, j] = kpis[metric]
    df = pd.DataFrame(res, index=np.round(x_vals, 4), columns=np.round(y_vals, 4))
    df.index.name = param_x.variable_name
    df.columns.name = param_y.variable_name
    return df


def plot_two_way_heatmap(
    df: pd.DataFrame,
    filename: str,
    title: str = "Two-Way Sensitivity Heatmap",
    cmap: str = "coolwarm",
):
    """Export heatmap and contour for Excel or slide deck."""
    fig, ax = plt.subplots(figsize=(8, 8))
    c = ax.pcolormesh(df.columns, df.index, df.values, shading="auto", cmap=cmap)
    fig.colorbar(c, ax=ax, label=df.index.name + "-" + df.columns.name)
    # Contour on top for IRR tiers
    CS = plt.contour(df.columns, df.index, df.values, colors="black", linewidths=0.8)
    plt.clabel(CS, inline=True, fmt="%.2f", fontsize=9)
    ax.set_xlabel(df.columns.name)
    ax.set_ylabel(df.index.name)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(filename, bbox_inches="tight", dpi=160)
    plt.close(fig)


def _build_nested_override(variable_name: str, value: Any) -> dict:
    keys = variable_name.split(".")
    d = value
    for key in reversed(keys):
        d = {key: d}
    return d
