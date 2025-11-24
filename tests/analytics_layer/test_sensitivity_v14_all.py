# tests/analytics_layer/test_sensitivity_v14_all.py

import tempfile
import pandas as pd
from analytics.sensitivity_v14 import (
    SensitivityRequest, run_tornado_sensitivity, run_breakeven_parameter, run_multi_metric_tornado
)
from analytics.sensitivity_export import tornado_suite_to_dataframe, breakeven_results_to_dataframe
from analytics.sensitivity_tail_risk import enrich_tornado_with_tail_risk
from analytics.sensitivity_pareto import optimize_from_sensitivity_insights
from analytics.sensitivity_heatmap import run_two_way_sensitivity, plot_two_way_heatmap

def test_tornado_and_breakeven_end_to_end():
    req = SensitivityRequest(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        parameters=[
            # Replace with minimal test params
        ],
        metric="project_irr"
    )
    suite = run_tornado_sensitivity(req)
    df = tornado_suite_to_dataframe(suite)
    assert "Impact" in df.columns and len(df) > 0

    br = run_breakeven_parameter(
        base_config_path=req.base_config_path,
        variable_name=req.parameters[0].variable_name,
        target_metric="project_irr",
        target_value=0.13
    )
    bdf = breakeven_results_to_dataframe([br])
    assert "Breakeven Value" in bdf.columns

def test_multi_metric_tornado_smoke():
    req = SensitivityRequest(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        parameters=[
            # Replace with minimal test params
        ]
    )
    suite = run_multi_metric_tornado(
        req, metrics=["project_irr", "equity_irr"]
    )
    assert len(suite.tornado_results) > 0
    record = suite.tornado_results[0]
    assert "project_irr" in record.impacts

def test_tail_risk_enrichment_stub(mc_result_stub):
    # mc_result_stub – provide a MonteCarloResult fixture
    suite_stub = ...  # minimal SensitivitySuite stub for test
    df = enrich_tornado_with_tail_risk(suite_stub, mc_result_stub, metric="project_irr")
    assert "VaR" in df.columns

def test_pareto_optimization_stub():
    # Use stubs for top 2-3 parameters to speed up
    suite_stub = ...  # minimal SensitivitySuite stub
    pf = optimize_from_sensitivity_insights(
        suite_stub,
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml"
    )
    assert isinstance(pf.frontier_points, list)

def test_two_way_heatmap_and_plot(tmp_path):
    # Provide small ParameterRangeConfig stubs for two-way
    df = run_two_way_sensitivity(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        param_x=..., param_y=...,
        metric="project_irr", steps=3
    )
    assert df.shape == (3, 3)
    filename = tmp_path / "heatmap.png"
    plot_two_way_heatmap(df, filename)
    assert filename.exists()
