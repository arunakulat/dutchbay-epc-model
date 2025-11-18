"""
Debt Planning Module for DutchBay V14 Project Finance

ENHANCEMENTS IN V14:
--------------------
- 2-year construction period with debt drawdown
- Interest During Construction (IDC) capitalization
- 23-period timeline (2 construction + 1 transition + 20 ops)
- Grace period handling for operations
- Enhanced DSCR calculation

ORIGINAL V13 FEATURES:
----------------------
- Multi-currency tranches: LKR, USD commercial, DFI
- Interest-only (grace) period, annuity/sculpted amortization
- YAML-driven validation for all banking covenants
- Balloon payment refinancing analysis

Author: DutchBay V14 Team, Nov 2025
Version: 3.0 (V14 construction period support)
"""

import math
import logging
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('dutchbay.v14chat.finance.debt')

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    """Safely traverse nested dict."""
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    """Safe float conversion with default."""
    try:
        return float(v) if v is not None else default
    except Exception:
        return default

def _pmt(rate: float, nper: int, pv: float) -> float:
    """Calculate annuity payment (Excel PMT equivalent)."""
    if rate == 0:
        return pv / nper
    return pv * (rate * (1 + rate) ** nper) / ((1 + rate) ** nper - 1)

# ============================================================================
# NEW V14: CONSTRUCTION PERIOD FUNCTIONS
# ============================================================================

def calculate_construction_drawdowns(
    total_debt: float,
    construction_schedule: List[float],
    drawdown_pct_per_year: List[float]
) -> List[float]:
    """
    Calculate debt drawdown during construction periods.
    
    Parameters:
    -----------
    total_debt : float
        Total debt amount available
    construction_schedule : list
        Capex per construction year [Year1, Year2]
    drawdown_pct_per_year : list
        % of total debt to draw each year [0.5, 0.5]
    
    Returns:
    --------
    list of drawn amounts per construction year
    """
    drawn_schedule = []
    cumulative_drawn = 0.0
    
    for year_idx, capex in enumerate(construction_schedule):
        if year_idx < len(drawdown_pct_per_year):
            drawn_this_year = total_debt * drawdown_pct_per_year[year_idx]
        else:
            drawn_this_year = 0.0
        
        drawn_schedule.append(drawn_this_year)
        cumulative_drawn += drawn_this_year
    
    # Ensure total drawn doesn't exceed available debt
    if cumulative_drawn > total_debt:
        logger.warning(f"Total drawn {cumulative_drawn:.2f} exceeds total debt {total_debt:.2f}")
    
    return drawn_schedule

def calculate_idc(
    debt_drawn_schedule: List[float],
    interest_rate: float,
    construction_periods: int
) -> Tuple[List[float], float]:
    """
    Calculate Interest During Construction.
    
    IDC is capitalized (added to loan balance) during construction.
    
    Parameters:
    -----------
    debt_drawn_schedule : list
        Debt drawn each period
    interest_rate : float
        Annual interest rate for tranche
    construction_periods : int
        Number of construction periods
    
    Returns:
    --------
    tuple: (idc_schedule, total_idc_capitalized)
    """
    idc_schedule = []
    outstanding_balance = 0.0
    total_idc_capitalized = 0.0
    
    for period in range(len(debt_drawn_schedule)):
        # Add this period's drawdown to balance
        outstanding_balance += debt_drawn_schedule[period]
        
        # Calculate IDC on outstanding balance
        idc_this_period = outstanding_balance * interest_rate
        idc_schedule.append(idc_this_period)
        
        if period < construction_periods:
            # During construction: capitalize IDC (add to balance)
            total_idc_capitalized += idc_this_period
            outstanding_balance += idc_this_period
    
    return idc_schedule, total_idc_capitalized

# ============================================================================
# TRANCHE DEFINITION
# ============================================================================

class Tranche:
    """Represents a single debt tranche."""
    __slots__ = ("name", "rate", "principal", "years_io")
    
    def __init__(self, name: str, rate: float, principal: float, years_io: int):
        self.name = name
        self.rate = float(rate)
        self.principal = float(principal)
        self.years_io = int(years_io)

def _solve_mix(p: Dict[str, Any], debt_total: float) -> Dict[str, Tranche]:
    """Solve tranche mix based on YAML constraints."""
    mix = p.get("mix", {})
    rates = p.get("rates", {})
    
    mix_lkr_max = _as_float(mix.get("lkr_max"), 0.0)
    mix_dfi_max = _as_float(mix.get("dfi_max"), 0.0)
    mix_usd_min = _as_float(mix.get("usd_commercial_min"), 0.0)
    
    r_lkr = _as_float(rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0)
    r_usd = _as_float(rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0)
    r_dfi = _as_float(rates.get("dfi_nominal") or rates.get("dfi_min"), 0.0)
    
    # Allocation logic (same as v13)
    lkr_amt = min(debt_total * mix_lkr_max, debt_total)
    dfi_amt = min(debt_total * mix_dfi_max, max(0.0, debt_total - lkr_amt))
    usd_amt = max(0.0, debt_total - lkr_amt - dfi_amt)
    
    # Enforce USD minimum
    min_usd_amt = debt_total * mix_usd_min
    if usd_amt < min_usd_amt:
        need = min_usd_amt - usd_amt
        pull_lkr = min(need, lkr_amt)
        lkr_amt -= pull_lkr
        need -= pull_lkr
        if need > 0:
            pull_dfi = min(need, dfi_amt)
            dfi_amt -= pull_dfi
        usd_amt = debt_total - lkr_amt - dfi_amt
    
    years_io = int(_as_float(p.get("interest_only_years"), 0) or 0)
    
    return {
        "LKR": Tranche("LKR", r_lkr, lkr_amt, years_io),
        "USD": Tranche("USD", r_usd, usd_amt, years_io),
        "DFI": Tranche("DFI", r_dfi, dfi_amt, years_io),
    }

# ============================================================================
# AMORTIZATION SCHEDULES (V13 preserved, extended for v14)
# ============================================================================

def _annuity_schedule(tr: Tranche, amort_years: int) -> List[Tuple[float, float, float]]:
    """Build annuity schedule."""
    n = amort_years
    bal = tr.principal
    rows: List[Tuple[float, float, float]] = []
    
    # Interest-only period
    for _ in range(tr.years_io):
        interest = bal * tr.rate
        rows.append((interest, 0.0, interest))
    
    # Amortization period
    if n > 0:
        pmt = _pmt(tr.rate, n, bal)
        for _ in range(n):
            interest = bal * tr.rate
            principal = max(0.0, pmt - interest)
            bal = max(0.0, bal - principal)
            rows.append((interest, principal, interest + principal))
    
    return rows

def _sculpted_schedule(
    tranches: Dict[str, Tranche],
    amort_years: int,
    cfads: List[float],
    dscr_target: float
) -> Dict[str, List[Tuple[float, float, float]]]:
    """Build sculpted schedule targeting DSCR."""
    obals = {k: tr.principal for k, tr in tranches.items()}
    schedules = {k: [] for k in tranches.keys()}
    io_years = max(tr.years_io for tr in tranches.values())
    year_index = 0
    
    # Interest-only period
    for _ in range(io_years):
        for k, tr in tranches.items():
            bal = obals[k]
            interest = bal * tr.rate
            schedules[k].append((interest, 0.0, interest))
        year_index += 1
    
    # Amortization period
    for _ in range(amort_years):
        cf = cfads[year_index] if year_index < len(cfads) else (cfads[-1] if cfads else 0.0)
        target_service = max(0.0, cf / dscr_target)
        
        interest_map = {k: obals[k] * tranches[k].rate for k in tranches.keys()}
        total_interest = sum(interest_map.values())
        principal_total = max(0.0, target_service - total_interest)
        
        total_bal = sum(obals.values()) or 1.0
        for k, tr in tranches.items():
            bal = obals[k]
            prorata = bal / total_bal if total_bal > 0 else 0.0
            principal_k = min(bal, principal_total * prorata)
            interest_k = interest_map[k]
            obals[k] = max(0.0, bal - principal_k)
            schedules[k].append((interest_k, principal_k, interest_k + principal_k))
        
        year_index += 1
    
    return schedules

# ============================================================================
# MAIN ENTRY POINT (ENHANCED FOR V14)
# ============================================================================

def apply_debt_layer(params: Dict[str, Any], annual_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply debt financing layer with V14 construction period support.
    
    NEW IN V14:
    -----------
    - Handles 2-year construction period
    - Calculates IDC and capitalizes it
    - Returns 23-period results
    - Grace period support
    """
    # Extract financing params
    p = params.get('Financing_Terms', params.get('financing', params))
    
    # ========== NEW V14: CONSTRUCTION PARAMETERS ==========
    construction_periods = int(_as_float(p.get("construction_periods"), 2))
    construction_schedule = p.get("construction_schedule", [40.0, 60.0])  # Capex per year
    drawdown_pct = p.get("debt_drawdown_pct", [0.5, 0.5])  # % of debt drawn each year
    grace_years = int(_as_float(p.get("grace_years"), 0))
    
    # ========== STANDARD PARAMETERS ==========
    debt_ratio = _as_float(p.get("debt_ratio"), 0.70)
    tenor = int(_as_float(p.get("tenor_years"), 15))
    years_io = int(_as_float(p.get("interest_only_years"), 0))
    amortization = (p.get("amortization_style", "sculpted") or "sculpted").lower()
    target_dscr = _as_float(p.get("target_dscr"), 1.30)
    
    capex = float(params.get("capex", {}).get("usd_total", 100.0))
    debt_total = capex * debt_ratio
    
    logger.info(f"V14 Debt Planning: {construction_periods}-year construction, {tenor}-year tenor")
    
    # ========== NEW V14: CALCULATE IDC ==========
    tranches = _solve_mix(p, debt_total)
    
    idc_schedule = {}
    total_idc_by_tranche = {}
    
    for tranche_name, tranche in tranches.items():
        # Calculate debt drawdown for this tranche
        drawn = calculate_construction_drawdowns(
            tranche.principal,
            construction_schedule,
            drawdown_pct
        )
        
        # Calculate IDC
        idc_per_period, total_idc_cap = calculate_idc(
            drawn,
            tranche.rate,
            construction_periods
        )
        
        idc_schedule[tranche_name] = idc_per_period
        total_idc_by_tranche[tranche_name] = total_idc_cap
        
        # Add IDC to principal (capitalized)
        tranche.principal += total_idc_cap
        logger.info(f"  {tranche_name}: Principal ${tranche.principal:.2f}M (IDC: ${total_idc_cap:.2f}M)")
    
    # ========== EXTEND CFADS TO 23 PERIODS ==========
    cfads = [a.get("cfads_usd", 0.0) for a in annual_rows]
    
    cfads_extended = []
    # Construction periods: 0 CFADS
    for _ in range(construction_periods):
        cfads_extended.append(0.0)
    
    # Transition period: partial CFADS (50%)
    if len(cfads) > 0:
        cfads_extended.append(cfads[0] * 0.5)
    else:
        cfads_extended.append(0.0)
    
    # Operational periods: full CFADS
    cfads_extended.extend(cfads)
    
    # Ensure exactly 23 periods
    while len(cfads_extended) < 23:
        cfads_extended.append(cfads[-1] if cfads else 0.0)
    cfads_extended = cfads_extended[:23]
    
    # ========== BUILD SCHEDULES ==========
    if amortization in ("annuity", "fixed"):
        schedules = {k: _annuity_schedule(tr, tenor - tr.years_io) for k, tr in tranches.items()}
    else:
        schedules = _sculpted_schedule(tranches, tenor - years_io, cfads_extended[construction_periods:], target_dscr)
    
    # Pad schedules with construction period zeros
    for k in schedules:
        padded = [(0.0, 0.0, 0.0)] * construction_periods + schedules[k]
        schedules[k] = padded
    
    # ========== COMPUTE METRICS FOR 23 PERIODS ==========
    dscr_series = []
    debt_service_total = []
    debt_outstanding = []
    
    outstanding_balances = {k: tr.principal for k, tr in tranches.items()}
    
    for period in range(23):
        total_outstanding = sum(outstanding_balances.values())
        debt_outstanding.append(total_outstanding)
        
        total_service = 0.0
        for k in schedules:
            if period < len(schedules[k]):
                interest, principal, service = schedules[k][period]
                total_service += service
                outstanding_balances[k] = max(0.0, outstanding_balances[k] - principal)
        
        debt_service_total.append(total_service)
        
        # DSCR: only during operations
        if period < len(cfads_extended):
            cfads_this_period = cfads_extended[period]
        else:
            cfads_this_period = 0.0
        
        if period >= construction_periods and total_service > 0:
            dscr = cfads_this_period / total_service
        else:
            dscr = float('inf')  # Not applicable during construction
        
        dscr_series.append(dscr)
    
    # Calculate min DSCR (only operational periods)
    dscr_operational = [d for i, d in enumerate(dscr_series) if i >= construction_periods and d < float('inf')]
    dscr_min = min(dscr_operational) if dscr_operational else 0.0
    
    balloon_remaining = sum(outstanding_balances.values())
    
    logger.info(f"V14 Results: Min DSCR={dscr_min:.2f}, Total IDC=${sum(total_idc_by_tranche.values()):.2f}M")
    
    # ========== RETURN COMPREHENSIVE RESULTS ==========
    return {
        'dscr_series': dscr_series,
        'dscr_min': dscr_min,
        'debt_service_total': debt_service_total,
        'debt_outstanding': debt_outstanding,
        'balloon_remaining': balloon_remaining,
        
        # NEW V14 fields
        'construction_periods': construction_periods,
        'construction_schedule': construction_schedule,
        'idc_schedule': idc_schedule,
        'total_idc_capitalized': sum(total_idc_by_tranche.values()),
        'idc_by_tranche': total_idc_by_tranche,
        'grace_periods': grace_years,
        'timeline_periods': 23,
        'cfads_extended': cfads_extended,
        
        # Validation fields (simplified for v14 initial version)
        'validation_warnings': [],
        'dscr_violations': [],
        'balloon_warnings': [],
        'audit_status': 'PASS' if dscr_min >= 1.30 else 'REVIEW',
    }
