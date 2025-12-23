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

# Parameter solvers - Reverse-engineering for Monte Carlo
from analytics.core.parameter_solvers import (
    SOLVER_REGISTRY,
    get_solver,
    solve_for_max_debt_given_dscr,
    solve_for_max_debt_multi_covenant,
    solve_for_min_capex_given_irr_floor,
    solve_for_tariff_given_irr,
    solve_for_tariff_given_npv,
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
    # Parameter solvers
    "SOLVER_REGISTRY",
    "get_solver",
    "solve_for_max_debt_given_dscr",
    "solve_for_max_debt_multi_covenant",
    "solve_for_min_capex_given_irr_floor",
    "solve_for_tariff_given_irr",
    "solve_for_tariff_given_npv",
]
