"""Smoke test for FX pipeline integration."""
import pytest
import yaml
from unittest.mock import patch, MagicMock
from analytics.pipeline_v14_enhanced import run_v14_pipeline

def test_fx_pipeline_smoke():
    """Verify that the financial pipeline runs with FX integration."""
    config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"

    # We use validation_mode='off' to skip schema checks for the smoke test
    result = run_v14_pipeline(config=config_path, validation_mode='off')

    assert result is not None
    assert result.get("status") == "success"
    assert "scenario_result" in result
    # In the current implementation, if FX is in config, it should be in the result
    # even if it's just empty/default blocks (depending on how it's implemented)

    # Let's check if the scenario_result has the expected fields
    scenario_res = result["scenario_result"]
    assert "project_irr" in scenario_res
    assert "min_dscr" in scenario_res

def test_pipeline_no_fx_smoke():
    """Verify that the pipeline runs correctly when FX is missing (backward compatibility)."""
    # Load config and remove FX
    config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    if "fx" in cfg:
        del cfg["fx"]

    temp_config = "smoke_no_fx.yaml"
    with open(temp_config, "w") as f:
        yaml.dump(cfg, f)

    try:
        result = run_v14_pipeline(config=temp_config, validation_mode='off')
        assert result is not None
        assert result.get("status") == "success"
        assert "scenario_result" in result
    finally:
        import os
        if os.path.exists(temp_config):
            os.remove(temp_config)
