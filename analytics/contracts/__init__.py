from __future__ import annotations

from ._phase_3_sensitivity import (
    SensitivitySuite,
    ShockResult,
    ShockSpec,
    StandardShockLibrary,
)

# ═════════════════════════════════════════════════════════════════════════════
# CONTRACTS PACKAGE __init__.py
# ═════════════════════════════════════════════════════════════════════════════
# Location: analytics/contracts/__init__.py
#
# This file re-exports all sensitivity contracts from the modular structure.
# External code imports from here:
#
#   from analytics.contracts import ShockSpec, ShockResult, SensitivitySuite, StandardShockLibrary
#


__all__ = [
    "ShockSpec",
    "ShockResult",
    "SensitivitySuite",
    "StandardShockLibrary",
]
