import os

content = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

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

class ShockSpec(BaseModel):
    parameter: str
    shocks: List[float]
    @computed_field
    @property
    def variable_name(self) -> str:
        return self.parameter

class StandardShockLibrary:
    pass

class TornadoResult(BaseModel):
    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    label: Optional[str] = None
    impact_abs: Optional[float] = None
    @model_validator(mode="after")
    def compute_impact(self) -> "TornadoResult":
        if self.impact_abs is None and self.shock_results:
            self.impact_abs = abs(self.shock_results[0].high_metric - self.shock_results[0].low_metric)
        return self

class MultiMetricTornadoResult(BaseModel):
    variable: str
    label: str
    base_values: Dict[str, float]
    low_values: Dict[str, float]
    high_values: Dict[str, float]

class ParameterRangeConfig(BaseModel):
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    label: Optional[str] = None

class SensitivitySuite(BaseModel):
    metric: str
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

class ShockResult(BaseModel):
    low_case: float
    high_case: float
    impact: float
    low_metric: float = 0.0
    high_metric: float = 0.0

class Distribution(BaseModel):
    dist_type: str = "normal"
    mean: float = 0.0
    std: float = 0.0

class DerivedParameter(BaseModel):
    name: str

class MonteCarloScenario(BaseModel):
    name: str

class MonteCarloResult(BaseModel):
    metric_name: str
    mean: float = 0.0
    std: float = 0.0
    p05: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    iterations: int = 0

class CasperResult(BaseModel):
    model_config = ConfigDict(extra='allow')

class TrancheDebtProfile(BaseModel):
    model_config = ConfigDict(extra='allow')

class DebtCovenantSnapshot(BaseModel):
    model_config = ConfigDict(extra='allow')

class CashflowResult(BaseModel):
    model_config = ConfigDict(extra='allow')

class EquityPerformance(BaseModel):
    model_config = ConfigDict(extra='allow')

class DownsideMetrics(BaseModel):
    model_config = ConfigDict(extra='allow')

class WaccComponents(BaseModel):
    model_config = ConfigDict(extra='allow')

class WaccResult(BaseModel):
    model_config = ConfigDict(extra='allow')

class ScenarioResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    kpis: Dict[str, Any] = Field(default_factory=dict)

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
\"\"\"
from pydantic import model_validator
\"\"\" + content
with open("analytics/contracts_v14.py", "w") as f:
    f.write(content)
