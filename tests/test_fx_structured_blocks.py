"""Comprehensive test suite for FX structured blocks.

Tests cover:
- FXStructuredBlock validation and edge cases
- FXRegimeScenario multi-regime support
- FXRiskProfile lender-grade metrics
- FXSensitivityConfig tornado analysis
- FXMonteCarloConfig 100k simulations
- FX loader functions
- FX curve generation with CI

All tests follow Go with the Flow v2.3/v14 standards.

Refs: Issue #31, v14R6, v2.3V2399 (tests gate changes)
"""

from __future__ import annotations

import pytest

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXMonteCarloConfig,
    FXRegimeScenario,
    FXRiskProfile,
    FXSensitivityConfig,
    FXStructuredBlock,
    RegimeType,
    VolatilityMethod,
)
from analytics.fx.fx_loader import (
    build_fx_curve_from_block,
    load_fx_structured_block,
    validate_fx_structured_config,
)


class TestFXStructuredBlockValidation:
    """Tests for FXStructuredBlock validation logic."""

    def test_valid_structured_block(self) -> None:
        """Valid FX structured block should construct."""
        block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        assert block.start_lkr_per_usd == 375.0
        assert block.annual_depr == 0.03
        assert block.base_currency == "USD"
        assert block.target_currency == "LKR"
        assert block.regime == RegimeType.RECENT

    def test_zero_start_rate_rejected(self) -> None:
        """Start rate must be > 0."""
        with pytest.raises(ValueError, match="start_lkr_per_usd"):
            FXStructuredBlock(
                start_lkr_per_usd=0.0,
                annual_depr=0.03,
            )

    def test_negative_start_rate_rejected(self) -> None:
        """Negative start rate rejected."""
        with pytest.raises(ValueError, match="start_lkr_per_usd"):
            FXStructuredBlock(
                start_lkr_per_usd=-10.0,
                annual_depr=0.03,
            )

    def test_negative_volatility_rejected(self) -> None:
        """Volatility must be >= 0."""
        with pytest.raises(ValueError, match="volatility"):
            FXStructuredBlock(
                start_lkr_per_usd=375.0,
                annual_depr=0.03,
                volatility=-0.1,
            )

    @pytest.mark.parametrize(
        "correlation",
        [-1.5, 1.5, 2.0],
        ids=["too_low", "too_high", "way_too_high"],
    )
    def test_invalid_correlation_rejected(
        self, correlation: float
    ) -> None:
        """Correlation must be in [-1, 1]."""
        with pytest.raises(ValueError, match="correlation_with_revenue"):
            FXStructuredBlock(
                start_lkr_per_usd=375.0,
                annual_depr=0.03,
                correlation_with_revenue=correlation,
            )

    @pytest.mark.parametrize(
        "hedge",
        [-0.1, 1.1, 2.0],
        ids=["negative", "over_100pct", "way_over"],
    )
    def test_invalid_hedge_ratio_rejected(self, hedge: float) -> None:
        """Hedge ratio must be in [0, 1]."""
        with pytest.raises(ValueError, match="hedge_ratio"):
            FXStructuredBlock(
                start_lkr_per_usd=375.0,
                annual_depr=0.03,
                hedge_ratio=hedge,
            )

    def test_appreciation_scenario_accepted(self) -> None:
        """Negative depreciation (appreciation) is valid."""
        block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=-0.02,
        )

        assert block.annual_depr == -0.02


class TestFXRegimeScenarios:
    """Tests for multi-regime scenario support."""

    def test_valid_regime_scenario(self) -> None:
        """Valid scenario should construct."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        scenario = FXRegimeScenario(
            scenario_name="Base Case",
            structured_block=base_block,
            probability=0.6,
            years=20,
        )

        assert scenario.scenario_name == "Base Case"
        assert scenario.probability == 0.6
        assert scenario.years == 20

    def test_invalid_probability_rejected(self) -> None:
        """Probability must be in [0, 1]."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        with pytest.raises(ValueError, match="probability"):
            FXRegimeScenario(
                scenario_name="Bad",
                structured_block=base_block,
                probability=1.5,
                years=20,
            )

    def test_zero_years_rejected(self) -> None:
        """Years must be >= 1."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        with pytest.raises(ValueError, match="years"):
            FXRegimeScenario(
                scenario_name="Bad",
                structured_block=base_block,
                probability=0.5,
                years=0,
            )

    def test_shock_scenario(self) -> None:
        """Shock scenario with magnitude."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        scenario = FXRegimeScenario(
            scenario_name="Stressed",
            structured_block=base_block,
            probability=0.1,
            years=20,
            apply_shock=True,
            shock_magnitude=0.15,
        )

        assert scenario.apply_shock is True
        assert scenario.shock_magnitude == 0.15


class TestFXRiskProfiles:
    """Tests for lender-grade risk profile outputs."""

    def test_valid_risk_profile(self) -> None:
        """Valid risk profile should construct."""
        risk = FXRiskProfile(
            scenario_name="Base",
            var_95=15.0,
            var_99=22.5,
            expected_shortfall=18.0,
            max_drawdown_pct=12.5,
            sharpe_ratio=0.85,
            volatility_realized=0.10,
        )

        assert risk.scenario_name == "Base"
        assert risk.var_95 == 15.0
        assert risk.var_99 == 22.5

    def test_risk_profile_with_correlation_matrix(self) -> None:
        """Risk profile with multi-currency correlation."""
        corr_matrix = ((1.0, 0.75), (0.75, 1.0))

        risk = FXRiskProfile(
            scenario_name="Multi-currency",
            var_95=20.0,
            var_99=30.0,
            expected_shortfall=25.0,
            max_drawdown_pct=15.0,
            sharpe_ratio=0.70,
            volatility_realized=0.12,
            correlation_matrix=corr_matrix,
        )

        assert risk.correlation_matrix == corr_matrix


class TestFXSensitivityConfig:
    """Tests for sensitivity/tornado configuration."""

    def test_valid_sensitivity_config(self) -> None:
        """Valid sensitivity config should construct."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        sens = FXSensitivityConfig(
            base_block=base_block,
            parameter_name="annual_depr",
            low_value=0.01,
            high_value=0.05,
            num_steps=5,
        )

        assert sens.parameter_name == "annual_depr"
        assert sens.low_value == 0.01
        assert sens.high_value == 0.05

    def test_num_steps_too_low_rejected(self) -> None:
        """num_steps must be >= 2."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        with pytest.raises(ValueError, match="num_steps"):
            FXSensitivityConfig(
                base_block=base_block,
                parameter_name="annual_depr",
                low_value=0.01,
                high_value=0.05,
                num_steps=1,
            )


class TestFXMonteCarloConfig:
    """Tests for Monte Carlo simulation configuration."""

    def test_valid_monte_carlo_config(self) -> None:
        """Valid MC config with 100k simulations."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        mc_config = FXMonteCarloConfig(
            base_block=base_block,
            num_simulations=100_000,
            time_horizon_years=20,
        )

        assert mc_config.num_simulations == 100_000
        assert mc_config.time_horizon_years == 20

    def test_too_few_simulations_rejected(self) -> None:
        """num_simulations must be >= 1000."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        with pytest.raises(ValueError, match="num_simulations"):
            FXMonteCarloConfig(
                base_block=base_block,
                num_simulations=500,
                time_horizon_years=20,
            )

    def test_zero_time_horizon_rejected(self) -> None:
        """time_horizon_years must be >= 1."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        with pytest.raises(ValueError, match="time_horizon_years"):
            FXMonteCarloConfig(
                base_block=base_block,
                num_simulations=10_000,
                time_horizon_years=0,
            )

    def test_monte_carlo_with_seed(self) -> None:
        """MC config with seed for reproducibility."""
        base_block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        mc_config = FXMonteCarloConfig(
            base_block=base_block,
            num_simulations=100_000,
            time_horizon_years=20,
            seed=42,
        )

        assert mc_config.seed == 42


class TestFXLoader:
    """Tests for FX loader functions."""

    def test_load_valid_structured_block(self) -> None:
        """Load valid FX structured block from dict."""
        config = {
            "fx": {
                "start_lkr_per_usd": 375.0,
                "annual_depr": 0.03,
            }
        }

        block = load_fx_structured_block(config)

        assert block.start_lkr_per_usd == 375.0
        assert block.annual_depr == 0.03

    def test_load_missing_fx_key_raises(self) -> None:
        """Missing 'fx' key should raise KeyError."""
        config = {"project": {"name": "test"}}

        with pytest.raises(KeyError, match="fx"):
            load_fx_structured_block(config)

    def test_load_scalar_fx_raises(self) -> None:
        """Scalar FX config should raise ValueError."""
        config = {"fx": 375.0}

        with pytest.raises(ValueError, match="Scalar 'fx' configs"):
            load_fx_structured_block(config)

    def test_validate_fx_structured_config_valid(self) -> None:
        """Validation should pass for valid config."""
        config = {
            "fx": {
                "start_lkr_per_usd": 375.0,
                "annual_depr": 0.03,
            }
        }

        assert validate_fx_structured_config(config) is True

    def test_validate_fx_missing_keys_fails(self) -> None:
        """Validation should fail for missing keys."""
        config = {"fx": {"start_lkr_per_usd": 375.0}}

        assert validate_fx_structured_config(config) is False


class TestFXCurveGeneration:
    """Tests for FX curve generation from structured blocks."""

    def test_build_fx_curve_basic(self) -> None:
        """Build basic FX curve from structured block."""
        block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
        )

        curve = build_fx_curve_from_block(block, years=3)

        assert len(curve.rates) == 3
        assert curve.years == [0, 1, 2]
        # Year 0: 375.0 * 1.03^0 = 375.0
        assert abs(curve.rates[0] - 375.0) < 0.01
        # Year 1: 375.0 * 1.03^1 = 386.25
        assert abs(curve.rates[1] - 386.25) < 0.01

    def test_build_fx_curve_with_confidence_interval(self) -> None:
        """Build FX curve with 95% confidence intervals."""
        block = FXStructuredBlock(
            start_lkr_per_usd=375.0,
            annual_depr=0.03,
            volatility=0.10,
        )

        curve = build_fx_curve_from_block(
            block, years=3, include_confidence_interval=True
        )

        assert curve.confidence_interval_lower is not None
        assert curve.confidence_interval_upper is not None
        assert len(curve.confidence_interval_lower) == 3
        assert len(curve.confidence_interval_upper) == 3

    def test_curve_output_validation(self) -> None:
        """FXCurveOutput validates length consistency."""
        with pytest.raises(ValueError, match="Length mismatch"):
            FXCurveOutput(
                years=[0, 1, 2],
                rates=[375.0, 386.25],  # Mismatch
                regime=RegimeType.RECENT,
                metadata={},
            )


# EOF
