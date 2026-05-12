"""Regression tests for Equity Distribution V14 module.

Tests comprehensive equity distribution functionality including:
- Configuration validation
- Covenant gate checking
- Reserve calculations
- Distribution waterfall
- Multi-tier equity handling
"""

import pytest
from finance.equity_distribution_v14 import (
    EquityDistributionConfig,
    CovenantGate,
    EquityDistributionCalculator,
    EquityDistributionOutput,
    calculate_equity_distribution,
)


class TestEquityDistributionConfig:
    """Test EquityDistributionConfig initialization and validation."""

    def test_config_creation_with_defaults(self) -> None:
        """Test creating config with default values."""
        config = EquityDistributionConfig()
        assert config.enabled is True
        assert config.min_dscr_for_distribution == 1.20
        assert config.min_llcr_for_distribution == 1.50
        assert config.debt_reserve_target_months == 6.0

    def test_config_creation_with_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = EquityDistributionConfig(
            min_dscr_for_distribution=1.25,
            min_llcr_for_distribution=1.75,
            class_a_preferred_return=0.10,
            class_b_preferred_return=0.14,
        )
        assert config.min_dscr_for_distribution == 1.25
        assert config.class_a_preferred_return == 0.10
        assert config.class_b_preferred_return == 0.14

    def test_config_validation_invalid_dscr(self) -> None:
        """Test config validation rejects invalid DSCR."""
        with pytest.raises(ValueError):
            EquityDistributionConfig(min_dscr_for_distribution=0.2)


class TestCovenantGate:
    """Test covenant gate functionality."""

    def test_dscr_gate_pass(self) -> None:
        """Test DSCR gate passes when conditions met."""
        config = EquityDistributionConfig(min_dscr_for_distribution=1.20)
        gate = CovenantGate(config)

        passed, reason = gate.check_dscr_gate(
            current_dscr=1.35,
            post_distribution_dscr=1.25,
        )

        assert passed is True
        assert "PASS" in reason

    def test_dscr_gate_fail(self) -> None:
        """Test DSCR gate fails when threshold breached."""
        config = EquityDistributionConfig(min_dscr_for_distribution=1.20)
        gate = CovenantGate(config)

        passed, reason = gate.check_dscr_gate(
            current_dscr=1.35,
            post_distribution_dscr=1.10,
        )

        assert passed is False
        assert "FAIL" in reason

    def test_llcr_gate_pass(self) -> None:
        """Test LLCR gate passes when conditions met."""
        config = EquityDistributionConfig(min_llcr_for_distribution=1.50)
        gate = CovenantGate(config)

        passed, reason = gate.check_llcr_gate(
            current_llcr=1.75,
            post_distribution_llcr=1.55,
        )

        assert passed is True
        assert "PASS" in reason

    def test_all_gates_evaluation(self) -> None:
        """Test evaluation of all covenant gates together."""
        config = EquityDistributionConfig(
            min_dscr_for_distribution=1.20,
            min_llcr_for_distribution=1.50,
        )
        gate = CovenantGate(config)

        all_pass, gates = gate.check_all_gates(
            current_dscr=1.35,
            current_llcr=1.75,
            post_dist_dscr=1.25,
            post_dist_llcr=1.60,
        )

        assert all_pass is True
        assert "dscr" in gates
        assert "llcr" in gates


class TestEquityDistributionCalculator:
    """Test equity distribution calculations."""

    def test_calculate_required_reserves(self) -> None:
        """Test required reserve calculation."""
        config = EquityDistributionConfig(
            debt_reserve_target_months=6.0,
            operating_reserve_target_months=3.0,
        )
        calc = EquityDistributionCalculator(config)

        reserves = calc.calculate_required_reserves(
            monthly_debt_service=1.0,
            monthly_operating_costs=0.5,
        )

        assert reserves["debt_service_reserve"] == pytest.approx(6.0, abs=0.01)
        assert reserves["operating_reserve"] == pytest.approx(1.5, abs=0.01)
        assert reserves["total_reserves"] == pytest.approx(7.5, abs=0.01)

    def test_calculate_available_for_equity_with_reserve_rebuild(self) -> None:
        """Test available cashflow with reserve rebuild priority."""
        config = EquityDistributionConfig(
            reserve_rebuild_priority=True,
            max_distribution_pct_cf=0.80,
        )
        calc = EquityDistributionCalculator(config)

        available = calc.calculate_available_for_equity(
            annual_cashflow=50.0,
            debt_service_required=20.0,
            reserve_deficit=5.0,
        )

        # 50 - 20 (debt) - 5 (reserve) = 25
        assert available == pytest.approx(25.0, abs=0.01)

    def test_distribute_to_equity_tiers(self) -> None:
        """Test distribution to equity tiers."""
        config = EquityDistributionConfig(
            class_a_preferred_return=0.08,
            class_b_preferred_return=0.12,
        )
        calc = EquityDistributionCalculator(config)

        distributions = calc.distribute_to_equity_tiers(
            available_cashflow=20.0,
            class_a_invested=50.0,
            class_b_invested=30.0,
            class_a_accumulated_returns=0.0,
            class_b_accumulated_returns=0.0,
        )

        assert "class_a" in distributions
        assert "class_b" in distributions
        assert "common" in distributions
        assert distributions["class_a"]["total"] >= 0
        assert distributions["class_b"]["total"] >= 0


class TestEquityDistributionIntegration:
    """Test full equity distribution integration."""

    def test_distribution_enabled_scenario(self) -> None:
        """Test full distribution workflow when distributions enabled."""
        config = EquityDistributionConfig(
            enabled=True,
            distributions_allowed_after_year=5,
            min_dscr_for_distribution=1.20,
            min_llcr_for_distribution=1.50,
            covenant_gating_strict=True,
        )

        result = calculate_equity_distribution(
            config=config,
            year=8,
            annual_cashflow=50.0,
            debt_service_required=20.0,
            monthly_debt_service=1.67,
            monthly_operating_costs=1.0,
            current_dscr=1.50,
            current_llcr=2.50,
            class_a_invested=50.0,
            class_b_invested=30.0,
        )

        assert isinstance(result, EquityDistributionOutput)
        assert result.distribution_year == 8
        assert result.distribution_enabled is True
        assert result.total_equity_distribution >= 0

    def test_distribution_disabled_early_years(self) -> None:
        """Test no distributions in early project years."""
        config = EquityDistributionConfig(
            distributions_allowed_after_year=5,
        )

        result = calculate_equity_distribution(
            config=config,
            year=3,  # Too early
            annual_cashflow=50.0,
            debt_service_required=20.0,
            monthly_debt_service=1.67,
            monthly_operating_costs=1.0,
            current_dscr=1.50,
            current_llcr=1.75,
            class_a_invested=50.0,
            class_b_invested=30.0,
        )

        assert result.distribution_enabled is False
        assert result.total_equity_distribution == 0.0

    def test_distribution_covenant_gate_fail(self) -> None:
        """Test no distributions when covenants would be breached."""
        config = EquityDistributionConfig(
            enabled=True,
            distributions_allowed_after_year=5,
            min_dscr_for_distribution=1.40,  # High threshold
            covenant_gating_strict=True,
        )

        result = calculate_equity_distribution(
            config=config,
            year=8,
            annual_cashflow=50.0,
            debt_service_required=20.0,
            monthly_debt_service=1.67,
            monthly_operating_costs=1.0,
            current_dscr=1.30,  # Below threshold
            current_llcr=1.75,
            class_a_invested=50.0,
            class_b_invested=30.0,
        )

        # Should fail due to low DSCR
        assert result.covenant_gates_passed is False

    def test_distribution_output_serialization(self) -> None:
        """Test EquityDistributionOutput can be serialized to dict."""
        config = EquityDistributionConfig()

        result = calculate_equity_distribution(
            config=config,
            year=8,
            annual_cashflow=50.0,
            debt_service_required=20.0,
            monthly_debt_service=1.67,
            monthly_operating_costs=1.0,
            current_dscr=1.50,
            current_llcr=1.75,
            class_a_invested=50.0,
            class_b_invested=30.0,
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "distribution_year" in result_dict
        assert "distributions_to_tiers" in result_dict
        assert "timestamp" in result_dict
        assert "covenant_gate_details" in result_dict
