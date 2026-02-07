from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

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
    if tolerance_bps < 0:
        raise ValueError(f"Tolerance must be non-negative, got {tolerance_bps}bp")

    if covenant_type not in ("floor", "ceiling"):
        raise ValueError(
            f"covenant_type must be 'floor' or 'ceiling', got '{covenant_type}'"
        )

    tolerance_abs = abs(threshold) * (tolerance_bps / 10000.0)

    if covenant_type == "floor":
        return actual < (threshold - tolerance_abs)
    else:  # covenant_type == "ceiling"
        return actual > (threshold + tolerance_abs)


# ═════════════════════════════════════════════════════════════════════════════
# WACC and Scenario Results
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class WaccComponents:
    """Breakdown of Weighted Average Cost of Capital components."""

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
    """Complete WACC calculation result."""

    base: WaccComponents
    prudential_rate: float
    prudential_npv: float


@dataclass
class ScenarioResult:
    """Full scenario evaluation output."""

    name: str
    config_path: Path
    kpis: Dict[str, Any]
    annual_rows: List[Dict[str, Any]]
    debt_result: Dict[str, Any]
    discount_rate: float
    fail_reason: Optional[str] = None
    project_irr: Optional[float] = None
    min_dscr: Optional[float] = None
    project_npv: Optional[float] = None


# ═════════════════════════════════════════════════════════════════════════════
# Sensitivity Analysis Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════


class ParameterRangeConfig(BaseModel):
    """Configuration for a single parameter's sensitivity range."""

    model_config = ConfigDict(frozen=True)
    variable_name: str
    base_value: float
    low_pct: float = Field(ge=-100, le=100)
    high_pct: float = Field(ge=-100, le=100)
    steps: int = Field(default=5, ge=2, le=20)
    label: Optional[str] = None
    shock_type: str = "scalar"


class ShockResult(BaseModel):
    """Result of a single parameter shock."""

    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    impact: float = 0.0
    direction: str = ""
    sensitivity: float = 0.0
    metric_name: str = ""
    label: Optional[str] = None


class TornadoResult(BaseModel):
    """Single parameter tornado sensitivity result."""

    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    label: Optional[str] = None
    impact_abs: float = 0.0
    low_case_metric: Optional[float] = None
    high_case_metric: Optional[float] = None


class MultiMetricTornadoResult(BaseModel):
    """Multi-metric tornado result for a single parameter."""

    variable: str
    label: str
    base_values: Dict[str, float]
    low_values: Dict[str, float]
    high_values: Dict[str, float]
    impacts: Dict[str, float] = Field(default_factory=dict)
    impact_dirs: Dict[str, int] = Field(default_factory=dict)


class SensitivitySuite(BaseModel):
    """Complete sensitivity analysis suite."""

    metric: str
    base_config_path: str
    tornado_results: List[TornadoResult]
    base_kpis: Optional[Dict[str, float]] = None
    base_metric_value: float = 0.0


class MultiMetricSensitivitySuite(BaseModel):
    """Multi-metric tornado sensitivity suite."""

    tornado_results: List[MultiMetricTornadoResult]
    base_metrics: Dict[str, float]
    base_config_path: str
    metrics: List[str]


class SensitivityRequest(BaseModel):
    """Request for sensitivity analysis."""

    base_config_path: str
    parameters: List[ParameterRangeConfig]
    metric: str = "project_irr"


class BreakevenResult(BaseModel):
    """Result of a breakeven analysis."""

    variable: str
    breakeven_value: float
    bracket: Tuple[float, float]
    status: str = "success"
    target_metric: str = "project_irr"
    target_value: float = 0.0


class ShockSpec(BaseModel):
    """Legacy/Compatibility shock specification."""

    variable_name: str
    low_value: float
    high_value: float
    label: Optional[str] = None


class StandardShockLibrary:
    """Library of standard project finance shocks."""

    @staticmethod
    def capex_overrun(base_capex: float) -> ShockSpec:
        return ShockSpec(
            variable_name="capex", low_value=base_capex, high_value=base_capex * 1.1
        )


# ═════════════════════════════════════════════════════════════════════════════
# Monte Carlo and Risk Contracts
# ═════════════════════════════════════════════════════════════════════════════


class Distribution(BaseModel):
    """Monte Carlo distribution specification."""

    dist_type: str = "normal"
    mean: float = 0.0
    std: float = 0.0
    parameters: Dict[str, Any] = Field(default_factory=dict)


class DerivedParameter(BaseModel):
    """Computed parameter in Monte Carlo."""

    name: str
    formula: str


class MonteCarloScenario(BaseModel):
    """Monte Carlo simulation configuration."""

    scenario_name: str
    n_iterations: int = 1000
    sampling_method: str = "latin_hypercube"
    seed: Optional[int] = None
    distributions: Dict[str, Distribution] = Field(default_factory=dict)


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation results."""

    scenario_name: str
    metric_name: str
    mean: float
    std: float
    p10: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    iterations: int = 0


class CasperResult(BaseModel):
    """Unified analysis result."""

    scenario: str
    baseline_kpis: Dict[str, float]
    sensitivities: Dict[str, Any] = Field(default_factory=dict)
    monte_carlo: Dict[str, Any] = Field(default_factory=dict)

    def contract_version(self) -> str:
        return CASPER_CONTRACT_VERSION


# ═════════════════════════════════════════════════════════════════════════════
# Debt, Cashflow, and Equity Contracts
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TrancheDebtProfile:
    """Debt profile for a single tranche."""

    construction_years: int = 0
    tenor_years: int = 0
    coupon_pct: float = 0.0


@dataclass
class DebtCovenantSnapshot:
    """Snapshot of debt covenants at a point in time."""

    dscr: float
    llcr: Optional[float] = None
    is_breached: bool = False


@dataclass
class CashflowResult:
    """Annual cashflow series results."""

    annual_cashflows: List[Dict[str, Any]]
    project_life_years: int
    construction_years: int


@dataclass
class EquityPerformance:
    """Equity return metrics."""

    equity_irr: float
    equity_npv: float
    equity_multiple: float
    downside_return_pct: float = 0.0


@dataclass
class DownsideMetrics:
    """Metrics specifically for downside/risk analysis."""

    p10_return: float = 0.0
    worst_case_irr: float = 0.0


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
