# ruff: noqa: E402
from __future__ import annotations

"""
analytics.sensitivity_export

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity.export import sensitivity_to_dataframe

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "analytics.sensitivity_export is deprecated. Use 'from analytics.sensitivity.export import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.export import *  # noqa: F401,F403
