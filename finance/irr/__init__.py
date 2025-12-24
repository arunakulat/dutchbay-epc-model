# ruff: noqa: E402
"""
IRR (Internal Rate of Return) Package for v14 Finance Models.

Sprint 16 Iteration 6 - IRR Package Creation
═══════════════════════════════════════════════════════════════════════════════════
Consolidates all IRR calculation functionality into a unified package.

Public API
────────────────────────────────────────────────────────────────────────────────────
From core module (finance.irr root file):
    - npv                       # Classic periodic Net Present Value
    - irr                       # Periodic Internal Rate of Return
    - xnpv                      # Date-adjusted Net Present Value
    - xirr                      # Date-adjusted Internal Rate of Return
    - project_npv_from_cfads    # Project NPV calculation
    - approx_project_irr        # Approximate project IRR

Backward Compatibility
────────────────────────────────────────────────────────────────────────────────────
All old imports continue to work:

    # Old way (still works)
    from finance.irr import npv, irr
    
    # New way (also works - same object)
    from finance.irr import npv, irr

Both import patterns resolve to the same functions defined in finance/irr.py.

Architecture Principles
────────────────────────────────────────────────────────────────────────────────────
GWTF:     Single source of truth: finance/irr.py at root
CESSPIT:  Comprehensive input validation with fail-fast errors
CASPER:   Contract-first design with explicit types
CCCDIR:   Fully documented with usage examples

Usage Examples
────────────────────────────────────────────────────────────────────────────────────
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

import sys
from pathlib import Path

# Add parent directory to path to import from finance.irr module (not package)
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

# Import from the irr.py file at finance root (not this package)
# We use importlib to avoid circular import issues
import importlib.util

_irr_module_path = _parent / "irr.py"
if not _irr_module_path.exists():
    raise ImportError(
        f"Cannot find finance/irr.py source file at {_irr_module_path}. "
        "The IRR package requires finance/irr.py to exist at the parent level."
    )

_spec = importlib.util.spec_from_file_location("_finance_irr_module", _irr_module_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load IRR module from {_irr_module_path}")

_irr_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_irr_module)

# Re-export all public functions
npv = _irr_module.npv
irr = _irr_module.irr
xnpv = _irr_module.xnpv
xirr = _irr_module.xirr
project_npv_from_cfads = _irr_module.project_npv_from_cfads
approx_project_irr = _irr_module.approx_project_irr

__all__ = [
    "npv",
    "irr",
    "xnpv",
    "xirr",
    "project_npv_from_cfads",
    "approx_project_irr",
]

# EOF
