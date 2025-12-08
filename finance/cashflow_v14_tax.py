from __future__ import annotations

from typing import List, Optional, Sequence, Tuple


def _compute_depreciation_schedule(
    capex_total: Optional[float],
    depreciation_years: int,
    enhanced_capital_allowance_pct: float,
) -> List[float]:
    """
    Build a straight-line depreciation schedule over depreciation_years.

    If capex_total is None or depreciation_years <= 0, an empty schedule
    is returned.

    Notes
    -----
    capex_total here represents the *depreciable base* in LKR, i.e.
    the portion of project capex eligible for tax depreciation under
    the chosen regime (after any enhanced capital allowance factors).
    """
    if capex_total is None or depreciation_years <= 0:
        return []
    total_depreciable = capex_total * enhanced_capital_allowance_pct
    annual = total_depreciable / float(depreciation_years)
    return [annual] * depreciation_years


def calculate_tax_with_interest_shield(
    pretax_cfads: float,
    corporate_tax_rate: float,
    capex_depreciable_lkr: Optional[float],
    depreciation_years: int,
    interest_expense_lkr: float,
    year_index: int,
    tax_holiday_years: int = 0,
    tax_holiday_start_year: int = 1,
    enhanced_capital_allowance_pct: float = 1.0,
    precomputed_depr_schedule: Optional[Sequence[float]] = None,
) -> Tuple[float, float]:
    """
    Calculate BOI-compliant tax with interest shield for a given year.

    Parameters
    ----------
    pretax_cfads :
        CFADS before tax and interest shield.
    corporate_tax_rate :
        Headline corporate tax rate (decimal; 0.24 = 24%).
        If <= 0, no tax is applied.
    capex_depreciable_lkr :
        Depreciable capex base in LKR (or None to disable depreciation).
        This is *not* the entire EPC/financed capex; it is the portion of
        project cost that the tax code allows to be depreciated.
    depreciation_years :
        Straight-line depreciation horizon in years.
    interest_expense_lkr :
        Interest expense for the year (LKR).
    year_index :
        Zero-based year index.
    tax_holiday_years :
        Number of tax holiday years (0 = none).
    tax_holiday_start_year :
        1-based start year of the tax holiday.
    enhanced_capital_allowance_pct :
        Factor for enhanced capital allowance (e.g. 1.2 for 120%).
    precomputed_depr_schedule :
        Optional pre-computed depreciation schedule. When provided, it is
        used directly instead of re-building the schedule.

    Returns
    -------
    (tax_lkr, depreciation_for_year_lkr)
    """
    if corporate_tax_rate <= 0.0:
        return 0.0, 0.0

    current_year = year_index + 1

    # Determine whether the year is within the tax holiday window.
    in_holiday = False
    if tax_holiday_years > 0:
        start = tax_holiday_start_year
        end = start + tax_holiday_years - 1
        in_holiday = start <= current_year <= end

    if precomputed_depr_schedule is not None:
        depreciation_schedule: Sequence[float] = precomputed_depr_schedule
    else:
        if capex_depreciable_lkr is None or depreciation_years <= 0:
            depreciation_schedule = []
        else:
            depreciation_schedule = _compute_depreciation_schedule(
                capex_depreciable_lkr,
                depreciation_years,
                enhanced_capital_allowance_pct,
            )

    if year_index < len(depreciation_schedule):
        depreciation_for_year = float(depreciation_schedule[year_index])
    else:
        depreciation_for_year = 0.0

    if in_holiday:
        # During BOI tax holiday, tax is zero regardless of taxable income.
        return 0.0, depreciation_for_year

    taxable_income = pretax_cfads - depreciation_for_year - interest_expense_lkr
    taxable_income = max(0.0, taxable_income)
    tax = taxable_income * corporate_tax_rate
    return tax, depreciation_for_year


__all__ = ["_compute_depreciation_schedule", "calculate_tax_with_interest_shield"]
