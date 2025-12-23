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

# Risk metrics module - VaR, CVaR, tail risk analytics
from analytics.core.risk_metrics import (
    CovenantBreachAnalysis,
    DownsideRisk,
    MetricRiskSummary,
    PercentileAnalysis,
    RiskConfig,
    TailRiskAnalyzer,
    TailRiskReport,
    VaRCVaRResult,
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
    # Risk metrics module
    "CovenantBreachAnalysis",
    "DownsideRisk",
    "MetricRiskSummary",
    "PercentileAnalysis",
    "RiskConfig",
    "TailRiskAnalyzer",
    "TailRiskReport",
    "VaRCVaRResult",
]
