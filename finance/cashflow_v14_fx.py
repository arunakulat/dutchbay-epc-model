from __future__ import annotations

import logging
from typing import Any, Dict, List

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


__all__ = ["_fx_curve"]
