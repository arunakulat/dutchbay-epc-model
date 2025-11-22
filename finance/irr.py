"""Investment-grade IRR/NPV calculations with date-aware XNPV/XIRR support.

Complies with global project finance standards for irregular cashflow timing.

Author: DutchBay V14 Team
Date: November 12, 2025
Standards: CFA Institute, IFC Project Finance Guidelines
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, List

import numpy_financial as npf

from finance.utils import as_float  # noqa: F401
from constants import DEFAULT_DISCOUNT_RATE  # noqa: F401


# ============================================================================
# PERIODIC NPV/IRR (Standard Annual Cashflows)
# ============================================================================


def npv(rate: float, cashflows: Sequence[float]) -> float:
    """Classic periodic Net Present Value."""
    r = float(rate)
    if r <= -1.0:
        r = -0.999999

    total = 0.0
    for t, cf in enumerate(cashflows):
        total += float(cf) / ((1.0 + r) ** t)
    return total


def irr(cashflows: Sequence[float]) -> Optional[float]:
    """Periodic Internal Rate of Return."""
    cfs: List[float] = [float(x) for x in cashflows]

    try:
        val = float(npf.irr(cfs))
    except Exception:
        return _irr_local(cfs)

    if val != val:  # NaN check
        return None
    return val


def _irr_local(cashflows: Sequence[float]) -> Optional[float]:
    """Bisection solver for IRR. Internal use only."""
    if not cashflows:
        return None

    if all(abs(cf) < 1e-12 for cf in cashflows):
        return 0.0

    lo, hi = -0.9999, 5.0
    f_lo = npv(lo, cashflows)
    f_hi = npv(hi, cashflows)

    if abs(f_lo) < 1e-12:
        return lo
    if abs(f_hi) < 1e-12:
        return hi

    if (f_lo > 0 and f_hi > 0) or (f_lo < 0 and f_hi < 0):
        return None

    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid, cashflows)

        if abs(f_mid) < 1e-10:
            return mid

        if (f_lo < 0 and f_mid > 0) or (f_lo > 0 and f_mid < 0):
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid

    return (lo + hi) / 2.0


# ============================================================================
# DATE-AWARE XNPV/XIRR (Irregular Cashflow Timing)
# ============================================================================


def xnpv(rate: float, cashflows: Sequence[float], dates: Sequence[datetime]) -> float:
    """Date-adjusted Net Present Value (XNPV)."""
    if len(cashflows) != len(dates):
        raise ValueError("Cashflows and dates must have same length")

    t0 = dates[0]
    total = 0.0

    for cf, date in zip(cashflows, dates):
        days = (date - t0).days
        years = days / 365.25
        total += float(cf) / ((1.0 + rate) ** years)

    return total


def xirr(cashflows: Sequence[float], dates: Sequence[datetime]) -> Optional[float]:
    """Date-adjusted Internal Rate of Return (XIRR)."""
    if len(cashflows) != len(dates):
        raise ValueError("Cashflows and dates must have same length")

    try:
        return _xirr_bisect(cashflows, dates)
    except Exception:
        return None


def _xirr_bisect(
    cashflows: Sequence[float],
    dates: Sequence[datetime],
) -> Optional[float]:
    """Bisection solver for XIRR. Internal use only."""
    lo, hi = -0.9999, 2.0

    npv_lo = xnpv(lo, cashflows, dates)
    npv_hi = xnpv(hi, cashflows, dates)

    if abs(npv_lo) < 1e-8:
        return lo
    if abs(npv_hi) < 1e-8:
        return hi

    if (npv_lo > 0 and npv_hi > 0) or (npv_lo < 0 and npv_hi < 0):
        return None

    for _ in range(100):
        mid = (lo + hi) / 2.0
        npv_mid = xnpv(mid, cashflows, dates)

        if abs(npv_mid) < 1e-8:
            return mid

        if (npv_lo < 0 and npv_mid > 0) or (npv_lo > 0 and npv_mid < 0):
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

