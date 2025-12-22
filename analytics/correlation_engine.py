"""
analytics.correlation_engine

BACKWARD COMPATIBILITY SHIM

DEPRECATED: Import from analytics.mc.correlation instead.

New canonical path:
    from analytics.mc.correlation import CorrelationSpec, load_correlation_from_config

This shim maintains backward compatibility for existing code.
"""
import warnings

warnings.warn(
    "Importing from analytics.correlation_engine is deprecated. "
    "Use 'from analytics.mc.correlation import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.mc.correlation import *  # noqa: F401, F403

__all__ = [
    "CorrelationSpec",
    "validate_correlation_matrix",
    "apply_correlation_structure",
    "get_renewable_energy_correlation_template",
    "load_correlation_from_config",
]
