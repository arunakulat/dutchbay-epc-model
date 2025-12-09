"""
Alias module for scenario_loader.

This module exists to provide a consistent import path:
  from analytics.scenarioloader import load_scenario_config

Instead of:
  from analytics.scenario_loader import load_scenario_config
"""

from analytics.scenario_loader import load_scenario_config

__all__ = ["load_scenario_config"]
