from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from .cashflow_v14_contracts import FxHedge
from .cashflow_v14_utils import _as_float_or_none, _pct_to_decimal, get_nested

logger = logging.getLogger(__name__)


def _fx_curve(
    config: Dict[str, Any], years: int, *, allow_flat_fx: bool = False
) -> List[float]:
    """
    Build an FX curve (LKR per USD) for `years`.

    Supported patterns
    ------------------
    1) Explicit curve:
       fx:
         curve_lkr_per_usd: [375, 386.25, ...]   # or `curve: [...]

    2) Parametric curve:
       fx:
         start_lkr_per_usd: 375
         annual_depr_pct: 3    # percentage
         # or
         annual_depr: 0.03     # decimal (scalar)
         # or
         annual_depr: [0.02, 0.025, 0.03, ...]  # per-year list

    Fail-loud (FIN-6)
    -----------------
    - If an `fx` block exists but has neither a curve nor a start value, this
      function raises a ValueError (schema violation).
    - If no FX curve can be resolved at all (no `fx` block, or a non-dict `fx`),
      it raises a ValueError rather than fabricating a flat, non-depreciating
      curve — for an unindexed-LKR model that flat curve is the single most
      optimistic FX assumption and would silently erase the project's core
      USD-erosion risk. Pass ``allow_flat_fx=True`` to opt into the flat
      config-reference fallback (deliberately FX-agnostic unit tests only).
    """
    years = max(1, int(years))
    fx_cfg = config.get("fx")

    # ------------------------------------------------------------------
    # Case 1: explicit fx block present
    # ------------------------------------------------------------------
    if isinstance(fx_cfg, dict):
        # 1a) Explicit curve list
        curve = fx_cfg.get("curve") or fx_cfg.get("curve_lkr_per_usd")
        if isinstance(curve, (list, tuple)):
            clean = [float(x) for x in curve]
            if len(clean) >= years:
                return clean[:years]
            if clean:
                # Pad with last known rate
                return clean + [clean[-1]] * (years - len(clean))

        # 1b) Parametric curve from start + depreciation
        start = (
            fx_cfg.get("start_lkr_per_usd")
            or fx_cfg.get("start")
            or fx_cfg.get("base")
            or fx_cfg.get("base_rate")
        )

        if start is not None:
            start_val = float(start)

            # Accept either annual_depr_pct (percent) or annual_depr (decimal)
            annual_depr = fx_cfg.get("annual_depr")
            depr_pct = fx_cfg.get("annual_depr_pct") or fx_cfg.get("depr_pct")

            if annual_depr is not None:
                # Support both scalar (uniform) and list (per-year) depreciation
                if isinstance(annual_depr, (list, tuple)):
                    # Per-year depreciation rates (e.g., Monte Carlo scenarios)
                    rates = [float(x) for x in annual_depr]
                    if not rates:
                        raise ValueError("fx.annual_depr list must not be empty")
                    # Pad if shorter than project life
                    if len(rates) < years:
                        rates = rates + [rates[-1]] * (years - len(rates))
                    # Build curve with year-specific rates
                    curve_out: List[float] = []
                    level = float(start_val)
                    for i in range(years):
                        curve_out.append(level)
                        level *= 1.0 + float(rates[i])  # Apply year i depreciation
                    return curve_out
                # Scalar depreciation (uniform across all years)
                depr = float(annual_depr)  # expected as decimal (0.03 = 3%)
            else:
                depr = _pct_to_decimal(_as_float_or_none(depr_pct) or 0.0) or 0.0

            # Build uniform depreciation curve
            out: List[float] = []
            cur = start_val
            for _ in range(years):
                out.append(cur)
                cur *= 1.0 + depr
            return out

        # 1c) Malformed fx block – present but missing both curve and start
        raise ValueError(
            "Invalid FX configuration: expected either "
            "`fx.curve`/`fx.curve_lkr_per_usd` or "
            "`fx.start_lkr_per_usd` (+ optional annual_depr / annual_depr_pct)."
        )

    # ------------------------------------------------------------------
    # Case 2: legacy / minimal – no explicit fx block
    # ------------------------------------------------------------------
    # Try legacy nested keys as a last-ditch attempt
    start_nested = get_nested(config, ["fx", "start_lkr_per_usd"], None)
    if start_nested is not None:
        start_val = float(start_nested)
        annual_depr_nested = get_nested(config, ["fx", "annual_depr"], None)
        if annual_depr_nested is not None:
            if isinstance(annual_depr_nested, (list, tuple)):
                # Per-year rates from nested path
                rates = [float(x) for x in annual_depr_nested]
                if not rates:
                    raise ValueError("fx.annual_depr list must not be empty")
                if len(rates) < years:
                    rates = rates + [rates[-1]] * (years - len(rates))
                curve_out2: List[float] = []
                level2 = float(start_val)
                for i in range(years):
                    curve_out2.append(level2)
                    level2 *= 1.0 + float(rates[i])
                return curve_out2
            depr = float(annual_depr_nested or 0.0)
        else:
            depr_nested = get_nested(config, ["fx", "annual_depr_pct"], None)
            depr = _pct_to_decimal(_as_float_or_none(depr_nested) or 0.0) or 0.0

        out2: List[float] = []
        cur2 = start_val
        for _ in range(years):
            out2.append(cur2)
            cur2 *= 1.0 + depr
        return out2

    # No resolvable FX curve (no `fx` block, or a non-dict `fx`). FIN-6 / CESSPIT:
    # refuse to fabricate a flat, non-depreciating curve — the single most optimistic
    # FX assumption for an unindexed-LKR model, which would silently erase the core
    # USD-erosion risk. Fail loud unless a caller has explicitly opted in.
    if not allow_flat_fx:
        raise ValueError(
            "FX configuration missing or unresolvable: a scenario must declare an "
            "`fx` block (an explicit `curve_lkr_per_usd`, or `start_lkr_per_usd` + "
            "`annual_depr_pct`). Refusing to fabricate a flat, non-depreciating FX "
            "curve for an unindexed-LKR model (FIN-6). Pass allow_flat_fx=True only "
            "for deliberately FX-agnostic unit tests."
        )

    # Opt-in flat fallback: single config-sourced reference rate
    # (config/defaults.yaml), never a Python literal (CESSPIT / ARCH-01).
    from analytics.fx.fx_fetch import default_fx_lkr_per_usd

    default_fx = default_fx_lkr_per_usd()
    logger.warning(
        "FX configuration missing; using the flat config reference %.2f LKR/USD for "
        "%d years (allow_flat_fx=True).",
        default_fx,
        years,
    )
    return [default_fx] * years


# =============================================================================
# FX forward hedge (CIP forward from the LKR/USD debt tranche rates)
# =============================================================================


def _rate_decimal(value: Any, default: float = 0.0) -> float:
    """Normalize a percent-or-decimal interest-rate input to a decimal.

    Mirrors ``finance.debt_v14._solve_mix`` / ``_rate_decimal`` semantics EXACTLY (a
    value > 1.0 is treated as a percentage and divided by 100) so the CIP forward is
    anchored on the SAME tranche rates the debt engine services the facility at. The
    tiny function is replicated (not imported) to keep this low-level FX module free of
    a dependency on the higher-level debt module (import safety, REFACTOR-02).
    """
    raw = _as_float_or_none(value)
    raw = default if raw is None else raw
    return raw / 100.0 if raw > 1.0 else raw


def _cip_forward_rates(config: Dict[str, Any]) -> Tuple[float, float]:
    """Resolve (r_lkr, r_usd) for the covered-interest-parity forward.

    Reads ``Financing_Terms.rates`` (or a ``debt.rates`` fallback) and applies the SAME
    key priority and normalization as ``finance.debt_v14._solve_mix``:

    - r_lkr = ``lkr_nominal`` or ``lkr_min``
    - r_usd = ``usd_nominal`` or ``usd_commercial_min``

    Using the engine's own LKR-vs-USD nominal debt cost is the locked design basis for
    the forward (CIP, not UIP-projected-spot, not a config forward-premium knob). Both
    are returned as decimals; a missing rate resolves to 0.0 and is rejected upstream
    when a hedge is actually requested (``_resolve_fx_hedge``).
    """
    financing = config.get("Financing_Terms") or config.get("financing_terms") or {}
    debt = config.get("debt") or {}
    rates: Dict[str, Any] = {}
    if isinstance(financing, dict) and isinstance(financing.get("rates"), dict):
        rates = financing["rates"]
    elif isinstance(debt, dict) and isinstance(debt.get("rates"), dict):
        rates = debt["rates"]

    r_lkr = _rate_decimal(rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0)
    r_usd = _rate_decimal(
        rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0
    )
    return r_lkr, r_usd


def _forward_curve(config: Dict[str, Any], n_years: int, spot_0: float) -> List[float]:
    """Build the CIP forward FX curve (LKR per USD) anchored on ``spot_0``.

    forward_t = spot_0 * ((1 + r_lkr) / (1 + r_usd)) ** t   for period index t = 0..n-1

    where (r_lkr, r_usd) come from :func:`_cip_forward_rates`. ``t == 0`` yields exactly
    ``spot_0`` (a same-day forward is spot). With the canonical lender-case rates the
    forward drift is (1 + r_lkr) / (1 + r_usd) - 1; when r_lkr was itself built as an
    additive UIP rate (r_usd + spot_drift) this multiplicative forward drift is fractionally
    BELOW the spot drift, so the forward path is a touch less depreciated than the projected
    spot. Raises when either rate is non-positive (a valid CIP forward needs both money-market
    rates).
    """
    n = max(1, int(n_years))
    r_lkr, r_usd = _cip_forward_rates(config)
    if r_lkr <= 0.0 or r_usd <= 0.0:
        raise ValueError(
            "FX hedge requested (fx.hedge_ratio > 0) but the CIP forward rates could "
            "not be resolved: Financing_Terms.rates must declare a positive LKR rate "
            "(lkr_nominal / lkr_min) and USD rate (usd_nominal / usd_commercial_min). "
            f"Resolved r_lkr={r_lkr}, r_usd={r_usd}."
        )
    ratio = (1.0 + r_lkr) / (1.0 + r_usd)
    curve: List[float] = []
    level = float(spot_0)
    for _ in range(n):
        curve.append(level)
        level *= ratio
    return curve


def _resolve_fx_hedge(
    config: Dict[str, Any], fx_curve_resolved: List[float]
) -> FxHedge:
    """Resolve the FX-forward hedge state for a scenario.

    Reads ``fx.hedge_ratio`` (decimal 0-1, default 0.0) and ``fx.spread_bps`` (>=0,
    default 0.0). When ``hedge_ratio == 0`` returns the null :class:`FxHedge` and does
    NOT build a forward curve (so scenarios that do not hedge need no Financing_Terms.rates
    and stay byte-identical). When ``hedge_ratio > 0`` the CIP forward curve is built,
    anchored on the SAME ``spot_0 = fx_curve_resolved[0]`` the per-year spot path uses.
    """
    fx_cfg = config.get("fx")
    if not isinstance(fx_cfg, dict):
        return FxHedge()

    hedge_ratio = _as_float_or_none(fx_cfg.get("hedge_ratio")) or 0.0
    spread_bps = _as_float_or_none(fx_cfg.get("spread_bps")) or 0.0

    if hedge_ratio <= 0.0:
        # Null hedge: pure-spot path, byte-identical. spread is inert without a hedge.
        return FxHedge()

    if not fx_curve_resolved:
        raise ValueError("Cannot build an FX forward curve from an empty spot curve.")

    n_years = len(fx_curve_resolved)
    spot_0 = float(fx_curve_resolved[0])
    forward_curve = _forward_curve(config, n_years, spot_0)
    return FxHedge(
        hedge_ratio=float(hedge_ratio),
        spread=float(spread_bps) / 10000.0,
        forward_curve=tuple(forward_curve),
    )


def _hedged_usd(
    value_lkr: float,
    spot: float,
    forward: float,
    hedge_ratio: float,
    spread: float,
) -> float:
    """Convert an LKR amount to USD, blending spot and CIP-forward conversion.

    usd = (1 - h) * (value_lkr / spot) + h * (value_lkr / (forward * (1 + spread)))

    At ``hedge_ratio <= 0`` this returns EXACTLY ``value_lkr / spot`` (the original,
    unblended arithmetic) so the pre-hedge engine is reproduced bit-for-bit — the blend
    expression is never evaluated, avoiding any float re-association. ``spot`` must be
    positive (guarded by the caller). When a hedge is active, ``forward`` and the
    spread-loaded hedged rate must be positive.
    """
    if hedge_ratio <= 0.0:
        return value_lkr / spot
    hedged_rate = forward * (1.0 + spread)
    if forward <= 0.0 or hedged_rate <= 0.0:
        raise ValueError(
            f"Invalid FX forward for hedged conversion: forward={forward}, "
            f"hedged_rate={hedged_rate} (both must be > 0)."
        )
    return (1.0 - hedge_ratio) * (value_lkr / spot) + hedge_ratio * (
        value_lkr / hedged_rate
    )


__all__ = ["_fx_curve", "_forward_curve", "_resolve_fx_hedge", "_hedged_usd"]
