"""
Backward-compatibility shim for legacy imports.

tests/api/test_tax_v14_lender_golden.py expects:

    from analytics.evaluationv14 import evaluatewithoverrides

The canonical implementation now lives in analytics.evaluation_v14
with the function name evaluate_with_overrides.

This module simply forwards the old name to the new gateway.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from analytics.evaluation_v14 import evaluate_with_overrides as _evaluate_with_overrides


def evaluatewithoverrides(
    config_path: str | Path,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """
    Legacy alias for `analytics.evaluation_v14.evaluate_with_overrides`.

    Parameters
    ----------
    config_path : str | Path
        Path to YAML scenario configuration file.
    overrides : Mapping[str, Any] | None
        Optional nested dict for in-memory parameter overrides.

    Returns
    -------
    dict[str, float]
        Flat KPI dict with numeric values.
    """
    return _evaluate_with_overrides(config_path=config_path, overrides=overrides)
