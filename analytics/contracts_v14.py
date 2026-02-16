from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from analytics.fx.fx_contracts import (
    FXStructuredBlock,
    FXCurveOutput,
    FXRiskProfile,
)

CASPER_CONTRACT_VERSION = "v1.0"

def check_covenant_breach_with_tolerance(
    actual: float,
    threshold: float,
    tolerance_bps: int = 1,
    covenant_type: str = "floor",
) -> bool:
    if tolerance_bps < 0:
        raise ValueError(f"Tolerance must be non-negative, got {tolerance_bps}bp")
    if covenant_type not in ("floor", "ceiling"):
        raise ValueError(f"covenant_type must be 'floor' or 'ceiling', got '{covenant_type}'")
    tolerance_abs = abs(threshold) * (tolerance_bps / 10000.0)
    if covenant_type == "floor":
        return actual < (threshold - tolerance_abs)
    else:
        return actual > (threshold + tolerance_abs)

class ParameterRangeConfig(BaseModel):
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    steps: int = 5
    label: Optional[str] = None
    shock_type: str = "scalar"

class ShockResult(BaseModel):
    low_case: float = 0.0
    high_case: float = 0.0
    impact: float = 0.0
    variable_name: Optional[str] = None
    base_value: Optional[float] = None
    low_value: Optional[float] = None
    high_value: Optional[float] = None
    base_metric: Optional[float] = None
    low_metric: Optional[float] = None
    high_metric: Optional[float] = None
    metric_name: Optional[str] = None
    label: Optional[str] = None

class TornadoResult(BaseModel):
    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    label: Optional[str] = None
    impact_abs: float = 0.0
    low_case_metric: Optional[float] = None
    high_case_metric: Optional[float] = None

class SensitivityRequest(BaseModel):
    config_path: str
    params: List[ParameterRangeConfig]

class MultiMetricTornadoResult(BaseModel):
    metric_names: List[str] = Field(default_factory=list)
    results: Dict[str, TornadoResult] = Field(default_factory=dict)
    variable: Optional[str] = None
    label: Optional[str] = None
    base_values: Dict[str, float] = Field(default_factory=dict)
    low_values: Dict[str, float] = Field(default_factory=dict)
    high_values: Dict[str, float] = Field(default_factory=dict)
    impacts: Dict[str, float] = Field(default_factory=dict)
    impact_dirs: Dict[str, int] = Field(default_factory=dict)

class SensitivitySuite(BaseModel):
    metric: str = "project_irr"
    base_config_path: str
    tornado_results: List[TornadoResult]
    base_kpis: Optional[Dict[str, float]] = None

class MultiMetricSensitivitySuite(BaseModel):
    tornado_results: List[MultiMetricTornadoResult] = Field(default_factory=list)
    base_metrics: Dict[str, float] = Field(default_factory=dict)
    base_config_path: str = ""
    metrics: List[str] = Field(default_factory=list)

class BreakevenResult(BaseModel):
    variable: str
    breakeven_value: float
    bracket: Tuple[float, float]
    status: str = "success"

class WaccComponents(BaseModel):
    pass
class WaccResult(BaseModel):
    pass
class ScenarioResult(BaseModel):
    pass
class CasperResult(BaseModel):
    pass
class TrancheDebtProfile(BaseModel):
    pass
class DebtCovenantSnapshot(BaseModel):
    pass
class CashflowResult(BaseModel):
    pass
class EquityPerformance(BaseModel):
    pass
class DownsideMetrics(BaseModel):
    pass
class ShockSpec(BaseModel):
    pass
class StandardShockLibrary(BaseModel):
    pass
class Distribution(BaseModel):
    pass
class DerivedParameter(BaseModel):
    pass
class MonteCarloScenario(BaseModel):
    pass
class MonteCarloResult(BaseModel):
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
