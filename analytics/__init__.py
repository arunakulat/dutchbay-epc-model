"""Analytics module for DutchBay EPC Model.

Pydantic v2 Migration Status (Sprint 12):
- contracts_v14.py: Core dataclasses (native)
- contracts_v14_compat.py: Backward-compat stubs (temporary)
- Full v2 migration: Sprint 13
"""

# Re-export compatibility stubs for legacy tests
from analytics.contracts_v14_compat import (
    CasperResult,
    TailRiskMetrics,
    MultiMetricSensitivitySuite,
    Distribution,
    DownsideMetrics,
    build_cashflow_result_from_annual_rows,
)

__all__ = [
    "CasperResult",
    "TailRiskMetrics",
    "MultiMetricSensitivitySuite",
    "Distribution",
    "DownsideMetrics",
    "build_cashflow_result_from_annual_rows",
]
