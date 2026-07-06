"""Debt-tranche-mix & capex-contingency optimizers (#740).

Two OPT-IN analysis optimizers that search a capital-structure decision space
against a return objective subject to covenant constraints, complementing the
engine's existing single-lever gearing solve (``finance.debt_v14._solve_gearing_for_dscr``):

* :func:`optimize_debt_mix` — search the debt tranche MIX (the lkr/usd/dfi
  split under ``Financing_Terms.mix``) to maximize (or minimize) an objective KPI
  (e.g. ``equity_irr``, or minimize a WACC proxy) SUBJECT TO covenant constraints
  (``min_dscr_period >= floor``, ``llcr``/``plcr`` floors, a balloon ceiling, ...).
  Two free proportions (LKR share, DFI share) span a 2-simplex; USD_Commercial
  absorbs the residual, mirroring the engine's ``_solve_mix``.
* :func:`optimize_capex_contingency` — search the capex CONTINGENCY fraction
  (a multiplicative uplift on a declared base capex, driving ``capex.usd_total``)
  against the same objective/constraints. Higher contingency is safer but lowers
  the return; the optimizer finds the return-maximizing fraction that still clears
  every covenant.

Design (CCCDIR / ARCH-04):
    Every candidate is scored by composing the canonical evaluation gateway
    :func:`analytics.evaluation_v14.evaluate_with_overrides` — no finance logic
    is re-implemented, no IRR/NPV is redefined (that lives only in
    ``finance.irr``), and the result types live in ``analytics.contracts_v14``.
    The optimizers are NEVER wired into ``run_v14_pipeline``: they are invoked
    explicitly (a function call / the opt-in ``analytics.cli`` entry), so running
    a committed scenario through the pipeline is byte-identical.

Fail-loud (CESSPIT):
    When no candidate satisfies the covenants the search returns a structured
    ``CapitalStructureOptimizationResult`` with ``feasible=False`` and an
    ``infeasible_reason`` naming the binding constraint(s) — never a bare crash
    or a silently-empty best. (The rich infeasibility register + full
    optimization audit log are a separate issue, #741; this carries the minimal
    diagnostic surface.)

Determinism (MRM-01):
    The search is an exhaustive deterministic grid (``numpy.linspace`` /
    ``numpy.arange`` on a fixed lattice) — no stochastic sampling, so repeated
    runs are bit-for-bit identical.

Context:
    Issue #740 (debt-mix & capex-contingency optimizers). Follow-up #741
    (infeasibility diagnostics + optimization audit log).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.contracts_v14 import (
    CapitalStructureOptimizationResult,
    CapitalStructurePoint,
    CovenantConstraint,
    DebtTrancheMix,
)
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.infeasibility_diagnostics import (
    InfeasibilityDiagnostics,
    OptimizationAuditLog,
    audit_log_from_diagnostics,
    build_capital_structure_diagnostics,
)

_DIRECTIONS = ("max", "min")

# Feasibility comparisons need a floating-point tolerance for the same reason
# ``optimization_v14`` does: the dual-DSCR debt sculpt pins the achieved DSCR
# *exactly* at the covenant target, so a constraint value lands at
# target +/- rounding noise. A naked ``value < bound`` would flip feasibility on
# that noise and mark covenant-grazing-but-compliant candidates infeasible at
# random. Treat a candidate as satisfying a bound within this tolerance
# (relative + absolute). Kept in lockstep with ``optimization_v14``.
_FEASIBILITY_ABS_TOL = 1e-9
_FEASIBILITY_REL_TOL = 1e-9

# Debt-mix shares are proportions summing to 1; USD absorbs the residual. The
# candidate lattice can leave a residual an epsilon below 0 through float
# accumulation — clamp within this tolerance before rejecting a candidate.
_SHARE_SUM_TOL = 1e-9

# Config paths the optimizers override (opt-in; never read by run_v14_pipeline
# on a committed scenario — proven byte-identical in the tests).
_MIX_LKR_PATH = "Financing_Terms.mix.lkr_max"
_MIX_DFI_PATH = "Financing_Terms.mix.dfi_max"
_CAPEX_TOTAL_PATH = "capex.usd_total"


def _bound_slack(bound: float) -> float:
    """Absolute slack to allow at a constraint bound (scales with the bound)."""
    return max(_FEASIBILITY_ABS_TOL, _FEASIBILITY_REL_TOL * abs(bound))


def _normalize_constraints(
    constraints: Optional[Sequence[CovenantConstraint]],
) -> List[CovenantConstraint]:
    """Validate the covenant constraints and return them as a concrete list.

    Raises:
        ValueError: If a constraint declares neither bound, or an inverted
            ``[minimum, maximum]`` interval, or a non-finite bound.
    """
    out: List[CovenantConstraint] = []
    for con in constraints or ():
        if con.minimum is None and con.maximum is None:
            raise ValueError(
                f"covenant constraint {con.key!r} declares neither minimum nor maximum"
            )
        if con.minimum is not None and not math.isfinite(con.minimum):
            raise ValueError(
                f"covenant constraint {con.key!r} minimum is non-finite: {con.minimum!r}"
            )
        if con.maximum is not None and not math.isfinite(con.maximum):
            raise ValueError(
                f"covenant constraint {con.key!r} maximum is non-finite: {con.maximum!r}"
            )
        if (
            con.minimum is not None
            and con.maximum is not None
            and con.minimum > con.maximum
        ):
            raise ValueError(
                f"covenant constraint {con.key!r} has minimum {con.minimum!r} "
                f"> maximum {con.maximum!r}"
            )
        out.append(con)
    return out


def _apply_constraints(
    kpis: Mapping[str, float],
    constraints: Sequence[CovenantConstraint],
) -> Tuple[Dict[str, float], bool, Tuple[str, ...]]:
    """Evaluate every covenant against a candidate's KPIs.

    Returns:
        ``(values, feasible, binding)`` where ``values`` maps each constraint
        key to the read-back KPI, ``feasible`` is ``True`` iff every bound is
        satisfied within ``_bound_slack``, and ``binding`` names the violated
        keys (empty when feasible).

    Raises:
        KeyError: If a constraint key is absent from the evaluated KPIs
            (fail-loud — a mistyped covenant key must not be silently feasible).
    """
    values: Dict[str, float] = {}
    binding: List[str] = []
    for con in constraints:
        if con.key not in kpis:
            raise KeyError(
                f"covenant constraint key {con.key!r} not found in evaluated KPIs "
                f"(available: {sorted(kpis)!r})"
            )
        value = float(kpis[con.key])
        values[con.key] = value
        ok = True
        if con.minimum is not None and value < con.minimum - _bound_slack(con.minimum):
            ok = False
        if con.maximum is not None and value > con.maximum + _bound_slack(con.maximum):
            ok = False
        if not ok:
            binding.append(con.key)
    return values, not binding, tuple(binding)


def _infeasible_reason(
    curve: Sequence[CapitalStructurePoint],
    constraints: Sequence[CovenantConstraint],
) -> str:
    """Name the covenant(s) that bound EVERY candidate (minimal #740 diagnostic).

    Rich per-candidate infeasibility diagnostics are the follow-up #741; here we
    report the constraint key(s) that appear in every candidate's
    ``binding_constraints`` (i.e. never once satisfied across the whole search),
    else — if the binding set varies — the union of all binding keys.
    """
    if not curve:
        return "no candidates were evaluated"
    always_binding = set(curve[0].binding_constraints)
    union_binding: set[str] = set()
    for point in curve:
        always_binding &= set(point.binding_constraints)
        union_binding |= set(point.binding_constraints)
    if always_binding:
        keys = ", ".join(sorted(always_binding))
        return f"covenant(s) never satisfied by any candidate: {keys}"
    keys = ", ".join(sorted(union_binding)) or "unknown"
    return (
        "no single candidate satisfied all covenants simultaneously; "
        f"binding across the search: {keys}"
    )


def _failure_diagnostics(
    kind: str,
    curve: Sequence[CapitalStructurePoint],
    constraints: Sequence[CovenantConstraint],
) -> Tuple[Optional[InfeasibilityDiagnostics], Optional[OptimizationAuditLog]]:
    """Structured why-infeasible register + audit log (#741) for a failed search.

    Called ONLY on the infeasible path (no feasible candidate). Returns
    ``(diagnostics, audit_log)``; a feasible solve never calls this and carries
    ``(None, None)`` so its result is byte-identical to the #740 surface.
    """
    diagnostics = build_capital_structure_diagnostics(curve, constraints)
    audit = audit_log_from_diagnostics(kind, diagnostics)
    return diagnostics, audit


def _select_best(
    curve: Sequence[CapitalStructurePoint],
    direction: str,
) -> Optional[CapitalStructurePoint]:
    """Best FEASIBLE candidate in ``direction`` (``None`` if none feasible)."""
    feasible = [p for p in curve if p.feasible and math.isfinite(p.objective)]
    if not feasible:
        return None
    if direction == "max":
        return max(feasible, key=lambda p: p.objective)
    return min(feasible, key=lambda p: p.objective)


def _score_candidate(
    config_path: str,
    *,
    value: Tuple[float, ...],
    mix: DebtTrancheMix | None,
    overrides: Mapping[str, Any],
    objective_key: str,
    constraints: Sequence[CovenantConstraint],
    base_overrides: Mapping[str, Any],
) -> CapitalStructurePoint:
    """Evaluate one candidate through the gateway and apply the covenants.

    Composes ``evaluate_with_overrides`` (the ONLY scoring path — ARCH-04) with
    the candidate's config overrides merged over any ``base_overrides``.

    Raises:
        KeyError: If ``objective_key`` or a constraint key is absent from the
            evaluated KPIs (fail-loud).
    """
    merged: Dict[str, Any] = dict(base_overrides)
    merged.update(overrides)
    kpis = evaluate_with_overrides(config_path, overrides=merged)
    if objective_key not in kpis:
        raise KeyError(
            f"objective_key {objective_key!r} not found in evaluated KPIs "
            f"(available: {sorted(kpis)!r})"
        )
    objective = float(kpis[objective_key])
    con_values, feasible, binding = _apply_constraints(kpis, constraints)
    return CapitalStructurePoint(
        value=value,
        mix=mix,
        objective=objective,
        constraints=con_values,
        feasible=feasible,
        binding_constraints=binding,
    )


def optimize_debt_mix(
    config_path: str,
    *,
    objective_key: str = "equity_irr",
    direction: str = "max",
    constraints: Optional[Sequence[CovenantConstraint]] = None,
    lkr_bounds: Tuple[float, float] = (0.0, 1.0),
    dfi_bounds: Tuple[float, float] = (0.0, 1.0),
    n_steps: int = 6,
    base_overrides: Optional[Mapping[str, Any]] = None,
) -> CapitalStructureOptimizationResult:
    """Optimize the debt tranche MIX (lkr/usd/dfi split) under covenant constraints.

    Searches the 2-simplex of ``(lkr_share, dfi_share)`` on a deterministic
    ``n_steps x n_steps`` lattice inside ``lkr_bounds`` / ``dfi_bounds``,
    discarding candidates whose USD_Commercial residual (``1 - lkr - dfi``) would
    be negative. Each admissible candidate is scored by overriding
    ``Financing_Terms.mix.lkr_max`` / ``.dfi_max`` and running the pipeline
    through :func:`~analytics.evaluation_v14.evaluate_with_overrides`; the best
    FEASIBLE candidate in ``direction`` is returned.

    Args:
        config_path: Path to the v14 scenario config (the base to perturb).
        objective_key: KPI key to optimize (default ``equity_irr``). To minimize
            a WACC proxy, pass e.g. ``discount_rate_used`` with ``direction="min"``.
        direction: ``"max"`` or ``"min"``.
        constraints: Covenant constraints (e.g. ``min_dscr_period >= 1.30``,
            ``llcr >= 1.0``, ``balloon_pct <= 0.10``). Empty -> unconstrained.
        lkr_bounds, dfi_bounds: Inclusive ``(low, high)`` share ranges to search
            (each in ``[0, 1]``, ``low <= high``).
        n_steps: Lattice resolution per axis (>= 2). The evaluated candidate
            count is at most ``n_steps**2`` (fewer, after the residual filter).
        base_overrides: Extra dotted overrides applied to every candidate (e.g.
            to co-vary rates); the search still perturbs only the mix.

    Returns:
        A :class:`~analytics.contracts_v14.CapitalStructureOptimizationResult`
        (``kind="debt_mix"``). ``best`` is the optimum feasible mix, or ``None``
        with ``feasible=False`` and an ``infeasible_reason`` when the covenants
        cannot be met anywhere in the searched region (fail-loud).

    Raises:
        ValueError: On an invalid ``direction``, ``n_steps`` < 2, out-of-range
            or inverted bounds, or a malformed constraint.
        KeyError: If ``objective_key`` or a constraint key is not an evaluated KPI.
    """
    if direction not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}, got {direction!r}")
    if n_steps < 2:
        raise ValueError(f"n_steps must be >= 2, got {n_steps}")
    for name, (lo, hi) in (("lkr_bounds", lkr_bounds), ("dfi_bounds", dfi_bounds)):
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError(f"{name} must be finite, got ({lo!r}, {hi!r})")
        if not 0.0 <= lo <= hi <= 1.0:
            raise ValueError(
                f"{name} must satisfy 0 <= low <= high <= 1, got ({lo!r}, {hi!r})"
            )

    cons = _normalize_constraints(constraints)
    base = dict(base_overrides or {})

    curve: List[CapitalStructurePoint] = []
    for lkr in np.linspace(lkr_bounds[0], lkr_bounds[1], n_steps):
        for dfi in np.linspace(dfi_bounds[0], dfi_bounds[1], n_steps):
            lkr_f = float(lkr)
            dfi_f = float(dfi)
            usd_f = 1.0 - lkr_f - dfi_f
            if usd_f < -_SHARE_SUM_TOL:
                # Infeasible geometry (over-100% allocation): skip, don't score.
                continue
            usd_f = max(0.0, usd_f)
            mix = DebtTrancheMix(lkr_share=lkr_f, dfi_share=dfi_f, usd_share=usd_f)
            overrides = {_MIX_LKR_PATH: lkr_f, _MIX_DFI_PATH: dfi_f}
            curve.append(
                _score_candidate(
                    config_path,
                    value=(lkr_f, dfi_f),
                    mix=mix,
                    overrides=overrides,
                    objective_key=objective_key,
                    constraints=cons,
                    base_overrides=base,
                )
            )

    if not curve:
        raise ValueError(
            "debt-mix search produced no admissible candidates; check that "
            "lkr_bounds + dfi_bounds admit a non-negative USD residual"
        )

    best = _select_best(curve, direction)
    feasible = best is not None
    diagnostics, audit_log = (
        (None, None) if feasible else _failure_diagnostics("debt_mix", curve, cons)
    )
    return CapitalStructureOptimizationResult(
        kind="debt_mix",
        objective_key=objective_key,
        direction=direction,
        constraints=cons,
        best=best,
        curve=curve,
        feasible=feasible,
        infeasible_reason=None if feasible else _infeasible_reason(curve, cons),
        diagnostics=diagnostics,
        audit_log=audit_log,
    )


def optimize_capex_contingency(
    config_path: str,
    *,
    base_capex_usd: float,
    objective_key: str = "equity_irr",
    direction: str = "max",
    constraints: Optional[Sequence[CovenantConstraint]] = None,
    contingency_bounds: Tuple[float, float] = (0.0, 0.20),
    n_steps: int = 11,
    base_overrides: Optional[Mapping[str, Any]] = None,
) -> CapitalStructureOptimizationResult:
    """Optimize the capex CONTINGENCY fraction under covenant constraints.

    Searches the contingency fraction ``f`` on a deterministic
    ``np.linspace(lo, hi, n_steps)`` grid; each candidate sets
    ``capex.usd_total = base_capex_usd * (1 + f)`` (contingency as a
    multiplicative uplift on the declared base cost) and is scored through
    :func:`~analytics.evaluation_v14.evaluate_with_overrides`. Higher contingency
    is safer but lowers the return, so the return-maximizing feasible fraction is
    the smallest one that still clears every covenant.

    Args:
        config_path: Path to the v14 scenario config.
        base_capex_usd: The base capex (EXCLUDING contingency) that the
            fraction upflifts, i.e. ``capex.usd_total`` net of its current
            contingency line. Must be finite and > 0. The optimizer sets
            ``capex.usd_total = base_capex_usd * (1 + f)`` so the search is
            self-consistent regardless of the committed contingency line.
        objective_key: KPI key to optimize (default ``equity_irr``).
        direction: ``"max"`` or ``"min"``.
        constraints: Covenant constraints (as in :func:`optimize_debt_mix`).
        contingency_bounds: Inclusive ``(low, high)`` fraction range to search
            (each >= 0, ``low <= high``; e.g. ``(0.0, 0.20)`` = 0%..20%).
        n_steps: Grid resolution (>= 2).
        base_overrides: Extra dotted overrides applied to every candidate.

    Returns:
        A :class:`~analytics.contracts_v14.CapitalStructureOptimizationResult`
        (``kind="capex_contingency"``). ``best`` is the optimum feasible
        fraction, or ``None`` with ``feasible=False`` + ``infeasible_reason``
        when the covenants cannot be met (fail-loud).

    Raises:
        ValueError: On an invalid ``direction``, ``n_steps`` < 2, non-positive
            ``base_capex_usd``, out-of-range/inverted ``contingency_bounds``, or
            a malformed constraint.
        KeyError: If ``objective_key`` or a constraint key is not an evaluated KPI.
    """
    if direction not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}, got {direction!r}")
    if n_steps < 2:
        raise ValueError(f"n_steps must be >= 2, got {n_steps}")
    if not (math.isfinite(base_capex_usd) and base_capex_usd > 0.0):
        raise ValueError(
            f"base_capex_usd must be finite and > 0, got {base_capex_usd!r}"
        )
    lo, hi = contingency_bounds
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise ValueError(f"contingency_bounds must be finite, got ({lo!r}, {hi!r})")
    if not (0.0 <= lo <= hi):
        raise ValueError(
            f"contingency_bounds must satisfy 0 <= low <= high, got ({lo!r}, {hi!r})"
        )

    cons = _normalize_constraints(constraints)
    base = dict(base_overrides or {})

    curve: List[CapitalStructurePoint] = []
    for frac in np.linspace(lo, hi, n_steps):
        frac_f = float(frac)
        total = base_capex_usd * (1.0 + frac_f)
        overrides = {_CAPEX_TOTAL_PATH: total}
        curve.append(
            _score_candidate(
                config_path,
                value=(frac_f,),
                mix=None,
                overrides=overrides,
                objective_key=objective_key,
                constraints=cons,
                base_overrides=base,
            )
        )

    best = _select_best(curve, direction)
    feasible = best is not None
    diagnostics, audit_log = (
        (None, None)
        if feasible
        else _failure_diagnostics("capex_contingency", curve, cons)
    )
    return CapitalStructureOptimizationResult(
        kind="capex_contingency",
        objective_key=objective_key,
        direction=direction,
        constraints=cons,
        best=best,
        curve=curve,
        feasible=feasible,
        infeasible_reason=None if feasible else _infeasible_reason(curve, cons),
        diagnostics=diagnostics,
        audit_log=audit_log,
    )


__all__ = [
    "optimize_debt_mix",
    "optimize_capex_contingency",
]
