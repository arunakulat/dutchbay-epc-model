"""
debt_v14.py

V14 debt utilities: drawdown schedule, Interest During Construction (IDC),
and a simple debt schedule with a grace period and sculpting helper.

This module is intentionally standalone. Integration with the rest of
the DutchBay EPC model is done by callers (e.g., core pipeline code).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional


@dataclass
class DebtProfile:
    """
    Structural parameters for a single debt facility.

    Attributes:
        total_debt: Total debt principal at COD (LKR).
        annual_interest_rate: Nominal annual interest rate (e.g. 0.08 for 8%).
        tenor_years: Total loan life in years (including grace).
        grace_years: Years with interest-only payments.
        construction_years: Number of pre-COD drawdown periods.
    """
    total_debt: float
    annual_interest_rate: float
    tenor_years: int
    grace_years: int
    construction_years: int


def calculate_drawdown_schedule(
    profile: DebtProfile,
    drawdown_weights: Optional[List[float]] = None,
) -> List[float]:
    """
    Calculate a drawdown schedule over the construction period.

    Default behaviour for construction_years == 3 is 40/40/20.
    For other values, equal weights are used unless drawdown_weights is given.

    Args:
        profile: DebtProfile with total_debt and construction_years.
        drawdown_weights: Optional weights (length == construction_years).

    Returns:
        List of drawdown amounts per construction period (length = construction_years).
    """
    n = profile.construction_years
    if n <= 0:
        return []

    if drawdown_weights is None:
        if n == 3:
            drawdown_weights = [0.4, 0.4, 0.2]
        else:
            drawdown_weights = [1.0 / n] * n

    if len(drawdown_weights) != n:
        raise ValueError("drawdown_weights length must equal construction_years")

    total_w = sum(drawdown_weights)
    if total_w <= 0:
        raise ValueError("drawdown_weights must sum to > 0")

    result = [profile.total_debt * w / total_w for w in drawdown_weights]

    # Minor rounding correction to ensure the sum matches total_debt
    diff = profile.total_debt - sum(result)
    if abs(diff) > 1e-6:
        result[-1] += diff

    return result


def calculate_idc(
    drawdowns: List[float],
    annual_interest_rate: float,
    capitalize: bool = True,
) -> Tuple[float, List[float]]:
    """
    Calculate Interest During Construction (IDC) for a sequence of drawdowns.

    Args:
        drawdowns: List of draw amounts per construction period.
        annual_interest_rate: Interest rate per period (assumed annual).
        capitalize: If True, interest is added to outstanding principal.

    Returns:
        total_idc: Total IDC across construction.
        period_interest: List of IDC per construction period.
    """
    outstanding = 0.0
    period_interest: List[float] = []

    for draw in drawdowns:
        outstanding += draw
        interest = outstanding * annual_interest_rate
        period_interest.append(interest)
        if capitalize:
            outstanding += interest

    total_idc = sum(period_interest)
    return total_idc, period_interest


def build_debt_schedule_with_grace(
    profile: DebtProfile,
    cfads_after_cod: List[float],
    target_dscr: float,
) -> Dict[str, List[float]]:
    """
    Build a simple annual debt service schedule with an initial grace period
    followed by sculpted repayments against CFADS.

    This aims to be transparent and deterministic, not a perfect copy of any
    specific bank term sheet.

    Args:
        profile: DebtProfile for the facility.
        cfads_after_cod: CFADS for each operational year (length >= tenor_years).
        target_dscr: Target DSCR used to approximate sculpting.

    Returns:
        A dict with lists (length = tenor_years):
            "opening_balance"
            "interest"
            "principal"
            "debt_service"
            "closing_balance"
    """
    if profile.tenor_years <= 0:
        raise ValueError("tenor_years must be > 0")
    if profile.grace_years < 0 or profile.grace_years > profile.tenor_years:
        raise ValueError("invalid grace_years")
    if len(cfads_after_cod) < profile.tenor_years:
        raise ValueError("cfads_after_cod must have at least tenor_years elements")
    if target_dscr <= 0:
        raise ValueError("target_dscr must be > 0")

    n = profile.tenor_years
    g = profile.grace_years
    r = profile.annual_interest_rate

    opening: List[float] = []
    interest: List[float] = []
    principal: List[float] = []
    debt_service: List[float] = []
    closing: List[float] = []

    outstanding = profile.total_debt

    # Precompute "affordable" principal based on CFADS and target DSCR
    affordable_principal: List[float] = []
    for year in range(n):
        cfads = cfads_after_cod[year]
        max_debt_service = cfads / target_dscr
        affordable = max(max_debt_service - outstanding * r, 0.0)
        affordable_principal.append(affordable)

    total_affordable = sum(affordable_principal[g:])
    if total_affordable <= 0:
        # fallback: flat amortisation after grace
        flat_principal = outstanding / max(n - g, 1)
        sculpting_factors = [0.0] * g + [1.0] * (n - g)
    else:
        sculpting_factors = [0.0] * g + [
            p / total_affordable for p in affordable_principal[g:]
        ]
        flat_principal = outstanding

    for year in range(n):
        opening.append(outstanding)
        interest_y = outstanding * r

        if year < g:
            principal_y = 0.0
        else:
            if total_affordable <= 0:
                principal_y = flat_principal
            else:
                principal_y = flat_principal * sculpting_factors[year]
            if principal_y > outstanding:
                principal_y = outstanding

        ds_y = interest_y + principal_y
        closing_y = outstanding - principal_y

        interest.append(interest_y)
        principal.append(principal_y)
        debt_service.append(ds_y)
        closing.append(closing_y)

        outstanding = closing_y

    # Final dust correction
    if abs(closing[-1]) > 1e-4:
        correction = closing[-1]
        principal[-1] += correction
        debt_service[-1] += correction
        closing[-1] = 0.0

    return {
        "opening_balance": opening,
        "interest": interest,
        "principal": principal,
        "debt_service": debt_service,
        "closing_balance": closing,
    }

    