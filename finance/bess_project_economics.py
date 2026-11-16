"""Standalone BESS project economics: landed capex, effective cost, IRR, NPV and LCOS.

Turns a standalone battery project's commercial inputs into project economics, for any
scenario that declares a ``bess_economics`` block (#863, #1774). The block, not this module,
holds every project figure: the quote, the duty basis, the cycling basis and the charging
price. It is the "put it together" layer over the existing BESS pieces, adding four things:

1. **Landed capex** from a CIF quote structure (equipment CIF + optional warranties or
   service + freight) + an import customs/duty layer ("at actual", buyer scope) + a
   USD -> LKR FX translation. The CIF price is NOT the installed cost; the duty, freight
   and FX layers are what the buyer actually pays.
2. **Capacity-charge effective-cost curve**, the method capacity-charge battery tenders use:
   ``effective LKR/kWh = annual capacity charge / degradation-adjusted annual discharge``,
   over life. The capacity revenue here is derated by the same state-of-health curve as the
   discharge (:mod:`finance.bess_revenue`), so the curve this module returns is flat; a
   tender that pays an undiminished charge would see it rise as energy degrades. The method
   **EXCLUDES the charging cost**; that omission is disclosed in the result, not hidden.
3. **The separate charging-cost lever** the method omits:
   ``energy_to_charge_mwh x charging_tariff_lkr_per_kwh x 1/RTE`` (the round-trip loss makes
   the charge-side energy larger than the discharge-side). Required for a full P&L.
4. **A standalone BESS cashflow -> IRR / NPV / LCOS**: ``landed capex`` at t0, then per year
   ``capacity revenue - opex - charging cost - warranty draws - augmentation capex``, plus a
   read-only LCOS view. The yearly LKR flows are translated to USD on the scenario's own
   operating FX curve (with the construction offset the scenario's cashflow uses), and the
   IRR and NPV are reported in USD at the scenario's project rate, the currency and rate of
   the scenario's own KPIs. The basis is nominal, pre-tax and unlevered, and the result says
   so. The LKR series and its IRR are kept for reference. IRR/NPV come from :mod:`finance.irr` (R7 single source of truth); the
   LCOS reuses :func:`finance.bess_lcos.compute_lcos`. Nothing is re-implemented.

RECONCILIATION (extends, does not duplicate)
--------------------------------------------
Every piece of physics/revenue this module needs already lives in the BESS layer and is
IMPORTED, never re-derived:

* Revenue + degradation: :func:`finance.bess_revenue.resolve_bess_specs`,
  :func:`finance.bess_revenue.bess_revenue_lkr_for_year` (the flat capacity charge x the
  year-indexed state-of-health), :func:`finance.bess_revenue.mdsc_soh_for_year` (the SoH
  curve), :func:`finance.bess_revenue.bess_augmentation_capex_lkr_for_year`.
* LCOS: :func:`finance.bess_lcos.resolve_lcos_specs` / :func:`finance.bess_lcos.compute_lcos`.
* IRR / NPV: :func:`finance.irr.irr` / :func:`finance.irr.npv` (never re-implemented, R7).
* FX: :func:`finance.cashflow_v14_fx._fx_curve` (the config-first, fail-loud FX routine — no
  hardcoded rate).

This module adds ONLY the capex ingest, the effective-cost curve, the charging lever, and
the standalone-cashflow assembly. It computes the discharge/SoH energy the SAME way the LCOS
and revenue paths do, so the three cannot diverge.

HOW A SCENARIO REACHES IT (KPI-neutral, opt-in)
-----------------------------------------------
Any scenario reaches it through the canonical pipeline: ``run_v14_pipeline`` calls
:func:`bess_economics_result` and returns the result under ``bess_project_economics`` when the
scenario declares ``bess_economics.enabled: true`` (#1774). It is a separate cashflow for the
battery as its own project, so it:

* refuses to run unless the scenario carries an explicit ``bess_economics.enabled: true``
  opt-in (:func:`bess_economics_requested`); absent that flag the result has no such key;
* touches nothing that feeds the CFADS/IRR/DSCR of the scenario's own cashflow.

Folding these economics INTO a multi-technology case's own cashflow (so the capacity charge,
the degradation and the charging cost move the project's KPIs) is a separate, owner-gated
step, NOT this module.

INPUTS (no hidden business values)
----------------------------------
Nothing in this module supplies a default capex, duty rate or cycling basis: a scenario must
declare ``bess_economics.capex.equipment_usd`` and ``bess_economics.discharge_cycles_per_year``
(CESSPIT). :func:`validate_bess_economics_block` checks a declared block strictly in pre-flight.
A BESS is NOT a ``capacity_factor x tariff`` generator; nothing here treats it as one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .bess_lcos import LcosResult, compute_lcos, resolve_lcos_specs
from .bess_revenue import (
    bess_augmentation_capex_lkr_for_year,
    bess_revenue_lkr_for_year,
    mdsc_soh_for_year,
    resolve_bess_specs,
)
from .cashflow_v14_fx import _fx_curve
from .cashflow_v14_utils import pct_to_decimal
from .irr import irr, npv

#: The opt-in flag key. Absent / not truthy => this analysis does not run (default-off).
_ENABLED_KEY = "enabled"
#: The scenario block that carries the standalone-BESS economics inputs.
_ECONOMICS_BLOCK = "bess_economics"
_KWH_PER_MWH = 1000.0


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

    Bools, ``None``, non-numerics, and non-finite values (NaN / +/-inf) return ``None`` so
    they trip the callers' fail-loud guards rather than poisoning a cost or IRR.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        coerced = float(value)
        return coerced if math.isfinite(coerced) else None
    return None


def _require_non_negative(value: Any, *, block: str, field_name: str) -> float:
    """Read a REQUIRED non-negative number; raise (CESSPIT) when absent/invalid.

    No silent default: a standalone BESS economics run must declare its costs explicitly, so a
    missing or negative capex/duty line is a config error, not a zero.
    """
    coerced = _as_float(value)
    if coerced is None or coerced < 0.0:
        raise ValueError(
            f"{block}.{field_name}={value!r} must be a non-negative number "
            f"(it is a required standalone-BESS economics input)."
        )
    return coerced


def _optional_non_negative(
    value: Any, *, block: str, field_name: str, default: float
) -> float:
    """Read an OPTIONAL non-negative number; return ``default`` when absent, raise when bad."""
    if value is None:
        return default
    coerced = _as_float(value)
    if coerced is None or coerced < 0.0:
        raise ValueError(
            f"{block}.{field_name}={value!r} must be a non-negative number."
        )
    return coerced


def _optional_ratio(
    value: Any, *, block: str, field_name: str, default: float
) -> float:
    """Read an OPTIONAL ratio in ``[0, 1]``; return ``default`` when absent, raise when bad."""
    if value is None:
        return default
    coerced = _as_float(value)
    if coerced is None or not 0.0 <= coerced <= 1.0:
        raise ValueError(
            f"{block}.{field_name}={value!r} must be a ratio in [0, 1] (e.g. 0.15, not 15)."
        )
    return coerced


def bess_economics_requested(config: Mapping[str, Any]) -> bool:
    """True iff the scenario opts INTO the standalone-BESS economics analysis (default-off).

    The opt-in is an explicit ``bess_economics.enabled: true``. Absent the block, or the flag
    not truthy, this returns ``False`` and :func:`compute_bess_project_economics` refuses to
    run — so no committed scenario (which carries no such block) is ever touched.
    """
    block = config.get(_ECONOMICS_BLOCK)
    if not isinstance(block, Mapping):
        return False
    return bool(block.get(_ENABLED_KEY))


# ─────────────────────────────────────────────────────────────────────────────
# 1. Landed capex — CIF quote structure + import customs/duty + USD->LKR FX
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LandedCapex:
    """The buyer's landed capex for a CIF-quoted BESS, in both USD and LKR.

    The CIF equipment price is only the ex-tax, ex-duty starting point; the buyer additionally
    pays freight (if not already CIF-included), import customs/duty "at actual", and bears
    the USD->LKR translation. ``equipment_usd`` + ``freight_usd`` = the dutiable base; duty is
    ``duty_pct`` of that (or an explicit ``duty_usd`` override); optional warranties are a
    financed capex add-on. ``fx_rate_lkr_per_usd`` is the year-0 spot from the project FX curve.
    """

    equipment_usd: float
    freight_usd: float
    optional_warranty_usd: float
    dutiable_base_usd: float
    customs_duty_usd: float
    landed_capex_usd: float
    fx_rate_lkr_per_usd: float
    landed_capex_lkr: float
    #: Provenance/limitation notes (e.g. duty basis, warranty inclusion).
    notes: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        """JSON-serialisable dict for report packs / CLIs."""
        return {
            "equipment_usd": self.equipment_usd,
            "freight_usd": self.freight_usd,
            "optional_warranty_usd": self.optional_warranty_usd,
            "dutiable_base_usd": self.dutiable_base_usd,
            "customs_duty_usd": self.customs_duty_usd,
            "landed_capex_usd": self.landed_capex_usd,
            "fx_rate_lkr_per_usd": self.fx_rate_lkr_per_usd,
            "landed_capex_lkr": self.landed_capex_lkr,
            "notes": list(self.notes),
        }


def resolve_landed_capex(
    config: Mapping[str, Any], *, fx_rate_lkr_per_usd: float
) -> LandedCapex:
    """Build the buyer's landed capex from a CIF quote structure + import duty + FX.

    Reads ``bess_economics.capex``:

    * ``equipment_usd`` (REQUIRED) — the CIF equipment sub-total.
    * ``freight_usd`` (optional, default 0) — freight if quoted separately from CIF.
    * ``optional_warranty_usd`` (optional, default 0) — 15-yr warranties/service financed as
      capex. NOT dutiable by default (a service line, not goods);
      set ``warranty_is_dutiable: true`` to include it in the dutiable base.
    * ``customs_duty_pct`` (optional, default 0) — import customs/duty as a fraction of the
      dutiable base, OR
    * ``customs_duty_usd`` (optional) — an explicit duty amount (overrides ``_pct``).

    The dutiable base is ``equipment_usd + freight_usd`` (+ warranty if flagged dutiable).
    Landed USD = dutiable base + duty + warranty. Landed LKR = landed USD x the supplied FX
    rate (the year-0 spot from :func:`finance.cashflow_v14_fx._fx_curve` — no hardcoded FX).

    Args:
        config: The scenario config (must carry a ``bess_economics.capex`` block).
        fx_rate_lkr_per_usd: The year-0 LKR/USD spot rate (from the project FX curve).

    Returns:
        A :class:`LandedCapex`.

    Raises:
        ValueError: The capex block is missing/malformed, or the FX rate is non-positive.
    """
    if not math.isfinite(fx_rate_lkr_per_usd) or fx_rate_lkr_per_usd <= 0.0:
        raise ValueError(
            f"fx_rate_lkr_per_usd={fx_rate_lkr_per_usd!r} must be a positive LKR/USD rate."
        )
    capex = _nested_get(config, _ECONOMICS_BLOCK, "capex")
    if not isinstance(capex, Mapping):
        raise ValueError(
            f"{_ECONOMICS_BLOCK}.capex block is required to resolve landed capex "
            "(declare at least equipment_usd, the CIF equipment sub-total)."
        )
    blk = f"{_ECONOMICS_BLOCK}.capex"
    equipment_usd = _require_non_negative(
        capex.get("equipment_usd"), block=blk, field_name="equipment_usd"
    )
    freight_usd = _optional_non_negative(
        capex.get("freight_usd"), block=blk, field_name="freight_usd", default=0.0
    )
    warranty_usd = _optional_non_negative(
        capex.get("optional_warranty_usd"),
        block=blk,
        field_name="optional_warranty_usd",
        default=0.0,
    )
    warranty_dutiable = bool(capex.get("warranty_is_dutiable"))

    notes: List[str] = []
    dutiable_base = equipment_usd + freight_usd
    if warranty_dutiable:
        dutiable_base += warranty_usd
        notes.append(
            "optional warranty included in the dutiable base (warranty_is_dutiable)."
        )
    else:
        notes.append(
            "optional warranty treated as a non-dutiable service line (set "
            "warranty_is_dutiable: true to include it in the duty base)."
        )

    duty_usd_raw = capex.get("customs_duty_usd")
    if duty_usd_raw is not None:
        customs_duty_usd = _require_non_negative(
            duty_usd_raw, block=blk, field_name="customs_duty_usd"
        )
        notes.append(
            "import customs/duty taken from an explicit customs_duty_usd amount."
        )
    else:
        duty_pct = _optional_ratio(
            capex.get("customs_duty_pct"),
            block=blk,
            field_name="customs_duty_pct",
            default=0.0,
        )
        customs_duty_usd = dutiable_base * duty_pct
        notes.append(
            f"import customs/duty = {duty_pct:.4g} x the dutiable base "
            "(CIF quotes are ex-tax; duty is buyer scope, 'at actual')."
        )

    landed_capex_usd = dutiable_base + customs_duty_usd + warranty_usd
    landed_capex_lkr = landed_capex_usd * fx_rate_lkr_per_usd

    return LandedCapex(
        equipment_usd=equipment_usd,
        freight_usd=freight_usd,
        optional_warranty_usd=warranty_usd,
        dutiable_base_usd=dutiable_base,
        customs_duty_usd=customs_duty_usd,
        landed_capex_usd=landed_capex_usd,
        fx_rate_lkr_per_usd=fx_rate_lkr_per_usd,
        landed_capex_lkr=landed_capex_lkr,
        notes=tuple(notes),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Capacity-charge effective-cost curve (LKR/kWh) — charging cost EXCLUDED
# ─────────────────────────────────────────────────────────────────────────────


def _discharge_mwh_for_year(
    spec: Dict[str, Any],
    year_index: int,
    *,
    energy_per_cycle_mwh: float,
    cycles_per_year: float,
) -> float:
    """Degradation-adjusted annual DISCHARGE energy (MWh) for one BESS in one year.

    ``energy_per_cycle_mwh x cycles_per_year x soh(year)`` — the nameplate-energy x
    state-of-health basis of the capacity-charge effective-cost method (nameplate energy at
    COD x the declared cycles per year, scaled by the SoH curve). The SoH comes from
    :func:`finance.bess_revenue.mdsc_soh_for_year` so it is IDENTICAL to the revenue/LCOS
    curves.
    """
    soh = mdsc_soh_for_year(spec, year_index)
    return energy_per_cycle_mwh * cycles_per_year * soh


def _required_cycles_per_year(config: Mapping[str, Any]) -> float:
    """Read the REQUIRED ``bess_economics.discharge_cycles_per_year`` (> 0); raise when absent.

    The cycling basis is a project input, not a code default (#1774): it differs by tender,
    by dispatch and by contract, so a scenario must declare it.
    """
    raw = _nested_get(config, _ECONOMICS_BLOCK, "discharge_cycles_per_year")
    cycles = _as_float(raw)
    if cycles is None or cycles <= 0.0:
        raise ValueError(
            f"{_ECONOMICS_BLOCK}.discharge_cycles_per_year={raw!r} must be a positive "
            "number of full discharge cycles per year (a required input; there is no "
            "code default)."
        )
    return cycles


def capacity_charge_effective_cost_curve(
    config: Mapping[str, Any], *, years: int
) -> Optional[List[Dict[str, Any]]]:
    """The effective-cost curve for every capacity-charge BESS (LKR/kWh over life).

    Applies the capacity-charge effective-cost method per operating year::

        effective_lkr_per_kwh(t) = annual_capacity_charge_lkr(t) / annual_discharge_kwh(t)

    where ``annual_capacity_charge_lkr`` is the flat charge x the year-indexed SoH (from
    :func:`finance.bess_revenue.bess_revenue_lkr_for_year`) and ``annual_discharge_kwh`` is the
    degradation-adjusted discharge (``energy_per_cycle x cycles/yr x soh(t) x 1000``). Both
    numerator and denominator fade with the SAME SoH, so the cost
    RISES over life only because the discharge basis falls faster than the (SoH-scaled) charge
    where the charge does not fade; with an ``mdsc_fade`` opt-in they share the fade and the
    curve is flatter. The cycles per year come from the REQUIRED
    ``bess_economics.discharge_cycles_per_year``.

    **CHARGING COST IS EXCLUDED**, as the method itself excludes it. Each row carries that
    disclosure; the charging cost is a SEPARATE lever
    (:func:`charging_cost_lkr_for_year`).

    Returns ``None`` when the scenario has no capacity-charge BESS (energy-tariff BESSes are
    not part of the capacity-charge method). ``lkr_per_kwh`` is ``None`` for a year whose
    discharge basis is zero (undefined, not silently zero).

    Args:
        config: The scenario config.
        years: The number of operating years to tabulate.

    Returns:
        A list of ``{technology, year, capacity_charge_lkr, discharge_mwh, lkr_per_kwh,
        charging_excluded, note}`` rows (one per capacity-charge BESS per year), or ``None``.

    Raises:
        ValueError: A capacity-charge BESS is present but
            ``bess_economics.discharge_cycles_per_year`` is absent or not positive.
    """
    specs = resolve_bess_specs(config)
    if not specs:
        return None
    if not any(spec.get("model") == "capacity_charge" for spec in specs):
        return None
    cycles_per_year = _required_cycles_per_year(config)

    rows: List[Dict[str, Any]] = []
    have_capacity_charge = False
    for spec in specs:
        if spec.get("model") != "capacity_charge":
            continue
        have_capacity_charge = True
        name = str(spec["technology"])
        # Nameplate energy per cycle: power_mw x 4h is not carried on the spec, so read the
        # block's energy rating (the capacity-charge spec does not store energy_mwh).
        block = _nested_get(config, "generation", "technologies", name)
        block = block if isinstance(block, Mapping) else {}
        energy_mwh = _as_float(block.get("energy_mwh"))
        power_mw = _as_float(spec.get("power_mw"))
        duration_h = _as_float(block.get("duration_h"))
        if energy_mwh is not None and energy_mwh > 0:
            energy_per_cycle = energy_mwh
        elif power_mw is not None and duration_h is not None and duration_h > 0:
            energy_per_cycle = power_mw * duration_h
        else:
            energy_per_cycle = 0.0

        contract_years = spec.get("contract_years")
        for t in range(years):
            if contract_years is not None and t >= int(contract_years):
                break
            charge_lkr = bess_revenue_lkr_for_year([spec], t)
            discharge_mwh = _discharge_mwh_for_year(
                spec,
                t,
                energy_per_cycle_mwh=energy_per_cycle,
                cycles_per_year=cycles_per_year,
            )
            discharge_kwh = discharge_mwh * _KWH_PER_MWH
            lkr_per_kwh = (charge_lkr / discharge_kwh) if discharge_kwh > 0 else None
            rows.append(
                {
                    "technology": name,
                    "year": t + 1,
                    "capacity_charge_lkr": charge_lkr,
                    "discharge_mwh": discharge_mwh,
                    "lkr_per_kwh": lkr_per_kwh,
                    "charging_excluded": True,
                    "note": (
                        "capacity-charge method: capacity charge / degradation-adjusted "
                        "discharge; "
                        "CHARGING COST EXCLUDED (add charging_cost_lkr_for_year for a full "
                        "P&L)."
                    ),
                }
            )
    if not have_capacity_charge:
        return None
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 3. Charging-cost lever (the piece the capacity-charge method omits)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChargingCostSpec:
    """The (opt-in) charging-cost lever the effective-cost method deliberately omits.

    A capacity-charge BESS must be CHARGED before it can discharge; the charge-side energy is
    ``discharge / RTE`` (the round-trip loss), priced at the ``charging_tariff_lkr_per_kwh``
    (the grid/off-peak energy the operator buys). This is ``0`` unless a scenario opts in with
    ``bess_economics.charging`` — so a run that does not model charging still gets a coherent
    (charging-excluded) result.
    """

    charging_tariff_lkr_per_kwh: float
    round_trip_efficiency: float


def resolve_charging_cost_spec(config: Mapping[str, Any]) -> Optional[ChargingCostSpec]:
    """Resolve the charging-cost lever, or ``None`` when the scenario does not opt in.

    Reads ``bess_economics.charging``: ``tariff_lkr_per_kwh`` (REQUIRED when the block is
    present — the price of charge energy), ``round_trip_efficiency`` (optional, default 0.85 —
    NREL ATB 2024, matching :mod:`finance.bess_revenue`). The charge-side energy is the
    discharge energy over RTE, and the discharge energy uses the block's required
    ``discharge_cycles_per_year``; there is no separate charging-cycles input, so the two
    cannot disagree (#1776 domain D-2). Absent block => ``None`` => no charging cost.
    """
    charging = _nested_get(config, _ECONOMICS_BLOCK, "charging")
    if not isinstance(charging, Mapping):
        return None
    blk = f"{_ECONOMICS_BLOCK}.charging"
    tariff = _require_non_negative(
        charging.get("tariff_lkr_per_kwh"), block=blk, field_name="tariff_lkr_per_kwh"
    )
    rte = _optional_ratio(
        charging.get("round_trip_efficiency"),
        block=blk,
        field_name="round_trip_efficiency",
        default=0.85,
    )
    if rte <= 0.0:
        raise ValueError(
            f"{blk}.round_trip_efficiency must be > 0 (charge energy = discharge / RTE)."
        )
    return ChargingCostSpec(
        charging_tariff_lkr_per_kwh=tariff,
        round_trip_efficiency=rte,
    )


def charging_cost_lkr_for_year(
    charging: Optional[ChargingCostSpec], discharge_mwh: float
) -> float:
    """The charging cost (LKR) for one year's discharge, or ``0`` with no charging lever.

    ``charge_energy_mwh = discharge_mwh / RTE`` (the round-trip loss inflates the charge-side
    energy above what is discharged), priced at ``tariff_lkr_per_kwh``::

        charging_cost_lkr = (discharge_mwh / RTE) x 1000 x tariff_lkr_per_kwh

    Returns ``0.0`` when ``charging`` is ``None`` (the charging-excluded case).
    """
    if charging is None:
        return 0.0
    charge_energy_mwh = discharge_mwh / charging.round_trip_efficiency
    return charge_energy_mwh * _KWH_PER_MWH * charging.charging_tariff_lkr_per_kwh


# ─────────────────────────────────────────────────────────────────────────────
# 4. Standalone BESS project economics — cashflow -> IRR / NPV / LCOS
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BessProjectEconomics:
    """The assembled standalone-BESS project economics (opt-in, off the committed path).

    ``cashflow_lkr`` is ``[-landed_capex_lkr, cf_1, cf_2, ...]`` — capex at t0, then per-year
    ``capacity revenue - opex - charging cost - warranty draw - augmentation capex``.
    ``cashflow_usd`` is the same series in USD: the landed capex in USD at t0, then each
    year's LKR flow divided by that operating year's rate on ``fx_lkr_per_usd`` (the
    scenario's FX curve with its construction offset). ``irr_usd`` and ``npv_usd`` are on
    that USD series at ``discount_rate`` (the scenario's project rate, a USD rate);
    ``irr_lkr`` is the LKR series' IRR, for reference. ``currency_basis`` states the basis
    (nominal, pre-tax, unlevered). ``lcos`` is the read-only LCOS view (USD/MWh).
    """

    technology: str
    landed_capex: LandedCapex
    discount_rate: float
    horizon_years: int
    cashflow_lkr: Tuple[float, ...]
    cashflow_usd: Tuple[float, ...]
    fx_lkr_per_usd: Tuple[float, ...]
    revenue_lkr: Tuple[float, ...]
    opex_lkr: Tuple[float, ...]
    charging_cost_lkr: Tuple[float, ...]
    augmentation_capex_lkr: Tuple[float, ...]
    irr_usd: Optional[float]
    npv_usd: float
    irr_lkr: Optional[float]
    currency_basis: str
    effective_cost_curve: Optional[List[Dict[str, Any]]]
    lcos: Optional[LcosResult]
    charging_modelled: bool
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> Dict[str, Any]:
        """JSON-serialisable dict for report packs / CLIs."""
        return {
            "technology": self.technology,
            "landed_capex": self.landed_capex.as_dict(),
            "discount_rate": self.discount_rate,
            "horizon_years": self.horizon_years,
            "cashflow_lkr": list(self.cashflow_lkr),
            "cashflow_usd": list(self.cashflow_usd),
            "fx_lkr_per_usd": list(self.fx_lkr_per_usd),
            "revenue_lkr": list(self.revenue_lkr),
            "opex_lkr": list(self.opex_lkr),
            "charging_cost_lkr": list(self.charging_cost_lkr),
            "augmentation_capex_lkr": list(self.augmentation_capex_lkr),
            "irr_usd": self.irr_usd,
            "npv_usd": self.npv_usd,
            "irr_lkr": self.irr_lkr,
            "currency_basis": self.currency_basis,
            "effective_cost_curve": self.effective_cost_curve,
            "lcos": self.lcos.as_dict() if self.lcos is not None else None,
            "charging_modelled": self.charging_modelled,
            "notes": list(self.notes),
        }


def compute_bess_project_economics(
    config: Mapping[str, Any], *, discount_rate: float, project_years: int
) -> Optional[List[BessProjectEconomics]]:
    """Assemble standalone-BESS project economics for every capacity-charge BESS (opt-in).

    Returns ``None`` unless the scenario opts in (``bess_economics.enabled: true``) AND has at
    least one capacity-charge BESS — so a committed generation scenario (no opt-in) is never
    touched. For each capacity-charge BESS it builds the LKR cashflow::

        t0:  -landed_capex_lkr                        (from the CIF/duty/FX ingest)
        t>0:  capacity_revenue - opex - charging_cost - warranty_draw - augmentation_capex

    translates it to USD on the operating FX curve (construction offset applied), computes the
    USD IRR (:func:`finance.irr.irr`) and the USD NPV (:func:`finance.irr.npv` at
    ``discount_rate``, a USD rate) and the LKR IRR for reference, and attaches the
    capacity-charge effective-cost curve and the read-only LCOS (:func:`finance.bess_lcos.compute_lcos`).

    Opex, the warranty draw schedule, and the charging tariff are all opt-in
    ``bess_economics.*`` inputs; absent, they are zero (a clean capex->capacity-revenue view).
    Revenue and augmentation reuse :mod:`finance.bess_revenue`; the discharge basis reuses the
    SAME SoH curve as the effective-cost/LCOS paths, so nothing can diverge.

    Args:
        config: The scenario config (must carry an enabled ``bess_economics`` block).
        discount_rate: The USD rate to discount the USD cash flow at (decimal, e.g. 0.10).
            The pipeline passes the scenario's project discount rate.
        project_years: The number of operating years to model.

    Returns:
        One :class:`BessProjectEconomics` per capacity-charge BESS, or ``None``.

    Raises:
        ValueError: A required ``bess_economics`` input is missing/invalid, the FX/rate
            arguments are non-finite, or the scenario declares more than one
            capacity-charge battery.
    """
    if not bess_economics_requested(config):
        return None
    if not math.isfinite(discount_rate) or discount_rate <= -1.0:
        raise ValueError(
            f"discount_rate={discount_rate!r} is invalid (need a finite rate > -1)."
        )
    if project_years < 1:
        raise ValueError(f"project_years={project_years!r} must be a positive integer.")

    specs = resolve_bess_specs(config)
    capacity_specs = [s for s in specs or [] if s.get("model") == "capacity_charge"]
    if not capacity_specs:
        return None
    if len(capacity_specs) > 1:
        # #1776 domain D-3: the block holds one capex, one opex and one charging spec, so
        # it describes ONE battery project. Two would each be charged the whole capex.
        raise ValueError(_MULTIPLE_BATTERIES_MESSAGE.format(n=len(capacity_specs)))

    # Year-0 FX spot from the project's own FX routine — no hardcoded rate. A standalone BESS
    # economics run must therefore declare an fx block (CESSPIT), exactly like the cashflow.
    fx_curve = _fx_curve(dict(config), project_years)
    fx0 = float(fx_curve[0])
    landed = resolve_landed_capex(config, fx_rate_lkr_per_usd=fx0)
    # The operating-year rates, offset by the construction periods exactly as the
    # scenario's own cashflow does (finance.cashflow_v14), so a year's LKR flow and its
    # augmentation capex convert at the same rate the scenario uses for that year.
    from .debt_v14 import _resolve_construction_periods

    fx_operating = _fx_curve(
        dict(config),
        project_years,
        period_offset=_resolve_construction_periods(config),
    )

    charging = resolve_charging_cost_spec(config)
    discharge_cycles = _required_cycles_per_year(config)

    # Optional opex (LKR/yr, flat) and warranty draw schedule ({year, lkr}); default empty.
    opex_lkr_per_year = _optional_non_negative(
        _nested_get(config, _ECONOMICS_BLOCK, "opex_lkr_per_year"),
        block=_ECONOMICS_BLOCK,
        field_name="opex_lkr_per_year",
        default=0.0,
    )
    opex_escalation = (
        pct_to_decimal(
            _as_float(_nested_get(config, _ECONOMICS_BLOCK, "opex_escalation_pct"))
        )
        or 0.0
    )
    warranty_draws = _resolve_warranty_draws(config)

    effective_cost = capacity_charge_effective_cost_curve(config, years=project_years)
    lcos_specs = resolve_lcos_specs(config) or []
    lcos_by_tech = {s.technology: s for s in lcos_specs}

    out: List[BessProjectEconomics] = []
    for spec in capacity_specs:
        if spec.get("model") != "capacity_charge":
            continue
        name = str(spec["technology"])
        contract_years = spec.get("contract_years")
        horizon = project_years
        if contract_years is not None:
            horizon = min(int(contract_years), project_years)
        horizon = max(1, horizon)

        block = _nested_get(config, "generation", "technologies", name)
        block = block if isinstance(block, Mapping) else {}
        energy_mwh = _as_float(block.get("energy_mwh"))
        power_mw = _as_float(spec.get("power_mw"))
        duration_h = _as_float(block.get("duration_h"))
        if energy_mwh is not None and energy_mwh > 0:
            energy_per_cycle = energy_mwh
        elif power_mw is not None and duration_h is not None and duration_h > 0:
            energy_per_cycle = power_mw * duration_h
        else:
            energy_per_cycle = 0.0

        revenue_series: List[float] = []
        opex_series: List[float] = []
        charging_series: List[float] = []
        aug_series: List[float] = []
        cashflow = [-landed.landed_capex_lkr]
        cashflow_usd = [-landed.landed_capex_usd]
        fx_series: List[float] = []
        for t in range(horizon):
            revenue = bess_revenue_lkr_for_year([spec], t)
            opex = opex_lkr_per_year * (1.0 + opex_escalation) ** t
            discharge_mwh = _discharge_mwh_for_year(
                spec,
                t,
                energy_per_cycle_mwh=energy_per_cycle,
                cycles_per_year=discharge_cycles,
            )
            charge_cost = charging_cost_lkr_for_year(charging, discharge_mwh)
            # Augmentation capex converted at the year's operating FX rate (shared routine).
            fx_year = float(fx_operating[min(t, len(fx_operating) - 1)])
            aug = bess_augmentation_capex_lkr_for_year([spec], t, fx_year)
            warranty = warranty_draws.get(t + 1, 0.0)
            revenue_series.append(revenue)
            opex_series.append(opex)
            charging_series.append(charge_cost)
            aug_series.append(aug)
            flow_lkr = revenue - opex - charge_cost - aug - warranty
            cashflow.append(flow_lkr)
            cashflow_usd.append(flow_lkr / fx_year)
            fx_series.append(fx_year)

        irr_usd = irr(cashflow_usd)
        npv_usd = npv(discount_rate, cashflow_usd)
        irr_lkr = irr(cashflow)
        lcos_res: Optional[LcosResult] = None
        if name in lcos_by_tech:
            lcos_res = compute_lcos(
                lcos_by_tech[name], wacc=discount_rate, project_years=project_years
            )

        notes = [
            "STANDALONE, OPT-IN analysis: the battery as its own project, separate from "
            "the scenario's own cashflow; folding these economics into a multi-technology "
            "case is a separate, owner-gated step.",
            "landed capex from the CIF quote structure + import customs/duty + USD->LKR FX; "
            "the CIF price is ex-tax/ex-duty (buyer bears duty 'at actual').",
        ]
        if charging is None:
            notes.append(
                "charging cost NOT modelled (the effective-cost method excludes it); opt in "
                "via bess_economics.charging for a full P&L."
            )
        out.append(
            BessProjectEconomics(
                technology=name,
                landed_capex=landed,
                discount_rate=float(discount_rate),
                horizon_years=horizon,
                cashflow_lkr=tuple(cashflow),
                cashflow_usd=tuple(cashflow_usd),
                fx_lkr_per_usd=tuple(fx_series),
                revenue_lkr=tuple(revenue_series),
                opex_lkr=tuple(opex_series),
                charging_cost_lkr=tuple(charging_series),
                augmentation_capex_lkr=tuple(aug_series),
                irr_usd=irr_usd,
                npv_usd=npv_usd,
                irr_lkr=irr_lkr,
                currency_basis=CURRENCY_BASIS,
                effective_cost_curve=effective_cost,
                lcos=lcos_res,
                charging_modelled=charging is not None,
                notes=tuple(notes),
            )
        )
    return out or None


def _resolve_warranty_draws(config: Mapping[str, Any]) -> Dict[int, float]:
    """Resolve the optional warranty/service draw schedule to ``{operating_year: lkr}``.

    Reads ``bess_economics.warranty_schedule`` — a list of ``{year, lkr}`` events (a mid-life
    service/warranty cash outflow, in LKR, in the 1-based operating ``year``). Absent => ``{}``
    => no warranty draws. Fail-loud (CESSPIT) on a non-list, a bad year, or a negative amount.
    """
    schedule = _nested_get(config, _ECONOMICS_BLOCK, "warranty_schedule")
    if schedule is None:
        return {}
    if not isinstance(schedule, (list, tuple)):
        raise ValueError(
            f"{_ECONOMICS_BLOCK}.warranty_schedule must be a list of {{year, lkr}} events."
        )
    draws: Dict[int, float] = {}
    for i, ev in enumerate(schedule):
        if not isinstance(ev, Mapping):
            raise ValueError(
                f"{_ECONOMICS_BLOCK}.warranty_schedule[{i}] must be a mapping {{year, lkr}}."
            )
        year = _as_float(ev.get("year"))
        if year is None or year != int(year) or year < 1:
            raise ValueError(
                f"{_ECONOMICS_BLOCK}.warranty_schedule[{i}].year={ev.get('year')!r} must be "
                "a positive whole operating year."
            )
        lkr = _require_non_negative(
            ev.get("lkr"),
            block=f"{_ECONOMICS_BLOCK}.warranty_schedule[{i}]",
            field_name="lkr",
        )
        draws[int(year)] = draws.get(int(year), 0.0) + lkr
    return draws


# ─────────────────────────────────────────────────────────────────────────────
# 5. Pre-flight contract and the pipeline entry point (#1774)
# ─────────────────────────────────────────────────────────────────────────────

#: The keys a ``bess_economics`` block may hold. Anything else is a typo or an input this
#: module does not read, so pre-flight refuses it rather than ignoring it.
_BLOCK_KEYS: Tuple[str, ...] = (
    "enabled",
    "capex",
    "discharge_cycles_per_year",
    "charging",
    "opex_lkr_per_year",
    "opex_escalation_pct",
    "warranty_schedule",
    "sources",
    "notes",
)
_CAPEX_KEYS: Tuple[str, ...] = (
    "equipment_usd",
    "freight_usd",
    "optional_warranty_usd",
    "warranty_is_dutiable",
    "customs_duty_pct",
    "customs_duty_usd",
)
_CHARGING_KEYS: Tuple[str, ...] = (
    "tariff_lkr_per_kwh",
    "round_trip_efficiency",
)
_WARRANTY_EVENT_KEYS: Tuple[str, ...] = ("year", "lkr")

#: The basis every reported IRR and NPV is on (#1776 domain D-1).
CURRENCY_BASIS = (
    "USD, nominal, pre-tax, unlevered: each operating year's LKR flow translated at the "
    "scenario's operating FX curve (construction offset applied) and discounted at the "
    "scenario's project rate; capex at year 0, operations from year 1; irr_lkr is the "
    "LKR series' IRR, for reference only"
)

_MULTIPLE_BATTERIES_MESSAGE = (
    "bess_economics describes one battery project (one capex, opex and charging spec), but "
    "generation.technologies declares {n} capacity-charge batteries; model one battery per "
    "scenario"
)


def _check_keys(
    block: Mapping[str, Any], allowed: Tuple[str, ...], path: str, errors: List[str]
) -> None:
    for key in block:
        if key not in allowed:
            errors.append(f"{path}.{key}: unknown key (allowed: {', '.join(allowed)})")


def _check_number(
    block: Mapping[str, Any],
    key: str,
    path: str,
    errors: List[str],
    *,
    required: bool = False,
    positive: bool = False,
    upper: Optional[float] = None,
) -> None:
    if key not in block or block[key] is None:
        if required:
            errors.append(
                f"{path}.{key}: required when {_ECONOMICS_BLOCK}.enabled is true"
            )
        return
    value = _as_float(block[key])
    if value is None:
        errors.append(f"{path}.{key}: must be a finite number (got {block[key]!r})")
        return
    if value < 0.0 or (positive and value == 0.0):
        bound = "> 0" if positive else ">= 0"
        errors.append(f"{path}.{key}: must be {bound} (got {block[key]!r})")
    elif upper is not None and value > upper:
        errors.append(f"{path}.{key}: must be <= {upper} (got {block[key]!r})")


def validate_bess_economics_block(config: Mapping[str, Any], errors: List[str]) -> None:
    """Check a declared ``bess_economics`` block strictly, appending one error per fault.

    Present-only: a scenario without the block gets no error and is unchanged. A declared
    block is refused on an unknown key, a wrong type or an out-of-range value, naming the
    path (``FRAMEWORK-02``). When ``enabled`` is true the inputs with no code default,
    ``capex.equipment_usd`` and ``discharge_cycles_per_year``, are required.

    Args:
        config: The scenario config.
        errors: The pre-flight error list to append to.
    """
    if _ECONOMICS_BLOCK not in config:
        return
    path = _ECONOMICS_BLOCK
    block = config.get(_ECONOMICS_BLOCK)
    if not isinstance(block, Mapping):
        errors.append(f"{path}: must be a mapping (got {type(block).__name__})")
        return
    _check_keys(block, _BLOCK_KEYS, path, errors)
    enabled = block.get(_ENABLED_KEY, False)
    if not isinstance(enabled, bool):
        errors.append(f"{path}.{_ENABLED_KEY}: must be true or false (got {enabled!r})")
        enabled = False

    capex = block.get("capex")
    if capex is None:
        if enabled:
            errors.append(f"{path}.capex: required when {path}.enabled is true")
    elif not isinstance(capex, Mapping):
        errors.append(f"{path}.capex: must be a mapping (got {type(capex).__name__})")
    else:
        cpath = f"{path}.capex"
        _check_keys(capex, _CAPEX_KEYS, cpath, errors)
        _check_number(capex, "equipment_usd", cpath, errors, required=bool(enabled))
        for key in ("freight_usd", "optional_warranty_usd", "customs_duty_usd"):
            _check_number(capex, key, cpath, errors)
        _check_number(capex, "customs_duty_pct", cpath, errors, upper=1.0)
        dutiable = capex.get("warranty_is_dutiable")
        if dutiable is not None and not isinstance(dutiable, bool):
            errors.append(
                f"{cpath}.warranty_is_dutiable: must be true or false (got {dutiable!r})"
            )

    _check_number(
        block,
        "discharge_cycles_per_year",
        path,
        errors,
        required=bool(enabled),
        positive=True,
    )
    _check_number(block, "opex_lkr_per_year", path, errors)
    _check_number(block, "opex_escalation_pct", path, errors, upper=100.0)
    if enabled:
        try:
            specs = resolve_bess_specs(config) or []
        except (ValueError, TypeError, KeyError):
            specs = []  # a malformed technology block is reported by its own check
        n_capacity = sum(1 for s in specs if s.get("model") == "capacity_charge")
        if n_capacity > 1:
            errors.append(
                f"{path}: " + _MULTIPLE_BATTERIES_MESSAGE.format(n=n_capacity)
            )

    charging = block.get("charging")
    if charging is not None:
        hpath = f"{path}.charging"
        if not isinstance(charging, Mapping):
            errors.append(f"{hpath}: must be a mapping (got {type(charging).__name__})")
        else:
            _check_keys(charging, _CHARGING_KEYS, hpath, errors)
            if charging.get("tariff_lkr_per_kwh") is None:
                errors.append(
                    f"{hpath}.tariff_lkr_per_kwh: required when {hpath} is declared"
                )
            else:
                _check_number(charging, "tariff_lkr_per_kwh", hpath, errors)
            _check_number(
                charging,
                "round_trip_efficiency",
                hpath,
                errors,
                positive=True,
                upper=1.0,
            )

    schedule = block.get("warranty_schedule")
    if schedule is not None:
        wpath = f"{path}.warranty_schedule"
        if not isinstance(schedule, (list, tuple)):
            errors.append(f"{wpath}: must be a list of {{year, lkr}} events")
        else:
            for i, event in enumerate(schedule):
                epath = f"{wpath}[{i}]"
                if not isinstance(event, Mapping):
                    errors.append(f"{epath}: must be a mapping {{year, lkr}}")
                    continue
                _check_keys(event, _WARRANTY_EVENT_KEYS, epath, errors)
                year = _as_float(event.get("year"))
                if year is None or year != int(year) or year < 1:
                    errors.append(
                        f"{epath}.year: must be a positive whole operating year "
                        f"(got {event.get('year')!r})"
                    )
                if event.get("lkr") is None:
                    errors.append(f"{epath}.lkr: required")
                else:
                    _check_number(event, "lkr", epath, errors)

    sources = block.get("sources")
    if sources is not None and (
        not isinstance(sources, (list, tuple))
        or not all(isinstance(item, str) and item.strip() for item in sources)
    ):
        errors.append(f"{path}.sources: must be a list of non-empty strings")
    notes = block.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append(f"{path}.notes: must be text (got {type(notes).__name__})")


#: Status of a requested analysis in the pipeline result.
STATUS_RUN = "run"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_FAILED = "failed"

_BASIS = (
    "standalone battery project: its own cashflow, separate from the scenario's "
    "cashflow; no scenario KPI uses it"
)


def bess_economics_failure(reason: str) -> Dict[str, Any]:
    """The result entry for an opted-in analysis that could not run, with its reason.

    Args:
        reason: Why it could not run (the refused input, naming its path).

    Returns:
        ``{"status": "failed", "reason": ..., "basis": ..., "projects": []}``.
    """
    return {"status": STATUS_FAILED, "reason": reason, "basis": _BASIS, "projects": []}


def bess_economics_result(
    config: Mapping[str, Any], *, discount_rate: float, project_years: int
) -> Optional[Dict[str, Any]]:
    """The pipeline's ``bess_project_economics`` entry for any scenario (#1774).

    Returns ``None`` when the scenario does not opt in, so the pipeline adds no key and the
    result is byte-identical. When it opts in, returns ``{"status": "run", "projects": [...]}``
    with one :meth:`BessProjectEconomics.as_dict` per capacity-charge battery, or
    ``{"status": "not_applicable", "reason": ...}`` when the scenario declares no
    capacity-charge battery, so an opted-in analysis is never dropped silently.

    Args:
        config: The resolved scenario config.
        discount_rate: The scenario's project discount rate (decimal).
        project_years: The scenario's project life in years.

    Returns:
        The result entry, or ``None`` when the scenario does not opt in.

    Raises:
        ValueError: A required ``bess_economics`` input is missing or invalid.
    """
    if not bess_economics_requested(config):
        return None
    projects = compute_bess_project_economics(
        config, discount_rate=discount_rate, project_years=project_years
    )
    basis = _BASIS
    if not projects:
        return {
            "status": STATUS_NOT_APPLICABLE,
            "reason": (
                "bess_economics is enabled but generation.technologies declares no "
                "type: bess technology with revenue_model capacity_charge"
            ),
            "basis": basis,
            "projects": [],
        }
    return {
        "status": STATUS_RUN,
        "basis": basis,
        "currency_basis": CURRENCY_BASIS,
        "discount_rate": float(discount_rate),
        "project_years": int(project_years),
        "projects": [project.as_dict() for project in projects],
    }


__all__ = [
    "CURRENCY_BASIS",
    "LandedCapex",
    "ChargingCostSpec",
    "BessProjectEconomics",
    "bess_economics_requested",
    "resolve_landed_capex",
    "capacity_charge_effective_cost_curve",
    "validate_bess_economics_block",
    "bess_economics_result",
    "bess_economics_failure",
    "resolve_charging_cost_spec",
    "charging_cost_lkr_for_year",
    "compute_bess_project_economics",
]
