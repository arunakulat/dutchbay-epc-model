"""
Project Finance Metrics Module - DutchBay V13 Enhanced

COMPLIANCE:
-----------
- IFC, World Bank, ADB coverage ratio standards
- Commercial bank credit assessment requirements
- Basel III capital adequacy frameworks

FEATURES:
---------
- DSCR (Debt Service Coverage Ratio) calculation and tracking
- LLCR (Loan Life Coverage Ratio) - P0-1C Phase 1
- PLCR (Project Life Coverage Ratio) - P0-1C Phase 2
- Multi-period covenant monitoring
- Integration with debt.py and irr.py modules

OUTPUTS:
--------
Comprehensive metrics dictionary with:
    - dscr_series, dscr_min, dscr_avg
    - llcr_series, llcr_min, llcr_avg
    - plcr_series, plcr_min, plcr_avg
    - covenant_status and violation tracking

Author: DutchBay V13 Team, Nov 2025, P0-1C Enhanced
Version: 2.0 (Complete LLCR/PLCR)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

# Import only what exists in irr.py
try:
    from .irr import irr
except ImportError:
    # Fallback if irr module has different structure
    irr = None

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('dutchbay.finance.metrics')

__all__ = [
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
    
    npv = 0.0
    for i, cf in enumerate(cashflows):
        period = start_period + i
        npv += cf / ((1 + discount_rate) ** period)
    
    return npv

# ============================================================================
# DSCR CALCULATIONS (Existing - Enhanced)
# ============================================================================

def compute_dscr_series(annual_rows: List[Dict[str, Any]]) -> List[Optional[float]]:
    """
    Calculate DSCR for each year.
    
    DSCR_t = CFADS_t / DebtService_t
    
    Expects per-row:
      - 'cfads_usd' (Cash Flow Available for Debt Service)
      - 'debt_service' (Interest + Principal payments)
    
    Returns None for years where DSCR is undefined (e.g., no debt service).
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
        Cash Flow Available for Debt Service for each year
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
    
    llcr_min = min(llcr_series) if llcr_series else 0.0
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
        Cash Flow Available for Debt Service for entire project life
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
    
    plcr_min = min(plcr_series) if plcr_series else 0.0
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
        'llcr_covenant': llcr_covenant,
        'plcr': plcr_result,
        'plcr_covenant': plcr_covenant,
        'discount_rate': discount_rate,
        'metrics_version': '2.0-P0-1C-Complete'
    }

