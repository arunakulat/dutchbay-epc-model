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
    """The sculpted lender case has no lockup after the COD-aligned correction.

    Guards the debt-service alignment fix: debt_service_total is period-indexed
    (offset by construction + bridge periods), and indexing it by annual-row index
    had spuriously collapsed the achieved DSCR ~3 years out of phase, locking 13
    years of equity distributions. The corrected period mapping plus F5-01's
    COD-aligned operating FX now leave every annual covenant row at or above the
    1.30 lockup threshold; the phase bug this guards would lock about 13 years.
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


def test_equity_irr_stays_negative_and_plateaus_at_the_dscr_cap() -> None:
    """Equity IRR stays negative and plateaus at the DSCR-solved cap.

    The project return remains below the cost of debt and equity IRR is negative.
    The dual_dscr sizer caps actual gearing near 0.355, so higher requests clamp to
    the same structure and the canonical -7.85% equity IRR. Below the cap the response
    is not strictly monotonic: the negative project
    IRR + DSCR sculpt/balloon interaction make it U-shaped, and F5-01 moves the 0.35
    point below the clamped plateau. We therefore assert the negative economics, the
    observed U-turn and the supra-cap clamp rather than an invalid monotonic claim.
    """
    import math

    irrs = [
        _kpis(dr)["equity_irr"] for dr in GEARINGS
    ]  # [0.35,0.40,0.45,0.50,0.60,0.70]
    for dr, irr in zip(GEARINGS, irrs):
        assert math.isfinite(irr) and -0.5 < irr < 0.5, f"dr={dr}: irr={irr}"
    # Above the F5-01 DSCR-solved cap (~0.355; ~0.41 after #738, 0.4275 post-#737,
    # ~0.45 post-PR-B, ~0.588 before) the sizer
    # clamps to the solved gearing -> equity IRR plateaus at the canonical clamped value
    # (-0.0785 after the F5-01 re-baseline; requested 0.45 also clamps now, so the
    # plateau slice below is conservative).
    plateau = irrs[3:]
    assert (
        max(plateau) - min(plateau) < 1e-6
    ), f"supra-cap equity_irr not flat (clamped): {plateau}"
    assert plateau[0] == pytest.approx(-0.0785, abs=0.002)
    assert all(irr < 0.0 for irr in irrs), f"equity unexpectedly profitable: {irrs}"
    # The pre-cap 0.35 point is the local trough and the cap/balloon interaction then
    # turns slightly upward before flattening.
    assert irrs[0] < plateau[0], f"expected pre-cap U-turn missing: {irrs}"
    assert plateau[0] - irrs[0] > 0.001, f"gearing barely moves equity_irr: {irrs}"


def test_interest_rate_nominal_is_noop_on_schedule() -> None:
    """Top-level interest_rate_nominal does not change the achieved equity IRR."""
    base = evaluate_with_overrides(LENDER_CONFIG, overrides={})["equity_irr"]
    bumped = evaluate_with_overrides(
        LENDER_CONFIG, overrides={"Financing_Terms.interest_rate_nominal": 0.12}
    )["equity_irr"]
    assert base == pytest.approx(bumped, abs=1e-9)
