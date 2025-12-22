"""DEPRECATED: Use analytics.core.returns instead.

This module will be removed in a future release.
Please update imports to: from analytics.core.returns import ...
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "analytics.returns is deprecated. "
    "Use 'from analytics.core.returns import ...' instead. "
    "This shim will be removed in Sprint 17.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from analytics.core.returns import (  # noqa: F401, E402
    AllReturns,
    EquityReturns,
    ProjectReturns,
    ReturnsConfig,
    calculate_equity_returns,
    calculate_irr,
    calculate_mirr,
    calculate_npv,
    calculate_project_returns,
    summarize_all_returns,
)

__all__ = [
    "AllReturns",
    "EquityReturns",
    "ProjectReturns",
    "ReturnsConfig",
    "calculate_equity_returns",
    "calculate_irr",
    "calculate_mirr",
    "calculate_npv",
    "calculate_project_returns",
    "summarize_all_returns",
]
