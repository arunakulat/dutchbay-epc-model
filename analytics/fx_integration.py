"""BACKWARD COMPATIBILITY SHIM: Import from analytics.fx.fx_integration instead.

This module provides backward compatibility for code that imports from the old
flat analytics/ structure. All functionality has moved to analytics/fx/.

OLD (deprecated but still works):
    from analytics.fx_integration import integrate_fx_into_scenario_result

NEW (preferred):
    from analytics.fx.fx_integration import integrate_fx_into_scenario_result
    from analytics.fx import integrate_fx_into_scenario_result

DEPRECATION: This shim will be removed in Sprint 18 (Q1 2026).

Migration: Priority 3 Phase 2 (FX backward compatibility)
Pattern: analytics/MODULE.py → analytics/fx/MODULE.py
GWTF R25: Feature branch migration, no main commits
"""

# Re-export everything from new location
from analytics.fx.fx_integration import *  # noqa: F401, F403
