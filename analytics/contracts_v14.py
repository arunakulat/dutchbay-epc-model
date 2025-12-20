from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

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
# Sensitivity Analysis Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════


class ParameterRangeConfig(BaseModel):
    """
    Parameter shock configuration for sensitivity analysis.
    
    CESSPIT: Contract-explicit parameter bounds.
    """
    model_config = ConfigDict(frozen=True)
    
    variable_name: str = Field(description="Dotted path to parameter (e.g., 'finance.capex_usd')")
    base_value: float = Field(description="Base case value")
    low_pct: float = Field(description="Low shock as % (e.g., -10.0 for -10%)")
    high_pct: float = Field(description="High shock as % (e.g., 10.0 for +10%)")
    label: Optional[str] = Field(default=None, description="Display label")
    
    @field_validator('low_pct', 'high_pct')
    @classmethod
    def validate_shock_range(cls, v: float) -> float:
        """Shocks must be reasonable (-100% to +500%)."""
        if not (-100.0 <= v <= 500.0):
            raise ValueError(f"Shock percentage must be in [-100, 500], got {v}")
        return v


class ShockResult(BaseModel):
    """
    Single shock result for one direction.
    """
    model_config = ConfigDict(frozen=True)
    
    low_case: float = Field(description="Metric value at low shock")
    high_case: float = Field(description="Metric value at high shock")
    impact: float = Field(description="Absolute impact (high - low)")


class TornadoResult(BaseModel):
    """
    Single variable tornado sensitivity result.
    
    Pydantic V2 contract - replaces old dataclass version.
    
    Field Mapping (V1 → V2):
    - variable → metric_name
    - base_irr → base_metric
    - low_irr → shock_results[0].low_case
    - high_irr → shock_results[0].high_case
    """
    model_config = ConfigDict(frozen=True)
    
    metric_name: str = Field(description="Variable being shocked")
    base_metric: float = Field(description="Base case metric value")
    shock_results: List[ShockResult] = Field(description="Shock outcomes")
    label: Optional[str] = Field(default=None, description="Display label")
    impact_abs: float = Field(default=0.0, description="Total impact magnitude")
    
    @computed_field
    @property
    def impact(self) -> float:
        """Computed impact from shock results."""
        if self.shock_results:
            return self.shock_results[0].impact
        return 0.0


class MultiMetricTornadoResult(BaseModel):
    """
    Multi-metric tornado result for one parameter.
    """
    model_config = ConfigDict(frozen=True)
    
    metric_name: str = Field(description="Variable being shocked")
    label: Optional[str] = Field(default=None)
    base_values: Dict[str, float] = Field(description="Base metric values")
    low_values: Dict[str, float] = Field(description="Low shock values")
    high_values: Dict[str, float] = Field(description="High shock values")
    impacts: Dict[str, float] = Field(description="Impact per metric")
    impact_dirs: Dict[str, int] = Field(description="Direction (+1/-1)")


class SensitivitySuite(BaseModel):
    """
    Complete sensitivity analysis suite.
    """
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    
    metric: str = Field(description="Target metric analyzed")
    base_config_path: str = Field(description="Base scenario path")
    tornado_results: List[TornadoResult] = Field(description="Tornado results")
    base_kpis: Optional[Dict[str, float]] = Field(default=None)


class SensitivityRequest(BaseModel):
    """
    Request structure for sensitivity analysis.
    """
    model_config = ConfigDict(frozen=True)
    
    base_config_path: str
    parameters: List[ParameterRangeConfig]
    metric: Optional[str] = Field(default="project_irr")


class BreakevenResult(BaseModel):
    """
    Breakeven parameter solution.
    """
    model_config = ConfigDict(frozen=True)
    
    variable: str
    target_metric: str
    target_value: float
    breakeven_value: float
    status: str = Field(default="success")
    bracket: Tuple[float, float] = Field(default=(0.0, 0.0))


# ═════════════════════════════════════════════════════════════════════════════
# CASPER Result Contract (with computed fields)
# ═════════════════════════════════════════════════════════════════════════════


class CasperResult(BaseModel):
    """
    CASPER unified analysis result.
    
    Pydantic V2 contract with computed_field support.
    """
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    
    scenario: Optional[str] = Field(default=None)
    baseline_kpis: Dict[str, float] = Field(default_factory=dict)
    sensitivities: Optional[Any] = Field(default=None)
    monte_carlo: Optional[Any] = Field(default=None)
    multi_tech_generation_breakdown: Optional[Any] = Field(default=None)
    
    @computed_field
    @property
    def contract_version(self) -> str:
        """Contract version - computed property."""
        return CASPER_CONTRACT_VERSION


class MonteCarloResult(BaseModel):
    """
    Monte Carlo simulation result.
    """
    model_config = ConfigDict(frozen=True)
    
    scenario_name: str
    iterations: int
    p10: float
    p50: float
    p90: float
    mean: float
    std: float


# ═════════════════════════════════════════════════════════════════════════════
# WACC, Lender/Scenario Results (Phase 1)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class WaccComponents:
    """WACC calculation component breakdown for scenario and audit."""

    mode: str
    wacc_nominal: float
    wacc_real: Optional[float]
    wacc_prudential: float
    risk_free_rate: float
    market_risk_premium: float
    asset_beta: float
    target_debt_to_equity: float
    target_debt_to_value: float
    target_equity_to_value: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    equity_beta_levered: float
    cost_of_equity: float
    tax_rate: float
    inflation_rate: Optional[float]
    prudential_spread_bps: int


@dataclass
class WaccResult:
    """Complete WACC result including base and prudential valuations."""

    base: WaccComponents
    prudential_rate: Optional[float] = None
    prudential_npv: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


# ═════════════════════════════════════════════════════════════════════════════
# ScenarioResult – canonical scenario surface (with FX integration - v14R6)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class ScenarioResult:
    """
    Complete scenario evaluation result with WACC and full outputs.
    Now includes FX structured blocks and curves per v14R6 requirement.
    """

    scenario_name: str
    config_path: str
    project_npv: float
    project_irr: float
    dscr_series: List[float]
    min_dscr: float
    max_debt_usd: float

    wacc: Optional[WaccResult] = None
    discount_rate_used: Optional[float] = None
    wacc_label: Optional[str] = None
    wacc_is_real: Optional[bool] = None

    # FX structured blocks and curves (Sprint 15 integration – Issue #31)
    fx_block: Optional[FXStructuredBlock] = None
    fx_curve: Optional[FXCurveOutput] = None
    fx_risk_profile: Optional[FXRiskProfile] = None

    validation_mode: str = "strict"
    config: Dict[str, Any] = field(default_factory=dict)
    annual_rows: Sequence[Dict[str, Any]] = field(default_factory=list)
    debt_result: Dict[str, Any] = field(default_factory=dict)
    kpis: Dict[str, Any] = field(default_factory=dict)
    cashflow: Optional["CashflowResult"] = None

    equity_performance: Optional["EquityPerformance"] = None
    debt_profile: Optional["TrancheDebtProfile"] = None
    debt_covenants: Optional["DebtCovenantSnapshot"] = None

    def as_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "scenario_name": self.scenario_name,
            "config_path": self.config_path,
            "project_npv": self.project_npv,
            "project_irr": self.project_irr,
            "min_dscr": self.min_dscr,
            "max_debt_usd": self.max_debt_usd,
        }
        data.update(self.kpis)
        return data


__all__ = [
    "CASPER_CONTRACT_VERSION",
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "SensitivityRequest",
    "BreakevenResult",
    "CasperResult",
    "MonteCarloResult",
    "ShockResult",
]
