#!/usr/bin/env python3
"""
Go-With-The-Flow smoke test for ScenarioAnalytics batch run.

Intent:
- Run ScenarioAnalytics over the real `scenarios/` directory.
- Assert:
  * Non-empty summary and timeseries DataFrames.
  * BatchResultSummary looks sane (successful / failed).
  * Canonical example scenarios are present in the summary index.
  * Timeseries is wired with `scenario_name` for downstream use.

This test is deliberately tolerant of:
- Some scenarios failing validation (e.g. bad_missing_tax, scenario_mytest).
"""

from pathlib import Path

from analytics.scenario_analytics import ScenarioAnalytics


def test_scenario_analytics_smoke(tmp_path: Path) -> None:
    """
    End-to-end smoke over the scenarios/ directory.
    """
    # Arrange: point to the bundled example scenarios
    scenarios_dir = Path("scenarios")
    assert (
        scenarios_dir.is_dir()
    ), "Expected 'scenarios/' directory to exist at repo root"

    output_path = tmp_path / "dummy.xlsx"

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
    )

    # Act: run without producing charts (fast path)
    summary_df, timeseries_df, batch_report = sa.run(
        export_excel=False,
        export_charts=False,
    )

    # Basic shape checks
    assert summary_df is not None
    assert timeseries_df is not None

    assert not summary_df.empty, "summary_df should not be empty"
    assert not timeseries_df.empty, "timeseries_df should not be empty"

    # Batch report sanity – duck-typed BatchResultSummary
    assert batch_report is not None
    assert hasattr(batch_report, "successful")
    assert hasattr(batch_report, "failed")

    successful = batch_report.successful
    failed = batch_report.failed

    assert isinstance(successful, list)
    assert isinstance(failed, list)
    assert (
        len(successful) >= 1
    ), "Expected at least one successful scenario in batch run"
    assert len(successful) + len(failed) >= 1, "Batch counters look broken"

    # Expected canonical example scenarios should be present in the summary index.
    # Note: the file stem is 'eaxmple_b', not 'example_b'.
    expected_scenarios = {
        "edge_extreme_stress",
        "example_a",
        "example_a_old",
        "example_b",
    }

    found_scenarios = set(summary_df.index.astype(str))
    missing = expected_scenarios - found_scenarios
    assert not missing, f"Missing expected scenarios in summary_df index: {missing}"

    # Timeseries should be wired with scenario_name so downstream filtering works.
    assert (
        "scenario_name" in timeseries_df.columns
    ), "timeseries_df must have 'scenario_name' column"
    assert (
        timeseries_df["scenario_name"].notna().any()
    ), "scenario_name column should contain non-null values"

    # There should be at least one row in timeseries per expected scenario set
    timeseries_scenarios = set(timeseries_df["scenario_name"].astype(str))
    overlap = timeseries_scenarios & expected_scenarios
    assert len(overlap) >= 1, (
        "Expected at least one canonical scenario to appear in timeseries_df; "
        f"found only {timeseries_scenarios}"
    )

    # IMPORTANT: we do *not* assert on output_path.is_file() here.
    # File creation on disk is covered by test_scenario_analytics_excel_export_smoke
    # where export_excel=True.
