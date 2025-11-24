"""
tests/contracts/test_sensitivity_edgecases.py

Runs the pipeline with nonsensical/extreme values to ensure graceful failure/handling.
"""

import pytest
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity.validation import validate_parameter_ranges

@pytest.mark.parametrize("params", [
    # Zero capex (nonsense)
    [ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=0, low_pct=0, high_pct=0, steps=3)],
    # Negative CF
    [ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=-5, low_pct=0, high_pct=0, steps=3)]
])
def test_bad_params_are_caught(params):
    config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"
    df = validate_parameter_ranges(config_path, params)
    assert not df.empty  # Should flag at least one problem for nonphysical input!
