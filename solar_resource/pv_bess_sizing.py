"""Seeded Monte Carlo sizing of the Blue Whale solar + BESS unit (``MRM-01``, ``TEST-03``).

The turbine is fixed (Blue Whale PR 1). This module chooses the PV DC capacity and the BESS
energy of the solar + BESS unit on a decision grid, under cited and uncertain prices and
uncertain yield, round-trip efficiency and battery fade. It adds no finance mathematics:

* the unit is dispatched hourly with the rules of :mod:`solar_resource.pv_bess_dispatch`
  (PR 2), evaluated for many trials and years at once by :func:`dispatch_columns`, an
  array form of that dispatcher which must reproduce it (``TEST-01``: the pre-existing
  dispatcher is the oracle);
* each trial is mapped onto the engine's fields by PR 2's
  :func:`~solar_resource.pv_bess_dispatch.engine_representation`, and the whole Blue Whale
  scenario is evaluated through the gateway
  :func:`analytics.evaluation_v14.evaluate_with_overrides` (``ARCH-04``,
  ``FRAMEWORK-03``). Project NPV and IRR therefore come from the engine, which takes them
  from ``finance.irr`` (``ARCH-02``);
* a secondary, unit-only pre-tax NPV and IRR (the unit's capex, its dispatched revenue and
  its O&M, no tax or debt) use :func:`finance.irr.npv` and :func:`finance.irr.irr`.

The module sits in ``solar_resource`` beside PR 2's dispatcher, whose rules it applies. It
reaches the analytics layer only through the gateway, the LHS sampler and PR 1/PR 2's
layout modules, so it adds no package edge to ``docs/architecture_import_graph.mmd``.

Sampling reuses the repository's Latin Hypercube sampler
(:func:`analytics.mc.samplers.generate_lhs_samples`) with an explicit seed. The same draws
are used at every grid point (common random numbers), so differences between sizes are not
sampling noise. One model evaluation is one dispatched 20-year path plus one engine
evaluation; :attr:`SizingRun.effective_evaluations` counts them truthfully.

Statistics follow the project-finance exceedance convention: ``p50`` is the median and
``p90`` is the value exceeded in 90% of trials (the 10th percentile); ``p10`` is exceeded
in 10% (the 90th percentile).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from statistics import NormalDist
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.mc.samplers import generate_lhs_samples
from finance.irr import irr, npv
from solar_resource.pv_bess_dispatch import (
    SUPPORTED_RATES,
    AnnualEnergy,
    BessConfig,
    DispatchConfig,
    EngineRepresentation,
    TariffConfig,
    WindBlock,
    Window,
    engine_representation,
    window_index,
)

FloatArray = npt.NDArray[np.float64]

_KWH_PER_MWH = 1000.0
#: The metrics summarised for every grid point.
METRICS = (
    "project_npv",
    "project_irr",
    "equity_npv",
    "equity_irr",
    "min_dscr",
    "unit_pretax_npv_usd",
    "unit_pretax_irr",
)
#: Statistics an objective may name.
STATISTICS = ("p50", "p90", "p10", "mean")


def _strict(raw: Mapping[str, Any], keys: Sequence[str], where: str) -> None:
    """Refuse a mapping whose keys are not exactly ``keys`` (``FRAMEWORK-02``)."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"{where} must be a mapping")
    missing = sorted(set(keys) - set(raw))
    extra = sorted(set(raw) - set(keys))
    if missing or extra:
        raise ValueError(
            f"{where}: missing keys {missing} and unknown keys {extra}; "
            f"expected exactly {sorted(keys)}."
        )


def _kpi(kpis: Mapping[str, Any], key: str) -> float:
    """A KPI as a float; an undefined (``None``) KPI is NaN and drops out of statistics.

    FIN-01 keeps 0.0 and undefined apart, and #1525 proposes reporting an unresolved
    project IRR as undefined, so ``None`` must not be read as 0.0.
    """
    value = kpis.get(key)
    return float("nan") if value is None else float(value)


def _num(value: Any, where: str, *, lo: float = -math.inf) -> float:
    """A finite float at or above ``lo``."""
    if isinstance(value, bool):
        raise ValueError(f"{where} must be a number; got {value!r}")
    out = float(value)
    if not math.isfinite(out) or out < lo:
        raise ValueError(f"{where} out of range; got {value!r}")
    return out


# ---------------------------------------------------------------------------
# Distributions and prices
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Triangular:
    """A triangular distribution.

    Attributes:
        low, mode, high: Bounds and mode, ``low <= mode <= high`` and ``low < high``.
    """

    low: float
    mode: float
    high: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], where: str) -> "Triangular":
        """Build from ``{low, mode, high}``, refusing an inverted or empty range."""
        _strict(raw, ("low", "mode", "high"), where)
        out = cls(*(_num(raw[k], f"{where}.{k}") for k in ("low", "mode", "high")))
        if not out.low <= out.mode <= out.high or out.low >= out.high:
            raise ValueError(f"{where}: need low <= mode <= high and low < high")
        return out

    def ppf(self, u: FloatArray) -> FloatArray:
        """Inverse CDF at probabilities ``u`` in ``[0, 1]``."""
        a, c, b = self.low, self.mode, self.high
        fc = (c - a) / (b - a)
        u = np.clip(np.asarray(u, dtype=np.float64), 0.0, 1.0)
        left = a + np.sqrt(u * (b - a) * (c - a))
        right = b - np.sqrt((1.0 - u) * (b - a) * (b - c))
        return np.asarray(np.where(u < fc, left, right), dtype=np.float64)


@dataclass(frozen=True)
class InverterSpec:
    """A utility string inverter, from its datasheet.

    Attributes:
        model: Model name.
        max_dc_voltage_v, mppt_min_v, mppt_max_v, start_voltage_v: Voltage limits.
        max_current_per_mppt_a: Operating input current limit per MPPT.
        max_short_circuit_current_per_mppt_a: Short-circuit input limit per MPPT.
        mppt_count: MPP trackers.
        max_inputs_per_mppt: String inputs on each tracker.
        nominal_ac_kw, max_ac_kva: AC ratings.
        european_efficiency: Weighted efficiency (the PVWatts nominal efficiency).
    """

    model: str
    max_dc_voltage_v: float
    mppt_min_v: float
    mppt_max_v: float
    start_voltage_v: float
    max_current_per_mppt_a: float
    max_short_circuit_current_per_mppt_a: float
    mppt_count: int
    max_inputs_per_mppt: Tuple[int, ...]
    nominal_ac_kw: float
    max_ac_kva: float
    european_efficiency: float


@dataclass(frozen=True)
class Pricing:
    """Frozen, cited prices (``conf/blue_whale_pv_bess_pricing.yaml``).

    Attributes:
        module_fob_usd_per_wp: Module price, FOB China.
        module_delivery_usd_per_wp: Freight, insurance and inland transport.
        inverter: The matched inverter.
        inverter_usd_per_wac: Inverter price per W of nominal AC rating.
        bop_usd_per_wp: PV balance of plant and EPC.
        bess_usd_per_kwh: BESS all-in price per kWh of nameplate energy.
        wind_capex_usd_per_kw: The fixed turbine's placeholder.
        pv_opex_usd_per_kwp_year, bess_opex_usd_per_kwh_year: O&M placeholders.
    """

    module_fob_usd_per_wp: Triangular
    module_delivery_usd_per_wp: float
    inverter: InverterSpec
    inverter_usd_per_wac: Triangular
    bop_usd_per_wp: Triangular
    bess_usd_per_kwh: Triangular
    wind_capex_usd_per_kw: float
    pv_opex_usd_per_kwp_year: float
    bess_opex_usd_per_kwh_year: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Pricing":
        """Build from the pricing config, refusing a missing or unknown key."""
        _strict(
            raw,
            (
                "schema_version",
                "retrieved",
                "currency",
                "sources",
                "fx",
                "pv_module",
                "inverter",
                "pv_bop_epc",
                "bess",
                "wind",
                "opex",
            ),
            "pricing",
        )
        if raw["schema_version"] != "blue_whale_pv_bess_pricing_v1":
            raise ValueError(
                "pricing.schema_version must be blue_whale_pv_bess_pricing_v1"
            )
        if raw["currency"] != "USD":
            raise ValueError("pricing.currency must be USD")
        sources = raw["sources"]
        if not isinstance(sources, Mapping) or not sources:
            raise ValueError("pricing.sources must be a non-empty mapping")
        for name, src in sources.items():
            if not isinstance(src, Mapping) or not src.get("verbatim"):
                raise ValueError(f"pricing.sources.{name} needs a verbatim figure")
            if "url" not in src and "files" not in src:
                raise ValueError(f"pricing.sources.{name} needs a url or files")
        mod = raw["pv_module"]
        _strict(mod, ("fob_usd_per_wp", "delivery_usd_per_wp"), "pricing.pv_module")
        inv = raw["inverter"]
        inv_keys = [f.name for f in InverterSpec.__dataclass_fields__.values()]
        _strict(inv, [*inv_keys, "source", "usd_per_wac"], "pricing.inverter")
        if inv["source"] not in sources:
            raise ValueError("pricing.inverter.source must name a source")
        inputs = tuple(int(n) for n in inv["max_inputs_per_mppt"])
        if len(inputs) != int(inv["mppt_count"]):
            raise ValueError("pricing.inverter: one input count per MPPT")
        spec = InverterSpec(
            model=str(inv["model"]),
            max_dc_voltage_v=_num(inv["max_dc_voltage_v"], "inverter.max_dc_voltage_v"),
            mppt_min_v=_num(inv["mppt_min_v"], "inverter.mppt_min_v"),
            mppt_max_v=_num(inv["mppt_max_v"], "inverter.mppt_max_v"),
            start_voltage_v=_num(inv["start_voltage_v"], "inverter.start_voltage_v"),
            max_current_per_mppt_a=_num(
                inv["max_current_per_mppt_a"], "inverter.max_current_per_mppt_a"
            ),
            max_short_circuit_current_per_mppt_a=_num(
                inv["max_short_circuit_current_per_mppt_a"],
                "inverter.max_short_circuit_current_per_mppt_a",
            ),
            mppt_count=int(inv["mppt_count"]),
            max_inputs_per_mppt=inputs,
            nominal_ac_kw=_num(inv["nominal_ac_kw"], "inverter.nominal_ac_kw", lo=0.0),
            max_ac_kva=_num(inv["max_ac_kva"], "inverter.max_ac_kva", lo=0.0),
            european_efficiency=_num(
                inv["european_efficiency"], "inverter.european_efficiency", lo=0.5
            ),
        )
        if spec.european_efficiency > 1.0:
            raise ValueError("inverter.european_efficiency must be <= 1")
        bop = raw["pv_bop_epc"]
        _strict(bop, ("usd_per_wp",), "pricing.pv_bop_epc")
        bess = raw["bess"]
        _strict(
            bess,
            (
                "all_in_usd_per_kwh",
                "equipment_usd_per_kwh_base",
                "bop_usd_per_kwh_base",
                "augmentation_reserve_usd_per_kwh_base",
                "land_and_auxiliaries_share_base",
            ),
            "pricing.bess",
        )
        # The public NSO 250 build-up must reproduce the all-in base it states.
        built = (
            float(bess["equipment_usd_per_kwh_base"])
            + float(bess["bop_usd_per_kwh_base"])
            + float(bess["augmentation_reserve_usd_per_kwh_base"])
        ) / (1.0 - float(bess["land_and_auxiliaries_share_base"]))
        all_in = Triangular.from_mapping(
            bess["all_in_usd_per_kwh"], "pricing.bess.all_in_usd_per_kwh"
        )
        if abs(built - all_in.mode) > 0.01:
            raise ValueError(
                f"pricing.bess: build-up {built:.4f} does not give the all-in mode "
                f"{all_in.mode}"
            )
        wind = raw["wind"]
        _strict(
            wind,
            ("capex_usd_per_kw", "source", "public_range_usd_per_kw"),
            "pricing.wind",
        )
        opex = raw["opex"]
        _strict(opex, ("pv_usd_per_kwp_year", "bess_usd_per_kwh_year"), "pricing.opex")
        return cls(
            module_fob_usd_per_wp=Triangular.from_mapping(
                mod["fob_usd_per_wp"], "pricing.pv_module.fob_usd_per_wp"
            ),
            module_delivery_usd_per_wp=_num(
                mod["delivery_usd_per_wp"], "pv_module.delivery_usd_per_wp", lo=0.0
            ),
            inverter=spec,
            inverter_usd_per_wac=Triangular.from_mapping(
                inv["usd_per_wac"], "pricing.inverter.usd_per_wac"
            ),
            bop_usd_per_wp=Triangular.from_mapping(
                bop["usd_per_wp"], "pricing.pv_bop_epc.usd_per_wp"
            ),
            bess_usd_per_kwh=all_in,
            wind_capex_usd_per_kw=_num(
                wind["capex_usd_per_kw"], "wind.capex_usd_per_kw", lo=0.0
            ),
            pv_opex_usd_per_kwp_year=_num(
                opex["pv_usd_per_kwp_year"], "opex.pv_usd_per_kwp_year", lo=0.0
            ),
            bess_opex_usd_per_kwh_year=_num(
                opex["bess_usd_per_kwh_year"], "opex.bess_usd_per_kwh_year", lo=0.0
            ),
        )


def pv_capex_usd(
    *,
    dc_mwp: float,
    inverter_count: int,
    inverter_kw: float,
    module_fob_usd_per_wp: float,
    module_delivery_usd_per_wp: float,
    inverter_usd_per_wac: float,
    bop_usd_per_wp: float,
) -> float:
    """PV capex: modules and BoP per Wp, inverters per W of their nominal AC rating."""
    wp = dc_mwp * 1.0e6
    return (
        wp * (module_fob_usd_per_wp + module_delivery_usd_per_wp + bop_usd_per_wp)
        + inverter_count * inverter_kw * 1000.0 * inverter_usd_per_wac
    )


# ---------------------------------------------------------------------------
# Inverter matching
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InverterMatch:
    """The inverter fleet for one array and the datasheet checks.

    Attributes:
        model: Inverter model.
        inverter_count: Units, so that their nominal AC rating covers the unit's AC.
        fleet_nominal_ac_mw: Units x nominal AC.
        strings: Strings of the array.
        strings_per_inverter_max: Strings on the most loaded unit.
        strings_per_mppt_max: Strings a tracker can take within its current limit and its
            input count.
        string_capacity_per_inverter: ``sum(min(inputs, current-limited strings))``.
        checks: Each check and whether it passes.
        ok: Every check passes.
    """

    model: str
    inverter_count: int
    fleet_nominal_ac_mw: float
    strings: int
    strings_per_inverter_max: int
    strings_per_mppt_max: int
    string_capacity_per_inverter: int
    checks: Dict[str, bool]
    ok: bool


def match_inverter(
    inverter: InverterSpec,
    *,
    strings: int,
    voc_cold_v: float,
    vmp_hot_v: float,
    vmp_stc_v: float,
    imp_a: float,
    isc_a: float,
    ac_capacity_mw: float,
) -> InverterMatch:
    """Size the inverter fleet for the array and check it against the datasheet.

    Args:
        inverter: The datasheet.
        strings: Strings in the array.
        voc_cold_v: String open-circuit voltage at the design minimum cell temperature.
        vmp_hot_v: String MPP voltage at the design maximum cell temperature.
        vmp_stc_v: String MPP voltage at STC.
        imp_a, isc_a: Module MPP and short-circuit current at STC.
        ac_capacity_mw: The unit's AC capacity.

    Returns:
        The fleet and its checks.
    """
    count = math.ceil(ac_capacity_mw * 1000.0 / inverter.nominal_ac_kw - 1e-12)
    by_current = int(inverter.max_current_per_mppt_a // imp_a)
    by_isc = int(inverter.max_short_circuit_current_per_mppt_a // isc_a)
    per_mppt = [min(n, by_current, by_isc) for n in inverter.max_inputs_per_mppt]
    capacity = sum(per_mppt)
    per_inverter = math.ceil(strings / count)
    checks = {
        "voc_cold_within_max_dc_voltage": voc_cold_v <= inverter.max_dc_voltage_v,
        "voc_cold_within_mppt_max": voc_cold_v <= inverter.mppt_max_v,
        "vmp_hot_above_mppt_min": vmp_hot_v >= inverter.mppt_min_v,
        "vmp_hot_above_start_voltage": vmp_hot_v >= inverter.start_voltage_v,
        "vmp_stc_within_mppt_range": inverter.mppt_min_v
        <= vmp_stc_v
        <= inverter.mppt_max_v,
        "strings_fit_inputs_within_current_limit": per_inverter <= capacity,
        "fleet_covers_ac_capacity": count * inverter.nominal_ac_kw
        >= ac_capacity_mw * 1000.0 - 1e-9,
    }
    return InverterMatch(
        model=inverter.model,
        inverter_count=count,
        fleet_nominal_ac_mw=count * inverter.nominal_ac_kw / 1000.0,
        strings=strings,
        strings_per_inverter_max=per_inverter,
        strings_per_mppt_max=max(per_mppt),
        string_capacity_per_inverter=capacity,
        checks=checks,
        ok=all(checks.values()),
    )


# ---------------------------------------------------------------------------
# Array form of the PR 2 dispatcher
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ColumnSums:
    """Annual totals of a set of dispatched columns (one value per column, MWh).

    Attributes:
        pv_mwh: PV offered.
        charge_mwh: PV into the battery.
        discharge_mwh_by_window: Battery export per window.
        pv_export_mwh_by_window: PV direct export per window and ``"outside"``.
        curtailed_mwh: PV not taken.
        soc_end_mwh: Stored energy at the end of the year.
        initial_soc_mwh: Stored energy at the start (the cyclic fixed point).
        iterations: Passes to converge, per column.
    """

    pv_mwh: FloatArray
    charge_mwh: FloatArray
    discharge_mwh_by_window: Dict[str, FloatArray]
    pv_export_mwh_by_window: Dict[str, FloatArray]
    curtailed_mwh: FloatArray
    soc_end_mwh: FloatArray
    initial_soc_mwh: FloatArray
    iterations: npt.NDArray[np.int64]


def dispatch_columns(
    pv_base_mw: FloatArray,
    timestamps_utc: Any,
    *,
    scale: FloatArray,
    energy_mwh: FloatArray,
    round_trip_efficiency: FloatArray,
    bess: BessConfig,
    cfg: DispatchConfig,
    curtailment_fraction: float = 0.0,
) -> ColumnSums:
    """Dispatch many columns at once, column ``j`` being PV ``pv_base_mw * scale[j]``.

    Each column follows :func:`solar_resource.pv_bess_dispatch.dispatch` exactly, with its
    own battery energy and round-trip efficiency; ``bess`` supplies the power, the charge
    efficiency and the state-of-charge fractions. Steps with no PV outside every window
    change nothing and are skipped. ``curtailment_fraction`` (a sensitivity, 0 in the base
    case) removes that share of the PV exported directly outside the windows.

    Raises:
        ValueError: On mismatched shapes, a non-physical input, or a cyclic state that does
            not converge.
    """
    import pandas as pd

    pv = np.asarray(pv_base_mw, dtype=np.float64)
    idx = pd.DatetimeIndex(timestamps_utc)
    if pv.shape != (len(idx),) or pv.size < 2:
        raise ValueError("pv_base_mw must be one value per timestamp")
    if ((idx[1:] - idx[:-1]) != pd.Timedelta(hours=1)).any():
        raise ValueError("the dispatcher needs consecutive hourly timestamps")
    if (pv < 0).any() or not np.isfinite(pv).all():
        raise ValueError("pv_base_mw must be finite and non-negative")
    s = np.asarray(scale, dtype=np.float64)
    e = np.asarray(energy_mwh, dtype=np.float64)
    rte = np.asarray(round_trip_efficiency, dtype=np.float64)
    if not (s.shape == e.shape == rte.shape) or s.ndim != 1 or s.size == 0:
        raise ValueError("scale, energy_mwh and round_trip_efficiency must match")
    if (s < 0).any() or (e <= 0).any() or (rte <= 0).any() or (rte > 1).any():
        raise ValueError("scale >= 0, energy_mwh > 0 and 0 < RTE <= 1 are required")
    if (rte > bess.charge_efficiency + 1e-15).any():
        raise ValueError("round_trip_efficiency must not exceed charge_efficiency")
    if not 0.0 <= curtailment_fraction < 1.0:
        raise ValueError("curtailment_fraction must lie in [0, 1)")
    window = window_index(idx, cfg.windows, cfg.timezone)
    names = [w.name for w in cfg.windows]
    eta_c = bess.charge_efficiency
    eta_d = rte / eta_c
    smin = e * bess.min_soc_fraction
    smax = e * bess.max_soc_fraction
    if cfg.charge_policy == "fill":
        target = smax
    else:
        priority_mwh = sum(
            w.hours * min(bess.power_mw, cfg.export_limit_mw)
            for w in cfg.windows
            if w.rate == "priority"
        )
        target = np.minimum(smax, smin + priority_mwh / eta_d)
    active = np.flatnonzero((window >= 0) | (pv > 0.0))
    n = s.size
    power = bess.power_mw
    limit = cfg.export_limit_mw
    keep = 1.0 - curtailment_fraction

    def one_pass(soc0: FloatArray) -> Tuple[FloatArray, ...]:
        soc = soc0.copy()
        charge = np.zeros(n)
        curtailed = np.zeros(n)
        dis = np.zeros((len(names), n))
        pvx = np.zeros((len(names) + 1, n))  # last row: outside
        for i in active:
            p = pv[i] * s
            k = int(window[i])
            if k >= 0:
                pv_out = np.minimum(p, limit)
                d = np.minimum(
                    np.minimum(power, limit - pv_out),
                    np.maximum(0.0, soc - smin) * eta_d,
                )
                soc = np.maximum(smin, soc - d / eta_d)
                dis[k] += d
                pvx[k] += pv_out
                curtailed += p - pv_out
            else:
                c = np.maximum(
                    0.0, np.minimum(np.minimum(p, power), (target - soc) / eta_c)
                )
                soc = np.minimum(smax, soc + c * eta_c)
                rest = p - c
                pv_out = np.minimum(rest, limit)
                exported = pv_out * keep
                charge += c
                pvx[-1] += exported
                curtailed += rest - exported
        return soc, charge, curtailed, dis, pvx

    soc0 = smin.copy()
    done = np.zeros(n, dtype=bool)
    out_soc0 = np.zeros(n)
    out_end = np.zeros(n)
    out_charge = np.zeros(n)
    out_curt = np.zeros(n)
    out_dis = np.zeros((len(names), n))
    out_pvx = np.zeros((len(names) + 1, n))
    iters = np.zeros(n, dtype=np.int64)
    for iteration in range(1, cfg.cyclic_soc_max_iterations + 1):
        soc_end, charge, curtailed, dis, pvx = one_pass(soc0)
        new = (~done) & (np.abs(soc_end - soc0) <= cfg.cyclic_soc_tolerance_mwh)
        out_soc0[new] = soc0[new]
        out_end[new] = soc_end[new]
        out_charge[new] = charge[new]
        out_curt[new] = curtailed[new]
        out_dis[:, new] = dis[:, new]
        out_pvx[:, new] = pvx[:, new]
        iters[new] = iteration
        done |= new
        if done.all():
            return ColumnSums(
                pv_mwh=pv.sum() * s,
                charge_mwh=out_charge,
                discharge_mwh_by_window={
                    name: out_dis[k] for k, name in enumerate(names)
                },
                pv_export_mwh_by_window={
                    **{name: out_pvx[k] for k, name in enumerate(names)},
                    "outside": out_pvx[-1],
                },
                curtailed_mwh=out_curt,
                soc_end_mwh=out_end,
                initial_soc_mwh=out_soc0,
                iterations=iters,
            )
        soc0 = np.where(done, soc0, soc_end)
    raise ValueError("the cyclic state of charge did not converge")


def annual_energy(
    sums: ColumnSums,
    j: int,
    *,
    windows: Sequence[Window],
    tariff: TariffConfig,
    year: int,
    pv_factor: float,
    usable_mwh: float,
    discharge_efficiency: float,
) -> AnnualEnergy:
    """Column ``j`` as PR 2's :class:`AnnualEnergy` (the rules of its ``summarise``)."""
    by_win_d = {w.name: float(sums.discharge_mwh_by_window[w.name][j]) for w in windows}
    by_win_pv = {k: float(v[j]) for k, v in sums.pv_export_mwh_by_window.items()}
    by_rate: Dict[str, float] = {r: 0.0 for r in SUPPORTED_RATES}
    by_rate["other"] += by_win_pv["outside"]
    for w in windows:
        rate = (
            "priority"
            if w.rate == "priority" and year <= tariff.priority_term_years
            else "other"
        )
        by_rate[rate] += by_win_d[w.name] + by_win_pv[w.name]
    revenue = {
        "priority": by_rate["priority"] * _KWH_PER_MWH * tariff.priority_lkr_per_kwh,
        "other": by_rate["other"] * _KWH_PER_MWH * tariff.other_lkr_per_kwh,
    }
    charge = float(sums.charge_mwh[j])
    discharge = sum(by_win_d.values())
    pv_export = sum(by_win_pv.values())
    d_soc = float(sums.soc_end_mwh[j] - sums.initial_soc_mwh[j])
    return AnnualEnergy(
        year=year,
        pv_factor=pv_factor,
        pv_mwh=float(sums.pv_mwh[j]),
        charge_mwh=charge,
        discharge_mwh_by_window=by_win_d,
        discharge_mwh=discharge,
        pv_export_mwh=pv_export,
        pv_export_mwh_by_window=by_win_pv,
        curtailed_mwh=float(sums.curtailed_mwh[j]),
        unit_export_mwh=pv_export + discharge,
        export_mwh_by_rate=by_rate,
        conversion_loss_mwh=charge - discharge - d_soc,
        equivalent_full_cycles=discharge / discharge_efficiency / usable_mwh,
        revenue_lkr_by_rate=revenue,
        revenue_lkr=revenue["priority"] + revenue["other"],
    )


# ---------------------------------------------------------------------------
# Trials, the engine and the unit-only metric
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Uncertainty:
    """The sampled non-price inputs.

    Attributes:
        yield_sigma_pct: One standard deviation of the long-term PV yield.
        yield_clip_sigma: Draws are clipped to this many standard deviations.
        rte_low, rte_high: Uniform round-trip efficiency range; the base case is the
            unit config's RTE.
        residual_fade_pct_per_year: Battery energy fade not covered by the augmentation
            reserve, linear in nameplate per year (base case: its mode).
    """

    yield_sigma_pct: float
    yield_clip_sigma: float
    rte_low: float
    rte_high: float
    residual_fade_pct_per_year: Triangular

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Uncertainty":
        """Build from the sizing config's ``uncertainty`` block."""
        _strict(
            raw,
            (
                "yield_sigma_pct",
                "yield_clip_sigma",
                "rte_low",
                "rte_high",
                "residual_fade_pct_per_year",
            ),
            "uncertainty",
        )
        out = cls(
            yield_sigma_pct=_num(raw["yield_sigma_pct"], "yield_sigma_pct", lo=0.0),
            yield_clip_sigma=_num(raw["yield_clip_sigma"], "yield_clip_sigma", lo=0.0),
            rte_low=_num(raw["rte_low"], "rte_low", lo=0.0),
            rte_high=_num(raw["rte_high"], "rte_high", lo=0.0),
            residual_fade_pct_per_year=Triangular.from_mapping(
                raw["residual_fade_pct_per_year"], "residual_fade_pct_per_year"
            ),
        )
        if not 0.0 < out.rte_low <= out.rte_high <= 1.0:
            raise ValueError("uncertainty: need 0 < rte_low <= rte_high <= 1")
        if out.yield_sigma_pct * out.yield_clip_sigma >= 100.0:
            raise ValueError("uncertainty: the clipped yield draw must stay positive")
        if out.residual_fade_pct_per_year.low < 0.0:
            raise ValueError("uncertainty: fade must be non-negative")
        return out


#: Order of the LHS dimensions.
DIMENSIONS = (
    "module_fob_usd_per_wp",
    "inverter_usd_per_wac",
    "bop_usd_per_wp",
    "bess_usd_per_kwh",
    "yield_multiplier",
    "round_trip_efficiency",
    "residual_fade_pct_per_year",
)


@dataclass(frozen=True)
class Trials:
    """Per-trial inputs, one array per :data:`DIMENSIONS` entry (index 0 is the base case
    when ``with_base`` was set)."""

    values: Dict[str, FloatArray]

    @property
    def n(self) -> int:
        """Trial count."""
        return int(next(iter(self.values.values())).size)


def draw_trials(
    *,
    n_trials: int,
    seed: int,
    pricing: Pricing,
    uncertainty: Uncertainty,
    base_rte: float,
    with_base: bool,
) -> Trials:
    """Seeded LHS draws mapped to each input's distribution.

    With ``with_base`` the first row is the deterministic base case: every price at its
    mode, yield 1, the base RTE and the fade mode.
    """
    u = generate_lhs_samples(
        n_trials=n_trials, bounds=[(0.0, 1.0)] * len(DIMENSIONS), seed=seed
    )
    u = np.clip(u, 1e-12, 1.0 - 1e-12)
    nd = NormalDist()
    z = np.array([nd.inv_cdf(float(x)) for x in u[:, 4]])
    z = np.clip(z, -uncertainty.yield_clip_sigma, uncertainty.yield_clip_sigma)
    vals = {
        "module_fob_usd_per_wp": pricing.module_fob_usd_per_wp.ppf(u[:, 0]),
        "inverter_usd_per_wac": pricing.inverter_usd_per_wac.ppf(u[:, 1]),
        "bop_usd_per_wp": pricing.bop_usd_per_wp.ppf(u[:, 2]),
        "bess_usd_per_kwh": pricing.bess_usd_per_kwh.ppf(u[:, 3]),
        "yield_multiplier": 1.0 + uncertainty.yield_sigma_pct / 100.0 * z,
        "round_trip_efficiency": uncertainty.rte_low
        + u[:, 5] * (uncertainty.rte_high - uncertainty.rte_low),
        "residual_fade_pct_per_year": uncertainty.residual_fade_pct_per_year.ppf(
            u[:, 6]
        ),
    }
    if with_base:
        base = {
            "module_fob_usd_per_wp": pricing.module_fob_usd_per_wp.mode,
            "inverter_usd_per_wac": pricing.inverter_usd_per_wac.mode,
            "bop_usd_per_wp": pricing.bop_usd_per_wp.mode,
            "bess_usd_per_kwh": pricing.bess_usd_per_kwh.mode,
            "yield_multiplier": 1.0,
            "round_trip_efficiency": base_rte,
            "residual_fade_pct_per_year": uncertainty.residual_fade_pct_per_year.mode,
        }
        vals = {k: np.concatenate([[base[k]], v]) for k, v in vals.items()}
    return Trials(values={k: np.asarray(v, dtype=np.float64) for k, v in vals.items()})


@dataclass(frozen=True)
class PointInputs:
    """Everything one grid point needs besides the trials.

    Attributes:
        dc_ac_ratio: Target DC/AC.
        dc_mwp: Installed DC peak (whole tables).
        ac_capacity_mw: The unit's AC capacity.
        bess_power_mw, bess_energy_mwh: Battery rating.
        pv_base_mw: Hourly PV at warranted factor 1 and yield 1.
        timestamps_utc: The TMY hours.
        warranty: Warranted PV factor per operating year.
        inverter_count, inverter_kw: The matched fleet.
    """

    dc_ac_ratio: float
    dc_mwp: float
    ac_capacity_mw: float
    bess_power_mw: float
    bess_energy_mwh: float
    pv_base_mw: FloatArray
    timestamps_utc: Any
    warranty: Tuple[float, ...]
    inverter_count: int
    inverter_kw: float


@dataclass(frozen=True)
class Context:
    """Fixed model context for every grid point.

    Attributes:
        scenario: The Blue Whale scenario (a plain mapping).
        bess_template: PR 2's battery config (power, efficiencies, SoC limits).
        dispatch: PR 2's dispatch config.
        tariff: PR 2's tariff config.
        wind: The fixed wind block.
        pricing: The cited prices.
        grid_civils_development_usd: Plant-level capex outside the unit (input B26).
        fixed_opex_usd_per_year: Wind O&M plus insurance, land and SPV (inputs B10, B28).
    """

    scenario: Mapping[str, Any]
    bess_template: BessConfig
    dispatch: DispatchConfig
    tariff: TariffConfig
    wind: WindBlock
    pricing: Pricing
    grid_civils_development_usd: float
    fixed_opex_usd_per_year: float


def _bess_for(
    ctx: Context, energy_mwh: float, rte: float, power_mw: float
) -> BessConfig:
    t = ctx.bess_template
    return BessConfig(
        power_mw=power_mw,
        energy_mwh=energy_mwh,
        round_trip_efficiency=rte,
        charge_efficiency=t.charge_efficiency,
        min_soc_fraction=t.min_soc_fraction,
        max_soc_fraction=t.max_soc_fraction,
        grid_charging=False,
    )


def engine_overrides(
    ctx: Context,
    rep: EngineRepresentation,
    *,
    point: PointInputs,
    pv_capex_usd: float,
    bess_capex_usd: float,
    opex_usd_per_year: float,
) -> Dict[str, Any]:
    """The Blue Whale scenario fields that carry one sized and priced unit (PR 2 wiring)."""
    wind_capex = float(ctx.scenario["generation"]["technologies"]["wind"]["capex_usd"])
    total = wind_capex + pv_capex_usd + bess_capex_usd + ctx.grid_civils_development_usd
    cap = float(ctx.scenario["project"]["capacity_mw"])
    t = "generation.technologies"
    return {
        f"{t}.solar.capacity_mw": rep.solar_capacity_mw,
        f"{t}.solar.capacity_factor": rep.solar_capacity_factor,
        f"{t}.solar.degradation_pct": rep.solar_degradation_pct,
        f"{t}.solar.aep_gwh": rep.solar_aep_gwh,
        f"{t}.solar.capex_usd": pv_capex_usd,
        f"{t}.bess_1.power_mw": point.bess_power_mw,
        f"{t}.bess_1.energy_mwh": point.bess_energy_mwh,
        f"{t}.bess_1.duration_h": point.bess_energy_mwh / point.bess_power_mw,
        f"{t}.bess_1.capex_usd": bess_capex_usd,
        f"{t}.bess_1.revenue.tariff_lkr_per_kwh": rep.bess_tariff_lkr_per_kwh,
        f"{t}.bess_1.revenue.cycles_per_year": rep.bess_cycles_per_year,
        f"{t}.bess_1.revenue.round_trip_efficiency": rep.bess_round_trip_efficiency,
        f"{t}.bess_1.revenue.contract_years": rep.bess_contract_years,
        f"{t}.bess_1.revenue.mdsc_fade_pct_annual": rep.bess_mdsc_fade_pct_annual,
        "tariff.lkr_per_kwh": rep.tariff_lkr_per_kwh,
        "project.capacity_factor": rep.project_capacity_factor,
        "capex.usd_total": total,
        "capex.capex_per_kw_usd": total / (cap * 1000.0),
        "opex.usd_per_year": opex_usd_per_year,
        "opex.opex_per_kw_yr_usd": opex_usd_per_year / (cap * 1000.0),
    }


def unit_pretax_cashflows_usd(
    revenue_lkr: Sequence[float],
    *,
    capex_usd: float,
    opex_usd_year1: float,
    opex_escalation_pct: float,
    lkr_per_usd: float,
    construction_years: int,
) -> List[float]:
    """The unit's own pre-tax cash flow: capex at t=0, a build lag, then revenue less O&M."""
    ops = [
        r / lkr_per_usd - opex_usd_year1 * (1.0 + opex_escalation_pct / 100.0) ** t
        for t, r in enumerate(revenue_lkr)
    ]
    return [-capex_usd] + [0.0] * construction_years + ops


@dataclass
class PointResult:
    """One grid point: its inputs, base case and trial metrics.

    Attributes:
        dc_ac_ratio, dc_mwp, bess_energy_mwh: The size.
        pv_capex_usd_base, bess_capex_usd_base: Capex at the price modes.
        base: KPIs and engine fields of the deterministic base case.
        trials: Per metric, one value per trial.
        year1_unit_export_mwh: Per trial.
        discount_rate_used: The engine's discount rate (constant across trials).
    """

    dc_ac_ratio: float
    dc_mwp: float
    bess_energy_mwh: float
    pv_capex_usd_base: float = 0.0
    bess_capex_usd_base: float = 0.0
    base: Dict[str, Any] = field(default_factory=dict)
    trials: Dict[str, List[float]] = field(default_factory=dict)
    year1_unit_export_mwh: List[float] = field(default_factory=list)
    discount_rate_used: Optional[float] = None


def evaluate_point(
    ctx: Context,
    point: PointInputs,
    trials: Trials,
    *,
    has_base: bool,
    curtailment_fraction: float = 0.0,
    evaluator: Callable[..., Mapping[str, Any]] = evaluate_with_overrides,
) -> PointResult:
    """Dispatch, map and evaluate every trial at one grid point.

    Row 0 of ``trials`` is the base case when ``has_base``.

    Raises:
        ValueError: If the scenario's FX drifts (the unit metric assumes a flat rate) or
            the engine returns no KPI for a trial.
    """
    fx = ctx.scenario["fx"]
    if float(fx["annual_depr"]) != 0.0:
        raise ValueError("unit_pretax metrics need fx.annual_depr == 0")
    lkr_per_usd = float(fx["start_lkr_per_usd"])
    years = len(point.warranty)
    v = trials.values
    n = trials.n
    fade = v["residual_fade_pct_per_year"] / 100.0
    if (fade * (years - 1) >= 1.0).any():
        raise ValueError("residual fade exhausts the battery within the horizon")
    # Columns: trial-major, year-minor.
    yrs = np.arange(years, dtype=np.float64)
    scale = (
        v["yield_multiplier"][:, None] * np.asarray(point.warranty)[None, :]
    ).ravel()
    energy = (point.bess_energy_mwh * (1.0 - fade[:, None] * yrs[None, :])).ravel()
    rte = np.repeat(v["round_trip_efficiency"], years)
    sums = dispatch_columns(
        point.pv_base_mw,
        point.timestamps_utc,
        scale=scale,
        energy_mwh=energy,
        round_trip_efficiency=rte,
        bess=_bess_for(
            ctx,
            point.bess_energy_mwh,
            ctx.bess_template.round_trip_efficiency,
            point.bess_power_mw,
        ),
        cfg=ctx.dispatch,
        curtailment_fraction=curtailment_fraction,
    )
    price = ctx.pricing
    inv_kw = point.inverter_kw
    esc = float(ctx.scenario["opex"]["escalation_pct"])
    lag = int(ctx.scenario["timeline"]["construction_years"])
    opex = (
        ctx.fixed_opex_usd_per_year
        + price.pv_opex_usd_per_kwp_year * point.dc_mwp * 1000.0
        + price.bess_opex_usd_per_kwh_year * point.bess_energy_mwh * 1000.0
    )
    unit_opex = opex - ctx.fixed_opex_usd_per_year
    result = PointResult(
        dc_ac_ratio=point.dc_ac_ratio,
        dc_mwp=point.dc_mwp,
        bess_energy_mwh=point.bess_energy_mwh,
    )
    result.trials = {m: [] for m in METRICS}
    for j in range(n):
        rte_j = float(v["round_trip_efficiency"][j])
        bess_j = _bess_for(ctx, point.bess_energy_mwh, rte_j, point.bess_power_mw)
        path = [
            annual_energy(
                sums,
                j * years + y,
                windows=ctx.dispatch.windows,
                tariff=ctx.tariff,
                year=y + 1,
                pv_factor=float(point.warranty[y]),
                usable_mwh=float(energy[j * years + y])
                * (bess_j.max_soc_fraction - bess_j.min_soc_fraction),
                discharge_efficiency=bess_j.discharge_efficiency,
            )
            for y in range(years)
        ]
        rep = engine_representation(
            path,
            wind=ctx.wind,
            capacity_mw=point.ac_capacity_mw,
            bess=bess_j,
            tariff=ctx.tariff,
        )
        pv_capex = pv_capex_usd(
            dc_mwp=point.dc_mwp,
            inverter_count=point.inverter_count,
            inverter_kw=inv_kw,
            module_fob_usd_per_wp=float(v["module_fob_usd_per_wp"][j]),
            module_delivery_usd_per_wp=price.module_delivery_usd_per_wp,
            inverter_usd_per_wac=float(v["inverter_usd_per_wac"][j]),
            bop_usd_per_wp=float(v["bop_usd_per_wp"][j]),
        )
        bess_capex = point.bess_energy_mwh * 1000.0 * float(v["bess_usd_per_kwh"][j])
        overrides = engine_overrides(
            ctx,
            rep,
            point=point,
            pv_capex_usd=pv_capex,
            bess_capex_usd=bess_capex,
            opex_usd_per_year=opex,
        )
        kpis = evaluator(raw_config=ctx.scenario, overrides=overrides)
        rate = float(kpis["discount_rate_used"])
        flows = unit_pretax_cashflows_usd(
            [a.revenue_lkr for a in path],
            capex_usd=pv_capex + bess_capex,
            opex_usd_year1=unit_opex,
            opex_escalation_pct=esc,
            lkr_per_usd=lkr_per_usd,
            construction_years=lag,
        )
        u_irr = irr(flows)
        row = {
            "project_npv": float(kpis["project_npv"]),
            "project_irr": _kpi(kpis, "project_irr"),
            "equity_npv": float(kpis["equity_npv"]),
            "equity_irr": _kpi(kpis, "equity_irr"),
            "min_dscr": _kpi(kpis, "min_dscr"),
            "unit_pretax_npv_usd": npv(rate, flows),
            "unit_pretax_irr": float("nan") if u_irr is None else float(u_irr),
        }
        if has_base and j == 0:
            result.discount_rate_used = rate
            result.pv_capex_usd_base = pv_capex
            result.bess_capex_usd_base = bess_capex
            result.base = {
                **row,
                "engine": asdict(rep),
                "overrides": overrides,
                "year1": asdict(path[0]),
            }
            continue
        for m in METRICS:
            result.trials[m].append(row[m])
        result.year1_unit_export_mwh.append(path[0].unit_export_mwh)
        if result.discount_rate_used is None:
            result.discount_rate_used = rate
    return result


def summarise_metric(values: Sequence[float]) -> Dict[str, float]:
    """Mean and exceedance percentiles (``p90`` = exceeded by 90% = 10th percentile)."""
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"n": 0.0}
    return {
        "n": float(arr.size),
        "mean": float(arr.mean()),
        "p10": float(np.percentile(arr, 90.0)),
        "p50": float(np.percentile(arr, 50.0)),
        "p90": float(np.percentile(arr, 10.0)),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def priority_window_capability(
    *,
    energy_mwh: float,
    power_mw: float,
    bess: BessConfig,
    cfg: DispatchConfig,
) -> Dict[str, float]:
    """What a full battery can export in the priority windows, against what they take.

    Deliverable energy is the usable stored energy times the discharge efficiency (the
    base RTE, all loss on discharge by the repository convention). The windows take
    ``min(power, export limit)`` for their length.
    """
    hours = sum(w.hours for w in cfg.windows if w.rate == "priority")
    deliverable = (
        energy_mwh
        * (bess.max_soc_fraction - bess.min_soc_fraction)
        * bess.discharge_efficiency
    )
    return {
        "priority_window_hours": hours,
        "deliverable_mwh": deliverable,
        "window_takes_mwh": hours * min(power_mw, cfg.export_limit_mw),
        "deliverable_hours_at_power": deliverable / min(power_mw, cfg.export_limit_mw),
    }


def best_point(
    stats: Sequence[Mapping[str, Any]],
    *,
    metric: str,
    statistic: str,
    key: str = "eligible",
) -> Optional[int]:
    """Index of the grid point, among those whose ``key`` is true (default: eligible),
    that maximises ``statistic`` of ``metric``."""
    if metric not in METRICS or statistic not in STATISTICS:
        raise ValueError(f"unknown objective {metric}.{statistic}")
    best: Optional[int] = None
    best_val = -math.inf
    for i, s in enumerate(stats):
        if not s[key]:
            continue
        val = s["metrics"][metric].get(statistic)
        if val is not None and math.isfinite(val) and val > best_val:
            best, best_val = i, float(val)
    return best


# ---------------------------------------------------------------------------
# The sizing run
# ---------------------------------------------------------------------------
SIZING_KEYS = (
    "schema_version",
    "unit_config",
    "pricing_config",
    "scenario",
    "grid",
    "monte_carlo",
    "uncertainty",
    "plant",
    "objective",
    "curtailment_scenario",
    "constraints",
    "recommendation",
    "output",
)


@dataclass(frozen=True)
class SizingRun:
    """A completed run.

    Attributes:
        spec: Seed, sampler, requested trials and effective evaluation counts.
        points: Per grid point: size, fit, inverter match, capex, base case and statistics.
        recommendation: The primary objective's choice and every alternative's.
        curtailment: The base-case sweep under the curtailment scenario, or ``None``.
    """

    spec: Dict[str, Any]
    points: List[Dict[str, Any]]
    recommendation: Dict[str, Any]
    curtailment: Optional[Dict[str, Any]]

    @property
    def effective_evaluations(self) -> int:
        """Model evaluations actually run (trials, base cases and curtailment cases)."""
        return int(self.spec["effective_evaluations"])


def _grid_values(raw: Any, where: str) -> Tuple[float, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, str) or not raw:
        raise ValueError(f"{where} must be a non-empty list")
    vals = tuple(_num(x, where, lo=0.0) for x in raw)
    if list(vals) != sorted(set(vals)):
        raise ValueError(f"{where} must be strictly increasing")
    return vals


def run_sizing(
    sizing_cfg: Mapping[str, Any],
    *,
    unit_cfg: Mapping[str, Any],
    pricing_cfg: Mapping[str, Any],
    scenario: Mapping[str, Any],
    site: Mapping[str, Any],
    evaluator: Callable[..., Mapping[str, Any]] = evaluate_with_overrides,
) -> SizingRun:
    """Run the seeded Monte Carlo over the decision grid.

    Args:
        sizing_cfg: ``conf/blue_whale_pv_bess_sizing.yaml``.
        unit_cfg: PR 2's ``conf/blue_whale_solar_bess.yaml``.
        pricing_cfg: ``conf/blue_whale_pv_bess_pricing.yaml``.
        scenario: The Blue Whale scenario mapping.
        site: ``{"geometry", "coastal", "frame", "lot_lat", "lot_lon"}`` as built by
            :func:`site_context`.
        evaluator: The evaluation gateway (a stand-in only in tests).

    Returns:
        The run.

    Raises:
        ValueError: On a malformed config or an infeasible grid.
    """
    from analytics.gis.pv_array_layout import (
        ArrayConfig,
        BessFootprintConfig,
        LandConfig,
        ModuleSpec,
        ShadingRuleConfig,
        SiteFitConfig,
        StringDesignConfig,
        compact_land_area,
        design_string,
        equipment_area,
        fit_site,
        row_pitch,
        size_array,
    )
    from solar_resource.pv_bess_dispatch import hourly_pv, with_array

    _strict(sizing_cfg, SIZING_KEYS, "sizing")
    if sizing_cfg["schema_version"] != "blue_whale_pv_bess_sizing_v1":
        raise ValueError("sizing.schema_version must be blue_whale_pv_bess_sizing_v1")
    grid = sizing_cfg["grid"]
    _strict(grid, ("dc_ac_ratios", "bess_energy_mwh", "bess_power_mw"), "sizing.grid")
    ratios = _grid_values(grid["dc_ac_ratios"], "grid.dc_ac_ratios")
    energies = _grid_values(grid["bess_energy_mwh"], "grid.bess_energy_mwh")
    power = _num(grid["bess_power_mw"], "grid.bess_power_mw", lo=0.0)
    mc = sizing_cfg["monte_carlo"]
    _strict(mc, ("seed", "n_trials", "sampler", "include_base_case"), "monte_carlo")
    if mc["sampler"] != "lhs":
        raise ValueError("monte_carlo.sampler must be lhs")
    seed = mc["seed"]
    n_trials = mc["n_trials"]
    for name, val in (("seed", seed), ("n_trials", n_trials)):
        if isinstance(val, bool) or not isinstance(val, int) or val < 1:
            raise ValueError(f"monte_carlo.{name} must be a positive integer")
    if mc["include_base_case"] is not True:
        raise ValueError(
            "monte_carlo.include_base_case must be true (the scenario case)"
        )
    plant = sizing_cfg["plant"]
    _strict(plant, ("grid_civils_development_usd", "fixed_opex_usd_per_year"), "plant")
    objective = sizing_cfg["objective"]
    _strict(objective, ("metric", "statistic", "alternatives"), "objective")
    cons = sizing_cfg["constraints"]
    _strict(cons, ("min_priority_window_discharge_hours", "basis"), "constraints")
    min_hours = _num(
        cons["min_priority_window_discharge_hours"],
        "constraints.min_priority_window_discharge_hours",
        lo=0.0,
    )
    curt = sizing_cfg["curtailment_scenario"]
    _strict(
        curt,
        ("enabled", "daytime_export_curtailment_fraction", "basis"),
        "curtailment_scenario",
    )

    pricing = Pricing.from_mapping(pricing_cfg)
    uncertainty = Uncertainty.from_mapping(sizing_cfg["uncertainty"])
    module = ModuleSpec.from_mapping(unit_cfg["module"])
    strings_design = design_string(
        module, StringDesignConfig.from_mapping(unit_cfg["string_design"])
    )
    land = LandConfig.from_mapping(unit_cfg["land"])
    footprint = BessFootprintConfig.from_mapping(unit_cfg["bess_footprint"])
    fit_cfg = SiteFitConfig.from_mapping(unit_cfg["site_fit"])
    shading = ShadingRuleConfig.from_mapping(unit_cfg["shading_rule"])
    template = BessConfig.from_mapping(unit_cfg["bess"])
    dcfg = DispatchConfig.from_mapping(unit_cfg["dispatch"])
    tariff = TariffConfig.from_mapping(unit_cfg["tariff"])
    wind_raw = scenario["generation"]["technologies"]["wind"]
    wind = WindBlock(
        capacity_mw=float(wind_raw["capacity_mw"]),
        capacity_factor=float(wind_raw["capacity_factor"]),
        degradation_pct=float(wind_raw["degradation_pct"]),
    )
    wind_capex = float(wind_raw["capex_usd"])
    expected_wind = pricing.wind_capex_usd_per_kw * wind.capacity_mw * 1000.0
    if abs(wind_capex - expected_wind) > 0.5:
        raise ValueError(
            f"the scenario's wind capex {wind_capex} is not the fixed placeholder "
            f"{expected_wind}; the turbine is not a sizing variable"
        )
    ctx = Context(
        scenario=scenario,
        bess_template=template,
        dispatch=dcfg,
        tariff=tariff,
        wind=wind,
        pricing=pricing,
        grid_civils_development_usd=_num(
            plant["grid_civils_development_usd"], "plant.grid_civils", lo=0.0
        ),
        fixed_opex_usd_per_year=_num(
            plant["fixed_opex_usd_per_year"], "plant.fixed_opex", lo=0.0
        ),
    )
    trials = draw_trials(
        n_trials=n_trials,
        seed=seed,
        pricing=pricing,
        uncertainty=uncertainty,
        base_rte=template.round_trip_efficiency,
        with_base=True,
    )
    years = int(unit_cfg["pv_yield"]["degradation_years"])
    warranty = tuple(module.warranted_power_fraction(y) for y in range(1, years + 1))
    resource = dict(unit_cfg["pv_yield"]["resource_solar"])
    resource["inverter_eff_nom"] = pricing.inverter.european_efficiency

    points: List[Dict[str, Any]] = []
    results: List[Optional[PointResult]] = []
    base_only: List[Tuple[PointInputs, bool]] = []
    evaluations = 0
    for ratio in ratios:
        arr_raw = {**dict(unit_cfg["array"]), "dc_ac_ratio": ratio}
        array = ArrayConfig.from_mapping(arr_raw)
        sizing = size_array(module, strings_design, array)
        inv = match_inverter(
            pricing.inverter,
            strings=sizing.strings,
            voc_cold_v=strings_design.string_voc_cold_v,
            vmp_hot_v=strings_design.string_vmp_hot_v,
            vmp_stc_v=strings_design.string_vmp_stc_v,
            imp_a=module.imp_a,
            isc_a=module.isc_a,
            ac_capacity_mw=array.ac_capacity_mw,
        )
        solar = with_array(
            resource,
            dc_capacity_mw=sizing.dc_capacity_mw,
            dc_ac_ratio=sizing.dc_ac_ratio,
            tilt_deg=array.tilt_deg,
            azimuth_deg=array.azimuth_deg,
            gamma_pdc_per_c=module.temp_coeff_pmax_pct_per_c / 100.0,
        )
        pv = hourly_pv(solar)
        pitch = row_pitch(
            lat_deg=float(site["lot_lat"]),
            lon_deg=float(site["lot_lon"]),
            sizing=sizing,
            array=array,
            rule=shading,
        )
        for energy in energies:
            equipment = equipment_area(
                bess_power_mw=power,
                bess_energy_mwh=energy,
                bess=footprint,
                land=land,
            )
            area = compact_land_area(
                sizing=sizing, pitch=pitch, array=array, land=land, equipment=equipment
            )
            layout = fit_site(
                site["geometry"],
                coastal=site["coastal"],
                cfg=fit_cfg,
                sizing=sizing,
                pitch=pitch,
                array=array,
                land=land,
                equipment=equipment,
                required_fenced_area_m2=area.fenced_area_m2,
            )
            point = PointInputs(
                dc_ac_ratio=ratio,
                dc_mwp=sizing.dc_capacity_mw,
                ac_capacity_mw=array.ac_capacity_mw,
                bess_power_mw=power,
                bess_energy_mwh=energy,
                pv_base_mw=pv.ac_mw,
                timestamps_utc=pv.timestamps_utc,
                warranty=warranty,
                inverter_count=inv.inverter_count,
                inverter_kw=pricing.inverter.nominal_ac_kw,
            )
            fits = bool(layout.fit.fits) and inv.ok
            capability = priority_window_capability(
                energy_mwh=energy,
                power_mw=power,
                bess=_bess_for(ctx, energy, template.round_trip_efficiency, power),
                cfg=dcfg,
            )
            meets_rule = (
                capability["deliverable_hours_at_power"] >= min_hours - 1e-9
                and capability["priority_window_hours"] >= min_hours - 1e-9
            )
            entry: Dict[str, Any] = {
                "dc_ac_ratio_target": ratio,
                "dc_ac_ratio": sizing.dc_ac_ratio,
                "dc_mwp": sizing.dc_capacity_mw,
                "tables": sizing.tables,
                "strings": sizing.strings,
                "bess_power_mw": power,
                "bess_energy_mwh": energy,
                "fits": fits,
                "meets_dispatch_rule": meets_rule,
                "eligible": fits and meets_rule,
                "priority_window_capability": capability,
                "land": {
                    "fenced_area_m2": area.fenced_area_m2,
                    "tables_that_fit": layout.fit.tables_that_fit,
                    "equipment_placed": layout.fit.equipment_placed,
                    "lot_fits": bool(layout.fit.fits),
                },
                "inverter": asdict(inv),
                "pv_ac_mwh_factor_1": pv.annual_mwh,
            }
            points.append(entry)
            if not fits:
                results.append(None)
                continue
            res = evaluate_point(ctx, point, trials, has_base=True, evaluator=evaluator)
            evaluations += trials.n
            results.append(res)
            base_only.append((point, meets_rule))
    stats: List[Dict[str, Any]] = []
    for entry, pres in zip(points, results, strict=True):
        if pres is None:
            entry["metrics"] = {}
            stats.append(entry)
            continue
        entry["capex_usd_base"] = {
            "pv": pres.pv_capex_usd_base,
            "bess": pres.bess_capex_usd_base,
        }
        entry["discount_rate_used"] = pres.discount_rate_used
        entry["base"] = {k: pres.base[k] for k in METRICS} | {
            "engine": pres.base["engine"],
            "year1": pres.base["year1"],
        }
        entry["metrics"] = {m: summarise_metric(pres.trials[m]) for m in METRICS}
        entry["year1_unit_export_mwh"] = summarise_metric(pres.year1_unit_export_mwh)
        entry["_trials"] = pres.trials
        stats.append(entry)
    primary = best_point(
        stats, metric=str(objective["metric"]), statistic=str(objective["statistic"])
    )
    if primary is None:
        raise ValueError(
            "no grid point fits the site and the inverter and meets the dispatch rule"
        )
    unconstrained = best_point(
        stats,
        metric=str(objective["metric"]),
        statistic=str(objective["statistic"]),
        key="fits",
    )
    alternatives = []
    for alt in objective["alternatives"]:
        metric, statistic = str(alt[0]), str(alt[1])
        i = best_point(stats, metric=metric, statistic=statistic)
        alternatives.append(
            {
                "metric": metric,
                "statistic": statistic,
                "dc_ac_ratio": None if i is None else stats[i]["dc_ac_ratio_target"],
                "bess_energy_mwh": None if i is None else stats[i]["bess_energy_mwh"],
            }
        )
    chosen = stats[primary]
    metric = str(objective["metric"])
    # Paired comparison with the runner-up (common random numbers).
    ranked = sorted(
        (i for i, s in enumerate(stats) if s["eligible"]),
        key=lambda i: stats[i]["metrics"][metric][str(objective["statistic"])],
        reverse=True,
    )
    paired: Optional[Dict[str, Any]] = None
    if len(ranked) > 1:
        a = np.asarray(stats[ranked[0]]["_trials"][metric])
        b = np.asarray(stats[ranked[1]]["_trials"][metric])
        paired = {
            "runner_up_dc_ac_ratio": stats[ranked[1]]["dc_ac_ratio_target"],
            "runner_up_bess_energy_mwh": stats[ranked[1]]["bess_energy_mwh"],
            "share_of_trials_chosen_beats_runner_up": float(np.mean(a >= b)),
            "difference_p50": float(np.percentile(a - b, 50.0)),
        }
    curtailment: Optional[Dict[str, Any]] = None
    if curt["enabled"]:
        f = _num(curt["daytime_export_curtailment_fraction"], "curtailment", lo=0.0)
        base_trial = Trials(values={k: v[:1] for k, v in trials.values.items()})
        rows = []
        for point, eligible in base_only:
            r = evaluate_point(
                ctx,
                point,
                base_trial,
                has_base=True,
                curtailment_fraction=f,
                evaluator=evaluator,
            )
            evaluations += 1
            rows.append(
                {
                    "dc_ac_ratio_target": point.dc_ac_ratio,
                    "bess_energy_mwh": point.bess_energy_mwh,
                    "eligible": eligible,
                    "project_npv": r.base["project_npv"],
                    "project_irr": r.base["project_irr"],
                    "unit_pretax_npv_usd": r.base["unit_pretax_npv_usd"],
                }
            )
        best = max((r for r in rows if r["eligible"]), key=lambda r: r["project_npv"])
        curtailment = {
            "daytime_export_curtailment_fraction": f,
            "basis": str(curt["basis"]),
            "base_case_only": True,
            "rows": rows,
            "best_by_project_npv": {
                "dc_ac_ratio": best["dc_ac_ratio_target"],
                "bess_energy_mwh": best["bess_energy_mwh"],
            },
        }
    for s in stats:
        s.pop("_trials", None)
    spec = {
        "seed": seed,
        "sampler": "lhs",
        "common_random_numbers": True,
        "requested_trials_per_point": n_trials,
        "grid_points": len(points),
        "grid_points_evaluated": len(base_only),
        "base_case_per_point": True,
        "effective_evaluations": evaluations,
        "dimensions": list(DIMENSIONS),
        "years": years,
        "objective": {
            "metric": metric,
            "statistic": str(objective["statistic"]),
        },
    }
    recommendation = {
        "dc_ac_ratio": chosen["dc_ac_ratio_target"],
        "dc_mwp": chosen["dc_mwp"],
        "bess_power_mw": chosen["bess_power_mw"],
        "bess_energy_mwh": chosen["bess_energy_mwh"],
        "objective_value": chosen["metrics"][metric][str(objective["statistic"])],
        "constraint": {
            "min_priority_window_discharge_hours": min_hours,
            "basis": str(cons["basis"]),
        },
        "unconstrained_best": (
            None
            if unconstrained is None
            else {
                "dc_ac_ratio": stats[unconstrained]["dc_ac_ratio_target"],
                "bess_energy_mwh": stats[unconstrained]["bess_energy_mwh"],
                "objective_value": stats[unconstrained]["metrics"][metric][
                    str(objective["statistic"])
                ],
                "meets_dispatch_rule": stats[unconstrained]["meets_dispatch_rule"],
            }
        ),
        "paired_with_runner_up": paired,
        "alternatives": alternatives,
    }
    return SizingRun(
        spec=spec, points=stats, recommendation=recommendation, curtailment=curtailment
    )


def site_context(
    unit_cfg: Mapping[str, Any], read_json: Callable[[str], Any]
) -> Dict[str, Any]:
    """PR 1's lot, coastline and setback for the land fit (as PR 2's runner builds them).

    Args:
        unit_cfg: PR 2's unit config.
        read_json: Reads a repository-relative JSON or YAML file.
    """
    from analytics.gis.pv_array_layout import SiteFitConfig, site_geometry
    from analytics.gis.shadow_flicker import CoastalSetbackConfig, LocalFrame

    fit_cfg = SiteFitConfig.from_mapping(unit_cfg["site_fit"])
    wind_siting = read_json(fit_cfg.wind_siting_config)
    frame = LocalFrame(
        float(wind_siting["site"]["reference_lat_deg"]),
        float(wind_siting["site"]["reference_lon_deg"]),
    )
    geometry = site_geometry(
        read_json(fit_cfg.site_geojson), read_json(fit_cfg.coastline_geojson), frame
    )
    ce = sum(p[0] for p in geometry.lot_ring) / len(geometry.lot_ring)
    cn = sum(p[1] for p in geometry.lot_ring) / len(geometry.lot_ring)
    lon, lat = frame.to_lon_lat(ce, cn)
    return {
        "geometry": geometry,
        "coastal": CoastalSetbackConfig.from_mapping(wind_siting["coastal_setback"]),
        "frame": frame,
        "lot_lat": lat,
        "lot_lon": lon,
    }


__all__ = [
    "ColumnSums",
    "SizingRun",
    "run_sizing",
    "site_context",
    "Context",
    "DIMENSIONS",
    "InverterMatch",
    "InverterSpec",
    "METRICS",
    "PointInputs",
    "PointResult",
    "Pricing",
    "STATISTICS",
    "Triangular",
    "Trials",
    "Uncertainty",
    "annual_energy",
    "best_point",
    "dispatch_columns",
    "draw_trials",
    "engine_overrides",
    "evaluate_point",
    "match_inverter",
    "pv_capex_usd",
    "summarise_metric",
    "unit_pretax_cashflows_usd",
]
