"""Phase 2 Refactoring: WACC Integration & Interest Wiring (CCCDIR-compliant)

This module implements Phase 2 of the v14 refactoring package:
  - Wire WACC into KPI discount rate calculations
  - Inject interest expense from debt module into annual rows
  - Integrate WACC components for cost-of-capital calculations

Design Principles:
  - Contract-first: All results are typed dataclasses
  - Config-driven: WACC parameters are explicit
  - Observable: Every calculation is traceable
  - Backward-compatible: Existing code continues to work

Phase 2 Deliverables:
  1. WaccComponents: WACC calculation breakdown
  2. WaccResult: Complete WACC calculation output
  3. calculate_wacc(): Core WACC engine
  4. integrate_interest_into_cashflow(): Injects interest into annual rows
  5. apply_wacc_to_kpis(): Discounts KPIs using WACC rate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class WaccComponents:
    """Immutable WACC calculation component breakdown (CCCDIR-compliant).

    Encodes all intermediate calculations for WACC, enabling audit trails
    and transparency for lender/investor reporting.

    Attributes:
        mode: Calculation mode ('nominal', 'real', 'prudential')
        risk_free_rate: Risk-free rate (e.g., government bond yield)
        market_risk_premium: Market risk premium (equities vs risk-free)
        asset_beta: Unlevered beta (business risk only)
        equity_beta_levered: Levered beta (includes financial risk)
        cost_of_equity: Calculated cost of equity
        cost_of_debt_pretax: Pre-tax cost of debt (weighted)
        cost_of_debt_aftertax: After-tax cost of debt (with tax shield)
        tax_rate: Tax rate applied for tax shield
        target_debt_to_value: Target debt ratio (D/(D+E))
        target_equity_to_value: Target equity ratio (E/(D+E))
        wacc_nominal: WACC before inflation adjustment
        wacc_real: WACC in real terms (inflation-adjusted)
        wacc_prudential: WACC with prudential spread added
        inflation_rate: Inflation assumption for real WACC
        prudential_spread_bps: Prudential buffer (basis points)
    """

    mode: str  # 'nominal', 'real', 'prudential'
    risk_free_rate: float
    market_risk_premium: float
    asset_beta: float
    equity_beta_levered: float
    cost_of_equity: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    tax_rate: float
    target_debt_to_value: float
    target_equity_to_value: float
    wacc_nominal: float
    wacc_real: Optional[float] = None
    wacc_prudential: Optional[float] = None
    inflation_rate: Optional[float] = None
    prudential_spread_bps: int = 0

    def __post_init__(self) -> None:
        """Validate WACC components."""
        if not 0.0 <= self.target_debt_to_value <= 1.0:
            raise ValueError("target_debt_to_value must be in [0, 1]")
        if abs(self.target_debt_to_value + self.target_equity_to_value - 1.0) > 1e-6:
            raise ValueError("debt_to_value + equity_to_value must sum to 1.0")


@dataclass(frozen=True)
class WaccResult:
    """Immutable complete WACC calculation result (CCCDIR-compliant).

    Complete WACC result including base and prudential valuations,
    ready for use in NPV/IRR calculations.

    Attributes:
        base: WaccComponents with base calculation
        prudential_rate: Prudential WACC rate (with buffer)
        prudential_npv: NPV using prudential discount rate (optional)
        meta: Metadata (timestamps, calculation notes, audit trail)
    """

    base: WaccComponents
    prudential_rate: float
    prudential_npv: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


def calculate_wacc(
    risk_free_rate: float,
    market_risk_premium: float,
    asset_beta: float,
    cost_of_debt_pretax: float,
    tax_rate: float,
    debt_to_value: float,
    inflation_rate: Optional[float] = None,
    prudential_spread_bps: int = 100,
) -> WaccResult:
    """Calculate WACC using standard corporate finance formula.

    Implements the standard WACC formula:
        WACC = (E/V) * Cost_of_Equity + (D/V) * Cost_of_Debt_AfterTax

    Where:
        E = Market value of equity
        D = Market value of debt
        V = E + D (total firm value)
        Cost_of_Equity = Rf + Beta * (Rm - Rf)
        Cost_of_Debt_AfterTax = Rd * (1 - Tax_Rate)

    Args:
        risk_free_rate: Risk-free rate (typically sovereign bond yield)
        market_risk_premium: Expected market return - risk-free rate
        asset_beta: Unlevered beta (systematic risk of assets)
        cost_of_debt_pretax: Pre-tax weighted average cost of debt
        tax_rate: Effective tax rate (for tax shield)
        debt_to_value: Target D/(D+E) ratio
        inflation_rate: Inflation rate for real WACC calculation
        prudential_spread_bps: Prudential buffer (basis points, default 100)

    Returns:
        WaccResult with complete calculation breakdown

    Example:
        >>> wacc = calculate_wacc(
        ...     risk_free_rate=0.05,
        ...     market_risk_premium=0.08,
        ...     asset_beta=1.2,
        ...     cost_of_debt_pretax=0.07,
        ...     tax_rate=0.28,
        ...     debt_to_value=0.60
        ... )
        >>> print(f"WACC: {wacc.base.wacc_nominal:.2%}")
    """
    # Step 1: Lever asset beta to reflect capital structure
    equity_to_value = 1.0 - debt_to_value

    # Levering formula: Beta_L = Beta_U * [1 + (1 - Tax) * (D/E)]
    if equity_to_value > 0:
        debt_to_equity = debt_to_value / equity_to_value
        equity_beta_levered = asset_beta * (1.0 + (1.0 - tax_rate) * debt_to_equity)
    else:
        equity_beta_levered = asset_beta

    # Step 2: Calculate cost of equity using CAPM
    cost_of_equity = risk_free_rate + equity_beta_levered * market_risk_premium

    # Step 3: Calculate after-tax cost of debt
    cost_of_debt_aftertax = cost_of_debt_pretax * (1.0 - tax_rate)

    # Step 4: Calculate WACC (nominal)
    wacc_nominal = (
        equity_to_value * cost_of_equity + debt_to_value * cost_of_debt_aftertax
    )

    # Step 5: Calculate real WACC if inflation provided
    wacc_real = None
    if inflation_rate is not None and inflation_rate > 0:
        # Fisher equation: (1 + r_real) = (1 + r_nominal) / (1 + inflation)
        wacc_real = ((1.0 + wacc_nominal) / (1.0 + inflation_rate)) - 1.0

    # Step 6: Calculate prudential WACC
    prudential_spread = prudential_spread_bps / 10000.0
    wacc_prudential = wacc_nominal + prudential_spread

    # Step 7: Build components
    components = WaccComponents(
        mode="nominal",
        risk_free_rate=risk_free_rate,
        market_risk_premium=market_risk_premium,
        asset_beta=asset_beta,
        equity_beta_levered=equity_beta_levered,
        cost_of_equity=cost_of_equity,
        cost_of_debt_pretax=cost_of_debt_pretax,
        cost_of_debt_aftertax=cost_of_debt_aftertax,
        tax_rate=tax_rate,
        target_debt_to_value=debt_to_value,
        target_equity_to_value=equity_to_value,
        wacc_nominal=wacc_nominal,
        wacc_real=wacc_real,
        wacc_prudential=wacc_prudential,
        inflation_rate=inflation_rate,
        prudential_spread_bps=prudential_spread_bps,
    )

    return WaccResult(
        base=components,
        prudential_rate=wacc_prudential,
        meta={
            "calculation_type": "standard_wacc",
            "formula": "WACC = (E/V)*CoE + (D/V)*CoD*(1-T)",
            "capm_used": True,
        },
    )


def inject_interest_into_annual_rows(
    annual_rows: List[Dict[str, float]],
    interest_expense_schedule: List[float],
) -> List[Dict[str, float]]:
    """Inject interest expense from debt module into annual rows.

    Phase 2 critical function: Merges debt-layer interest into cashflow rows,
    enabling interest-aware tax calculations and complete financial statements.

    Args:
        annual_rows: List of annual row dicts from build_annual_rows()
        interest_expense_schedule: Interest expense by year from debt module

    Returns:
        Modified annual_rows with interest_expense_lkr field added

    Note:
        This function mutates the rows in-place (dict updates).
        To maintain immutability, convert rows to frozen dataclasses
        in Phase 3.
    """
    if len(annual_rows) != len(interest_expense_schedule):
        raise ValueError(
            f"annual_rows length ({len(annual_rows)}) != "
            f"interest_expense_schedule length ({len(interest_expense_schedule)})"
        )

    for row, interest in zip(annual_rows, interest_expense_schedule):
        row["interest_expense_lkr"] = interest

    return annual_rows


def apply_wacc_to_npv(
    cash_flows: List[float],
    wacc_result: WaccResult,
    start_period: int = 0,
) -> Dict[str, float]:
    """Calculate NPV using WACC as discount rate.

    Phase 2 critical function: Enables NPV calculations using WACC instead of
    legacy hardcoded discount rate.

    Args:
        cash_flows: Annual cash flow series (year 0, 1, 2, ...)
        wacc_result: WaccResult from calculate_wacc()
        start_period: Starting period for discounting (default 0)

    Returns:
        Dict with npv_nominal, npv_prudential, and wacc_used

    Note:
        NPV = sum(CF_t / (1 + WACC)^t) for t = start_period to end
    """
    cf_array = np.array(cash_flows, dtype=float)
    periods = np.arange(start_period, start_period + len(cf_array))

    # NPV using nominal WACC
    discount_factors_nominal = 1.0 / (1.0 + wacc_result.base.wacc_nominal) ** periods
    npv_nominal = float(np.sum(cf_array * discount_factors_nominal))

    # NPV using prudential WACC
    discount_factors_prudential = 1.0 / (1.0 + wacc_result.prudential_rate) ** periods
    npv_prudential = float(np.sum(cf_array * discount_factors_prudential))

    return {
        "npv_nominal": npv_nominal,
        "npv_prudential": npv_prudential,
        "wacc_nominal_used": wacc_result.base.wacc_nominal,
        "wacc_prudential_used": wacc_result.prudential_rate,
    }


def apply_wacc_to_irr_comparison(
    project_irr: float,
    wacc_result: WaccResult,
) -> Dict[str, Any]:
    """Compare project IRR against WACC hurdle rates.

    Phase 2 analysis function: Determines if project creates value.

    Args:
        project_irr: Calculated project IRR
        wacc_result: WaccResult from calculate_wacc()

    Returns:
        Dict with value creation metrics

    Logic:
        - If IRR > WACC_nominal: Project creates value
        - If IRR > WACC_prudential: Project creates value with prudential buffer
        - IRR margin = IRR - WACC
    """
    wacc_nom = wacc_result.base.wacc_nominal
    wacc_prud = wacc_result.prudential_rate

    return {
        "project_irr": project_irr,
        "wacc_nominal": wacc_nom,
        "wacc_prudential": wacc_prud,
        "irr_vs_wacc_nominal": project_irr - wacc_nom,
        "irr_vs_wacc_prudential": project_irr - wacc_prud,
        "creates_value_nominal": project_irr > wacc_nom,
        "creates_value_prudential": project_irr > wacc_prud,
        "margin_bps": (project_irr - wacc_nom) * 10000,  # basis points
    }


__all__ = [
    "WaccComponents",
    "WaccResult",
    "calculate_wacc",
    "inject_interest_into_annual_rows",
    "apply_wacc_to_npv",
    "apply_wacc_to_irr_comparison",
]
