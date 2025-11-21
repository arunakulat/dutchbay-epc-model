"""
Unit-level tests for analytics.scenario_analytics.ScenarioAnalytics._build_dataframes.

We avoid running the full cashflow/debt stack and instead feed in
pre-constructed ScenarioResult objects to exercise:

- KPI aggregation into summary_df
- scenario_name as both index and column
- DSCR scalar fallback into timeseries rows
- DSCR derivation from CFADS / debt-service columns when present
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from analytics.scenario_analytics import ScenarioAnalytics, ScenarioResult


def _make_scenario_result(
    name: str,
    kpis: Dict[str, Any],
    annual_rows: List[Dict[str, Any]],
) -> ScenarioResult:
    return ScenarioResult(
        name=name,
        config_path=Path(f"{name}.yaml"),
        kpis=kpis,
        annual_rows=annual_rows,
        debt_result={"dscr_series": kpis.get("dscr_series", [])},
    )


def test_build_dataframes_preserves_scenario_name_and_dscr_series():
    sa = ScenarioAnalytics(scenarios_dir=Path("scenarios"))

    # Scenario A: has dscr_min + dscr_series and explicit CFADS/debt columns
    annual_a = [
        {"year": 1, "cfads_final_lkr": 1000.0, "debt_service_lkr": 500.0},
        {"year": 2, "cfads_final_lkr": 1100.0, "debt_service_lkr": 550.0},
    ]
    kpis_a: Dict[str, Any] = {
        "project_irr": 0.14,
        "dscr_min": 1.5,
        "dscr_series": [1.5, 1.6],
    }

    # Scenario B: no explicit DSCR series, only dscr_min scalar
    annual_b = [
        {"year": 1, "cfads_final_lkr": 900.0, "debt_service_lkr": 450.0},
        {"year": 2, "cfads_final_lkr": 950.0, "debt_service_lkr": 470.0},
    ]
    kpis_b: Dict[str, Any] = {
        "project_irr": 0.12,
        "dscr_min": 1.4,
    }

    res_a = _make_scenario_result("scenario_a", kpis_a, annual_a)
    res_b = _make_scenario_result("scenario_b", kpis_b, annual_b)

    summary_df, timeseries_df = sa._build_dataframes([res_a, res_b])

    # ------------------------------------------------------------------
    # Summary expectations
    # ------------------------------------------------------------------
    # Index should be scenario_name
    assert list(summary_df.index) == ["scenario_a", "scenario_b"]
    # And scenario_name should also be a column for downstream filters
    assert "scenario_name" in summary_df.columns

    # project_irr should be present for both scenarios
    assert "project_irr" in summary_df.columns

    # ------------------------------------------------------------------
    # Timeseries expectations
    # ------------------------------------------------------------------
    # We should have 4 rows (2 years x 2 scenarios)
    assert len(timeseries_df) == 4
    assert "scenario_name" in timeseries_df.columns

    # DSCR column must exist after derivation/fallback
    assert "dscr" in timeseries_df.columns

    # Each scenario should have a sensible DSCR series
    dscr_a = timeseries_df.loc[timeseries_df["scenario_name"] == "scenario_a", "dscr"]
    dscr_b = timeseries_df.loc[timeseries_df["scenario_name"] == "scenario_b", "dscr"]

    # For scenario A, DSCR comes from CFADS/debt columns (approx 2.0)
    assert all(d > 1.0 for d in dscr_a)

    # For scenario B, we at least get a flat series from dscr_min fallback
    assert all(abs(d - 1.4) < 1e-9 for d in dscr_b)

    # Final normalisation step should preserve scenario_name and dscr columns
    assert "scenario_name" in summary_df.columns
    assert "dscr" in timeseries_df.columns
