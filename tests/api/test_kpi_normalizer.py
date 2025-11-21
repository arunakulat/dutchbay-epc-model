#!/usr/bin/env python3
"""
Tests for analytics.kpi_normalizer helpers.

Covers:
- Scenario name wiring in both summary and timeseries frames
- Project IRR canonicalisation
- DSCR canonicalisation
- Integration via normalise_kpis_for_export
"""

from __future__ import annotations

import pandas as pd

from analytics.kpi_normalizer import (
    _ensure_scenario_name,
    _ensure_project_irr,
    _ensure_dscr,
    normalise_kpis_for_export,
)


def test_ensure_scenario_name_preserves_existing_column():
    """If both frames already have 'scenario_name', they should be returned unchanged."""
    summary = pd.DataFrame(
        {"scenario_name": ["A", "B"], "npv": [1.0, 2.0]}
    )
    timeseries = pd.DataFrame(
        {"scenario_name": ["A", "A", "B"], "year": [1, 2, 1]}
    )

    out_summary, out_timeseries = _ensure_scenario_name(
        summary_df=summary,
        timeseries_df=timeseries,
        scenario_id="ignored",
    )

    # Identity semantics: same columns and values
    assert list(out_summary.columns) == list(summary.columns)
    assert list(out_timeseries.columns) == list(timeseries.columns)
    assert out_summary.equals(summary)
    assert out_timeseries.equals(timeseries)


def test_ensure_scenario_name_renames_common_keys_and_falls_back():
    """
    If 'scenario' / 'config_name' exist, they should be renamed.
    If still missing, a default scenario_name should be attached.
    """
    summary = pd.DataFrame(
        {"scenario": ["S1", "S2"], "npv": [10.0, 20.0]}
    )
    timeseries = pd.DataFrame(
        {"year": [1, 2], "cfads_usd": [100.0, 200.0]}
    )

    out_summary, out_timeseries = _ensure_scenario_name(
        summary_df=summary,
        timeseries_df=timeseries,
        scenario_id="my_scenario",
    )

    # Summary: 'scenario' should have been renamed -> 'scenario_name'
    assert "scenario_name" in out_summary.columns
    assert "scenario" not in out_summary.columns
    assert list(out_summary["scenario_name"]) == ["S1", "S2"]

    # Timeseries: no scenario-like column existed, so we should get the default
    assert "scenario_name" in out_timeseries.columns
    assert set(out_timeseries["scenario_name"].unique()) == {"my_scenario"}


def test_ensure_scenario_name_uses_default_when_no_id_provided():
    """
    If no scenario_id and no scenario-like columns, we still attach a default name.
    """
    summary = pd.DataFrame({"npv": [1.0]})
    timeseries = pd.DataFrame({"year": [1, 2], "cfads_usd": [10.0, 20.0]})

    out_summary, out_timeseries = _ensure_scenario_name(
        summary_df=summary,
        timeseries_df=timeseries,
        scenario_id=None,
    )

    assert "scenario_name" in out_summary.columns
    assert "scenario_name" in out_timeseries.columns
    assert set(out_summary["scenario_name"].unique()) == {"default_scenario"}
    assert set(out_timeseries["scenario_name"].unique()) == {"default_scenario"}


def test_ensure_project_irr_aliases_from_other_irr_column():
    """
    When 'project_irr' is missing but an IRR-like column exists,
    it should be aliased.
    """
    summary = pd.DataFrame(
        {
            "irr": [0.1, 0.12],
            "npv": [100.0, 150.0],
        }
    )

    out = _ensure_project_irr(summary)

    assert "project_irr" in out.columns
    assert list(out["project_irr"]) == [0.1, 0.12]


def test_ensure_dscr_aliases_from_dscr_like_column():
    """
    When 'dscr' is missing but a DSCR-like column exists,
    it should be aliased.
    """
    timeseries = pd.DataFrame(
        {
            "year": [1, 2, 3],
            "dscr_period": [1.1, 1.2, 1.3],
        }
    )

    out = _ensure_dscr(timeseries)

    assert "dscr" in out.columns
    assert list(out["dscr"]) == [1.1, 1.2, 1.3]


def test_normalise_kpis_for_export_integration():
    """
    Full integration: both frames should emerge with
    - scenario_name
    - project_irr (summary)
    - dscr (timeseries)
    """
    summary = pd.DataFrame(
        {
            "scenario": ["case_a", "case_b"],
            "irr": [0.09, 0.11],
            "npv": [123.0, 456.0],
        }
    )
    timeseries = pd.DataFrame(
        {
            "year": [1, 2, 1, 2],
            "scenario": ["case_a", "case_a", "case_b", "case_b"],
            "dscr_period": [1.1, 1.2, 1.3, 1.4],
        }
    )

    out_summary, out_timeseries = normalise_kpis_for_export(
        summary_df=summary,
        timeseries_df=timeseries,
        scenario_id="ignored_for_this_test",
    )

    # scenario_name present and consistent
    assert "scenario_name" in out_summary.columns
    assert "scenario_name" in out_timeseries.columns
    assert set(out_summary["scenario_name"].unique()) == {"case_a", "case_b"}
    assert set(out_timeseries["scenario_name"].unique()) == {"case_a", "case_b"}

    # canonical KPI columns wired
    assert "project_irr" in out_summary.columns
    assert list(out_summary["project_irr"]) == [0.09, 0.11]

    assert "dscr" in out_timeseries.columns
    assert list(out_timeseries["dscr"]) == [1.1, 1.2, 1.3, 1.4]
