"""Regression tests for Refinancing V14 module.

Tests comprehensive refinancing functionality including:
- Configuration validation
- Trigger condition evaluation
- Debt schedule recalculation
- Covenant impact analysis
- Integration scenarios
"""

import pytest
from finance.refinancing_v14 import (
    RefinancingConfig,
    RefinancingTrigger,
    RefinancingCalculator,
    RefinancingOutput,
    calculate_refinancing,
)


class TestRefinancingConfig:
    """Test RefinancingConfig initialization and validation."""

    def test_config_creation_with_defaults(self) -> None:
        """Test creating config with default values."""
        config = RefinancingConfig()
        assert config.enabled is True
        assert config.trigger_year == 8
        assert config.min_dscr_for_trigger == 1.25
        assert config.new_interest_rate == 0.05

    def test_config_creation_with_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = RefinancingConfig(
            enabled=True,
            trigger_year=6,
            min_dscr_for_trigger=1.30,
            new_interest_rate=0.045,
        )
        assert config.trigger_year == 6
        assert config.min_dscr_for_trigger == 1.30
        assert config.new_interest_rate == 0.045

    def test_config_validation_invalid_trigger_year(self) -> None:
        """Test config validation rejects invalid trigger year."""
        with pytest.raises(ValueError):
            RefinancingConfig(trigger_year=0)


class TestRefinancingTrigger:
    """Test RefinancingTrigger condition evaluation."""

    def test_trigger_all_conditions_pass(self) -> None:
        """Test trigger evaluation when all conditions pass."""
        config = RefinancingConfig(
            trigger_year=8,
            min_dscr_for_trigger=1.25,
            rate_savings_threshold=50.0,
            npv_positive_threshold=0.0,
        )
        trigger = RefinancingTrigger(config)

        triggered, reasons, conditions = trigger.evaluate(
            current_year=10,
            current_dscr=1.35,
            current_interest_rate=0.070,
            npv_benefit=5.0,
        )

        assert triggered is True
        assert len(reasons) == 4
        assert conditions["year_threshold"] is True
        assert conditions["dscr_strength"] is True
        assert conditions["rate_savings"] is True
        assert conditions["npv_positive"] is True

    def test_trigger_year_condition_fails(self) -> None:
        """Test trigger when year condition fails."""
        config = RefinancingConfig(trigger_year=8)
        trigger = RefinancingTrigger(config)

        triggered, reasons, conditions = trigger.evaluate(
            current_year=5,
            current_dscr=1.35,
            current_interest_rate=0.070,
            npv_benefit=5.0,
        )

        assert triggered is False
        assert conditions["year_threshold"] is False

    def test_trigger_dscr_condition_fails(self) -> None:
        """Test trigger when DSCR condition fails."""
        config = RefinancingConfig(
            trigger_year=8,
            min_dscr_for_trigger=1.25,
        )
        trigger = RefinancingTrigger(config)

        triggered, reasons, conditions = trigger.evaluate(
            current_year=10,
            current_dscr=1.20,
            current_interest_rate=0.070,
            npv_benefit=5.0,
        )

        assert triggered is False
        assert conditions["dscr_strength"] is False

    def test_trigger_rate_savings_condition_fails(self) -> None:
        """Test trigger when rate savings condition fails."""
        config = RefinancingConfig(
            trigger_year=8,
            min_dscr_for_trigger=1.25,
            rate_savings_threshold=50.0,
            new_interest_rate=0.070,
        )
        trigger = RefinancingTrigger(config)

        triggered, reasons, conditions = trigger.evaluate(
            current_year=10,
            current_dscr=1.35,
            current_interest_rate=0.072,
            npv_benefit=5.0,
        )

        assert triggered is False
        assert conditions["rate_savings"] is False


class TestRefinancingCalculator:
    """Test RefinancingCalculator debt schedule calculations."""

    def test_debt_service_payment_basic(self) -> None:
        """Test basic debt service payment calculation."""
        config = RefinancingConfig()
        calc = RefinancingCalculator(config)

        # $100M at 5% for 15 years
        payment = calc.calculate_debt_service_payment(
            principal=100.0, rate=0.05, years=15
        )

        # Expected: ~9.6 (rough approximation)
        assert payment > 0
        assert payment < 15

    def test_debt_service_payment_zero_rate(self) -> None:
        """Test debt service payment with zero interest rate."""
        config = RefinancingConfig()
        calc = RefinancingCalculator(config)

        payment = calc.calculate_debt_service_payment(
            principal=100.0, rate=0.0, years=10
        )

        # With zero rate, should be principal / years
        assert abs(payment - 10.0) < 0.01

    def test_recalculate_schedule_refinancing(self) -> None:
        """Test debt schedule recalculation post-refinancing."""
        config = RefinancingConfig(
            new_interest_rate=0.05,
            new_tenor=15,
            upfront_cost_pct=0.02,
        )
        calc = RefinancingCalculator(config)

        result = calc.recalculate_schedule(
            current_balance=100.0,
            current_year=8,
            remaining_years=17,
        )

        assert "new_annual_payment" in result
        assert "interest_savings" in result
        assert "upfront_costs" in result
        assert "net_benefit" in result
        assert result["new_tenor_effective"] == 15
        assert result["upfront_costs"] == pytest.approx(2.0, abs=0.01)

    def test_recalculate_covenants(self) -> None:
        """Test covenant recalculation post-refinancing."""
        config = RefinancingConfig()
        calc = RefinancingCalculator(config)

        covenants = calc.recalculate_covenants(
            new_annual_debt_service=10.0,
            annual_cashflow=15.0,
            ebitda=25.0,
            total_debt=100.0,
        )

        # DSCR = 15 / 10 = 1.5
        assert covenants["dscr"] == pytest.approx(1.5, abs=0.01)
        # LLCR = 25 / 100 = 0.25
        assert covenants["llcr"] == pytest.approx(0.25, abs=0.01)


class TestRefinancingIntegration:
    """Test full refinancing calculation integration."""

    def test_refinancing_triggered_scenario(self) -> None:
        """Test complete refinancing workflow when trigger occurs."""
        config = RefinancingConfig(
            enabled=True,
            trigger_year=8,
            min_dscr_for_trigger=1.25,
            rate_savings_threshold=50.0,
            new_interest_rate=0.050,
        )

        result = calculate_refinancing(
            config=config,
            current_year=10,
            current_dscr=1.35,
            current_interest_rate=0.070,
            current_debt_balance=100.0,
            remaining_years=17,
            annual_cashflow=20.0,
            ebitda=25.0,
        )

        assert isinstance(result, RefinancingOutput)
        assert result.refinancing_triggered is True
        assert result.current_year == 10
        assert result.new_tenor_years > 0
        assert len(result.trigger_reasons) > 0

    def test_refinancing_not_triggered_scenario(self) -> None:
        """Test refinancing when trigger conditions not met."""
        config = RefinancingConfig(
            enabled=True,
            trigger_year=8,
            min_dscr_for_trigger=1.25,
        )

        result = calculate_refinancing(
            config=config,
            current_year=5,  # Too early
            current_dscr=1.35,
            current_interest_rate=0.070,
            current_debt_balance=100.0,
            remaining_years=20,
            annual_cashflow=20.0,
            ebitda=25.0,
        )

        assert result.refinancing_triggered is False
        assert len(result.trigger_reasons) == 0
        assert result.new_tenor_years == 0

    def test_refinancing_output_serialization(self) -> None:
        """Test RefinancingOutput can be serialized to dict."""
        config = RefinancingConfig()

        result = calculate_refinancing(
            config=config,
            current_year=10,
            current_dscr=1.35,
            current_interest_rate=0.070,
            current_debt_balance=100.0,
            remaining_years=17,
            annual_cashflow=20.0,
            ebitda=25.0,
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "refinancing_triggered" in result_dict
        assert "timestamp" in result_dict
        assert "new_annual_payment" in result_dict
