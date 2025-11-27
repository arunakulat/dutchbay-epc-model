"""FX Data Loader - Unified interface for loading FX configuration and curves.

Provides:
- load_fx_regime(): Load FX regime from YAML
- discover_fx_files(): Find all FX YAML files in scenarios/
- build_fx_curve(): Generate FX rate curve from config

Part of: analytics/fx/ subpackage (Task 2, Sprint Day 5)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .fx_contracts import FXCurveOutput, FXRegimeConfig


def load_fx_regime(regime_file: Path) -> dict[str, Any]:
    """Load FX regime data from YAML file.

    Args:
        regime_file: Path to FX YAML file

    Returns:
        Parsed YAML configuration dict

    Raises:
        FileNotFoundError: If regime_file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    if not regime_file.exists():
        raise FileNotFoundError(f"FX regime file not found: {regime_file}")

    with open(regime_file, "r") as f:
        return yaml.safe_load(f) or {}


def discover_fx_files(scenarios_dir: Path | None = None) -> dict[str, Path]:
    """Discover all FX YAML files in scenarios directory.

    Args:
        scenarios_dir: Path to scenarios directory (default: ./scenarios)

    Returns:
        Dict mapping file stem to Path (e.g., 'fx_data_recent_Period2_2018_2019' → Path)

    """
    if scenarios_dir is None:
        scenarios_dir = Path("scenarios")

    if not scenarios_dir.exists():
        return {}

    fx_files = {}
    for fx_file in scenarios_dir.glob("fx_data_*.yaml"):
        fx_files[fx_file.stem] = fx_file

    return fx_files


def build_fx_curve(
    config: FXRegimeConfig,
    start_rate: float | None = None,
) -> FXCurveOutput:
    """Build FX rate curve from configuration.

    Applies annual depreciation to starting rate over specified years.

    Args:
        config: FXRegimeConfig with regime parameters
        start_rate: Override starting rate (uses config.start_rate if None)

    Returns:
        FXCurveOutput with years, rates, regime, metadata
    """
    rate = start_rate if start_rate is not None else config.start_rate
    years = list(range(config.years))
    rates = []

    for year in years:
        # Apply annual depreciation
        depreciated_rate = rate * ((1 - config.annual_depr) ** year)
        rates.append(depreciated_rate)

    return FXCurveOutput(
        years=years,
        rates=rates,
        regime=config.regime_type,
        metadata={
            "base_currency": config.base_currency,
            "target_currency": config.target_currency,
            "annual_depr": config.annual_depr,
            "start_rate": config.start_rate,
        },
    )
