#!/usr/bin/env python3
"""
analytics.evaluation_v14_legacy

Backward-compatibility shim for legacy camelCase imports.

Historical Context
------------------
Older code (especially pre-refactor tests) expected:
    from analytics.evaluationv14 import evaluatewithoverrides

After v14 refactoring, the canonical implementation moved to:
    from analytics.evaluation_v14 import evaluate_with_overrides (snake_case)

This module bridges the gap, allowing legacy imports to continue working
while encouraging migration to the new snake_case API.

Migration Path
--------------
Old code:
    from analytics.evaluationv14 import evaluatewithoverrides
    result = evaluatewithoverrides(config_path)

New code:
    from analytics.evaluation_v14 import evaluate_with_overrides
    result = evaluate_with_overrides(config_path=config_path)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from analytics.evaluation_v14 import evaluate_with_overrides as _evaluate_with_overrides

__all__ = ["evaluatewithoverrides"]


def evaluatewithoverrides(
    config_path: str | Path,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """
    Legacy alias for `analytics.evaluation_v14.evaluate_with_overrides`.

    ⚠️  Deprecated: Use `analytics.evaluation_v14.evaluate_with_overrides` instead.

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

    Examples
    --------
    >>> from analytics.evaluation_v14_legacy import evaluatewithoverrides
    >>> result = evaluatewithoverrides("path/to/config.yaml")
    >>> result["project_irr"]
    0.12
    """
    return _evaluate_with_overrides(config_path=config_path, overrides=overrides)
