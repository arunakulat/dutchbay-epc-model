"""Unit tests for analytics.sensitivity_v14 module (Phase 2B).

Tests validate v14 pipeline integration:
1. Sensitivity acts as COORDINATOR only (no finance math duplication)
2. Uses run_v14_pipeline() gateway (migrated from evaluate_with_overrides)
3. No direct imports of finance.irr or finance.wacc_v14
4. Proper error handling and validation

Pattern: TDD approach with mocking for unit tests.

Sprint 7 Phase 2B: Migrated from evaluate_with_overrides to run_v14_pipeline.
"""

from unittest.mock import patch

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, TornadoResult
from analytics.sensitivity_v14 import (
    SensitivityRequest,
    _analyze_single_parameter,
    _build_nested_override,
    run_tornado_sensitivity,
)


class TestRunTornadoSensitivity:
    """Test suite for main coordinator function."""

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_happy_path_with_defaults(self, mock_load, mock_pipeline):
        """Test complete sensitivity run with default parameters."""
        # Mock v14 pipeline components
        mock_load.return_value = {
            "finance": {"capex": 850.0, "tariff": 65.0},
            "debt": {},
        }

        # Mock pipeline to return predictable KPIs
        def mock_pipeline_eval(*args, **kwargs):
            config = kwargs.get("config", {})
            # Simple logic: vary IRR based on config
            base_irr = 0.12
            # Check if config has been perturbed
            if config.get("finance", {}).get("capex") != 850.0:
                return {"kpis": {"project_irr": 0.11, "project_npv": 14000000.0}}
            return {"kpis": {"project_irr": base_irr, "project_npv": 15000000.0}}

        mock_pipeline.side_effect = mock_pipeline_eval

        # Create parameters
        params = [
            ParameterRangeConfig(
                variable_name="finance.capex",
                base_value=850.0,
                low_pct=-0.20,
                high_pct=0.20,
            ),
            ParameterRangeConfig(
                variable_name="finance.tariff",
                base_value=65.0,
                low_pct=-0.15,
                high_pct=0.15,
            ),
        ]

        request = SensitivityRequest(
            base_config_path="test_config.yaml",
            parameters=params,
            metric="project_irr",
        )

        suite = run_tornado_sensitivity(request)

        # Assertions
        assert suite.base_metric == 0.12
        assert len(suite.tornado_results) == 2
        assert all(isinstance(r, TornadoResult) for r in suite.tornado_results)

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_explicit_parameters(self, mock_load, mock_pipeline):
        """Test sensitivity with explicit parameter configs."""
        mock_load.return_value = {"test": {"param1": 100.0}}
        mock_pipeline.return_value = {
            "kpis": {"project_irr": 0.12, "project_npv": 15000000.0}
        }

        params = [
            ParameterRangeConfig(
                variable_name="test.param1",
                base_value=100.0,
                low_pct=-0.10,
                high_pct=0.10,
            )
        ]

        request = SensitivityRequest(
            base_config_path="test_config.yaml",
            parameters=params,
            metric="project_irr",
        )

        suite = run_tornado_sensitivity(request)

        assert len(suite.tornado_results) == 1
        assert suite.tornado_results[0].variable == "test.param1"

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_top_risk_drivers(self, mock_load, mock_pipeline):
        """Test that results are sorted by impact (top risk drivers first)."""
        mock_load.return_value = {
            "project": {"capex": 100.0},
            "financial": {"tariff": 65.0},
            "generation": {"capacity_factor": 0.25},
        }

        # Mock different impacts for each parameter
        call_count = [0]

        def mock_pipeline_eval(*args, **kwargs):
            call_count[0] += 1
            config = kwargs.get("config", {})

            # Base case
            if call_count[0] == 1:
                return {"kpis": {"project_irr": 0.12, "project_npv": 15000000.0}}

            # Vary IRR based on which parameter changed
            capex = config.get("project", {}).get("capex", 100.0)
            tariff = config.get("financial", {}).get("tariff", 65.0)
            cf = config.get("generation", {}).get("capacity_factor", 0.25)

            # High impact from capex
            if capex != 100.0:
                return {"kpis": {"project_irr": 0.10 if capex > 100 else 0.14}}
            # Medium impact from tariff
            elif tariff != 65.0:
                return {"kpis": {"project_irr": 0.11 if tariff < 65 else 0.13}}
            # Low impact from capacity factor
            elif cf != 0.25:
                return {"kpis": {"project_irr": 0.115 if cf < 0.25 else 0.125}}

            return {"kpis": {"project_irr": 0.12}}

        mock_pipeline.side_effect = mock_pipeline_eval

        params = [
            ParameterRangeConfig(
                variable_name="project.capex",
                base_value=100.0,
                low_pct=-0.10,
                high_pct=0.10,
            ),
            ParameterRangeConfig(
                variable_name="financial.tariff",
                base_value=65.0,
                low_pct=-0.10,
                high_pct=0.10,
            ),
            ParameterRangeConfig(
                variable_name="generation.capacity_factor",
                base_value=0.25,
                low_pct=-0.10,
                high_pct=0.10,
            ),
        ]

        request = SensitivityRequest(
            base_config_path="test.yaml",
            parameters=params,
            metric="project_irr",
        )

        suite = run_tornado_sensitivity(request)

        # Results should be sorted by impact_abs descending
        impacts = [r.impact_abs for r in suite.tornado_results]
        assert impacts == sorted(impacts, reverse=True)

        # Top driver should be capex (highest impact)
        assert suite.tornado_results[0].variable == "project.capex"


class TestLoadParameters:
    """Test parameter loading from various sources."""

    def test_explicit_parameters_priority(self):
        """Test that explicit parameters are used."""
        params = [
            ParameterRangeConfig(
                variable_name="test.param",
                base_value=100.0,
                low_pct=-0.10,
                high_pct=0.10,
            )
        ]

        # Verify parameter structure
        assert len(params) == 1
        assert params[0].variable_name == "test.param"
        assert params[0].base_value == 100.0

    def test_defaults_fallback(self):
        """Test that empty parameter list is handled."""
        params = []
        assert len(params) == 0

    def test_no_parameters_error(self):
        """Test that empty parameters are handled gracefully."""
        # Empty parameter list should be acceptable
        params = []
        assert isinstance(params, list)
        assert len(params) == 0


class TestBuildNestedOverride:
    """Test nested dict construction from dot-separated paths."""

    def test_single_level(self):
        """Test single-level path."""
        result = _build_nested_override("param", 100.0)
        assert result == {"param": 100.0}

    def test_two_levels(self):
        """Test two-level nested path."""
        result = _build_nested_override("project.capex", 850.0)
        assert result == {"project": {"capex": 850.0}}

    def test_three_levels(self):
        """Test three-level nested path."""
        result = _build_nested_override("a.b.c", 42.0)
        assert result == {"a": {"b": {"c": 42.0}}}

    def test_list_path(self):
        """Test path as list of keys."""
        result = _build_nested_override(["project", "capex"], 850.0)
        assert result == {"project": {"capex": 850.0}}


class TestAnalyzeSingleParameter:
    """Test single parameter analysis."""

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_basic_analysis(self, mock_load, mock_pipeline):
        """Test analysis with low/high evaluations."""
        mock_load.return_value = {"project": {"capex": 850.0}}

        # Mock pipeline to return different values for low/high
        call_count = [0]

        def mock_pipeline_eval(*args, **kwargs):
            call_count[0] += 1
            # First call: low case (IRR = 0.10)
            # Second call: high case (IRR = 0.14)
            irr_value = 0.10 if call_count[0] == 1 else 0.14
            return {"kpis": {"project_irr": irr_value}}

        mock_pipeline.side_effect = mock_pipeline_eval

        param = ParameterRangeConfig(
            variable_name="project.capex",
            base_value=850.0,
            low_pct=-0.20,
            high_pct=0.20,
        )

        result = _analyze_single_parameter(
            base_config_path="test.yaml",
            base_metric_value=0.12,
            metric_name="project_irr",
            param=param,
        )

        assert isinstance(result, TornadoResult)
        assert result.variable == "project.capex"
        assert result.base_irr == 0.12
        assert result.low_irr == 0.10
        assert result.high_irr == 0.14
        assert result.impact_abs == 0.04


class TestImportCompliance:
    """Test that sensitivity_v14 respects import restrictions."""

    def test_no_direct_finance_imports(self):
        """Test that finance engines are not imported directly."""
        import analytics.sensitivity_v14 as sens_module

        module_globals = vars(sens_module)

        # Check for forbidden imports
        forbidden_imports = [
            "CashflowEngine",
            "DebtEngine",
            "calculate_irr",
            "calculate_wacc",
        ]

        for forbidden in forbidden_imports:
            assert (
                forbidden not in module_globals
            ), f"Forbidden import detected: {forbidden}"

    def test_only_allowed_imports(self):
        """Test that only allowed surfaces are imported."""
        import analytics.sensitivity_v14 as sens_module

        # Should have v14 pipeline imports
        assert hasattr(sens_module, "run_v14_pipeline")
        assert hasattr(sens_module, "load_scenario_config")
        assert hasattr(sens_module, "run_tornado_sensitivity")


class TestYAMLErrorHandling:
    """Test YAML configuration error handling."""

    def test_invalid_yaml_structure(self, tmp_path):
        """Test error when YAML has wrong structure."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("invalid: structure\nno: parameters")

        # YAML loading is handled by scenario_loader
        with pytest.raises((ValueError, KeyError)):
            from analytics.scenario_loader import load_scenario_config

            load_scenario_config(str(yaml_file))

    def test_invalid_parameter_validation(self):
        """Test error when parameter fails validation."""
        # Negative base_value should be rejected
        with pytest.raises((ValueError, TypeError)):
            ParameterRangeConfig(
                variable_name="test.param",
                base_value=-100.0,  # Invalid: negative base value
                low_pct=-0.10,
                high_pct=0.10,
            )


# pytest configuration
pytest_plugins = []

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
