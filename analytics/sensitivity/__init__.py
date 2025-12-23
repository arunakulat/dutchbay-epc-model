from __future__ import annotations

"""
analytics.sensitivity

Sensitivity analysis package for v14+ scenarios.

Public API:
- run_sensitivity_analysis(...)
- build_one_way_sensitivity_suite(...)
- suite_to_tables(...)
- suite_to_records(...)
- TailRiskConfig
- SensitivityRunConfig
"""

from analytics.sensitivity.engine import (  # noqa: F401
    SensitivityRunConfig,
    run_sensitivity_analysis,
    build_one_way_sensitivity_suite,
)
from analytics.sensitivity.tail_risk import (  # noqa: F401
    TailRiskConfig,
    enrich_suite_with_tail_risk,
)
from analytics.sensitivity.export import (  # noqa: F401
    suite_to_tables,
    suite_to_records,
)

__all__ = [
    "SensitivityRunConfig",
    "run_sensitivity_analysis",
    "build_one_way_sensitivity_suite",
    "TailRiskConfig",
    "enrich_suite_with_tail_risk",
    "suite_to_tables",
    "suite_to_records",
]
