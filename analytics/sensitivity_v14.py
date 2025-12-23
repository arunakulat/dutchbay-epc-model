from __future__ import annotations

"""
analytics.sensitivity_v14

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity import run_sensitivity_analysis, build_one_way_sensitivity_suite

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "analytics.sensitivity_v14 is deprecated. Use 'from analytics.sensitivity import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.engine import *  # noqa: F401,F403
