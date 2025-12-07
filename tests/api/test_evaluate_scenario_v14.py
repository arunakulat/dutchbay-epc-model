from __future__ import annotations

from typing import Any, Mapping

import pytest

from analytics.evaluate_scenario import _merge_engine_kpis, evaluate_with_overrides


def test_merge_engine_kpis_falls_back_to_top_level_when_kpi_missing() -> None:
    """
    _merge_engine_kpis should:
      - prefer top-level scenario_name when present
      - fall back to top-level metrics when KPI block omits them

    It does NOT add the dscr_min alias; that is handled by
    evaluate_with_overrides.
    """
    pipeline_result = {
        "scenario_name": "top_level_name",
        "project_irr": 0.2,
        "project_npv": 99_000_000.0,
        "min_dscr": 1.4,
        "max_debt_usd": 12_000_000.0,
        # kpis is deliberately incomplete to exercise the fallback.
        "kpis": {
            "scenario_name": "kpi_name",
            "project_irr": 0.2,
            # project_npv and min_dscr intentionally omitted
        },
    }

    merged = _merge_engine_kpis(pipeline_result)

    # Should preserve KPI block values where present for metrics
    assert merged["project_irr"] == pytest.approx(0.2)

    # Scenario name should prefer the top-level label if present
    assert merged["scenario_name"] == "top_level_name"

    # Should fall back to top-level when KPI block lacks the field
    assert merged["project_npv"] == 99_000_000.0
    assert merged["min_dscr"] == pytest.approx(1.4)

    # And _merge_engine_kpis itself does NOT add dscr_min; that's the job of
    # evaluate_with_overrides so concerns stay nicely separated.
    assert "dscr_min" not in merged


def test_evaluate_with_overrides_attaches_dscr_min_alias(monkeypatch, tmp_path) -> None:
    """
    evaluate_with_overrides should:
      - delegate to run_v14_pipeline
      - flatten the pipeline result via _merge_engine_kpis
      - add a dscr_min alias when min_dscr is present
    """
    # Fake config file so Path(str) and logging make sense.
    config_path = tmp_path / "dummy_scenario.yaml"
    config_path.write_text("project: {}\n")

    captured: dict[str, Any] = {}

    def fake_run_v14_pipeline(
        *, config: str, overrides: dict[str, Any] | None = None
    ) -> Mapping[str, Any]:
        captured["config"] = config
        captured["overrides"] = overrides
        return {
            "scenario_name": "from_pipeline",
            "project_irr": 0.17,
            "project_npv": 123.0,
            "min_dscr": 1.23,
            "max_debt_usd": 456.0,
            "kpis": {
                # Suppose the KPI block omits these so fallback logic is exercised
                "project_irr": 0.17,
            },
        }

    # Patch the symbol used inside analytics.evaluate_scenario
    monkeypatch.setattr(
        "analytics.evaluate_scenario.run_v14_pipeline",
        fake_run_v14_pipeline,
    )

    result = evaluate_with_overrides(
        base_config_path=str(config_path),
        overrides={"foo": {"bar": 1}},
    )

    # 1) Pipeline should be called with the resolved config path + overrides
    assert captured["config"] == str(config_path)
    assert captured["overrides"] == {"foo": {"bar": 1}}

    # 2) Core metrics should be present
    assert result["project_irr"] == pytest.approx(0.17)
    assert result["project_npv"] == pytest.approx(123.0)
    assert result["min_dscr"] == pytest.approx(1.23)
    assert result["max_debt_usd"] == pytest.approx(456.0)

    # 3) Alias must be wired and consistent
    assert "dscr_min" in result
    assert result["dscr_min"] == pytest.approx(result["min_dscr"])

    # 4) Scenario label should come from the top-level pipeline block
    assert result["scenario_name"] == "from_pipeline"
