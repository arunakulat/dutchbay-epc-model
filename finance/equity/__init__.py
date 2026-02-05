"""
Equity Package for v14 Finance Models.

Sprint 16 Iteration 6 - Equity Package Creation
═══════════════════════════════════════════════════════════════════════════════════════
Consolidates all equity-related functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────────
From core module:
    - EquityCalculator          # Main equity calculation engine
    - calculate_equity_irr      # Equity IRR calculations
    - calculate_distributions   # Distribution calculations

From distribution:
    - EquityDistributionEngine  # Distribution engine
    - calculate_dividend_policy # Dividend policy calculations

Backward Compatibility
────────────────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.equity_v14 import EquityCalculator
    from finance.equity_distribution_v14_hydra import EquityDistributionEngine

    # New way (recommended)
    from finance.equity import EquityCalculator
    from finance.equity import EquityDistributionEngine

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth for equity calculations
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples
"""

from __future__ import annotations

# Core module will be imported from equity_v14.py (source of truth)
# When source files are in place, they will be imported here

__all__ = [
    # Will be populated when modules are created
]

# EOF
