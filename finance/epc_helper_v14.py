"""
v14 EPC / capex helper for lender-grade analytics.

This module centralises:
  * EPC cost breakout (base EPC, freight, contingency),
  * LKR conversion via a resolved FX rate,
  * schema registration for the EPC-related fields so that
    analytics.schema_guard.validate_config_for_v14() can see them.

Intended canonical location:
  finance/epc_helper_v14.py

Other callers (existing shims) should import from here, e.g.:

  # analytics/core/epc_helper.py
  from finance.epc_helper_v14 import (
      epc_breakdown_from_config,
      epc_breakdown_dict,
  )

  # dutchbay_v14chat/finance/v14/epc_helper.py
  from finance.epc_helper_v14 import (
      epc_breakdown_from_config,
      epc_breakdown_dict,
  )
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from analytics.config_schema import RequiredFieldSpec, register_required_fields
from finance.utils import as_float, get_nested


# ---------------------------------------------------------------------------
# FX resolution
# ---------------------------------------------------------------------------


def _resolve_fx_rate(
    config: Dict[str, Any],
    default_fx_rate: Optional[float] = None,
) -> float:
    """
    Resolve an FX rate (LKR per USD) from the v14 config.

    Resolution order (first hit wins):
      1. fx.base_rate
      2. fx.rate
      3. fx.start_lkr_per_usd
      4. scalar fx at top level (historical v13 style)
      5. default_fx_rate argument

    Raises:
      ValueError if no FX rate can be resolved.
    """
    fx_block = config.get("fx", {})

    candidates: List[Optional[float]] = []

    # v14-style keys under `fx`
    if isinstance(fx_block, dict):
        for key in ("base_rate", "rate", "start_lkr_per_usd"):
            if key in fx_block:
                candidates.append(as_float(fx_block.get(key)))

    # Historical scalar fx at root (non-mapping)
    if "fx" in config and not isinstance(fx_block, dict):
        candidates.append(as_float(config.get("fx")))

    # Caller-provided fallback
    if default_fx_rate is not None:
        candidates.append(float(default_fx_rate))

    for value in candidates:
        if value is not None and value > 0:
            return float(value)

    raise ValueError("Unable to resolve FX rate (LKR per USD) from config or defaults")


def _pct_or_zero(value: Any) -> float:
    """
    Normalise percentage-style values to a proper fraction.

    Accepts either:
      * a fraction (0.1 for 10%), or
      * a whole percent (10 for 10%).

    Returns a float in [0, 1]. None and invalid values become 0.0.
    """
    raw = as_float(value, default=0.0)
    if raw is None:
        return 0.0
    v = float(raw)
    # Heuristic: treat values > 1 as percentages (10 -> 0.10)
    if v > 1.0:
        v = v / 100.0
    if v < 0.0:
        v = 0.0
    return v


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def epc_breakdown_from_config(
    config: Dict[str, Any],
    default_fx_rate: Optional[float] = None,
) -> Dict[str, float]:
    """
    Extract a normalised EPC breakdown dict from a v14 scenario config.

    Expected config structure (happy path):

      capex:
        usd_total: 100000000      # base EPC in USD
        freight_pct: 5            # optional, % of base EPC (5 == 5%)
        contingency_pct: 10       # optional, % of base EPC

      fx:
        base_rate: 375.0          # LKR per USD (or equivalent keys)

    Behaviour:
      * freight_pct / contingency_pct default to 0 if absent or null.
      * FX is resolved via _resolve_fx_rate (see its docstring).
      * Values are fully normalised floats (no Optional[float] leaks).
    """
    # Base EPC in USD – this is required and should already be enforced
    # by the schema guard, but we defend anyway.
    base_epc_usd_opt = as_float(get_nested(config, ("capex", "usd_total")))
    if base_epc_usd_opt is None or base_epc_usd_opt <= 0:
        raise ValueError("capex.usd_total must be a positive number (USD EPC base)")

    base_epc_usd = float(base_epc_usd_opt)

    # Optional percentages with sane defaults
    freight_pct = _pct_or_zero(get_nested(config, ("capex", "freight_pct")))
    contingency_pct = _pct_or_zero(get_nested(config, ("capex", "contingency_pct")))

    # Derived USD amounts
    freight_usd = base_epc_usd * freight_pct
    contingency_usd = base_epc_usd * contingency_pct
    total_epc_usd = base_epc_usd + freight_usd + contingency_usd

    # FX and LKR view
    fx_rate = _resolve_fx_rate(config, default_fx_rate=default_fx_rate)
    total_epc_lkr = total_epc_usd * fx_rate

    # Dict contract: keep this aligned with tests/api/test_epc_helper_v14.py
    return {
        "epc_base_usd": float(base_epc_usd),
        "epc_freight_usd": float(freight_usd),
        "epc_contingency_usd": float(contingency_usd),
        "epc_total_usd": float(total_epc_usd),
        "epc_total_lkr": float(total_epc_lkr),
    }


def epc_breakdown_dict(
    config: Mapping[str, Any],
    default_fx_rate: float = 300.0,
) -> Dict[str, float]:
    """Compute a simple EPC cost breakdown in USD and LCY.

    Expected config shape (minimal):

        {
            "capex": {
                "usd_total": 100_000_000.0,
                "freight_pct": 0.05,          # optional, defaults to 0.0
                "contingency_pct": 0.10,      # optional, defaults to 0.0
            },
            "fx": {
                "base_rate": 350.0,           # optional, falls back to default_fx_rate
            },
        }

    Returns a dict that always includes the following keys:

        - base_cost_usd
        - freight_pct
        - freight_usd
        - contingency_pct
        - contingency_usd
        - total_usd
        - fx_rate
        - base_cost_lcy
        - freight_lcy
        - contingency_lcy
        - total_lcy
    """
    capex = config.get("capex") or {}
    fx_cfg = config.get("fx") or {}

    # Base EPC cost in USD (required)
    base_cost_usd_val = capex.get("usd_total")
    if base_cost_usd_val is None:
        raise KeyError("capex.usd_total is required for EPC breakdown")
    base_cost_usd = float(base_cost_usd_val)

    # Percentages – coalesce None / missing to 0.0
    raw_freight_pct = capex.get("freight_pct", 0.0)
    raw_contingency_pct = capex.get("contingency_pct", 0.0)

    freight_pct = float(raw_freight_pct or 0.0)
    contingency_pct = float(raw_contingency_pct or 0.0)

    # FX – prefer config, fall back to default
    fx_rate_val = fx_cfg.get("base_rate", default_fx_rate)
    fx_rate = float(fx_rate_val)

    # USD layer
    freight_usd = base_cost_usd * freight_pct
    contingency_usd = base_cost_usd * contingency_pct
    total_usd = base_cost_usd + freight_usd + contingency_usd

    # LCY layer
    base_cost_lcy = base_cost_usd * fx_rate
    freight_lcy = freight_usd * fx_rate
    contingency_lcy = contingency_usd * fx_rate
    total_lcy = total_usd * fx_rate

    return {
        "base_cost_usd": base_cost_usd,
        "freight_pct": freight_pct,
        "freight_usd": freight_usd,
        "contingency_pct": contingency_pct,
        "contingency_usd": contingency_usd,
        "total_usd": total_usd,
        "fx_rate": fx_rate,
        "base_cost_lcy": base_cost_lcy,
        "freight_lcy": freight_lcy,
        "contingency_lcy": contingency_lcy,
        "total_lcy": total_lcy,
    }


# ---------------------------------------------------------------------------
# Schema registration – hook into the v14 validator
# ---------------------------------------------------------------------------


def _register_epc_schema() -> None:
    """
    Register EPC-related fields with the shared config schema so that
    validate_config_for_v14(..., modules=["cashflow"]) can flag missing
    EPC inputs.

    We register against the "cashflow" module because EPC is a core
    cashflow dependency (capex and depreciation ladder), not a separate
    module in its own right.
    """
    specs: List[RequiredFieldSpec] = [
        RequiredFieldSpec(
            module="cashflow",
            name="epc_usd_total",
            paths=[
                ("capex", "usd_total"),
                ("capex", "epc_usd"),  # backwards-compatible alias
            ],
            required=True,
            severity="error",
            description="Base EPC / capex total in USD",
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="epc_freight_pct",
            paths=[
                ("capex", "freight_pct"),
            ],
            required=False,
            severity="warning",
            description="Freight as a percentage of base EPC (0–1 or 0–100)",
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="epc_contingency_pct",
            paths=[
                ("capex", "contingency_pct"),
            ],
            required=False,
            severity="warning",
            description="Contingency as a percentage of base EPC (0–1 or 0–100)",
        ),
    ]

    register_required_fields("cashflow", specs)


# Register at import time so the schema guard sees us.
_register_epc_schema()


__all__ = [
    "epc_breakdown_from_config",
    "epc_breakdown_dict",
]

