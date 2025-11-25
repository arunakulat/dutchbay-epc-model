#!/usr/bin/env python3
"""
Unit tests for finance.irr

Covers:
- Periodic NPV / IRR
- XNPV / XIRR with date-based timing
- Edge cases and fallback behaviour
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Sequence

import numpy_financial as npf
import pytest

from finance.irr import irr, npv, xirr, xnpv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _approx(a: float, b: float, tol: float = 1e-8) -> bool:
    """Simple approximate equality helper."""
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# NPV tests
# ---------------------------------------------------------------------------


def test_npv_basic_discounting() -> None:
    """
    Sanity check: NPV of a simple project at 10% discount rate.

    Cashflows:
      t0: -100
      t1: +60
      t2: +60

    Expected NPV ~ 4.1322 at 10%.
    """
    cfs: Sequence[float] = [-100.0, 60.0, 60.0]
    rate = 0.10

    val = npv(rate, cfs)

    assert _approx(val, 4.13223140495868, tol=1e-6)


def test_npv_monotonic_with_rate() -> None:
    """
    NPV should decrease as the discount rate increases for the same cashflows.
    """
    cfs: Sequence[float] = [-100.0, 60.0, 60.0]

    npv_low = npv(0.05, cfs)
    npv_high = npv(0.15, cfs)

    assert npv_low > npv_high


def test_npv_handles_near_minus_one_rate() -> None:
    """
    Guard on rates <= -1.0 should avoid division by zero / explosions.
    """
    cfs: Sequence[float] = [-100.0, 60.0, 60.0]

    # This should not raise and should return a finite number.
    val = npv(-1.0, cfs)

    assert math.isfinite(val)


# ---------------------------------------------------------------------------
# IRR tests
# ---------------------------------------------------------------------------


def test_irr_simple_profile_matches_numpy_financial() -> None:
    """
    IRR([-100, 60, 60]) should be ~13.066%.

    This is a standard textbook example and should match numpy_financial.irr.
    """
    cfs: Sequence[float] = [-100.0, 60.0, 60.0]

    expected = float(npf.irr(cfs))
    result = irr(cfs)

    assert result is not None
    assert _approx(result, expected, tol=1e-8)
    # Ballpark check to catch wild regressions
    assert 0.10 < result < 0.20


def test_irr_all_zero_cashflows_returns_zero() -> None:
    """
    All-zero cashflows should return 0.0 rather than None/NaN.
    """
    cfs: Sequence[float] = [0.0, 0.0, 0.0]

    result = irr(cfs)

    assert result == 0.0


def test_irr_no_sign_change_returns_none() -> None:
    """
    If cashflows never change sign (all positive or all negative), IRR is undefined.
    """
    # All positive
    cfs: Sequence[float] = [100.0, 20.0, 20.0]

    result = irr(cfs)

    assert result is None


def test_irr_falls_back_when_numpy_financial_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    If numpy_financial.irr raises, our irr() should fall back to the local solver.
    """

    def boom(_cashflows: Sequence[float]) -> float:
        raise RuntimeError("forced failure")

    monkeypatch.setattr(npf, "irr", boom)

    cfs: Sequence[float] = [-100.0, 60.0, 60.0]

    result = irr(cfs)

    # We don't assert an exact number here, just that we got a sane float.
    assert result is not None
    assert isinstance(result, float)
    assert -1.0 < result < 5.0


# ---------------------------------------------------------------------------
# XNPV / XIRR tests
# ---------------------------------------------------------------------------


def test_xnpv_matches_periodic_npv_for_annual_steps() -> None:
    """
    For cashflows spaced ~1 year apart, xnpv should be close to periodic npv.

    We use a looser tolerance because xnpv uses 365.25-day years,
    while we advance dates by exactly 365 days here.
    """
    cfs: Sequence[float] = [-100.0, 60.0, 60.0]
    rate = 0.10

    t0 = datetime(2025, 1, 1)
    dates = [t0, t0 + timedelta(days=365), t0 + timedelta(days=730)]

    periodic_val = npv(rate, cfs)
    date_val = xnpv(rate, cfs, dates)

    # Allow a few cents of drift due to 365 vs 365.25
    assert _approx(periodic_val, date_val, tol=0.05)


def test_xirr_two_point_profile() -> None:
    """
    Simple two-point profile:
      t0: -1000
      t1: +1100 (exactly 1 year later)
    IRR should be ~10%.

    We allow a bit of slack because XIRR also uses 365.25-day years.
    """
    cfs: Sequence[float] = [-1000.0, 1100.0]
    t0 = datetime(2025, 1, 1)
    dates = [t0, t0 + timedelta(days=365)]

    result = xirr(cfs, dates)

    assert result is not None
    # Result is ~0.10007; allow 0.1% absolute tolerance
    assert _approx(result, 0.10, tol=1e-3)


def test_xnpv_raises_on_length_mismatch() -> None:
    """
    xnpv must raise ValueError if cashflows and dates lengths differ.
    """
    cfs: Sequence[float] = [-100.0, 110.0]
    dates = [datetime(2025, 1, 1)]  # length 1 instead of 2

    with pytest.raises(ValueError):
        xnpv(0.10, cfs, dates)


def test_xirr_raises_on_length_mismatch() -> None:
    """
    xirr must raise ValueError if cashflows and dates lengths differ.
    """
    cfs: Sequence[float] = [-100.0, 110.0]
    dates = [datetime(2025, 1, 1)]  # length 1 instead of 2

    with pytest.raises(ValueError):
        xirr(cfs, dates)
