"""Smoke test for FX pipeline integration."""
import pytest
from unittest.mock import patch, MagicMock
from analytics.pipeline_v14 import run_v14_pipeline

@patch("analytics.pipeline_v14.WindPipeline")
def test_fx_pipeline_smoke(mock_wind_pipeline):
    """Verify that the pipeline runs with a basic FX config."""
    # Build a complex mock result structure to satisfy run_v14_pipeline
    mock_results = {
        "wind_data": {"mean_ws": 7.5},
        "energy_production": {
            "net_aep": {
                "net_aep_p50_mwh": 500000.0,
                "net_aep_p75_mwh": 480000.0,
                "net_aep_p90_mwh": 450000.0,
                "capacity_factor_net_p75": 0.4
            },
            "gross_aep": {"capacity_factor_gross": 45.0}
        },
        "statistical_analysis": {
            "weibull": {"shape_k": 2.0, "scale_c": 8.0}
        }
    }

    mock_cashflow_data = {
        "revenue_annual_usd": 10000000.0
    }

    mock_instance = mock_wind_pipeline.return_value
    mock_instance.run_complete_assessment.return_value = mock_results
    mock_instance.export_for_cashflow_model.return_value = mock_cashflow_data

    config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"

    # We want to verify that run_v14_pipeline can at least be called
    # and it successfully imports all its dependencies (like omegaconf, numpy, etc.)
    result = run_v14_pipeline(config=config_path, validation_mode='off')

    assert result is not None
    assert result.get("status") == "success"
    assert "wind_assessment" in result
    assert result["aep_p50_mwh"] == 500000.0
