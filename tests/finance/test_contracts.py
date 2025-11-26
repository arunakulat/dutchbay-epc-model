"""Unit tests for analytics.contracts_v14 module (Phase 3: Sensitivity).

Tests validate:
- Pydantic v2 validation patterns
- ParameterRangeConfig validation logic
- TornadoResult property calculations
- Edge cases and error conditions

Pattern: TDD - These tests define expected behavior before implementation.
"""

import numpy as np
import pytest
from pydantic import ValidationError

# CORRECTED IMPORT (analytics.contracts_v14, not finance.shared_contracts)
from analytics.contracts_v14 import ParameterRangeConfig, TornadoResult


class TestParameterRangeConfig:
    """Test suite for ParameterRangeConfig validation."""

    def test_valid_basic_configuration(self):
        """Test creation with valid parameters."""
        config = ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=850.0,
            low_pct=-20.0,
            high_pct=20.0,
            steps=5,
        )

        assert config.variable_name == "project.capex_usd_per_kw"
        assert config.base_value == 850.0
        assert config.low_pct == -20.0
        assert config.high_pct == 20.0
        assert config.steps == 5

    def test_default_steps(self):
        """Test that steps defaults to 5."""
        config = ParameterRangeConfig(
            variable_name="test_param", base_value=100.0, low_pct=-10.0, high_pct=10.0
        )

        assert config.steps == 5

    def test_low_value_calculation(self):
        """Test low_value property calculation."""
        config = ParameterRangeConfig(
            variable_name="test", base_value=100.0, low_pct=-20.0, high_pct=20.0
        )

        # base * (1 + low_pct/100) = 100 * (1 - 0.20) = 80.0
        assert config.low_value == 80.0

    def test_high_value_calculation(self):
        """Test high_value property calculation."""
        config = ParameterRangeConfig(
            variable_name="test", base_value=100.0, low_pct=-20.0, high_pct=20.0
        )

        # base * (1 + high_pct/100) = 100 * (1 + 0.20) = 120.0
        assert config.high_value == 120.0

    def test_whitespace_stripping(self):
        """Test that variable_name whitespace is stripped."""
        config = ParameterRangeConfig(
            variable_name="  project.capex  ",
            base_value=100.0,
            low_pct=-10.0,
            high_pct=10.0,
        )

        assert config.variable_name == "project.capex"

    # Validation Error Tests

    def test_empty_variable_name_rejected(self):
        """Test that empty variable name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="", base_value=100.0, low_pct=-10.0, high_pct=10.0
            )

        assert "variable_name" in str(exc_info.value)

    def test_zero_base_value_rejected(self):
        """Test that base_value must be > 0."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test", base_value=0.0, low_pct=-10.0, high_pct=10.0
            )

        assert "base_value" in str(exc_info.value)

    def test_negative_base_value_rejected(self):
        """Test that negative base_value is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test", base_value=-100.0, low_pct=-10.0, high_pct=10.0
            )

        assert "base_value" in str(exc_info.value)

    def test_low_pct_too_negative_rejected(self):
        """Test that low_pct < -50 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test",
                base_value=100.0,
                low_pct=-60.0,  # Below -50
                high_pct=20.0,
            )

        assert "low_pct" in str(exc_info.value)

    def test_low_pct_positive_rejected(self):
        """Test that low_pct > 0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test",
                base_value=100.0,
                low_pct=10.0,  # Should be negative
                high_pct=20.0,
            )

        assert "low_pct" in str(exc_info.value)

    def test_high_pct_negative_rejected(self):
        """Test that high_pct < 0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test",
                base_value=100.0,
                low_pct=-10.0,
                high_pct=-5.0,  # Should be positive
            )

        assert "high_pct" in str(exc_info.value)

    def test_high_pct_too_large_rejected(self):
        """Test that high_pct > 100 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test",
                base_value=100.0,
                low_pct=-10.0,
                high_pct=150.0,  # Above 100
            )

        assert "high_pct" in str(exc_info.value)

    def test_high_less_than_abs_low_rejected(self):
        """Test that high_pct must exceed abs(low_pct)."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test",
                base_value=100.0,
                low_pct=-30.0,
                high_pct=20.0,  # 20 < 30
            )

        error_msg = str(exc_info.value)
        assert "high_pct" in error_msg or "High bound" in error_msg

    def test_steps_too_few_rejected(self):
        """Test that steps < 3 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test",
                base_value=100.0,
                low_pct=-10.0,
                high_pct=10.0,
                steps=2,  # Below minimum
            )

        assert "steps" in str(exc_info.value)

    def test_steps_too_many_rejected(self):
        """Test that steps > 20 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterRangeConfig(
                variable_name="test",
                base_value=100.0,
                low_pct=-10.0,
                high_pct=10.0,
                steps=25,  # Above maximum
            )

        assert "steps" in str(exc_info.value)

    @pytest.mark.parametrize(
        "base,low_pct,high_pct,expected_low,expected_high",
        [
            (1000, -15, 25, 850, 1250),
            (50, -10, 10, 45, 55),
            (200, -5, 15, 190, 230),
            (75, -20, 30, 60, 97.5),
        ],
    )
    def test_parametrized_value_calculations(
        self, base, low_pct, high_pct, expected_low, expected_high
    ):
        """Test low/high value calculations with multiple scenarios."""
        config = ParameterRangeConfig(
            variable_name="test", base_value=base, low_pct=low_pct, high_pct=high_pct
        )

        assert np.isclose(config.low_value, expected_low, atol=0.01)
        assert np.isclose(config.high_value, expected_high, atol=0.01)


class TestTornadoResult:
    """Test suite for TornadoResult dataclass."""

    def test_basic_creation(self):
        """Test creation with valid data."""
        result = TornadoResult(
            variable="capex_usd_per_kw", base_irr=0.12, low_irr=0.10, high_irr=0.14
        )

        assert result.variable == "capex_usd_per_kw"
        assert result.base_irr == 0.12
        assert result.low_irr == 0.10
        assert result.high_irr == 0.14

    def test_impact_pct_calculation(self):
        """Test impact_pct property calculation."""
        result = TornadoResult(
            variable="test", base_irr=0.10, low_irr=0.08, high_irr=0.12
        )

        # (high - low) / base * 100 = (0.12 - 0.08) / 0.10 * 100 = 40%
        assert np.isclose(result.impact_pct, 40.0, atol=0.01)

    def test_impact_abs_calculation(self):
        """Test impact_abs property calculation."""
        result = TornadoResult(
            variable="test", base_irr=0.10, low_irr=0.08, high_irr=0.12
        )

        # abs(high - low) = abs(0.12 - 0.08) = 0.04
        assert np.isclose(result.impact_abs, 0.04, atol=0.0001)

    def test_impact_pct_zero_base(self):
        """Test that impact_pct handles zero base gracefully."""
        result = TornadoResult(
            variable="test", base_irr=0.0, low_irr=-0.05, high_irr=0.05
        )

        # Should return 0.0 when base is zero (avoid division by zero)
        assert result.impact_pct == 0.0

    def test_negative_impact(self):
        """Test handling of inverted sensitivity (high < low)."""
        result = TornadoResult(
            variable="test",
            base_irr=0.10,
            low_irr=0.12,  # Higher IRR at low input
            high_irr=0.08,  # Lower IRR at high input
        )

        # impact_abs should still be positive (absolute value)
        assert result.impact_abs > 0

        # impact_pct reflects direction
        assert result.impact_pct < 0

    def test_nan_handling(self):
        """Test that NaN values are preserved in calculations."""
        result = TornadoResult(
            variable="test", base_irr=0.10, low_irr=np.nan, high_irr=0.12
        )

        # impact_abs with NaN should return NaN
        assert np.isnan(result.impact_abs)
        assert np.isnan(result.impact_pct)

    @pytest.mark.parametrize(
        "base,low,high,expected_pct,expected_abs",
        [
            (0.10, 0.08, 0.12, 40.0, 0.04),
            (0.15, 0.10, 0.20, 66.67, 0.10),
            (0.08, 0.06, 0.10, 50.0, 0.04),
            (0.12, 0.11, 0.13, 16.67, 0.02),
        ],
    )
    def test_parametrized_impact_calculations(
        self, base, low, high, expected_pct, expected_abs
    ):
        """Test impact calculations with multiple scenarios."""
        result = TornadoResult(
            variable="test", base_irr=base, low_irr=low, high_irr=high
        )

        assert np.isclose(result.impact_pct, expected_pct, atol=0.1)
        assert np.isclose(result.impact_abs, expected_abs, atol=0.001)

    def test_sorting_by_impact_abs(self):
        """Test that results can be sorted by impact magnitude."""
        results = [
            TornadoResult("var1", 0.10, 0.09, 0.11),  # impact_abs = 0.02
            TornadoResult("var2", 0.10, 0.08, 0.14),  # impact_abs = 0.06
            TornadoResult("var3", 0.10, 0.095, 0.105),  # impact_abs = 0.01
        ]

        sorted_results = sorted(results, key=lambda r: r.impact_abs, reverse=True)

        assert sorted_results[0].variable == "var2"  # Highest impact
        assert sorted_results[1].variable == "var1"
        assert sorted_results[2].variable == "var3"  # Lowest impact


class TestIntegration:
    """Integration tests for contracts working together."""

    def test_end_to_end_sensitivity_workflow(self):
        """Test complete workflow: config → calculation → result."""
        # Define sensitivity parameters
        param_config = ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=850.0,
            low_pct=-20.0,
            high_pct=20.0,
            steps=5,
        )

        # Simulate sensitivity results
        # (In real code, these would come from evaluate_scenario)
        base_irr = 0.115
        low_irr = 0.095  # Lower IRR with higher capex
        high_irr = 0.135  # Higher IRR with lower capex

        result = TornadoResult(
            variable=param_config.variable_name,
            base_irr=base_irr,
            low_irr=low_irr,
            high_irr=high_irr,
        )

        # Verify result makes sense
        assert result.impact_abs > 0.01  # Significant impact
        assert result.impact_pct > 10.0  # > 10% sensitivity

    def test_batch_parameter_configs(self):
        """Test creating multiple parameter configs for batch analysis."""
        params = [
            ParameterRangeConfig(
                variable_name="project.capex_usd_per_kw",
                base_value=850.0,
                low_pct=-20.0,
                high_pct=20.0,
            ),
            ParameterRangeConfig(
                variable_name="financial.tariff_lkr_per_kwh",
                base_value=65.0,
                low_pct=-15.0,
                high_pct=15.0,
            ),
            ParameterRangeConfig(
                variable_name="generation.capacity_factor_pct",
                base_value=45.0,
                low_pct=-10.0,
                high_pct=10.0,
            ),
        ]

        # Verify all configs valid
        assert len(params) == 3
        assert all(p.base_value > 0 for p in params)
        assert all(p.low_pct < 0 for p in params)
        assert all(p.high_pct > 0 for p in params)

    def test_tornado_ranking(self):
        """Test ranking tornado results by impact."""
        results = [
            TornadoResult("capex", 0.10, 0.08, 0.12),  # High impact
            TornadoResult("opex", 0.10, 0.095, 0.105),  # Low impact
            TornadoResult("tariff", 0.10, 0.07, 0.13),  # Highest impact
            TornadoResult("discount", 0.10, 0.09, 0.11),  # Medium impact
        ]

        # Sort by absolute impact
        ranked = sorted(results, key=lambda r: r.impact_abs, reverse=True)

        # Verify ranking
        assert ranked[0].variable == "tariff"  # 0.06 swing
        assert ranked[1].variable == "capex"  # 0.04 swing
        assert ranked[2].variable == "discount"  # 0.02 swing
        assert ranked[3].variable == "opex"  # 0.01 swing


# pytest configuration for this module
pytest_plugins = []

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
