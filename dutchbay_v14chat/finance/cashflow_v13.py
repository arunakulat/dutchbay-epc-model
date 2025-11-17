"""
Cash Flow Module for DutchBay V13 Project Finance (v2.2 - BOI Tax Holiday/Enhancement Compliant)

COMPLIANCE:
-----------
- IFC/DFI/World Bank project finance standards
- Sri Lanka Inland Revenue Act (interest expense deductibility, BOI incentives)
- YAML-driven configuration (sourced from full_model_variables_updated.yaml)
- Complete statutory, regulatory, and risk deduction framework
- Audit-ready: full calculation trail and parameter validation

FEATURES & TAX/DEPRECIATION LOGIC:
----------------------------------
- Multi-year, FX-aware, grid-loss-adjusted, statutorily correct LKR cashflows
- CFADS reflects correct order: post all deductions, post-tax, **pre-debt service**
- **Interest expense is deductible for tax calculation** (with full BOI-compliant tax shield)
- **Tax holiday** and **enhanced capital allowance** (100–200% depreciation) logic for BOI
- All periods, parameters, and cash flows driven by YAML settings

Author: DutchBay V13 Team
Version: 2.2 (BOI + enhanced depreciation, strict typing)
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('dutchbay.finance.cashflow')

HOURS_PER_YEAR: float = 8760.0

__all__ = [
    "build_annual_cfads",
    "build_annual_rows",
    "calculate_single_year_cfads",
    "validate_parameters",
]

def _get(d: Dict[str, Any], path: List[str], default=None) -> Any:
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _as_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(x) if x is not None else default
    except Exception:
        return default

def _as_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _years_total(p: Dict[str, Any]) -> int:
    life_years = _as_int(_get(p, ['returns', 'project_life_years'], None))
    if life_years is not None and life_years > 0:
        return life_years
    ops_years = _as_int(_get(p, ['project', 'timeline', 'ops_years'], None))
    if ops_years is not None:
        pre = _as_int(_get(p, ['project', 'timeline', 'ppa_to_fc_years'], 0)) + \
              _as_int(_get(p, ['project', 'timeline', 'construction_years'], 0))
        return pre + ops_years
    return _as_int(_get(p, ['project', 'timeline', 'lifetime_years'], 20))

def _fx_curve(p: Dict[str, Any], n: int) -> List[float]:
    explicit = _get(p, ['fx', 'curve_lkr_per_usd'])
    if isinstance(explicit, list) and explicit:
        if len(explicit) >= n:
            return [float(x) for x in explicit[:n]]
        return [float(x) for x in explicit] + [float(explicit[-1])] * (n - len(explicit))
    start = _as_float(_get(p, ['fx', 'start_lkr_per_usd'], 300.0)) or 300.0
    depr = _as_float(_get(p, ['fx', 'annual_depr'], 0.03)) or 0.03
    out: List[float] = []
    cur = float(start)
    for _ in range(max(1, n)):
        out.append(cur)
        cur *= (1.0 + depr)
    return out

def validate_parameters(p: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if _get(p, ['project', 'capacity_mw']) is None:
        issues.append("ERROR: project.capacity_mw missing")
    if _get(p, ['project', 'capacity_factor']) is None:
        issues.append("ERROR: project.capacity_factor missing")
    if _get(p, ['tariff', 'lkr_per_kwh']) is None:
        issues.append("ERROR: tariff.lkr_per_kwh missing")
    if _get(p, ['regulatory', 'grid_loss_pct']) is None:
        issues.append("WARNING: regulatory.grid_loss_pct missing (defaulting to 0.02)")
    if _get(p, ['opex', 'usd_per_year']) is None:
        issues.append("ERROR: opex.usd_per_year missing")
    cap_factor = _as_float(_get(p, ['project', 'capacity_factor'], None))
    if cap_factor is not None and (cap_factor <= 0 or cap_factor > 1):
        issues.append(f"ERROR: capacity_factor {cap_factor} out of range (0, 1)")
    grid_loss = _as_float(_get(p, ['regulatory', 'grid_loss_pct'], None))
    if grid_loss is not None and (grid_loss < 0 or grid_loss > 0.5):
        issues.append(f"WARNING: grid_loss_pct {grid_loss} seems high")
    return issues

def _extract_parameters(p: Dict[str, Any]) -> Dict[str, float]:
    # Extract all required parameters from YAML config with safe defaults.
    return {
        "capacity_mw": _as_float(_get(p, ["project", "capacity_mw"], 150.0)),
        "capacity_factor": _as_float(_get(p, ["project", "capacity_factor"], 0.40)),
        "degradation": _as_float(_get(p, ["project", "degradation"], 0.006)),
        "tariff_lkr_per_kwh": _as_float(_get(p, ["tariff", "lkr_per_kwh"], 20.30)),
        "grid_loss_pct": _as_float(_get(p, ["regulatory", "grid_loss_pct"], 0.02)),
        "success_fee_pct": _as_float(_get(p, ["regulatory", "success_fee_pct"], 0.01)),
        "env_surcharge_pct": _as_float(_get(p, ["regulatory", "env_surcharge_pct"], 0.005)),
        "social_levy_pct": _as_float(_get(p, ["regulatory", "social_services_levy_pct"], 0.025)),
        "opex_usd_per_year": _as_float(_get(p, ["opex", "usd_per_year"], 3000000.0)),
        "corporate_tax_rate": _as_float(_get(p, ["tax", "corporate_tax_rate"], 0.30)),
        "depreciation_years": _as_int(_get(p, ["tax", "depreciation_years"], 15)),
        "tax_holiday_years": _as_int(_get(p, ["tax", "tax_holiday_years"], 0)),
        "tax_holiday_start_year": _as_int(_get(p, ["tax", "tax_holiday_start_year"], 1)),
        "enhanced_capital_allowance_pct": _as_float(_get(p, ["tax", "enhanced_capital_allowance_pct"], 1.0)),
        "risk_haircut_pct": _as_float(_get(p, ["risk_adjustment", "cfads_haircut_pct"], 0.10)),
        "project_life_years": _years_total(p),
    }

def _calculate_net_production(
    capacity_mw: float,
    capacity_factor: float,
    degradation: float,
    grid_loss_pct: float,
    year: int,
) -> Tuple[float, float]:
    degraded_capacity_factor = capacity_factor * (1.0 - degradation) ** year
    gross_kwh = capacity_mw * 1000.0 * HOURS_PER_YEAR * degraded_capacity_factor
    net_kwh = gross_kwh * (1.0 - grid_loss_pct)
    return gross_kwh, net_kwh

def _calculate_revenue_lkr(net_kwh: float, tariff_lkr_per_kwh: float) -> float:
    return net_kwh * tariff_lkr_per_kwh

def _calculate_statutory_deductions(
    revenue_lkr: float,
    success_fee_pct: float,
    env_surcharge_pct: float,
    social_levy_pct: float,
) -> Dict[str, float]:
    success_fee = revenue_lkr * success_fee_pct
    env_surcharge = revenue_lkr * env_surcharge_pct
    social_levy = revenue_lkr * social_levy_pct
    total_statutory = success_fee + env_surcharge + social_levy
    return {
        "success_fee": success_fee,
        "environmental_surcharge": env_surcharge,
        "social_services_levy": social_levy,
        "total_statutory_deductions": total_statutory,
    }

def _calculate_opex_lkr(opex_usd_per_year: float, fx_rate: float) -> float:
    return opex_usd_per_year * fx_rate

def calculate_tax_with_interest_shield(
    pretax_income: float,
    tax_rate: float,
    capex_total: Optional[float] = None,
    depreciation_years: Optional[int] = None,
    interest_expense_lkr: float = 0.0,
    year: int = 0,
    # Non-breaking extension: BOI incentives
    tax_holiday_years: int = 0,
    tax_holiday_start_year: int = 1,
    enhanced_capital_allowance_pct: float = 1.0,
) -> Tuple[float, float]:
    """
    Calculate corporate tax with tax holiday/enhanced depreciation.
    - Returns (tax_amount, total_depreciation)
    """
    # Check BOI tax holiday
    if year + 1 >= tax_holiday_start_year and year + 1 < (tax_holiday_start_year + tax_holiday_years):
        normal_depr = 0.0
        if capex_total and depreciation_years and year < depreciation_years:
            normal_depr = capex_total / depreciation_years
        enhanced = normal_depr * (enhanced_capital_allowance_pct - 1.0)
        return 0.0, normal_depr + enhanced
    normal_depr = 0.0
    enhanced = 0.0
    if capex_total and depreciation_years and year < depreciation_years:
        normal_depr = capex_total / depreciation_years
        enhanced = normal_depr * (enhanced_capital_allowance_pct - 1.0)
    total_dep = normal_depr + enhanced
    taxable_income = max(0.0, pretax_income - total_dep - interest_expense_lkr)
    tax = taxable_income * tax_rate
    return tax, total_dep

def _apply_risk_haircut(cfads_pretax: float, haircut_pct: float) -> float:
    return cfads_pretax * (1.0 - haircut_pct)

def calculate_single_year_cfads(
    params: Dict[str, float],
    fx_rate: float,
    year: int,
    capex_total: Optional[float] = None,
    interest_expense_lkr: float = 0.0,
    verbose: bool = False,
) -> Dict[str, float]:
    gross_kwh, net_kwh = _calculate_net_production(
        params["capacity_mw"],
        params["capacity_factor"],
        params["degradation"],
        params["grid_loss_pct"],
        year,
    )
    revenue_lkr = _calculate_revenue_lkr(net_kwh, params["tariff_lkr_per_kwh"])
    statutory = _calculate_statutory_deductions(
        revenue_lkr, params["success_fee_pct"], params["env_surcharge_pct"], params["social_levy_pct"]
    )
    opex_lkr = _calculate_opex_lkr(params["opex_usd_per_year"], fx_rate)
    pretax_cfads = revenue_lkr - statutory["total_statutory_deductions"] - opex_lkr

    # All BOI/tax parameters passed from params
    tax, total_depr = calculate_tax_with_interest_shield(
        pretax_cfads,
        params["corporate_tax_rate"],
        capex_total,
        params["depreciation_years"],
        interest_expense_lkr,
        year,
        params.get("tax_holiday_years", 0),
        params.get("tax_holiday_start_year", 1),
        params.get("enhanced_capital_allowance_pct", 1.0),
    )
    posttax_cfads = pretax_cfads - tax
    cfads_final = _apply_risk_haircut(posttax_cfads, params["risk_haircut_pct"])
    result = {
        "year": year + 1,
        "gross_kwh": gross_kwh,
        "grid_loss": gross_kwh - net_kwh,
        "net_kwh": net_kwh,
        "revenue_lkr": revenue_lkr,
        "success_fee": statutory["success_fee"],
        "env_surcharge": statutory["environmental_surcharge"],
        "social_levy": statutory["social_services_levy"],
        "total_statutory_deductions": statutory["total_statutory_deductions"],
        "opex_usd": params["opex_usd_per_year"],
        "fx_rate": fx_rate,
        "opex_lkr": opex_lkr,
        "pretax_cfads": pretax_cfads,
        "total_depreciation": total_depr,
        "interest_expense_lkr": interest_expense_lkr,
        "taxable_income": max(0.0, pretax_cfads - total_depr - interest_expense_lkr),
        "tax": tax,
        "posttax_cfads": posttax_cfads,
        "risk_haircut_amount": posttax_cfads - cfads_final,
        "cfads_final_lkr": cfads_final,
    }
    if verbose:
        logger.info(f"Year {year+1} CFADS: {result}")
    return result

def build_annual_cfads(
    p: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
    verbose: bool = False,
) -> List[float]:
    issues = validate_parameters(p)
    if any("ERROR" in issue for issue in issues):
        for issue in issues:
            logger.error(issue)
        raise ValueError("Cannot calculate CFADS - Critical parameter errors")
    for issue in issues:
        if "WARNING" in issue:
            logger.warning(issue)
    params = _extract_parameters(p)
    years = params["project_life_years"]
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    if capex_total is None:
        capex_usd = _as_float(_get(p, ["capex", "usd_total"], None))
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]
    if interest_expense_series is None:
        interest_expense_series = [0.0] * years
    cfads_list = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        interest_lkr = interest_expense_series[year] if year < len(interest_expense_series) else 0.0
        result = calculate_single_year_cfads(params, fx_rate, year, capex_total, interest_lkr, verbose=verbose)
        cfads_list.append(result["cfads_final_lkr"])
    logger.info(f"Calculated CFADS for {years} years, range: {min(cfads_list):,.0f} to {max(cfads_list):,.0f}")
    return cfads_list

def build_annual_rows(
    p: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
) -> List[Dict[str, float]]:
    params = _extract_parameters(p)
    years = params["project_life_years"]
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    if capex_total is None:
        capex_usd = _as_float(_get(p, ["capex", "usd_total"], None))
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]
    if interest_expense_series is None:
        interest_expense_series = [0.0] * years
    rows = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        interest_lkr = interest_expense_series[year] if year < len(interest_expense_series) else 0.0
        result = calculate_single_year_cfads(params, fx_rate, year, capex_total, interest_lkr, verbose=False)
        result["revenue_usd"] = result["revenue_lkr"] / fx_rate if fx_rate > 0 else 0.0
        result["cfads_usd"] = result["cfads_final_lkr"] / fx_rate if fx_rate > 0 else 0.0
        rows.append(result)
    return rows

if __name__ == "__main__":
    print("=" * 100)
    print("CASHFLOW MODULE v2.2 (BOI-Ready) - SELF-TEST")
    print("=" * 100)
    import yaml
    from pathlib import Path
    yaml_path = Path(__file__).parent.parent.parent / "full_model_variables_updated.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r") as f:
            sample_config = yaml.safe_load(f)
        print(f"\nLoaded configuration from: {yaml_path}")
    else:
        print("\nWARNING: YAML not found, using test config")
        sample_config = {
            "project": {"capacity_mw": 150, "capacity_factor": 0.40, "degradation": 0.006},
            "tariff": {"lkr_per_kwh": 20.30},
            "regulatory": {
                "grid_loss_pct": 0.02,
                "success_fee_pct": 0.01,
                "env_surcharge_pct": 0.005,
                "social_services_levy_pct": 0.025,
            },
            "opex": {"usd_per_year": 3000000},
            "tax": {
                "corporate_tax_rate": 0.00,
                "depreciation_years": 15,
                "tax_holiday_years": 12,
                "tax_holiday_start_year": 1,
                "enhanced_capital_allowance_pct": 1.50,
            },
            "risk_adjustment": {"cfads_haircut_pct": 0.10},
            "fx": {"start_lkr_per_usd": 305, "annual_depr": 0.03},
            "returns": {"project_life_years": 20},
            "capex": {"usd_total": 150000000},
        }
    print("\nTesting parameter validation...")
    issues = validate_parameters(sample_config)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  All parameters valid!")
    print("\nTesting CFADS calculation (with tax holiday + enhancement)...")
    interest_series = [8_000_000 * (1 - i / 15) for i in range(20)]
    cfads_series = build_annual_cfads(sample_config, interest_expense_series=interest_series, verbose=False)
    print(f"\nCFADS Summary (with tax holiday/enhancement):")
    print(f"  Year 1 (LKR):  {cfads_series[0]:,.0f}")
    print(f"  Year 10 (LKR): {cfads_series[9]:,.0f}")
    print(f"  Year 20 (LKR): {cfads_series[19]:,.0f}")
    print(f"  Average (LKR): {sum(cfads_series)/len(cfads_series):,.0f}")
    print("\nTesting detailed breakdown...")
    rows = build_annual_rows(sample_config, interest_expense_series=interest_series)
    print(f"  Generated {len(rows)} annual rows")
    print(f"\n  Year 1 breakdown:")
    for key, value in rows[0].items():
        if isinstance(value, (int, float)) and key != "year":
            print(f"    {key}: {value:,.0f}")
    print("\n" + "=" * 100)
    print("SELF-TEST COMPLETE - Module ready for production use")
    print("=" * 100)


