"""
IRR (Internal Rate of Return) Package for v14 Finance Models.

Sprint 16 Iteration 6 - IRR Package Creation
═══════════════════════════════════════════════════════════════════════════════════════
Consolidates all IRR calculation functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────────
From core module:
    - calculate_irr             # Main IRR calculation
    - calculate_project_irr     # Project-level IRR
    - calculate_equity_irr      # Equity-level IRR
    - calculate_mirr            # Modified IRR

From config:
    - IRRConfig                 # IRR calculation configuration
    - IRRResult                 # IRR calculation results

Backward Compatibility
────────────────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.irr import calculate_irr
    from finance.irr_config import IRRConfig
    
    # New way (recommended)
    from finance.irr import calculate_irr
    from finance.irr import IRRConfig

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth for IRR calculations
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples
"""

from __future__ import annotations

# Core module will be imported from irr.py (source of truth)
# When source files are in place, they will be imported here

__all__ = [
    # Will be populated when modules are created
]

# EOF
