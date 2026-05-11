"""Hardened refinancing module for v14 refinancing event modelling."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DSCR_MIN_VALID = 0.8
DSCR_MAX_VALID = 2.5
COUPON_MIN_PCT = 0.0
COUPON_MAX_PCT = 20.0
TENOR_MIN_YEARS = 5
TENOR_MAX_YEARS = 30
REFIN_COST_MIN_PCT = 0.0
REFIN_COST_MAX_PCT = 2.0
PRINCIPAL_REPAY_MIN_PCT = 0.0
PRINCIPAL_REPAY_MAX_PCT = 100.0


class RefinancingValidationError(ValueError):
    """Raised when refinancing config or inputs fail validation."""


class RefinancingConfigError(ValueError):
    """Raised when refinancing configuration is invalid."""


class RefinancingCalculationError(RuntimeError):
    """Raised when refinancing calculations fail."""


@dataclass
class RefinancingConfig:
    """Refinancing event configuration."""

    enabled: bool = False
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    new_coupon_pct: Optional[float] = None
    refinancing_cost_pct: float = 0.5
    new_tenor_years: Optional[int] = None
    principal_repayment_pct: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefinancingOutput:
    """Refinancing event output contract with audit metadata."""

    scenario_name: str
    refinancing_occurred: bool
    event_year: Optional[int] = None
    trigger_type: Optional[str] = None
    trigger_value: Optional[float] = None
    trigger_dscr: Optional[float] = None
    pre_refi_npv: Optional[float] = None
    post_refi_npv: Optional[float] = None
    npv_benefit: Optional[float] = None
    pre_refi_equity_irr: Optional[float] = None
    post_refi_equity_irr: Optional[float] = None
    equity_irr_benefit_bps: Optional[float] = None
    refinancing_cost_usd: Optional[float] = None
    new_principal_usd: Optional[float] = None
    new_coupon_pct: Optional[float] = None
    principal_repaid_usd: Optional[float] = None
    new_tenor_years: Optional[int] = None
    covenant_breach_resolved: bool = False
    pre_refi_min_dscr: Optional[float] = None
    post_refi_min_dscr: Optional[float] = None
    years_in_breach_before: int = 0
    years_in_breach_after: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    contract_version: str = "v14.4.0"


def validate_dscr_value(dscr: float, field_name: str = "dscr") -> None:
    """Validate DSCR is within acceptable range."""
    if not isinstance(dscr, (int, float)):
        raise RefinancingValidationError(
            f"{field_name} must be numeric, got {type(dscr).__name__}"
        )
    if not (DSCR_MIN_VALID <= dscr <= DSCR_MAX_VALID):
        raise RefinancingValidationError(
            f"{field_name} must be between {DSCR_MIN_VALID} and {DSCR_MAX_VALID}, "
            f"got {dscr:.2f}"
        )


def validate_coupon_pct(coupon: float, field_name: str = "coupon_pct") -> None:
    """Validate coupon percentage."""
    if not isinstance(coupon, (int, float)):
        raise RefinancingValidationError(
            f"{field_name} must be numeric, got {type(coupon).__name__}"
        )
    if not (COUPON_MIN_PCT <= coupon <= COUPON_MAX_PCT):
        raise RefinancingValidationError(
            f"{field_name} must be between {COUPON_MIN_PCT}% and {COUPON_MAX_PCT}%, "
            f"got {coupon}%"
        )


def validate_tenor_years(tenor: int, field_name: str = "tenor_years") -> None:
    """Validate tenor in years."""
    if not isinstance(tenor, (int, float)):
        raise RefinancingValidationError(
            f"{field_name} must be numeric, got {type(tenor).__name__}"
        )
    tenor_int = int(tenor)
    if not (TENOR_MIN_YEARS <= tenor_int <= TENOR_MAX_YEARS):
        raise RefinancingValidationError(
            f"{field_name} must be between {TENOR_MIN_YEARS} and {TENOR_MAX_YEARS} years, "
            f"got {tenor_int} years"
        )


def validate_cost_pct(cost: float, field_name: str = "cost_pct") -> None:
    """Validate cost percentage."""
    if not isinstance(cost, (int, float)):
        raise RefinancingValidationError(
            f"{field_name} must be numeric, got {type(cost).__name__}"
        )
    if not (REFIN_COST_MIN_PCT <= cost <= REFIN_COST_MAX_PCT):
        raise RefinancingValidationError(
            f"{field_name} must be between {REFIN_COST_MIN_PCT}% and {REFIN_COST_MAX_PCT}%, "
            f"got {cost}%"
        )


class RefinancingCalculatorHardened:
    """Production-grade refinancing calculator with validation."""

    def __init__(
        self,
        config: RefinancingConfig,
        debt_result: Dict[str, Any],
        annual_rows: List[Dict[str, Any]],
    ) -> None:
        self.config = config
        self.debt_result = debt_result
        self.annual_rows = annual_rows
        self._extract_pipeline_metrics()
        self._validate_config()

    def _extract_pipeline_metrics(self) -> None:
        """Extract and cache key metrics from pipeline results."""
        self.current_principal = float(
            self.debt_result.get("total_debt_remaining")
            or self.debt_result.get("total_debt", 0.0)
        )
        self.dscr_series = list(self.debt_result.get("dscr_series") or [])
        self.min_dscr = float(self.debt_result.get("min_dscr", 0.0))
        self.current_coupon_rate = 0.065

    def _validate_config(self) -> None:
        """Validate configuration thoroughly."""
        if not self.config.enabled:
            logger.info("Refinancing disabled, skipping validation")
            return

        if not self.config.triggers:
            raise RefinancingConfigError("Refinancing enabled but no triggers defined")

        if self.config.new_coupon_pct is None:
            raise RefinancingConfigError(
                "Refinancing enabled but new_coupon_pct not specified"
            )

        validate_coupon_pct(self.config.new_coupon_pct, "new_coupon_pct")
        validate_cost_pct(self.config.refinancing_cost_pct, "refinancing_cost_pct")

        if not (
            PRINCIPAL_REPAY_MIN_PCT
            <= self.config.principal_repayment_pct
            <= PRINCIPAL_REPAY_MAX_PCT
        ):
            raise RefinancingValidationError(
                "principal_repayment_pct must be 0-100%, "
                f"got {self.config.principal_repayment_pct}%"
            )

        if self.config.new_tenor_years is not None:
            validate_tenor_years(self.config.new_tenor_years, "new_tenor_years")

        logger.info("Refinancing config validation passed")

    def evaluate_refinancing_event(
        self,
        year: int,
        trigger_dscr: float,
        discount_rate: float,
    ) -> RefinancingOutput:
        """Evaluate refinancing event impact."""
        if year < 1 or year > len(self.annual_rows):
            raise RefinancingValidationError(
                f"Refinancing year must be 1-{len(self.annual_rows)}, got {year}"
            )

        validate_dscr_value(trigger_dscr, "trigger_dscr")

        if not self.config.enabled:
            logger.info("Refinancing disabled, no event")
            return RefinancingOutput(
                scenario_name="base",
                refinancing_occurred=False,
            )

        new_coupon_pct = self.config.new_coupon_pct
        if new_coupon_pct is None:
            raise RefinancingCalculationError(
                "new_coupon_pct is required when refinancing is enabled"
            )

        try:
            refinancing_cost = self.current_principal * (
                self.config.refinancing_cost_pct / 100
            )
            old_annual_interest = self.current_principal * self.current_coupon_rate
            new_coupon_rate = new_coupon_pct / 100
            new_annual_interest = self.current_principal * new_coupon_rate
            annual_savings = old_annual_interest - new_annual_interest
            tenor = self.config.new_tenor_years or (len(self.annual_rows) - year)
            npv_savings = sum(
                annual_savings / ((1 + discount_rate) ** t) for t in range(1, tenor + 1)
            )
            npv_benefit = npv_savings - refinancing_cost
            equity_irr_improvement_bps = (
                (npv_benefit / self.current_principal * 10000)
                if self.current_principal > 0
                else 0
            )
            breach_before = sum(1 for d in self.dscr_series if d < 1.25)
            breach_after = max(0, breach_before - 1)
            breach_resolved = trigger_dscr < 1.25 and breach_before > breach_after

            output = RefinancingOutput(
                scenario_name="base",
                refinancing_occurred=True,
                event_year=year,
                trigger_type="dscr_floor",
                trigger_value=trigger_dscr,
                trigger_dscr=trigger_dscr,
                pre_refi_npv=None,
                post_refi_npv=None,
                npv_benefit=npv_benefit,
                equity_irr_benefit_bps=equity_irr_improvement_bps,
                refinancing_cost_usd=refinancing_cost,
                new_principal_usd=self.current_principal,
                new_coupon_pct=new_coupon_pct,
                principal_repaid_usd=(
                    self.current_principal * (self.config.principal_repayment_pct / 100)
                ),
                new_tenor_years=tenor,
                covenant_breach_resolved=breach_resolved,
                pre_refi_min_dscr=self.min_dscr,
                years_in_breach_before=breach_before,
                years_in_breach_after=breach_after,
                metadata={
                    "old_coupon_pct": self.current_coupon_rate * 100,
                    "annual_savings_usd": annual_savings,
                    "annual_rows_count": len(self.annual_rows),
                    "discount_rate": discount_rate,
                    "validator_version": "v14.4.0",
                },
            )
            logger.info(
                "Refinancing evaluation complete: year=%s, npv_benefit=USD %.0f, breach_resolved=%s",
                year,
                npv_benefit,
                breach_resolved,
            )
            return output

        except Exception as exc:
            logger.error("Refinancing calculation failed: %s", exc)
            raise RefinancingCalculationError(
                f"Refinancing calculation failed at year {year}: {exc}"
            ) from exc

    def __repr__(self) -> str:
        return (
            "RefinancingCalculatorHardened("
            f"enabled={self.config.enabled}, "
            f"principal=USD {self.current_principal:,.0f}, "
            f"min_dscr={self.min_dscr:.2f})"
        )


__all__ = [
    "RefinancingConfig",
    "RefinancingOutput",
    "RefinancingCalculatorHardened",
    "validate_dscr_value",
    "validate_coupon_pct",
    "validate_tenor_years",
    "validate_cost_pct",
    "RefinancingValidationError",
    "RefinancingConfigError",
    "RefinancingCalculationError",
    "DSCR_MIN_VALID",
    "DSCR_MAX_VALID",
    "COUPON_MIN_PCT",
    "COUPON_MAX_PCT",
    "TENOR_MIN_YEARS",
    "TENOR_MAX_YEARS",
]
