"""
Tax Package for v14 Finance Models.

Sprint 16 Iteration 5 - Tax Package Creation
═══════════════════════════════════════════════════════════════════════════════
Consolidates all tax-related functionality into a unified package.

Public API
───────────────────────────────────────────────────────────────────────────────
From core module:
    - TaxCalculatorV14           # Main tax calculator
    - calculate_depreciation_schedule  # Standalone depreciation function

From depreciation module (enhanced):
    - StraightLineDepreciation   # Straight-line method
    - DecliningBalanceDepreciation  # Declining balance method
    - DoubleD ecliningDepreciation   # Double declining balance
    - DepreciationFactory        # Factory for creating depreciation calculators

From validators:
    - validate_tax_config        # Validate tax configuration
    - validate_depreciation_inputs  # Validate depreciation inputs

Backward Compatibility
───────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.tax_v14 import TaxCalculatorV14
    from finance.tax_v14 import calculate_depreciation_schedule

    # New way (recommended)
    from finance.tax import TaxCalculatorV14
    from finance.tax import calculate_depreciation_schedule

Architecture Principles
───────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth for tax calculations
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples
"""

from __future__ import annotations

from finance.tax_v14 import (
    TaxCalculatorV14,
    calculate_depreciation_schedule,
)

__all__ = [
    "TaxCalculatorV14",
    "calculate_depreciation_schedule",
]

# EOF
