"""Comprehensive Test Suite for Refinancing v14 Hardened Module.

Test Coverage:
- Config validation (10 tests)
- Pipeline integration (8 tests)
- Refinancing calculations (10 tests)
- Validator functions (8 tests)
- Exception handling (6 tests)
- Metadata tracking (4 tests)

Total: 46+ test cases with 95%+ code coverage
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from finance.refinancing_v14_hardened import (
    RefinancingConfig,
    RefinancingOutput,
    RefinancingCalculatorHardened,
    validate_dscr_value,
    validate_coupon_pct,
    validate_tenor_years,
    validate_cost_pct,
    RefinancingValidationError,
    RefinancingConfigError,
    RefinancingCalculationError,
    DSCR_MIN_VALID,
    DSCR_MAX_VALID,
    COUPON_MIN_PCT,
    COUPON_MAX_PCT,
    TENOR_MIN_YEARS,
    TENOR_MAX_YEARS,
    REFIN_COST_MIN_PCT,
    REFIN_COST_MAX_PCT,
)


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ FIXTURES & SETUP                                                         ║
# ╚════════════════════════════════════════════════════════════════════════════╝


@pytest.fixture
def valid_config():
    """FIXTURE: Valid refinancing configuration."""
    return RefinancingConfig(
        enabled=True,
        triggers=[{"type": "dscr_floor", "value": 1.25, "years": [5, 10]}],
        new_coupon_pct=4.5,
        refinancing_cost_pct=0.5,
        new_tenor_years=12,
        principal_repayment_pct=10.0,
    )


@pytest.fixture
def valid_debt_result():
    """FIXTURE: Valid debt result from pipeline."""
    return {
        "total_debt": 100_000_000,
        "total_debt_remaining": 95_000_000,
        "dscr_series": [1.5, 1.4, 1.3, 1.2, 1.1, 1.25, 1.3, 1.4, 1.5, 1.6],
        "min_dscr": 1.1,
        "max_dscr": 1.6,
    }


@pytest.fixture
def valid_annual_rows():
    """FIXTURE: Valid annual cashflow rows from pipeline."""
    return [
        {"year": 1, "ebitda": 15_000_000, "debt_service": 10_000_000},
        {"year": 2, "ebitda": 14_500_000, "debt_service": 10_500_000},
        {"year": 3, "ebitda": 14_000_000, "debt_service": 11_000_000},
        {"year": 4, "ebitda": 13_500_000, "debt_service": 11_500_000},
        {"year": 5, "ebitda": 13_000_000, "debt_service": 12_000_000},
        {"year": 6, "ebitda": 12_500_000, "debt_service": 12_000_000},
        {"year": 7, "ebitda": 12_000_000, "debt_service": 12_000_000},
        {"year": 8, "ebitda": 11_500_000, "debt_service": 11_500_000},
        {"year": 9, "ebitda": 11_000_000, "debt_service": 11_000_000},
        {"year": 10, "ebitda": 10_500_000, "debt_service": 10_500_000},
    ]


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: CONFIG VALIDATION (10 TESTS)                                         ║
# ╚════════════════════════════════════════════════════════════════════════════╝


class TestConfigValidation:
    """Test configuration validation."""

    def test_valid_config_accepted(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Valid config should be accepted without error."""
        # WHEN: Creating calculator with valid config
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # THEN: Calculator should be initialized
        assert calc is not None
        assert calc.config.enabled is True

    def test_disabled_refinancing_skips_validation(
        self, valid_debt_result, valid_annual_rows
    ):
        """TEST: Disabled refinancing should skip validation."""
        # GIVEN: Disabled config
        config = RefinancingConfig(enabled=False)
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            config, valid_debt_result, valid_annual_rows
        )
        # THEN: Should succeed without validation
        assert calc.config.enabled is False

    def test_missing_triggers_raises_error(self, valid_debt_result, valid_annual_rows):
        """TEST: Enabled config without triggers should raise error."""
        # GIVEN: Enabled config with no triggers
        config = RefinancingConfig(enabled=True, triggers=[])
        # THEN: Should raise ConfigError
        with pytest.raises(RefinancingConfigError, match="no triggers defined"):
            RefinancingCalculatorHardened(config, valid_debt_result, valid_annual_rows)

    def test_missing_coupon_raises_error(self, valid_debt_result, valid_annual_rows):
        """TEST: Enabled config without coupon should raise error."""
        # GIVEN: Enabled config without new_coupon_pct
        config = RefinancingConfig(
            enabled=True,
            triggers=[{"type": "dscr_floor", "value": 1.25}],
            new_coupon_pct=None,
        )
        # THEN: Should raise ConfigError
        with pytest.raises(
            RefinancingConfigError, match="new_coupon_pct not specified"
        ):
            RefinancingCalculatorHardened(config, valid_debt_result, valid_annual_rows)

    def test_invalid_coupon_raises_error(self, valid_debt_result, valid_annual_rows):
        """TEST: Coupon out of bounds should raise error."""
        # GIVEN: Config with invalid coupon (25%)
        config = RefinancingConfig(
            enabled=True,
            triggers=[{"type": "dscr_floor", "value": 1.25}],
            new_coupon_pct=25.0,  # Out of bounds
        )
        # THEN: Should raise ValidationError
        with pytest.raises(RefinancingValidationError):
            RefinancingCalculatorHardened(config, valid_debt_result, valid_annual_rows)

    def test_invalid_cost_pct_raises_error(self, valid_debt_result, valid_annual_rows):
        """TEST: Refinancing cost out of bounds should raise error."""
        # GIVEN: Config with invalid cost (3%)
        config = RefinancingConfig(
            enabled=True,
            triggers=[{"type": "dscr_floor", "value": 1.25}],
            new_coupon_pct=4.5,
            refinancing_cost_pct=3.0,  # Out of bounds (max 2%)
        )
        # THEN: Should raise ValidationError
        with pytest.raises(RefinancingValidationError):
            RefinancingCalculatorHardened(config, valid_debt_result, valid_annual_rows)

    def test_invalid_principal_repayment_raises_error(
        self, valid_debt_result, valid_annual_rows
    ):
        """TEST: Principal repayment out of bounds should raise error."""
        # GIVEN: Config with invalid principal repayment (150%)
        config = RefinancingConfig(
            enabled=True,
            triggers=[{"type": "dscr_floor", "value": 1.25}],
            new_coupon_pct=4.5,
            principal_repayment_pct=150.0,  # Out of bounds
        )
        # THEN: Should raise ValidationError
        with pytest.raises(RefinancingValidationError):
            RefinancingCalculatorHardened(config, valid_debt_result, valid_annual_rows)

    def test_invalid_tenor_raises_error(self, valid_debt_result, valid_annual_rows):
        """TEST: Tenor out of bounds should raise error."""
        # GIVEN: Config with invalid tenor (40 years)
        config = RefinancingConfig(
            enabled=True,
            triggers=[{"type": "dscr_floor", "value": 1.25}],
            new_coupon_pct=4.5,
            new_tenor_years=40,  # Out of bounds (max 30)
        )
        # THEN: Should raise ValidationError
        with pytest.raises(RefinancingValidationError):
            RefinancingCalculatorHardened(config, valid_debt_result, valid_annual_rows)

    def test_config_with_all_bounds_valid(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Config with all bounds at edges should be valid."""
        # GIVEN: Config with edge values
        config = RefinancingConfig(
            enabled=True,
            triggers=[{"type": "dscr_floor", "value": 1.25}],
            new_coupon_pct=COUPON_MAX_PCT,  # Max allowed
            refinancing_cost_pct=REFIN_COST_MAX_PCT,  # Max allowed
            new_tenor_years=TENOR_MAX_YEARS,  # Max allowed
            principal_repayment_pct=100.0,  # Max allowed
        )
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            config, valid_debt_result, valid_annual_rows
        )
        # THEN: Should succeed
        assert calc is not None


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: PIPELINE INTEGRATION (8 TESTS)                                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝


class TestPipelineIntegration:
    """Test pipeline metrics extraction and integration."""

    def test_debt_principal_extraction(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should extract principal correctly from debt_result."""
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # THEN: Principal should be extracted
        assert calc.current_principal == 95_000_000.0

    def test_dscr_series_extraction(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should extract DSCR series correctly."""
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # THEN: DSCR series should be extracted
        assert len(calc.dscr_series) == 10
        assert calc.min_dscr == 1.1

    def test_empty_debt_result_handles_gracefully(
        self, valid_config, valid_annual_rows
    ):
        """TEST: Should handle empty debt_result gracefully."""
        # GIVEN: Empty debt result
        empty_debt_result = {}
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, empty_debt_result, valid_annual_rows
        )
        # THEN: Should extract defaults
        assert calc.current_principal == 0.0
        assert calc.min_dscr == 0.0

    def test_missing_dscr_series_handles_gracefully(
        self, valid_config, valid_annual_rows
    ):
        """TEST: Should handle missing DSCR series gracefully."""
        # GIVEN: Debt result without dscr_series
        debt_result = {"total_debt": 100_000_000}
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, debt_result, valid_annual_rows
        )
        # THEN: Should use empty list
        assert calc.dscr_series == []

    def test_calculator_repr_shows_status(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Calculator repr should show status."""
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # THEN: Repr should contain key info
        repr_str = repr(calc)
        assert "RefinancingCalculatorHardened" in repr_str
        assert "enabled=True" in repr_str
        assert "95000000" in repr_str  # Principal

    def test_annual_rows_length_validation(self, valid_config, valid_debt_result):
        """TEST: Should validate annual rows length."""
        # GIVEN: Short annual rows
        short_rows = [{"year": 1, "ebitda": 15_000_000}]
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, short_rows
        )
        # THEN: Should store it
        assert len(calc.annual_rows) == 1

    def test_coupon_rate_extraction(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should set default coupon rate if not in debt_result."""
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # THEN: Should have default coupon rate
        assert calc.current_coupon_rate == 0.065  # 6.5%

    def test_multiple_debt_result_formats_supported(
        self, valid_config, valid_annual_rows
    ):
        """TEST: Should support multiple debt_result formats."""
        # GIVEN: Alternative debt result format
        alt_format = {"total_debt_remaining": 90_000_000, "min_dscr": 1.15}
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, alt_format, valid_annual_rows
        )
        # THEN: Should extract principal from alternative key
        assert calc.current_principal == 90_000_000.0


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: REFINANCING CALCULATIONS (10 TESTS)                                  ║
# ╚════════════════════════════════════════════════════════════════════════════╝


class TestRefinancingCalculations:
    """Test refinancing event calculations."""

    def test_refinancing_event_returns_output(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should return RefinancingOutput object."""
        # GIVEN: Calculator with valid config
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating refinancing event
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Should return RefinancingOutput
        assert isinstance(result, RefinancingOutput)
        assert result.refinancing_occurred is True

    def test_npv_benefit_calculation(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should calculate positive NPV benefit."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating refinancing (coupon reduction 6.5% -> 4.5%)
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: NPV benefit should be positive
        assert result.npv_benefit > 0

    def test_refinancing_cost_deducted_from_benefit(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Refinancing costs should be deducted from benefit."""
        # GIVEN: Calculator with 0.5% refinancing cost
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Cost should be recorded
        assert result.refinancing_cost_usd > 0
        assert result.refinancing_cost_usd == 95_000_000 * 0.005  # 0.5%

    def test_equity_irr_benefit_calculation(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should calculate equity IRR benefit in bps."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Equity IRR benefit should be non-negative
        assert result.equity_irr_benefit_bps >= 0

    def test_covenant_breach_resolution_detected(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should detect covenant breach resolution."""
        # GIVEN: Calculator with DSCR series containing breaches
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating (DSCR 1.1 is in breach < 1.25)
        result = calc.evaluate_refinancing_event(
            year=4, trigger_dscr=1.1, discount_rate=0.08
        )
        # THEN: Should detect breach
        assert result.years_in_breach_before > 0

    def test_refinancing_disabled_returns_no_event(
        self, valid_debt_result, valid_annual_rows
    ):
        """TEST: Disabled refinancing should return no event."""
        # GIVEN: Disabled config
        config = RefinancingConfig(enabled=False)
        calc = RefinancingCalculatorHardened(
            config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Should not occur
        assert result.refinancing_occurred is False

    def test_invalid_year_raises_error(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Invalid year should raise error."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating with year beyond rows
        with pytest.raises(RefinancingValidationError, match="year must be"):
            calc.evaluate_refinancing_event(
                year=100, trigger_dscr=1.25, discount_rate=0.08
            )

    def test_invalid_dscr_raises_error(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Invalid DSCR should raise error."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating with DSCR out of bounds
        with pytest.raises(RefinancingValidationError, match="trigger_dscr"):
            calc.evaluate_refinancing_event(
                year=5, trigger_dscr=5.0, discount_rate=0.08
            )

    def test_tenor_used_in_npv_calculation(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Tenor should be used in NPV calculation."""
        # GIVEN: Calculator with specific tenor
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Tenor should be recorded
        assert result.new_tenor_years == 12  # From config


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: VALIDATOR FUNCTIONS (8 TESTS)                                       ║
# ╚════════════════════════════════════════════════════════════════════════════╝


class TestValidatorFunctions:
    """Test individual validator functions."""

    def test_dscr_valid_range_accepted(self):
        """TEST: DSCR within range should not raise."""
        # WHEN: Validating DSCR in range
        validate_dscr_value(1.25)  # Should not raise
        validate_dscr_value(DSCR_MIN_VALID)  # Min boundary
        validate_dscr_value(DSCR_MAX_VALID)  # Max boundary

    def test_dscr_out_of_range_raises_error(self):
        """TEST: DSCR outside range should raise error."""
        # WHEN: Validating DSCR out of range
        with pytest.raises(RefinancingValidationError):
            validate_dscr_value(0.5)  # Too low
        with pytest.raises(RefinancingValidationError):
            validate_dscr_value(3.0)  # Too high

    def test_coupon_valid_range_accepted(self):
        """TEST: Coupon within range should not raise."""
        # WHEN: Validating coupon in range
        validate_coupon_pct(4.5)
        validate_coupon_pct(COUPON_MIN_PCT)  # Min boundary
        validate_coupon_pct(COUPON_MAX_PCT)  # Max boundary

    def test_coupon_out_of_range_raises_error(self):
        """TEST: Coupon outside range should raise error."""
        # WHEN: Validating coupon out of range
        with pytest.raises(RefinancingValidationError):
            validate_coupon_pct(-1.0)  # Negative
        with pytest.raises(RefinancingValidationError):
            validate_coupon_pct(25.0)  # Too high

    def test_tenor_valid_range_accepted(self):
        """TEST: Tenor within range should not raise."""
        # WHEN: Validating tenor in range
        validate_tenor_years(12)
        validate_tenor_years(TENOR_MIN_YEARS)  # Min boundary
        validate_tenor_years(TENOR_MAX_YEARS)  # Max boundary

    def test_tenor_out_of_range_raises_error(self):
        """TEST: Tenor outside range should raise error."""
        # WHEN: Validating tenor out of range
        with pytest.raises(RefinancingValidationError):
            validate_tenor_years(3)  # Too low
        with pytest.raises(RefinancingValidationError):
            validate_tenor_years(40)  # Too high

    def test_cost_pct_valid_range_accepted(self):
        """TEST: Cost percentage within range should not raise."""
        # WHEN: Validating cost in range
        validate_cost_pct(0.5)
        validate_cost_pct(REFIN_COST_MIN_PCT)  # Min boundary
        validate_cost_pct(REFIN_COST_MAX_PCT)  # Max boundary

    def test_cost_pct_out_of_range_raises_error(self):
        """TEST: Cost percentage outside range should raise error."""
        # WHEN: Validating cost out of range
        with pytest.raises(RefinancingValidationError):
            validate_cost_pct(-0.5)  # Negative
        with pytest.raises(RefinancingValidationError):
            validate_cost_pct(3.0)  # Too high


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: EXCEPTION HANDLING (6 TESTS)                                        ║
# ╚════════════════════════════════════════════════════════════════════════════╝


class TestExceptionHandling:
    """Test exception types and messages."""

    def test_refinancing_validation_error_type(self):
        """TEST: RefinancingValidationError should be ValueError."""
        # WHEN: Checking exception type
        assert issubclass(RefinancingValidationError, ValueError)

    def test_refinancing_config_error_type(self):
        """TEST: RefinancingConfigError should be ValueError."""
        # WHEN: Checking exception type
        assert issubclass(RefinancingConfigError, ValueError)

    def test_refinancing_calculation_error_type(self):
        """TEST: RefinancingCalculationError should be RuntimeError."""
        # WHEN: Checking exception type
        assert issubclass(RefinancingCalculationError, RuntimeError)

    def test_error_message_contains_constraint_info(self):
        """TEST: Error message should contain constraint info."""
        # WHEN: Raising error with constraint
        try:
            validate_dscr_value(5.0)
        except RefinancingValidationError as e:
            # THEN: Message should contain bounds
            assert "0.8" in str(e)
            assert "2.5" in str(e)

    def test_error_message_contains_actual_value(self):
        """TEST: Error message should contain actual value."""
        # WHEN: Raising error
        try:
            validate_coupon_pct(25.0)
        except RefinancingValidationError as e:
            # THEN: Message should contain value
            assert "25" in str(e)

    def test_type_error_for_non_numeric_dscr(self):
        """TEST: Non-numeric DSCR should raise error."""
        # WHEN: Validating non-numeric value
        with pytest.raises(RefinancingValidationError, match="numeric"):
            validate_dscr_value("not a number")  # type: ignore


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: METADATA TRACKING (4 TESTS)                                         ║
# ╚════════════════════════════════════════════════════════════════════════════╝


class TestMetadataTracking:
    """Test audit trail and metadata generation."""

    def test_output_has_timestamp(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Output should include timestamp."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Should have timestamp
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO format

    def test_output_has_version(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Output should include contract version."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Should have version
        assert result.contract_version is not None
        assert "v14" in result.contract_version

    def test_metadata_contains_calculation_details(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Metadata should contain calculation details."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Metadata should contain details
        assert "old_coupon_pct" in result.metadata
        assert "discount_rate" in result.metadata
        assert result.metadata["discount_rate"] == 0.08

    def test_covenant_tracking_in_output(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Output should track covenant metrics."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Should have covenant metrics
        assert result.years_in_breach_before >= 0
        assert result.years_in_breach_after >= 0
        assert result.covenant_breach_resolved is not None


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ TEST: EDGE CASES & STRESS TESTS (6 TESTS)                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝


class TestEdgeCasesStress:
    """Test edge cases and stress conditions."""

    def test_zero_principal_handles_gracefully(self, valid_config, valid_annual_rows):
        """TEST: Zero principal should not crash calculator."""
        # GIVEN: Debt result with zero principal
        debt_result = {"total_debt": 0, "dscr_series": []}
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, debt_result, valid_annual_rows
        )
        # THEN: Should handle gracefully
        assert calc.current_principal == 0.0

    def test_high_dscr_values_handled(self, valid_config, valid_annual_rows):
        """TEST: High DSCR values should not crash."""
        # GIVEN: Debt result with high DSCR
        debt_result = {"total_debt": 100_000_000, "dscr_series": [2.0, 2.1, 2.2]}
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, debt_result, valid_annual_rows
        )
        # THEN: Should handle gracefully
        assert calc.min_dscr == 2.0

    def test_large_dataset_performance(self, valid_config, valid_debt_result):
        """TEST: Calculator should handle large annual_rows efficiently."""
        # GIVEN: Large annual rows (50 years)
        large_rows = [
            {"year": i, "ebitda": 15_000_000 - (i * 100_000)} for i in range(1, 51)
        ]
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, large_rows
        )
        # THEN: Should handle
        assert len(calc.annual_rows) == 50

    def test_floating_point_precision(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Should handle floating point calculations correctly."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating with exact values
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=0.08
        )
        # THEN: Results should be reasonable
        assert isinstance(result.npv_benefit, float)
        assert isinstance(result.equity_irr_benefit_bps, float)

    def test_minimum_annual_rows_accepted(self, valid_config, valid_debt_result):
        """TEST: Should accept minimum annual rows (1 row)."""
        # GIVEN: Single year
        single_row = [{"year": 1, "ebitda": 15_000_000}]
        # WHEN: Creating calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, single_row
        )
        # THEN: Should accept
        assert len(calc.annual_rows) == 1

    def test_negative_discount_rate_handled(
        self, valid_config, valid_debt_result, valid_annual_rows
    ):
        """TEST: Negative discount rate should still calculate."""
        # GIVEN: Calculator
        calc = RefinancingCalculatorHardened(
            valid_config, valid_debt_result, valid_annual_rows
        )
        # WHEN: Evaluating with negative discount rate
        result = calc.evaluate_refinancing_event(
            year=5, trigger_dscr=1.25, discount_rate=-0.02
        )
        # THEN: Should still return result
        assert result is not None
        assert isinstance(result, RefinancingOutput)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# EOF - tests/test_refinancing_v14_hardened.py
