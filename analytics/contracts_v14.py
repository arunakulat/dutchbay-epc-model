from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
)

if TYPE_CHECKING:
    # Forward references - these classes will be implemented in future sprints
    class CashflowResult:
        pass

    class EquityPerformance:
        pass


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
# Monte Carlo Contracts (Sprint 16 - Issue #43 Resolution)
# ═════════════════════════════════════════════════════════════════════════════


class Distribution(BaseModel):
    """
    Distribution specification for Monte Carlo sampling.

    CASPER: Contract-explicit probability distribution.
    CESSPIT: All distribution parameters from config.
    """

    model_config = ConfigDict(frozen=True)

    dist_type: str = Field(
        description="Distribution type (normal, uniform, lognormal, triangular)"
    )
    parameters: Dict[str, float] = Field(
        description="Distribution parameters (mean, std, min, max, etc)"
    )

    @field_validator("dist_type")
    @classmethod
    def validate_dist_type(cls, v: str) -> str:
        """Validate supported distribution types."""
        supported = {"normal", "uniform", "lognormal", "triangular", "beta"}
        if v.lower() not in supported:
            raise ValueError(
                f"Distribution type '{v}' not supported. Use: {supported}"
            )
        return v.lower()


class DerivedParameter(BaseModel):
    """
    Derived parameter definition for Monte Carlo scenarios.

    Derived parameters are computed from other sampled parameters.

    CASPER: Explicit dependency tracking.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Derived parameter name")
    expression: str = Field(description="Python expression to compute value")
    dependencies: List[str] = Field(
        default_factory=list, description="List of parameter names this depends on"
    )


class MonteCarloScenario(BaseModel):
    """
    Monte Carlo scenario definition.

    CASPER: Complete scenario specification for MC simulation.
    CESSPIT: All parameters from config, no defaults.
    """

    model_config = ConfigDict(frozen=True)

    scenario_name: str = Field(description="Scenario identifier")
    n_iterations: int = Field(gt=0, description="Number of MC iterations")
    sampling_method: str = Field(
        default="lhs", description="Sampling method (lhs, sobol, random)"
    )
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")

    # Stochastic variables to sample
    distributions: Dict[str, Distribution] = Field(
        description="Variable name -> Distribution mapping"
    )

    # Derived parameters (computed from sampled variables)
    derived_parameters: List[DerivedParameter] = Field(
        default_factory=list, description="Computed parameters"
    )

    # Discount rate configuration
    discount_rate_source: str = Field(
        default="config",
        description="Source of discount rate (config, wacc, fixed)",
    )
    discount_rate_value: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fixed discount rate if discount_rate_source='fixed'",
    )

    @field_validator("sampling_method")
    @classmethod
    def validate_sampling_method(cls, v: str) -> str:
        """Validate sampling method."""
        supported = {"lhs", "sobol", "random", "halton"}
        if v.lower() not in supported:
            raise ValueError(f"Sampling method '{v}' not supported. Use: {supported}")
        return v.lower()


# ═════════════════════════════════════════════════════════════════════════════
# Sensitivity Analysis Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════


class ShockSpec(BaseModel):
    """Individual parameter shock specification for sensitivity analysis.
    
    Defines a single parameter to shock with specific percentage variations.
    
    CASPER: Contract-explicit shock definition.
    CESSPIT: All shock values from config or library.
    
    Example:
        >>> shock = ShockSpec(
        ...     parameter="capex",
        ...     shocks=[-0.10, -0.05, 0.05, 0.10],
        ...     label="Capital Cost"
        ... )
    """
    
    model_config = ConfigDict(frozen=True)
    
    parameter: str = Field(
        description="Parameter name to shock (e.g., 'capex', 'tariff', 'capacity_factor')"
    )
    shocks: List[float] = Field(
        description="List of shock percentages as decimals (e.g., [-0.1, 0.1] for ±10%)"
    )
    label: Optional[str] = Field(
        default=None,
        description="Display label for reporting (defaults to parameter name)"
    )
    
    @field_validator("shocks")
    @classmethod
    def validate_shocks(cls, v: List[float]) -> List[float]:
        """Validate shock list is non-empty and reasonable."""
        if not v:
            raise ValueError("Shock list cannot be empty")
        if any(s < -1.0 or s > 5.0 for s in v):
            raise ValueError("Shock values must be in range [-1.0, 5.0] (-100% to +500%)")
        return v


class StandardShockLibrary:
    """Predefined library of standard sensitivity shocks.
    
    Provides common shock patterns for typical project finance parameters.
    
    CESSPIT: Centralized shock library prevents drift.
    GWTF: One source of truth for standard shocks.
    
    Usage:
        >>> shocks = StandardShockLibrary.standard_shocks()
        >>> capex_shock = StandardShockLibrary.capex_shock()
    """
    
    @staticmethod
    def standard_shocks() -> List[ShockSpec]:
        """Return standard shock library for typical project parameters.
        
        Returns:
            List of ShockSpec for: capex, tariff, capacity_factor, opex, discount_rate
            
        Example:
            >>> shocks = StandardShockLibrary.standard_shocks()
            >>> len(shocks)
            5
        """
        return [
            ShockSpec(
                parameter="capex",
                shocks=[-0.10, -0.05, 0.05, 0.10],
                label="Capital Cost"
            ),
            ShockSpec(
                parameter="tariff",
                shocks=[-0.10, -0.05, 0.05, 0.10],
                label="Tariff Rate"
            ),
            ShockSpec(
                parameter="capacity_factor",
                shocks=[-0.10, -0.05, 0.05, 0.10],
                label="Capacity Factor"
            ),
            ShockSpec(
                parameter="opex",
                shocks=[-0.10, -0.05, 0.05, 0.10],
                label="Operating Cost"
            ),
            ShockSpec(
                parameter="discount_rate",
                shocks=[-0.01, -0.005, 0.005, 0.01],
                label="Discount Rate"
            ),
        ]
    
    @staticmethod
    def capex_shock() -> ShockSpec:
        """Standard CAPEX shock (±10%)."""
        return ShockSpec(
            parameter="capex",
            shocks=[-0.10, -0.05, 0.05, 0.10],
            label="Capital Cost"
        )
    
    @staticmethod
    def tariff_shock() -> ShockSpec:
        """Standard tariff shock (±10%)."""
        return ShockSpec(
            parameter="tariff",
            shocks=[-0.10, -0.05, 0.05, 0.10],
            label="Tariff Rate"
        )
    
    @staticmethod
    def capacity_factor_shock() -> ShockSpec:
        """Standard capacity factor shock (±10%)."""
        return ShockSpec(
            parameter="capacity_factor",
            shocks=[-0.10, -0.05, 0.05, 0.10],
            label="Capacity Factor"
        )


class ParameterRangeConfig(BaseModel):
    """
    Parameter shock configuration for sensitivity analysis.

    CESSPIT: Contract-explicit parameter bounds.
    """

    model_config = ConfigDict(frozen=True)

    variable_name: str = Field(
        description="Dotted path to parameter (e.g., 'finance.capex_usd')"
    )
    base_value: float = Field(description="Base case value")
    low_pct: float = Field(description="Low shock as % (e.g., -10.0 for -10%)")
    high_pct: float = Field(description="High shock as % (e.g., 10.0 for +10%)")
    label: Optional[str] = Field(default=None, description="Display label")

    @field_validator("low_pct", "high_pct")
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
# Tail Risk Contracts (Sprint 17 - Pydantic V2 Migration)
# ═════════════════════════════════════════════════════════════════════════════


class TailRiskMetrics(BaseModel):
    """
    Computed tail-risk metrics for a single KPI distribution.

    This is the lightweight contract returned by compute_tail_risk_metrics().
    Contains only computed values (no metadata like metric name or confidence).

    CASPER: Frozen contract for tail risk snapshots.
    CESSPIT: All values computed from MC samples.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    var: float = Field(description="Value-at-Risk at confidence level")
    cvar: float = Field(description="Conditional VaR (Expected Shortfall)")
    p10: float = Field(description="10th percentile")
    p50: float = Field(description="50th percentile (median)")
    p90: float = Field(description="90th percentile")
    breach_prob: float = Field(
        ge=0.0, le=1.0, description="Probability of breach (sample < VaR)"
    )


class TailRiskSnapshot(BaseModel):
    """
    Complete tail-risk snapshot with full context.

    This contract includes metric name and confidence level, making it
    suitable for CASPER reporting and dashboards.

    Built by build_tail_risk_snapshot() in sensitivity_tail_risk.py.

    CASPER: Full audit trail with metric name + confidence.
    CESSPIT: All values computed, no defaults.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(description="Metric name (e.g., 'project_irr', 'min_dscr')")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence level (e.g., 0.9 for 90%)")
    var: float = Field(description="Value-at-Risk at confidence level")
    cvar: float = Field(description="Conditional VaR (Expected Shortfall)")
    p10: float = Field(description="10th percentile")
    p50: float = Field(description="50th percentile (median)")
    p90: float = Field(description="90th percentile")
    breach_probability: float = Field(
        ge=0.0, le=1.0, description="Probability of breach (sample < VaR)"
    )


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

    def contract_version(self) -> str:
        """Contract version - computed property."""
        return CASPER_CONTRACT_VERSION


class MonteCarloResult(BaseModel):
    """
    Monte Carlo simulation result.

    CASPER: Frozen contract for MC outputs.
    CESSPIT: All values computed, no defaults.
    """

    model_config = ConfigDict(frozen=True)

    scenario_name: str = Field(description="MC scenario identifier")
    n_iterations: int = Field(gt=0, description="Number of iterations executed")
    
    # Distribution statistics
    mean: float = Field(description="Mean of metric distribution")
    std: float = Field(ge=0.0, description="Standard deviation")
    
    # Percentiles
    p10: float = Field(description="10th percentile")
    p50: float = Field(description="50th percentile (median)")
    p90: float = Field(description="90th percentile")
    
    # Extreme values
    min_value: float = Field(description="Minimum value observed")
    max_value: float = Field(description="Maximum value observed")
    
    # Risk metrics
    var_95: Optional[float] = Field(default=None, description="Value at Risk (95%)")
    cvar_95: Optional[float] = Field(default=None, description="Conditional VaR (95%)")
    
    # Metadata
    metric_name: str = Field(description="Metric analyzed (irr, npv, dscr, etc)")
    sampling_method: str = Field(description="Sampling method used")
    execution_time_seconds: Optional[float] = Field(default=None, ge=0.0)


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


@dataclass
class TrancheDebtProfile:
    """Lender-facing debt tranche summary for covenant reporting.
    
    Sprint 16 - Required by pipeline_v14.py for debt profiling.
    """

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


@dataclass
class DebtCovenantSnapshot:
    """Debt covenant compliance snapshot for lender reporting.
    
    Sprint 16 - Required by pipeline_v14.py for covenant tracking.
    """

    dscr_min: float
    dscr_threshold: float
    years_below_threshold: int
    first_breach_year: Optional[int] = None
    last_breach_year: Optional[int] = None
    balloon_remaining: float = 0.0
    balloon_flag: bool = False
    audit_status: str = "REVIEW"
    notes: str = ""


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
    debt_profile: Optional[TrancheDebtProfile] = None
    debt_covenants: Optional[DebtCovenantSnapshot] = None

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


# Helper function for backward compatibility with cashflow contract building
def build_cashflow_result_from_annual_rows(
    config: Dict[str, Any], annual_rows: Sequence[Dict[str, Any]]
) -> Optional[Any]:
    """Build CashflowResult from annual rows.
    
    Placeholder for future cashflow contract implementation.
    Currently returns None as CashflowResult is a forward reference.
    """
    # TODO: Implement when CashflowResult contract is defined
    return None


__all__ = [
    "CASPER_CONTRACT_VERSION",
    # Monte Carlo (Sprint 16 - Issue #43)
    "Distribution",
    "DerivedParameter",
    "MonteCarloScenario",
    "MonteCarloResult",
    # WACC
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    # Debt Profiling (Sprint 16 - Pipeline Integration)
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    # FX
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    # Sensitivity (with new ShockSpec and StandardShockLibrary)
    "ShockSpec",
    "StandardShockLibrary",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "SensitivityRequest",
    "BreakevenResult",
    # Tail Risk (Sprint 17)
    "TailRiskMetrics",
    "TailRiskSnapshot",
    # CASPER
    "CasperResult",
    "ShockResult",
    # Helper functions
    "build_cashflow_result_from_annual_rows",
]
