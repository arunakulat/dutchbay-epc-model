from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple, Union

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
    
    Backward Compatibility (Pydantic v1 → v2 Migration):
        The following computed properties maintain compatibility with legacy code:
        - variable_name: returns parameter
        - low_value: returns min(shocks)
        - high_value: returns max(shocks)
        - base_value: returns 0.0 (shocks are relative percentages)
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
    
    # === BACKWARD COMPATIBILITY PROPERTIES (Sprint 17 Fix - Issue #52) ===
    
    @computed_field  # type: ignore[misc]
    @property
    def variable_name(self) -> str:
        """Backward compatibility property for legacy sensitivity_runner.py.
        
        Returns the parameter name. Allows legacy code using shock.variable_name
        to continue working after Pydantic v2 migration renamed this field.
        """
        return self.parameter
    
    @computed_field  # type: ignore[misc]
    @property
    def low_value(self) -> float:
        """Lowest (most negative) shock value.
        
        For sensitivity runner compatibility. Returns min(shocks).
        """
        return min(self.shocks) if self.shocks else 0.0
    
    @computed_field  # type: ignore[misc]
    @property
    def high_value(self) -> float:
        """Highest (most positive) shock value.
        
        For sensitivity runner compatibility. Returns max(shocks).
        """
        return max(self.shocks) if self.shocks else 0.0
    
    @computed_field  # type: ignore[misc]
    @property
    def base_value(self) -> float:
        """Base value for shock application.
        
        Returns 0.0 because shocks are defined as relative percentages,
        not absolute values. The actual base comes from config.
        """
        return 0.0


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
    
    # === FACTORY METHODS FOR SENSITIVITY RUNNER (take base value) ===
    
    @staticmethod
    def capacity_factor(base: float) -> ShockSpec:
        """Capacity factor shock with ±10%."""
        return ShockSpec(
            parameter="capacity_factor",
            shocks=[-0.10, 0.10],
            label="Capacity Factor"
        )
    
    @staticmethod
    def capex_overrun(base: float) -> ShockSpec:
        """CAPEX overrun shock with +10%/-5%."""
        return ShockSpec(
            parameter="capex",
            shocks=[-0.05, 0.10],
            label="CAPEX Cost"
        )
    
    @staticmethod
    def opex_variation(base: float) -> ShockSpec:
        """OPEX variation shock with ±10%."""
        return ShockSpec(
            parameter="opex",
            shocks=[-0.10, 0.10],
            label="OPEX Cost"
        )
    
    @staticmethod
    def power_price(base: float) -> ShockSpec:
        """Power price (tariff) shock with ±10%."""
        return ShockSpec(
            parameter="tariff",
            shocks=[-0.10, 0.10],
            label="Power Price"
        )
    
    @staticmethod
    def debt_tenor(base: float) -> ShockSpec:
        """Debt tenor shock with ±2 years (as percentage of base)."""
        tenor_shock_pct = 2.0 / base if base > 0 else 0.1
        return ShockSpec(
            parameter="debt_tenor",
            shocks=[-tenor_shock_pct, tenor_shock_pct],
            label="Debt Tenor"
        )
    
    @staticmethod
    def interest_rate(base: float) -> ShockSpec:
        """Interest rate shock with ±100 bps (as percentage of base)."""
        rate_shock_pct = 0.01 / base if base > 0 else 0.1
        return ShockSpec(
            parameter="interest_rate",
            shocks=[-rate_shock_pct, rate_shock_pct],
            label="Interest Rate"
        )


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
# Monte Carlo Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════


class Distribution(BaseModel):
    """Distribution specification for Monte Carlo sampling.
    
    CASPER: Contract-explicit probability distribution.
    CESSPIT: All distribution parameters from config.
    
    Example:
        >>> dist = Distribution(
        ...     variable_name="capex",
        ...     dist_type="normal",
        ...     mean=1200.0,
        ...     std=120.0
        ... )
    """
    model_config = ConfigDict(frozen=True)
    
    variable_name: str = Field(description="Variable name")
    dist_type: Literal["normal", "triangular", "uniform", "lognormal"] = Field(
        description="Distribution type"
    )
    mean: Optional[float] = Field(default=None, description="Mean (for normal/lognormal)")
    std: Optional[float] = Field(default=None, description="Standard deviation")
    min_val: Optional[float] = Field(default=None, description="Minimum value")
    max_val: Optional[float] = Field(default=None, description="Maximum value")
    mode: Optional[float] = Field(default=None, description="Mode (for triangular)")
    description: Optional[str] = Field(default=None, description="Description")


class DerivedParameter(BaseModel):
    """Derived parameter computed from other sampled parameters.
    
    CASPER: Explicit dependency tracking.
    
    Example:
        >>> param = DerivedParameter(
        ...     name="total_opex",
        ...     formula="fixed_opex + variable_opex * generation",
        ...     depends_on=["fixed_opex", "variable_opex", "generation"]
        ... )
    """
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(description="Derived parameter name")
    formula: str = Field(description="Python expression to compute value")
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of parameter names this depends on"
    )


class MonteCarloScenario(BaseModel):
    """Monte Carlo scenario configuration.
    
    CASPER: Complete MC scenario specification.
    CESSPIT: All parameters from config, no hidden defaults.
    
    Example:
        >>> scenario = MonteCarloScenario(
        ...     name="base_case",
        ...     n_iterations=1000,
        ...     distributions=[dist1, dist2],
        ...     seed=42
        ... )
    """
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(description="Scenario name")
    n_iterations: int = Field(gt=0, description="Number of iterations")
    distributions: List[Distribution] = Field(
        default_factory=list,
        description="Parameter distributions"
    )
    derived_parameters: List[DerivedParameter] = Field(
        default_factory=list,
        description="Derived parameters"
    )
    seed: Optional[int] = Field(default=None, description="Random seed")
    sampling_method: str = Field(default="lhs", description="Sampling method (lhs/random)")


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result with lender-grade analytics support.
    
    Enhanced contract (Sprint 18) to support breach probability calculations
    and worst-case downside statistics required by analytics/mc/exports.py.
    
    CRITICAL FIELD: trials
    ----------------------
    The `trials` field stores raw per-trial metric arrays. This is REQUIRED
    for computing lender-grade risk metrics:
    - Prob(DSCR < covenant_floor)
    - Worst-year DSCR P95 downside (5th percentile)
    - Custom breach statistics
    
    Without raw trial data, these metrics cannot be computed correctly.
    
    Structure:
    ----------
    trials: Dict[str, List[float]]
        {
            "dscr_min": [1.32, 1.45, 1.51, ...],  # n_trials values
            "project_irr": [0.142, 0.138, ...],
            "project_npv": [55.3e9, 48.2e9, ...],
            "llcr": [1.65, 1.48, ...],
            "plcr": [1.55, 1.38, ...],
        }
    
    summary: Dict[str, Any]
        {
            "dscr_min": {"mean": 1.42, "std": 0.08, "P50": 1.45, "P90": 1.32},
            "project_irr": {"mean": 0.139, "std": 0.012, "P50": 0.142},
            ...
        }
    
    metadata: Dict[str, Any]
        {
            "n_trials": 1000,
            "seed": 42,
            "sampler": "lhs",
            "correlation_enabled": true,
            "config_hash": "abc123..."
        }
    
    Example:
    --------
    >>> result = MonteCarloResult(
    ...     summary={"dscr_min": {"mean": 1.42, "P50": 1.45}},
    ...     metadata={"n_trials": 1000, "seed": 42},
    ...     trials={"dscr_min": [1.32, 1.45, 1.51, ...]},
    ... )
    >>> 
    >>> # Lender analytics
    >>> from analytics.mc.exports import build_lender_risk_table, CovenantSpec
    >>> table = build_lender_risk_table(result, covenant=CovenantSpec(dscr_floor=1.30))
    
    FRAMEWORK COMPLIANCE:
    ---------------------
    ✅ CASPER: Contract-explicit schema with validation
    ✅ CESSPIT: Fail-fast if trials missing for lender metrics
    ✅ GWTF: Single source of truth for MC results
    ✅ CCCDIR: Comprehensive docstrings
    
    BACKWARD COMPATIBILITY:
    -----------------------
    Old code using only `summary` continues to work. The `trials` field
    is Optional for now but STRONGLY RECOMMENDED for production use.
    
    Future: Make `trials` required (breaking change in v15.0.0).
    """
    model_config = ConfigDict(frozen=True)
    
    summary: Dict[str, Any] = Field(
        description="Aggregated statistics per metric (mean, std, percentiles)"
    )
    metadata: Dict[str, Any] = Field(
        description="Execution metadata (n_trials, seed, correlation_enabled, etc.)"
    )
    trials: Optional[Dict[str, List[float]]] = Field(
        default=None,
        description="Raw per-trial arrays for each metric (REQUIRED for lender analytics)"
    )
    percentiles: Optional[Dict[int, Dict[str, float]]] = Field(
        default=None,
        description="Percentile lookup table: {50: {'dscr_min': 1.45}, 90: {...}}"
    )
    
    @field_validator('trials')
    @classmethod
    def validate_trials_consistent(cls, v: Optional[Dict[str, List[float]]]) -> Optional[Dict[str, List[float]]]:
        """Validate all trial arrays have same length."""
        if v is None:
            return v
        if not v:
            return v
        lengths = {k: len(arr) for k, arr in v.items()}
        unique_lengths = set(lengths.values())
        if len(unique_lengths) > 1:
            raise ValueError(
                f"All trial arrays must have same length. Got: {lengths}"
            )
        return v


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


# ═════════════════════════════════════════════════════════════════════════════
# WACC, Lender/Scenario Results (Phase 1) - Dataclass Contracts
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class WaccResult:
    """Complete WACC result including base and prudential valuations."""

    base: WaccComponents
    prudential_rate: Optional[float] = None
    prudential_npv: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrancheDebtProfile:
    """Aggregate per-tranche debt profile for a scenario (Lender View)."""
    
    construction_years: int = 0
    tenor_years: int = 0
    timeline_periods: int = 0
    total_debt: float = 0.0
    total_idc: float = 0.0
    lkr_principal: float = 0.0
    usd_principal: float = 0.0
    dfi_principal: float = 0.0
    lkr_idc: float = 0.0
    usd_idc: float = 0.0
    dfi_idc: float = 0.0
    lkr_rate: Optional[float] = None
    usd_rate: Optional[float] = None
    dfi_rate: Optional[float] = None
    interest_only_years: int = 0
    amortization_style: str = "sculpted"
    dscr_target: Optional[float] = None


@dataclass(frozen=True)
class DebtCovenantSnapshot:
    """Covenant snapshot for a single debt case (DSCR, LLCR, PLCR)."""
    
    dscr_min: float
    dscr_threshold: float
    years_below_threshold: int
    first_breach_year: Optional[int] = None
    last_breach_year: Optional[int] = None
    balloon_flag: bool = False
    balloon_remaining: float = 0.0
    llcr: Optional[float] = None
    plcr: Optional[float] = None
    llcr_threshold: Optional[float] = None
    plcr_threshold: Optional[float] = None
    fx_min: Optional[float] = None
    fx_max: Optional[float] = None
    fx_avg: Optional[float] = None
    notes: str = ""
    audit_status: str = "REVIEW"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CashflowResult:
    """Canonical multi-year project cashflow surface in LKR."""
    
    years: List[int]
    annual_rows: List[Dict[str, float]]
    gross_generation_kwh: List[float]
    net_generation_kwh: List[float]
    revenue_lkr: List[float]
    statutory_deductions_lkr: List[float]
    opex_lkr: List[float]
    pretax_cfads_lkr: List[float]
    tax_lkr: List[float]
    posttax_cfads_lkr: List[float]
    cfads_final_lkr: List[float]
    depreciation_lkr: List[float]
    interest_expense_lkr: List[float]
    taxable_income_lkr: List[float]
    risk_haircut_pct: float
    risk_haircut_amount_lkr: List[float]
    fx_curve_lkr_per_usd: Optional[List[float]] = None
    notes: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)

    def as_dict_rows(self) -> List[Dict[str, float]]:
        return list(self.annual_rows)


@dataclass(frozen=True)
class DownsideMetrics:
    """Downside risk metrics for equity performance."""
    
    prob_negative_npv: Optional[float] = None
    prob_below_hurdle: Optional[float] = None
    worst_case_irr: Optional[float] = None
    max_drawdown: Optional[float] = None


@dataclass(frozen=True)
class EquityPerformance:
    """Equity performance metrics."""
    
    equity_irr: Optional[float] = None
    equity_npv: Optional[float] = None
    moic: Optional[float] = None
    dpi: Optional[float] = None
    rvpi: Optional[float] = None
    tvpi: Optional[float] = None
    annual_coc: List[float] = field(default_factory=list)
    average_coc: float = 0.0
    payback_period_years: Optional[float] = None
    downside: Optional[DownsideMetrics] = None


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
    cashflow: Optional[CashflowResult] = None

    equity_performance: Optional[EquityPerformance] = None
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


__all__ = [
    "CASPER_CONTRACT_VERSION",
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    # Sensitivity contracts
    "ShockSpec",
    "StandardShockLibrary",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "SensitivityRequest",
    "BreakevenResult",
    "ShockResult",
    # Monte Carlo contracts
    "Distribution",
    "DerivedParameter",
    "MonteCarloScenario",
    "MonteCarloResult",
    # CASPER
    "CasperResult",
    # Debt & Cashflow contracts
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    "CashflowResult",
    "EquityPerformance",
    "DownsideMetrics",
]
