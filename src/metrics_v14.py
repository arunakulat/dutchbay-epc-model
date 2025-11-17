"""
metrics_v14.py

V14 metrics: DSCR series, LLCR, PLCR.

These utilities are generic and do not depend on any particular model
implementation beyond receiving CFADS, debt service, outstanding debt,
and discount rates.
"""

from __future__ import annotations

from typing import List
from math import isclose


def calculate_dscr_series(
    cfads: List[float],
    debt_service: List[float],
    years: List[int],
) -> List[float]:
    """
    Calculate DSCR per period for operational years (year > 0).

    For years <= 0, DSCR is returned as 0.0.

    Args:
        cfads: CFADS per period.
        debt_service: Debt service per period.
        years: Timeline of years.

    Returns:
        DSCR series of same length as inputs.
    """
    if len(cfads) != len(debt_service) or len(cfads) != len(years):
        raise ValueError("cfads, debt_service, and years must have same length")

    dscr: List[float] = []
    for c, ds, y in zip(cfads, debt_service, years):
        if y <= 0:
            dscr.append(0.0)
        else:
            if ds <= 0:
                dscr.append(float("inf") if c > 0 else 0.0)
            else:
                dscr.append(c / ds)
    return dscr


def _discount_factor(rate: float, t: int) -> float:
    return 1.0 / ((1.0 + rate) ** t)


def calculate_llcr(
    cfads: List[float],
    outstanding_debt: List[float],
    discount_rate: float,
    years: List[int],
) -> float:
    """
    Loan Life Coverage Ratio (LLCR).

    Uses discounted CFADS over remaining loan life divided by debt
    outstanding at COD (or the earliest non-negative year if 0 not present).
    """
    if not cfads or len(cfads) != len(outstanding_debt) or len(cfads) != len(years):
        raise ValueError("cfads, outstanding_debt, and years must have same length")

    pv_cfads = 0.0
    for c, y in zip(cfads, years):
        if y <= 0:
            continue
        pv_cfads += c * _discount_factor(discount_rate, y)

    try:
        idx_cod = years.index(0)
        debt_at_cod = outstanding_debt[idx_cod]
    except ValueError:
        debt_at_cod = outstanding_debt[0]

    if isclose(debt_at_cod, 0.0, abs_tol=1e-6):
        return float("inf")
    return pv_cfads / debt_at_cod


def calculate_plcr(
    cfads: List[float],
    project_discount_rate: float,
    total_debt: float,
    years: List[int],
) -> float:
    """
    Project Life Coverage Ratio (PLCR).

    Uses discounted CFADS over the entire project life against total debt.
    """
    if not cfads or len(cfads) != len(years):
        raise ValueError("cfads and years must have same length")

    pv_cfads = 0.0
    for c, y in zip(cfads, years):
        if y <= 0:
            continue
        pv_cfads += c * _discount_factor(project_discount_rate, y)

    if isclose(total_debt, 0.0, abs_tol=1e-6):
        return float("inf")
    return pv_cfads / total_debt

    