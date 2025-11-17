"""
scenario_manager_v14.py

V14 scenario manager for dict/YAML configs.

Provides:
    - deep_merge: recursive dict merge.
    - ScenarioDefinition: dataclass representation of a scenario.
    - apply_scenario: overlay scenario onto a base config.
    - list_scenarios: summarise multiple scenarios.
    - compare_scenarios: inspect how a particular key-path differs per scenario.

This module deliberately does not know how configs are loaded (YAML vs JSON);
callers are expected to load into dicts first.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


def deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries.

    - Nested dicts are merged recursively.
    - All other values in overlay replace those in base.
    - Lists are treated as scalars (overlay replaces base).

    Returns a new dict; base is not mutated.
    """
    result: Dict[str, Any] = deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


@dataclass
class ScenarioDefinition:
    """
    Representation of a scenario overlay.

    Attributes:
        name: Scenario name (used for CLI, reports).
        description: Human-readable description.
        overlay: Dict representing changes to apply to the base config.
    """
    name: str
    description: str
    overlay: Dict[str, Any]


def apply_scenario(
    base_config: Dict[str, Any],
    scenario: ScenarioDefinition,
) -> Dict[str, Any]:
    """
    Apply a ScenarioDefinition overlay to a base configuration.
    """
    return deep_merge(base_config, scenario.overlay)


def list_scenarios(
    scenarios: Iterable[ScenarioDefinition],
) -> List[Dict[str, Any]]:
    """
    Render a list of ScenarioDefinition as simple dicts for reporting/CLI.
    """
    return [
        {"name": s.name, "description": s.description}
        for s in scenarios
    ]


def compare_scenarios(
    base_config: Dict[str, Any],
    scenarios: Iterable[ScenarioDefinition],
    key_path: str,
) -> List[Dict[str, Any]]:
    """
    Compare base config and scenarios for a given dotted key path.

    Example:
        key_path = "Financing_Terms.tenor_years"

    Returns:
        List of dicts: [{"scenario": "BASE", "value": ...}, ...]
    """
    def resolve(cfg: Dict[str, Any], path: str) -> Any:
        cur: Any = cfg
        for part in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    base_value = resolve(base_config, key_path)
    results: List[Dict[str, Any]] = [{"scenario": "BASE", "value": base_value}]

    for s in scenarios:
        cfg_s = apply_scenario(base_config, s)
        results.append(
            {"scenario": s.name, "value": resolve(cfg_s, key_path)}
        )

    return results

    