"""
analytics.monte_carlo_correlation

BACKWARD COMPATIBILITY SHIM

DEPRECATED: Import from analytics.mc.correlation instead.

New canonical path:
    from analytics.mc.correlation import apply_correlation_structure

This shim maintains backward compatibility for existing code.
"""
import warnings

warnings.warn(
    "Importing from analytics.monte_carlo_correlation is deprecated. "
    "Use 'from analytics.mc.correlation import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.mc.correlation import *  # noqa: F401, F403

__all__ = [
    "CorrelationSpec",
    "validate_correlation_matrix",
    "apply_correlation_structure",
    "apply_correlation_to_lhs",
    "get_renewable_energy_correlation_template",
    "load_correlation_from_config",
]
