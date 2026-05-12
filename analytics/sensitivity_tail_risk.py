# ruff: noqa: E402
from __future__ import annotations

"""
analytics.sensitivity_tail_risk

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity.tail_risk import TailRiskConfig, enrich_suite_with_tail_risk

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "analytics.sensitivity_tail_risk is deprecated. Use 'from analytics.sensitivity.tail_risk import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.tail_risk import *  # noqa: F401,F403
