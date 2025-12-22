"""
analytics.monte_carlo_v14

BACKWARD COMPATIBILITY SHIM

DEPRECATED: Import from analytics.mc.engine instead.

New canonical path:
    from analytics.mc.engine import MonteCarloEngine, run_monte_carlo_analysis

This shim maintains backward compatibility for existing code.
"""
import warnings

warnings.warn(
    "Importing from analytics.monte_carlo_v14 is deprecated. "
    "Use 'from analytics.mc.engine import MonteCarloEngine' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.mc.engine import (  # noqa: F401
    MonteCarloEngine,
    run_monte_carlo_analysis,
)

__all__ = ["MonteCarloEngine", "run_monte_carlo_analysis"]
