from __future__ import annotations

"""
Legacy shim for v14chat.

ScenarioManager has been moved to analytics.scenario_manager
to ring-fence dutchbay_v14chat/ as a thin wrapper layer.

All new code should import:
    from analytics.scenario_manager import ScenarioManager
"""

from analytics.scenario_manager import ScenarioManager

__all__ = ["ScenarioManager"]