"""Shim module for v14 IRR/NPV helpers.

This keeps the legacy import path dutchbay_v14chat.finance.irr
working while delegating all logic to finance.irr.
"""

from __future__ import annotations

from finance.irr import (
    npv,
    irr,
    xnpv,
    xirr,
)

__all__ = [
    "npv",
    "irr",
    "xnpv",
    "xirr",
]
