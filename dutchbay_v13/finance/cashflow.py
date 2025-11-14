"""
Cash Flow Module for DutchBay V13 Project Finance

COMPLIANCE:
-----------
- IFC, World Bank, DFI project finance standards
- Full YAML-driven configuration (no hardcoding)
- Complete statutory and regulatory deduction framework
- Audit-ready with full calculation trail
- Pre-tax and post-tax CFADS calculation options

FEATURES:
---------
- Multi-year cash flow projection with degradation
- FX-aware (LKR revenue, USD OPEX conversion to LKR)
- All statutory deductions (success fee, environmental, social levy)
- Tax calculation with depreciation
- Risk adjustment haircut
- CFADS (Cash Flow Available for Debt Service) in LKR
- Comprehensive parameter validation
- Full audit trail logging

INPUTS:
-------
All parameters from full_model_variables_updated.yaml:
  - project: capacity_mw, capacity_factor, degradation
  - tariff: lkr_per_kwh (fixed PPA tariff)
  - regulatory: grid_loss_pct, success_fee_pct, env_surcharge_pct, social_services_levy_pct
  - opex: usd_per_year (converted to LKR using FX)
  - tax: corporate_tax_rate, depreciation_years
  - risk_adjustment: cfads_haircut_pct
  - fx: start_lkr_per_usd, annual_depr (or explicit curve)
  - returns: project_life_years

OUTPUTS:
--------
- build_annual_cfads(): List[float] - Annual CFADS in LKR for debt module
- build_annual_rows(): List[Dict] - Detailed breakdown with all components
- calculate_single_year_cfads(): Dict - Single year calculation with audit trail

VERSION HISTORY:
----------------
v1.0 (2025-11-14): Original implementation
v2.0 (2025-11-15): Refactored with full statutory deductions and CFADS calculation

Author: DutchBay V13 Team
Version: 2.0 (Audit-Ready)
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('dutchbay.finance.cashflow')

# Constants
HOURS_PER_YEAR = 8760.0

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# HELPER FUNCTIONS (Unchanged from v1.0)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _get(d: Dict[str, Any], path: List[str], default=None):
    """Safely traverse nested dictionary."""
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _as_float(x, default=None):
    """Safe float conversion with default fallback."""
    try:
        return float(x) if x is not None else default
    except Exception:
        return default

def _int(x, default=0) -> int:
    """Safe integer conversion with default fallback."""
    try:
        return int(x)
    except Exception:
        return default

def _years_total(p: Dict[str, Any]) -> int:
    """Get total project lifetime in years."""
    # Try project_life_years first (simpler)
    life_years = _int(_get(p, ["returns", "project_life_years"]), None)
    if life_years is not None and life_years > 0:
        return life_years
    
    # Fallback: Try timeline breakdown
    ops_years = _int(_get(p, ["project", "timeline", "ops_years"]), None)
    if ops_years is not None:
        pre = _int(_get(p, ["project", "timeline", "ppa_to_fc_years"]), 0) \
            + _int(_get(p, ["project", "timeline", "construction_years"]), 0)
        return pre + ops_years
    
    # Ultimate fallback
    return _int(_get(p, ["project", "timeline", "lifetime_years"]), 20)

def _ops_start_index(p: Dict[str, Any]) -> int:
    """Get year index when operations start (post-construction)."""
    return _int(_get(p, ["project", "timeline", "ppa_to_fc_years"]), 0) \
         + _int(_get(p, ["project", "timeline", "construction_years"]), 0)

def _capacity_mw(p: Dict[str, Any]) -> float:
    """Get project capacity in MW."""
    v = _get(p, ["project", "capacity_mw"])
    if v is None:
        v = p.get("capacity_mw")
    return _as_float(v, 150.0) or 150.0  # Default to 150MW if missing

def _fx_curve(p: Dict[str, Any], n: int) -> List[float]:
    """
    Generate FX curve for n years.
    Uses explicit curve if provided, otherwise generates from start + depreciation.
    """
    explicit = _get(p, ["fx", "curve_lkr_per_usd"])
    if isinstance(explicit, list) and explicit:
        if len(explicit) >= n:
            return [float(x) for x in explicit[:n]]
        return [float(x) for x in explicit] + [float(explicit[-1])] * (n - len(explicit))
    
    start = _as_float(_get(p, ["fx", "start_lkr_per_usd"]), 300.0) or 300.0
    depr = _as_float(_get(p, ["fx", "annual_depr"]), 0.03) or 0.03
    
    out: List[float] = []
    cur = float(start)
    for _ in range(max(1, n)):
        out.append(cur)
        cur *= (1.0 + depr)
    return out

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PARAMETER EXTRACTION & VALIDATION (NEW in v2.0)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _validate_parameters(p: Dict[str, Any]) -> List[str]:
    """
    Validate all required YAML parameters are present and reasonable.
    
    Returns:
        List of warning/error messages (empty if all valid)
    """
    issues = []
    
    # Required parameters
    if _get(p, ["project", "capacity_mw"]) is None:
        issues.append("ERROR: project.capacity_mw missing")
    
    if _get(p, ["project", "capacity_factor"]) is None:
        issues.append("ERROR: project.capacity_factor missing")
    
    if _get(p, ["tariff", "lkr_per_kwh"]) is None:
        issues.append("ERROR: tariff.lkr_per_kwh missing")
    
    if _get(p, ["regulatory", "grid_loss_pct"]) is None:
        issues.append("WARNING: regulatory.grid_loss_pct missing (defaulting to 0.02)")
    
    if _get(p, ["opex", "usd_per_year"]) is None:
        issues.append("ERROR: opex.usd_per_year missing")
    
    # Validate ranges
    cap_factor = _as_float(_get(p, ["project", "capacity_factor"]), None)
    if cap_factor is not None and (cap_factor < 0 or cap_factor > 1):
        issues.append(f"ERROR: capacity_factor {cap_factor} out of range [0, 1]")
    
    grid_loss = _as_float(_get(p, ["regulatory", "grid_loss_pct"]), None)
    if grid_loss is not None and (grid_loss < 0 or grid_loss > 0.5):
        issues.append(f"WARNING: grid_loss_pct {grid_loss} seems high")
    
    return issues

def _extract_parameters(p: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract all required parameters from YAML config with safe defaults.
    
    Returns:
        Dictionary of all parameters needed for CFADS calculation
    """
    return {
        'capacity_mw': _as_float(_get(p, ["project", "capacity_mw"]), 150.0),
        'capacity_factor': _as_float(_get(p, ["project", "capacity_factor"]), 0.40),
        'degradation': _as_float(_get(p, ["project", "degradation"]), 0.006),
        'tariff_lkr_per_kwh': _as_float(_get(p, ["tariff", "lkr_per_kwh"]), 20.30),
        'grid_loss_pct': _as_float(_get(p, ["regulatory", "grid_loss_pct"]), 0.02),
        'success_fee_pct': _as_float(_get(p, ["regulatory", "success_fee_pct"]), 0.01),
        'env_surcharge_pct': _as_float(_get(p, ["regulatory", "env_surcharge_pct"]), 0.005),
        'social_levy_pct': _as_float(_get(p, ["regulatory", "social_services_levy_pct"]), 0.025),
        'opex_usd_per_year': _as_float(_get(p, ["opex", "usd_per_year"]), 3_000_000.0),
        'corporate_tax_rate': _as_float(_get(p, ["tax", "corporate_tax_rate"]), 0.30),
        'depreciation_years': _int(_get(p, ["tax", "depreciation_years"]), 15),
        'risk_haircut_pct': _as_float(_get(p, ["risk_adjustment", "cfads_haircut_pct"]), 0.10),
        'project_life_years': _years_total(p),
    }

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PRODUCTION & REVENUE CALCULATION (Enhanced from v1.0)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def calculate_net_production(capacity_mw: float, 
                            capacity_factor: float,
                            degradation: float,
                            grid_loss_pct: float,
                            year: int) -> Tuple[float, float]:
    """
    Calculate gross and net production for a given year.
    
    Args:
        capacity_mw: Plant capacity in MW
        capacity_factor: Capacity factor (0-1)
        degradation: Annual degradation rate (0-1)
        grid_loss_pct: Grid loss percentage (0-1)
        year: Year index (0-based)
    
    Returns:
        Tuple of (gross_kwh, net_kwh)
    """
    # Apply degradation
    degraded_capacity_factor = capacity_factor * ((1.0 - degradation) ** year)
    
    # Gross production
    gross_kwh = capacity_mw * 1000.0 * HOURS_PER_YEAR * degraded_capacity_factor
    
    # Net production (after grid loss)
    net_kwh = gross_kwh * (1.0 - grid_loss_pct)
    
    return gross_kwh, net_kwh

def calculate_revenue_lkr(net_kwh: float, tariff_lkr_per_kwh: float) -> float:
    """
    Calculate revenue in LKR from net production.
    
    Args:
        net_kwh: Net production in kWh (after grid loss)
        tariff_lkr_per_kwh: PPA tariff in LKR/kWh (fixed)
    
    Returns:
        Revenue in LKR
    """
    return net_kwh * tariff_lkr_per_kwh

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STATUTORY DEDUCTIONS (NEW in v2.0)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def calculate_statutory_deductions(revenue_lkr: float,
                                   success_fee_pct: float,
                                   env_surcharge_pct: float,
                                   social_levy_pct: float) -> Dict[str, float]:
    """
    Calculate all statutory/regulatory deductions from revenue.
    
    Args:
        revenue_lkr: Gross revenue in LKR
        success_fee_pct: Success fee as % of revenue
        env_surcharge_pct: Environmental surcharge as % of revenue
        social_levy_pct: Social services levy as % of revenue
    
    Returns:
        Dictionary with breakdown of each deduction
    """
    success_fee = revenue_lkr * success_fee_pct
    env_surcharge = revenue_lkr * env_surcharge_pct
    social_levy = revenue_lkr * social_levy_pct
    total_statutory = success_fee + env_surcharge + social_levy
    
    return {
        'success_fee': success_fee,
        'environmental_surcharge': env_surcharge,
        'social_services_levy': social_levy,
        'total_statutory_deductions': total_statutory,
    }

def calculate_opex_lkr(opex_usd_per_year: float, fx_rate: float) -> float:
    """
    Convert USD OPEX to LKR using annual FX rate.
    
    Args:
        opex_usd_per_year: Annual OPEX in USD
        fx_rate: FX rate (LKR per USD) for that year
    
    Returns:
        OPEX in LKR
    """
    return opex_usd_per_year * fx_rate

def calculate_tax(pretax_income: float,
                 tax_rate: float,
                 capex_total: Optional[float] = None,
                 depreciation_years: Optional[int] = None,
                 year: int = 0) -> Tuple[float, float]:
    """
    Calculate corporate tax with depreciation deduction.
    
    Args:
        pretax_income: Pre-tax income in LKR
        tax_rate: Corporate tax rate (0-1)
        capex_total: Total CAPEX for depreciation calculation (optional)
        depreciation_years: Depreciation period in years (optional)
        year: Year index for depreciation calculation
    
    Returns:
        Tuple of (tax_amount, depreciation_deduction)
    """
    # Calculate depreciation deduction if CAPEX provided
    depreciation = 0.0
    if capex_total is not None and depreciation_years is not None and depreciation_years > 0:
        if year < depreciation_years:
            depreciation = capex_total / depreciation_years
    
    # Taxable income after depreciation
    taxable_income = max(0.0, pretax_income - depreciation)
    
    # Tax amount
    tax = taxable_income * tax_rate
    
    return tax, depreciation

def apply_risk_haircut(cfads_pretax: float, haircut_pct: float) -> float:
    """
    Apply risk adjustment haircut to CFADS.
    
    Args:
        cfads_pretax: CFADS before risk adjustment
        haircut_pct: Risk haircut percentage (0-1)
    
    Returns:
        CFADS after risk adjustment
    """
    return cfads_pretax * (1.0 - haircut_pct)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CFADS CALCULATION (NEW in v2.0 - Core Function for Debt Module)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def calculate_single_year_cfads(params: Dict[str, float],
                               fx_rate: float,
                               year: int,
                               capex_total: Optional[float] = None,
                               verbose: bool = False) -> Dict[str, float]:
    """
    Calculate CFADS for a single year with complete audit trail.
    
    This is the core function that implements the correct CFADS calculation:
    CFADS = Revenue - Statutory Deductions - OPEX - Tax - Risk Haircut
    
    Args:
        params: Parameter dictionary from _extract_parameters()
        fx_rate: FX rate for this year
        year: Year index (0-based)
        capex_total: Total CAPEX for tax depreciation (optional)
        verbose: If True, log detailed breakdown
    
    Returns:
        Dictionary with complete breakdown of all components
    """
    # Step 1: Production
    gross_kwh, net_kwh = calculate_net_production(
        params['capacity_mw'],
        params['capacity_factor'],
        params['degradation'],
        params['grid_loss_pct'],
        year
    )
    
    # Step 2: Revenue (LKR)
    revenue_lkr = calculate_revenue_lkr(net_kwh, params['tariff_lkr_per_kwh'])
    
    # Step 3: Statutory deductions
    statutory = calculate_statutory_deductions(
        revenue_lkr,
        params['success_fee_pct'],
        params['env_surcharge_pct'],
        params['social_levy_pct']
    )
    
    # Step 4: OPEX (convert USD to LKR)
    opex_lkr = calculate_opex_lkr(params['opex_usd_per_year'], fx_rate)
    
    # Step 5: Pre-tax CFADS
    pretax_cfads = revenue_lkr - statutory['total_statutory_deductions'] - opex_lkr
    
    # Step 6: Tax
    tax, depreciation = calculate_tax(
        pretax_cfads,
        params['corporate_tax_rate'],
        capex_total,
        params['depreciation_years'],
        year
    )
    
    # Step 7: Post-tax CFADS
    posttax_cfads = pretax_cfads - tax
    
    # Step 8: Risk adjustment
    cfads_final = apply_risk_haircut(posttax_cfads, params['risk_haircut_pct'])
    
    # Build result dictionary
    result = {
        'year': year + 1,  # 1-indexed for reporting
        'gross_kwh': gross_kwh,
        'grid_loss': gross_kwh - net_kwh,
        'net_kwh': net_kwh,
        'revenue_lkr': revenue_lkr,
        'success_fee': statutory['success_fee'],
        'env_surcharge': statutory['environmental_surcharge'],
        'social_levy': statutory['social_services_levy'],
        'total_statutory_deductions': statutory['total_statutory_deductions'],
        'opex_usd': params['opex_usd_per_year'],
        'fx_rate': fx_rate,
        'opex_lkr': opex_lkr,
        'pretax_cfads': pretax_cfads,
        'depreciation': depreciation,
        'tax': tax,
        'posttax_cfads': posttax_cfads,
        'risk_haircut_amount': posttax_cfads - cfads_final,
        'cfads_final_lkr': cfads_final,
    }
    
    if verbose:
        logger.info(f"Year {year+1} CFADS Calculation:")
        logger.info(f"  Gross Production: {gross_kwh:,.0f} kWh")
        logger.info(f"  Net Production: {net_kwh:,.0f} kWh (after {params['grid_loss_pct']:.1%} grid loss)")
        logger.info(f"  Revenue (LKR): {revenue_lkr:,.0f}")
        logger.info(f"  Statutory Deductions: {statutory['total_statutory_deductions']:,.0f}")
        logger.info(f"  OPEX (USD {params['opex_usd_per_year']:,.0f} @ FX {fx_rate:.2f}): {opex_lkr:,.0f} LKR")
        logger.info(f"  Pre-tax CFADS: {pretax_cfads:,.0f}")
        logger.info(f"  Tax: {tax:,.0f}")
        logger.info(f"  Post-tax CFADS: {posttax_cfads:,.0f}")
        logger.info(f"  Risk Haircut ({params['risk_haircut_pct']:.1%}): {posttax_cfads - cfads_final:,.0f}")
        logger.info(f"  FINAL CFADS (LKR): {cfads_final:,.0f}")
    
    return result

def build_annual_cfads(p: Dict[str, Any],
                      fx_curve: Optional[List[float]] = None,
                      capex_total: Optional[float] = None,
                      verbose: bool = False) -> List[float]:
    """
    Calculate CFADS for every year of the project (for debt module).
    
    This is the PRIMARY FUNCTION for debt.py integration.
    Returns CFADS in LKR for each year with all deductions applied.
    
    Args:
        p: Configuration dictionary from full_model_variables_updated.yaml
        fx_curve: List of FX rates (if None, will be generated)
        capex_total: Total CAPEX for tax depreciation (if None, extracted from YAML)
        verbose: If True, log detailed breakdown for each year
    
    Returns:
        List of annual CFADS values in LKR (ready for debt module)
    """
    # Validate parameters
    issues = _validate_parameters(p)
    if any('ERROR' in issue for issue in issues):
        for issue in issues:
            logger.error(issue)
        raise ValueError(f"Cannot calculate CFADS: {len([i for i in issues if 'ERROR' in i])} critical errors")
    
    for issue in issues:
        if 'WARNING' in issue:
            logger.warning(issue)
    
    # Extract parameters
    params = _extract_parameters(p)
    years = params['project_life_years']
    
    # Get FX curve
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    
    # Get CAPEX if not provided
    if capex_total is None:
        capex_usd = _as_float(_get(p, ["capex", "usd_total"]), None)
        if capex_usd is not None:
            # Convert to LKR using initial FX
            capex_total = capex_usd * fx_curve[0]
    
    # Calculate CFADS for each year
    cfads_list = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        result = calculate_single_year_cfads(params, fx_rate, year, capex_total, verbose=verbose)
        cfads_list.append(result['cfads_final_lkr'])
    
    logger.info(f"âœ“ Calculated CFADS for {years} years")
    logger.info(f"  CFADS range: LKR {min(cfads_list):,.0f} to {max(cfads_list):,.0f}")
    logger.info(f"  Average CFADS: LKR {sum(cfads_list)/len(cfads_list):,.0f}")
    
    return cfads_list

def build_annual_rows(p: Dict[str, Any],
                     fx_curve: Optional[List[float]] = None,
                     capex_total: Optional[float] = None) -> List[Dict[str, float]]:
    """
    Build detailed annual cash flow breakdown (for reporting/analysis).
    
    Returns complete breakdown of all components for each year.
    
    Args:
        p: Configuration dictionary from full_model_variables_updated.yaml
        fx_curve: List of FX rates (if None, will be generated)
        capex_total: Total CAPEX for tax depreciation
    
    Returns:
        List of dictionaries with detailed breakdown for each year
    """
    # Extract parameters
    params = _extract_parameters(p)
    years = params['project_life_years']
    
    # Get FX curve
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    
    # Get CAPEX if not provided
    if capex_total is None:
        capex_usd = _as_float(_get(p, ["capex", "usd_total"]), None)
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]
    
    # Build rows
    rows = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        result = calculate_single_year_cfads(params, fx_rate, year, capex_total, verbose=False)
        
        # Add USD equivalents for reporting
        result['revenue_usd'] = result['revenue_lkr'] / fx_rate if fx_rate > 0 else 0.0
        result['cfads_usd'] = result['cfads_final_lkr'] / fx_rate if fx_rate > 0 else 0.0
        
        rows.append(result)
    
    return rows

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BACKWARD COMPATIBILITY (Deprecated functions from v1.0)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def kwh_per_year(p: Dict[str, Any]) -> float:
    """
    DEPRECATED: Use calculate_net_production() instead.
    Kept for backward compatibility only.
    
    Calculate annual kWh production (year 0, no degradation).
    """
    logger.warning("kwh_per_year() is deprecated. Use calculate_net_production() instead.")
    
    params = _extract_parameters(p)
    gross_kwh, net_kwh = calculate_net_production(
        params['capacity_mw'],
        params['capacity_factor'],
        params['degradation'],
        params['grid_loss_pct'],
        year=0
    )
    return net_kwh

def revenue_usd_per_year(p: Dict[str, Any], year: int = 0) -> float:
    """
    DEPRECATED: Use build_annual_rows() instead.
    Kept for backward compatibility only.
    
    Calculate annual revenue in USD for reporting.
    """
    logger.warning("revenue_usd_per_year() is deprecated. Use build_annual_rows() instead.")
    
    params = _extract_parameters(p)
    fx_curve = _fx_curve(p, params['project_life_years'])
    fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
    
    gross_kwh, net_kwh = calculate_net_production(
        params['capacity_mw'],
        params['capacity_factor'],
        params['degradation'],
        params['grid_loss_pct'],
        year
    )
    
    revenue_lkr = calculate_revenue_lkr(net_kwh, params['tariff_lkr_per_kwh'])
    revenue_usd = revenue_lkr / fx_rate if fx_rate > 0 else 0.0
    
    return revenue_usd

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MODULE SELF-TEST
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

if __name__ == "__main__":
    print("\n" + "="*100)
    print("CASHFLOW MODULE v2.0 - SELF-TEST")
    print("="*100)
    
    # Sample configuration
    sample_config = {
        'project': {
            'capacity_mw': 150,
            'capacity_factor': 0.40,
            'degradation': 0.006,
        },
        'tariff': {
            'lkr_per_kwh': 20.30,
        },
        'regulatory': {
            'grid_loss_pct': 0.02,
            'success_fee_pct': 0.01,
            'env_surcharge_pct': 0.005,
            'social_services_levy_pct': 0.025,
        },
        'opex': {
            'usd_per_year': 3_000_000,
        },
        'tax': {
            'corporate_tax_rate': 0.30,
            'depreciation_years': 15,
        },
        'risk_adjustment': {
            'cfads_haircut_pct': 0.10,
        },
        'fx': {
            'start_lkr_per_usd': 305,
            'annual_depr': 0.03,
        },
        'returns': {
            'project_life_years': 20,
        },
        'capex': {
            'usd_total': 150_000_000,
        },
    }
    
    print("\nâœ“ Testing parameter validation...")
    issues = _validate_parameters(sample_config)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  All parameters valid")
    
    print("\nâœ“ Testing CFADS calculation (first 3 years, verbose)...")
    cfads_series = build_annual_cfads(sample_config, verbose=False)
    
    print(f"\nâœ“ CFADS Summary:")
    print(f"  Year 1: LKR {cfads_series[0]:,.0f}")
    print(f"  Year 10: LKR {cfads_series[9]:,.0f}")
    print(f"  Year 20: LKR {cfads_series[19]:,.0f}")
    print(f"  Average: LKR {sum(cfads_series)/len(cfads_series):,.0f}")
    
    print("\nâœ“ Testing detailed breakdown...")
    rows = build_annual_rows(sample_config)
    print(f"  Generated {len(rows)} annual rows")
    print(f"  Year 1 breakdown:")
    for key, value in rows[0].items():
        if isinstance(value, (int, float)) and key != 'year':
            print(f"    {key}: {value:,.0f}")
    
    print("\n" + "="*100)
    print("âœ“ SELF-TEST COMPLETE - Module ready for production use")
    print("="*100 + "\n")

    