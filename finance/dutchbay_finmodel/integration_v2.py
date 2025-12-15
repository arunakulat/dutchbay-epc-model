"""Phase 1-2 Integration: Complete refactored financial model.

This module ties together Phase 1 (tax layer) and Phase 2 (WACC + interest)
into a complete, coherent financial model implementation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from tax_profile import DepreciationSchedule, TaxProfile, build_tax_series
from wacc_integration import WaccResult, apply_wacc_to_irr_comparison


def integrate_tax_and_wacc(
    years: List[int],
    revenue: np.ndarray,
    opex: np.ndarray,
    interest_expense: np.ndarray,
    debt_service: np.ndarray,
    capex_total: float,
    total_debt: float,
    total_equity: float,
    tax_profile: Optional[TaxProfile] = None,
    wacc_result: Optional[WaccResult] = None,
    depreciation_schedule: Optional[DepreciationSchedule] = None,
) -> Dict[str, Any]:
    """Integration function for Phase 1-2 refactoring.

    Args:
        years: Project years (1-based)
        revenue: Annual revenue (LKR)
        opex: Annual opex (LKR)
        interest_expense: Annual interest from debt module
        debt_service: Annual debt service (principal + interest)
        capex_total: Total capex (LKR)
        total_debt: Total debt (LKR)
        total_equity: Total equity (LKR)
        tax_profile: TaxProfile for Phase 1 tax calculation
        wacc_result: WaccResult for Phase 2 WACC integration
        depreciation_schedule: Pre-computed depreciation schedule

    Returns:
        Complete financial model results with tax and WACC integrated
    """

    # Step 1: Calculate EBIT
    ebit = revenue - opex

    # Step 2: Phase 1 - Tax calculation
    if tax_profile is None:
        tax_liability = np.zeros(len(years))
        tax_series = None
    else:
        if depreciation_schedule is None:
            # Default: straight-line over project life
            depreciation_schedule = DepreciationSchedule.build_straight_line(
                capex_total, len(years), len(years)
            )

        tax_series = build_tax_series(
            years=years,
            ebit_series=ebit.tolist(),
            interest_series=interest_expense.tolist(),
            depreciation_schedule=depreciation_schedule,
            tax_profile=tax_profile,
        )
        tax_liability = np.array([tr.tax_liability for tr in tax_series])

    # Step 3: CFADS calculation (includes interest)
    cfads = ebit - tax_liability - interest_expense
    cfads = np.maximum(cfads, -1e20)

    # Step 4: DSCR
    with np.errstate(divide="ignore", invalid="ignore"):
        dscr = np.where(debt_service > 0.0, cfads / debt_service, np.inf)

    # Step 5: Phase 2 - Build cash flows for WACC discounting
    proj_cf = np.zeros(len(years) + 1)
    proj_cf[0] = -capex_total
    proj_cf[1:] = cfads

    eq_cf = np.zeros(len(years) + 1)
    eq_cf[0] = -total_equity
    eq_cf[1:] = cfads - debt_service

    # Step 6: Calculate IRR
    irr_result = _calculate_irr(proj_cf)
    project_irr = irr_result["irr"]

    # Step 7: Phase 2 - WACC analysis
    wacc_analysis = None
    if wacc_result is not None:
        wacc_analysis = apply_wacc_to_irr_comparison(project_irr, wacc_result)

    # Build results dictionary
    results = {
        "years": years,
        "revenue": revenue,
        "opex": opex,
        "ebit": ebit,
        "interest_expense": interest_expense,
        "tax_liability": tax_liability,
        "cfads": cfads,
        "debt_service": debt_service,
        "dscr": dscr,
        "project_irr": project_irr,
        "equity_irr": _calculate_irr(eq_cf)["irr"],
        "tax_series": tax_series,
        "depreciation_schedule": depreciation_schedule,
        "wacc_analysis": wacc_analysis,
        "min_dscr": float(np.nanmin(np.where(np.isfinite(dscr), dscr, np.nan))),
        "capital_structure": {
            "capex": capex_total,
            "debt": total_debt,
            "equity": total_equity,
        },
    }

    return results


def _calculate_irr(cash_flows: np.ndarray) -> Dict[str, float]:
    """Calculate IRR using brute-force method."""
    try:
        import numpy_financial as nf

        irr_val = float(nf.irr(cash_flows))
        if np.isfinite(irr_val):
            return {"irr": irr_val, "method": "numpy_financial"}
    except Exception:
        pass

    # Fallback: brute force
    rates = np.linspace(-0.5, 1.5, 20001)
    cf = np.asarray(cash_flows, dtype=float)
    periods = np.arange(len(cf))
    npvs = np.array([np.sum(cf / (1.0 + r) ** periods) for r in rates])

    sign_changes = np.where(np.diff(np.sign(npvs)) != 0)[0]
    if len(sign_changes) > 0:
        i = sign_changes[0]
        r0, r1 = rates[i], rates[i + 1]
        v0, v1 = npvs[i], npvs[i + 1]
        if v1 != v0:
            return {
                "irr": float(r0 + (0.0 - v0) * (r1 - r0) / (v1 - v0)),
                "method": "brute_force",
            }

    return {"irr": float("nan"), "method": "failed"}


def create_summary_dataframe(integration_results: Dict[str, Any]) -> pd.DataFrame:
    """Create summary DataFrame from integration results."""
    return pd.DataFrame(
        {
            "Year": integration_results["years"],
            "Revenue_LKR": integration_results["revenue"],
            "Opex_LKR": integration_results["opex"],
            "EBIT_LKR": integration_results["ebit"],
            "InterestExpense_LKR": integration_results["interest_expense"],
            "Tax_LKR": integration_results["tax_liability"],
            "CFADS_LKR": integration_results["cfads"],
            "DebtService_LKR": integration_results["debt_service"],
            "DSCR": integration_results["dscr"],
            "PostDebtCF_LKR": integration_results["cfads"]
            - integration_results["debt_service"],
        }
    )


__all__ = [
    "integrate_tax_and_wacc",
    "create_summary_dataframe",
]
