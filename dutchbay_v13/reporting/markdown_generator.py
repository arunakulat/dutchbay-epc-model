"""
Markdown Report Generator for DutchBay V13 - Integrated Full Coverage (LLCR/PLCR, DSCR, IRR)
Version: Nov 2025, Option A Step 5 (All Years, Fully Parameterized)

This generator displays all standard DFI/commercial lender metrics (LLCR, PLCR, DSCR) 
and full post-tax, post-regulatory, post-risk returns across all project years.
All values are parameterized from YAML config.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dutchbay_v13.finance.metrics import calculate_llcr, calculate_plcr

def _format_currency(value: float) -> str:
    return f"${value:,.2f}"

def _format_percent(value: float) -> str:
    return f"{value*100:.1f}%"

def _format_ratio(value: float) -> str:
    return f"{value:.2f}x"

def generate_executive_summary(
    params: Dict[str, Any],
    returns: Dict[str, Any],
    dscr_min: float,
    llcr_summary: Dict[str, Any],
    plcr_summary: Dict[str, Any],
    output_path: Optional[Path] = None
) -> str:
    """Generate comprehensive Executive Summary with full year financials."""
    report_date = datetime.now().strftime("%B %d, %Y at %H:%M:%S")
    
    # Parameterize all report metadata from YAML
    project_name = params.get('project', {}).get('name', 'Wind Farm Project')
    capacity_mw = params.get('project', {}).get('capacity_mw', 0)
    tariff_lkr = params.get('tariff', {}).get('lkr_per_kwh', 0)
    lifetime = params.get('returns', {}).get('project_life_years', 20)
    debt_ratio = params.get('Financing_Terms', {}).get('debt_ratio', 0.70)
    tenor_years = params.get('Financing_Terms', {}).get('tenor_years', 15)
    project_discount_rate = params.get('returns', {}).get('project_discount_rate', 0.10)
    equity_discount_rate = params.get('returns', {}).get('equity_discount_rate', 0.12)
    
    equity = returns['equity']
    project = returns['project']
    ds_list = returns['debt_service']
    cfads_list = returns['cfads']
    tax_list = returns['tax']
    cfads_gross = returns['cfads_gross']

    report = f"""# {project_name} - Executive Summary

**Report Date:** {report_date}

---

## Project Overview

| Parameter | Value |
|-----------|-------|
| **Capacity** | {capacity_mw} MW |
| **PPA Tariff** | LKR {tariff_lkr}/kWh |
| **Project Life** | {lifetime} years |
| **Debt Ratio** | {_format_percent(debt_ratio)} |
| **Debt Tenor** | {tenor_years} years |
| **Equity Investment** | {_format_currency(equity['equity_investment'])} |

---

## Financial Returns

| Metric | Value |
|--------|-------|
| **Project IRR** | {project['project_irr']*100:.2f}% |
| **Project NPV ({_format_percent(project_discount_rate)})** | {_format_currency(project['project_npv'])} |
| **Equity IRR** | {equity['equity_irr']*100:.2f}% |
| **Equity NPV ({_format_percent(equity_discount_rate)})** | {_format_currency(equity['equity_npv'])} |

---

## Coverage Ratios (Key Years)

| Year | DSCR | LLCR | PLCR |
|------|------|------|------|
"""
    # Print out up to 5 years as a preview
    for y in range(min(5, len(ds_list))):
        dscr = cfads_list[y] / ds_list[y] if ds_list[y] > 1e-7 else 0.0
        llcr = llcr_summary['llcr_series'][y] if y < len(llcr_summary['llcr_series']) else 0.0
        plcr = plcr_summary['plcr_series'][y] if y < len(plcr_summary['plcr_series']) else 0.0
        report += f"| {y+1} | {_format_ratio(dscr)} | {_format_ratio(llcr)} | {_format_ratio(plcr)} |\n"
    
    report += f"""
---

## Coverage Summary

- **Minimum DSCR:** {_format_ratio(dscr_min)}
- **Minimum LLCR:** {_format_ratio(llcr_summary['llcr_min'])} 
- **Minimum PLCR:** {_format_ratio(plcr_summary['plcr_min'])} 

---

## All Years: Financials w/ Net Tax & Regulatory

| Year | CFADS (Gross) | Net CFADS | Debt Service | Taxes |
|------|---------------|-----------|--------------|-------|
"""
    for i in range(len(ds_list)):
        y = i + 1
        report += (
            f"| {y:2d} | {_format_currency(cfads_gross[i])} | "
            f"{_format_currency(cfads_list[i])} | "
            f"{_format_currency(ds_list[i])} | {_format_currency(tax_list[i])} |\n"
        )
    
    report += """
---

## Key Findings

All financial metrics reflect actual DSCR/LLCR/PLCR, post-tax and post-levy. Data spans complete project lifecycle including construction, grace period, and all operating years.

---

"""
    report += f"*This Executive Summary is based on fully netted base case as of {report_date}.*"
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    return report


def generate_dfi_lender_pack(
    params: Dict[str, Any],
    returns: Dict[str, Any],
    dscr_min: float,
    llcr_summary: Dict[str, Any],
    plcr_summary: Dict[str, Any],
    output_path: Optional[Path] = None
) -> str:
    """Generate comprehensive DFI/Lender Due Diligence Pack with full year financials and coverage."""
    report_date = datetime.now().strftime("%B %d, %Y")
    
    # Parameterize all report metadata from YAML
    project_name = params.get('project', {}).get('name', 'Wind Farm Project')
    project_discount_rate = params.get('returns', {}).get('project_discount_rate', 0.10)
    equity_discount_rate = params.get('returns', {}).get('equity_discount_rate', 0.12)
    
    equity = returns['equity']
    project = returns['project']
    ds_list = returns['debt_service']
    cfads_list = returns['cfads']
    tax_list = returns['tax']
    cfads_gross = returns['cfads_gross']
    tenor_years = params.get('Financing_Terms', {}).get('tenor_years', 15)
    
    report = f"""# {project_name} - DFI/Lender Due Diligence Pack

**Prepared:** {report_date}

---

## Financial Returns

| Metric | Value |
|--------|-------|
| **Project IRR** | {project['project_irr']*100:.2f}% |
| **Project NPV ({_format_percent(project_discount_rate)})** | {_format_currency(project['project_npv'])} |
| **Equity IRR** | {equity['equity_irr']*100:.2f}% |
| **Equity NPV ({_format_percent(equity_discount_rate)})** | {_format_currency(equity['equity_npv'])} |
| **Equity Investment** | {_format_currency(equity['equity_investment'])} |

---

## Full Term Coverage Ratios

| Year | DSCR | LLCR | PLCR |
|------|------|------|------|
"""
    for y in range(min(tenor_years, len(ds_list))):
        dscr = cfads_list[y] / ds_list[y] if ds_list[y] > 1e-7 else 0.0
        llcr = llcr_summary['llcr_series'][y] if y < len(llcr_summary['llcr_series']) else 0.0
        plcr = plcr_summary['plcr_series'][y] if y < len(plcr_summary['plcr_series']) else 0.0
        report += f"| {y+1} | {_format_ratio(dscr)} | {_format_ratio(llcr)} | {_format_ratio(plcr)} |\n"
    
    report += f"""
---

## Minimum/Mean Coverage

- **Minimum DSCR:** {_format_ratio(dscr_min)}
- **Minimum LLCR:** {_format_ratio(llcr_summary['llcr_min'])} 
- **LLCR Avg:** {_format_ratio(llcr_summary['llcr_avg'])}
- **Minimum PLCR:** {_format_ratio(plcr_summary['plcr_min'])} 
- **PLCR Avg:** {_format_ratio(plcr_summary['plcr_avg'])}

---

## Financials w/ Net Tax & Regulatory (All Project Years)

| Year | Gross CFADS | Net CFADS | Debt Service | Taxes |
|------|-------------|-----------|--------------|-------|
"""
    for i in range(len(ds_list)):
        y = i + 1
        report += (
            f"| {y:2d} | {_format_currency(cfads_gross[i])} | "
            f"{_format_currency(cfads_list[i])} | "
            f"{_format_currency(ds_list[i])} | {_format_currency(tax_list[i])} |\n"
        )
    
    report += """
---

## Notes

All returns and coverage numbers reflect LLCR, PLCR covenants, and post-tax, levy-adjusted flows.
Debt schedule and coverage ratios aligned to actual net after-tax cash generation.
Full project timeline includes construction, grace, and all operating years through project end.

---

*This due diligence pack is for lender/DFI internal use only. Confidential.*
"""
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    return report
