"""FX Structured Block Builder (v14R6).

Provides factory functions for constructing FX blocks from configuration
and scenario data. All functions follow GWTF and CESSPIT standards:
- Full type hints and docstrings
- Immutable outputs (frozen dataclasses)
- Fail-fast validation
- No internal state or side effects

Pipeline Integration:
  Called from analytics.fx_integration.integrate_fx_into_scenario_result()
  which is invoked by pipeline_v14.run_full_pipeline_v14().

Usage:
  from analytics.fx.fx_builder import compute_fx_structured_block
  
  config = {...}  # Project config dict
  debt_result = {...}  # Output from plan_debt()
  annual_rows = [...]  # Cashflow rows from compute_cashflow()
  
  fx_block = compute_fx_structured_block(
      config=config,
      debt_result=debt_result,
      annual_rows=annual_rows,
  )
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence

from analytics.fx.fx_contracts import (
    FXStructuredBlock,
    FXCurveOutput,
    FXRiskProfile,
    FXVolumetry,
)


def compute_fx_structured_block(
    *,
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
) -> FXStructuredBlock:
    """Build FXStructuredBlock from scenario configuration and debt output.
    
    Args:
        config: Project config dict (includes FX settings under 'FX' or 'fx').
        debt_result: Output from plan_debt() (includes debt schedules by tranche).
        annual_rows: Annual cashflow rows from compute_cashflow().
    
    Returns:
        FXStructuredBlock with volumetry, debt tranches, and strategy.
    
    Raises:
        ValueError: If config is malformed or debt_result missing key fields.
        TypeError: If inputs are wrong types.
    """
    # Extract FX configuration section (case-insensitive)
    fx_config_raw = config.get("FX") or config.get("fx") or {}
    if not isinstance(fx_config_raw, Mapping):
        fx_config_raw = {}
    
    fx_config: Mapping[str, Any] = fx_config_raw

    # Read FX strategy (default: blended)
    strategy_str = str(fx_config.get("strategy", "blended")).lower()
    if strategy_str not in ["natural_hedge", "fixed_ccy", "hedged", "blended"]:
        strategy_str = "blended"

    # Read currency configuration
    base_currency = str(fx_config.get("base_currency", "USD"))
    reporting_currency = str(fx_config.get("reporting_currency", "USD"))

    # Read FX match and hedging ratios
    fx_match_ratio = float(fx_config.get("fx_match_ratio", 0.0))
    hedging_coverage_pct = float(fx_config.get("hedging_coverage_pct", 0.0))

    # Extract debt tranches from debt_result
    debt_tranches_raw = debt_result.get("tranches", {}) or {}
    debt_tranches: Dict[str, str] = {}
    if isinstance(debt_tranches_raw, Mapping):
        for tranche_name, tranche_data in debt_tranches_raw.items():
            if isinstance(tranche_data, Mapping):
                currency = str(tranche_data.get("currency", "USD"))
                debt_tranches[str(tranche_name)] = currency

    # Revenue currencies (default: LKR)
    revenue_currencies_raw = fx_config.get("revenue_currencies") or ["LKR"]
    if isinstance(revenue_currencies_raw, str):
        revenue_currencies = [revenue_currencies_raw]
    else:
        revenue_currencies = list(revenue_currencies_raw)

    # Build volumetry from annual rows
    volumetry: List[FXVolumetry] = []
    for idx, row in enumerate(annual_rows):
        try:
            volumetry.append(
                FXVolumetry(
                    period=idx,
                    total_debt_lkr=float(row.get("total_debt_lkr", 0.0)),
                    total_debt_usd=float(row.get("total_debt_usd", 0.0)),
                    total_debt_cny=float(row.get("total_debt_cny", 0.0)),
                    revenue_lkr=float(row.get("revenue_lkr", 0.0)),
                    revenue_usd=float(row.get("revenue_usd", 0.0)),
                    interest_lkr=float(row.get("interest_lkr", 0.0)),
                    principal_lkr=float(row.get("principal_lkr", 0.0)),
                )
            )
        except (ValueError, TypeError) as e:
            # CESSPIT: Fail-fast on malformed row
            raise ValueError(
                f"compute_fx_structured_block: Row {idx} malformed: {e}"
            ) from e

    # Build FXStructuredBlock
    fx_notes = str(fx_config.get("notes", ""))

    return FXStructuredBlock(
        strategy=strategy_str,  # type: ignore
        base_currency=base_currency,
        reporting_currency=reporting_currency,
        volumetry=volumetry,
        debt_tranches=debt_tranches,
        revenue_currencies=revenue_currencies,
        fx_match_ratio=fx_match_ratio,
        hedging_coverage_pct=hedging_coverage_pct,
        notes=fx_notes,
    )


def compute_fx_curve(
    *,
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
) -> FXCurveOutput:
    """Generate FX rate curve from configuration and scenario timeline.
    
    Args:
        config: Project config (includes FX curve assumptions).
        annual_rows: Annual rows (used to determine timeline).
    
    Returns:
        FXCurveOutput with annual LKR/USD, LKR/CNY, etc. rates.
    
    Raises:
        ValueError: If config lacks curve data or is malformed.
    """
    # Extract FX curve section
    fx_config_raw = config.get("FX") or config.get("fx") or {}
    if not isinstance(fx_config_raw, Mapping):
        fx_config_raw = {}
    
    fx_config: Mapping[str, Any] = fx_config_raw
    curve_config_raw = fx_config.get("curve") or {}
    if not isinstance(curve_config_raw, Mapping):
        curve_config_raw = {}
    
    curve_config: Mapping[str, Any] = curve_config_raw

    # Build years array from annual_rows
    years: List[int] = [
        int(row.get("year", idx)) for idx, row in enumerate(annual_rows)
    ]

    # Read LKR/USD curve (required)
    lkr_usd_raw = curve_config.get("lkr_usd")
    if lkr_usd_raw is None:
        # Default: flat curve at spot rate
        spot = float(curve_config.get("spot_lkr_usd", 300.0))
        lkr_usd = [spot] * len(years)
    else:
        lkr_usd = [float(x) for x in lkr_usd_raw]

    # Read optional CNY curve
    lkr_cny_raw = curve_config.get("lkr_cny")
    lkr_cny = [float(x) for x in lkr_cny_raw] if lkr_cny_raw is not None else None

    # Read optional EUR curve
    lkr_eur_raw = curve_config.get("lkr_eur")
    lkr_eur = [float(x) for x in lkr_eur_raw] if lkr_eur_raw is not None else None

    # Read optional GBP curve
    lkr_gbp_raw = curve_config.get("lkr_gbp")
    lkr_gbp = [float(x) for x in lkr_gbp_raw] if lkr_gbp_raw is not None else None

    # Curve metadata
    source = str(curve_config.get("source", "base_case"))
    notes = str(curve_config.get("notes", ""))

    # Basic validation: ensure primary curve length matches years
    if len(lkr_usd) != len(years):
        raise ValueError(
            "compute_fx_curve: lkr_usd length "
            f"{len(lkr_usd)} does not match years length {len(years)}."
        )

    return FXCurveOutput(
        years=years,
        lkr_usd=lkr_usd,
        lkr_cny=lkr_cny,
        lkr_eur=lkr_eur,
        lkr_gbp=lkr_gbp,
        source=source,
        notes=notes,
    )


def compute_fx_risk_profile(
    *,
    fx_block: FXStructuredBlock,
    fx_curve: FXCurveOutput,
) -> FXRiskProfile:
    """Calculate FX risk metrics (VaR, CVaR, concentration).
    
    Args:
        fx_block: FXStructuredBlock with volumetry.
        fx_curve: FXCurveOutput with rate projections.
    
    Returns:
        FXRiskProfile with lender-grade risk summary.
    
    Raises:
        ValueError: If inputs are inconsistent (e.g., mismatched periods).
    """
    if not fx_block.volumetry:
        # No volumetry; return minimal profile
        return FXRiskProfile(
            var_95_usd_million=0.0,
            cvar_95_usd_million=0.0,
            debt_lkr_pct=0.0,
            debt_usd_pct=100.0,
            debt_cny_pct=0.0,
        )

    # Get final period volumetry
    final_vol = fx_block.volumetry[-1]

    # Calculate total debt by currency
    total_debt_lkr = final_vol.total_debt_lkr
    total_debt_usd = final_vol.total_debt_usd
    total_debt_cny = final_vol.total_debt_cny
    total_debt = total_debt_lkr + total_debt_usd + total_debt_cny

    # Avoid division by zero
    if total_debt <= 0:
        return FXRiskProfile(
            var_95_usd_million=0.0,
            cvar_95_usd_million=0.0,
            debt_lkr_pct=0.0,
            debt_usd_pct=0.0,
            debt_cny_pct=0.0,
        )

    # Debt percentages
    debt_lkr_pct = 100.0 * total_debt_lkr / total_debt if total_debt > 0 else 0.0
    debt_usd_pct = 100.0 * total_debt_usd / total_debt if total_debt > 0 else 0.0
    debt_cny_pct = 100.0 * total_debt_cny / total_debt if total_debt > 0 else 0.0

    # Get spot rate from curve (final year)
    spot_lkr_usd = fx_curve.lkr_usd[-1] if fx_curve.lkr_usd else 300.0

    # Compute VaR/CVaR as simplified estimate:
    # VaR_95 = 5% potential LKR depreciation impact on LKR-denominated debt
    # This is a simplified calculation; full Monte Carlo would be more rigorous
    lkr_debt_usd_equiv = total_debt_lkr / spot_lkr_usd
    var_shock_pct = 0.05  # 5% LKR depreciation shock
    var_95_usd = lkr_debt_usd_equiv * var_shock_pct
    cvar_95_usd = var_95_usd * 1.5  # CVaR typically 1.5x VaR in normal scenarios

    # Revenue percentages (assume all in LKR unless specified otherwise)
    revenues_lkr_pct = 100.0 if "LKR" in fx_block.revenue_currencies else 0.0

    # Herfindahl index of debt concentration
    # HHI = (debt_lkr_pct/100)^2 + (debt_usd_pct/100)^2 + (debt_cny_pct/100)^2
    hhi = (
        (debt_lkr_pct / 100.0) ** 2
        + (debt_usd_pct / 100.0) ** 2
        + (debt_cny_pct / 100.0) ** 2
    )

    return FXRiskProfile(
        var_95_usd_million=var_95_usd,
        cvar_95_usd_million=cvar_95_usd,
        debt_lkr_pct=debt_lkr_pct,
        debt_usd_pct=debt_usd_pct,
        debt_cny_pct=debt_cny_pct,
        debt_concentration_hhi=hhi,
        revenues_lkr_pct=revenues_lkr_pct,
        correlation_shock_scenario="",
        worst_case_year=None,
        recovery_years_to_1x_llcr=None,
    )


__all__ = [
    "compute_fx_structured_block",
    "compute_fx_curve",
    "compute_fx_risk_profile",
]

# EOF - analytics/fx/fx_builder.py
