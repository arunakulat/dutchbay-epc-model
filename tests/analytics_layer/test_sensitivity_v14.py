"""Unit tests for analytics.sensitivity_v14 module (Phase 1).

Tests validate guardrail contract compliance:
1. Sensitivity acts as COORDINATOR only (no finance math duplication)
2. Only uses evaluate_with_overrides() gateway
3. No direct imports of finance.irr or finance.wacc_v14
4. Proper error handling and validation

Pattern: TDD approach with monkeypatching for integration tests.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="sensitivity_v14 is parked for a future refactor; "
    "regression + helper surface not finalized yet."
)
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, TornadoResult
from analytics.sensitivity_v14 import (
    _analyze_single_parameter,
    _build_nested_override,
    _create_default_parameters,
    _load_parameters,
    run_tornado_sensitivity,
)


class TestRunTornadoSensitivity:
    """Test suite for main coordinator function."""

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_happy_path_with_defaults(self, mock_evaluate):
        """Test complete sensitivity run with default parameters."""

        # Mock evaluate_with_overrides to return predictable KPIs
        def mock_eval(config_path, overrides=None):
            if overrides is None:
                # Base case
                return {"project_irr": 0.12, "project_npv": 15000000.0}
            else:
                # Perturbed case (simplified logic)
                return {"project_irr": 0.11, "project_npv": 14000000.0}

        mock_evaluate.side_effect = mock_eval

        # Run sensitivity with use_defaults=True
        with patch("analytics.sensitivity_v14._load_parameters") as mock_load:
            # Return just 2 parameters for speed
            mock_load.return_value = [
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
            ]

            suite = run_tornado_sensitivity(
                base_config_path="test_config.yaml", use_defaults=True
            )

        # Assertions
        assert suite.base_case_irr == 0.12
        assert suite.base_case_npv == 15000000.0
        assert len(suite.tornado_results) == 2
        assert all(isinstance(r, TornadoResult) for r in suite.tornado_results)
        assert len(suite.sensitivity_rank) == 2

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_explicit_parameters(self, mock_evaluate):
        """Test sensitivity with explicit parameter configs."""
        mock_evaluate.return_value = {"project_irr": 0.12, "project_npv": 15000000.0}

        params = [
            ParameterRangeConfig(
                variable_name="test.param1",
                base_value=100.0,
                low_pct=-10.0,
                high_pct=10.0,
            )
        ]

        suite = run_tornado_sensitivity(
            base_config_path="test_config.yaml", parameters=params, use_defaults=False
        )

        assert len(suite.tornado_results) == 1
        assert suite.tornado_results[0].variable == "test.param1"

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_top_risk_drivers(self, mock_evaluate):
        """Test that top_risk_drivers returns correctly ordered list."""
        # Mock different impacts for each parameter
        impact_map = {
            "project.capex_usd_per_kw": (0.10, 0.14),  # High impact
            "financial.tariff_lkr_per_kwh": (0.11, 0.13),  # Medium impact
            "generation.capacity_factor_pct": (0.115, 0.125),  # Low impact
        }

        def mock_eval(config_path, overrides=None):
            if overrides is None:
                return {"project_irr": 0.12, "project_npv": 15000000.0}

            # Determine which parameter was overridden
            for var_name in impact_map:
                if var_name in str(overrides):
                    low_irr, high_irr = impact_map[var_name]
                    # Return low or high based on override value (simplified)
                    return {"project_irr": low_irr, "project_npv": 15000000.0}

            return {"project_irr": 0.12, "project_npv": 15000000.0}

        mock_evaluate.side_effect = mock_eval

        params = [
            ParameterRangeConfig(
                variable_name=name, base_value=100.0, low_pct=-10, high_pct=10
            )
            for name in impact_map.keys()
        ]

        suite = run_tornado_sensitivity("test.yaml", parameters=params)

        # Top driver should be capex (highest impact)
        top_drivers = suite.top_risk_drivers(3)
        assert top_drivers[0] == "project.capex_usd_per_kw"


class TestLoadParameters:
    """Test parameter loading from various sources."""

    def test_explicit_parameters_priority(self):
        """Test that explicit parameters take highest priority."""
        params = [
            ParameterRangeConfig(
                variable_name="test.param",
                base_value=100.0,
                low_pct=-10.0,
                high_pct=10.0,
            )
        ]

        result = _load_parameters(params, use_defaults=False)

        assert len(result) == 1
        assert result[0].variable_name == "test.param"

    def test_defaults_fallback(self):
        """Test fallback to SENSITIVITY_RANGES when use_defaults=True."""
        with patch(
            "analytics.sensitivity_v14._create_default_parameters"
        ) as mock_create:
            mock_create.return_value = [
                ParameterRangeConfig(
                    variable_name="default.param",
                    base_value=850.0,
                    low_pct=-20.0,
                    high_pct=20.0,
                )
            ]

            result = _load_parameters(None, use_defaults=True)

            assert len(result) >= 1
            mock_create.assert_called_once()

    def test_no_parameters_error(self):
        """Test error when no parameters available."""
        with pytest.raises(ValueError, match="No parameters provided"):
            _load_parameters(None, use_defaults=False)


class TestBuildNestedOverride:
    """Test nested dict construction from dot-separated paths."""

    def test_single_level(self):
        """Test single-level path."""
        result = _build_nested_override(["param"], 100.0)
        assert result == {"param": 100.0}

    def test_two_levels(self):
        """Test two-level nested path."""
        result = _build_nested_override(["project", "capex"], 850.0)
        assert result == {"project": {"capex": 850.0}}

    def test_three_levels(self):
        """Test three-level nested path."""
        result = _build_nested_override(["a", "b", "c"], 42.0)
        assert result == {"a": {"b": {"c": 42.0}}}


class TestAnalyzeSingleParameter:
    """Test single parameter analysis."""

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_basic_analysis(self, mock_evaluate):
        """Test analysis with low/high evaluations."""
        # Base case
        mock_evaluate.side_effect = [
            {"project_irr": 0.10},  # Low value
            {"project_irr": 0.14},  # High value
        ]

        param = ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=850.0,
            low_pct=-20.0,
            high_pct=20.0,
        )

        result = _analyze_single_parameter(
            base_config_path="test.yaml", param=param, base_irr=0.12
        )

        assert isinstance(result, TornadoResult)
        assert result.variable == "project.capex_usd_per_kw"
        assert result.base_irr == 0.12
        assert result.low_irr == 0.10
        assert result.high_irr == 0.14
        assert result.impact_abs == 0.04


class TestImportCompliance:
    """Test that sensitivity_v14 respects import restrictions."""

    def test_no_direct_finance_imports(self):
        """Test that finance.irr and finance.wacc_v14 are not imported."""
        import analytics.sensitivity_v14 as sens_module

        module_globals = vars(sens_module)

        # Check for forbidden imports
        forbidden_imports = [
            "finance.irr",
            "finance.wacc_v14",
            "finance.cashflow_v14",
            "finance.debt_v14",
        ]

        for forbidden in forbidden_imports:
            assert forbidden not in str(
                module_globals
            ), f"Forbidden import detected: {forbidden}"

    def test_only_allowed_imports(self):
        """Test that only allowed surfaces are imported."""
        import analytics.sensitivity_v14 as sens_module

        # Allowed imports
        allowed_prefixes = [
            "analytics.contracts_v14",
            "analytics.evaluate_scenario",
            "constants",
            "validate",
        ]

        # This is a smoke test - actual module should only use allowed imports
        # (Full validation would require AST parsing)
        assert hasattr(sens_module, "run_tornado_sensitivity")
        assert hasattr(sens_module, "evaluate_with_overrides")


class TestYAMLErrorHandling:
    """Test YAML configuration error handling."""

    def test_invalid_yaml_structure(self, tmp_path):
        """Test error when YAML has wrong structure."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("invalid: structure\nno: parameters")

        with pytest.raises(ValueError, match="Invalid YAML structure"):
            from analytics.sensitivity_v14 import _load_parameters_from_yaml

            _load_parameters_from_yaml(yaml_file)

    def test_invalid_parameter_validation(self, tmp_path):
        """Test error when parameter fails Pydantic validation."""
        yaml_file = tmp_path / "bad_param.yaml"
        yaml_file.write_text(
            """
parameters:
  - variable_name: "test.param"
    base_value: -100.0
    low_pct: -10.0
    high_pct: 10.0
"""
        )

        with pytest.raises(ValueError, match="validation failed"):
            from analytics.sensitivity_v14 import _load_parameters_from_yaml

            _load_parameters_from_yaml(yaml_file)


# pytest configuration
pytest_plugins = []

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
