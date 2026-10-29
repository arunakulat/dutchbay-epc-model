"""Construction drawdowns and IDC (extracted from debt_v14)."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from finance.debt.helpers import _as_float

def calculate_construction_drawdowns(
    debt_total: float,
    drawdown_pct: Sequence[float],
    construction_periods: int,
) -> List[float]:
    """Allocate debt draws across construction periods from percentage weights."""
    weights = [float(x) for x in drawdown_pct]
    if construction_periods <= 0:
        return []
    if len(weights) < construction_periods:
        weights = weights + [0.0] * (construction_periods - len(weights))
    weights = weights[:construction_periods]
    total_w = sum(weights) or 1.0
    return [debt_total * (w / total_w) for w in weights]


def calculate_idc(
    debt_drawn_schedule: Sequence[float],
    interest_rate: float,
    construction_periods: int,
) -> Tuple[List[float], float]:
    """Interest during construction; capitalises IDC into balance during construction."""
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
