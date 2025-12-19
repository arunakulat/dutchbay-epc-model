from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

# ═════════════════════════════════════════════════════════════════════════════
# VERSION & FRAMEWORK METADATA (CASPER)
# ═════════════════════════════════════════════════════════════════════════════

CASPER_CONTRACT_VERSION = "v14.3.0"
"""CASPER framework version for this contract set."""


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
# DEBT & EQUITY CONTRACTS (Phase 1-2)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class TrancheDebtProfile:
    """Individual debt tranche profile (senior, mezzanine, etc)."""

    tranche_id: str
    principal_usd: float
    tenor_years: int
    coupon_pct: float
    disbursement_schedule: Dict[int, float]  # {year: amount}
    min_dscr_requirement: float
    covenant_breaches: int = 0


@dataclass
class DebtCovenantSnapshot:
    """CASPER: Debt covenant status at each year (for tail risk analysis)."""

    year: int
    dscr: float
    min_dscr_requirement: float
    is_breach: bool
    cushion_pct: float  # (dscr - requirement) / requirement
    principal_outstanding_usd: float
    interest_expense_usd: float
    debt_service_coverage_metric: str  # "EBITDA" or "Net CF"


@dataclass
class EquityPerformance:
    """Equity IRR, NPV, and downside metrics."""

    equity_irr: float
    equity_npv: float
    equity_multiple: float
    year_1_dividend: float
    dividend_schedule: Dict[int, float]  # {year: dividend}
    downside_return_pct: float  # 10th percentile return


@dataclass
class EquityResult:
    """CCCDIR: Complete equity evaluation result."""

    scenario_name: str
    equity_irr: float
    equity_npv: float
    equity_multiple: float
    performance: EquityPerformance
    covenant_breaches: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═════════════════════════════════════════════════════════════════════════════
# MONTE CARLO CONTRACTS (Phase 2-3)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class DerivedParameter:
    """CASPER: Envelope of derived parameter from Monte Carlo."""

    name: str
    base_value: float
    p10: float  # 10th percentile
    p50: float  # Median
    p90: float  # 90th percentile
    min_value: float
    max_value: float
    stdev: float
    correlation_to_irr: float


@dataclass
class MonteCarloResult:
    """CASPER: Complete Monte Carlo simulation output."""

    scenario_name: str
    n_iterations: int
    n_success: int
    success_rate: float
    base_irr: float
    median_irr: float
    p10_irr: float
    p90_irr: float
    std_irr: float
    var_90: float  # Value at Risk at 90% confidence
    cvar_90: float  # Conditional VaR
    base_dscr: float
    min_dscr_series: List[float]  # Annual minimum DSCR values
    derived_parameters: List[DerivedParameter] = field(default_factory=list)
    random_seed: int = 0
    sampler_type: str = "LHS"  # Latin Hypercube Sampling
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None


@dataclass
class FXMonteCarloConfig:
    """CESSPIT: FX Monte Carlo configuration for structured scenarios."""

    base_rate: float
    volatility_pct: float
    correlation_to_cashflow: float
    shock_range_pct: float  # ±% to test
    escalation_base_pct: Optional[float] = None  # Annual escalation if not shocked


# ═════════════════════════════════════════════════════════════════════════════
# SENSITIVITY & TORNADO CONTRACTS (Phase 2)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class ParameterRangeConfig:
    """CCCDIR: Configuration for a single sensitivity parameter."""

    variable_name: str  # e.g., "project.capacity_factor"
    base_value: float
    low_value: Optional[float] = None
    high_value: Optional[float] = None
    low_pct: Optional[float] = None  # If using percentages
    high_pct: Optional[float] = None
    label: Optional[str] = None
    shock_type: str = "scalar"  # "scalar" or "proportional"


@dataclass
class ShockSpec:
    """CCCDIR: Single shock specification for sensitivity."""

    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    label: str
    shock_type: str = "proportional"


@dataclass
class ShockResult:
    """CCCDIR: Result of single shock."""

    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str
    label: Optional[str] = None

    @property
    def impact(self) -> float:
        """CASPER: Total impact (half of range to capture magnitude)."""
        return abs(self.high_metric - self.low_metric) / 2.0

    @property
    def direction(self) -> str:
        """CASPER: Which direction has larger impact."""
        if self.high_metric - self.base_metric > abs(self.low_metric - self.base_metric):
            return "UP"
        elif self.low_metric - self.base_metric < abs(self.high_metric - self.base_metric):
            return "DOWN"
        return "NEUTRAL"


@dataclass
class TornadoResult:
    """CASPER: Tornado chart data (all shocks ranked by impact)."""

    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    low_case_metric: Optional[float] = None
    high_case_metric: Optional[float] = None

    def sorted_by_impact(self) -> List[ShockResult]:
        """Return shocks sorted by absolute impact (descending)."""
        return sorted(self.shock_results, key=lambda x: abs(x.impact), reverse=True)


@dataclass
class SensitivitySuite:
    """CCCDIR: Complete sensitivity analysis output."""

    scenario_name: str
    metric_name: str
    base_metric: float
    tornado_results: List[ShockResult]
    n_shocks: int
    min_metric: float
    max_metric: float
    range_metric: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None


@dataclass
class BreakevenResult:
    """CASPER: Breakeven analysis (what value makes project NPV=0)."""

    variable_name: str
    base_value: float
    breakeven_value: float
    breakeven_pct_change: float
    is_positive_breakeven: bool  # True if higher value breaks even, False if lower
    metric_name: str = "project_npv"
    tolerance: float = 1000.0  # USD tolerance for breakeven definition


# ═════════════════════════════════════════════════════════════════════════════
# CASH FLOW & TECHNOLOGY CONTRACTS
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class CashflowResult:
    """CCCDIR: Annual cashflow breakdown."""

    annual_cashflows: List[float]
    project_life_years: int
    construction_years: int
    ncf_lcy: List[float]  # Net cash flow in local currency
    pv_lcy: List[float]  # Present value in local currency


@dataclass
class TechnologyBreakdown:
    """CASPER: Technology-specific metrics (capacity, efficiency, etc)."""

    technology_type: str  # e.g., "solar_pv", "wind"
    nameplate_capacity_mw: float
    availability_pct: float
    capacity_factor_pct: float
    annual_generation_gwh: float
    degradation_rate_pct: float
    technology_risk_premium_bps: int
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO & RESULTS CONTRACTS (Phase 1-3)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class ScenarioDescriptor:
    """CCCDIR: High-level scenario descriptor."""

    scenario_name: str
    scenario_type: str  # "base", "bear", "stress", "custom"
    config_path: str
    description: Optional[str] = None


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


# ═════════════════════════════════════════════════════════════════════════════
# UNIFIED RISK BUNDLE (Phase 3)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class OptimizationResult:
    """CASPER: Capital structure optimization result (Swimlane 1)."""

    scenario_name: str
    optimized_debt_usd: float
    optimized_equity_usd: float
    optimized_wacc: float
    optimized_equity_irr: float
    base_equity_irr: float
    improvement_bps: float
    constraints_met: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CapitalRiskBundle:
    """CCCDIR: Unified capital & risk analytics output.
    
    Combines baseline scenario results with optional sensitivity,
    Monte Carlo, and optimization layers for comprehensive risk reporting.
    
    CASPER Compliance:
    - All results traceable and auditable
    - Tail risk metrics (VaR, CVaR) included
    - Covenant breach probabilities captured
    - Metadata for lender reporting
    """

    scenario: ScenarioDescriptor
    baseline_kpis: Dict[str, float]
    
    wacc_result: Optional[WaccResult] = None
    equity_result: Optional[EquityResult] = None
    
    sensitivity_suite: Optional[SensitivitySuite] = None
    monte_carlo: Optional[MonteCarloResult] = None
    optimization_result: Optional[OptimizationResult] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None
    contract_version: str = CASPER_CONTRACT_VERSION


# ═════════════════════════════════════════════════════════════════════════════
# REFINANCING CONTRACTS (Phase 1 - Swimlane 1)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class RefinancingTrigger:
    """CCCDIR: Condition that triggers refinancing event."""

    trigger_type: str  # "dscr_floor", "scheduled", "opportunistic"
    trigger_value: Optional[float] = None  # DSCR floor if applicable
    trigger_year: Optional[int] = None  # Year if scheduled
    description: str = ""


@dataclass
class RefinancingStructure:
    """CCCDIR: Post-refinancing debt structure."""

    new_principal_usd: float
    new_coupon_pct: float
    new_tenor_years: int
    refinancing_cost_pct: float  # % of refinanced amount
    principal_repayment_usd: float  # From refinancing proceeds


@dataclass
class RefinancingResult:
    """CASPER: Refinancing event outcome."""

    year: int
    trigger_dscr: float
    pre_refi_npv: float
    post_refi_npv: float
    npv_benefit: float
    pre_refi_equity_irr: float
    post_refi_equity_irr: float
    equity_irr_benefit_bps: float
    covenant_breach_resolved: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Version
    "CASPER_CONTRACT_VERSION",
    # WACC
    "WaccComponents",
    "WaccResult",
    # Debt & Equity
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    "EquityPerformance",
    "EquityResult",
    # Monte Carlo
    "DerivedParameter",
    "MonteCarloResult",
    "FXMonteCarloConfig",
    # Sensitivity
    "ParameterRangeConfig",
    "ShockSpec",
    "ShockResult",
    "TornadoResult",
    "SensitivitySuite",
    "BreakevenResult",
    # Cashflow & Technology
    "CashflowResult",
    "TechnologyBreakdown",
    # Scenario
    "ScenarioDescriptor",
    "ScenarioResult",
    # Risk Bundle & Optimization
    "OptimizationResult",
    "CapitalRiskBundle",
    # Refinancing
    "RefinancingTrigger",
    "RefinancingStructure",
    "RefinancingResult",
    # FX (imported)
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
]

# EOF - analytics/contracts_v14.py
