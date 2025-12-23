"""Enhanced Schema Guard - CESSPIT-Compliant Config Validation.

CESSPIT Pattern (Config-Enabled Schema Safety Pre-Ingress Testing):
- Pre-flight validation BEFORE execution
- Fail-fast on any violation
- Comprehensive error reporting
- Defensive rehydration support
- Full audit trail

Usage:
    from analytics.schema_guard_enhanced import validate_config_enhanced

    validate_config_enhanced(
        raw_config=config,
        config_path='scenarios/base.yaml',
        modules=['cashflow', 'debt', 'wacc'],
        fail_fast=True,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ValidationErrorSeverity(Enum):
    """CESSPIT: Severity levels for validation failures."""

    CRITICAL = "CRITICAL"  # Config unusable
    ERROR = "ERROR"  # Feature disabled
    WARNING = "WARNING"  # Degraded mode
    INFO = "INFO"  # Informational


@dataclass
class ValidationViolation:
    """CESSPIT: Single validation violation with full context."""

    severity: ValidationErrorSeverity
    module: str
    field_path: str  # Dot-notation path in config
    value: Any
    expected: str  # Description of expected value/type
    actual: str  # Description of actual value/type
    message: str
    remediation: Optional[str] = None
    timestamp: Optional[str] = None

    def __str__(self) -> str:
        """Human-readable violation format."""
        return (
            f"[{self.severity.value}] {self.module}/{self.field_path}: "
            f"{self.message} (got {self.actual}, expected {self.expected})"
        )


class SchemaGuardError(Exception):
    """CESSPIT: Raised when schema validation fails."""

    def __init__(
        self,
        violations: list[ValidationViolation],
        config_path: str,
    ):
        self.violations = violations
        self.config_path = config_path

        critical_count = sum(
            1 for v in violations if v.severity == ValidationErrorSeverity.CRITICAL
        )
        error_count = sum(
            1 for v in violations if v.severity == ValidationErrorSeverity.ERROR
        )

        message = (
            f"Schema validation failed for {config_path}: "
            f"{critical_count} CRITICAL, {error_count} ERROR violations\n"
        )

        for v in violations[:10]:  # Show first 10
            message += f"  {v}\n"

        if len(violations) > 10:
            message += f"  ... and {len(violations) - 10} more violations\n"

        super().__init__(message)


class ConfigValidator:
    """CESSPIT: Comprehensive config validation engine."""

    def __init__(
        self,
        config_path: str,
        fail_fast: bool = True,
        audit_trail: bool = True,
    ):
        self.config_path = config_path
        self.fail_fast = fail_fast
        self.audit_trail = audit_trail
        self.violations: list[ValidationViolation] = []
        self.audit_log: list[str] = []

    def _log_audit(self, message: str) -> None:
        """Log to audit trail."""
        if self.audit_trail:
            self.audit_log.append(message)
            logger.debug("[AUDIT] %s", message)

    def _add_violation(
        self,
        severity: ValidationErrorSeverity,
        module: str,
        field_path: str,
        value: Any,
        expected: str,
        actual: str,
        message: str,
        remediation: Optional[str] = None,
    ) -> None:
        """Record a validation violation."""
        violation = ValidationViolation(
            severity=severity,
            module=module,
            field_path=field_path,
            value=value,
            expected=expected,
            actual=actual,
            message=message,
            remediation=remediation,
        )

        self.violations.append(violation)
        self._log_audit(str(violation))

        if self.fail_fast and severity == ValidationErrorSeverity.CRITICAL:
            raise SchemaGuardError(self.violations, self.config_path)

    def _validate_type(
        self,
        module: str,
        field_path: str,
        value: Any,
        expected_type: type | tuple[type, ...],
        allow_none: bool = False,
    ) -> bool:
        """Validate field type.

        Parameters
        ----------
        module : str
            Module name
        field_path : str
            Dot-notation path in config
        value : any
            Value to validate
        expected_type : type or tuple[type, ...]
            Expected type(s)
        allow_none : bool
            If True, None is valid

        Returns
        -------
        bool
            True if valid, False otherwise
        """
        if value is None and allow_none:
            return True

        if not isinstance(value, expected_type):
            if isinstance(expected_type, tuple):
                expected_str = " or ".join(t.__name__ for t in expected_type)
            else:
                expected_str = expected_type.__name__

            self._add_violation(
                severity=ValidationErrorSeverity.ERROR,
                module=module,
                field_path=field_path,
                value=value,
                expected=expected_str,
                actual=type(value).__name__,
                message=f"Type mismatch at {field_path}",
            )
            return False

        return True

    def _validate_range(
        self,
        module: str,
        field_path: str,
        value: float | int,
        min_val: Optional[float | int] = None,
        max_val: Optional[float | int] = None,
        exclusive_min: bool = False,
        exclusive_max: bool = False,
    ) -> bool:
        """Validate numeric range.

        Parameters
        ----------
        module : str
            Module name
        field_path : str
            Dot-notation path
        value : float or int
            Value to check
        min_val : float or int, optional
            Minimum allowed value
        max_val : float or int, optional
            Maximum allowed value
        exclusive_min : bool
            If True, min is exclusive (>) not inclusive (>=)
        exclusive_max : bool
            If True, max is exclusive (<) not inclusive (<=)

        Returns
        -------
        bool
            True if in range, False otherwise
        """
        if not isinstance(value, (int, float)):
            return False

        if min_val is not None:
            if exclusive_min and value <= min_val:
                self._add_violation(
                    severity=ValidationErrorSeverity.ERROR,
                    module=module,
                    field_path=field_path,
                    value=value,
                    expected=f"> {min_val}",
                    actual=f"{value}",
                    message=f"Value must be > {min_val}",
                )
                return False
            elif not exclusive_min and value < min_val:
                self._add_violation(
                    severity=ValidationErrorSeverity.ERROR,
                    module=module,
                    field_path=field_path,
                    value=value,
                    expected=f">= {min_val}",
                    actual=f"{value}",
                    message=f"Value must be >= {min_val}",
                )
                return False

        if max_val is not None:
            if exclusive_max and value >= max_val:
                self._add_violation(
                    severity=ValidationErrorSeverity.ERROR,
                    module=module,
                    field_path=field_path,
                    value=value,
                    expected=f"< {max_val}",
                    actual=f"{value}",
                    message=f"Value must be < {max_val}",
                )
                return False
            elif not exclusive_max and value > max_val:
                self._add_violation(
                    severity=ValidationErrorSeverity.ERROR,
                    module=module,
                    field_path=field_path,
                    value=value,
                    expected=f"<= {max_val}",
                    actual=f"{value}",
                    message=f"Value must be <= {max_val}",
                )
                return False

        return True

    def _get_nested(
        self,
        obj: dict[str, Any],
        path: list[str],
        default: Any = None,
    ) -> tuple[Any, str]:
        """Get nested value with path tracking.

        Returns
        -------
        tuple[Any, str]
            (value, path_str) where path_str is dot-notation
        """
        current = obj
        for part in path:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default, ".".join(path)

        return current, ".".join(path)

    def validate_cashflow_module(self, config: dict[str, Any]) -> None:
        """CESSPIT: Validate cashflow configuration.

        Parameters
        ----------
        config : dict[str, Any]
            Raw configuration
        """
        self._log_audit("[CASHFLOW] Validation starting")

        module = "cashflow"

        # Project life (years)
        project_life, path = self._get_nested(config, ["Project", "life_years"])
        if project_life is not None:
            self._validate_type(module, path, project_life, (int, float))
            self._validate_range(module, path, project_life, min_val=5, max_val=50)
        else:
            self._add_violation(
                severity=ValidationErrorSeverity.CRITICAL,
                module=module,
                field_path="Project.life_years",
                value=None,
                expected="integer",
                actual="missing",
                message="Missing required field: Project.life_years",
                remediation="Add Project.life_years (5-50 years)",
            )

        # Capex
        capex, path = self._get_nested(config, ["Project", "capex_usd"])
        if capex is not None:
            self._validate_type(module, path, capex, (int, float))
            self._validate_range(module, path, capex, min_val=0, exclusive_min=True)
        else:
            self._add_violation(
                severity=ValidationErrorSeverity.CRITICAL,
                module=module,
                field_path="Project.capex_usd",
                value=None,
                expected="float > 0",
                actual="missing",
                message="Missing required field: Project.capex_usd",
            )

        self._log_audit("[CASHFLOW] Validation complete")

    def validate_debt_module(self, config: dict[str, Any]) -> None:
        """CESSPIT: Validate debt configuration.

        Parameters
        ----------
        config : dict[str, Any]
            Raw configuration
        """
        self._log_audit("[DEBT] Validation starting")

        module = "debt"

        # Debt-to-capex ratio
        debt_usd, debt_path = self._get_nested(
            config, ["Financing_Terms", "total_debt_usd"]
        )
        capex_usd, capex_path = self._get_nested(config, ["Project", "capex_usd"])

        if debt_usd is not None and capex_usd is not None:
            self._validate_type(module, debt_path, debt_usd, (int, float))

            debt_to_capex = float(debt_usd) / float(capex_usd) if capex_usd > 0 else 0
            if debt_to_capex > 0.85:
                self._add_violation(
                    severity=ValidationErrorSeverity.WARNING,
                    module=module,
                    field_path=debt_path,
                    value=debt_usd,
                    expected="<= 85% of capex",
                    actual=f"{debt_to_capex * 100:.1f}% of capex",
                    message="High leverage: debt > 85% of capex",
                    remediation="Consider reducing debt or increasing capex",
                )

        # Tenor years
        tenor, path = self._get_nested(config, ["Financing_Terms", "tenor_years"])
        if tenor is not None:
            self._validate_type(module, path, tenor, (int, float))
            self._validate_range(module, path, tenor, min_val=5, max_val=25)

        # Target DSCR
        dscr, path = self._get_nested(config, ["Financing_Terms", "target_dscr"])
        if dscr is not None:
            self._validate_type(module, path, dscr, (int, float))
            self._validate_range(module, path, dscr, min_val=1.0, max_val=2.0)

        self._log_audit("[DEBT] Validation complete")

    def validate_wacc_module(self, config: dict[str, Any]) -> None:
        """CESSPIT: Validate WACC configuration.

        Parameters
        ----------
        config : dict[str, Any]
            Raw configuration
        """
        self._log_audit("[WACC] Validation starting")

        module = "wacc"

        # WACC mode
        mode, path = self._get_nested(config, ["WACC", "mode"])
        if mode is not None:
            allowed_modes = {"capm", "blended", "prudential"}
            if str(mode).lower() not in allowed_modes:
                self._add_violation(
                    severity=ValidationErrorSeverity.ERROR,
                    module=module,
                    field_path=path,
                    value=mode,
                    expected=f"one of {allowed_modes}",
                    actual=str(mode),
                    message=f"Invalid WACC mode: {mode}",
                )

        # Risk-free rate
        rfr, path = self._get_nested(config, ["WACC", "risk_free_rate"])
        if rfr is not None:
            self._validate_type(module, path, rfr, (int, float))
            self._validate_range(module, path, rfr, min_val=0, max_val=0.05)

        self._log_audit("[WACC] Validation complete")

    def validate(
        self,
        config: dict[str, Any],
        modules: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute full validation.

        Parameters
        ----------
        config : dict[str, Any]
            Raw configuration
        modules : list[str] or None
            Modules to validate. Defaults to all.

        Returns
        -------
        dict[str, Any]
            Validation report with violations and audit log

        Raises
        ------
        SchemaGuardError
            If CRITICAL violations found and fail_fast=True
        """
        if modules is None:
            modules = ["cashflow", "debt", "wacc"]

        self._log_audit(f"Starting validation: modules={modules}")

        # Validate each module
        if "cashflow" in modules:
            self.validate_cashflow_module(config)

        if "debt" in modules:
            self.validate_debt_module(config)

        if "wacc" in modules:
            self.validate_wacc_module(config)

        self._log_audit(
            f"Validation complete: {len(self.violations)} violations, "
            f"{len(self.audit_log)} audit entries"
        )

        # Check for critical violations
        critical_violations = [
            v for v in self.violations if v.severity == ValidationErrorSeverity.CRITICAL
        ]

        if critical_violations and self.fail_fast:
            raise SchemaGuardError(self.violations, self.config_path)

        return {
            "status": "valid" if not critical_violations else "invalid",
            "violations": self.violations,
            "audit_log": self.audit_log,
            "critical_count": len(critical_violations),
            "error_count": len(
                [
                    v
                    for v in self.violations
                    if v.severity == ValidationErrorSeverity.ERROR
                ]
            ),
        }


def validate_config_enhanced(
    raw_config: dict[str, Any],
    config_path: str,
    modules: list[str] | None = None,
    fail_fast: bool = True,
) -> dict[str, Any]:
    """CESSPIT: Enhanced config validation entry point.

    Parameters
    ----------
    raw_config : dict[str, Any]
        Raw configuration from YAML/JSON
    config_path : str
        Path to config file (for logging)
    modules : list[str] or None
        Modules to validate
    fail_fast : bool
        If True, raise on CRITICAL violations

    Returns
    -------
    dict[str, Any]
        Validation report

    Raises
    ------
    SchemaGuardError
        If CRITICAL violations found and fail_fast=True
    """
    validator = ConfigValidator(
        config_path=config_path,
        fail_fast=fail_fast,
        audit_trail=True,
    )

    return validator.validate(raw_config, modules)


__all__ = [
    "validate_config_enhanced",
    "ConfigValidator",
    "ValidationViolation",
    "ValidationErrorSeverity",
    "SchemaGuardError",
]
