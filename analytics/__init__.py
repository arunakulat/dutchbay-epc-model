"""Analytics Package - v14 Orchestration Layer.

Canonical entry point for v14 financial analytics, scenario management,
and reporting. Sits above finance/ engines.

**Core Modules:**
- scenario_loader: Load YAML scenarios
- scenario_manager: Batch scenario discovery
- scenario_analytics: Main orchestrator
- contracts_v14: API surface contracts

**Analysis Subpackages:**
- fx: Advanced FX modeling and risk analysis (independent, optional)
- core: Core analytics helpers (metrics, EPC)

**Exports:**
    from analytics import (
        load_scenario_config,
        ScenarioManager,
        ScenarioAnalytics,
    )

**Part of:** Sprint Day 5 (Task 2 - FX modularization)
"""
from __future__ import annotations

# Re-export key analytics APIs
from . import fx  # noqa: F401 - subpackage

__all__ = [
    'fx',  # FX/risk analytics subpackage
]
