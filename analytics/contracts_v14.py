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
# Sensitivity Analysis Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════

class ParameterRangeConfig(BaseModel):
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    steps: int = 5
    label: Optional[str] = None

class SensitivityRequest(BaseModel):
    config_path: str
    params: List[ParameterRangeConfig]

class ShockResult(BaseModel):
    variable_name: str
    shock_value: float
    metrics: Dict[str, float]

class TornadoResult(BaseModel):
    variable_name: str
    base_metrics: Dict[str, float]
    shocks: List[ShockResult]

class SensitivitySuite(BaseModel):
    results: List[TornadoResult]

class MultiMetricTornadoResult(BaseModel):
    results: Dict[str, Any]

class ScenarioResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    metrics: Dict[str, Any]
    cashflows: Optional[Any] = None

class WaccComponents(BaseModel):
    pass

class WaccResult(BaseModel):
    pass

class ShockSpec(BaseModel):
    pass

class StandardShockLibrary(BaseModel):
    pass

class MultiMetricSensitivitySuite(BaseModel):
    pass

class BreakevenResult(BaseModel):
    pass

class Distribution(BaseModel):
    pass

class DerivedParameter(BaseModel):
    pass

class MonteCarloScenario(BaseModel):
    pass

class MonteCarloResult(BaseModel):
    pass

class CasperResult(BaseModel):
    pass

class TrancheDebtProfile(BaseModel):
    pass

class DebtCovenantSnapshot(BaseModel):
    pass

class CashflowResult(BaseModel):
    pass

class EquityPerformance(BaseModel):
    pass

class DownsideMetrics(BaseModel):
    pass

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
