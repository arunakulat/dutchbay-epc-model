"""
Scenario management package for v14 analytics.

Provides unified scenario loading, discovery, and analytics capabilities.

Sprint 16 Reorganization
────────────────────────
Consolidates fragmented scenario utilities into single organized package:
- scenario_loader.py (production)
- scenarioloader.py (legacy compat)
- scenario_manager.py (discovery)
- scenario_analytics.py (analysis)
- evaluate_scenario.py (evaluation)

Public API
──────────
From loader:
    - load_scenario_config()  # Production loader
    - ScenarioConfigError     # Error type

From legacy (backward compat):
    - loadscenarioconfig()    # Legacy name

From manager:
    - ScenarioManager         # Discovery class

From analytics:
    - compare_scenarios()     # Comparison utilities
    - analyze_scenario()      # Analysis helpers

Backward Compatibility
──────────────────────
All old imports continue to work:
    from analytics.scenario_loader import load_scenario_config  # Still works
    from analytics.scenarioloader import loadscenarioconfig    # Still works
    from analytics.scenarios import load_scenario_config        # New way
"""

from __future__ import annotations

# Re-export production loader (primary API)
from analytics.scenario_loader import (
    ScenarioConfigError,
    load_scenario_config,
    _resolve_fx,
)

# Re-export legacy loader for backward compatibility
from analytics.scenarioloader import loadscenarioconfig

# Re-export manager
from analytics.scenario_manager import ScenarioManager

# Re-export analytics
# Note: scenario_analytics.py will be analyzed and potentially reorganized


__all__ = [
    # Production API
    "load_scenario_config",
    "ScenarioConfigError",
    "_resolve_fx",
    # Legacy API
    "loadscenarioconfig",
    # Management
    "ScenarioManager",
]

# EOF
