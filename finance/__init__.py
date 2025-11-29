#!/usr/bin/env python3
"""
DutchBay EPC Model - v14 Finance Layer Public API

This module exposes the canonical v14 finance calculation engines used by
run_full_pipeline_v14.py and the analytics layer.

Note: This module uses lazy imports to avoid circular dependencies between
finance and analytics layers.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.3.0"
__author__ = "DutchBay EPC Model Team"

# =============================================================================
# Public API - Lazy Imports to Avoid Circular Dependencies
# =============================================================================


def __getattr__(name: str) -> Any:
    """
    Lazy import mechanism to avoid circular dependencies.

    This allows analytics.evaluate_scenario to import finance.cashflow_v14
    without finance/__init__.py pre-importing everything.

    Parameters
    ----------
    name : str
        Attribute name to import.

    Returns
    -------
    Any
        The imported function/class/object.

    Raises
    ------
    AttributeError
        If the requested attribute doesn't exist.
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
        # TODO(mypy): Verify this function exists in finance.irr
        # from finance.irr import calculate_irr
        raise AttributeError(
            f"'{name}' is not currently exported. "
            "Check finance.irr for actual function name."
        )

    if name == "calculate_wacc":
        from finance.wacc_v14 import calculate_real_wacc as calculate_wacc

        return calculate_wacc

    # Configuration objects
    if name == "IRRConfig":
        # TODO(mypy): Verify this class exists in finance.irr_config
        # from finance.irr_config import IRRConfig
        raise AttributeError(
            f"'{name}' is not currently exported. "
            "Check finance.irr_config for actual class name."
        )

    if name == "load_scenario_config":
        # TODO(mypy): This function moved to analytics.scenario_loader
        # from finance.scenario_config import load_scenario_config
        raise AttributeError(
            f"'{name}' moved to analytics.scenario_loader. "
            "Use: from analytics.scenario_loader import load_scenario_config"
        )

    # Helper utilities
    if name == "calculate_epc_breakdown":
        # TODO(mypy): Verify this function exists in finance.epc_helper_v14
        # from finance.epc_helper_v14 import calculate_epc_breakdown
        raise AttributeError(
            f"'{name}' is not currently exported. "
            "Check finance.epc_helper_v14 for actual function name."
        )

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
    "calculate_wacc",  # Note: calculate_irr removed until verified
    # Configuration objects - removed until verified
    # "IRRConfig",
    # "load_scenario_config",
    # Helper utilities
    "as_float",
    "get_nested",
    # Note: calculate_epc_breakdown removed until verified
]


def __dir__() -> list[str]:
    """
    Support for dir(finance) and IDE autocomplete.

    Returns
    -------
    list[str]
        List of public attributes.
    """
    return __all__ + ["__version__", "__author__"]


# EOF
