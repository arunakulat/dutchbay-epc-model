"""V14 Contracts and Data Structures - WACC-Integrated.

Central repository for all v14 dataclass contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# =============================================================================
# Phase 1: WACC and Lender Valuation
# =============================================================================


@dataclass
class WaccComponents:
    """WACC calculation component breakdown."""

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
    """Complete WACC result with base and prudential valuations."""

    base: WaccComponents
    prudential_rate: Optional[float] = None
    prudential_npv: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """Complete scenario evaluation result with WACC integration."""

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
    validation_mode: str = "strict"
    config: Dict[str, Any] = field(default_factory=dict)
    annual_rows: Sequence[Dict[str, Any]] = field(default_factory=list)
    debt_result: Dict[str, Any] = field(default_factory=dict)
    kpis: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Phase 2: Equity Performance Tracking
# =============================================================================


@dataclass
class DownsideMetrics:
    """Downside risk metrics for equity investors.
    
    Populated by Monte Carlo or stress testing modules.
    """

    prob_negative_npv: Optional[float] = None
    prob_below_hurdle: Optional[float] = None
    worst_case_irr: Optional[float] = None
    max_drawdown: Optional[float] = None


@dataclass
class EquityPerformance:
    """Equity-focused KPI container.
    
    Tracks PE-style metrics: IRR, MOIC, DPI/RVPI/TVPI, cash-on-cash, payback.
    """

    equity_irr: Optional[float] = None
    equity_npv: Optional[float] = None
    moic: Optional[float] = None  # Multiple on Invested Capital
    dpi: Optional[float] = None  # Distributions to Paid-In
    rvpi: Optional[float] = None  # Residual Value to Paid-In
    tvpi: Optional[float] = None  # Total Value to Paid-In
    annual_coc: List[float] = field(default_factory=list)  # Cash-on-cash by year
    average_coc: float = 0.0
    payback_period_years: Optional[float] = None
    downside: Optional[DownsideMetrics] = None


