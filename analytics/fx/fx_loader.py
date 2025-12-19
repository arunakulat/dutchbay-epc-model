"""FX Data Loader - Unified interface for FX configuration and curves.

Provides loaders for:
- Structured FX blocks (v14R6 compliant)
- Multi-regime scenarios
- FX curves with confidence intervals
- Legacy config migration

All functions follow Go with the Flow standards:
- Full type hints
- 88-char line limit
- Comprehensive docstrings

Example
-------
>>> from pathlib import Path
>>> config = load_fx_structured_block({"fx": {
...     "start_lkr_per_usd": 375.0,
...     "annual_depr": 0.03,
... }})
>>> config.start_lkr_per_usd
375.0

Part of: analytics/fx/ subpackage
Specs: v14R6 (FX mapping requirement), v2.3V236 (full types)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXMonteCarloConfig,
    FXRegimeScenario,
    FXSensitivityConfig,
    FXStructuredBlock,
    RegimeType,
    VolatilityMethod,
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
    ...         "start_lkr_per_usd": 375.0,
    ...         "annual_depr": 0.03,
    ...     }
    ... })
    >>> config.start_lkr_per_usd
    375.0
    """
    fx_cfg = raw_config.get("fx")

    if fx_cfg is None:
        raise KeyError("Missing 'fx' key in config")

    if isinstance(fx_cfg, (int, float)):
        raise ValueError(
            "Scalar 'fx' configs not supported in v14. "
            "Use structured block with start_lkr_per_usd and "
            "annual_depr."
        )

    if not isinstance(fx_cfg, dict):
        raise ValueError(
            f"Invalid FX config type: {type(fx_cfg).__name__}, " "expected dict."
        )

    # Extract required fields
    start_rate = fx_cfg["start_lkr_per_usd"]
    annual_depr = fx_cfg["annual_depr"]

    # Extract optional fields with defaults
    base_currency = fx_cfg.get("base_currency", "USD")
    target_currency = fx_cfg.get("target_currency", "LKR")
    regime_str = fx_cfg.get("regime", "recent")
    volatility = fx_cfg.get("volatility", 0.10)
    corr_revenue = fx_cfg.get("correlation_with_revenue", 0.0)
    hedge_ratio = fx_cfg.get("hedge_ratio", 0.0)
    metadata = fx_cfg.get("metadata")

    # Convert regime string to enum
    regime = RegimeType(regime_str.lower())

    return FXStructuredBlock(
        start_lkr_per_usd=start_rate,
        annual_depr=annual_depr,
        base_currency=base_currency,
        target_currency=target_currency,
        regime=regime,
        volatility=volatility,
        correlation_with_revenue=corr_revenue,
        hedge_ratio=hedge_ratio,
        metadata=metadata,
    )


def load_fx_regime_scenario(
    raw_config: dict[str, Any],
) -> FXRegimeScenario:
    """Load FX regime scenario with structured block.

    Args
    ----
    raw_config : dict[str, Any]
        Scenario config with 'fx_scenario' section.

    Returns
    -------
    FXRegimeScenario
        Multi-regime scenario config.

    Raises
    ------
    KeyError
        If required keys missing.

    Example
    -------
    >>> scenario = load_fx_regime_scenario({
    ...     "fx_scenario": {
    ...         "scenario_name": "Base Case",
    ...         "probability": 0.6,
    ...         "years": 20,
    ...         "fx": {
    ...             "start_lkr_per_usd": 375.0,
    ...             "annual_depr": 0.03,
    ...         },
    ...     }
    ... })
    >>> scenario.scenario_name
    'Base Case'
    """
    fx_scenario = raw_config["fx_scenario"]

    scenario_name = fx_scenario["scenario_name"]
    probability = fx_scenario["probability"]
    years = fx_scenario["years"]
    apply_shock = fx_scenario.get("apply_shock", False)
    shock_magnitude = fx_scenario.get("shock_magnitude", 0.0)

    # Load nested structured block
    fx_block_config = {"fx": fx_scenario["fx"]}
    structured_block = load_fx_structured_block(fx_block_config)

    return FXRegimeScenario(
        scenario_name=scenario_name,
        structured_block=structured_block,
        probability=probability,
        years=years,
        apply_shock=apply_shock,
        shock_magnitude=shock_magnitude,
    )


def build_fx_curve_from_block(
    block: FXStructuredBlock,
    years: int,
    include_confidence_interval: bool = False,
) -> FXCurveOutput:
    """Build FX rate curve from structured block.

    Applies compound annual depreciation over specified years.
    Optionally includes 95% confidence intervals based on volatility.

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
    >>> block = FXStructuredBlock(
    ...     start_lkr_per_usd=375.0, annual_depr=0.03
    ... )
    >>> curve = build_fx_curve_from_block(block, years=3)
    >>> len(curve.rates)
    3
    """
    year_indices = list(range(years))
    rates = []
    ci_lower = [] if include_confidence_interval else None
    ci_upper = [] if include_confidence_interval else None

    for year_idx in year_indices:
        # Compound depreciation: rate * (1 + annual_depr)^year
        rate = block.start_lkr_per_usd * ((1 + block.annual_depr) ** year_idx)
        rates.append(rate)

        if include_confidence_interval:
            # 95% CI ~ ±1.96 * sigma * sqrt(t)
            # Approx using annual vol
            vol_adjustment = 1.96 * block.volatility * (year_idx**0.5)
            lower = rate * (1 - vol_adjustment)
            upper = rate * (1 + vol_adjustment)
            ci_lower.append(lower)  # type: ignore[union-attr]
            ci_upper.append(upper)  # type: ignore[union-attr]

    metadata: dict[str, Any] = {
        "base_currency": block.base_currency,
        "target_currency": block.target_currency,
        "annual_depr": block.annual_depr,
        "start_rate": block.start_lkr_per_usd,
        "volatility": block.volatility,
        "hedge_ratio": block.hedge_ratio,
    }

    return FXCurveOutput(
        years=year_indices,
        rates=rates,
        regime=block.regime,
        confidence_interval_lower=ci_lower,
        confidence_interval_upper=ci_upper,
        metadata=metadata,
    )


def load_fx_sensitivity_config(
    raw_config: dict[str, Any],
) -> FXSensitivityConfig:
    """Load FX sensitivity/tornado configuration.

    Args
    ----
    raw_config : dict[str, Any]
        Config with 'fx_sensitivity' section.

    Returns
    -------
    FXSensitivityConfig
        Sensitivity analysis config.

    Example
    -------
    >>> config = load_fx_sensitivity_config({
    ...     "fx_sensitivity": {
    ...         "parameter_name": "annual_depr",
    ...         "low_value": 0.01,
    ...         "high_value": 0.05,
    ...         "num_steps": 5,
    ...         "base_fx": {
    ...             "start_lkr_per_usd": 375.0,
    ...             "annual_depr": 0.03,
    ...         },
    ...     }
    ... })
    >>> config.parameter_name
    'annual_depr'
    """
    sens_cfg = raw_config["fx_sensitivity"]

    base_fx_config = {"fx": sens_cfg["base_fx"]}
    base_block = load_fx_structured_block(base_fx_config)

    return FXSensitivityConfig(
        base_block=base_block,
        parameter_name=sens_cfg["parameter_name"],
        low_value=sens_cfg["low_value"],
        high_value=sens_cfg["high_value"],
        num_steps=sens_cfg.get("num_steps", 5),
    )


def load_fx_monte_carlo_config(
    raw_config: dict[str, Any],
) -> FXMonteCarloConfig:
    """Load FX Monte Carlo simulation configuration.

    Args
    ----
    raw_config : dict[str, Any]
        Config with 'fx_monte_carlo' section.

    Returns
    -------
    FXMonteCarloConfig
        Monte Carlo simulation config.

    Example
    -------
    >>> config = load_fx_monte_carlo_config({
    ...     "fx_monte_carlo": {
    ...         "num_simulations": 100000,
    ...         "time_horizon_years": 20,
    ...         "volatility_method": "historical_std",
    ...         "seed": 42,
    ...         "base_fx": {
    ...             "start_lkr_per_usd": 375.0,
    ...             "annual_depr": 0.03,
    ...         },
    ...     }
    ... })
    >>> config.num_simulations
    100000
    """
    mc_cfg = raw_config["fx_monte_carlo"]

    base_fx_config = {"fx": mc_cfg["base_fx"]}
    base_block = load_fx_structured_block(base_fx_config)

    vol_method_str = mc_cfg.get("volatility_method", "historical_std").lower()
    vol_method = VolatilityMethod(vol_method_str)

    correlation_raw = mc_cfg.get("correlation_matrix")
    correlation_matrix = (
        tuple(tuple(row) for row in correlation_raw) if correlation_raw else None
    )

    return FXMonteCarloConfig(
        base_block=base_block,
        num_simulations=mc_cfg["num_simulations"],
        time_horizon_years=mc_cfg["time_horizon_years"],
        volatility_method=vol_method,
        correlation_matrix=correlation_matrix,
        seed=mc_cfg.get("seed"),
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
    ...     "start_lkr_per_usd": 375.0,
    ...     "annual_depr": 0.03,
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

    required_keys = ["start_lkr_per_usd", "annual_depr"]
    missing = [k for k in required_keys if k not in fx_cfg]

    if missing:
        logger.error(f"FX config missing keys: {missing}")
        return False

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
    "load_fx_regime_scenario",
    "build_fx_curve_from_block",
    "load_fx_sensitivity_config",
    "load_fx_monte_carlo_config",
    "validate_fx_structured_config",
    "discover_fx_files",
    "load_fx_regime",
]
# EOF
