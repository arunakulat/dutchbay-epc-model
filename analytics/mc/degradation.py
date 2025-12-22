from __future__ import annotations

"""
analytics.mc.degradation

Degradation hook for Monte Carlo analysis.
Keep it small, deterministic, and optional.

This module should not assume any particular cashflow structure;
it should either:
- modify overrides (preferred), or
- return instructions for the pipeline.
"""

from typing import Any, Dict, Mapping


def apply_degradation_if_enabled(
    *,
    base_cfg: Mapping[str, Any],
    overrides: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply degradation adjustments to overrides if enabled in config.
    
    Expected config structure:
        monte_carlo:
          degradation:
            enabled: true
            default_rate: 0.005  # 0.5% annual degradation
    
    Args:
        base_cfg: Base configuration
        overrides: Override dictionary (modified in-place)
    
    Returns:
        Modified overrides dictionary
    
    Example:
        >>> cfg = {"monte_carlo": {"degradation": {"enabled": True, "default_rate": 0.005}}}
        >>> overrides = {"wind.capacity_factor": 0.35}
        >>> overrides = apply_degradation_if_enabled(base_cfg=cfg, overrides=overrides)
        >>> overrides.get("wind.degradation_rate")
        0.005
    """
    mc = base_cfg.get("monte_carlo", {}) if isinstance(base_cfg, Mapping) else {}
    degr = mc.get("degradation", {}) if isinstance(mc, Mapping) else {}
    enabled = bool(degr.get("enabled", False))
    
    if not enabled:
        return overrides

    # Example: if your model accepts a degradation_rate override key
    # Replace with your real override keys.
    default_rate = float(degr.get("default_rate", 0.0))
    
    # Check if degradation rate already in overrides (sampled parameter)
    # If not, use default
    rate = float(overrides.get("wind.degradation_rate", default_rate))
    overrides["wind.degradation_rate"] = rate
    
    return overrides


__all__ = ["apply_degradation_if_enabled"]
