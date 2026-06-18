"""Pydantic v2 Compatibility Stubs for Sprint 12 Migration.

This module provides minimal backward-compatible Pydantic v2 models
for legacy test files during the Sprint 12 refinancing/equity rollout.

Full migration plan:
- Sprint 12: Use these stubs to unblock new features
- Sprint 13: Migrate all analytics modules to native Pydantic v2
- Sprint 14: Remove this compatibility layer

Refs:
- process-improvements-nov27.md Rule 80
- SPRINT_12_R23_ACTIVATION_SUMMARY.md
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class CasperResult(BaseModel):
    """Temporary stub - legacy analytics/casper_v14 module.
    
    Replaced by CapitalRiskBundle in Pydantic v2 architecture.
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    
    scenario_name: str = ""
    iterations: int = 0
    results: Dict[str, Any] = {}


class TailRiskMetrics(BaseModel):
    """Temporary stub - legacy sensitivity_tail_risk module.
    
    Replaced by MonteCarloResult.var_90/cvar_90 in v2.
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    
    var_90: float = 0.0
    cvar_90: float = 0.0
    worst_case_irr: float = 0.0


class Distribution(BaseModel):
    """Temporary stub - legacy monte_carlo_v14 module.
    
    Statistical distribution model for MC inputs.
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    
    dist_type: str = "normal"
    mean: float = 0.0
    std: float = 0.0


class DownsideMetrics(BaseModel):
    """Temporary stub - legacy equity_v14 module.
    
    Replaced by EquityPerformance.downside_return_pct.
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    
    downside_return_pct: float = 0.0
    p10_return: float = 0.0


def build_cashflow_result_from_annual_rows(
    annual_rows: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Temporary stub - legacy pipeline_v14 helper.
    
    Replaced by CashflowResult dataclass construction.
    """
    return {
        "annual_cashflows": [],
        "project_life_years": len(annual_rows),
        "construction_years": 0,
        "ncf_lcy": [],
        "pv_lcy": [],
    }


__all__ = [
    "CasperResult",
    "TailRiskMetrics",
    "Distribution",
    "DownsideMetrics",
    "build_cashflow_result_from_annual_rows",
]
