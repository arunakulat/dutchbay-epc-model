"""FX Data Loader - Unified interface for FX configuration and curves.

Provides loaders for:
- Structured FX blocks (v14R6 compliant)
- FX curves
- Legacy config migration

All functions follow Go with the Flow v3.0 standards:
- Full type hints
- 88-char line limit
- Comprehensive docstrings

Example
-------
>>> from pathlib import Path
>>> config = {"fx": {"strategy": "blended", "base_currency": "USD"}}
>>> block = load_fx_structured_block(config)
>>> block.base_currency
'USD'

Part of: analytics/fx/ subpackage
Specs: v14R6 (FX mapping requirement), GWTF v3.0
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
    FXVolumetry,
)

logger = logging.getLogger(__name__)


def load_fx_structured_block(
    raw_config: dict[str, Any],
) -> FXStructuredBlock:
    """Load FX structured block from raw YAML/dict config.

    Args
    ----
    raw_config : dict[str, Any]
        Raw scenario config with 'fx' key.

    Returns
    -------
    FXStructuredBlock
        Validated FX structured block.

    Raises
    ------
    KeyError
        If 'fx' key missing or required subkeys absent.
    ValueError
        If FX config is scalar (legacy) or invalid.

    Example
    -------
    >>> config = load_fx_structured_block({
    ...     "fx": {
    ...         "strategy": "blended",
    ...         "base_currency": "USD",
    ...     }
    ... })
    >>> config.base_currency
    'USD'
    """
    fx_cfg = raw_config.get("fx")

    if fx_cfg is None:
        raise KeyError("Missing 'fx' key in config")

    if isinstance(fx_cfg, (int, float)):
        raise ValueError(
            "Scalar 'fx' configs not supported in v14. "
            "Use structured block with strategy and base_currency."
        )

    if not isinstance(fx_cfg, dict):
        raise ValueError(
            f"Invalid FX config type: {type(fx_cfg).__name__}, " "expected dict."
        )

    # Extract fields with defaults matching FXStructuredBlock
    strategy = fx_cfg.get("strategy", "blended")
    base_currency = fx_cfg.get("base_currency", "USD")
    reporting_currency = fx_cfg.get("reporting_currency", "USD")
    fx_match_ratio = fx_cfg.get("fx_match_ratio", 0.0)
    hedging_coverage_pct = fx_cfg.get("hedging_coverage_pct", 0.0)
    notes = fx_cfg.get("notes", "")

    # Build volumetry if provided
    volumetry_list = []
    if "volumetry" in fx_cfg:
        for vol_data in fx_cfg["volumetry"]:
            volumetry_list.append(
                FXVolumetry(
                    period=vol_data["period"],
                    total_debt_lkr=vol_data.get("total_debt_lkr", 0.0),
                    total_debt_usd=vol_data.get("total_debt_usd", 0.0),
                    total_debt_cny=vol_data.get("total_debt_cny", 0.0),
                    revenue_lkr=vol_data.get("revenue_lkr", 0.0),
                    revenue_usd=vol_data.get("revenue_usd", 0.0),
                    interest_lkr=vol_data.get("interest_lkr", 0.0),
                    principal_lkr=vol_data.get("principal_lkr", 0.0),
                )
            )

    debt_tranches = fx_cfg.get("debt_tranches", {})
    revenue_currencies = fx_cfg.get("revenue_currencies", ["LKR"])

    return FXStructuredBlock(
        strategy=strategy,
        base_currency=base_currency,
        reporting_currency=reporting_currency,
        volumetry=volumetry_list,
        debt_tranches=debt_tranches,
        revenue_currencies=revenue_currencies,
        fx_match_ratio=fx_match_ratio,
        hedging_coverage_pct=hedging_coverage_pct,
        notes=notes,
    )


def build_fx_curve_from_block(
    block: FXStructuredBlock,
    years: int,
    include_confidence_interval: bool = False,
) -> FXCurveOutput:
    """Build FX rate curve from structured block.

    NOTE: This is a STUB implementation for Sprint 12.
    Full curve generation will be implemented in Sprint 13.

    Args
    ----
    block : FXStructuredBlock
        Structured FX configuration.
    years : int
        Number of projection years.
    include_confidence_interval : bool
        Include 95% CI bounds (default False).

    Returns
    -------
    FXCurveOutput
        Time-series FX rates with optional CI.

    Example
    -------
    >>> block = FXStructuredBlock(strategy="blended")
    >>> curve = build_fx_curve_from_block(block, years=3)
    >>> len(curve.years)
    3
    """
    # This was a STUB that silently emitted a flat 300 LKR/USD curve regardless of
    # input — a hardcoded FX rate (CESSPIT / ARCH-01 violation). It has no live
    # callers (verified). Rather than emit a wrong curve, fail loudly: real curve
    # generation must source the spot from config via analytics.fx.fx_fetch (the
    # FIXED-vintage / pinned-rate path) or compute_fx_curve in fx_builder.
    raise NotImplementedError(
        "build_fx_curve_from_block is not implemented: it previously emitted a "
        "hardcoded flat 300 LKR/USD curve. Use analytics.fx.fx_builder.compute_fx_curve "
        "with a config-sourced spot (fx.start_lkr_per_usd / fx.source pinned vintage), "
        f"not a magic default. (requested years={years}, strategy={block.strategy})"
    )


def validate_fx_structured_config(
    raw_config: dict[str, Any],
) -> bool:
    """Validate FX config structure before loading.

    Pre-validation to provide clear error messages.

    Args
    ----
    raw_config : dict[str, Any]
        Raw config to validate.

    Returns
    -------
    bool
        True if valid, False otherwise.

    Example
    -------
    >>> config = {"fx": {
    ...     "strategy": "blended",
    ...     "base_currency": "USD",
    ... }}
    >>> validate_fx_structured_config(config)
    True
    """
    fx_cfg = raw_config.get("fx")

    if fx_cfg is None:
        logger.error("Missing 'fx' key in config")
        return False

    if not isinstance(fx_cfg, dict):
        logger.error(f"FX config must be dict, got {type(fx_cfg).__name__}")
        return False

    # No required keys for current FXStructuredBlock (all have defaults)
    # Validation succeeds if 'fx' is a dict
    return True


def discover_fx_files(
    scenarios_dir: Path | None = None,
) -> dict[str, Path]:
    """Discover all FX YAML files in scenarios directory.

    Args
    ----
    scenarios_dir : Path | None
        Path to scenarios directory (default: ./scenarios).

    Returns
    -------
    dict[str, Path]
        Mapping of file stem to Path.

    Example
    -------
    >>> files = discover_fx_files(Path("scenarios"))
    >>> len(files) >= 0
    True
    """
    if scenarios_dir is None:
        scenarios_dir = Path("scenarios")

    if not scenarios_dir.exists():
        return {}

    fx_files = {}
    for fx_file in scenarios_dir.glob("fx_data_*.yaml"):
        fx_files[fx_file.stem] = fx_file

    return fx_files


def load_fx_regime(
    regime_file: Path,
) -> dict[str, Any]:
    """Load FX regime data from YAML file (legacy support).

    Args
    ----
    regime_file : Path
        Path to FX YAML file.

    Returns
    -------
    dict[str, Any]
        Parsed YAML configuration.

    Raises
    ------
    FileNotFoundError
        If regime_file doesn't exist.
    yaml.YAMLError
        If YAML parsing fails.

    Example
    -------
    >>> from pathlib import Path
    >>> # data = load_fx_regime(Path("scenarios/fx_base.yaml"))
    """
    if not regime_file.exists():
        raise FileNotFoundError(f"FX regime file not found: {regime_file}")

    with open(regime_file, "r") as file_handle:
        return yaml.safe_load(file_handle) or {}


__all__ = [
    "load_fx_structured_block",
    "build_fx_curve_from_block",
    "validate_fx_structured_config",
    "discover_fx_files",
    "load_fx_regime",
]
# EOF
