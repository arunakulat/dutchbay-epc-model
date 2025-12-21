"""
Cashflow Package for v14 Finance Models.

Sprint 16 Iteration 6 - Cashflow Package Creation
═══════════════════════════════════════════════════════════════════════════════════════
Consolidates all cashflow-related functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────────
From core module:
    - CashFlowEngine            # Main cashflow calculation engine
    - generate_cashflow_v14     # Top-level generation function

From utils:
    - cashflow_utilities        # Helper functions (from cashflow_v14_utils.py)

From params:
    - cashflow_parameters       # Parameter management (from cashflow_v14_params.py)

From contracts:
    - cashflow_contracts        # Pydantic contracts (from cashflow_v14_contracts.py)

From variants:
    - cashflow_with_tax         # Tax-integrated variant (cashflow_v14_tax.py)
    - cashflow_with_fx          # FX-integrated variant (cashflow_v14_fx.py)
    - cashflow_production       # Production schedules (cashflow_v14_production.py)

Backward Compatibility
────────────────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.cashflow_v14 import CashFlowEngine
    from finance.cashflow_v14_utils import cashflow_utilities
    from finance.cashflow_v14_tax import cashflow_with_tax
    
    # New way (recommended)
    from finance.cashflow import CashFlowEngine
    from finance.cashflow import cashflow_utilities
    from finance.cashflow import cashflow_with_tax

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth for cashflow calculations
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples
"""

from __future__ import annotations

# Core module will be imported from cashflow_v14.py (source of truth)
# When source files are in place, they will be imported here

__all__ = [
    # Will be populated when modules are created
]

# EOF
