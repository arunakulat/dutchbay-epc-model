"""Shim module for v14 cashflow.

This keeps the legacy import path dutchbay_v14chat.finance.cashflow
working while delegating all logic to finance.cashflow_v14.
"""

from __future__ import annotations

from finance.cashflow_v14 import (
    calculate_single_year_cfads,
    build_annual_cfads,
    build_annual_rows,
)

__all__ = [
    "calculate_single_year_cfads",
    "build_annual_cfads",
    "build_annual_rows",
]
