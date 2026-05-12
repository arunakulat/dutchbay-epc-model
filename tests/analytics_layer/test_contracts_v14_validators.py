"""Regression tests for analytics/contracts_v14_validators.py.

Tests Sprint 16 additions:
- validate_npv() and validate_npv_consistency()
- validate_equity_irr(), validate_equity_multiple()
- validate_equity_result()

Framework Compliance:
- GWTF: Evidence-based testing with real pipeline outputs
- CESSPIT: Tests config-driven bounds and fail-fast
- CASPER: Validates all Pydantic V2 contracts
- CCCDIR: Single responsibility - validation only
"""

from __future__ import annotations

import math

import pytest

from analytics.contracts_v14_validators import (
    EQUITY_IRR_MAX,
    EQUITY_IRR_MIN,
    EQUITY_IRR_TYPICAL_MAX,
    EQUITY_IRR_TYPICAL_MIN,
    EQUITY_MULTIPLE_MAX,
    EQUITY_MULTIPLE_MIN,
    NPV_MAX,
    NPV_MIN,
    NPV_TYPICAL_MAX,
    NPV_TYPICAL_MIN,
    ValidationError,
    ValidationResult,
    validate_equity_irr,
    validate_equity_multiple,
    validate_equity_result,
    validate_npv,
    validate_npv_consistency,
)

# ═════════════════════════════════════════════════════════════════════════════
# NPV VALIDATION TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestValidateNPV:
    """Test suite for validate_npv() function."""

    def test_valid_npv_positive(self):
        """Valid positive NPV should return None."""
        error = validate_npv(50_000_000, "project_npv")
        assert error is None

    def test_valid_npv_negative(self):
        """Valid negative NPV should return None (distressed scenarios)."""
        error = validate_npv(-100_000_000, "project_npv")
        assert error is None

    def test_valid_npv_zero(self):
        """NPV of zero should be valid."""
        error = validate_npv(0.0, "project_npv")
        assert error is None

    def test_npv_nan_critical_error(self):
        """NaN NPV should return CRITICAL error."""
        error = validate_npv(float('nan'), "project_npv")
        assert error is not None
        assert error.severity == "CRITICAL"
        assert "NaN" in error.message
        assert "must not be NaN" in error.constraint

    def test_npv_infinity_critical_error(self):
        """Infinite NPV should return CRITICAL error."""
        error = validate_npv(float('inf'), "project_npv")
        assert error is not None
        assert error.severity == "CRITICAL"
        assert "infinite" in error.message
        assert error.remediation is not None

    def test_npv_exceeds_max_bound(self):
        """NPV exceeding absolute max should return CRITICAL error."""
        error = validate_npv(NPV_MAX + 1e9, "project_npv")
        assert error is not None
        assert error.severity == "CRITICAL"
        assert "absolute bounds" in error.message
        assert error.value > NPV_MAX

    def test_npv_below_min_bound(self):
        """NPV below absolute min should return CRITICAL error."""
        error = validate_npv(NPV_MIN - 1e9, "project_npv")
        assert error is not None
        assert error.severity == "CRITICAL"
        assert "absolute bounds" in error.message
        assert error.value < NPV_MIN

    def test_npv_outside_typical_range_strict(self):
        """NPV outside typical range with strict_bounds=True returns WARNING."""
        error = validate_npv(NPV_TYPICAL_MAX + 5e8, "project_npv", strict_bounds=True)
        assert error is not None
        assert error.severity == "WARNING"
        assert "outside typical" in error.message

        error = validate_npv(NPV_TYPICAL_MIN - 5e8, "project_npv", strict_bounds=True)
        assert error is not None
        assert error.severity == "WARNING"
        assert "outside typical" in error.message

    def test_npv_outside_typical_range_not_strict(self):
        """NPV outside typical range with strict_bounds=False returns None."""
        error = validate_npv(NPV_TYPICAL_MAX + 5e8, "project_npv", strict_bounds=False)
        assert error is None

    def test_npv_type_error(self):
        """Non-numeric NPV should return ERROR."""
        error = validate_npv("not_a_number", "project_npv")  # type: ignore
        assert error is not None
        assert error.severity == "ERROR"
        assert "must be numeric" in error.constraint

    def test_npv_field_name_in_error(self):
        """Validation error should include field name."""
        error = validate_npv(float('nan'), "equity_npv")
        assert error is not None
        assert error.field == "equity_npv"
        assert "equity_npv" in error.message


class TestValidateNPVConsistency:
    """Test suite for validate_npv_consistency() function."""

    def test_consistent_npvs(self):
        """Project NPV = Equity NPV + Debt NPV should return None."""
        error = validate_npv_consistency(
            project_npv=100_000_000,
            equity_npv=40_000_000,
            debt_npv=60_000_000,
        )
        assert error is None

    def test_consistent_npvs_zero_debt(self):
        """Project NPV = Equity NPV (debt priced at par) should be valid."""
        error = validate_npv_consistency(
            project_npv=50_000_000,
            equity_npv=50_000_000,
            debt_npv=0.0,
        )
        assert error is None

    def test_npv_inconsistency_exceeds_tolerance(self):
        """Large NPV inconsistency should return WARNING."""
        error = validate_npv_consistency(
            project_npv=100_000_000,
            equity_npv=150_000_000,
            debt_npv=0.0,
        )
        assert error is not None
        assert error.severity == "WARNING"
        assert "inconsistency" in error.message.lower()
        assert "difference" in error.message.lower()

    def test_npv_consistency_within_tolerance(self):
        """NPV difference within 5% tolerance should return None."""
        error = validate_npv_consistency(
            project_npv=100_000_000,
            equity_npv=52_000_000,
            debt_npv=50_000_000,
        )
        assert error is None

    def test_npv_consistency_negative_values(self):
        """Consistency check should work with negative NPVs."""
        error = validate_npv_consistency(
            project_npv=-50_000_000,
            equity_npv=-30_000_000,
            debt_npv=-20_000_000,
        )
        assert error is None


# ═════════════════════════════════════════════════════════════════════════════
# EQUITY IRR VALIDATION TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestValidateEquityIRR:
    """Test suite for validate_equity_irr() function."""

    def test_valid_equity_irr_typical(self):
        """Typical equity IRR (15%) should return None."""
        error = validate_equity_irr(0.15, "equity_irr")
        assert error is None

    def test_valid_equity_irr_high_leverage(self):
        """High equity IRR (40%) due to leverage should return None."""
        error = validate_equity_irr(0.40, "equity_irr", strict_bounds=False)
        assert error is None

    def test_equity_irr_above_typical_warning(self):
        """Equity IRR above typical range with strict=True returns WARNING."""
        error = validate_equity_irr(0.35, "equity_irr", strict_bounds=True)
        assert error is not None
        assert error.severity == "WARNING"
        assert "outside typical range" in error.message

    def test_equity_irr_below_typical_warning(self):
        """Equity IRR below typical range with strict=True returns WARNING."""
        error = validate_equity_irr(0.05, "equity_irr", strict_bounds=True)
        assert error is not None
        assert error.severity == "WARNING"
        assert "outside typical range" in error.message

    def test_equity_irr_nan_critical(self):
        """NaN equity IRR should return CRITICAL error."""
        error = validate_equity_irr(float('nan'), "equity_irr")
        assert error is not None
        assert error.severity == "CRITICAL"
        assert "NaN" in error.message

    def test_equity_irr_infinity_critical(self):
        """Infinite equity IRR should return CRITICAL error."""
        error = validate_equity_irr(float('inf'), "equity_irr")
        assert error is not None
        assert error.severity == "CRITICAL"
        assert "infinite" in error.message

    def test_equity_irr_exceeds_absolute_max(self):
        """Equity IRR exceeding absolute max (60%) should return ERROR."""
        error = validate_equity_irr(0.70, "equity_irr")
        assert error is not None
        assert error.severity == "ERROR"
        assert "absolute bounds" in error.message
        assert error.value > EQUITY_IRR_MAX

    def test_equity_irr_below_absolute_min(self):
        """Equity IRR below absolute min (-10%) should return ERROR."""
        error = validate_equity_irr(-0.15, "equity_irr")
        assert error is not None
        assert error.severity == "ERROR"
        assert "absolute bounds" in error.message
        assert error.value < EQUITY_IRR_MIN

    def test_equity_irr_type_error(self):
        """Non-numeric equity IRR should return ERROR."""
        error = validate_equity_irr("not_a_number", "equity_irr")  # type: ignore
        assert error is not None
        assert error.severity == "ERROR"
        assert "must be numeric" in error.constraint


# ═════════════════════════════════════════════════════════════════════════════
# EQUITY MULTIPLE VALIDATION TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestValidateEquityMultiple:
    """Test suite for validate_equity_multiple() function."""

    def test_valid_equity_multiple_typical(self):
        """Typical equity multiple (2.0x) should return None."""
        error = validate_equity_multiple(2.0, "equity_multiple")
        assert error is None

    def test_valid_equity_multiple_high(self):
        """High equity multiple (4.0x) should return None."""
        error = validate_equity_multiple(4.0, "equity_multiple")
        assert error is None

    def test_equity_multiple_below_one_warning(self):
        """Equity multiple < 1.0 (loss) should return WARNING."""
        error = validate_equity_multiple(0.8, "equity_multiple")
        assert error is not None
        assert error.severity == "WARNING"
        assert "indicates equity loss" in error.message
        assert "losing money" in error.remediation

    def test_equity_multiple_negative_critical(self):
        """Negative equity multiple should return CRITICAL error."""
        error = validate_equity_multiple(-0.5, "equity_multiple")
        assert error is not None
        assert error.severity == "CRITICAL"
        assert "negative" in error.message.lower()

    def test_equity_multiple_exceeds_max_warning(self):
        """Equity multiple > 5.0x should return WARNING."""
        error = validate_equity_multiple(6.0, "equity_multiple")
        assert error is not None
        assert error.severity == "WARNING"
        assert "outside typical range" in error.message

    def test_equity_multiple_type_error(self):
        """Non-numeric equity multiple should return ERROR."""
        error = validate_equity_multiple("not_a_number", "equity_multiple")  # type: ignore
        assert error is not None
        assert error.severity == "ERROR"
        assert "must be numeric" in error.constraint


# ═════════════════════════════════════════════════════════════════════════════
# EQUITY RESULT VALIDATION TESTS (COMPREHENSIVE)
# ═════════════════════════════════════════════════════════════════════════════


class TestValidateEquityResult:
    """Test suite for validate_equity_result() function."""

    def test_valid_equity_result_all_fields(self):
        """Valid equity result with all fields should pass."""
        equity_dict = {
            "equity_irr": 0.18,
            "equity_npv": 50_000_000,
            "equity_multiple": 2.5,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_equity_result_missing_fields(self):
        """Equity result with missing fields should still validate present ones."""
        equity_dict = {
            "equity_irr": 0.15,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_equity_result_none_values_skipped(self):
        """None values should be skipped, not validated."""
        equity_dict = {
            "equity_irr": None,
            "equity_npv": 50_000_000,
            "equity_multiple": 2.0,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_equity_result_critical_error_irr_nan(self):
        """NaN equity IRR should result in is_valid=False."""
        equity_dict = {
            "equity_irr": float('nan'),
            "equity_npv": 50_000_000,
            "equity_multiple": 2.0,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert not result.is_valid
        assert result.has_critical_errors()
        assert any(e.field == "equity_irr" for e in result.errors)

    def test_equity_result_critical_error_npv_infinity(self):
        """Infinite equity NPV should result in is_valid=False."""
        equity_dict = {
            "equity_irr": 0.15,
            "equity_npv": float('inf'),
            "equity_multiple": 2.0,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert not result.is_valid
        assert result.has_critical_errors()
        assert any(e.field == "equity_npv" for e in result.errors)

    def test_equity_result_warnings_not_blocking(self):
        """Warnings should not make is_valid=False."""
        equity_dict = {
            "equity_irr": 0.35,
            "equity_npv": 50_000_000,
            "equity_multiple": 0.9,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert result.is_valid
        assert len(result.errors) == 2
        assert all(e.severity == "WARNING" for e in result.errors)

    def test_equity_result_npv_irr_consistency_positive_npv_low_irr(self):
        """Positive NPV with low IRR should trigger consistency WARNING."""
        equity_dict = {
            "equity_irr": 0.04,
            "equity_npv": 100_000_000,
            "equity_multiple": 1.5,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert any(
            "npv_irr_consistency" in e.field and "positive" in e.message.lower()
            for e in result.errors
        )

    def test_equity_result_npv_irr_consistency_negative_npv_high_irr(self):
        """Negative NPV with high IRR should trigger consistency WARNING."""
        equity_dict = {
            "equity_irr": 0.20,
            "equity_npv": -50_000_000,
            "equity_multiple": 1.2,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert any(
            "npv_irr_consistency" in e.field and "negative" in e.message.lower()
            for e in result.errors
        )

    def test_equity_result_strict_mode(self):
        """Strict mode should enforce typical bounds."""
        equity_dict = {
            "equity_irr": 0.05,
            "equity_npv": 50_000_000,
            "equity_multiple": 2.0,
        }
        result = validate_equity_result(equity_dict, strict=True)
        assert any(e.field == "equity_irr" for e in result.errors)

    def test_equity_result_non_strict_mode(self):
        """Non-strict mode should only check absolute bounds."""
        equity_dict = {
            "equity_irr": 0.05,
            "equity_npv": 50_000_000,
            "equity_multiple": 2.0,
        }
        result = validate_equity_result(equity_dict, strict=False)
        assert len(result.errors) == 0

    def test_equity_result_contract_type(self):
        """ValidationResult should have correct contract_type."""
        equity_dict = {"equity_irr": 0.15}
        result = validate_equity_result(equity_dict, strict=True)
        assert result.contract_type == "EquityResult"


# ═════════════════════════════════════════════════════════════════════════════
# VALIDATION ERROR DATACLASS TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestValidationError:
    """Test suite for ValidationError dataclass."""

    def test_validation_error_creation(self):
        """ValidationError should be creatable with all fields."""
        error = ValidationError(
            severity="CRITICAL",
            field="equity_irr",
            value=float('nan'),
            constraint="must not be NaN",
            message="equity_irr is NaN",
            remediation="Check equity cashflows",
        )
        assert error.severity == "CRITICAL"
        assert error.field == "equity_irr"
        assert math.isnan(error.value)
        assert error.constraint == "must not be NaN"
        assert error.message == "equity_irr is NaN"
        assert error.remediation == "Check equity cashflows"
        assert error.timestamp is not None

    def test_validation_error_str_representation(self):
        """ValidationError __str__ should include severity and message."""
        error = ValidationError(
            severity="WARNING",
            field="equity_multiple",
            value=0.8,
            constraint="should be >= 1.0",
            message="Equity multiple indicates loss",
        )
        str_repr = str(error)
        assert "[WARNING]" in str_repr
        assert "equity_multiple" in str_repr
        assert "loss" in str_repr.lower()


class TestValidationResult:
    """Test suite for ValidationResult dataclass."""

    def test_validation_result_creation(self):
        """ValidationResult should be creatable with defaults."""
        result = ValidationResult(is_valid=True, contract_type="TestContract")
        assert result.is_valid
        assert result.contract_type == "TestContract"
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert result.timestamp is not None

    def test_has_critical_errors(self):
        """has_critical_errors() should detect CRITICAL severity."""
        result = ValidationResult(is_valid=False)
        result.errors.append(
            ValidationError(
                severity="CRITICAL",
                field="test",
                value=None,
                constraint="test",
                message="test",
            )
        )
        assert result.has_critical_errors()

    def test_has_errors(self):
        """has_errors() should detect ERROR or CRITICAL."""
        result = ValidationResult(is_valid=False)
        result.errors.append(
            ValidationError(
                severity="ERROR",
                field="test",
                value=None,
                constraint="test",
                message="test",
            )
        )
        assert result.has_errors()

    def test_error_count(self):
        """error_count() should count total or by severity."""
        result = ValidationResult(is_valid=False)
        result.errors.append(
            ValidationError(
                severity="CRITICAL",
                field="test1",
                value=None,
                constraint="test",
                message="test",
            )
        )
        result.errors.append(
            ValidationError(
                severity="WARNING",
                field="test2",
                value=None,
                constraint="test",
                message="test",
            )
        )
        assert result.error_count() == 2
        assert result.error_count("CRITICAL") == 1
        assert result.error_count("WARNING") == 1
        assert result.error_count("ERROR") == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
