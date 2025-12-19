"""FX Structured Blocks, Curves, and Risk Profiles (v14R6).

Complete Pydantic v2 models for FX hedging strategies and
exposure management in renewable energy projects.

Integration:
- ScenarioResult.fx_block, fx_curve, fx_risk_profile
- Monte Carlo FX shock scenarios
- Sensitivity analysis for currency risk

Sprint 12 Status: Stable with compatibility stub for FXMonteCarloConfig.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FXStructuredBlock(BaseModel):
    """FX hedging structured block."""
    model_config = ConfigDict(extra='allow')
    
    block_id: str
    currency_pair: str  # e.g., "USD/LKR"
    notional_amount: float
    hedge_ratio: float  # 0.0 to 1.0
    hedge_type: str  # "forward", "option", "collar"


class FXCurveOutput(BaseModel):
    """FX forward curve output."""
    model_config = ConfigDict(extra='allow')
    
    base_rate: float
    curve_points: List[Dict[str, float]] = []  # [{"year": 1, "rate": 195.5}]


class FXRiskProfile(BaseModel):
    """FX exposure risk profile."""
    model_config = ConfigDict(extra='allow')
    
    total_exposure_usd: float
    hedged_exposure_usd: float
    unhedged_exposure_usd: float
    var_90_usd: float  # Value at Risk


# Compatibility stub for Monte Carlo tests
class FXMonteCarloConfig(BaseModel):
    """Temporary stub - FX Monte Carlo configuration.
    
    Used by test_fx_structured_blocks.py during migration.
    Real implementation in analytics.contracts_v14.FXMonteCarloConfig (dataclass).
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    
    base_rate: float = 0.0
    volatility_pct: float = 0.0
    correlation_to_cashflow: float = 0.0
    shock_range_pct: float = 0.0
    escalation_base_pct: Optional[float] = None


__all__ = [
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    "FXMonteCarloConfig",  # Temporary
]
