#!/usr/bin/env python3
"""
DutchBay EPC Model - v14 Finance Layer Public API

This module exposes the canonical v14 finance calculation engines used by
run_full_pipeline_v14.py and the analytics layer.

Note: This module uses lazy imports to avoid circular dependencies between
finance and analytics layers.
"""

from __future__ import annotations

__version__ = "0.3.0"
__author__ = "DutchBay EPC Model Team"

# =============================================================================
# Public API - Lazy Imports to Avoid Circular Dependencies
# =============================================================================


def __getattr__(name: str):
    """
    Lazy import mechanism to avoid circular dependencies.

    This allows analytics.evaluate_scenario to import finance.cashflow_v14
    without finance/__init__.py pre-importing everything.
    """
    # Core calculation engines
    if name == "build_annual_rows":
        from finance.cashflow_v14 import build_annual_rows

        return build_annual_rows

    if name == "apply_debt_layer":
        from finance.debt_v14 import apply_debt_layer

        return apply_debt_layer

    if name == "calculate_equity_performance":
        from finance.equity_v14 import calculate_equity_performance

        return calculate_equity_performance

    if name == "calculate_irr":
        from finance.irr import calculate_irr

        return calculate_irr

    if name == "calculate_wacc":
        from finance.wacc_v14 import calculate_wacc

        return calculate_wacc

    # Configuration objects
    if name == "IRRConfig":
        from finance.irr_config import IRRConfig

        return IRRConfig

    if name == "load_scenario_config":
        from finance.scenario_config import load_scenario_config

        return load_scenario_config

    # Helper utilities
    if name == "calculate_epc_breakdown":
        from finance.epc_helper_v14 import calculate_epc_breakdown

        return calculate_epc_breakdown

    if name == "as_float":
        from finance.utils import as_float

        return as_float

    if name == "get_nested":
        from finance.utils import get_nested

        return get_nested

    raise AttributeError(f"module 'finance' has no attribute '{name}'")


__all__ = [
    # Core calculation engines
    "build_annual_rows",
    "apply_debt_layer",
    "calculate_equity_performance",
    "calculate_irr",
    "calculate_wacc",
    # Configuration objects
    "IRRConfig",
    "load_scenario_config",
    # Helper utilities
    "calculate_epc_breakdown",
    "as_float",
    "get_nested",
]


def __dir__():
    """Support for dir(finance) and IDE autocomplete."""
    return __all__ + ["__version__", "__author__"]
