# BACKWARD COMPATIBILITY SHIM
# =========================
#
# This module has been moved to analytics.casper.kpi_normalizer
# This shim will be removed in v15.
#
# Migration Guide:
#   OLD: from analytics.kpi_normalizer import normalize_kpis_by_capacity
#   NEW: from analytics.casper import normalize_kpis_by_capacity
#   OR:  from analytics.casper.kpi_normalizer import normalize_kpis_by_capacity
#
# Sprint 9 Migration: CASPER modules consolidated to analytics.casper/
#

from analytics.casper.kpi_normalizer import *  # noqa: F401, F403

__all__ = [
    "normalize_kpis_by_capacity",
    "calculate_percentile_ranking",
    "benchmark_normalized_kpis",
    "compare_projects",
    "NormalizedKPIs",
    "IndustryBenchmarks",
    "PercentileRanking",
]
