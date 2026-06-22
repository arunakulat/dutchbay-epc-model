#!/usr/bin/env python
"""Tests for analytics.core.parameter_solvers.

The parameter solvers reverse-engineer an input (tariff, debt, capex) from a
target KPI (IRR, DSCR, NPV) using bisection over evaluate_with_overrides().

House style: load the lender case scenario by REPO_ROOT path and drive the real
finance engine. These tests assert the *bisection control flow* (which boundary
or last-midpoint the solver lands on given the engine's response), the
documented raises, the registry surface, and the shallow-clone contract.

Engine note (load-bearing for the assertions below):
    Against scenarios/dutchbay_lendercase_2025Q4.yaml the solver override keys
    ("financial.tariff_lkr_per_kwh", "financial.debt_amount_usd",
    "project.capex_usd") are NOT part of that config's schema, so the merged
    KPIs are invariant to the swept parameter. The solved KPI is therefore
    constant across the bracket, which makes the bisection direction (and thus
    the landing boundary) fully deterministic:
      - base project_irr  ~= 0.0543
      - base project_npv  ~= -3.19e7 USD
      - base min_dscr / dscr_min == 1.30
    All boundary assertions are derived from these constants.

KNOWN BUG (Sprint 16 P3-2 multi-covenant solver):
    solve_for_max_debt_multi_covenant reads kpis["llcr_min"], a key the engine
    never produces (it emits "llcr"). kpis.get("llcr_min", 0.0) is therefore
    always 0.0, so any positive LLCR covenant is never satisfied and debt is
    driven to the lower bound regardless of the true (DSCR/LLCR) slack. The
    correct-behaviour test for a binding-but-satisfiable LLCR is xfailed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.core.parameter_solvers import (
    SOLVER_REGISTRY,
    get_solver,
    solve_for_max_debt_given_dscr,
    solve_for_max_debt_multi_covenant,
    solve_for_min_capex_given_irr_floor,
    solve_for_tariff_given_irr,
    solve_for_tariff_given_npv,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Engine constants for the lender case (see module docstring).
BASE_PROJECT_IRR = 0.0543
BASE_PROJECT_NPV = -3.19e7
BASE_DSCR = 1.30


# ---------------------------------------------------------------------------
# IRR-based tariff solver
# ---------------------------------------------------------------------------


def test_irr_solver_target_below_achieved_lands_on_low_bound() -> None:
    """Target IRR < achieved => delta > 0 every step => bracket collapses to low."""
    low, high = 40.0, 100.0
    tariff = solve_for_tariff_given_irr(
        LENDER_CONFIG, None, target_irr=0.04, bounds=(low, high)
    )
    assert low <= tariff <= high
    assert tariff == pytest.approx(low, abs=1e-6)


def test_irr_solver_target_above_achieved_lands_on_high_bound() -> None:
    """Target IRR > achieved => delta < 0 every step => bracket collapses to high."""
    low, high = 40.0, 100.0
    tariff = solve_for_tariff_given_irr(
        LENDER_CONFIG, None, target_irr=0.10, bounds=(low, high)
    )
    assert low <= tariff <= high
    assert tariff == pytest.approx(high, abs=1e-6)


def test_irr_solver_rejects_non_bisection_method() -> None:
    with pytest.raises(ValueError, match="Unsupported solver method"):
        solve_for_tariff_given_irr(
            LENDER_CONFIG, None, target_irr=0.10, method="gradient"
        )


def test_irr_solver_zero_iterations_raises_no_midpoint() -> None:
    """With no iterations the loop never sets last_good_mid -> hard ValueError."""
    with pytest.raises(ValueError, match="failed to converge"):
        solve_for_tariff_given_irr(
            LENDER_CONFIG, None, target_irr=0.10, max_iterations=0
        )


def test_irr_solver_converges_within_tolerance_when_target_reachable() -> None:
    """A wide tolerance is met on the first probe; result stays inside bounds."""
    low, high = 40.0, 100.0
    tariff = solve_for_tariff_given_irr(
        LENDER_CONFIG,
        None,
        target_irr=BASE_PROJECT_IRR,
        bounds=(low, high),
        tolerance=0.05,  # |achieved - target| ~ 0 << tolerance
    )
    assert tariff == pytest.approx((low + high) / 2.0, abs=1e-6)


# ---------------------------------------------------------------------------
# DSCR-based max-debt solver
# ---------------------------------------------------------------------------


def test_dscr_solver_loose_covenant_pushes_debt_to_high_bound() -> None:
    """DSCR (1.30) > target (1.10) every step => can always raise debt => high."""
    low, high = 1.0e6, 1.0e9
    debt = solve_for_max_debt_given_dscr(
        LENDER_CONFIG, None, target_dscr=1.10, bounds=(low, high), tolerance=1000.0
    )
    assert low <= debt <= high
    assert debt == pytest.approx(high, rel=1e-5)


def test_dscr_solver_tight_covenant_pushes_debt_to_low_bound() -> None:
    """DSCR (1.30) < target (1.50) every step => must lower debt => low bound."""
    low, high = 1.0e6, 1.0e9
    debt = solve_for_max_debt_given_dscr(
        LENDER_CONFIG, None, target_dscr=1.50, bounds=(low, high), tolerance=1000.0
    )
    assert low <= debt <= high
    assert debt == pytest.approx(low, rel=1e-3)


def test_dscr_solver_respects_tolerance_bracket_width() -> None:
    """Returned debt is within tolerance of a bracket endpoint."""
    low, high = 1.0e6, 1.0e9
    tol = 5_000.0
    debt = solve_for_max_debt_given_dscr(
        LENDER_CONFIG, None, target_dscr=1.10, bounds=(low, high), tolerance=tol
    )
    # Loose covenant collapses toward high; final midpoint sits within tol of it.
    assert abs(debt - high) < tol


# ---------------------------------------------------------------------------
# NPV-based tariff solver
# ---------------------------------------------------------------------------


def test_npv_solver_project_metric_converges_at_midpoint() -> None:
    """Target == achieved project_npv with a wide tolerance => early convergence.

    The first probe is the bracket midpoint; |achieved - target| < tolerance, so
    the solver returns the midpoint before reaching the (buggy) non-convergence
    warning path.
    """
    low, high = 40.0, 100.0
    tariff = solve_for_tariff_given_npv(
        LENDER_CONFIG,
        None,
        target_npv=BASE_PROJECT_NPV,
        metric="project_npv",
        bounds=(low, high),
        tolerance=1.0e7,
    )
    assert tariff == pytest.approx((low + high) / 2.0, abs=1e-6)


def test_npv_solver_equity_metric_accepted_and_converges() -> None:
    """equity_npv is a valid metric; with a wide tolerance it converges cleanly."""
    low, high = 40.0, 100.0
    tariff = solve_for_tariff_given_npv(
        LENDER_CONFIG,
        None,
        target_npv=-3.8e7,  # ~ achieved equity_npv for the lender case
        metric="equity_npv",
        bounds=(low, high),
        tolerance=1.0e7,
    )
    assert tariff == pytest.approx((low + high) / 2.0, abs=1e-6)


def test_npv_solver_unreachable_target_should_return_boundary_not_raise() -> None:
    """An unreachable target lands on a bound instead of raising.

    project_npv is invariant for this config, so a target far below it yields a
    constant positive delta => the bracket collapses to the low bound and the
    solver returns it. (Previously the non-convergence warning's '%,.0f' logging
    format raised ValueError on this path; this regression-guards that fix.)
    """
    low, high = 40.0, 100.0
    tariff = solve_for_tariff_given_npv(
        LENDER_CONFIG,
        None,
        target_npv=-1.0e9,
        metric="project_npv",
        bounds=(low, high),
    )
    assert tariff == pytest.approx(low, abs=1e-6)


def test_npv_solver_rejects_invalid_metric() -> None:
    with pytest.raises(ValueError, match="Invalid NPV metric"):
        solve_for_tariff_given_npv(
            LENDER_CONFIG, None, target_npv=0.0, metric="not_a_metric"
        )


# ---------------------------------------------------------------------------
# Multi-covenant (DSCR + LLCR) solver  -- carries the known LLCR bug
# ---------------------------------------------------------------------------


def test_multi_covenant_collapses_to_floor_due_to_missing_llcr_key() -> None:
    """Current (buggy) behaviour: debt is driven to the lower bound.

    DSCR (1.30) satisfies target (1.10), but llcr is read as kpis["llcr_min"]
    which the engine never sets, so it defaults to 0.0 and never meets the
    target_llcr. ``both_satisfied`` is therefore always False and the bracket
    collapses toward the low bound.
    """
    low, high = 1.0e6, 1.0e9
    debt = solve_for_max_debt_multi_covenant(
        LENDER_CONFIG,
        None,
        target_dscr=1.10,
        target_llcr=1.50,
        bounds=(low, high),
        tolerance=1000.0,
    )
    # BUG: should be able to raise debt (DSCR has slack) but LLCR reads 0.0,
    # so debt collapses to the floor. Assert the current behaviour.
    assert debt == pytest.approx(low, rel=1e-3)


@pytest.mark.xfail(
    reason=(
        "KNOWN BUG: solver reads kpis['llcr_min'] but the engine emits 'llcr'; "
        "the missing key defaults LLCR to 0.0 so a satisfiable LLCR covenant "
        "never binds and debt collapses to the floor instead of rising with "
        "the available DSCR/LLCR slack."
    ),
    strict=False,
)
def test_multi_covenant_satisfiable_llcr_should_not_collapse_to_floor() -> None:
    """Correct behaviour (fix-me): a satisfiable LLCR should let debt rise.

    The engine reports llcr ~= 1.13 and dscr_min == 1.30 for this case. With
    target_dscr=1.10 and target_llcr=1.00 (both genuinely satisfied), a correct
    solver would behave like the DSCR-only solver and push debt toward the high
    bound rather than the floor.
    """
    low, high = 1.0e6, 1.0e9
    debt = solve_for_max_debt_multi_covenant(
        LENDER_CONFIG,
        None,
        target_dscr=1.10,
        target_llcr=1.00,
        bounds=(low, high),
        tolerance=1000.0,
    )
    # Would pass only if LLCR were read correctly (1.13 >= 1.00).
    assert debt > 10.0 * low


# ---------------------------------------------------------------------------
# Capex optimizer (minimize capex subject to IRR floor)
# ---------------------------------------------------------------------------


def test_min_capex_floor_below_achieved_minimizes_to_low_bound() -> None:
    """IRR (0.0543) >= floor (0.04) every step => keep lowering capex => low."""
    low, high = 100.0e6, 500.0e6
    capex = solve_for_min_capex_given_irr_floor(
        LENDER_CONFIG, None, irr_floor=0.04, bounds=(low, high), tolerance=10_000.0
    )
    assert low <= capex <= high
    assert capex == pytest.approx(low, rel=1e-3)


def test_min_capex_floor_above_achieved_pushes_to_high_bound() -> None:
    """IRR (0.0543) < floor (0.10) every step => need more capex => high bound."""
    low, high = 100.0e6, 500.0e6
    capex = solve_for_min_capex_given_irr_floor(
        LENDER_CONFIG, None, irr_floor=0.10, bounds=(low, high), tolerance=10_000.0
    )
    assert low <= capex <= high
    assert capex == pytest.approx(high, rel=1e-3)


# ---------------------------------------------------------------------------
# Solver registry / get_solver
# ---------------------------------------------------------------------------


def test_registry_exposes_all_expected_labels() -> None:
    assert set(SOLVER_REGISTRY) == {
        "target_project_irr",
        "target_equity_irr",
        "dscr_covenant",
        "target_project_npv",
        "target_equity_npv",
        "multi_covenant_dscr_llcr",
        "min_capex_irr_floor",
    }


def test_get_solver_returns_correct_callable() -> None:
    assert get_solver("target_project_irr") is solve_for_tariff_given_irr
    assert get_solver("target_equity_irr") is solve_for_tariff_given_irr
    assert get_solver("dscr_covenant") is solve_for_max_debt_given_dscr
    assert get_solver("target_project_npv") is solve_for_tariff_given_npv
    assert get_solver("target_equity_npv") is solve_for_tariff_given_npv
    assert get_solver("multi_covenant_dscr_llcr") is solve_for_max_debt_multi_covenant
    assert get_solver("min_capex_irr_floor") is solve_for_min_capex_given_irr_floor


def test_get_solver_unknown_label_raises_keyerror_listing_options() -> None:
    with pytest.raises(KeyError) as exc_info:
        get_solver("totally_unknown")
    msg = str(exc_info.value)
    assert "No solver registered for 'totally_unknown'" in msg
    # Error lists available solvers, sorted.
    assert "dscr_covenant" in msg
    assert "target_project_irr" in msg


def test_get_solver_result_is_callable_and_solves() -> None:
    solver = get_solver("target_project_irr")
    tariff = solver(LENDER_CONFIG, None, target_irr=0.04, bounds=(40.0, 100.0))
    assert tariff == pytest.approx(40.0, abs=1e-6)


# ---------------------------------------------------------------------------
# _clone_overrides contract (via observable side effects)
# ---------------------------------------------------------------------------


def test_base_overrides_not_mutated_by_solver() -> None:
    """The solver shallow-clones overrides; the caller's dict is left intact."""
    base = {"sentinel": {"keep": 1}}
    solve_for_tariff_given_irr(
        LENDER_CONFIG, base, target_irr=0.04, bounds=(40.0, 100.0), max_iterations=2
    )
    assert base == {"sentinel": {"keep": 1}}
    # The solver injects "financial" into its *clone*, not the caller's dict.
    assert "financial" not in base


def test_none_overrides_supported() -> None:
    """base_overrides=None is a supported happy path (fresh dict internally)."""
    tariff = solve_for_tariff_given_irr(
        LENDER_CONFIG, None, target_irr=0.04, bounds=(40.0, 100.0)
    )
    assert tariff == pytest.approx(40.0, abs=1e-6)
