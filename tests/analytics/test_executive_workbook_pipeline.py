"""Live-caller wiring for the single-scenario Executive Workbook (#656, slice 3).

``analytics.executive_workbook.build_executive_workbook`` shipped orphaned in
PR #179 — its only caller was a unit test. This module pins the wiring that gives
it a genuine live caller:

* ``frames_from_pipeline_result`` assembles the five finance sheets from a plain
  ``run_v14_pipeline`` result (shape pinned against a REAL pipeline run so it
  cannot silently drift);
* ``serialize_resource_trend`` / ``resource_trend_df_from_wind_export`` are exact
  inverses, so a long-term-trend block round-trips through a frozen wind export
  and reaches the "ResourceTrend" sheet unchanged — sourced from the REAL
  ``wind_resource.long_term_trend.analyze_long_term_resource`` output, never a
  fabricated table;
* ``emit_executive_workbook_from_pipeline`` writes all five sheets, adding
  "ResourceTrend" only when the export carries the trend;
* the opt-in ``run_full_pipeline_v14.py`` step writes the workbook when
  ``emit_executive_workbook=true`` and is a pure no-op (byte-identical result)
  when left off.

Framework: TEST-01 golden pin for the new opt-in surface; CESSPIT fail-loud;
CCCDIR one-source (no financial value derived here).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

import run_full_pipeline_v14 as rfp
from analytics.executive_workbook import (
    emit_executive_workbook_from_pipeline,
    frames_from_pipeline_result,
    resource_trend_df_from_wind_export,
    serialize_resource_trend,
)
from wind_resource.era5_retrieval import ERA5RequestConfig
from wind_resource.long_term_trend import analyze_long_term_resource

openpyxl = pytest.importorskip("openpyxl")

_EXPECTED_SHEETS = ["Summary", "Cashflow", "DebtService", "Ratios", "ScenarioSummary"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def pipeline_result() -> dict[str, Any]:
    """A synthetic result mirroring the real ``run_v14_pipeline`` surface keys."""
    return {
        "status": "success",
        "kpis": {
            "scenario_name": "unit",
            "project_irr": 0.0268,
            "equity_irr": -0.0486,
            "project_npv": -65_460_000.0,
            "equity_npv": -12_000_000.0,
            "min_dscr": 1.30,
            "avg_dscr": 1.90,
            "dscr_mean": 1.90,
            "dscr_median": 1.80,
            "dscr_min": 1.30,
            "dscr_max": 2.60,
            "dscr_p10": 1.40,
            "dscr_p90": 2.40,
            "dscr_std": 0.30,
            "llcr": 1.50,
            "plcr": 1.60,
            "max_debt_usd": 83_043_199.88,
            "total_idc_usd": 5_000_000.0,
            "balloon_pct": 0.413,
            "balloon_residual": 34_291_332.7,
            "balloon_covenant_breach": True,
            "wacc_label": "nominal",
            # A list-valued KPI must NOT leak into the Metric/Value Summary sheet.
            "dscr_series": [1.30, 2.60, 1.90],
        },
        "annual_rows": [
            {"year": 1, "revenue_usd": 100.0, "cfads_usd": 22_071_078.66},
            {"year": 2, "revenue_usd": 110.0, "cfads_usd": 20_576_252.02},
        ],
        "debt_result": {
            "timeline_periods": 3,
            "debt_outstanding": [83_043_199.88, 83_043_199.88, 40_000_000.0],
            "interest_total": [0.0, 0.0, 5_000_000.0],
            "debt_service_total": [0.0, 0.0, 12_000_000.0],
            "total_service": [0.0, 0.0, 12_000_000.0],
            "balloon_resolution": [0.0, 0.0, 0.0],
            "raw_dscr_series": [None, None, 1.30],
            # len==3 but NOT in the debt-period allow-list → excluded from the sheet.
            "dscr_series": [1.30, 2.60, 1.90],
        },
        "scenario_result": {
            "debt_covenants": {
                "dscr_threshold": 1.30,
                "years_below_threshold": 3,
                "first_breach_year": 5,
                "last_breach_year": 11,
                "balloon_flag": True,
                "audit_status": "FAIL",
                "notes": "Significant breach in 3 year(s)",
            },
        },
    }


def _real_trend_analysis() -> dict[str, Any]:
    """Run the REAL long-term trend analysis on a synthetic 20-yr hub series."""
    cfg = ERA5RequestConfig(
        project_name="UnitSite",
        latitude=8.27,
        longitude=79.75,
        start_year=2005,
        end_year=2024,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
    )
    idx = pd.date_range("2005-01-01", "2024-12-31 23:00", freq="h")
    rng = np.random.default_rng(7)
    series = pd.DataFrame({"ws_150m": rng.weibull(2.5, len(idx)) * 8.0}, index=idx)
    return analyze_long_term_resource(cfg, series=series)


# ---------------------------------------------------------------------------
# Frame assembly
# ---------------------------------------------------------------------------


class TestFramesFromPipelineResult:
    def test_five_frames_present(self, pipeline_result) -> None:
        frames = frames_from_pipeline_result(pipeline_result)
        assert set(frames) == {
            "summary",
            "cashflow",
            "debt",
            "ratios",
            "scenario_summary",
        }

    def test_summary_is_scalar_metric_value(self, pipeline_result) -> None:
        summary = frames_from_pipeline_result(pipeline_result)["summary"]
        assert list(summary.columns) == ["Metric", "Value"]
        metrics = set(summary["Metric"])
        assert "project_irr" in metrics
        # list-valued KPI excluded from the Metric/Value table
        assert "dscr_series" not in metrics

    def test_cashflow_year_first(self, pipeline_result) -> None:
        cashflow = frames_from_pipeline_result(pipeline_result)["cashflow"]
        assert cashflow.columns[0] == "year"
        assert len(cashflow) == 2

    def test_debt_schedule_period_indexed_allowlisted(self, pipeline_result) -> None:
        debt = frames_from_pipeline_result(pipeline_result)["debt"]
        assert list(debt["period"]) == [0, 1, 2]
        assert "debt_outstanding" in debt.columns
        assert "raw_dscr_series" in debt.columns
        # a non-allow-listed same-length series must not leak into the schedule
        assert "dscr_series" not in debt.columns

    def test_ratios_pull_kpis_and_covenants(self, pipeline_result) -> None:
        ratios = frames_from_pipeline_result(pipeline_result)["ratios"]
        assert list(ratios.columns) == ["Metric", "Value"]
        metrics = set(ratios["Metric"])
        assert {"min_dscr", "llcr", "plcr"} <= metrics  # from kpis
        assert {"dscr_threshold", "audit_status"} <= metrics  # from covenants

    def test_scenario_summary_single_row(self, pipeline_result) -> None:
        summary = frames_from_pipeline_result(pipeline_result)["scenario_summary"]
        assert len(summary) == 1
        assert summary.iloc[0]["scenario_name"] == "unit"
        assert "project_irr" in summary.columns

    def test_missing_blocks_degrade_to_empty(self) -> None:
        frames = frames_from_pipeline_result({})
        assert frames["cashflow"].empty
        assert frames["debt"].empty
        assert frames["summary"].empty


class TestFramesAgainstRealPipeline:
    """Shape-drift guard: the assembler must consume a genuine pipeline result."""

    def test_real_result_yields_non_empty_frames(self) -> None:
        from analytics.pipeline_v14_enhanced import run_v14_pipeline

        result = run_v14_pipeline(
            config="scenarios/dutchbay_lendercase_2025Q4.yaml",
            validation_mode="strict",
        )
        frames = frames_from_pipeline_result(result)
        assert not frames["summary"].empty
        assert not frames["cashflow"].empty
        assert not frames["debt"].empty
        assert "period" in frames["debt"].columns
        assert not frames["ratios"].empty
        assert len(frames["scenario_summary"]) == 1


# ---------------------------------------------------------------------------
# Resource-trend round-trip (producer encoder <-> consumer decoder)
# ---------------------------------------------------------------------------


class TestResourceTrendRoundTrip:
    def test_serialize_then_read_equals_live_summary_df(self) -> None:
        analysis = _real_trend_analysis()
        block = serialize_resource_trend(analysis)
        assert block["analyzed"] is True
        export = {"long_term_trend": block}
        got = resource_trend_df_from_wind_export(export)
        assert got is not None
        pd.testing.assert_frame_equal(
            got.reset_index(drop=True),
            analysis["summary_df"].reset_index(drop=True),
        )

    def test_read_from_nested_cashflow_export(self) -> None:
        block = serialize_resource_trend(_real_trend_analysis())
        export = {"cashflow_export": {"long_term_trend": block}}
        assert resource_trend_df_from_wind_export(export) is not None

    def test_serialize_passes_through_degraded_block(self) -> None:
        degraded = {"analyzed": False, "reason": "series too short"}
        assert serialize_resource_trend(degraded) == degraded

    def test_serialize_requires_summary_df(self) -> None:
        with pytest.raises(TypeError, match="summary_df"):
            serialize_resource_trend({"analyzed": True})

    @pytest.mark.parametrize(
        "export",
        [
            None,
            {},
            {"long_term_trend": {"analyzed": False, "reason": "short"}},
            {"long_term_trend": {"analyzed": True, "summary_records": []}},
            {"long_term_trend": "not-a-dict"},
        ],
    )
    def test_absent_or_degraded_returns_none(self, export) -> None:
        assert resource_trend_df_from_wind_export(export) is None


# ---------------------------------------------------------------------------
# End-to-end emission
# ---------------------------------------------------------------------------


class TestEmitFromPipeline:
    def test_writes_five_sheets_without_trend(self, tmp_path, pipeline_result) -> None:
        out = emit_executive_workbook_from_pipeline(
            pipeline_result, tmp_path / "wb.xlsx"
        )
        names = openpyxl.load_workbook(out).sheetnames
        assert names == _EXPECTED_SHEETS
        assert "ResourceTrend" not in names

    def test_adds_resource_trend_when_export_carries_it(
        self, tmp_path, pipeline_result
    ) -> None:
        export = {"long_term_trend": serialize_resource_trend(_real_trend_analysis())}
        out = emit_executive_workbook_from_pipeline(
            pipeline_result, tmp_path / "wb.xlsx", wind_export=export
        )
        wb = openpyxl.load_workbook(out)
        assert "ResourceTrend" in wb.sheetnames
        header = [c.value for c in wb["ResourceTrend"][1]]
        assert header == ["Metric", "Value"]


# ---------------------------------------------------------------------------
# CLI wiring (opt-in; default-off no-op)
# ---------------------------------------------------------------------------


def _run_cli(overrides: dict[str, Any]) -> None:
    """Drive the undecorated Hydra cli() with a plain OmegaConf config."""
    base = {
        "config": overrides.pop("config", ""),
        "validation_mode": "off",
        "validation_modules": None,
        "export_dir": overrides.pop("export_dir", "_out/test"),
        "write_artifacts": False,
        "wind_assessment_json": None,
        "wind_auto_orchestrate": False,
        "adapter_mode": "fill_if_absent",
        "wind_tolerance_pct": 0.5,
        "wind_export_scenario": "P75",
        "solar_assessment_json": None,
        "solar_adapter_mode": "fill_if_absent",
        "solar_tolerance_pct": 0.5,
        "solar_export_scenario": "P50",
        "solar_technology": "solar",
        "emit_executive_workbook": False,
        "executive_workbook_path": None,
    }
    base.update(overrides)
    rfp.cli.__wrapped__(OmegaConf.create(base))


class TestCliEmitWiring:
    def _fake_engine_returning(self, result):
        def _engine(*, config, validation_mode, validation_modules):
            return dict(result)

        return _engine

    def test_default_off_is_noop(
        self, tmp_path, pipeline_result, monkeypatch, capsys
    ) -> None:
        import json

        monkeypatch.setattr(
            rfp, "run_v14_pipeline", self._fake_engine_returning(pipeline_result)
        )
        _run_cli({"config": "scenarios/example_a.yaml"})
        out = json.loads(capsys.readouterr().out)
        assert "executive_workbook_path" not in out

    def test_emit_on_writes_workbook_and_echoes_path(
        self, tmp_path, pipeline_result, monkeypatch, capsys
    ) -> None:
        import json

        wb_path = tmp_path / "exec.xlsx"
        monkeypatch.setattr(
            rfp, "run_v14_pipeline", self._fake_engine_returning(pipeline_result)
        )
        _run_cli(
            {
                "config": "scenarios/example_a.yaml",
                "emit_executive_workbook": True,
                "executive_workbook_path": str(wb_path),
            }
        )
        out = json.loads(capsys.readouterr().out)
        assert out["executive_workbook_path"] == str(wb_path)
        assert wb_path.exists()
        assert openpyxl.load_workbook(wb_path).sheetnames == _EXPECTED_SHEETS

    def test_emit_on_defaults_path_under_export_dir(
        self, tmp_path, pipeline_result, monkeypatch, capsys
    ) -> None:
        monkeypatch.setattr(
            rfp, "run_v14_pipeline", self._fake_engine_returning(pipeline_result)
        )
        _run_cli(
            {
                "config": "scenarios/example_a.yaml",
                "export_dir": str(tmp_path / "run"),
                "emit_executive_workbook": True,
            }
        )
        assert (tmp_path / "run" / "executive_workbook.xlsx").exists()

    def test_emit_on_surfaces_wind_export_trend(
        self, tmp_path, pipeline_result, monkeypatch, capsys
    ) -> None:
        """A frozen wind export carrying a trend reaches the ResourceTrend sheet."""
        import json

        # Frozen wind export on disk carrying the JSON-safe trend block.
        export = {
            "cashflow_export": {"scenario": "P75"},
            "long_term_trend": serialize_resource_trend(_real_trend_analysis()),
        }
        wind_json = tmp_path / "wind_export_P75.json"
        wind_json.write_text(json.dumps(export), encoding="utf-8")

        # Isolate the workbook-trend glue from the wind ADAPTER contract: bypass
        # _apply_wind_to_scenario with a throwaway patched-file copy (the real
        # adapter is exercised in tests/api/test_run_full_pipeline_v14_lender_stack.py).
        patched = tmp_path / "patched.yaml"
        patched.write_text("project: {}\n", encoding="utf-8")
        monkeypatch.setattr(rfp, "_apply_wind_to_scenario", lambda **_kw: patched)
        monkeypatch.setattr(
            rfp, "run_v14_pipeline", self._fake_engine_returning(pipeline_result)
        )

        wb_path = tmp_path / "exec.xlsx"
        _run_cli(
            {
                "config": "scenarios/example_a.yaml",
                "wind_assessment_json": str(wind_json),
                "emit_executive_workbook": True,
                "executive_workbook_path": str(wb_path),
            }
        )
        assert "ResourceTrend" in openpyxl.load_workbook(wb_path).sheetnames
