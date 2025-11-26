from __future__ import annotations

"""
Legacy shim for v14 cashflow functions.

For backward-compatible imports such as:

    from dutchbay_v14chat.finance.cashflow import (
        build_annual_rows,
        _extract_parameters,
        _extract_project_life_years,
    )

this module simply re-exports the canonical v14 implementations from
finance.cashflow_v14.

The v14chat layer is intentionally a thin wrapper so that analytics and
finance logic remain anchored under the main `finance/` package.
"""

from typing import Any, Dict, Sequence

from finance.cashflow_v14 import (  # type: ignore[import-not-found]
    build_annual_rows,
    _extract_parameters,
    _extract_project_life_years,
)

__all__ = [
    "build_annual_rows",
    "_extract_parameters",
    "_extract_project_life_years",
]


# Explicit re-bindings for static checkers and introspection tools.


def build_annual_rows(config: Dict[str, Any]) -> Sequence[Dict[str, Any]]:
    """
    Public v14chat-facing entry point for annual cashflow rows.

    Delegates to finance.cashflow_v14.build_annual_rows.
    """
    return _build_annual_rows_impl(config)


def _build_annual_rows_impl(config: Dict[str, Any]) -> Sequence[Dict[str, Any]]:
    # Import at top-level for mypy friendliness; this function exists to keep
    # a clear seam in case we ever need logging/instrumentation here.
    from finance.cashflow_v14 import build_annual_rows as _inner

    return _inner(config)


def _extract_parameters(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Re-export of finance.cashflow_v14._extract_parameters for legacy tests.
    """
    from finance.cashflow_v14 import _extract_parameters as _inner

    return _inner(config)


def _extract_project_life_years(config: Dict[str, Any]) -> int:
    """
    Re-export of finance.cashflow_v14._extract_project_life_years.

    This is what tests/api/test_cashflow_v14.py expects to import from
    dutchbay_v14chat.finance.cashflow.
    """
    from finance.cashflow_v14 import _extract_project_life_years as _inner

    return _inner(config)
