"""
Equity Package for v14 Finance Models.

This package is the public equity namespace for the v14 finance stack. The
production distribution waterfall lives in finance.equity_distribution_v14_hydra
for backward compatibility with existing imports, and is re-exported here for
new code.

Public API
----------
Core equity metrics:
    - EquityCashflowSummary
    - calculate_equity_irr
    - calculate_equity_npv
    - calculate_cash_on_cash
    - calculate_moic
    - calculate_payback_period
    - calculate_pe_triad
    - calculate_equity_performance

Distribution waterfall:
    - EquityDistributionConfig
    - EquityDistributionEngine
    - build_equity_distribution_schedule
    - calculate_equity_distribution_from_pipeline

Architecture Principles
-----------------------
GWTF:     Single public namespace for equity calculations.
CESSPIT:  Explicit validation and fail-fast distribution status.
CASPER:   JSON-safe audit metadata for computed/defaulted/failed states.
CCCDIR:   Clear import surface; no generated orchestrator becomes canonical.
"""

from __future__ import annotations

from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    EquityDistributionEngine,
    build_equity_distribution_schedule,
    calculate_equity_distribution_from_pipeline,
)
from finance.equity_v14 import (
    EquityCashflowSummary,
    calculate_cash_on_cash,
    calculate_equity_irr,
    calculate_equity_npv,
    calculate_equity_performance,
    calculate_moic,
    calculate_payback_period,
    calculate_pe_triad,
    summarise_equity_cashflows,
)

__all__ = [
    "EquityCashflowSummary",
    "EquityDistributionConfig",
    "EquityDistributionEngine",
    "build_equity_distribution_schedule",
    "calculate_cash_on_cash",
    "calculate_equity_distribution_from_pipeline",
    "calculate_equity_irr",
    "calculate_equity_npv",
    "calculate_equity_performance",
    "calculate_moic",
    "calculate_payback_period",
    "calculate_pe_triad",
    "summarise_equity_cashflows",
]

# EOF
