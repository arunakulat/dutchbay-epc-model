#!/usr/bin/env python
"""Characterization tests for the dual-DSCR debt sizer behaviour.

These lock in *verified-correct* behaviour that previously looked like bugs when
sweeping ``Financing_Terms.debt_ratio`` (see the #30 optimization facade):

1. ``min_dscr`` sits at the sculpt target across gearings (DSCR-sculpted debt) —
   it is NOT mis-reported; the DSCR *series* spread (mean/max) does vary.
2. ``equity_npv`` is monotonic non-decreasing in gearing — but this is an equity
   *sizing* artifact (higher gearing → less equity invested → smaller absolute
   negative NPV), NOT evidence that more leverage improves return quality. Equity
   *IRR* actually FALLS with gearing here: post-M3e degradation re-baseline the
   project return (~5.05%) is BELOW the cost of debt (~7.63%), so every turn of
   leverage is negative carry and the IRR sweep crosses from positive to negative.
   (NOTE: the equity_irr non-monotonicity / sub-target achieved DSCR first seen
   here was later traced to a real debt-service ALIGNMENT bug — period- vs
   annual-row indexing of debt service — and FIXED. The base case now holds DSCR
   at target with no covenant lockup; see test_no_phantom_covenant_lockup.)
   SEPARATELY: the sculpt leaves a ~36% balloon at maturity; how the equity
   waterfall resolves it is config-selectable — see test_balloon_treatment.py.
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


def test_equity_irr_finite_and_falls_with_gearing() -> None:
    """Equity IRR stays finite, falls monotonically with gearing, and crosses zero.

    Post-M3e degradation re-baseline (0.5%/yr aging), the project IRR (~5.05%) sits
    BELOW the cost of debt (~7.63%), so leverage is value-destructive: each extra
    turn of gearing dilutes equity return (negative carry). The sweep therefore runs
    strictly downhill and crosses zero — positive to sponsors at low gearing (~3.3%
    at 0.45), negative at the DSCR-bound high end (~-2.5% at 0.70). This is the honest
    economics, NOT a sign that more leverage helps (cf. the equity_npv sizing artifact).
    """
    import math

    irrs = [_kpis(dr)["equity_irr"] for dr in GEARINGS]
    for dr, irr in zip(GEARINGS, irrs):
        assert math.isfinite(irr) and -0.5 < irr < 0.5, f"dr={dr}: irr={irr}"
    # Monotonically falling as gearing rises (value-destructive leverage).
    for lower, higher in zip(irrs, irrs[1:]):
        assert higher < lower, f"equity_irr not strictly falling with gearing: {irrs}"
    # The sweep brackets zero: positive at low gearing, negative at high gearing.
    assert irrs[0] > 0.0 > irrs[-1], f"sweep does not cross zero: {irrs}"


def test_interest_rate_nominal_is_noop_on_schedule() -> None:
    """Top-level interest_rate_nominal does not change the achieved equity IRR."""
    base = evaluate_with_overrides(LENDER_CONFIG, overrides={})["equity_irr"]
    bumped = evaluate_with_overrides(
        LENDER_CONFIG, overrides={"Financing_Terms.interest_rate_nominal": 0.12}
    )["equity_irr"]
    assert base == pytest.approx(bumped, abs=1e-9)
