# analytics/sensitivity_pareto.py

"""
Pareto Frontier Optimization Guided by Sensitivity (v14+)
* Multi-objective (IRR/DSCR) grid search for feasible, efficient solutions.
* Pluggable interfaces for DFI review, scenario planning, and tariff negotiation.
"""

from typing import Sequence, Dict, Any, Optional, Tuple
from analytics.contracts_v14 import SensitivitySuite, ParameterRangeConfig, ParetoFrontierResult
from analytics.evaluate_scenario import evaluate_with_overrides

def optimize_from_sensitivity_insights(
    sensitivity_suite: SensitivitySuite,
    base_config_path: str,
    objectives: Sequence[str] = ("project_irr", "dscr_min"),
    constraints: Dict[str, float] = {"project_irr": 0.12, "dscr_min": 1.3},
    steps: int = 6
) -> ParetoFrontierResult:
    """
    Use top risk drivers from tornado to build a Pareto-efficient grid search.
    Returns all non-dominated solutions for IRR/DSCR given driver parameter ranges.
    """
    params = [t.variable for t in sensitivity_suite.tornado_results[:3]]
    configs = _generate_param_grid(params, steps)
    results = []
    for cfg in configs:
        overrides = {}
        for k, v in cfg.items():
            overrides.update(_build_nested_override(k, v))
        kpis = evaluate_with_overrides(base_config_path, overrides)
        row = {obj: kpis[obj] for obj in objectives}
        row.update(cfg)
        results.append(row)
    # Non-dominated filtering
    df = pd.DataFrame(results)
    mask = _is_nondominated(df[objectives].values)
    return ParetoFrontierResult(
        frontier_points=df[mask].to_dict(orient="records"),
        objectives=list(objectives)
    )

def _generate_param_grid(params, steps):
    """Grid-search parameter combinations for up to 3 variables."""
    from itertools import product
    grid = []
    pct_range = np.linspace(-0.2, 0.2, steps)  # ±20%
    keys = params
    for vals in product(pct_range, repeat=len(params)):
        grid.append({k: 1 + v for k, v in zip(keys, vals)})
    return grid

def _is_nondominated(points):
    """Efficiently checks non-dominated Pareto points."""
    # For 2 objectives (max IRR, max DSCR)
    n = len(points)
    mask = np.ones(n, dtype=bool)
    for i in range(n):
        for j in range(n):
            if all(points[j] >= points[i]) and any(points[j] > points[i]):
                mask[i] = False
                break
    return mask

def _build_nested_override(variable_name: str, value: Any) -> dict:
    keys = variable_name.split(".")
    d = value
    for key in reversed(keys):
        d = {key: d}
    return d

