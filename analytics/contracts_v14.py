from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, computed_field

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
    """Check if covenant breaches threshold with floating-point tolerance.

    Prevents false breach warnings from floating-point rounding errors
    by applying industry-standard 1 basis point (0.01%) tolerance.
    """
    # Input validation
    if tolerance_bps < 0:
        raise ValueError(f"Tolerance must be non-negative, got {tolerance_bps}bp")

    if covenant_type not in ("floor", "ceiling"):
        raise ValueError(
            f"covenant_type must be 'floor' or 'ceiling', got '{covenant_type}'"
        )

    # Convert basis points to absolute tolerance
    # 1bp = 0.01% = 0.0001
    tolerance_abs = abs(threshold) * (tolerance_bps / 10000.0)

    # Floor covenant: breach if actual < threshold (allowing tolerance)
    if covenant_type == "floor":
        return actual < (threshold - tolerance_abs)

    # Ceiling covenant: breach if actual > threshold (allowing tolerance)
    else:  # covenant_type == "ceiling"
        return actual > (threshold + tolerance_abs)


# ═════════════════════════════════════════════════════════════════════════════
# WACC Contracts
# ═════════════════════════════════════════════════════════════════════════════


class WaccComponents(BaseModel):
    """CCCDIR: Components of the Weighted Average Cost of Capital calculation."""

    model_config = ConfigDict(frozen=True)

    mode: str = "capm"
    wacc_nominal: float
    wacc_real: Optional[float] = None
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
    inflation_rate: Optional[float] = None
    prudential_spread_bps: int = 100


class WaccResult(BaseModel):
    """Complete WACC analysis result."""

    model_config = ConfigDict(frozen=True)

    base: WaccComponents
    prudential_rate: float
    prudential_npv: Optional[float] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


# ═════════════════════════════════════════════════════════════════════════════
# Debt & Cashflow Contracts
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TrancheDebtProfile:
    """Lender-facing debt summary by tranche."""

    construction_years: int
    tenor_years: int
    timeline_periods: int
    total_debt: float
    total_idc: float
    lkr_principal: float
    usd_principal: float
    dfi_principal: float
    lkr_idc: float
    usd_idc: float
    dfi_idc: float
    lkr_rate: Optional[float] = None
    usd_rate: Optional[float] = None
    dfi_rate: Optional[float] = None
    interest_only_years: int = 0
    amortization_style: str = "sculpted"
    dscr_target: Optional[float] = None


class DebtCovenantSnapshot(BaseModel):
    """CASPER: Covenant status for auditable reporting."""

    model_config = ConfigDict(frozen=True)

    dscr_min: float
    dscr_threshold: float
    years_below_threshold: int
    first_breach_year: Optional[int] = None
    last_breach_year: Optional[int] = None
    balloon_remaining: float
    balloon_flag: bool
    audit_status: str  # 'PASS', 'REVIEW', 'FAIL'
    notes: str


@dataclass(frozen=True)
class CashflowResult:
    """Summary of project cashflows."""

    annual_cashflows: List[Dict[str, Any]]
    project_life_years: int
    construction_years: int
    ncf_lcy: List[float]
    pv_lcy: List[float]


# ═════════════════════════════════════════════════════════════════════════════
# Scenario Result Contract
# ═════════════════════════════════════════════════════════════════════════════


class ScenarioResult(BaseModel):
    """Top-level scenario result for dashboards/lenders."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    scenario_name: str
    config_path: Optional[str] = None
    project_npv: float
    project_irr: float
    dscr_series: List[float] = Field(default_factory=list)
    min_dscr: float
    max_debt_usd: float = 0.0

    # Nested contracts
    wacc: Optional[WaccResult] = None
    discount_rate_used: float = 0.10
    wacc_label: Optional[str] = None
    validation_mode: str = "strict"

    # Full data blocks (optional/lazy)
    config: Dict[str, Any] = Field(default_factory=dict)
    annual_rows: List[Dict[str, Any]] = Field(default_factory=list)
    debt_result: Dict[str, Any] = Field(default_factory=dict)
    kpis: Dict[str, Any] = Field(default_factory=dict)
    debt_profile: Optional[TrancheDebtProfile] = None
    debt_covenants: Optional[DebtCovenantSnapshot] = None
    fx_block: Optional[FXStructuredBlock] = None


# ═════════════════════════════════════════════════════════════════════════════
# Sensitivity Analysis Contracts
# ═════════════════════════════════════════════════════════════════════════════


class ParameterRangeConfig(BaseModel):
    """Configuration for a single parameter's sensitivity range."""

    model_config = ConfigDict(frozen=True)

    variable_name: str
    base_value: float
    low_pct: float = -10.0
    high_pct: float = 10.0
    steps: int = 5
    label: Optional[str] = None
    shock_type: str = "scalar"

    @property
    def low_value(self) -> float:
        return self.base_value * (1.0 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        return self.base_value * (1.0 + self.high_pct / 100.0)


class ShockResult(BaseModel):
    """Result of a single parameter shock."""

    model_config = ConfigDict(frozen=True)

    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str
    label: Optional[str] = None

    @computed_field
    @property
    def impact(self) -> float:
        return self.high_metric - self.low_metric


class TornadoResult(BaseModel):
    """Single parameter tornado sensitivity result."""

    model_config = ConfigDict(frozen=True)

    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    label: Optional[str] = None
    impact_abs: float = 0.0
    low_case_metric: Optional[float] = None
    high_case_metric: Optional[float] = None


class SensitivitySuite(BaseModel):
    """Complete tornado sensitivity analysis suite for a single metric."""

    model_config = ConfigDict(frozen=True)

    metric: str
    base_config_path: str
    tornado_results: List[TornadoResult]
    base_kpis: Dict[str, float] = Field(default_factory=dict)


class MultiMetricTornadoResult(BaseModel):
    """Multi-metric tornado result for a single parameter."""

    model_config = ConfigDict(frozen=True)

    variable: str
    label: str
    base_values: Dict[str, float]
    low_values: Dict[str, float]
    high_values: Dict[str, float]
    impacts: Dict[str, float] = Field(default_factory=dict)
    impact_dirs: Dict[str, int] = Field(default_factory=dict)


class MultiMetricSensitivitySuite(BaseModel):
    """Multi-metric tornado sensitivity suite."""

    model_config = ConfigDict(frozen=True)

    tornado_results: List[MultiMetricTornadoResult]
    base_metrics: Dict[str, float]
    base_config_path: str
    metrics: List[str]


class SensitivityRequest(BaseModel):
    """Request for a sensitivity analysis run."""

    model_config = ConfigDict(frozen=True)

    base_config_path: str
    parameters: List[ParameterRangeConfig]
    metric: str = "project_irr"


class BreakevenResult(BaseModel):
    """Breakeven parameter search result."""

    model_config = ConfigDict(frozen=True)

    variable: str
    target_metric: str = "project_irr"
    target_value: float = 0.0
    breakeven_value: float
    status: str = "success"
    bracket: Tuple[float, float]
    iterations: Optional[int] = None


# ═════════════════════════════════════════════════════════════════════════════
# Monte Carlo Contracts
# ═════════════════════════════════════════════════════════════════════════════


class Distribution(BaseModel):
    """Statistical distribution model for MC inputs."""

    model_config = ConfigDict(frozen=True, extra="allow")

    dist_type: str = "normal"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    mean: float = 0.0
    std: float = 0.0


class DerivedParameter(BaseModel):
    """Computed parameter derived from other MC inputs."""

    model_config = ConfigDict(frozen=True)

    name: str
    formula: str
    base_value: float


class MonteCarloScenario(BaseModel):
    """Configuration for a Monte Carlo simulation."""

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    n_iterations: int = 1000
    sampling_method: str = "lhs"
    seed: Optional[int] = None
    distributions: Dict[str, Distribution] = Field(default_factory=dict)


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation results."""

    model_config = ConfigDict(frozen=True, extra="allow")

    scenario_name: str
    iterations: int
    failed_iterations: int = 0
    raw_results: Optional[List[Dict[str, Any]]] = None

    # Project metrics
    project_irr_mean: float = 0.0
    project_irr_std: float = 0.0
    project_irr_p10: float = 0.0
    project_irr_p50: float = 0.0
    project_irr_p90: float = 0.0

    project_npv_mean: float = 0.0
    project_npv_std: float = 0.0
    project_npv_p10: float = 0.0
    project_npv_p50: float = 0.0
    project_npv_p90: float = 0.0

    # Debt metrics
    dscr_min_p10: float = 0.0
    dscr_min_p50: float = 0.0


# ═════════════════════════════════════════════════════════════════════════════
# CASPER Unified Result
# ═════════════════════════════════════════════════════════════════════════════


class CasperResult(BaseModel):
    """Unified analysis result (CASPER compliant)."""

    model_config = ConfigDict(frozen=True, extra="allow", arbitrary_types_allowed=True)

    scenario: ScenarioResult
    baseline_kpis: Dict[str, float]
    sensitivities: Optional[SensitivitySuite] = None
    monte_carlo: Optional[MonteCarloResult] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def contract_version(self) -> str:
        return CASPER_CONTRACT_VERSION


# ═════════════════════════════════════════════════════════════════════════════
# Other Analytics Contracts
# ═════════════════════════════════════════════════════════════════════════════


class EquityPerformance(BaseModel):
    """Equity performance metrics."""

    model_config = ConfigDict(frozen=True, extra="allow")

    equity_irr: float = 0.0
    equity_npv: float = 0.0
    moic: float = 0.0


class DownsideMetrics(BaseModel):
    """Metrics specifically for downside/stressed analysis."""

    model_config = ConfigDict(frozen=True, extra="allow")

    downside_return_pct: float = 0.0
    p10_return: float = 0.0


@dataclass(frozen=True)
class ShockSpec:
    """Legacy/Phase 3 shock specification compatibility."""

    variable_name: str
    low_value: float
    high_value: float
    label: Optional[str] = None


class StandardShockLibrary:
    """Library of standard project finance shocks."""

    @staticmethod
    def capex_overrun(base_capex: float) -> ShockSpec:
        return ShockSpec(
            "capex_total", base_capex * 0.90, base_capex * 1.10, "CAPEX ±10%"
        )


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
