# --- FILE: dutchbay_v14chat/finance/v14/epc_helper.py

"""
v14 EPC helper – structured EPC cost breakdown for DutchBay scenarios.

Purpose
-------
This module provides a small, self-contained helper for computing a structured
EPC breakdown (base EPC, freight, contingency, totals in USD and LCY) from a
v14-style scenario config.

Design notes
------------
- This module is deliberately YAML-agnostic.
  Callers should use ``analytics.scenario_loader.load_scenario_config`` to load
  a scenario file into a Python ``dict`` and then pass that config here.
- Inputs are read from the canonical v14 config structure:

    capex.usd_total            : float, required
    capex.freight_pct          : float in [0, 1], optional (default 0.0)
    capex.contingency_pct      : float in [0, 1], optional (default 0.0)
    fx.base_rate               : float, optional
    fx.rate                    : float, optional
    fx                         : float, optional (legacy/simple form)

- If no FX rate is found in the config, you may pass ``default_fx_rate``;
  otherwise a ValueError is raised.

Intended usage
--------------
Typical usage in v14 analytics:

    from analytics.scenario_loader import load_scenario_config
    from dutchbay_v14chat.finance.v14.epc_helper import epc_breakdown_dict

    cfg = load_scenario_config("scenarios/example_a.yaml")
    epc = epc_breakdown_dict(cfg)

    # epc is a flat dict with USD/LCY components that can be logged,
    # exported to Excel, or fed into dashboards.

This keeps EPC logic in one place and makes it easier to evolve the
capex schema without sprinkling ad-hoc arithmetic around the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from finance.utils import as_float, get_nested


@dataclass(frozen=True)
class EPCCostBreakdown:
    """Structured EPC cost breakdown in USD and local currency (LCY)."""

    # Inputs / percentages
    base_cost_usd: float
    freight_pct: float
    contingency_pct: float
    fx_rate: float  # USD → LCY

    # Derived USD components
    freight_usd: float
    contingency_usd: float
    total_usd: float

    # Derived LCY components
    base_cost_lcy: float
    freight_lcy: float
    contingency_lcy: float
    total_lcy: float


def _resolve_fx_rate(config: Dict[str, Any], default_fx_rate: Optional[float]) -> float:
    """
    Resolve an FX rate from a v14 scenario config.

    Resolution order (first non-null wins):
    - fx.base_rate
    - fx.rate
    - top-level fx (if a bare number)
    - default_fx_rate (function argument)

    Raises:
        ValueError if no valid FX rate can be resolved.
    """
    fx_cfg = get_nested(config, ["fx"], None)

    # fx.base_rate or fx.rate if fx is a mapping
    if isinstance(fx_cfg, dict):
        fx = as_float(
            get_nested(fx_cfg, ["base_rate"], get_nested(fx_cfg, ["rate"], None)),
            None,
        )
        if fx is not None and fx > 0:
            return fx

    # Bare numeric fx at top level (legacy/simple form)
    fx_top = as_float(fx_cfg, None)
    if fx_top is not None and fx_top > 0:
        return fx_top

    # Fallback to provided default_fx_rate
    if default_fx_rate is not None and default_fx_rate > 0:
        return float(default_fx_rate)

    raise ValueError("Unable to resolve a positive FX rate from config or default_fx_rate")


def build_epc_from_config(
    config: Dict[str, Any],
    default_fx_rate: Optional[float] = None,
) -> EPCCostBreakdown:
    """
    Build an EPCCostBreakdown from a v14 scenario config.

    Args:
        config:
            Scenario configuration dict as returned by
            ``analytics.scenario_loader.load_scenario_config``.
        default_fx_rate:
            Optional fallback FX rate (USD → LCY) if the config does not carry a
            usable ``fx`` section.

    Returns:
        EPCCostBreakdown instance with USD and LCY components populated.

    Raises:
        ValueError if required fields are missing or inconsistent:
        - capex.usd_total is missing or non-positive
        - freight_pct or contingency_pct are outside [0, 1]
        - FX rate cannot be resolved to a positive value
    """
    base_cost_usd = as_float(get_nested(config, ["capex", "usd_total"], None), None)
    if base_cost_usd is None or base_cost_usd <= 0:
        raise ValueError("capex.usd_total must be a positive number for EPC calculations")

    freight_pct = as_float(get_nested(config, ["capex", "freight_pct"], 0.0), 0.0)
    contingency_pct = as_float(
        get_nested(config, ["capex", "contingency_pct"], 0.0),
        0.0,
    )

    if not (0.0 <= freight_pct <= 1.0):
        raise ValueError(f"capex.freight_pct must be in [0, 1], got {freight_pct}")
    if not (0.0 <= contingency_pct <= 1.0):
        raise ValueError(f"capex.contingency_pct must be in [0, 1], got {contingency_pct}")

    fx_rate = _resolve_fx_rate(config, default_fx_rate)

    freight_usd = base_cost_usd * freight_pct
    contingency_usd = base_cost_usd * contingency_pct
    total_usd = base_cost_usd + freight_usd + contingency_usd

    base_cost_lcy = base_cost_usd * fx_rate
    freight_lcy = freight_usd * fx_rate
    contingency_lcy = contingency_usd * fx_rate
    total_lcy = total_usd * fx_rate

    return EPCCostBreakdown(
        base_cost_usd=base_cost_usd,
        freight_pct=freight_pct,
        contingency_pct=contingency_pct,
        fx_rate=fx_rate,
        freight_usd=freight_usd,
        contingency_usd=contingency_usd,
        total_usd=total_usd,
        base_cost_lcy=base_cost_lcy,
        freight_lcy=freight_lcy,
        contingency_lcy=contingency_lcy,
        total_lcy=total_lcy,
    )


def epc_breakdown_dict(
    config: Dict[str, Any],
    default_fx_rate: Optional[float] = None,
) -> Dict[str, float]:
    """
    Convenience wrapper: return an EPC breakdown as a flat dict.

    This is the most convenient form for logging, JSON/Excel exports, and tests.

    Keys include:

        base_cost_usd
        freight_pct
        contingency_pct
        fx_rate
        freight_usd
        contingency_usd
        total_usd
        base_cost_lcy
        freight_lcy
        contingency_lcy
        total_lcy
    """
    breakdown = build_epc_from_config(config, default_fx_rate=default_fx_rate)
    # asdict() returns a mapping[str, float]; we keep it as-is for maximum flexibility
    return asdict(breakdown)
