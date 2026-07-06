"""Structured infeasibility diagnostics + optimization audit log (#741).

When a debt-sizing / capital-structure optimizer search finds NO feasible
candidate, a bare ``feasible=False`` + one-line ``infeasible_reason`` (the
minimal #740 surface) tells a lender *that* the covenants could not be met but
not *which* covenant bound bound the search, *by how much*, or *how hard the
optimizer looked*. This module enriches ONLY that failure path with:

* :class:`ConstraintViolation` — per-covenant, WHICH bound (min/max) was
  violated, the ``required`` bound value, the closest ``achieved`` value any
  candidate reached, the signed ``shortfall`` (how far short/over), and whether
  the covenant was violated by *every* candidate (``never_satisfied``) or only
  some.
* :class:`InfeasibilityDiagnostics` — the roll-up: candidate counts, the ordered
  per-covenant violations, a human ``binding_summary``, and the objective range
  the search spanned.
* :class:`OptimizationAuditLog` — a lightweight audit trail of the solve:
  ``method``, ``evaluations`` / ``iterations``, ``final_status``, the
  ``binding_constraints``, and the ``best_objective`` reached (``None`` when
  infeasible).

Design (CCCDIR / KPI-NEUTRAL, #741):
    These types are populated ONLY on the infeasible / no-best failure path of
    the existing optimizers (``analytics.optimization_v14`` and
    ``analytics.capital_structure_optimizer_v14``). A *successful* solve never
    constructs any of them — the result carries ``diagnostics=None`` and its
    numeric path is byte-identical to before. Nothing here re-implements finance
    logic, reads no config, and is never wired into ``run_v14_pipeline``.

    All fields are JSON-safe scalars / strings / tuples so the whole object
    serializes cleanly via ``dataclasses.asdict`` (the CLI's serializer) or
    ``ContractMixin.model_dump`` — the same contract the #740 result surface
    already honors.

Context:
    Issue #741 (infeasibility diagnostics + optimization audit log); parent
    #622 §5a; follow-up to #740 (the debt-mix / capex-contingency optimizers).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    # Type-only imports (never executed at runtime → no import cycle): the
    # builders type-check against the real contract / optimizer point types,
    # but this module imports nothing from them at runtime, so
    # ``analytics.contracts_v14`` / ``analytics.optimization_v14`` can safely
    # import this module.
    from analytics.contracts_v14 import CapitalStructurePoint, CovenantConstraint
    from analytics.optimization_v14 import OptimizationPoint

__all__ = [
    "ConstraintViolation",
    "InfeasibilityDiagnostics",
    "OptimizationAuditLog",
    "build_capital_structure_diagnostics",
    "build_parameter_diagnostics",
    "audit_log_from_diagnostics",
]


# ---------------------------------------------------------------------------
# JSON-safe structured records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstraintViolation:
    """One covenant that could not be satisfied by the best candidate for it.

    ``bound_kind`` is ``"minimum"`` or ``"maximum"`` (the side that was
    breached). ``required`` is the covenant bound; ``achieved`` is the *closest*
    value any evaluated candidate reached toward that bound (the maximum KPI for
    a ``minimum`` bound, the minimum KPI for a ``maximum`` bound). ``shortfall``
    is the signed magnitude by which even that closest candidate misses
    (``required - achieved`` for a floor; ``achieved - required`` for a ceiling)
    — strictly positive when the bound is truly unreachable, ``<= 0`` when *some*
    candidate cleared this bound alone (it is only in the diagnostics because a
    different covenant bound it at that point). ``candidates_violating`` /
    ``candidates_total`` count how widely it bound; ``never_satisfied`` is
    ``True`` iff no candidate ever cleared this bound.
    """

    key: str
    bound_kind: str
    required: float
    achieved: float
    shortfall: float
    candidates_violating: int
    candidates_total: int
    never_satisfied: bool


@dataclass(frozen=True)
class InfeasibilityDiagnostics:
    """Structured why-infeasible register for a failed optimizer search.

    Populated ONLY when the search found no feasible candidate. ``violations``
    is ordered worst-shortfall-first so the tightest binding covenant is first.
    ``binding_summary`` is a one-line human reason (a superset of the #740
    ``infeasible_reason``). ``objective_range`` is the ``(min, max)`` objective
    span the search covered (``None`` if no finite objective was evaluated).
    """

    n_candidates: int
    n_feasible: int
    violations: Tuple[ConstraintViolation, ...] = ()
    binding_summary: str = ""
    objective_range: Optional[Tuple[float, float]] = None


@dataclass(frozen=True)
class OptimizationAuditLog:
    """Lightweight audit trail of an optimizer solve.

    ``method`` names the search ("grid", "bounded", "debt_mix",
    "capex_contingency"). ``evaluations`` is the number of scored candidates;
    ``iterations`` is the solver's own iteration count when it reports one (grid
    searches use the evaluation count). ``final_status`` is ``"feasible"`` or
    ``"infeasible"``. ``binding_constraints`` names the covenant key(s) that
    bound the search (empty when feasible). ``best_objective`` is the best
    feasible objective reached, or ``None`` when infeasible.
    """

    method: str
    evaluations: int
    iterations: int
    final_status: str
    binding_constraints: Tuple[str, ...] = ()
    best_objective: Optional[float] = None


# ---------------------------------------------------------------------------
# Builders — capital-structure optimizer (multi-covenant curve)
# ---------------------------------------------------------------------------


def _finite_objectives(objectives: Sequence[float]) -> List[float]:
    return [o for o in objectives if math.isfinite(o)]


def _objective_range(
    objectives: Sequence[float],
) -> Optional[Tuple[float, float]]:
    finite = _finite_objectives(objectives)
    if not finite:
        return None
    return (min(finite), max(finite))


def _violation_for_covenant(
    key: str,
    minimum: Optional[float],
    maximum: Optional[float],
    values: Sequence[float],
    n_violating: int,
    n_total: int,
) -> Optional[ConstraintViolation]:
    """Build the worst-side violation record for one covenant across the curve.

    ``values`` are that covenant's read-back KPI across every evaluated
    candidate. Returns ``None`` if the covenant has no evaluated values (it was
    never scored — nothing to diagnose).
    """
    finite = [v for v in values if math.isfinite(v)]
    if not finite:
        return None
    # For a floor, the closest a candidate came is the LARGEST KPI; for a
    # ceiling, the SMALLEST. Report whichever side is actually binding hardest.
    candidates: List[Tuple[str, float, float, float]] = []
    if minimum is not None:
        achieved = max(finite)
        candidates.append(("minimum", minimum, achieved, minimum - achieved))
    if maximum is not None:
        achieved = min(finite)
        candidates.append(("maximum", maximum, achieved, achieved - maximum))
    if not candidates:
        return None
    # Pick the side with the largest (most positive) shortfall — the one that
    # truly could not be cleared; ties keep the floor (listed first).
    bound_kind, required, achieved, shortfall = max(candidates, key=lambda c: c[3])
    return ConstraintViolation(
        key=key,
        bound_kind=bound_kind,
        required=float(required),
        achieved=float(achieved),
        shortfall=float(shortfall),
        candidates_violating=int(n_violating),
        candidates_total=int(n_total),
        never_satisfied=n_violating >= n_total,
    )


def build_capital_structure_diagnostics(
    curve: Sequence["CapitalStructurePoint"],
    constraints: Sequence["CovenantConstraint"],
) -> InfeasibilityDiagnostics:
    """Structured diagnostics for an infeasible capital-structure search.

    Uses each candidate's read-back ``constraints`` map + ``binding_constraints``
    to compute, per covenant, which bound was violated and by how much (the
    closest any candidate reached). Ordered worst-shortfall-first.
    """
    n_total = len(curve)
    n_feasible = sum(1 for p in curve if p.feasible)
    objectives = [float(p.objective) for p in curve]

    violations: List[ConstraintViolation] = []
    for con in constraints:
        values = [
            float(p.constraints[con.key]) for p in curve if con.key in p.constraints
        ]
        n_violating = sum(1 for p in curve if con.key in p.binding_constraints)
        violation = _violation_for_covenant(
            con.key, con.minimum, con.maximum, values, n_violating, n_total
        )
        if violation is not None and n_violating > 0:
            violations.append(violation)
    violations.sort(key=lambda v: v.shortfall, reverse=True)

    return InfeasibilityDiagnostics(
        n_candidates=n_total,
        n_feasible=n_feasible,
        violations=tuple(violations),
        binding_summary=_summarize(violations, n_total),
        objective_range=_objective_range(objectives),
    )


# ---------------------------------------------------------------------------
# Builders — single-parameter optimizer (one optional constraint)
# ---------------------------------------------------------------------------


def build_parameter_diagnostics(
    curve: Sequence["OptimizationPoint"],
    *,
    constraint_key: Optional[str],
    constraint_min: Optional[float],
    constraint_max: Optional[float],
) -> InfeasibilityDiagnostics:
    """Structured diagnostics for an infeasible single-parameter search.

    The single-parameter optimizer carries at most one constraint (``min`` /
    ``max`` on one KPI). Reports the closest the constrained KPI came to each
    active bound.
    """
    n_total = len(curve)
    n_feasible = sum(1 for p in curve if p.feasible)
    objectives = [float(p.objective) for p in curve]

    violations: List[ConstraintViolation] = []
    if constraint_key is not None:
        values = [
            float(p.constraint)
            for p in curve
            if p.constraint is not None and math.isfinite(p.constraint)
        ]
        n_violating = sum(1 for p in curve if not p.feasible)
        violation = _violation_for_covenant(
            constraint_key,
            constraint_min,
            constraint_max,
            values,
            n_violating,
            n_total,
        )
        if violation is not None and n_violating > 0:
            violations.append(violation)

    return InfeasibilityDiagnostics(
        n_candidates=n_total,
        n_feasible=n_feasible,
        violations=tuple(violations),
        binding_summary=_summarize(violations, n_total),
        objective_range=_objective_range(objectives),
    )


# ---------------------------------------------------------------------------
# Shared summary
# ---------------------------------------------------------------------------


def _summarize(
    violations: Sequence[ConstraintViolation],
    n_total: int,
) -> str:
    """One-line human reason built from the structured violations."""
    if not violations:
        return (
            "no candidates satisfied the covenants (no binding constraint identified)"
        )
    parts: List[str] = []
    for v in violations:
        op = ">=" if v.bound_kind == "minimum" else "<="
        parts.append(
            f"{v.key} {op} {v.required:g} (best achieved {v.achieved:g}, "
            f"short by {v.shortfall:g}; bound {v.candidates_violating}/"
            f"{v.candidates_total} candidates)"
        )
    return "; ".join(parts)


def audit_log_from_diagnostics(
    method: str,
    diagnostics: InfeasibilityDiagnostics,
) -> OptimizationAuditLog:
    """Derive the infeasible-path audit log from the diagnostics roll-up."""
    return OptimizationAuditLog(
        method=method,
        evaluations=diagnostics.n_candidates,
        iterations=diagnostics.n_candidates,
        final_status="infeasible",
        binding_constraints=tuple(v.key for v in diagnostics.violations),
        best_objective=None,
    )
