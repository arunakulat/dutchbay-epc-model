#!/usr/bin/env python3
"""
Smoke test for the ScenarioAnalytics export path.

Goals:
- Run the v14 analytics stack over the bundled scenarios.
- Invoke the Excel export path (ExcelExporter or fallback).
- Assert that an Excel file is created at the configured output_path.

This deliberately does NOT check chart export to avoid pulling in heavy
plotting dependencies in minimal environments. Charts are exercised
indirectly when used via the CLI.
"""

from pathlib import Path

import pytest

from analytics.scenario_analytics import ScenarioAnalytics


def test_scenario_analytics_excel_export_smoke(tmp_path):
    """
    Run ScenarioAnalytics with export_excel=True and ensure an Excel
    workbook is written to disk.
    """
    scenarios_dir = Path("scenarios")
    assert scenarios_dir.is_dir(), "Expected 'scenarios/' directory to exist at repo root"

    output_path = tmp_path / "scenario_analytics_export.xlsx"

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
    )

    # Act: run with Excel export enabled, charts disabled (lighter dependencies).
    summary_df, timeseries_df = sa.run(
        export_excel=True,
        export_charts=False,
    )

    # Basic sanity on DataFrames (should already be ensured by the main smoke,
    # but we re-assert to keep this test self-contained).
    assert not summary_df.empty, "summary_df should not be empty"
    assert not timeseries_df.empty, "timeseries_df should not be empty"

    # Assert: Excel file exists and is non-empty.
    assert output_path.exists(), f"Expected Excel output at {output_path}"
    assert output_path.is_file(), f"Expected Excel output to be a file at {output_path}"
    size = output_path.stat().st_size
    assert size > 0, f"Excel output appears empty (size={size})"
