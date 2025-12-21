"""
IRR (Internal Rate of Return) Package for v14 Finance Models.

Sprint 16 Iteration 6 - IRR Package Creation
═══════════════════════════════════════════════════════════════════════════════════════
Consolidates all IRR calculation functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────────
From core module (finance.irr):
    - npv                       # Classic periodic Net Present Value
    - irr                       # Periodic Internal Rate of Return
    - xnpv                      # Date-adjusted Net Present Value
    - xirr                      # Date-adjusted Internal Rate of Return
    - project_npv_from_cfads    # Project NPV calculation
    - approx_project_irr        # Approximate project IRR

Backward Compatibility
────────────────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.irr import npv, irr
    
    # New way (also works - same object)
    from finance.irr import npv, irr

Both import patterns resolve to the same functions defined in finance/irr.py.

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth: finance/irr.py at root
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples

Usage Examples
────────────────────────────────────────────────────────────────────────────────────────
Basic NPV calculation:

    >>> from finance.irr import npv
    >>> cashflows = [-100, 30, 30, 30, 30]
    >>> rate = 0.10  # 10% discount rate
    >>> result = npv(rate, cashflows)
    >>> print(f"NPV: ${result:,.2f}")

Basic IRR calculation:

    >>> from finance.irr import irr
    >>> cashflows = [-100, 30, 30, 30, 30]
    >>> rate = irr(cashflows)
    >>> print(f"IRR: {rate:.2%}")

Project-level NPV:

    >>> from finance.irr import project_npv_from_cfads
    >>> cfads = [10, 12, 15, 18, 20]  # Million USD
    >>> capex = 50  # Million USD
    >>> discount_rate = 0.08
    >>> project_npv = project_npv_from_cfads(discount_rate, cfads, capex)
    >>> print(f"Project NPV: ${project_npv:.2f}M")

Date-aware XIRR:

    >>> from datetime import datetime
    >>> from finance.irr import xirr
    >>> cashflows = [-100, 30, 30, 30, 30]
    >>> dates = [
    ...     datetime(2024, 1, 1),
    ...     datetime(2024, 6, 15),
    ...     datetime(2025, 3, 20),
    ...     datetime(2025, 11, 10),
    ...     datetime(2026, 12, 31),
    ... ]
    >>> rate = xirr(cashflows, dates)
    >>> print(f"XIRR: {rate:.2%}")
"""

from __future__ import annotations

# Re-export all IRR functionality from the canonical source: finance.irr
# Source of truth remains at root for maximum backward compatibility
from finance.irr import (
    approx_project_irr,
    irr,
    npv,
    project_npv_from_cfads,
    xirr,
    xnpv,
)

__all__ = [
    "npv",
    "irr",
    "xnpv",
    "xirr",
    "project_npv_from_cfads",
    "approx_project_irr",
]

# EOF
