"""Regression tests for analytics/fx_sensitivity_real.py.

Tests Sprint 16 FX sensitivity implementation:
- FXSensitivityAnalyzer with real pipeline integration
- Linear regression-based sensitivity coefficients
- Relative variance attribution across configured sweep regimes
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
from statistics import fmean, linear_regression, pvariance
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.fx_sensitivity_real import (
    FXSensitivityAnalyzer,
    FXSensitivityConfig,
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
        # DELTAS around the base fx.spread_bps — non-negative so base+shock can never
        # cross the engine's >= 0 gate on an unhedged (base 0) scenario (#659).
        spread_shocks_bps=[0, 25, 50, 75, 100],
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
        # non-negative DELTAS around base fx.spread_bps (#659)
        assert config.spread_shocks_bps == [0.0, 50.0, 100.0]
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
        with pytest.raises(
            ValueError, match="confidence_level must be between 0 and 1"
        ):
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
    def test_run_fx_rate_sensitivity(
        self, mock_evaluate, sample_config, mock_pipeline_results
    ):
        """FX rate sensitivity should run pipeline for each shock."""

        # Mock pipeline to return different IRRs for different FX rates
        def mock_pipeline_call(base_config_path, overrides):
            # The fx_rate sweep drives the LIVE key start_lkr_per_usd.
            fx_rate = overrides.get("fx", {}).get("start_lkr_per_usd", 320.0)
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
    def test_sensitivity_coefficient_calculation(
        self, mock_evaluate, sample_config, mock_pipeline_results
    ):
        """Sensitivity coefficients should be calculated from regression."""
        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )
        base_fx = analyzer._base_fx()

        # Mock the LIVE key: the fx_rate sweep sends start_lkr_per_usd = base_fx*(1+shock),
        # so the implied shock is start/base_fx - 1; IRR = 0.12 - 0.15 * shock.
        def mock_pipeline_call(base_config_path, overrides):
            fx = overrides.get("fx", {})
            start = fx.get("start_lkr_per_usd")
            shock = (
                (float(start) / base_fx - 1.0)
                if start is not None
                else float(fx.get("fx_shock", 0.0))
            )
            result = mock_pipeline_results.copy()
            result["project_irr"] = 0.12 - 0.15 * shock
            return result

        mock_evaluate.side_effect = mock_pipeline_call

        result = analyzer.run()

        # Find FX rate coefficient
        fx_coef = next(
            (c for c in result.coefficients if c.parameter == "fx_rate"), None
        )
        assert fx_coef is not None
        # Should be approximately -0.15 (from our mock)
        assert abs(fx_coef.coefficient - (-0.15)) < 0.05
        assert fx_coef.r_squared is not None

    @patch("analytics.fx_sensitivity_real.evaluate_with_overrides")
    def test_variance_decomposition(
        self,
        mock_evaluate: MagicMock,
        sample_config: FXSensitivityConfig,
        mock_pipeline_results: dict[str, Any],
    ) -> None:
        """Sweep variance shares should match a known linear response."""
        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )
        base_fx = analyzer._base_fx()

        # Mock with different sensitivities
        def mock_pipeline_call(
            base_config_path: str, overrides: dict[str, Any]
        ) -> dict[str, Any]:
            fx = overrides.get("fx", {})
            fx_shock = float(fx.get("start_lkr_per_usd", base_fx)) / base_fx - 1.0
            hedge_ratio = float(fx.get("hedge_ratio", 0.0))
            spread_bps = float(fx.get("spread_bps", 0.0))
            result = mock_pipeline_results.copy()
            result["project_irr"] = (
                0.12 - 0.15 * fx_shock + 0.05 * hedge_ratio - 0.0001 * spread_bps
            )
            return result

        mock_evaluate.side_effect = mock_pipeline_call

        result = analyzer.run()

        # Var(a + bX) = b**2 Var(X), independently of the fitted coefficients.
        expected = {
            "fx_rate": (-0.15, 0.15**2 * pvariance(sample_config.fx_rate_shocks)),
            "hedge_ratio": (
                0.05,
                0.05**2 * pvariance(sample_config.hedge_ratio_values),
            ),
            "spread": (-0.0001, 0.0001**2 * pvariance(sample_config.spread_shocks_bps)),
        }
        total = sum(variance for _, variance in expected.values())
        assert len(result.coefficients) == 3
        assert {c.parameter for c in result.coefficients} == set(expected)
        assert result.total_variance == pytest.approx(total, rel=1e-10, abs=1e-15)
        for coefficient in result.coefficients:
            slope, variance = expected[coefficient.parameter]
            assert coefficient.coefficient == pytest.approx(slope, rel=1e-10, abs=1e-12)
            assert coefficient.variance_contribution == pytest.approx(
                variance / total, rel=1e-10, abs=1e-12
            )

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
    def test_regression_quality_check(
        self,
        mock_evaluate: MagicMock,
        sample_config: FXSensitivityConfig,
        mock_pipeline_results: dict[str, Any],
    ) -> None:
        """A perfect fit must retain its known nonzero FX slope."""
        analyzer = FXSensitivityAnalyzer(
            base_config_path="scenarios/test.yaml",
            config=sample_config,
        )
        base_fx = analyzer._base_fx()

        # Mock perfect linear relationship for high R-squared
        def mock_pipeline_call(
            base_config_path: str, overrides: dict[str, Any]
        ) -> dict[str, Any]:
            fx = overrides.get("fx", {})
            fx_shock = float(fx.get("start_lkr_per_usd", base_fx)) / base_fx - 1.0
            result = mock_pipeline_results.copy()
            result["project_irr"] = 0.12 - 0.10 * fx_shock  # Perfect linear
            return result

        mock_evaluate.side_effect = mock_pipeline_call

        result = analyzer.run()

        # R-squared should be high for perfect linear relationship
        fx_coef = next(
            (c for c in result.coefficients if c.parameter == "fx_rate"), None
        )
        assert fx_coef is not None
        assert fx_coef.coefficient == pytest.approx(-0.10, rel=1e-10, abs=1e-12)
        assert fx_coef.r_squared == pytest.approx(1.0, abs=1e-12)

    def test_scenario_generation_fx_shocks(self, sample_config):
        """Analyzer should generate correct number of scenarios."""
        # This is tested indirectly through pipeline calls
        assert len(sample_config.fx_rate_shocks) == 5
        assert len(sample_config.hedge_ratio_values) == 5
        assert len(sample_config.spread_shocks_bps) == 5


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestFXSensitivityIntegration:
    """Integration tests for FX sensitivity analyzer."""

    def test_real_pipeline_integration(self) -> None:
        """Compare live base-case sweeps with gateway and scalar statistical oracles."""
        scenario_path = (
            Path(__file__).resolve().parents[2]
            / "scenarios/dutchbay_basecase_2025Q4.yaml"
        )
        assert scenario_path.is_file(), f"Committed scenario missing: {scenario_path}"
        scenario = yaml.safe_load(scenario_path.read_text())
        base_fx = float(scenario["fx"]["start_lkr_per_usd"])
        # This committed scenario is unhedged, so spread is measured at FULL hedge.
        assert float(scenario["fx"].get("hedge_ratio") or 0.0) == 0.0
        base_spread = float(scenario["fx"].get("spread_bps") or 0.0)

        config = FXSensitivityConfig(
            fx_rate_shocks=[-0.05, 0.0, 0.05],
            hedge_ratio_values=[0.0, 0.5, 1.0],
            spread_shocks_bps=[0, 25, 50],  # non-negative deltas (#659)
            target_metric="project_irr",
        )

        analyzer = FXSensitivityAnalyzer(
            base_config_path=str(scenario_path),
            config=config,
        )

        result = analyzer.run()

        def project_irr(fx: dict[str, float]) -> float:
            """Evaluate directly through the canonical gateway, outside the analyzer."""
            overrides = {"fx": fx} if fx else {}
            value = float(
                evaluate_with_overrides(str(scenario_path), overrides)["project_irr"]
            )
            assert math.isfinite(value)
            return value

        baseline = project_irr({})
        assert math.isfinite(result.base_value)
        assert result.base_value == pytest.approx(baseline, rel=1e-10, abs=1e-12)
        fx_values = [
            project_irr({"start_lkr_per_usd": base_fx * (1.0 + shock)})
            for shock in config.fx_rate_shocks
        ]
        hedge_values = [
            project_irr({"hedge_ratio": hedge}) for hedge in config.hedge_ratio_values
        ]
        spread_values = [
            project_irr({"spread_bps": base_spread + shock, "hedge_ratio": 1.0})
            for shock in config.spread_shocks_bps
        ]
        # Directions are specific to this scenario's forward-versus-spot relationship.
        assert fx_values[0] > fx_values[1] > fx_values[2]
        assert hedge_values[0] < hedge_values[1] < hedge_values[2]
        assert spread_values[0] > spread_values[1] > spread_values[2]
        assert fx_values[1] == pytest.approx(baseline, rel=1e-10, abs=1e-12)
        assert hedge_values[0] == pytest.approx(baseline, rel=1e-10, abs=1e-12)
        assert spread_values[0] == pytest.approx(hedge_values[-1], rel=1e-10, abs=1e-12)

        samples = {
            "fx_rate": (config.fx_rate_shocks, fx_values),
            "hedge_ratio": (config.hedge_ratio_values, hedge_values),
            "spread": (config.spread_shocks_bps, spread_values),
        }
        assert len(result.coefficients) == 3
        assert {c.parameter for c in result.coefficients} == set(samples)
        total_variance = sum(pvariance(ys) for _, ys in samples.values())
        assert total_variance > 0.0
        assert result.total_variance == pytest.approx(
            total_variance, rel=1e-10, abs=1e-15
        )
        r_squared_values = []
        for coefficient in result.coefficients:
            xs, ys = samples[coefficient.parameter]
            # Standard-library scalar regression is independent of the analyzer's NumPy fit.
            slope, intercept = linear_regression(xs, ys)
            variance = pvariance(ys)
            residual_mean_square = fmean(
                (y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=True)
            )
            r_squared = 1.0 - residual_mean_square / variance
            r_squared_values.append(r_squared)
            assert math.isfinite(coefficient.coefficient)
            assert coefficient.coefficient == pytest.approx(slope, rel=1e-10, abs=1e-12)
            assert coefficient.r_squared == pytest.approx(r_squared, abs=1e-12)
            assert coefficient.variance_contribution == pytest.approx(
                variance / total_variance, rel=1e-10, abs=1e-12
            )
        # This is mean fit R-squared across different sweep regimes, not an
        # independent stochastic variance decomposition. Raw slopes have unlike units.
        assert result.explained_variance == pytest.approx(
            fmean(r_squared_values), abs=1e-12
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
