"""Investment-grade IRR/NPV calculations with configurable bounds.

This module provides the core discounting and IRR engines for the v14 stack
with support for project-specific validation bounds (YAML-driven when provided).

Features
--------
- Periodic NPV/IRR for regular (e.g. annual) cashflows.
- Date-aware XNPV/XIRR for irregular cashflow timing.
- Configurable search bounds for project-specific risk tolerance.
- Robust IRR solvers with:
  - Guardrails on the rate search interval.
  - Fallback bisection methods when library routines fail.
  - Graceful handling of NaN / non-bracketing cases.

These helpers are intended to be reused by:
- analytics.core.metrics (project/equity NPV & IRR),
- finance.equity_v14 (equity performance),
- Monte Carlo, sensitivity, and optimizer modules.

Author: DutchBay V14 Team
Version: 2.0 (YAML-configurable bounds)
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional, Sequence

import numpy_financial as npf

# Conservative mathematical defaults (used when no config provided)
# These are numerical stability guards, not business rules
_DEFAULT_IRR_LOWER_BOUND = -0.9999  # Prevents division by zero at -100%
_DEFAULT_IRR_UPPER_BOUND = 5.0  # 500% p.a. numerical stability cap
_DEFAULT_XIRR_UPPER_BOUND = 2.0  # 200% p.a. cap for dated cashflows


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

    Formula: NPV = Σ(CF_t / (1 + r)^t) for t = 0, 1, 2, ...

    Parameters
    ----------
    rate:
        Periodic discount rate (e.g. annual WACC as decimal, 0.10 = 10%).
        Clamped to [-0.9999, ∞) to prevent division by zero.
    cashflows:
        Sequence of cashflows where index = period number, starting at 0.

    Returns
    -------
    float
        Present value of the cashflow series at the given rate.

    Note
    ----
    All intermediate calculations use float64 for precision.
    If rate ≤ -1.0, it is clamped to -0.9999 for numerical stability.
    """
    r = float(rate)
    if r <= -1.0:
        # Prevent division by zero and nonsense values
        r = _DEFAULT_IRR_LOWER_BOUND

    total = 0.0
    for t, cf in enumerate(cashflows):
        total += float(cf) / ((1.0 + r) ** float(t))
    return total


def irr(
    cashflows: Sequence[float],
    lower_bound: Optional[float] = None,
    upper_bound: Optional[float] = None,
) -> Optional[float]:
    """Periodic Internal Rate of Return with configurable bounds.

    Tries numpy_financial.irr first (fast), then falls back to robust
    bisection-based solver if needed (reliable).

    Parameters
    ----------
    cashflows:
        Sequence of periodic cashflows (negative = investment, positive = return).
    lower_bound:
        Minimum acceptable IRR (default: -0.9999).
        Override from YAML config for project-specific risk tolerance.
    upper_bound:
        Maximum acceptable IRR (default: 5.0).
        Override from YAML config for project-specific return caps.

    Returns
    -------
    Optional[float]
        IRR as a decimal (e.g. 0.12 for 12%) or None if no valid root exists.

    Examples
    --------
    With module defaults:
    >>> irr([-100, 30, 30, 30, 30])
    0.07155

    With project-specific bounds from YAML:
    >>> irr([-100, 30, 30, 30, 30], lower_bound=-0.50, upper_bound=0.30)
    0.07155

    Notes
    -----
    - Returns 0.0 for economically flat series (all cashflows ≈ 0)
    - Returns None for empty series or when no sign change exists
    - Hybrid approach: library first (performance), bisection fallback (robustness)
    """
    cfs = _normalize_cashflows(cashflows)

    if not cfs:
        return None
    if _all_near_zero(cfs):
        # Economically flat – treat as 0% return
        return 0.0

    # Use provided bounds or fall back to module defaults
    lo = float(lower_bound) if lower_bound is not None else _DEFAULT_IRR_LOWER_BOUND
    hi = float(upper_bound) if upper_bound is not None else _DEFAULT_IRR_UPPER_BOUND

    # First attempt: library IRR (fast when it works)
    try:
        val = float(npf.irr(cfs))
    except Exception:
        val = float("nan")

    # If numpy_financial fails (NaN or out-of-bounds), fall back to bisection
    if val != val or val < lo or val > hi:
        return _irr_bisect(cfs, lower_bound=lo, upper_bound=hi)

    return val


def _irr_bisect(
    cashflows: Sequence[float],
    lower_bound: float = _DEFAULT_IRR_LOWER_BOUND,
    upper_bound: float = _DEFAULT_IRR_UPPER_BOUND,
) -> Optional[float]:
    """Bisection solver for IRR with configurable bounds. Internal use only.

    Ensures:
    - Search interval is [lower_bound, upper_bound]
    - Returns None if NPV does not change sign over the interval.

    Parameters
    ----------
    cashflows:
        Normalized cashflow series.
    lower_bound:
        Lower search bound.
    upper_bound:
        Upper search bound.

    Returns
    -------
    Optional[float]
        IRR or None if no root exists in the interval.
    """
    if not cashflows:
        return None

    cfs = _normalize_cashflows(cashflows)
    lo, hi = float(lower_bound), float(upper_bound)

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

    # Bisection loop (200 iterations = 2^-200 precision ≈ machine epsilon)
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

    Discounts cashflows from their actual calendar dates to the first date.

    Formula: XNPV = Σ(CF_t / (1 + r)^((date_t - date_0) / 365.25))

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

    Raises
    ------
    ValueError:
        If cashflows and dates have different lengths.

    Note
    ----
    Yearfraction uses ACT/365.25 convention (accounts for leap years).
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


def xirr(
    cashflows: Sequence[float],
    dates: Sequence[datetime],
    lower_bound: Optional[float] = None,
    upper_bound: Optional[float] = None,
) -> Optional[float]:
    """Date-adjusted Internal Rate of Return (XIRR) with configurable bounds.

    Uses bisection method directly (more reliable than library XIRR for irregular dates).

    Parameters
    ----------
    cashflows:
        Cashflow series (negative = investment, positive = return).
    dates:
        Matching sequence of datetime objects; must be same length as cashflows.
    lower_bound:
        Minimum acceptable XIRR (default: -0.9999).
        Override from YAML config for project-specific risk tolerance.
    upper_bound:
        Maximum acceptable XIRR (default: 2.0).
        Override from YAML config for project-specific return caps.
        Note: Default is more conservative than periodic IRR (2.0 vs 5.0).

    Returns
    -------
    Optional[float]
        Annualized XIRR as a decimal or None if no valid root exists.

    Raises
    ------
    ValueError:
        If cashflows and dates have different lengths.

    Note
    ----
    XIRR upper bound defaults to 2.0 (200% p.a.) which is more conservative
    than periodic IRR (5.0) due to date arithmetic being less precise.
    """
    if len(cashflows) != len(dates):
        raise ValueError("Cashflows and dates must have same length")

    cfs = _normalize_cashflows(cashflows)
    if not cfs:
        return None
    if _all_near_zero(cfs):
        return 0.0

    # Use provided bounds or fall back to module defaults
    lo = float(lower_bound) if lower_bound is not None else _DEFAULT_IRR_LOWER_BOUND
    hi = float(upper_bound) if upper_bound is not None else _DEFAULT_XIRR_UPPER_BOUND

    try:
        return _xirr_bisect(cfs, dates, lower_bound=lo, upper_bound=hi)
    except Exception:
        return None


def _xirr_bisect(
    cashflows: Sequence[float],
    dates: Sequence[datetime],
    lower_bound: float = _DEFAULT_IRR_LOWER_BOUND,
    upper_bound: float = _DEFAULT_XIRR_UPPER_BOUND,
) -> Optional[float]:
    """Bisection solver for XIRR with configurable bounds. Internal use only.

    Parameters
    ----------
    cashflows:
        Normalized cashflow series.
    dates:
        Matching datetime sequence.
    lower_bound:
        Lower search bound.
    upper_bound:
        Upper search bound.

    Returns
    -------
    Optional[float]
        XIRR or None if no root exists in the interval.
    """
    lo, hi = float(lower_bound), float(upper_bound)

    npv_lo = xnpv(lo, cashflows, dates)
    npv_hi = xnpv(hi, cashflows, dates)

    # Exact roots at bounds
    if abs(npv_lo) < 1e-8:
        return lo
    if abs(npv_hi) < 1e-8:
        return hi

    # No sign change = no root
    if not _have_opposite_signs(npv_lo, npv_hi):
        return None

    # Bisection loop (100 iterations sufficient for date arithmetic precision)
    for _ in range(100):
        mid = (lo + hi) / 2.0
        npv_mid = xnpv(mid, cashflows, dates)

        if abs(npv_mid) < 1e-8:
            return mid

        if _have_opposite_signs(npv_lo, npv_mid):
            hi = mid
        else:
            lo, npv_lo = mid, npv_mid

    # Best-effort approximation
    return (lo + hi) / 2.0


__all__ = [
    "npv",
    "irr",
    "xnpv",
    "xirr",
]
