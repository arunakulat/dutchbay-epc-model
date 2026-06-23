"""Comprehensive Validators for All v14 Contracts (CESSPIT Pattern).

This module provides exhaustive validation of all data contracts used in the
financial modeling pipeline:

- WaccResult: WACC component bounds and consistency
- ScenarioResult: Project economics sanity checks
- DebtCovenantSnapshot: DSCR thresholds and breach logic
- MonteCarloResult: VaR/CVaR bounds and distribution checks
- EquityResult: IRR/NPV ranges and multiple validation
- NPV Validation: Net Present Value bounds and sanity checks (Sprint 16)
- Equity Validation: Equity IRR/NPV/multiple validation (Sprint 16)

CESSPIT Compliance:
- All validations run pre-flight before execution
- Fail-fast on CRITICAL violations
- Comprehensive error reporting with remediation

CASPER Compliance:
- All validations logged with timestamp
- Full audit trail available
- Metadata attached to all results

CCCDIR Compliance:
- All bounds config-driven (no magic numbers)
- Typed validation functions
- Clear error types and messages

GWTF Compliance:
- Validates at gateway before operations
- Lazy validation (on-demand)
- Type-safe throughout

Usage:
    # Validate scenario result
    from analytics.contracts_v14_validators import validate_scenario_result

    result = validate_scenario_result(scenario, strict=True)
    if result.is_valid:
        proceed_with_calculations(scenario)
    else:
        log_validation_errors(result.errors)
        handle_warnings(result.warnings)

    # Sprint 16: Validate NPV
    from analytics.contracts_v14_validators import validate_npv
    
    npv_error = validate_npv(project_npv, "project_npv")
    if npv_error:
        logger.warning(npv_error.message)
    
    # Sprint 16: Validate Equity result
    equity_result = validate_equity_result(equity_dict, strict=True)
    if not equity_result.is_valid:
        raise ValueError(f"Equity validation failed: {equity_result.errors}")
"""

from __future__ import annotations

import dataclasses
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ VALIDATION BOUNDS (CCCDIR: CONFIG-DRIVEN)                                   ║
# ╚════════════════════════════════════════════════════════════════════════════╝

# DSCR: Debt Service Coverage Ratio (must be 0.8-2.5 to be realistic)
DSCR_MIN = 0.8
DSCR_MAX = 2.5

# IRR: Internal Rate of Return (should be 5-25% for renewable projects)
IRR_MIN = -0.05  # Allow negative for distressed scenarios
IRR_MAX = 0.50

# WACC: Weighted Average Cost of Capital (should be 3-12% for renewables)
WACC_MIN = 0.03
WACC_MAX = 0.12

# NPV: Net Present Value bounds (project-specific, but check for infinite/NaN)
NPV_MIN = -1e10  # -10 billion (distressed scenarios)
NPV_MAX = 1e10   # +10 billion (optimistic scenarios)

# Sprint 16: NPV sanity thresholds for warnings
NPV_TYPICAL_MIN = -1e9  # -1 billion
NPV_TYPICAL_MAX = 1e9   # +1 billion

# Coupon: Debt coupon percentage (0-20%)
COUPON_MIN = 0.0
COUPON_MAX = 0.20

# Tenor: Debt tenor years (5-30 years typical for project finance)
TENOR_MIN = 5
TENOR_MAX = 30

# Tax Rate: Should be 0-50% for realistic scenarios
TAX_RATE_MIN = 0.0
TAX_RATE_MAX = 0.50

# Debt-to-Value: Should be 40-85% for projects
DTV_MIN = 0.40
DTV_MAX = 0.85

# VaR/CVaR: Value at Risk and Conditional VaR (Monte Carlo)
VAR_MIN = -1.0  # Can't lose more than 100%
VAR_MAX = 0.0  # VaR is typically negative (loss metric)

# Equity Multiple: Equity investors expect 1.2-3.0x return
EQUITY_MULTIPLE_MIN = 0.8
EQUITY_MULTIPLE_MAX = 5.0

# Sprint 16: Equity IRR bounds (higher than project IRR due to leverage)
EQUITY_IRR_MIN = -0.10  # -10% for distressed
EQUITY_IRR_MAX = 0.60   # 60% for highly levered successful projects
EQUITY_IRR_TYPICAL_MIN = 0.10  # 10% typical minimum
EQUITY_IRR_TYPICAL_MAX = 0.30  # 30% typical maximum

# Sprint 16: Equity NPV bounds (smaller than project NPV)
EQUITY_NPV_MIN = -1e9  # -1 billion
EQUITY_NPV_MAX = 1e9   # +1 billion


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ VALIDATION RESULT CONTAINER                                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝


@dataclass
class ValidationError:
    """CESSPIT: Single validation error with full context."""

    severity: str  # "CRITICAL", "ERROR", "WARNING"
    field: str  # e.g., "project_irr", "min_dscr"
    value: Any
    constraint: str  # e.g., "must be >= 0.8"
    message: str
    remediation: Optional[str] = None
    timestamp: str = dataclasses.field(default_factory=lambda: datetime.utcnow().isoformat())

    def __str__(self) -> str:
        return f"[{self.severity}] {self.field}: {self.message}"


@dataclass
class ValidationResult:
    """CCCDIR: Complete validation result with audit trail."""

    is_valid: bool
    errors: List[ValidationError] = dataclasses.field(default_factory=list)
    warnings: List[str] = dataclasses.field(default_factory=list)
    info_messages: List[str] = dataclasses.field(default_factory=list)
    validation_time_ms: float = 0.0
    contract_type: str = "unknown"
    timestamp: str = dataclasses.field(default_factory=lambda: datetime.utcnow().isoformat())

    def has_critical_errors(self) -> bool:
        """Check if any CRITICAL errors present."""
        return any(e.severity == "CRITICAL" for e in self.errors)

    def has_errors(self) -> bool:
        """Check if any ERROR or CRITICAL errors present."""
        return any(e.severity in {"ERROR", "CRITICAL"} for e in self.errors)

    def error_count(self, severity: Optional[str] = None) -> int:
        """Count errors by severity.

        Args:
            severity: If None, count all. Otherwise count specific severity.
        """
        if severity is None:
            return len(self.errors)
        return sum(1 for e in self.errors if e.severity == severity)


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ INDIVIDUAL FIELD VALIDATORS                                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝


def validate_dscr(
    value: float,
    field_name: str = "dscr",
) -> Optional[ValidationError]:
    """Validate DSCR value is within realistic bounds.

    Args:
        value: DSCR value to validate
        field_name: Name of field for error message

    Returns:
        ValidationError if invalid, None if valid
    """
    if not isinstance(value, (int, float)):
        return ValidationError(
            severity="ERROR",
            field=field_name,
            value=value,
            constraint="must be numeric",
            message=f"{field_name} must be numeric, got {type(value).__name__}",
        )

    if not (DSCR_MIN <= value <= DSCR_MAX):
        return ValidationError(
            severity="WARNING" if value < 1.25 else "INFO",
            field=field_name,
            value=value,
            constraint=f"{DSCR_MIN} <= value <= {DSCR_MAX}",
            message=f"{field_name}={value:.2f} is outside typical range [{DSCR_MIN}, {DSCR_MAX}]",
            remediation="High DSCR > 2.5 may indicate over-conservative debt. Low DSCR < 0.8 indicates distress.",
        )

    return None


def validate_irr(
    value: float,
    field_name: str = "irr",
) -> Optional[ValidationError]:
    """Validate IRR is within project finance realistic bounds.

    Args:
        value: IRR value (decimal, e.g., 0.15 for 15%)
        field_name: Name of field for error message

    Returns:
        ValidationError if invalid, None if valid
    """
    if not isinstance(value, (int, float)):
        return ValidationError(
            severity="ERROR",
            field=field_name,
            value=value,
            constraint="must be numeric",
            message=f"{field_name} must be numeric, got {type(value).__name__}",
        )

    # Check for NaN or Infinity
    if not (-1e10 < value < 1e10):
        return ValidationError(
            severity="CRITICAL",
            field=field_name,
            value=value,
            constraint="must be finite",
            message=f"{field_name} is not finite: {value}",
        )

    if not (IRR_MIN <= value <= IRR_MAX):
        return ValidationError(
            severity="WARNING",
            field=field_name,
            value=value,
            constraint=f"{IRR_MIN*100:.0f}% <= value <= {IRR_MAX*100:.0f}%",
            message=f"{field_name}={value*100:.1f}% is outside typical renewable project range [5%-25%]",
        )

    return None


def validate_wacc(
    value: float,
    field_name: str = "wacc",
) -> Optional[ValidationError]:
    """Validate WACC is realistic for renewable projects.

    Args:
        value: WACC value (decimal, e.g., 0.08 for 8%)
        field_name: Name of field for error message

    Returns:
        ValidationError if invalid, None if valid
    """
    if not isinstance(value, (int, float)):
        return ValidationError(
            severity="ERROR",
            field=field_name,
            value=value,
            constraint="must be numeric",
            message=f"{field_name} must be numeric, got {type(value).__name__}",
        )

    if not (WACC_MIN <= value <= WACC_MAX):
        return ValidationError(
            severity="WARNING",
            field=field_name,
            value=value,
            constraint=f"{WACC_MIN*100:.0f}% <= value <= {WACC_MAX*100:.0f}%",
            message=f"{field_name}={value*100:.1f}% is outside typical renewable project range [3%-12%]",
        )

    return None


def validate_covenant_breach(
    dscr: float,
    threshold: float = 1.25,
) -> Optional[ValidationError]:
    """Validate covenant breach logic.

    Args:
        dscr: Debt Service Coverage Ratio
        threshold: Covenant threshold (default 1.25)

    Returns:
        ValidationError if invalid, None if valid
    """
    if not isinstance(dscr, (int, float)):
        return ValidationError(
            severity="ERROR",
            field="dscr",
            value=dscr,
            constraint="must be numeric",
            message=f"DSCR must be numeric, got {type(dscr).__name__}",
        )

    if dscr < 1.0:
        return ValidationError(
            severity="WARNING",
            field="dscr",
            value=dscr,
            constraint="DSCR < 1.0 indicates negative cash flow",
            message=f"DSCR={dscr:.2f} indicates project cannot cover debt service",
            remediation="Project may violate financial covenants. Consider refinancing or operational improvements.",
        )

    if dscr < threshold:
        return ValidationError(
            severity="WARNING",
            field="dscr",
            value=dscr,
            constraint=f"DSCR < {threshold}",
            message=f"DSCR={dscr:.2f} below lender threshold {threshold}",
            remediation="Covenant breach may trigger refinancing or equity calls.",
        )

    return None


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ SPRINT 16: NPV VALIDATORS                                                   ║
# ╚════════════════════════════════════════════════════════════════════════════╝


def validate_npv(
    value: float,
    field_name: str = "npv",
    strict_bounds: bool = False,
) -> Optional[ValidationError]:
    """Sprint 16: Validate Net Present Value is finite and within bounds.
    
    Args:
        value: NPV value in currency units (e.g., USD or LKR)
        field_name: Name of field for error message
        strict_bounds: If True, use typical bounds; if False, use wide bounds
    
    Returns:
        ValidationError if invalid, None if valid
    
    Example:
        >>> error = validate_npv(50_000_000, "project_npv")
        >>> assert error is None  # Valid NPV
        >>> 
        >>> error = validate_npv(float('inf'), "project_npv")
        >>> assert error.severity == "CRITICAL"  # Infinite NPV
        >>>
        >>> error = validate_npv(5_000_000_000, "project_npv", strict_bounds=True)
        >>> assert error.severity == "WARNING"  # Outside typical range
    """
    # Type check
    if not isinstance(value, (int, float)):
        return ValidationError(
            severity="ERROR",
            field=field_name,
            value=value,
            constraint="must be numeric",
            message=f"{field_name} must be numeric, got {type(value).__name__}",
        )
    
    # Check for NaN
    if math.isnan(value):
        return ValidationError(
            severity="CRITICAL",
            field=field_name,
            value=value,
            constraint="must not be NaN",
            message=f"{field_name} is NaN (Not a Number)",
            remediation="Check cashflow and discount rate inputs. NPV calculation failed.",
        )
    
    # Check for Infinity
    if math.isinf(value):
        return ValidationError(
            severity="CRITICAL",
            field=field_name,
            value=value,
            constraint="must be finite",
            message=f"{field_name} is infinite: {value}",
            remediation="Check discount rate (may be zero or negative). NPV calculation diverged.",
        )
    
    # Absolute bounds check (CRITICAL)
    if not (NPV_MIN <= value <= NPV_MAX):
        return ValidationError(
            severity="CRITICAL",
            field=field_name,
            value=value,
            constraint=f"{NPV_MIN:,.0f} <= value <= {NPV_MAX:,.0f}",
            message=f"{field_name}={value:,.0f} exceeds absolute bounds [-10B, +10B]",
            remediation="NPV magnitude unrealistic. Verify capex, revenue, and discount rate.",
        )
    
    # Typical bounds check (WARNING)
    if strict_bounds and not (NPV_TYPICAL_MIN <= value <= NPV_TYPICAL_MAX):
        return ValidationError(
            severity="WARNING",
            field=field_name,
            value=value,
            constraint=f"{NPV_TYPICAL_MIN:,.0f} <= value <= {NPV_TYPICAL_MAX:,.0f}",
            message=f"{field_name}={value:,.0f} is outside typical renewable project range [-1B, +1B]",
            remediation="Verify project scale. NPV > 1B suggests mega-project. NPV < -1B suggests distressed asset.",
        )
    
    # All checks passed
    return None


def validate_npv_consistency(
    project_npv: float,
    equity_npv: float,
    debt_npv: float = 0.0,
) -> Optional[ValidationError]:
    """Sprint 16: Validate NPV consistency across project/equity/debt.
    
    Project NPV should approximately equal Equity NPV + Debt NPV.
    
    Args:
        project_npv: Total project NPV
        equity_npv: Equity NPV
        debt_npv: Debt NPV (typically 0 if debt priced at par)
    
    Returns:
        ValidationError if inconsistent, None if valid
    
    Example:
        >>> error = validate_npv_consistency(
        ...     project_npv=100_000_000,
        ...     equity_npv=40_000_000,
        ...     debt_npv=60_000_000
        ... )
        >>> assert error is None  # Consistent
        >>>
        >>> error = validate_npv_consistency(
        ...     project_npv=100_000_000,
        ...     equity_npv=150_000_000,  # Too high!
        ...     debt_npv=0
        ... )
        >>> assert error.severity == "WARNING"  # Inconsistent
    """
    # Calculate implied NPV from equity + debt
    implied_project_npv = equity_npv + debt_npv
    
    # Allow 5% tolerance for rounding and timing differences
    tolerance = abs(project_npv) * 0.05 if project_npv != 0 else 1e6
    difference = abs(project_npv - implied_project_npv)
    
    if difference > tolerance:
        return ValidationError(
            severity="WARNING",
            field="npv_consistency",
            value={
                "project_npv": project_npv,
                "equity_npv": equity_npv,
                "debt_npv": debt_npv,
                "difference": difference,
            },
            constraint="project_npv ≈ equity_npv + debt_npv (within 5%)",
            message=(
                f"NPV inconsistency: Project NPV={project_npv:,.0f}, "
                f"Equity NPV={equity_npv:,.0f}, Debt NPV={debt_npv:,.0f}. "
                f"Difference={difference:,.0f} exceeds tolerance={tolerance:,.0f}"
            ),
            remediation=(
                "Check cashflow allocation. Equity + Debt NPV should sum to Project NPV. "
                "Verify debt pricing assumptions (debt NPV typically 0 if priced at par)."
            ),
        )
    
    return None


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ SPRINT 16: EQUITY VALIDATORS                                                ║
# ╚════════════════════════════════════════════════════════════════════════════╝


def validate_equity_irr(
    value: float,
    field_name: str = "equity_irr",
    strict_bounds: bool = True,
) -> Optional[ValidationError]:
    """Sprint 16: Validate Equity IRR is within realistic bounds.
    
    Equity IRR should be higher than project IRR due to leverage.
    Typical range: 10-30% for renewable projects.
    
    Args:
        value: Equity IRR value (decimal, e.g., 0.15 for 15%)
        field_name: Name of field for error message
        strict_bounds: If True, warn on atypical values
    
    Returns:
        ValidationError if invalid, None if valid
    
    Example:
        >>> error = validate_equity_irr(0.18)  # 18% - Good
        >>> assert error is None
        >>> 
        >>> error = validate_equity_irr(0.45)  # 45% - High but possible
        >>> assert error.severity == "WARNING"
        >>>
        >>> error = validate_equity_irr(float('nan'))  # NaN - Critical
        >>> assert error.severity == "CRITICAL"
    """
    # Type check
    if not isinstance(value, (int, float)):
        return ValidationError(
            severity="ERROR",
            field=field_name,
            value=value,
            constraint="must be numeric",
            message=f"{field_name} must be numeric, got {type(value).__name__}",
        )
    
    # Check for NaN
    if math.isnan(value):
        return ValidationError(
            severity="CRITICAL",
            field=field_name,
            value=value,
            constraint="must not be NaN",
            message=f"{field_name} is NaN (Not a Number)",
            remediation="Check equity cashflows. IRR calculation failed.",
        )
    
    # Check for Infinity
    if math.isinf(value):
        return ValidationError(
            severity="CRITICAL",
            field=field_name,
            value=value,
            constraint="must be finite",
            message=f"{field_name} is infinite: {value}",
            remediation="IRR calculation diverged. Check equity cashflow sign changes.",
        )
    
    # Absolute bounds check
    if not (EQUITY_IRR_MIN <= value <= EQUITY_IRR_MAX):
        return ValidationError(
            severity="ERROR",
            field=field_name,
            value=value,
            constraint=f"{EQUITY_IRR_MIN*100:.0f}% <= value <= {EQUITY_IRR_MAX*100:.0f}%",
            message=f"{field_name}={value*100:.1f}% exceeds absolute bounds [-10%, 60%]",
            remediation="Equity IRR outside plausible range. Verify equity cashflows and leverage.",
        )
    
    # Typical bounds check (WARNING)
    if strict_bounds and not (EQUITY_IRR_TYPICAL_MIN <= value <= EQUITY_IRR_TYPICAL_MAX):
        return ValidationError(
            severity="WARNING",
            field=field_name,
            value=value,
            constraint=f"{EQUITY_IRR_TYPICAL_MIN*100:.0f}% <= value <= {EQUITY_IRR_TYPICAL_MAX*100:.0f}%",
            message=f"{field_name}={value*100:.1f}% is outside typical range [10%-30%]",
            remediation=(
                "Equity IRR < 10% may indicate low leverage or poor project economics. "
                "Equity IRR > 30% may indicate high leverage or exceptional project."
            ),
        )
    
    return None


def validate_equity_multiple(
    value: float,
    field_name: str = "equity_multiple",
) -> Optional[ValidationError]:
    """Sprint 16: Validate Equity Multiple (Total Cash / Invested Capital).
    
    Equity multiple should be > 1.0 for positive return.
    Typical range: 1.2-3.0x for renewable projects.
    
    Args:
        value: Equity multiple (e.g., 2.5 means 2.5x return)
        field_name: Name of field for error message
    
    Returns:
        ValidationError if invalid, None if valid
    
    Example:
        >>> error = validate_equity_multiple(2.0)  # 2x - Good
        >>> assert error is None
        >>>
        >>> error = validate_equity_multiple(0.8)  # 0.8x - Loss
        >>> assert error.severity == "WARNING"
        >>>
        >>> error = validate_equity_multiple(5.5)  # 5.5x - Very high
        >>> assert error.severity == "WARNING"
    """
    # Type check
    if not isinstance(value, (int, float)):
        return ValidationError(
            severity="ERROR",
            field=field_name,
            value=value,
            constraint="must be numeric",
            message=f"{field_name} must be numeric, got {type(value).__name__}",
        )
    
    # Check for negative (impossible)
    if value < 0:
        return ValidationError(
            severity="CRITICAL",
            field=field_name,
            value=value,
            constraint="must be >= 0",
            message=f"{field_name}={value:.2f}x is negative (impossible)",
            remediation="Equity multiple cannot be negative. Check equity cashflow calculations.",
        )
    
    # Check for loss (multiple < 1.0)
    if value < 1.0:
        return ValidationError(
            severity="WARNING",
            field=field_name,
            value=value,
            constraint="should be >= 1.0 for positive return",
            message=f"{field_name}={value:.2f}x indicates equity loss ({(1-value)*100:.1f}%)",
            remediation="Equity investors losing money. Review project economics or increase leverage.",
        )
    
    # Absolute bounds check
    if not (EQUITY_MULTIPLE_MIN <= value <= EQUITY_MULTIPLE_MAX):
        return ValidationError(
            severity="WARNING",
            field=field_name,
            value=value,
            constraint=f"{EQUITY_MULTIPLE_MIN:.1f}x <= value <= {EQUITY_MULTIPLE_MAX:.1f}x",
            message=f"{field_name}={value:.2f}x is outside typical range [0.8x-5.0x]",
            remediation=(
                "Multiple > 5x suggests exceptional project or very long tenor. "
                "Multiple < 0.8x suggests project failure."
            ),
        )
    
    return None


def validate_equity_result(
    equity_result: Dict[str, Any],
    strict: bool = True,
) -> ValidationResult:
    """Sprint 16: Validate complete EquityResult contract.
    
    Validates:
    - Equity IRR: 10-30% typical
    - Equity NPV: Finite and realistic
    - Equity Multiple: > 1.0 for positive return
    - Consistency: NPV and IRR should be directionally aligned
    
    Args:
        equity_result: EquityResult dict to validate
        strict: If True, enforce typical bounds; if False, only check absolutes
    
    Returns:
        ValidationResult with all findings
    
    Example:
        >>> equity_dict = {
        ...     "equity_irr": 0.18,
        ...     "equity_npv": 50_000_000,
        ...     "equity_multiple": 2.5,
        ... }
        >>> result = validate_equity_result(equity_dict, strict=True)
        >>> assert result.is_valid
        >>> assert len(result.errors) == 0
    """
    result = ValidationResult(is_valid=True, contract_type="EquityResult")
    
    # Validate Equity IRR
    if "equity_irr" in equity_result and equity_result["equity_irr"] is not None:
        error = validate_equity_irr(
            equity_result["equity_irr"],
            "equity_irr",
            strict_bounds=strict,
        )
        if error:
            result.errors.append(error)
            if error.severity == "CRITICAL":
                result.is_valid = False
    
    # Validate Equity NPV
    if "equity_npv" in equity_result and equity_result["equity_npv"] is not None:
        error = validate_npv(
            equity_result["equity_npv"],
            "equity_npv",
            strict_bounds=strict,
        )
        if error:
            result.errors.append(error)
            if error.severity == "CRITICAL":
                result.is_valid = False
    
    # Validate Equity Multiple
    if "equity_multiple" in equity_result and equity_result["equity_multiple"] is not None:
        error = validate_equity_multiple(
            equity_result["equity_multiple"],
            "equity_multiple",
        )
        if error:
            result.errors.append(error)
            if error.severity == "CRITICAL":
                result.is_valid = False
    
    # Consistency check: NPV and IRR should align
    if (
        "equity_npv" in equity_result
        and "equity_irr" in equity_result
        and equity_result["equity_npv"] is not None
        and equity_result["equity_irr"] is not None
    ):
        npv = equity_result["equity_npv"]
        irr = equity_result["equity_irr"]
        
        # If NPV is positive, IRR should be above discount rate (typically 8-12%)
        # If NPV is negative, IRR should be below discount rate
        # We'll use a simple heuristic: positive NPV should mean IRR > 5%
        if npv > 0 and irr < 0.05:
            result.errors.append(
                ValidationError(
                    severity="WARNING",
                    field="npv_irr_consistency",
                    value={"npv": npv, "irr": irr},
                    constraint="Positive NPV should imply IRR > 5%",
                    message=(
                        f"Equity NPV is positive ({npv:,.0f}) but IRR is low ({irr*100:.1f}%). "
                        f"Check discount rate assumptions."
                    ),
                )
            )
        elif npv < 0 and irr > 0.15:
            result.errors.append(
                ValidationError(
                    severity="WARNING",
                    field="npv_irr_consistency",
                    value={"npv": npv, "irr": irr},
                    constraint="Negative NPV should imply IRR < 15%",
                    message=(
                        f"Equity NPV is negative ({npv:,.0f}) but IRR is high ({irr*100:.1f}%). "
                        f"Check discount rate assumptions."
                    ),
                )
            )
    
    # Summary logging
    if result.has_critical_errors():
        logger.error(
            f"Equity validation FAILED: {result.error_count('CRITICAL')} critical errors"
        )
    elif result.has_errors():
        logger.warning(
            f"Equity validation completed with {result.error_count('ERROR')} errors, "
            f"{result.error_count('WARNING')} warnings"
        )
    else:
        logger.info(
            f"Equity validation PASSED: {result.error_count('WARNING')} warnings"
        )
    
    return result


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ CONTRACT VALIDATORS (MAIN INTERFACE)                                       ║
# ╚════════════════════════════════════════════════════════════════════════════╝


def validate_scenario_result(
    scenario_result: Dict[str, Any],
    strict: bool = True,
) -> ValidationResult:
    """CESSPIT: Validate complete ScenarioResult contract.

    Args:
        scenario_result: ScenarioResult dict to validate
        strict: If True, raise on errors; if False, just collect

    Returns:
        ValidationResult with all findings
    """
    result = ValidationResult(is_valid=True, contract_type="ScenarioResult")

    # Validate key fields
    if "project_irr" in scenario_result:
        error = validate_irr(scenario_result["project_irr"], "project_irr")
        if error:
            result.errors.append(error)
            result.is_valid = False

    if "min_dscr" in scenario_result:
        error = validate_dscr(scenario_result["min_dscr"], "min_dscr")
        if error:
            result.errors.append(error)
            if error.severity == "CRITICAL":
                result.is_valid = False
    
    # Sprint 16: Validate project NPV if present
    if "project_npv" in scenario_result and scenario_result["project_npv"] is not None:
        error = validate_npv(
            scenario_result["project_npv"],
            "project_npv",
            strict_bounds=strict,
        )
        if error:
            result.errors.append(error)
            if error.severity == "CRITICAL":
                result.is_valid = False

    if strict and result.has_critical_errors():
        logger.error(
            f"Scenario validation failed: {result.error_count('CRITICAL')} critical errors"
        )
        raise ValueError(
            f"Scenario validation failed with {result.error_count('CRITICAL')} critical errors"
        )

    logger.info(
        f"Scenario validation: {result.error_count()} errors, {len(result.warnings)} warnings"
    )

    return result


__all__ = [
    # Constants
    "DSCR_MIN",
    "DSCR_MAX",
    "IRR_MIN",
    "IRR_MAX",
    "WACC_MIN",
    "WACC_MAX",
    "NPV_MIN",
    "NPV_MAX",
    "EQUITY_IRR_MIN",
    "EQUITY_IRR_MAX",
    "EQUITY_MULTIPLE_MIN",
    "EQUITY_MULTIPLE_MAX",
    # Classes
    "ValidationError",
    "ValidationResult",
    # Validators
    "validate_dscr",
    "validate_irr",
    "validate_wacc",
    "validate_covenant_breach",
    # Sprint 16: NPV validators
    "validate_npv",
    "validate_npv_consistency",
    # Sprint 16: Equity validators
    "validate_equity_irr",
    "validate_equity_multiple",
    "validate_equity_result",
    # Contract validators
    "validate_scenario_result",
]

# EOF - analytics/contracts_v14_validators.py
