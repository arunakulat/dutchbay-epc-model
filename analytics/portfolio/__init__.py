"""Portfolio-level multi-technology generation aggregation.

Builds the multi-tech generation contracts (``GenerationProfile`` /
``MultiTechGenerationResult`` / ``TechnologyBreakdown`` from
``analytics.contracts_v14``) from a real finance run. Supports wind + solar
(declared via a ``generation.technologies`` block); the run's combined CFADS is
split across technologies in proportion to AEP. Storage slots in next.

Also exposes the per-technology tornado sensitivity (``multi_tech_tornado``,
Epic 6.1): which technology drives the hybrid's IRR / covenant volatility.
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
from analytics.portfolio.multi_tech_tornado import (
    DEFAULT_DRIVERS,
    DEFAULT_METRICS,
    DEFAULT_SHOCK_PCT,
    MultiTechTornadoBar,
    applicable_drivers,
    build_coupled_override,
    discover_generation_technologies,
    discover_non_generation_technologies,
    discover_storage_technologies,
    flat_metrics,
    impact_by_technology,
    run_multi_tech_tornado,
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
    # Epic 6.1 — per-technology tornado
    "DEFAULT_DRIVERS",
    "DEFAULT_METRICS",
    "DEFAULT_SHOCK_PCT",
    "MultiTechTornadoBar",
    "applicable_drivers",
    "build_coupled_override",
    "discover_generation_technologies",
    "discover_non_generation_technologies",
    "discover_storage_technologies",
    "flat_metrics",
    "impact_by_technology",
    "run_multi_tech_tornado",
]
