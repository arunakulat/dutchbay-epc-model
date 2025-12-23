"""DEPRECATED: Use analytics.core.sensitivity_runner instead.

This module will be removed in a future release.
Please update imports to: from analytics.core.sensitivity_runner import ...
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "analytics.sensitivity_runner is deprecated. "
    "Use 'from analytics.core.sensitivity_runner import ...' instead. "
    "This shim will be removed in Sprint 17.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from analytics.core.sensitivity_runner import (  # noqa: F401, E402
    run_sensitivity_analysis,
)

__all__ = [
    "run_sensitivity_analysis",
]
