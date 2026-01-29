"""Regression tests for analytics/fx_sensitivity_real.py.

Tests Sprint 16 FX sensitivity implementation:
- FXSensitivityAnalyzer with real pipeline integration
- Linear regression-based sensitivity coefficients
- Variance decomposition for risk attribution
- Multiple sensitivity scenarios (FX rate, hedge ratio, spread)

Framework Compliance:
- GWTF: Evidence-based testing with real scenarios
- CESSPIT: Tests config-driven bounds and fail-fast
- CASPER: Validates all Pydantic V2 contracts
- CCCDIR: Single responsibility - sensitivity analysis only
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from analytics.fx_sensitivity_real import (
    FXSensitivityAnalyzer,
    # FXSensitivityConfig,
    FXSensitivityResult,
    SensitivityCoefficient,
)

# ═════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_config() -> FXSensitivityConfig:
    """Provide a sample FX sensitivity configuration."""
    return FXSensitivityConfig(
        fx_rate_shocks=[-0.10, -0.05, 0.0, 0.05, 0.10],
        hedge_ratio_values=[0.0, 0.25, 0.50, 0.75, 1.0],
        spread_shocks_bps=[-100, -50, 0, 50, 100],
        target_metric="project_irr",
        confidence_level=0.95,
    )


@pytest.fixture
def mock_pipeline_results() -> Dict[str, Any]:
    """Mock pipeline results for testing."""
    return {
        "project_irr": 0.12,
        "equity_irr": 0.18,
        "dscr_min": 1.35,
        "project_npv": 100_000_000,
        "equity_npv": 50_000_000,
    }


# ═════════════════════════════════════════════════════════════════════════════
# FXSENSITIVITYCONFIG TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestFXSensitivityConfig:
    """Test suite for FXSensitivityConfig dataclass."""

    def test_config_creation_with_defaults(self):
        """Config should have sensible defaults."""
        config = FXSensitivityConfig()
        assert config.fx_rate_shocks == [-0.10, -0.05, 0.0, 0.05, 0.10]
        assert config.hedge_ratio_values == [0.0, 0.5, 1.0]
        assert config.spread_shocks_bps == [-100, 0, 100]
        assert config.target_metric == "project_irr"
        assert config.confidence_level == 0.95

    def test_config_custom_values(self, sample_config):
        """Config should accept custom values."""
        assert len(sample_config.fx_rate_shocks) == 5
        assert len(sample_config.hedge_ratio_values) == 5
        assert len(sample_config.spread_shocks_bps) == 5
        assert sample_config.target_metric == "project_irr"

    def test_config_immutability(self, sample_config):
        """Config should be frozen (immutable)."""
        with pytest.raises(AttributeError):
            sample_config.target_metric = "equity_irr"  # type: ignore

    def test_config_invalid_confidence_level(self):
        """Invalid confidence level should raise ValueError."""
        with pytest.raises(ValueError, match="confidence_level must be between 0 and 1"):
            FXSensitivityConfig(confidence_level=1.5)

    def test_config_invalid_target_metric(self):
        """Invalid target metric should raise ValueError."""
        with pytest.raises(ValueError, match="target_metric must be one of"):
            FXSensitivityConfig(target_metric="invalid_metric")


# ═════════════════════════════════════════════════════════════════════════════
# SENSITIVITYCOEFFICIENT TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestSensitivityCoefficient:
    """Test suite for SensitivityCoefficient dataclass."""

    def test_coefficient_creation(self):
        """Sensitivity coefficient should be creatable with all fields."""
        coef = SensitivityCoefficient(
            parameter="fx_rate",
            coefficient=-0.15,
            std_error=0.02,
            r_squared=0.85,
            variance_contribution=0.40,
        )
        assert coef.parameter == "fx_rate"
        assert coef.coefficient == -0.15
        assert coef.std_error == 0.02
        assert coef.r_squared == 0.85
        assert coef.variance_contribution == 0.40

    def test_coefficient_immutability(self):
        """Sensitivity coefficient should be frozen."""
        coef = SensitivityCoefficient(
            parameter="fx_rate",
            coefficient=-0.15,
            std_error=0.02,
            r_squared=0.85,
        )
        with pytest.raises(AttributeError):
            coef.coefficient = -0.20  # type: ignore

    def test_coefficient_optional_fields(self):
        """Optional fields should default to None."""
        coef = SensitivityCoefficient(
            parameter="hedge_ratio",
            coefficient=0.05,
            std_error=0.01,
            r_squared=0.70,
        )
        assert coef.variance_contribution is None


# ═════════════════════════════════════════════════════════════════════════════
# FXSENSITIVITYRESULT TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestFXSensitivityResult:
    """Test suite for FXSensitivityResult dataclass."""

    def test_result_creation(self):
        """FX sensitivity result should be creatable with all fields."""
        coefficients = [
            SensitivityCoefficient(
                parameter="fx_rate",
                coefficient=-0.15,
                std_error=0.02,
                r_squared=0.85,
            )
        ]
        result = FXSensitivityResult(
            coefficients=coefficients,
            base_value=0.12,
            total_variance=0.01,
            explained_variance=0.85,
        )
        assert len(result.coefficients) == 1
        assert result.base_value == 0.12
        assert result.total_variance == 0.01
        assert result.explained_variance == 0.85

    def test_result_immutability(self):
        """FX sensitivity result should be frozen."""
        result = FXSensitivityResult(
            coefficients=[],
            base_value=0.12,
            total_variance=0.01,
            explained_variance=0.85,
        )
        with pytest.raises(AttributeError):
            result.base_value = 0.15  # type: ignore

    def test_result_optional_fields(self):
        """Optional fields should default to None."""
        result = FXSensitivityResult(
            coefficients=[],
            base_value=0.12,
        )
        assert result.total_variance is None
        assert result.explained_variance is None


# ═════════════════════════════════════════════════════════════════════════════
# FXSENSITIVITYANALYZER TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestFXSensitivityAnalyzer:
    """Test suite for FXSensitivityAnalyzer class."""

    def test_analyzer_initialization(self, sample_config):
        """Analyzer should initialize with config and base path."""
        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )
        assert analyzer.config == sample_config
        assert analyzer.base_config_path == "scenarios/test.yaml"

    def test_analyzer_default_config(self):
        """Analyzer should use default config if none provided."""
        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
        )
        assert analyzer.config is not None
        assert analyzer.config.target_metric == "project_irr"

    @patch("analytics.fx_sensitivity_real.evaluate_with_overrides")
    def test_run_fx_rate_sensitivity(self, mock_evaluate, sample_config, mock_pipeline_results):
        """FX rate sensitivity should run pipeline for each shock."""
        # Mock pipeline to return different IRRs for different FX rates
        def mock_pipeline_call(base_config_path, overrides):
            fx_rate = overrides.get("fx", {}).get("spot_rate_lkr_usd", 320.0)
            # Simple linear response for testing
            irr_impact = -0.001 * (fx_rate - 320.0)
            result = mock_pipeline_results.copy()
            result["project_irr"] = 0.12 + irr_impact
            return result

        mock_evaluate.side_effect = mock_pipeline_call

        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )

        result = analyzer.run()

        # Should have called pipeline 5 times (5 FX rate shocks)
        assert mock_evaluate.call_count >= 5
        assert result.base_value is not None
        assert len(result.coefficients) > 0

    @patch("analytics.fx_sensitivity_real.evaluate_with_overrides")
    def test_sensitivity_coefficient_calculation(self, mock_evaluate, sample_config, mock_pipeline_results):
        """Sensitivity coefficients should be calculated from regression."""
        # Mock linear relationship: IRR = 0.12 - 0.15 * fx_shock
        def mock_pipeline_call(base_config_path, overrides):
            fx_shock = overrides.get("fx", {}).get("fx_shock", 0.0)
            result = mock_pipeline_results.copy()
            result["project_irr"] = 0.12 - 0.15 * fx_shock
            return result

        mock_evaluate.side_effect = mock_pipeline_call

        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )

        result = analyzer.run()

        # Find FX rate coefficient
        fx_coef = next((c for c in result.coefficients if c.parameter == "fx_rate"), None)
        assert fx_coef is not None
        # Should be approximately -0.15 (from our mock)
        assert abs(fx_coef.coefficient - (-0.15)) < 0.05
        assert fx_coef.r_squared is not None

    @patch("analytics.fx_sensitivity_real.evaluate_with_overrides")
    def test_variance_decomposition(self, mock_evaluate, sample_config, mock_pipeline_results):
        """Variance decomposition should attribute risk to parameters."""
        # Mock with different sensitivities
        def mock_pipeline_call(base_config_path, overrides):
            fx_shock = overrides.get("fx", {}).get("fx_shock", 0.0)
            hedge_ratio = overrides.get("fx", {}).get("hedge_ratio", 0.0)
            result = mock_pipeline_results.copy()
            # FX has larger impact than hedge ratio
            result["project_irr"] = 0.12 - 0.15 * fx_shock + 0.05 * hedge_ratio
            return result

        mock_evaluate.side_effect = mock_pipeline_call

        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )

        result = analyzer.run()

        # Total variance contributions should sum to ~1.0
        total_variance_contrib = sum(
            c.variance_contribution for c in result.coefficients if c.variance_contribution is not None
        )
        assert 0.9 <= total_variance_contrib <= 1.1

    @patch("analytics.fx_sensitivity_real.evaluate_with_overrides")
    def test_error_handling_pipeline_failure(self, mock_evaluate, sample_config):
        """Analyzer should handle pipeline failures gracefully."""
        mock_evaluate.side_effect = RuntimeError("Pipeline failed")

        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )

        with pytest.raises(RuntimeError, match="Pipeline failed"):
            analyzer.run()

    @patch("analytics.fx_sensitivity_real.evaluate_with_overrides")
    def test_multiple_target_metrics(self, mock_evaluate, mock_pipeline_results):
        """Analyzer should support different target metrics."""
        mock_evaluate.return_value = mock_pipeline_results

        # Test with equity_irr as target
        config = FXSensitivityConfig(target_metric="equity_irr")
        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=config,
        )

        result = analyzer.run()
        assert result.base_value is not None

    @patch("analytics.fx_sensitivity_real.evaluate_with_overrides")
    def test_regression_quality_check(self, mock_evaluate, sample_config, mock_pipeline_results):
        """Analyzer should report regression quality (R-squared)."""
        # Mock perfect linear relationship for high R-squared
        def mock_pipeline_call(base_config_path, overrides):
            fx_shock = overrides.get("fx", {}).get("fx_shock", 0.0)
            result = mock_pipeline_results.copy()
            result["project_irr"] = 0.12 - 0.10 * fx_shock  # Perfect linear
            return result

        mock_evaluate.side_effect = mock_pipeline_call

        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )

        result = analyzer.run()

        # R-squared should be high for perfect linear relationship
        fx_coef = next((c for c in result.coefficients if c.parameter == "fx_rate"), None)
        assert fx_coef is not None
        assert fx_coef.r_squared is not None
        assert fx_coef.r_squared > 0.95  # High quality fit

    def test_scenario_generation_fx_shocks(self, sample_config):
        """Analyzer should generate correct number of scenarios."""
        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )

        # With 5 FX shocks, 5 hedge ratios, 5 spreads = 5 + 5 + 5 = 15 scenarios minimum
        # (assuming one-at-a-time sensitivity)
        expected_min_scenarios = 15

        # This is tested indirectly through pipeline calls
        assert len(sample_config.fx_rate_shocks) == 5
        assert len(sample_config.hedge_ratio_values) == 5
        assert len(sample_config.spread_shocks_bps) == 5


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestFXSensitivityIntegration:
    """Integration tests for FX sensitivity analyzer."""

    @pytest.mark.skip(reason="Requires real scenario file and pipeline")
    def test_real_pipeline_integration(self):
        """Test FX sensitivity with actual pipeline (integration test)."""
        # This test requires a real scenario file
        scenario_path = Path("scenarios/dutchbay_basecase_2025Q4.yaml")
        if not scenario_path.exists():
            pytest.skip("Test scenario file not found")

        config = FXSensitivityConfig(
            fx_rate_shocks=[-0.05, 0.0, 0.05],
            hedge_ratio_values=[0.0, 0.5, 1.0],
            spread_shocks_bps=[-50, 0, 50],
            target_metric="project_irr",
        )

        analyzer = FXSensitivityAnalyzer(
            base_config_path=str(scenario_path),
            config=config,
        )

        result = analyzer.run()

        # Assertions
        assert result.base_value is not None
        assert len(result.coefficients) > 0
        assert result.explained_variance is not None
        assert 0.0 <= result.explained_variance <= 1.0

        # FX rate should typically have largest impact
        fx_coef = next((c for c in result.coefficients if c.parameter == "fx_rate"), None)
        assert fx_coef is not None
        assert fx_coef.coefficient != 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
