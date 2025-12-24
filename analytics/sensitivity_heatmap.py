# ruff: noqa: E402
from __future__ import annotations

"""
analytics.sensitivity_heatmap

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity.heatmap import build_sensitivity_heatmap

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "analytics.sensitivity_heatmap is deprecated. Use 'from analytics.sensitivity.heatmap import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.heatmap import *  # noqa: F401,F403
