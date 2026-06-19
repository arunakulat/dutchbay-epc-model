"""Parameter optimization facade over ``evaluate_with_overrides`` (#30).

A thin, generic optimizer: sweep one config parameter across a range, evaluate
the v14 pipeline at each point via :func:`analytics.evaluation_v14.evaluate_with_overrides`,
and return the value that maximizes (or minimizes) a target KPI subject to an
optional KPI constraint (e.g. *max equity IRR subject to min DSCR ≥ covenant*).

It composes the existing evaluation gateway — it does not reimplement any
finance logic — so it stays correct as the model evolves (CCCDIR / ARCH-04).

Example:
    >>> result = optimize_parameter(
    ...     "scenarios/dutchbay_lendercase_2025Q4.yaml",
    ...     param_path="Financing_Terms.debt_ratio",
    ...     objective_key="equity_irr", direction="max",
    ...     lower=0.45, upper=0.70, n_steps=11,
    ...     constraint_key="min_dscr", constraint_min=1.20,
    ... )
    >>> result.best.value          # gearing cap maximizing equity IRR within covenant

Context:
    Sprint 11 - Issue #30 (optimization_v14 using evaluate_with_overrides).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import numpy as np

from analytics.evaluation_v14 import evaluate_with_overrides

_DIRECTIONS = ("max", "min")

# Feasibility comparisons need a floating-point tolerance: the dual-DSCR debt
# sculpt pins the achieved DSCR *exactly* at the covenant target, so the
# constraint value lands at target +/- ~1e-15 rounding noise. A naked
# ``constraint < constraint_min`` then flips feasibility on that noise, marking
# covenant-grazing-but-compliant points infeasible at random. Treat a point as
# satisfying a bound when it does so within this tolerance (relative + absolute).
_FEASIBILITY_ABS_TOL = 1e-9
_FEASIBILITY_REL_TOL = 1e-9


def _bound_slack(bound: float) -> float:
    """Absolute slack to allow at a constraint bound (scales with the bound)."""
    return max(_FEASIBILITY_ABS_TOL, _FEASIBILITY_REL_TOL * abs(bound))


@dataclass(frozen=True)
class OptimizationPoint:
    """One swept point: the parameter value and the resulting KPIs."""

    value: float
    objective: float
    constraint: Optional[float]
    feasible: bool


@dataclass(frozen=True)
class OptimizationResult:
    """Outcome of an optimization sweep."""

    param_path: str
    objective_key: str
    direction: str
    constraint_key: Optional[str]
    best: Optional[OptimizationPoint]
    curve: List[OptimizationPoint]


def optimize_parameter(
    config_path: str,
    *,
    param_path: str,
    objective_key: str,
    lower: float,
    upper: float,
    direction: str = "max",
    n_steps: int = 11,
    constraint_key: Optional[str] = None,
    constraint_min: Optional[float] = None,
    constraint_max: Optional[float] = None,
    base_overrides: Optional[Mapping[str, Any]] = None,
) -> OptimizationResult:
    """Sweep ``param_path`` and optimize ``objective_key`` under a KPI constraint.

    Args:
        config_path: Path to the v14 scenario config.
        param_path: Dotted config path to sweep (e.g. ``Financing_Terms.debt_ratio``).
        objective_key: KPI key to optimize (e.g. ``equity_irr``).
        lower, upper: Inclusive sweep bounds for the parameter.
        direction: ``"max"`` or ``"min"``.
        n_steps: Number of points across ``[lower, upper]`` (>= 2).
        constraint_key: Optional KPI key to constrain (e.g. ``min_dscr``).
        constraint_min, constraint_max: Inclusive bounds for the constraint KPI.
        base_overrides: Extra dotted overrides applied at every point.

    Returns:
        An :class:`OptimizationResult` with the full ``curve`` and the best
        feasible point (``best`` is ``None`` if no point is feasible).

    Raises:
        ValueError: If ``direction`` is invalid or ``n_steps`` < 2.
    """
    if direction not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}, got {direction!r}")
    if n_steps < 2:
        raise ValueError(f"n_steps must be >= 2, got {n_steps}")

    base: Dict[str, Any] = dict(base_overrides or {})
    curve: List[OptimizationPoint] = []

    for value in np.linspace(lower, upper, n_steps):
        overrides = dict(base)
        overrides[param_path] = float(value)
        kpis = evaluate_with_overrides(config_path, overrides=overrides)

        objective = float(kpis[objective_key])
        constraint: Optional[float] = None
        feasible = True
        if constraint_key is not None:
            constraint = float(kpis[constraint_key])
            if (
                constraint_min is not None
                and constraint < constraint_min - _bound_slack(constraint_min)
            ):
                feasible = False
            if (
                constraint_max is not None
                and constraint > constraint_max + _bound_slack(constraint_max)
            ):
                feasible = False

        curve.append(
            OptimizationPoint(
                value=float(value),
                objective=objective,
                constraint=constraint,
                feasible=feasible,
            )
        )

    feasible_points = [p for p in curve if p.feasible]
    best: Optional[OptimizationPoint] = None
    if feasible_points:
        best = (
            max(feasible_points, key=lambda p: p.objective)
            if direction == "max"
            else min(feasible_points, key=lambda p: p.objective)
        )

    return OptimizationResult(
        param_path=param_path,
        objective_key=objective_key,
        direction=direction,
        constraint_key=constraint_key,
        best=best,
        curve=curve,
    )


__all__ = [
    "OptimizationPoint",
    "OptimizationResult",
    "optimize_parameter",
]
