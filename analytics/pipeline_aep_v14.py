"""BACKWARD COMPATIBILITY SHIM: Import from analytics.wind.pipeline_aep_v14 instead.

This module provides backward compatibility for code that imports from the old
flat analytics/ structure. All functionality has moved to analytics/wind/.

OLD (deprecated but still works):
    from analytics.pipeline_aep_v14 import integrate_aep_pipeline

NEW (preferred):
    from analytics.wind.pipeline_aep_v14 import integrate_aep_pipeline
    from analytics.wind import integrate_aep_pipeline

DEPRECATION: This shim will be removed in Sprint 18 (Q1 2026).

Migration: Priority 4 Phase 2 (Wind backward compatibility)
Pattern: analytics/MODULE.py → analytics/wind/MODULE.py
GWTF R25: Feature branch migration, no main commits
"""

# Re-export everything from new location
from analytics.wind.pipeline_aep_v14 import *  # noqa: F401, F403
