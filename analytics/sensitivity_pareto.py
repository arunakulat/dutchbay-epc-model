"""Legacy shim for Pareto optimization (v14+).

DO NOT add logic here.
Single source of truth: analytics.sensitivity.optimizer

This module exists solely for backward compatibility with code that imports:
  from analytics.sensitivity_pareto import optimize_from_sensitivity_insights

All implementation is in analytics/sensitivity/optimizer.py.

Migration Guide:
  OLD: from analytics.sensitivity_pareto import run_pareto_search
  NEW: from analytics.sensitivity.optimizer import run_pareto_search

Deprecation Timeline:
  - v14.5 (current): Shim active, no warnings
  - v15.0: Add DeprecationWarning
  - v16.0: Remove this file
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from analytics.sensitivity.optimizer import (
    ObjectiveSpec,
    ParameterGridSpec,
    ParetoResult,
    export_pareto_table,
    run_pareto_search,
)


def optimize_from_sensitivity_insights(
    *,
    base_config: Mapping[str, Any],
    objectives: Sequence[ObjectiveSpec],
    grid: Sequence[ParameterGridSpec],
    plan_kind: str = "grid",
    max_points: int = 5000,
    n_samples: int = 500,
    seed: int = 123,
) -> ParetoResult:
    """Legacy wrapper for run_pareto_search().
    
    This function exists for backward compatibility only.
    New code should use analytics.sensitivity.optimizer.run_pareto_search directly.
    
    Args:
        base_config: Base scenario configuration
        objectives: List of optimization objectives
        grid: Parameter grid specifications
        plan_kind: Sampling strategy ("grid" or "lhs")
        max_points: Maximum evaluation points
        n_samples: Number of samples for LHS
        seed: Random seed for reproducibility
        
    Returns:
        ParetoResult with frontier and all evaluated points
        
    Example:
        >>> from analytics.sensitivity_pareto import optimize_from_sensitivity_insights
        >>> result = optimize_from_sensitivity_insights(
        ...     base_config=config,
        ...     objectives=[ObjectiveSpec(metric="project_irr", direction="maximize")],
        ...     grid=[ParameterGridSpec(param="capex", values=[900, 1000, 1100])],
        ... )
    """
    return run_pareto_search(
        base_config=base_config,
        objectives=objectives,
        grid=grid,
        plan_kind=plan_kind,
        max_points=max_points,
        n_samples=n_samples,
        seed=seed,
    )


__all__ = [
    "ObjectiveSpec",
    "ParameterGridSpec",
    "ParetoResult",
    "run_pareto_search",
    "export_pareto_table",
    "optimize_from_sensitivity_insights",
]

# EOF - analytics/sensitivity_pareto.py (legacy shim)
