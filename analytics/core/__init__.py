"""analytics.core

Core metrics and calculation utilities.
Foundation for all analytics modules.
"""

# Returns module - Project & Equity returns analytics
from analytics.core.returns import (
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
    # Returns module
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
