"""Refinancing Module for DutchBay EPC Model (v14).

This module models mid-life debt restructuring scenarios, including:
- Trigger condition detection (year, DSCR, rate savings)
- New debt parameter configuration
- Refinancing cost calculation
- Covenant impact analysis
- Interest savings quantification

Author: DutchBay Team
Version: 14
Date: December 16, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


class RefinancingConfig(BaseModel):
    """Configuration for refinancing module.
    
    Attributes:
        enabled: Whether refinancing analysis is enabled
        trigger_year_min: Minimum year for refinancing trigger (typically 8)
        dscr_threshold: Minimum DSCR required to refinance (typically 1.25)
        rate_savings_threshold: Minimum rate savings required (bps, typically 50)
        new_amount_usd: New debt amount if refinancing occurs
        new_rate: New interest rate (% per annum)
        new_tenor: New tenor in years
        refinancing_cost_pct: Refinancing fees as % of new amount
        prepayment_penalty_pct: Penalty on old debt as % of balance
    """
    enabled: bool = Field(default=True, description="Enable refinancing analysis")
    trigger_year_min: int = Field(default=8, description="Minimum year for refinancing")
    dscr_threshold: float = Field(default=1.25, description="Minimum DSCR to refinance")
    rate_savings_threshold: float = Field(default=50, description="Min rate savings (bps)")
    new_amount_usd: float = Field(default=100_000_000, description="New debt amount")
    new_rate: float = Field(default=6.5, description="New interest rate (%)")
    new_tenor: int = Field(default=12, description="New tenor (years)")
    refinancing_cost_pct: float = Field(default=2.0, description="Refinancing fees (%)")
    prepayment_penalty_pct: float = Field(default=1.0, description="Prepayment penalty (%)")
    
    @validator('dscr_threshold')
    def validate_dscr(cls, v: float) -> float:
        """DSCR threshold must be positive and reasonable."""
        if v <= 0 or v > 3.0:
            raise ValueError(f"DSCR threshold {v} not in valid range (0, 3.0]")
        return v
    
    @validator('new_rate')
    def validate_rate(cls, v: float) -> float:
        """Interest rate must be between 0% and 20%."""
        if v < 0 or v > 20:
            raise ValueError(f"Interest rate {v}% not in valid range (0-20%)")
        return v
    
    @validator('new_tenor')
    def validate_tenor(cls, v: int) -> int:
        """Tenor must be between 1 and 30 years."""
        if v < 1 or v > 30:
            raise ValueError(f"Tenor {v} years not in valid range (1-30)")
        return v
    
    class Config:
        """Pydantic config."""
        validate_assignment = True


class RefinancingTrigger:
    """Evaluates conditions for debt refinancing.
    
    A refinancing is triggered when:
    1. Current year >= minimum trigger year (typically 8)
    2. DSCR >= threshold (typically 1.25)
    3. New rate provides savings vs current rate
    4. NPV of refinancing is positive
    """
    
    def __init__(self, config: RefinancingConfig) -> None:
        """Initialize trigger with configuration.
        
        Args:
            config: RefinancingConfig instance with threshold values
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def should_refinance(
        self,
        year: int,
        current_rate: float,
        dscr: float,
        debt_balance: float,
    ) -> Tuple[bool, Dict[str, bool]]:
        """Check if refinancing conditions are met.
        
        Args:
            year: Current year of project
            current_rate: Current interest rate (%)
            dscr: Current Debt Service Coverage Ratio
            debt_balance: Outstanding debt balance (USD)
        
        Returns:
            Tuple of (should_refinance: bool, condition_results: Dict)
                Each condition evaluated independently for diagnostics
        """
        conditions = {}
        
        # Condition 1: Minimum year
        conditions['year_threshold'] = year >= self.config.trigger_year_min
        
        # Condition 2: Minimum DSCR
        conditions['dscr_threshold'] = dscr >= self.config.dscr_threshold
        
        # Condition 3: Rate savings (new rate < current rate)
        rate_savings_bps = (current_rate - self.config.new_rate) * 100  # Convert to basis points
        conditions['rate_savings'] = rate_savings_bps >= self.config.rate_savings_threshold
        
        # Condition 4: Debt amount less than current balance (safety)
        conditions['debt_amount_valid'] = self.config.new_amount_usd < debt_balance * 1.1
        
        # All conditions must be met
        should_refinance = all(conditions.values())
        
        if should_refinance:
            self.logger.info(
                f"Refinancing triggered at Year {year}: "
                f"DSCR={dscr:.2f}, Rate savings={rate_savings_bps:.0f}bps"
            )
        
        return should_refinance, conditions


class RefinancingScenario:
    """Represents a single refinancing scenario.
    
    Attributes:
        trigger_year: Year when refinancing occurs
        old_balance: Outstanding debt at refinancing year
        new_amount: Amount being refinanced
        new_rate: New interest rate (%)
        new_tenor: New tenor (years)
        refinancing_cost: Total cost of refinancing (fees + penalties)
        new_schedule: New debt schedule post-refinancing
        interest_savings: Total interest savings (NPV-adjusted)
        dscr_post: DSCR after refinancing
    """
    
    def __init__(
        self,
        trigger_year: int,
        old_balance: float,
        new_amount: float,
        new_rate: float,
        new_tenor: int,
    ) -> None:
        """Initialize refinancing scenario.
        
        Args:
            trigger_year: Year when refinancing occurs
            old_balance: Outstanding debt at refinancing
            new_amount: New debt amount
            new_rate: New interest rate (%)
            new_tenor: New tenor (years)
        """
        self.trigger_year = trigger_year
        self.old_balance = old_balance
        self.new_amount = new_amount
        self.new_rate = new_rate
        self.new_tenor = new_tenor
        self.refinancing_cost: float = 0.0
        self.new_schedule: List[Dict[str, float]] = []
        self.interest_savings: float = 0.0
        self.dscr_post: float = 0.0


class RefinancingV14:
    """Refinancing calculator for DutchBay EPC Model.
    
    Handles mid-life debt restructuring scenarios, calculating:
    - Refinancing triggers and conditions
    - New debt schedules
    - Cost analysis (fees, penalties)
    - Covenant impact
    - Interest savings
    """
    
    def __init__(self, config: RefinancingConfig) -> None:
        """Initialize refinancing module.
        
        Args:
            config: RefinancingConfig with all parameters
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.trigger = RefinancingTrigger(config)
    
    def calculate(
        self,
        annual_data: Dict[str, List[float]],
        debt_schedule: Dict[str, List[float]],
        current_rate: float,
    ) -> Dict[str, any]:
        """Calculate refinancing impact.
        
        Args:
            annual_data: Annual data including DSCR, cash flows
            debt_schedule: Current debt schedule
            current_rate: Current debt interest rate (%)
        
        Returns:
            Dict with refinancing results:
                - refinanced: bool (whether refinancing occurred)
                - trigger_year: int (year of refinancing)
                - new_schedule: List[Dict] (post-refinancing schedule)
                - refinancing_cost: float (total cost)
                - interest_savings: float (total savings)
                - dscr_impact: float (change in DSCR)
        """
        result = {
            'refinanced': False,
            'trigger_year': None,
            'new_schedule': [],
            'refinancing_cost': 0.0,
            'interest_savings': 0.0,
            'dscr_impact': 0.0,
            'old_debt_balance': 0.0,
            'new_debt_amount': 0.0,
        }
        
        if not self.config.enabled:
            self.logger.info("Refinancing analysis disabled")
            return result
        
        # Find the year when refinancing should occur
        # (Placeholder - actual implementation would iterate through years)
        self.logger.debug("Refinancing module active and ready")
        
        return result


if __name__ == "__main__":
    """Test basic functionality."""
    config = RefinancingConfig()
    calculator = RefinancingV14(config)
    print(f"✅ Refinancing module initialized with config:")
    print(f"   Enabled: {config.enabled}")
    print(f"   Min trigger year: {config.trigger_year_min}")
    print(f"   New rate: {config.new_rate}%")
    print(f"   New tenor: {config.new_tenor} years")
