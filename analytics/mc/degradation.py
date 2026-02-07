from __future__ import annotations

"""
analytics.mc.degradation

Degradation hook. Keep it small, deterministic, and optional.

This module should not assume any particular cashflow structure;
it should either:
- modify overrides (preferred), or
- return instructions for the pipeline.
"""

from typing import Any, Dict, Mapping


def apply_degradation_if_enabled(*, base_cfg: Mapping[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    mc = base_cfg.get("monte_carlo", {}) if isinstance(base_cfg, Mapping) else {}
    degr = mc.get("degradation", {}) if isinstance(mc, Mapping) else {}
    enabled = bool(degr.get("enabled", False))
    if not enabled:
        return overrides

    # Example: if your model accepts a degradation_rate override key
    # Replace with your real override keys.
    default_rate = float(degr.get("default_rate", 0.0))
    rate = float(overrides.get("wind.degradation_rate", default_rate))
    overrides["wind.degradation_rate"] = rate
    return overrides
