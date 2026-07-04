#!/usr/bin/env python
"""Tests for the optimization_v14 facade (#30, #602).

Structural tests (robust to model nonlinearity): the sweep runs over the v14
pipeline, records a full curve, applies the KPI constraint, and selects the best
feasible point in the requested direction.

The ``method="bounded"`` tests (#602) validate the opt-in SciPy bounded scalar
refinement: fail-loud input validation, convergence against known analytic
optima (via a monkeypatched gateway), infeasibility penalization, determinism,
and a grid-vs-bounded cross-check on the committed lender scenario's
DSCR-sculpt region.

Context:
    Sprint 11 - Issue #30 (optimization_v14 using evaluate_with_overrides).
    Issue #602 (opt-in ``method="bounded"`` scalar refinement).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import pytest

import analytics.optimization_v14 as opt_mod
from analytics.optimization_v14 import OptimizationResult, optimize_parameter

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Sweep the gearing cap; equity IRR is the objective, min DSCR the constraint.
COMMON = dict(
    config_path=LENDER_CONFIG,
    param_path="Financing_Terms.debt_ratio",
    objective_key="equity_irr",
    lower=0.45,
    upper=0.70,
    n_steps=5,
)


def test_sweep_runs_and_curve_length() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=1.20)
    assert isinstance(res, OptimizationResult)
    assert len(res.curve) == 5
    assert res.best is not None


def test_best_is_max_feasible() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=1.20)
    feasible = [p for p in res.curve if p.feasible]
    assert res.best is not None
    assert res.best.objective == max(p.objective for p in feasible)
    assert res.best.feasible


def test_min_direction_selects_lowest() -> None:
    res = optimize_parameter(**COMMON, direction="min")
    assert res.best is not None
    assert res.best.objective == min(p.objective for p in res.curve)


def test_no_constraint_all_feasible() -> None:
    res = optimize_parameter(**COMMON)
    assert all(p.feasible for p in res.curve)
    assert all(p.constraint is None for p in res.curve)
    assert res.best is not None
    assert res.best.objective == max(p.objective for p in res.curve)


def test_constraint_recorded() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=1.20)
    assert all(p.constraint is not None for p in res.curve)


def test_impossible_constraint_returns_no_best() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=99.0)
    assert res.best is None
    assert all(not p.feasible for p in res.curve)


def test_invalid_direction_raises() -> None:
    with pytest.raises(ValueError, match="direction must be"):
        optimize_parameter(**COMMON, direction="sideways")


def test_too_few_steps_raises() -> None:
    args = dict(COMMON)
    args["n_steps"] = 1
    with pytest.raises(ValueError, match="n_steps must be"):
        optimize_parameter(**args)


# ---------------------------------------------------------------------------
# method="bounded" (#602) — opt-in SciPy bounded scalar refinement
# ---------------------------------------------------------------------------

# Bracket for the synthetic analytic tests; the config path is never read by
# the monkeypatched gateway but keeps the call signature realistic.
BOUNDED_COMMON: Dict[str, Any] = dict(
    config_path=LENDER_CONFIG,
    param_path="Financing_Terms.debt_ratio",
    objective_key="equity_irr",
    lower=0.0,
    upper=1.0,
    method="bounded",
)


def _make_analytic_eval(
    objective_fn: Callable[[float], float],
    constraint_fn: Optional[Callable[[float], float]] = None,
) -> Callable[..., Dict[str, Any]]:
    """Fake ``evaluate_with_overrides`` mapping the override to analytic KPIs."""

    def _fake(
        config_path: str,
        *,
        overrides: Optional[Mapping[str, Any]] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        x = float((overrides or {})[str(BOUNDED_COMMON["param_path"])])
        kpis: Dict[str, Any] = {"equity_irr": objective_fn(x)}
        if constraint_fn is not None:
            kpis["min_dscr"] = constraint_fn(x)
        return kpis

    return _fake


def test_unknown_method_raises() -> None:
    with pytest.raises(ValueError, match="method must be"):
        optimize_parameter(**COMMON, method="newton")


def test_bounded_nonfinite_bracket_raises() -> None:
    with pytest.raises(ValueError, match="finite bracket"):
        optimize_parameter(**{**BOUNDED_COMMON, "upper": float("inf")})
    with pytest.raises(ValueError, match="finite bracket"):
        optimize_parameter(**{**BOUNDED_COMMON, "lower": float("nan")})


def test_bounded_inverted_or_degenerate_bracket_raises() -> None:
    with pytest.raises(ValueError, match="lower < upper"):
        optimize_parameter(**{**BOUNDED_COMMON, "lower": 0.7, "upper": 0.45})
    with pytest.raises(ValueError, match="lower < upper"):
        optimize_parameter(**{**BOUNDED_COMMON, "lower": 0.5, "upper": 0.5})


def test_bounded_invalid_options_raise() -> None:
    with pytest.raises(ValueError, match="bounded_xatol must be"):
        optimize_parameter(**BOUNDED_COMMON, bounded_xatol=0.0)
    with pytest.raises(ValueError, match="bounded_xatol must be"):
        optimize_parameter(**BOUNDED_COMMON, bounded_xatol=float("nan"))
    with pytest.raises(ValueError, match="bounded_maxiter must be"):
        optimize_parameter(**BOUNDED_COMMON, bounded_maxiter=0)


def test_bounded_converges_to_analytic_interior_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Known analytic optimum: objective = 2 - (x - 0.6)^2, unique max at 0.6."""
    fake = _make_analytic_eval(lambda x: 2.0 - (x - 0.6) ** 2)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_parameter(**BOUNDED_COMMON, direction="max")

    assert isinstance(res, OptimizationResult)
    assert res.best is not None
    assert res.best.feasible
    assert res.best.value == pytest.approx(0.6, abs=1e-4)
    assert res.best.objective == pytest.approx(2.0, abs=1e-6)
    # The curve is the evaluation trace: every point recorded, inside bracket.
    assert len(res.curve) >= 3
    assert all(0.0 <= p.value <= 1.0 for p in res.curve)
    # No constraint requested: constraint is None, everything feasible.
    assert all(p.constraint is None and p.feasible for p in res.curve)


def test_bounded_converges_to_analytic_interior_min(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Known analytic optimum: objective = (x - 0.25)^2 + 1, unique min at 0.25."""
    fake = _make_analytic_eval(lambda x: (x - 0.25) ** 2 + 1.0)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_parameter(**BOUNDED_COMMON, direction="min")

    assert res.best is not None
    assert res.best.value == pytest.approx(0.25, abs=1e-4)
    assert res.best.objective == pytest.approx(1.0, abs=1e-6)


def test_bounded_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two identical runs produce identical traces and identical bests."""
    fake = _make_analytic_eval(lambda x: 2.0 - (x - 0.6) ** 2)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res1 = optimize_parameter(**BOUNDED_COMMON, direction="max")
    res2 = optimize_parameter(**BOUNDED_COMMON, direction="max")

    assert res1.curve == res2.curve
    assert res1.best == res2.best


def test_bounded_penalization_steers_away_from_infeasible_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never silently return an infeasible point (#602 acceptance).

    The objective increases with x (unconstrained max at the upper bound), but
    the constraint makes only x <= 0.5 feasible. The penalized search must
    converge tight against the feasibility wall from the feasible side.
    """
    fake = _make_analytic_eval(
        lambda x: x,
        lambda x: 2.0 if x <= 0.5 else 0.0,
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_parameter(
        **BOUNDED_COMMON,
        direction="max",
        constraint_key="min_dscr",
        constraint_min=1.0,
    )

    assert res.best is not None
    assert res.best.feasible
    assert res.best.value <= 0.5  # never inside the infeasible region
    assert res.best.value >= 0.5 - 1e-3  # converged against the wall
    # The trace shows the search probed (and rejected) the infeasible side.
    assert any(not p.feasible for p in res.curve)


def test_bounded_infeasible_everywhere_returns_no_best(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _make_analytic_eval(lambda x: x, lambda x: 0.0)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_parameter(
        **BOUNDED_COMMON,
        direction="max",
        constraint_key="min_dscr",
        constraint_min=99.0,
    )

    assert res.best is None
    assert res.curve
    assert all(not p.feasible for p in res.curve)


def test_bounded_nonfinite_objective_returns_no_best(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NaN objective is penalized, never returned as best (FIN-01)."""
    fake = _make_analytic_eval(lambda x: float("nan"))
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_parameter(**BOUNDED_COMMON, direction="max")

    assert res.best is None
    assert res.curve
    assert all(math.isnan(p.objective) for p in res.curve)


def test_bounded_nonconvergence_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_analytic_eval(lambda x: 2.0 - (x - 0.6) ** 2)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    with pytest.raises(RuntimeError, match="did not converge"):
        optimize_parameter(**BOUNDED_COMMON, direction="max", bounded_maxiter=1)


def test_bounded_applies_bound_slack_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Covenant-grazing points (within ``_bound_slack``) stay feasible.

    The constraint sits 1e-12 below the 1.30 bound — inside the shared
    ``_bound_slack(1.30)`` ~ 1.3e-9 tolerance — mirroring the DSCR-sculpt
    plateau; the bounded path must treat it as feasible exactly like the
    grid path does.
    """
    fake = _make_analytic_eval(
        lambda x: 2.0 - (x - 0.6) ** 2,
        lambda x: 1.30 - 1e-12,
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_parameter(
        **BOUNDED_COMMON,
        direction="max",
        constraint_key="min_dscr",
        constraint_min=1.30,
    )

    assert res.best is not None
    assert res.best.feasible
    assert res.best.value == pytest.approx(0.6, abs=1e-4)
    assert all(p.feasible for p in res.curve)


@pytest.mark.slow
def test_grid_vs_bounded_cross_check_dscr_sculpt() -> None:
    """Grid-vs-bounded cross-check on the committed lender case (#602).

    On the canonical deleverage sweep the dual-DSCR sculpt pins ``min_dscr``
    at the 1.30 covenant across the whole bracket (a plateau that is feasible
    only through the shared ``_bound_slack`` tolerance — the sculpt lands an
    epsilon *below* 1.30), and equity IRR is maximized by deleveraging, i.e.
    at the LOWER bracket endpoint.

    Documented local-optimum/boundary divergence: the bounded method searches
    the open interval, so for a boundary optimum it converges within ~xatol of
    the endpoint rather than on it, while the grid evaluates the endpoint
    exactly. The resulting objective shortfall is bounded by (local slope
    ~0.13 IRR/unit ratio) x (boundary offset < ~1e-3) ~ 1e-4; assert the
    direction="max" cross-check within a 2e-4 tolerance.

    BRACKET (#737): strictly SUB-CAP [0.30, 0.42]. Above the ~0.4275
    DSCR-solved cap the sizer clamps every requested ratio to the same solved
    structure, but the gearing scan's 0.0025 step grid is anchored at the
    REQUESTED ratio, so the clamp region carries a small quantization texture
    (~5e-4 IRR between adjacent requests). That texture fakes interior optima
    and violates the unimodality assumption Brent needs — the pre-#737 bracket
    reached 0.70 only because the texture then sat below the solver tolerance.
    Sub-cap, the fee-inclusive objective is smooth and strictly decreasing in
    gearing (deleveraging wins), which is exactly the property cross-checked.
    """
    common: Dict[str, Any] = dict(
        config_path=LENDER_CONFIG,
        param_path="Financing_Terms.debt_ratio",
        objective_key="equity_irr",
        direction="max",
        lower=0.30,
        upper=0.42,
        constraint_key="min_dscr",
        constraint_min=1.30,
    )
    grid = optimize_parameter(**common, n_steps=9)
    bounded = optimize_parameter(**common, method="bounded", bounded_xatol=1e-3)

    assert grid.best is not None
    assert bounded.best is not None
    assert bounded.best.feasible
    # The real sculpt plateau exercises the shared feasibility tolerance.
    assert bounded.best.constraint == pytest.approx(1.30, abs=1e-9)
    # direction="max" cross-check: bounded best >= grid best within tolerance.
    assert bounded.best.objective >= grid.best.objective - 2e-4
    # Both localize the same optimum: the lower boundary of the bracket.
    assert grid.best.value == pytest.approx(0.30, abs=1e-9)
    assert bounded.best.value == pytest.approx(0.30, abs=5e-3)
