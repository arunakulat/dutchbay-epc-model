from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, TornadoResult
from analytics.sensitivity_v14 import (
    SensitivityRequest,
    analyze_single_parameter,
    build_nested_override,
    load_parameters_from_yaml,
    run_tornado_sensitivity,
)


def make_param(
    name: str = "project.capex_usd_per_kw",
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


class TestBuildNestedOverride:
    """Unit tests for build_nested_override helper."""

    def test_single_level(self) -> None:
        result = build_nested_override("param", 100.0)
        assert result == {"param": 100.0}

    def test_two_levels(self) -> None:
        result = build_nested_override("project.capex", 850.0)
        assert result == {"project": {"capex": 850.0}}

    def test_three_levels(self) -> None:
        result = build_nested_override("a.b.c", 42.0)
        assert result == {"a": {"b": {"c": 42.0}}}

    def test_list_path(self) -> None:
        result = build_nested_override(["project", "capex"], 850.0)
        assert result == {"project": {"capex": 850.0}}

    def test_empty_string_path(self) -> None:
        result = build_nested_override("", 30.0)
        assert result == {}

    def test_empty_list_path(self) -> None:
        result = build_nested_override([], 30.0)
        assert result == {}


class TestYamlErrorHandling:
    """YAML structure and error-handling tests for load_parameters_from_yaml."""

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "does_not_exist.yaml"
        with pytest.raises(FileNotFoundError):
            load_parameters_from_yaml(yaml_file)

    def test_empty_yaml_raises_value_error(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty or null"):
            load_parameters_from_yaml(yaml_file)

    def test_invalid_yaml_structure_raises_value_error(self, tmp_path: Path) -> None:
        """Syntactically valid but structurally wrong: top-level dict."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("invalid: structure", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a list"):
            load_parameters_from_yaml(yaml_file)

    def test_valid_parameter_list(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "good.yaml"
        yaml_file.write_text(
            """
            - variable_name: project.capex
              base_value: 850.0
              low_pct: -0.1
              high_pct: 0.1
            """,
            encoding="utf-8",
        )

        params = load_parameters_from_yaml(yaml_file)
        assert isinstance(params, list)
        assert len(params) == 1

        p = params[0]
        assert isinstance(p, ParameterRangeConfig)
        assert p.variable_name == "project.capex"
        assert p.base_value == pytest.approx(850.0)
        assert p.low_pct == pytest.approx(-0.1)
        assert p.high_pct == pytest.approx(0.1)


class TestAnalyzeSingleParameter:
    """Unit tests for single-parameter analysis helper."""

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_basic_analysis(
        self,
        mock_eval,
        tmp_path: Path,
    ) -> None:
        """Low/high calls should produce consistent TornadoResult."""

        # Two calls: low then high
        def _side_effect(*args: Any, **kwargs: Any) -> Mapping[str, Any]:
            # analyze_single_parameter calls evaluate_with_overrides(base_config_path, overrides)
            overrides = args[1] if len(args) > 1 else kwargs.get("overrides", {})
            capex = overrides["project"]["capex_usd_per_kw"]
            if capex < 850.0:
                return {"project_irr": 0.10}
            return {"project_irr": 0.14}

        mock_eval.side_effect = _side_effect

        config_path = tmp_path / "test.yaml"
        config_path.write_text("dummy: true", encoding="utf-8")

        param = make_param("project.capex_usd_per_kw", 850.0, -0.20, 0.20)

        result = analyze_single_parameter(
            base_config_path=config_path,
            base_metric_value=0.12,
            metric_name="project_irr",
            param=param,
            override_labels=None,
        )

        assert isinstance(result, TornadoResult)
        assert result.variable == "project.capex_usd_per_kw"
        assert result.base_irr == pytest.approx(0.12)
        assert result.low_irr == pytest.approx(0.10)
        assert result.high_irr == pytest.approx(0.14)
        assert result.impact_abs == pytest.approx(0.04, abs=1e-8)

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_missing_metric_raises_key_error(
        self,
        mock_eval,
        tmp_path: Path,
    ) -> None:
        config_path = tmp_path / "test.yaml"
        config_path.write_text("dummy: true", encoding="utf-8")

        mock_eval.return_value = {"other_metric": 123.0}
        param = make_param()

        with pytest.raises(KeyError, match="Metric 'project_irr'"):
            analyze_single_parameter(
                base_config_path=config_path,
                base_metric_value=0.0,
                metric_name="project_irr",
                param=param,
                override_labels=None,
            )


class TestRunTornadoSensitivity:
    """Tests for main coordinator function run_tornado_sensitivity."""

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_happy_path_with_request(
        self,
        mock_eval,
        tmp_path: Path,
    ) -> None:
        """New API: SensitivityRequest with explicit parameters and metric."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("dummy: true", encoding="utf-8")

        # First call: base KPIs; subsequent calls: shocks
        def _side_effect(*args: Any, **kwargs: Any) -> Mapping[str, Any]:
            overrides = args[1] if len(args) > 1 else kwargs.get("overrides")
            if overrides is None:
                return {"project_irr": 0.12}
            capex = overrides["finance"]["capex_usd"]
            if capex < 850.0:
                return {"project_irr": 0.11}
            return {"project_irr": 0.13}

        mock_eval.side_effect = _side_effect

        params = [
            ParameterRangeConfig(
                variable_name="finance.capex_usd",
                base_value=850.0,
                low_pct=-0.20,
                high_pct=0.20,
            )
        ]

        request = SensitivityRequest(
            base_config_path=str(cfg_path),
            parameters=params,
            metric="project_irr",
        )

        suite = run_tornado_sensitivity(request)

        assert suite.base_config_path == str(cfg_path)
        assert suite.metric == "project_irr"
        assert suite.base_metric == pytest.approx(0.12)
        assert len(suite.tornado_results) == 1
        assert all(isinstance(r, TornadoResult) for r in suite.tornado_results)

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_legacy_api_with_string_config_path(
        self,
        mock_eval,
        tmp_path: Path,
    ) -> None:
        """Legacy API: config path string, parameters, metric."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("dummy: true", encoding="utf-8")

        # Base + two shock evaluations
        def _side_effect(*args: Any, **kwargs: Any) -> Mapping[str, Any]:
            overrides = args[1] if len(args) > 1 else kwargs.get("overrides")
            if overrides is None:
                return {"project_irr": 0.12}
            return {"project_irr": 0.13}

        mock_eval.side_effect = _side_effect

        params = [
            ParameterRangeConfig(
                variable_name="test.param",
                base_value=100.0,
                low_pct=-0.10,
                high_pct=0.10,
            )
        ]

        suite = run_tornado_sensitivity(
            str(cfg_path),
            parameters=params,
            metric="project_irr",
        )

        assert suite.base_config_path == str(cfg_path)
        assert suite.metric == "project_irr"
        assert len(suite.tornado_results) == 1
        assert suite.tornado_results[0].variable == "test.param"

    @patch("analytics.sensitivity_v14.evaluate_with_overrides")
    def test_metric_missing_in_base_kpis_raises_key_error(
        self,
        mock_eval,
        tmp_path: Path,
    ) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("dummy: true", encoding="utf-8")

        mock_eval.return_value = {"other": 1.23}
        params = [make_param("test.param", 100.0)]

        with pytest.raises(KeyError, match="Metric 'project_irr' not found"):
            run_tornado_sensitivity(
                str(cfg_path),
                parameters=params,
                metric="project_irr",
            )
