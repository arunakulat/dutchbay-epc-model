from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from analytics.fx.fx_contracts import (
    FXStructuredBlock,
    FXCurveOutput,
    FXRiskProfile,
)

# Contract version tracking
CASPER_CONTRACT_VERSION = "v1.0"


def check_covenant_breach_with_tolerance(
    actual: float,
    threshold: float,
    tolerance_bps: int = 1,
    covenant_type: str = "floor",
) -> bool:
    """Check if covenant breaches threshold with floating-point tolerance."""
    if tolerance_bps < 0:
        raise ValueError(f"Tolerance must be non-negative, got {tolerance_bps}bp")
    if covenant_type not in ("floor", "ceiling"):
        raise ValueError(f"covenant_type must be 'floor' or 'ceiling', got '{covenant_type}'")
    tolerance_abs = abs(threshold) * (tolerance_bps / 10000.0)
    if covenant_type == "floor":
        return actual < (threshold - tolerance_abs)
    else:
        return actual > (threshold + tolerance_abs)


@dataclass
class WaccComponents:
    mode: str = "nominal"
    wacc_nominal: float = 0.0
    wacc_real: Optional[float] = None
    wacc_prudential: float = 0.0
    risk_free_rate: float = 0.0
    market_risk_premium: float = 0.0
    asset_beta: float = 0.0
    target_debt_to_equity: float = 0.0
    target_debt_to_value: float = 0.0
    target_equity_to_value: float = 0.0
    cost_of_debt_pretax: float = 0.0
    cost_of_debt_aftertax: float = 0.0
    equity_beta_levered: float = 0.0
    cost_of_equity: float = 0.0
    tax_rate: float = 0.0
    inflation_rate: Optional[float] = None
    prudential_spread_bps: int = 0


@dataclass
class WaccResult:
    base: WaccComponents
    prudential_rate: float = 0.0
    prudential_npv: float = 0.0


@dataclass
class ScenarioResult:
    name: str
    config_path: str
    kpis: Dict[str, Any]
    annual_rows: List[Dict[str, Any]]
    debt_result: Dict[str, Any]
    discount_rate: float
    fail_reason: Optional[str] = None


class ParameterRangeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    variable_name: str
    base_value: float
    low_pct: float = 0.0
    high_pct: float = 0.0
    steps: int = 5
    label: Optional[str] = None


class ShockResult(BaseModel):
    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str
    label: str
    low_case: float = 0.0
    high_case: float = 0.0
    impact: float = 0.0


class TornadoResult(BaseModel):
    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    label: Optional[str] = None
    impact_abs: float = 0.0
    low_case_metric: Optional[float] = None
    high_case_metric: Optional[float] = None


class MultiMetricTornadoResult(BaseModel):
    variable: str
    label: str
    base_values: Dict[str, float]
    low_values: Dict[str, float]
    high_values: Dict[str, float]
    impacts: Optional[Dict[str, float]] = None
    impact_dirs: Optional[Dict[str, int]] = None


class SensitivitySuite(BaseModel):
    metric: str = "project_irr"
    base_config_path: str
    tornado_results: List[TornadoResult]
    base_kpis: Optional[Dict[str, float]] = None


class MultiMetricSensitivitySuite(BaseModel):
    tornado_results: List[MultiMetricTornadoResult]
    base_metrics: Dict[str, float]
    base_config_path: str
    metrics: List[str]


class SensitivityRequest(BaseModel):
    base_config_path: str
    parameters: List[ParameterRangeConfig]
    metric: str = "project_irr"


class BreakevenResult(BaseModel):
    variable: str
    breakeven_value: float
    bracket: Tuple[float, float]
    status: str = "success"
    target_metric: str = "project_irr"
    target_value: float = 0.0


@dataclass
class Distribution:
    dist_type: str = "normal"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DerivedParameter:
    name: str
    formula: str


@dataclass
class MonteCarloScenario:
    scenario_name: str
    n_iterations: int
    distributions: Dict[str, Distribution]
    sampling_method: str = "lhs"
    seed: Optional[int] = None


@dataclass
class MonteCarloResult:
    scenario_name: str
    n_iterations: int
    mean: float
    std: float
    p10: float
    p50: float
    p90: float
    min_value: float
    max_value: float
    metric_name: str
    sampling_method: str = "lhs"
    var_95: float = 0.0


@dataclass
class CasperResult:
    scenario: str
    baseline_kpis: Dict[str, float]
    sensitivities: Dict[str, Any] = field(default_factory=dict)
    monte_carlo: Dict[str, Any] = field(default_factory=dict)

    def contract_version(self) -> str:
        return CASPER_CONTRACT_VERSION


@dataclass
class TrancheDebtProfile:
    name: str = ""
    principal: float = 0.0


@dataclass
class DebtCovenantSnapshot:
    dscr: float = 0.0


@dataclass
class CashflowResult:
    annual_cashflows: List[float] = field(default_factory=list)


@dataclass
class EquityPerformance:
    equity_irr: float = 0.0


@dataclass
class DownsideMetrics:
    downside_return_pct: float = 0.0


# Legacy Phase 3 Stubs
@dataclass(frozen=True)
class ShockSpec:
    variable_name: str
    low_value: float
    high_value: float
    label: Optional[str] = None


class StandardShockLibrary:
    pass


__all__ = [
    "CASPER_CONTRACT_VERSION",
    "check_covenant_breach_with_tolerance",
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    "ShockSpec",
    "StandardShockLibrary",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "MultiMetricSensitivitySuite",
    "SensitivityRequest",
    "BreakevenResult",
    "ShockResult",
    "Distribution",
    "DerivedParameter",
    "MonteCarloScenario",
    "MonteCarloResult",
    "CasperResult",
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    "CashflowResult",
    "EquityPerformance",
    "DownsideMetrics",
]
