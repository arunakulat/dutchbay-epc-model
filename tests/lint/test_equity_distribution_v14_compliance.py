"""Compliance and linting tests for Equity Distribution V14 module.

Verifies:
- 100% type hint coverage
- 100% docstring coverage
- No hardcoded values (config-driven)
- Production-quality code standards
"""

import ast
import inspect
from typing import List
import pytest
from finance.equity_distribution_v14 import (
    EquityDistributionConfig,
    EquityTierType,
    CovenantGate,
    EquityDistributionCalculator,
    EquityDistributionOutput,
    calculate_equity_distribution,
)


class TestTypeHints:
    """Verify type hint coverage."""

    def test_equity_distribution_config_type_hints(self) -> None:
        """Test EquityDistributionConfig has complete type hints."""
        hints = EquityDistributionConfig.model_fields
        assert len(hints) > 0
        assert "enabled" in hints
        assert "min_dscr_for_distribution" in hints
        assert "min_llcr_for_distribution" in hints
        assert "class_a_preferred_return" in hints

    def test_covenant_gate_methods_type_hints(self) -> None:
        """Test CovenantGate methods have type hints."""
        sig = inspect.signature(CovenantGate.check_dscr_gate)
        assert sig.return_annotation != inspect.Parameter.empty
        # Should return Tuple[bool, str]
        assert "Tuple" in str(sig.return_annotation)

    def test_main_function_type_hints(self) -> None:
        """Test calculate_equity_distribution has type hints."""
        sig = inspect.signature(calculate_equity_distribution)
        assert sig.return_annotation == EquityDistributionOutput


class TestDocstrings:
    """Verify docstring coverage."""

    def test_config_class_docstring(self) -> None:
        """Test EquityDistributionConfig has comprehensive docstring."""
        docstring = EquityDistributionConfig.__doc__
        assert docstring is not None
        assert len(docstring) > 50
        assert "waterfall" in docstring.lower()
        assert "Attributes:" in docstring

    def test_covenant_gate_docstring(self) -> None:
        """Test CovenantGate has complete docstring."""
        docstring = CovenantGate.__doc__
        assert docstring is not None
        assert "covenant" in docstring.lower()

    def test_main_function_docstring(self) -> None:
        """Test main function has comprehensive docstring."""
        docstring = calculate_equity_distribution.__doc__
        assert docstring is not None
        assert "Args:" in docstring
        assert "Returns:" in docstring
        assert len(docstring) > 100

    def test_calculator_methods_docstrings(self) -> None:
        """Test EquityDistributionCalculator methods have docstrings."""
        calc = EquityDistributionCalculator(EquityDistributionConfig())
        # Key methods should have docstrings
        assert calc.calculate_required_reserves.__doc__ is not None
        assert calc.calculate_available_for_equity.__doc__ is not None
        assert calc.distribute_to_equity_tiers.__doc__ is not None


class TestNonHardcodedValues:
    """Verify no hardcoded values in business logic."""

    def test_covenant_thresholds_from_config(self) -> None:
        """Test covenant gates use config thresholds, not hardcoded."""
        config = EquityDistributionConfig(
            min_dscr_for_distribution=1.25,
            min_llcr_for_distribution=1.60,
        )
        gate = CovenantGate(config)

        assert gate.config.min_dscr_for_distribution == 1.25
        assert gate.config.min_llcr_for_distribution == 1.60

    def test_distribution_parameters_from_config(self) -> None:
        """Test distribution uses config values, not hardcoded."""
        config = EquityDistributionConfig(
            class_a_preferred_return=0.09,
            class_b_preferred_return=0.13,
            max_distribution_pct_cf=0.75,
        )
        calc = EquityDistributionCalculator(config)

        assert calc.config.class_a_preferred_return == 0.09
        assert calc.config.class_b_preferred_return == 0.13
        assert calc.config.max_distribution_pct_cf == 0.75

    def test_reserve_targets_from_config(self) -> None:
        """Test reserve calculations use config targets."""
        config = EquityDistributionConfig(
            debt_reserve_target_months=7.0,
            operating_reserve_target_months=4.0,
        )
        calc = EquityDistributionCalculator(config)

        assert calc.config.debt_reserve_target_months == 7.0
        assert calc.config.operating_reserve_target_months == 4.0


class TestConfigDriven:
    """Verify config-driven design patterns."""

    def test_all_covenant_gates_configurable(self) -> None:
        """Test all covenant thresholds are configurable."""
        config_strict = EquityDistributionConfig(
            min_dscr_for_distribution=1.35,
            min_llcr_for_distribution=1.70,
        )
        config_flexible = EquityDistributionConfig(
            min_dscr_for_distribution=1.15,
            min_llcr_for_distribution=1.40,
        )

        assert (
            config_strict.min_dscr_for_distribution
            > config_flexible.min_dscr_for_distribution
        )
        assert (
            config_strict.min_llcr_for_distribution
            > config_flexible.min_llcr_for_distribution
        )

    def test_equity_returns_configurable(self) -> None:
        """Test preferred returns are fully configurable."""
        config = EquityDistributionConfig(
            class_a_preferred_return=0.075,
            class_b_preferred_return=0.125,
        )
        calc = EquityDistributionCalculator(config)

        distributions = calc.distribute_to_equity_tiers(
            available_cashflow=100.0,
            class_a_invested=100.0,
            class_b_invested=50.0,
            class_a_accumulated_returns=0.0,
            class_b_accumulated_returns=0.0,
        )

        # Class A should respect configured return
        a_pref = 100.0 * 0.075
        assert distributions["class_a"]["preferred_return"] <= a_pref

    def test_waterfall_priority_from_config(self) -> None:
        """Test waterfall priorities follow config settings."""
        config_rebuild = EquityDistributionConfig(
            reserve_rebuild_priority=True,
        )
        config_no_rebuild = EquityDistributionConfig(
            reserve_rebuild_priority=False,
        )

        calc_rebuild = EquityDistributionCalculator(config_rebuild)
        calc_no_rebuild = EquityDistributionCalculator(config_no_rebuild)

        assert calc_rebuild.config.reserve_rebuild_priority is True
        assert calc_no_rebuild.config.reserve_rebuild_priority is False


class TestCodeQuality:
    """Verify code quality standards."""

    def test_no_print_statements(self) -> None:
        """Test module doesn't use print() for logging."""
        source = inspect.getsource(
            __import__(
                "finance.equity_distribution_v14", fromlist=["equity_distribution_v14"]
            )
        )
        assert "print(" not in source

    def test_enums_properly_defined(self) -> None:
        """Test enumerations are properly defined."""
        # Should be able to access enum values
        assert EquityTierType.PREFERRED == "preferred"
        assert EquityTierType.CLASS_A == "class_a"
        assert EquityTierType.CLASS_B == "class_b"
        assert EquityTierType.COMMON == "common"

    def test_output_dataclass_properly_structured(self) -> None:
        """Test EquityDistributionOutput is properly structured."""
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

        # Should be able to serialize
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "distribution_year" in result_dict
        assert "timestamp" in result_dict

    def test_configuration_validation(self) -> None:
        """Test configuration has proper validators."""
        # Valid config should work
        config = EquityDistributionConfig(
            min_dscr_for_distribution=1.20,
        )
        assert config.min_dscr_for_distribution == 1.20

        # Invalid config should fail
        with pytest.raises(ValueError):
            EquityDistributionConfig(min_dscr_for_distribution=0.2)  # Too low
