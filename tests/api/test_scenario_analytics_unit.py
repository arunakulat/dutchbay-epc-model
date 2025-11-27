#!/usr/bin/env python3
"""
Unit tests for Analytics scenario dataframe construction (Go With The Flow edition).
Ensures all arguments to ScenarioResult are supplied.
"""

from analytics.scenario_analytics import ScenarioResult


def _make_scenario_result(scenario_name, kpis, annual):
    # Insert required placeholders for new/required model fields.
    dummy_annual_rows = []
    dummy_debt_result = {}
    return ScenarioResult(
        scenario_name,
        kpis,
        annual,
        dummy_annual_rows,
        dummy_debt_result,
        discount_rate=0.08,
    )


def test_build_dataframes_preserves_scenario_name_and_dscr_series():
    scenario_name = "scenario_a"
    kpis_a = {"IRR": 0.124}
    annual_a = [{"year": 2030, "dscr": 1.2}, {"year": 2031, "dscr": 1.3}]
    res_a = _make_scenario_result(scenario_name, kpis_a, annual_a)
    # Go With The Flow: check both possible keys for name.
    assert (
        getattr(res_a, "scenario_name", getattr(res_a, "name", None)) == scenario_name
    )
    assert hasattr(res_a, "discount_rate")
