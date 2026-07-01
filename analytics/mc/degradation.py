# ruff: noqa: E402
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


def apply_degradation_if_enabled(
    *, base_cfg: Mapping[str, Any], overrides: Dict[str, Any]
) -> Dict[str, Any]:
    mc = base_cfg.get("monte_carlo", {}) if isinstance(base_cfg, Mapping) else {}
    degr = mc.get("degradation", {}) if isinstance(mc, Mapping) else {}
    enabled = bool(degr.get("enabled", False))
    if not enabled:
        return overrides

    # Drive the LIVE engine key project.degradation (a percent, /100'd by
    # finance.cashflow_v14_params). The previous key 'wind.degradation_rate' was not read by
    # the cashflow engine, so an enabled degradation block silently did nothing. Default off
    # (enabled: false) -> overrides returned unchanged (byte-identical).
    #
    # A Monte-Carlo SAMPLED draw may arrive either as the flat dotted key
    # 'project.degradation' OR nested under overrides['project']['degradation']. If EITHER
    # is present, the sampler already drives the live key — do NOT clobber it with the
    # static default_rate (the previous flat .get missed the nested form and overwrote the
    # sampled draw, collapsing the degradation distribution to a constant).
    if "project.degradation" in overrides:
        return overrides
    project_block = overrides.get("project")
    if isinstance(project_block, Mapping) and "degradation" in project_block:
        return overrides

    overrides["project.degradation"] = float(degr.get("default_rate", 0.0))
    return overrides
