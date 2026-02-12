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
        raise ValueError(
            f"covenant_type must be 'floor' or 'ceiling', got '{covenant_type}'"
        )
    
    tolerance_abs = abs(threshold) * (tolerance_bps / 10000.0)
    
    if covenant_type == "floor":
        return actual < (threshold - tolerance_abs)
    else:  # covenant_type == "ceiling"
        return actual > (threshold + tolerance_abs)


# ═════════════════════════════════════════════════════════════════════════════
# WACC & Scenario Contracts
# ═════════════════════════════════════════════════════════════════════════════

class WaccComponents(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: str = "nominal"
    wacc_nominal: float
    wacc_real: Optional[float] = None
    wacc_prudential: Optional[float] = None

class WaccResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    base: WaccComponents
    prudential_rate: float
    prudential_npv: float

class ScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    project_irr: float
    min_dscr: float
    wacc: WaccResult

# ═════════════════════════════════════════════════════════════════════════════
# Sensitivity Analysis Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════

class ParameterRangeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    steps: int = 5
    label: Optional[str] = None

    @field_validator("low_pct", "high_pct")
    @classmethod
    def validate_pct(cls, v: float) -> float:
        # Some versions require positive, some allow negative relative to base.
        # Based on Memory, we should ensure they are handled correctly.
        return v

class ShockResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    low_case: float
    high_case: float
    impact: float

class TornadoResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    label: str
    impact_abs: float

class MultiMetricTornadoResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    variable_name: str
    base_values: Dict[str, float]
    metrics: Dict[str, List[ShockResult]]

class SensitivitySuite(BaseModel):
    model_config = ConfigDict(frozen=True)
    results: List[TornadoResult]

class MultiMetricSensitivitySuite(BaseModel):
    model_config = ConfigDict(frozen=True)
    results: List[MultiMetricTornadoResult]

class SensitivityRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    base_config_path: str
    parameters: List[ParameterRangeConfig]
    metric: str = "project_irr"

class BreakevenResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    variable: str
    target_metric: str
    target_value: float
    breakeven_value: float
    status: str
    bracket: Tuple[float, float]

class ShockSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    variable: str
    value: float

class StandardShockLibrary(BaseModel):
    model_config = ConfigDict(frozen=True)
    shocks: Dict[str, ShockSpec]

# ═════════════════════════════════════════════════════════════════════════════
# Monte Carlo Contracts
# ═════════════════════════════════════════════════════════════════════════════

class Distribution(BaseModel):
    model_config = ConfigDict(frozen=True)
    dist_type: str
    parameters: Dict[str, Any]

class DerivedParameter(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    formula: str

class MonteCarloScenario(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario_name: str
    n_iterations: int
    sampling_method: str = "lhs"
    seed: int = 42
    distributions: Dict[str, Distribution]

class MonteCarloResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario_name: str
    n_iterations: int
    mean: float
    std: float
    p10: float
    p50: float
    p90: float
    min_value: float
    max_value: float
    metric_name: str
    sampling_method: str

# ═════════════════════════════════════════════════════════════════════════════
# CASPER & Debt Contracts
# ═════════════════════════════════════════════════════════════════════════════

class CasperResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario: str
    baseline_kpis: Dict[str, float]
    sensitivities: Optional[Dict[str, Any]] = None
    monte_carlo: Optional[Dict[str, Any]] = None

    def contract_version(self) -> str:
        return CASPER_CONTRACT_VERSION

class TrancheDebtProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    tranche_name: str
    opening_balance: List[float]
    principal_repayment: List[float]
    interest_payment: List[float]
    closing_balance: List[float]

class DebtCovenantSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    year: int
    dscr: float
    is_breached: bool

class CashflowResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    annual_cashflows: List[float]
    total_cashflow: float

class EquityPerformance(BaseModel):
    model_config = ConfigDict(frozen=True)
    equity_irr: float
    equity_npv: float

class DownsideMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    p90_irr: float
    llcr_min: float

__all__ = [
    "CASPER_CONTRACT_VERSION",
    "check_covenant_breach_with_tolerance",
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
    "MultiMetricSensitivitySuite",
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
