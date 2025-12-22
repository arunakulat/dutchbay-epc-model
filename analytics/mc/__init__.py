from __future__ import annotations

"""
analytics.mc

Canonical Monte Carlo package for v14 analytics.

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

# Engine
from analytics.mc.engine import (
    MonteCarloEngine,
    run_monte_carlo_analysis,
)

# Correlation
from analytics.mc.correlation import (
    CorrelationSpec,
    load_correlation_from_config,
    apply_correlation_structure,
    validate_correlation_matrix,
)

# Exports (Lender Analytics)
from analytics.mc.exports import (
    CovenantSpec,
    build_lender_risk_table,
    build_casper_risk_blocks,
)

# Aggregation
from analytics.mc.aggregate import aggregate_trials

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
