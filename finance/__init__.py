#!/usr/bin/env python3
"""
DutchBay EPC Model - v14 Finance Layer Public API

This module exposes the canonical v14 finance calculation engines used by
run_full_pipeline_v14.py and the analytics layer.

Public API Design Principles:
    1. Only expose functions/classes used by run_v14_pipeline()
    2. All exports are mypy-clean and fully typed
    3. Internal helpers remain private (no underscore exports)
    4. Config objects are exposed for type hints in client code

Canonical Entrypoint:
    >>> from run_full_pipeline_v14 import run_v14_pipeline
    >>> result = run_v14_pipeline("scenarios/example_a.yaml", validation_mode="strict")

Direct Finance API Usage:
    >>> from finance import build_annual_rows, apply_debt_layer, calculate_wacc
    >>> from analytics.scenario_loader import load_scenario_config
    >>> 
    >>> config = load_scenario_config("scenarios/example_a.yaml")
    >>> annual_rows = build_annual_rows(config)
    >>> debt_result = apply_debt_layer(config, annual_rows)
    >>> wacc = calculate_wacc(config)

Version History:
    0.1.0 - Initial v14 finance stack (cashflow, debt, equity)
    0.2.0 - Added WACC, IRR config, EPC helper
    0.3.0 - Promoted from dutchbay_v14chat to canonical finance/
"""

from __future__ import annotations

__version__ = "0.3.0"
__author__ = "DutchBay EPC Model Team"

# =============================================================================
# Core Calculation Engines (Primary Public API)
# =============================================================================

from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import apply_debt_layer
from finance.equity_v14 import calculate_equity_returns
from finance.irr import calculate_irr
from finance.wacc_v14 import calculate_wacc

# =============================================================================
# Configuration & Schema Objects
# =============================================================================

from finance.irr_config import IRRConfig
from finance.scenario_config import load_scenario_config

# =============================================================================
# Helper Utilities
# =============================================================================

from finance.epc_helper_v14 import calculate_epc_breakdown
from finance.utils import as_float, get_nested

# =============================================================================
# Public API Surface
# =============================================================================

__all__ = [
    # Core calculation engines
    "build_annual_rows",        # Cashflow projection engine
    "apply_debt_layer",         # Debt schedule & DSCR calculator
    "calculate_equity_returns", # Equity IRR & NPV
    "calculate_irr",            # Standalone IRR solver
    "calculate_wacc",           # WACC calculation
    
    # Configuration objects
    "IRRConfig",                # IRR solver configuration
    "load_scenario_config",     # Scenario YAML/JSON loader
    
    # Helper utilities
    "calculate_epc_breakdown",  # EPC cost breakdown
    "as_float",                 # Safe float conversion
    "get_nested",              # Nested dict accessor
    
    # Module metadata
    "__version__",
]

# =============================================================================
# Verification: Ensure All Exports Exist
# =============================================================================

def _verify_exports() -> None:
    """
    Runtime verification that all __all__ exports are actually importable.
    
    This function is called at module import time to catch any missing
    exports before they cause runtime errors in client code.
    
    Raises:
        ImportError: If any export in __all__ is not defined
    """
    import sys
    current_module = sys.modules[__name__]
    
    missing_exports = []
    for export_name in __all__:
        if export_name.startswith("__"):
            continue  # Skip dunder names like __version__
        if not hasattr(current_module, export_name):
            missing_exports.append(export_name)
    
    if missing_exports:
        raise ImportError(
            f"finance/__init__.py: Missing exports in __all__: {missing_exports}. "
            f"This indicates a mismatch between declared public API and actual imports."
        )

# Run verification at import time
_verify_exports()
