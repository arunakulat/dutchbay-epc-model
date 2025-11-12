#!/usr/bin/env python3
"""
Dutch Bay 150MW Wind Farm - Financial Model V12
Production-Grade with Full Type Hints, Robust IRR/NPV, Cash Flow, and Debt Logic

CAPEX: $155M (Wind only, no BESS)
Debt Structure: 80% total (45% USD, 55% LKR) (USD = 10% DFI @ 6.5%, 90% Market @ 7.0%)
Equity: 20%

Date: November 8, 2025
Version: V12 RECONSTRUCTED
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Final
from dataclasses import dataclass, field
from scipy.optimize import brentq, newton


# =========================================================================
# GLOBAL CONSTANTS & PROJECT PARAMETERS
# =========================================================================

TOTAL_CAPEX: Final[float] = 155.0
PROJECT_LIFE_YEARS: Final[int] = 20
NAMEPLATE_MW: Final[float] = 150
CF_P50: Final[float] = 0.40
YEARLY_DEGRADATION: Final[float] = 0.006
HOURS_PER_YEAR: Final[float] = 8760.0
TARIFF_LKR_KWH: Final[float] = 20.36
FX_INITIAL: Final[float] = 300.0
FX_DEPR: Final[float] = 0.03
OPEX_USD_MWH: Final[float] = 6.83
OPEX_ESC_USD: Final[float] = 0.02
OPEX_ESC_LKR: Final[float] = 0.05
OPEX_SPLIT_USD: Final[float] = 0.3
OPEX_SPLIT_LKR: Final[float] = 0.7
SSCL_RATE: Final[float] = 0.025
TAX_RATE: Final[float] = 0.30
ECON_LIFE: Final[int] = 20
MAX_DEBT_RATIO: Final[float] = 0.80
USD_DEBT_RATIO: Final[float] = 0.45
USD_DFI_PCT: Final[float] = 0.10
USD_MKT_PCT: Final[float] = 0.90
USD_DFI_RATE: Final[float] = 0.065
USD_MKT_RATE: Final[float] = 0.07
LKR_DEBT_RATE: Final[float] = 0.075
DEBT_TENOR_YEARS: Final[int] = 15
GRACE_PERIOD: Final[int] = 1
PRINCIPAL_PCT_1_4: Final[float] = 0.80
PRINCIPAL_PCT_5_ON: Final[float] = 0.20
MONTHS_TO_COD: Final[float] = 49.0

# =========================================================================
# DATACLASSES
# =========================================================================


@dataclass
class FinancialResults:
    equity_irr: float
    project_irr: float
    npv_12pct: float
    min_dscr: float
    avg_dscr: float
    year1_dscr: float
    annual_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    project_cashflows: list = field(default_factory=list)
    equity_cashflows: list = field(default_factory=list)
    irr_convergence_status: str = "UNKNOWN"
    irr_method: str = "UNKNOWN"


@dataclass
class ProjectParameters:
    total_capex: float = TOTAL_CAPEX
    project_life_years: int = PROJECT_LIFE_YEARS
    nameplate_mw: float = NAMEPLATE_MW
    cf_p50: float = CF_P50
    yearly_degradation: float = YEARLY_DEGRADATION
    hours_per_year: float = HOURS_PER_YEAR
    tariff_lkr_kwh: float = TARIFF_LKR_KWH
    fx_initial: float = FX_INITIAL
    fx_depr: float = FX_DEPR
    opex_usd_mwh: float = OPEX_USD_MWH
    opex_esc_usd: float = OPEX_ESC_USD
    opex_esc_lkr: float = OPEX_ESC_LKR
    opex_split_usd: float = OPEX_SPLIT_USD
    opex_split_lkr: float = OPEX_SPLIT_LKR
    sscl_rate: float = SSCL_RATE
    tax_rate: float = TAX_RATE
    econ_life: int = ECON_LIFE
    grace_period: int = GRACE_PERIOD
    principal_pct_1_4: float = PRINCIPAL_PCT_1_4
    principal_pct_5_on: float = PRINCIPAL_PCT_5_ON
    months_to_cod: float = MONTHS_TO_COD


@dataclass
class DebtStructure:
    total_debt: float
    usd_debt: float
    lkr_debt: float
    usd_dfi_rate: float
    usd_mkt_rate: float
    lkr_rate: float
    dfi_pct_of_usd: float
    debt_tenor_years: int


@dataclass
class IRRResult:
    irr: Optional[float]
    status: str
    method: str
    npv_check: Optional[float]
    warning: Optional[str]
    message: Optional[str] = None


def create_default_parameters() -> ProjectParameters:
    """Exported for CLI/tools compatibility: Returns default project parameters."""
    return ProjectParameters()


def create_default_debt_structure() -> DebtStructure:
    total_debt = TOTAL_CAPEX * MAX_DEBT_RATIO
    usd_debt = total_debt * USD_DEBT_RATIO
    lkr_debt = total_debt - usd_debt
    return DebtStructure(
        total_debt=total_debt,
        usd_debt=usd_debt,
        lkr_debt=lkr_debt,
        usd_dfi_rate=USD_DFI_RATE,
        usd_mkt_rate=USD_MKT_RATE,
        lkr_rate=LKR_DEBT_RATE,
        dfi_pct_of_usd=USD_DFI_PCT,
        debt_tenor_years=DEBT_TENOR_YEARS,
    )


# =========================================================================
# IRR/NPV CALCULATION FUNCTIONS
# =========================================================================


def calculate_npv(rate: float, cash_flows: List[float]) -> float:
    return float(np.sum([cf / (1 + rate) ** i for i, cf in enumerate(cash_flows)]))


def calculate_irr_robust(
    cash_flows: List[float],
    method: str = "brentq",
    initial_guess: float = 0.10,
    tolerance: float = 1e-8,
    max_iterations: int = 1000,
) -> IRRResult:
    cf = np.array(cash_flows, dtype=float)
    if len(cf) < 2:
        return IRRResult(
            None, "ERROR", method, None, "Too few cash flows", "Too few cash flows"
        )
    if np.all(cf >= 0):
        return IRRResult(
            None,
            "ERROR",
            method,
            None,
            "No negative cash flows - IRR undefined",
            "No negative cash flows",
        )
    if np.all(cf <= 0):
        return IRRResult(
            None,
            "ERROR",
            method,
            None,
            "No positive cash flows - IRR undefined",
            "No positive cash flows",
        )
    sign_changes = sum(1 for i in range(len(cf) - 1) if (cf[i] * cf[i + 1] < 0))
    warning = (
        f"{sign_changes} sign changes detected - multiple IRRs may exist"
        if sign_changes > 1
        else None
    )
    # Brentq root finder
    if method in ["brentq", "both"]:
        try:
            irr_result = brentq(
                lambda r: calculate_npv(r, cf),
                -0.99,
                5.00,
                xtol=tolerance,
                maxiter=max_iterations,
            )
            npv_check = calculate_npv(irr_result, cf)
            if abs(npv_check) < tolerance * 10:
                return IRRResult(irr_result, "CONVERGED", "Brentq", npv_check, warning)
        except Exception as e:
            if method == "brentq":
                return IRRResult(None, "ERROR", "Brentq", None, warning, str(e))
            # Otherwise, try Newton
    if method in ["newton", "both"]:
        try:

            def npv_derivative(rate, cf):
                return -np.sum(
                    [i * c / (1 + rate) ** (i + 1) for i, c in enumerate(cf)]
                )

            irr_result = newton(
                lambda r: calculate_npv(r, cf),
                initial_guess,
                fprime=lambda r: npv_derivative(r, cf),
                tol=tolerance,
                maxiter=max_iterations,
            )
            npv_check = calculate_npv(irr_result, cf)
            if abs(npv_check) < tolerance * 10 and -0.99 < irr_result < 5.0:
                return IRRResult(irr_result, "CONVERGED", "Newton", npv_check, warning)
        except Exception:
            pass
    return IRRResult(
        None, "FAILED", "None", None, warning, "All solver methods failed to converge"
    )


# =========================================================================
# CASH FLOW AND CORE FINANCIAL CALCULATION FUNCTIONS
# =========================================================================


def build_financial_model(
    proj: ProjectParameters = ProjectParameters(), debt: Optional[DebtStructure] = None
) -> Dict[str, Any]:
    """Build a complete 20-year financial projection given project and debt parameters."""
    # Defaults
    if debt is None:
        total_debt = proj.total_capex * MAX_DEBT_RATIO
        usd_debt = total_debt * USD_DEBT_RATIO
        lkr_debt = total_debt - usd_debt
        debt = DebtStructure(
            total_debt=total_debt,
            usd_debt=usd_debt,
            lkr_debt=lkr_debt,
            usd_dfi_rate=USD_DFI_RATE,
            usd_mkt_rate=USD_MKT_RATE,
            lkr_rate=LKR_DEBT_RATE,
            dfi_pct_of_usd=USD_DFI_PCT,
            debt_tenor_years=DEBT_TENOR_YEARS,
        )
    years = np.arange(1, proj.project_life_years + 1)
    # Operating metrics
    gen = np.array(
        [
            proj.nameplate_mw
            * proj.hours_per_year
            * proj.cf_p50
            * (1 - proj.yearly_degradation) ** (y - 1)
            for y in years
        ]
    )
    fx = np.array([proj.fx_initial * (1 + proj.fx_depr) ** (y - 1) for y in years])
    tariff_usd = np.array([proj.tariff_lkr_kwh / fx[y - 1] * 1000 for y in years])
    revenue = gen * tariff_usd / 1_000_000
    sscl = revenue * proj.sscl_rate
    # OPEX escalation
    usd_portion = (
        proj.opex_usd_mwh * proj.opex_split_usd * (1 + proj.opex_esc_usd) ** (years - 1)
    )
    lkr_portion_base = (
        proj.opex_usd_mwh * proj.opex_split_lkr * (1 + proj.opex_esc_lkr) ** (years - 1)
    )
    lkr_portion_usd = lkr_portion_base / (fx / proj.fx_initial)
    opex = gen * (usd_portion + lkr_portion_usd) / 1_000_000
    da = np.full(proj.project_life_years, proj.total_capex / proj.econ_life)
    ebitda = revenue - sscl - opex
    ebit = ebitda - da
    tax = np.maximum(0, ebit * proj.tax_rate)
    op_cf = ebit - tax + da
    # Debt schedules
    usd_bal = debt.usd_debt
    lkr_bal = debt.lkr_debt
    usd_principal_hist = []
    usd_interest_hist = []
    lkr_principal_hist = []
    lkr_interest_hist = []
    lkr_ds_hist = []
    for year in range(1, proj.project_life_years + 1):
        usd_int = (
            usd_bal * USD_MKT_RATE
        )  # For simplicity, use market USD rate as default
        lkr_int = lkr_bal * LKR_DEBT_RATE
        fx_year = proj.fx_initial * (1 + proj.fx_depr) ** (year - 1)
        lkr_int_usd = lkr_int / fx_year
        # Principal based on OpCF after interest, tax
        ebitda_y = revenue[year - 1] - sscl[year - 1] - opex[year - 1]
        da_y = da[year - 1]
        ebit_y = ebitda_y - da_y
        tax_y = max(0, ebit_y * proj.tax_rate)
        op_cf_y = ebit_y - tax_y + da_y
        op_cf_avail = op_cf_y - usd_int - lkr_int_usd
        if year == 1 and proj.grace_period == 1:
            usd_prin = 0
        elif 2 <= year <= 4:
            usd_prin = min(usd_bal, proj.principal_pct_1_4 * op_cf_avail)
        elif year > 4:
            usd_prin = min(usd_bal, proj.principal_pct_5_on * op_cf_avail)
        else:
            usd_prin = 0
        usd_bal = max(0.0, usd_bal - usd_prin)
        if year <= debt.debt_tenor_years:
            lkr_prin = lkr_bal / (debt.debt_tenor_years - year + 1)
        else:
            lkr_prin = 0
        lkr_bal = max(0.0, lkr_bal - lkr_prin)
        lkr_ds = lkr_int + lkr_prin
        usd_principal_hist.append(usd_prin)
        usd_interest_hist.append(usd_int)
        lkr_principal_hist.append(lkr_prin)
        lkr_interest_hist.append(lkr_int)
        lkr_ds_hist.append(lkr_ds)
    usd_prin = np.array(usd_principal_hist)
    usd_int = np.array(usd_interest_hist)
    lkr_prin = np.array(lkr_principal_hist)
    lkr_int = np.array(lkr_interest_hist)
    lkr_ds = np.array(lkr_ds_hist)
    lkr_int_usd = lkr_int / fx
    lkr_prin_usd = lkr_prin / fx
    total_ds = usd_int + usd_prin + lkr_int_usd + lkr_prin_usd
    dscr = np.where(total_ds > 1e-6, op_cf / total_ds, np.nan)
    eq_cf = op_cf - total_ds
    # Build annual dataframe
    annual_data = pd.DataFrame(
        {
            "Year": years,
            "Generation_MWh": gen,
            "FX": fx,
            "Tariff_USD_MWh": tariff_usd,
            "Revenue_USD_M": revenue,
            "SSCL_USD_M": sscl,
            "OPEX_USD_M": opex,
            "EBITDA": ebitda,
            "DA": da,
            "EBIT": ebit,
            "Tax": tax,
            "Op_CF": op_cf,
            "USD_Int": usd_int,
            "USD_Prin": usd_prin,
            "LKR_Int": lkr_int_usd,
            "LKR_Prin": lkr_prin_usd,
            "Total_DS": total_ds,
            "DSCR": dscr,
            "Eq_CF": eq_cf,
        }
    )
    # Full project/equity cash flows for IRR
    project_cf = [-proj.total_capex] + list(op_cf)
    eq_cf_full = [-proj.total_capex + debt.total_debt] + list(eq_cf)
    equity_irr_result = calculate_irr_robust(eq_cf_full)
    project_irr_result = calculate_irr_robust(project_cf)
    npv_12pct = calculate_npv(0.12, eq_cf_full)
    return {
        "annual_data": annual_data,
        "equity_irr": equity_irr_result.irr,
        "project_irr": project_irr_result.irr,
        "npv_12pct": npv_12pct,
        "min_dscr": np.nanmin(dscr),
        "avg_dscr": np.nanmean(dscr),
        "year1_dscr": dscr[0],
        "irr_convergence_status": equity_irr_result.status,
        "irr_method": equity_irr_result.method,
    }


if __name__ == "__main__":
    result = build_financial_model()
    result["annual_data"].to_csv("outputs/dutchbay_v12_outputs.csv", index=False)
    print("\nModel run successful. Key outputs:")
    print(result["annual_data"].head())
    print(f"\nEquity IRR: {result['equity_irr']:.4f}")
    print(f"Project IRR: {result['project_irr']:.4f}")
    print(f"NPV @ 12%: {result['npv_12pct']:.2f}M USD")
    print(f"Min DSCR: {result['min_dscr']:.2f}")
