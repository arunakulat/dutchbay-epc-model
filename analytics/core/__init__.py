"""Core analytics namespace with cycle-safe lazy compatibility exports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from analytics.core.parameter_solvers import (  # noqa: F401
        SOLVER_REGISTRY,
        get_solver,
        solve_for_max_debt_given_dscr,
        solve_for_max_debt_multi_covenant,
        solve_for_min_capex_given_irr_floor,
        solve_for_tariff_given_equity_irr,
        solve_for_tariff_given_irr,
        solve_for_tariff_given_npv,
        solve_tariff_breakeven,
    )
    from analytics.core.returns import (  # noqa: F401
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
    from analytics.core.risk_metrics import (  # noqa: F401
        CovenantBreachAnalysis,
        DownsideRisk,
        MetricRiskSummary,
        PercentileAnalysis,
        RiskConfig,
        TailRiskAnalyzer,
        TailRiskReport,
        VaRCVaRResult,
    )
    from analytics.core.sensitivity_runner import (  # noqa: F401
        run_sensitivity_analysis,
        run_sensitivity_analysis_from_path,
    )

_PARAMETER_EXPORTS: Final = (
    "SOLVER_REGISTRY",
    "get_solver",
    "solve_for_max_debt_given_dscr",
    "solve_for_max_debt_multi_covenant",
    "solve_for_min_capex_given_irr_floor",
    "solve_for_tariff_given_equity_irr",
    "solve_for_tariff_given_irr",
    "solve_for_tariff_given_npv",
    "solve_tariff_breakeven",
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
_SENSITIVITY_EXPORTS: Final = (
    "run_sensitivity_analysis",
    "run_sensitivity_analysis_from_path",
)

_EXPORT_MODULES: Final[dict[str, str]] = {
    **{name: "analytics.core.parameter_solvers" for name in _PARAMETER_EXPORTS},
    **{name: "analytics.core.returns" for name in _RETURN_EXPORTS},
    **{name: "analytics.core.risk_metrics" for name in _RISK_EXPORTS},
    **{name: "analytics.core.sensitivity_runner" for name in _SENSITIVITY_EXPORTS},
}

__all__ = [
    *_RETURN_EXPORTS,
    *_RISK_EXPORTS,
    *_PARAMETER_EXPORTS,
    *_SENSITIVITY_EXPORTS,
]


def __getattr__(name: str) -> Any:
    """Resolve one historical core export without importing unrelated engines."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose lazy compatibility names to interactive and inspection clients."""

    return sorted(set(globals()) | set(__all__))
