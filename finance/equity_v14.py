# finance/equity_v14.py
"""Equity-focused performance metrics for DutchBay V14.

This module computes core equity investor metrics from a generic equity cashflow
series. It is the **only** place in the codebase that is allowed to define how
equity IRR, equity NPV, MOIC, DPI/RVPI/TVPI, payback and cash-on-cash are
calculated.

Other layers (scenario analytics, Monte Carlo, exports, CLI) must:
  - assemble equity cashflow series, and
  - call these functions to obtain metrics.

Sign convention
---------------
All cashflows are assumed to be *periodic* (e.g. annual) and ordered in time,
with negative values representing capital contributions and positive values
representing distributions or terminal equity value.

This mirrors standard project finance and private equity practice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from analytics.contracts_v14 import DownsideMetrics, EquityPerformance
from constants import DEFAULT_DISCOUNT_RATE
from finance.irr import irr as _irr
from finance.irr import npv as _npv

Number = float  # keep it simple internally


# =============================================================================
# Data structures
# =============================================================================


@dataclass
class EquityCashflowSummary:
    """
    Summary statistics for an equity cashflow series.

    Attributes
    ----------
    cashflows :
        Original cashflow series (periodic, ordered in time).
    total_invested :
        Sum of negative cashflows (absolute value).
    total_distributed :
        Sum of positive cashflows.
    cumulative_distributions :
        Total cumulative distributions (scalar), i.e. sum of positive cashflows.
    total_called :
        Same as total_invested (naming convenience).
    """

    cashflows: Sequence[Number]
    total_invested: float
    total_distributed: float
    cumulative_distributions: float
    total_called: float


# =============================================================================
# Internal helpers
# =============================================================================


def _npv_wrapper(rate: float, cashflows: Sequence[Number]) -> float:
    """Thin wrapper over the core NPV implementation."""
    return float(_npv(rate, list(cashflows)))


def _irr_wrapper(cashflows: Sequence[Number]) -> Optional[float]:
    """Thin wrapper over the core IRR implementation with safe handling."""
    try:
        value = _irr(list(cashflows))
    except (ZeroDivisionError, OverflowError, ValueError):
        return None
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


# =============================================================================
# Public utilities
# =============================================================================


def summarise_equity_cashflows(cashflows: Sequence[Number]) -> EquityCashflowSummary:
    """Build a summary object from a raw equity cashflow series.

    Parameters
    ----------
    cashflows :
        Equity cashflows (negative = contributions, positive = distributions).

    Returns
    -------
    EquityCashflowSummary
        Summary metrics for quick reuse across calculators.
    """
    total_invested = float(-sum(cf for cf in cashflows if cf < 0.0))
    total_distributed = float(sum(cf for cf in cashflows if cf > 0.0))
    cumulative_distributions = total_distributed

    return EquityCashflowSummary(
        cashflows=list(cashflows),
        total_invested=total_invested,
        total_distributed=total_distributed,
        cumulative_distributions=cumulative_distributions,
        total_called=total_invested,
    )


# =============================================================================
# Core calculators
# =============================================================================


def calculate_equity_irr(cashflows: Sequence[Number]) -> Optional[float]:
    """Calculate equity IRR for a cashflow series.

    Returns None if IRR cannot be computed or is not meaningful.
    """
    return _irr_wrapper(cashflows)


def calculate_equity_npv(
    cashflows: Sequence[Number],
    *,
    discount_rate: Optional[float] = None,
) -> Optional[float]:
    """Calculate equity NPV at a given discount rate.

    Parameters
    ----------
    cashflows :
        Equity cashflows (negative = contributions, positive = distributions).
    discount_rate :
        Discount rate as a decimal (e.g. 0.12 for 12%). If None, falls back
        to DEFAULT_DISCOUNT_RATE.
    """
    rate = float(discount_rate if discount_rate is not None else DEFAULT_DISCOUNT_RATE)
    try:
        return _npv_wrapper(rate, cashflows)
    except (ZeroDivisionError, OverflowError, ValueError):
        return None


def calculate_cash_on_cash(
    annual_distributions: Sequence[Number],
    total_equity_invested: float,
) -> List[float]:
    """Calculate annual cash-on-cash returns.

    Parameters
    ----------
    annual_distributions :
        Positive annual distributions (one per period).
    total_equity_invested :
        Total equity invested (absolute value of negative cashflows).

    Returns
    -------
    List[float]
        Annual cash-on-cash (distributions / total_equity_invested).

        If total_equity_invested <= 0, returns an empty list (no meaningful CoC).
    """
    if total_equity_invested <= 0.0:
        return []
    return [float(d) / float(total_equity_invested) for d in annual_distributions]


def calculate_moic(
    cumulative_distributions: float,
    current_nav: float,
    total_invested: float,
) -> Optional[float]:
    """Calculate Multiple on Invested Capital (MOIC).

    MOIC = (Total distributions + NAV) / Total invested.

    Returns None if total_invested <= 0.
    """
    if total_invested <= 0.0:
        return None
    total_distributions = float(cumulative_distributions)
    return float(total_distributions + float(current_nav)) / float(total_invested)


def calculate_payback_period(
    annual_distributions: Sequence[Number],
    initial_equity: float,
) -> Optional[float]:
    """Calculate payback period in years.

    Payback period is the time required for cumulative distributions to
    equal or exceed initial equity invested.

    Parameters
    ----------
    annual_distributions :
        Positive annual distributions (one per period).
    initial_equity :
        Initial equity invested (absolute value of negative cashflows).

    Returns
    -------
    Optional[float]
        Payback period in years (may be fractional), or None if payback is
        never achieved or initial_equity <= 0.
    """
    if initial_equity <= 0.0:
        return None

    cumulative = 0.0
    for idx, amount in enumerate(annual_distributions, start=1):
        amt = float(amount)
        cumulative += amt
        if cumulative >= initial_equity:
            # Linear interpolation within the year for fractional period:
            # shortfall at end of previous year divided by this year's dist.
            shortfall = cumulative - initial_equity
            year_dist = amt if amt != 0.0 else 1.0
            fraction = 1.0 - (shortfall / year_dist)
            return float(idx - 1) + fraction
    return None


def calculate_pe_triad(
    cumulative_distributions: float,
    current_nav: float,
    capital_called: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Compute DPI, RVPI and TVPI for a PE-style equity position.

    Definitions
    -----------
    - DPI  = Distributions / Capital Called
    - RVPI = NAV / Capital Called
    - TVPI = DPI + RVPI

    Parameters
    ----------
    cumulative_distributions :
        Total distributions returned to equity (cash only).
    current_nav :
        Current net asset value attributable to equity.
    capital_called :
        Total equity capital called over the life of the investment.

    Returns
    -------
    Tuple[Optional[float], Optional[float], Optional[float]]
        (dpi, rvpi, tvpi). If capital_called <= 0, returns (None, None, None).
    """
    if capital_called <= 0.0:
        return (None, None, None)

    called = float(capital_called)
    dpi = float(cumulative_distributions) / called
    rvpi = float(current_nav) / called
    return (dpi, rvpi, dpi + rvpi)


# =============================================================================
# Downside proxy
# =============================================================================


def _calculate_downside_proxy(annual_coc: Sequence[float]) -> Optional[float]:
    """Simple downside proxy for equity performance.

    For now, this is defined as the minimum annual cash-on-cash return
    observed over the life of the investment.

    Rationale:
      - Easy to explain to investment committees.
      - Gives a quick sense of how bad the worst year looks in % of equity.

    Returns
    -------
    Optional[float]
        Minimum annual CoC (could be negative if capital is added later),
        or None if annual_coc is empty.
    """
    if not annual_coc:
        return None
    return float(min(annual_coc))


# =============================================================================
# High-level aggregator
# =============================================================================


def calculate_equity_performance(
    cashflows: Sequence[Number],
    *,
    discount_rate: Optional[float] = None,
    current_nav: float = 0.0,
) -> Optional[EquityPerformance]:
    """Return an EquityPerformance snapshot for a given equity cashflow series.

    The series is assumed to be periodic and ordered in time, with negative
    values representing capital contributions and positive values representing
    distributions or terminal equity value.

    Parameters
    ----------
    cashflows :
        Equity cashflows (negative = contributions, positive = distributions).
    discount_rate :
        Discount rate for NPV; falls back to DEFAULT_DISCOUNT_RATE if None.
    current_nav :
        Current net asset value to be added to cumulative distributions for MOIC.

    Returns
    -------
    Optional[EquityPerformance]
        Structured equity metrics or None if there is no meaningful investment
        (e.g. total_invested <= 0).
    """
    summary = summarise_equity_cashflows(cashflows)
    if summary.total_invested <= 0.0:
        # Nothing invested, nothing to measure.
        return None

    # Annual distributions are the positive legs of the series
    annual_dists: List[float] = [cf for cf in summary.cashflows if cf > 0.0]

    equity_irr = calculate_equity_irr(summary.cashflows)
    equity_npv = calculate_equity_npv(summary.cashflows, discount_rate=discount_rate)

    annual_coc = calculate_cash_on_cash(annual_dists, summary.total_invested)
    average_coc: float = float(sum(annual_coc) / len(annual_coc)) if annual_coc else 0.0
    payback_period_years = calculate_payback_period(
        annual_dists,
        summary.total_invested,
    )
    moic = calculate_moic(
        summary.cumulative_distributions,
        current_nav,
        summary.total_invested,
    )

    # DPI/RVPI/TVPI are PE-style metrics
    if summary.total_invested > 0.0:
        dpi: Optional[float] = float(summary.total_distributed) / float(
            summary.total_invested
        )
    else:
        dpi = None

    if summary.total_invested > 0.0 and current_nav != 0.0:
        rvpi: Optional[float] = float(current_nav) / float(summary.total_invested)
    else:
        rvpi = None

    if dpi is not None and rvpi is not None:
        tvpi: Optional[float] = float(dpi + rvpi)
    else:
        tvpi = None

    downside_proxy = _calculate_downside_proxy(annual_coc)

    if downside_proxy is None:
        downside_metrics: Optional[DownsideMetrics] = None
    else:
        # For now we map the worst single-year cash-on-cash to max_drawdown.
        downside_metrics = DownsideMetrics(
            max_drawdown=downside_proxy,
        )

    return EquityPerformance(
        equity_irr=equity_irr,
        equity_npv=equity_npv,
        moic=moic,
        dpi=dpi,
        rvpi=rvpi,
        tvpi=tvpi,
        annual_coc=annual_coc,
        average_coc=average_coc,
        payback_period_years=payback_period_years,
        downside=downside_metrics,
    )


__all__ = [
    "EquityCashflowSummary",
    "summarise_equity_cashflows",
    "calculate_equity_irr",
    "calculate_equity_npv",
    "calculate_cash_on_cash",
    "calculate_moic",
    "calculate_payback_period",
    "calculate_pe_triad",
    "calculate_equity_performance",
]
