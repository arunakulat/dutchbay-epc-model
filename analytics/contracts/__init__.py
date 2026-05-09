"""Unified contracts package for v14 analytics.

The canonical compatibility surface currently lives in
``analytics.contracts_v14``. Re-exporting it here preserves both import styles:

    from analytics.contracts_v14 import ScenarioResult
    from analytics.contracts import ScenarioResult

Legacy phase-3 sensitivity helpers are intentionally not redefined here. Keep
this package as a thin public API facade over the v14 source of truth.
"""

from __future__ import annotations

from analytics.contracts_v14 import *  # noqa: F401,F403
from analytics.contracts_v14 import __all__ as _CONTRACTS_V14_ALL

__all__ = list(_CONTRACTS_V14_ALL)
