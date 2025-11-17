"""
tax_calculator_v14.py

V14 tax and depreciation utilities.

Supports:
    - Straight-line depreciation.
    - Simple accelerated depreciation (via an acceleration factor).
    - Tax holiday logic with loss carry-forward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal


DepreciationMethod = Literal["straight_line", "accelerated"]


@dataclass
class TaxScenario:
    """
    Parameters defining a corporate tax regime and depreciation behaviour.
    """
    corporate_rate: float          # e.g. 0.24
    tax_holiday_years: int         # years with zero corporate tax
    tax_holiday_start_year: int    # first operational year with zero tax
    depreciation_method: DepreciationMethod
    depreciation_years: int        # years over which asset is depreciated
    accelerated_factor: float = 1.0  # >1.0 => accelerated


def build_depreciation_schedule(
    asset_value: float,
    operations_years: int,
    scenario: TaxScenario,
) -> List[float]:
    """
    Build an annual depreciation schedule over the operational horizon.

    Args:
        asset_value: Depreciable base (LKR).
        operations_years: Number of post-COD years to model.
        scenario: TaxScenario.

    Returns:
        List of depreciation charges per year (length = operations_years).
    """
    n = operations_years
    dep: List[float] = [0.0] * n
    if asset_value <= 0 or scenario.depreciation_years <= 0:
        return dep

    if scenario.depreciation_method == "straight_line":
        annual = asset_value / scenario.depreciation_years
        for i in range(min(n, scenario.depreciation_years)):
            dep[i] = annual
    else:
        base_years = scenario.depreciation_years
        rate = scenario.accelerated_factor / base_years
        remaining = asset_value
        for i in range(n):
            if remaining <= 1e-6:
                break
            dep_i = remaining * rate
            if dep_i > remaining:
                dep_i = remaining
            dep[i] = dep_i
            remaining -= dep_i

        # Normalise to ensure total depreciation == asset_value (within floating tolerance)
        total_dep = sum(dep)
        residual = asset_value - total_dep
        if abs(residual) > 1e-6:
            # Adjust the last positive depreciation entry
            last_idx = max((idx for idx, v in enumerate(dep) if v > 0.0), default=None)
            if last_idx is not None:
                dep[last_idx] += residual

    return dep


def calculate_tax_series(
    ebit: List[float],
    depreciation: List[float],
    scenario: TaxScenario,
    years: List[int],
) -> List[float]:
    """
    Calculate tax charges per period with holiday and loss carry-forward.

    Args:
        ebit: EBIT per period.
        depreciation: Depreciation per period.
        scenario: TaxScenario.
        years: Timeline including construction and operations.

    Returns:
        List of tax charges per period (same length as ebit).
    """
    n = len(ebit)
    if len(depreciation) != n or len(years) != n:
        raise ValueError("ebit, depreciation, and years must have same length")

    tax: List[float] = [0.0] * n
    loss_carry_forward = 0.0

    for i in range(n):
        year = years[i]

        # No corporate tax before COD (years <= 0)
        if year <= 0:
            tax[i] = 0.0
            continue

        taxable = ebit[i] - depreciation[i] - loss_carry_forward
        if taxable <= 0:
            loss_carry_forward = -taxable
            tax[i] = 0.0
            continue

        rel_year = year  # assume year 1 is first operational year
        in_holiday = (
            rel_year >= scenario.tax_holiday_start_year
            and rel_year < scenario.tax_holiday_start_year + scenario.tax_holiday_years
        )

        if in_holiday:
            tax[i] = 0.0
            # carry forward unchanged
        else:
            tax_charge = taxable * scenario.corporate_rate
            tax[i] = tax_charge
            loss_carry_forward = 0.0

    return tax

    