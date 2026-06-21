"""analytics.casper

CASPER payload generation and contract-compliant structures.

This package contains all CASPER-related functionality for the v14 analytics stack.

Public API:
    # Main orchestrator
    evaluate_with_casper_tail_risk_and_payload
    
    # Payload generation
    build_casper_payload
    CASPER_CONTRACT_VERSION
    
    # KPI normalization
    normalize_kpis_by_capacity
    calculate_percentile_ranking
    benchmark_normalized_kpis
    compare_projects
    
    # Data structures
    NormalizedKPIs
    IndustryBenchmarks
    PercentileRanking

Migration Note:
    Files moved from analytics/ root to analytics/casper/ in Sprint 9.
    Import from the package directly:
        from analytics.casper import evaluate_with_casper_tail_risk_and_payload
"""

from analytics.casper.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.casper.casper_payload import (
    CASPER_CONTRACT_VERSION,
    build_casper_payload,
)
from analytics.casper.kpi_normalizer import (
    IndustryBenchmarks,
    NormalizedKPIs,
    PercentileRanking,
    benchmark_normalized_kpis,
    calculate_percentile_ranking,
    compare_projects,
    normalize_kpis_by_capacity,
)

__all__ = [
    # Orchestrator
    "evaluate_with_casper_tail_risk_and_payload",
    # Payload
    "build_casper_payload",
    "CASPER_CONTRACT_VERSION",
    # Normalization
    "normalize_kpis_by_capacity",
    "calculate_percentile_ranking",
    "benchmark_normalized_kpis",
    "compare_projects",
    # Data structures
    "NormalizedKPIs",
    "IndustryBenchmarks",
    "PercentileRanking",
]
