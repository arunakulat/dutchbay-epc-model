#!/usr/bin/env python3
"""
Smokes + micro-unit tests for the ScenarioAnalytics orchestrator and KPI metrics.

Covers:
- Batch run over the example scenarios directory
- Presence of key KPI columns (NPV/IRR/DSCR)
- Presence and cleanliness of the dscr_series field
- Basic structure of the timeseries DataFrame
- Direct unit test of calculate_scenario_kpis DSCR filtering/aggregation
"""

from pathlib import Path
import math

import pytest

from analytics.scenario_analytics import ScenarioAnalytics
from analytics.core.metrics import calculate_scenario_kpis


def test_scenario_analytics_smoke(tmp_path):
    """
    End-to-end smoke over the scenarios/ directory.

    Asserts:
    - Non-empty summary and timeseries DataFrames
    - Expected scenarios present
    - KPI columns (including dscr_series) exist
    - dscr_series is a finite numeric list per scenario
    - timeseries has basic CFADS + scenario_name wiring
    """
    # Arrange: point to the bundled example scenarios
    scenarios_dir = Path("scenarios")
    assert scenarios_dir.is_dir(), "Expected 'scenarios/' directory to exist at repo root"

    output_path = tmp_path / "dummy.xlsx"

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
    )

    # Act: run without producing Excel/charts (fast smoke)
    summary_df, timeseries_df = sa.run(
        export_excel=False,
        export_charts=False,
    )

    # Assert: we got non-empty DataFrames
    assert not summary_df.empty, "summary_df should not be empty"
    assert not timeseries_df.empty, "timeseries_df should not be empty"

    # We expect at least the canonical four examples in the index
    expected_scenarios = {
        "edge_extreme_stress",
        "example_a",
        "example_a_old",
        "example_b",
    }
    found_scenarios = set(summary_df.index.astype(str))
    missing = expected_scenarios - found_scenarios
    assert not missing, f"Missing expected scenarios: {missing}"

    # Summary KPI columns that should always be present
    for col in [
        "npv",
        "irr",
        "dscr_min",
        "dscr_max",
        "dscr_mean",
        "dscr_median",
        "total_cfads_usd",
        "final_cfads_usd",
        "mean_operational_cfads_usd",
        "dscr_series",
    ]:
        assert col in summary_df.columns, f"Expected KPI column '{col}' in summary_df"

    # dscr_series should be a cleaned, finite numeric list per scenario
    series_col = summary_df["dscr_series"]
    for scenario_name, dscr_list in series_col.items():
        assert isinstance(
            dscr_list, (list, tuple)
        ), f"dscr_series for {scenario_name} should be list/tuple, got {type(dscr_list)}"
        assert dscr_list, f"dscr_series for {scenario_name} should not be empty"

        for v in dscr_list:
            assert isinstance(
                v, (int, float)
            ), f"DSCR value for {scenario_name} should be numeric, got {type(v)}"
            assert math.isfinite(
                v
            ), f"DSCR value for {scenario_name} should be finite, got {v}"

    # Timeseries should have a scenario_name column and basic CFADS fields
    for col in ["year", "cfads_usd", "scenario_name"]:
        assert col in timeseries_df.columns, f"Expected '{col}' in timeseries_df"

    # Every scenario in summary_df should appear in timeseries_df
    ts_scenarios = set(timeseries_df["scenario_name"].astype(str).unique())
    missing_in_ts = expected_scenarios - ts_scenarios
    assert not missing_in_ts, f"Scenarios missing from timeseries_df: {missing_in_ts}"

    # Quick sanity check: at least one scenario has a "healthy" DSCR min > 1
    healthy = summary_df["dscr_min"].dropna()
    assert (healthy > 1.0).any(), "Expected at least one scenario with dscr_min > 1.0"


def test_calculate_scenario_kpis_dscr_filtering():
    """
    Unit test: calculate_scenario_kpis should:
    - Drop non-positive and non-finite DSCR values from the series
    - Compute stats from the cleaned series only

    Input dscr_series: [0, inf, 1.5, 2.0]
    Expected cleaned series: [1.5, 2.0]
    Expected stats:
      dscr_min    = 1.5
      dscr_max    = 2.0
      dscr_mean   = 1.75
      dscr_median = 1.75
    """
    scenario_name = "unit_test_scenario"

    # Minimal valuation payload — the function should pass these through
    valuation = {
        "npv": 0.0,
        "irr": None,
    }

    # Synthetic debt_result with deliberately dirty DSCRs
    raw_dscr = [0.0, math.inf, 1.5, 2.0]
    debt_result = {
        "dscr_series": raw_dscr,
        # Provide minimal additional fields if the implementation expects them
        "max_debt_usd": 100.0,
        "final_debt_usd": 0.0,
        "total_idc_usd": 0.0,
    }

    # CFADS series can be arbitrary here; DSCR stats should not depend on it
    cfads_series_usd = [0.0, 0.0, 0.0, 0.0]

    # Act
    result = calculate_scenario_kpis(
        scenario_name=scenario_name,
        valuation=valuation,
        debt_result=debt_result,
        cfads_series_usd=cfads_series_usd,
    )

    # Assert: DSCR series was cleaned correctly
    assert result["dscr_series"] == [1.5, 2.0]

    # Assert: stats are based on the cleaned series only
    assert result["dscr_min"] == pytest.approx(1.5)
    assert result["dscr_max"] == pytest.approx(2.0)
    assert result["dscr_mean"] == pytest.approx(1.75)
    assert result["dscr_median"] == pytest.approx(1.75)

    # Sanity: no NaNs or infs in the stored stats
    for key in ["dscr_min", "dscr_max", "dscr_mean", "dscr_median"]:
        v = result[key]
        assert isinstance(v, (int, float)), f"{key} should be numeric"
        assert math.isfinite(v), f"{key} should be finite, got {v}"
