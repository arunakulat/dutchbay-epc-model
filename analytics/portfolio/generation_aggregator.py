"""Build multi-technology generation views from a finance run (Dolphin).

Turns the **real** outputs of a v14 run — the run KPIs (CFADS) and the scenario's
resolved AEP — into the multi-tech generation contracts defined in
``analytics.contracts_v14`` (``GenerationProfile``, ``MultiTechGenerationResult``,
``TechnologyBreakdown``). It re-uses those contracts rather than inventing new ones,
and performs **no finance recomputation**: every value is read from the run/config,
so it cannot perturb the economics (it is an additive output slice).

Wind-only today; a solar/BESS ``GenerationProfile`` slots into the same
``aggregate_generation`` call as the multi-tech build lands. This is the producer
that de-orphans the previously never-fed multi-tech contracts.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Tuple

from analytics.contracts_v14 import (
    GenerationProfile,
    MultiTechGenerationResult,
    TechnologyBreakdown,
)

#: GWh → kWh (the contracts carry AEP in kWh).
GWH_TO_KWH = 1_000_000.0


def _nested_get(config: Mapping[str, Any], *path: str) -> Any:
    """Walk a nested mapping by ``path``; return ``None`` on any miss."""
    cur: Any = config
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def resolve_wind_aep_kwh(config: Mapping[str, Any]) -> Optional[float]:
    """Resolve the run's net P50 wind AEP (kWh) from the scenario config.

    Tries the canonical ``resource.wind.aep_gwh`` then ``aep_summary
    .net_aep_p50_gwh``. Returns ``None`` if neither is present (the caller then
    skips the generation view rather than fabricating a number).
    """
    for path in (("resource", "wind", "aep_gwh"), ("aep_summary", "net_aep_p50_gwh")):
        value = _nested_get(config, *path)
        if value is not None:
            return float(value) * GWH_TO_KWH
    return None


def build_wind_generation_profile(
    kpis: Mapping[str, Any], config: Mapping[str, Any]
) -> Optional[GenerationProfile]:
    """Build the wind ``GenerationProfile`` from a run's KPIs + scenario config.

    AEP comes from the scenario (the frozen P50 the finance run used); the
    representative annual CFADS comes from the run KPIs
    (``mean_operational_cfads_usd``, falling back to ``final_cfads_usd``).
    Returns ``None`` if the AEP cannot be resolved.
    """
    aep_kwh = resolve_wind_aep_kwh(config)
    if aep_kwh is None:
        return None
    cfads = kpis.get("mean_operational_cfads_usd")
    if cfads is None:
        cfads = kpis.get("final_cfads_usd", 0.0)
    availability = _nested_get(config, "resource", "wind", "availability_pct")
    return GenerationProfile(
        technology="wind",
        annual_aep_kwh=aep_kwh,
        annual_cfads_usd=float(cfads),
        availability_pct=float(availability) if availability is not None else None,
        losses_breakdown=None,
    )


def aggregate_generation(
    profiles: Sequence[GenerationProfile],
) -> MultiTechGenerationResult:
    """Aggregate per-technology profiles into a portfolio generation result.

    Raises:
        ValueError: ``profiles`` is empty.
    """
    if not profiles:
        raise ValueError("aggregate_generation requires at least one profile")
    return MultiTechGenerationResult(
        total_aep_kwh=sum(p.annual_aep_kwh for p in profiles),
        total_cfads_usd=sum(p.annual_cfads_usd for p in profiles),
        technologies={p.technology: p for p in profiles},
    )


def technology_breakdown(
    result: MultiTechGenerationResult,
    *,
    capex_by_tech: Optional[Mapping[str, float]] = None,
) -> List[TechnologyBreakdown]:
    """Per-technology AEP/CFADS (and optional CAPEX) shares for lender visibility."""
    total_aep = result.total_aep_kwh
    total_cfads = result.total_cfads_usd
    total_capex = sum(capex_by_tech.values()) if capex_by_tech else None
    rows: List[TechnologyBreakdown] = []
    for tech, profile in result.technologies.items():
        share_capex = None
        if capex_by_tech and tech in capex_by_tech and total_capex:
            share_capex = 100.0 * capex_by_tech[tech] / total_capex
        rows.append(
            TechnologyBreakdown(
                technology=tech,
                share_of_aep_pct=(
                    100.0 * profile.annual_aep_kwh / total_aep if total_aep else None
                ),
                share_of_cfads_pct=(
                    100.0 * profile.annual_cfads_usd / total_cfads
                    if total_cfads
                    else None
                ),
                share_of_capex_pct=share_capex,
            )
        )
    return rows


def build_multi_tech_from_run(
    kpis: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    capex_by_tech: Optional[Mapping[str, float]] = None,
) -> Tuple[Optional[MultiTechGenerationResult], Optional[List[TechnologyBreakdown]]]:
    """Build the (wind-only) multi-tech generation view from a finance run.

    Returns ``(None, None)`` when the AEP cannot be resolved, so callers can
    attach the view opportunistically without breaking runs that lack it.
    """
    wind = build_wind_generation_profile(kpis, config)
    if wind is None:
        return None, None
    result = aggregate_generation([wind])
    return result, technology_breakdown(result, capex_by_tech=capex_by_tech)
