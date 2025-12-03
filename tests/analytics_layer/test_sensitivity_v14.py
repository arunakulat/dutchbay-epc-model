from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, TornadoResult
from analytics.sensitivity_v14 import (
    SensitivityRequest,
    _analyze_single_parameter,
    _build_nested_override,
    _load_parameters_from_yaml,
    run_tornado_sensitivity,
)

"""
Unit tests for analytics.sensitivity_v14 module (v14 coordinator layer).

Scope
-----
These tests focus on the *analytics* sensitivity coordinator, not the
finance engine itself. The finance engine is exercised by dedicated
integration tests in test_sensitivity_v14_all.py.

Design principles validated here:

1. Sensitivity layer acts as a coordinator only:
   - No direct access to cashflow/debt engines.
   - Talks only to run_v14_pipeline + scenario loader.

2. All base / shocked evaluations go through run_v14_pipeline.

3. Helper utilities behave predictably and fail fast:
   - _build_nested_override
   - _load_parameters_from_yaml
   - _analyze_single_parameter

4. Backwards-compatible calling styles:
   - New: SensitivityRequest
   - Legacy: string config path + parameters + metric
"""
# ═══════════════════════════════════════════════════════════════════════
# Helpers / fixtures
# ═══════════════════════════════════════════════════════════════════════


def _make_param(
    name: str = "project.capex",
    base: float = 850.0,
    low_pct: float = -0.2,
    high_pct: float = 0.2,
) -> ParameterRangeConfig:
    """Convenience factory for ParameterRangeConfig."""
    return ParameterRangeConfig(
        variable_name=name,
        base_value=base,
        low_pct=low_pct,
        high_pct=high_pct,
    )


# ═══════════════════════════════════════════════════════════════════════
# _build_nested_override
# ═══════════════════════════════════════════════════════════════════════


class TestBuildNestedOverride:
    """Unit tests for _build_nested_override helper."""

    def test_single_level(self):
        result = _build_nested_override("param", 100.0)
        assert result == {"param": 100.0}

    def test_two_levels(self):
        result = _build_nested_override("project.capex", 850.0)
        assert result == {"project": {"capex": 850.0}}

    def test_three_levels(self):
        result = _build_nested_override("a.b.c", 42.0)
        assert result == {"a": {"b": {"c": 42.0}}}

    def test_list_path(self):
        result = _build_nested_override(["project", "capex"], 850.0)
        assert result == {"project": {"capex": 850.0}}

    def test_empty_string_path(self):
        result = _build_nested_override("", 30.0)
        assert result == {}

    def test_empty_list_path(self):
        result = _build_nested_override([], 30.0)
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════
# _load_parameters_from_yaml
# ═══════════════════════════════════════════════════════════════════════


class TestYAMLErrorHandling:
    """YAML structure and error-handling tests for _load_parameters_from_yaml."""

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        yaml_file = tmp_path / "does_not_exist.yaml"
        with pytest.raises(FileNotFoundError):
            _load_parameters_from_yaml(yaml_file)

    def test_empty_yaml_raises_value_error(self, tmp_path: Path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        with pytest.raises(ValueError):
            _load_parameters_from_yaml(yaml_file)

    def test_invalid_yaml_structure(self, tmp_path: Path):
        """Top-level dict instead of list should raise ValueError."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("invalid: structure\nno: parameters")

        with pytest.raises(ValueError):
            _load_parameters_from_yaml(yaml_file)

    def test_valid_parameter_list(self, tmp_path: Path):
        yaml_file = tmp_path / "good.yaml"
        yaml_file.write_text(
            """
            - variable_name: project.capex
              base_value: 850.0
              low_pct: -0.1
              high_pct: 0.1
            """
        )

        params = _load_parameters_from_yaml(yaml_file)
        assert isinstance(params, list)
        assert len(params) == 1
        p = params[0]
        assert isinstance(p, ParameterRangeConfig)
        assert p.variable_name == "project.capex"
        assert p.base_value == 850.0
        assert p.low_pct == pytest.approx(-0.1)
        assert p.high_pct == pytest.approx(0.1)


# ═══════════════════════════════════════════════════════════════════════
# _analyze_single_parameter
# ═══════════════════════════════════════════════════════════════════════


class TestAnalyzeSingleParameter:
    """Unit tests for single-parameter analysis helper."""

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_basic_analysis(self, mock_load, mock_pipeline):
        """Low/high calls should produce consistent TornadoResult."""
        mock_load.return_value = {"project": {"capex": 850.0}}

        call_count = [0]

        def mock_pipeline_eval(*_, **__):
            call_count[0] += 1
            if call_count[0] == 1:
                # Low case
                return {"kpis": {"project_irr": 0.10}}
            else:
                # High case
                return {"kpis": {"project_irr": 0.14}}

        mock_pipeline.side_effect = mock_pipeline_eval

        param = _make_param("project.capex", 850.0, -0.20, 0.20)

        result = _analyze_single_parameter(
            base_config_path="test.yaml",
            base_metric_value=0.12,
            metric_name="project_irr",
            param=param,
        )

        assert isinstance(result, TornadoResult)
        assert result.variable == "project.capex"
        assert result.base_irr == pytest.approx(0.12)
        assert result.low_irr == pytest.approx(0.10)
        assert result.high_irr == pytest.approx(0.14)
        assert result.impact_abs == pytest.approx(0.04, abs=1e-8)

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_missing_metric_raises_key_error(self, mock_load, mock_pipeline):
        """If KPI dict does not contain the requested metric, KeyError is raised."""
        mock_load.return_value = {"project": {"capex": 850.0}}
        mock_pipeline.return_value = {"kpis": {"other_metric": 123.0}}

        param = _make_param()

        with pytest.raises(KeyError):
            _analyze_single_parameter(
                base_config_path="test.yaml",
                base_metric_value=0.0,
                metric_name="project_irr",
                param=param,
            )


# ═══════════════════════════════════════════════════════════════════════
# run_tornado_sensitivity – new and legacy APIs
# ═══════════════════════════════════════════════════════════════════════


class TestRunTornadoSensitivity:
    """Tests for main coordinator function run_tornado_sensitivity."""

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_happy_path_with_request(self, mock_load, mock_pipeline):
        """New API: SensitivityRequest with explicit parameters and metric."""
        mock_load.return_value = {
            "finance": {"capex": 850.0, "tariff": 65.0},
        }

        def mock_pipeline_eval(*_, **kwargs):
            cfg = kwargs.get("config", {})
            capex = cfg.get("finance", {}).get("capex", 850.0)
            # Base case 0.12; perturb capex slightly for clarity
            if capex != 850.0:
                return {"kpis": {"project_irr": 0.11}}
            return {"kpis": {"project_irr": 0.12}}

        mock_pipeline.side_effect = mock_pipeline_eval

        params = [
            ParameterRangeConfig(
                variable_name="finance.capex",
                base_value=850.0,
                low_pct=-0.20,
                high_pct=0.20,
            )
        ]

        request = SensitivityRequest(
            base_config_path="test_config.yaml",
            parameters=params,
            metric="project_irr",
        )

        suite = run_tornado_sensitivity(request)

        assert suite.base_config_path == "test_config.yaml"
        assert suite.metric == "project_irr"
        assert suite.base_metric == pytest.approx(0.12)
        assert len(suite.tornado_results) == 1
        assert all(isinstance(r, TornadoResult) for r in suite.tornado_results)

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_legacy_api_with_string_config_path(self, mock_load, mock_pipeline):
        """Legacy API: config path string + parameters + metric."""
        mock_load.return_value = {"test": {"param": 100.0}}
        mock_pipeline.return_value = {"kpis": {"project_irr": 0.12}}

        params = [
            ParameterRangeConfig(
                variable_name="test.param",
                base_value=100.0,
                low_pct=-0.10,
                high_pct=0.10,
            )
        ]

        suite = run_tornado_sensitivity(
            "test.yaml",
            parameters=params,
            metric="project_irr",
        )

        assert suite.base_config_path == "test.yaml"
        assert suite.metric == "project_irr"
        assert len(suite.tornado_results) == 1
        assert suite.tornado_results[0].variable == "test.param"

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_legacy_api_metric_default(self, mock_load, mock_pipeline):
        """Legacy API should default metric to project_irr when not provided."""
        mock_load.return_value = {"test": {"param": 100.0}}
        mock_pipeline.return_value = {"kpis": {"project_irr": 0.12}}

        params = [_make_param("test.param", 100.0)]

        suite = run_tornado_sensitivity("test.yaml", parameters=params)

        assert suite.metric == "project_irr"

    @patch("analytics.sensitivity_v14.run_v14_pipeline")
    @patch("analytics.sensitivity_v14.load_scenario_config")
    def test_metric_missing_in_base_kpis_raises_key_error(
        self, mock_load, mock_pipeline
    ):
        mock_load.return_value = {"test": {"param": 100.0}}
        mock_pipeline.return_value = {"kpis": {"other": 1.23}}

        params = [_make_param("test.param", 100.0)]

        with pytest.raises(KeyError):
            run_tornado_sensitivity(
                "test.yaml",
                parameters=params,
                metric="project_irr",
            )


# Note: Multi-metric tornado and breakeven parameter flows are covered in
# the integration suite (test_sensitivity_v14_all.py) against the real
# run_v14_pipeline implementation and scenario configs. This file keeps
# their pure-unit coverage limited to helpers and the single-metric
# coordinator path.
