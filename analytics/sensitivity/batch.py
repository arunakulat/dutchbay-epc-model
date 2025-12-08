"""
batch.py – Batch Heatmap Generator for Sensitivity Analysis (v14+)

PURPOSE:
    For a given scenario/param set, generates PNG heatmaps
    for all param pairs. Useful for investigator/developer speed,
    board or IC slide decks, and automated model validation.

USAGE:
    from analytics.sensitivity.batch import batch_heatmap_grid
    paths = batch_heatmap_grid(config_path, params)

OUTPUT:
    Exports all heatmaps to "exports/heatmaps/" as PNG files.
"""

from __future__ import annotations

import os
from itertools import combinations
from pathlib import Path
from typing import List

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity_heatmap import plot_two_way_heatmap, run_two_way_sensitivity


def batch_heatmap_grid(
    base_config_path: str,
    parameters: list[ParameterRangeConfig],
    metric: str = "project_irr",
    steps: int = 4,
    outdir: str = "exports/heatmaps/",
) -> List[Path]:
    """
    Generate heatmap/contour plots for all parameter pairs.

    Args:
        base_config_path: Path to base scenario configuration.
        parameters: List of driver parameter configs.
        metric: KPI name for heatmap values.
        steps: Grid resolution per parameter.
        outdir: Directory to write PNG files to.

    Returns:
        List of generated heatmap file paths.
    """
    os.makedirs(outdir, exist_ok=True)
    out_paths: List[Path] = []

    for pa, pb in combinations(parameters, 2):
        df = run_two_way_sensitivity(
            base_config_path, pa, pb, metric=metric, steps=steps
        )
        fname = (
            f"{pa.variable_name.replace('.', '_')}_"
            f"{pb.variable_name.replace('.', '_')}.png"
        )
        path = Path(outdir) / fname
        plot_two_way_heatmap(df, str(path))
        out_paths.append(path)

    return out_paths
