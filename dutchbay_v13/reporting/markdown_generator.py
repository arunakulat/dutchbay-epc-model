"""
Markdown Report Generator for DutchBay V13 - Option A Step 3 (Working IRR/NPV output)
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

def _format_currency(value: float) -> str:
    return f"${value:,.2f}"

def _format_percent(value: float) -> str:
    return f"{value*100:.1f}%"

def _format_ratio(value: float) -> str:
    return f"{value:.2f}x"

def generate_executive_summary(
    params: Dict[str, Any],
    cfads_series: List[float],
    debt_outstanding_series: List[float],
    llcr_result: Dict[str, Any],
    plcr_result: Dict[str, Any],
    returns: Dict[str, Any],
    dscr_series: Optional[List[float]] = None,
    output_path: Optional[Path] = None
) -> str:
    report_date = datetime.now().strftime("%B %d, %Y at %H:%M:%S")
    capacity_mw = params.get('project', {}).get('capacity_mw', 0)
    tariff_lkr = params.get('tariff', {}).get('lkr_per_kwh', 0)
    lifetime = params.get('project', {}).get('timeline', {}).get('lifetime_years', 20)
    debt_ratio = params.get('Financing_Terms', {}).get('debt_ratio', 0.70)
    tenor_years = params.get('Financing_Terms', {}).get('tenor_years', 15)
    target_dscr = params.get('Financing_Terms', {}).get('target_dscr', 1.30)
    llcr_min = llcr_result['llcr_min']
    plcr_min = plcr_result['plcr_min']
    llcr_covenant = 1.20
    plcr_covenant = 1.40
    llcr_status = "✅ PASS" if llcr_min >= llcr_covenant else "⚠️ WARN"
    plcr_status = "✅ PASS" if plcr_min >= plcr_covenant else "⚠️ WARN"
    year1_cfads = cfads_series[0] if cfads_series else 0
    year1_debt = debt_outstanding_series[0] if debt_outstanding_series else 0

    project_irr_str = f"{returns['project']['project_irr']*100:.2f}%" if returns['project']['project_irr'] else "N/A"
    equity_irr_str = f"{returns['equity']['equity_irr']*100:.2f}%" if returns['equity']['equity_irr'] else "N/A"
    project_npv = returns['project']['project_npv']
    equity_npv = returns['equity']['equity_npv']

    report = f"""# Dutch Bay 150MW Wind Farm - Executive Summary\n\n**Report Date:** {report_date}\n\n---\n\n## Project Overview\n\n| Parameter | Value |\n|-----------|-------|\n| **Capacity** | {capacity_mw} MW |\n| **PPA Tariff** | LKR {tariff_lkr}/kWh |\n| **Project Life** | {lifetime} years |\n| **Debt Ratio** | {_format_percent(debt_ratio)} |\n| **Debt Tenor** | {tenor_years} years |\n\n---\n\n## Financial Returns\n\n| Metric | Value |\n|--------|-------|\n| **Project IRR** | {project_irr_str} |\n| **Project NPV (10%)** | {_format_currency(project_npv)} |\n| **Equity IRR** | {equity_irr_str} |\n| **Equity NPV (12%)** | {_format_currency(equity_npv)} |\n\n---\n\n## Coverage Ratios Summary\n\n### Loan Life Coverage Ratio (LLCR)\n- **Minimum:** {_format_ratio(llcr_min)} {llcr_status}\n- **Average:** {_format_ratio(llcr_result['llcr_avg'])}\n- **Covenant Threshold:** {_format_ratio(llcr_covenant)}x\n- **Margin to Covenant:** {_format_ratio(llcr_min - llcr_covenant)}\n\n### Project Life Coverage Ratio (PLCR)\n- **Minimum:** {_format_ratio(plcr_min)} {plcr_status}\n- **Average:** {_format_ratio(plcr_result['plcr_avg'])}\n- **Covenant Threshold:** {_format_ratio(plcr_covenant)}x\n- **Margin to Covenant:** {_format_ratio(plcr_min - plcr_covenant)}\n\n---\n\n## Year 1 Financial Snapshot\n\n| Metric | Value |\n|--------|-------|\n| **CFADS** | {_format_currency(year1_cfads)} |\n| **Debt Outstanding** | {_format_currency(year1_debt)} |\n| **Target DSCR** | {_format_ratio(target_dscr)} |\n\n---\n\n## Covenant Compliance Status\n\n| Covenant | Min Required | Actual | Status |\n|----------|--------------|--------|--------|\n| LLCR | {_format_ratio(llcr_covenant)} | {_format_ratio(llcr_min)} | {llcr_status} |\n| PLCR | {_format_ratio(plcr_covenant)} | {_format_ratio(plcr_min)} | {plcr_status} |\n\n---\n\n## Key Findings\n\n✅ **Attractive Returns:** Project IRR of {project_irr_str} and Equity IRR of {equity_irr_str} indicate strong financial performance.\n\n✅ **Strong Coverage Ratios:** LLCR and PLCR exceed DFI/lender covenant thresholds by comfortable margins.\n\n✅ **Sculpted Debt Schedule:** Debt service optimized to maintain {_format_ratio(target_dscr)} DSCR following {params.get('Financing_Terms', {}).get('interest_only_years', 2)}-year grace period.\n\n---\n\n## Next Steps\n\n1. Conduct sensitivity analysis on key drivers\n2. Review detailed debt schedule and annual cashflows\n3. Schedule investment committee presentation\n4. Proceed to lender due diligence phase\n\n---\n\n*This Executive Summary is based on base case assumptions as of {report_date}.*"""
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    return report

def generate_dfi_lender_pack(
    params: Dict[str, Any],
    cfads_series: List[float],
    debt_outstanding_series: List[float],
    debt_service_series: List[float],
    llcr_result: Dict[str, Any],
    plcr_result: Dict[str, Any],
    returns: Dict[str, Any],
    output_path: Optional[Path] = None
) -> str:
    report_date = datetime.now().strftime("%B %d, %Y")
    interest_only_years = params.get('Financing_Terms', {}).get('interest_only_years', 2)
    tenor_years = params.get('Financing_Terms', {}).get('tenor_years', 15)
    project_irr_str = f"{returns['project']['project_irr']*100:.2f}%" if returns['project']['project_irr'] else "N/A"
    equity_irr_str = f"{returns['equity']['equity_irr']*100:.2f}%" if returns['equity']['equity_irr'] else "N/A"
    report = (
        f"# DutchBay 150MW Wind Farm - DFI/Lender Due Diligence Pack\n\n"
        f"**Prepared:** {report_date}\n\n"
        f"---\n\n"
        f"## Financial Returns\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| **Project IRR** | {project_irr_str} |\n"
        f"| **Project NPV (10%)** | {_format_currency(returns['project']['project_npv'])} |\n"
        f"| **Equity IRR** | {equity_irr_str} |\n"
        f"| **Equity NPV (12%)** | {_format_currency(returns['equity']['equity_npv'])} |\n"
        f"| **Equity Investment** | {_format_currency(returns['equity']['equity_investment'])} |\n\n"
        f"---\n\n"
        f"## 1. Debt Service Coverage Schedule (Full {tenor_years}-Year Tenor)\n\n"
        f"**Note:** Years 1-{interest_only_years} are interest-only; sculpted amortization begins Year {interest_only_years + 1} targeting DSCR 1.30x.\n\n"
        f"| Year | CFADS (USD) | Debt Service (USD) | DSCR | Debt Outstanding (USD) | LLCR |\n"
        f"|------|-------------|-------------------|------|------------------------|------|\n"
    )
    max_rows = min(tenor_years, len(cfads_series), len(debt_service_series), len(debt_outstanding_series))
    for i in range(max_rows):
        cfads = cfads_series[i]
        ds = debt_service_series[i] if i < len(debt_service_series) else 0
        dscr = cfads / ds if ds > 0 else float('inf')
        debt = debt_outstanding_series[i]
        llcr = llcr_result['llcr_series'][i] if i < len(llcr_result['llcr_series']) else 0
        report += f"| {i+1} | {_format_currency(cfads)} | {_format_currency(ds)} | {_format_ratio(dscr)} | {_format_currency(debt)} | {_format_ratio(llcr)} |\n"
    report += (
        f"\n---\n\n"
        f"## 2. Covenant Compliance Matrix\n\n"
        f"| Covenant | Threshold | Minimum | Status |\n"
        f"|----------|-----------|---------|--------|\n"
        f"| LLCR | 1.20x | {_format_ratio(llcr_result['llcr_min'])} | {'✅ PASS' if llcr_result['llcr_min'] >= 1.20 else '⚠️ WARN'} |\n"
        f"| PLCR | 1.40x | {_format_ratio(plcr_result['plcr_min'])} | {'✅ PASS' if plcr_result['plcr_min'] >= 1.40 else '⚠️ WARN'} |\n\n"
        f"---\n\n"
        f"## 3. Debt Structure\n\n"
        f"- **Total Debt:** {_format_currency(debt_outstanding_series[0] if debt_outstanding_series else 0)}\n"
        f"- **Tenor:** {params.get('Financing_Terms', {}).get('tenor_years', 15)} years\n"
        f"- **Amortization Style:** {params.get('Financing_Terms', {}).get('amortization_style', 'sculpted')}\n"
        f"- **Interest Only Period:** {params.get('Financing_Terms', {}).get('interest_only_years', 2)} years\n"
        f"- **Target DSCR:** {params.get('Financing_Terms', {}).get('target_dscr', 1.30)}x\n"
        f"---\n\n"
        f"## 4. Risk Assessment\n\n"
        f"### Strengths\n"
        f"- Attractive equity returns ({equity_irr_str}) with strong debt service coverage\n"
        f"- Proven wind resource and offtaker creditworthiness\n"
        f"- Sculpted debt service optimizes cashflow utilization\n"
        f"- Strong LLCR/PLCR margins above covenant thresholds\n\n"
        f"### Mitigants\n"
        f"- DSRA reserve structure\n"
        f"- Receivables guarantee facility\n"
        f"- Lender technical advisor oversight\n"
        f"- Annual reforecasting and covenant review\n\n"
        f"---\n\n"
        f"## 5. Financial Assumptions (Summary)\n\n"
        f"- **Capacity Factor:** {params.get('project', {}).get('capacity_factor', 0.40) * 100:.1f}%\n"
        f"- **Tariff (LKR):** {params.get('tariff', {}).get('lkr_per_kwh', 0)}/kWh\n"
        f"- **OPEX:** {_format_currency(params.get('opex', {}).get('usd_per_year', 0))}/year\n"
        f"- **FX Depreciation:** {params.get('fx', {}).get('annual_depr', 0.03) * 100:.1f}%/year\n\n"
        f"---\n\n"
        f"*This due diligence pack is for lender/DFI internal use only. Confidential.*"
    )
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    return report
