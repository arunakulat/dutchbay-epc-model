"""Static hybrid-POC aggregation: sum the multi-tech electrical models onto one POC (#880).

This is the D5b plug-in. Where the per-tech plug-ins (D4b wind / D4c solar / D4d BESS)
each characterise ONE resource's converter interface, this module walks the RESOLVED
multi-tech resource list of a hybrid plant and sums every resource's electrical model onto
ONE point-of-connection (POC) bus, producing the two metrics that only exist for the
combined fleet:

(a) COMPOSITE / weighted SCR (WSCR)
-----------------------------------
Every IBR MW connected behind the POC shares the SAME upstream fault level, so the
short-circuit ratio each inverter effectively sees is the POC fault level divided by the
*total* IBR apparent power behind the POC — not by one resource's rating. Adding solar or
BESS behind a wind POC therefore LOWERS the effective SCR for every inverter (more IBR MVA
on the same fault level). This is the load-bearing hybrid rule: a per-tech SCR computed
against a single resource's rating is OPTIMISTIC for a hybrid plant.

A BESS power-conversion-system (PCS) is different from the grid-following generation: it
presents a real (current-limited) sustained fault-current contribution (its manual
``sc_contribution_pu``, per D4d), so it STIFFENS the grid — it enters BOTH the numerator
(a fault-level contribution) and the denominator (IBR MVA). Grid-following wind/solar
inverters ride their current limit and add ≈0 to the fault level (the D4c anti-optimism
rule: solar MUST NOT be credited as a synchronous machine), so they enter the denominator
only.

(b) AGGREGATE ±Q(P) reactive envelope
-------------------------------------
The reactive headroom the fleet can present AT THE POC is the VECTOR SUM of each resource's
±Q capability (taken from its D4b/c/d plug-in — a Type-3 DFIG's partial-load-narrowed
value, a BESS's SoH-degraded value, a solar inverter's pf-capability value) MINUS the
reactive absorbed by the collector network + POC transformer between the resources and the
POC. It is NEVER a single-tech box. The netted at-POC headroom is screened against the
grid-code reactive demand there → a Mvar shortfall (the STATCOM/MSC sizing figure for the
WHOLE hybrid plant) + a PQ-box verdict.

Pure STATIC screening — NO ANDES / EMT
--------------------------------------
This is a steady-state / static aggregation only; it runs NO dynamic (ANDES) study. It
REUSES the D4b/c/d per-tech plug-ins for each resource's contribution rather than
re-deriving converter models. Every result is design-stage ADVISORY (``bankable=False``)
and NEVER feeds the finance engine — committed scenarios stay byte-identical (KPI-neutral).

CASPER / CESSPIT / NO-SPURIOUS-PASS
-----------------------------------
The aggregation MATH is pure Python and imports NO grid library at module-import time (the
per-tech plug-ins it reuses guard ``pandapower`` / ``andes`` at call-time). Every required
input is strict (CESSPIT — no silent defaults): a missing POC voltage / source fault level
/ grid-code pf_range / resource rating RAISES rather than defaulting a value into a
spurious PASS.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence, TypeGuard

from analytics.contracts_v14 import (
    GRID_SCR_STRONG_ABOVE,
    GRID_SCR_WEAK_BELOW,
    PocCapabilityEnvelope,
    ResourceReactiveContribution,
    grid_gfl_gfm_recommendation,
    grid_scr_band,
)
from analytics.grid.capabilities.bess import (
    bess_sc_contribution_pu,
    degrade_bess_rating,
)
from analytics.grid.capabilities.solar import (
    ac_rating_from_dc,
    solar_fault_contribution,
)
from analytics.grid.capabilities.wind import (
    q_capability_mvar_at_p,
    resolve_wind_converter_spec,
)
from analytics.grid.reactive_screen import pf_to_qp_ratio

#: The technology classes this aggregator can dispatch to a per-tech plug-in. Keyed on the
#: shared classifiers (:mod:`finance.tech_types` / the wind/solar/bess plug-ins), so the
#: registry never drifts from the per-tech modules.
_WIND_TECH = "wind"
_SOLAR_TECH = "solar"
_BESS_TECH = "bess"


def _is_number(value: Any) -> TypeGuard[int | float]:
    """True for a real (non-bool) int/float (narrows the type for mypy)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_positive(value: Any, field: str) -> float:
    """Return ``value`` as a positive float or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) <= 0.0:
        raise ValueError(
            f"hybrid POC aggregation requires {field} to be a number > 0, got {value!r}."
        )
    return float(value)


def _resource_tech(resource: Mapping[str, Any]) -> str:
    """Resolve a resource's technology class token from its ``tech`` / ``type`` field.

    Strict (CESSPIT): a resource with no recognised tech token RAISES — the aggregator
    never silently guesses a converter model (which would fabricate a reactive/fault
    contribution the resource may not provide).
    """
    raw = resource.get("tech", resource.get("type"))
    tech = str(raw).strip().lower() if raw is not None else ""
    if tech in (_WIND_TECH, _SOLAR_TECH, _BESS_TECH):
        return tech
    raise ValueError(
        "hybrid POC aggregation requires each resource to declare a recognised tech/type "
        f"(wind | solar | bess) so it dispatches to a per-tech plug-in, got {raw!r}."
    )


def _binding_pf_range(grid: Mapping[str, Any]) -> tuple[float, float, float]:
    """Return (pf_binding_magnitude, pf_min_signed, pf_max_signed) for the POC grid code.

    Prefers ``grid.gridcode.pf_range`` (the D2 structured location); falls back to a
    top-level ``grid.pf_range``. Strict (CESSPIT): an absent/ill-formed range RAISES — the
    aggregate reactive screen never assumes a unity-pf (no reactive) demand.
    """
    gridcode = grid.get("gridcode")
    pf_range = gridcode.get("pf_range") if isinstance(gridcode, Mapping) else None
    if pf_range is None:
        pf_range = grid.get("pf_range")
    if (
        not isinstance(pf_range, Sequence)
        or isinstance(pf_range, (str, bytes))
        or len(pf_range) != 2
        or not all(_is_number(v) for v in pf_range)
    ):
        raise ValueError(
            "hybrid POC aggregation requires a grid-code pf_range [pf_lag, pf_lead] "
            "(grid.gridcode.pf_range or grid.pf_range) — the reactive demand the aggregate "
            "plant must hold at the POC."
        )
    pf_min, pf_max = float(pf_range[0]), float(pf_range[1])
    pf_binding = min(abs(pf_min), abs(pf_max))
    if pf_binding <= 0.0 or pf_binding > 1.0:
        raise ValueError(
            "hybrid POC grid-code pf_range endpoints must have magnitude in (0, 1], "
            f"got {pf_range!r}."
        )
    return pf_binding, pf_min, pf_max


def _iter_resources(grid: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the resolved multi-tech resource blocks behind the POC (strict, >= 1).

    Reads ``grid.resources`` — the list of per-tech resource descriptors resolved for the
    hybrid plant. Strict (CESSPIT): an absent/empty/ill-formed list RAISES; a hybrid POC
    aggregation is meaningless without the resource fleet to sum.
    """
    resources = grid.get("resources")
    if not isinstance(resources, Sequence) or isinstance(resources, (str, bytes)):
        raise ValueError(
            "hybrid POC aggregation requires grid.resources — the list of resolved "
            "multi-tech resource blocks (wind/solar/bess) behind the POC."
        )
    out = [r for r in resources if isinstance(r, Mapping)]
    if not out:
        raise ValueError(
            "hybrid POC aggregation requires at least one resource mapping in "
            "grid.resources; got an empty / non-mapping list."
        )
    return out


def _wind_contribution(
    resource: Mapping[str, Any], *, p_fraction: float
) -> ResourceReactiveContribution:
    """Reactive + fault contribution of one WIND resource, via the D4b plug-in (pure).

    Reuses :func:`analytics.grid.capabilities.wind.resolve_wind_converter_spec` +
    :func:`~analytics.grid.capabilities.wind.q_capability_mvar_at_p` for the topology-aware
    ±Q at the POC active-power reference (a Type-3 DFIG's is NARROWED at partial load; a
    Type-4 full-converter's is the rectangular box). A grid-FOLLOWING wind plant rides its
    current limit, so it contributes ≈0 to the POC fault level (it does not stiffen the
    grid like a synchronous machine).
    """
    spec = resolve_wind_converter_spec(resource)
    p_ref_mw = spec.rated_mva * p_fraction
    q_avail = q_capability_mvar_at_p(spec, p_ref_mw)
    return ResourceReactiveContribution(
        name=str(resource.get("name", _WIND_TECH)),
        tech=_WIND_TECH,
        rated_mva=spec.rated_mva,
        q_available_mvar=q_avail,
        fault_mva_contribution=0.0,
        is_synchronous=False,
    )


def _solar_contribution(
    resource: Mapping[str, Any], *, p_fraction: float
) -> ResourceReactiveContribution:
    """Reactive + fault contribution of one SOLAR resource, via the D4c plug-in (pure).

    Reuses :func:`analytics.grid.capabilities.solar.ac_rating_from_dc` for the AC export
    rating (the reactive base — inverter efficiency NOT re-applied, per D4c) and
    :func:`~analytics.grid.capabilities.solar.solar_fault_contribution` to confirm solar is
    a current-limited, NON-synchronous source. The ±Q headroom is the inverter's
    pf-capability Mvar at the POC active-power reference. A grid-following PV plant adds ≈0
    to the POC fault level (D4c anti-optimism rule: NOT credited as a machine).
    """
    ac_rating_mva = ac_rating_from_dc(
        resource.get("dc_capacity_mw"), resource.get("dc_ac_ratio")
    )
    # Confirm (and document) the current-limited, non-synchronous characterisation; the
    # infeed is credited ~0 to grid strength, so the numerator contribution stays 0.0.
    solar_fault_contribution(ac_rating_mva)

    pf_cap = _solar_pf_capability(resource)
    p_ref_mw = ac_rating_mva * p_fraction
    q_avail = p_ref_mw * pf_to_qp_ratio(pf_cap)
    return ResourceReactiveContribution(
        name=str(resource.get("name", _SOLAR_TECH)),
        tech=_SOLAR_TECH,
        rated_mva=ac_rating_mva,
        q_available_mvar=q_avail,
        fault_mva_contribution=0.0,
        is_synchronous=False,
    )


def _solar_pf_capability(resource: Mapping[str, Any]) -> float:
    """The solar inverter's reactive pf capability magnitude (in (0, 1]).

    Prefers an explicit ``pf_capability`` (the inverter Q-envelope); otherwise the binding
    (tighter) endpoint of the grid-code ``gridcode.pf_range`` — a PV plant is typically
    specified to deliver exactly the code pf. Strict (CESSPIT) when neither is present.
    """
    pf_capability = resource.get("pf_capability")
    if _is_number(pf_capability):
        pf = abs(float(pf_capability))
        if 0.0 < pf <= 1.0:
            return pf
    pf_binding, _, _ = _binding_pf_range(resource)
    return pf_binding


def _bess_contribution(
    resource: Mapping[str, Any], *, reference_year: int | None
) -> ResourceReactiveContribution:
    """Reactive + fault contribution of one BESS resource, via the D4d plug-in (pure).

    Reuses :func:`analytics.grid.capabilities.bess.degrade_bess_rating` for the
    SoH-degraded ± reactive headroom (year-15 shrinks as SoH degrades) and
    :func:`~analytics.grid.capabilities.bess.bess_sc_contribution_pu` for the MANUAL PCS
    short-circuit contribution. Unlike grid-following wind/solar, the BESS PCS presents a
    real (current-limited) fault-current contribution — ``sc_pu × rated_mva_bol`` — that
    STIFFENS the grid (it enters the fault-level numerator), using the BoL rating (the
    converter current limit is a hardware constant that does not degrade with SoH).
    """
    rated = degrade_bess_rating(resource, reference_year=reference_year)
    sc_pu = bess_sc_contribution_pu(resource)
    pcs_sc_mva = sc_pu * rated.rated_mva_bol
    return ResourceReactiveContribution(
        name=str(resource.get("name", _BESS_TECH)),
        tech=_BESS_TECH,
        rated_mva=rated.rated_mva_bol,
        q_available_mvar=rated.q_rated_mvar_soh,
        fault_mva_contribution=pcs_sc_mva,
        is_synchronous=False,
    )


def resource_contribution(
    resource: Mapping[str, Any],
    *,
    p_fraction: float = 1.0,
    reference_year: int | None = None,
) -> ResourceReactiveContribution:
    """Dispatch one resolved resource to its per-tech plug-in for the POC contribution.

    The single dispatch seam: keyed on :func:`_resource_tech`, it routes a wind / solar /
    BESS resource to the D4b / D4c / D4d plug-in and returns the pure-data
    :class:`ResourceReactiveContribution` (rating + ±Q at the POC reference + fault-level
    contribution). Pure Python; no grid library.

    Args:
        resource: one resolved per-tech resource block behind the POC.
        p_fraction: the POC active-power reference as a fraction of each resource's rating
            (the operating point the ±Q headroom is evaluated at; 1.0 = full export, the
            binding reactive case for a pf-limited plant). Clamped to [0, 1].
        reference_year: the BESS SoH evaluation year (``None`` = end-of-life, the binding
            reactive case); ignored by wind/solar.

    Raises:
        ValueError: on an unrecognised tech or any strict per-tech input failure (CESSPIT).
    """
    frac = max(0.0, min(1.0, float(p_fraction)))
    tech = _resource_tech(resource)  # guaranteed one of wind | solar | bess
    if tech == _WIND_TECH:
        return _wind_contribution(resource, p_fraction=frac)
    if tech == _SOLAR_TECH:
        return _solar_contribution(resource, p_fraction=frac)
    # tech == _BESS_TECH (the only remaining recognised token).
    return _bess_contribution(resource, reference_year=reference_year)


def _collector_transformer_q_loss_mvar(
    grid: Mapping[str, Any], gross_q_available_mvar: float
) -> float:
    """Reactive (Mvar) absorbed by the collector network + POC transformer (strict).

    The vector sum of the resources' ±Q is the reactive AT THE RESOURCE TERMINALS; the
    collector cabling + POC transformer between the resources and the POC absorb some of it,
    so the AT-POC headroom is smaller. Resolves the loss from EITHER:

      * an explicit ``grid.collector_transformer_q_loss_mvar`` (an absolute Mvar figure); OR
      * a ``grid.collector_transformer_q_loss_fraction`` (a fraction in [0, 1) of the gross
        reactive) — the screening default form.

    Strict (CESSPIT): a negative absolute loss, or a fraction outside [0, 1), RAISES. When
    NEITHER key is present the loss is 0.0 (an explicit "no netting" — the gross reactive is
    presented at the POC), which is a documented screening choice, not a silent pass: the
    absence is a valid "lossless collector" declaration and the notes disclose it.
    """
    absolute = grid.get("collector_transformer_q_loss_mvar")
    if absolute is not None:
        if not _is_number(absolute) or float(absolute) < 0.0:
            raise ValueError(
                "grid.collector_transformer_q_loss_mvar must be a number >= 0 (Mvar), "
                f"got {absolute!r}."
            )
        return float(absolute)

    fraction = grid.get("collector_transformer_q_loss_fraction")
    if fraction is not None:
        if not _is_number(fraction) or not (0.0 <= float(fraction) < 1.0):
            raise ValueError(
                "grid.collector_transformer_q_loss_fraction must be a number in [0, 1), "
                f"got {fraction!r}."
            )
        return float(fraction) * max(0.0, gross_q_available_mvar)

    return 0.0


def aggregate_poc_capability(
    config: Mapping[str, Any],
    *,
    p_fraction: float = 1.0,
    reference_year: int | None = None,
    scr_weak_below: float = GRID_SCR_WEAK_BELOW,
    scr_strong_above: float = GRID_SCR_STRONG_ABOVE,
    provenance: str | None = None,
) -> PocCapabilityEnvelope:
    """Aggregate the resolved multi-tech resources onto one POC and emit the envelope.

    Walks ``config['grid']['resources']`` (or a bare ``grid`` block), dispatches each
    resource to its D4b/c/d per-tech plug-in (:func:`resource_contribution`), and sums the
    electrical models onto ONE POC bus:

      * COMPOSITE / weighted SCR = (source fault level + Σ resource fault contributions) /
        Σ resource IBR MVA — LOWER than a single-tech SCR because the whole fleet shares
        one fault level; banded exactly like the D1 grid-strength screen.
      * AGGREGATE ±Q at the POC = (Σ resource ±Q headroom) − collector/transformer reactive
        loss, screened against the grid-code reactive demand at the POC active-power
        reference → a Mvar shortfall + PQ-box verdict.

    Args:
        config: the scenario config (or at least its top-level ``grid`` block). Reads
            ``grid.poc_voltage_kv``, ``grid.source_fault_level_mva``, ``grid.resources``,
            the grid-code ``gridcode.pf_range`` / ``pf_range``, and the collector/
            transformer reactive-loss key.
        p_fraction: POC active-power reference fraction (of each resource's rating) the
            reactive headroom + demand are evaluated at (1.0 = full export, the binding
            case). Clamped to [0, 1].
        reference_year: the BESS SoH year (``None`` = end-of-life, the binding case).
        scr_weak_below / scr_strong_above: composite-SCR band thresholds (config-overridable).
        provenance: override the stamped provenance string.

    Returns:
        :class:`PocCapabilityEnvelope` — ADVISORY (``bankable=False``); never feeds the
        finance engine (KPI-neutral).

    Raises:
        ValueError: on an absent ``grid`` block, absent/empty resources, an unrecognised
            resource tech, or any strict per-tech / POC input failure (CESSPIT).
    """
    grid = config.get("grid") if isinstance(config, Mapping) else None
    if not isinstance(grid, Mapping):
        # Allow passing the grid block directly (the resources live under it).
        grid = config if isinstance(config, Mapping) and "resources" in config else None
    if not isinstance(grid, Mapping):
        raise ValueError(
            "aggregate_poc_capability requires a 'grid' block (or a grid-shaped mapping "
            "with a 'resources' list) — the hybrid POC and its resource fleet."
        )

    poc_kv = _require_positive(grid.get("poc_voltage_kv"), "grid.poc_voltage_kv")
    source_fault_mva = _require_positive(
        grid.get("source_fault_level_mva"), "grid.source_fault_level_mva"
    )
    pf_binding, pf_min, pf_max = _binding_pf_range(grid)
    frac = max(0.0, min(1.0, float(p_fraction)))

    contributions: list[ResourceReactiveContribution] = []
    for resource in _iter_resources(grid):
        contributions.append(
            resource_contribution(
                resource, p_fraction=frac, reference_year=reference_year
            )
        )

    total_ibr_mva = sum(c.rated_mva for c in contributions)
    if total_ibr_mva <= 0.0:
        raise ValueError(
            "hybrid POC aggregation total IBR MVA must be > 0 (the composite-SCR "
            f"denominator); got {total_ibr_mva!r} — check the resource ratings."
        )
    resource_fault_mva = sum(c.fault_mva_contribution for c in contributions)
    aggregate_fault_level_mva = source_fault_mva + resource_fault_mva
    composite_scr = aggregate_fault_level_mva / total_ibr_mva
    band = grid_scr_band(
        composite_scr, weak_below=scr_weak_below, strong_above=scr_strong_above
    )

    gross_q_available = sum(c.q_available_mvar for c in contributions)
    q_loss = _collector_transformer_q_loss_mvar(grid, gross_q_available)
    aggregate_q_available = max(0.0, gross_q_available - q_loss)

    # The aggregate reactive DEMAND at the POC is |Q| = P·tan(acos(pf_binding)) at the POC
    # active-power reference. The reference active power is the fleet's combined MW at the
    # operating fraction (Σ resource rating · fraction), the binding demand corner.
    reference_p_mw = total_ibr_mva * frac
    aggregate_q_required = abs(reference_p_mw) * pf_to_qp_ratio(pf_binding)
    aggregate_q_shortfall = max(0.0, aggregate_q_required - aggregate_q_available)

    tech_counts = _tech_summary(contributions)
    return PocCapabilityEnvelope(
        contributions=tuple(contributions),
        total_ibr_mva=total_ibr_mva,
        source_fault_level_mva=source_fault_mva,
        aggregate_fault_level_mva=aggregate_fault_level_mva,
        composite_scr=composite_scr,
        scr_band=band,
        gfl_gfm_recommendation=grid_gfl_gfm_recommendation(band),
        gross_q_available_mvar=gross_q_available,
        collector_transformer_q_loss_mvar=q_loss,
        aggregate_q_available_mvar=aggregate_q_available,
        aggregate_q_required_mvar=aggregate_q_required,
        aggregate_q_shortfall_mvar=aggregate_q_shortfall,
        inside_pq_box=aggregate_q_shortfall <= 0.0,
        reference_p_mw=reference_p_mw,
        pf_required_min=pf_min,
        pf_required_max=pf_max,
        n_resources=len(contributions),
        method="static_poc_aggregation",
        bankable=False,
        provenance=provenance if provenance is not None else _default_provenance(),
        notes=(
            f"Static hybrid-POC aggregation at {poc_kv:g} kV over {len(contributions)} "
            f"resource(s) [{tech_counts}]: composite/weighted SCR "
            f"{composite_scr:.3f} ({band}) = fault {aggregate_fault_level_mva:.1f} MVA "
            f"(source {source_fault_mva:.1f} + PCS {resource_fault_mva:.1f}) / total IBR "
            f"{total_ibr_mva:.1f} MVA — adding IBR behind the POC LOWERS the SCR every "
            f"inverter sees. Aggregate ±Q at POC {aggregate_q_available:.3f} Mvar (gross "
            f"{gross_q_available:.3f} − collector/tx {q_loss:.3f}) vs demand "
            f"{aggregate_q_required:.3f} Mvar → shortfall {aggregate_q_shortfall:.3f} Mvar "
            "(STATCOM/MSC sizing for the whole plant). STATIC screen (no ANDES/EMT) — "
            "confirm the POC + PQ requirement with the utility base case."
        ),
    )


def _tech_summary(contributions: Sequence[ResourceReactiveContribution]) -> str:
    """Compact ``wind×2, solar×1, bess×1`` tech-count string for the notes."""
    counts: dict[str, int] = {}
    for c in contributions:
        counts[c.tech] = counts.get(c.tech, 0) + 1
    return ", ".join(f"{tech}×{n}" for tech, n in sorted(counts.items()))


def _default_provenance() -> str:
    """The default provenance string (the contract's canonical POC-aggregation provenance)."""
    from analytics.contracts_v14 import _POC_AGGREGATION_PROVENANCE

    return _POC_AGGREGATION_PROVENANCE


__all__ = [
    "resource_contribution",
    "aggregate_poc_capability",
]
