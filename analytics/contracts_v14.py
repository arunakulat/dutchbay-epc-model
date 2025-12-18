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
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
]

# EOF - analytics/contracts_v14.py (minimal subset for demonstration)
