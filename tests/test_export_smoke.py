#!/usr/bin/env python3
"""
Go-With-The-Flow smoke test for ScenarioAnalytics Excel export.

Intent:
- Hit the ScenarioAnalytics.run(...) path with export_excel=True.
- Assert that:
  * summary_df and timeseries_df are non-empty.
  * A BatchResultSummary-like object comes back (successful/failed).
  * An Excel file is written to disk at the requested path.

Deliberately *not* asserting on:
- Any `errors` or `export_path` attributes on the batch summary.
- Any ExcelExporter internals.
"""

from pathlib import Path

from analytics.scenario_analytics import ScenarioAnalytics


def test_scenario_analytics_excel_export_smoke(tmp_path: Path) -> None:
    """
    Run ScenarioAnalytics with export_excel=True and ensure an Excel
    workbook is written to disk.
    """
    # Arrange
    scenarios_dir = Path("scenarios")
    assert (
        scenarios_dir.is_dir()
    ), "Expected 'scenarios/' directory to exist at repo root"

    output_path = tmp_path / "scenario_analytics_export.xlsx"

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
    )

    # Act: run with Excel export enabled, charts disabled (lighter deps)
    summary_df, timeseries_df, batch_report = sa.run(
        export_excel=True,
        export_charts=False,
    )

    # Basic sanity checks on outputs
    assert summary_df is not None
    assert timeseries_df is not None

    assert not summary_df.empty, "summary_df should not be empty"
    assert not timeseries_df.empty, "timeseries_df should not be empty"

    # Batch report: duck-typed BatchResultSummary
    assert batch_report is not None
    assert hasattr(batch_report, "successful")
    assert hasattr(batch_report, "failed")

    successful = getattr(batch_report, "successful")
    failed = getattr(batch_report, "failed")

    # These are currently lists of scenario_ids / error dicts
    assert isinstance(successful, list)
    assert isinstance(failed, list)
    assert (
        len(successful) >= 1
    ), "Expected at least one successful scenario in Excel export run"

    # And the file should exist on disk (either minimal exporter or ExcelExporter)
    assert output_path.is_file(), f"Expected Excel file at {output_path}"
