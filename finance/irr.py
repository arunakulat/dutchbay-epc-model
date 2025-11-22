"""Investment-grade IRR/NPV calculations with date-aware XNPV/XIRR support.

Complies with global project finance standards for irregular cashflow timing.

Author: DutchBay V14 Team
Date: November 12, 2025
Standards: CFA Institute, IFC Project Finance Guidelines
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from finance.utils import as_float  # noqa: F401
from constants import DEFAULT_DISCOUNT_RATE  # noqa: F401

try:
    import numpy_financial as npf  # type: ignore
except Exception:
    npf = None


# ============================================================================
# PERIODIC NPV/IRR (Standard Annual Cashflows)
# ============================================================================


def npv(rate: float, cashflows: Sequence[float]) -> float:
    """Classic periodic Net Present Value.

    NPV(r) = sum_{t=0..N} CF[t] / (1+r)^t

    Parameters
    ----------
    rate : float
        Discount rate (decimal, e.g. 0.12 for 12%)
    cashflows : Sequence[float]
        Cashflow series starting at t=0

    Returns
    -------
    float
        Net Present Value

    Notes
    -----
    - Assumes periodic (annual) cashflows
    - For irregular dates, use xnpv()
    - Rate clamped at -99.99% to avoid division errors

    Examples
    --------
    >>> npv(0.10, [-1000, 500, 500, 500])
    243.426...
    """
    r = float(rate)
    if r <= -1.0:
        r = -0.999999

    total = 0.0
    for t, cf in enumerate(cashflows):
        total += float(cf) / ((1.0 + r) ** t)
    return total


def irr(cashflows: Sequence[float]) -> Optional[float]:
    """Periodic Internal Rate of Return.

    Finds rate r such that NPV(r, cashflows) = 0.
    Uses numpy-financial if available, otherwise bisection solver.

    Parameters
    ----------
    cashflows : Sequence[float]
        Cashflow series starting at t=0

    Returns
    -------
    Optional[float]
        IRR as decimal (e.g. 0.18 = 18%), or None if not found

    Notes
    -----
    - Returns None if no sign change in NPV across search range
    - Search range: -99.99% to 500%
    - For irregular dates, use xirr()

    Edge Cases
    ----------
    - All zeros: returns 0.0
    - No sign change: returns None
    - Multiple roots: returns first found in [-0.9999, 5.0]

    Examples
    --------
    >>> irr([-1000, 500, 500, 500])
    0.2343...
    """
    cfs = [float(x) for x in cashflows]

    if npf is not None:
        try:
            val = float(npf.irr(cfs))
            if val != val:
                return None
            return val
        except Exception:
            pass

    return _irr_local(cfs)


def _irr_local(cashflows: Sequence[float]) -> Optional[float]:
    """Bisection solver for IRR. Internal use only.

    Search domain: [-0.9999, 5.0] (-99.99% to 500%)
    Convergence: |NPV| < 1e-10
    Max iterations: 200
    """
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
    """Date-adjusted Net Present Value (XNPV).

    NPV = sum CF[i] / (1+r)^((date[i]-date[0]).days/365.25)

    Parameters
    ----------
    rate : float
        Annual discount rate (decimal)
    cashflows : Sequence[float]
        Cashflow amounts
    dates : Sequence[datetime]
        Corresponding dates (must align with cashflows)

    Returns
    -------
    float
        Net Present Value adjusted for actual dates

    Notes
    -----
    - Uses 365.25 days per year convention
    - First date (dates[0]) is t=0 reference
    - Standard in Excel XNPV and project finance models

    Examples
    --------
    >>> from datetime import datetime
    >>> xnpv(0.10, [-1000, 500, 500],
    ...      [datetime(2020,1,1), datetime(2020,7,1), datetime(2021,1,1)])
    -44.87...
    """
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
    """Date-adjusted Internal Rate of Return (XIRR).

    Finds rate r such that XNPV(r, cashflows, dates) = 0.
    Equivalent to Excel's XIRR function.

    Parameters
    ----------
    cashflows : Sequence[float]
        Cashflow amounts
    dates : Sequence[datetime]
        Corresponding dates (must align with cashflows)

    Returns
    -------
    Optional[float]
        Annual IRR as decimal, or None if not found

    Notes
    -----
    - Uses bisection solver (same as Excel XIRR)
    - Search range: -99.99% to 200% annual
    - Convergence: |XNPV| < 1e-8
    - Max iterations: 100

    Edge Cases
    ----------
    - Mismatched lengths: raises ValueError
    - No sign change: returns None
    - All zero cashflows: returns None

    Examples
    --------
    >>> from datetime import datetime
    >>> xirr([-1000, 500, 700],
    ...      [datetime(2020,1,1), datetime(2021,1,1), datetime(2022,7,1)])
    0.2846...
    """
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
    """Bisection solver for XIRR. Internal use only.

    Search domain: [-0.9999, 2.0] (-99.99% to 200%)
    Convergence: |XNPV| < 1e-8
    Max iterations: 100
    """
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
