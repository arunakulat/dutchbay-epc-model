"""Refinancing Module V14.

Provides refinancing functionality for debt restructuring with:
- Trigger condition evaluation (year, DSCR, rate, NPV)
- Debt schedule recalculation
- Covenant impact analysis
- Interest savings quantification
"""

from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator, ConfigDict
import numpy as np
from enum import Enum


class RefinancingTriggerReason(str, Enum):
    """Enumeration of refinancing trigger reasons."""

    YEAR_THRESHOLD = "year_threshold"
    DSCR_STRENGTH = "dscr_strength"
    RATE_SAVINGS = "rate_savings"
    NPV_POSITIVE = "npv_positive"
    MANUAL_OVERRIDE = "manual_override"


class RefinancingConfig(BaseModel):
    """Pydantic v2 configuration for refinancing parameters.

    Controls trigger thresholds, refinancing terms, and covenant adjustments.
    All parameters are externalized and configurable.

    Attributes:
        enabled: Whether refinancing module is active
        trigger_year: Minimum year for refinancing eligibility (typically 8)
        min_dscr_for_trigger: Minimum DSCR to trigger refinancing (typically 1.25)
        rate_savings_threshold: Minimum rate reduction in basis points (typically 50)
        npv_positive_threshold: Minimum NPV benefit for refinancing (in millions)
        new_interest_rate: Refinanced interest rate (e.g., 0.05 for 5%)
        new_tenor: New debt tenor in years post-refinancing
        upfront_cost_pct: Upfront refinancing costs as % of new debt (typically 0.02)
        recalculate_covenants: Whether to recalculate covenants post-refinancing
    """

    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable refinancing module")
    trigger_year: int = Field(default=8, ge=1, le=30, description="Minimum year for refinancing")
    min_dscr_for_trigger: float = Field(
        default=1.25, ge=1.0, le=3.0, description="Minimum DSCR for trigger"
    )
    rate_savings_threshold: float = Field(
        default=50.0, ge=0, le=500, description="Rate savings threshold in bps"
    )
    npv_positive_threshold: float = Field(
        default=0.0, ge=-100, le=100, description="NPV threshold in millions"
    )
    new_interest_rate: float = Field(
        default=0.05, ge=0.01, le=0.15, description="New interest rate post-refinancing"
    )
    new_tenor: int = Field(default=15, ge=5, le=30, description="New tenor in years")
    upfront_cost_pct: float = Field(
        default=0.02, ge=0.0, le=0.10, description="Upfront costs as % of new debt"
    )
    recalculate_covenants: bool = Field(
        default=True, description="Recalculate covenants post-refinancing"
    )

    @field_validator("trigger_year")
    @classmethod
    def validate_trigger_year(cls, v: int) -> int:
        """Validate trigger year is reasonable."""
        if v < 1:
            raise ValueError("trigger_year must be >= 1")
        return v

    @field_validator("new_tenor")
    @classmethod
    def validate_new_tenor(cls, v: int) -> int:
        """Validate new tenor is reasonable."""
        if v < 5:
            raise ValueError("new_tenor must be >= 5 years")
        return v


class RefinancingTrigger:
    """Evaluates refinancing trigger conditions.

    Checks 4 independent conditions:
    1. Year >= trigger_year (minimum debt age)
    2. DSCR > min_dscr_for_trigger (refinancing strength)
    3. New rate < current rate - threshold (savings justification)
    4. NPV positive (financial benefit)

    All 4 conditions must be met for refinancing to trigger.
    """

    def __init__(self, config: RefinancingConfig) -> None:
        """Initialize trigger with configuration.

        Args:
            config: RefinancingConfig instance
        """
        self.config = config

    def evaluate(
        self,
        current_year: int,
        current_dscr: float,
        current_interest_rate: float,
        npv_benefit: float,
    ) -> Tuple[bool, List[str], Dict[str, bool]]:
        """Evaluate all trigger conditions.

        Args:
            current_year: Current year in simulation (1-indexed)
            current_dscr: Current debt service coverage ratio
            current_interest_rate: Current interest rate (0-1 format, e.g., 0.07)
            npv_benefit: Net present value benefit of refinancing (in millions)

        Returns:
            Tuple of:
            - trigger: True if all conditions met
            - reasons: List of trigger reasons (empty if no trigger)
            - conditions: Dict showing each condition status
        """
        conditions = {}
        reasons: List[str] = []

        # Condition 1: Year threshold
        year_ok = current_year >= self.config.trigger_year
        conditions["year_threshold"] = year_ok
        if year_ok:
            reasons.append(RefinancingTriggerReason.YEAR_THRESHOLD.value)

        # Condition 2: DSCR strength
        dscr_ok = current_dscr > self.config.min_dscr_for_trigger
        conditions["dscr_strength"] = dscr_ok
        if dscr_ok:
            reasons.append(RefinancingTriggerReason.DSCR_STRENGTH.value)

        # Condition 3: Rate savings (threshold in basis points)
        rate_savings_bps = (current_interest_rate - self.config.new_interest_rate) * 10000
        rate_ok = rate_savings_bps >= self.config.rate_savings_threshold
        conditions["rate_savings"] = rate_ok
        if rate_ok:
            reasons.append(RefinancingTriggerReason.RATE_SAVINGS.value)

        # Condition 4: NPV positive
        npv_ok = npv_benefit >= self.config.npv_positive_threshold
        conditions["npv_positive"] = npv_ok
        if npv_ok:
            reasons.append(RefinancingTriggerReason.NPV_POSITIVE.value)

        # All conditions must be met
        trigger = year_ok and dscr_ok and rate_ok and npv_ok
        reasons = reasons if trigger else []

        return trigger, reasons, conditions


@dataclass
class DebtTerm:
    """Represents a debt term line item."""

    original_amount: float
    current_balance: float
    interest_rate: float
    tenor_years: int
    year_issued: int


class RefinancingCalculator:
    """Calculates refinancing impacts on debt schedule.

    Handles:
    - Debt consolidation
    - Schedule recalculation
    - Interest savings quantification
    - Covenant recalculation
    """

    def __init__(self, config: RefinancingConfig) -> None:
        """Initialize calculator with configuration.

        Args:
            config: RefinancingConfig instance
        """
        self.config = config

    def calculate_debt_service_payment(
        self, principal: float, rate: float, years: int
    ) -> float:
        """Calculate annual debt service payment (annuity).

        Uses standard annuity formula: P * (r(1+r)^n) / ((1+r)^n - 1)

        Args:
            principal: Principal amount
            rate: Annual interest rate (0-1 format)
            years: Number of years

        Returns:
            Annual debt service payment
        """
        if years <= 0 or rate < 0:
            return 0.0
        if rate == 0:
            return principal / years if years > 0 else 0.0

        factor = (1 + rate) ** years
        payment = principal * (rate * factor) / (factor - 1)
        return max(0.0, payment)

    def recalculate_schedule(
        self,
        current_balance: float,
        current_year: int,
        remaining_years: int,
        debt_terms: Optional[List[DebtTerm]] = None,
    ) -> Dict[str, float]:
        """Recalculate debt schedule post-refinancing.

        Args:
            current_balance: Total current debt balance
            current_year: Current year in simulation
            remaining_years: Years remaining in project life
            debt_terms: Optional list of existing debt terms

        Returns:
            Dict with recalculated schedule metrics:
            - new_annual_payment: Annual debt service post-refinancing
            - new_tenor_effective: Effective tenor used
            - old_annual_estimate: Estimated prior annual payment
            - total_interest_paid_old: Estimated old total interest
            - total_interest_paid_new: Estimated new total interest
            - interest_savings: Total interest savings (millions)
            - upfront_costs: Refinancing upfront costs (millions)
            - net_benefit: Net benefit after costs (millions)
        """
        # Calculate new annual payment
        effective_tenor = min(self.config.new_tenor, remaining_years)
        new_payment = self.calculate_debt_service_payment(
            current_balance, self.config.new_interest_rate, effective_tenor
        )

        # Estimate old schedule (simplified: assume same rate for comparison)
        # In production, would use actual debt terms
        old_rate_estimate = self.config.new_interest_rate + 0.01  # Assume 100bps higher
        old_payment = self.calculate_debt_service_payment(
            current_balance, old_rate_estimate, remaining_years
        )

        # Calculate interest savings
        years_in_calc = min(effective_tenor, remaining_years)
        old_total_interest = (old_payment * years_in_calc) - current_balance
        new_total_interest = (new_payment * years_in_calc) - current_balance
        interest_savings = old_total_interest - new_total_interest

        # Calculate upfront costs
        upfront_costs = current_balance * self.config.upfront_cost_pct

        # Net benefit
        net_benefit = interest_savings - upfront_costs

        return {
            "new_annual_payment": max(0.0, new_payment),
            "new_tenor_effective": effective_tenor,
            "old_annual_estimate": max(0.0, old_payment),
            "total_interest_paid_old": max(0.0, old_total_interest),
            "total_interest_paid_new": max(0.0, new_total_interest),
            "interest_savings": max(0.0, interest_savings),
            "upfront_costs": max(0.0, upfront_costs),
            "net_benefit": net_benefit,
        }

    def recalculate_covenants(
        self,
        new_annual_debt_service: float,
        annual_cashflow: float,
        ebitda: float,
        total_debt: float,
        existing_covenants: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Recalculate key covenant ratios post-refinancing.

        Args:
            new_annual_debt_service: New annual debt service post-refinancing
            annual_cashflow: Annual available cashflow
            ebitda: Earnings before interest, taxes, depreciation, amortization
            total_debt: Total debt balance post-refinancing
            existing_covenants: Optional dict of covenant names/thresholds

        Returns:
            Dict with recalculated covenant ratios:
            - dscr: Debt Service Coverage Ratio
            - llcr: Loan Life Coverage Ratio
            - plcr: Project Life Coverage Ratio
        """
        # Calculate DSCR
        dscr = (
            annual_cashflow / new_annual_debt_service
            if new_annual_debt_service > 0
            else 0.0
        )

        # Calculate LLCR (simplified: total cashflow to total debt)
        llcr = ebitda / total_debt if total_debt > 0 else 0.0

        # Calculate PLCR (simplified: same as LLCR for this context)
        plcr = llcr

        return {
            "dscr": max(0.0, dscr),
            "llcr": max(0.0, llcr),
            "plcr": max(0.0, plcr),
        }


@dataclass
class RefinancingOutput:
    """Structured output from refinancing calculation.

    Attributes:
        refinancing_triggered: Whether refinancing occurred
        trigger_reasons: List of reasons refinancing was triggered
        trigger_conditions: Dict showing each condition status
        current_year: Year when refinancing was triggered
        new_annual_payment: New annual debt service post-refinancing
        new_tenor_years: New tenor after refinancing
        total_interest_savings: Total interest savings (millions)
        upfront_costs: Refinancing upfront costs (millions)
        net_benefit: Net benefit after costs (millions)
        new_covenants: Dict of recalculated covenant ratios
        schedule_metrics: Dict with full schedule recalculation results
        timestamp: When calculation was performed
    """

    refinancing_triggered: bool
    trigger_reasons: List[str]
    trigger_conditions: Dict[str, bool]
    current_year: int
    new_annual_payment: float
    new_tenor_years: int
    total_interest_savings: float
    upfront_costs: float
    net_benefit: float
    new_covenants: Dict[str, float]
    schedule_metrics: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "refinancing_triggered": self.refinancing_triggered,
            "trigger_reasons": self.trigger_reasons,
            "trigger_conditions": self.trigger_conditions,
            "current_year": self.current_year,
            "new_annual_payment": float(self.new_annual_payment),
            "new_tenor_years": self.new_tenor_years,
            "total_interest_savings": float(self.total_interest_savings),
            "upfront_costs": float(self.upfront_costs),
            "net_benefit": float(self.net_benefit),
            "new_covenants": self.new_covenants,
            "schedule_metrics": self.schedule_metrics,
            "timestamp": self.timestamp.isoformat(),
        }


def calculate_refinancing(
    config: RefinancingConfig,
    current_year: int,
    current_dscr: float,
    current_interest_rate: float,
    current_debt_balance: float,
    remaining_years: int,
    annual_cashflow: float,
    ebitda: float,
) -> RefinancingOutput:
    """Main entry point for refinancing calculation.

    Orchestrates trigger evaluation and schedule recalculation.

    Args:
        config: RefinancingConfig instance
        current_year: Current year in simulation
        current_dscr: Current debt service coverage ratio
        current_interest_rate: Current interest rate
        current_debt_balance: Current debt balance
        remaining_years: Years remaining in project
        annual_cashflow: Annual available cashflow
        ebitda: Annual EBITDA

    Returns:
        RefinancingOutput with complete results
    """
    # Create trigger and calculator
    trigger = RefinancingTrigger(config)
    calculator = RefinancingCalculator(config)

    # Estimate NPV benefit (simplified calculation)
    npv_benefit = calculator.calculate_debt_service_payment(
        current_debt_balance, config.new_interest_rate, config.new_tenor
    ) * 0.1  # Simplified placeholder

    # Evaluate trigger conditions
    triggered, reasons, conditions = trigger.evaluate(
        current_year,
        current_dscr,
        current_interest_rate,
        npv_benefit,
    )

    # If triggered, recalculate schedule and covenants
    if triggered:
        schedule_metrics = calculator.recalculate_schedule(
            current_debt_balance,
            current_year,
            remaining_years,
        )
        new_covenants = calculator.recalculate_covenants(
            schedule_metrics["new_annual_payment"],
            annual_cashflow,
            ebitda,
            current_debt_balance,
        )
    else:
        schedule_metrics = {
            "new_annual_payment": 0.0,
            "new_tenor_effective": 0,
            "old_annual_estimate": 0.0,
            "total_interest_paid_old": 0.0,
            "total_interest_paid_new": 0.0,
            "interest_savings": 0.0,
            "upfront_costs": 0.0,
            "net_benefit": 0.0,
        }
        new_covenants = {"dscr": current_dscr, "llcr": 0.0, "plcr": 0.0}

    return RefinancingOutput(
        refinancing_triggered=triggered,
        trigger_reasons=reasons,
        trigger_conditions=conditions,
        current_year=current_year,
        new_annual_payment=schedule_metrics["new_annual_payment"],
        new_tenor_years=schedule_metrics["new_tenor_effective"],
        total_interest_savings=schedule_metrics["interest_savings"],
        upfront_costs=schedule_metrics["upfront_costs"],
        net_benefit=schedule_metrics["net_benefit"],
        new_covenants=new_covenants,
        schedule_metrics=schedule_metrics,
    )
