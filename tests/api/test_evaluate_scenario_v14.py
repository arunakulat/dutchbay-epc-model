"""
Unit tests for analytics.evaluate_scenario module.

This module provides evaluate_with_overrides(), a facade over run_v14_pipeline
that flattens KPIs and adds analytics-friendly aliases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from analytics.evaluate_scenario import (
    _deep_merge_dicts,
    _merge_engine_kpis,
    evaluate_with_overrides,
)


def test_merge_engine_kpis_falls_back_to_top_level_when_kpi_missing() -> None:
    """
    _merge_engine_kpis should:
      - prefer KPI block scenario_name when present
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

    # Scenario name should prefer KPI block if present
    assert merged["scenario_name"] == "kpi_name"  # ✅ FIXED

    # Should fall back to top-level for missing metrics
    assert merged["project_npv"] == pytest.approx(99_000_000.0)
    assert merged["min_dscr"] == pytest.approx(1.4)
    assert merged["max_debt_usd"] == pytest.approx(12_000_000.0)


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
        *,
        config: str | dict[str, Any],  # ✅ Can accept dict
        overrides: dict[str, Any] | None = None,
        validation_mode: str = "strict",  # ✅ FIXED - added parameter
        validation_modules: list[str] | None = None,  # ✅ FIXED - added parameter
    ) -> Mapping[str, Any]:
        captured["config"] = config
        captured["overrides"] = overrides
        captured["validation_mode"] = validation_mode
        captured["validation_modules"] = validation_modules
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

    # Should have called the pipeline with merged config
    assert captured["config"] is not None
    assert captured["validation_mode"] == "strict"
    assert captured["validation_modules"] == ["cashflow", "debt"]

    # Result should be flattened KPI dict
    assert result["scenario_name"] == "from_pipeline"
    assert result["project_irr"] == pytest.approx(0.17)
    assert result["project_npv"] == pytest.approx(123.0)
    assert result["min_dscr"] == pytest.approx(1.23)

    # Should have dscr_min alias
    assert result["dscr_min"] == pytest.approx(1.23)
    assert result["max_debt_usd"] == pytest.approx(456.0)


def test_deep_merge_dicts_simple() -> None:
    """Test _deep_merge_dicts with simple dicts."""
    base = {"a": 1, "b": 2}
    overrides = {"b": 3, "c": 4}

    merged = _deep_merge_dicts(base, overrides)

    assert merged == {"a": 1, "b": 3, "c": 4}
    # Should not mutate originals
    assert base == {"a": 1, "b": 2}
    assert overrides == {"b": 3, "c": 4}


def test_deep_merge_dicts_nested() -> None:
    """Test _deep_merge_dicts with nested structures."""
    base = {
        "project": {"capex_usd_per_kw": 1000.0, "capacity_mw": 50.0},
        "financial": {"equity_fraction": 0.3},
    }
    overrides = {
        "project": {"capex_usd_per_kw": 1200.0},  # Override one field
        "financial": {"tariff_lkr_per_kwh": 70.0},  # Add new field
    }

    merged = _deep_merge_dicts(base, overrides)

    assert merged["project"]["capex_usd_per_kw"] == 1200.0  # Overridden
    assert merged["project"]["capacity_mw"] == 50.0  # Preserved
    assert merged["financial"]["equity_fraction"] == 0.3  # Preserved
    assert merged["financial"]["tariff_lkr_per_kwh"] == 70.0  # Added


# ══════════════════════════════════════════════════════════════════════════
# EOF - tests/api/test_evaluate_scenario_v14.py
# ══════════════════════════════════════════════════════════════════════════
