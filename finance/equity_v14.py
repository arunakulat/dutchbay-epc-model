# finance/equity_v14.py
"""Equity-focused performance metrics for DutchBay V14.

This module computes core equity investor metrics from a generic equity cashflow
series. It deliberately stays small and reusable so that other analytics layers
(scenario analytics, Monte Carlo, optimisation) can call a single canonical
implementation.

All cashflows are assumed to be *periodic* (e.g. annual) and ordered in time,
with the following sign convention:

- Negative values = equity contributions (capital calls).
- Positive values = equity distributions (dividends / buybacks / exit value).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import math

from constants import DEFAULT_DISCOUNT_RATE
from finance.irr import irr as _irr, npv as _npv
from analytics.contracts_v14 import EquityPerformance, DownsideMetrics


Number = float  # keep it simple internally


@dataclass
class EquityCashflowSummary:
    """Derived equity cashflow series.

    This keeps the mapping logic separate from the metric calculations and
    makes it easy to unit-test series construction independently.
    """

    cashflows: List[Number]
    """Full equity cashflow series (negative = contributions, positive = distributions)."""

    total_invested: float
    """Total equity contributed (absolute value of negative cashflows)."""

    cumulative_distributions: float
    """Total cash returned to equity (sum of positive cashflows)."""


def _clean_cashflows(cashflows: Sequence[float]) -> List[Number]:
    """Coerce an arbitrary numeric sequence into a clean List[float]."""
    cleaned: List[Number] = []
    for v in cashflows:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(f):
            continue
        cleaned.append(f)
    return cleaned


def summarise_equity_cashflows(cashflows: Sequence[float]) -> EquityCashflowSummary:
    """Build a summary object from a raw equity cashflow series.

    The first element is usually (but not required to be) the initial equity
    investment. We do not enforce a specific structure here; callers are
    responsible for assembling the series in the economic order they want
    to analyse.
    """
    cleaned = _clean_cashflows(cashflows)
    total_invested = -sum(cf for cf in cleaned if cf < 0.0)
    cumulative_distributions = sum(cf for cf in cleaned if cf > 0.0)
    return EquityCashflowSummary(
        cashflows=cleaned,
        total_invested=total_invested,
        cumulative_distributions=cumulative_distributions,
    )


def calculate_equity_irr(cashflows: Sequence[float]) -> Optional[float]:
    """Calculate the equity IRR for a series of periodic cashflows.

    Returns None if IRR cannot be computed (no sign change, degenerate series, etc.).
    """
    cleaned = _clean_cashflows(cashflows)
    if not cleaned:
        return None

    try:
        value = _irr(cleaned)
    except Exception:
        return None

    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def calculate_cash_on_cash(
    annual_distributions: Sequence[float],
    total_equity_invested: float,
) -> List[float]:
    """Year-by-year cash-on-cash return.

    If total_equity_invested is zero or negative, returns an empty list to avoid
    divide-by-zero issues.
    """
    if total_equity_invested <= 0.0:
        return []

    result: List[float] = []
    for dist in annual_distributions:
        try:
            f = float(dist)
        except (TypeError, ValueError):
            f = 0.0
        result.append(f / total_equity_invested)
    return result


def calculate_moic(
    cumulative_distributions: float,
    current_nav: float,
    total_invested: float,
) -> Optional[float]:
    """Multiple on invested capital.

    MOIC = (Distributions + NAV) / Invested Capital

    Returns None if total_invested is zero or negative.
    """
    if total_invested <= 0.0:
        return None
    return (float(cumulative_distributions) + float(current_nav)) / float(total_invested)


def calculate_payback_period(
    annual_distributions: Sequence[float],
    initial_equity: float,
) -> Optional[float]:
    """Compute the payback period in years.

    Returns the (possibly fractional) year in which cumulative distributions
    first equal or exceed the initial equity investment. Returns None if the
    series never pays back.
    """
    if initial_equity <= 0.0:
        return None

    cumulative = 0.0
    year_index = 0
    for dist in annual_distributions:
        year_index += 1
        try:
            f = float(dist)
        except (TypeError, ValueError):
            f = 0.0

        prev_cumulative = cumulative
        cumulative += f

        if cumulative >= initial_equity and f > 0.0:
            # Linear interpolation within the year for a smoother payback estimate.
            shortfall = initial_equity - prev_cumulative
            fraction = shortfall / f
            # We reached payback within this year; fraction of the year consumed.
            return (year_index - 1) + fraction

    return None


def _equity_npv(
    cashflows: Sequence[float],
    discount_rate: Optional[float] = None,
) -> Optional[float]:
    """Helper to compute NPV for an equity series.

    If discount_rate is None, DEFAULT_DISCOUNT_RATE is used.
    Returns None if the series is empty.
    """
    cleaned = _clean_cashflows(cashflows)
    if not cleaned:
        return None

    rate = float(discount_rate) if discount_rate is not None else DEFAULT_DISCOUNT_RATE
    try:
        value = _npv(rate, cleaned)
    except Exception:
        return None

    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def calculate_pe_triad(
    cumulative_distributions: float,
    current_nav: float,
    capital_called: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Compute DPI, RVPI and TVPI.

    - DPI  = Distributions / Capital Called
    - RVPI = NAV / Capital Called
    - TVPI = DPI + RVPI

    Returns a tuple (dpi, rvpi, tvpi), any of which may be None if capital_called
    is not positive.
    """
    if capital_called <= 0.0:
        return (None, None, None)

    called = float(capital_called)
    dpi = float(cumulative_distributions) / called
    rvpi = float(current_nav) / called
    return (dpi, rvpi, dpi + rvpi)


def calculate_equity_performance(
    cashflows: Sequence[float],
    *,
    discount_rate: Optional[float] = None,
    current_nav: float = 0.0,
) -> Optional[EquityPerformance]:
    """Return an EquityPerformance snapshot for a given equity cashflow series.

    The series is assumed to be periodic and ordered in time, with negative
    values representing capital contributions and positive values representing
    distributions or terminal equity value.
    """
    summary = summarise_equity_cashflows(cashflows)
    if summary.total_invested <= 0.0:
        # Nothing invested, nothing to measure.
        return None

    annual_dists: List[float] = [cf for cf in summary.cashflows if cf > 0.0]

    equity_irr = calculate_equity_irr(summary.cashflows)
    equity_npv = _equity_npv(summary.cashflows, discount_rate=discount_rate)

    annual_coc = calculate_cash_on_cash(annual_dists, summary.total_invested)
    average_coc: float = float(sum(annual_coc) / len(annual_coc)) if annual_coc else 0.0
    payback_period_years = calculate_payback_period(annual_dists, summary.total_invested)
    moic = calculate_moic(summary.cumulative_distributions, current_nav, summary.total_invested)

    dpi, rvpi, tvpi = calculate_pe_triad(
        cumulative_distributions=summary.cumulative_distributions,
        current_nav=current_nav,
        capital_called=summary.total_invested,
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
        downside=None,
    )

    