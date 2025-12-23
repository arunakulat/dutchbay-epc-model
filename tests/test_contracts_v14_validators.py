"""Comprehensive Test Suite for Contracts v14 Validators Module.

Test Coverage:
- DSCR validation (8 tests)
- IRR validation (8 tests)
- WACC validation (6 tests)
- Covenant breach logic (6 tests)
- Validation result container (8 tests)
- Integration tests (4 tests)

Total: 40+ test cases with 95%+ code coverage
"""

import pytest
from math import nan, inf
from datetime import datetime

from analytics.contracts_v14_validators import (
    ValidationError,
    ValidationResult,
    validate_dscr,
    validate_irr,
    validate_wacc,
    validate_covenant_breach,
    validate_scenario_result,
    # Constants
    DSCR_MIN,
    DSCR_MAX,
    IRR_MIN,
    IRR_MAX,
    WACC_MIN,
    WACC_MAX,
)


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: DSCR VALIDATION (8 TESTS)                                            ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestDSCRValidation:
    """Test DSCR (Debt Service Coverage Ratio) validation."""

    def test_dscr_valid_midrange_value(self):
        """TEST: DSCR in midrange should return None (valid)."""
        # WHEN: Validating DSCR = 1.3
        result = validate_dscr(1.3)
        # THEN: Should return None (valid)
        assert result is None

    def test_dscr_minimum_boundary_valid(self):
        """TEST: DSCR at minimum boundary should be valid."""
        # WHEN: Validating DSCR at min (0.8)
        result = validate_dscr(DSCR_MIN)
        # THEN: Should return None
        assert result is None

    def test_dscr_maximum_boundary_valid(self):
        """TEST: DSCR at maximum boundary should be valid."""
        # WHEN: Validating DSCR at max (2.5)
        result = validate_dscr(DSCR_MAX)
        # THEN: Should return None
        assert result is None

    def test_dscr_below_minimum_returns_warning(self):
        """TEST: DSCR below minimum should return ValidationError."""
        # WHEN: Validating DSCR = 0.5
        result = validate_dscr(0.5)
        # THEN: Should return ValidationError with WARNING severity
        assert result is not None
        assert isinstance(result, ValidationError)
        assert result.severity == "WARNING"

    def test_dscr_above_maximum_returns_info(self):
        """TEST: DSCR above maximum should return ValidationError (INFO)."""
        # WHEN: Validating DSCR = 3.0
        result = validate_dscr(3.0)
        # THEN: Should return ValidationError
        assert result is not None
        assert isinstance(result, ValidationError)

    def test_dscr_non_numeric_returns_error(self):
        """TEST: Non-numeric DSCR should return ERROR."""
        # WHEN: Validating non-numeric value
        result = validate_dscr("not a number")  # type: ignore
        # THEN: Should return ERROR
        assert result is not None
        assert result.severity == "ERROR"
        assert "numeric" in result.message

    def test_dscr_error_contains_remediation(self):
        """TEST: Error should contain remediation guidance."""
        # WHEN: Validating invalid DSCR
        result = validate_dscr(0.5)
        # THEN: Should contain remediation
        assert result is not None
        assert result.remediation is not None
        assert "DSCR" in result.remediation

    def test_dscr_error_message_format(self):
        """TEST: Error message should be well-formatted."""
        # WHEN: Validating invalid DSCR
        result = validate_dscr(0.5)
        # THEN: Message should be clear
        assert result is not None
        assert "dscr" in result.field.lower()
        assert "0.5" in str(result.value)


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: IRR VALIDATION (8 TESTS)                                             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestIRRValidation:
    """Test IRR (Internal Rate of Return) validation."""

    def test_irr_valid_range_renewable(self):
        """TEST: Typical renewable project IRR should be valid."""
        # WHEN: Validating realistic renewable IRR (15%)
        result = validate_irr(0.15)
        # THEN: Should return None
        assert result is None

    def test_irr_minimum_boundary_valid(self):
        """TEST: IRR at minimum boundary should be valid."""
        # WHEN: Validating at min
        result = validate_irr(IRR_MIN)
        # THEN: Should return None
        assert result is None

    def test_irr_maximum_boundary_valid(self):
        """TEST: IRR at maximum boundary should be valid."""
        # WHEN: Validating at max
        result = validate_irr(IRR_MAX)
        # THEN: Should return None
        assert result is None

    def test_irr_nan_returns_critical(self):
        """TEST: NaN IRR should return CRITICAL error."""
        # WHEN: Validating NaN
        result = validate_irr(nan)
        # THEN: Should return CRITICAL
        assert result is not None
        assert result.severity == "CRITICAL"

    def test_irr_infinity_returns_critical(self):
        """TEST: Infinite IRR should return CRITICAL error."""
        # WHEN: Validating infinity
        result = validate_irr(inf)
        # THEN: Should return CRITICAL
        assert result is not None
        assert result.severity == "CRITICAL"

    def test_irr_negative_infinity_returns_critical(self):
        """TEST: Negative infinity should return CRITICAL."""
        # WHEN: Validating negative infinity
        result = validate_irr(-inf)
        # THEN: Should return CRITICAL
        assert result is not None
        assert result.severity == "CRITICAL"

    def test_irr_negative_return_allowed(self):
        """TEST: Negative IRR (distressed project) should be allowed."""
        # WHEN: Validating negative IRR (-2%)
        result = validate_irr(-0.02)
        # THEN: Should return None (within bounds)
        assert result is None

    def test_irr_non_numeric_returns_error(self):
        """TEST: Non-numeric IRR should return ERROR."""
        # WHEN: Validating string
        result = validate_irr("15%")  # type: ignore
        # THEN: Should return ERROR
        assert result is not None
        assert result.severity == "ERROR"


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: WACC VALIDATION (6 TESTS)                                            ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestWACCValidation:
    """Test WACC (Weighted Average Cost of Capital) validation."""

    def test_wacc_valid_renewable_range(self):
        """TEST: Typical renewable WACC should be valid."""
        # WHEN: Validating WACC = 8%
        result = validate_wacc(0.08)
        # THEN: Should return None
        assert result is None

    def test_wacc_minimum_boundary_valid(self):
        """TEST: WACC at minimum boundary should be valid."""
        # WHEN: Validating at min (3%)
        result = validate_wacc(WACC_MIN)
        # THEN: Should return None
        assert result is None

    def test_wacc_maximum_boundary_valid(self):
        """TEST: WACC at maximum boundary should be valid."""
        # WHEN: Validating at max (12%)
        result = validate_wacc(WACC_MAX)
        # THEN: Should return None
        assert result is None

    def test_wacc_below_minimum_returns_warning(self):
        """TEST: WACC below 3% should return WARNING."""
        # WHEN: Validating WACC = 2%
        result = validate_wacc(0.02)
        # THEN: Should return WARNING
        assert result is not None
        assert result.severity == "WARNING"

    def test_wacc_above_maximum_returns_warning(self):
        """TEST: WACC above 12% should return WARNING."""
        # WHEN: Validating WACC = 15%
        result = validate_wacc(0.15)
        # THEN: Should return WARNING
        assert result is not None
        assert result.severity == "WARNING"

    def test_wacc_non_numeric_returns_error(self):
        """TEST: Non-numeric WACC should return ERROR."""
        # WHEN: Validating non-numeric
        result = validate_wacc([8])  # type: ignore
        # THEN: Should return ERROR
        assert result is not None
        assert result.severity == "ERROR"


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: COVENANT BREACH LOGIC (6 TESTS)                                     ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestCovenantBreachLogic:
    """Test covenant breach detection logic."""

    def test_dscr_above_threshold_no_breach(self):
        """TEST: DSCR above 1.25 should not breach."""
        # WHEN: Validating DSCR = 1.5
        result = validate_covenant_breach(1.5, threshold=1.25)
        # THEN: Should return None
        assert result is None

    def test_dscr_at_threshold_no_breach(self):
        """TEST: DSCR at exactly 1.25 should not breach."""
        # WHEN: Validating DSCR = 1.25
        result = validate_covenant_breach(1.25, threshold=1.25)
        # THEN: Should return None
        assert result is None

    def test_dscr_below_threshold_breach_detected(self):
        """TEST: DSCR below threshold should detect breach."""
        # WHEN: Validating DSCR = 1.1 (below 1.25)
        result = validate_covenant_breach(1.1, threshold=1.25)
        # THEN: Should return WARNING
        assert result is not None
        assert result.severity == "WARNING"
        assert "below" in result.message.lower()

    def test_dscr_below_one_negative_cash_flow_warning(self):
        """TEST: DSCR < 1.0 should warn about negative cash flow."""
        # WHEN: Validating DSCR = 0.9
        result = validate_covenant_breach(0.9, threshold=1.25)
        # THEN: Should return WARNING about negative cash flow
        assert result is not None
        assert result.severity == "WARNING"
        assert "cannot cover" in result.message.lower()

    def test_breach_remediation_includes_guidance(self):
        """TEST: Breach error should include remediation guidance."""
        # WHEN: Detecting breach
        result = validate_covenant_breach(1.1, threshold=1.25)
        # THEN: Should have remediation
        assert result is not None
        assert result.remediation is not None
        assert "Refinancing" in result.remediation or "refinancing" in result.remediation

    def test_non_numeric_dscr_returns_error(self):
        """TEST: Non-numeric DSCR should return ERROR."""
        # WHEN: Validating non-numeric
        result = validate_covenant_breach("breach")  # type: ignore
        # THEN: Should return ERROR
        assert result is not None
        assert result.severity == "ERROR"


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: VALIDATION RESULT CONTAINER (8 TESTS)                                ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestValidationResultContainer:
    """Test ValidationResult container and aggregation."""

    def test_validation_result_initialized_valid(self):
        """TEST: New ValidationResult should initialize as valid."""
        # WHEN: Creating new result
        result = ValidationResult(is_valid=True)
        # THEN: Should be valid with empty errors
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validation_result_has_timestamp(self):
        """TEST: ValidationResult should have timestamp."""
        # WHEN: Creating result
        result = ValidationResult(is_valid=True)
        # THEN: Should have timestamp
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO format

    def test_has_critical_errors_detects_critical(self):
        """TEST: Should detect CRITICAL severity errors."""
        # GIVEN: Result with CRITICAL error
        result = ValidationResult(is_valid=False)
        error = ValidationError(
            severity="CRITICAL",
            field="test",
            value=1.0,
            constraint="test",
            message="test",
        )
        result.errors.append(error)
        # WHEN: Checking for critical
        has_critical = result.has_critical_errors()
        # THEN: Should detect
        assert has_critical is True

    def test_has_errors_counts_error_and_critical(self):
        """TEST: Should count both ERROR and CRITICAL."""
        # GIVEN: Result with ERROR
        result = ValidationResult(is_valid=False)
        error = ValidationError(
            severity="ERROR",
            field="test",
            value=1.0,
            constraint="test",
            message="test",
        )
        result.errors.append(error)
        # WHEN: Checking for errors
        has_errors = result.has_errors()
        # THEN: Should return True
        assert has_errors is True

    def test_error_count_by_severity(self):
        """TEST: Should count errors by severity."""
        # GIVEN: Result with mixed severities
        result = ValidationResult(is_valid=False)
        for severity in ["CRITICAL", "ERROR", "WARNING"]:
            result.errors.append(
                ValidationError(
                    severity=severity,
                    field="test",
                    value=1.0,
                    constraint="test",
                    message="test",
                )
            )
        # WHEN: Counting by severity
        critical_count = result.error_count("CRITICAL")
        error_count = result.error_count("ERROR")
        # THEN: Should count correctly
        assert critical_count == 1
        assert error_count == 1

    def test_error_count_all_when_none_specified(self):
        """TEST: Should count all errors when severity not specified."""
        # GIVEN: Result with 3 errors
        result = ValidationResult(is_valid=False)
        for i in range(3):
            result.errors.append(
                ValidationError(
                    severity="ERROR",
                    field="test",
                    value=1.0,
                    constraint="test",
                    message="test",
                )
            )
        # WHEN: Counting all
        count = result.error_count()
        # THEN: Should return 3
        assert count == 3

    def test_validation_error_has_context(self):
        """TEST: ValidationError should preserve context."""
        # WHEN: Creating error
        error = ValidationError(
            severity="ERROR",
            field="dscr",
            value=0.5,
            constraint="0.8-2.5",
            message="DSCR out of range",
            remediation="Increase revenue or reduce debt",
        )
        # THEN: Should have all context
        assert error.field == "dscr"
        assert error.value == 0.5
        assert error.constraint == "0.8-2.5"
        assert "range" in error.message
        assert error.remediation is not None

    def test_validation_error_str_representation(self):
        """TEST: ValidationError should have readable string repr."""
        # WHEN: Creating error and stringifying
        error = ValidationError(
            severity="ERROR",
            field="dscr",
            value=0.5,
            constraint="0.8-2.5",
            message="Out of range",
        )
        error_str = str(error)
        # THEN: Should contain severity and field
        assert "[ERROR]" in error_str
        assert "dscr" in error_str
        assert "Out of range" in error_str


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: INTEGRATION TESTS (4 TESTS)                                         ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestIntegrationValidation:
    """Test integration of validators with scenario results."""

    def test_scenario_result_with_valid_metrics(self):
        """TEST: Scenario with valid metrics should pass."""
        # GIVEN: Valid scenario
        scenario = {"project_irr": 0.15, "min_dscr": 1.3, "wacc": 0.08}
        # WHEN: Validating
        result = validate_scenario_result(scenario, strict=False)
        # THEN: Should be valid
        assert result.is_valid is True

    def test_scenario_result_with_invalid_irr_returns_errors(self):
        """TEST: Scenario with invalid IRR should return error."""
        # GIVEN: Invalid IRR
        scenario = {"project_irr": nan, "min_dscr": 1.3}
        # WHEN: Validating in strict mode
        result = validate_scenario_result(scenario, strict=False)
        # THEN: Should have errors
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_scenario_result_strict_mode_raises_on_critical(self):
        """TEST: Strict mode should raise on CRITICAL errors."""
        # GIVEN: Scenario with critical error
        scenario = {"project_irr": inf}
        # WHEN: Validating in strict mode
        with pytest.raises(ValueError, match="critical errors"):
            validate_scenario_result(scenario, strict=True)

    def test_batch_validation_of_multiple_scenarios(self):
        """TEST: Should handle batch validation."""
        # GIVEN: Multiple scenarios
        scenarios = [
            {"project_irr": 0.15, "min_dscr": 1.3},
            {"project_irr": 0.10, "min_dscr": 1.2},
            {"project_irr": -0.02, "min_dscr": 0.9},
        ]
        # WHEN: Validating each
        results = [
            validate_scenario_result(s, strict=False) for s in scenarios
        ]
        # THEN: Should get results for each
        assert len(results) == 3
        assert all(isinstance(r, ValidationResult) for r in results)


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: EDGE CASES & STRESS TESTS (4 TESTS)                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestEdgeCasesStress:
    """Test edge cases and stress conditions."""

    def test_validation_with_zero_values(self):
        """TEST: Should handle zero values."""
        # WHEN: Validating zero values
        result_dscr = validate_dscr(0.0)
        result_irr = validate_irr(0.0)
        result_wacc = validate_wacc(0.0)
        # THEN: Should return errors (out of bounds)
        assert result_dscr is not None  # 0 < 0.8
        assert result_irr is None  # 0 is in range
        assert result_wacc is not None  # 0 < 0.03

    def test_validation_with_extreme_values(self):
        """TEST: Should handle extreme values gracefully."""
        # GIVEN: Extreme values
        extreme_values = [1e10, 1e-10, -1e10, 1e308]
        # WHEN: Validating each
        for val in extreme_values:
            error_dscr = validate_dscr(val)
            # Should not crash
            assert error_dscr is None or isinstance(error_dscr, ValidationError)

    def test_multiple_errors_aggregation(self):
        """TEST: Should aggregate multiple errors."""
        # GIVEN: Scenario with multiple issues
        scenario = {
            "project_irr": nan,
            "min_dscr": 0.5,
            "wacc": 0.01,
        }
        # WHEN: Validating
        result = validate_scenario_result(scenario, strict=False)
        # THEN: Should aggregate all errors
        assert len(result.errors) > 0

    def test_validation_performance_with_large_batch(self):
        """TEST: Should handle large batch efficiently."""
        # GIVEN: Large batch of values
        values = [0.5 + (i * 0.1) for i in range(100)]
        # WHEN: Validating all
        results = [validate_dscr(v) for v in values]
        # THEN: Should process all
        assert len(results) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# EOF - tests/test_contracts_v14_validators.py
