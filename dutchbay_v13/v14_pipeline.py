from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from dutchbay_v13.params import load_params

# V14 engine layer
from src.debt_v14 import DebtProfile, build_debt_schedule_with_grace
from src.cashflow_v14 import TimelineConfig, build_timeline
from src.tax_calculator_v14 import (
    TaxScenario,
    build_depreciation_schedule,
    calculate_tax_series,
)
from src.metrics_v14 import (
    calculate_dscr_series,
    calculate_llcr,
    calculate_plcr,
)
from src.equity_analysis_v14 import generate_comprehensive_equity_table_v14
from src.scenario_manager_v14 import ScenarioDefinition, apply_scenario


@dataclass
class V14Config:
    """
    Thin, typed view over the raw YAML parameters needed by the v14 engine.
    All values are in LKR once constructed.
    """
    years: List[int]
    construction_years: int
    operations_years: int
    tariff_lkr_per_kwh: float
    capacity_mw: float
    capacity_factor: float
    annual_opex_lkr: float
    capex_total_lkr: float
    debt_ratio: float
    interest_rate_nominal: float
    tenor_years: int
    grace_years: int
    target_dscr: float
    llcr_discount_rate: float
    plcr_discount_rate: float
    corporate_tax_rate: float
    tax_holiday_years: int
    tax_holiday_start_year: int
    depreciation_method: str
    depreciation_years: int
    accelerated_factor: float
    usd_equity_pct: float
    lkr_equity_pct: float
    equity_required_return: float
    fx_start_lkr_per_usd: float
    fx_annual_depr: float


def _hours_per_year() -> float:
    # Simple constant; if needed we can make this configurable later.
    return 8760.0


def _extract_base_config(params: Dict[str, Any]) -> V14Config:
    project = params.get("project", {})
    timeline = params.get("timeline", {})
    tariff = params.get("tariff", {})
    fx = params.get("fx", params.get("FX", {}))
    capex = params.get("capex", params.get("Capex", {}))
    opex = params.get("opex", params.get("Opex", {}))
    tax = params.get("tax", params.get("Tax", {}))
    fin = params.get("Financing_Terms", params.get("FinancingTerms", {}))
    metrics = params.get("metrics", params.get("Metrics", {}))
    equity = params.get("Equity", {})

    construction_years = int(timeline.get("construction_years", 2))
    operations_years = int(
        timeline.get("ops_years", timeline.get("lifetime_years", 20))
    )
    include_cod_year = True
    tl_cfg = TimelineConfig(
        construction_years=construction_years,
        operations_years=operations_years,
        include_cod_year=include_cod_year,
    )
    years = build_timeline(tl_cfg)

    # FX
    fx_start = float(
        fx.get("start_lkr_per_usd", fx.get("initial_rate_lkr_usd", 300.0))
    )
    fx_depr = float(
        fx.get("annual_depr", fx.get("annual_depreciation", 0.03))
    )

    # Capex & opex
    capex_usd_total = float(capex.get("usd_total", capex.get("USD_total", 0.0)))
    capex_total_lkr = capex_usd_total * fx_start

    opex_usd_per_year = float(
        opex.get("usd_per_year", opex.get("USD_per_year", 0.0))
    )
    annual_opex_lkr = opex_usd_per_year * fx_start

    # Project / tariff
    capacity_mw = float(project.get("capacity_mw", 0.0))
    capacity_factor = float(project.get("capacity_factor", 0.0))
    tariff_lkr_per_kwh = float(
        tariff.get("lkr_per_kwh", tariff.get("LKR_per_kwh", 0.0))
    )

    # Financing
    debt_ratio = float(fin.get("debt_ratio", 0.7))
    interest_rate_nominal = float(
        fin.get(
            "interest_rate_nominal",
            fin.get("rates", {}).get("usd_nominal", 0.08),
        )
    )
    tenor_years = int(fin.get("tenor_years", 15))
    grace_years = int(fin.get("interest_only_years", fin.get("grace_years", 0)))
    target_dscr = float(fin.get("target_dscr", 1.3))

    # Metrics
    llcr_discount_rate = float(metrics.get("llcr_discount_rate", 0.1))
    plcr_discount_rate = float(metrics.get("plcr_discount_rate", 0.1))

    # Tax
    corporate_tax_rate = float(
        tax.get("corporate_tax_rate", tax.get("Corporate_Tax_Rate", 0.0))
    )
    tax_holiday_years = int(tax.get("tax_holiday_years", 0))
    tax_holiday_start_year = int(tax.get("tax_holiday_start_year", 1))
    depreciation_method = str(tax.get("depreciation_method", "straight_line"))
    depreciation_years = int(tax.get("depreciation_years", 15))
    accelerated_factor = float(
        tax.get("enhanced_capital_allowance_pct", 1.0)
    )

    # Equity
    usd_equity_pct = float(equity.get("usd_equity_pct", 1.0))
    lkr_equity_pct = float(equity.get("lkr_equity_pct", 0.0))
    equity_required_return = float(equity.get("required_return", 0.12))

    return V14Config(
        years=years,
        construction_years=construction_years,
        operations_years=operations_years,
        tariff_lkr_per_kwh=tariff_lkr_per_kwh,
        capacity_mw=capacity_mw,
        capacity_factor=capacity_factor,
        annual_opex_lkr=annual_opex_lkr,
        capex_total_lkr=capex_total_lkr,
        debt_ratio=debt_ratio,
        interest_rate_nominal=interest_rate_nominal,
        tenor_years=tenor_years,
        grace_years=grace_years,
        target_dscr=target_dscr,
        llcr_discount_rate=llcr_discount_rate,
        plcr_discount_rate=plcr_discount_rate,
        corporate_tax_rate=corporate_tax_rate,
        tax_holiday_years=tax_holiday_years,
        tax_holiday_start_year=tax_holiday_start_year,
        depreciation_method=depreciation_method,
        depreciation_years=depreciation_years,
        accelerated_factor=accelerated_factor,
        usd_equity_pct=usd_equity_pct,
        lkr_equity_pct=lkr_equity_pct,
        equity_required_return=equity_required_return,
        fx_start_lkr_per_usd=fx_start,
        fx_annual_depr=fx_depr,
    )


def _apply_scenario_if_any(
    base_params: Dict[str, Any],
    scenario_name: Optional[str],
) -> Tuple[Dict[str, Any], Optional[str]]:
    if not scenario_name:
        return base_params, None

    scenarios = base_params.get("scenarios", {})
    overlay = scenarios.get(scenario_name)
    if overlay is None:
        # Unknown scenario; behave as base case
        return base_params, None

    scen = ScenarioDefinition(
        name=scenario_name,
        description=overlay.get("description", ""),
        overlay=overlay,
    )
    merged = apply_scenario(base_params, scen)
    return merged, scenario_name


def _build_fx_curve(cfg: V14Config) -> List[float]:
    """
    Build a simple LKR/USD path across the full timeline.
    We apply the annual depreciation factor only to operational years.
    """
    rates: List[float] = []
    for y in cfg.years:
        if y <= 0:
            rates.append(cfg.fx_start_lkr_per_usd)
        else:
            t = max(0, y)
            rates.append(
                cfg.fx_start_lkr_per_usd * ((1.0 + cfg.fx_annual_depr) ** t)
            )
    return rates


def run_v14_pipeline(
    config: Optional[str] = None,
    *,
    scenario: Optional[str] = None,
    overrides: Optional[Mapping[str, Any]] = None,
    validation_mode: str = "strict",
) -> Dict[str, Any]:
    """
    High-level v14 pipeline:
    - load & optionally overlay scenario YAML
    - map into V14Config
    - run debt, tax, CFADS, DSCR, LLCR, PLCR, and equity table.

    Args:
        config: Optional path to YAML; if None, uses params.load_params() default.
        scenario: Optional scenario name from the YAML 'scenarios' dict.
        overrides: Optional in-memory overrides merged last.
        validation_mode: passed through to params.load_params.

    Returns:
        Dict containing the key results and the raw parameters used.
    """
    if overrides is None:
        params = load_params(config, mode=validation_mode)
    else:
        params = load_params(config, mode=validation_mode, overrides=overrides)

    effective_params, used_scenario = _apply_scenario_if_any(params, scenario)
    cfg = _extract_base_config(effective_params)

    years = cfg.years
    n = len(years)

    # 1. Revenue & opex (in LKR)
    hours = _hours_per_year()
    annual_energy_kwh = cfg.capacity_mw * 1_000.0 * hours * cfg.capacity_factor
    annual_revenue_lkr = annual_energy_kwh * cfg.tariff_lkr_per_kwh

    gross_revenue: List[float] = []
    opex: List[float] = []
    for y in years:
        if y <= 0:
            gross_revenue.append(0.0)
            opex.append(0.0)
        else:
            gross_revenue.append(annual_revenue_lkr)
            opex.append(cfg.annual_opex_lkr)

    # 2. Tax & depreciation (operational years only)
    tax_scenario = TaxScenario(
        corporate_rate=cfg.corporate_tax_rate,
        tax_holiday_years=cfg.tax_holiday_years,
        tax_holiday_start_year=cfg.tax_holiday_start_year,
        depreciation_method=cfg.depreciation_method,
        depreciation_years=cfg.depreciation_years,
        accelerated_factor=cfg.accelerated_factor,
    )

    dep_ops = build_depreciation_schedule(
        asset_value=cfg.capex_total_lkr,
        operations_years=cfg.operations_years,
        scenario=tax_scenario,
    )

    # EBIT for ops years: revenue - opex
    ebit_ops: List[float] = []
    years_ops: List[int] = []
    for y, gr, op in zip(years, gross_revenue, opex):
        if y >= 1:
            years_ops.append(y)
            ebit_ops.append(gr - op)

    tax_ops = calculate_tax_series(
        ebit=ebit_ops,
        depreciation=dep_ops,
        scenario=tax_scenario,
        years=years_ops,
    )

    # Map tax back to full timeline
    tax_full: List[float] = [0.0] * n
    dep_full: List[float] = [0.0] * n
    ops_index = 0
    for i, y in enumerate(years):
        if y >= 1:
            if ops_index < len(tax_ops):
                tax_full[i] = tax_ops[ops_index]
            if ops_index < len(dep_ops):
                dep_full[i] = dep_ops[ops_index]
            ops_index += 1

    # 3. Pre-debt CFADS (approximation: revenue - opex - tax)
    cfads_pre_debt: List[float] = []
    for gr, op, tx in zip(gross_revenue, opex, tax_full):
        cfads_pre_debt.append(gr - op - tx)

    # 4. Debt profile and schedule (using operational CFADS only)
    total_project_lkr = cfg.capex_total_lkr
    total_debt_lkr = total_project_lkr * cfg.debt_ratio

    debt_profile = DebtProfile(
        total_debt=total_debt_lkr,
        annual_interest_rate=cfg.interest_rate_nominal,
        tenor_years=cfg.tenor_years,
        grace_years=cfg.grace_years,
        construction_years=cfg.construction_years,
    )

    cfads_after_cod = [c for y, c in zip(years, cfads_pre_debt) if y >= 1]
    debt_schedule = build_debt_schedule_with_grace(
        profile=debt_profile,
        cfads_after_cod=cfads_after_cod,
        target_dscr=cfg.target_dscr,
    )

    # Align debt service and outstanding debt to full timeline
    debt_service: List[float] = [0.0] * n
    outstanding_debt: List[float] = [0.0] * n
    ops_idx = 0
    for i, y in enumerate(years):
        if y >= 1 and ops_idx < len(debt_schedule["debt_service"]):
            debt_service[i] = debt_schedule["debt_service"][ops_idx]
            outstanding_debt[i] = debt_schedule["closing_balance"][ops_idx]
            ops_idx += 1

    # 5. Coverage ratios
    dscr_series = calculate_dscr_series(
        cfads=cfads_pre_debt,
        debt_service=debt_service,
        years=years,
    )
    llcr = calculate_llcr(
        cfads=cfads_pre_debt,
        outstanding_debt=outstanding_debt,
        discount_rate=cfg.llcr_discount_rate,
        years=years,
    )
    plcr = calculate_plcr(
        cfads=cfads_pre_debt,
        project_discount_rate=cfg.plcr_discount_rate,
        total_debt=total_debt_lkr,
        years=years,
    )

    # 6. Equity table
    equity_commitment_lkr = total_project_lkr * (1.0 - cfg.debt_ratio)
    fx_curve = _build_fx_curve(cfg)

    equity_table = generate_comprehensive_equity_table_v14(
        years=years,
        cfads=cfads_pre_debt,
        tax=tax_full,
        debt_service=debt_service,
        equity_commitment_lkr=equity_commitment_lkr,
        usd_equity_pct=cfg.usd_equity_pct,
        lkr_equity_pct=cfg.lkr_equity_pct,
        usd_fx_rates=fx_curve,
        bank_equivalent_rate=cfg.equity_required_return,
    )

    return {
        "years": years,
        "gross_revenue": gross_revenue,
        "opex": opex,
        "ebit_ops": ebit_ops,
        "depreciation": dep_full,
        "tax": tax_full,
        "cfads_pre_debt": cfads_pre_debt,
        "debt_service": debt_service,
        "outstanding_debt": outstanding_debt,
        "dscr": dscr_series,
        "llcr": llcr,
        "plcr": plcr,
        "equity_table": equity_table,
        "total_debt_lkr": total_debt_lkr,
        "equity_commitment_lkr": equity_commitment_lkr,
        "raw_params": params,
        "scenario_used": used_scenario,
    }


def main() -> None:
    """
    Simple manual entry point:

        python -m dutchbay_v13.v14_pipeline

    Prints a one-line summary of key v14 metrics.
    """
    result = run_v14_pipeline()
    years = result["years"]
    llcr = result["llcr"]
    plcr = result["plcr"]
    dscr = result["dscr"]
    print("V14 pipeline run complete.")
    print(f"Years: {years[0]}..{years[-1]} (n={len(years)})")
    print(f"LLCR: {llcr:.3f}, PLCR: {plcr:.3f}")
    print(f"DSCR (min/avg): {min(dscr):.3f} / {sum(dscr)/len(dscr):.3f}")


if __name__ == "__main__":  # pragma: no cover - manual entry
    main()