from __future__ import annotations

"""
analytics.sensitivity_dscr_v14

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity.dscr import run_dscr_one_way, DscrSensitivityConfig

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "analytics.sensitivity_dscr_v14 is deprecated. Use 'from analytics.sensitivity.dscr import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.dscr import *  # noqa: F401,F403
