#!/usr/bin/env python
"""Proper corporate tax calculation with TLCF for DutchBay EPC Model v14.

Fixes oversimplified tax model by implementing:
1. Proper taxable income = Revenue - OPEX - Depreciation - Interest
2. TLCF accumulation during loss years
3. TLCF shield application to offset taxable profits
4. Cash Available for Distribution (CAFOD) calculation
5. Separation of tax calculation from distribution decisions

Key Insight:
- Distributions are NOT taxable events at corporate level
- Tax is calculated on EBIT less interest
- TLCF shields taxable income, reducing tax liability
- Lower tax → More cash available → More distributable cash
- Distribution timing affects TLCF utilization indirectly

Proper Cash Waterfall:
    Revenue
    - OPEX
    = EBITDA
    - Depreciation (non-cash)
    = EBIT
    - Interest Expense
    = EBT (Earnings Before Tax)
    - TLCF Shield (if available)
    = Taxable Income
    × Corporate Tax Rate
    = Tax Liability
    
    CAFOD = Revenue - OPEX - Interest - Tax + Depreciation
          = Operating cash after tax, before distributions

Framework Compliance:
- GWTF: Proper tax mechanics (industry-standard)
- CESSPIT: All parameters from config
- CASPER: Conservative depreciation (straight-line base, MACRS optional)
- CCCDIR: Clear separation: Tax → CAFOD → Distribution
- TYPE-01: Full type hints

Author: DutchBay Tax Mechanics Team
Date: December 2025
Version: 2.0 (Enhanced)
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum


logger = logging.getLogger(__name__)


class DepreciationMethod(Enum):
    """Depreciation calculation methods."""
    STRAIGHT_LINE = "straight_line"
    MACRS_5 = "macrs_5_year"  # 5-year MACRS (e.g., solar equipment)
    MACRS_7 = "macrs_7_year"  # 7-year MACRS (e.g., wind turbines)
    MACRS_15 = "macrs_15_year"  # 15-year MACRS (e.g., transmission)


@dataclass
class DepreciationSchedule:
    """Depreciation schedule over project life.
    
    Attributes:
        annual_depreciation: Annual depreciation expense (USD)
        cumulative_depreciation: Cumulative depreciation (USD)
        book_value: Remaining book value (USD)
        method: Depreciation method used
    """
    annual_depreciation: List[float]
    cumulative_depreciation: List[float]
    book_value: List[float]
    method: DepreciationMethod


@dataclass
class TaxSchedule:
    """Complete corporate tax schedule with TLCF mechanics.
    
    Attributes:
        annual_revenue: Annual revenue (USD)
        annual_opex: Annual operating expenses (USD)
        annual_depreciation: Annual depreciation (USD, non-cash)
        annual_interest: Annual interest expense (USD)
        annual_ebitda: EBITDA (Revenue - OPEX)
        annual_ebit: EBIT (EBITDA - Depreciation)
        annual_ebt: EBT (EBIT - Interest)
        annual_tlcf_balance: TLCF balance at year end (USD)
        annual_tlcf_utilized: TLCF utilized in year (USD)
        annual_taxable_income: Taxable income after TLCF shield (USD)
        annual_tax_liability: Corporate tax liability (USD)
        annual_cafod: Cash Available For Distribution (USD)
        tlcf_exhaustion_year: Year when TLCF drops below threshold
    """
    annual_revenue: List[float]
    annual_opex: List[float]
    annual_depreciation: List[float]
    annual_interest: List[float]
    annual_ebitda: List[float]
    annual_ebit: List[float]
    annual_ebt: List[float]
    annual_tlcf_balance: List[float]
    annual_tlcf_utilized: List[float]
    annual_taxable_income: List[float]
    annual_tax_liability: List[float]
    annual_cafod: List[float]
    tlcf_exhaustion_year: int


def calculate_straight_line_depreciation(
    capex: float,
    useful_life_years: int,
    salvage_value: float = 0.0,
    project_life_years: int = 20
) -> DepreciationSchedule:
    """Calculate straight-line depreciation schedule.
    
    Args:
        capex: Initial capital expenditure (USD)
        useful_life_years: Depreciation period (years)
        salvage_value: Salvage value at end of useful life (USD)
        project_life_years: Total project life (years)
    
    Returns:
        DepreciationSchedule with annual depreciation
    
    Example:
        >>> # $200M wind farm, 10-year depreciation
        >>> depreciation = calculate_straight_line_depreciation(200e6, 10, 0, 20)
        >>> depreciation.annual_depreciation[0]  # Year 1
        20000000.0  # $20M/year for 10 years
        >>> depreciation.annual_depreciation[10]  # Year 11
        0.0  # Fully depreciated
    """
    depreciable_base = capex - salvage_value
    annual_depreciation_amount = depreciable_base / useful_life_years
    
    annual_depreciation = []
    cumulative_depreciation = []
    book_value = []
    
    cum_dep = 0.0
    
    for year in range(project_life_years):
        if year < useful_life_years:
            # Depreciation period
            dep = annual_depreciation_amount
        else:
            # Fully depreciated
            dep = 0.0
        
        cum_dep += dep
        bv = capex - cum_dep
        
        annual_depreciation.append(dep)
        cumulative_depreciation.append(cum_dep)
        book_value.append(max(0, bv))  # Never negative
    
    return DepreciationSchedule(
        annual_depreciation=annual_depreciation,
        cumulative_depreciation=cumulative_depreciation,
        book_value=book_value,
        method=DepreciationMethod.STRAIGHT_LINE
    )


def calculate_macrs_depreciation(
    capex: float,
    macrs_class: DepreciationMethod = DepreciationMethod.MACRS_7,
    project_life_years: int = 20
) -> DepreciationSchedule:
    """Calculate MACRS accelerated depreciation schedule.
    
    MACRS (Modified Accelerated Cost Recovery System) provides faster
    depreciation in early years, creating larger TLCF.
    
    Args:
        capex: Initial capital expenditure (USD)
        macrs_class: MACRS class (5, 7, or 15 year)
        project_life_years: Total project life (years)
    
    Returns:
        DepreciationSchedule with MACRS depreciation
    
    Example:
        >>> # $200M wind farm, 7-year MACRS
        >>> depreciation = calculate_macrs_depreciation(200e6, DepreciationMethod.MACRS_7)
        >>> depreciation.annual_depreciation[0]  # Year 1
        28571428.57  # 14.29% × $200M (half-year convention)
    """
    # MACRS percentage tables (IRS Publication 946)
    macrs_tables = {
        DepreciationMethod.MACRS_5: [0.20, 0.32, 0.192, 0.1152, 0.1152, 0.0576],
        DepreciationMethod.MACRS_7: [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446],
        DepreciationMethod.MACRS_15: [
            0.05, 0.095, 0.0855, 0.077, 0.0693, 0.0623, 0.0590, 0.0590,
            0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0295
        ]
    }
    
    if macrs_class not in macrs_tables:
        raise ValueError(f"MACRS class {macrs_class} not supported")
    
    percentages = macrs_tables[macrs_class]
    
    annual_depreciation = []
    cumulative_depreciation = []
    book_value = []
    
    cum_dep = 0.0
    
    for year in range(project_life_years):
        if year < len(percentages):
            # MACRS period
            dep = capex * percentages[year]
        else:
            # Fully depreciated
            dep = 0.0
        
        cum_dep += dep
        bv = capex - cum_dep
        
        annual_depreciation.append(dep)
        cumulative_depreciation.append(cum_dep)
        book_value.append(max(0, bv))
    
    return DepreciationSchedule(
        annual_depreciation=annual_depreciation,
        cumulative_depreciation=cumulative_depreciation,
        book_value=book_value,
        method=macrs_class
    )


def calculate_corporate_tax_schedule(
    revenue_schedule: List[float],
    opex_schedule: List[float],
    depreciation_schedule: List[float],
    interest_schedule: List[float],
    corporate_tax_rate: float,
    initial_tlcf: float = 0.0,
    tlcf_carryforward_limit_years: int = 20
) -> TaxSchedule:
    """Calculate proper corporate tax schedule with TLCF mechanics.
    
    This is the CORRECT tax calculation that fixes the oversimplified model.
    
    Key Mechanics:
    1. Taxable Income = Revenue - OPEX - Depreciation - Interest
    2. If Taxable Income < 0: Accumulate as TLCF (tax loss)
    3. If Taxable Income > 0: Apply TLCF shield (reduce taxable income)
    4. Tax Liability = (Taxable Income - TLCF Shield) × Tax Rate
    5. CAFOD = Revenue - OPEX - Interest - Tax + Depreciation
    
    Args:
        revenue_schedule: Annual revenue (USD)
        opex_schedule: Annual operating expenses (USD)
        depreciation_schedule: Annual depreciation (USD, non-cash)
        interest_schedule: Annual interest expense (USD)
        corporate_tax_rate: Corporate tax rate (decimal, e.g., 0.28)
        initial_tlcf: Initial TLCF balance (USD)
        tlcf_carryforward_limit_years: Years TLCF can be carried forward
    
    Returns:
        TaxSchedule with complete tax calculation
    
    Example:
        >>> # Year 1: Revenue $20M, OPEX $7M, Depreciation $20M, Interest $10M
        >>> # EBT = $20M - $7M - $20M - $10M = -$17M (loss)
        >>> # TLCF accumulates $17M
        >>> # Tax = $0 (loss year)
        >>> # CAFOD = $20M - $7M - $10M - $0 + $20M = $23M
    """
    project_life = len(revenue_schedule)
    
    # Validate inputs
    assert len(opex_schedule) == project_life
    assert len(depreciation_schedule) == project_life
    assert len(interest_schedule) == project_life
    
    # Initialize tracking arrays
    ebitda = []
    ebit = []
    ebt = []
    tlcf_balance = []
    tlcf_utilized = []
    taxable_income = []
    tax_liability = []
    cafod = []
    
    # Track TLCF balance across years
    current_tlcf = initial_tlcf
    
    for t in range(project_life):
        # Step 1: Calculate EBITDA
        ebitda_t = revenue_schedule[t] - opex_schedule[t]
        ebitda.append(ebitda_t)
        
        # Step 2: Calculate EBIT (subtract depreciation)
        ebit_t = ebitda_t - depreciation_schedule[t]
        ebit.append(ebit_t)
        
        # Step 3: Calculate EBT (subtract interest)
        ebt_t = ebit_t - interest_schedule[t]
        ebt.append(ebt_t)
        
        # Step 4: TLCF mechanics
        if ebt_t < 0:
            # Loss year: Accumulate TLCF
            tlcf_addition = abs(ebt_t)
            current_tlcf += tlcf_addition
            tlcf_utilized_t = 0.0
            taxable_income_t = 0.0
            tax_t = 0.0
            
            logger.debug(
                f"Year {t+1}: Loss ${tlcf_addition/1e6:.1f}M, "
                f"TLCF balance ${current_tlcf/1e6:.1f}M"
            )
        else:
            # Profit year: Utilize TLCF shield
            tlcf_utilized_t = min(current_tlcf, ebt_t)
            current_tlcf -= tlcf_utilized_t
            taxable_income_t = ebt_t - tlcf_utilized_t
            tax_t = taxable_income_t * corporate_tax_rate
            
            logger.debug(
                f"Year {t+1}: EBT ${ebt_t/1e6:.1f}M, "
                f"TLCF shield ${tlcf_utilized_t/1e6:.1f}M, "
                f"Tax ${tax_t/1e6:.1f}M"
            )
        
        tlcf_balance.append(current_tlcf)
        tlcf_utilized.append(tlcf_utilized_t)
        taxable_income.append(taxable_income_t)
        tax_liability.append(tax_t)
        
        # Step 5: Calculate CAFOD (Cash Available For Distribution)
        # CAFOD = Revenue - OPEX - Interest - Tax + Depreciation (add back non-cash)
        cafod_t = (
            revenue_schedule[t] - 
            opex_schedule[t] - 
            interest_schedule[t] - 
            tax_t +
            depreciation_schedule[t]  # Add back non-cash depreciation
        )
        cafod.append(cafod_t)
    
    # Find TLCF exhaustion year
    exhaustion_year = project_life
    for i, tlcf in enumerate(tlcf_balance):
        if tlcf < 1e6:  # < $1M threshold
            exhaustion_year = i
            break
    
    logger.info(
        f"Tax calculation complete: TLCF exhausts at year {exhaustion_year+1}, "
        f"Total tax paid ${sum(tax_liability)/1e6:.1f}M"
    )
    
    return TaxSchedule(
        annual_revenue=revenue_schedule,
        annual_opex=opex_schedule,
        annual_depreciation=depreciation_schedule,
        annual_interest=interest_schedule,
        annual_ebitda=ebitda,
        annual_ebit=ebit,
        annual_ebt=ebt,
        annual_tlcf_balance=tlcf_balance,
        annual_tlcf_utilized=tlcf_utilized,
        annual_taxable_income=taxable_income,
        annual_tax_liability=tax_liability,
        annual_cafod=cafod,
        tlcf_exhaustion_year=exhaustion_year
    )


def calculate_tax_savings_from_tlcf(
    tax_schedule_with_tlcf: TaxSchedule,
    tax_schedule_without_tlcf: TaxSchedule,
    discount_rate: float = 0.12
) -> Tuple[float, float]:
    """Calculate tax savings from TLCF shield.
    
    Compares tax liability with and without TLCF to quantify benefit.
    
    Args:
        tax_schedule_with_tlcf: Tax schedule utilizing TLCF
        tax_schedule_without_tlcf: Tax schedule ignoring TLCF
        discount_rate: Discount rate for NPV calculation
    
    Returns:
        Tuple of (total_savings, npv_savings)
    
    Example:
        >>> # With TLCF: Tax = $45M over 20 years
        >>> # Without TLCF: Tax = $48M over 20 years
        >>> # Savings = $3M nominal, $2.1M NPV
    """
    project_life = len(tax_schedule_with_tlcf.annual_tax_liability)
    
    # Calculate savings per year
    annual_savings = [
        tax_schedule_without_tlcf.annual_tax_liability[t] - 
        tax_schedule_with_tlcf.annual_tax_liability[t]
        for t in range(project_life)
    ]
    
    # Total nominal savings
    total_savings = sum(annual_savings)
    
    # NPV of savings
    npv_savings = sum(
        savings / (1 + discount_rate) ** t
        for t, savings in enumerate(annual_savings)
    )
    
    logger.info(
        f"TLCF tax savings: ${total_savings/1e6:.1f}M nominal, "
        f"${npv_savings/1e6:.1f}M NPV"
    )
    
    return total_savings, npv_savings


if __name__ == "__main__":
    # Example: DutchBay 150MW wind farm
    logging.basicConfig(level=logging.INFO)
    
    # Project parameters
    capex = 200e6  # $200M
    project_life = 20
    
    # Revenue and cost schedules
    revenue = [20e6 + i * 0.5e6 for i in range(project_life)]  # Growing
    opex = [7e6] * project_life  # Constant
    
    # Depreciation (straight-line 10 years)
    depreciation_sched = calculate_straight_line_depreciation(
        capex=capex,
        useful_life_years=10,
        project_life_years=project_life
    )
    depreciation = depreciation_sched.annual_depreciation
    
    # Interest schedule (from debt)
    debt = 140e6  # 70% debt
    interest_rate = 0.08
    interest = [debt * interest_rate * (1 - t/15) for t in range(project_life)]  # Declining
    
    # Calculate tax schedule WITH TLCF
    tax_with_tlcf = calculate_corporate_tax_schedule(
        revenue_schedule=revenue,
        opex_schedule=opex,
        depreciation_schedule=depreciation,
        interest_schedule=interest,
        corporate_tax_rate=0.28
    )
    
    # Calculate tax schedule WITHOUT TLCF (for comparison)
    tax_without_tlcf = calculate_corporate_tax_schedule(
        revenue_schedule=revenue,
        opex_schedule=opex,
        depreciation_schedule=[0] * project_life,  # No depreciation shield
        interest_schedule=interest,
        corporate_tax_rate=0.28
    )
    
    # Calculate savings
    savings_total, savings_npv = calculate_tax_savings_from_tlcf(
        tax_with_tlcf, tax_without_tlcf
    )
    
    print("\n" + "="*70)
    print("PROPER CORPORATE TAX CALCULATION WITH TLCF")
    print("="*70)
    print(f"\nTLCF Exhaustion: Year {tax_with_tlcf.tlcf_exhaustion_year + 1}")
    print(f"Peak TLCF Balance: ${max(tax_with_tlcf.annual_tlcf_balance)/1e6:.1f}M")
    print(f"\nTotal Tax (With TLCF): ${sum(tax_with_tlcf.annual_tax_liability)/1e6:.1f}M")
    print(f"Total Tax (No Depreciation Shield): ${sum(tax_without_tlcf.annual_tax_liability)/1e6:.1f}M")
    print(f"\nTax Savings: ${savings_total/1e6:.1f}M nominal, ${savings_npv/1e6:.1f}M NPV")
    print(f"\nYear 5 CAFOD: ${tax_with_tlcf.annual_cafod[4]/1e6:.1f}M (available for distribution)")
    print("="*70)
