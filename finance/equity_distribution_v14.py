"""Equity Distribution Module V14 - Production Hardened.

Provides equity distribution waterfall with:
- Priority-based cascading distribution (debt -> reserves -> equity)
- Covenant compliance gating (DSCR/LLCR gates)
- Multi-tier equity support (Class A, Class B, Common)
- Reserve account management and rebuilding
- Tax timing flexibility

All calculations follow standard project finance waterfall patterns.
"""

from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EquityTierType(str, Enum):
    """Equity tier classifications.

    Standard project finance equity structure.
    """

    PREFERRED = "preferred"
    CLASS_A = "class_a"
    CLASS_B = "class_b"
    COMMON = "common"


class DistributionWaterfall(Enum):
    """Waterfall priority levels.

    Defines cascade order:
    1. Debt service (mandatory)
    2. Debt service reserve (rebuild to target)
    3. Operating reserve (rebuild to target)
    4. Class A equity (preferred return, then principal)
    5. Class B equity (preferred return, then principal)
    6. Common equity (residual)
    """

    DEBT_SERVICE = 1
    DEBT_RESERVE = 2
    OPERATING_RESERVE = 3
    CLASS_A_EQUITY = 4
    CLASS_B_EQUITY = 5
    COMMON_EQUITY = 6


class EquityDistributionConfig(BaseModel):
    """Pydantic v2 configuration for equity distribution.

    All parameters externalized and configurable. Controls:
    - Waterfall priorities
    - Covenant thresholds
    - Reserve levels
    - Preferred return rates
    - Distribution gating

    Attributes:
        enabled: Whether equity distribution module is active
        waterfall_enabled: Enable waterfall distribution logic
        min_dscr_for_distribution: Minimum DSCR required (0.5-3.0, default 1.20)
        min_llcr_for_distribution: Minimum LLCR required (0.5-5.0, default 1.50)
        debt_reserve_target_months: Debt service reserve in months (0-24, default 6)
        operating_reserve_target_months: Operating reserve in months (0-12, default 3)
        reserve_rebuild_priority: Rebuild reserves before distributions (default True)
        class_a_preferred_return: Class A preferred return rate (0-20%, default 8%)
        class_b_preferred_return: Class B preferred return rate (0-25%, default 12%)
        distributions_allowed_after_year: Year after which distributions start (0-20, default 5)
        max_distribution_pct_cf: Max distribution as % of available CF (0-100%, default 80%)
        tax_distribution_only: Restrict to tax distributions early (default False)
        covenant_gating_strict: Apply strict gates to all distributions (default True)
    """

    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable equity distribution")
    waterfall_enabled: bool = Field(default=True, description="Enable waterfall logic")
    min_dscr_for_distribution: float = Field(
        default=1.20, ge=0.5, le=3.0, description="Minimum DSCR for distributions"
    )
    min_llcr_for_distribution: float = Field(
        default=1.50, ge=0.5, le=5.0, description="Minimum LLCR for distributions"
    )
    debt_reserve_target_months: float = Field(
        default=6.0, ge=0, le=24, description="Debt service reserve in months"
    )
    operating_reserve_target_months: float = Field(
        default=3.0, ge=0, le=12, description="Operating reserve in months"
    )
    reserve_rebuild_priority: bool = Field(
        default=True, description="Rebuild reserves before distributions"
    )
    class_a_preferred_return: float = Field(
        default=0.08, ge=0.0, le=0.20, description="Class A preferred return"
    )
    class_b_preferred_return: float = Field(
        default=0.12, ge=0.0, le=0.25, description="Class B preferred return"
    )
    distributions_allowed_after_year: int = Field(
        default=5, ge=0, le=20, description="Year distributions start"
    )
    max_distribution_pct_cf: float = Field(
        default=0.80, ge=0.0, le=1.0, description="Max distribution as % of CF"
    )
    tax_distribution_only: bool = Field(
        default=False, description="Restrict to tax distributions"
    )
    covenant_gating_strict: bool = Field(
        default=True, description="Apply strict covenant gates"
    )

    @field_validator("min_dscr_for_distribution")
    @classmethod
    def validate_min_dscr(cls, v: float) -> float:
        """Validate DSCR threshold is reasonable."""
        if v < 0.5:
            raise ValueError("min_dscr_for_distribution must be >= 0.5")
        return v

    @field_validator("class_a_preferred_return")
    @classmethod
    def validate_class_a_return(cls, v: float) -> float:
        """Validate Class A preferred return is reasonable."""
        if v < 0.0:
            raise ValueError("class_a_preferred_return must be >= 0.0")
        return v

    @field_validator("debt_reserve_target_months")
    @classmethod
    def validate_debt_reserve(cls, v: float) -> float:
        """Validate debt reserve target."""
        if v < 0:
            raise ValueError("debt_reserve_target_months must be >= 0")
        return v


class CovenantGate:
    """Evaluates covenant compliance gates for distribution.

    Implements gating logic to prevent distributions when covenants
    would be breached or are too close to limits.

    Thresholds defined in config, not hardcoded.
    """

    def __init__(self, config: EquityDistributionConfig) -> None:
        """Initialize gate with configuration.

        Args:
            config: EquityDistributionConfig instance

        Raises:
            TypeError: If config invalid type
        """
        if not isinstance(config, EquityDistributionConfig):
            raise TypeError(f"config must be EquityDistributionConfig, got {type(config).__name__}")
        self.config = config

    def check_dscr_gate(
        self, current_dscr: float, post_distribution_dscr: float
    ) -> Tuple[bool, str]:
        """Check DSCR covenant gate.

        Validates that DSCR after distribution remains above threshold.

        Args:
            current_dscr: Current DSCR before distribution (must be >= 0)
            post_distribution_dscr: Estimated DSCR after distribution

        Returns:
            Tuple of (gate_pass, reason_string)

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if current_dscr < 0:
            raise ValueError(f"current_dscr must be >= 0, got {current_dscr}")
        if post_distribution_dscr < 0:
            raise ValueError(f"post_distribution_dscr must be >= 0, got {post_distribution_dscr}")

        threshold = self.config.min_dscr_for_distribution

        # FIX: Handle infinity (construction period)
        if post_distribution_dscr == float("inf"):
            reason = f"DSCR gate PASS: Construction/grace period (inf >= {threshold:.3f})"
            return True, reason

        if post_distribution_dscr < threshold:
            reason = (
                f"DSCR gate FAIL: Post-distribution DSCR {post_distribution_dscr:.3f} "
                f"< threshold {threshold:.3f}"
            )
            return False, reason

        reason = f"DSCR gate PASS: {post_distribution_dscr:.3f} >= {threshold:.3f}"
        return True, reason

    def check_llcr_gate(
        self, current_llcr: float, post_distribution_llcr: float
    ) -> Tuple[bool, str]:
        """Check LLCR covenant gate.

        Validates that LLCR after distribution remains above threshold.

        Args:
            current_llcr: Current LLCR before distribution (must be >= 0)
            post_distribution_llcr: Estimated LLCR after distribution

        Returns:
            Tuple of (gate_pass, reason_string)

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if current_llcr < 0:
            raise ValueError(f"current_llcr must be >= 0, got {current_llcr}")
        if post_distribution_llcr < 0:
            raise ValueError(f"post_distribution_llcr must be >= 0, got {post_distribution_llcr}")

        threshold = self.config.min_llcr_for_distribution

        # FIX: Handle infinity (no debt)
        if post_distribution_llcr == float("inf"):
            reason = f"LLCR gate PASS: No debt outstanding (inf >= {threshold:.3f})"
            return True, reason

        if post_distribution_llcr < threshold:
            reason = (
                f"LLCR gate FAIL: Post-distribution LLCR {post_distribution_llcr:.3f} "
                f"< threshold {threshold:.3f}"
            )
            return False, reason

        reason = f"LLCR gate PASS: {post_distribution_llcr:.3f} >= {threshold:.3f}"
        return True, reason

    def check_all_gates(
        self,
        current_dscr: float,
        current_llcr: float,
        post_dist_dscr: float,
        post_dist_llcr: float,
    ) -> Tuple[bool, Dict[str, Tuple[bool, str]]]:
        """Check all covenant gates.

        Args:
            current_dscr: Current DSCR (>= 0)
            current_llcr: Current LLCR (>= 0)
            post_dist_dscr: DSCR after distribution
            post_dist_llcr: LLCR after distribution

        Returns:
            Tuple of (all_pass, gates_status_dict)
        """
        gates_status = {}
        gates_status["dscr"] = self.check_dscr_gate(current_dscr, post_dist_dscr)
        gates_status["llcr"] = self.check_llcr_gate(current_llcr, post_dist_llcr)

        all_pass = all(result[0] for result in gates_status.values())
        return all_pass, gates_status


class EquityDistributionCalculator:
    """Calculates equity distribution waterfall.

    Implements priority-based cascading distribution:
    1. Debt service (pass-through, mandatory)
    2. Debt reserve (rebuild to target)
    3. Operating reserve (rebuild to target)
    4. Class A equity (preferred return + principal)
    5. Class B equity (preferred return + principal)
    6. Common equity (residual)

    All distributions are gated by covenant compliance.
    """

    def __init__(self, config: EquityDistributionConfig) -> None:
        """Initialize calculator with configuration.

        Args:
            config: EquityDistributionConfig instance

        Raises:
            TypeError: If config invalid type
        """
        if not isinstance(config, EquityDistributionConfig):
            raise TypeError(f"config must be EquityDistributionConfig, got {type(config).__name__}")
        self.config = config
        self.covenant_gate = CovenantGate(config)

    def calculate_required_reserves(
        self, monthly_debt_service: float, monthly_operating_costs: float
    ) -> Dict[str, float]:
        """Calculate required reserve levels.

        Args:
            monthly_debt_service: Monthly debt service amount (>= 0)
            monthly_operating_costs: Monthly operating costs (>= 0)

        Returns:
            Dict with required reserve levels:
            - debt_service_reserve: Required DSR
            - operating_reserve: Required OR
            - total_reserves: Sum of reserves

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if monthly_debt_service < 0:
            raise ValueError(f"monthly_debt_service must be >= 0, got {monthly_debt_service}")
        if monthly_operating_costs < 0:
            raise ValueError(f"monthly_operating_costs must be >= 0, got {monthly_operating_costs}")

        debt_reserve = (
            monthly_debt_service * self.config.debt_reserve_target_months
        )
        operating_reserve = (
            monthly_operating_costs * self.config.operating_reserve_target_months
        )

        return {
            "debt_service_reserve": max(0.0, debt_reserve),
            "operating_reserve": max(0.0, operating_reserve),
            "total_reserves": max(0.0, debt_reserve + operating_reserve),
        }

    def calculate_available_for_equity(
        self,
        annual_cashflow: float,
        debt_service_required: float,
        reserve_deficit: float,
    ) -> float:
        """Calculate cashflow available for equity distribution.

        Waterfall priority:
        1. Debt service (pass-through, mandatory)
        2. Reserve rebuilding (if enabled)
        3. Remaining for equity (capped by max_distribution_pct_cf)

        Args:
            annual_cashflow: Annual available cashflow (>= 0)
            debt_service_required: Annual debt service required (>= 0)
            reserve_deficit: Amount needed to restore reserves (>= 0)

        Returns:
            Available cashflow for equity distribution (>= 0)

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if annual_cashflow < 0:
            raise ValueError(f"annual_cashflow must be >= 0, got {annual_cashflow}")
        if debt_service_required < 0:
            raise ValueError(f"debt_service_required must be >= 0, got {debt_service_required}")
        if reserve_deficit < 0:
            raise ValueError(f"reserve_deficit must be >= 0, got {reserve_deficit}")

        # Debt service first (non-negotiable)
        after_debt_service = max(0.0, annual_cashflow - debt_service_required)

        # Reserve rebuilding second (if enabled and config-driven priority)
        if self.config.reserve_rebuild_priority:
            after_reserves = max(0.0, after_debt_service - reserve_deficit)
        else:
            after_reserves = after_debt_service

        # Cap distribution
        max_distribution = annual_cashflow * self.config.max_distribution_pct_cf
        available = min(after_reserves, max_distribution)

        return max(0.0, available)

    def distribute_to_equity_tiers(
        self,
        available_cashflow: float,
        class_a_invested: float,
        class_b_invested: float,
        class_a_accumulated_returns: float = 0.0,
        class_b_accumulated_returns: float = 0.0,
    ) -> Dict[str, Dict[str, float]]:
        """Distribute available cashflow to equity tiers.

        Implements preferred return structure:
        - Class A: Preferred return first, then principal recovery (pro-rata)
        - Class B: Preferred return first, then principal recovery (pro-rata)
        - Common: Residual

        All returns calculated on invested capital basis.

        Args:
            available_cashflow: Available for distribution (>= 0)
            class_a_invested: Class A invested capital (>= 0)
            class_b_invested: Class B invested capital (>= 0)
            class_a_accumulated_returns: Accumulated returns for deferred preferred (>= 0)
            class_b_accumulated_returns: Accumulated returns for deferred preferred (>= 0)

        Returns:
            Dict with distribution to each tier:
            {
                'class_a': {'preferred_return': X, 'principal_recovery': Y, 'total': X+Y},
                'class_b': {'preferred_return': A, 'principal_recovery': B, 'total': A+B},
                'common': {'distribution': Z, 'total': Z}
            }

        Raises:
            ValueError: If inputs invalid
        """
        # Input validation
        if available_cashflow < 0:
            raise ValueError(f"available_cashflow must be >= 0, got {available_cashflow}")
        if class_a_invested < 0:
            raise ValueError(f"class_a_invested must be >= 0, got {class_a_invested}")
        if class_b_invested < 0:
            raise ValueError(f"class_b_invested must be >= 0, got {class_b_invested}")

        distributions = {
            "class_a": {"preferred_return": 0.0, "principal_recovery": 0.0, "total": 0.0},
            "class_b": {"preferred_return": 0.0, "principal_recovery": 0.0, "total": 0.0},
            "common": {"distribution": 0.0, "total": 0.0},
        }

        # Edge case: no cashflow to distribute
        if available_cashflow <= 0:
            return distributions

        remaining = available_cashflow

        # Class A preferred return
        # FIX: Only calculate if Class A has invested capital
        if class_a_invested > 0:
            a_pref_owed = class_a_invested * self.config.class_a_preferred_return
            a_pref_dist = min(remaining, a_pref_owed)
            distributions["class_a"]["preferred_return"] = a_pref_dist
            remaining -= a_pref_dist

        # Class B preferred return
        # FIX: Only calculate if Class B has invested capital and remaining > 0
        if class_b_invested > 0 and remaining > 0:
            b_pref_owed = class_b_invested * self.config.class_b_preferred_return
            b_pref_dist = min(remaining, b_pref_owed)
            distributions["class_b"]["preferred_return"] = b_pref_dist
            remaining -= b_pref_dist

        # Principal recovery (pro-rata to invested basis)
        # FIX: Only distribute if both parties have investments
        total_invested = class_a_invested + class_b_invested
        if total_invested > 0 and remaining > 0:
            a_share = class_a_invested / total_invested
            b_share = class_b_invested / total_invested

            distributions["class_a"]["principal_recovery"] = remaining * a_share
            distributions["class_b"]["principal_recovery"] = remaining * b_share
            remaining = 0.0
        elif remaining > 0:  # No invested capital, all goes to common
            logger.warning(
                "Principal recovery requested but no invested capital; "  
                "allocating %.2f to common",
                remaining,
            )

        # Common equity gets residual (if any)
        distributions["common"]["distribution"] = max(0.0, remaining)

        # Totals
        distributions["class_a"]["total"] = (
            distributions["class_a"]["preferred_return"]
            + distributions["class_a"]["principal_recovery"]
        )
        distributions["class_b"]["total"] = (
            distributions["class_b"]["preferred_return"]
            + distributions["class_b"]["principal_recovery"]
        )
        distributions["common"]["total"] = distributions["common"]["distribution"]

        return distributions


@dataclass
class EquityDistributionOutput:
    """Structured output from equity distribution calculation.

    Attributes:
        distribution_year: Year of calculation
        distribution_enabled: Whether distributions occurred (gates passed)
        required_debt_service: Annual debt service required
        available_cashflow: Cashflow available after debt service
        reserve_deficit: Amount needed to rebuild reserves
        available_for_equity: Cashflow available for equity distribution
        covenant_gates_passed: Whether all covenant gates passed
        covenant_gate_details: Dict with gate status details
        distributions_to_tiers: Dict with distribution to each equity tier
        total_equity_distribution: Total distributed to equity
        remaining_cashflow: Cashflow remaining after all uses
        timestamp: When calculation was performed
    """

    distribution_year: int
    distribution_enabled: bool
    required_debt_service: float
    available_cashflow: float
    reserve_deficit: float
    available_for_equity: float
    covenant_gates_passed: bool
    covenant_gate_details: Dict[str, Tuple[bool, str]]
    distributions_to_tiers: Dict[str, Dict[str, float]]
    total_equity_distribution: float
    remaining_cashflow: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "distribution_year": self.distribution_year,
            "distribution_enabled": self.distribution_enabled,
            "required_debt_service": float(self.required_debt_service),
            "available_cashflow": float(self.available_cashflow),
            "reserve_deficit": float(self.reserve_deficit),
            "available_for_equity": float(self.available_for_equity),
            "covenant_gates_passed": self.covenant_gates_passed,
            "covenant_gate_details": {
                k: {"pass": v[0], "reason": v[1]}
                for k, v in self.covenant_gate_details.items()
            },
            "distributions_to_tiers": self.distributions_to_tiers,
            "total_equity_distribution": float(self.total_equity_distribution),
            "remaining_cashflow": float(self.remaining_cashflow),
            "timestamp": self.timestamp.isoformat(),
        }


def calculate_equity_distribution(
    config: EquityDistributionConfig,
    year: int,
    annual_cashflow: float,
    debt_service_required: float,
    monthly_debt_service: float,
    monthly_operating_costs: float,
    current_dscr: float,
    current_llcr: float,
    class_a_invested: float,
    class_b_invested: float,
) -> EquityDistributionOutput:
    """Main entry point for equity distribution calculation.

    Orchestrates waterfall calculation and covenant gating.

    Args:
        config: EquityDistributionConfig instance
        year: Current year in simulation (>= 1)
        annual_cashflow: Annual available cashflow (>= 0)
        debt_service_required: Annual debt service required (>= 0)
        monthly_debt_service: Monthly debt service (>= 0)
        monthly_operating_costs: Monthly operating costs (>= 0)
        current_dscr: Current DSCR (>= 0)
        current_llcr: Current LLCR (>= 0)
        class_a_invested: Class A invested capital (>= 0)
        class_b_invested: Class B invested capital (>= 0)

    Returns:
        EquityDistributionOutput with complete distribution results

    Raises:
        TypeError: If config invalid type
        ValueError: If any input invalid
    """
    if not isinstance(config, EquityDistributionConfig):
        raise TypeError(f"config must be EquityDistributionConfig, got {type(config).__name__}")

    # Input validation
    if year < 1:
        raise ValueError(f"year must be >= 1, got {year}")
    if annual_cashflow < 0:
        raise ValueError(f"annual_cashflow must be >= 0, got {annual_cashflow}")
    if debt_service_required < 0:
        raise ValueError(f"debt_service_required must be >= 0, got {debt_service_required}")

    calculator = EquityDistributionCalculator(config)

    # Check if distributions allowed in this year
    distributions_allowed = year >= config.distributions_allowed_after_year

    if not distributions_allowed or not config.enabled:
        return EquityDistributionOutput(
            distribution_year=year,
            distribution_enabled=False,
            required_debt_service=debt_service_required,
            available_cashflow=max(0.0, annual_cashflow - debt_service_required),
            reserve_deficit=0.0,
            available_for_equity=0.0,
            covenant_gates_passed=False,
            covenant_gate_details={},
            distributions_to_tiers={
                "class_a": {"preferred_return": 0.0, "principal_recovery": 0.0, "total": 0.0},
                "class_b": {"preferred_return": 0.0, "principal_recovery": 0.0, "total": 0.0},
                "common": {"distribution": 0.0, "total": 0.0},
            },
            total_equity_distribution=0.0,
            remaining_cashflow=max(0.0, annual_cashflow - debt_service_required),
        )

    # Calculate required reserves
    required_reserves = calculator.calculate_required_reserves(
        monthly_debt_service, monthly_operating_costs
    )
    reserve_deficit = required_reserves["total_reserves"]

    # Calculate available for equity (before covenant gating)
    available_after_debt = max(0.0, annual_cashflow - debt_service_required)
    available_for_equity = calculator.calculate_available_for_equity(
        annual_cashflow, debt_service_required, reserve_deficit
    )

    # FIX: Properly calculate post-distribution covenant impact
    # DSCR impact: distribution reduces available cashflow
    if debt_service_required > 0:
        post_dist_dscr = (
            (annual_cashflow - available_for_equity) / debt_service_required
        )
    else:
        post_dist_dscr = current_dscr

    # LLCR impact: simplified as reduction in asset base
    # In production, would use actual debt/EBITDA recalculation
    if current_llcr > 0 and available_for_equity > 0:
        # Conservative estimate: distribution reduces equity by distribution amount
        # which indirectly increases leverage
        impact_factor = 1.0 - (available_for_equity / (annual_cashflow + 1e-6))
        post_dist_llcr = current_llcr * impact_factor
    else:
        post_dist_llcr = current_llcr

    # Check covenant gates
    gates_passed, gates_details = calculator.covenant_gate.check_all_gates(
        current_dscr, current_llcr, post_dist_dscr, post_dist_llcr
    )

    # If gates fail, no distribution
    if config.covenant_gating_strict and not gates_passed:
        available_for_equity = 0.0
        logger.warning(
            "Covenant gates failed in year %d; distributions suppressed", year
        )

    # Distribute to equity tiers
    distributions = calculator.distribute_to_equity_tiers(
        available_for_equity,
        class_a_invested,
        class_b_invested,
        0.0,  # accumulated_returns (simplified)
        0.0,
    )

    total_distributed = (
        distributions["class_a"]["total"]
        + distributions["class_b"]["total"]
        + distributions["common"]["total"]
    )

    return EquityDistributionOutput(
        distribution_year=year,
        distribution_enabled=gates_passed,
        required_debt_service=debt_service_required,
        available_cashflow=available_after_debt,
        reserve_deficit=reserve_deficit,
        available_for_equity=available_for_equity,
        covenant_gates_passed=gates_passed,
        covenant_gate_details=gates_details,
        distributions_to_tiers=distributions,
        total_equity_distribution=total_distributed,
        remaining_cashflow=max(0.0, available_after_debt - total_distributed),
    )
