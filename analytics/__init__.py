"""Analytics module for DutchBay EPC Model.

Contracts status:
- contracts_v14.py: frozen dataclasses with a Pydantic-compatible ``model_dump()``
  facade (it deliberately uses ``@dataclass`` + ``dataclasses.asdict`` for
  serialization and does NOT provide Pydantic field-level validation; the
  serialization layer accepts both dataclasses and Pydantic objects).
- returns.py: Project & equity returns (IRR, NPV, MIRR)
- risk_metrics.py: Tail risk analytics (VaR, CVaR)

Sprint 16 Planned:
- Add Pydantic V2 contracts for returns and risk outputs
"""

# Core contracts (frozen dataclasses) - ONLY import what exists in contracts_v14.py
from analytics.contracts_v14 import (
    CASPER_CONTRACT_VERSION,
    BreakevenResult,
    CasperResult,
    MonteCarloResult,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
    ParameterRangeConfig,
    ScenarioResult,
    SensitivityRequest,
    SensitivitySuite,
    ShockResult,
    TornadoResult,
    WaccComponents,
    WaccResult,
)

# Returns calculation module
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

# Risk metrics module
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

# FX contracts
from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
)

# (The analytics.contracts_v14_compat stub layer is fully retired. The
# DownsideMetrics/TailRiskMetrics stubs went in audit R2; the last symbol,
# build_cashflow_result_from_annual_rows, had ZERO real callers — the "live
# production callers" note was stale — so the module is removed. The canonical
# MultiMetricSensitivitySuite/DownsideMetrics live in analytics.contracts_v14.)


__all__ = [
    # Contract version
    "CASPER_CONTRACT_VERSION",
    # Core contracts (frozen dataclasses)
    "BreakevenResult",
    "CasperResult",
    "MonteCarloResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "ScenarioResult",
    "SensitivityRequest",
    "SensitivitySuite",
    "ShockResult",
    "TornadoResult",
    "WaccComponents",
    "WaccResult",
    # FX contracts
    "FXCurveOutput",
    "FXRiskProfile",
    "FXStructuredBlock",
    # Legacy compatibility (Sprint 16 removal)
    "MultiMetricSensitivitySuite",
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
