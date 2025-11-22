"""
Unit/contract test for analytics.scenario_analytics.ScenarioAnalytics.

Goals:
    - Drive ScenarioAnalytics over a minimal, controlled scenarios/ folder
      that contains only the pinned lender-case config.
    - Assert:
        * summary_df and timeseries_df are non-empty,
        * both expose a scenario_name column,
        * scenario_name labels are consistent between layers,
        * at least one KPI column exists in the summary layer,
        * subsetting on scenario_name is stable,
        * the lender-case scenario is present in the labels.
"""

from pathlib import Path
import shutil

import pandas as pd

from analytics.scenario_loader import load_scenario_config
from analytics.scenario_analytics import ScenarioAnalytics


# Canonical lender-case scenario in the repo
SCENARIO_PATH = Path("scenarios") / "dutchbay_lendercase_2025Q4.yaml"
LENDER_SCENARIO_NAME = "dutchbay_lendercase_2025Q4"


def _all_numeric(series: pd.Series) -> bool:
    """Return True if series can be safely coerced to numeric."""
    coerced = pd.to_numeric(series, errors="coerce")
    return coerced.notna().all()


def test_scenario_analytics_labels_and_shapes(tmp_path):
    """
    Run ScenarioAnalytics on a temporary scenarios/ directory containing only
    the lender-case scenario and assert:

    - summary_df and timeseries_df are non-empty.
    - Both dataframes expose a scenario_name column.
    - The same scenario_name values appear in both frames.
    - KPI columns exist in the summary layer.
    - We can subset on scenario_name without errors.
    - The lender-case scenario is present in the labels.
    """
    # 0) Sanity: lender-case config is loadable and non-empty
    assert SCENARIO_PATH.exists(), f"Expected lender-case config at {SCENARIO_PATH}"
    config = load_scenario_config(str(SCENARIO_PATH))
    assert isinstance(config, dict)
    assert config, "Loaded lender-case config should not be empty"

    # 1) Build an isolated scenarios/ directory under tmp_path
    tmp_scenarios_dir = tmp_path / "scenarios"
    tmp_scenarios_dir.mkdir(parents=True, exist_ok=True)

    # Copy the lender-case config into the temp directory
    tmp_lender_path = tmp_scenarios_dir / SCENARIO_PATH.name
    shutil.copy2(SCENARIO_PATH, tmp_lender_path)
    assert tmp_lender_path.exists()

    # 2) Run analytics via the canonical orchestrator on the isolated folder
    sa = ScenarioAnalytics(
        scenarios_dir=tmp_scenarios_dir,
        output_path=tmp_path / "v14_analytics.xlsx",
        strict=True,
    )
    summary_df, timeseries_df = sa.run()

    # 3) Non-empty frames
    assert isinstance(summary_df, pd.DataFrame)
    assert isinstance(timeseries_df, pd.DataFrame)
    assert not summary_df.empty, "summary_df should not be empty"
    assert not timeseries_df.empty, "timeseries_df should not be empty"

    # 4) scenario_name must exist and be non-null
    assert "scenario_name" in summary_df.columns
    assert "scenario_name" in timeseries_df.columns

    assert summary_df["scenario_name"].notna().all()
    assert timeseries_df["scenario_name"].notna().all()

    # 5) Scenario labels must be consistent between layers
    summary_names = set(summary_df["scenario_name"].unique())
    timeseries_names = set(timeseries_df["scenario_name"].unique())
    assert summary_names == timeseries_names
    assert len(summary_names) >= 1

    # And lender-case must be among them
    assert (
        LENDER_SCENARIO_NAME in summary_names
    ), f"Expected {LENDER_SCENARIO_NAME!r} in summary scenario_name set"
    assert (
        LENDER_SCENARIO_NAME in timeseries_names
    ), f"Expected {LENDER_SCENARIO_NAME!r} in timeseries scenario_name set"

    # 6) KPI columns should be present in the summary layer
    kpi_candidates = {"min_dscr", "project_irr", "equity_irr"}
    available_kpis = kpi_candidates & set(summary_df.columns)
    assert available_kpis, (
        "Expected at least one KPI column in summary_df; "
        f"available columns: {sorted(summary_df.columns)}"
    )

    # 7) Subsetting by scenario_name must be stable
    first_name = next(iter(summary_names))
    sub_summary = summary_df[summary_df["scenario_name"] == first_name]
    sub_timeseries = timeseries_df[timeseries_df["scenario_name"] == first_name]

    assert not sub_summary.empty
    assert not sub_timeseries.empty

    # 8) DSCR / IRR values (where present) should be numeric for the lender case
    lender_summary = summary_df[summary_df["scenario_name"] == LENDER_SCENARIO_NAME]
    assert not lender_summary.empty

    for col in ("min_dscr", "project_irr", "equity_irr"):
        if col in lender_summary.columns:
            assert _all_numeric(
                lender_summary[col]
            ), f"{col} should be numeric for lender case"
