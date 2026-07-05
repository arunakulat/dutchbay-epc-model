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

import analytics.core.parameter_solvers as ps
from analytics.contracts_v14 import BreakevenResult
from analytics.core.parameter_solvers import (
    SOLVER_REGISTRY,
    get_solver,
    solve_for_max_debt_given_dscr,
    solve_for_max_debt_multi_covenant,
    solve_for_min_capex_given_irr_floor,
    solve_for_tariff_given_equity_irr,
    solve_for_tariff_given_irr,
    solve_for_tariff_given_npv,
    solve_tariff_breakeven,
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


def test_irr_solver_rejects_invalid_metric() -> None:
    """metric must be one of the IRR KPIs; an unknown metric fails loud up front."""
    with pytest.raises(ValueError, match="Invalid IRR metric"):
        solve_for_tariff_given_irr(
            LENDER_CONFIG, None, target_irr=0.20, metric="not_a_metric"
        )


# ---------------------------------------------------------------------------
# Equity-IRR tariff solver (#615): registry fix + generalized metric
# ---------------------------------------------------------------------------


def test_equity_irr_solver_converges_to_a_real_tariff() -> None:
    """The equity-IRR-pinned solver genuinely SOLVES the engine's equity_irr KPI: the achieved
    equity_irr at the returned tariff matches the target. On the lender case equity_irr spans
    ~0.13..0.40 over 40..100 LKR/kWh, so 0.20 is bracketed and interior."""
    target = 0.20
    tariff = solve_for_tariff_given_equity_irr(
        LENDER_CONFIG, None, target_irr=target, bounds=(40.0, 100.0), tolerance=1e-4
    )
    assert 40.0 < tariff < 100.0
    achieved = float(
        evaluate_with_overrides(
            base_config_path=LENDER_CONFIG,
            overrides={"tariff": {"lkr_per_kwh": tariff}},
        )["equity_irr"]
    )
    assert achieved == pytest.approx(target, abs=2e-3)


def test_equity_irr_solver_differs_from_project_irr_solver() -> None:
    """Solving for the same target against equity_irr vs project_irr yields DIFFERENT tariffs —
    proving the registry fix actually answers a different question. On the geared lender case
    equity_irr > project_irr at any given tariff (leverage lifts equity returns: at the
    project-solve tariff project_irr==0.20 while equity_irr~=0.269), so the equity solve reaches
    the same 0.20 target at a LOWER tariff. Either way the two tariffs differ; the assertion only
    pins that they are not equal.
    """
    target = 0.20
    tariff_project = solve_for_tariff_given_irr(
        LENDER_CONFIG,
        None,
        target_irr=target,
        metric="project_irr",
        bounds=(40.0, 100.0),
    )
    tariff_equity = solve_for_tariff_given_equity_irr(
        LENDER_CONFIG, None, target_irr=target, bounds=(40.0, 100.0)
    )
    assert tariff_equity != pytest.approx(tariff_project, abs=1.0)


def test_generalized_metric_matches_dedicated_equity_wrapper() -> None:
    """The generalized solver with metric='equity_irr' and the dedicated wrapper solve the
    identical problem (the wrapper is a thin pin), so they return the same tariff."""
    target = 0.20
    via_metric = solve_for_tariff_given_irr(
        LENDER_CONFIG,
        None,
        target_irr=target,
        metric="equity_irr",
        bounds=(40.0, 100.0),
    )
    via_wrapper = solve_for_tariff_given_equity_irr(
        LENDER_CONFIG, None, target_irr=target, bounds=(40.0, 100.0)
    )
    assert via_metric == pytest.approx(via_wrapper, abs=1e-9)


def test_equity_irr_solver_fails_loud_when_equity_irr_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CESSPIT: if the scenario computes no equity distribution the engine emits no equity_irr,
    and the equity solver must FAIL LOUD naming the missing KPI rather than silently solving a
    different one. Simulated by a gateway stub that omits equity_irr (all committed scenarios
    happen to compute it, so the miss is forced here)."""

    def _no_equity_eval(base_config_path: str, overrides=None, **_kw):  # type: ignore[no-untyped-def]
        return {"project_irr": 0.10, "project_npv": -1.0e7}

    monkeypatch.setattr(ps, "evaluate_with_overrides", _no_equity_eval)
    with pytest.raises(ValueError, match="does not.*expose"):
        solve_for_tariff_given_equity_irr(
            LENDER_CONFIG, None, target_irr=0.15, bounds=(40.0, 100.0)
        )


def test_project_irr_default_metric_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression pin: the default (no metric arg) still targets project_irr. A gateway stub
    that exposes ONLY project_irr solves fine by default, proving the default path never reads
    equity_irr."""

    def _project_only_eval(base_config_path: str, overrides=None, **_kw):  # type: ignore[no-untyped-def]
        tariff = float(overrides["tariff"]["lkr_per_kwh"]) if overrides else 0.0
        # Monotone-in-tariff synthetic project_irr with a root at tariff==70.
        return {"project_irr": (tariff - 70.0) / 100.0}

    monkeypatch.setattr(ps, "evaluate_with_overrides", _project_only_eval)
    tariff = solve_for_tariff_given_irr(
        LENDER_CONFIG, None, target_irr=0.0, bounds=(40.0, 100.0), tolerance=1e-4
    )
    assert tariff == pytest.approx(70.0, abs=0.1)


# ---------------------------------------------------------------------------
# Tariff-breakeven surface (#615): returns contracts_v14.BreakevenResult
# ---------------------------------------------------------------------------


def test_breakeven_npv_zero_converges_and_returns_result() -> None:
    """NPV=0 breakeven: over 10..60 LKR/kWh project_npv crosses zero (~$-149M..$+35M), so the
    breakeven is bracketed. The result is a BreakevenResult with status='converged' and a
    breakeven_value whose achieved project_npv is ~0 (within tolerance)."""
    result = solve_tariff_breakeven(
        LENDER_CONFIG,
        metric="project_npv",
        target_value=0.0,
        bounds=(10.0, 60.0),
        tolerance=1.0e5,
    )
    assert isinstance(result, BreakevenResult)
    assert result.status == "converged"
    assert result.variable == "tariff.lkr_per_kwh"
    assert result.target_metric == "project_npv"
    assert result.target_value == 0.0
    assert result.breakeven_value is not None and 10.0 < result.breakeven_value < 60.0
    achieved = float(
        evaluate_with_overrides(
            base_config_path=LENDER_CONFIG,
            overrides={"tariff": {"lkr_per_kwh": result.breakeven_value}},
        )["project_npv"]
    )
    assert achieved == pytest.approx(0.0, abs=1.0e5)


def test_breakeven_equity_irr_hurdle_converges() -> None:
    """IRR-hurdle breakeven: the tariff at which equity_irr equals a 0.15 hurdle. Returns a
    converged BreakevenResult whose achieved equity_irr matches the hurdle."""
    result = solve_tariff_breakeven(
        LENDER_CONFIG,
        metric="equity_irr",
        target_value=0.15,
        bounds=(40.0, 100.0),
        tolerance=1.0e-4,
    )
    assert result.status == "converged"
    assert result.target_metric == "equity_irr"
    assert result.breakeven_value is not None
    achieved = float(
        evaluate_with_overrides(
            base_config_path=LENDER_CONFIG,
            overrides={"tariff": {"lkr_per_kwh": result.breakeven_value}},
        )["equity_irr"]
    )
    assert achieved == pytest.approx(0.15, abs=2e-3)


def test_breakeven_unreachable_reports_unbracketed_not_raises() -> None:
    """When the target is not achievable over the bounds the breakeven surface does NOT raise a
    bare exception — it returns a BreakevenResult with status='unbracketed', breakeven_value
    None, and the searched bracket populated (so a batch sweep is safe). project_npv is positive
    (~$85M..$439M) over 40..100 LKR/kWh, so NPV=0 is unreachable there."""
    result = solve_tariff_breakeven(
        LENDER_CONFIG,
        metric="project_npv",
        target_value=0.0,
        bounds=(40.0, 100.0),
    )
    assert result.status == "unbracketed"
    assert result.breakeven_value is None
    assert result.bracket == (40.0, 100.0)
    assert "not achievable within bounds" in result.metadata.get("error", "")


def test_breakeven_missing_equity_irr_reports_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The equity-IRR breakeven surface translates the underlying fail-loud (missing equity_irr)
    into status='error' with the message captured — not a bare raise."""

    def _no_equity_eval(base_config_path: str, overrides=None, **_kw):  # type: ignore[no-untyped-def]
        return {"project_irr": 0.10, "project_npv": -1.0e7}

    monkeypatch.setattr(ps, "evaluate_with_overrides", _no_equity_eval)
    result = solve_tariff_breakeven(
        LENDER_CONFIG, metric="equity_irr", target_value=0.12, bounds=(40.0, 100.0)
    )
    assert result.status == "error"
    assert result.breakeven_value is None
    assert "equity_irr" in result.metadata.get("error", "")


def test_breakeven_rejects_invalid_metric() -> None:
    """A truly unknown metric is a programming error (not scenario infeasibility) and raises."""
    with pytest.raises(ValueError, match="Invalid breakeven metric"):
        solve_tariff_breakeven(LENDER_CONFIG, metric="not_a_metric")


def test_breakeven_iteration_starved_reports_max_iterations_not_converged() -> None:
    """HONEST convergence status (Fable blocker on #615). The underlying root-finders return the
    last midpoint on iteration exhaustion (they raise ONLY when no midpoint could be evaluated) and
    merely log a warning, so a naive wrapper would stamp status='converged' on a bound that misses
    the target by orders of magnitude. With a bracketed NPV=0 target but only 2 iterations and a
    $1 tolerance the solve CANNOT reach tolerance; the breakeven surface must report a NON-
    'converged' status with the true residual in metadata, not a false 'converged'.

    Exact repro from the review: project_npv target 0.0 over 10..60 LKR/kWh, tolerance=1.0,
    max_iterations=2. (#738 re-baseline note: the import-levy flip shifted the whole
    NPV(tariff) curve down and moved NPV@35 just below zero, so the two-midpoint
    bisection path flipped from 35 -> 22.5 (achieved ~-$59.8M) to 35 -> 47.5
    (achieved ~+$61.1M). The test's point is unchanged: the residual is ORDERS
    beyond the $1 tolerance and the status must say so honestly.)"""
    result = solve_tariff_breakeven(
        LENDER_CONFIG,
        metric="project_npv",
        target_value=0.0,
        bounds=(10.0, 60.0),
        tolerance=1.0,
        max_iterations=2,
    )
    assert isinstance(result, BreakevenResult)
    # status must NOT falsely claim convergence.
    assert result.status != "converged"
    assert result.status == "max_iterations"
    # No trustworthy breakeven value on a non-converged solve.
    assert result.breakeven_value is None
    # The residual is surfaced honestly and is far outside tolerance.
    assert "abs_residual" in result.metadata
    assert result.metadata["abs_residual"] > result.metadata["tolerance"]
    # The achieved value at the last bound is captured — a $10M+ miss either way
    # (the sign depends on which side of the root the exhausted bisection
    # stopped; see the #738 path-flip note in the docstring).
    assert abs(result.metadata["achieved"]) > 1.0e7
    assert result.bracket == (10.0, 60.0)


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
    # #615: target_equity_irr now resolves to the equity-IRR-pinned solver (it previously
    # mislabelled the project-IRR solver, silently solving the wrong KPI).
    assert get_solver("target_equity_irr") is solve_for_tariff_given_equity_irr
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
