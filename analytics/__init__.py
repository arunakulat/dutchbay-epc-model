#!/usr/bin/env python3
"""
DutchBay v14 Analytics Layer - Production Release

Scenario analysis, sensitivity, Monte Carlo, and reporting for v14 finance engine.

Canonical Entrypoint:
    >>> from run_full_pipeline_v14 import run_v14_pipeline
    >>> result = run_v14_pipeline("scenarios/example_a.yaml")

Direct Analytics API:
    >>> from analytics import load_scenario_config, evaluate_with_overrides
    >>> config = load_scenario_config("scenarios/example_a.yaml")
    >>> kpis = evaluate_with_overrides(config, {})

Batch Processing:
    >>> from analytics import ScenarioAnalytics
    >>> sa = ScenarioAnalytics(scenarios_dir="scenarios/")
    >>> summary_df, timeseries_df = sa.run()

Version History:
    0.1.0 - Initial v14 analytics (scenario loader, evaluator)
    0.2.0 - Added ScenarioAnalytics batch processor
    0.2.1 - Fixed public API to expose evaluate_with_overrides
"""

from __future__ import annotations

__version__ = "0.2.1"
__author__ = "DutchBay EPC Model Team"

# =============================================================================
# Core Analytics API (Used by run_full_pipeline_v14.py)
# =============================================================================

from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config

# =============================================================================
# Batch Processing & Utilities
# =============================================================================

from analytics.scenario_analytics import ScenarioAnalytics

# =============================================================================
# Optional: Keep legacy alias for backwards compatibility
# =============================================================================

from analytics.evaluate_scenario import evaluate_scenario_as_dict

# =============================================================================
# Public API Surface
# =============================================================================

__all__ = [
    # Core API (canonical)
    "evaluate_with_overrides",  # Used by run_v14_pipeline()
    "load_scenario_config",     # Config loader
    
    # Batch processing
    "ScenarioAnalytics",        # Batch scenario runner
    
    # Legacy compatibility
    "evaluate_scenario_as_dict",  # Deprecated: use evaluate_with_overrides
    
    # Module metadata
    "__version__",
]

# =============================================================================
# Verification: Ensure All Exports Exist
# =============================================================================

def _verify_exports() -> None:
    """
    Runtime verification that all __all__ exports are actually importable.
    
    Raises:
        ImportError: If any export in __all__ is not defined
    """
    import sys
    current_module = sys.modules[__name__]
    
    missing_exports = []
    for export_name in __all__:
        if export_name.startswith("__"):
            continue  # Skip dunder names
        if not hasattr(current_module, export_name):
            missing_exports.append(export_name)
    
    if missing_exports:
        raise ImportError(
            f"analytics/__init__.py: Missing exports in __all__: {missing_exports}"
        )

# Run verification at import time
_verify_exports()

