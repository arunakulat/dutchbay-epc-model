#!/usr/bin/env python
"""Characterization tests for the dual-DSCR debt sizer behaviour.

These lock in *verified-correct* behaviour that previously looked like bugs when
sweeping ``Financing_Terms.debt_ratio`` (see the #30 optimization facade):

1. ``min_dscr`` sits at the sculpt target across gearings (DSCR-sculpted debt) —
   it is NOT mis-reported; the DSCR *series* spread (mean/max) does vary.
2. ``equity_npv`` is monotonic non-decreasing in gearing — cheaper leverage
   improves equity value smoothly, so the IRR solver / economics are sound.
   (NOTE: the equity_irr non-monotonicity / sub-target achieved DSCR first seen
   here was later traced to a real debt-service ALIGNMENT bug — period- vs
   annual-row indexing of debt service — and FIXED. The base case now holds DSCR
   at target with no covenant lockup; see test_no_phantom_covenant_lockup.)
3. ``Financing_Terms.interest_rate_nominal`` is a no-op on the achieved schedule
   (per-tranche rates govern; the top-level key only discounts the dual-DSCR
   capacity detail).

Context:
    Sprint 11 follow-up — diagnosed while building optimization_v14 (#30).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Gearings spanning the ratio-capped region (< ~0.625 solved) and the DSCR-bound
# region (>= ~0.625).
GEARINGS = [0.45, 0.50, 0.55, 0.60, 0.625, 0.70]


def _kpis(debt_ratio: float) -> dict:
    return evaluate_with_overrides(
        LENDER_CONFIG, overrides={"Financing_Terms.debt_ratio": debt_ratio}
    )


def test_no_phantom_covenant_lockup() -> None:
    """The sculpted lender case holds DSCR at target with NO covenant lockup.

    Guards the debt-service alignment fix: debt_service_total is period-indexed
    (offset by construction + bridge periods), and indexing it by annual-row index
    had spuriously collapsed the achieved DSCR ~3 years out of phase, locking 13
    years of equity distributions. Correct alignment leaves zero locked years.
    """
    kpis = evaluate_with_overrides(LENDER_CONFIG, overrides={})
    assert kpis["equity_covenant_locked_years"] == 0
    # The reported covenant DSCR is genuinely achieved (sculpted to target).
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)


def test_min_dscr_holds_sculpt_target_across_gearing() -> None:
    """Sculpted debt: min DSCR sits at the 1.30 target for every gearing."""
    for dr in GEARINGS:
        k = _kpis(dr)
        assert k["min_dscr"] == pytest.approx(1.30, abs=0.02), f"dr={dr}"
        # The DSCR *series* is not flat — the max exceeds the floor.
        assert k["dscr_max"] > k["min_dscr"] + 0.1, f"dr={dr}"


def test_equity_npv_monotonic_in_gearing() -> None:
    """Equity NPV improves (weakly) as gearing rises — economics are sound."""
    npvs = [_kpis(dr)["equity_npv"] for dr in GEARINGS]
    for lower, higher in zip(npvs, npvs[1:]):
        assert higher >= lower - 1.0, f"equity_npv not monotonic: {npvs}"


def test_equity_irr_finite_and_positive() -> None:
    """Equity IRR stays finite and positive across the gearing sweep."""
    for dr in GEARINGS:
        irr = _kpis(dr)["equity_irr"]
        assert 0.0 < irr < 0.5, f"dr={dr}: irr={irr}"


def test_interest_rate_nominal_is_noop_on_schedule() -> None:
    """Top-level interest_rate_nominal does not change the achieved equity IRR."""
    base = evaluate_with_overrides(LENDER_CONFIG, overrides={})["equity_irr"]
    bumped = evaluate_with_overrides(
        LENDER_CONFIG, overrides={"Financing_Terms.interest_rate_nominal": 0.12}
    )["equity_irr"]
    assert base == pytest.approx(bumped, abs=1e-9)
