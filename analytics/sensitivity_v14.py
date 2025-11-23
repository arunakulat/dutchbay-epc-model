"""Sensitivity analysis coordinator for v14 pipeline.

This module is a COORDINATOR ONLY - it does not reimplement finance math.

Architecture:
- Loads parameter configurations (YAML or defaults)
- Generates value grids for each parameter
- Calls evaluate_scenario via evaluate_with_overrides() gateway
- Aggregates results into TornadoResult and SensitivitySuite
- NO direct imports of finance.irr or finance.wacc_v14

Frozen Surfaces Used:
- analytics.contracts_v14 (ParameterRangeConfig, TornadoResult, SensitivitySuite)
- analytics.evaluate_scenario (evaluate_with_overrides gateway)
- constants (SENSITIVITY_RANGES, SENSITIVITY_DEFAULT_STEPS)
- validate (validate_config_for_v14)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Any

import numpy as np
import yaml
from pydantic import ValidationError

from analytics.contracts_v14 import (
    ParameterRangeConfig,
    TornadoResult,
    SensitivitySuite,
)
from analytics.evaluate_scenario import evaluate_with_overrides
from constants import SENSITIVITY_RANGES, SENSITIVITY_DEFAULT_STEPS

logger = logging.getLogger(__name__)


def run_tornado_sensitivity(
    base_config_path: str,
    parameters: Iterable[ParameterRangeConfig] | None = None,
    use_defaults: bool = True,
) -> SensitivitySuite:
    """
    Run one-way tornado sensitivity analysis on scenario.
    
    Coordinator function that:
    1. Loads parameter configurations
    2. Evaluates base case
    3. Sweeps each parameter (low/high values)
    4. Aggregates results into ranked tornado chart
    
    Args:
        base_config_path: Path to base scenario YAML
        parameters: Iterable of ParameterRangeConfig objects
                    If None, loads from sensitivity_defaults.yaml
        use_defaults: If True and parameters is None, use default ranges
    
    Returns:
        SensitivitySuite with tornado_results, rankings, base case KPIs
    
    Raises:
        FileNotFoundError: If config files not found
        ValidationError: If parameter configs invalid
        ValueError: If evaluation fails
    
    Example:
        >>> suite = run_tornado_sensitivity(
        ...     "scenarios/dutchbay_master_config_v14.yaml",
        ...     use_defaults=True
        ... )
        >>> suite.top_risk_drivers(3)
        ['capex_usd_per_kw', 'tariff_lkr_per_kwh', 'capacity_factor_pct']
    """
    logger.info(f"Starting tornado sensitivity analysis: {base_config_path}")
    
    # 1. Load parameter configurations
    params = _load_parameters(parameters, use_defaults)
    logger.info(f"Loaded {len(params)} parameters for sensitivity analysis")
    
    # 2. Evaluate base case
    logger.info("Evaluating base case scenario...")
    base_kpis = evaluate_with_overrides(base_config_path, overrides=None)
    base_irr = base_kpis["project_irr"]
    base_npv = base_kpis["project_npv"]
    logger.info(f"Base case: IRR={base_irr:.2%}, NPV=${base_npv:,.0f}")
    
    # 3. Run tornado analysis for each parameter
    tornado_results = []
    
    for i, param in enumerate(params, 1):
        logger.info(f"[{i}/{len(params)}] Analyzing: {param.variable_name}")
        
        try:
            result = _analyze_single_parameter(
                base_config_path=base_config_path,
                param=param,
                base_irr=base_irr
            )
            tornado_results.append(result)
            
            logger.info(
                f"  Impact: {result.impact_pct:.1f}% "
                f"(Low IRR: {result.low_irr:.2%}, High IRR: {result.high_irr:.2%})"
            )
            
        except Exception as e:
            logger.error(f"  Failed to analyze {param.variable_name}: {e}")
            # Continue with other parameters (fail gracefully)
            continue
    
    # 4. Rank by impact and create suite
    sensitivity_rank = sorted(
        [(r.variable, r.impact_abs) for r in tornado_results],
        key=lambda x: x[1],
        reverse=True
    )
    
    suite = SensitivitySuite(
        tornado_results=tornado_results,
        base_case_irr=base_irr,
        base_case_npv=base_npv,
        sensitivity_rank=sensitivity_rank
    )
    
    logger.info(
        f"Sensitivity analysis complete. Top driver: {sensitivity_rank[0][0]} "
        f"(impact: {sensitivity_rank[0][1]:.4f})"
    )
    
    return suite


def _load_parameters(
    parameters: Iterable[ParameterRangeConfig] | None,
    use_defaults: bool
) -> list[ParameterRangeConfig]:
    """
    Load parameter configurations from arguments, YAML, or defaults.
    
    Priority:
    1. Explicit parameters argument
    2. config/sensitivity_defaults.yaml (if exists)
    3. Built-in SENSITIVITY_RANGES from constants.py
    
    Args:
        parameters: Explicit parameter configs (highest priority)
        use_defaults: If True, fall back to SENSITIVITY_RANGES
    
    Returns:
        List of validated ParameterRangeConfig objects
    
    Raises:
        ValidationError: If any parameter config is invalid
        ValueError: If no parameters available
    """
    # Priority 1: Explicit parameters
    if parameters is not None:
        param_list = list(parameters)
        logger.info(f"Using {len(param_list)} explicit parameters")
        return param_list
    
    # Priority 2: Load from YAML if exists
    yaml_path = Path("config/sensitivity_defaults.yaml")
    if yaml_path.exists():
        logger.info(f"Loading parameters from {yaml_path}")
        return _load_parameters_from_yaml(yaml_path)
    
    # Priority 3: Built-in defaults from constants.py
    if use_defaults:
        logger.info("Using built-in SENSITIVITY_RANGES from constants.py")
        return _create_default_parameters()
    
    raise ValueError(
        "No parameters provided. Either pass explicit parameters, "
        "create config/sensitivity_defaults.yaml, or set use_defaults=True"
    )


def _load_parameters_from_yaml(yaml_path: Path) -> list[ParameterRangeConfig]:
    """
    Load and validate parameters from YAML file.
    
    Args:
        yaml_path: Path to sensitivity_defaults.yaml
    
    Returns:
        List of validated ParameterRangeConfig objects
    
    Raises:
        ValidationError: If YAML contains invalid parameters
    """
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    if not data or "parameters" not in data:
        raise ValueError(
            f"Invalid YAML structure in {yaml_path}. Expected 'parameters' key."
        )
    
    params = []
    for param_dict in data["parameters"]:
        try:
            # Pydantic validation happens here
            param = ParameterRangeConfig(**param_dict)
            params.append(param)
        except ValidationError as e:
            logger.error(f"Invalid parameter in YAML: {param_dict}")
            raise ValueError(f"Parameter validation failed: {e}") from e
    
    return params


def _load_base_values_from_yaml() -> dict[str, float]:
    """
    Load base values from config/sensitivity_defaults.yaml.
    
    Returns:
        Dict mapping variable names to base values
        Empty dict if file doesn't exist or has no base_values section
    
    Example YAML structure:
        base_values:
          capex_usd_per_kw: 850.0
          tariff_lkr_per_kwh: 65.0
    """
    yaml_path = Path("config/sensitivity_defaults.yaml")
    
    if not yaml_path.exists():
        logger.warning(f"{yaml_path} not found, using default base values")
        return {}
    
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data or "base_values" not in data:
            logger.warning(f"No 'base_values' section in {yaml_path}")
            return {}
        
        base_values = data["base_values"]
        
        # Validate that values are numeric
        for key, value in base_values.items():
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Invalid base_value for '{key}': {value} (must be numeric)"
                )
        
        logger.info(f"Loaded {len(base_values)} base values from {yaml_path}")
        return base_values
        
    except Exception as e:
        logger.error(f"Failed to load base values from {yaml_path}: {e}")
        return {}


def _create_default_parameters() -> list[ParameterRangeConfig]:
    """
    Create default ParameterRangeConfig objects from SENSITIVITY_RANGES.
    
    Loads base values from config/sensitivity_defaults.yaml if available,
    otherwise uses constants only with default base value of 100.0.
    
    Returns:
        List of default parameter configurations
    
    Raises:
        ValueError: If base_values in YAML are invalid
    """
    # Try to load base values from YAML
    base_values = _load_base_values_from_yaml()
    
    params = []
    for var_name, (low_pct, high_pct) in SENSITIVITY_RANGES.items():
        base_value = base_values.get(var_name, 100.0)  # Default 100 if not in YAML
        
        param = ParameterRangeConfig(
            variable_name=var_name,
            base_value=base_value,
            low_pct=low_pct,
            high_pct=high_pct,
            steps=SENSITIVITY_DEFAULT_STEPS
        )
        params.append(param)
    
    return params


def _analyze_single_parameter(
    base_config_path: str,
    param: ParameterRangeConfig,
    base_irr: float
) -> TornadoResult:
    """
    Analyze sensitivity for a single parameter.
    
    Evaluates scenario at low and high parameter values,
    compares IRR to base case.
    
    Args:
        base_config_path: Path to base scenario YAML
        param: Parameter configuration
        base_irr: Base case IRR for reference
    
    Returns:
        TornadoResult with low/high IRR values
    
    Raises:
        ValueError: If evaluation fails for either value
    """
    # Convert variable_name to nested dict path
    # e.g., "project.capex_usd_per_kw" -> {"project": {"capex_usd_per_kw": value}}
    path_parts = param.variable_name.split(".")
    
    # Evaluate at low value
    low_overrides = _build_nested_override(path_parts, param.low_value)
    low_kpis = evaluate_with_overrides(base_config_path, low_overrides)
    low_irr = low_kpis["project_irr"]
    
    # Evaluate at high value
    high_overrides = _build_nested_override(path_parts, param.high_value)
    high_kpis = evaluate_with_overrides(base_config_path, high_overrides)
    high_irr = high_kpis["project_irr"]
    
    return TornadoResult(
        variable=param.variable_name,
        base_irr=base_irr,
        low_irr=low_irr,
        high_irr=high_irr
    )


def _build_nested_override(
    path_parts: list[str],
    value: float
) -> dict[str, Any]:
    """
    Build nested dict from dot-separated path.
    
    Args:
        path_parts: List of path components (e.g., ["project", "capex_usd_per_kw"])
        value: Value to set at leaf
    
    Returns:
        Nested dict (e.g., {"project": {"capex_usd_per_kw": 900.0}})
    
    Example:
        >>> _build_nested_override(["project", "capex_usd_per_kw"], 900.0)
        {"project": {"capex_usd_per_kw": 900.0}}
    """
    if len(path_parts) == 1:
        return {path_parts[0]: value}
    
    return {path_parts[0]: _build_nested_override(path_parts[1:], value)}

