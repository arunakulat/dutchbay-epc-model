#!/usr/bin/env python
"""Tests for config-selectable balloon treatment in the equity waterfall.

The dual-DSCR sculpt over a fixed tenor leaves an unamortised BALLOON at
maturity. Previously the equity waterfall ignored it — equity collected 100% of
post-maturity CFADS as a free pass, overstating equity IRR by ~5.8pp on the
lender case. These tests lock in the verified-correct treatments:

    legacy_ignore  — historical free pass (reproduces pre-fix numbers).
    cash_sweep     — trap post-maturity CFADS to retire the balloon (default).
    refinance      — refinance the balloon at a penalty rate; service it.
    bullet         — single lump repayment at maturity.
    amortize       — resize debt DOWN so the sculpt fully amortises (no balloon).

Ground truth: the lender case carries a ~42% balloon ($42.5M on $100.1M debt),
which breaches constraints.max_balloon_pct (10%). (Equity IRRs are at the corrected
FX 333.79, the ERA5-fitted Weibull re-baseline, the 2026-06 debt-service-orphan
fix / audit finding 2.1 AND the M3e degradation re-baseline (0.005 -> 0.5, honest
0.5%/yr aging) — markedly lower than the prior numbers; lower CFADS also enlarges
the structural balloon 36% -> 42%. The Wave-1 equity-waterfall fix then RELEASES the DSRA
(and any held-back / un-swept SPV cash) to the sponsor at maturity instead of destroying
it, lifting the canonical cash_sweep equity IRR ~-2.5% -> ~-0.8%.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

TREATMENTS = ("legacy_ignore", "cash_sweep", "refinance", "bullet", "amortize")


def _full(treatment: str) -> dict:
    return evaluate_with_overrides(
        LENDER_CONFIG,
        overrides={"Financing_Terms.balloon_treatment": treatment},
        return_full_result=True,
    )


@pytest.fixture(scope="module")
def results() -> dict:
    return {t: _full(t) for t in TREATMENTS}


def test_lender_case_carries_a_covenant_breaching_balloon(results: dict) -> None:
    """The structural balloon is ~38% of debt and breaches max_balloon_pct (10%).

    Wave-1 fix: balloon_pct now divides the (IDC-inclusive) balloon_remaining by the
    IDC-inclusive amortizing principal (sum of principal_after_idc, ~$111.9M), not the
    pre-IDC debt_total (~$100.1M) — a consistent base. The $ balloon is unchanged
    ($42.48M); only the reported fraction corrects from 0.424 to 0.380.
    """
    dr = results["cash_sweep"]["debt_result"]
    assert dr["balloon_remaining"] == pytest.approx(42_475_853, rel=0.02)
    assert dr["balloon_pct"] == pytest.approx(0.380, abs=0.01)
    assert dr["balloon_covenant_breach"] is True
    assert dr["max_balloon_pct"] == pytest.approx(0.10)


def test_legacy_ignore_reproduces_free_pass(results: dict) -> None:
    """legacy_ignore preserves the (inflated) free-pass equity IRR and never services.

    The free-pass IRR also benefits from the Wave-1 equity-waterfall fix (the DSRA is now
    released to the sponsor at maturity), lifting it 0.0334 -> 0.0418.
    """
    kpis = results["legacy_ignore"]["kpis"]
    dr = results["legacy_ignore"]["debt_result"]
    assert kpis["equity_irr"] == pytest.approx(0.0355, abs=0.002)
    # No servicing: residual equals the structural balloon, resolution all zero.
    assert dr["balloon_residual"] == pytest.approx(dr["balloon_remaining"], rel=1e-6)
    assert sum(dr["balloon_resolution"]) == pytest.approx(0.0, abs=1.0)


def test_cash_sweep_clears_balloon_and_lowers_equity_irr(results: dict) -> None:
    """cash_sweep fully retires the balloon and is materially below the free pass."""
    legacy = results["legacy_ignore"]["kpis"]["equity_irr"]
    sweep = results["cash_sweep"]["kpis"]["equity_irr"]
    dr = results["cash_sweep"]["debt_result"]
    assert dr["balloon_residual"] == pytest.approx(0.0, abs=1.0)
    # Sweep cash conserves: total swept ≈ the structural balloon.
    assert sum(dr["balloon_resolution"]) == pytest.approx(
        dr["balloon_remaining"], rel=0.02
    )
    assert sweep < legacy - 0.03  # ~5.8pp lower, honest
    # Wave-1 equity-waterfall fix releases the DSRA to the sponsor at maturity: -0.0247 -> -0.0082.
    assert sweep == pytest.approx(-0.0082, abs=0.003)


def test_refinance_is_lowest_due_to_penalty_rate(results: dict) -> None:
    """Refinancing the balloon at rate+premium is the most punitive treatment."""
    sweep = results["cash_sweep"]["kpis"]["equity_irr"]
    refi = results["refinance"]["kpis"]["equity_irr"]
    assert refi <= sweep
    # Re-baselined with the equity-waterfall DSRA-release fix (was -0.0436).
    assert refi == pytest.approx(-0.0210, abs=0.004)


def test_amortize_removes_balloon_by_resizing_debt(results: dict) -> None:
    """amortize sizes debt DOWN until the sculpt fully amortises (no balloon)."""
    amort = results["amortize"]["debt_result"]
    legacy = results["legacy_ignore"]["debt_result"]
    assert amort["balloon_remaining"] == pytest.approx(0.0, abs=2.0)
    assert amort["balloon_covenant_breach"] is False
    # Less leverage than the balloon-laden structure.
    assert amort["debt_total"] < legacy["debt_total"] - 1_000_000
    # Still sculpted to the DSCR target.
    assert amort["min_dscr"] == pytest.approx(1.30, abs=0.02)


def test_min_dscr_invariant_across_treatments(results: dict) -> None:
    """Balloon resolution is senior to equity but NOT scheduled service: DSCR is unchanged.

    (amortize excepted — it changes the debt amount, not just the waterfall.)
    """
    base = results["legacy_ignore"]["kpis"]["min_dscr"]
    for t in ("cash_sweep", "refinance", "bullet"):
        assert results[t]["kpis"]["min_dscr"] == pytest.approx(base, abs=1e-6)


def test_unknown_treatment_falls_back_to_default(results: dict) -> None:
    """An unrecognised treatment degrades to the cash_sweep default, not a crash."""
    bogus = _full("nonsense_treatment")
    assert bogus["debt_result"]["balloon_treatment"] == "cash_sweep"
    assert bogus["kpis"]["equity_irr"] == pytest.approx(
        results["cash_sweep"]["kpis"]["equity_irr"], rel=1e-6
    )
