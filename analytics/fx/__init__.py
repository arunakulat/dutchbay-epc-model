from __future__ import annotations

"""
analytics.fx - Foreign Exchange Risk Analysis Package

Lazy-loaded exports to avoid circular import with contracts_v14.

IMPORTANT: This module uses PEP 562 lazy loading to break the import cycle:
  contracts_v14.py → fx_contracts.py → __init__.py → fx_integration.py → contracts_v14.py

Solution: Don't import fx_integration at module import time; defer until first access.
"""

from typing import Any

# DO NOT import fx_integration at import time (avoids circular imports)
__all__ = ["integrate_fx_into_scenario_result"]


def __getattr__(name: str) -> Any:
    """PEP 562: Lazy module attribute access.

    Defers importing fx_integration until first use of integrate_fx_into_scenario_result.
    This breaks the circular dependency chain.
    """
    if name == "integrate_fx_into_scenario_result":
        from .fx_integration import integrate_fx_into_scenario_result

        return integrate_fx_into_scenario_result
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
