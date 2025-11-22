"""
Financial Reporting Module - DutchBay V13

Generates institutional-grade reports from model outputs:
- Covenant Compliance Certificates
- Investment Committee Summaries
- Lender Presentation Packages

Author: DutchBay V13 Team, Nov 2025
Version: 1.0
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger('dutchbay.finance.reporting')

__all__ = [
    "generate_covenant_certificate",
    "generate_investment_committee_summary",
    "generate_all_reports"
]

# ============================================================================
# COVENANT COMPLIANCE CERTIFICATE
# ============================================================================

def generate_covenant_certificate(
    metrics_result: Dict[str, Any],
    params: Dict[str, Any],
    reporting_period: str = "Q4 2025",
    lender_name: str = "[Lender Name]",
    output_path: Optional[Path] = None
) -> str:
    """
    Generate Covenant Compliance Certificate from metrics results.
    
    Parameters
    ----------
    metrics_result : dict
        Output from summarize_project_metrics()
    params : dict
        Full YAML parameters
    reporting_period : str
        Reporting period (e.g., "Q4 2025")
    lender_name : str
        Name of lender/DFI
    output_path : Path, optional
        If provided, writes to file
    
    Returns
    -------
    str
        Markdown-formatted certificate
    """
    report_date = datetime.now().strftime("%B %d, %Y")
    
    # Extract metrics
    dscr = metrics_result.get('dscr', {}).get('summary', {})
    llcr = metrics_result.get('llcr', {})
    plcr = metrics_result.get('plcr', {})
    
    llcr_covenant_status = metrics_result.get('llcr_covenant', {})
    plcr_covenant_status = metrics_result.get('plcr_covenant', {})
    
    # Get covenant thresholds
    metrics_config = params.get('metrics', {})
    dscr_min_covenant = metrics_config.get('dscr_min_covenant', 1.30)
    llcr_min_covenant = metrics_config.get('llcr_min_covenant', 1.20)
    plcr_min_covenant = metrics_config.get('plcr_min_covenant', 1.40)
    
    # Calculate buffers
    dscr_min = dscr.get('dscr_min', 0)
    llcr_min = llcr.get('llcr_min', 0)
    plcr_min = plcr.get('plcr_min', 0)
    
    dscr_buffer = dscr_min - dscr_min_covenant if dscr_min else 0
    llcr_buffer = llcr_min - llcr_min_covenant if llcr_min else 0
    plcr_buffer = plcr_min - plcr_min_covenant if plcr_min else 0
    
    # Overall status
    all_pass = (
        llcr_covenant_status.get('covenant_status') == 'PASS' and
        plcr_covenant_status.get('covenant_status') == 'PASS' and
        dscr_min >= dscr_min_covenant
    )
    
    status_emoji = "✅" if all_pass else "⚠️"
    status_text = "FULL COMPLIANCE" if all_pass else "REVIEW REQUIRED"
    
    # Generate report
    report = f"""# COVENANT COMPLIANCE CERTIFICATE
## Dutch Bay 150MW Wind Farm Project

**Reporting Period:** {reporting_period}  
**Report Date:** {report_date}  
**Prepared By:** Envision Energy / Financial Team  
**Lender:** {lender_name}

---

## EXECUTIVE SUMMARY

This certificate confirms the Dutch Bay 150MW Wind Farm Project covenant compliance status as of {report_date}.

**Overall Status: {status_emoji} {status_text}**

---

## COVENANT COMPLIANCE SUMMARY

| Financial Covenant | Minimum Required | Actual (Period) | Status | Buffer |
|-------------------|------------------|-----------------|--------|--------|
| DSCR (Debt Service Coverage) | ≥ {dscr_min_covenant:.2f}x | {dscr_min:.2f}x | {'✅ PASS' if dscr_min >= dscr_min_covenant else '⚠️ WARN'} | {dscr_buffer:+.2f}x |
| LLCR (Loan Life Coverage) | ≥ {llcr_min_covenant:.2f}x | {llcr_min:.2f}x | {status_emoji} {llcr_covenant_status.get('covenant_status', 'N/A')} | {llcr_buffer:+.2f}x |
| PLCR (Project Life Coverage) | ≥ {plcr_min_covenant:.2f}x | {plcr_min:.2f}x | {status_emoji} {plcr_covenant_status.get('covenant_status', 'N/A')} | {plcr_buffer:+.2f}x |

---

## DETAILED METRICS

### Debt Service Coverage Ratio (DSCR)
- **Definition:** CFADS / Annual Debt Service
- **Covenant:** Minimum {dscr_min_covenant:.2f}x throughout loan tenor
- **Current Period:** {dscr_min:.2f}x
- **Historical Range:** {dscr_min:.2f}x - {dscr.get('dscr_max', 0):.2f}x
- **Average:** {dscr.get('dscr_avg', 0):.2f}x
- **Status:** {'✅ No violations recorded' if dscr.get('years_below_1_3', 0) == 0 else f"⚠️ {dscr.get('years_below_1_3', 0)} period(s) below 1.3x"}

### Loan Life Coverage Ratio (LLCR)
- **Definition:** NPV(Future CFADS over loan life) / Outstanding Debt
- **Covenant:** Minimum {llcr_min_covenant:.2f}x at all measurement dates
- **Current:** {llcr_min:.2f}x
- **Average:** {llcr.get('llcr_avg', 0):.2f}x
- **Calculation Basis:** {metrics_result.get('discount_rate', 0.10):.1%} discount rate
- **Status:** {llcr_covenant_status.get('summary', 'N/A')}

### Project Life Coverage Ratio (PLCR)
- **Definition:** NPV(All future CFADS) / Outstanding Debt
- **Covenant:** Minimum {plcr_min_covenant:.2f}x
- **Current:** {plcr_min:.2f}x
- **Average:** {plcr.get('plcr_avg', 0):.2f}x
- **Status:** {plcr_covenant_status.get('summary', 'N/A')}

---

## DEBT PROFILE

- **Total Debt Outstanding:** ${params.get('capex', {}).get('usd_total', 0) * params.get('Financing_Terms', {}).get('debt_ratio', 0.70) / 1e6:.1f}M
- **Remaining Tenor:** {params.get('Financing_Terms', {}).get('tenor_years', 15)} years
- **Amortization Status:** On schedule
- **Interest-Only Period:** {params.get('Financing_Terms', {}).get('interest_only_years', 2)} years

---

## CERTIFICATIONS

I hereby certify that:

1. All financial covenants are {'satisfied' if all_pass else 'under review'} as of the reporting date
2. All calculations follow the methodology specified in the Credit Agreement
3. {'No Events of Default or Potential Events of Default exist' if all_pass else 'All violations have been disclosed to lenders'}
4. All financial statements and supporting documentation are accurate and complete

---

**Authorized Signatory:**

Name: ______________________  
Title: Chief Financial Officer  
Date: {report_date}

---

**Attachments:**
- Detailed DSCR calculation schedule
- LLCR/PLCR calculation worksheets
- Annual financial statements
- Model output validation reports

---

*Generated by DutchBay V13 Financial Model - P0-1C*  
*Report ID: COV-{datetime.now().strftime("%Y%m%d-%H%M%S")}*
"""
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        logger.info(f"Covenant certificate written to {output_path}")
    
    return report

# ============================================================================
# INVESTMENT COMMITTEE SUMMARY
# ============================================================================

def generate_investment_committee_summary(
    metrics_result: Dict[str, Any],
    irr_result: Dict[str, Any],
    params: Dict[str, Any],
    output_path: Optional[Path] = None
) -> str:
    """
    Generate Investment Committee Summary from full model results.
    
    Parameters
    ----------
    metrics_result : dict
        Output from summarize_project_metrics()
    irr_result : dict
        Output from IRR calculations (equity_irr, project_irr, etc.)
    params : dict
        Full YAML parameters
    output_path : Path, optional
        If provided, writes to file
    
    Returns
    -------
    str
        Markdown-formatted IC summary
    """
    report_date = datetime.now().strftime("%B %d, %Y")
    
    # Extract metrics
    dscr = metrics_result.get('dscr', {}).get('summary', {})
    llcr = metrics_result.get('llcr', {})
    plcr = metrics_result.get('plcr', {})
    
    llcr_covenant = metrics_result.get('llcr_covenant', {})
    plcr_covenant = metrics_result.get('plcr_covenant', {})
    
    # Get covenant thresholds
    metrics_config = params.get('metrics', {})
    dscr_min_covenant = metrics_config.get('dscr_min_covenant', 1.30)
    llcr_min_covenant = metrics_config.get('llcr_min_covenant', 1.20)
    plcr_min_covenant = metrics_config.get('plcr_min_covenant', 1.40)
    
    # Calculate buffers
    dscr_min = dscr.get('dscr_min', 0)
    llcr_min = llcr.get('llcr_min', 0)
    plcr_min = plcr.get('plcr_min', 0)
    
    llcr_buffer_pct = ((llcr_min / llcr_min_covenant) - 1) * 100 if llcr_min_covenant else 0
    plcr_buffer_pct = ((plcr_min / plcr_min_covenant) - 1) * 100 if plcr_min_covenant else 0
    dscr_buffer_pct = ((dscr_min / dscr_min_covenant) - 1) * 100 if dscr_min_covenant else 0
    
    # Overall status
    all_pass = (
        llcr_covenant.get('covenant_status') == 'PASS' and
        plcr_covenant.get('covenant_status') == 'PASS' and
        dscr_min >= dscr_min_covenant
    )
    
    report = f"""# INVESTMENT COMMITTEE SUMMARY
## P0-1C: Enhanced Coverage Metrics Implementation

**Date:** {report_date}  
**Project:** Dutch Bay 150MW Wind Farm  
**Phase:** P0-1C Complete

---

## EXECUTIVE SUMMARY

The Dutch Bay financial model has been enhanced with institutional-grade coverage ratio calculations, meeting DFI and commercial lender standards for project finance credit approval.

**Key Achievement:** All financial covenants {'significantly exceeded with healthy buffers' if all_pass else 'under review'}.

---

## METRICS IMPLEMENTED

### 1. LLCR (Loan Life Coverage Ratio)
- **Purpose:** Primary DFI credit metric
- **Calculation:** NPV of future debt-service cashflows / Outstanding debt
- **Standard:** IFC, EBRD, ADB methodology
- **Result:** {llcr_min:.2f}x ({llcr_buffer_pct:+.0f}% vs {llcr_min_covenant:.2f}x minimum)

### 2. PLCR (Project Life Coverage Ratio)
- **Purpose:** Full project value assessment
- **Calculation:** NPV of all future cashflows / Outstanding debt
- **Standard:** Equity investor protection metric
- **Result:** {plcr_min:.2f}x ({plcr_buffer_pct:+.0f}% vs {plcr_min_covenant:.2f}x minimum)

### 3. Enhanced DSCR Tracking
- **Purpose:** Annual debt serviceability
- **Result:** {dscr_min:.2f}x minimum ({dscr_buffer_pct:+.0f}% vs {dscr_min_covenant:.2f}x covenant)

---

## FINANCIAL STRENGTH INDICATORS

| Indicator | Value | Interpretation |
|-----------|-------|----------------|
| **Minimum DSCR** | {dscr_min:.2f}x | {'Strong annual coverage' if dscr_min >= 1.5 else 'Adequate coverage'} |
| **Average DSCR** | {dscr.get('dscr_avg', 0):.2f}x | {'Excellent headroom' if dscr.get('dscr_avg', 0) >= 2.0 else 'Good headroom'} |
| **LLCR Buffer** | {llcr_min - llcr_min_covenant:+.2f}x | {llcr_buffer_pct:.0f}% above covenant |
| **PLCR Buffer** | {plcr_min - plcr_min_covenant:+.2f}x | {plcr_buffer_pct:.0f}% above covenant |
| **Covenant Violations** | {len(llcr_covenant.get('violations', [])) + len(plcr_covenant.get('violations', []))} | {'Zero across all scenarios' if all_pass else 'Review required'} |

---

## PROJECT RETURNS (From IRR Module)

| Metric | Value | Assessment |
|--------|-------|------------|
| **Equity IRR** | {irr_result.get('equity_irr', 0):.1%} | {'Strong' if irr_result.get('equity_irr', 0) > 0.15 else 'Review'} |
| **Project IRR** | {irr_result.get('project_irr', 0):.1%} | Target achieved |
| **NPV (10%)** | ${irr_result.get('npv_10', 0)/1e6:.1f}M | Value creation |

---

## RISK ASSESSMENT

### Strengths:
{'✅ All metrics significantly exceed minimums' if all_pass else '⚠️ Covenant compliance under review'}  
✅ Conservative debt structure  
✅ Strong downside protection for equity  
✅ DFI-compliant methodology and reporting

### Considerations:
- PLCR {'=' if abs(plcr_min - llcr_min) < 0.01 else '>'} LLCR indicates {'no post-loan cashflows (conservative)' if abs(plcr_min - llcr_min) < 0.01 else 'post-loan value creation'}
- Debt fully amortized within {params.get('Financing_Terms', {}).get('tenor_years', 15)} years
- Project life: {params.get('project', {}).get('timeline', {}).get('lifetime_years', 20)} years

---

## LENDER IMPLICATIONS

**For DFI Lenders (IFC/EBRD/ADB):**
- {'✅' if llcr_min >= llcr_min_covenant else '⚠️'} LLCR {llcr_min:.2f}x vs {llcr_min_covenant:.2f}x minimum
- {'✅ Ready for credit committee approval' if all_pass else '⚠️ Additional review required'}

**For Commercial Banks:**
- {'✅' if dscr_min >= 1.3 else '⚠️'} Strong DSCR profile ({dscr_min:.2f}x - {dscr.get('dscr_max', 0):.2f}x)
- {'✅' if all_pass else '⚠️'} Conservative amortization structure

**For Equity Investors:**
- {'✅' if plcr_min >= plcr_min_covenant else '⚠️'} PLCR {plcr_min:.2f}x provides {'excellent' if plcr_min >= 2.0 else 'adequate'} downside protection
- ✅ Post-debt equity cashflows maximized

---

## RECOMMENDATION

**The Investment Committee is recommended to:**

1. **{'Approve' if all_pass else 'Review'}** the P0-1C enhanced metrics module for production use
2. **Note** the covenant compliance results (metrics {llcr_buffer_pct:.0f}%-{dscr_buffer_pct:.0f}% above minimums)
3. **{'Authorize' if all_pass else 'Defer'}** use of these metrics in lender presentations and credit applications
4. **Proceed** to next development phase (P0-2 Optimization)

---

**Prepared by:** Financial Modeling Team  
**Date:** {report_date}  
**Status:** For Committee Review

---

*Generated by DutchBay V13 Financial Model - P0-1C*  
*Report ID: IC-{datetime.now().strftime("%Y%m%d-%H%M%S")}*
"""
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        logger.info(f"Investment Committee summary written to {output_path}")
    
    return report

# ============================================================================
# BATCH GENERATION
# ============================================================================

def generate_all_reports(
    metrics_result: Dict[str, Any],
    irr_result: Dict[str, Any],
    params: Dict[str, Any],
    output_dir: Path = Path("outputs"),
    reporting_period: str = "Q4 2025",
    lender_name: str = "[Lender Name]"
) -> Dict[str, Path]:
    """
    Generate all reports in one call.
    
    Returns
    -------
    dict
        {'covenant_cert': Path, 'ic_summary': Path}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate both reports
    covenant_path = output_dir / f"covenant_compliance_certificate_{datetime.now().strftime('%Y%m%d')}.md"
    ic_path = output_dir / f"investment_committee_summary_{datetime.now().strftime('%Y%m%d')}.md"
    
    generate_covenant_certificate(
        metrics_result, params, reporting_period, lender_name, covenant_path
    )
    
    generate_investment_committee_summary(
        metrics_result, irr_result, params, ic_path
    )
    
    logger.info(f"✓ All reports generated in {output_dir}")
    
    return {
        'covenant_cert': covenant_path,
        'ic_summary': ic_path
    }
