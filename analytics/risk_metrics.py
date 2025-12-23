"""DEPRECATED: Use analytics.core.risk_metrics instead.

This module will be removed in a future release.
Please update imports to: from analytics.core.risk_metrics import ...
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "analytics.risk_metrics is deprecated. "
    "Use 'from analytics.core.risk_metrics import ...' instead. "
    "This shim will be removed in Sprint 17.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from analytics.core.risk_metrics import (  # noqa: F401, E402
    CovenantBreachAnalysis,
    DownsideRisk,
    MetricRiskSummary,
    PercentileAnalysis,
    RiskConfig,
    TailRiskAnalyzer,
    TailRiskReport,
    VaRCVaRResult,
)

__all__ = [
    "CovenantBreachAnalysis",
    "DownsideRisk",
    "MetricRiskSummary",
    "PercentileAnalysis",
    "RiskConfig",
    "TailRiskAnalyzer",
    "TailRiskReport",
    "VaRCVaRResult",
]
