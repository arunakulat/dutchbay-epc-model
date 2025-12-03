from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence, Tuple

from analytics.config_schema import RequiredFieldSpec, register_required_fields
from finance.utils import as_float

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / path definitions
# ---------------------------------------------------------------------------

# Canonical and legacy paths for EPC total in USD
_EPC_PATHS_CANONICAL: Sequence[Tuple[str, str]] = (
    ("capex", "usd_total"),  # canonical v14 lender-grade
    ("capex", "epc_usd"),  # backwards-compatible alias
)

_EPC_PATH_LEGACY: Tuple[str, str] = ("finance", "capex_usd")  # toy / test configs

"""
v14 EPC / capex helper for lender-grade analytics.

This module centralises:

  * EPC cost breakout (base EPC, freight, contingency),
  * LKR conversion via a resolved FX rate,
  * schema registration for EPC-related fields so that
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

Schema Registration Strategy
----------------------------
The `epc_usd_total` field accepts THREE paths (first hit wins):

  1. capex.usd_total       ← canonical v14 lender-grade path
  2. capex.epc_usd         ← backwards-compatible alias
  3. finance.capex_usd     ← legacy alias for toy/test configs

This design:

  - Keeps production configs clean (use capex.usd_total),
  - Preserves minimal test scenarios (e.g., scenarios/test/base_scenario.yaml),
  - Avoids cascading test rewrites mid-sprint,
  - Provides a clear migration path: deprecate finance.* in a later sprint.

Rationale:
  Sensitivity / analytics integration tests use inline configs with
  finance.capex_usd. Rather than rewrite tests + scenarios + parameter
  names mid-migration, we add an explicit schema alias that documents:

    "This is legacy, tolerated for backwards compatibility."

Real-world lender-grade configs should use capex.usd_total exclusively.
"""
# ---------------------------------------------------------------------------
# FX resolution
# ---------------------------------------------------------------------------


def _resolve_fx_rate(
    config: Mapping[str, Any],
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

    Examples:
        >>> config = {"fx": {"start_lkr_per_usd": 320.0}}
        >>> _resolve_fx_rate(config)
        320.0

        >>> config = {"fx": {"base_rate": 350.0}}
        >>> _resolve_fx_rate(config)
        350.0
    """
    fx_block = config.get("fx", {})

    candidates: list[Optional[float]] = []

    # v14-style keys under `fx`
    if isinstance(fx_block, Mapping):
        for key in ("base_rate", "rate", "start_lkr_per_usd"):
            if key in fx_block:
                candidates.append(as_float(fx_block.get(key)))

    # Historical scalar fx at root (non-mapping)
    if "fx" in config and not isinstance(fx_block, Mapping):
        candidates.append(as_float(config.get("fx")))

    # Caller-provided fallback
    if default_fx_rate is not None:
        candidates.append(float(default_fx_rate))

    for value in candidates:
        if value is not None and value > 0:
            return float(value)

    raise ValueError(
        "Unable to resolve FX rate (LKR per USD) from config or defaults. "
        "Expected one of: fx.base_rate, fx.rate, fx.start_lkr_per_usd, "
        "or default_fx_rate."
    )


def _pct_or_zero(value: Any) -> float:
    """
    Normalise percentage-style values to a proper fraction.

    Accepts either:
      * a fraction (0.1 for 10%), or
      * a whole percent (10 for 10%).

    Returns:
        float in [0.0, 1.0]. None and invalid values become 0.0.

    Examples:
        >>> _pct_or_zero(0.05)
        0.05
        >>> _pct_or_zero(5)
        0.05
        >>> _pct_or_zero(None)
        0.0
        >>> _pct_or_zero(-10)
        0.0
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

    # Clamp in case of weird inputs
    if v > 1.0:
        v = 1.0

    return v


# ---------------------------------------------------------------------------
# CAPEX resolution (multi-path support)
# ---------------------------------------------------------------------------


def _resolve_capex_usd_total(config: Mapping[str, Any]) -> Optional[float]:
    """
    Resolve EPC total USD from supported paths, in canonical order.

    Resolution order (first hit wins):
      1. capex.usd_total       ← canonical v14 lender-grade path
      2. capex.epc_usd         ← backwards-compatible alias
      3. finance.capex_usd     ← legacy alias for toy/test configs

    Returns:
        Positive float if found, None otherwise.

    Examples:
        >>> config = {"capex": {"usd_total": 10000000.0}}
        >>> _resolve_capex_usd_total(config)
        10000000.0

        >>> config = {"finance": {"capex_usd": 10000000.0}}
        >>> _resolve_capex_usd_total(config)
        10000000.0
    """
    # Try canonical paths first
    capex = config.get("capex", {}) or {}
    if isinstance(capex, Mapping):
        for key in ("usd_total", "epc_usd"):
            val = as_float(capex.get(key))
            if val is not None and val > 0:
                return float(val)

    # Fallback to legacy path
    finance = config.get("finance", {}) or {}
    if isinstance(finance, Mapping):
        val = as_float(finance.get("capex_usd"))
        if val is not None and val > 0:
            logger.debug(
                "Using legacy finance.capex_usd for EPC total (backwards-compat alias)."
            )
            return float(val)

    return None


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def epc_breakdown_from_config(
    config: Mapping[str, Any],
    default_fx_rate: Optional[float] = None,
) -> Dict[str, float]:
    """
    Extract a normalised EPC breakdown dict from a v14 scenario config.

    Expected config structure (happy path):

      capex:
        usd_total: 100000000      # base EPC in USD (canonical)
        freight_pct: 5            # optional, % of base EPC (5 == 5%)
        contingency_pct: 10       # optional, % of base EPC

      fx:
        base_rate: 375.0          # LKR per USD (or equivalent keys)

    Behaviour:
      * EPC base cost is resolved via _resolve_capex_usd_total, which supports:
          - capex.usd_total       (canonical)
          - capex.epc_usd         (alias)
          - finance.capex_usd     (legacy alias)
      * freight_pct / contingency_pct default to 0 if absent or null.
      * Percentage-style values can be given as 0.1 or 10 (both → 10%).
      * FX is resolved via _resolve_fx_rate (see its docstring).
      * Values are fully normalised floats (no Optional[float] leaks).

    Returns:
        Dict with keys:
          - epc_base_usd
          - epc_freight_usd
          - epc_contingency_usd
          - epc_total_usd
          - epc_total_lkr

    Raises:
        ValueError if base EPC cannot be resolved or is invalid.
    """
    cfg: MutableMapping[str, Any] = dict(config)

    # Base EPC in USD – try multi-path resolution
    base_epc_usd_opt = _resolve_capex_usd_total(cfg)
    if base_epc_usd_opt is None or base_epc_usd_opt <= 0:
        raise ValueError(
            "Base EPC USD must be a positive number. "
            "Expected one of: capex.usd_total, capex.epc_usd, finance.capex_usd"
        )

    base_epc_usd = float(base_epc_usd_opt)

    # Optional percentages with sane defaults
    capex = cfg.get("capex", {}) or {}
    if not isinstance(capex, Mapping):
        capex = {}

    freight_pct = _pct_or_zero(capex.get("freight_pct"))
    contingency_pct = _pct_or_zero(capex.get("contingency_pct"))

    # Derived USD amounts
    freight_usd = base_epc_usd * freight_pct
    contingency_usd = base_epc_usd * contingency_pct
    total_epc_usd = base_epc_usd + freight_usd + contingency_usd

    # FX and LKR view
    fx_rate = _resolve_fx_rate(cfg, default_fx_rate=default_fx_rate)
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
    """
    Compute a simple EPC cost breakdown in USD and LCY.

    Expected minimal config shape:

        {
            "capex": {
                "usd_total": 100_000_000.0,
                "freight_pct": 0.05,      # or 5 for 5%
                "contingency_pct": 0.10,  # or 10 for 10%
            },
            "fx": {
                "base_rate": 350.0,       # or fx.rate / fx.start_lkr_per_usd
            },
        }

    Also accepts legacy path:

        {
            "finance": {
                "capex_usd": 100_000_000.0,
            },
        }

    Behaviour:
      * EPC base cost is resolved via _resolve_capex_usd_total.
      * freight_pct / contingency_pct use the same normalisation as
        _pct_or_zero: 0.1 or 10 both → 10%.
      * FX is resolved via _resolve_fx_rate, with default_fx_rate as a
        final fallback.

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

    Raises:
        KeyError if base EPC USD cannot be resolved.
        ValueError if FX cannot be resolved.
    """
    cfg: MutableMapping[str, Any] = dict(config)

    # Try multi-path resolution for EPC base cost
    base_cost_usd_opt = _resolve_capex_usd_total(cfg)
    if base_cost_usd_opt is None:
        raise KeyError(
            "EPC base cost required. Expected one of: "
            "capex.usd_total, capex.epc_usd, finance.capex_usd"
        )
    base_cost_usd = float(base_cost_usd_opt)

    # Optional percentages – coalesce None / missing to 0.0
    capex = cfg.get("capex", {}) or {}
    if not isinstance(capex, Mapping):
        capex = {}

    freight_pct = _pct_or_zero(capex.get("freight_pct", 0.0))
    contingency_pct = _pct_or_zero(capex.get("contingency_pct", 0.0))

    # FX – prefer config, fall back to default
    fx_rate = _resolve_fx_rate(cfg, default_fx_rate=default_fx_rate)

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

    Current behaviour:
      - `epc_usd_total` is REQUIRED, error severity.
      - `epc_freight_pct` and `epc_contingency_pct` are OPTIONAL, warning severity.

    Paths for `epc_usd_total`:

      1. capex.usd_total       ← canonical v14 lender-grade path
      2. capex.epc_usd         ← backwards-compatible alias
      3. finance.capex_usd     ← legacy alias for toy/test configs

    Migration Path (informal plan):

      - Production configs: use capex.usd_total (canonical).
      - Test / toy configs: tolerate finance.capex_usd (legacy).
      - Later sprint: optionally emit warnings when legacy path is used.
      - Subsequent sprint: remove finance.* paths entirely.
    """
    specs: list[RequiredFieldSpec] = [
        RequiredFieldSpec(
            module="cashflow",
            name="epc_usd_total",
            paths=[
                ("capex", "usd_total"),  # canonical v14 lender-grade path
                ("capex", "epc_usd"),  # backwards-compatible alias
                ("finance", "capex_usd"),  # legacy alias for toy/test configs
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
            description="Freight as a percentage of base EPC (0–1 or 0–100).",
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="epc_contingency_pct",
            paths=[
                ("capex", "contingency_pct"),
            ],
            required=False,
            severity="warning",
            description="Contingency as a percentage of base EPC (0–1 or 0–100).",
        ),
    ]

    register_required_fields("cashflow", specs)


# Register at import time so the schema guard sees us.
try:
    _register_epc_schema()
except Exception as exc:  # pragma: no cover
    # Defensive: if schema registration fails (e.g., during isolated unit tests),
    # log but don't crash the module import.
    logger.debug(
        "EPC schema registration skipped or deferred: %s: %s",
        type(exc).__name__,
        exc,
    )


__all__ = [
    "epc_breakdown_from_config",
    "epc_breakdown_dict",
]
