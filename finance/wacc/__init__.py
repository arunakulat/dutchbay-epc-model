"""
WACC (Weighted Average Cost of Capital) Package for v14 Finance Models.

Sprint 16 Iteration 6 - WACC Package Creation
═══════════════════════════════════════════════════════════════════════════════════════
Consolidates all WACC calculation functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────────
From core module:
    - WaccCalculatorV14         # Main WACC calculator
    - calculate_wacc            # Standalone WACC calculation
    - calculate_cost_of_equity  # Cost of equity (CAPM)
    - calculate_cost_of_debt    # Cost of debt

From integration:
    - wacc_integration          # Integration utilities
    - integrate_wacc_with_cashflow  # Cashflow integration

Backward Compatibility
────────────────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.wacc_v14 import WaccCalculatorV14
    from finance.wacc_v14 import calculate_wacc
    from finance.wacc_integration import wacc_integration
    
    # New way (recommended)
    from finance.wacc import WaccCalculatorV14
    from finance.wacc import calculate_wacc
    from finance.wacc import wacc_integration

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth for WACC calculations
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples
"""

from __future__ import annotations

# Core module will be imported from wacc_v14.py (source of truth)
# When source files are in place, they will be imported here

__all__ = [
    # Will be populated when modules are created
]

# EOF
