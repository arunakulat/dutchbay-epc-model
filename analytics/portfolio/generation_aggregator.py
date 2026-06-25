"""Build multi-technology generation views from a finance run (Dolphin).

Turns the **real** outputs of a v14 run — the run KPIs (CFADS) and the scenario's
declared per-technology AEP — into the multi-tech generation contracts in
``analytics.contracts_v14`` (``GenerationProfile`` / ``MultiTechGenerationResult`` /
``TechnologyBreakdown``). It re-uses those contracts and performs **no finance
recomputation**: it is an additive output slice that cannot perturb the economics.

Per-technology AEP is read from a ``generation.technologies.<tech>`` block
(preferred) or the legacy ``resource.<tech>``. The run's combined operational CFADS
is split across technologies **in proportion to their AEP** — an *indicative*
allocation of one combined-plant run, clearly distinct from true per-tech project
finance (separate solar CAPEX/OPEX/degradation through the cashflow), which is a
later step. Wind-only collapses to a 100% wind share (identical to the prior
behaviour).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from analytics.contracts_v14 import (
    GenerationProfile,
    MultiTechGenerationResult,
    TechnologyBreakdown,
)

#: GWh → kWh (the contracts carry AEP in kWh).
GWH_TO_KWH = 1_000_000.0

#: Technologies recognised, in display order. BESS/storage slots in later.
SUPPORTED_TECHNOLOGIES: Tuple[str, ...] = ("wind", "solar")


def _nested_get(config: Mapping[str, Any], *path: str) -> Any:
    """Walk a nested mapping by ``path``; return ``None`` on any miss."""
    cur: Any = config
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def resolve_tech_aep_kwh(config: Mapping[str, Any], tech: str) -> Optional[float]:
    """Resolve a technology's net P50 AEP (kWh) from the scenario config.

    Looks at ``generation.technologies.<tech>.aep_gwh`` first, then the legacy
    ``resource.<tech>.aep_gwh``, then (wind only) ``aep_summary.net_aep_p50_gwh``.
    Returns ``None`` if none is present.
    """
    candidates = [
        ("generation", "technologies", tech, "aep_gwh"),
        ("resource", tech, "aep_gwh"),
    ]
    if tech == "wind":
        candidates.append(("aep_summary", "net_aep_p50_gwh"))
    for path in candidates:
        value = _nested_get(config, *path)
        if value is not None:
            return float(value) * GWH_TO_KWH
    return None


def resolve_wind_aep_kwh(config: Mapping[str, Any]) -> Optional[float]:
    """Back-compat alias: the wind AEP (kWh). See :func:`resolve_tech_aep_kwh`."""
    return resolve_tech_aep_kwh(config, "wind")


def _tech_availability(config: Mapping[str, Any], tech: str) -> Optional[float]:
    for path in (
        ("generation", "technologies", tech, "availability_pct"),
        ("resource", tech, "availability_pct"),
    ):
        value = _nested_get(config, *path)
        if value is not None:
            return float(value)
    return None


def _tech_capex_usd(config: Mapping[str, Any], tech: str) -> Optional[float]:
    value = _nested_get(config, "generation", "technologies", tech, "capex_usd")
    return float(value) if value is not None else None


def _run_cfads_usd(kpis: Mapping[str, Any]) -> float:
    """Representative annual operational CFADS from the run KPIs."""
    cfads = kpis.get("mean_operational_cfads_usd")
    if cfads is None:
        cfads = kpis.get("final_cfads_usd", 0.0)
    return float(cfads)


def build_tech_generation_profile(
    tech: str,
    aep_kwh: float,
    cfads_usd: float,
    config: Mapping[str, Any],
) -> GenerationProfile:
    """Assemble one technology's :class:`GenerationProfile`."""
    availability = _tech_availability(config, tech)
    return GenerationProfile(
        technology=tech,
        annual_aep_kwh=aep_kwh,
        annual_cfads_usd=cfads_usd,
        availability_pct=availability,
        losses_breakdown=None,
    )


def build_wind_generation_profile(
    kpis: Mapping[str, Any], config: Mapping[str, Any]
) -> Optional[GenerationProfile]:
    """Back-compat: the wind profile carrying the run's full operational CFADS.

    Returns ``None`` if the wind AEP cannot be resolved.
    """
    aep_kwh = resolve_tech_aep_kwh(config, "wind")
    if aep_kwh is None:
        return None
    return build_tech_generation_profile(
        "wind", aep_kwh, _run_cfads_usd(kpis), config
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
) -> Tuple[Optional[MultiTechGenerationResult], Optional[List[TechnologyBreakdown]]]:
    """Build the multi-tech generation view from a finance run.

    Collects every supported technology with a declared AEP, splits the run's
    combined operational CFADS across them **in proportion to AEP** (indicative
    allocation of one combined run), and returns the aggregate plus the per-tech
    breakdown. Wind-only yields a single 100%-wind technology. Returns
    ``(None, None)`` when no technology AEP is resolvable, so callers can attach
    the view opportunistically without breaking runs that lack it.
    """
    # Discover generation technologies tech-agnostically from the generation.technologies
    # block (wind == solar == tidal == …; storage/BESS excluded) so a third tech is NOT
    # silently dropped from the lender AEP/CFADS/capex split — the hardcoded
    # SUPPORTED_TECHNOLOGIES gate did exactly that. Legacy single-tech scenarios carry no
    # such block; fall back to the conventional generation techs resolved from resource.<tech>
    # (this keeps the canonical wind-only run byte-identical). Reuses the same discovery the
    # cashflow and the multi-tech tornado use, so the three cannot disagree (CCCDIR).
    from analytics.portfolio.multi_tech_tornado import discover_generation_technologies

    techs = discover_generation_technologies(config) or list(SUPPORTED_TECHNOLOGIES)
    aeps: Dict[str, float] = {}
    for tech in techs:
        aep = resolve_tech_aep_kwh(config, tech)
        if aep is not None:
            aeps[tech] = aep
    if not aeps:
        return None, None

    total_aep = sum(aeps.values())
    run_cfads = _run_cfads_usd(kpis)
    profiles: List[GenerationProfile] = []
    for tech, aep in aeps.items():
        cfads_alloc = run_cfads * (aep / total_aep) if total_aep else 0.0
        profiles.append(
            build_tech_generation_profile(tech, aep, cfads_alloc, config)
        )

    result = aggregate_generation(profiles)
    capex_by_tech = {
        tech: capex
        for tech in aeps
        if (capex := _tech_capex_usd(config, tech)) is not None
    } or None
    return result, technology_breakdown(result, capex_by_tech=capex_by_tech)
