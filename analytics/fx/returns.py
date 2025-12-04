from __future__ import annotations

"""
Project & Equity Returns Module – V14-compliant

- IRR/NPV logic is delegated to finance.irr (single source of truth).
- This module focuses on *using* IRR/NPV to produce project/equity returns,
  not on implementing the IRR algorithm itself.
"""

import logging
from math import isinf, isnan
from typing import Any, Dict, List, Optional

from finance.irr import irr as _irr
from finance.irr import npv as _npv

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dutchbay.analytics.fx.returns")

__all__ = [
    "calculate_npv",
    "calculate_irr",
    "calculate_mirr",
    "calculate_project_returns",
    "calculate_equity_returns",
    "summarize_all_returns",
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _as_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    """Safe float conversion with default fallback."""
    try:
        return float(x) if x is not None else default
    except Exception:
        return default


def _as_int(x: Any, default: int = 0) -> int:
    """Safe integer conversion with default fallback."""
    try:
        return int(x)
    except Exception:
        return default


def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    """Safely traverse nested dictionary."""
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# ============================================================================
# CORE NPV & IRR CALCULATIONS (WRAPPERS AROUND finance.irr)
# ============================================================================


def calculate_npv(
    cashflows: List[float],
    discount_rate: float,
    start_period: int = 0,
) -> float:
    """
    Calculate Net Present Value of a cashflow series.

    Notes
    -----
    - Delegates core NPV calculation to finance.irr.npv.
    - start_period is implemented by padding with zero-cash periods,
      which is mathematically equivalent to shifting the discounting origin.

    Parameters
    ----------
    cashflows : list of float
        Annual cashflows (positive or negative).
    discount_rate : float
        Annual discount rate (0–1, e.g. 0.10 for 10%).
    start_period : int, default 0
        Starting period for discounting.

    Returns
    -------
    float
        NPV of cashflows.
    """
    if not cashflows or discount_rate < -1.0:
        return 0.0

    if start_period < 0:
        logger.warning("start_period < 0; treating as 0 instead of %r", start_period)
        start_period = 0

    # Shift in time by inserting zero cashflows at the front.
    # NPV(rate, [0, 0, ..., cf1, cf2, ...]) == discounted series starting later.
    adjusted_cashflows: List[float] = [0.0] * start_period + list(cashflows)

    try:
        return float(_npv(discount_rate, adjusted_cashflows))
    except Exception as exc:  # pragma: no cover - ultra-defensive
        logger.error("NPV calculation failed: %s", exc)
        return 0.0


def calculate_irr(cashflows: List[float]) -> Optional[float]:
    """
    Calculate Internal Rate of Return for a cashflow series.

    Notes
    -----
    - Delegates to finance.irr.irr as the single IRR implementation.
    - Returns None if IRR cannot be computed or is not finite.

    Parameters
    ----------
    cashflows : list of float
        Cashflow series, typically with a negative initial investment and
        subsequent positive cashflows.

    Returns
    -------
    Optional[float]
        IRR as a decimal (e.g. 0.12 for 12%), or None on failure.
    """
    if not cashflows or len(cashflows) < 2:
        return None

    try:
        value = _irr(list(cashflows))
    except (ZeroDivisionError, OverflowError, ValueError) as exc:
        logger.warning("IRR calculation failed for cashflows %r: %s", cashflows, exc)
        return None

    if value is None:
        return None

    try:
        f = float(value)
    except (TypeError, ValueError):
        return None

    if isnan(f) or isinf(f):
        return None

    return f


def calculate_mirr(
    cashflows: List[float],
    finance_rate: float = 0.10,
    reinvest_rate: float = 0.12,
) -> Optional[float]:
    """
    Calculate Modified Internal Rate of Return (MIRR).

    MIRR accounts for cost of financing (negative CF) and reinvestment rate
    (positive CF).

    Parameters
    ----------
    cashflows : list of float
        Annual cashflows.
    finance_rate : float, default 0.10
        Cost of financing rate (for negative cashflows).
    reinvest_rate : float, default 0.12
        Reinvestment rate (for positive cashflows).

    Returns
    -------
    Optional[float]
        MIRR as decimal, or None if unable to calculate.
    """
    if not cashflows or len(cashflows) < 2:
        return None

    n_periods = len(cashflows)

    # Separate positive and negative cashflows
    pv_negative = 0.0
    fv_positive = 0.0

    for i, cf in enumerate(cashflows):
        if cf < 0:
            pv_negative += cf / ((1 + finance_rate) ** i)
        else:
            fv_positive += cf * ((1 + reinvest_rate) ** (n_periods - i - 1))

    # Avoid division by zero or invalid MIRR inputs
    if pv_negative >= 0 or fv_positive <= 0:
        return None

    try:
        mirr = (fv_positive / abs(pv_negative)) ** (1 / (n_periods - 1)) - 1
        if isnan(mirr) or isinf(mirr):
            return None
        return float(mirr)
    except Exception:
        return None


# ============================================================================
# PROJECT RETURNS (Entire Project CFADS)
# ============================================================================


def calculate_project_returns(
    cfads_series: List[float],
    capex_usd: float,
    capex_fx_rate: float,
    project_discount_rate: float = 0.10,
    finance_rate: float = 0.10,
    reinvest_rate: Optional[float] = None,
    operation_start_year: int = 1,
) -> Dict[str, Any]:
    """
    Calculate returns on entire project (CFADS stream).

    Project returns measure value creation on ALL capital invested,
    regardless of debt/equity split. Used for project-level decisions.
    """
    if reinvest_rate is None:
        reinvest_rate = project_discount_rate

    # Convert CAPEX to LKR
    capex_lkr = capex_usd * capex_fx_rate

    # Full cashflow series with CAPEX at t=0
    full_cashflows: List[float] = [-capex_lkr] + list(cfads_series)

    # Core project metrics
    project_irr = calculate_irr(full_cashflows)
    project_npv = calculate_npv(
        cfads_series,
        project_discount_rate,
        start_period=operation_start_year,
    )
    project_mirr = calculate_mirr(full_cashflows, finance_rate, reinvest_rate)

    # Profitability Index = NPV / CAPEX
    pi = project_npv / capex_lkr if capex_lkr > 0 else 0.0

    # Payback period: years until cumulative CFADS >= CAPEX
    payback_period: Optional[int] = None
    cumulative = 0.0
    for i, cf in enumerate(cfads_series):
        cumulative += cf
        if cumulative >= capex_lkr:
            payback_period = i + 1
            break

    return {
        "project_irr": project_irr,
        "project_npv": project_npv,
        "project_mirr": project_mirr,
        "profitability_index": pi,
        "payback_period": payback_period,
        "cashflows_with_capex": full_cashflows,
        "calculations_detail": {
            "capex_lkr": capex_lkr,
            "capex_usd": capex_usd,
            "cfads_total": sum(cfads_series),
            "cfads_avg": (
                sum(cfads_series) / len(cfads_series) if cfads_series else 0.0
            ),
            "project_discount_rate": project_discount_rate,
            "finance_rate": finance_rate,
            "reinvest_rate": reinvest_rate,
        },
    }


# ============================================================================
# EQUITY RETURNS (After Debt Service & Taxes)
# ============================================================================


def calculate_equity_returns(
    cfads_series: List[float],
    debt_service_series: List[float],
    equity_investment_lkr: float,
    equity_discount_rate: float = 0.12,
    finance_rate: float = 0.10,
    reinvest_rate: Optional[float] = None,
    equity_start_year: int = 1,
) -> Dict[str, Any]:
    """
    Calculate returns to equity holders (after debt service).

    Equity returns measure value creation on equity capital only.
    Used for equity investor decisions and board reporting.

    Formula
    -------
    Equity cashflow = CFADS - Debt Service (interest + principal)
    """
    if reinvest_rate is None:
        reinvest_rate = equity_discount_rate

    if len(cfads_series) != len(debt_service_series):
        raise ValueError("CFADS and debt service series must have same length")

    # Equity cashflows = CFADS - Debt Service
    equity_cashflows: List[float] = [
        cfads - ds for cfads, ds in zip(cfads_series, debt_service_series)
    ]

    # Initial equity at t=0
    full_equity_cashflows: List[float] = [-equity_investment_lkr] + equity_cashflows

    # Core equity metrics
    equity_irr = calculate_irr(full_equity_cashflows)
    equity_npv = calculate_npv(
        equity_cashflows,
        equity_discount_rate,
        start_period=equity_start_year,
    )
    equity_mirr = calculate_mirr(full_equity_cashflows, finance_rate, reinvest_rate)

    # Equity Profitability Index = NPV / Equity Investment
    equity_pi = (
        equity_npv / equity_investment_lkr if equity_investment_lkr > 0.0 else 0.0
    )

    # Equity payback period
    payback_period: Optional[int] = None
    cumulative = 0.0
    for i, cf in enumerate(equity_cashflows):
        cumulative += cf
        if cumulative >= equity_investment_lkr:
            payback_period = i + 1
            break

    return {
        "equity_irr": equity_irr,
        "equity_npv": equity_npv,
        "equity_mirr": equity_mirr,
        "equity_pi": equity_pi,
        "equity_payback_period": payback_period,
        "equity_cashflows": equity_cashflows,
        "equity_cashflows_with_investment": full_equity_cashflows,
        "calculations_detail": {
            "equity_investment_lkr": equity_investment_lkr,
            "equity_cashflows_total": sum(equity_cashflows),
            "equity_cashflows_avg": (
                sum(equity_cashflows) / len(equity_cashflows)
                if equity_cashflows
                else 0.0
            ),
            "equity_discount_rate": equity_discount_rate,
            "finance_rate": finance_rate,
            "reinvest_rate": reinvest_rate,
        },
    }


# ============================================================================
# COMPREHENSIVE RETURNS SUMMARY
# ============================================================================


def summarize_all_returns(
    p: Dict[str, Any],
    cfads_series: List[float],
    debt_service_series: List[float],
) -> Dict[str, Any]:
    """
    Calculate all project and equity returns metrics from a YAML-style config.
    """
    # Extract parameters from YAML/config
    capex_usd = (
        _as_float(_get(p, ["capex", "usd_total"], 150_000_000.0)) or 150_000_000.0
    )
    capex_fx = _as_float(_get(p, ["fx", "start_lkr_per_usd"], 300.0)) or 300.0

    debt_ratio = _as_float(_get(p, ["financing", "debt_ratio"], 0.70)) or 0.70
    project_discount_rate = (
        _as_float(_get(p, ["returns", "project_discount_rate"], 0.10)) or 0.10
    )
    equity_discount_rate = (
        _as_float(_get(p, ["returns", "equity_discount_rate"], 0.12)) or 0.12
    )

    total_investment = capex_usd * capex_fx
    debt_investment = total_investment * debt_ratio
    equity_investment = total_investment * (1.0 - debt_ratio)

    # Project-level returns
    project_returns = calculate_project_returns(
        cfads_series=cfads_series,
        capex_usd=capex_usd,
        capex_fx_rate=capex_fx,
        project_discount_rate=project_discount_rate,
        finance_rate=project_discount_rate,
        reinvest_rate=equity_discount_rate,
    )

    # Equity-level returns
    equity_returns = calculate_equity_returns(
        cfads_series=cfads_series,
        debt_service_series=debt_service_series,
        equity_investment_lkr=equity_investment,
        equity_discount_rate=equity_discount_rate,
        finance_rate=project_discount_rate,
        reinvest_rate=equity_discount_rate,
    )

    return {
        "project_returns": project_returns,
        "equity_returns": equity_returns,
        "summary": {
            "total_capex_lkr": total_investment,
            "debt_investment_lkr": debt_investment,
            "equity_investment_lkr": equity_investment,
            "debt_ratio": debt_ratio,
            "equity_ratio": 1.0 - debt_ratio,
            "project_irr": project_returns.get("project_irr"),
            "project_npv": project_returns.get("project_npv"),
            "equity_irr": equity_returns.get("equity_irr"),
            "equity_npv": equity_returns.get("equity_npv"),
            "irr_uplift": (
                (equity_returns.get("equity_irr", 0.0) or 0.0)
                - (project_returns.get("project_irr", 0.0) or 0.0)
            ),
        },
    }
