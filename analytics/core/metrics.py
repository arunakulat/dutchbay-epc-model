"""Financial metrics calculation module.

Provides NPV, IRR, and DSCR KPI calculations for scenario analysis.
"""

import numpy as np
import numpy_financial as npf
from typing import Dict, List, Any, Optional


def calculate_npv(
    cashflows: List[float],
    discount_rate: float = 0.08
) -> float:
    """
    Calculate Net Present Value.
    
    Args:
        cashflows: List of annual cashflows (year 0 = initial investment, typically negative)
        discount_rate: Annual discount rate (e.g., 0.08 for 8%)
    
    Returns:
        NPV in same currency as cashflows
    """
    if not cashflows:
        return 0.0
    return float(npf.npv(discount_rate, cashflows))


def calculate_irr(
    cashflows: List[float],
    guess: float = 0.1
) -> Optional[float]:
    """
    Calculate Internal Rate of Return.
    
    Args:
        cashflows: List of annual cashflows (year 0 = initial investment, typically negative)
        guess: Initial guess for IRR calculation
    
    Returns:
        IRR as decimal (e.g., 0.12 for 12%), or None if calculation fails
    """
    if not cashflows or len(cashflows) < 2:
        return None
    
    try:
        irr_value = npf.irr(cashflows)
        # Check for invalid results (nan, inf)
        if np.isnan(irr_value) or np.isinf(irr_value):
            return None
        return float(irr_value)
    except (ValueError, RuntimeError):
        return None


def calculate_dscr_stats(dscr_series: List[float]) -> Dict[str, float]:
    """
    Calculate DSCR statistics.
    
    Args:
        dscr_series: List of annual DSCR values
    
    Returns:
        Dictionary with min, max, mean, median DSCR
    """
    if not dscr_series:
        return {
            "dscr_min": None,
            "dscr_max": None,
            "dscr_mean": None,
            "dscr_median": None
        }
    
    # Filter out invalid values
    valid_dscr = [x for x in dscr_series if isinstance(x, (int, float)) and not np.isnan(x) and not np.isinf(x)]
    
    if not valid_dscr:
        return {
            "dscr_min": None,
            "dscr_max": None,
            "dscr_mean": None,
            "dscr_median": None
        }
    
    return {
        "dscr_min": float(np.min(valid_dscr)),
        "dscr_max": float(np.max(valid_dscr)),
        "dscr_mean": float(np.mean(valid_dscr)),
        "dscr_median": float(np.median(valid_dscr))
    }


def calculate_debt_stats(debt_series: List[float]) -> Dict[str, float]:
    """
    Calculate debt statistics.
    
    Args:
        debt_series: List of annual debt outstanding values
    
    Returns:
        Dictionary with max debt, final debt
    """
    if not debt_series:
        return {
            "max_debt_outstanding": 0.0,
            "final_debt_outstanding": 0.0
        }
    
    valid_debt = [x for x in debt_series if isinstance(x, (int, float)) and not np.isnan(x)]
    
    if not valid_debt:
        return {
            "max_debt_outstanding": 0.0,
            "final_debt_outstanding": 0.0
        }
    
    return {
        "max_debt_outstanding": float(np.max(valid_debt)),
        "final_debt_outstanding": float(valid_debt[-1]) if valid_debt else 0.0
    }


def calculate_cfads_stats(cfads_series: List[float]) -> Dict[str, float]:
    """
    Calculate CFADS (Cash Flow Available for Debt Service) statistics.
    
    Args:
        cfads_series: List of annual CFADS values
    
    Returns:
        Dictionary with total CFADS, final year CFADS, operational mean
    """
    if not cfads_series:
        return {
            "total_cfads": 0.0,
            "final_cfads": 0.0,
            "mean_operational_cfads": 0.0
        }
    
    valid_cfads = [x for x in cfads_series if isinstance(x, (int, float)) and not np.isnan(x)]
    
    if not valid_cfads:
        return {
            "total_cfads": 0.0,
            "final_cfads": 0.0,
            "mean_operational_cfads": 0.0
        }
    
    # Operational CFADS: exclude construction years (typically first few years with negative/zero CFADS)
    operational_cfads = [x for x in valid_cfads if x > 0]
    
    return {
        "total_cfads": float(np.sum(valid_cfads)),
        "final_cfads": float(valid_cfads[-1]) if valid_cfads else 0.0,
        "mean_operational_cfads": float(np.mean(operational_cfads)) if operational_cfads else 0.0
    }


def calculate_scenario_kpis(
    annual_rows: List[Dict[str, Any]],
    debt_result: Dict[str, Any],
    discount_rate: float = 0.08,
    initial_investment: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive KPIs for a single scenario.
    
    Args:
        annual_rows: List of annual cashflow dictionaries from build_annual_rows_v14()
        debt_result: Debt calculation result from apply_debt_layer()
        discount_rate: Discount rate for NPV calculation
        initial_investment: Initial investment (if not in annual_rows). If None, extracted from config.
    
    Returns:
        Dictionary with all KPIs: NPV, IRR, DSCR stats, debt stats, CFADS stats
    """
    kpis = {}
    
    # Extract cashflow series
    cfads_series = [row.get("cfads_usd", 0.0) for row in annual_rows]
    equity_fcf_series = [row.get("equity_fcf_usd", 0.0) for row in annual_rows]
    
    # Extract debt series
    dscr_series = debt_result.get("dscr_series", [])
    debt_outstanding = debt_result.get("debt_outstanding", [])
    
    # NPV calculation (on equity free cash flow)
    # Prepend initial equity investment if provided
    if initial_investment is not None:
        npv_cashflows = [-initial_investment] + equity_fcf_series
    else:
        npv_cashflows = equity_fcf_series
    
    kpis["npv"] = calculate_npv(npv_cashflows, discount_rate)
    
    # IRR calculation (on equity free cash flow)
    kpis["irr"] = calculate_irr(npv_cashflows)
    
    # DSCR statistics
    kpis.update(calculate_dscr_stats(dscr_series))
    
    # Debt statistics
    kpis.update(calculate_debt_stats(debt_outstanding))
    
    # CFADS statistics
    kpis.update(calculate_cfads_stats(cfads_series))
    
    # Additional metrics from debt result
    kpis["total_idc_capitalized"] = debt_result.get("total_idc_capitalized", 0.0)
    kpis["grace_years"] = debt_result.get("grace_periods", 0)
    kpis["timeline_periods"] = debt_result.get("timeline_periods", len(annual_rows))
    
    return kpis


def format_kpi_summary(kpis: Dict[str, Any], scenario_name: str = "") -> str:
    """
    Format KPIs as human-readable text summary.
    
    Args:
        kpis: KPI dictionary from calculate_scenario_kpis()
        scenario_name: Scenario name for header
    
    Returns:
        Formatted string summary
    """
    lines = []
    
    if scenario_name:
        lines.append(f"\n{'='*60}")
        lines.append(f"Scenario: {scenario_name}")
        lines.append(f"{'='*60}")
    
    lines.append(f"\nValuation Metrics:")
    lines.append(f"  NPV (USD):           {kpis.get('npv', 0):>15,.2f}")
    irr = kpis.get('irr')
    if irr is not None:
        lines.append(f"  IRR:                 {irr:>15.2%}")
    else:
        lines.append(f"  IRR:                 {'N/A':>15}")
    
    lines.append(f"\nDSCR Statistics:")
    lines.append(f"  Minimum DSCR:        {kpis.get('dscr_min', 0):>15.2f}")
    lines.append(f"  Maximum DSCR:        {kpis.get('dscr_max', 0):>15.2f}")
    lines.append(f"  Mean DSCR:           {kpis.get('dscr_mean', 0):>15.2f}")
    lines.append(f"  Median DSCR:         {kpis.get('dscr_median', 0):>15.2f}")
    
    lines.append(f"\nDebt Statistics:")
    lines.append(f"  Max Debt (USD):      {kpis.get('max_debt_outstanding', 0):>15,.2f}")
    lines.append(f"  Final Debt (USD):    {kpis.get('final_debt_outstanding', 0):>15,.2f}")
    lines.append(f"  Total IDC (USD):     {kpis.get('total_idc_capitalized', 0):>15,.2f}")
    
    lines.append(f"\nCFADS Statistics:")
    lines.append(f"  Total CFADS (USD):   {kpis.get('total_cfads', 0):>15,.2f}")
    lines.append(f"  Final Year CFADS:    {kpis.get('final_cfads', 0):>15,.2f}")
    lines.append(f"  Mean Operational:    {kpis.get('mean_operational_cfads', 0):>15,.2f}")
    
    return "\n".join(lines)
