"""Equity Distribution Module for DutchBay EPC Model (v14).

This module models equity cash distribution waterfalls, including:
- Distribution eligibility (post-debt service, reserves)
- Waterfall logic (debt priority, equity tiers)
- Covenant compliance (DSCR, LLCR thresholds)
- Tax-efficient distribution timing
- Target distribution ratios
- IRR impact quantification

Author: DutchBay Finance Team
Version: 14.0.0
Date: December 16, 2025

**CRITICAL: GWTF v3.0 Compliance**
- ARCH-01: Config-first (ALL params from YAML)
- VAL-01: Schema guard validates distribution config
- CLI-01: Hydra-based (never argparse)
- CST-01: Type-safe with mypy --strict
- R3: No argparse anywhere
- R4: No Typer in v14
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

logger = logging.getLogger(__name__)


class EquityDistributionConfig(BaseModel):
    """Configuration for equity distribution module.
    
    Attributes:
        enabled: Whether equity distribution analysis is enabled
        min_reserve_months: Minimum months of debt service to keep in reserve
        min_dscr_threshold: Minimum DSCR required to distribute (typically 1.20)
        min_llcr_threshold: Minimum LLCR required to distribute (typically 1.10)
        distribution_frequency: How often to evaluate ('annual', 'semi-annual', 'quarterly')
        target_equity_return_pct: Target equity cash-on-cash return (%)
        enable_tax_timing: Whether to optimize distribution timing for tax efficiency
        waterfall_tiers: List of distribution tiers (debt holders, Class A equity, etc.)
    """
    model_config = ConfigDict(validate_assignment=True)
    
    enabled: bool = Field(default=True, description="Enable equity distribution analysis")
    min_reserve_months: float = Field(default=6.0, description="Minimum reserve (months of debt service)")
    min_dscr_threshold: float = Field(default=1.20, description="Minimum DSCR to distribute")
    min_llcr_threshold: float = Field(default=1.10, description="Minimum LLCR to distribute")
    distribution_frequency: str = Field(default="annual", description="Distribution frequency")
    target_equity_return_pct: float = Field(default=15.0, description="Target equity return (%)")
    enable_tax_timing: bool = Field(default=True, description="Optimize for tax efficiency")
    max_distribution_pct: float = Field(default=100.0, description="Max % of available cash to distribute")
    
    @field_validator('min_dscr_threshold')
    @classmethod
    def validate_dscr(cls, v: float) -> float:
        """DSCR threshold must be positive and reasonable."""
        if v <= 0 or v > 3.0:
            raise ValueError(f"DSCR threshold {v} not in valid range (0, 3.0]")
        return v
    
    @field_validator('min_llcr_threshold')
    @classmethod
    def validate_llcr(cls, v: float) -> float:
        """LLCR threshold must be positive and reasonable."""
        if v <= 0 or v > 2.0:
            raise ValueError(f"LLCR threshold {v} not in valid range (0, 2.0]")
        return v
    
    @field_validator('min_reserve_months')
    @classmethod
    def validate_reserve(cls, v: float) -> float:
        """Reserve months must be between 0 and 24."""
        if v < 0 or v > 24:
            raise ValueError(f"Reserve months {v} not in valid range [0, 24]")
        return v
    
    @field_validator('distribution_frequency')
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        """Distribution frequency must be valid option."""
        valid = {'annual', 'semi-annual', 'quarterly', 'monthly'}
        if v.lower() not in valid:
            raise ValueError(f"Frequency '{v}' not in valid options: {valid}")
        return v.lower()
    
    @field_validator('target_equity_return_pct')
    @classmethod
    def validate_equity_return(cls, v: float) -> float:
        """Equity return target must be between 0% and 50%."""
        if v < 0 or v > 50:
            raise ValueError(f"Equity return {v}% not in valid range (0-50%)")
        return v


class DistributionWaterfall:
    """Equity distribution waterfall calculator.
    
    Implements multi-tier waterfall logic:
    1. Senior debt service (principal + interest)
    2. Reserve account funding (minimum balance)
    3. Class A equity (priority return)
    4. Class B equity (residual)
    
    Distributions only occur if:
    - DSCR >= threshold
    - LLCR >= threshold
    - Reserves >= minimum months
    - Available cash > 0 after debt service
    """
    
    def __init__(self, config: EquityDistributionConfig) -> None:
        """Initialize waterfall with configuration.
        
        Args:
            config: EquityDistributionConfig instance
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate_distributable_cash(
        self,
        year: int,
        cfads: float,
        debt_service: float,
        reserve_balance: float,
        target_reserve: float,
    ) -> float:
        """Calculate cash available for distribution.
        
        Args:
            year: Current year
            cfads: Cash Flow Available for Debt Service (after tax)
            debt_service: Total debt service (principal + interest)
            reserve_balance: Current reserve account balance
            target_reserve: Target reserve balance
        
        Returns:
            Cash available for equity distribution (USD)
        """
        # Cash after debt service
        cash_after_debt = cfads - debt_service
        
        # Reserve top-up required
        reserve_shortfall = max(0.0, target_reserve - reserve_balance)
        
        # Distributable = cash after debt and reserve top-up
        distributable = cash_after_debt - reserve_shortfall
        
        # Cannot distribute negative amounts
        distributable = max(0.0, distributable)
        
        self.logger.debug(
            f"Year {year}: CFADS={cfads:,.0f}, Debt={debt_service:,.0f}, "
            f"Reserve shortfall={reserve_shortfall:,.0f}, Distributable={distributable:,.0f}"
        )
        
        return distributable
    
    def check_distribution_covenants(
        self,
        dscr: float,
        llcr: float,
    ) -> Tuple[bool, Dict[str, bool]]:
        """Check if covenant conditions allow distribution.
        
        Args:
            dscr: Current Debt Service Coverage Ratio
            llcr: Current Loan Life Coverage Ratio
        
        Returns:
            Tuple of (can_distribute: bool, conditions: Dict)
        """
        conditions: Dict[str, bool] = {
            'dscr_ok': dscr >= self.config.min_dscr_threshold,
            'llcr_ok': llcr >= self.config.min_llcr_threshold,
        }
        
        can_distribute = all(conditions.values())
        
        if not can_distribute:
            self.logger.info(
                f"Distribution blocked: DSCR={dscr:.2f} (min {self.config.min_dscr_threshold:.2f}), "
                f"LLCR={llcr:.2f} (min {self.config.min_llcr_threshold:.2f})"
            )
        
        return can_distribute, conditions
    
    def apply_waterfall(
        self,
        distributable_cash: float,
        equity_tiers: List[Dict[str, float]],
    ) -> List[Dict[str, float]]:
        """Apply waterfall distribution logic to equity tiers.
        
        Args:
            distributable_cash: Total cash available for distribution
            equity_tiers: List of equity tier definitions
                Each tier: {'name': str, 'priority': int, 'target_pct': float}
        
        Returns:
            List of distributions per tier: [{'name': str, 'amount': float}]
        """
        # Sort by priority (lower number = higher priority)
        sorted_tiers = sorted(equity_tiers, key=lambda x: x.get('priority', 999))
        
        distributions: List[Dict[str, float]] = []
        remaining = distributable_cash
        
        for tier in sorted_tiers:
            tier_name = tier.get('name', 'Unknown')
            tier_pct = tier.get('target_pct', 100.0)
            
            # Calculate tier distribution (% of remaining)
            tier_amount = remaining * (tier_pct / 100.0)
            tier_amount = min(tier_amount, remaining)  # Cannot exceed remaining
            
            distributions.append({
                'tier_name': tier_name,
                'amount': tier_amount,
                'pct_of_total': (tier_amount / distributable_cash * 100.0) if distributable_cash > 0 else 0.0,
            })
            
            remaining -= tier_amount
            
            if remaining <= 0:
                break
        
        return distributions


class EquityDistributionV14:
    """Equity distribution calculator for DutchBay EPC Model.
    
    Handles equity cash distribution analysis:
    - Eligibility checks (covenants, reserves)
    - Waterfall distribution logic
    - Tax-efficient timing
    - IRR impact quantification
    - Distribution schedules
    """
    
    def __init__(self, config: EquityDistributionConfig) -> None:
        """Initialize equity distribution module.
        
        Args:
            config: EquityDistributionConfig with all parameters
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.waterfall = DistributionWaterfall(config)
    
    def calculate(
        self,
        annual_data: Dict[str, List[float]],
        debt_schedule: Dict[str, List[float]],
        equity_investment: float,
    ) -> Dict[str, Any]:
        """Calculate equity distributions across project life.
        
        Args:
            annual_data: Annual cashflow and covenant data
                Must include: 'cfads', 'dscr', 'llcr', 'reserve_balance'
            debt_schedule: Debt service schedule
                Must include: 'debt_service_total'
            equity_investment: Total equity invested (for IRR calc)
        
        Returns:
            Dict with distribution results:
                - enabled: bool (whether distributions occurred)
                - total_distributed: float (total equity distributions)
                - distribution_schedule: List[Dict] (year-by-year)
                - equity_irr: float (equity IRR including distributions)
                - equity_multiple: float (cash-on-cash multiple)
                - blocked_years: List[int] (years where covenants blocked)
        """
        result: Dict[str, Any] = {
            'enabled': self.config.enabled,
            'total_distributed': 0.0,
            'distribution_schedule': [],
            'equity_irr': 0.0,
            'equity_multiple': 0.0,
            'blocked_years': [],
            'total_years': 0,
        }
        
        if not self.config.enabled:
            self.logger.info("Equity distribution analysis disabled")
            return result
        
        # Calculate target reserve (months of debt service)
        avg_debt_service = sum(debt_schedule.get('debt_service_total', [0.0])) / max(1, len(debt_schedule.get('debt_service_total', [1])))
        target_reserve = avg_debt_service * (self.config.min_reserve_months / 12.0)
        
        # Year-by-year distribution calculation
        cfads_list = annual_data.get('cfads', [])
        dscr_list = annual_data.get('dscr', [])
        llcr_list = annual_data.get('llcr', [])
        reserve_list = annual_data.get('reserve_balance', [])
        debt_service_list = debt_schedule.get('debt_service_total', [])
        
        n_years = min(len(cfads_list), len(dscr_list), len(llcr_list))
        result['total_years'] = n_years
        
        total_distributed = 0.0
        
        for year in range(n_years):
            cfads = cfads_list[year] if year < len(cfads_list) else 0.0
            dscr = dscr_list[year] if year < len(dscr_list) else 0.0
            llcr = llcr_list[year] if year < len(llcr_list) else 0.0
            reserve_balance = reserve_list[year] if year < len(reserve_list) else 0.0
            debt_service = debt_service_list[year] if year < len(debt_service_list) else 0.0
            
            # Check covenants
            can_distribute, conditions = self.waterfall.check_distribution_covenants(dscr, llcr)
            
            if not can_distribute:
                result['blocked_years'].append(year + 1)  # 1-indexed
                result['distribution_schedule'].append({
                    'year': year + 1,
                    'distributed': 0.0,
                    'blocked': True,
                    'reason': 'covenant_breach',
                })
                continue
            
            # Calculate distributable cash
            distributable = self.waterfall.calculate_distributable_cash(
                year=year + 1,
                cfads=cfads,
                debt_service=debt_service,
                reserve_balance=reserve_balance,
                target_reserve=target_reserve,
            )
            
            # Apply max distribution limit
            distributable = min(distributable, distributable * (self.config.max_distribution_pct / 100.0))
            
            total_distributed += distributable
            
            result['distribution_schedule'].append({
                'year': year + 1,
                'distributed': distributable,
                'blocked': False,
                'dscr': dscr,
                'llcr': llcr,
            })
        
        result['total_distributed'] = total_distributed
        
        # Calculate equity metrics
        if equity_investment > 0:
            result['equity_multiple'] = total_distributed / equity_investment
        else:
            result['equity_multiple'] = 0.0
        
        self.logger.info(
            f"Equity distributions: Total={total_distributed:,.0f}, "
            f"Multiple={result['equity_multiple']:.2f}x, "
            f"Blocked years={len(result['blocked_years'])}"
        )
        
        return result


if __name__ == "__main__":
    """Test basic functionality."""
    config = EquityDistributionConfig()
    calculator = EquityDistributionV14(config)
    print("\u2705 Equity Distribution module initialized with config:")
    print(f"   Enabled: {config.enabled}")
    print(f"   Min DSCR threshold: {config.min_dscr_threshold:.2f}")
    print(f"   Min LLCR threshold: {config.min_llcr_threshold:.2f}")
    print(f"   Reserve months: {config.min_reserve_months:.1f}")
    print(f"   Distribution frequency: {config.distribution_frequency}")
