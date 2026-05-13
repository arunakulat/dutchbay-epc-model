# finance/equity_v14.py
"""Equity-focused performance metrics for DutchBay V14.

This module computes core equity investor metrics from a generic equity cashflow
series. IRR and NPV logic remains delegated to ``finance.irr`` under the v14
singleton rule. Scenario-specific discount rates should be supplied by callers;
the local fallback below is only a numerical fallback for legacy callers that do
not pass a rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from analytics.contracts_v14 import EquityPerformance
from finance.irr import irr as _irr
from finance.irr import npv as _npv

Number = float
LEGACY_EQUITY_DISCOUNT_RATE = 0.10


@dataclass
class EquityCashflowSummary:
    """Summary statistics for an equity cashflow series."""

    cashflows: Sequence[Number]
    total_invested: float
    total_distributed: float
    cumulative_distributions: float
    total_called: float


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


def summarise_equity_cashflows(cashflows: Sequence[Number]) -> EquityCashflowSummary:
    """Build a summary object from a raw equity cashflow series."""
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


def calculate_equity_irr(cashflows: Sequence[Number]) -> Optional[float]:
    """Calculate equity IRR for a cashflow series."""
    return _irr_wrapper(cashflows)


def calculate_equity_npv(
    cashflows: Sequence[Number],
    *,
    discount_rate: Optional[float] = None,
) -> Optional[float]:
    """Calculate equity NPV at a given discount rate.

    ``discount_rate`` should normally be passed from the scenario/config. The
    local fallback is retained only for legacy import compatibility and is not a
    project assumption stored in ``constants.py``.
    """
    rate = float(
        discount_rate if discount_rate is not None else LEGACY_EQUITY_DISCOUNT_RATE
    )
    try:
        return _npv_wrapper(rate, cashflows)
    except (ZeroDivisionError, OverflowError, ValueError):
        return None


def calculate_cash_on_cash(
    annual_distributions: Sequence[Number],
    total_equity_invested: float,
) -> List[float]:
    """Calculate annual cash-on-cash returns."""
    if total_equity_invested <= 0.0:
        return []
    return [float(d) / float(total_equity_invested) for d in annual_distributions]


def calculate_moic(
    cumulative_distributions: float,
    current_nav: float,
    total_invested: float,
) -> Optional[float]:
    """Calculate Multiple on Invested Capital (MOIC)."""
    if total_invested <= 0.0:
        return None
    total_distributions = float(cumulative_distributions)
    return float(total_distributions + float(current_nav)) / float(total_invested)


def calculate_payback_period(
    annual_distributions: Sequence[Number],
    initial_equity: float,
) -> Optional[float]:
    """Calculate payback period in years."""
    if initial_equity <= 0.0:
        return None

    cumulative = 0.0
    for idx, amount in enumerate(annual_distributions, start=1):
        amt = float(amount)
        cumulative += amt
        if cumulative >= initial_equity:
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
    """Compute DPI, RVPI and TVPI for a PE-style equity position."""
    if capital_called <= 0.0:
        return (None, None, None)

    called = float(capital_called)
    dpi = float(cumulative_distributions) / called
    rvpi = float(current_nav) / called
    return (dpi, rvpi, dpi + rvpi)


def calculate_equity_performance(
    cashflows: Sequence[Number],
    *,
    discount_rate: Optional[float] = None,
    current_nav: float = 0.0,
) -> Optional[EquityPerformance]:
    """Return an EquityPerformance snapshot for a given equity cashflow series.

    The active ``analytics.contracts_v14.EquityPerformance`` contract exposes
    only equity_irr, equity_npv, equity_multiple and metadata. Additional PE
    metrics are therefore retained inside metadata rather than passed as unknown
    dataclass constructor fields.
    """
    summary = summarise_equity_cashflows(cashflows)
    if summary.total_invested <= 0.0:
        return None

    annual_dists: List[float] = [cf for cf in summary.cashflows if cf > 0.0]
    equity_irr = calculate_equity_irr(summary.cashflows)
    equity_npv = calculate_equity_npv(summary.cashflows, discount_rate=discount_rate)
    annual_coc = calculate_cash_on_cash(annual_dists, summary.total_invested)
    average_coc = float(sum(annual_coc) / len(annual_coc)) if annual_coc else 0.0
    payback_period_years = calculate_payback_period(
        annual_dists,
        summary.total_invested,
    )
    moic = calculate_moic(
        summary.cumulative_distributions,
        current_nav,
        summary.total_invested,
    )
    dpi, rvpi, tvpi = calculate_pe_triad(
        summary.cumulative_distributions,
        current_nav,
        summary.total_invested,
    )

    return EquityPerformance(
        equity_irr=equity_irr,
        equity_npv=equity_npv,
        equity_multiple=moic,
        metadata={
            "moic": moic,
            "dpi": dpi,
            "rvpi": rvpi,
            "tvpi": tvpi,
            "annual_coc": annual_coc,
            "average_coc": average_coc,
            "payback_period_years": payback_period_years,
            "current_nav": float(current_nav),
            "total_invested": summary.total_invested,
            "total_distributed": summary.total_distributed,
        },
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
