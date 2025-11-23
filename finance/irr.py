"""Investment-grade IRR/NPV calculations with date-aware XNPV/XIRR support.

This module provides the core discounting and IRR engines for the v14 stack.

Features
--------
- Periodic NPV/IRR for regular (e.g. annual) cashflows.
- Date-aware XNPV/XIRR for irregular cashflow timing.
- Robust IRR solvers with:
  - Guardrails on the rate search interval.
  - Fallback bisection methods when library routines fail.
  - Graceful handling of NaN / non-bracketing cases.

These helpers are intended to be reused by:
- analytics.core.metrics (project/equity NPV & IRR),
- finance.equity_v14 (equity performance),
- Monte Carlo, sensitivity, and optimizer modules.

Author: DutchBay V14 Team
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional, Sequence

import numpy_financial as npf

# Reasonable IRR search bounds for long-dated infra (annualised)
_IRR_LOWER_BOUND = -0.9999
_IRR_UPPER_BOUND = 5.0  # 500% p.a. as a hard cap
_XIRR_UPPER_BOUND = 2.0  # 200% p.a. cap for dated cashflows


# ============================================================================
# Internal helpers
# ============================================================================


def _normalize_cashflows(cashflows: Iterable[float]) -> List[float]:
    """Return cashflows as a list of floats, filtering out trivial noise.

    This keeps all values, only coercing numerics to float. It does NOT
    modify the economic content (no rounding, no thresholding).
    """
    return [float(x) for x in cashflows]


def _all_near_zero(cashflows: Sequence[float], tol: float = 1e-12) -> bool:
    """True if all cashflows are economically zero."""
    return all(abs(cf) < tol for cf in cashflows)


def _have_opposite_signs(a: float, b: float) -> bool:
    """True if a and b have opposite signs."""
    return (a < 0.0 < b) or (b < 0.0 < a)


# ============================================================================
# PERIODIC NPV/IRR (Standard Regular Cashflows)
# ============================================================================


def npv(rate: float, cashflows: Sequence[float]) -> float:
    """Classic periodic Net Present Value using simple discounting.

    Parameters
    ----------
    rate:
        Periodic discount rate (e.g. annual WACC).
    cashflows:
        Sequence of cashflows where index = period number, starting at 0.

    Returns
    -------
    float
        Present value of the cashflow series at the given rate.
    """
    r = float(rate)
    if r <= -1.0:
        # Prevent division by zero and nonsense values
        r = _IRR_LOWER_BOUND

    total = 0.0
    for t, cf in enumerate(cashflows):
        total += float(cf) / ((1.0 + r) ** float(t))
    return total


def irr(cashflows: Sequence[float]) -> Optional[float]:
    """Periodic Internal Rate of Return.

    Tries numpy_financial.irr first, then falls back to a robust
    bisection-based solver if needed.

    Parameters
    ----------
    cashflows:
        Sequence of periodic cashflows (negative = investment, positive = return).

    Returns
    -------
    Optional[float]
        IRR as a decimal (e.g. 0.12 for 12%) or None if no valid root exists.
    """
    cfs = _normalize_cashflows(cashflows)

    if not cfs:
        return None
    if _all_near_zero(cfs):
        # Economically flat – treat as 0% return
        return 0.0

    # First attempt: library IRR
    try:
        val = float(npf.irr(cfs))
    except Exception:
        val = float("nan")

    # If numpy_financial fails (NaN or out-of-bounds), fall back to bisection
    if val != val or val < _IRR_LOWER_BOUND or val > _IRR_UPPER_BOUND:
        return _irr_bisect(cfs)

    return val


def _irr_bisect(cashflows: Sequence[float]) -> Optional[float]:
    """Bisection solver for IRR. Internal use only.

    Ensures:
    - Search interval is [_IRR_LOWER_BOUND, _IRR_UPPER_BOUND]
    - Returns None if NPV does not change sign over the interval.
    """
    if not cashflows:
        return None

    cfs = _normalize_cashflows(cashflows)

    lo, hi = _IRR_LOWER_BOUND, _IRR_UPPER_BOUND
    f_lo = npv(lo, cfs)
    f_hi = npv(hi, cfs)

    # Exact roots at the bounds
    if abs(f_lo) < 1e-12:
        return lo
    if abs(f_hi) < 1e-12:
        return hi

    # If no sign change, there is no guarantee of a root
    if not _have_opposite_signs(f_lo, f_hi):
        return None

    # Bisection loop
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid, cfs)

        if abs(f_mid) < 1e-10:
            return mid

        if _have_opposite_signs(f_lo, f_mid):
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid

    # Best-effort approximation
    return (lo + hi) / 2.0


# ============================================================================
# DATE-AWARE XNPV/XIRR (Irregular Cashflow Timing)
# ============================================================================


def xnpv(rate: float, cashflows: Sequence[float], dates: Sequence[datetime]) -> float:
    """Date-adjusted Net Present Value (XNPV).

    Parameters
    ----------
    rate:
        Annual discount rate.
    cashflows:
        Cashflow series (negative = investment, positive = return).
    dates:
        Matching sequence of datetime objects; must be same length as cashflows.

    Returns
    -------
    float
        Present value of the cashflows discounted from the first date.
    """
    if len(cashflows) != len(dates):
        raise ValueError("Cashflows and dates must have same length")

    cfs = _normalize_cashflows(cashflows)
    if not cfs:
        return 0.0

    t0 = dates[0]
    total = 0.0

    for cf, date in zip(cfs, dates):
        days = (date - t0).days
        years = days / 365.25
        total += cf / ((1.0 + float(rate)) ** years)

    return total


def xirr(cashflows: Sequence[float], dates: Sequence[datetime]) -> Optional[float]:
    """Date-adjusted Internal Rate of Return (XIRR) using bisection.

    Parameters
    ----------
    cashflows:
        Cashflow series (negative = investment, positive = return).
    dates:
        Matching sequence of datetime objects; must be same length as cashflows.

    Returns
    -------
    Optional[float]
        Annualised XIRR as a decimal or None if no valid root exists.
    """
    if len(cashflows) != len(dates):
        raise ValueError("Cashflows and dates must have same length")

    cfs = _normalize_cashflows(cashflows)
    if not cfs:
        return None
    if _all_near_zero(cfs):
        return 0.0

    try:
        return _xirr_bisect(cfs, dates)
    except Exception:
        return None


def _xirr_bisect(
    cashflows: Sequence[float],
    dates: Sequence[datetime],
) -> Optional[float]:
    """Bisection solver for XIRR. Internal use only."""
    lo, hi = _IRR_LOWER_BOUND, _XIRR_UPPER_BOUND

    npv_lo = xnpv(lo, cashflows, dates)
    npv_hi = xnpv(hi, cashflows, dates)

    if abs(npv_lo) < 1e-8:
        return lo
    if abs(npv_hi) < 1e-8:
        return hi

    if not _have_opposite_signs(npv_lo, npv_hi):
        return None

    for _ in range(100):
        mid = (lo + hi) / 2.0
        npv_mid = xnpv(mid, cashflows, dates)

        if abs(npv_mid) < 1e-8:
            return mid

        if _have_opposite_signs(npv_lo, npv_mid):
            hi = mid
        else:
            lo, npv_lo = mid, npv_mid

    return (lo + hi) / 2.0


__all__ = [
    "npv",
    "irr",
    "xnpv",
    "xirr",
]
