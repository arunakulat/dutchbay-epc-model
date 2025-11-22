"""Shim module to keep old dutchbay_v14chat.finance.debt imports working.

The canonical V14 debt engine now lives in finance.debt_v14.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from finance.debt_v14 import (
    apply_debt_layer as _apply_debt_layer_impl,
    plan_debt as _plan_debt_impl,
)


def apply_debt_layer(params: Dict[str, Any], annual_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Proxy to finance.debt_v14.apply_debt_layer."""
    return _apply_debt_layer_impl(params=params, annual_rows=annual_rows)


def plan_debt(*, annual_rows: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """Proxy to finance.debt_v14.plan_debt."""
    return _plan_debt_impl(annual_rows=annual_rows, config=config)
