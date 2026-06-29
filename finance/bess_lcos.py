"""Levelised Cost of Storage (LCOS) for a BESS — a READ-ONLY reporting view.

LCOS answers "what does one MWh discharged from this battery cost, all-in, over its
life?" and is the storage analogue of LCOE. It is computed as::

    LCOS [USD/MWh] = PV(lifetime costs) / PV(lifetime discharged energy)

with both numerator and denominator discounted at the **project WACC** — the same rate
the cashflow uses, reused here rather than introducing a second discount rate (CCCDIR:
one rate, supplied by the caller because ``wacc.mode: build_up`` resolves it in-pipeline
from sized debt, not from config alone).

This module is strictly **read-only / off the cashflow path**: it never feeds CFADS,
IRR, DSCR, or any committed KPI. It imports the degradation curve
(:func:`finance.bess_revenue.mdsc_soh_for_year`) and the NPV primitive
(:func:`finance.irr.npv`) so there is a single source of truth for both; it does not
re-derive either. Because it touches nothing on the cashflow, adding it is KPI-neutral.

Costs (all USD, discounted at WACC over the asset's operating horizon)::

    PV(costs) = capex_usd                      (initial, at t=0)
              + Σ_t opex_usd(t) / (1+w)^t       (fixed O&M, optionally escalating)
              + Σ_e augmentation_capex_usd_e / (1+w)^year_e   (mid-life cell top-ups)
              − salvage_usd / (1+w)^horizon     (end-of-life residual, default 0)

Discharged energy (MWh, discounted at WACC), per operating year ``t`` (1-based)::

    discharged_mwh(t) = energy_per_cycle_mwh × cycles_per_year × depth_of_discharge
                        × round_trip_efficiency × soh(t)

where ``energy_per_cycle_mwh`` is the nameplate energy (``energy_mwh``, or
``power_mw × duration_h`` when only the power/duration rating is given) and ``soh(t)`` is
the year-indexed state-of-health from :func:`finance.bess_revenue.mdsc_soh_for_year` (so
the LCOS energy declines with the same MDSC fade / augmentation curve the revenue uses).

LIMITATIONS (stated for lender DD, DOC-03):

* The discharged energy of a **capacity-charge** (availability-tolling) BESS depends on
  CEB dispatch, which the engine does not simulate. Its LCOS therefore assumes a fixed
  ``cycles_per_year`` at ``depth_of_discharge`` — an explicit, overridable assumption,
  not a simulated dispatch. The result carries a note recording this.
* **Opex attribution** is clean only for a standalone BESS, where the project's
  ``opex.usd_per_year`` is wholly the battery's. On a hybrid (wind/solar + BESS) the
  project opex is shared, so it is NOT attributed to the BESS unless the BESS block
  declares its own ``revenue.opex_usd_per_year``; absent that, opex is excluded and the
  LCOS (which then understates true cost) carries a note.
* Augmentation capex is taken at face USD value; its depreciation tax shield is not
  credited here (consistent with the cashflow's lender-prudent treatment).

Every config key this module reads beyond the revenue spec is optional with an
identity/neutral default, so resolving LCOS never changes the resolved revenue spec or
the cashflow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .bess_revenue import mdsc_soh_for_year, resolve_bess_specs
from .irr import npv
from .tech_types import is_generation_type

#: Default depth-of-discharge by revenue model. A capacity-charge (availability) BESS is
#: dispatched deep on call (0.80); an energy-tariff night-peak BESS does a shallower
#: partial daily shift of its pack (0.40). Both are overridable per scenario via
#: ``revenue.depth_of_discharge``.
_DEFAULT_DOD_CAPACITY_CHARGE = 0.80
_DEFAULT_DOD_ENERGY_TARIFF = 0.40
#: Default cycles/year for the LCOS energy basis (one charge/discharge per day). Mirrors
#: :data:`finance.bess_revenue._DEFAULT_CYCLES_PER_YEAR`; overridable via
#: ``revenue.cycles_per_year``.
_DEFAULT_CYCLES_PER_YEAR = 365.0
#: Default AC-AC round-trip efficiency (mirrors
#: :data:`finance.bess_revenue._DEFAULT_ROUND_TRIP_EFFICIENCY`); overridable via
#: ``revenue.round_trip_efficiency``.
_DEFAULT_ROUND_TRIP_EFFICIENCY = 0.90


def _nested_get(config: Mapping[str, Any], *path: str) -> Any:
    """Walk a nested mapping by ``path``; return ``None`` on any miss."""
    cur: Any = config
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def _as_float(value: Any) -> Optional[float]:
    """Coerce a config scalar to a finite ``float``; ``None`` otherwise.

    Bools, ``None``, non-numerics, and non-finite values (NaN / ±inf) return ``None`` so
    they trip the callers' fail-loud guards rather than poisoning a present value.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        coerced = float(value)
        return coerced if math.isfinite(coerced) else None
    return None


def _ratio(value: Any, *, tech: str, field: str, default: float) -> float:
    """Validate an optional ratio in ``[0, 1]``; return ``default`` when absent.

    A value outside ``[0, 1]`` (e.g. ``80`` for ``0.80``) is a config error and **raises**
    (CESSPIT fail-loud), symmetric with the BESS revenue module's derate guards.
    """
    if value is None:
        return default
    coerced = _as_float(value)
    if coerced is None or not 0.0 <= coerced <= 1.0:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{field}={value!r} must be a "
            "ratio in [0, 1] (e.g. 0.80, not 80)."
        )
    return coerced


def _non_negative(value: Any, *, tech: str, field: str, default: float) -> float:
    """Validate an optional non-negative USD/amount; return ``default`` when absent.

    A negative or non-finite value **raises** (CESSPIT fail-loud).
    """
    if value is None:
        return default
    coerced = _as_float(value)
    if coerced is None or coerced < 0.0:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{field}={value!r} must be a "
            "non-negative number."
        )
    return coerced


def _positive(value: Any, *, tech: str, field: str, default: float) -> float:
    """Validate an optional strictly-positive number; return ``default`` when absent."""
    if value is None:
        return default
    coerced = _as_float(value)
    if coerced is None or coerced <= 0.0:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{field}={value!r} must be a "
            "positive number."
        )
    return coerced


@dataclass(frozen=True)
class LcosSpec:
    """Fully-resolved cost and energy inputs for one BESS's LCOS (read-only).

    Built by :func:`resolve_lcos_specs` from the revenue spec plus the BESS block's
    reporting fields and the project cost blocks. Carries everything
    :func:`compute_lcos` needs, so the compute is a pure function of this spec, the WACC,
    and the horizon.
    """

    technology: str
    revenue_model: str
    energy_per_cycle_mwh: float
    cycles_per_year: float
    round_trip_efficiency: float
    depth_of_discharge: float
    capex_usd: float
    opex_usd_per_year: float
    opex_escalation_pct: float
    salvage_usd: float
    contract_years: Optional[int]
    soh_fade_pct_annual: float
    soh_floor: float
    #: Mid-life cell top-ups: ``{year, capex_usd, restore_to_soh}`` (1-based year).
    augmentation_events: Tuple[Dict[str, Any], ...]
    #: Resolution-time limitations (e.g. opex/capex excluded on a hybrid).
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class LcosResult:
    """The computed LCOS and its present-value build-up for one BESS (read-only).

    ``lcos_usd_per_mwh`` is ``None`` when the present value of discharged energy is zero
    (e.g. a zero depth-of-discharge), in which case the metric is undefined rather than
    silently zero. All ``pv_*`` figures are USD present values at ``wacc`` except
    ``pv_discharged_mwh`` (discounted MWh), so ``lcos = pv_costs_usd / pv_discharged_mwh``.
    """

    technology: str
    revenue_model: str
    lcos_usd_per_mwh: Optional[float]
    pv_costs_usd: float
    pv_discharged_mwh: float
    pv_capex_usd: float
    pv_opex_usd: float
    pv_augmentation_usd: float
    pv_salvage_usd: float
    wacc: float
    horizon_years: int
    depth_of_discharge: float
    round_trip_efficiency: float
    cycles_per_year: float
    notes: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dict of the result (for report packs / CLIs)."""
        return {
            "technology": self.technology,
            "revenue_model": self.revenue_model,
            "lcos_usd_per_mwh": self.lcos_usd_per_mwh,
            "pv_costs_usd": self.pv_costs_usd,
            "pv_discharged_mwh": self.pv_discharged_mwh,
            "pv_capex_usd": self.pv_capex_usd,
            "pv_opex_usd": self.pv_opex_usd,
            "pv_augmentation_usd": self.pv_augmentation_usd,
            "pv_salvage_usd": self.pv_salvage_usd,
            "wacc": self.wacc,
            "horizon_years": self.horizon_years,
            "depth_of_discharge": self.depth_of_discharge,
            "round_trip_efficiency": self.round_trip_efficiency,
            "cycles_per_year": self.cycles_per_year,
            "notes": list(self.notes),
        }


def _has_generation(config: Mapping[str, Any]) -> bool:
    """True iff the scenario has any generation (non-storage) technology.

    A block is generation when its ``type`` is a recognised generation type, or — for
    pre-enum scenarios that omit ``type`` — when it declares a ``capacity_factor`` (the
    generation key-sniff that mirrors :mod:`finance.tech_types`). Used to decide whether a
    BESS is standalone (so the project ``opex``/``capex`` are wholly the battery's). Only
    reached with a populated ``generation.technologies`` (a BESS implies one).
    """
    techs = _nested_get(config, "generation", "technologies")
    if isinstance(techs, Mapping):
        for block in techs.values():
            if not isinstance(block, Mapping):
                continue
            type_value = block.get("type")
            if is_generation_type(type_value):
                return True
            if type_value is None and block.get("capacity_factor") is not None:
                return True
    return False


def resolve_lcos_specs(config: Mapping[str, Any]) -> Optional[List[LcosSpec]]:
    """Resolve an :class:`LcosSpec` for every ``type: bess`` technology.

    Reuses :func:`finance.bess_revenue.resolve_bess_specs` for the revenue-relevant fields
    (model, ratings, MDSC fade / floor, augmentation events, contract years) and enriches
    each with the cost and energy inputs LCOS needs, read from the BESS block's reporting
    fields and the project cost blocks. Returns ``None`` when there is no BESS block, so a
    wind/solar-only scenario yields no LCOS view.

    Cost sourcing (all USD):

    * **capex** — the BESS block's ``capex_usd``; if absent and the BESS is standalone,
      the project ``capex.usd_total``; otherwise excluded (with a note).
    * **opex** — the BESS block's ``revenue.opex_usd_per_year``; if absent and the BESS is
      standalone, the project ``opex.usd_per_year``; otherwise excluded (with a note,
      because a hybrid's project opex is shared and cannot be attributed cleanly).
    * **augmentation / salvage** — the block's ``revenue.augmentation_schedule`` capex and
      optional ``revenue.salvage_usd`` (default 0).

    Args:
        config: A loaded scenario config mapping.

    Returns:
        A list of resolved :class:`LcosSpec`, or ``None`` when no BESS block is present.

    Raises:
        ValueError: A BESS block carries an invalid LCOS field (a ratio outside ``[0, 1]``,
            a negative cost, a non-positive cycles/duration).
    """
    bess_specs = resolve_bess_specs(config)
    if not bess_specs:
        return None

    techs = _nested_get(config, "generation", "technologies")
    techs_map: Mapping[str, Any] = techs if isinstance(techs, Mapping) else {}
    standalone = not _has_generation(config)
    single_bess = len(bess_specs) == 1

    project_opex = _as_float(_nested_get(config, "opex", "usd_per_year"))
    project_opex_esc = _as_float(_nested_get(config, "opex", "escalation_pct")) or 0.0
    project_capex_total = _as_float(_nested_get(config, "capex", "usd_total"))

    out: List[LcosSpec] = []
    for spec in bess_specs:
        name = str(spec["technology"])
        model = str(spec["model"])
        block = techs_map.get(name)
        block = block if isinstance(block, Mapping) else {}
        revenue = block.get("revenue")
        revenue = revenue if isinstance(revenue, Mapping) else {}
        notes: List[str] = []

        # --- Energy basis (nameplate MWh per full cycle) ------------------------------
        energy_mwh = _as_float(block.get("energy_mwh"))
        power_mw = _as_float(spec.get("power_mw"))
        duration_h = _as_float(block.get("duration_h"))
        if energy_mwh is not None and energy_mwh > 0:
            energy_per_cycle = energy_mwh
        elif power_mw is not None and duration_h is not None and duration_h > 0:
            energy_per_cycle = power_mw * duration_h
        else:
            energy_per_cycle = 0.0
            notes.append(
                "no energy rating (energy_mwh or power_mw*duration_h) — LCOS energy "
                "basis is zero and the metric is undefined."
            )

        # --- Cycling / efficiency / depth (read-only LCOS assumptions) ----------------
        cycles = _positive(
            revenue.get("cycles_per_year"),
            tech=name,
            field="cycles_per_year",
            default=float(spec.get("cycles_per_year") or _DEFAULT_CYCLES_PER_YEAR),
        )
        rte = _ratio(
            revenue.get("round_trip_efficiency"),
            tech=name,
            field="round_trip_efficiency",
            default=float(
                spec.get("round_trip_efficiency") or _DEFAULT_ROUND_TRIP_EFFICIENCY
            ),
        )
        default_dod = (
            _DEFAULT_DOD_CAPACITY_CHARGE
            if model == "capacity_charge"
            else _DEFAULT_DOD_ENERGY_TARIFF
        )
        dod = _ratio(
            revenue.get("depth_of_discharge"),
            tech=name,
            field="depth_of_discharge",
            default=default_dod,
        )
        if model == "capacity_charge":
            notes.append(
                f"capacity-charge LCOS assumes {cycles:g} cycles/yr at "
                f"{dod:g} depth-of-discharge — actual dispatch is set by CEB and not "
                "simulated."
            )

        # --- Capex (USD) --------------------------------------------------------------
        block_capex = _non_negative(
            block.get("capex_usd"), tech=name, field="capex_usd", default=-1.0
        )
        if block_capex >= 0.0:
            capex_usd = block_capex
        elif standalone and single_bess and project_capex_total is not None:
            capex_usd = project_capex_total
        else:
            capex_usd = 0.0
            notes.append(
                "no BESS-block capex_usd and not a standalone single-BESS scenario — "
                "capex excluded; LCOS understates true cost."
            )

        # --- Opex (USD/yr) ------------------------------------------------------------
        block_opex = _non_negative(
            revenue.get("opex_usd_per_year"),
            tech=name,
            field="opex_usd_per_year",
            default=-1.0,
        )
        if block_opex >= 0.0:
            opex_usd = block_opex
        elif standalone and single_bess and project_opex is not None:
            opex_usd = project_opex
        else:
            opex_usd = 0.0
            notes.append(
                "opex not attributed (hybrid project opex is shared and no "
                "revenue.opex_usd_per_year on the BESS block) — LCOS understates true "
                "cost."
            )

        salvage_usd = _non_negative(
            revenue.get("salvage_usd"), tech=name, field="salvage_usd", default=0.0
        )

        out.append(
            LcosSpec(
                technology=name,
                revenue_model=model,
                energy_per_cycle_mwh=energy_per_cycle,
                cycles_per_year=cycles,
                round_trip_efficiency=rte,
                depth_of_discharge=dod,
                capex_usd=capex_usd,
                opex_usd_per_year=opex_usd,
                opex_escalation_pct=project_opex_esc,
                salvage_usd=salvage_usd,
                contract_years=spec.get("contract_years"),
                soh_fade_pct_annual=float(spec.get("mdsc_fade_pct_annual", 0.0)),
                soh_floor=float(spec.get("mdsc_floor_soh", 0.70)),
                augmentation_events=tuple(spec.get("augmentation_events") or ()),
                notes=tuple(notes),
            )
        )
    return out


def compute_lcos(spec: LcosSpec, *, wacc: float, project_years: int) -> LcosResult:
    """Compute the LCOS for one resolved :class:`LcosSpec` at the project WACC.

    The horizon is the BESS's operating life within the project — ``contract_years``
    capped at ``project_years`` (or ``project_years`` when the spec has no contract term).
    Initial capex is taken at ``t=0``; opex, augmentation capex, discharged energy, and
    salvage are discounted over operating years ``1..horizon`` at ``wacc`` (reusing
    :func:`finance.irr.npv`). The state-of-health curve is
    :func:`finance.bess_revenue.mdsc_soh_for_year`.

    Args:
        spec: A resolved LCOS spec from :func:`resolve_lcos_specs`.
        wacc: The project WACC as a decimal (e.g. ``0.0983``). The caller resolves it (it
            is the same rate the cashflow discounts at — one rate, CCCDIR).
        project_years: The project operating life in years (caps the LCOS horizon).

    Returns:
        An :class:`LcosResult` with the LCOS and its present-value build-up.

    Raises:
        ValueError: ``wacc`` is non-finite or ``<= -1``, or ``project_years < 1``.
    """
    if not math.isfinite(wacc) or wacc <= -1.0:
        raise ValueError(
            f"wacc={wacc!r} is invalid for LCOS discounting (need a finite rate > -1)."
        )
    if project_years < 1:
        raise ValueError(f"project_years={project_years!r} must be a positive integer.")

    horizon = project_years
    if spec.contract_years is not None:
        horizon = min(int(spec.contract_years), project_years)
    horizon = max(1, horizon)

    soh_lookup: Dict[str, Any] = {
        "mdsc_fade_pct_annual": spec.soh_fade_pct_annual,
        "mdsc_floor_soh": spec.soh_floor,
        "augmentation_events": list(spec.augmentation_events),
    }

    # Cashflow arrays indexed by period: index 0 = t0 (capex), index t = operating year t.
    capex_cf = [0.0] * (horizon + 1)
    opex_cf = [0.0] * (horizon + 1)
    aug_cf = [0.0] * (horizon + 1)
    salvage_cf = [0.0] * (horizon + 1)
    energy_cf = [0.0] * (horizon + 1)

    capex_cf[0] = spec.capex_usd
    for t in range(1, horizon + 1):
        opex_cf[t] = spec.opex_usd_per_year * (1.0 + spec.opex_escalation_pct) ** (
            t - 1
        )
        soh = mdsc_soh_for_year(soh_lookup, t - 1)
        energy_cf[t] = (
            spec.energy_per_cycle_mwh
            * spec.cycles_per_year
            * spec.depth_of_discharge
            * spec.round_trip_efficiency
            * soh
        )
    for event in spec.augmentation_events:
        year = int(event["year"])
        if 1 <= year <= horizon:
            aug_cf[year] += float(event["capex_usd"])
    salvage_cf[horizon] = spec.salvage_usd

    pv_capex = npv(wacc, capex_cf)
    pv_opex = npv(wacc, opex_cf)
    pv_aug = npv(wacc, aug_cf)
    pv_salvage = npv(wacc, salvage_cf)
    pv_costs = pv_capex + pv_opex + pv_aug - pv_salvage
    pv_energy = npv(wacc, energy_cf)

    notes = list(spec.notes)
    if pv_energy > 0.0:
        lcos: Optional[float] = pv_costs / pv_energy
    else:
        lcos = None
        notes.append("present value of discharged energy is zero — LCOS is undefined.")

    return LcosResult(
        technology=spec.technology,
        revenue_model=spec.revenue_model,
        lcos_usd_per_mwh=lcos,
        pv_costs_usd=pv_costs,
        pv_discharged_mwh=pv_energy,
        pv_capex_usd=pv_capex,
        pv_opex_usd=pv_opex,
        pv_augmentation_usd=pv_aug,
        pv_salvage_usd=pv_salvage,
        wacc=float(wacc),
        horizon_years=horizon,
        depth_of_discharge=spec.depth_of_discharge,
        round_trip_efficiency=spec.round_trip_efficiency,
        cycles_per_year=spec.cycles_per_year,
        notes=tuple(notes),
    )


def compute_lcos_suite(
    config: Mapping[str, Any], *, wacc: float, project_years: int
) -> List[LcosResult]:
    """Compute the LCOS for every BESS in a scenario (read-only report-pack entry point).

    Resolves the LCOS specs (:func:`resolve_lcos_specs`) and computes each
    (:func:`compute_lcos`). Returns an empty list when the scenario has no BESS, so a
    wind/solar-only report renders no LCOS section.

    Args:
        config: A loaded scenario config mapping.
        wacc: The project WACC as a decimal (resolved upstream — same rate the cashflow
            uses).
        project_years: The project operating life in years.

    Returns:
        One :class:`LcosResult` per BESS technology (possibly empty).
    """
    specs = resolve_lcos_specs(config)
    if not specs:
        return []
    return [compute_lcos(s, wacc=wacc, project_years=project_years) for s in specs]


__all__ = [
    "LcosSpec",
    "LcosResult",
    "resolve_lcos_specs",
    "compute_lcos",
    "compute_lcos_suite",
]
