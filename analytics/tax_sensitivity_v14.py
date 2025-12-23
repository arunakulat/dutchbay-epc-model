from __future__ import annotations

"""
analytics.tax_sensitivity_v14

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity.tax import run_tax_one_way, TaxSensitivityConfig

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "analytics.tax_sensitivity_v14 is deprecated. Use 'from analytics.sensitivity.tax import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.tax import *  # noqa: F401,F403
