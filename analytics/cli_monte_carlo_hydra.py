"""BACKWARD COMPATIBILITY SHIM: Import from analytics.cli.cli_monte_carlo_hydra instead.

This module provides backward compatibility for code that imports from the old
flat analytics/ structure. All functionality has moved to analytics/cli/.

OLD (deprecated but still works):
    from analytics.cli_monte_carlo_hydra import main
    python analytics/cli_monte_carlo_hydra.py config=...

NEW (preferred):
    from analytics.cli.cli_monte_carlo_hydra import main
    python analytics/cli/cli_monte_carlo_hydra.py config=...

DEPRECATION: This shim will be removed in Sprint 18 (Q1 2026).

Migration: Priority 2 Phase 2 (CLI backward compatibility)
Pattern: analytics/MODULE.py → analytics/cli/MODULE.py
GWTF R25: Feature branch migration, no main commits
"""

# Re-export everything from new location
from analytics.cli.cli_monte_carlo_hydra import *  # noqa: F401, F403
