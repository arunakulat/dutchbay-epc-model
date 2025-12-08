# analytics/sensitivity_pareto.py
"""
Pareto frontier optimization guided by sensitivity (v14+).

- Multi-objective (IRR / DSCR) grid search for feasible, efficient solutions.
- Uses the top tornado drivers from a SensitivitySuite.
"""

from __future__ import annotations

from itertools import product
from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd

from analytics.contracts_v14 import ParetoFrontierResult, SensitivitySuite
from analytics.evaluate_scenario import evaluate_with_overrides


def optimize_from_sensitivity_insights(
    sensitivity_suite: SensitivitySuite,
    base_config_path: str,
    objectives: Sequence[str] = ("project_irr", "dscr_min"),
    constraints: Dict[str, float] | None = None,
    steps: int = 6,
) -> ParetoFrontierResult:
    """
    Use top risk drivers from tornado to build a Pareto-efficient grid search.

    Returns all non-dominated solutions for IRR/DSCR given driver parameter ranges.

    Args:
        sensitivity_suite: Tornado / sensitivity results.
        base_config_path: Base YAML config to override.
        objectives: KPI names to optimize (maximization).
        constraints: Optional minimum thresholds for KPIs.
        steps: Number of discrete steps per driver over ±20%.
    """
    if constraints is None:
        constraints = {"project_irr": 0.12, "dscr_min": 1.30}

    # Take the top 3 drivers (or fewer if suite is smaller)
    params = [t.variable for t in sensitivity_suite.tornado_results[:3]]

    configs = _generate_param_grid(params, steps)
    results: List[Dict[str, float]] = []

    for cfg in configs:
        overrides: Dict[str, Any] = {}
        for k, v in cfg.items():
            overrides.update(_build_nested_override(k, v))

        kpis = evaluate_with_overrides(base_config_path, overrides)

        # Enforce constraints; skip dominated/invalid points early
        if any(
            kpis.get(obj, float("-inf")) < constraints.get(obj, float("-inf"))
            for obj in objectives
        ):
            continue

        row: Dict[str, float] = {obj: float(kpis[obj]) for obj in objectives}
        # Also keep the parameter multipliers themselves
        for name, multiplier in cfg.items():
            row[name] = float(multiplier)

        results.append(row)

    if not results:
        return ParetoFrontierResult(frontier_points=[], objectives=list(objectives))

    df = pd.DataFrame(results)
    mask = _is_nondominated(df[list(objectives)].values)

    frontier_points = df[mask].to_dict(orient="records")
    return ParetoFrontierResult(
        frontier_points=frontier_points, objectives=list(objectives)
    )


def _generate_param_grid(params: Sequence[str], steps: int) -> List[Dict[str, float]]:
    """
    Grid-search parameter combinations for up to 3 variables.

    Each parameter is represented as a multiplicative factor in [0.8, 1.2].
    """
    if not params:
        return []

    pct_range = np.linspace(-0.2, 0.2, steps)  # ±20%
    grid: List[Dict[str, float]] = []

    for vals in product(pct_range, repeat=len(params)):
        grid.append({k: 1.0 + v for k, v in zip(params, vals)})

    return grid


def _is_nondominated(points: np.ndarray) -> np.ndarray:
    """
    Efficiently check non-dominated Pareto points for 2+ objectives (maximization).

    Args:
        points: 2D array of shape (n_points, n_objectives).

    Returns:
        Boolean mask of length n_points indicating non-dominated points.
    """
    n = points.shape[0]
    mask = np.ones(n, dtype=bool)

    for i in range(n):
        if not mask[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            # j dominates i if j is >= i in all objectives and > in at least one
            if np.all(points[j] >= points[i]) and np.any(points[j] > points[i]):
                mask[i] = False
                break

    return mask


def _build_nested_override(variable_name: str, value: Any) -> Dict[str, Any]:
    """
    Build a nested override dict from a dotted variable name.

    Example:
        "project.tariff.lkr_per_kwh", 1.05
        -> {"project": {"tariff": {"lkr_per_kwh": 1.05}}}
    """
    keys = variable_name.split(".")
    d: Any = value
    for key in reversed(keys):
        d = {key: d}
    return d
