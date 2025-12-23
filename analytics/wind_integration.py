"""BACKWARD COMPATIBILITY SHIM: Import from analytics.wind.wind_integration instead.

This module provides backward compatibility for code that imports from the old
flat analytics/ structure. All functionality has moved to analytics/wind/.

OLD (deprecated but still works):
    from analytics.wind_integration import load_aep_for_project

NEW (preferred):
    from analytics.wind.wind_integration import load_aep_for_project
    from analytics.wind import load_aep_for_project

DEPRECATION: This shim will be removed in Sprint 18 (Q1 2026).

Migration: Priority 4 Phase 2 (Wind backward compatibility)
Pattern: analytics/MODULE.py → analytics/wind/MODULE.py
GWTF R25: Feature branch migration, no main commits
"""

# Re-export everything from new location
from analytics.wind.wind_integration import *  # noqa: F401, F403
