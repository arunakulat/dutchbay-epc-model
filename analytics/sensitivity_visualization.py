from __future__ import annotations

"""
analytics.sensitivity_visualization

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity.viz import plot_tornado, plot_heatmap_matrix

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "analytics.sensitivity_visualization is deprecated. Use 'from analytics.sensitivity.viz import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.viz import *  # noqa: F401,F403
