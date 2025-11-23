"""Helper utilities for extracting IRR bounds from YAML configuration.

This module provides clean helper functions to extract IRR validation bounds
from canonical YAML configuration with explicit Pattern 1 integration.

Pattern 1 (Explicit Config - Recommended for Production):
    Load YAML once at application start, pass config dictionary to all functions.

Author: DutchBay V14 Team
Version: 1.0
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import yaml


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load canonical YAML configuration (Pattern 1 helper).
    
    Parameters
    ----------
    config_path:
        Path to YAML config file.
        Default: "scenarios/dutchbay_master_config_v14.yaml"
    
    Returns
    -------
    Dict[str, Any]
        Loaded configuration dictionary.
    
    Raises
    ------
    FileNotFoundError:
        If config file doesn't exist.
    
    Examples
    --------
    >>> config = load_config()  # Uses default path
    >>> config = load_config("scenarios/custom_scenario.yaml")  # Custom path
    """
    if config_path is None:
        config_path = "scenarios/dutchbay_master_config_v14.yaml"
    
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Current working directory: {Path.cwd()}\n"
            f"Ensure you're running from project root."
        )
    
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_irr_bounds(
    config: Dict[str, Any],
    role: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """Extract IRR bounds from YAML configuration.
    
    Parameters
    ----------
    config:
        Full YAML configuration dictionary (from load_config()).
    role:
        Optional role-specific override: "equity", "debt", or None for project-level.
    
    Returns
    -------
    Tuple[Optional[float], Optional[float]]
        (lower_bound, upper_bound) or (None, None) if not configured.
    
    Examples
    --------
    Pattern 1 (Explicit Config - Recommended):
    >>> from finance.irr_config import load_config, get_irr_bounds
    >>> config = load_config()  # Load once at app start
    >>> lower, upper = get_irr_bounds(config)
    >>> print(f"Project IRR bounds: [{lower}, {upper}]")
    Project IRR bounds: [-0.7, 0.35]
    
    >>> lower_eq, upper_eq = get_irr_bounds(config, role="equity")
    >>> print(f"Equity IRR bounds: [{lower_eq}, {upper_eq}]")
    Equity IRR bounds: [-0.5, 0.5]
    """
    irr_cfg = config.get("irr_validation", {})
    
    if not irr_cfg:
        return None, None
    
    # Role-specific override if requested
    if role == "equity":
        lower = irr_cfg.get("equity_irr_lower_bound")
        upper = irr_cfg.get("equity_irr_upper_bound")
        if lower is not None or upper is not None:
            # Found role-specific, use it (may still fall back to project-level for one)
            lower = lower or irr_cfg.get("irr_lower_bound")
            upper = upper or irr_cfg.get("irr_upper_bound")
            return lower, upper
    
    elif role == "debt":
        lower = irr_cfg.get("debt_irr_lower_bound")
        upper = irr_cfg.get("debt_irr_upper_bound")
        if lower is not None or upper is not None:
            lower = lower or irr_cfg.get("irr_lower_bound")
            upper = upper or irr_cfg.get("irr_upper_bound")
            return lower, upper
    
    # Default: project-level bounds
    lower = irr_cfg.get("irr_lower_bound")
    upper = irr_cfg.get("irr_upper_bound")
    return lower, upper


def get_xirr_bounds(
    config: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    """Extract XIRR bounds from YAML configuration.
    
    Parameters
    ----------
    config:
        Full YAML configuration dictionary (from load_config()).
    
    Returns
    -------
    Tuple[Optional[float], Optional[float]]
        (lower_bound, upper_bound) or (None, None) if not configured.
    
    Examples
    --------
    Pattern 1 (Explicit Config):
    >>> from finance.irr_config import load_config, get_xirr_bounds
    >>> config = load_config()
    >>> lower, upper = get_xirr_bounds(config)
    >>> print(f"XIRR bounds: [{lower}, {upper}]")
    XIRR bounds: [-0.7, 0.25]
    """
    irr_cfg = config.get("irr_validation", {})
    
    if not irr_cfg:
        return None, None
    
    lower = irr_cfg.get("xirr_lower_bound")
    upper = irr_cfg.get("xirr_upper_bound")
    return lower, upper


__all__ = [
    "load_config",
    "get_irr_bounds",
    "get_xirr_bounds",
]
