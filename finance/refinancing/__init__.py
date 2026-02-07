"""
Refinancing Package for v14 Finance Models.

Sprint 16 Iteration 6 - Refinancing Package Creation
═══════════════════════════════════════════════════════════════════════════════════════
Consolidates all refinancing-related functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────────
From core module:
    - RefinancingEngine         # Main refinancing engine
    - calculate_refinancing     # Refinancing calculations
    - evaluate_refinancing_options  # Option evaluation

Backward Compatibility
────────────────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.refinancing_v14_hydra import RefinancingEngine

    # New way (recommended)
    from finance.refinancing import RefinancingEngine

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth for refinancing calculations
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples
"""

from __future__ import annotations

# Core module will be imported from refinancing_v14_hydra.py (source of truth)
# When source files are in place, they will be imported here

__all__ = [
    # Will be populated when modules are created
]

# EOF
