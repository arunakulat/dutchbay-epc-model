"""
Architecture test: IRR/NPV functions must stay in finance.irr module only.

Purpose: Prevent duplicate IRR/NPV implementations and ensure single source of truth
in finance.irr module. The metrics module should only use finance.irr functions.

Go With The Flow: Architecture guardrails prevent technical debt.
"""

from __future__ import annotations

import importlib
import inspect
from typing import List

import pytest


def _find_irr_like_functions(module) -> List[str]:
    """Find any function names that look like IRR/NPV calculations."""
    irr_keywords = {
        "irr",
        "npv",
        "calculate_irr",
        "calculate_npv",
        "calc_irr",
        "calc_npv",
    }

    found = []
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if any(keyword in name.lower() for keyword in irr_keywords):
            # Exclude imports from finance.irr (only catch local definitions)
            if hasattr(obj, "__module__") and obj.__module__ == module.__name__:
                found.append(name)

    return found


def test_no_irr_npvs_in_metrics_module():
    """
    Architecture guardrail: IRR/NPV functions must NOT be in analytics.core.metrics.

    This test ensures that:
    1. IRR/NPV calculation logic lives ONLY in finance.irr
    2. metrics module imports and uses finance.irr, doesn't reimplement
    3. Single source of truth is maintained for financial calculations

    If this fails:
    - Move any calc_irr/calc_npv from analytics.core.metrics to finance.irr
    - Update analytics.core.metrics to import from finance.irr
    - Update any tests that reference metrics.calc_irr to use finance.irr.calculate_irr
    """
    metrics_module = importlib.import_module("analytics.core.metrics")

    names = _find_irr_like_functions(metrics_module)

    assert not names, (
        f"IRR/NPV-like functions must NOT be defined in analytics.core.metrics; "
        f"keep them only in finance.irr. Found: {names}. "
        f"Either move these to finance.irr or import them from finance.irr instead."
    )


def test_irr_functions_exist_in_finance_irr():
    """
    Verify that IRR/NPV functions ARE available in finance.irr module.
    """
    finance_irr = importlib.import_module("finance.irr")

    # At least one IRR function should exist
    irr_funcs = _find_irr_like_functions(finance_irr)

    assert irr_funcs, (
        "No IRR/NPV functions found in finance.irr. "
        "Expected at least calculate_irr or similar function."
    )


def test_metrics_imports_from_finance_irr():
    """
    Verify that metrics module properly imports IRR functions from finance.irr.
    """
    metrics_module = importlib.import_module("analytics.core.metrics")

    # Check if metrics has irr or npv in its namespace
    has_irr_import = any(
        name
        for name in dir(metrics_module)
        if "irr" in name.lower() or "npv" in name.lower()
    )

    # If metrics uses IRR/NPV, it should be imported, not defined locally
    if has_irr_import:
        # Verify it's an import (has __module__ pointing elsewhere)
        for name in dir(metrics_module):
            if "irr" in name.lower() or "npv" in name.lower():
                obj = getattr(metrics_module, name)
                if callable(obj) and hasattr(obj, "__module__"):
                    assert obj.__module__ != metrics_module.__name__, (
                        f"{name} should be imported from another module, "
                        f"not defined in metrics"
                    )
