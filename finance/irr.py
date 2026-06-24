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

import math
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

import numpy_financial as npf

# Conservative mathematical defaults (used when no config provided)
# These are numerical stability guards, not business rules
_DEFAULT_IRR_LOWER_BOUND = -0.9999  # Prevents division by zero at -100%
_DEFAULT_IRR_UPPER_BOUND = 5.0  # 500% p.a. numerical stability cap
_DEFAULT_XIRR_UPPER_BOUND = 2.0  # 200% p.a. cap for dated cashflows

# Lower bound for the bespoke project-IRR bisection (approx_project_irr). Kept off the
# theoretical -100% floor on purpose: at -0.9999 the discount base (1+r)=1e-4 underflows
# over long CFADS series (~77+ periods), so npv() collapses to a spurious 0.0 and the
# bisection mistakes the bracket floor for an exact root. -0.99 is already "essentially
# total loss" (no real project IRR sits below it; DutchBay's are in [-3%, +6%]) and stays
# numerically safe out to ~150 periods.
_PROJECT_IRR_LOWER_BOUND = -0.99


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
    construction_years: int = 0,
) -> float:
    """Compute project NPV from a properly time-aligned cashflow vector.

    The project cashflow is assembled as a single signed series::

        [-capex_total] + [0.0] * construction_years + list(cfads_series)

    so capex sits at t=0, the ``construction_years`` build period produces no
    operating cash, and the FIRST operating CFADS is discounted at
    t=(construction_years + 1) — not at t=0.

    History (audit 2026-06-22, finding 2.0): the prior implementation returned
    ``NPV(cfads) - capex`` with ``npv`` enumerating ``cfads`` from t=0, so operating
    year 1 was undiscounted and the whole operating stream was pulled forward one
    period while the 2-year construction lag was ignored entirely. That overstated
    the canonical lender NPV (the reported +$2.03M was a timing artifact; correctly
    discounted it is negative). This convention now matches analytics.core.returns
    (``[-capex] + cfads``) and additionally honours the construction lag the debt
    engine already models.
    """
    try:
        capex = float(capex_total)
    except (TypeError, ValueError):
        capex = 0.0

    try:
        lag = max(0, int(construction_years))
    except (TypeError, ValueError):
        lag = 0

    project_vector = [-capex] + [0.0] * lag + [float(cf) for cf in cfads_series]

    try:
        return float(npv(rate, project_vector))
    except Exception:
        # Defensive: if NPV calculation fails, treat as neutral.
        return 0.0


def approx_project_irr(
    cfads_series: Sequence[float],
    capex_total: float,
    *,
    construction_years: int = 0,
    r_low: float = _PROJECT_IRR_LOWER_BOUND,
    r_high: float = 0.5,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> Optional[float]:
    """Approximate project IRR — the rate at which project NPV ≈ 0.

    Uses the SAME time-aligned cashflow vector as ``project_npv_from_cfads``
    (capex at t=0, ``construction_years`` zero-cash build periods, then CFADS),
    so the IRR and NPV conventions cannot diverge (audit 2026-06-22, finding 2.0).

    The default search bracket spans NEGATIVE rates (``_PROJECT_IRR_LOWER_BOUND``
    = -0.99) so a value-destructive project whose lifetime CFADS fall short of
    capex reports its true negative IRR rather than being silently floored at 0.0
    (honesty fix, 2026-06-23 M3e: the prior ``r_low=0.0`` default clamped every
    sub-zero project to exactly 0.0 — see the 5usc Kalpitiya case, true IRR ~-0.3%).
    The floor sits at -0.99 rather than the theoretical -100% to stay numerically
    safe over long horizons (see ``_PROJECT_IRR_LOWER_BOUND``); an explicit
    overflow guard below additionally protects against an extreme caller-supplied
    ``r_low``.

    If no sign change is found in the initial ``[r_low, r_high]`` bracket, ``r_high``
    is expanded geometrically toward the numerical cap (``_DEFAULT_IRR_UPPER_BOUND``
    = 5.0 / 500%) before declaring no root — this removes the upper "cliff" where a
    project whose true IRR exceeds the default ``r_high`` (0.5) had POSITIVE NPV at
    both ends and was wrongly reported as 0.0. The initial bracket is left untouched
    whenever a sign change already exists (every real DutchBay scenario, IRR in
    [-0.99, 0.5]), so those results are byte-identical.

    Returns ``None`` (IRR undefined) — distinct from a genuine 0% IRR — if:
    - capex_total <= 0
    - cfads_series is empty
    - the NPV cannot be evaluated, or
    - no sign change / no sensible root can be found in [r_low, 5.0].
    """
    try:
        capex = float(capex_total)
    except (TypeError, ValueError):
        capex = 0.0

    if capex <= 0.0 or not cfads_series:
        return None

    def npv_gap(rate: float) -> float:
        return project_npv_from_cfads(
            rate, cfads_series, capex, construction_years=construction_years
        )

    try:
        f_low = npv_gap(r_low)
        f_high = npv_gap(r_high)
    except Exception:
        return None

    # Overflow guard at extreme-negative rates: (1 + r_low)^-t explodes as r_low -> -1,
    # so for a long CFADS series npv_gap(r_low) can overflow to +inf and collapse the
    # bisection onto the bracket floor — a spurious near -100% "root" that moves the WRONG
    # way as cashflows improve. Walk r_low toward 0 until the boundary NPV is finite, so the
    # search still brackets the true root within the representable range. (No-op for the
    # ~20-year DutchBay scenarios — overflow only bites horizons of ~77+ periods.)
    _guard = 0
    while not math.isfinite(f_low) and r_low < r_high and _guard < 64:
        r_low *= 0.5
        _guard += 1
        try:
            f_low = npv_gap(r_low)
        except Exception:
            return None
    if not math.isfinite(f_low):
        return None

    if f_low == 0.0:
        return float(r_low)
    if f_high == 0.0:
        return float(r_high)

    # Upper-cliff guard: if the bracket holds no sign change, the true IRR may exceed
    # r_high (a project returning > r_high has POSITIVE NPV at both ends). Expand r_high
    # geometrically toward the numerical cap before declaring no root. This only runs when
    # the initial bracket already FAILED to bracket a root, so cases that do bracket one
    # (every real DutchBay scenario) are byte-identical.
    _g = 0
    while (
        not _have_opposite_signs(f_low, f_high)
        and r_high < _DEFAULT_IRR_UPPER_BOUND
        and _g < 64
    ):
        r_high = min(r_high * 2.0 if r_high > 0.0 else 0.5, _DEFAULT_IRR_UPPER_BOUND)
        _g += 1
        try:
            f_high = npv_gap(r_high)
        except Exception:
            return None
        if not math.isfinite(f_high):
            return None
        if f_high == 0.0:
            return float(r_high)

    if not _have_opposite_signs(f_low, f_high):
        return None

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
