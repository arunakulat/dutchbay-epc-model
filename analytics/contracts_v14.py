"""V14 Contracts and Data Structures - WACC-Integrated + Sensitivity Analysis.

Central repository for all v14 dataclass contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from pydantic import BaseModel, Field, ConfigDict, field_validator


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


# =============================================================================
# Phase 3: Sensitivity Analysis (NEW - 2025-11-23)
# =============================================================================


class ParameterRangeConfig(BaseModel):
    """Sensitivity parameter range configuration.
    
    Validates parameter sweep configurations loaded from YAML files.
    Uses Pydantic v2 for robust input validation at config boundaries.
    
    Attributes:
        variable_name: Dot-separated parameter path (e.g., 'project.capex_usd_per_kw')
        base_value: Base case value for the parameter
        low_pct: Lower bound as percentage change (must be negative, -50 to 0)
        high_pct: Upper bound as percentage change (must be positive, 0 to 100)
        steps: Number of steps in sensitivity sweep (3 to 20)
    
    Example:
        >>> config = ParameterRangeConfig(
        ...     variable_name="project.capex_usd_per_kw",
        ...     base_value=850.0,
        ...     low_pct=-20.0,
        ...     high_pct=20.0,
        ...     steps=5
        ... )
        >>> config.low_value
        680.0
        >>> config.high_value
        1020.0
    """
    
    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=False,
    )
    
    variable_name: str = Field(
        ...,
        min_length=1,
        description="Parameter to sweep (dot-separated path)"
    )
    
    base_value: float = Field(
        ...,
        gt=0,
        description="Base case value (must be positive)"
    )
    
    low_pct: float = Field(
        ...,
        ge=-50.0,
        le=0.0,
        description="Lower bound as percentage change (e.g., -20 for -20%)"
    )
    
    high_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Upper bound as percentage change (e.g., +20 for +20%)"
    )
    
    steps: int = Field(
        default=5,
        ge=3,
        le=20,
        description="Number of steps in sensitivity sweep"
    )
    
    @field_validator('high_pct')
    @classmethod
    def validate_high_exceeds_low(cls, v: float, info: Any) -> float:
        """Ensure high_pct is at least as large as abs(low_pct).
        
        This ensures the sensitivity range is meaningful (not inverted).
        Allows symmetric ranges like (-20%, +20%).
        
        Args:
            v: high_pct value
            info: Validation context with other field values
        
        Returns:
            Validated high_pct value
        
        Raises:
            ValueError: If high_pct < abs(low_pct)
        """
        low_pct = info.data.get('low_pct')
        if low_pct is not None:
            if v < abs(low_pct):  # Changed from <= to <
                raise ValueError(
                    f"High bound ({v}%) must be at least {abs(low_pct)}% (abs of low bound {low_pct}%)"
                )
        return v
    
    @property
    def low_value(self) -> float:
        """Calculate absolute low value.
        
        Returns:
            Base value adjusted by low_pct
        
        Example:
            >>> config = ParameterRangeConfig(
            ...     variable_name="test",
            ...     base_value=100.0,
            ...     low_pct=-20.0,
            ...     high_pct=20.0
            ... )
            >>> config.low_value
            80.0
        """
        return self.base_value * (1 + self.low_pct / 100.0)
    
    @property
    def high_value(self) -> float:
        """Calculate absolute high value.
        
        Returns:
            Base value adjusted by high_pct
        
        Example:
            >>> config = ParameterRangeConfig(
            ...     variable_name="test",
            ...     base_value=100.0,
            ...     low_pct=-20.0,
            ...     high_pct=20.0
            ... )
            >>> config.high_value
            120.0
        """
        return self.base_value * (1 + self.high_pct / 100.0)


@dataclass
class TornadoResult:
    """Single variable tornado chart result.
    
    Stores sensitivity analysis results for one parameter.
    Uses dataclass for performance (no validation overhead on internal results).
    
    Attributes:
        variable: Parameter name that was swept
        base_irr: IRR at base case
        low_irr: IRR at low parameter value
        high_irr: IRR at high parameter value
    
    Example:
        >>> result = TornadoResult(
        ...     variable="capex_usd_per_kw",
        ...     base_irr=0.12,
        ...     low_irr=0.10,
        ...     high_irr=0.14
        ... )
        >>> result.impact_pct
        40.0
        >>> result.impact_abs
        0.04
    """
    
    variable: str
    base_irr: float
    low_irr: float
    high_irr: float
    
    @property
    def impact_pct(self) -> float:
        """Calculate impact as percentage change from base.
        
        Formula: (high_irr - low_irr) / base_irr * 100
        
        Returns:
            Percentage impact (e.g., 40.0 for 40% impact)
            Returns 0.0 if base_irr is zero (avoids division by zero)
        
        Example:
            >>> result = TornadoResult("test", 0.10, 0.08, 0.12)
            >>> result.impact_pct
            40.0
        """
        if self.base_irr == 0.0:
            return 0.0
        
        return ((self.high_irr - self.low_irr) / self.base_irr) * 100.0
    
    @property
    def impact_abs(self) -> float:
        """Calculate absolute IRR swing.
        
        Formula: abs(high_irr - low_irr)
        
        Returns:
            Absolute impact (e.g., 0.04 for 4 percentage points)
        
        Example:
            >>> result = TornadoResult("test", 0.10, 0.08, 0.12)
            >>> result.impact_abs
            0.04
        """
        return abs(self.high_irr - self.low_irr)


@dataclass
class SensitivitySuite:
    """Complete sensitivity analysis results.
    
    Aggregates tornado analysis results for multiple parameters,
    ranks them by impact, and identifies top risk drivers for Monte Carlo.
    
    Attributes:
        tornado_results: List of individual parameter sensitivity results
        base_case_irr: IRR at base case scenario
        base_case_npv: NPV at base case scenario
        sensitivity_rank: Sorted list of (variable, impact) tuples
    
    Example:
        >>> suite = SensitivitySuite(
        ...     tornado_results=[result1, result2],
        ...     base_case_irr=0.12,
        ...     base_case_npv=15000000,
        ...     sensitivity_rank=[("capex", 0.05), ("tariff", 0.08)]
        ... )
        >>> suite.top_risk_drivers(3)
        ['tariff', 'capex']
    """
    
    tornado_results: List[TornadoResult]
    base_case_irr: float
    base_case_npv: float
    sensitivity_rank: List[tuple[str, float]] = field(default_factory=list)
    
    def top_risk_drivers(self, n: int = 5) -> List[str]:
        """Get top N risk drivers for Monte Carlo simulation.
        
        Args:
            n: Number of top variables to return (default: 5)
        
        Returns:
            List of variable names sorted by impact (highest first)
        
        Example:
            >>> suite.top_risk_drivers(3)
            ['tariff_lkr_per_kwh', 'capex_usd_per_kw', 'capacity_factor_pct']
        """
        return [var for var, _ in self.sensitivity_rank[:n]]


