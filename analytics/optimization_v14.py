"""Parameter optimization facade over ``evaluate_with_overrides`` (#30, #602).

A thin, generic optimizer: optimize one config parameter over ``[lower, upper]``,
evaluate the v14 pipeline at each candidate via
:func:`analytics.evaluation_v14.evaluate_with_overrides`, and return the value
that maximizes (or minimizes) a target KPI subject to an optional KPI
constraint (e.g. *max equity IRR subject to min DSCR >= covenant*).

Two search methods are available via ``method=``:

* ``"grid"`` (default) — the original exhaustive ``np.linspace`` sweep of
  ``n_steps`` points across ``[lower, upper]``. Behavior is unchanged from the
  original #30 implementation; ``curve`` is the full uniform grid in sweep
  order.
* ``"bounded"`` (opt-in, #602) — SciPy's bounded scalar minimizer
  (:func:`scipy.optimize.minimize_scalar` with ``method="bounded"``), which
  refines a continuum optimum inside ``(lower, upper)`` with far fewer
  pipeline evaluations than a fine grid. Constraint-infeasible evaluations
  (per the same ``_bound_slack`` tolerance the grid path uses) and non-finite
  objectives are penalized with a large finite value so the search is steered
  back into the feasible region; the converged point is then re-checked, and
  ``best`` is ``None`` if the solver converged on a penalized point. The
  search is deterministic (Brent/golden-section, no randomness); ``curve``
  holds every evaluated point in evaluation order, not a uniform grid.
  Caveat: the DSCR-sculpt feasibility region has non-convex kinks, so the
  bounded method — like any local scalar minimizer — can converge to a local
  optimum; cross-check against a coarse grid when the objective landscape is
  unknown.

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
    Issue #602 (opt-in ``method="bounded"`` scalar refinement).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
from scipy.optimize import minimize_scalar

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.infeasibility_diagnostics import (
    InfeasibilityDiagnostics,
    OptimizationAuditLog,
    build_parameter_diagnostics,
)

_DIRECTIONS = ("max", "min")
_METHODS = ("grid", "bounded")

# Feasibility comparisons need a floating-point tolerance: the dual-DSCR debt
# sculpt pins the achieved DSCR *exactly* at the covenant target, so the
# constraint value lands at target +/- ~1e-15 rounding noise. A naked
# ``constraint < constraint_min`` then flips feasibility on that noise, marking
# covenant-grazing-but-compliant points infeasible at random. Treat a point as
# satisfying a bound when it does so within this tolerance (relative + absolute).
_FEASIBILITY_ABS_TOL = 1e-9
_FEASIBILITY_REL_TOL = 1e-9

# Penalty the bounded scalar minimizer sees for constraint-infeasible (or
# non-finite-objective) evaluations. Large enough to dwarf any real KPI
# magnitude (IRRs are O(1), NPVs are O(1e8) USD) yet finite, so the Brent
# search stays numerically well-behaved and is steered back into the feasible
# region instead of silently converging on a covenant-breaching point.
_BOUNDED_INFEASIBLE_PENALTY = 1e18


def _bound_slack(bound: float) -> float:
    """Absolute slack to allow at a constraint bound (scales with the bound)."""
    return max(_FEASIBILITY_ABS_TOL, _FEASIBILITY_REL_TOL * abs(bound))


@dataclass(frozen=True)
class OptimizationPoint:
    """One evaluated point: the parameter value and the resulting KPIs."""

    value: float
    objective: float
    constraint: Optional[float]
    feasible: bool


@dataclass(frozen=True)
class OptimizationResult:
    """Outcome of an optimization run.

    ``diagnostics`` / ``audit_log`` (#741) are populated ONLY when the search
    found no feasible optimum (``best is None``): the structured why-infeasible
    register (which bound the constrained KPI could not clear, and by how much)
    and a lightweight audit trail (method, evaluations, iterations, final
    status). When ``best`` is not ``None`` BOTH stay ``None`` — a successful
    solve's numeric result is byte-identical to before #741.
    """

    param_path: str
    objective_key: str
    direction: str
    constraint_key: Optional[str]
    best: Optional[OptimizationPoint]
    curve: List[OptimizationPoint]
    diagnostics: Optional[InfeasibilityDiagnostics] = None
    audit_log: Optional[OptimizationAuditLog] = None


def _build_failure_records(
    *,
    method: str,
    curve: List[OptimizationPoint],
    constraint_key: Optional[str],
    constraint_min: Optional[float],
    constraint_max: Optional[float],
    iterations: int,
) -> tuple[InfeasibilityDiagnostics, OptimizationAuditLog]:
    """Diagnostics + audit log for a no-feasible-optimum search (#741).

    Called ONLY when ``best is None``. A successful solve never invokes this and
    carries ``(None, None)`` so its result is byte-identical to before #741.
    """
    diagnostics = build_parameter_diagnostics(
        curve,
        constraint_key=constraint_key,
        constraint_min=constraint_min,
        constraint_max=constraint_max,
    )
    audit = OptimizationAuditLog(
        method=method,
        evaluations=len(curve),
        iterations=iterations,
        final_status="infeasible",
        binding_constraints=tuple(v.key for v in diagnostics.violations),
        best_objective=None,
    )
    return diagnostics, audit


def _evaluate_point(
    config_path: str,
    *,
    param_path: str,
    value: float,
    objective_key: str,
    constraint_key: Optional[str],
    constraint_min: Optional[float],
    constraint_max: Optional[float],
    base: Mapping[str, Any],
) -> OptimizationPoint:
    """Evaluate the pipeline at one parameter value and apply the constraint.

    Shared by the grid and bounded paths so both use the identical
    ``evaluate_with_overrides`` gateway call and the identical
    ``_bound_slack`` feasibility tolerance.

    Args:
        config_path: Path to the v14 scenario config.
        param_path: Dotted config path being optimized.
        value: Parameter value to evaluate.
        objective_key: KPI key to read as the objective.
        constraint_key: Optional KPI key to constrain.
        constraint_min, constraint_max: Inclusive bounds for the constraint KPI.
        base: Extra dotted overrides applied at every point.

    Returns:
        The evaluated :class:`OptimizationPoint` (``feasible`` reflects the
        constraint bounds within ``_bound_slack`` tolerance).
    """
    overrides = dict(base)
    overrides[param_path] = float(value)
    kpis = evaluate_with_overrides(config_path, overrides=overrides)

    objective = float(kpis[objective_key])
    constraint: Optional[float] = None
    feasible = True
    if constraint_key is not None:
        constraint = float(kpis[constraint_key])
        if constraint_min is not None and constraint < constraint_min - _bound_slack(
            constraint_min
        ):
            feasible = False
        if constraint_max is not None and constraint > constraint_max + _bound_slack(
            constraint_max
        ):
            feasible = False

    return OptimizationPoint(
        value=float(value),
        objective=objective,
        constraint=constraint,
        feasible=feasible,
    )


def _optimize_bounded(
    config_path: str,
    *,
    param_path: str,
    objective_key: str,
    lower: float,
    upper: float,
    direction: str,
    constraint_key: Optional[str],
    constraint_min: Optional[float],
    constraint_max: Optional[float],
    base: Mapping[str, Any],
    xatol: float,
    maxiter: int,
) -> OptimizationResult:
    """Refine the constrained optimum with SciPy's bounded scalar minimizer.

    Wraps the objective as a penalized scalar function (sign-folded so both
    directions minimize; infeasible or non-finite evaluations return
    ``_BOUNDED_INFEASIBLE_PENALTY``) and runs
    ``minimize_scalar(method="bounded", bounds=(lower, upper))``. Every
    pipeline evaluation is recorded in ``curve`` in evaluation order.

    Args:
        config_path: Path to the v14 scenario config.
        param_path: Dotted config path to optimize.
        objective_key: KPI key to optimize.
        lower, upper: Finite bracket with ``lower < upper``.
        direction: ``"max"`` or ``"min"`` (validated by the caller).
        constraint_key: Optional KPI key to constrain.
        constraint_min, constraint_max: Inclusive bounds for the constraint KPI.
        base: Extra dotted overrides applied at every point.
        xatol: Absolute convergence tolerance on the parameter (> 0).
        maxiter: Maximum number of solver iterations (>= 1).

    Returns:
        An :class:`OptimizationResult`; ``best`` is ``None`` if the converged
        point is infeasible (equivalently: no evaluated point was feasible
        with a finite objective, since any such point beats the penalty).

    Raises:
        ValueError: If the bracket is non-finite or inverted, or
            ``xatol``/``maxiter`` are invalid.
        RuntimeError: If the solver does not converge within ``maxiter``
            iterations (fail-loud; no silently degraded answer).
    """
    if not (math.isfinite(lower) and math.isfinite(upper)):
        raise ValueError(
            f"method='bounded' requires a finite bracket, got ({lower!r}, {upper!r})"
        )
    if not lower < upper:
        raise ValueError(
            f"method='bounded' requires lower < upper, got ({lower!r}, {upper!r})"
        )
    if not (math.isfinite(xatol) and xatol > 0.0):
        raise ValueError(f"bounded_xatol must be finite and > 0, got {xatol!r}")
    if maxiter < 1:
        raise ValueError(f"bounded_maxiter must be >= 1, got {maxiter}")

    curve: List[OptimizationPoint] = []
    cache: Dict[float, OptimizationPoint] = {}

    def _eval_at(value: float) -> OptimizationPoint:
        key = float(value)
        cached = cache.get(key)
        if cached is not None:
            return cached
        point = _evaluate_point(
            config_path,
            param_path=param_path,
            value=key,
            objective_key=objective_key,
            constraint_key=constraint_key,
            constraint_min=constraint_min,
            constraint_max=constraint_max,
            base=base,
        )
        cache[key] = point
        curve.append(point)
        return point

    sign = -1.0 if direction == "max" else 1.0

    def _penalized(value: float) -> float:
        point = _eval_at(float(value))
        if not point.feasible or not math.isfinite(point.objective):
            return _BOUNDED_INFEASIBLE_PENALTY
        return sign * point.objective

    solver = minimize_scalar(
        _penalized,
        bounds=(lower, upper),
        method="bounded",
        options={"xatol": xatol, "maxiter": maxiter},
    )
    if not bool(solver.success):
        raise RuntimeError(
            "method='bounded' did not converge within "
            f"maxiter={maxiter}: {solver.message!s}"
        )

    # Re-check the converged point for feasibility (never silently return an
    # infeasible best). The solver returns an already-evaluated x, so this is
    # a cache hit, not an extra pipeline evaluation.
    candidate = _eval_at(float(solver.x))
    best: Optional[OptimizationPoint] = None
    if candidate.feasible and math.isfinite(candidate.objective):
        best = candidate

    diagnostics: Optional[InfeasibilityDiagnostics] = None
    audit_log: Optional[OptimizationAuditLog] = None
    if best is None:
        # Prefer the solver's own iteration count; fall back to the evaluation
        # count when SciPy does not report one.
        solver_nit = getattr(solver, "nit", None)
        iterations = int(solver_nit) if solver_nit is not None else len(curve)
        diagnostics, audit_log = _build_failure_records(
            method="bounded",
            curve=curve,
            constraint_key=constraint_key,
            constraint_min=constraint_min,
            constraint_max=constraint_max,
            iterations=iterations,
        )

    return OptimizationResult(
        param_path=param_path,
        objective_key=objective_key,
        direction=direction,
        constraint_key=constraint_key,
        best=best,
        curve=curve,
        diagnostics=diagnostics,
        audit_log=audit_log,
    )


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
    method: str = "grid",
    bounded_xatol: float = 1e-5,
    bounded_maxiter: int = 500,
) -> OptimizationResult:
    """Optimize ``objective_key`` over ``param_path`` under a KPI constraint.

    Args:
        config_path: Path to the v14 scenario config.
        param_path: Dotted config path to optimize (e.g.
            ``Financing_Terms.debt_ratio``).
        objective_key: KPI key to optimize (e.g. ``equity_irr``).
        lower, upper: Inclusive bounds for the parameter. The bounded method
            additionally requires a finite bracket with ``lower < upper``.
        direction: ``"max"`` or ``"min"``.
        n_steps: Number of grid points across ``[lower, upper]`` (>= 2).
            Grid method only; ignored by ``method="bounded"``.
        constraint_key: Optional KPI key to constrain (e.g. ``min_dscr``).
        constraint_min, constraint_max: Inclusive bounds for the constraint KPI.
        base_overrides: Extra dotted overrides applied at every point.
        method: ``"grid"`` (default, exhaustive sweep — unchanged legacy
            behavior) or ``"bounded"`` (opt-in SciPy bounded scalar
            refinement, #602).
        bounded_xatol: Bounded method only — absolute convergence tolerance
            on the parameter (> 0). Default matches SciPy's ``1e-5``.
        bounded_maxiter: Bounded method only — maximum solver iterations
            (>= 1). Default matches SciPy's ``500``.

    Returns:
        An :class:`OptimizationResult` with the evaluated ``curve`` (the full
        uniform grid for ``"grid"``; the evaluation trace for ``"bounded"``)
        and the best feasible point (``best`` is ``None`` if no feasible
        optimum was found).

    Raises:
        ValueError: If ``direction`` or ``method`` is invalid, if ``n_steps``
            < 2 (grid), or if the bounded bracket/options are invalid.
        RuntimeError: If the bounded solver does not converge within
            ``bounded_maxiter`` iterations.
    """
    if direction not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}, got {direction!r}")
    if method not in _METHODS:
        raise ValueError(f"method must be one of {_METHODS}, got {method!r}")

    base: Dict[str, Any] = dict(base_overrides or {})

    if method == "bounded":
        return _optimize_bounded(
            config_path,
            param_path=param_path,
            objective_key=objective_key,
            lower=lower,
            upper=upper,
            direction=direction,
            constraint_key=constraint_key,
            constraint_min=constraint_min,
            constraint_max=constraint_max,
            base=base,
            xatol=bounded_xatol,
            maxiter=bounded_maxiter,
        )

    if n_steps < 2:
        raise ValueError(f"n_steps must be >= 2, got {n_steps}")

    curve: List[OptimizationPoint] = []
    for value in np.linspace(lower, upper, n_steps):
        curve.append(
            _evaluate_point(
                config_path,
                param_path=param_path,
                value=float(value),
                objective_key=objective_key,
                constraint_key=constraint_key,
                constraint_min=constraint_min,
                constraint_max=constraint_max,
                base=base,
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

    diagnostics: Optional[InfeasibilityDiagnostics] = None
    audit_log: Optional[OptimizationAuditLog] = None
    if best is None:
        diagnostics, audit_log = _build_failure_records(
            method="grid",
            curve=curve,
            constraint_key=constraint_key,
            constraint_min=constraint_min,
            constraint_max=constraint_max,
            iterations=len(curve),
        )

    return OptimizationResult(
        param_path=param_path,
        objective_key=objective_key,
        direction=direction,
        constraint_key=constraint_key,
        best=best,
        curve=curve,
        diagnostics=diagnostics,
        audit_log=audit_log,
    )


__all__ = [
    "OptimizationPoint",
    "OptimizationResult",
    "optimize_parameter",
]
