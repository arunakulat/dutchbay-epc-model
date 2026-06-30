"""Build multi-technology generation views from a finance run (Dolphin).

Turns the **real** outputs of a v14 run — the run KPIs (CFADS) and the scenario's
declared per-technology AEP — into the multi-tech generation contracts in
``analytics.contracts_v14`` (``GenerationProfile`` / ``MultiTechGenerationResult`` /
``TechnologyBreakdown``). It re-uses those contracts and performs **no finance
recomputation**: it is an additive output slice that cannot perturb the economics.

Per-technology AEP is read from a ``generation.technologies.<tech>`` block
(preferred) or the legacy ``resource.<tech>``. The run's combined operational CFADS
is apportioned across technologies by **operating margin** (revenue minus opex;
ARCH-2, #488) when a hybrid's per-tech tariffs and opex resolve, else **in proportion
to AEP** (the prior indicative basis, kept byte-identical for single-tech and
under-specified scenarios). Either way it is an exact partition of the run's actual
(tax-netted) CFADS — tax is project-level, not per-tech — so this stays an additive
output slice that cannot perturb the committed economics. Wind-only collapses to a
100% wind share (identical to the prior behaviour).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from analytics.contracts_v14 import (
    GenerationProfile,
    MultiTechGenerationResult,
    TechnologyBreakdown,
)
from finance.tech_types import GENERATION_TYPES

#: GWh → kWh (the contracts carry AEP in kWh).
GWH_TO_KWH = 1_000_000.0

#: Generation technologies recognised in the LEGACY single-tech fallback (scenarios with
#: no ``generation.technologies`` block), in a conventional display order. DERIVED from
#: finance.tech_types.GENERATION_TYPES (the single source of truth) so the two cannot drift
#: and a new generation type (e.g. tidal) is included automatically — the old hardcoded
#: ("wind", "solar") silently dropped any third generation technology. Storage (BESS) is
#: excluded; it earns a capacity charge, not generation revenue.
_DISPLAY_ORDER: Tuple[str, ...] = (
    "wind",
    "solar",
    "tidal",
    "hydro",
    "run_of_river",
    "geothermal",
)
SUPPORTED_TECHNOLOGIES: Tuple[str, ...] = tuple(
    t for t in _DISPLAY_ORDER if t in GENERATION_TYPES
) + tuple(sorted(GENERATION_TYPES.difference(_DISPLAY_ORDER)))


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
    # The top-level `aep_summary.net_aep_p50_gwh` is the WIND plant's bankable AEP artifact
    # (tests/mocks/aep_summary_*.json), so it is attributed to wind only — this is a data
    # attribution, NOT a class gate (tech CLASS is type-driven via finance.tech_types, so
    # tidal/solar/… aggregate on their own footing via their declared aep_gwh). A non-wind
    # single-tech plant carries its AEP in resource.<tech>.aep_gwh (the candidate above).
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
    return build_tech_generation_profile("wind", aep_kwh, _run_cfads_usd(kpis), config)


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


#: Project-level tariff paths (LKR/kWh). These mirror the *LKR/kWh* keys of
#: ``finance.cashflow_v14_params._resolve_tariff_lkr_per_kwh``, read here as plain config
#: data (no finance import). The engine's resolver additionally accepts USD-denominated
#: tariffs and a bare ``tariff:`` scalar; those forms are deliberately NOT mirrored — a
#: scenario billed on a USD tariff (or with no LKR/kWh tariff key) simply falls back to the
#: AEP split, which degrades safely (it never invents revenue).
_PROJECT_TARIFF_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("tariff", "lkr_per_kwh"),
    ("tariff", "lkr_kwh"),
    ("tariff", "tariff_lkr_per_kwh"),
    ("revenue", "tariff_lkr_per_kwh"),
    ("revenue", "tariff_lkr_kwh"),
    ("tariff_lkr_per_kwh",),
    ("tariff_lkr",),
)


def _resolve_project_tariff_lkr_per_kwh(config: Mapping[str, Any]) -> Optional[float]:
    """Project generation tariff (LKR/kWh), config-first; ``None`` if absent."""
    for path in _PROJECT_TARIFF_PATHS:
        value = _nested_get(config, *path)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _resolve_fx_start_lkr_per_usd(config: Mapping[str, Any]) -> Optional[float]:
    """Year-1 representative FX (LKR/USD) from ``fx.start_lkr_per_usd``; ``None`` if absent."""
    value = _nested_get(config, "fx", "start_lkr_per_usd")
    if value is None:
        return None
    try:
        fx = float(value)
    except (TypeError, ValueError):
        return None
    return fx if fx > 0 else None


def _operating_margin_weights(
    aeps: Mapping[str, float], config: Mapping[str, Any]
) -> Optional[Dict[str, float]]:
    """Per-technology operating-margin weights (ARCH-2, #488) — or ``None`` to fall back.

    Weights each technology by its operating margin ``revenue - opex`` rather than by raw
    AEP, so a technology with a different opex intensity gets a correct CFADS share. Two
    deliberate choices keep this honest and consistent with the finance engine:

    * **Revenue uses the single PROJECT tariff** (``net AEP x project_tariff / FX``), not a
      per-tech tariff. The engine bills one blended generation tariff and never reads a
      per-tech tariff, so apportioning by a per-tech tariff would attribute revenue the run
      never earned. The legitimate per-tech differentiator here is therefore opex (and AEP).
    * **OPEX** is read via :func:`analytics.portfolio.tech_wbs.resolve_tech_opex_usd` (the
      ARCH-3 single source of truth) — no full work-breakdown build, and no over-attribution
      raise, so this helper never breaks the aggregator's opportunistic ``(None, None)``
      contract.

    The result still partitions the run's *actual* tax-netted CFADS exactly (tax is
    project-level, not per-tech, so it stays inside the partitioned total). For a flat-tariff
    hybrid with no per-tech opex it reduces algebraically to the AEP split (byte-identical).

    Returns ``None`` (caller keeps the AEP split) unless there are 2+ technologies, FX and a
    project tariff resolve, and every per-tech margin is non-negative with a positive sum — a
    negative per-tech margin would produce a negative / >100% share, which the AEP fallback
    can never do.
    """
    if len(aeps) < 2:
        return None
    fx_start = _resolve_fx_start_lkr_per_usd(config)
    tariff = _resolve_project_tariff_lkr_per_kwh(config)
    if fx_start is None or tariff is None:
        return None

    from analytics.portfolio.tech_wbs import resolve_tech_opex_usd

    margins: Dict[str, float] = {}
    for tech, aep_kwh in aeps.items():
        revenue_usd = aep_kwh * tariff / fx_start
        margin = revenue_usd - (resolve_tech_opex_usd(config, tech) or 0.0)
        if not math.isfinite(margin) or margin < 0:
            return (
                None  # negative/non-finite margin -> AEP fallback (never goes negative)
            )
        margins[tech] = margin

    total = sum(margins.values())
    if total <= 0:
        return None
    return {tech: margin / total for tech, margin in margins.items()}


def build_multi_tech_from_run(
    kpis: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Tuple[Optional[MultiTechGenerationResult], Optional[List[TechnologyBreakdown]]]:
    """Build the multi-tech generation view from a finance run.

    Collects every supported technology with a declared AEP and apportions the run's
    combined operational CFADS across them, returning the aggregate plus the per-tech
    breakdown. The split is by **operating margin** (revenue - opex; ARCH-2, #488) when a
    hybrid's per-tech tariffs/opex resolve, else **in proportion to AEP** (the prior
    indicative basis, kept byte-identical for single-tech and under-specified scenarios).
    Either way the per-tech CFADS sums to the run's actual (tax-netted) combined CFADS — an
    exact partition, not a re-derivation, so this stays KPI-neutral for committed economics.
    Wind-only yields a single 100%-wind technology. Returns ``(None, None)`` when no
    technology AEP is resolvable, so callers can attach the view opportunistically without
    breaking runs that lack it.
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
    # ARCH-2 (#488): apportion by operating margin when resolvable, else by AEP.
    margin_weights = _operating_margin_weights(aeps, config)
    profiles: List[GenerationProfile] = []
    for tech, aep in aeps.items():
        if margin_weights is not None:
            cfads_alloc = run_cfads * margin_weights[tech]
        else:
            cfads_alloc = run_cfads * (aep / total_aep) if total_aep else 0.0
        profiles.append(build_tech_generation_profile(tech, aep, cfads_alloc, config))

    result = aggregate_generation(profiles)
    capex_by_tech = {
        tech: capex
        for tech in aeps
        if (capex := _tech_capex_usd(config, tech)) is not None
    } or None
    return result, technology_breakdown(result, capex_by_tech=capex_by_tech)
