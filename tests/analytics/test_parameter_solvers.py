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

REGRESSION PIN (Sprint 16 P3-2 multi-covenant solver; bug fixed in #307):
    solve_for_max_debt_multi_covenant once read kpis["llcr_min"], a key the
    engine never produces (it emits "llcr"), so any positive LLCR covenant was
    never satisfied and debt was driven to the lower bound regardless of the true
    (DSCR/LLCR) slack. It now reads kpis.get("llcr", 0.0); the
    binding-but-satisfiable LLCR test below pins the corrected behaviour (there
    is no xfail — the defect is closed).
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
from analytics.evaluate_scenario import evaluate_with_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Engine constants for the lender case (see module docstring).
BASE_PROJECT_IRR = 0.0543
BASE_PROJECT_NPV = -3.19e7
BASE_DSCR = 1.30


# ---------------------------------------------------------------------------
# IRR-based tariff solver
# ---------------------------------------------------------------------------


def test_irr_solver_target_below_range_raises() -> None:
    """A target IRR below the achievable range over [low, high] is not bracketed: the solver
    fails loud (round-2 fix) instead of silently returning the low bound. At tariff 40-100
    LKR/kWh projIRR is ~0.137-0.298, so a 0.04 target is unreachable in-range."""
    with pytest.raises(ValueError, match="not achievable within bounds"):
        solve_for_tariff_given_irr(
            LENDER_CONFIG, None, target_irr=0.04, bounds=(40.0, 100.0)
        )


def test_irr_solver_target_above_range_raises() -> None:
    """A target IRR above what even the max tariff achieves is not bracketed: fail loud
    (round-2 fix) rather than silently returning the high bound. projIRR tops out ~0.298
    at tariff 100, so a 0.40 target is unreachable in-range."""
    with pytest.raises(ValueError, match="not achievable within bounds"):
        solve_for_tariff_given_irr(
            LENDER_CONFIG, None, target_irr=0.40, bounds=(40.0, 100.0)
        )


def test_irr_solver_converges_to_a_real_tariff_for_reachable_target() -> None:
    """A reachable target is genuinely SOLVED: the achieved projIRR at the returned tariff
    matches the target (the override now drives the live engine, not a dead path)."""
    target = 0.20  # within the ~0.137..0.298 reachable band
    tariff = solve_for_tariff_given_irr(
        LENDER_CONFIG, None, target_irr=target, bounds=(40.0, 100.0), tolerance=1e-4
    )
    assert 40.0 < tariff < 100.0  # interior solution, not a bound
    achieved = float(
        evaluate_with_overrides(
            base_config_path=LENDER_CONFIG,
            overrides={"tariff": {"lkr_per_kwh": tariff}},
        )["project_irr"]
    )
    assert achieved == pytest.approx(target, abs=2e-3)


def test_irr_solver_rejects_non_bisection_method() -> None:
    with pytest.raises(ValueError, match="Unsupported solver method"):
        solve_for_tariff_given_irr(
            LENDER_CONFIG, None, target_irr=0.10, method="gradient"
        )


def test_irr_solver_zero_iterations_raises_no_midpoint() -> None:
    """With no iterations the loop never sets last_good_mid -> hard ValueError."""
    with pytest.raises(ValueError, match="failed to converge"):
        # target 0.20 is bracketed by [irr(40), irr(100)] so the precheck passes; with 0
        # iterations the loop never sets last_good_mid -> hard ValueError.
        solve_for_tariff_given_irr(
            LENDER_CONFIG, None, target_irr=0.20, bounds=(40.0, 100.0), max_iterations=0
        )


# ---------------------------------------------------------------------------
# DSCR-based max-debt solver
# ---------------------------------------------------------------------------


def test_dscr_solver_fails_loud_under_dual_dscr_sizing() -> None:
    """The v14 engine sizes debt itself (dual_dscr auto-solves gearing to target DSCR), so
    there is no absolute debt-amount input: sweeping financial.debt_amount_usd does not move
    dscr_min. The solver must FAIL LOUD (Wave-2 fix) rather than silently returning a bound —
    "max debt given DSCR" IS the engine's solved gearing."""
    with pytest.raises(ValueError, match="does not move dscr_min"):
        solve_for_max_debt_given_dscr(
            LENDER_CONFIG,
            None,
            target_dscr=1.10,
            bounds=(1.0e6, 1.0e9),
            tolerance=1000.0,
        )


# ---------------------------------------------------------------------------
# NPV-based tariff solver
# ---------------------------------------------------------------------------


def test_npv_solver_project_metric_converges_to_real_tariff() -> None:
    """A reachable project_npv target is genuinely solved (live tariff path): the achieved
    project_npv at the returned tariff matches the target."""
    target = 200.0e6  # within the reachable ~85M..439M band over 40..100 LKR/kWh
    tariff = solve_for_tariff_given_npv(
        LENDER_CONFIG,
        None,
        target_npv=target,
        metric="project_npv",
        bounds=(40.0, 100.0),
        tolerance=1.0e5,
    )
    assert 40.0 < tariff < 100.0
    achieved = float(
        evaluate_with_overrides(
            base_config_path=LENDER_CONFIG,
            overrides={"tariff": {"lkr_per_kwh": tariff}},
        )["project_npv"]
    )
    assert achieved == pytest.approx(target, abs=2.0e6)


def test_npv_solver_equity_metric_is_accepted_and_live() -> None:
    """equity_npv is a valid metric and the override is live (else the self-check raises);
    the solver returns a tariff within bounds."""
    tariff = solve_for_tariff_given_npv(
        LENDER_CONFIG,
        None,
        target_npv=100.0e6,
        metric="equity_npv",
        bounds=(40.0, 100.0),
        tolerance=1.0e6,
    )
    assert (
        40.0 <= tariff <= 100.0
    )  # target 100M is within the ~54M..365M reachable band


def test_npv_solver_unreachable_target_raises() -> None:
    """An unreachable project_npv target is not bracketed over [low, high], so the solver
    fails loud (round-2 fix) instead of silently returning a bound. project_npv is positive
    (~85M..439M) over 40-100 LKR/kWh, so a -1e9 target is unreachable in-range."""
    with pytest.raises(ValueError, match="not achievable within bounds"):
        solve_for_tariff_given_npv(
            LENDER_CONFIG,
            None,
            target_npv=-1.0e9,
            metric="project_npv",
            bounds=(40.0, 100.0),
        )


def test_npv_solver_rejects_invalid_metric() -> None:
    with pytest.raises(ValueError, match="Invalid NPV metric"):
        solve_for_tariff_given_npv(
            LENDER_CONFIG, None, target_npv=0.0, metric="not_a_metric"
        )


# ---------------------------------------------------------------------------
# Multi-covenant (DSCR + LLCR) solver
# ---------------------------------------------------------------------------


def test_multi_covenant_fails_loud_under_dual_dscr_sizing() -> None:
    """Like the single-covenant debt solver, the multi-covenant solver sweeps an absolute
    debt amount the engine never reads (debt is auto-sized via dual_dscr). The self-check
    fails loud rather than collapsing to a meaningless bound (Wave-2 fix)."""
    with pytest.raises(ValueError, match="does not move dscr_min"):
        solve_for_max_debt_multi_covenant(
            LENDER_CONFIG,
            None,
            target_dscr=1.10,
            target_llcr=1.50,
            bounds=(1.0e6, 1.0e9),
            tolerance=1000.0,
        )


# ---------------------------------------------------------------------------
# Capex optimizer (minimize capex subject to IRR floor)
# ---------------------------------------------------------------------------


def test_min_capex_solves_breakeven_capex_at_the_floor() -> None:
    """Returns the MAX capex at which projIRR still meets the floor (breakeven). With the
    live capex path + the corrected bisection direction (IRR falls as capex rises), the
    achieved IRR at the returned capex equals the floor."""
    low, high = 100.0e6, 500.0e6
    capex = solve_for_min_capex_given_irr_floor(
        LENDER_CONFIG, None, irr_floor=0.04, bounds=(low, high), tolerance=10_000.0
    )
    assert low < capex < high  # interior breakeven, not a bound
    achieved = float(
        evaluate_with_overrides(
            base_config_path=LENDER_CONFIG, overrides={"capex": {"usd_total": capex}}
        )["project_irr"]
    )
    assert achieved == pytest.approx(0.04, abs=1e-3)


def test_min_capex_floor_unreachable_raises() -> None:
    """A floor above the IRR achievable even at the minimum capex is not bracketed: the
    solver fails loud (round-3 fix, extending the round-2 bracketing guard to the capex
    solver) instead of silently collapsing to the low bound. The cheapest project here
    (~$100M) clears well under 20% IRR, so a 0.20 floor is unreachable in-range."""
    with pytest.raises(ValueError, match="not achievable within bounds"):
        solve_for_min_capex_given_irr_floor(
            LENDER_CONFIG,
            None,
            irr_floor=0.20,
            bounds=(100.0e6, 500.0e6),
            tolerance=10_000.0,
        )


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
    tariff = solver(LENDER_CONFIG, None, target_irr=0.20, bounds=(40.0, 100.0))
    assert 40.0 < tariff < 100.0  # bracketed target -> interior solution


# ---------------------------------------------------------------------------
# _clone_overrides contract (via observable side effects)
# ---------------------------------------------------------------------------


def test_base_overrides_not_mutated_by_solver() -> None:
    """The solver shallow-clones overrides; the caller's dict is left intact."""
    base = {"sentinel": {"keep": 1}}
    solve_for_tariff_given_irr(
        LENDER_CONFIG, base, target_irr=0.20, bounds=(40.0, 100.0), max_iterations=2
    )
    assert base == {"sentinel": {"keep": 1}}
    # The solver injects "financial" into its *clone*, not the caller's dict.
    assert "financial" not in base


def test_none_overrides_supported() -> None:
    """base_overrides=None is a supported happy path (fresh dict internally)."""
    tariff = solve_for_tariff_given_irr(
        LENDER_CONFIG, None, target_irr=0.20, bounds=(40.0, 100.0)
    )
    assert 40.0 < tariff < 100.0
