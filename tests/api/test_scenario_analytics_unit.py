#!/usr/bin/env python3
"""
Targeted unit tests for ScenarioAnalytics._build_dataframes.

Goals:
- Verify scenario_name wiring (index + column).
- Verify DSCR scalar fallback (dscr_min -> flat dscr line).
- Verify cooperation with kpi_normalizer:
    * project_irr canonicalisation from an IRR-like column.
    * dscr canonicalisation in timeseries.
"""

from pathlib import Path

import pandas as pd

from analytics.scenario_analytics import ScenarioAnalytics, ScenarioResult


def _make_sa() -> ScenarioAnalytics:
    """
    Construct a ScenarioAnalytics instance for unit testing only.

    scenarios_dir/output_path are not used by _build_dataframes, so we can
    point them at dummy paths.
    """
    return ScenarioAnalytics(
        scenarios_dir=Path("scenarios"),
        output_path=None,
        strict=True,
    )


def test_build_dataframes_attaches_scenario_name_and_dscr_scalar():
    """
    When annual_rows lack a 'dscr' column but KPIs expose a scalar dscr_min,
    _build_dataframes should:
      - propagate scenario_name into summary + timeseries,
      - attach a flat 'dscr' series per (scenario, period) using dscr_min.
    """
    sa = _make_sa()

    results = [
        ScenarioResult(
            name="scenario_one",
            config_path=Path("scenarios/one.yaml"),
            kpis={
                "npv": 100.0,
                "irr": 0.12,
                "dscr_min": 1.3,
                "dscr_mean": 1.4,
            },
            annual_rows=[
                {"year": 1, "cfads_usd": 10.0},
                {"year": 2, "cfads_usd": 11.0},
            ],
            debt_result={},
        ),
        ScenarioResult(
            name="scenario_two",
            config_path=Path("scenarios/two.yaml"),
            kpis={
                "npv": 200.0,
                "irr": 0.10,
                "dscr_min": 1.1,
                "dscr_mean": 1.2,
            },
            annual_rows=[
                {"year": 1, "cfads_usd": 9.0},
                {"year": 2, "cfads_usd": 8.5},
            ],
            debt_result={},
        ),
    ]

    summary_df, timeseries_df = sa._build_dataframes(results)

    # Summary: scenario_name as index AND as an explicit column.
    assert "scenario_name" in summary_df.columns
    assert summary_df.index.name == "scenario_name"
    assert set(summary_df.index.astype(str)) == {"scenario_one", "scenario_two"}

    # Timeseries: scenario_name + dscr must be present.
    assert {"scenario_name", "year", "cfads_usd", "dscr"}.issubset(
        set(timeseries_df.columns)
    )

    # Each scenario should have a flat dscr equal to its dscr_min across periods.
    grouped = timeseries_df.groupby("scenario_name")
    for name, group in grouped:
        dscr_values = sorted(set(group["dscr"].tolist()))
        assert len(dscr_values) == 1, f"Expected flat dscr line for {name}"
        expected = 1.3 if name == "scenario_one" else 1.1
        assert dscr_values[0] == expected


def test_build_dataframes_respects_existing_dscr_and_derives_project_irr():
    """
    If annual_rows already include 'dscr', _build_dataframes should:
      - preserve that dscr series (no scalar override),
      - ensure summary_df has 'project_irr' via kpi_normalizer, using the
        first IRR-like column (here 'irr').
    """
    sa = _make_sa()

    results = [
        ScenarioResult(
            name="scenario_with_dscr",
            config_path=Path("scenarios/with_dscr.yaml"),
            kpis={
                "npv": 150.0,
                # Only 'irr' provided; kpi_normalizer should alias it to project_irr.
                "irr": 0.09,
                "dscr_min": 1.2,
            },
            annual_rows=[
                {"year": 1, "cfads_usd": 10.0, "dscr": 1.5},
                {"year": 2, "cfads_usd": 11.0, "dscr": 1.6},
            ],
            debt_result={},
        ),
    ]

    summary_df, timeseries_df = sa._build_dataframes(results)

    # Summary: project_irr must be present and equal to the original irr.
    assert "project_irr" in summary_df.columns
    irr_val = summary_df.loc["scenario_with_dscr", "irr"]
    project_irr_val = summary_df.loc["scenario_with_dscr", "project_irr"]
    assert project_irr_val == irr_val

    # Timeseries: dscr column must exist and preserve the original values.
    assert "dscr" in timeseries_df.columns
    dscr_list = timeseries_df.sort_values("year")["dscr"].tolist()
    assert dscr_list == [1.5, 1.6]

    # scenario_name must exist in both DataFrames.
    assert "scenario_name" in summary_df.columns
    assert "scenario_name" in timeseries_df.columns
    assert set(timeseries_df["scenario_name"].unique()) == {"scenario_with_dscr"}
