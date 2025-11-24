"""
scripts/model_guard.py

Quick CLI tool to validate all parameter ranges for a scenario.
Detects negative IRR, crazy swings, missing values, etc.
"""

import sys
from analytics.sensitivity.validation import validate_parameter_ranges
from analytics.contracts_v14 import ParameterRangeConfig

# This would typically load your param configs from YAML:
params = [
    ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900, low_pct=-25, high_pct=25, steps=5),
    ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=42, low_pct=-10, high_pct=10, steps=5)
]
config_path = sys.argv[1] if len(sys.argv) > 1 else "scenarios/dutchbay_lendercase_2025Q4.yaml"

problems = validate_parameter_ranges(config_path, params)
if not problems.empty:
    print("🛑 Issues found in parameter sweeps:")
    print(problems.to_string(index=False))
else:
    print("✅ All parameter sweeps are physically and financially plausible.")
