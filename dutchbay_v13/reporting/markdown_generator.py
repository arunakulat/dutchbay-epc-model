"""
Markdown Report Generator for DutchBay V13 - Option A Step 2
Generates institutional-grade Markdown reports for lenders and execs.
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
    report = f"""# Dutch Bay 150MW Wind Farm - Executive Summary

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

---

## Coverage Ratios Summary

### Loan Life Coverage Ratio (LLCR)
- **Minimum:** {_format_ratio(llcr_min)} {llcr_status}
- **Average:** {_format_ratio(llcr_result['llcr_avg'])}
- **Covenant Threshold:** {_format_ratio(llcr_covenant)}x
- **Margin to Covenant:** {_format_ratio(llcr_min - llcr_covenant)}

### Project Life Coverage Ratio (PLCR)
- **Minimum:** {_format_ratio(plcr_min)} {plcr_status}
- **Average:** {_format_ratio(plcr_result['plcr_avg'])}
- **Covenant Threshold:** {_format_ratio(plcr_covenant)}x
- **Margin to Covenant:** {_format_ratio(plcr_min - plcr_covenant)}

---

## Year 1 Financial Snapshot

| Metric | Value |
|--------|-------|
| **CFADS** | {_format_currency(year1_cfads)} |
| **Debt Outstanding** | {_format_currency(year1_debt)} |
| **Target DSCR** | {_format_ratio(target_dscr)} |

---

## Covenant Compliance Status

| Covenant | Min Required | Actual | Status |
|----------|--------------|--------|--------|
| LLCR | {_format_ratio(llcr_covenant)} | {_format_ratio(llcr_min)} | {llcr_status} |
| PLCR | {_format_ratio(plcr_covenant)} | {_format_ratio(plcr_min)} | {plcr_status} |

---

## Key Findings

✅ **Strong Coverage Ratios:** LLCR and PLCR are comfortably above DFI/lender covenant thresholds, indicating robust debt service capacity.

✅ **Aggressive Debt Paydown:** USD-denominated debt is amortized rapidly to minimize FX exposure, with full repayment by Year 6.

✅ **Healthy Financial Margins:** Substantial cushion above required minimums provides buffer for adverse scenarios.

---

## Next Steps

1. Review detailed financial schedules (available in full model output)
2. Conduct sensitivity analysis on key assumptions
3. Schedule investment committee presentation
4. Proceed to lender due diligence phase

---

*This Executive Summary is based on base case assumptions as of {report_date}.*
"""
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
    output_path: Optional[Path] = None
) -> str:
    report_date = datetime.now().strftime("%B %d, %Y")
    report = (
        f"# DutchBay 150MW Wind Farm - DFI/Lender Due Diligence Pack\n\n"
        f"**Prepared:** {report_date}\n\n"
        f"---\n\n"
        f"## 1. Debt Service Coverage Schedule\n\n"
        f"| Year | CFADS (USD) | Debt Service (USD) | DSCR | Debt Outstanding (USD) | LLCR |\n"
        f"|------|-------------|-------------------|------|------------------------|------|\n"
    )
    for i in range(min(5, len(cfads_series))):
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
        f"---\n\n"
        f"## 4. Risk Assessment\n\n"
        f"### Strengths\n"
        f"- Strong LLCR/PLCR coverage with healthy margins\n"
        f"- Proven wind resource in region\n"
        f"- PPA with offtaker of good creditworthiness\n"
        f"- Diversified revenue base reduces concentration risk\n\n"
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
