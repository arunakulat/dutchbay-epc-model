"""
Markdown Report Generator for DutchBay V13 - DFI/Board/Exec-Grade

Reads post-tax, grid/risk/reg-adjusted cashflows and returns as produced by the enhanced returns/DSCR module,
and produces Markdown for both Executive Summary and DFI/Lender Pack directly from these.

All logic and outputs match the rigor of current returns.py and scenario_runner.py.
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
    returns: Dict[str, Any],
    output_path: Optional[Path] = None
) -> str:
    report_date = datetime.now().strftime("%B %d, %Y at %H:%M:%S")
    capacity_mw = params.get('project', {}).get('capacity_mw', 0)
    tariff_lkr = params.get('tariff', {}).get('lkr_per_kwh', 0)
    lifetime = params.get('returns', {}).get('project_life_years', 20)
    debt_ratio = params.get('Financing_Terms', {}).get('debt_ratio', 0.70)
    tenor_years = params.get('Financing_Terms', {}).get('tenor_years', 15)
    target_dscr = params.get('Financing_Terms', {}).get('target_dscr', 1.30)
    equity = returns['equity']
    project = returns['project']
    # Coverage ratios, DSCR coverage for display
    ds_list = returns['debt_service']
    cfads_list = returns['cfads']
    tax_list = returns['tax']
    cfads_gross = returns['cfads_gross']

    project_irr_str = f"{project['project_irr']*100:.2f}%" if project['project_irr'] else "N/A"
    equity_irr_str = f"{equity['equity_irr']*100:.2f}%" if equity['equity_irr'] else "N/A"
    project_npv = project['project_npv']
    equity_npv = equity['equity_npv']
    equity_investment = equity['equity_investment']

    report = f"""# Dutch Bay 150MW Wind Farm - Executive Summary\n\n**Report Date:** {report_date}\n\n---\n\n## Project Overview\n\n| Parameter | Value |\n|-----------|-------|\n| **Capacity** | {capacity_mw} MW |\n| **PPA Tariff** | LKR {tariff_lkr}/kWh |\n| **Project Life** | {lifetime} years |\n| **Debt Ratio** | {_format_percent(debt_ratio)} |\n| **Debt Tenor** | {tenor_years} years |\n| **Equity Investment** | {_format_currency(equity_investment)} |\n\n---\n\n## Financial Returns\n\n| Metric | Value |\n|--------|-------|\n| **Project IRR** | {project_irr_str} |\n| **Project NPV (10%)** | {_format_currency(project_npv)} |\n| **Equity IRR** | {equity_irr_str} |\n| **Equity NPV (12%)** | {_format_currency(equity_npv)} |\n\n---\n\n## Year 1 / Stress Year Financial Snapshot\n\n| Year | CFADS (Gross) | Net CFADS | Debt Service | Taxes |
|------|---------------|-----------|--------------|-------|
"""
    for i in range(min(5, len(ds_list))):
        y = i + 1
        report += (
            f"| {y:2d} | {_format_currency(cfads_gross[i])} | "
            f"{_format_currency(cfads_list[i])} | "
            f"{_format_currency(ds_list[i])} | {_format_currency(tax_list[i])} |\n"
        )
    report += "\n---\n\n## Key Findings\n\nAll financials are post-tax, after grid loss, regulatory and technical risk, and reflect actual USD revenues under deterministic FX/YAML.\n\n---\n\n*This Executive Summary is based on fully netted base case as of {report_date}.*"
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    return report

def generate_dfi_lender_pack(
    params: Dict[str, Any],
    returns: Dict[str, Any],
    output_path: Optional[Path] = None
) -> str:
    report_date = datetime.now().strftime("%B %d, %Y")
    equity = returns['equity']
    project = returns['project']
    ds_list = returns['debt_service']
    cfads_list = returns['cfads']
    tax_list = returns['tax']
    cfads_gross = returns['cfads_gross']
    # Tenor/financing display
    tenor_years = params.get('Financing_Terms', {}).get('tenor_years', 15)
    interest_only_years = params.get('Financing_Terms', {}).get('interest_only_years', 2)
    report = (
        f"# DutchBay 150MW Wind Farm - DFI/Lender Due Diligence Pack\n\n"
        f"**Prepared:** {report_date}\n\n"
        f"---\n\n"
        f"## Financial Returns\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| **Project IRR** | {project['project_irr']*100:.2f}% |\n"
        f"| **Project NPV (10%)** | {_format_currency(project['project_npv'])} |\n"
        f"| **Equity IRR** | {equity['equity_irr']*100:.2f}% |\n"
        f"| **Equity NPV (12%)** | {_format_currency(equity['equity_npv'])} |\n"
        f"| **Equity Investment** | {_format_currency(equity['equity_investment'])} |\n\n"
        f"---\n\n"
        f"## Debt Service Coverage Schedule (Full {tenor_years}-Year Tenor, Net of Tax/Reg/Risk)\n\n"
        f"| Year | Gross CFADS | Net CFADS | Debt Service | Taxes |\n"
        f"|------|-------------|-----------|--------------|-------|\n"
    )
    for i in range(min(tenor_years, len(ds_list))):
        y = i + 1
        report += (
            f"| {y:2d} | {_format_currency(cfads_gross[i])} | "
            f"{_format_currency(cfads_list[i])} | "
            f"{_format_currency(ds_list[i])} | {_format_currency(tax_list[i])} |\n"
        )
    report += (
        f"\n---\n\n"
        f"## Key Findings\n\n"
        f"All returns and coverage numbers reflect tax, grid loss, technical risk adjustments.\n"
        f"Debt schedule aligned to net after-tax cash generation.\n\n"
        f"---\n\n"
        f"*This due diligence pack is for lender/DFI internal use only. Confidential.*"
    )
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    return report
