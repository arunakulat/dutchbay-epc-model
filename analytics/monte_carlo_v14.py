"""DEPRECATED LEGACY SHIM: use analytics.mc.engine instead.

This flat-module import surface is retained only for backward compatibility.
Canonical Monte Carlo execution now lives in ``analytics.mc.engine`` and the
Hydra CLI lives in ``analytics/cli/cli_monte_carlo_hydra.py``.
"""

from analytics.mc.engine import MonteCarloEngine, run_monte_carlo_analysis  # noqa
