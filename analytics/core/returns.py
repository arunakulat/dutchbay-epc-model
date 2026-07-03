"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    DUTCHBAY V14 - RETURNS MODULE                             ║
║                   Project & Equity Returns Analytics                         ║
║                                                                              ║
║  CASPER Compliance: Contract-first with Pydantic V2 outputs                  ║
║  CESSPIT Compliance: Config-driven, zero hardcoded defaults                  ║
║  GWTF Compliance: Evidence-based, delegates to finance.irr                   ║
║  CCCDIR Compliance: Single responsibility - returns calculation only         ║
║                                                                              ║
║  Author: DutchBay Analytics Team                                             ║
║  Version: 2.0.0 (Pydantic V2 Migration - Sprint 15)                          ║
║  Last Updated: 2025-12-21                                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
from math import isinf, isnan
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# GWTF: Single source of truth for IRR/NPV - delegate to finance.irr
from finance.irr import irr as _irr
from finance.irr import npv as _npv

__version__ = "2.0.0"
__author__ = "DutchBay Analytics Team"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dutchbay.analytics.core.returns")

# ═════════════════════════════════════════════════════════════════════════════
# PYDANTIC V2 CONTRACTS (CASPER Compliance)
# ═════════════════════════════════════════════════════════════════════════════


class ReturnsConfig(BaseModel):
    """
    Returns calculation configuration.

    CESSPIT: All parameters must be provided via config - no hardcoded defaults.
    """

    model_config = ConfigDict(frozen=True)

    # CAPEX configuration (required)
    capex_usd: float = Field(gt=0, description="Total CAPEX in USD")
    capex_fx_rate: float = Field(gt=0, description="LKR per USD at CAPEX")

    # Financing structure (required)
    debt_ratio: float = Field(ge=0.0, le=1.0, description="Debt ratio (0-1)")

    # Discount rates (required)
    project_discount_rate: float = Field(
        ge=0.0, le=1.0, description="Project discount rate (decimal)"
    )
    equity_discount_rate: float = Field(
        ge=0.0, le=1.0, description="Equity discount rate (decimal)"
    )

    # MIRR rates (optional, defaults to discount rates)
    finance_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Financing rate for MIRR"
    )
    reinvest_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Reinvestment rate for MIRR"
    )

    # Timing
    operation_start_year: int = Field(default=1, ge=0, description="Operations start")
    equity_start_year: int = Field(default=1, ge=0, description="Equity cashflow start")

    @field_validator("finance_rate", "reinvest_rate", mode="before")
    @classmethod
    def default_to_discount_rate(cls, v: Optional[float]) -> Optional[float]:
        """Allow None for optional rates - will be filled later."""
        return v

    @classmethod
    def from_yaml(cls, config: Dict[str, Any]) -> "ReturnsConfig":
        """
        Parse from YAML-style nested config.

        CESSPIT: Fail-fast if required keys missing.
        """
        try:
            capex_usd = float(config["capex"]["usd_total"])
            capex_fx_rate = float(config["fx"]["start_lkr_per_usd"])
            # Canonical scenarios carry gearing under 'Financing_Terms'; older or
            # lightweight configs use lowercase 'financing'. Accept either (the
            # canonical block wins) so returns analytics run on the real lender
            # scenarios, not just hand-authored test configs.
            financing = config.get("Financing_Terms")
            if not isinstance(financing, dict):
                financing = config.get("financing", {})
            debt_ratio = float(financing["debt_ratio"])
            project_dr = float(config["returns"]["project_discount_rate"])
            equity_dr = float(config["returns"]["equity_discount_rate"])

            # Optional rates
            finance_rate = config.get("returns", {}).get("finance_rate")
            reinvest_rate = config.get("returns", {}).get("reinvest_rate")

            return cls(
                capex_usd=capex_usd,
                capex_fx_rate=capex_fx_rate,
                debt_ratio=debt_ratio,
                project_discount_rate=project_dr,
                equity_discount_rate=equity_dr,
                finance_rate=finance_rate,
                reinvest_rate=reinvest_rate,
            )
        except KeyError as e:
            raise ValueError(
                f"Required config key missing for ReturnsConfig: {e}. "
                "Expected: capex.usd_total, fx.start_lkr_per_usd, "
                "Financing_Terms.debt_ratio (or financing.debt_ratio), "
                "returns.project_discount_rate, returns.equity_discount_rate"
            ) from e


class ProjectReturns(BaseModel):
    """
    Project-level returns metrics.

    CASPER: Frozen, typed contract for project returns.
    """

    model_config = ConfigDict(frozen=True)

    project_irr: Optional[float] = Field(
        default=None, description="Project IRR (decimal, e.g., 0.12 = 12%)"
    )
    project_npv: float = Field(description="Project NPV in LKR")
    project_mirr: Optional[float] = Field(default=None, description="Modified IRR")
    profitability_index: float = Field(ge=0.0, description="PV(inflows) / CAPEX")
    payback_period: Optional[int] = Field(default=None, ge=0, description="Years")

    # Full cashflow series (for audit/debugging)
    cashflows_with_capex: List[float] = Field(
        description="Full series: [-CAPEX, CF1, CF2, ...]"
    )

    # Calculation metadata (GWTF: reproducibility)
    calculations_detail: Dict[str, float] = Field(
        description="Calculation inputs and intermediate values"
    )


class EquityReturns(BaseModel):
    """
    Equity investor returns metrics.

    CASPER: Frozen, typed contract for equity returns.
    """

    model_config = ConfigDict(frozen=True)

    equity_irr: Optional[float] = Field(
        default=None, description="Equity IRR (decimal)"
    )
    equity_npv: float = Field(description="Equity NPV in LKR")
    equity_mirr: Optional[float] = Field(default=None, description="Modified IRR")
    equity_pi: float = Field(ge=0.0, description="Equity Profitability Index")
    equity_payback_period: Optional[int] = Field(
        default=None, ge=0, description="Years to recover equity"
    )

    # Cashflow series
    equity_cashflows: List[float] = Field(description="Equity CF (after debt)")
    equity_cashflows_with_investment: List[float] = Field(
        description="Full series: [-equity, CF1, CF2, ...]"
    )

    # Calculation metadata
    calculations_detail: Dict[str, float] = Field(
        description="Calculation inputs and intermediate values"
    )


class AllReturns(BaseModel):
    """
    Combined project and equity returns.

    CASPER: Single contract for complete returns analysis.
    """

    model_config = ConfigDict(frozen=True)

    project_returns: ProjectReturns
    equity_returns: EquityReturns

    # Summary KPIs
    total_capex_lkr: float = Field(description="Total CAPEX in LKR")
    debt_investment_lkr: float = Field(description="Debt portion in LKR")
    equity_investment_lkr: float = Field(description="Equity portion in LKR")
    debt_ratio: float = Field(ge=0.0, le=1.0, description="Debt / Total")
    equity_ratio: float = Field(ge=0.0, le=1.0, description="Equity / Total")

    # IRR uplift (equity leverage benefit)
    irr_uplift: float = Field(description="Equity IRR - Project IRR")


# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (Internal - CCCDIR: Clear separation)
# ═════════════════════════════════════════════════════════════════════════════


def _safe_float(value: Any, context: str = "value") -> Optional[float]:
    """
    Safe float conversion with logging.

    Returns None if conversion fails or value is NaN/Inf.
    """
    if value is None:
        return None

    try:
        f = float(value)
        if isnan(f) or isinf(f):
            logger.warning("%s is NaN or Inf, returning None", context)
            return None
        return f
    except (TypeError, ValueError) as e:
        logger.warning("Failed to convert %s to float: %s", context, e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# CORE NPV & IRR CALCULATIONS (GWTF: Delegates to finance.irr)
# ═════════════════════════════════════════════════════════════════════════════


def calculate_npv(
    cashflows: List[float],
    discount_rate: float,
    start_period: int = 0,
) -> float:
    """
    Calculate Net Present Value of a cashflow series.

    GWTF: Delegates to finance.irr.npv (single source of truth).

    Parameters
    ----------
    cashflows : list of float
        Annual cashflows (positive or negative).
    discount_rate : float
        Annual discount rate (0-1, e.g., 0.10 for 10%).
    start_period : int, default 0
        Starting period for discounting (0 = immediate).

    Returns
    -------
    float
        NPV of cashflows in same currency as cashflows.
    """
    if not cashflows:
        return 0.0

    if discount_rate < 0.0:
        logger.error("Negative discount rate %s, returning 0.0", discount_rate)
        return 0.0

    # Time-shift cashflows by prepending zeros
    if start_period > 0:
        adjusted_cashflows: List[float] = [0.0] * start_period + list(cashflows)
    else:
        adjusted_cashflows = list(cashflows)

    try:
        return float(_npv(discount_rate, adjusted_cashflows))
    except Exception as exc:
        logger.error("NPV calculation failed: %s", exc, exc_info=True)
        return 0.0


def calculate_irr(cashflows: List[float]) -> Optional[float]:
    """
    Calculate Internal Rate of Return for a cashflow series.

    GWTF: Delegates to finance.irr.irr as single implementation.

    Parameters
    ----------
    cashflows : list of float
        Cashflow series (typically: [-CAPEX, +CF1, +CF2, ...]).

    Returns
    -------
    Optional[float]
        IRR as decimal (e.g., 0.12 for 12%), or None if cannot compute.
    """
    if not cashflows or len(cashflows) < 2:
        logger.warning("IRR requires at least 2 cashflows, got %d", len(cashflows))
        return None

    try:
        value = _irr(list(cashflows))
        return _safe_float(value, context="IRR")
    except (ZeroDivisionError, OverflowError, ValueError) as exc:
        logger.warning("IRR calculation failed: %s", exc)
        return None


def calculate_mirr(
    cashflows: List[float],
    finance_rate: float,
    reinvest_rate: float,
) -> Optional[float]:
    """
    Calculate Modified Internal Rate of Return (MIRR).

    MIRR separates financing cost (negative CF) from reinvestment rate (positive CF).

    Parameters
    ----------
    cashflows : list of float
        Annual cashflows.
    finance_rate : float
        Cost of financing (for negative cashflows).
    reinvest_rate : float
        Reinvestment rate (for positive cashflows).

    Returns
    -------
    Optional[float]
        MIRR as decimal, or None if unable to calculate.
    """
    if not cashflows or len(cashflows) < 2:
        return None

    n_periods = len(cashflows)

    # PV of negative cashflows discounted at finance_rate
    pv_negative = sum(
        cf / ((1 + finance_rate) ** i) for i, cf in enumerate(cashflows) if cf < 0
    )

    # FV of positive cashflows compounded at reinvest_rate
    fv_positive = sum(
        cf * ((1 + reinvest_rate) ** (n_periods - i - 1))
        for i, cf in enumerate(cashflows)
        if cf > 0
    )

    # MIRR formula requires negative PV and positive FV
    if pv_negative >= 0 or fv_positive <= 0:
        logger.warning(
            "MIRR invalid: pv_negative=%s, fv_positive=%s", pv_negative, fv_positive
        )
        return None

    try:
        mirr = (fv_positive / abs(pv_negative)) ** (1 / (n_periods - 1)) - 1
        return _safe_float(mirr, context="MIRR")
    except (ZeroDivisionError, OverflowError) as exc:
        logger.warning("MIRR calculation failed: %s", exc)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# PROJECT RETURNS (Entire Project CFADS)
# ═════════════════════════════════════════════════════════════════════════════


def calculate_project_returns(
    cfads_series: List[float],
    config: ReturnsConfig,
) -> ProjectReturns:
    """
    Calculate returns on entire project (CFADS stream).

    CESSPIT: All parameters from config, no hardcoded defaults.
    CASPER: Returns Pydantic V2 contract.

    Parameters
    ----------
    cfads_series : list of float
        Annual CFADS (Cash Flow Available for Debt Service).
    config : ReturnsConfig
        Configuration with CAPEX, discount rates, etc.

    Returns
    -------
    ProjectReturns
        Pydantic V2 contract with all project metrics.
    """
    # Convert CAPEX to LKR
    capex_lkr = config.capex_usd * config.capex_fx_rate

    # Full cashflow series: [-CAPEX at t=0, CFADS1, CFADS2, ...]
    full_cashflows: List[float] = [-capex_lkr] + list(cfads_series)

    # Use config rates, fallback to discount rate if not specified
    finance_rate = config.finance_rate or config.project_discount_rate
    reinvest_rate = config.reinvest_rate or config.project_discount_rate

    # Core metrics. NPV discounts the SAME signed vector as the IRR — [-capex] + cfads —
    # so the initial outlay is netted (a "Net" PV must subtract the investment). Previously
    # the NPV discounted cfads_series alone (PV of inflows only), overstating it by the entire
    # capex and inflating the profitability index — and diverging from the IRR's own vector.
    project_irr = calculate_irr(full_cashflows)
    project_npv = calculate_npv(full_cashflows, config.project_discount_rate)
    project_mirr = calculate_mirr(full_cashflows, finance_rate, reinvest_rate)

    # Profitability Index = NPV / CAPEX
    # Profitability index = PV(inflows) / CAPEX (the standard PI: >1 creates value, >=0
    # always). project_npv now nets the outlay, so PV(inflows) = project_npv + capex; the PI
    # therefore equals (project_npv + capex)/capex and is unchanged by the NPV fix.
    pi = (project_npv + capex_lkr) / capex_lkr if capex_lkr > 0 else 0.0

    # Payback period: years until cumulative CFADS >= CAPEX
    payback_period: Optional[int] = None
    cumulative = 0.0
    for i, cf in enumerate(cfads_series):
        cumulative += cf
        if cumulative >= capex_lkr:
            payback_period = i + 1
            break

    return ProjectReturns(
        project_irr=project_irr,
        project_npv=project_npv,
        project_mirr=project_mirr,
        profitability_index=pi,
        payback_period=payback_period,
        cashflows_with_capex=full_cashflows,
        calculations_detail={
            "capex_lkr": capex_lkr,
            "capex_usd": config.capex_usd,
            "capex_fx_rate": config.capex_fx_rate,
            "cfads_total": sum(cfads_series),
            "cfads_avg": sum(cfads_series) / len(cfads_series) if cfads_series else 0.0,
            "project_discount_rate": config.project_discount_rate,
            "finance_rate": finance_rate,
            "reinvest_rate": reinvest_rate,
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
# EQUITY RETURNS (After Debt Service & Taxes)
# ═════════════════════════════════════════════════════════════════════════════


def calculate_equity_returns(
    cfads_series: List[float],
    debt_service_series: List[float],
    config: ReturnsConfig,
) -> EquityReturns:
    """
    Calculate returns to equity holders (after debt service).

    CESSPIT: All parameters from config.
    CASPER: Returns Pydantic V2 contract.

    Parameters
    ----------
    cfads_series : list of float
        Annual CFADS.
    debt_service_series : list of float
        Annual debt service (interest + principal).
    config : ReturnsConfig
        Configuration with equity investment, discount rates, etc.

    Returns
    -------
    EquityReturns
        Pydantic V2 contract with all equity metrics.
    """
    if len(cfads_series) != len(debt_service_series):
        raise ValueError(
            f"CFADS and debt service series length mismatch: "
            f"{len(cfads_series)} vs {len(debt_service_series)}"
        )

    # Calculate equity investment
    total_investment = config.capex_usd * config.capex_fx_rate
    equity_investment_lkr = total_investment * (1.0 - config.debt_ratio)

    # Equity cashflows = CFADS - Debt Service
    equity_cashflows: List[float] = [
        cfads - ds for cfads, ds in zip(cfads_series, debt_service_series, strict=True)
    ]

    # Full equity cashflows: [-equity_investment at t=0, ECF1, ECF2, ...]
    full_equity_cashflows: List[float] = [-equity_investment_lkr] + equity_cashflows

    # Use config rates
    finance_rate = config.finance_rate or config.equity_discount_rate
    reinvest_rate = config.reinvest_rate or config.equity_discount_rate

    # Core metrics. NPV discounts the SAME signed vector as the IRR — [-equity] + ECF — so
    # the equity outlay is netted (see calculate_project_returns). Previously it discounted
    # equity_cashflows alone, overstating equity_npv by the whole equity investment and
    # inflating equity_pi.
    equity_irr = calculate_irr(full_equity_cashflows)
    equity_npv = calculate_npv(full_equity_cashflows, config.equity_discount_rate)
    equity_mirr = calculate_mirr(full_equity_cashflows, finance_rate, reinvest_rate)

    # Equity Profitability Index
    # Standard PI = PV(equity CF) / equity investment (>=0); equity_npv now nets the outlay,
    # so this equals (equity_npv + equity_investment)/equity_investment.
    equity_pi = (
        (equity_npv + equity_investment_lkr) / equity_investment_lkr
        if equity_investment_lkr > 0.0
        else 0.0
    )

    # Equity payback period
    payback_period: Optional[int] = None
    cumulative = 0.0
    for i, cf in enumerate(equity_cashflows):
        cumulative += cf
        if cumulative >= equity_investment_lkr:
            payback_period = i + 1
            break

    return EquityReturns(
        equity_irr=equity_irr,
        equity_npv=equity_npv,
        equity_mirr=equity_mirr,
        equity_pi=equity_pi,
        equity_payback_period=payback_period,
        equity_cashflows=equity_cashflows,
        equity_cashflows_with_investment=full_equity_cashflows,
        calculations_detail={
            "equity_investment_lkr": equity_investment_lkr,
            "total_investment_lkr": total_investment,
            "debt_ratio": config.debt_ratio,
            "equity_cashflows_total": sum(equity_cashflows),
            "equity_cashflows_avg": (
                sum(equity_cashflows) / len(equity_cashflows)
                if equity_cashflows
                else 0.0
            ),
            "equity_discount_rate": config.equity_discount_rate,
            "finance_rate": finance_rate,
            "reinvest_rate": reinvest_rate,
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE RETURNS SUMMARY
# ═════════════════════════════════════════════════════════════════════════════


def summarize_all_returns(
    cfads_series: List[float],
    debt_service_series: List[float],
    config: ReturnsConfig,
) -> AllReturns:
    """
    Calculate all project and equity returns metrics.

    CESSPIT: Fully config-driven.
    CASPER: Returns Pydantic V2 contract.

    Parameters
    ----------
    cfads_series : list of float
        Annual CFADS.
    debt_service_series : list of float
        Annual debt service.
    config : ReturnsConfig
        Complete configuration.

    Returns
    -------
    AllReturns
        Pydantic V2 contract with project, equity, and summary metrics.
    """
    # Calculate project and equity returns
    project_returns = calculate_project_returns(cfads_series, config)
    equity_returns = calculate_equity_returns(cfads_series, debt_service_series, config)

    # Investment breakdown
    total_investment = config.capex_usd * config.capex_fx_rate
    debt_investment = total_investment * config.debt_ratio
    equity_investment = total_investment * (1.0 - config.debt_ratio)

    # IRR uplift (leverage benefit)
    project_irr_val = project_returns.project_irr or 0.0
    equity_irr_val = equity_returns.equity_irr or 0.0
    irr_uplift = equity_irr_val - project_irr_val

    return AllReturns(
        project_returns=project_returns,
        equity_returns=equity_returns,
        total_capex_lkr=total_investment,
        debt_investment_lkr=debt_investment,
        equity_investment_lkr=equity_investment,
        debt_ratio=config.debt_ratio,
        equity_ratio=1.0 - config.debt_ratio,
        irr_uplift=irr_uplift,
    )


# ═════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Contracts
    "ReturnsConfig",
    "ProjectReturns",
    "EquityReturns",
    "AllReturns",
    # Functions
    "calculate_npv",
    "calculate_irr",
    "calculate_mirr",
    "calculate_project_returns",
    "calculate_equity_returns",
    "summarize_all_returns",
]
