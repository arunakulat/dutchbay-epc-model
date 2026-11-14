"""Construction drawdowns and interest during construction."""

from __future__ import annotations

import math
from typing import List, Tuple

_DRAWDOWN_SUM_TOL = 1e-6


def calculate_construction_drawdowns(
    total_debt: float,
    construction_schedule: List[float],
    drawdown_pct_per_year: List[float],
) -> List[float]:
    """Return the debt drawn at the start of each construction-schedule period.

    The capex phasing sets only how many periods are drawn; the amounts come from
    ``drawdown_pct_per_year``. Refuses schedules whose draws do not match the
    phasing length or fail to sum to 1.0 (except the documented single-period
    ``[0.5]`` COD-split placeholder convention from #1570) (#1507).

    Args:
        total_debt: Debt principal before IDC.
        construction_schedule: Capex phasing; only its length is used.
        drawdown_pct_per_year: Fraction of ``total_debt`` drawn per period.

    Returns:
        The amount drawn in each period of ``construction_schedule``.
    """
    n_periods = len(construction_schedule)
    n_draws = len(drawdown_pct_per_year)
    draws = [float(x) for x in drawdown_pct_per_year]
    if any(not math.isfinite(d) or d < 0.0 for d in draws):
        raise ValueError(
            f"drawdown_pct_per_year {draws!r} must contain finite non-negative "
            "fractions (#1507)."
        )
    if n_periods > 0:
        if n_draws < n_periods:
            raise ValueError(
                f"construction_schedule has {n_periods} period(s) but "
                f"drawdown_pct_per_year has only {n_draws} entry/entries; supply a "
                "drawdown fraction per construction period (#1507)."
            )
        is_single_period_cod_placeholder = (
            n_periods == 1
            and n_draws == 1
            and math.isclose(draws[0], 0.5, abs_tol=1e-9)
        )
        draw_sum = sum(draws)
        if not is_single_period_cod_placeholder and not math.isclose(
            draw_sum, 1.0, abs_tol=_DRAWDOWN_SUM_TOL
        ):
            raise ValueError(
                f"drawdown_pct_per_year {draws!r} sums to {draw_sum:.6f}, expected 1.0 "
                "(within 1e-6) so IDC reflects the full facility (#1507)."
            )
    elif n_draws > 0 and not math.isclose(
        sum(float(x) for x in drawdown_pct_per_year), 1.0, abs_tol=_DRAWDOWN_SUM_TOL
    ):
        raise ValueError(
            "drawdown_pct_per_year must sum to 1.0 (or be empty when construction_schedule is empty) (#1507)."
        )

    drawn_schedule: List[float] = []
    for i, _ in enumerate(construction_schedule):
        amt = total_debt * float(drawdown_pct_per_year[i])
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
    capitalised in earlier periods. Refuses when ``construction_periods`` exceeds
    ``len(debt_drawn_schedule)`` so unscheduled build years cannot silently accrue
    zero IDC (#1507).

    Args:
        debt_drawn_schedule: Amount drawn at the start of each period.
        interest_rate: Per-period interest rate as a decimal.
        construction_periods: The resolved construction-period count.

    Returns:
        The interest per listed period, and the total capitalised as IDC.
    """
    if construction_periods > len(debt_drawn_schedule):
        raise ValueError(
            f"construction_periods ({construction_periods}) exceeds "
            f"debt_drawn_schedule length ({len(debt_drawn_schedule)}); extend "
            "construction_schedule / drawdown_pct_per_year so every build period "
            "accrues IDC (#1507)."
        )
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
