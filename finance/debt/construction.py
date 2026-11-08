"""Construction drawdowns and interest during construction."""

from __future__ import annotations

from typing import List, Tuple


def calculate_construction_drawdowns(
    total_debt: float,
    construction_schedule: List[float],
    drawdown_pct_per_year: List[float],
) -> List[float]:
    """Return the debt drawn at the start of each construction-schedule period.

    The capex phasing sets only how many periods are drawn; the amounts come from
    ``drawdown_pct_per_year``. Debt not drawn here is drawn at COD and accrues no
    interest during construction (see :func:`calculate_idc`).

    Args:
        total_debt: Debt principal before IDC.
        construction_schedule: Capex phasing; only its length is used.
        drawdown_pct_per_year: Fraction of ``total_debt`` drawn per period.

    Returns:
        The amount drawn in each period of ``construction_schedule``.
    """
    drawn_schedule: List[float] = []
    for i, _ in enumerate(construction_schedule):
        amt = (
            total_debt * float(drawdown_pct_per_year[i])
            if i < len(drawdown_pct_per_year)
            else 0.0
        )
        drawn_schedule.append(amt)
    return drawn_schedule


def calculate_idc(
    debt_drawn_schedule: List[float],
    interest_rate: float,
    construction_periods: int,
) -> Tuple[List[float], float]:
    """Return per-period interest and the IDC capitalised over the build.

    The convention (#1570): each draw is made at the start of its period and
    accrues a full period's interest on the balance, which includes the IDC
    capitalised in earlier periods. Interest is capitalised only for periods below
    ``construction_periods``; an entry at or beyond it is listed but not
    capitalised. A one-period build with half the debt drawn at financial close and
    the rest at COD therefore capitalises ``0.5 * D * r``, a year's interest on the
    average balance of an even draw (the placeholder in
    :func:`finance.debt.terms.placeholder_debt_drawdown_pct`).

    Args:
        debt_drawn_schedule: Amount drawn at the start of each period.
        interest_rate: Per-period interest rate as a decimal.
        construction_periods: The resolved construction-period count.

    Returns:
        The interest per listed period, and the total capitalised as IDC.
    """
    idc_schedule: List[float] = []
    balance = 0.0
    total_idc = 0.0
    for period in range(len(debt_drawn_schedule)):
        balance += debt_drawn_schedule[period]
        idc = balance * interest_rate
        idc_schedule.append(idc)
        if period < construction_periods:
            total_idc += idc
            balance += idc
    return idc_schedule, total_idc
