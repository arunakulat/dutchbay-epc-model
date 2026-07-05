"""FX Structured Block Builder (v14R6).

Provides factory functions for constructing FX blocks from configuration
and scenario data. All functions follow GWTF and CESSPIT standards:
- Full type hints and docstrings
- Immutable outputs (frozen dataclasses)
- Fail-fast validation
- Comprehensive logging for debugging
- No internal state or side effects

Pipeline Integration:
  Called from analytics.fx.fx_integration.integrate_fx_into_scenario_result(),
  which the LIVE pipeline analytics.pipeline_v14_enhanced.run_v14_pipeline invokes
  after the ScenarioResult is assembled (populating fx_block/fx_curve/fx_risk_profile).

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

import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
    FXVolumetry,
)

logger = logging.getLogger(__name__)

# v14 debt tranche name -> reporting currency. The DFI development-finance tranche is
# USD-denominated, so it carries USD FX risk against the LKR-primary revenue. All debt
# amounts in this module are kept in a single consistent unit (USD-equivalent — the
# native unit of debt_result['principal_by_tranche'] / debt_total), so the currency-share
# split and the VaR are computed on like-for-like figures.
_TRANCHE_CURRENCY: Dict[str, str] = {
    "lkr": "LKR",
    "usd": "USD",
    "dfi": "USD",
    "cny": "CNY",
}


def _tranche_principal_usd(debt_result: Mapping[str, Any]) -> Dict[str, float]:
    """Committed principal per *reporting currency* (USD-equivalent) from debt_result.

    Reads debt_result['principal_by_tranche'] (keys lkr/usd/dfi), the engine's real
    per-tranche principal, and buckets each tranche into its reporting currency via
    _TRANCHE_CURRENCY (DFI -> USD). Returns {'LKR': x, 'USD': y, 'CNY': z}. Empty/absent
    -> all zero (the caller warns).
    """
    out: Dict[str, float] = {"LKR": 0.0, "USD": 0.0, "CNY": 0.0}
    principal_by_tranche = debt_result.get("principal_by_tranche", {}) or {}
    if isinstance(principal_by_tranche, Mapping):
        for tranche_name, amount in principal_by_tranche.items():
            ccy = _TRANCHE_CURRENCY.get(str(tranche_name).lower(), "USD")
            try:
                out[ccy] = out.get(ccy, 0.0) + float(amount)
            except (TypeError, ValueError):
                continue
    return out


def compute_fx_structured_block(
    *,
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    degraded: Optional[List[str]] = None,
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
        # #785: a PRESENT-but-non-mapping fx block silently coerced to {} means
        # every FX figure below is built from defaults, not the scenario — the
        # run still "succeeds", so disclose the fallback to the caller.
        if degraded is not None:
            degraded.append(
                "fx config block is not a mapping "
                f"(got {type(fx_config_raw).__name__}); FX structured block "
                "built from defaults"
            )
        fx_config_raw = {}

    fx_config: Mapping[str, Any] = fx_config_raw

    # Read FX strategy (default: blended)
    strategy_str = str(fx_config.get("strategy", "blended")).lower()
    if strategy_str not in ["natural_hedge", "fixed_ccy", "hedged", "blended"]:
        # #785: label-only substitution (strategy does not move VaR/CVaR), but
        # a declared-and-ignored token still misrepresents the config.
        if degraded is not None:
            degraded.append(
                f"fx.strategy {strategy_str!r} is not a recognised token; "
                "reported as 'blended' (label-only substitution)"
            )
        strategy_str = "blended"

    # Read currency configuration
    base_currency = str(fx_config.get("base_currency", "USD"))
    reporting_currency = str(fx_config.get("reporting_currency", "USD"))

    # Read FX match and hedging ratios
    fx_match_ratio = float(fx_config.get("fx_match_ratio", 0.0))
    hedging_coverage_pct = float(fx_config.get("hedging_coverage_pct", 0.0))

    # Extract debt tranches from the v14 debt_result. The engine emits the per-currency
    # principal under `principal_by_tranche` (keys lkr/usd/dfi); there is NO `tranches`
    # key (reading it produced an empty map -> a degenerate FX risk profile). The DFI
    # tranche is a hard-currency (USD-denominated) development-finance loan, so it carries
    # USD FX risk and is bucketed with USD.
    principal_by_tranche = debt_result.get("principal_by_tranche", {}) or {}
    debt_tranches: Dict[str, str] = {}
    if isinstance(principal_by_tranche, Mapping):
        for tranche_name in principal_by_tranche:
            currency = _TRANCHE_CURRENCY.get(str(tranche_name).lower(), "USD")
            debt_tranches[str(tranche_name)] = currency

    # CESSPIT: Warn if no debt tranches found
    if not debt_tranches:
        logger.warning(
            "compute_fx_structured_block: No debt tranches found in debt_result "
            "(expected key 'principal_by_tranche'); FX block will have empty tranches."
        )

    # Revenue currencies (default: LKR). Explicit None check, NOT `... or ["LKR"]`: a
    # supplied empty list is a real (if odd) choice and must not be silently replaced by the
    # LKR default (the same falsy-or family as the fx spot trap fixed earlier).
    revenue_currencies_raw = fx_config.get("revenue_currencies")
    if revenue_currencies_raw is None:
        revenue_currencies = ["LKR"]
    elif isinstance(revenue_currencies_raw, str):
        revenue_currencies = [revenue_currencies_raw]
    else:
        revenue_currencies = list(revenue_currencies_raw)

    # Per-currency committed debt (USD-equivalent) from debt_result['principal_by_tranche'].
    # NOTE: the engine's per-period 'debt_schedules' are a sculpting sub-structure, NOT the
    # outstanding balance (their peak is ~1/10th of the committed principal), and the annual
    # cashflow rows carry no total_debt_* keys — reading either produced a degenerate profile.
    # The committed principal is the stable, correctly-scaled measure of the financing's FX
    # exposure; it is carried on every period (debt currency mix does not change with
    # amortisation), with the per-period REVENUE still sourced from the cashflow rows.
    debt_by_ccy = _tranche_principal_usd(debt_result)

    # Build volumetry — committed debt (USD-equiv) + per-period revenue from the rows.
    volumetry: List[FXVolumetry] = []
    for idx, row in enumerate(annual_rows):
        try:
            volumetry.append(
                FXVolumetry(
                    period=idx,
                    total_debt_lkr=debt_by_ccy["LKR"],
                    total_debt_usd=debt_by_ccy["USD"],
                    total_debt_cny=debt_by_ccy["CNY"],
                    revenue_lkr=float(row.get("revenue_lkr", 0.0)),
                    revenue_usd=float(row.get("revenue_usd", 0.0)),
                    # Live pipeline carries debt interest under 'interest_usd' (USD-equiv,
                    # overlaid by _enrich_annual_rows_with_debt); 'interest_expense_lkr' is
                    # 0.0 in operating rows. Read interest_usd first so the exported FX
                    # interest exposure is non-zero (was always 0 for every year).
                    interest_lkr=float(
                        row.get("interest_usd", row.get("interest_expense_lkr", 0.0))
                    ),
                    principal_lkr=0.0,
                )
            )
        except (ValueError, TypeError) as e:
            # CESSPIT: Fail-fast on malformed row
            logger.error(
                "compute_fx_structured_block: Row %d malformed: %s",
                idx,
                e,
            )
            raise ValueError(
                f"compute_fx_structured_block: Row {idx} malformed: {e}"
            ) from e

    # Build FXStructuredBlock
    fx_notes = str(fx_config.get("notes", ""))

    fx_block = FXStructuredBlock(
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

    logger.debug(
        "compute_fx_structured_block: strategy=%s, base_ccy=%s, "
        "reporting_ccy=%s, tranches=%d, volumetry_periods=%d, "
        "fx_match_ratio=%.1f, hedging_coverage=%.1f",
        strategy_str,
        base_currency,
        reporting_currency,
        len(debt_tranches),
        len(volumetry),
        fx_match_ratio,
        hedging_coverage_pct,
    )

    return fx_block


def _resolve_scenario_spot(fx_config: Mapping[str, Any]) -> Optional[float]:
    """Resolve the LKR/USD spot from the keys scenarios actually declare.

    Scenarios pin the rate under ``fx.rates.lkr_per_usd``, ``fx.start_lkr_per_usd`` or
    ``fx.source.pinned_rate`` (NOT under an ``fx.curve`` block, which none of them use).
    Returns the first present positive value, else ``None`` so the caller falls back to the
    global config default.
    """
    rates = fx_config.get("rates")
    candidates = [
        rates.get("lkr_per_usd") if isinstance(rates, Mapping) else None,
        fx_config.get("start_lkr_per_usd"),
        (
            (fx_config.get("source") or {}).get("pinned_rate")
            if isinstance(fx_config.get("source"), Mapping)
            else None
        ),
    ]
    for value in candidates:
        if value is None:
            continue
        try:
            spot = float(value)
        except (TypeError, ValueError):
            continue
        if spot > 0.0:
            return spot
    return None


def compute_fx_curve(
    *,
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    degraded: Optional[List[str]] = None,
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
        # #785: same disclosure stance as compute_fx_structured_block — a
        # present-but-non-mapping fx block degrades to defaults, loudly.
        if degraded is not None:
            degraded.append(
                "fx config block is not a mapping "
                f"(got {type(fx_config_raw).__name__}); FX curve built from "
                "defaults"
            )
        fx_config_raw = {}

    fx_config: Mapping[str, Any] = fx_config_raw
    curve_config_raw = fx_config.get("curve") or {}
    if not isinstance(curve_config_raw, Mapping):
        # #785: a present-but-non-mapping fx.curve (e.g. a bare list) silently
        # loses the scenario's explicit curve and falls through to the
        # parametric/flat path — schema_guard does not validate curve shape,
        # so this is pipeline-reachable. Disclose it.
        if degraded is not None:
            degraded.append(
                "fx.curve is not a mapping "
                f"(got {type(curve_config_raw).__name__}); the explicit curve "
                "was ignored and the parametric/flat derivation used instead"
            )
        curve_config_raw = {}

    curve_config: Mapping[str, Any] = curve_config_raw

    # Build years array from annual_rows
    years: List[int] = [
        int(row.get("year", idx)) for idx, row in enumerate(annual_rows)
    ]

    # Read LKR/USD curve (required)
    lkr_usd_raw = curve_config.get("lkr_usd")
    if lkr_usd_raw is None:
        # Default: flat curve at the config spot, else the single config-sourced
        # reference rate (config/defaults.yaml) — never a Python literal (CESSPIT).
        from analytics.fx.fx_fetch import default_fx_lkr_per_usd

        # Resolve the flat-curve spot from the keys a scenario ACTUALLY declares before
        # falling back to the global default. No scenario ships an fx.curve block, so the
        # old code always built the curve at default_fx_lkr_per_usd() and ignored the
        # scenario's own pinned rate (fx.rates.lkr_per_usd / fx.start_lkr_per_usd /
        # fx.source.pinned_rate) — wrong whenever that rate diverges from the default.
        # Order: explicit per-curve spot -> scenario rate -> global default.
        # Explicit absence check (CESSPIT fail-loud): a supplied 0.0/negative is a config
        # error, not "absent".
        raw_spot = curve_config.get("spot_lkr_usd")
        if raw_spot is None:
            raw_spot = _resolve_scenario_spot(fx_config)
        if raw_spot is None:
            spot = float(default_fx_lkr_per_usd())
        else:
            spot = float(raw_spot)
            if spot <= 0.0:
                raise ValueError(f"fx spot rate must be > 0; got {raw_spot!r}")
        # SINGLE SOURCE OF TRUTH: when the scenario's fx block resolves to a parametric
        # curve (start + annual_depr), reuse the cashflow's resolver so the REPORTED FX
        # curve EQUALS the curve the USD economics are computed at. Previously this built a
        # FLAT curve and silently ignored fx.annual_depr — the reported curve diverged from
        # the depreciating curve the cashflow/IRR actually used. Falls back to a flat curve
        # at the resolved spot when there is no fx block with a usable start (e.g. a config
        # carrying only fx.rates.lkr_per_usd, or no fx block at all).
        lkr_usd = None
        if isinstance(fx_config, Mapping) and fx_config:
            try:
                from finance.cashflow_v14_fx import _fx_curve as _cashflow_fx_curve

                lkr_usd = _cashflow_fx_curve({"fx": dict(fx_config)}, len(years))
            except (ValueError, KeyError, TypeError):
                lkr_usd = None
        if lkr_usd is None:
            lkr_usd = [spot] * len(years)
            logger.debug(
                "compute_fx_curve: No lkr_usd / parametric curve; flat at %.2f", spot
            )
            # #785: a FLAT curve at the resolved spot is a stale/default FX
            # assumption presented as a projection — disclose it. (The
            # parametric fx.annual_depr path above is the canonical derivation
            # and is NOT a fallback.)
            if degraded is not None:
                degraded.append(
                    "no explicit or parametric FX curve resolvable; using a "
                    f"FLAT curve at spot {spot:.2f} LKR/USD for all years"
                )
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

    # Validation: Ensure primary curve length matches years
    if len(lkr_usd) != len(years):
        logger.error(
            "compute_fx_curve: lkr_usd length %d does not match years length %d",
            len(lkr_usd),
            len(years),
        )
        raise ValueError(
            "compute_fx_curve: lkr_usd length "
            f"{len(lkr_usd)} does not match years length {len(years)}."
        )

    # Validation: Optional curves must also match years length (if present)
    if lkr_cny is not None and len(lkr_cny) != len(years):
        logger.error(
            "compute_fx_curve: lkr_cny length %d does not match years length %d",
            len(lkr_cny),
            len(years),
        )
        raise ValueError(
            "compute_fx_curve: lkr_cny length "
            f"{len(lkr_cny)} does not match years length {len(years)}."
        )

    if lkr_eur is not None and len(lkr_eur) != len(years):
        logger.error(
            "compute_fx_curve: lkr_eur length %d does not match years length %d",
            len(lkr_eur),
            len(years),
        )
        raise ValueError(
            "compute_fx_curve: lkr_eur length "
            f"{len(lkr_eur)} does not match years length {len(years)}."
        )

    if lkr_gbp is not None and len(lkr_gbp) != len(years):
        logger.error(
            "compute_fx_curve: lkr_gbp length %d does not match years length %d",
            len(lkr_gbp),
            len(years),
        )
        raise ValueError(
            "compute_fx_curve: lkr_gbp length "
            f"{len(lkr_gbp)} does not match years length {len(years)}."
        )

    # Count available pairs
    num_pairs = 1  # lkr_usd always present
    if lkr_cny is not None:
        num_pairs += 1
    if lkr_eur is not None:
        num_pairs += 1
    if lkr_gbp is not None:
        num_pairs += 1

    logger.debug(
        "compute_fx_curve: years=%d, pairs=%d, source=%s, "
        "lkr_usd[0]=%.2f, lkr_usd[-1]=%.2f",
        len(years),
        num_pairs,
        source,
        lkr_usd[0] if lkr_usd else float("nan"),
        lkr_usd[-1] if lkr_usd else float("nan"),
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
    var_shock_pct: float = 0.05,
    degraded: Optional[List[str]] = None,
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
        logger.warning(
            "compute_fx_risk_profile: No volumetry in fx_block; "
            "returning minimal profile."
        )
        # #785: a zeroed VaR/CVaR profile is not "no FX risk", it is "no data
        # to compute FX risk from" — disclose the degenerate substitution.
        if degraded is not None:
            degraded.append(
                "fx_block has no volumetry; FX risk profile is a degenerate "
                "minimal placeholder (VaR/CVaR 0.0, nominal 100% USD)"
            )
        return FXRiskProfile(
            var_95_usd_million=0.0,
            cvar_95_usd_million=0.0,
            debt_lkr_pct=0.0,
            debt_usd_pct=100.0,
            debt_cny_pct=0.0,
        )

    # Use the PEAK-debt period, not the final period. Debt amortises toward zero by
    # maturity, so the last row understates (here zeroes out) the financing's FX exposure;
    # the lender-relevant concentration/VaR snapshot is the period of largest outstanding.
    peak_vol = max(
        fx_block.volumetry,
        key=lambda v: v.total_debt_lkr + v.total_debt_usd + v.total_debt_cny,
    )

    # Calculate total debt by currency
    total_debt_lkr = peak_vol.total_debt_lkr
    total_debt_usd = peak_vol.total_debt_usd
    total_debt_cny = peak_vol.total_debt_cny
    total_debt = total_debt_lkr + total_debt_usd + total_debt_cny

    # Avoid division by zero
    if total_debt <= 0:
        logger.warning(
            "compute_fx_risk_profile: Total debt is zero or negative (%.2f); "
            "returning minimal profile.",
            total_debt,
        )
        # #785: disclose the degenerate substitution (see the volumetry arm).
        if degraded is not None:
            degraded.append(
                f"peak total debt is {total_debt:.2f} (zero/negative); FX risk "
                "profile is a degenerate minimal placeholder (VaR/CVaR 0.0)"
            )
        # With no debt there is no FX exposure, but FXRiskProfile still requires
        # the debt-currency percentages to sum to ~100. Mirror the no-volumetry
        # branch above (nominal 100% USD) so the minimal profile is valid rather
        # than tripping its own __post_init__ validator.
        return FXRiskProfile(
            var_95_usd_million=0.0,
            cvar_95_usd_million=0.0,
            debt_lkr_pct=0.0,
            debt_usd_pct=100.0,
            debt_cny_pct=0.0,
        )

    # Debt percentages
    debt_lkr_pct = 100.0 * total_debt_lkr / total_debt if total_debt > 0 else 0.0
    debt_usd_pct = 100.0 * total_debt_usd / total_debt if total_debt > 0 else 0.0
    debt_cny_pct = 100.0 * total_debt_cny / total_debt if total_debt > 0 else 0.0

    # Spot rate (final-year curve point, else config reference) — retained for the log.
    from analytics.fx.fx_fetch import default_fx_lkr_per_usd

    spot_lkr_usd = (
        fx_curve.lkr_usd[-1] if fx_curve.lkr_usd else default_fx_lkr_per_usd()
    )

    # FX VaR is on the CURRENCY-MISMATCHED legs ONLY (audit fix). The project's revenue is
    # LKR; LKR-denominated debt serviced from that LKR revenue is a NATURAL HEDGE — its
    # USD-reporting swing is a translation artifact, NOT a lender cash risk — so it is
    # EXCLUDED. The genuine, material exposure is the HARD-CURRENCY debt (USD + DFI[=USD] +
    # CNY) serviced from LKR revenue: an adverse LKR depreciation of var_shock_pct raises the
    # LKR cost (USD-equivalent loss) on that unhedged balance. The prior code based VaR on the
    # LKR leg — the hedged leg — which inverted the exposure direction.
    # All debt amounts are already USD-equivalent, so the shock applies directly; result in
    # USD MILLIONS. var_shock_pct (the adverse LKR/USD move) is sourced from fx.uncertainty_pct.
    if var_shock_pct <= 0.0:
        raise ValueError(f"var_shock_pct must be > 0; got {var_shock_pct!r}")
    # Apply the declared FX hedge to the EXPOSED (hard-currency) balance only. hedging_
    # coverage_pct was read onto the block but never reduced the VaR. Clamp to [0,1];
    # 0% coverage -> full exposure.
    hedge_frac = max(0.0, min(1.0, fx_block.hedging_coverage_pct / 100.0))
    hard_currency_exposure = (
        total_debt_usd + total_debt_cny
    )  # mismatched vs LKR revenue
    residual_exposure = hard_currency_exposure * (1.0 - hedge_frac)
    var_95_usd_million = (residual_exposure * var_shock_pct) / 1e6
    cvar_95_usd_million = (
        var_95_usd_million * 1.5
    )  # CVaR ~1.5x VaR (normal-tail heuristic)

    # Revenue percentages (assume all in LKR unless specified otherwise)
    revenues_lkr_pct = 100.0 if "LKR" in fx_block.revenue_currencies else 0.0

    # Herfindahl index of debt concentration
    # HHI = (debt_lkr_pct/100)^2 + (debt_usd_pct/100)^2 + (debt_cny_pct/100)^2
    hhi = (
        (debt_lkr_pct / 100.0) ** 2
        + (debt_usd_pct / 100.0) ** 2
        + (debt_cny_pct / 100.0) ** 2
    )

    fx_risk = FXRiskProfile(
        var_95_usd_million=var_95_usd_million,
        cvar_95_usd_million=cvar_95_usd_million,
        debt_lkr_pct=debt_lkr_pct,
        debt_usd_pct=debt_usd_pct,
        debt_cny_pct=debt_cny_pct,
        debt_concentration_hhi=hhi,
        revenues_lkr_pct=revenues_lkr_pct,
        correlation_shock_scenario="",
        worst_case_year=None,
        recovery_years_to_1x_llcr=None,
    )

    logger.debug(
        "compute_fx_risk_profile: var_95=%.3f USD_M, cvar_95=%.3f USD_M, "
        "hhi=%.3f, debt_composition: lkr=%.1f%%, usd=%.1f%%, cny=%.1f%%, "
        "spot_rate=%.2f, total_debt=%.2f",
        var_95_usd_million,
        cvar_95_usd_million,
        hhi,
        debt_lkr_pct,
        debt_usd_pct,
        debt_cny_pct,
        spot_lkr_usd,
        total_debt,
    )

    return fx_risk


__all__ = [
    "compute_fx_structured_block",
    "compute_fx_curve",
    "compute_fx_risk_profile",
]

# EOF - analytics/fx/fx_builder.py
