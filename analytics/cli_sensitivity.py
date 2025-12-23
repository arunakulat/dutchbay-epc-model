"""BACKWARD COMPATIBILITY SHIM: Import from analytics.cli.cli_sensitivity instead.

This module provides backward compatibility for code that imports from the old
flat analytics/ structure. All functionality has moved to analytics/cli/.

⚠️ NOTE: The underlying cli_sensitivity.py is itself DEPRECATED (argparse-based).
Prefer analytics.cli.cli_sensitivity_hydra for new code.

OLD (deprecated but still works):
    from analytics.cli_sensitivity import main
    python analytics/cli_sensitivity.py scenario.yaml

NEW (preferred - Hydra-based):
    from analytics.cli.cli_sensitivity_hydra import main
    python analytics/cli/cli_sensitivity_hydra.py config=scenario.yaml

DEPRECATION TIMELINE:
- This shim: Removed Sprint 18 (Q1 2026)
- cli_sensitivity.py itself: Removed Sprint 18 (Q1 2026)
- Use cli_sensitivity_hydra.py instead

Migration: Priority 2 Phase 2 (CLI backward compatibility)
Pattern: analytics/MODULE.py → analytics/cli/MODULE.py
GWTF R25: Feature branch migration, no main commits
"""

# Re-export everything from new location
from analytics.cli.cli_sensitivity import *  # noqa: F401, F403
