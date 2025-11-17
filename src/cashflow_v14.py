"""
cashflow_v14.py

V14 cashflow utilities: 23-period construction + operations timeline and
CFADS calculation that distinguishes construction, COD, and operational years.

Timeline convention:
    - construction_years: negative years (-c .. -1)
    - COD: year 0 (optional)
    - operations_years: 1..N
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TimelineConfig:
    """
    Configuration for building a V14-style timeline.

    Attributes:
        construction_years: number of pre-COD years (e.g. 2 for -2, -1).
        operations_years: number of post-COD operational years.
        include_cod_year: whether to explicitly include year 0.
    """
    construction_years: int
    operations_years: int
    include_cod_year: bool = True


def build_timeline(cfg: TimelineConfig) -> List[int]:
    """
    Build an integer timeline like [-2, -1, 0, 1, ..., 20].

    Args:
        cfg: TimelineConfig.

    Returns:
        List of year labels as integers.
    """
    c = cfg.construction_years
    o = cfg.operations_years
    years: List[int] = []

    # construction years: -c .. -1
    for k in range(c, 0, -1):
        years.append(-k)

    # COD (year 0)
    if cfg.include_cod_year:
        years.append(0)

    # operations: 1..o
    for k in range(1, o + 1):
        years.append(k)

    return years


def calculate_cfads_with_construction(
    years: List[int],
    gross_revenue: List[float],
    opex: List[float],
    tax: List[float],
    debt_service: List[float],
) -> List[float]:
    """
    Calculate CFADS over a mixed construction/operations timeline.

    This function assumes that revenue, opex, tax, and debt_service have
    already been shaped (e.g. zero revenue during construction).

    Args:
        years: Timeline as produced by build_timeline.
        gross_revenue: Revenue per period.
        opex: Operating expenses per period.
        tax: Tax per period.
        debt_service: Debt service per period.

    Returns:
        CFADS per period, same length as years.
    """
    n = len(years)
    for name, arr in [
        ("gross_revenue", gross_revenue),
        ("opex", opex),
        ("tax", tax),
        ("debt_service", debt_service),
    ]:
        if len(arr) != n:
            raise ValueError(f"{name} length must equal len(years)")

    cfads: List[float] = []
    for i in range(n):
        ebitda = gross_revenue[i] - opex[i]
        cfads_i = ebitda - tax[i] - debt_service[i]
        cfads.append(cfads_i)

    return cfads

    