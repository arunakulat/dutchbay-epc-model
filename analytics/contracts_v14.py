from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from analytics.fx.fx_contracts import (
    FXStructuredBlock,
    FXCurveOutput,
    FXRiskProfile,
)

"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     DUTCHBAY v14 DATA CONTRACTS                             ║
║                  (Fully Refactored with Pydantic V2)                        ║
║                                                                              ║
║  CESSPIT/CASPER/GWTF/CCCDIR Compliance:                                     ║
║  - Contract-first: All models explicitly typed                               ║
║  - Evidence-based: Validation rules from test requirements                   ║
║  - Scenario-stable: Frozen configs, reproducible outputs                     ║
║  - Config-driven: No hardcoded constants                                     ║
║                                                                              ║
║  All pipeline modules must import analytics results ONLY from here.          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# Contract version tracking
CASPER_CONTRACT_VERSION = "v1.0"

# ═════════════════════════════════════════════════════════════════════════════
# Covenant Breach Detection with Floating-Point Tolerance (Sprint 18 - Issue #4)
# ═════════════════════════════════════════════════════════════════════════════


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


# ═════════════════════════════════════════════════════════════════════════════
# Sensitivity Analysis Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════

class ParameterRangeConfig(BaseModel):
    """Configuration for a single parameter's sensitivity range."""
    variable_name: str
    base_value: float
    low_pct: float = Field(ge=-100, le=100)
    high_pct: float = Field(ge=-100, le=100)
    steps: int = Field(default=5, ge=2, le=20)
    label: Optional[str] = None
    shock_type: str = "scalar"
    low_value: Optional[float] = None
    high_value: Optional[float] = None

    @model_validator(mode="after")
    def compute_range_values(self) -> "ParameterRangeConfig":
        if self.low_value is None:
            self.low_value = self.base_value * (1 + self.low_pct / 100)
        if self.high_value is None:
            self.high_value = self.base_value * (1 + self.high_pct / 100)
        return self

class ShockSpec(BaseModel):
    """Specification for a single sensitivity shock."""
    variable_name: str
    low_value: float
    high_value: float
    label: Optional[str] = None

class ShockResult(BaseModel):
    """Result of applying a shock to a variable."""
    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str
    label: str
    low_case: Optional[float] = None
    high_case: Optional[float] = None
    impact: Optional[float] = None

class TornadoResult(BaseModel):
    """Single parameter tornado sensitivity result."""
    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    label: Optional[str] = None
    impact_abs: Optional[float] = None
    impact_dir: Optional[int] = None
    low_case_metric: Optional[float] = None
    high_case_metric: Optional[float] = None

class MultiMetricTornadoResult(BaseModel):
    """Multi-metric tornado result for a single parameter."""
    variable: str
    label: str
    base_values: Dict[str, float]
    low_values: Dict[str, float]
    high_values: Dict[str, float]
    impacts: Optional[Dict[str, float]] = None
    impact_dirs: Optional[Dict[str, int]] = None

class SensitivitySuite(BaseModel):
    """Complete tornado sensitivity analysis suite."""
    tornado_results: List[TornadoResult]
    base_metric: float
    base_config_path: str
    metric: str = "project_irr"
    base_kpis: Optional[Dict[str, float]] = None

class MultiMetricSensitivitySuite(BaseModel):
    """Multi-metric tornado sensitivity suite."""
    tornado_results: List[MultiMetricTornadoResult]
    base_metrics: Dict[str, float]
    base_config_path: str
    metrics: List[str]

class SensitivityRequest(BaseModel):
    """Request for sensitivity analysis."""
    config_path: str
    params: List[ParameterRangeConfig]

class BreakevenResult(BaseModel):
    """Breakeven parameter search result."""
    variable: str
    breakeven_value: float
    bracket: Tuple[float, float]
    status: str = "success"
    iterations: Optional[int] = None
    target_value: Optional[float] = 0.0

class StandardShockLibrary:
    """Library of standard sensitivity shocks."""
    @staticmethod
    def capex_overrun(base_capex: float) -> ShockSpec:
        return ShockSpec(variable_name="capex", low_value=base_capex*0.9, high_value=base_capex*1.1)

class Distribution(BaseModel):
    """Statistical distribution specification."""
    type: str = "normal"
    mean: float = 0.0
    std: float = 1.0
    min: Optional[float] = None
    max: Optional[float] = None

class DerivedParameter(BaseModel):
    """Parameter derived from other parameters."""
    variable_name: str
    formula: str

class CasperResult(BaseModel):
    """CASPER evaluation result."""
    scenario_name: str
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ScenarioResult(BaseModel):
    """Result of evaluating a multi-variable scenario."""
    scenario_name: str
    description: str
    base_metrics: Dict[str, float]
    shocked_metrics: Dict[str, float]
    shock_values: Dict[str, float]

class WaccComponents(BaseModel):
    """Components of WACC calculation."""
    cost_of_equity: float
    cost_of_debt: float
    gearing_pct: float
    tax_rate: float

class WaccResult(BaseModel):
    """Result of WACC calculation."""
    wacc_nominal: float
    wacc_real: float
    components: WaccComponents

class TrancheDebtProfile(BaseModel):
    """Debt profile for a single tranche."""
    tranche_id: str
    principal: float
    interest_rate: float
    tenor: int

class DebtCovenantSnapshot(BaseModel):
    """Snapshot of debt covenants."""
    dscr: float
    llcr: float
    is_compliant: bool

class CashflowResult(BaseModel):
    """Result of cashflow projection."""
    annual_cfads: List[float]
    annual_debt_service: List[float]
    total_npv: float

class EquityPerformance(BaseModel):
    """Equity performance metrics."""
    equity_irr: float
    equity_npv: float

class DownsideMetrics(BaseModel):
    """Downside risk metrics."""
    dscr_min: float
    break_even_capex_pct: float

class MonteCarloScenario(BaseModel):
    """Single Monte Carlo iteration scenario."""
    index: int
    overrides: Dict[str, float]

class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result."""
    metric_name: str
    mean: float
    std: float
    p05: float
    p50: float
    p95: float
    iterations: int
    seed: Optional[int] = None

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
    "StandardShockLibrary",
    "MonteCarloResult",
    "MonteCarloScenario",
    "CasperResult",
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    "CashflowResult",
    "EquityPerformance",
    "DownsideMetrics",
]
