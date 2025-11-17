"""
equity_analysis_v14.py

V14 equity analysis utilities.

Provides:
    - generate_comprehensive_equity_table_v14: a detailed equity table with
      LKR and USD views and optional "bank-equivalent" yield.
    - calculate_payback_period: first year when cumulative equity cashflow
      turns non-negative.
"""

from __future__ import annotations

from typing import List, Dict, Optional

import pandas as pd


def generate_comprehensive_equity_table_v14(
    years: List[int],
    cfads: List[float],
    tax: List[float],
    debt_service: List[float],
    equity_commitment_lkr: float,
    usd_equity_pct: float,
    lkr_equity_pct: float,
    usd_fx_rates: List[float],
    bank_equivalent_rate: Optional[float] = None,
) -> pd.DataFrame:
    """
    Build a DataFrame showing equity flows and balances over time.

    Assumptions:
        - Equity is injected during construction years (years < 0),
          split evenly across construction periods.
        - After COD, equity cashflow is residual CFADS - tax - debt_service
          (floored at 0.0; no further equity injections modelled here).

    Args:
        years: Timeline (construction + COD + operations).
        cfads: CFADS per period.
        tax: Tax per period.
        debt_service: Debt service per period.
        equity_commitment_lkr: Total equity to be injected (LKR).
        usd_equity_pct: Fraction of equity considered USD-equity.
        lkr_equity_pct: Fraction considered LKR-equity (usd + lkr must = 1.0).
        usd_fx_rates: FX rates (LKR per USD) per period.
        bank_equivalent_rate: Optional; if provided, a simple "bank-equivalent"
            yield series is added.

    Returns:
        pandas.DataFrame with columns:
            year, cfads, tax, debt_service,
            equity_cashflow, cum_equity_invested, equity_balance,
            usd_equity_balance, lkr_equity_balance, usd_equity_balance_usd,
            (optionally) bank_equivalent_yield.
    """
    n = len(years)
    for name, arr in [
        ("cfads", cfads),
        ("tax", tax),
        ("debt_service", debt_service),
        ("usd_fx_rates", usd_fx_rates),
    ]:
        if len(arr) != n:
            raise ValueError(f"{name} length must equal len(years)")

    if abs(usd_equity_pct + lkr_equity_pct - 1.0) > 1e-6:
        raise ValueError("usd_equity_pct + lkr_equity_pct must equal 1.0")

    equity_cashflow: List[float] = []
    cum_invested: List[float] = []
    equity_balance: List[float] = []

    invested_so_far = 0.0
    balance = -equity_commitment_lkr  # initial equity outflow (from equity POV)

    construction_indices = [i for i, y in enumerate(years) if y < 0]
    num_construction = len(construction_indices)
    per_period_injection = (
        equity_commitment_lkr / num_construction if num_construction > 0 else 0.0
    )

    for i, y in enumerate(years):
        if y < 0:
            inj = per_period_injection
            equity_cf = -inj
            invested_so_far += inj
        else:
            distributable = cfads[i] - tax[i] - debt_service[i]
            equity_cf = max(distributable, 0.0)

        balance += equity_cf
        equity_cashflow.append(equity_cf)
        cum_invested.append(invested_so_far)
        equity_balance.append(balance)

    usd_equity_balance = [b * usd_equity_pct for b in equity_balance]
    lkr_equity_balance = [b * lkr_equity_pct for b in equity_balance]
    usd_equity_balance_usd = [
        (b / fx if fx > 0 else 0.0) for b, fx in zip(usd_equity_balance, usd_fx_rates)
    ]

    data: Dict[str, List[float]] = {
        "year": years,
        "cfads": cfads,
        "tax": tax,
        "debt_service": debt_service,
        "equity_cashflow": equity_cashflow,
        "cum_equity_invested": cum_invested,
        "equity_balance": equity_balance,
        "usd_equity_balance": usd_equity_balance,
        "lkr_equity_balance": lkr_equity_balance,
        "usd_equity_balance_usd": usd_equity_balance_usd,
    }

    if bank_equivalent_rate is not None and bank_equivalent_rate > 0:
        bank_yield: List[float] = []
        prev_balance = -equity_commitment_lkr
        for cf, y, bal in zip(equity_cashflow, years, equity_balance):
            if y <= 0 or prev_balance >= 0:
                bank_yield.append(0.0)
            else:
                bank_yield.append(cf / abs(prev_balance) if prev_balance != 0 else 0.0)
            prev_balance = bal
        data["bank_equivalent_yield"] = bank_yield

    df = pd.DataFrame(data)
    return df


def calculate_payback_period(
    years: List[int],
    equity_cashflow: List[float],
) -> Optional[int]:
    """
    Calculate the first year where cumulative equity cashflow >= 0.

    Args:
        years: Timeline (same length as equity_cashflow).
        equity_cashflow: Equity CF series.

    Returns:
        The year (int) at which cumulative CF turns non-negative, or None.
    """
    if len(years) != len(equity_cashflow):
        raise ValueError("years and equity_cashflow must have same length")

    cum = 0.0
    for y, cf in zip(years, equity_cashflow):
        cum += cf
        if cum >= 0:
            return y
    return None

    