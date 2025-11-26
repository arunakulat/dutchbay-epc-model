"""Helpers for loading and extracting scenario-specific configurations.

Works with multi-scenario YAML structure in dutchbay_master_config_v14.yaml

Author: DutchBay V14 Team
Version: 1.0
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from finance.irr_config import load_config


def get_scenario(
    config: Dict[str, Any],
    scenario_name: str = "base_case",
) -> Dict[str, Any]:
    """Extract scenario-specific configuration.

    Parameters
    ----------
    config:
        Full YAML configuration dictionary.
    scenario_name:
        Scenario key: "base_case", "optimistic_wind", "conservative_wind",
        "hybrid_wind_solar", "private_equity_case"

    Returns
    -------
    Dict[str, Any]
        Scenario configuration block (name, description, overrides, bounds).

    Examples
    --------
    >>> from finance.irr_config import load_config
    >>> from finance.scenario_config import get_scenario
    >>>
    >>> config = load_config()
    >>> scenario = get_scenario(config, "optimistic_wind")
    >>> print(scenario["description"])
    Better wind resource (P50) with same DFI financing
    """
    scenarios = config.get("scenarios", {})

    if scenario_name not in scenarios:
        available = list(scenarios.keys())
        raise ValueError(
            f"Scenario '{scenario_name}' not found.\n"
            f"Available scenarios: {available}"
        )

    return scenarios[scenario_name]


def get_scenario_irr_bounds(
    config: Dict[str, Any],
    scenario_name: str = "base_case",
    role: Optional[str] = None,
) -> tuple:
    """Extract IRR bounds for a specific scenario and role.

    Parameters
    ----------
    config:
        Full YAML configuration dictionary.
    scenario_name:
        Scenario key.
    role:
        Optional role: "project", "equity", "debt", "xirr"

    Returns
    -------
    tuple
        (lower_bound, upper_bound)
    """
    scenario = get_scenario(config, scenario_name)
    bounds = scenario.get("irr_bounds", {})

    if role is None or role == "project":
        return bounds.get("project_irr_lower"), bounds.get("project_irr_upper")
    elif role == "equity":
        return bounds.get("equity_irr_lower"), bounds.get("equity_irr_upper")
    elif role == "debt":
        return bounds.get("debt_irr_lower"), bounds.get("debt_irr_upper")
    elif role == "xirr":
        return bounds.get("xirr_lower"), bounds.get("xirr_upper")

    raise ValueError(f"Unknown role: {role}")


def list_scenarios(config: Dict[str, Any]) -> list:
    """List all available scenarios.

    Returns
    -------
    list
        List of scenario names with descriptions.
    """
    scenarios = config.get("scenarios", {})
    result = []

    for name, scenario in scenarios.items():
        result.append(
            {
                "name": name,
                "title": scenario.get("name"),
                "description": scenario.get("description"),
            }
        )

    return result
