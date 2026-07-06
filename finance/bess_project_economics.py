"""Standalone BESS project economics — landed capex, CEB effective-cost, IRR/NPV/LCOS.

This module turns the **real 2025 Sri Lankan commercial inputs** for a standalone battery
project into workable project economics, for the CEB distributed-BESS tender case and the
DutchBay ~11 MW Kalpitiya BESS. It is the "put it together" layer over the existing BESS
pieces, adding the four things issue #863 asks for that were not modelled anywhere:

1. **Landed capex** from a Huawei-LUNA2000-style **CIF quote structure** (equipment CIF +
   optional 15-yr warranties/service + freight) + a **Sri Lanka customs/duty layer**
   ("extra at actual", buyer scope) + a **USD -> LKR FX** translation. The CIF price is
   NOT the installed cost; the duty/freight/FX layers are what the buyer actually pays.
2. **CEB effective-cost curve** — the tender's own methodology,
   ``effective LKR/kWh = annual capacity charge / degradation-adjusted annual discharge``,
   over life (rising as energy degrades while the flat charge stays constant). Per the CEB
   ``BESS Energy Cost`` doc this **EXCLUDES the charging cost** — that omission is disclosed
   in the result, not hidden.
3. **The separate charging-cost lever** the CEB method omits:
   ``energy_to_charge_mwh x charging_tariff_lkr_per_kwh x 1/RTE`` (the round-trip loss makes
   the charge-side energy larger than the discharge-side). Required for a full P&L.
4. **A standalone BESS cashflow -> IRR / NPV / LCOS**: ``landed capex`` at t0, then per year
   ``capacity revenue - opex - charging cost - warranty draws - augmentation capex``, plus a
   read-only LCOS view. IRR/NPV come from :mod:`finance.irr` (R7 single source of truth); the
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

This module adds ONLY the capex-ingest, the CEB effective-cost curve, the charging lever, and
the standalone-cashflow assembly. It computes the discharge/SoH energy the SAME way the LCOS
and revenue paths do, so the three cannot diverge.

KPI-NEUTRAL / DEFAULT-OFF (the cardinal rule)
---------------------------------------------
This is a **standalone, opt-in analysis** off the committed cashflow path. It:

* is reached ONLY through :func:`compute_bess_project_economics`, which nothing on the
  committed 5th-gen cashflow path calls;
* refuses to run unless the scenario carries an explicit ``bess_economics.enabled: true``
  opt-in (:func:`bess_economics_requested`) — absent that flag it does nothing;
* touches nothing that feeds CFADS/IRR/DSCR of a committed generation scenario.

Wiring these BESS economics INTO a committed multi-tech case (so the capacity charge, the
degradation, and the charging cost move the project's KPIs) is a SEPARATE, user-gated step —
NOT this module. See the module ``__doc__`` note and issue #863.

PROVENANCE (honest, no fabricated figures)
------------------------------------------
The default CIF line items, the customs/duty basis, the capacity-charge band, the 400
cycles/yr and 2.5%/yr degradation, and the "charging cost excluded" caveat all come from the
real primary-source docs for the CEB ``TR/REP&PM/ICB/2025/003/C`` 160 MW / 640 MWh (16-site)
standalone-BESS procurement: the Huawei LUNA2000 CIF price offer (``251002 - Price Offer -
CIF Basis.pdf``: equipment sub-total $4,829,679.59, optional service $907,264.63), the CEB
tender results (``TENDER RESULTS.xlsx``: capacity charge ~1.46-2.4M LKR/MW/month), and the
CEB energy-cost methodology (``BESS Energy Cost - CEB.pdf``: 42.57 MWh @ COD, 400 cycles/yr,
97.5%->62.5% degradation, "Charging Cost NOT considered"). A BESS is NOT a
``capacity_factor x tariff`` generator; nothing here treats it as one. Nothing in this module
supplies a default capex or duty rate silently — a scenario must declare them (CESSPIT).
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
#: Default discharge cycles/year for the CEB effective-cost basis (CEB doc: 400/yr ~ 1.1/day).
_DEFAULT_CYCLES_PER_YEAR = 400.0
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
# 1. Landed capex — Huawei-CIF structure + SL customs/duty + USD->LKR FX
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LandedCapex:
    """The buyer's landed capex for a CIF-quoted BESS, in both USD and LKR.

    The CIF equipment price is only the ex-tax, ex-duty starting point; the buyer additionally
    pays freight (if not already CIF-included), Sri Lanka customs/duty "at actual", and bears
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
    """Build the buyer's landed capex from a CIF quote structure + SL duty + FX.

    Reads ``bess_economics.capex``:

    * ``equipment_usd`` (REQUIRED) — the CIF equipment sub-total (e.g. Huawei $4,829,679.59).
    * ``freight_usd`` (optional, default 0) — freight if quoted separately from CIF.
    * ``optional_warranty_usd`` (optional, default 0) — 15-yr warranties/service financed as
      capex (e.g. Huawei $907,264.63). NOT dutiable by default (a service line, not goods);
      set ``warranty_is_dutiable: true`` to include it in the dutiable base.
    * ``customs_duty_pct`` (optional, default 0) — SL customs/duty as a fraction of the
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
        notes.append("SL customs/duty taken from an explicit customs_duty_usd amount.")
    else:
        duty_pct = _optional_ratio(
            capex.get("customs_duty_pct"),
            block=blk,
            field_name="customs_duty_pct",
            default=0.0,
        )
        customs_duty_usd = dutiable_base * duty_pct
        notes.append(
            f"SL customs/duty = {duty_pct:.4g} x the dutiable base "
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
# 2. CEB effective-cost curve (LKR/kWh) — charging cost EXCLUDED (the CEB method)
# ─────────────────────────────────────────────────────────────────────────────


def _discharge_mwh_for_year(
    spec: Dict[str, Any],
    year_index: int,
    *,
    energy_per_cycle_mwh: float,
    cycles_per_year: float,
) -> float:
    """Degradation-adjusted annual DISCHARGE energy (MWh) for one BESS in one year.

    ``energy_per_cycle_mwh x cycles_per_year x soh(year)`` — the same nameplate-energy x
    state-of-health basis the CEB energy-cost doc uses (42.57 MWh @ COD x 400 cycles/yr, then
    scaled by the 97.5%->62.5% SoH curve). The SoH comes from
    :func:`finance.bess_revenue.mdsc_soh_for_year` so it is IDENTICAL to the revenue/LCOS
    curves.
    """
    soh = mdsc_soh_for_year(spec, year_index)
    return energy_per_cycle_mwh * cycles_per_year * soh


def ceb_effective_cost_curve(
    config: Mapping[str, Any], *, years: int
) -> Optional[List[Dict[str, Any]]]:
    """The CEB effective-cost curve for every capacity-charge BESS (LKR/kWh over life).

    Replicates the CEB ``BESS Energy Cost`` methodology per operating year::

        effective_lkr_per_kwh(t) = annual_capacity_charge_lkr(t) / annual_discharge_kwh(t)

    where ``annual_capacity_charge_lkr`` is the flat charge x the year-indexed SoH (from
    :func:`finance.bess_revenue.bess_revenue_lkr_for_year`) and ``annual_discharge_kwh`` is the
    degradation-adjusted discharge (``energy_per_cycle x cycles/yr x soh(t) x 1000``). Both
    numerator and denominator fade with the SAME SoH, so — matching the CEB result — the cost
    RISES over life only because the discharge basis falls faster than the (SoH-scaled) charge
    where the charge does not fade; with an ``mdsc_fade`` opt-in they share the fade and the
    curve is flatter. Charge cycles/yr default to 400 (the CEB doc); overridable via
    ``bess_economics.discharge_cycles_per_year``.

    **CHARGING COST IS EXCLUDED** — exactly as the CEB doc states ("Charging Cost NOT
    considered"). Each row carries that disclosure; the charging cost is a SEPARATE lever
    (:func:`charging_cost_lkr_for_year`).

    Returns ``None`` when the scenario has no capacity-charge BESS (energy-tariff BESSes are
    not part of the CEB capacity-charge method). ``lkr_per_kwh`` is ``None`` for a year whose
    discharge basis is zero (undefined, not silently zero).

    Args:
        config: The scenario config.
        years: The number of operating years to tabulate.

    Returns:
        A list of ``{technology, year, capacity_charge_lkr, discharge_mwh, lkr_per_kwh,
        charging_excluded, note}`` rows (one per capacity-charge BESS per year), or ``None``.
    """
    specs = resolve_bess_specs(config)
    if not specs:
        return None
    cyc = _as_float(_nested_get(config, _ECONOMICS_BLOCK, "discharge_cycles_per_year"))
    cycles_per_year = cyc if (cyc is not None and cyc > 0) else _DEFAULT_CYCLES_PER_YEAR

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
                        "CEB method: capacity charge / degradation-adjusted discharge; "
                        "CHARGING COST EXCLUDED (add charging_cost_lkr_for_year for a full "
                        "P&L)."
                    ),
                }
            )
    if not have_capacity_charge:
        return None
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 3. Charging-cost lever (the piece the CEB method omits)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChargingCostSpec:
    """The (opt-in) charging-cost lever the CEB effective-cost method deliberately omits.

    A capacity-charge BESS must be CHARGED before it can discharge; the charge-side energy is
    ``discharge / RTE`` (the round-trip loss), priced at the ``charging_tariff_lkr_per_kwh``
    (the grid/off-peak energy the operator buys). This is ``0`` unless a scenario opts in with
    ``bess_economics.charging`` — so a run that does not model charging still gets a coherent
    (CEB-style, charging-excluded) result.
    """

    charging_tariff_lkr_per_kwh: float
    round_trip_efficiency: float
    cycles_per_year: float


def resolve_charging_cost_spec(config: Mapping[str, Any]) -> Optional[ChargingCostSpec]:
    """Resolve the charging-cost lever, or ``None`` when the scenario does not opt in.

    Reads ``bess_economics.charging``: ``tariff_lkr_per_kwh`` (REQUIRED when the block is
    present — the price of charge energy), ``round_trip_efficiency`` (optional, default 0.85 —
    NREL ATB 2024, matching :mod:`finance.bess_revenue`), and ``cycles_per_year`` (optional,
    default 400 — the CEB discharge basis). Absent block => ``None`` => no charging cost.
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
    cyc = _as_float(charging.get("cycles_per_year"))
    cycles_per_year = cyc if (cyc is not None and cyc > 0) else _DEFAULT_CYCLES_PER_YEAR
    return ChargingCostSpec(
        charging_tariff_lkr_per_kwh=tariff,
        round_trip_efficiency=rte,
        cycles_per_year=cycles_per_year,
    )


def charging_cost_lkr_for_year(
    charging: Optional[ChargingCostSpec], discharge_mwh: float
) -> float:
    """The charging cost (LKR) for one year's discharge, or ``0`` with no charging lever.

    ``charge_energy_mwh = discharge_mwh / RTE`` (the round-trip loss inflates the charge-side
    energy above what is discharged), priced at ``tariff_lkr_per_kwh``::

        charging_cost_lkr = (discharge_mwh / RTE) x 1000 x tariff_lkr_per_kwh

    Returns ``0.0`` when ``charging`` is ``None`` (the CEB-style, charging-excluded case).
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
    ``capacity revenue - opex - charging cost - warranty draw - augmentation capex``. IRR is
    the periodic project IRR of that series; NPV is its present value at ``discount_rate``.
    ``lcos`` is the read-only LCOS view (USD/MWh) for the BESS. All monetary figures are LKR
    except the LCOS (USD/MWh, per its own contract) and the landed capex (both).
    """

    technology: str
    landed_capex: LandedCapex
    discount_rate: float
    horizon_years: int
    cashflow_lkr: Tuple[float, ...]
    revenue_lkr: Tuple[float, ...]
    opex_lkr: Tuple[float, ...]
    charging_cost_lkr: Tuple[float, ...]
    augmentation_capex_lkr: Tuple[float, ...]
    irr: Optional[float]
    npv_lkr: float
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
            "revenue_lkr": list(self.revenue_lkr),
            "opex_lkr": list(self.opex_lkr),
            "charging_cost_lkr": list(self.charging_cost_lkr),
            "augmentation_capex_lkr": list(self.augmentation_capex_lkr),
            "irr": self.irr,
            "npv_lkr": self.npv_lkr,
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

    then computes the periodic project IRR (:func:`finance.irr.irr`) and NPV
    (:func:`finance.irr.npv` at ``discount_rate``) of that series, and attaches the CEB
    effective-cost curve and the read-only LCOS (:func:`finance.bess_lcos.compute_lcos`).

    Opex, the warranty draw schedule, and the charging tariff are all opt-in
    ``bess_economics.*`` inputs; absent, they are zero (a clean capex->capacity-revenue view).
    Revenue and augmentation reuse :mod:`finance.bess_revenue`; the discharge basis reuses the
    SAME SoH curve as the effective-cost/LCOS paths, so nothing can diverge.

    Args:
        config: The scenario config (must carry an enabled ``bess_economics`` block).
        discount_rate: The rate to discount the NPV at (decimal, e.g. 0.10). The caller
            resolves it (the project's WACC/hurdle for a standalone BESS).
        project_years: The number of operating years to model.

    Returns:
        One :class:`BessProjectEconomics` per capacity-charge BESS, or ``None``.

    Raises:
        ValueError: A required ``bess_economics`` input is missing/invalid, or the FX/rate
            arguments are non-finite.
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
    if not specs:
        return None

    # Year-0 FX spot from the project's own FX routine — no hardcoded rate. A standalone BESS
    # economics run must therefore declare an fx block (CESSPIT), exactly like the cashflow.
    fx_curve = _fx_curve(dict(config), project_years)
    fx0 = float(fx_curve[0])
    landed = resolve_landed_capex(config, fx_rate_lkr_per_usd=fx0)

    charging = resolve_charging_cost_spec(config)
    cyc = _as_float(_nested_get(config, _ECONOMICS_BLOCK, "discharge_cycles_per_year"))
    discharge_cycles = (
        cyc if (cyc is not None and cyc > 0) else _DEFAULT_CYCLES_PER_YEAR
    )

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

    effective_cost = ceb_effective_cost_curve(config, years=project_years)
    lcos_specs = resolve_lcos_specs(config) or []
    lcos_by_tech = {s.technology: s for s in lcos_specs}

    out: List[BessProjectEconomics] = []
    for spec in specs:
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
            # Augmentation capex converted at the year's FX rate (reuse the shared routine).
            fx_year = float(fx_curve[t]) if t < len(fx_curve) else fx0
            aug = bess_augmentation_capex_lkr_for_year([spec], t, fx_year)
            warranty = warranty_draws.get(t + 1, 0.0)
            revenue_series.append(revenue)
            opex_series.append(opex)
            charging_series.append(charge_cost)
            aug_series.append(aug)
            cashflow.append(revenue - opex - charge_cost - aug - warranty)

        project_irr = irr(cashflow)
        project_npv = npv(discount_rate, cashflow)
        lcos_res: Optional[LcosResult] = None
        if name in lcos_by_tech:
            lcos_res = compute_lcos(
                lcos_by_tech[name], wacc=discount_rate, project_years=project_years
            )

        notes = [
            "STANDALONE, OPT-IN analysis — off the committed cashflow path; wiring these "
            "economics into a committed multi-tech case is a separate, user-gated step.",
            "landed capex from the CIF quote structure + SL customs/duty + USD->LKR FX; "
            "the CIF price is ex-tax/ex-duty (buyer bears duty 'at actual').",
        ]
        if charging is None:
            notes.append(
                "charging cost NOT modelled (CEB effective-cost method excludes it); opt in "
                "via bess_economics.charging for a full P&L."
            )
        out.append(
            BessProjectEconomics(
                technology=name,
                landed_capex=landed,
                discount_rate=float(discount_rate),
                horizon_years=horizon,
                cashflow_lkr=tuple(cashflow),
                revenue_lkr=tuple(revenue_series),
                opex_lkr=tuple(opex_series),
                charging_cost_lkr=tuple(charging_series),
                augmentation_capex_lkr=tuple(aug_series),
                irr=project_irr,
                npv_lkr=project_npv,
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


__all__ = [
    "LandedCapex",
    "ChargingCostSpec",
    "BessProjectEconomics",
    "bess_economics_requested",
    "resolve_landed_capex",
    "ceb_effective_cost_curve",
    "resolve_charging_cost_spec",
    "charging_cost_lkr_for_year",
    "compute_bess_project_economics",
]
