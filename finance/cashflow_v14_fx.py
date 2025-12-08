from __future__ import annotations

import logging
from typing import Any, Dict, List

from .cashflow_v14_utils import _as_float_or_none, _pct_to_decimal, get_nested

logger = logging.getLogger(__name__)


def _fx_curve(config: Dict[str, Any], years: int) -> List[float]:
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
         annual_depr: 0.03     # decimal

    Fallbacks
    ---------
    - If an `fx` block exists but has neither a curve nor a start value,
      this function raises a ValueError (schema violation).
    - If there is no `fx` block at all, it falls back to a flat 375 LKR/USD
      with a WARNING log (legacy behaviour for very old scenarios).
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
                depr = float(annual_depr)  # expected as decimal (0.03 = 3%)
            else:
                depr = _pct_to_decimal(_as_float_or_none(depr_pct) or 0.0) or 0.0

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

    # Final hard fallback – true legacy behaviour
    default_fx = 375.0
    logger.warning(
        "FX configuration missing; falling back to flat %.2f LKR/USD for %d years",
        default_fx,
        years,
    )
    return [default_fx] * years


__all__ = ["_fx_curve"]
