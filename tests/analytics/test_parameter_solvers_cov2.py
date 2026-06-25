#!/usr/bin/env python
"""Coverage-completion tests for analytics.core.parameter_solvers.

Companion to test_parameter_solvers.py. That file exercises the happy-path
bisection control flow and the documented input-validation raises; this file
fills the remaining branches that the first file does not reach:

  - the non-convergence WARNING path of each bisection solver (loop exhausts
    ``max_iterations`` without ever narrowing the bracket below ``tolerance``,
    so the solver logs a warning and returns ``last_good_mid``), and
  - the hard "no valid midpoint" ValueError of each solver (``max_iterations=0``
    means the loop body never runs, ``last_good_mid`` stays ``None``), and
  - the NPV solver's ``npv_delta < 0`` bracket-update branch (target NPV strictly
    above the achieved, invariant NPV).

House style mirrors the sibling file: load the canonical lender case by
REPO_ROOT-relative path and drive the LIVE finance engine — no mocks, no magic
KPI numbers. The override keys these solvers sweep
("financial.tariff_lkr_per_kwh", "financial.debt_amount_usd",
"project.capex_usd") are not part of this config's schema, so the targeted KPI
is invariant across the bracket. That makes the bisection direction fully
deterministic, which is what lets these tests pin the landing boundary and the
warning-vs-raise outcome from first principles.

Engine constants for scenarios/dutchbay_lendercase_2025Q4.yaml (verified live):
    project_irr ~= 0.0543, project_npv ~= -3.19e7 USD,
    dscr_min == 1.30, llcr ~= 1.13.

Non-convergence-warning construction (load-bearing):
    For the debt/capex solvers the loop stops early only when
    ``(high - low) < tolerance``. Each iteration halves the bracket, so after k
    iterations the bracket width is ``(high0 - low0) / 2**k``. Picking a
    ``tolerance`` far smaller than that residual width (here effectively zero)
    guarantees the early-return convergence check NEVER fires; the loop instead
    runs to ``max_iterations`` with ``last_good_mid`` set on the first pass, so
    the solver takes the warning branch and returns that last midpoint. This is
    a genuine non-convergence (the swept parameter has no effect on the KPI, so
    the bracket can never satisfy a positive covenant slack to machine zero).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from analytics.core.parameter_solvers import (
    solve_for_max_debt_given_dscr,
    solve_for_max_debt_multi_covenant,
    solve_for_min_capex_given_irr_floor,
    solve_for_tariff_given_npv,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Verified-live engine constants for the lender case (see module docstring).
BASE_PROJECT_NPV = -3.19e7


# ---------------------------------------------------------------------------
# DSCR max-debt solver: non-convergence warning + hard raise
# ---------------------------------------------------------------------------


def test_dscr_solver_fails_loud_under_dual_dscr_sizing() -> None:
    """The single-covenant max-debt solver sweeps an absolute debt amount the v14 engine
    never reads (debt is auto-sized via dual_dscr), so the entry self-check fails loud rather
    than running the (now guarded-unreachable) bisection — its old non-convergence / zero-
    iteration branches can no longer be reached on a real scenario (Wave-2 fix)."""
    with pytest.raises(ValueError, match="does not move dscr_min"):
        solve_for_max_debt_given_dscr(
            LENDER_CONFIG, None, target_dscr=1.10, bounds=(1.0e6, 1.0e9), tolerance=0.0,
        )


# ---------------------------------------------------------------------------
# NPV tariff solver: target-above-achieved branch + hard raise
# ---------------------------------------------------------------------------


def test_npv_solver_target_above_achieved_collapses_to_high_bound() -> None:
    """Target NPV above achieved => npv_delta < 0 each step => bracket -> high.

    project_npv (~ -3.19e7) is invariant for this config. Asking for a target far
    above it makes ``achieved - target`` strictly negative on every probe, so the
    solver repeatedly executes ``low = mid`` and the bracket collapses to the high
    bound. (This exercises the ``npv_delta < 0`` branch the sibling file's
    below-target case does not reach.)
    """
    low, high = 40.0, 100.0
    tariff = solve_for_tariff_given_npv(
        LENDER_CONFIG,
        None,
        target_npv=5.0e8,  # well above the achieved (negative) NPV
        metric="project_npv",
        bounds=(low, high),
    )
    assert low <= tariff <= high
    assert tariff == pytest.approx(high, abs=1e-6)


def test_npv_solver_zero_iterations_raises_no_midpoint() -> None:
    """max_iterations=0 leaves last_good_mid None -> hard ValueError raise."""
    with pytest.raises(ValueError, match="failed to converge"):
        solve_for_tariff_given_npv(
            LENDER_CONFIG,
            None,
            target_npv=BASE_PROJECT_NPV,
            metric="project_npv",
            bounds=(40.0, 100.0),
            max_iterations=0,
        )


# ---------------------------------------------------------------------------
# Multi-covenant (DSCR + LLCR) solver: non-convergence warning + hard raise
# ---------------------------------------------------------------------------


def test_multi_covenant_fails_loud_under_dual_dscr_sizing() -> None:
    """Same as the single-covenant solver: the absolute debt-amount sweep is not a live
    engine input under dual_dscr sizing, so the entry self-check fails loud (the old
    non-convergence / zero-iteration bisection branches are now guarded-unreachable)."""
    with pytest.raises(ValueError, match="does not move dscr_min"):
        solve_for_max_debt_multi_covenant(
            LENDER_CONFIG, None, target_dscr=1.10, target_llcr=1.00,
            bounds=(1.0e6, 1.0e9), tolerance=0.0,
        )


# ---------------------------------------------------------------------------
# Capex optimizer: non-convergence warning + hard raise
# ---------------------------------------------------------------------------


def test_capex_optimizer_non_convergence_warns_and_returns_last_midpoint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Zero tolerance + finite cap exhausts the loop on the warning branch.

    IRR (~0.0543) clears the floor (0.04) every step, so ``high = mid`` each pass;
    with tolerance=0 the bracket never satisfies ``(high - low) < tolerance``, so
    the optimizer warns and returns the last midpoint inside the bracket.
    """
    low, high = 100.0e6, 500.0e6
    with caplog.at_level(logging.WARNING, logger="analytics.core.parameter_solvers"):
        capex = solve_for_min_capex_given_irr_floor(
            LENDER_CONFIG,
            None,
            irr_floor=0.04,
            bounds=(low, high),
            tolerance=0.0,
            max_iterations=3,
        )
    assert low <= capex <= high
    assert "did not fully converge" in caplog.text
    # IRR clears the floor, so capex is driven downward but stays interior.
    assert capex < high


def test_capex_optimizer_zero_iterations_raises_no_midpoint() -> None:
    """max_iterations=0 -> last_good_mid never set -> hard ValueError."""
    with pytest.raises(ValueError, match="failed to converge"):
        solve_for_min_capex_given_irr_floor(
            LENDER_CONFIG,
            None,
            irr_floor=0.04,
            bounds=(100.0e6, 500.0e6),
            max_iterations=0,
        )
