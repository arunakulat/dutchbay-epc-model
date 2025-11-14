"""
Returns Module for DutchBay V13 - Option A Step 4 (updated for social services levy)
Full tax, regulatory, risk, and DSCR-sculpted logic with MC FX support, now incorporates social_services_levy.
"""
from typing import List, Dict, Any, Optional
import logging
import numpy as np

logger = logging.getLogger('dutchbay.finance.returns')

def corrected_project_cashflows_and_ds(params: dict, montecarlo_fx: Optional[List[float]] = None):
    """
    Calculate corrected project/equity cashflows with:
    - Grid loss, regulatory (success, env, social levy), risk haircut, tax, DSCR sculpt
    - Monte Carlo FX override
    Returns: (project_cfs, equity_cfs, ds_list, cfads_list, tax_list, cfads_gross)
    """
    capex = params.get('capex', {}).get('usd_total', 150_000_000)
    opex_usd = params.get('opex', {}).get('usd_per_year', 3_000_000)
    project = params.get('project', {})
    capacity_mw = project.get('capacity_mw', 150)
    capacity_factor = project.get('capacity_factor', 0.40)
    degradation = project.get('degradation', 0.006)
    project_life = params.get('returns', {}).get('project_life_years', 20)
    tariff_lkr = params.get('tariff', {}).get('lkr_per_kwh', 20.3)
    fx_info = params.get('fx', {})
    start_fx = fx_info.get('start_lkr_per_usd', 300)
    annual_fx_depr = fx_info.get('annual_depr', 0.03)
    grid_loss = params.get('regulatory', {}).get('grid_loss_pct', 0.0) or 0.0
    success_fee = params.get('regulatory', {}).get('success_fee_pct', 0.0) or 0.0
    env_surcharge = params.get('regulatory', {}).get('env_surcharge_pct', 0.0) or 0.0
    social_levy = params.get('regulatory', {}).get('social_services_levy_pct', 0.0) or 0.0
    cfads_haircut_pct = params.get('risk_adjustment', {}).get('cfads_haircut_pct', 0.0) or 0.0
    tax_rate = params.get('tax', {}).get('corporate_tax_rate', 0.30)
    depreciation_years = params.get('tax', {}).get('depreciation_years', 15)
    min_tax = params.get('tax', {}).get('min_tax', 0.0)
    debt_ratio = params.get('Financing_Terms', {}).get('debt_ratio', 0.70)
    interest_only_years = params.get('Financing_Terms', {}).get('interest_only_years', 2)
    tenor_years = params.get('Financing_Terms', {}).get('tenor_years', 15)
    interest_rate = params.get('Financing_Terms', {}).get('interest_rate_nominal', 0.08)
    target_dscr = params.get('Financing_Terms', {}).get('target_dscr', 1.30)
    total_debt = capex * debt_ratio
    equity_invest = capex * (1 - debt_ratio)
    fx_curve = montecarlo_fx if montecarlo_fx is not None else [start_fx * ((1 + annual_fx_depr)**i) for i in range(project_life)]
    yearly_depr = capex / depreciation_years if depreciation_years > 0 else 0
    kwh_base = capacity_mw * 1000 * 8760 * capacity_factor
    project_cfs, equity_cfs, ds_list, ctax_list, cfads_list, cfads_gross = [], [], [], [], [], []
    debt_left = total_debt
    years_left = tenor_years
    project_cfs.append(-capex)
    equity_cfs.append(-equity_invest)
    for year in range(project_life):
        gross_kwh = kwh_base * ((1-degradation) ** year)
        net_kwh = gross_kwh * (1 - grid_loss)
        rev_lkr = net_kwh * tariff_lkr
        # Deduct all regulatory fees/levies (add new levies here for future):
        total_reg = success_fee + env_surcharge + social_levy
        rev_lkr_adj = rev_lkr * (1 - total_reg)
        fx = fx_curve[year]
        rev_usd = rev_lkr_adj / fx
        cfads_pre_risk = rev_usd - opex_usd
        cfads_gross.append(cfads_pre_risk)
        cfads = cfads_pre_risk * (1 - cfads_haircut_pct)
        cfads_list.append(cfads)
        if year < interest_only_years:
            debt_service = debt_left * interest_rate
            principal = 0
        elif years_left > 0 and debt_left > 0:
            interest = debt_left * interest_rate
            principal = max(0, min((cfads / target_dscr) - interest, debt_left))
            debt_service = interest + principal
            debt_left -= principal
            years_left -= 1
        else:
            debt_service = 0
            principal = 0
        ds_list.append(debt_service)
        ebt = cfads - (debt_left * interest_rate) - yearly_depr
        tax_pay = max(tax_rate * max(ebt, 0), min_tax)
        ctax_list.append(tax_pay)
        project_cfs.append(cfads - tax_pay)
        equity_cfs.append(cfads - debt_service - tax_pay)
    return project_cfs, equity_cfs, ds_list, cfads_list, ctax_list, cfads_gross

def npv(cashflows: List[float], discount: float) -> float:
    return sum(cf / ((1 + discount) ** i) for i, cf in enumerate(cashflows))

def irr(cashflows: List[float], guess: float = 0.10) -> Optional[float]:
    try:
        import numpy_financial as npf
        return float(npf.irr(cashflows))
    except ImportError:
        return float('nan')

def calculate_all_returns(params: dict, montecarlo_fx: Optional[List[float]] = None) -> Dict[str, float]:
    project_cfs, equity_cfs, ds_list, cfads_list, tax_list, cfads_gross = corrected_project_cashflows_and_ds(params, montecarlo_fx)
    project_discount_rate = params.get('returns', {}).get('project_discount_rate', 0.10)
    equity_discount_rate = params.get('returns', {}).get('equity_discount_rate', 0.12)
    project_npv = npv(project_cfs, project_discount_rate)
    equity_npv = npv(equity_cfs, equity_discount_rate)
    project_irr = irr(project_cfs)
    equity_irr = irr(equity_cfs)
    return {
        'project': {'project_npv': project_npv,'project_irr': project_irr,'project_cfs': project_cfs},
        'equity': {'equity_npv': equity_npv,'equity_irr': equity_irr,'equity_cfs': equity_cfs,'equity_investment': -equity_cfs[0]},
        'debt_service': ds_list,
        'cfads': cfads_list,
        'tax': tax_list,
        'cfads_gross': cfads_gross
    }
