"""Refinancing Module V14 - Production Hardened.

Provides refinancing functionality for debt restructuring with:
- Trigger condition evaluation (year, DSCR, rate, NPV)
- Debt schedule recalculation with actuarial accuracy
- Covenant impact analysis
- Interest savings quantification

All calculation methodologies are industry-standard:
- Annuity formula for debt service
- Discounted cash flow (DCF) for NPV
- Standard covenant calculations (DSCR, LLCR)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class RefinancingTriggerReason(str, Enum):
    """Enumeration of refinancing trigger reasons."""

    YEAR_THRESHOLD = "year_threshold"
    DSCR_STRENGTH = "dscr_strength"
    RATE_SAVINGS = "rate_savings"
    NPV_POSITIVE = "npv_positive"
    MANUAL_OVERRIDE = "manual_override"


class RefinancingConfig(BaseModel):
    """Pydantic v2 configuration for refinancing parameters.

    All parameters are externalized and configurable. Controls trigger
    thresholds, refinancing terms, and covenant adjustments.

    Attributes:
        enabled: Whether refinancing module is active
        trigger_year: Minimum year for refinancing eligibility (1-30)
        min_dscr_for_trigger: Minimum DSCR to trigger refinancing (1.0-3.0)
        rate_savings_threshold: Minimum rate reduction in basis points (0-500)
        npv_positive_threshold: Minimum NPV benefit in millions (-100 to 100)
        new_interest_rate: Refinanced interest rate (0.01-0.15 or 1%-15%)
        new_tenor: New debt tenor in years post-refinancing (5-30)
        upfront_cost_pct: Upfront refinancing costs as % of new debt (0-10%)
        recalculate_covenants: Whether to recalculate covenants post-refinancing
        discount_rate_for_npv: Discount rate for NPV calculations (default 0.10)
    """

    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable refinancing module")
    trigger_year: int = Field(
        default=8, ge=1, le=30, description="Minimum year for refinancing"
    )
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
    discount_rate_for_npv: float = Field(
        default=0.10, ge=0.01, le=0.30, description="Discount rate for NPV calcs"
    )

    @field_validator("trigger_year")
    @classmethod
    def validate_trigger_year(cls, v: int) -> int:
        """Validate trigger year is reasonable (1-30)."""
        if v < 1:
            raise ValueError("trigger_year must be >= 1")
        if v > 30:
            raise ValueError("trigger_year must be <= 30")
        return v

    @field_validator("new_tenor")
    @classmethod
    def validate_new_tenor(cls, v: int) -> int:
        """Validate new tenor is reasonable (5-30 years)."""
        if v < 5:
            raise ValueError("new_tenor must be >= 5 years")
        if v > 30:
            raise ValueError("new_tenor must be <= 30 years")
        return v

    @field_validator("new_interest_rate")
    @classmethod
    def validate_interest_rate(cls, v: float) -> float:
        """Validate interest rate is reasonable (1%-15%)."""
        if v < 0.01:
            raise ValueError("new_interest_rate must be >= 0.01 (1%)")
        if v > 0.15:
            raise ValueError("new_interest_rate must be <= 0.15 (15%)")
        return v


class RefinancingTrigger:
    """Evaluates refinancing trigger conditions.

    All 4 conditions must be met for refinancing to trigger:
    1. Year >= trigger_year (minimum debt age)
    2. DSCR > min_dscr_for_trigger (refinancing strength)
    3. New rate < current rate - threshold (savings justification)
    4. NPV positive (financial benefit)

    Each condition is independently evaluated and reported.
    """

    def __init__(self, config: RefinancingConfig) -> None:
        """Initialize trigger with configuration.

        Args:
            config: RefinancingConfig instance
        """
        if not isinstance(config, RefinancingConfig):
            raise TypeError(
                f"config must be RefinancingConfig, got {type(config).__name__}"
            )
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
            current_dscr: Current debt service coverage ratio (must be > 0)
            current_interest_rate: Current interest rate (0-1 format, e.g., 0.07 for 7%)
            npv_benefit: Net present value benefit of refinancing (in millions)

        Returns:
            Tuple of:
            - trigger: True if all conditions met
            - reasons: List of trigger reasons (empty if no trigger)
            - conditions: Dict showing each condition status

        Raises:
            ValueError: If any input parameter is invalid
        """
        # Validate inputs
        if not isinstance(current_year, int) or current_year < 1:
            raise ValueError(f"current_year must be positive int, got {current_year}")
        if current_dscr < 0:
            raise ValueError(f"current_dscr must be >= 0, got {current_dscr}")
        if current_interest_rate < 0:
            raise ValueError(
                f"current_interest_rate must be >= 0, got {current_interest_rate}"
            )
        if not isinstance(npv_benefit, (int, float)):
            raise ValueError(
                f"npv_benefit must be numeric, got {type(npv_benefit).__name__}"
            )

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
        # FIX: Validate current_interest_rate is in reasonable range before comparison
        if current_interest_rate > 0.50:  # Sanity check: rate > 50%?
            logger.warning(
                "Unusually high current_interest_rate: %.2f%%",
                current_interest_rate * 100,
            )
        rate_savings_bps = (
            current_interest_rate - self.config.new_interest_rate
        ) * 10000
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
    """Represents a debt term line item.

    Attributes:
        original_amount: Original principal amount
        current_balance: Current outstanding balance
        interest_rate: Current interest rate
        tenor_years: Remaining tenor in years
        year_issued: Year the debt was issued
    """

    original_amount: float
    current_balance: float
    interest_rate: float
    tenor_years: int
    year_issued: int

    def __post_init__(self) -> None:
        """Validate debt term parameters."""
        if self.original_amount < 0:
            raise ValueError(
                f"original_amount must be >= 0, got {self.original_amount}"
            )
        if self.current_balance < 0:
            raise ValueError(
                f"current_balance must be >= 0, got {self.current_balance}"
            )
        if self.interest_rate < 0:
            raise ValueError(f"interest_rate must be >= 0, got {self.interest_rate}")
        if self.tenor_years < 1:
            raise ValueError(f"tenor_years must be >= 1, got {self.tenor_years}")


class RefinancingCalculator:
    """Calculates refinancing impacts on debt schedule.

    Handles:
    - Debt consolidation and schedule recalculation
    - Annuity-based payment calculation
    - Discounted cash flow (DCF) NPV analysis
    - Covenant impact analysis
    - Interest savings quantification
    """

    def __init__(self, config: RefinancingConfig) -> None:
        """Initialize calculator with configuration.

        Args:
            config: RefinancingConfig instance
        """
        if not isinstance(config, RefinancingConfig):
            raise TypeError(
                f"config must be RefinancingConfig, got {type(config).__name__}"
            )
        self.config = config

    def calculate_debt_service_payment(
        self, principal: float, rate: float, years: int
    ) -> float:
        """Calculate annual debt service payment (annuity).

        Uses standard annuity formula:
        P * (r(1+r)^n) / ((1+r)^n - 1)

        Where P=principal, r=annual rate, n=years

        Handles edge cases:
        - Zero rate -> P/n (straight amortization)
        - Zero principal -> 0
        - Zero years -> 0

        Args:
            principal: Principal amount (must be >= 0)
            rate: Annual interest rate (0-1 format, must be >= 0)
            years: Number of years (must be > 0)

        Returns:
            Annual debt service payment (always >= 0)

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if principal < 0:
            raise ValueError(f"principal must be >= 0, got {principal}")
        if rate < 0:
            raise ValueError(f"rate must be >= 0, got {rate}")
        if years <= 0:
            raise ValueError(f"years must be > 0, got {years}")

        # Edge cases
        if principal == 0:
            return 0.0
        if years == 0:
            return 0.0

        # Zero rate -> straight amortization
        if rate == 0:
            return principal / years

        # Standard annuity formula
        # FIX: Handle potential numerical overflow for very high rates
        try:
            factor = (1 + rate) ** years
            # Prevent division by zero (should never occur since rate > 0)
            denominator = factor - 1
            if denominator == 0:
                logger.warning(
                    "Annuity denominator is zero for rate=%.4f, years=%d",
                    rate,
                    years,
                )
                return principal / years  # Fallback to straight amortization
            payment = principal * (rate * factor) / denominator
            return max(0.0, payment)
        except (OverflowError, ZeroDivisionError) as e:
            logger.error(
                "Error calculating debt service (principal=%.2f, rate=%.4f, years=%d): %s",
                principal,
                rate,
                years,
                e,
            )
            # Fallback to linear amortization
            return principal / years

    def calculate_npv_savings(
        self,
        old_annual_payment: float,
        new_annual_payment: float,
        years: int,
        discount_rate: float,
    ) -> float:
        """Calculate NPV of refinancing savings (DCF methodology).

        Computes present value of difference between old and new
        annual payments over the refinancing period.

        Formula: NPV = SUM[t=1 to n] of (old_payment - new_payment) / (1 + r)^t

        Args:
            old_annual_payment: Annual payment under old terms
            new_annual_payment: Annual payment under new terms
            years: Number of years to calculate over
            discount_rate: Discount rate for NPV (0-1 format)

        Returns:
            NPV of savings in millions (can be negative if refinancing is expensive)

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if old_annual_payment < 0:
            raise ValueError(
                f"old_annual_payment must be >= 0, got {old_annual_payment}"
            )
        if new_annual_payment < 0:
            raise ValueError(
                f"new_annual_payment must be >= 0, got {new_annual_payment}"
            )
        if years <= 0:
            raise ValueError(f"years must be > 0, got {years}")
        if discount_rate < 0 or discount_rate > 0.5:
            raise ValueError(
                f"discount_rate must be 0-50%, got {discount_rate*100:.1f}%"
            )

        # Edge case: no difference
        annual_benefit = old_annual_payment - new_annual_payment
        if annual_benefit == 0:
            return 0.0

        # Discounted cash flow calculation
        try:
            npv = 0.0
            for t in range(1, years + 1):
                # FIX: Handle zero discount rate (no time value)
                if discount_rate == 0:
                    npv += annual_benefit
                else:
                    discount_factor = (1 + discount_rate) ** (-t)
                    npv += annual_benefit * discount_factor
            return npv
        except (OverflowError, ValueError) as e:
            logger.error(
                "Error calculating NPV (annual_benefit=%.2f, years=%d, discount_rate=%.4f): %s",
                annual_benefit,
                years,
                discount_rate,
                e,
            )
            return 0.0

    def recalculate_schedule(
        self,
        current_balance: float,
        current_year: int,
        remaining_years: int,
        current_interest_rate: float,
        debt_terms: Optional[List[DebtTerm]] = None,
    ) -> Dict[str, float]:
        """Recalculate debt schedule post-refinancing.

        Computes new annual payments, total interest, and savings.

        Args:
            current_balance: Total current debt balance (>= 0)
            current_year: Current year in simulation (>= 1)
            remaining_years: Years remaining in project life (> 0)
            current_interest_rate: Current weighted average interest rate
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
            - npv_of_savings: DCF NPV of savings (millions)

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if current_balance < 0:
            raise ValueError(f"current_balance must be >= 0, got {current_balance}")
        if current_year < 1:
            raise ValueError(f"current_year must be >= 1, got {current_year}")
        if remaining_years <= 0:
            raise ValueError(f"remaining_years must be > 0, got {remaining_years}")
        if current_interest_rate < 0:
            raise ValueError(
                f"current_interest_rate must be >= 0, got {current_interest_rate}"
            )

        # Edge case: zero balance
        if current_balance == 0:
            return {
                "new_annual_payment": 0.0,
                "new_tenor_effective": 0,
                "old_annual_estimate": 0.0,
                "total_interest_paid_old": 0.0,
                "total_interest_paid_new": 0.0,
                "interest_savings": 0.0,
                "upfront_costs": 0.0,
                "net_benefit": 0.0,
                "npv_of_savings": 0.0,
            }

        # Calculate new annual payment
        effective_tenor = min(self.config.new_tenor, remaining_years)
        new_payment = self.calculate_debt_service_payment(
            current_balance, self.config.new_interest_rate, effective_tenor
        )

        # FIX: Use actual current_interest_rate, not estimate
        old_rate = current_interest_rate if current_interest_rate > 0 else 0.06
        old_payment = self.calculate_debt_service_payment(
            current_balance, old_rate, remaining_years
        )

        # Calculate interest savings (over effective tenor)
        years_in_calc = min(effective_tenor, remaining_years)
        old_total_interest = (old_payment * years_in_calc) - current_balance
        new_total_interest = (new_payment * years_in_calc) - current_balance
        interest_savings = old_total_interest - new_total_interest

        # Calculate upfront costs
        upfront_costs = current_balance * self.config.upfront_cost_pct

        # Net benefit
        net_benefit = interest_savings - upfront_costs

        # Calculate NPV of savings
        npv_of_savings = self.calculate_npv_savings(
            old_payment, new_payment, years_in_calc, self.config.discount_rate_for_npv
        )

        return {
            "new_annual_payment": max(0.0, new_payment),
            "new_tenor_effective": effective_tenor,
            "old_annual_estimate": max(0.0, old_payment),
            "total_interest_paid_old": max(0.0, old_total_interest),
            "total_interest_paid_new": max(0.0, new_total_interest),
            "interest_savings": max(0.0, interest_savings),
            "upfront_costs": max(0.0, upfront_costs),
            "net_benefit": net_benefit,
            "npv_of_savings": npv_of_savings,
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
            - dscr: Debt Service Coverage Ratio = annual_cashflow / debt_service
            - llcr: Loan Life Coverage Ratio = ebitda / total_debt
            - plcr: Project Life Coverage Ratio (simplified as LLCR)

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if new_annual_debt_service < 0:
            raise ValueError(
                f"new_annual_debt_service must be >= 0, got {new_annual_debt_service}"
            )
        if annual_cashflow < 0:
            raise ValueError(f"annual_cashflow must be >= 0, got {annual_cashflow}")
        if ebitda < 0:
            raise ValueError(f"ebitda must be >= 0, got {ebitda}")
        if total_debt < 0:
            raise ValueError(f"total_debt must be >= 0, got {total_debt}")

        # Calculate DSCR (Debt Service Coverage Ratio)
        # FIX: Handle zero debt service
        if new_annual_debt_service > 0:
            dscr = annual_cashflow / new_annual_debt_service
        else:
            dscr = float("inf") if annual_cashflow > 0 else 0.0

        # Calculate LLCR (Loan Life Coverage Ratio)
        # FIX: Handle zero total debt
        if total_debt > 0:
            llcr = ebitda / total_debt
        else:
            llcr = float("inf") if ebitda > 0 else 0.0

        # Calculate PLCR (Project Life Coverage Ratio)
        # Simplified: same as LLCR for this context
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

    Raises:
        TypeError: If config is invalid type
        ValueError: If any input parameter is invalid
    """
    if not isinstance(config, RefinancingConfig):
        raise TypeError(
            f"config must be RefinancingConfig, got {type(config).__name__}"
        )

    # Create trigger and calculator
    trigger = RefinancingTrigger(config)
    calculator = RefinancingCalculator(config)

    # Calculate NPV benefit using actual DCF methodology
    # FIX: Replace placeholder with actual NPV calculation
    if current_debt_balance > 0 and remaining_years > 0:
        # Estimate old rate (use actual if available, or add 100bps to new rate)
        old_rate_estimate = (
            current_interest_rate
            if current_interest_rate > 0
            else (config.new_interest_rate + 0.01)
        )
        old_payment = calculator.calculate_debt_service_payment(
            current_debt_balance, old_rate_estimate, remaining_years
        )
        new_payment = calculator.calculate_debt_service_payment(
            current_debt_balance, config.new_interest_rate, remaining_years
        )
        npv_benefit = calculator.calculate_npv_savings(
            old_payment,
            new_payment,
            min(config.new_tenor, remaining_years),
            config.discount_rate_for_npv,
        )
    else:
        npv_benefit = 0.0

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
            current_interest_rate,
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
            "npv_of_savings": 0.0,
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
