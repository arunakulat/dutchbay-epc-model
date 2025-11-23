"""WACC Calculation Module for DutchBay V14 Project Finance.

COMPLIANCE:
-----------
- Project-specific WACC using CAPM for cost of equity.
- Asset beta de-levering and re-levering at target capital structure.
- Nominal and real after-tax WACC.
- Prudential WACC for conservative valuation.
- Full component breakdown for lender/equity disclosure.

FEATURES:
---------
- CAPM cost of equity: Rf + β_equity × MRP.
- Beta re-levering: β_equity = β_asset × [1 + (1 - T) × D/E].
- After-tax WACC: (E/V × Ke) + (D/V × Kd × (1 - T)).
- Real WACC: [(1 + WACC_nominal) / (1 + inflation)] - 1.
- Prudential adjustment: WACC + X bps for conservative NPV.

MODES:
------
- Simple / fixed:
  wacc:
    discount_rate: 12.0  # percent or decimal
    prudential_spread_bps: 100  # default 100 bps

- CAPM:
  wacc:
    mode: capm
    risk_free: 5.0  # or risk_free_rate
    market_premium: 6.0  # or market_risk_premium
    beta: 0.8  # or asset_beta
    # Capital structure:
    gearing: 60.0  # D/V, percent or decimal
    # or
    target_debt_to_equity: 1.5  # D/E
    # Cost of debt:
    cost_of_debt: 8.0  # or base_rate + margin
    # Tax:
    tax_rate: 24.0  # or tax.corporate_tax_rate(_pct)
    # Optional:
    inflation_rate: 2.0
    prudential_spread_bps: 100
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Helper utilities
# =============================================================================


def _as_float_or_none(value: Any) -> Optional[float]:
    """Return float(value) or None."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_to_decimal(raw: Optional[float]) -> Optional[float]:
    """
    Interpret a numeric as a percentage if > 1.0, otherwise as a decimal:
        24 -> 0.24
        0.24 -> 0.24
    """
    if raw is None:
        return None
    if raw > 1.0:
        return raw / 100.0
    return raw


def get_nested(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Safely navigate nested dictionaries by list of keys."""
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


# =============================================================================
# CAPM Cost of Equity
# =============================================================================


def calculate_cost_of_equity_capm(
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float,
) -> float:
    """Ke = Rf + β × MRP."""
    return risk_free_rate + (beta * market_risk_premium)


def relever_beta(
    asset_beta: float,
    debt_to_equity: float,
    tax_rate: float,
) -> float:
    """β_equity = β_asset × [1 + (1 - T) × D/E]."""
    return asset_beta * (1.0 + (1.0 - tax_rate) * debt_to_equity)


# =============================================================================
# After-Tax WACC
# =============================================================================


def calculate_after_tax_wacc(
    cost_of_equity: float,
    cost_of_debt: float,
    equity_to_value: float,
    debt_to_value: float,
    tax_rate: float,
) -> float:
    """WACC = (E/V × Ke) + (D/V × Kd × (1 - T))."""
    equity_component = equity_to_value * cost_of_equity
    debt_component = debt_to_value * cost_of_debt * (1.0 - tax_rate)
    return equity_component + debt_component


def calculate_real_wacc(
    wacc_nominal: float,
    inflation_rate: float,
) -> float:
    """WACC_real = [(1 + WACC_nominal) / (1 + inflation)] - 1."""
    return ((1.0 + wacc_nominal) / (1.0 + inflation_rate)) - 1.0


# =============================================================================
# Pure WACC builder
# =============================================================================


def build_wacc(
    risk_free_rate: float,
    asset_beta: float,
    market_risk_premium: float,
    debt_to_value: float,
    cost_of_debt: float,
    tax_rate: float,
    inflation_rate: Optional[float] = None,
    prudential_spread_bps: int = 100,
) -> Dict[str, Any]:
    """
    Pure WACC builder from explicit inputs.

    Parameters
    ----------
    risk_free_rate : float
    asset_beta : float
    market_risk_premium : float
    debt_to_value : float
        D/V in decimal (0–1).
    cost_of_debt : float
        Pre-tax cost of debt (decimal).
    tax_rate : float
        Corporate tax rate (decimal).
    inflation_rate : Optional[float]
        Expected inflation (decimal).
    prudential_spread_bps : int
        Prudential bump in basis points.

    Returns
    -------
    Dict[str, Any]
        WACC components dict compatible with WaccComponents dataclass.
    """
    if not (0.0 <= debt_to_value < 1.0):
        raise ValueError(f"Invalid debt_to_value: {debt_to_value}")

    equity_to_value = 1.0 - debt_to_value
    d_to_e = debt_to_value / equity_to_value if equity_to_value > 0 else 0.0

    equity_beta = relever_beta(asset_beta, d_to_e, tax_rate)
    cost_of_equity = calculate_cost_of_equity_capm(
        risk_free_rate, equity_beta, market_risk_premium
    )

    wacc_nominal = calculate_after_tax_wacc(
        cost_of_equity, cost_of_debt, equity_to_value, debt_to_value, tax_rate
    )

    wacc_real: Optional[float] = None
    if inflation_rate is not None and inflation_rate > 0:
        wacc_real = calculate_real_wacc(wacc_nominal, inflation_rate)

    prudential_spread = prudential_spread_bps / 10000.0
    wacc_prudential = wacc_nominal + prudential_spread

    return {
        "wacc_nominal": wacc_nominal,
        "wacc_real": wacc_real,
        "wacc_prudential": wacc_prudential,
        "risk_free_rate": risk_free_rate,
        "market_risk_premium": market_risk_premium,
        "asset_beta": asset_beta,
        "target_debt_to_equity": d_to_e,
        "target_debt_to_value": debt_to_value,
        "target_equity_to_value": equity_to_value,
        "cost_of_debt_pretax": cost_of_debt,
        "cost_of_debt_aftertax": cost_of_debt * (1.0 - tax_rate),
        "equity_beta_levered": equity_beta,
        "cost_of_equity": cost_of_equity,
        "tax_rate": tax_rate,
        "inflation_rate": inflation_rate,
        "prudential_spread_bps": prudential_spread_bps,
    }


# =============================================================================
# WACC from Config
# =============================================================================


def compute_wacc_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute project-specific WACC from scenario config.

    Returns a dict compatible with contracts_v14.WaccComponents.
    If WACC block is absent, returns {} and caller should fall back.
    """
    wacc_cfg = config.get("wacc", {})
    if not wacc_cfg:
        # No WACC config – use default discount rate upstream.
        logger.warning("No 'wacc' block in config; evaluator will use default rate.")
        return {}

    # Simple / discount-rate-only mode
    dr_raw = wacc_cfg.get("discount_rate")
    simple_mode = wacc_cfg.get("mode", "").lower() in {"", "simple", "fixed"}

    if dr_raw is not None and simple_mode:
        discount_rate = _pct_to_decimal(_as_float_or_none(dr_raw))
        if discount_rate is None or discount_rate <= 0:
            raise ValueError(f"Invalid wacc.discount_rate: {dr_raw}")

        prudential_bps = int(wacc_cfg.get("prudential_spread_bps", 100))
        prudential_spread = prudential_bps / 10000.0

        return {
            "mode": "fixed",
            "wacc_nominal": discount_rate,
            "wacc_real": None,
            "wacc_prudential": discount_rate + prudential_spread,
            "risk_free_rate": 0.0,
            "market_risk_premium": 0.0,
            "asset_beta": 0.0,
            "target_debt_to_equity": 0.0,
            "target_debt_to_value": 0.0,
            "target_equity_to_value": 1.0,
            "cost_of_debt_pretax": 0.0,
            "cost_of_debt_aftertax": 0.0,
            "equity_beta_levered": 0.0,
            "cost_of_equity": discount_rate,
            "tax_rate": 0.0,
            "inflation_rate": None,
            "prudential_spread_bps": prudential_bps,
        }

    mode = wacc_cfg.get("mode", "capm").lower()
    if mode != "capm":
        raise ValueError(f"Unknown wacc.mode: '{mode}'. Use 'capm' or 'fixed/simple'.")

    # CAPM inputs (dual naming)
    rf_raw = wacc_cfg.get("risk_free_rate", wacc_cfg.get("risk_free"))
    mrp_raw = wacc_cfg.get("market_risk_premium", wacc_cfg.get("market_premium"))
    asset_beta_raw = wacc_cfg.get("asset_beta", wacc_cfg.get("beta"))

    if rf_raw is None:
        raise ValueError("wacc.risk_free or wacc.risk_free_rate required for CAPM mode")
    if mrp_raw is None:
        raise ValueError(
            "wacc.market_premium or wacc.market_risk_premium required for CAPM mode"
        )
    if asset_beta_raw is None:
        raise ValueError("wacc.beta or wacc.asset_beta required for CAPM mode")

    risk_free_rate_opt: Optional[float] = _pct_to_decimal(_as_float_or_none(rf_raw))
    market_risk_premium_opt: Optional[float] = _pct_to_decimal(_as_float_or_none(mrp_raw))
    asset_beta_opt: Optional[float] = _as_float_or_none(asset_beta_raw)

    if risk_free_rate_opt is None or risk_free_rate_opt < 0:
        raise ValueError(f"Invalid risk_free: {rf_raw}")
    if market_risk_premium_opt is None or market_risk_premium_opt < 0:
        raise ValueError(f"Invalid market_premium: {mrp_raw}")
    if asset_beta_opt is None or asset_beta_opt < 0:
        raise ValueError(f"Invalid beta: {asset_beta_raw}")

    # Type narrowing: after validation, assign to non-Optional
    risk_free_rate: float = risk_free_rate_opt
    market_risk_premium: float = market_risk_premium_opt
    asset_beta: float = asset_beta_opt

    # Capital structure
    d_to_e_raw = wacc_cfg.get("target_debt_to_equity")
    gearing_raw = wacc_cfg.get("target_gearing", wacc_cfg.get("gearing"))

    d_to_v: float
    d_to_e: float

    if d_to_e_raw is not None:
        d_to_e_opt: Optional[float] = _as_float_or_none(d_to_e_raw)
        if d_to_e_opt is None or d_to_e_opt < 0:
            raise ValueError(f"Invalid target_debt_to_equity: {d_to_e_raw}")
        d_to_e = d_to_e_opt
        d_to_v = d_to_e / (1.0 + d_to_e)
    elif gearing_raw is not None:
        d_to_v_opt: Optional[float] = _pct_to_decimal(_as_float_or_none(gearing_raw))
        if d_to_v_opt is None or not (0 <= d_to_v_opt < 1):
            raise ValueError(f"Invalid gearing (D/V): {gearing_raw}")
        d_to_v = d_to_v_opt
        d_to_e = d_to_v / (1.0 - d_to_v) if d_to_v < 1.0 else 0.0
    else:
        raise ValueError("wacc: requires either target_debt_to_equity or gearing/target_gearing")

    # Cost of debt
    kd_raw = wacc_cfg.get("cost_of_debt")
    if kd_raw is not None:
        cost_of_debt_opt: Optional[float] = _pct_to_decimal(_as_float_or_none(kd_raw))
        if cost_of_debt_opt is None or cost_of_debt_opt < 0:
            raise ValueError(f"Invalid cost_of_debt: {kd_raw}")
        cost_of_debt: float = cost_of_debt_opt
    else:
        base_rate_raw = wacc_cfg.get("base_rate")
        margin_raw = wacc_cfg.get("margin")
        if base_rate_raw is None or margin_raw is None:
            raise ValueError(
                "wacc: requires either cost_of_debt or (base_rate + margin) for CAPM mode"
            )
        base_rate_opt: Optional[float] = _pct_to_decimal(_as_float_or_none(base_rate_raw))
        margin_opt: Optional[float] = _pct_to_decimal(_as_float_or_none(margin_raw))
        if base_rate_opt is None or base_rate_opt < 0:
            raise ValueError(f"Invalid base_rate: {base_rate_raw}")
        if margin_opt is None or margin_opt < 0:
            raise ValueError(f"Invalid margin: {margin_raw}")
        cost_of_debt = base_rate_opt + margin_opt

    # Tax rate
    tax_rate_raw = wacc_cfg.get("tax_rate")
    if tax_rate_raw is None:
        tax_rate_raw = get_nested(config, ["tax", "corporate_tax_rate_pct"])
    if tax_rate_raw is None:
        tax_rate_raw = get_nested(config, ["tax", "corporate_tax_rate"])
    if tax_rate_raw is None:
        raise ValueError("wacc.tax_rate or tax.corporate_tax_rate(_pct) required")

    tax_rate_opt: Optional[float] = _pct_to_decimal(_as_float_or_none(tax_rate_raw))
    if tax_rate_opt is None or not (0 <= tax_rate_opt <= 1):
        raise ValueError(f"Invalid tax_rate: {tax_rate_raw}")
    tax_rate: float = tax_rate_opt

    # Optional inflation - FIX FOR LINE 312: Explicit type annotation
    inflation_raw = wacc_cfg.get("inflation_rate")
    inflation_rate: Optional[float] = None
    if inflation_raw is not None:
        inflation_rate = _pct_to_decimal(_as_float_or_none(inflation_raw))

    prudential_bps = int(wacc_cfg.get("prudential_spread_bps", 100))

    components = build_wacc(
        risk_free_rate=risk_free_rate,
        asset_beta=asset_beta,
        market_risk_premium=market_risk_premium,
        debt_to_value=d_to_v,
        cost_of_debt=cost_of_debt,
        tax_rate=tax_rate,
        inflation_rate=inflation_rate,
        prudential_spread_bps=prudential_bps,
    )

    components["mode"] = "capm"
    logger.info(
        "WACC calculated: nominal=%.2f%%, real=%s, prudential=%.2f%%",
        components["wacc_nominal"] * 100,
        f"{components['wacc_real']*100:.2f}%" if components["wacc_real"] is not None else "N/A",
        components["wacc_prudential"] * 100,
    )

    return components


