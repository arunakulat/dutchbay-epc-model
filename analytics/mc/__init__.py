from __future__ import annotations

from typing import Any

"""
analytics.mc

Canonical Monte Carlo package for v14 analytics.

CRITICAL: This __init__.py uses lazy loading via __getattr__ to avoid
circular imports with analytics.evaluation_v14.

Public API:
    # Engine
    MonteCarloEngine
    run_monte_carlo_analysis
    
    # Correlation
    CorrelationSpec
    load_correlation_from_config
    apply_correlation_structure
    validate_correlation_matrix
    
    # Exports (Lender Analytics)
    CovenantSpec
    build_lender_risk_table
    build_casper_risk_blocks
    
    # Aggregation
    aggregate_trials
"""

__all__ = [
    # Engine
    "MonteCarloEngine",
    "run_monte_carlo_analysis",
    # Correlation
    "CorrelationSpec",
    "load_correlation_from_config",
    "apply_correlation_structure",
    "validate_correlation_matrix",
    # Exports
    "CovenantSpec",
    "build_lender_risk_table",
    "build_casper_risk_blocks",
    # Aggregation
    "aggregate_trials",
]


def __getattr__(name: str) -> Any:
    """
    Lazy module loading to prevent circular imports.

    This pattern ensures that importing 'analytics.mc' does NOT
    trigger import of analytics.evaluation_v14 at import time.
    """
    # Engine exports
    if name in ("MonteCarloEngine", "run_monte_carlo_analysis"):
        from analytics.mc.engine import (
            MonteCarloEngine,
            run_monte_carlo_analysis,
        )

        return {
            "MonteCarloEngine": MonteCarloEngine,
            "run_monte_carlo_analysis": run_monte_carlo_analysis,
        }[name]

    # Correlation exports
    if name in (
        "CorrelationSpec",
        "load_correlation_from_config",
        "apply_correlation_structure",
        "validate_correlation_matrix",
    ):
        from analytics.mc.correlation import (
            CorrelationSpec,
            apply_correlation_structure,
            load_correlation_from_config,
            validate_correlation_matrix,
        )

        return {
            "CorrelationSpec": CorrelationSpec,
            "load_correlation_from_config": load_correlation_from_config,
            "apply_correlation_structure": apply_correlation_structure,
            "validate_correlation_matrix": validate_correlation_matrix,
        }[name]

    # Export utilities
    if name in ("CovenantSpec", "build_lender_risk_table", "build_casper_risk_blocks"):
        from analytics.mc.exports import (
            CovenantSpec,
            build_casper_risk_blocks,
            build_lender_risk_table,
        )

        return {
            "CovenantSpec": CovenantSpec,
            "build_lender_risk_table": build_lender_risk_table,
            "build_casper_risk_blocks": build_casper_risk_blocks,
        }[name]

    # Aggregation
    if name == "aggregate_trials":
        from analytics.mc.aggregate import aggregate_trials

        return aggregate_trials

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
