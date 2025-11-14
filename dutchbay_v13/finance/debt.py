"""
Debt Planning Module for DutchBay V13 Project Finance

COMPLIANCE:
-----------
- IFC, World Bank project finance standards
- Commercial/DFI/ECA scenarios supported
- Audit/control features for DSCR, balloon, tenor, leverage
- Refinancing feasibility analysis for balloon payments

FEATURES:
---------
- Multi-currency tranches: LKR, USD commercial, DFI
- Interest-only (grace) period, annuity/sculpted amortization
- YAML-driven validation for all banking covenants
- Automated auditing/logging/flagging for constraints
- Balloon payment refinancing analysis
- Parameter alignment documentation (YAML vs code defaults)

INPUTS:
-------
All 'Financing_Terms' block from YAML (see full_model_variables_updated.yaml):
  - debt_ratio, tenor_years, interest_only_years, amortization_style
  - mix (tranche limitations), rates, DSCR targets/minimums
  - constraints (max_debt_ratio, min_dscr_covenant, max_balloon_pct, ...)
  - refinancing (enabled, max_refinance_pct, rate premium, tenor)

OUTPUTS:
--------
Dict with:
    dscr_series: list, dscr_min: float, debt_service_total: list
    balloon_remaining: float, validation_warnings: list
    dscr_violations: list, balloon_warnings: list
    refinancing_analysis: dict, alignment_notes: dict
    audit_status: PASS or REVIEW

Author: DutchBay V13 Team, Nov 2025, P0-1B Enhanced
Version: 2.0 (with refinancing & alignment features)
"""

import math
import logging
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('dutchbay.finance.debt')

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
# TRANCHE DEFINITION & MIX SOLVER
# ============================================================================

class Tranche:
    """Represents a single debt tranche (LKR, USD, or DFI)."""
    __slots__ = ("name", "rate", "principal", "years_io")
    
    def __init__(self, name: str, rate: float, principal: float, years_io: int):
        self.name = name
        self.rate = float(rate)
        self.principal = float(principal)
        self.years_io = int(years_io)

def _solve_mix(p: Dict[str, Any], debt_total: float) -> Dict[str, Tranche]:
    """
    Solve tranche mix based on YAML constraints.
    
    Enforces:
    - LKR max cap
    - DFI max cap
    - USD commercial minimum floor
    - Pro-rata allocation logic
    """
    mix = p.get("mix", {})
    rates = p.get("rates", {})
    
    mix_lkr_max = _as_float(mix.get("lkr_max"), 0.0)
    mix_dfi_max = _as_float(mix.get("dfi_max"), 0.0)
    mix_usd_min = _as_float(mix.get("usd_commercial_min"), 0.0)
    
    r_lkr = _as_float(rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0)
    r_usd = _as_float(rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0)
    r_dfi = _as_float(rates.get("dfi_nominal") or rates.get("dfi_min"), 0.0)

    # Initial allocation
    lkr_amt = min(debt_total * mix_lkr_max, debt_total)
    dfi_amt = min(debt_total * mix_dfi_max, max(0.0, debt_total - lkr_amt))
    usd_amt = max(0.0, debt_total - lkr_amt - dfi_amt)
    
    # Enforce USD minimum by pulling from LKR then DFI
    min_usd_amt = debt_total * mix_usd_min
    if usd_amt < min_usd_amt:
        need = min_usd_amt - usd_amt
        pull_lkr = min(need, lkr_amt)
        lkr_amt -= pull_lkr
        need -= pull_lkr
        if need > 0:
            pull_dfi = min(need, dfi_amt)
            dfi_amt -= pull_dfi
            need -= pull_dfi
        usd_amt = debt_total - lkr_amt - dfi_amt

    years_io = int(_as_float(p.get("interest_only_years"), 0) or 0)
    
    return {
        "LKR": Tranche("LKR", r_lkr, lkr_amt, years_io),
        "USD": Tranche("USD", r_usd, usd_amt, years_io),
        "DFI": Tranche("DFI", r_dfi, dfi_amt, years_io),
    }

# ============================================================================
# AMORTIZATION SCHEDULES
# ============================================================================

def _annuity_schedule(tr: Tranche, amort_years: int) -> List[Tuple[float, float, float]]:
    """
    Build annuity schedule for one tranche.
    
    Returns list of (interest, principal, total_service) per year.
    """
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
    """
    Build sculpted schedule targeting DSCR.
    
    Allocates principal pro-rata across tranches to hit target debt service.
    """
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
# VALIDATION FUNCTIONS
# ============================================================================

def _validate_financing_params(p: Dict[str, Any]) -> List[str]:
    """
    Validate financing parameters against YAML-configured constraints.
    Falls back to industry defaults if constraints not specified.
    """
    issues = []
    constraints = p.get("constraints", {})
    
    # Load constraints with fallbacks
    max_debt = _as_float(constraints.get("max_debt_ratio"), 0.85)
    warn_debt = _as_float(constraints.get("warn_debt_ratio"), 0.80)
    min_dscr = _as_float(constraints.get("min_dscr_covenant"), 1.30)
    warn_dscr = _as_float(constraints.get("warn_dscr"), 1.25)
    max_balloon = _as_float(constraints.get("max_balloon_pct"), 0.10)
    warn_balloon = _as_float(constraints.get("warn_balloon_pct"), 0.05)
    max_tenor = int(_as_float(constraints.get("max_tenor_years"), 25) or 25)
    warn_tenor = int(_as_float(constraints.get("warn_tenor_years"), 20) or 20)
    max_rate = _as_float(constraints.get("max_interest_rate"), 0.25)
    min_rate = _as_float(constraints.get("min_interest_rate"), 0.0)

    # Validate debt ratio
    debt_ratio = _as_float(p.get("debt_ratio"), None)
    if debt_ratio is None:
        issues.append("ERROR: debt_ratio missing")
    elif debt_ratio < 0 or debt_ratio > 1:
        issues.append(f"ERROR: debt_ratio {debt_ratio} out of [0,1]")
    elif debt_ratio > max_debt:
        issues.append(f"ERROR: debt_ratio {debt_ratio:.1%} > max {max_debt:.1%}")
    elif debt_ratio > warn_debt:
        issues.append(f"WARNING: High debt ratio {debt_ratio:.1%} > warn {warn_debt:.1%}")

    # Validate tenor
    tenor = int(_as_float(p.get("tenor_years"), 0) or 0)
    if tenor <= 0:
        issues.append("ERROR: tenor_years must be positive")
    elif tenor > max_tenor:
        issues.append(f"ERROR: tenor {tenor} > max {max_tenor}")
    elif tenor > warn_tenor:
        issues.append(f"WARNING: long tenor {tenor} > warn {warn_tenor}")

    # Validate DSCR target
    amort = (p.get("amortization_style") or "sculpted").lower()
    dscr_target = _as_float(p.get("target_dscr"), None)
    if amort.startswith("sculpt") and (dscr_target is None or dscr_target < 1.0):
        issues.append(f"ERROR: sculpted amortization requires dscr_target >= 1.0 (got {dscr_target})")
    elif amort.startswith("sculpt") and dscr_target < min_dscr:
        issues.append(f"WARNING: target_dscr {dscr_target:.2f} < min {min_dscr:.2f}")

    # Validate interest rates
    rates = p.get("rates", {})
    for tranche in ["lkr_nominal", "usd_nominal", "dfi_nominal", "lkr_min", "usd_commercial_min", "dfi_min"]:
        rate = _as_float(rates.get(tranche), None)
        if rate is not None:
            if rate < min_rate:
                issues.append(f"ERROR: Negative rate {tranche}: {rate}")
            elif rate > max_rate:
                issues.append(f"ERROR: {tranche} {rate:.1%} > max {max_rate:.1%}")
    
    return issues

def _check_dscr_covenant(dscr_series: List[float], p: Dict[str, Any]) -> List[str]:
    """
    Check DSCR covenant compliance across all years.
    """
    constraints = p.get("constraints", {})
    min_dscr = _as_float(constraints.get("min_dscr_covenant"), 1.30)
    warn_dscr = _as_float(constraints.get("warn_dscr"), 1.25)
    violations = []
    
    for year, dscr in enumerate(dscr_series, 1):
        if dscr < 1.0:
            violations.append(f"CRITICAL: Year {year} DSCR {dscr:.2f} < 1.0")
        elif dscr < min_dscr:
            violations.append(f"WARNING: Year {year} DSCR {dscr:.2f} < covenant {min_dscr:.2f}")
        elif dscr < warn_dscr:
            violations.append(f"INFO: Year {year} DSCR {dscr:.2f} < warn {warn_dscr:.2f}")
    
    return violations

def _check_refinancing_feasibility(balloon: float, principal: float, p: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze balloon payment and determine refinancing feasibility.
    
    Returns:
        dict with feasibility assessment and mitigation options
    """
    constraints = p.get("constraints", {})
    refinancing = constraints.get("refinancing", {})
    
    balloon_pct = balloon / principal if principal > 0 else 0
    warn_pct = _as_float(constraints.get("warn_balloon_pct"), 0.05)
    max_pct = _as_float(constraints.get("max_balloon_pct"), 0.10)
    
    result = {
        'balloon_amount': balloon,
        'balloon_pct': balloon_pct,
        'feasible': True,
        'mitigation_required': False,
        'mitigation_options': [],
        'notes': ''
    }
    
    # No balloon - all good
    if balloon_pct < 0.01:
        result['notes'] = "No material balloon payment"
        return result
    
    # Small balloon - acceptable
    if balloon_pct <= warn_pct:
        result['notes'] = f"Small balloon ({balloon_pct:.1%}) - acceptable"
        return result
    
    # Medium balloon - mitigation recommended
    if balloon_pct <= max_pct:
        result['mitigation_required'] = True
        result['mitigation_options'] = [
            "Refinancing commitment from lender",
            "Cash sweep mechanism to reduce balloon",
            "Equity injection commitment at maturity",
            "Extend amortization period",
            "Increase DSCR target (more aggressive principal repayment)"
        ]
        
        # Check if refinancing is enabled
        if refinancing.get('enabled', False):
            max_refi = _as_float(refinancing.get('max_refinance_pct'), 0.15)
            if balloon_pct <= max_refi:
                result['feasible'] = True
                result['notes'] = f"Balloon {balloon_pct:.1%} can be refinanced (max {max_refi:.1%})"
            else:
                result['feasible'] = False
                result['notes'] = f"Balloon {balloon_pct:.1%} exceeds refinancing limit {max_refi:.1%}"
        else:
            result['notes'] = f"Balloon {balloon_pct:.1%} requires mitigation - refinancing disabled"
    
    # Large balloon - not feasible
    else:
        result['feasible'] = False
        result['mitigation_required'] = True
        result['mitigation_options'] = [
            "ERROR: Balloon too large - must restructure debt",
            "Option 1: Extend tenor (reduce annual DS, more principal repaid)",
            "Option 2: Increase DSCR target significantly",
            "Option 3: Reduce debt ratio",
            "Option 4: Switch to annuity amortization"
        ]
        result['notes'] = f"Balloon {balloon_pct:.1%} exceeds maximum {max_pct:.1%} - not acceptable"
    
    return result

def _check_balloon_payment(balloon: float, original_principal: float, p: Dict[str, Any]) -> List[str]:
    """
    Check balloon payment against YAML-configured thresholds with refinancing logic.
    """
    warnings_list = []
    
    constraints = p.get("constraints", {})
    max_balloon_pct = _as_float(constraints.get("max_balloon_pct"), 0.10)
    warn_balloon_pct = _as_float(constraints.get("warn_balloon_pct"), 0.05)
    
    if balloon > 0 and original_principal > 0:
        pct = balloon / original_principal
        
        # Check refinancing feasibility
        refi_check = _check_refinancing_feasibility(balloon, original_principal, p)
        
        if pct > max_balloon_pct:
            if refi_check['feasible']:
                warnings_list.append(
                    f"WARNING: Large balloon ${balloon:.2f}M ({pct:.1%}) - refinancing required"
                )
            else:
                warnings_list.append(
                    f"ERROR: Balloon ${balloon:.2f}M ({pct:.1%}) exceeds max {max_balloon_pct:.0%} - not refinanceable"
                )
        elif pct > warn_balloon_pct:
            warnings_list.append(
                f"INFO: Material balloon ${balloon:.2f}M ({pct:.1%}) - mitigation recommended"
            )
            if refi_check['mitigation_options']:
                warnings_list.append(f"  Options: {', '.join(refi_check['mitigation_options'][:2])}")
        else:
            logger.info(f"Balloon payment: ${balloon:.2f}M ({pct:.1%} of principal) - within limits")
    
    return warnings_list

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def apply_debt_layer(params: Dict[str, Any], annual_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply debt financing layer to project cashflows.
    
    Parameters
    ----------
    params : dict
        Full parameter dictionary (should contain 'Financing_Terms')
    annual_rows : list of dict
        Annual cashflow data with 'cfads_usd' key
    
    Returns
    -------
    dict
        Comprehensive debt analysis including DSCR, balloon, validation
    """
    # Extract financing params (supports both nested and flat structures)
    p = params.get('Financing_Terms', params.get('financing', params))
    constraints = p.get("constraints", {})
    
    # ========== VALIDATION ==========
    validation_issues = _validate_financing_params(p)
    for issue in validation_issues:
        logger.warning(issue)
    
    if any(i.startswith("ERROR") for i in validation_issues):
        logger.error("Validation failed with error(s).")
        raise ValueError(
            "Financing parameter validation failed:\n" + 
            "\n".join([i for i in validation_issues if i.startswith("ERROR")])
        )

    # ========== EXTRACT PARAMETERS ==========
    lifetime = int(_as_float(
        params.get("project", {}).get("timeline", {}).get("lifetime_years"),
        _as_float(params.get("lifetime_years"), 20)
    ))
    debt_ratio = _as_float(p.get("debt_ratio"), 0.70)
    tenor = int(_as_float(p.get("tenor_years"), 15))
    years_io = int(_as_float(p.get("interest_only_years"), 0))
    amortization = (p.get("amortization_style", "sculpted") or "sculpted").lower()
    target_dscr = _as_float(p.get("target_dscr"), 1.30)
    min_dscr = _as_float(p.get("min_dscr"), 1.20)
    capex = float(params.get("capex", {}).get("usd_total", 1e6))
    debt_total = capex * debt_ratio

    # ========== BUILD SCHEDULES ==========
    cfads = [a.get("cfads_usd", 0.0) for a in annual_rows]
    tranches = _solve_mix(p, debt_total)
    
    if amortization in ("annuity", "fixed", "constant"):
        schedules = {k: _annuity_schedule(tr, tenor - tr.years_io) for k, tr in tranches.items()}
    else:  # sculpted, target_dscr, auto
        schedules = _sculpted_schedule(tranches, tenor - years_io, cfads, target_dscr)
    
    # ========== COMPUTE METRICS ==========
    years = max(len(s) for s in schedules.values())
    dscr_series = []
    debt_service_total = []
    debt_outstanding_series = []  # NEW: Track outstanding balance
    # Initialize outstanding balances per tranche
    outstanding_balances = {k: tr.principal for k, tr in tranches.items()}
    for i in range(years):
        # Total outstanding at start of this year
        total_outstanding = sum(outstanding_balances.values())
        debt_outstanding_series.append(total_outstanding)  # NEW
        # Debt service for this year
        total_service = 0.0
        total_principal_paid = 0.0
        for k in schedules:
            if i < len(schedules[k]):
                interest, principal, service = schedules[k][i]
                total_service += service
                total_principal_paid += principal
                # Update outstanding balance for this tranche
                outstanding_balances[k] = max(0.0, outstanding_balances[k] - principal)
            else:
                total_service += 0.0
        # DSCR calculation
        opcf = cfads[i] if i < len(cfads) else 0.0
        dscr = opcf / total_service if total_service > 0 else float('inf')
        dscr_series.append(dscr)
        debt_service_total.append(total_service)
    
    dscr_min = min(dscr_series) if dscr_series else 0.0
    balloon_remaining = sum(schedules[k][-1][1] if schedules[k] else 0.0 for k in schedules)
    original_principal = debt_total

    # ========== COVENANT CHECKS ==========
    dscr_violations = _check_dscr_covenant(dscr_series, p)
    balloon_warnings = _check_balloon_payment(balloon_remaining, original_principal, p)
    refi_analysis = _check_refinancing_feasibility(balloon_remaining, debt_total, p)
    
    # Audit status
    status = "PASS" if not (dscr_violations or balloon_warnings) else "REVIEW"
    
    # Log summary
    logger.info(f"Debt planning: Min DSCR={dscr_min:.2f}, Balloon={balloon_remaining:.2f}, Status={status}")
    
    if refi_analysis['mitigation_required']:
        logger.warning(f"Balloon mitigation required: {refi_analysis['notes']}")
        if refi_analysis['mitigation_options']:
            logger.info(f"  Mitigation options available: {len(refi_analysis['mitigation_options'])}")

    # ========== RETURN COMPREHENSIVE RESULTS ==========
    return {
        'dscr_series': dscr_series,
        'dscr_min': dscr_min,
        'debt_service_total': debt_service_total,
        'debt_outstanding': debt_outstanding_series,  # NEW LINE
        'balloon_remaining': balloon_remaining,
        'validation_warnings': validation_issues,
        'dscr_violations': dscr_violations,
        'balloon_warnings': balloon_warnings,
        'refinancing_analysis': refi_analysis,
        'audit_status': status,
        'alignment_notes': {
            "max_debt_ratio": {
                "yaml": _as_float(constraints.get("max_debt_ratio"), None),
                "code_fallback": 0.85,
                "effective": _as_float(constraints.get("max_debt_ratio"), 0.85),
                "note": "YAML value takes precedence when present"
            },
            "max_tenor_years": {
                "yaml": constraints.get("max_tenor_years"),
                "code_fallback": 25,
                "effective": int(_as_float(constraints.get("max_tenor_years"), 25)),
                "note": "Reduced to 20 for wind/solar best practice"
            }
        }
    }


