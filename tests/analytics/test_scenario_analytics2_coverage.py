#!/usr/bin/env python3
"""Supplemental coverage for analytics.scenario_analytics.

test_scenario_analytics.py covers the main surface (discovery, discount-rate
precedence, _run_single, run() shape, JSON/Excel happy paths). This file
targets the remaining branches that file does not exercise:

- _effective_discount_rate: unparseable wacc.project_discount_rate fall-through
- run(): the parallel ThreadPoolExecutor path (parallel + >4 scenarios)
- run(): export_charts=True dispatch
- _build_dataframes: DSCR derivation from cfads/debt columns, plus the
  "cannot derive" warning branch (driven via synthetic BatchScenarioResults so the
  exact column shapes are deterministic and independent of the live engine)
- _export_to_excel: the no-output-path no-op and the ExcelExporter-failure
  fallback to a basic pandas workbook
- _export_charts: the no-output-path no-op, the export_charts dispatch, the
  per-method (export_dscr_chart/export_irr_histogram) dispatch, and the
  ChartExporter-unavailable warning branch

All exporter / chart machinery is monkeypatched so nothing touches matplotlib
display or a real Excel engine beyond pandas' own writer. Repo paths are
resolved relative to this file for CI portability; outputs go under tmp_path.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

import analytics.scenario_analytics as sa_mod
from analytics.scenario_analytics import BatchScenarioResult, ScenarioAnalytics

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "scenarios"
LENDER_YAML = SCENARIOS_DIR / "dutchbay_lendercase_2025Q4.yaml"
LENDER_STEM = "dutchbay_lendercase_2025Q4"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def lender_dir(tmp_path: Path) -> Path:
    """A directory containing only the canonical lender scenario."""
    shutil.copy(LENDER_YAML, tmp_path / LENDER_YAML.name)
    return tmp_path


def _synthetic_result(
    name: str,
    kpis: Dict[str, Any],
    annual_rows: List[Dict[str, Any]],
) -> BatchScenarioResult:
    """A BatchScenarioResult populated enough to drive _build_dataframes."""
    return BatchScenarioResult(
        name=name,
        config_path=Path(f"{name}.yaml"),
        kpis=kpis,
        annual_rows=annual_rows,
        debt_result={},
        discount_rate=0.10,
    )


# ---------------------------------------------------------------------------
# _effective_discount_rate: unparseable wacc value (lines 188-189)
# ---------------------------------------------------------------------------
def test_discount_rate_invalid_wacc_falls_to_default(tmp_path: Path) -> None:
    """An unparseable wacc.project_discount_rate falls through to the default.

    No top-level discount_rate is present, so after the wacc block raises and
    logs, precedence drops straight to global_default_discount_rate.
    """
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, global_default_discount_rate=0.123)
    cfg = {"wacc": {"project_discount_rate": "not-a-number"}}
    assert sa._effective_discount_rate(cfg) == pytest.approx(0.123)


def test_discount_rate_invalid_wacc_falls_to_top_level(tmp_path: Path) -> None:
    """An unparseable wacc value still yields to a valid top-level discount_rate."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, global_default_discount_rate=0.123)
    cfg = {"wacc": {"project_discount_rate": None}, "discount_rate": 0.066}
    assert sa._effective_discount_rate(cfg) == pytest.approx(0.066)


# ---------------------------------------------------------------------------
# run(): parallel ThreadPoolExecutor path (lines 320-330)
# ---------------------------------------------------------------------------
def test_run_parallel_batch_dispatches_threadpool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """parallel=True with >4 scenarios runs via the ThreadPoolExecutor branch.

    _run_single is stubbed to return deterministic results (5 succeed, 1 fails)
    so the parallel collection of results/failures is exercised without paying
    the full engine cost six times.
    """
    # Need strictly more than 4 discovered scenario paths to flip batch_run on.
    for i in range(6):
        shutil.copy(LENDER_YAML, tmp_path / f"scenario_{i}.yaml")

    sa = ScenarioAnalytics(scenarios_dir=tmp_path, parallel=True)

    def fake_run_single(config_path: Path) -> BatchScenarioResult:
        stem = config_path.stem
        if stem == "scenario_5":
            # Empty kpis -> classified as a failure by run().
            return _synthetic_result(stem, {}, [])
        return _synthetic_result(
            stem,
            {"dscr_min": 1.5, "equity_irr": 0.08},
            [{"year": 1, "dscr": 1.5}],
        )

    monkeypatch.setattr(sa, "_run_single", fake_run_single)

    summary_df, timeseries_df, meta = sa.run()

    assert meta.n_success == 5
    assert meta.n_failed == 1
    assert "scenario_5" in meta.failed
    assert set(summary_df.index) == {f"scenario_{i}" for i in range(5)}
    assert len(timeseries_df) == 5


# ---------------------------------------------------------------------------
# run(): export_charts dispatch (line 377)
# ---------------------------------------------------------------------------
def test_run_export_charts_invokes_chart_export(
    lender_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """export_charts=True with an output_path routes through _export_charts."""
    calls: List[str] = []

    def fake_export_charts(
        self: ScenarioAnalytics, summary_df: Any, ts_df: Any
    ) -> None:
        calls.append("charts")

    monkeypatch.setattr(ScenarioAnalytics, "_export_charts", fake_export_charts)

    out = lender_dir / "report.xlsx"
    sa = ScenarioAnalytics(scenarios_dir=lender_dir, output_path=out)
    sa.run(export_charts=True)

    assert calls == ["charts"]


def test_run_export_charts_noop_without_output_path(lender_dir: Path) -> None:
    """export_charts=True with no output_path is a safe no-op (branch skipped)."""
    sa = ScenarioAnalytics(scenarios_dir=lender_dir, output_path=None)
    summary_df, _ts_df, _meta = sa.run(export_charts=True)
    assert list(summary_df.index) == [LENDER_STEM]


# ---------------------------------------------------------------------------
# _build_dataframes: DSCR derivation (lines 430-459)
# ---------------------------------------------------------------------------
def test_build_dataframes_derives_dscr_from_cfads_and_debt(tmp_path: Path) -> None:
    """When no native dscr exists, dscr = cfads / debt_service is back-filled.

    KPIs carry no dscr scalar and annual rows carry no 'dscr' column, so the
    derivation branch must locate the cfads + single debt-service columns and
    compute the ratio. A zero debt-service row becomes NA (no div-by-zero).
    """
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    rows = [
        {"year": 1, "cfads_final_lkr": 200.0, "debt_service_lkr": 100.0},
        {"year": 2, "cfads_final_lkr": 300.0, "debt_service_lkr": 150.0},
        {"year": 3, "cfads_final_lkr": 90.0, "debt_service_lkr": 0.0},
    ]
    result = _synthetic_result("synthetic", {"equity_irr": 0.08}, rows)

    _summary_df, timeseries_df = sa._build_dataframes([result])

    assert "dscr" in timeseries_df.columns
    derived = timeseries_df.set_index("year")["dscr"]
    assert derived.loc[1] == pytest.approx(2.0)
    assert derived.loc[2] == pytest.approx(2.0)
    # Zero debt-service denominator -> NA, not an exception or infinity.
    assert pd.isna(derived.loc[3])


def test_build_dataframes_derives_dscr_from_unpreferred_cfads(tmp_path: Path) -> None:
    """A cfads column matching no preferred name still drives derivation.

    'cfads_total_lkr' contains 'cfads' but none of the preferred substrings
    (cfads_final_lkr / cfads_final / posttax_cfads), so it is picked up by the
    'first candidate' fallback before the ratio is computed.
    """
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    rows = [{"year": 1, "cfads_total_lkr": 240.0, "debt_service_lkr": 120.0}]
    result = _synthetic_result("unpreferred", {"equity_irr": 0.08}, rows)

    _summary_df, timeseries_df = sa._build_dataframes([result])

    assert "dscr" in timeseries_df.columns
    assert timeseries_df["dscr"].tolist() == pytest.approx([2.0])


def test_build_dataframes_derives_dscr_from_plain_debt_column(tmp_path: Path) -> None:
    """A 'debt' column without serv/pay/repay falls back to the plain-debt set.

    'debt_outstanding_lkr' does not match the serv/pay/repay pattern, so the
    first debt-candidate list is empty and the broader 'any debt column'
    fallback supplies the single denominator column.
    """
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    rows = [{"year": 1, "cfads_final_lkr": 300.0, "debt_outstanding_lkr": 150.0}]
    result = _synthetic_result("plaindebt", {"equity_irr": 0.08}, rows)

    _summary_df, timeseries_df = sa._build_dataframes([result])

    assert "dscr" in timeseries_df.columns
    assert timeseries_df["dscr"].tolist() == pytest.approx([2.0])


def test_build_dataframes_prefers_scalar_dscr_from_kpis(tmp_path: Path) -> None:
    """A dscr_min scalar in KPIs is broadcast to every timeseries row.

    This takes the 'dscr_scalar is not None' back-fill path in the row loop
    rather than the cfads/debt derivation.
    """
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    rows = [{"year": 1, "cfads": 200.0}, {"year": 2, "cfads": 300.0}]
    result = _synthetic_result("scalar", {"dscr_min": 1.31}, rows)

    _summary_df, timeseries_df = sa._build_dataframes([result])

    assert timeseries_df["dscr"].tolist() == pytest.approx([1.31, 1.31])


def test_build_dataframes_cannot_derive_dscr_warns(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ambiguous columns (two debt-service cols) leave dscr underivable + warn.

    No dscr scalar, no native dscr column, a cfads column present, but more than
    one column matching the debt-service pattern (serv/pay/repay) -> the else
    branch logs and no dscr column is added.
    """
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    rows = [
        {
            "year": 1,
            "cfads_final_lkr": 200.0,
            "debt_service_lkr": 100.0,
            "debt_repay_lkr": 50.0,
        },
    ]
    result = _synthetic_result("ambiguous", {"equity_irr": 0.08}, rows)

    with caplog.at_level("WARNING", logger=sa_mod.logger.name):
        _summary_df, timeseries_df = sa._build_dataframes([result])

    assert "dscr" not in timeseries_df.columns
    assert any("Could not derive DSCR" in rec.message for rec in caplog.records)


def test_build_dataframes_no_cfads_cannot_derive(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No cfads column at all also lands in the underivable warning branch."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    rows = [{"year": 1, "revenue_lkr": 200.0, "debt_service_lkr": 100.0}]
    result = _synthetic_result("nocfads", {"equity_irr": 0.08}, rows)

    with caplog.at_level("WARNING", logger=sa_mod.logger.name):
        _summary_df, timeseries_df = sa._build_dataframes([result])

    assert "dscr" not in timeseries_df.columns
    assert any("Could not derive DSCR" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _export_to_excel: no-op and fallback (lines 481-482, 494-501)
# ---------------------------------------------------------------------------
def test_export_to_excel_noop_when_no_output_path(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_export_to_excel with output_path=None logs and returns without writing."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, output_path=None)
    with caplog.at_level("WARNING", logger=sa_mod.logger.name):
        sa._export_to_excel(pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]}))
    assert any("No output_path configured" in rec.message for rec in caplog.records)


def test_export_to_excel_falls_back_to_basic_workbook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ExcelExporter raises, a basic pandas workbook is written instead.

    ExcelExporter is replaced with a constructor that raises, forcing the
    except branch that writes Summary/Timeseries sheets via pd.ExcelWriter.
    """

    class _BoomExporter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("exporter unavailable")

    # The method imports ExcelExporter from analytics.export_helpers at call
    # time; patch it there so the import inside the method picks up the boom.
    import analytics.export_helpers as eh

    monkeypatch.setattr(eh, "ExcelExporter", _BoomExporter)

    out = tmp_path / "fallback.xlsx"
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, output_path=out)
    summary_df = pd.DataFrame({"equity_irr": [0.08]}, index=["s1"])
    timeseries_df = pd.DataFrame({"year": [1, 2], "cfads": [10.0, 20.0]})

    sa._export_to_excel(summary_df, timeseries_df)

    assert out.exists()
    assert out.stat().st_size > 0
    # Both sheets are present in the fallback workbook.
    sheets = pd.read_excel(out, sheet_name=None)
    assert set(sheets) == {"Summary", "Timeseries"}


# ---------------------------------------------------------------------------
# _export_charts: all branches (lines 510-528)
# ---------------------------------------------------------------------------
def test_export_charts_noop_when_no_output_path(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_export_charts with output_path=None logs and returns without exporting."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, output_path=None)
    with caplog.at_level("WARNING", logger=sa_mod.logger.name):
        sa._export_charts(pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]}))
    assert any("No output_path configured" in rec.message for rec in caplog.records)


def test_export_charts_uses_export_charts_method(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ChartExporter exposing export_charts is dispatched through it."""
    calls: List[str] = []

    class _Charter:
        def __init__(self, output_dir: str) -> None:
            self.output_dir = output_dir

        def export_charts(self, summary_df: Any, ts_df: Any) -> None:
            calls.append("export_charts")

    import analytics.export_helpers as eh

    monkeypatch.setattr(eh, "ChartExporter", _Charter)

    out = tmp_path / "report.xlsx"
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, output_path=out)
    sa._export_charts(pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]}))

    assert calls == ["export_charts"]


def test_export_charts_falls_back_to_individual_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ChartExporter without export_charts falls back to per-chart methods."""
    calls: List[str] = []

    class _Charter:
        def __init__(self, output_dir: str) -> None:
            self.output_dir = output_dir

        def export_dscr_chart(self, ts_df: Any) -> None:
            calls.append("dscr")

        def export_irr_histogram(self, summary_df: Any) -> None:
            calls.append("irr")

    import analytics.export_helpers as eh

    monkeypatch.setattr(eh, "ChartExporter", _Charter)

    out = tmp_path / "report.xlsx"
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, output_path=out)
    sa._export_charts(pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]}))

    assert calls == ["dscr", "irr"]


def test_export_charts_unavailable_warns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ChartExporter that raises on construction lands in the warning branch."""

    class _BoomCharter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("charts unavailable")

    import analytics.export_helpers as eh

    monkeypatch.setattr(eh, "ChartExporter", _BoomCharter)

    out = tmp_path / "report.xlsx"
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, output_path=out)
    with caplog.at_level("WARNING", logger=sa_mod.logger.name):
        sa._export_charts(pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]}))

    assert any("ChartExporter not available" in rec.message for rec in caplog.records)
