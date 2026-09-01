"""Public analytics namespace with import-safe lazy compatibility exports.

Importing an ``analytics`` child module must not pull the evaluator or finance
surface into memory as a side effect. The historical eager facade did exactly
that through ``analytics.core``. PEP 562 lazy attributes preserve the public
``from analytics import ...`` API while allowing pure contract consumers to
load without an evaluator, finance, filesystem, or calculation graph.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
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
    from analytics.fx.fx_contracts import (
        FXCurveOutput,
        FXRiskProfile,
        FXStructuredBlock,
    )

_CONTRACT_EXPORTS: Final = (
    "CASPER_CONTRACT_VERSION",
    "BreakevenResult",
    "CasperResult",
    "MonteCarloResult",
    "MultiMetricSensitivitySuite",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "ScenarioResult",
    "SensitivityRequest",
    "SensitivitySuite",
    "ShockResult",
    "TornadoResult",
    "WaccComponents",
    "WaccResult",
)
_RETURN_EXPORTS: Final = (
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
)
_RISK_EXPORTS: Final = (
    "CovenantBreachAnalysis",
    "DownsideRisk",
    "MetricRiskSummary",
    "PercentileAnalysis",
    "RiskConfig",
    "TailRiskAnalyzer",
    "TailRiskReport",
    "VaRCVaRResult",
)
_FX_EXPORTS: Final = ("FXCurveOutput", "FXRiskProfile", "FXStructuredBlock")

_EXPORT_MODULES: Final[dict[str, str]] = {
    **{name: "analytics.contracts_v14" for name in _CONTRACT_EXPORTS},
    **{name: "analytics.core.returns" for name in _RETURN_EXPORTS},
    **{name: "analytics.core.risk_metrics" for name in _RISK_EXPORTS},
    **{name: "analytics.fx.fx_contracts" for name in _FX_EXPORTS},
}

__all__ = [
    "CASPER_CONTRACT_VERSION",
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
    "FXCurveOutput",
    "FXRiskProfile",
    "FXStructuredBlock",
    "MultiMetricSensitivitySuite",
    *_RETURN_EXPORTS,
    *_RISK_EXPORTS,
]


def __getattr__(name: str) -> Any:
    """Resolve one historical public export without eager graph loading."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose lazy compatibility names to interactive and inspection clients."""

    return sorted(set(globals()) | set(__all__))
