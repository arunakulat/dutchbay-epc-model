"""
scripts/model_guard.py

Quick CLI tool to validate all parameter ranges for a scenario.
Detects negative IRR, crazy swings, missing values, etc.
"""

import sys

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity.validation import validate_parameter_ranges

# This would typically load your param configs from YAML:
params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900,
        low_pct=-25,
        high_pct=25,
        points=5,
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=42,
        low_pct=-10,
        high_pct=10,
        points=5,
    ),
]
if len(sys.argv) < 2:
    # #1775: the scenario is always the caller's choice; no site default.
    print("usage: python scripts/ci/model_guard.py <scenario.yaml>")
    sys.exit(2)
config_path = sys.argv[1]

problems = validate_parameter_ranges(config_path, params)
if not problems.empty:
    print("🛑 Issues found in parameter sweeps:")
    print(problems.to_string(index=False))
else:
    print("✅ All parameter sweeps are physically and financially plausible.")

# EOF
