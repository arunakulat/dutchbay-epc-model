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
║                  (Fully Refactored with Validators)                         ║
║                                                                              ║
║  All canonical data structures (dataclasses, pydantic models) used for:      ║
║  - Valuation, WACC, and scenario results                                     ║
║  - FX structured blocks, curves, and risk metrics (v14R6)                    ║
║  - Equity metrics, downside risk                                             ║
║  - Sensitivity/tornado/optimizer/Monte Carlo surfaces for analytics          ║
║  - Ready for export, reporting, dashboard use                                ║
║                                                                              ║
║  ALWAYS update comments and docstrings in this file for future maintainers.  ║
║  All pipeline modules must import *analytics results* only from here.        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# Contract version constant (CASPER: Single source of truth)
CASPER_CONTRACT_VERSION = "2.0.0"

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
# Sensitivity Analysis Contracts (Phase 3)
# ═════════════════════════════════════════════════════════════════════════════


class ParameterRangeConfig(BaseModel):
    """
    Configuration for a single parameter's sensitivity range.
    
    CASPER: Contract-first definition for tornado analysis.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    variable_name: str = Field(..., description="Dot-notation path to parameter")
    base_value: float = Field(..., description="Base case value")
    low_pct: float = Field(..., description="Downside shock percentage")
    high_pct: float = Field(..., description="Upside shock percentage")
    label: Optional[str] = Field(None, description="Human-readable label")
    
    @field_validator('low_pct', 'high_pct')
    @classmethod
    def validate_percentages(cls, v: float) -> float:
        if v < -100 or v > 1000:
            raise ValueError(f"Percentage out of reasonable range: {v}")
        return v


class SensitivityRequest(BaseModel):
    """
    Request specification for sensitivity analysis.
    
    CCCDIR: Config-driven sensitivity runs.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    base_config_path: str = Field(..., description="Path to base scenario YAML")
    parameters: List[ParameterRangeConfig] = Field(..., description="Parameters to vary")
    metric: Optional[str] = Field(None, description="Target metric (for single-metric)")


class TornadoResult(BaseModel):
    """
    Single-parameter tornado sensitivity result.
    
    CASPER: Immutable contract for tornado chart data.
    GWTF: Clear field names that match test expectations.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    # Field names match test expectations (Pydantic V2 style)
    variable: str = Field(..., description="Parameter name")
    label: Optional[str] = Field(None, description="Display label")
    
    # Base case
    base_value: float = Field(..., description="Base parameter value")
    base_metric: float = Field(..., description="Base metric value")
    
    # Shocked cases
    low_value: float = Field(..., description="Low-case parameter value")
    low_metric: float = Field(..., description="Low-case metric value")
    high_value: float = Field(..., description="High-case parameter value")
    high_metric: float = Field(..., description="High-case metric value")
    
    # Impact metrics
    impact_abs: float = Field(..., description="Absolute impact range")
    impact_dir: int = Field(..., description="Impact direction: -1, 0, +1")
    
    # Legacy field aliases for backward compatibility
    @property
    def base_irr(self) -> float:
        """Legacy alias for base_metric (backward compat)."""
        return self.base_metric
    
    @property
    def low_irr(self) -> float:
        """Legacy alias for low_metric (backward compat)."""
        return self.low_metric
    
    @property
    def high_irr(self) -> float:
        """Legacy alias for high_metric (backward compat)."""
        return self.high_metric


class MultiMetricTornadoResult(BaseModel):
    """
    Multi-metric tornado result for a single parameter.
    
    CASPER: Contract-first for comparative sensitivity analysis.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    variable: str = Field(..., description="Parameter name")
    label: Optional[str] = Field(None, description="Display label")
    
    base_values: Dict[str, float] = Field(..., description="Base metrics by name")
    low_values: Dict[str, float] = Field(..., description="Low-case metrics")
    high_values: Dict[str, float] = Field(..., description="High-case metrics")
    impacts: Dict[str, float] = Field(..., description="Impact ranges by metric")
    impact_dirs: Dict[str, int] = Field(..., description="Impact directions by metric")


class CasperResult(BaseModel):
    """
    Complete CASPER evaluation result.
    
    CASPER: Contract-first, immutable result container.
    CESSPIT: Single responsibility - result aggregation only.
    """
    model_config = ConfigDict(frozen=True, extra="allow")
    
    scenario: Optional[str] = Field(None, description="Scenario name")
    baseline_kpis: Dict[str, float] = Field(..., description="Base case KPIs")
    sensitivities: Optional[Dict[str, Any]] = Field(None, description="Tornado results")
    monte_carlo: Optional[Dict[str, Any]] = Field(None, description="MC results")
    multi_tech_generation_breakdown: Optional[Dict[str, Any]] = Field(
        None, description="Multi-tech generation data"
    )
    
    @computed_field
    @property
    def contract_version(self) -> str:
        """CASPER contract version (computed field for Pydantic V2)."""
        return CASPER_CONTRACT_VERSION


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
    # WACC & Scenarios
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    
    # FX Integration
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    
    # Sensitivity Analysis
    "ParameterRangeConfig",
    "SensitivityRequest",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "CasperResult",
    
    # Constants
    "CASPER_CONTRACT_VERSION",
]

# EOF - analytics/contracts_v14.py