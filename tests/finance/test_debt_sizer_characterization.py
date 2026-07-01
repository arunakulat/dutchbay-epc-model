#!/usr/bin/env python
"""Characterization tests for the dual-DSCR debt sizer behaviour.

These lock in *verified-correct* behaviour that previously looked like bugs when
sweeping ``Financing_Terms.debt_ratio`` (see the #30 optimization facade):

1. ``min_dscr`` sits at the sculpt target across gearings (DSCR-sculpted debt) —
   it is NOT mis-reported; the DSCR *series* spread (mean/max) does vary.
2. ``equity_npv`` is monotonic non-decreasing in gearing — but this is an equity
   *sizing* artifact (higher gearing → less equity invested → smaller absolute
   negative NPV), NOT evidence that more leverage improves return quality. Equity
   *IRR* actually FALLS with gearing here: after the 5.9% FX-drift re-baseline the
   project return (~2.75%; was ~5.05% at the old 3% drift) is BELOW the cost of debt
   (~7.63%), so every turn of leverage is negative carry and the IRR sweep is negative.
   (NOTE: the equity_irr non-monotonicity / sub-target achieved DSCR first seen
   here was later traced to a real debt-service ALIGNMENT bug — period- vs
   annual-row indexing of debt service — and FIXED. The base case now holds DSCR
   at target with no covenant lockup; see test_no_phantom_covenant_lockup.)
   SEPARATELY: the sculpt leaves a ~58% balloon at maturity (was ~36% at the old 3%
   drift; the weaker CFADS amortises less); how the equity waterfall resolves it is
   config-selectable — see test_balloon_treatment.py.
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

# Gearings spanning the sub-cap sculpt region (< ~0.45 DSCR-solved) and the clamped
# region (>= ~0.45). PR B's UIP LKR debt rate (13.39%) dropped the DSCR-solved cap to ~0.45,
# so the sweep now starts BELOW the cap (0.35/0.40) to retain genuinely sub-cap points.
GEARINGS = [0.35, 0.40, 0.45, 0.50, 0.60, 0.70]


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


def test_equity_irr_value_destructive_with_gearing_and_plateaus_at_the_dscr_cap() -> (
    None
):
    """Leverage is value-destructive and equity IRR plateaus at the DSCR-solved cap.

    The project return (~2.7%) sits well BELOW the cost of debt (the PR-B UIP LKR rate of
    13.39% widened the gap), so leverage is value-destructive and equity IRR is NEGATIVE.
    The dual_dscr sizer caps the ACTUAL gearing at ~0.45, so every requested gearing at or
    above that (0.45/0.50/0.60/0.70) clamps to the same solved structure and equity IRR
    PLATEAUS at the canonical ~-0.0486. The least-levered (sub-cap) point (0.35) carries a
    HIGHER equity IRR than the clamped plateau — i.e. more leverage erodes the return
    end-to-end. NOTE: below the cap the response is no longer strictly monotonic (the
    negative project IRR + the DSCR sculpt/balloon interaction make it U-shaped); we therefore
    assert the value-destruction (lowest gearing beats the levered plateau) and the supra-cap
    clamp, not a strict step-by-step decline.
    """
    import math

    irrs = [
        _kpis(dr)["equity_irr"] for dr in GEARINGS
    ]  # [0.35,0.40,0.45,0.50,0.60,0.70]
    for dr, irr in zip(GEARINGS, irrs):
        assert math.isfinite(irr) and -0.5 < irr < 0.5, f"dr={dr}: irr={irr}"
    # Above the ~0.45 DSCR-solved cap (PR-B's UIP LKR debt rate 13.39% de-levered the deal
    # from ~0.588) the sizer clamps to the solved gearing -> equity IRR plateaus at the
    # canonical clamped value (now -0.0486 after the PR-B debt-rate re-baseline).
    plateau = irrs[3:]
    assert (
        max(plateau) - min(plateau) < 1e-6
    ), f"supra-cap equity_irr not flat (clamped): {plateau}"
    assert plateau[0] == pytest.approx(-0.0486, abs=0.002)
    # Value-destructive leverage: the least-levered point beats the clamped high-gearing plateau,
    # and the gap is material.
    assert irrs[0] > plateau[0], f"leverage not value-destructive: {irrs}"
    assert irrs[0] - plateau[0] > 0.002, f"gearing barely moves equity_irr: {irrs}"


def test_interest_rate_nominal_is_noop_on_schedule() -> None:
    """Top-level interest_rate_nominal does not change the achieved equity IRR."""
    base = evaluate_with_overrides(LENDER_CONFIG, overrides={})["equity_irr"]
    bumped = evaluate_with_overrides(
        LENDER_CONFIG, overrides={"Financing_Terms.interest_rate_nominal": 0.12}
    )["equity_irr"]
    assert base == pytest.approx(bumped, abs=1e-9)
