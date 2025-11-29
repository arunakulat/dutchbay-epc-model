#!/usr/bin/env python3
"""
DutchBay v14 Analytics Layer - Production Release

Scenario analysis, sensitivity, Monte Carlo, and reporting for v14 finance engine.

Note: Uses lazy imports to avoid circular dependencies with finance layer.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.2.1"
__author__ = "DutchBay EPC Model Team"

# =============================================================================
# Public API - Lazy Imports to Avoid Circular Dependencies
# =============================================================================


def __getattr__(name: str) -> Any:
    """
    Lazy import mechanism to avoid circular dependencies.

    The analytics layer imports from finance.cashflow_v14, which imports
    analytics.config_schema. If analytics/__init__.py eagerly imports
    evaluate_scenario, we get a circular import. Lazy loading fixes this.
    """
    if name == "evaluate_with_overrides":
        from analytics.evaluate_scenario import evaluate_with_overrides

        return evaluate_with_overrides

    if name == "load_scenario_config":
        from analytics.scenario_loader import load_scenario_config

        return load_scenario_config

    if name == "ScenarioAnalytics":
        from analytics.scenario_analytics import ScenarioAnalytics

        return ScenarioAnalytics

    if name == "evaluate_scenario_as_dict":
        # from analytics.evaluate_scenario import evaluate_scenario_as_dict  # TODO: Verify

        raise AttributeError(f"'{name}' not implemented yet")

    raise AttributeError(f"module 'analytics' has no attribute '{name}'")


__all__ = [
    # Core API (canonical)
    "evaluate_with_overrides",
    "load_scenario_config",
    # Batch processing
    "ScenarioAnalytics",
    # Legacy compatibility
    "evaluate_scenario_as_dict",
]


def __dir__() -> list[str]:
    """Support for dir(analytics) and IDE autocomplete."""
    return __all__ + ["__version__", "__author__"]
