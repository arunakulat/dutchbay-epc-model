"""Backward-compatible alias module.

Some older code used `analytics.contractsv14` (no underscore).
The canonical module is now `analytics.contracts_v14`.

Keep this file as a tiny, stable compatibility shim.
"""

from __future__ import annotations

from .contracts_v14 import *  # noqa: F401,F403
