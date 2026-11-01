"""Hourly PV output and a PV-charged BESS dispatcher for a solar + BESS unit (``[solar]``).

Scenario-local and minimal by design. #1472 proposes a general hourly BESS feasibility
ledger (``analytics.storage_dispatch``); it is not on ``main`` or on this branch, so this
module does not build on it and does not try to be one. It serves one unit: a PV array
and a battery behind one export limit, the battery charged only from that PV and
discharged in fixed clock-time windows. There is no optimisation, no grid charging and no
merchant price.

Hourly PV
---------
:func:`hourly_pv` runs the same pvlib chain as
:func:`solar_resource.pv_producer.compute_solar_aep` on the same frozen TMY (Hay-Davies
transposition, Faiman cell temperature, PVWatts DC, PVWatts inverter clipped at the AC
nameplate, then the flat or itemised loss factor), and keeps the hourly series that
``compute_solar_aep`` sums away. ``compute_solar_aep`` returns only annual totals and
editing it is outside this change, so the series is rebuilt here and pinned to it: the
hourly sum must equal its annual energy (``TEST-01``, a pre-existing oracle). Only the
frozen-TMY path is supported.

Dispatch
--------
Each step is one hour, ``[t, t + 1 h)``. A step whose local start and end fall inside a
discharge window is a window step, and every window must start and end on step
boundaries (otherwise the dispatcher refuses the input). In a window step the PV exports
first, within the export limit, and the battery discharges into the headroom, up to its
power and its stored energy; it does not charge. In any other step the PV charges the
battery first, up to its power and the policy's state-of-charge target, and exports the
rest within the limit. Whatever exceeds the limit is curtailed. So, every hour::

    pv = charge + pv_export + curtailed
    soc[t+1] = soc[t] + charge * eta_c - discharge / eta_d

with ``eta_c * eta_d`` the round-trip efficiency. The year is run as a repeating year:
the first morning draws on the last evening's residue, and the initial state of charge is
iterated to a fixed point.

Tariff
------
Each exported kWh is paid by WHEN it is exported: the rate of the window it falls in, or
the other-period rate outside every window. After ``priority_term_years`` the priority
window is paid the other-period rate.

Engine representation (no engine code)
--------------------------------------
The v14 engine bills one generation tariff on ``sum(capacity x CF x 8760)`` per
technology, plus each ``type: bess`` block's ``energy_tariff`` revenue
``energy_mwh x 1000 x cycles x RTE x tariff x soh(t)`` for ``contract_years``. The unit
maps onto it exactly in year 1:

* ``solar``: capacity = the unit's AC export capacity; CF = everything the unit exports
  (PV direct plus battery discharge) over ``capacity x 8760``; its degradation is the
  geometric rate whose 20-year sum matches the dispatcher's.
* ``bess_1``: ``energy_tariff`` at the priority PREMIUM (priority less other rate) on the
  energy exported in the priority window, with ``cycles = that energy / (energy_mwh x
  RTE)`` and ``contract_years`` = the priority term; its ``mdsc_fade_pct_annual`` is the
  geometric rate whose sum over the term matches the dispatcher's decline in that
  energy. It carries the PV-degradation effect on the evening export, not cell fade,
  which is not modelled.
* the generation tariff: the year-1 energy-weighted blend of the wind rate and the
  other-period rate over the wind and unit energy.

Then generation revenue plus BESS revenue equals the dispatcher's unit revenue plus the
wind revenue in year 1, and within a stated tolerance in later years. A battery cell
fade, augmentation or availability derate is not modelled.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from datetime import time as dtime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from solar_resource.loss_model import compute_net_solar_loss_factor
from solar_resource.pv_producer import SolarResourceConfig, _load_tmy, _require_pvlib
from solar_resource.soiling_profile import soiling_profile_from_config

FloatArray = npt.NDArray[np.float64]

HOURS_PER_YEAR = 8760.0
_KWH_PER_MWH = 1000.0
SUPPORTED_CHARGE_POLICIES = ("fill", "evening_need")
SUPPORTED_RATES = ("priority", "other")


def _strict(cls: type, raw: Mapping[str, Any], where: str) -> Dict[str, Any]:
    """Return ``raw`` as constructor kwargs, refusing missing or unknown keys."""
    names = {f.name for f in fields(cls)}
    missing = sorted(names - set(raw))
    extra = sorted(set(raw) - names)
    if missing or extra:
        raise ValueError(
            f"{where}: missing keys {missing} and unknown keys {extra}; "
            f"expected exactly {sorted(names)}."
        )
    return {name: raw[name] for name in names}


def _number(
    value: Any, where: str, *, lo: float = 0.0, positive: bool = False
) -> float:
    """Coerce to a finite float at or above ``lo`` (strictly above when ``positive``)."""
    if isinstance(value, bool):
        raise ValueError(f"{where} must be a number; got {value!r}")
    out = float(value)
    if not math.isfinite(out) or out < lo or (positive and out <= lo):
        raise ValueError(f"{where} out of range; got {value!r}")
    return out


# ---------------------------------------------------------------------------
# Hourly PV
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HourlyPv:
    """One TMY year of PV output at the point of connection.

    Attributes:
        timestamps_utc: Hour-start timestamps (pandas ``DatetimeIndex``, UTC).
        ac_mw: AC output after inverter clipping and the loss factor (MW = MWh per hour).
        dc_clipped_mw: DC power above the inverter's DC rating (lost to clipping).
        ac_nameplate_mw: Inverter AC nameplate.
        loss_factor: The loss retention applied after the inverter.
    """

    timestamps_utc: Any
    ac_mw: FloatArray
    dc_clipped_mw: FloatArray
    ac_nameplate_mw: float
    loss_factor: float

    @property
    def annual_mwh(self) -> float:
        """Annual AC energy."""
        return float(self.ac_mw.sum())


def hourly_pv(config: SolarResourceConfig) -> HourlyPv:
    """Hourly AC output of the producer's pvlib chain on its frozen TMY.

    The steps, inputs and loss factor are those of
    :func:`solar_resource.pv_producer.compute_solar_aep`'s TMY branch, so the annual sum
    equals its ``annual_energy_gwh``.

    Raises:
        ValueError: If the config has no ``tmy_path`` (the clear-sky path is annual only).
        RuntimeError: If pvlib is not installed.
    """
    if config.tmy_path is None:
        raise ValueError(
            "hourly_pv needs resource.solar.tmy_path (a frozen hourly TMY)"
        )
    pvlib = _require_pvlib()
    tmy = _load_tmy(config.tmy_path)
    times = tmy.index
    loc = pvlib.location.Location(
        config.latitude,
        config.longitude,
        tz=config.timezone,
        altitude=config.altitude_m,
    )
    solpos = loc.get_solarposition(times)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=config.tilt_deg,
        surface_azimuth=config.azimuth_deg,
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=tmy["dni"],
        ghi=tmy["ghi"],
        dhi=tmy["dhi"],
        dni_extra=pvlib.irradiance.get_extra_radiation(times),
        model="haydavies",
    )["poa_global"].clip(lower=0.0)
    cell = pvlib.temperature.faiman(
        poa, temp_air=tmy["temp_air"], wind_speed=tmy["wind_speed"]
    )
    pdc0_w = config.dc_capacity_mw * 1.0e6
    dc = pvlib.pvsystem.pvwatts_dc(poa, cell, pdc0_w, config.gamma_pdc_per_c)
    ac_nameplate_w = pdc0_w / config.dc_ac_ratio
    inverter_dc_w = ac_nameplate_w / config.inverter_eff_nom
    ac = pvlib.inverter.pvwatts(
        dc, pdc0=inverter_dc_w, eta_inv_nom=config.inverter_eff_nom
    ).clip(upper=ac_nameplate_w)
    factor = _loss_factor(config)
    ac_mw = np.asarray(ac.to_numpy(dtype=float) * factor / 1.0e6, dtype=np.float64)
    clipped = np.maximum(0.0, dc.to_numpy(dtype=float) - inverter_dc_w) / 1.0e6
    return HourlyPv(
        timestamps_utc=times,
        ac_mw=ac_mw,
        dc_clipped_mw=np.asarray(clipped, dtype=np.float64),
        ac_nameplate_mw=ac_nameplate_w / 1.0e6,
        loss_factor=factor,
    )


def _loss_factor(config: SolarResourceConfig) -> float:
    """The producer's post-inverter loss retention (flat or itemised, with soiling)."""
    soiling: Optional[float] = None
    if config.soiling_profile is not None:
        profile = soiling_profile_from_config(config.soiling_profile)
        assert profile is not None
        soiling = profile.effective_soiling_pct()
    if config.losses is not None:
        losses = dict(config.losses)
        if soiling is not None:
            losses["soiling_pct"] = soiling
        return float(compute_net_solar_loss_factor(losses))
    factor = 1.0 - config.system_loss_pct / 100.0
    if soiling is not None:
        factor *= 1.0 - soiling / 100.0
    return factor


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BessConfig:
    """Battery rating and efficiency.

    Attributes:
        power_mw: Charge and discharge power limit (AC).
        energy_mwh: Energy a full charge absorbs (the repository convention).
        round_trip_efficiency: AC-AC round-trip efficiency.
        charge_efficiency: Share of the round trip booked on charge; discharge
            efficiency is ``round_trip_efficiency / charge_efficiency``.
        min_soc_fraction, max_soc_fraction: State-of-charge window.
        grid_charging: Must be false: the battery charges only from the PV.
    """

    power_mw: float
    energy_mwh: float
    round_trip_efficiency: float
    charge_efficiency: float
    min_soc_fraction: float
    max_soc_fraction: float
    grid_charging: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "BessConfig":
        """Build from config, refusing missing, unknown or non-physical keys.

        Raises:
            ValueError: On a bad key, or when ``grid_charging`` is not false.
        """
        kw = _strict(cls, raw, "bess")
        for key in (
            "power_mw",
            "energy_mwh",
            "round_trip_efficiency",
            "charge_efficiency",
        ):
            kw[key] = _number(kw[key], f"bess.{key}", positive=True)
        for key in ("min_soc_fraction", "max_soc_fraction"):
            kw[key] = _number(kw[key], f"bess.{key}")
        if kw["grid_charging"] is not False:
            raise ValueError("bess.grid_charging must be false: PV-only charging")
        out = cls(**kw)
        if not out.round_trip_efficiency <= out.charge_efficiency <= 1.0:
            raise ValueError("bess.charge_efficiency must lie in [RTE, 1]")
        if out.round_trip_efficiency > 1.0:
            raise ValueError("bess.round_trip_efficiency must be <= 1")
        if not 0.0 <= out.min_soc_fraction < out.max_soc_fraction <= 1.0:
            raise ValueError("bess: need 0 <= min_soc_fraction < max_soc_fraction <= 1")
        return out

    @property
    def discharge_efficiency(self) -> float:
        """Discharge efficiency."""
        return self.round_trip_efficiency / self.charge_efficiency

    @property
    def soc_min_mwh(self) -> float:
        """Lowest stored energy."""
        return self.energy_mwh * self.min_soc_fraction

    @property
    def soc_max_mwh(self) -> float:
        """Highest stored energy."""
        return self.energy_mwh * self.max_soc_fraction

    @property
    def usable_mwh(self) -> float:
        """Stored energy between the state-of-charge limits."""
        return self.soc_max_mwh - self.soc_min_mwh


@dataclass(frozen=True)
class Window:
    """A discharge window in local clock time.

    Attributes:
        name: Label.
        start_minute, end_minute: Minutes after local midnight; ``end > start``.
        rate: ``"priority"`` or ``"other"``.
    """

    name: str
    start_minute: int
    end_minute: int
    rate: str

    @property
    def hours(self) -> float:
        """Length in hours."""
        return (self.end_minute - self.start_minute) / 60.0


def _minutes(hhmm: str, where: str) -> int:
    """``HH:MM`` as minutes after midnight."""
    try:
        t = dtime.fromisoformat(str(hhmm))
    except ValueError as exc:
        raise ValueError(f"{where} must be HH:MM; got {hhmm!r}") from exc
    return t.hour * 60 + t.minute


@dataclass(frozen=True)
class DispatchConfig:
    """Discharge windows, export limit and charge policy.

    Attributes:
        timezone: IANA zone of the window clock times.
        windows: The discharge windows, non-overlapping.
        export_limit_mw: The unit's combined export limit at the point of connection.
        charge_policy: ``"fill"`` (charge to full) or ``"evening_need"`` (charge only what
            the priority windows can export).
        cyclic_soc_tolerance_mwh: Fixed-point tolerance on the year's initial state.
        cyclic_soc_max_iterations: Iteration cap for that fixed point.
    """

    timezone: str
    windows: Tuple[Window, ...]
    export_limit_mw: float
    charge_policy: str
    cyclic_soc_tolerance_mwh: float
    cyclic_soc_max_iterations: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "DispatchConfig":
        """Build from config, refusing missing, unknown or overlapping entries."""
        kw = _strict(cls, raw, "dispatch")
        windows: List[Window] = []
        if not isinstance(kw["windows"], Mapping) or not kw["windows"]:
            raise ValueError("dispatch.windows must be a non-empty mapping")
        for name, w in kw["windows"].items():
            where = f"dispatch.windows.{name}"
            if not isinstance(w, Mapping) or set(w) != {
                "start_local",
                "end_local",
                "rate",
            }:
                raise ValueError(f"{where} needs exactly start_local, end_local, rate")
            start = _minutes(w["start_local"], f"{where}.start_local")
            end = _minutes(w["end_local"], f"{where}.end_local")
            if end <= start:
                raise ValueError(f"{where}: end must be after start (no midnight wrap)")
            if w["rate"] not in SUPPORTED_RATES:
                raise ValueError(f"{where}.rate must be one of {SUPPORTED_RATES}")
            windows.append(Window(str(name), start, end, str(w["rate"])))
        windows.sort(key=lambda w: w.start_minute)
        for a, b in zip(windows, windows[1:], strict=False):
            if b.start_minute < a.end_minute:
                raise ValueError(f"dispatch windows {a.name} and {b.name} overlap")
        if kw["charge_policy"] not in SUPPORTED_CHARGE_POLICIES:
            raise ValueError(
                f"dispatch.charge_policy must be one of {SUPPORTED_CHARGE_POLICIES}"
            )
        it = kw["cyclic_soc_max_iterations"]
        if isinstance(it, bool) or int(it) != it or int(it) < 1:
            raise ValueError(
                "dispatch.cyclic_soc_max_iterations must be a positive integer"
            )
        return cls(
            timezone=str(kw["timezone"]),
            windows=tuple(windows),
            export_limit_mw=_number(
                kw["export_limit_mw"], "dispatch.export_limit_mw", positive=True
            ),
            charge_policy=str(kw["charge_policy"]),
            cyclic_soc_tolerance_mwh=_number(
                kw["cyclic_soc_tolerance_mwh"],
                "dispatch.cyclic_soc_tolerance_mwh",
                positive=True,
            ),
            cyclic_soc_max_iterations=int(it),
        )


@dataclass(frozen=True)
class TariffConfig:
    """Feed-in rates for the unit and the wind.

    Attributes:
        priority_lkr_per_kwh: Rate in a ``priority`` window.
        other_lkr_per_kwh: Rate for every other exported kWh.
        priority_term_years: Years the priority rate is paid; then the other rate.
        wind_lkr_per_kwh: Wind rate.
    """

    priority_lkr_per_kwh: float
    other_lkr_per_kwh: float
    priority_term_years: int
    wind_lkr_per_kwh: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TariffConfig":
        """Build from config, refusing missing or unknown keys."""
        kw = _strict(cls, raw, "tariff")
        for key in ("priority_lkr_per_kwh", "other_lkr_per_kwh", "wind_lkr_per_kwh"):
            kw[key] = _number(kw[key], f"tariff.{key}")
        term = kw["priority_term_years"]
        if isinstance(term, bool) or int(term) != term or int(term) < 1:
            raise ValueError("tariff.priority_term_years must be a positive integer")
        kw["priority_term_years"] = int(term)
        out = cls(**kw)
        if out.priority_lkr_per_kwh < out.other_lkr_per_kwh:
            raise ValueError("tariff: the priority rate is below the other rate")
        return out

    def rate(self, window_rate: Optional[str], year: int) -> float:
        """LKR/kWh for energy exported under ``window_rate`` in operating ``year``."""
        if window_rate == "priority" and year <= self.priority_term_years:
            return self.priority_lkr_per_kwh
        return self.other_lkr_per_kwh


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DispatchSeries:
    """Hourly dispatch of one year (all MW over a one-hour step, i.e. MWh per step).

    Attributes:
        pv_mw: PV output offered.
        charge_mw: PV energy into the battery.
        pv_export_mw: PV exported directly.
        discharge_mw: Battery export.
        curtailed_mw: PV the export limit and the battery could not take.
        soc_end_mwh: Stored energy at the end of each step.
        window: Index into the dispatch windows, or -1 outside them.
        initial_soc_mwh: Stored energy before the first step (the cyclic fixed point).
        iterations: Passes to reach the fixed point.
    """

    pv_mw: FloatArray
    charge_mw: FloatArray
    pv_export_mw: FloatArray
    discharge_mw: FloatArray
    curtailed_mw: FloatArray
    soc_end_mwh: FloatArray
    window: npt.NDArray[np.int64]
    initial_soc_mwh: float
    iterations: int


def window_index(
    timestamps_utc: Any, windows: Sequence[Window], timezone: str, step_h: float = 1.0
) -> npt.NDArray[np.int64]:
    """Window of each step (``-1`` outside every window).

    A step belongs to a window when both its local start and its local end lie inside
    it.

    Raises:
        ValueError: If a window boundary falls inside a step, which would split the
            step's energy between periods.
    """
    import pandas as pd

    local = pd.DatetimeIndex(timestamps_utc).tz_convert(timezone)
    start = np.asarray(local.hour * 60 + local.minute, dtype=np.int64)
    step = int(round(step_h * 60))
    out = np.full(start.shape, -1, dtype=np.int64)
    starts_seen = set(int(s) for s in start)
    for k, w in enumerate(windows):
        for boundary in (w.start_minute, w.end_minute):
            if (boundary % (24 * 60)) not in starts_seen:
                raise ValueError(
                    f"window {w.name} boundary {boundary // 60:02d}:{boundary % 60:02d} "
                    "is not on a step boundary of the series"
                )
        inside = (start >= w.start_minute) & (start + step <= w.end_minute)
        out[inside] = k
    return out


def _run_once(
    pv: FloatArray,
    window: npt.NDArray[np.int64],
    windows: Sequence[Window],
    bess: BessConfig,
    cfg: DispatchConfig,
    soc0: float,
) -> Tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    """One chronological pass over the year from ``soc0``."""
    n = pv.size
    charge = np.zeros(n)
    export = np.zeros(n)
    discharge = np.zeros(n)
    curtailed = np.zeros(n)
    soc_end = np.zeros(n)
    eta_c = bess.charge_efficiency
    eta_d = bess.discharge_efficiency
    limit = cfg.export_limit_mw
    if cfg.charge_policy == "fill":
        target = bess.soc_max_mwh
    else:
        priority_mwh = sum(
            w.hours * min(bess.power_mw, limit) for w in windows if w.rate == "priority"
        )
        target = min(bess.soc_max_mwh, bess.soc_min_mwh + priority_mwh / eta_d)
    soc = soc0
    for i in range(n):
        p = float(pv[i])
        if window[i] >= 0:
            pv_out = min(p, limit)
            d = min(
                bess.power_mw, limit - pv_out, max(0.0, soc - bess.soc_min_mwh) * eta_d
            )
            soc = max(bess.soc_min_mwh, soc - d / eta_d)
            export[i] = pv_out
            discharge[i] = d
            curtailed[i] = p - pv_out
        else:
            c = max(0.0, min(p, bess.power_mw, (target - soc) / eta_c))
            soc = min(bess.soc_max_mwh, soc + c * eta_c)
            rest = p - c
            pv_out = min(rest, limit)
            charge[i] = c
            export[i] = pv_out
            curtailed[i] = rest - pv_out
        soc_end[i] = soc
    return charge, export, discharge, curtailed, soc_end


def dispatch(
    pv_mw: FloatArray,
    timestamps_utc: Any,
    bess: BessConfig,
    cfg: DispatchConfig,
) -> DispatchSeries:
    """Dispatch the battery over a repeating year of hourly PV.

    Raises:
        ValueError: If the series is not hourly, has negative PV, or the cyclic state
            does not converge.
    """
    import pandas as pd

    pv = np.asarray(pv_mw, dtype=np.float64)
    idx = pd.DatetimeIndex(timestamps_utc)
    if pv.shape != (len(idx),) or pv.size < 2:
        raise ValueError("pv_mw must be one value per timestamp")
    if ((idx[1:] - idx[:-1]) != pd.Timedelta(hours=1)).any():
        raise ValueError("the dispatcher needs consecutive hourly timestamps")
    if (pv < 0).any() or not np.isfinite(pv).all():
        raise ValueError("pv_mw must be finite and non-negative")
    window = window_index(idx, cfg.windows, cfg.timezone)
    soc0 = bess.soc_min_mwh
    for iteration in range(1, cfg.cyclic_soc_max_iterations + 1):
        charge, export, discharge, curtailed, soc_end = _run_once(
            pv, window, cfg.windows, bess, cfg, soc0
        )
        if abs(soc_end[-1] - soc0) <= cfg.cyclic_soc_tolerance_mwh:
            return DispatchSeries(
                pv_mw=pv,
                charge_mw=charge,
                pv_export_mw=export,
                discharge_mw=discharge,
                curtailed_mw=curtailed,
                soc_end_mwh=soc_end,
                window=window,
                initial_soc_mwh=soc0,
                iterations=iteration,
            )
        soc0 = float(soc_end[-1])
    raise ValueError("the cyclic state of charge did not converge")


# ---------------------------------------------------------------------------
# Annual summary and revenue
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AnnualEnergy:
    """One year's energy and revenue (MWh, LKR).

    Attributes:
        year: Operating year (1-based).
        pv_factor: PV output factor applied (warranted power fraction).
        pv_mwh: PV output.
        charge_mwh: PV into the battery.
        discharge_mwh_by_window: Battery export per window.
        discharge_mwh: Battery export.
        pv_export_mwh: PV exported directly (net of charging and curtailment).
        pv_export_mwh_by_window: That, per window and ``outside``.
        curtailed_mwh: PV the limit and battery could not take.
        unit_export_mwh: Everything the unit exports.
        export_mwh_by_rate: Unit export per tariff rate in this year.
        conversion_loss_mwh: Charge less discharge, less the change in stored energy.
        equivalent_full_cycles: Energy drawn from storage over usable energy.
        revenue_lkr_by_rate: Revenue per rate.
        revenue_lkr: Total unit revenue.
    """

    year: int
    pv_factor: float
    pv_mwh: float
    charge_mwh: float
    discharge_mwh_by_window: Dict[str, float]
    discharge_mwh: float
    pv_export_mwh: float
    pv_export_mwh_by_window: Dict[str, float]
    curtailed_mwh: float
    unit_export_mwh: float
    export_mwh_by_rate: Dict[str, float]
    conversion_loss_mwh: float
    equivalent_full_cycles: float
    revenue_lkr_by_rate: Dict[str, float]
    revenue_lkr: float


def summarise(
    series: DispatchSeries,
    bess: BessConfig,
    cfg: DispatchConfig,
    tariff: TariffConfig,
    *,
    year: int = 1,
    pv_factor: float = 1.0,
) -> AnnualEnergy:
    """Annual totals, energy by rate and revenue for one dispatched year."""
    names = [w.name for w in cfg.windows]
    by_win_d: Dict[str, float] = {}
    by_win_pv: Dict[str, float] = {
        "outside": float(series.pv_export_mw[series.window < 0].sum())
    }
    by_rate: Dict[str, float] = {r: 0.0 for r in SUPPORTED_RATES}
    by_rate["other"] += by_win_pv["outside"]
    for k, name in enumerate(names):
        mask = series.window == k
        by_win_d[name] = float(series.discharge_mw[mask].sum())
        by_win_pv[name] = float(series.pv_export_mw[mask].sum())
        rate_name = (
            "priority"
            if cfg.windows[k].rate == "priority" and year <= tariff.priority_term_years
            else "other"
        )
        by_rate[rate_name] += by_win_d[name] + by_win_pv[name]
    revenue = {
        "priority": by_rate["priority"] * _KWH_PER_MWH * tariff.priority_lkr_per_kwh,
        "other": by_rate["other"] * _KWH_PER_MWH * tariff.other_lkr_per_kwh,
    }
    charge = float(series.charge_mw.sum())
    discharge = float(series.discharge_mw.sum())
    d_soc = float(series.soc_end_mwh[-1] - series.initial_soc_mwh)
    drawn = discharge / bess.discharge_efficiency
    return AnnualEnergy(
        year=year,
        pv_factor=pv_factor,
        pv_mwh=float(series.pv_mw.sum()),
        charge_mwh=charge,
        discharge_mwh_by_window=by_win_d,
        discharge_mwh=discharge,
        pv_export_mwh=float(series.pv_export_mw.sum()),
        pv_export_mwh_by_window=by_win_pv,
        curtailed_mwh=float(series.curtailed_mw.sum()),
        unit_export_mwh=float(series.pv_export_mw.sum()) + discharge,
        export_mwh_by_rate=by_rate,
        conversion_loss_mwh=charge - discharge - d_soc,
        equivalent_full_cycles=drawn / bess.usable_mwh,
        revenue_lkr_by_rate=revenue,
        revenue_lkr=revenue["priority"] + revenue["other"],
    )


def degradation_path(
    pv: HourlyPv,
    factors: Sequence[float],
    bess: BessConfig,
    cfg: DispatchConfig,
    tariff: TariffConfig,
) -> List[AnnualEnergy]:
    """Dispatch each operating year with the PV scaled by that year's factor."""
    out = []
    for year, f in enumerate(factors, start=1):
        series = dispatch(pv.ac_mw * f, pv.timestamps_utc, bess, cfg)
        out.append(summarise(series, bess, cfg, tariff, year=year, pv_factor=f))
    return out


# ---------------------------------------------------------------------------
# Engine representation
# ---------------------------------------------------------------------------
def geometric_rate_matching_sum(series: Sequence[float]) -> float:
    """Rate ``r`` with ``sum_t s[0] (1 - r)^t == sum(s)`` over ``len(s)`` years.

    Bisection on ``[0, 0.5]``; returns ``0.0`` for a non-declining series.

    Raises:
        ValueError: If the series is empty or its first value is not positive.
    """
    if not series or series[0] <= 0:
        raise ValueError("series must be non-empty with a positive first value")
    target = float(sum(series))
    n = len(series)

    def total(r: float) -> float:
        return float(sum(series[0] * (1.0 - r) ** t for t in range(n)))

    if total(0.0) <= target:
        return 0.0
    lo, hi = 0.0, 0.5
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if total(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


@dataclass(frozen=True)
class WindBlock:
    """The wind technology as the scenario declares it.

    Attributes:
        capacity_mw: Wind capacity.
        capacity_factor: Net CF.
        degradation_pct: Annual degradation, percent.
    """

    capacity_mw: float
    capacity_factor: float
    degradation_pct: float

    def energy_mwh(self, year: int) -> float:
        """Engine wind energy in operating ``year`` (geometric degradation)."""
        return (
            self.capacity_mw
            * HOURS_PER_YEAR
            * self.capacity_factor
            * (1.0 - self.degradation_pct / 100.0) ** (year - 1)
        )


@dataclass(frozen=True)
class EngineRepresentation:
    """Engine fields for the unit, and the revenue check against the dispatcher.

    Attributes:
        solar_capacity_mw: Unit AC export capacity.
        solar_capacity_factor: Unit export over capacity x 8760, year 1.
        solar_aep_gwh: Unit export, year 1.
        solar_degradation_pct: Geometric rate matching the 20-year unit export.
        bess_tariff_lkr_per_kwh: The priority premium.
        bess_cycles_per_year: Priority-window export over (energy x RTE), year 1.
        bess_round_trip_efficiency: RTE.
        bess_contract_years: Priority term.
        bess_mdsc_fade_pct_annual: Geometric rate matching the priority-window export
            over the term (a decimal, as the engine reads it).
        tariff_lkr_per_kwh: Year-1 blend of the wind and other rates.
        project_capacity_mw: Wind plus unit capacity.
        project_capacity_factor: Capacity-weighted CF.
        dispatcher_revenue_lkr: Per year: unit revenue plus wind energy x wind rate.
        engine_revenue_lkr: Per year: the engine formulas on the fields above.
        max_later_year_gap_pct: Largest gap in years 2 onwards.
    """

    solar_capacity_mw: float
    solar_capacity_factor: float
    solar_aep_gwh: float
    solar_degradation_pct: float
    bess_tariff_lkr_per_kwh: float
    bess_cycles_per_year: float
    bess_round_trip_efficiency: float
    bess_contract_years: int
    bess_mdsc_fade_pct_annual: float
    tariff_lkr_per_kwh: float
    project_capacity_mw: float
    project_capacity_factor: float
    dispatcher_revenue_lkr: List[float]
    engine_revenue_lkr: List[float]
    max_later_year_gap_pct: float


def engine_bess_revenue_lkr(
    *,
    energy_mwh: float,
    cycles_per_year: float,
    round_trip_efficiency: float,
    tariff_lkr_per_kwh: float,
    fade: float,
    contract_years: int,
    year: int,
) -> float:
    """``finance.bess_revenue`` energy-tariff revenue for ``year`` (geometric fade, no floor hit)."""
    if year > contract_years:
        return 0.0
    return (
        energy_mwh
        * _KWH_PER_MWH
        * cycles_per_year
        * round_trip_efficiency
        * tariff_lkr_per_kwh
        * (1.0 - fade) ** (year - 1)
    )


def engine_representation(
    path: Sequence[AnnualEnergy],
    *,
    wind: WindBlock,
    capacity_mw: float,
    bess: BessConfig,
    tariff: TariffConfig,
) -> EngineRepresentation:
    """Map the dispatched unit onto the engine's fields and check the revenue per year."""
    unit = [a.unit_export_mwh for a in path]
    prio = [
        a.export_mwh_by_rate["priority"] for a in path[: tariff.priority_term_years]
    ]
    cf = unit[0] / (capacity_mw * HOURS_PER_YEAR)
    sol_deg = geometric_rate_matching_sum(unit)
    fade = geometric_rate_matching_sum(prio)
    cycles = prio[0] / (bess.energy_mwh * bess.round_trip_efficiency)
    premium = tariff.priority_lkr_per_kwh - tariff.other_lkr_per_kwh
    e_w1 = wind.energy_mwh(1)
    blend = (e_w1 * tariff.wind_lkr_per_kwh + unit[0] * tariff.other_lkr_per_kwh) / (
        e_w1 + unit[0]
    )
    disp: List[float] = []
    eng: List[float] = []
    for a in path:
        y = a.year
        disp.append(
            a.revenue_lkr + wind.energy_mwh(y) * _KWH_PER_MWH * tariff.wind_lkr_per_kwh
        )
        e_unit = unit[0] * (1.0 - sol_deg) ** (y - 1)
        gen = (wind.energy_mwh(y) + e_unit) * _KWH_PER_MWH * blend
        eng.append(
            gen
            + engine_bess_revenue_lkr(
                energy_mwh=bess.energy_mwh,
                cycles_per_year=cycles,
                round_trip_efficiency=bess.round_trip_efficiency,
                tariff_lkr_per_kwh=premium,
                fade=fade,
                contract_years=tariff.priority_term_years,
                year=y,
            )
        )
    gaps = [abs(e - d) / d * 100.0 for e, d in zip(eng[1:], disp[1:], strict=True)]
    total_cap = wind.capacity_mw + capacity_mw
    return EngineRepresentation(
        solar_capacity_mw=capacity_mw,
        solar_capacity_factor=cf,
        solar_aep_gwh=unit[0] / 1000.0,
        solar_degradation_pct=sol_deg * 100.0,
        bess_tariff_lkr_per_kwh=premium,
        bess_cycles_per_year=cycles,
        bess_round_trip_efficiency=bess.round_trip_efficiency,
        bess_contract_years=tariff.priority_term_years,
        bess_mdsc_fade_pct_annual=fade,
        tariff_lkr_per_kwh=blend,
        project_capacity_mw=total_cap,
        project_capacity_factor=(
            wind.capacity_mw * wind.capacity_factor + capacity_mw * cf
        )
        / total_cap,
        dispatcher_revenue_lkr=disp,
        engine_revenue_lkr=eng,
        max_later_year_gap_pct=max(gaps) if gaps else 0.0,
    )


def with_array(
    resource_solar: Mapping[str, Any],
    *,
    dc_capacity_mw: float,
    dc_ac_ratio: float,
    tilt_deg: float,
    azimuth_deg: float,
    gamma_pdc_per_c: float,
) -> SolarResourceConfig:
    """The producer config from a ``resource.solar`` block plus the array's own values.

    Raises:
        ValueError: If the block already states one of the inserted keys.
    """
    inserted = {
        "dc_capacity_mw": dc_capacity_mw,
        "dc_ac_ratio": dc_ac_ratio,
        "tilt_deg": tilt_deg,
        "azimuth_deg": azimuth_deg,
        "gamma_pdc_per_c": gamma_pdc_per_c,
    }
    clash = sorted(set(inserted) & set(resource_solar))
    if clash:
        raise ValueError(f"pv_yield.resource_solar must not state {clash}")
    block = {**dict(resource_solar), **inserted}
    return SolarResourceConfig.from_scenario({"resource": {"solar": block}})


def as_dict(obj: Any) -> Dict[str, Any]:
    """A result dataclass as a JSON-ready dict."""
    return asdict(obj)


__all__ = [
    "AnnualEnergy",
    "BessConfig",
    "DispatchConfig",
    "DispatchSeries",
    "EngineRepresentation",
    "HourlyPv",
    "SUPPORTED_CHARGE_POLICIES",
    "TariffConfig",
    "WindBlock",
    "Window",
    "as_dict",
    "degradation_path",
    "dispatch",
    "engine_bess_revenue_lkr",
    "engine_representation",
    "geometric_rate_matching_sum",
    "hourly_pv",
    "summarise",
    "window_index",
    "with_array",
]
