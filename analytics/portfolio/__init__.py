"""Portfolio-level multi-technology generation aggregation.

Builds the multi-tech generation contracts (``GenerationProfile`` /
``MultiTechGenerationResult`` / ``TechnologyBreakdown`` from
``analytics.contracts_v14``) from a real finance run. Wind-only today; solar and
storage profiles slot into the same aggregate as the multi-tech build lands.
"""

from __future__ import annotations

from analytics.portfolio.generation_aggregator import (
    aggregate_generation,
    build_multi_tech_from_run,
    build_wind_generation_profile,
    resolve_wind_aep_kwh,
    technology_breakdown,
)

__all__ = [
    "aggregate_generation",
    "build_multi_tech_from_run",
    "build_wind_generation_profile",
    "resolve_wind_aep_kwh",
    "technology_breakdown",
]
