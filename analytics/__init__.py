"""
Thin facade for v14 sensitivity analytics.

For now this just re-exports the main public API from analytics.sensitivity_v14.
The heavy v14 feature set (tail risk, Pareto, multi-metric, etc.) is parked for
a future refactor.
"""

from analytics.sensitivity_v14 import (  # type: ignore[import]
    ParameterRangeConfig,
    TornadoResult,
    SensitivitySuite,
    run_tornado_sensitivity,
)

__all__ = [
    "ParameterRangeConfig",
    "TornadoResult",
    "SensitivitySuite",
    "run_tornado_sensitivity",
]