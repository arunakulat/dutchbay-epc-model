"""
Project Finance Metrics Module - DutchBay V13 (v2.1 - Tax Shield Aware)

COMPLIANCE:
-----------
- IFC, World Bank, ADB coverage ratio standards
- Sri Lanka Inland Revenue Act (interest expense deductibility)
- Commercial bank credit assessment requirements
- Basel III capital adequacy frameworks

TAX TREATMENT (SRI LANKA):
---------------------------
- Interest on debt IS TAX-DEDUCTIBLE
- CFADS calculation accounts for interest tax shield
- Tax = (Revenue - Statutory - OPEX - Depreciation - Interest) × Tax Rate
- CFADS = Post-tax cash flow (benefits from interest deductibility)

CRITICAL CFADS DEFINITION:
---------------------------
CFADS = Revenue (LKR)
        - Statutory deductions (success fee, environmental, social)
        - Operating expenses (OPEX)
        - Cash Taxes (calculated AFTER interest expense deduction)
        - Risk adjustments

Where Cash Taxes = Taxable Income × Tax Rate
And Taxable Income = Revenue - Statutory - OPEX - Depreciation - Interest Expense

NOTE: Interest expense is NOT deducted from CFADS itself (only from taxable
      income for tax calculation). CFADS is used to SERVICE debt (pay both
      interest and principal). The tax benefit of interest deductibility is
      captured in the reduced tax amount.

DSCR FORMULA:
-------------
DSCR = CFADS (post-tax, post all deductions) / Total Debt Service (LKR)

For multi-currency projects:
Total Debt Service (LKR) = LKR Debt Service + (USD Debt Service × FX Rate)

FEATURES:
---------
- DSCR (Debt Service Coverage Ratio) calculation and tracking
- LLCR (Loan Life Coverage Ratio) - P0-1C Phase 1
- PLCR (Project Life Coverage Ratio) - P0-1C Phase 2
- Multi-period covenant monitoring
- Multi-currency (LKR/USD) debt service handling with FX conversion
- Integration with debt.py and cashflow.py modules

VERSION HISTORY:
----------------
v2.0 (2025-11-15): FX handling and strict typing
v2.1 (2025-11-15): Tax shield awareness and Sri Lanka compliance

Author: DutchBay V13 Team
Version: 2.1 (Tax Shield Aware)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

# Import only what exists in irr.py
try:
    from .irr import irr
except ImportError:
    irr = None

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('dutchbay.finance.metrics')

__all__ = [
    "build_annual_rows_with_fx",
    "compute_dscr_series",
    "summarize_dscr",
    "calculate_llcr",
    "calculate_plcr",
    "compute_llcr_plcr",
    "check_llcr_covenant",
    "check_plcr_covenant",
    "summarize_project_metrics",
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _to_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    """Safe float conversion with default."""
    try:
        return float(x) if x is not None else default
    except Exception:
        return default


def _npv(cashflows: List[float], discount_rate: float, start_period: int = 0) -> float:
    """
    Calculate Net Present Value of cashflow series.
    
    Parameters
    ----------
    cashflows : list of float
        Annual cashflows (CFADS)
    discount_rate : float
        Annual discount rate (decimal, e.g., 0.10 for 10%)
    start_period : int, default 0
        Starting period for discounting (0 = now)
    
    Returns
    -------
    float
        NPV of cashflows
    """
    if not cashflows or discount_rate < 0:
        return 0.0
    
    npv_val = 0.0
    for i, cf in enumerate(cashflows):
        period = start_period + i
        npv_val += cf / ((1 + discount_rate) ** period)
    
    return npv_val


# ============================================================================
# FX-AWARE ANNUAL_ROWS BUILDER (Bulletproofing)
# ============================================================================

def build_annual_rows_with_fx(
    cfads_lkr: List[float],
    lkr_debt_service: List[float],
    usd_debt_service: List[float],
    fx_rates: List[float],
    debt_outstanding_lkr: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Build annual_rows with FX-converted total debt service.
    
    CRITICAL: This ensures multi-currency debt is properly aggregated 
    in common currency (LKR) before DSCR calculation.
    
    TAX SHIELD NOTE: The cfads_lkr input should be POST-TAX CFADS from
    cashflow.py, which already accounts for interest expense tax deductibility.
    
    Parameters
    ----------
    cfads_lkr : list of float
        CFADS in LKR for each year (POST-TAX, post all deductions)
    lkr_debt_service : list of float
        LKR tranche debt service for each year (interest + principal)
    usd_debt_service : list of float
        USD tranche debt service for each year (interest + principal)
    fx_rates : list of float
        LKR/USD exchange rate for each year
    debt_outstanding_lkr : list of float, optional
        Total debt outstanding in LKR (if needed for LLCR/PLCR)
    
    Returns
    -------
    list of dict
        Annual rows ready for metrics.py DSCR calculation
    """
    annual_rows = []
    n_years = len(cfads_lkr)
    
    for i in range(n_years):
        total_ds_lkr = lkr_debt_service[i] + (usd_debt_service[i] * fx_rates[i])
        row = {
            'year': i + 1,
            'cfads_usd': cfads_lkr[i],  # Legacy field name; actual LKR
            'debt_service': total_ds_lkr,  # FX-converted total
            'fx_rate': fx_rates[i]  # For reference/audit
        }
        if debt_outstanding_lkr is not None:
            row['debt_outstanding'] = debt_outstanding_lkr[i]
        annual_rows.append(row)
    
    return annual_rows


# ============================================================================
# DSCR CALCULATIONS
# ============================================================================

def compute_dscr_series(annual_rows: List[Dict[str, Any]]) -> List[Optional[float]]:
    """
    Calculate DSCR for each year.
    
    DSCR_t = CFADS_t / DebtService_t
    
    CRITICAL REQUIREMENTS (SRI LANKA TAX-COMPLIANT):
    ------------------------------------------------
    - 'cfads_usd': Must be POST-TAX CFADS from cashflow.py
      Calculation sequence:
        1. Revenue - Statutory deductions - OPEX = Pre-tax cash flow
        2. Taxable Income = Pre-tax cash flow - Depreciation - Interest Expense
        3. Tax = Taxable Income × Tax Rate (interest expense is tax-deductible)
        4. CFADS = Pre-tax cash flow - Tax - Risk adjustment
      
    - 'debt_service': Must be in COMMON CURRENCY (LKR)
      For multi-currency projects: LKR_DS + (USD_DS × FX_rate)
      
    - Interest expense is deducted for TAX calculation (reducing tax liability)
      but NOT from CFADS itself, since CFADS is used to PAY debt service
    
    Parameters
    ----------
    annual_rows : list of dict
        Each row must contain:
        - 'cfads_usd': float (POST-TAX CFADS in LKR, despite legacy field name)
        - 'debt_service': float (Total debt service in LKR)
    
    Returns
    -------
    list of float or None
        DSCR for each year; None where debt service is zero
    """
    dscr_series = []
    for row in annual_rows:
        cfads = _to_float(row.get('cfads_usd'), 0.0)
        ds = _to_float(row.get('debt_service'), 0.0)
        
        if ds > 0:
            dscr = cfads / ds
        else:
            dscr = None  # Undefined when no debt service
        
        dscr_series.append(dscr)
    
    return dscr_series


def summarize_dscr(dscr_series: List[Optional[float]]) -> Dict[str, Any]:
    """
    Compute summary statistics for DSCR series.
    
    Returns
    -------
    dict
        {
            'dscr_min': float or None,
            'dscr_avg': float or None,
            'dscr_max': float or None,
            'years_with_dscr': int,
            'years_below_1_0': int,
            'years_below_1_3': int
        }
    """
    valid = [d for d in dscr_series if d is not None]
    
    if not valid:
        return {
            'dscr_min': None,
            'dscr_avg': None,
            'dscr_max': None,
            'years_with_dscr': 0,
            'years_below_1_0': 0,
            'years_below_1_3': 0
        }
    
    return {
        'dscr_min': min(valid),
        'dscr_avg': sum(valid) / len(valid),
        'dscr_max': max(valid),
        'years_with_dscr': len(valid),
        'years_below_1_0': sum(1 for d in valid if d < 1.0),
        'years_below_1_3': sum(1 for d in valid if d < 1.3)
    }


# ============================================================================
# LLCR CALCULATION (P0-1C Phase 1)
# ============================================================================

def calculate_llcr(
    cfads_series: List[float],
    debt_outstanding_series: List[float],
    discount_rate: float = 0.10,
    start_year: int = 0
) -> Dict[str, Any]:
    """
    Calculate Loan Life Coverage Ratio (LLCR) for each period.
    
    LLCR = NPV(future CFADS over remaining loan life) / Outstanding Debt
    
    This is the PRIMARY coverage metric used by DFIs and commercial lenders
    for project finance credit decisions.
    
    Parameters
    ----------
    cfads_series : list of float
        Cash Flow Available for Debt Service for each year (POST-TAX)
    debt_outstanding_series : list of float
        Outstanding debt balance at start of each year
    discount_rate : float, default 0.10
        Discount rate for NPV calculation (typically WACC or lender's hurdle)
    start_year : int, default 0
        Starting year index for LLCR calculation
    
    Returns
    -------
    dict
        {
            'llcr_series': list of float,
            'llcr_min': float,
            'llcr_avg': float,
            'years_calculated': int,
            'calculation_details': list of dict
        }
    
    Notes
    -----
    - LLCR ≥ 1.20x is typical DFI covenant
    - LLCR ≥ 1.15x is typical commercial bank covenant
    - LLCR is forward-looking (uses future cashflows only)
    """
    if not cfads_series or not debt_outstanding_series:
        return {
            'llcr_series': [],
            'llcr_min': 0.0,
            'llcr_avg': 0.0,
            'years_calculated': 0,
            'calculation_details': []
        }
    
    llcr_series = []
    calculation_details = []
    
    n_years = min(len(cfads_series), len(debt_outstanding_series))
    
    for year in range(start_year, n_years):
        debt_outstanding = debt_outstanding_series[year]
        
        if debt_outstanding <= 0:
            continue
        
        # NPV of remaining cashflows from this year forward
        remaining_cfads = cfads_series[year:]
        npv_future_cfads = _npv(remaining_cfads, discount_rate, start_period=0)
        
        # LLCR = NPV(future CFADS) / Current Debt Outstanding
        llcr = npv_future_cfads / debt_outstanding if debt_outstanding > 0 else float('inf')
        llcr_series.append(llcr)
        
        calculation_details.append({
            'year': year,
            'debt_outstanding': debt_outstanding,
            'npv_future_cfads': npv_future_cfads,
            'llcr': llcr,
            'remaining_years': len(remaining_cfads)
        })
    
    llcr_min = min([x for x in llcr_series if x > 0], default=0.0)
    llcr_avg = sum(llcr_series) / len(llcr_series) if llcr_series else 0.0
    
    return {
        'llcr_series': llcr_series,
        'llcr_min': llcr_min,
        'llcr_avg': llcr_avg,
        'years_calculated': len(llcr_series),
        'calculation_details': calculation_details
    }


# ============================================================================
# PLCR CALCULATION (P0-1C Phase 2)
# ============================================================================

def calculate_plcr(
    cfads_series: List[float],
    debt_outstanding_series: List[float],
    discount_rate: float = 0.10,
    start_year: int = 0
) -> Dict[str, Any]:
    """
    Calculate Project Life Coverage Ratio (PLCR) for each period.
    
    PLCR = NPV(all future CFADS over full project life) / Outstanding Debt
    
    PLCR measures full project value vs debt burden and is used for
    refinancing and restructuring decisions.
    
    Parameters
    ----------
    cfads_series : list of float
        Cash Flow Available for Debt Service for entire project life (POST-TAX)
    debt_outstanding_series : list of float
        Outstanding debt balance at start of each year
    discount_rate : float, default 0.10
        Discount rate for NPV calculation
    start_year : int, default 0
        Starting year index
    
    Returns
    -------
    dict
        {
            'plcr_series': list of float,
            'plcr_min': float,
            'plcr_avg': float,
            'years_calculated': int,
            'calculation_details': list of dict
        }
    
    Notes
    -----
    - PLCR ≥ 1.40x is typical target
    - PLCR is always >= LLCR (includes cashflows beyond loan maturity)
    - Key metric for equity investors (measures downside protection)
    """
    if not cfads_series or not debt_outstanding_series:
        return {
            'plcr_series': [],
            'plcr_min': 0.0,
            'plcr_avg': 0.0,
            'years_calculated': 0,
            'calculation_details': []
        }
    
    plcr_series = []
    calculation_details = []
    
    n_years = min(len(cfads_series), len(debt_outstanding_series))
    
    # PLCR uses ALL remaining cashflows (not just loan life)
    for year in range(start_year, n_years):
        debt_outstanding = debt_outstanding_series[year]
        
        if debt_outstanding <= 0:
            continue
        
        # NPV of ALL remaining project cashflows
        remaining_cfads = cfads_series[year:]
        npv_all_cfads = _npv(remaining_cfads, discount_rate, start_period=0)
        
        # PLCR = NPV(all future CFADS) / Current Debt Outstanding
        plcr = npv_all_cfads / debt_outstanding if debt_outstanding > 0 else float('inf')
        plcr_series.append(plcr)
        
        calculation_details.append({
            'year': year,
            'debt_outstanding': debt_outstanding,
            'npv_all_cfads': npv_all_cfads,
            'plcr': plcr,
            'remaining_project_years': len(remaining_cfads)
        })
    
    plcr_min = min([x for x in plcr_series if x > 0], default=0.0)
    plcr_avg = sum(plcr_series) / len(plcr_series) if plcr_series else 0.0
    
    return {
        'plcr_series': plcr_series,
        'plcr_min': plcr_min,
        'plcr_avg': plcr_avg,
        'years_calculated': len(plcr_series),
        'calculation_details': calculation_details
    }


# ============================================================================
# BACKWARD COMPATIBILITY (Legacy Function)
# ============================================================================

def compute_llcr_plcr(
    annual_rows: List[Dict[str, Any]],
    discount_rate: float = 0.10
) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    Computes both LLCR and PLCR from annual_rows structure.
    """
    cfads_series = [_to_float(row.get('cfads_usd'), 0.0) for row in annual_rows]
    debt_outstanding_series = [_to_float(row.get('debt_outstanding'), 0.0) for row in annual_rows]
    
    llcr_result = calculate_llcr(cfads_series, debt_outstanding_series, discount_rate)
    plcr_result = calculate_plcr(cfads_series, debt_outstanding_series, discount_rate)
    
    return {
        'llcr': llcr_result,
        'plcr': plcr_result,
        'discount_rate': discount_rate
    }


# ============================================================================
# COVENANT MONITORING
# ============================================================================

def check_llcr_covenant(
    llcr_result: Dict[str, Any],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Check LLCR against covenant thresholds from YAML."""
    metrics = params.get('metrics', {})
    llcr_min_covenant = _to_float(metrics.get('llcr_min_covenant'), 1.20)
    llcr_warn_threshold = _to_float(metrics.get('llcr_warn_threshold'), 1.25)
    
    llcr_min = llcr_result.get('llcr_min', 0.0)
    violations = []
    status = 'PASS'
    
    if llcr_min < llcr_min_covenant:
        status = 'BREACH'
        violations.append(f"BREACH: Minimum LLCR {llcr_min:.2f}x < covenant {llcr_min_covenant:.2f}x")
    elif llcr_min < llcr_warn_threshold:
        status = 'WARN'
        violations.append(f"WARNING: Minimum LLCR {llcr_min:.2f}x < warning {llcr_warn_threshold:.2f}x")
    
    summary = f"LLCR {status}: Min {llcr_min:.2f}x (covenant: {llcr_min_covenant:.2f}x)"
    logger.info(summary)
    
    return {
        'covenant_status': status,
        'violations': violations,
        'summary': summary
    }


def check_plcr_covenant(
    plcr_result: Dict[str, Any],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Check PLCR against covenant thresholds from YAML."""
    metrics = params.get('metrics', {})
    plcr_min_covenant = _to_float(metrics.get('plcr_min_covenant'), 1.40)
    plcr_target = _to_float(metrics.get('plcr_target'), 1.60)
    
    plcr_min = plcr_result.get('plcr_min', 0.0)
    violations = []
    status = 'PASS'
    
    if plcr_min < plcr_min_covenant:
        status = 'BREACH'
        violations.append(f"BREACH: Minimum PLCR {plcr_min:.2f}x < covenant {plcr_min_covenant:.2f}x")
    elif plcr_min < plcr_target:
        status = 'WARN'
        violations.append(f"WARNING: Minimum PLCR {plcr_min:.2f}x < target {plcr_target:.2f}x")
    
    summary = f"PLCR {status}: Min {plcr_min:.2f}x (covenant: {plcr_min_covenant:.2f}x)"
    logger.info(summary)
    
    return {
        'covenant_status': status,
        'violations': violations,
        'summary': summary
    }


# ============================================================================
# COMPREHENSIVE SUMMARY
# ============================================================================

def summarize_project_metrics(
    annual_rows: List[Dict[str, Any]],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute all project finance metrics.
    Returns comprehensive dict with DSCR, LLCR, PLCR, and covenant status.
    """
    metrics_config = params.get('metrics', {})
    discount_rate = _to_float(metrics_config.get('llcr_discount_rate'), 0.10)
    
    # DSCR
    dscr_series = compute_dscr_series(annual_rows)
    dscr_summary = summarize_dscr(dscr_series)
    
    # LLCR and PLCR
    cfads_series = [_to_float(row.get('cfads_usd'), 0.0) for row in annual_rows]
    debt_outstanding_series = [_to_float(row.get('debt_outstanding'), 0.0) for row in annual_rows]
    
    llcr_result = calculate_llcr(cfads_series, debt_outstanding_series, discount_rate)
    plcr_result = calculate_plcr(cfads_series, debt_outstanding_series, discount_rate)
    
    # Covenant checks
    llcr_covenant = check_llcr_covenant(llcr_result, params)
    plcr_covenant = check_plcr_covenant(plcr_result, params)
    
    return {
        'dscr': {
            'series': dscr_series,
            'summary': dscr_summary
        },
        'llcr': llcr_result,
        'plcr': plcr_result,
        'llcr_covenant': llcr_covenant,
        'plcr_covenant': plcr_covenant
    }


