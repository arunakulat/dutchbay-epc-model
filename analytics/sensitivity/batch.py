"""
batch.py – Batch Heatmap Generator for Sensitivity Analysis (v14+)

PURPOSE:
    For a given scenario/param set, generates PNG heatmaps 
    for all param pairs. Useful for investigator/developer speed, 
    board or IC slide decks, and automated model validation.

USAGE:
    from analytics.sensitivity.batch import batch_heatmap_grid
    batch_heatmap_grid(config_path, params)

OUTPUT:
    Exports all heatmaps to "exports/heatmaps/" as PNG files 
    for inclusion in PowerPoint, docs, or dashboard.

EXAMPLE:
    batch_heatmap_grid("scenarios/basecase.yaml", params, steps=4)
"""

import os
from itertools import combinations

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity_heatmap import plot_two_way_heatmap, run_two_way_sensitivity


def batch_heatmap_grid(
    base_config_path: str,
    parameters: list[ParameterRangeConfig],
    metric: str = "project_irr",
    steps: int = 4,
    outdir: str = "exports/heatmaps/",
):
    """
    Loops over all parameter pairs, creates heatmap/contour plots as PNGs.
    Each file is named by driver variable names.
    """
    os.makedirs(outdir, exist_ok=True)
    for pa, pb in combinations(parameters, 2):
        df = run_two_way_sensitivity(
            base_config_path, pa, pb, metric=metric, steps=steps
        )
        fname = (
    f"{outdir}/{pa.variable_name.replace('.', '_')}_"
    f"{pb.variable_name.replace('.', '_')}.png"
)
        plot_two_way_heatmap(df, fname)
    print(f"Generated {len(list(combinations(parameters,2)))} heatmaps in {outdir}")
