"""
Returns Module for DutchBay V13 - Option A Step 3 (YAML-driven discount rates)
Calculates project- and equity-level IRR, NPV, payback period using rates from YAML.
"""
from typing import List, Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger('dutchbay.finance.returns')

def _npv(cashflows: List[float], discount_rate: float = 0.10) -> float:
    if not cashflows:
        return 0.0
    npv = 0.0
    for i, cf in enumerate(cashflows):
        npv += cf / ((1 + discount_rate) ** i)
    return npv

def _irr(cashflows: List[float], max_iterations: int = 1000, tolerance: float = 1e-6) -> Optional[float]:
    if not cashflows or len(cashflows) < 2:
        return None
    rate = 0.10
    for iteration in range(max_iterations):
        npv = sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cashflows))
        dnpv = sum(-i * cf / ((1 + rate) ** (i + 1)) for i, cf in enumerate(cashflows))
        if abs(dnpv) < 1e-10:
            break
        rate_new = rate - npv / dnpv
        if abs(rate_new - rate) < tolerance:
            return rate_new
        rate = rate_new
    return rate if abs(npv) < tolerance else None

def _payback_period(cashflows: List[float]) -> Optional[float]:
    cumulative = 0.0
    for i, cf in enumerate(cashflows):
        cumulative += cf
        if cumulative >= 0:
            if i == 0:
                return 0.0
            prev_cumulative = cumulative - cf
            fraction = abs(prev_cumulative) / cf if cf != 0 else 0
            return i - 1 + fraction
    return None

def calculate_project_returns(
    cfads_series: List[float],
    capex: float,
    discount_rate: float = 0.10,
    project_life: int = 20
) -> Dict[str, Any]:
    project_cfs = [-capex] + cfads_series[:project_life]
    npv = _npv(project_cfs, discount_rate)
    irr = _irr(project_cfs)
    payback = _payback_period(project_cfs)
    return {
        'project_npv': npv,
        'project_irr': irr,
        'project_payback': payback,
        'calculation_details': {
            'capex': capex,
            'discount_rate': discount_rate,
            'project_life': project_life,
            'years_with_cfads': len(cfads_series)
        }
    }

def calculate_equity_returns(
    cfads_series: List[float],
    debt_service_series: List[float],
    capex: float,
    debt_ratio: float = 0.70,
    discount_rate: float = 0.12,
    project_life: int = 20
) -> Dict[str, Any]:
    equity_investment = capex * (1 - debt_ratio)
    equity_cfs = [-equity_investment]
    for i in range(project_life):
        cfads = cfads_series[i] if i < len(cfads_series) else 0.0
        ds = debt_service_series[i] if i < len(debt_service_series) else 0.0
        equity_cf = cfads - ds
        equity_cfs.append(equity_cf)
    npv = _npv(equity_cfs, discount_rate)
    irr = _irr(equity_cfs)
    payback = _payback_period(equity_cfs)
    return {
        'equity_npv': npv,
        'equity_irr': irr,
        'equity_payback': payback,
        'equity_investment': equity_investment,
        'calculation_details': {
            'capex': capex,
            'debt_ratio': debt_ratio,
            'equity_ratio': 1 - debt_ratio,
            'discount_rate': discount_rate,
            'project_life': project_life
        }
    }

def calculate_all_returns(
    cfads_series: List[float],
    debt_service_series: List[float],
    capex: float,
    debt_ratio: float = 0.70,
    project_discount_rate: Optional[float] = None,
    equity_discount_rate: Optional[float] = None,
    project_life: int = 20
) -> Dict[str, Any]:
    # Default to 10% and 12% if None (enforced at entrypoint)
    project_discount_rate = project_discount_rate if project_discount_rate is not None else 0.10
    equity_discount_rate = equity_discount_rate if equity_discount_rate is not None else 0.12
    project = calculate_project_returns(cfads_series, capex, project_discount_rate, project_life)
    equity = calculate_equity_returns(cfads_series, debt_service_series, capex, debt_ratio, equity_discount_rate, project_life)
    summary = {
        'project_irr': project['project_irr'],
        'equity_irr': equity['equity_irr'],
        'project_npv': project['project_npv'],
        'equity_npv': equity['equity_npv'],
        'leverage': f"{debt_ratio*100:.1f}% debt / {(1-debt_ratio)*100:.1f}% equity"
    }
    return {
        'project': project,
        'equity': equity,
        'summary': summary
    }
