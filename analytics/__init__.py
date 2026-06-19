"""Analytics module for DutchBay EPC Model.

Pydantic v2 Migration Status (Sprint 15):
- contracts_v14.py: Fully migrated to Pydantic V2 ✅
- returns.py: Project & equity returns (IRR, NPV, MIRR)
- risk_metrics.py: Tail risk analytics (VaR, CVaR)

Sprint 16 Planned:
- Add Pydantic V2 contracts for returns and risk outputs
"""

# Core contracts (Pydantic V2) - ONLY import what exists in contracts_v14.py
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

# Legacy compatibility stubs (temporary - Sprint 16)
# NOTE: MultiMetricSensitivitySuite is no longer a compat stub — it is the
# canonical contracts_v14 dataclass, imported above (ARCH-04, issue #118).
from analytics.contracts_v14_compat import (
    DownsideMetrics,
    TailRiskMetrics,
    build_cashflow_result_from_annual_rows,
)

# FX contracts
from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
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

__all__ = [
    # Contract version
    "CASPER_CONTRACT_VERSION",
    # Core Pydantic V2 Contracts
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
    "DownsideMetrics",
    "MultiMetricSensitivitySuite",
    "TailRiskMetrics",
    "build_cashflow_result_from_annual_rows",
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
