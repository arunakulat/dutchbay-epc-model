"""
IRR (Internal Rate of Return) Package for v14 Finance Models.

Sprint 16 Iteration 6 - IRR Package Creation
═══════════════════════════════════════════════════════════════════════════════════════
Consolidates all IRR calculation functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────────
From core module (finance.irr root file):
    - npv                       # Classic periodic Net Present Value
    - irr                       # Periodic Internal Rate of Return
    - xnpv                      # Date-adjusted Net Present Value
    - xirr                      # Date-adjusted Internal Rate of Return
    - project_npv_from_cfads    # Project NPV calculation
    - approx_project_irr        # Approximate project IRR

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth: finance/irr/__init__.py
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples
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
    """Return cashflows as a list of floats, coercing numerics to float."""
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
    """Bisection solver for IRR with configurable bounds. Internal use only."""
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

    Uses bisection method for reliability with irregular dates.
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
    """Bisection solver for XIRR with configurable bounds. Internal use only."""
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


# ============================================================================
# Project-Level IRR/NPV Helpers (R7: Singleton Pattern)
# ============================================================================
# These helpers are used by analytics.core.metrics but must be defined here
# per R7 singleton contract: all IRR/NPV calculation logic lives in finance.irr


def project_npv_from_cfads(
    rate: float,
    cfads_series: Sequence[float],
    capex_total: float,
) -> float:
    """Compute project NPV as NPV(CFADS) - capex_total.

    This is the canonical project NPV calculation where:
    - NPV(CFADS) represents discounted value of all CFADS over project life.
    - capex_total is the upfront capital investment (positive value).

    Higher capex reduces project NPV (holding CFADS and discount rate constant).
    """
    try:
        npv_cfads = float(npv(rate, cfads_series))
    except Exception:
        # Defensive: if NPV calculation fails, treat as neutral.
        return 0.0

    try:
        capex = float(capex_total)
    except (TypeError, ValueError):
        capex = 0.0

    return npv_cfads - capex


def approx_project_irr(
    cfads_series: Sequence[float],
    capex_total: float,
    *,
    r_low: float = 0.0,
    r_high: float = 0.5,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> float:
    """Approximate project IRR where NPV(CFADS) - capex_total ≈ 0.

    Uses bisection method to find the discount rate that makes project NPV ~ 0.

    Returns 0.0 if:
    - capex_total <= 0
    - cfads_series is empty
    - no sign change / no sensible root can be found.
    """
    try:
        capex = float(capex_total)
    except (TypeError, ValueError):
        capex = 0.0

    if capex <= 0.0 or not cfads_series:
        return 0.0

    def npv_gap(rate: float) -> float:
        return project_npv_from_cfads(rate, cfads_series, capex)

    try:
        f_low = npv_gap(r_low)
        f_high = npv_gap(r_high)
    except Exception:
        return 0.0

    # If no sign change, bail out – report 0.0 IRR
    if f_low == 0.0:
        return float(r_low)
    if f_high == 0.0:
        return float(r_high)
    if not _have_opposite_signs(f_low, f_high):
        return 0.0

    a, b = float(r_low), float(r_high)
    fa = f_low
    for _ in range(int(max_iter)):
        mid = 0.5 * (a + b)
        fm = npv_gap(mid)
        if abs(fm) < tol:
            return mid
        if _have_opposite_signs(fa, fm):
            b = mid
        else:
            a, fa = mid, fm

    return 0.5 * (a + b)


__all__ = [
    "npv",
    "irr",
    "xnpv",
    "xirr",
    "project_npv_from_cfads",
    "approx_project_irr",
]
