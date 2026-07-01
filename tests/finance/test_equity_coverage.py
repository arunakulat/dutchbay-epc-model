#!/usr/bin/env python
"""Coverage-raising tests for finance.equity_v14.

These tests exercise every public helper in the equity-metrics module with
deterministic, first-principles assertions. No economic magic number is
hardcoded: every expected value is derived inside the test from the synthetic
inputs (conservation / sign / monotonicity / ratio identities) or computed via
the module's own delegated IRR/NPV helpers. Source files are never modified.

The defensive exception/NaN branches inside the IRR and NPV wrappers are
covered by monkeypatching the *delegated* primitives (``_irr`` / ``_npv_wrapper``)
to raise or return a non-finite value -- the module's documented contract is to
swallow those into ``None`` -- rather than by fabricating a result.
"""

from __future__ import annotations

import math
from typing import List

import pytest

from analytics.contracts_v14 import EquityPerformance
from finance import equity_v14 as mod
from finance.equity_v14 import (
    LEGACY_EQUITY_DISCOUNT_RATE,
    EquityCashflowSummary,
    calculate_cash_on_cash,
    calculate_equity_irr,
    calculate_equity_npv,
    calculate_equity_performance,
    calculate_moic,
    calculate_payback_period,
    calculate_pe_triad,
    summarise_equity_cashflows,
)


# ---------------------------------------------------------------------------
# summarise_equity_cashflows (lines 54-58)
# ---------------------------------------------------------------------------
def test_summarise_partitions_inflows_and_outflows() -> None:
    """Negatives -> total_invested (sign-flipped), positives -> distributions.

    Conservation: total_invested equals the magnitude of the only outflow and
    total_distributed equals the exact sum of the inflows; zero entries are
    ignored by both partitions.
    """
    cfs = [-100.0, 0.0, 40.0, 60.0, 30.0]
    summary = summarise_equity_cashflows(cfs)

    assert isinstance(summary, EquityCashflowSummary)
    assert summary.total_invested == 100.0
    assert summary.total_distributed == pytest.approx(40.0 + 60.0 + 30.0)
    # cumulative_distributions mirrors total_distributed; total_called mirrors invested.
    assert summary.cumulative_distributions == summary.total_distributed
    assert summary.total_called == summary.total_invested
    # The stored series is a faithful copy of the input.
    assert list(summary.cashflows) == cfs


def test_summarise_all_positive_has_zero_invested() -> None:
    """With no negative entry total_invested must be exactly 0.0."""
    summary = summarise_equity_cashflows([10.0, 20.0])
    assert summary.total_invested == 0.0
    assert summary.total_distributed == 30.0


# ---------------------------------------------------------------------------
# calculate_equity_irr -- happy path + None / NaN / exception branches (45-49)
# ---------------------------------------------------------------------------
def test_equity_irr_recovers_known_rate() -> None:
    """A -100 / +110 one-period series has an algebraically exact IRR of 10%."""
    irr = calculate_equity_irr([-100.0, 110.0])
    assert irr is not None
    assert irr == pytest.approx(0.10, abs=1e-6)


def test_equity_irr_none_when_no_sign_change() -> None:
    """All-positive (no sign change) yields no real root -> None."""
    assert calculate_equity_irr([100.0, 50.0]) is None


def test_equity_irr_none_on_non_finite(monkeypatch: pytest.MonkeyPatch) -> None:
    """A NaN from the delegated solver must be normalised to None (line 47-48)."""
    monkeypatch.setattr(mod, "_irr", lambda _cfs: float("nan"))
    assert calculate_equity_irr([-100.0, 110.0]) is None


@pytest.mark.parametrize("exc", [ZeroDivisionError, OverflowError, ValueError])
def test_equity_irr_swallows_documented_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    exc: type[Exception],
) -> None:
    """Each documented raise from the solver is caught -> None (lines 45-46)."""

    def _boom(_cfs: object) -> float:
        raise exc("boom")

    monkeypatch.setattr(mod, "_irr", _boom)
    assert calculate_equity_irr([-100.0, 110.0]) is None


# ---------------------------------------------------------------------------
# calculate_equity_npv -- legacy default-rate path + exception branch (88-89)
# ---------------------------------------------------------------------------
def test_equity_npv_uses_legacy_default_rate() -> None:
    """When no discount_rate is passed the LEGACY default rate is applied.

    Derived from first principles: NPV = -100 + 110/(1+r) at r = legacy rate.
    """
    cfs = [-100.0, 110.0]
    rate = LEGACY_EQUITY_DISCOUNT_RATE
    expected = -100.0 + 110.0 / (1.0 + rate)
    npv = calculate_equity_npv(cfs)
    assert npv is not None
    assert npv == pytest.approx(expected, abs=1e-9)


def test_equity_npv_explicit_rate_overrides_default() -> None:
    """A passed discount_rate takes precedence over the legacy fallback."""
    cfs = [-100.0, 110.0]
    explicit = 0.0  # at 0% NPV is the undiscounted sum
    npv = calculate_equity_npv(cfs, discount_rate=explicit)
    assert npv is not None
    assert npv == pytest.approx(10.0, abs=1e-9)
    # And it differs from the legacy-rate result (which discounts the +110).
    assert npv != calculate_equity_npv(cfs)


def test_equity_npv_zero_rate_equals_undiscounted_sum() -> None:
    """At r=0 NPV equals the plain arithmetic sum of the flows."""
    cfs = [-50.0, 20.0, 20.0, 20.0]
    npv = calculate_equity_npv(cfs, discount_rate=0.0)
    assert npv == pytest.approx(sum(cfs), abs=1e-9)


@pytest.mark.parametrize("exc", [ZeroDivisionError, OverflowError, ValueError])
def test_equity_npv_swallows_documented_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    exc: type[Exception],
) -> None:
    """A raise from the NPV primitive is caught -> None (lines 88-89)."""

    def _boom(_rate: object, _cfs: object) -> float:
        raise exc("boom")

    monkeypatch.setattr(mod, "_npv_wrapper", _boom)
    assert calculate_equity_npv([-100.0, 110.0]) is None


# ---------------------------------------------------------------------------
# calculate_cash_on_cash (line 98 guard + happy path)
# ---------------------------------------------------------------------------
def test_cash_on_cash_ratios() -> None:
    """Each entry is the distribution divided by the equity base."""
    coc = calculate_cash_on_cash([25.0, 50.0], 100.0)
    assert coc == [pytest.approx(0.25), pytest.approx(0.50)]


@pytest.mark.parametrize("base", [0.0, -10.0])
def test_cash_on_cash_non_positive_base_returns_empty(base: float) -> None:
    """Non-positive equity base short-circuits to [] (line 98)."""
    assert calculate_cash_on_cash([10.0, 20.0], base) == []


# ---------------------------------------------------------------------------
# calculate_moic (line 109 guard + happy path)
# ---------------------------------------------------------------------------
def test_moic_combines_distributions_and_nav() -> None:
    """MOIC = (cumulative distributions + NAV) / invested."""
    moic = calculate_moic(
        cumulative_distributions=80.0, current_nav=40.0, total_invested=100.0
    )
    assert moic == pytest.approx((80.0 + 40.0) / 100.0)


@pytest.mark.parametrize("invested", [0.0, -5.0])
def test_moic_non_positive_invested_returns_none(invested: float) -> None:
    """Non-positive invested base returns None (line 109)."""
    assert calculate_moic(50.0, 10.0, invested) is None


# ---------------------------------------------------------------------------
# calculate_payback_period (line 128 guard + crossing arithmetic)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("equity", [0.0, -1.0])
def test_payback_non_positive_equity_returns_none(equity: float) -> None:
    """Non-positive initial equity returns None (line 128)."""
    assert calculate_payback_period([10.0, 10.0], equity) is None


def test_payback_exact_crossing_at_period_boundary() -> None:
    """Cumulative reaches equity exactly at the end of year 2.

    With flows [60, 40] and equity 100, cumulative hits 100 at idx=2 with zero
    shortfall, so fraction == 1.0 and the result is exactly 2.0.
    """
    pb = calculate_payback_period([60.0, 40.0], 100.0)
    assert pb == pytest.approx(2.0)


def test_payback_fractional_within_year() -> None:
    """Mid-year crossing yields a fractional payback derived from the shortfall.

    Flows [60, 80], equity 100: crossing in year 2 where cumulative=140,
    shortfall=40, year_dist=80 -> fraction = 1 - 40/80 = 0.5 -> payback 1.5.
    """
    pb = calculate_payback_period([60.0, 80.0], 100.0)
    assert pb == pytest.approx(1.5)


def test_payback_zero_year_distribution_uses_unit_denominator() -> None:
    """A zero crossing-year flow falls back to a unit denominator (amt==0 branch).

    Flows [100, 0]: cumulative reaches equity 100 at idx=1 with amt=0; the guard
    sets year_dist=1.0 and shortfall=0 -> fraction=1.0 -> payback exactly 1.0.
    """
    pb = calculate_payback_period([100.0, 0.0], 100.0)
    assert pb == pytest.approx(1.0)


def test_payback_never_reached_returns_none() -> None:
    """If cumulative never reaches equity, the loop falls through to None (139)."""
    assert calculate_payback_period([10.0, 10.0], 1000.0) is None


# ---------------------------------------------------------------------------
# calculate_pe_triad (lines 148-154 guard + body)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("called", [0.0, -3.0])
def test_pe_triad_non_positive_called_returns_none_triple(called: float) -> None:
    """Non-positive capital called returns the (None, None, None) triple (149)."""
    assert calculate_pe_triad(50.0, 10.0, called) == (None, None, None)


def test_pe_triad_identities() -> None:
    """DPI=dist/called, RVPI=nav/called, TVPI=DPI+RVPI (lines 151-154)."""
    dpi, rvpi, tvpi = calculate_pe_triad(
        cumulative_distributions=120.0,
        current_nav=30.0,
        capital_called=100.0,
    )
    assert dpi == pytest.approx(1.20)
    assert rvpi == pytest.approx(0.30)
    assert tvpi == pytest.approx(dpi + rvpi)


# ---------------------------------------------------------------------------
# calculate_equity_performance (lines 170-194: orchestration)
# ---------------------------------------------------------------------------
def test_equity_performance_none_when_no_capital_invested() -> None:
    """With no outflow total_invested<=0 -> None (lines 171-172)."""
    assert calculate_equity_performance([10.0, 20.0]) is None


def test_equity_performance_full_snapshot_is_internally_consistent() -> None:
    """End-to-end snapshot: every reported field reconciles to its helper.

    Drive with a synthetic series: invest 100 up front, then distribute
    50/60/30. All expected values are re-derived from the same helpers the
    module uses, so no economic constant is hardcoded.
    """
    cfs = [-100.0, 50.0, 60.0, 30.0]
    nav = 25.0
    perf = calculate_equity_performance(cfs, current_nav=nav)

    assert isinstance(perf, EquityPerformance)

    invested = 100.0
    dists: List[float] = [50.0, 60.0, 30.0]
    cum = sum(dists)

    # Top-level fields reconcile to the delegated helpers.
    assert perf.equity_irr == calculate_equity_irr(cfs)
    assert perf.equity_npv == calculate_equity_npv(cfs)
    assert perf.equity_multiple == calculate_moic(cum, nav, invested)
    assert perf.equity_multiple == pytest.approx((cum + nav) / invested)

    meta = perf.metadata
    assert meta["moic"] == perf.equity_multiple
    assert meta["total_invested"] == pytest.approx(invested)
    assert meta["total_distributed"] == pytest.approx(cum)
    assert meta["current_nav"] == pytest.approx(nav)

    # PE triad inside metadata matches the standalone helper.
    dpi, rvpi, tvpi = calculate_pe_triad(cum, nav, invested)
    assert meta["dpi"] == pytest.approx(dpi)
    assert meta["rvpi"] == pytest.approx(rvpi)
    assert meta["tvpi"] == pytest.approx(tvpi)

    # cash-on-cash: per-year ratios and their mean.
    expected_coc = calculate_cash_on_cash(dists, invested)
    assert meta["annual_coc"] == [pytest.approx(c) for c in expected_coc]
    assert meta["average_coc"] == pytest.approx(sum(expected_coc) / len(expected_coc))

    # payback reconciles to the standalone helper.
    assert meta["payback_period_years"] == calculate_payback_period(dists, invested)

    # Sanity invariants on the recovered IRR/NPV: investing 100 to receive 140
    # over time at the 10% legacy rate must yield a positive (>0) IRR and a
    # finite NPV.
    assert perf.equity_irr is not None and perf.equity_irr > 0.0
    assert perf.equity_npv is not None and math.isfinite(perf.equity_npv)


def test_equity_performance_default_nav_is_zero() -> None:
    """Omitting current_nav defaults NAV to 0.0 in the snapshot metadata."""
    cfs = [-100.0, 60.0, 70.0]
    perf = calculate_equity_performance(cfs)
    assert perf is not None
    assert perf.metadata["current_nav"] == 0.0
    # With NAV=0, MOIC reduces to total distributions / invested.
    assert perf.equity_multiple == pytest.approx((60.0 + 70.0) / 100.0)
