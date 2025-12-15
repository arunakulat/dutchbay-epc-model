from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

import pytest

from analytics.evaluation_v14 import (
    evaluate_scenario,
    evaluate_scenario_from_dict,
    evaluate_with_overrides,
    normalize_kpi_dict,
)


class TestNormalizeKpiDict:
    def test_all_numeric_values_pass(self) -> None:
        raw: Mapping[str, Any] = {
            "project_irr": 0.12,
            "equity_irr": "0.15",
            "npv": 1_000_000,
        }

        kpis = normalize_kpi_dict(raw)

        assert kpis == {
            "project_irr": pytest.approx(0.12),
            "equity_irr": pytest.approx(0.15),
            "npv": pytest.approx(1_000_000.0),
        }

    def test_non_numeric_values_are_skipped(self) -> None:
        """
        Non‑numeric KPI values should be ignored rather than raising.

        This matches the relaxed v14 gateway semantics:
        - Keep any KPI that can be float(...)-ed.
        - Drop non‑numeric values (e.g. labels, scenario names).
        """
        raw: Mapping[str, Any] = {
            "project_irr": 0.12,
            "bad_metric": "not_a_number",
        }

        kpis = normalize_kpi_dict(raw)

        assert kpis["project_irr"] == pytest.approx(0.12)
        assert "bad_metric" not in kpis


class TestEvaluateScenarioFromDict:
    @patch("analytics.evaluation_v14.run_v14_pipeline")
    def test_happy_path_merges_and_runs_pipeline(
        self,
        mock_run_pipeline,
    ) -> None:
        base_config: Mapping[str, Any] = {
            "project": {"capex_usd_per_kw": 1000.0},
            "generation": {"capacity_factor_pct": 35.0},
        }

        overrides: Mapping[str, Any] = {
            "project": {"capex_usd_per_kw": 1200.0},
        }

        mock_run_pipeline.return_value = {
            "kpis": {
                "project_irr": 0.11,
                "equity_irr": 0.14,
            }
        }

        result = evaluate_scenario_from_dict(base_config, overrides=overrides)

        assert result["project_irr"] == pytest.approx(0.11)
        assert result["equity_irr"] == pytest.approx(0.14)

        # Check we merged overrides correctly
        args, kwargs = mock_run_pipeline.call_args
        cfg = kwargs["config"]

        assert cfg["project"]["capex_usd_per_kw"] == 1200.0
        assert cfg["generation"]["capacity_factor_pct"] == 35.0

    @patch("analytics.evaluation_v14.run_v14_pipeline")
    def test_missing_kpis_key_raises_key_error(
        self,
        mock_run_pipeline,
    ) -> None:
        base_config: Mapping[str, Any] = {"project": {"capex_usd_per_kw": 1000.0}}
        mock_run_pipeline.return_value = {"not_kpis": {}}

        with pytest.raises(KeyError, match="does not contain 'kpis'"):
            evaluate_scenario_from_dict(base_config)


class TestEvaluateWithOverrides:
    @patch("analytics.evaluation_v14.load_scenario_config")
    @patch("analytics.evaluation_v14.run_v14_pipeline")
    def test_happy_path(
        self,
        mock_run_pipeline,
        mock_load_config,
        tmp_path: Path,
    ) -> None:
        cfg_path = tmp_path / "scenario.yaml"
        cfg_path.write_text("dummy: true", encoding="utf-8")

        mock_load_config.return_value = {"project": {"capex_usd_per_kw": 1000.0}}
        mock_run_pipeline.return_value = {"kpis": {"project_irr": 0.13}}

        result = evaluate_with_overrides(
            config_path=cfg_path,
            overrides={"project": {"capex_usd_per_kw": 900.0}},
        )

        assert result["project_irr"] == pytest.approx(0.13)
        mock_load_config.assert_called_once_with(cfg_path)

        args, kwargs = mock_run_pipeline.call_args
        cfg = kwargs["config"]

        assert cfg["project"]["capex_usd_per_kw"] == 900.0

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "missing.yaml"
        with pytest.raises(FileNotFoundError):
            evaluate_with_overrides(cfg_path)

    @patch("analytics.evaluation_v14.load_scenario_config")
    def test_non_mapping_config_raises_type_error(
        self,
        mock_load_config,
        tmp_path: Path,
    ) -> None:
        cfg_path = tmp_path / "dummy.yaml"
        cfg_path.write_text("dummy: true", encoding="utf-8")

        mock_load_config.return_value = ["not", "a", "mapping"]

        with pytest.raises(
            TypeError, match="Expected load_scenario_config to return Mapping"
        ):
            evaluate_with_overrides(cfg_path)

    def test_alias_evaluate_scenario_points_to_main(self) -> None:
        # Backward compatibility alias
        assert evaluate_scenario is evaluate_with_overrides
