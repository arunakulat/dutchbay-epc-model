"""Portfolio-level multi-technology generation aggregation.

Builds the multi-tech generation contracts (``GenerationProfile`` /
``MultiTechGenerationResult`` / ``TechnologyBreakdown`` from
``analytics.contracts_v14``) from a real finance run. Supports wind + solar
(declared via a ``generation.technologies`` block); the run's combined CFADS is
split across technologies in proportion to AEP. Storage slots in next.
"""

from __future__ import annotations

from analytics.portfolio.generation_aggregator import (
    SUPPORTED_TECHNOLOGIES,
    aggregate_generation,
    build_multi_tech_from_run,
    build_tech_generation_profile,
    build_wind_generation_profile,
    resolve_tech_aep_kwh,
    resolve_wind_aep_kwh,
    technology_breakdown,
)

__all__ = [
    "SUPPORTED_TECHNOLOGIES",
    "aggregate_generation",
    "build_multi_tech_from_run",
    "build_tech_generation_profile",
    "build_wind_generation_profile",
    "resolve_tech_aep_kwh",
    "resolve_wind_aep_kwh",
    "technology_breakdown",
]
