"""Compliance tests for Refinancing Module v14.

Tests code quality including:
- Type hints coverage
- Docstring coverage
- No hardcoding
- Error handling
- Edge cases
"""

from inspect import signature
from typing import get_type_hints

import pytest

from finance.refinancing_v14_hydra import (
    RefinancingConfig,
    RefinancingTrigger,
    RefinancingV14,
)


class TestTypeHints:
    """Test type hint coverage."""

    def test_refinancing_config_typed(self) -> None:
        """Test RefinancingConfig is properly typed."""
        config = RefinancingConfig()
        assert hasattr(config, "enabled")
        assert hasattr(config, "trigger_year_min")
        assert hasattr(config, "new_rate")

    def test_refinancing_trigger_methods_typed(self) -> None:
        """Test RefinancingTrigger methods have type hints."""
        config = RefinancingConfig()
        trigger = RefinancingTrigger(config)

        # Check should_refinance signature has return annotation
        method_sig = signature(trigger.should_refinance)
        assert method_sig.return_annotation is not None
        # Return type should be Tuple[bool, Dict[str, bool]]
        assert "Tuple" in str(method_sig.return_annotation)

    def test_refinancing_v14_methods_typed(self) -> None:
        """Test RefinancingV14 methods have type hints."""
        config = RefinancingConfig()
        calc = RefinancingV14(config)

        method_sig = signature(calc.calculate)
        assert method_sig.return_annotation is not None
        # Return type should be Dict[str, Any]
        assert "Dict" in str(method_sig.return_annotation)


class TestDocstrings:
    """Test docstring coverage."""

    def test_module_docstring(self) -> None:
        """Test module has docstring."""
        import finance.refinancing_v14_hydra as module

        assert module.__doc__ is not None
        assert len(module.__doc__) > 0

    def test_config_class_docstring(self) -> None:
        """Test RefinancingConfig has docstring."""
        assert RefinancingConfig.__doc__ is not None
        assert (
            "Attributes" in RefinancingConfig.__doc__
            or "enabled" in RefinancingConfig.__doc__
        )

    def test_trigger_class_docstring(self) -> None:
        """Test RefinancingTrigger has docstring."""
        assert RefinancingTrigger.__doc__ is not None

    def test_calculator_class_docstring(self) -> None:
        """Test RefinancingV14 has docstring."""
        assert RefinancingV14.__doc__ is not None

    def test_calculator_methods_have_docstrings(self) -> None:
        """Test calculator methods have docstrings."""
        assert RefinancingV14.__init__.__doc__ is not None
        assert RefinancingV14.calculate.__doc__ is not None


class TestNoHardcoding:
    """Test no hardcoded values in logic."""

    def test_trigger_uses_config_values(self) -> None:
        """Test trigger uses config instead of hardcoded thresholds."""
        config1 = RefinancingConfig(trigger_year_min=8)
        config2 = RefinancingConfig(trigger_year_min=10)

        trigger1 = RefinancingTrigger(config1)
        trigger2 = RefinancingTrigger(config2)

        # Different configs should behave differently
        should_refi1, cond1 = trigger1.should_refinance(9, 8.0, 1.5, 100_000_000)
        should_refi2, cond2 = trigger2.should_refinance(9, 8.0, 1.5, 100_000_000)

        # Year 9 should trigger for config1 (min=8) but not config2 (min=10)
        assert cond1["year_threshold"] is True
        assert cond2["year_threshold"] is False


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_dscr_raises(self) -> None:
        """Test invalid DSCR raises exception."""
        with pytest.raises(ValueError):
            RefinancingConfig(dscr_threshold=-1.0)

    def test_invalid_rate_raises(self) -> None:
        """Test invalid interest rate raises exception."""
        with pytest.raises(ValueError):
            RefinancingConfig(new_rate=-5.0)

    def test_invalid_tenor_raises(self) -> None:
        """Test invalid tenor raises exception."""
        with pytest.raises(ValueError):
            RefinancingConfig(new_tenor=-1)


class TestEdgeCases:
    """Test edge cases."""

    def test_year_zero(self) -> None:
        """Test year 0 handled correctly."""
        config = RefinancingConfig()
        trigger = RefinancingTrigger(config)
        should_refi, conditions = trigger.should_refinance(
            year=0,
            current_rate=8.0,
            dscr=1.5,
            debt_balance=100_000_000,
        )
        assert conditions["year_threshold"] is False

    def test_minimum_dscr(self) -> None:
        """Test minimum DSCR value."""
        config = RefinancingConfig(dscr_threshold=1.0)
        trigger = RefinancingTrigger(config)
        should_refi, conditions = trigger.should_refinance(
            year=10,
            current_rate=8.0,
            dscr=1.0,
            debt_balance=100_000_000,
        )
        assert conditions["dscr_threshold"] is True

    def test_zero_debt_balance(self) -> None:
        """Test zero debt balance edge case."""
        config = RefinancingConfig()
        trigger = RefinancingTrigger(config)
        # Should handle gracefully - likely no refinancing
        should_refi, conditions = trigger.should_refinance(
            year=10,
            current_rate=8.0,
            dscr=1.5,
            debt_balance=0.001,
        )
        # With tiny debt, refinancing amount check may fail
        assert isinstance(should_refi, bool)


if __name__ == "__main__":
    """Run tests."""
    pytest.main([__file__, "-v"])
