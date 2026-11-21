"""Battery options for a wind-only project: tariff basis, dispatch and engine mapping.

A wind plant charges a co-located battery from its own turbine (the charged energy forgoes the
wind tariff) and discharges it in the Prioritized Feed-in Time. PUCSL's BESS tariff names solar
PV only, so the peak rate here is a WORKING ASSUMPTION built from the solar + BESS formula
(methodology s.5.1.2): priority = R_charging / RTE + BESS component.

Every KPI comes from :func:`analytics.evaluation_v14.evaluate_with_overrides`; this module only
builds the scenario the engine evaluates. :mod:`analytics.wind.wind_bess_options_runner` runs it
for any scenario that declares a ``storage_options`` block (#1578 U2), and for the single-site
config through its own script.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
from numpy.typing import NDArray

from analytics.core.returns import calculate_irr, calculate_npv
from analytics.storage_headline import strip_headline_option

FloatArray = NDArray[np.float64]
HOURS_PER_YEAR = 8760.0
REVENUE_BASES = (
    "whole_wind_peak_rate",
    "stacked",
    "whole_wind_peak_rate_on_all_window_exports",
)
OPERATIONS = ("cycled", "held")


# ---------------------------------------------------------------------------
# Config (strict: every key required, unknown keys refused)
# ---------------------------------------------------------------------------
CONFIG_KEYS: Dict[str, Optional[Tuple[str, ...]]] = {
    "schema_version": None,
    "scenario": None,
    "retrieved": None,
    "sources": None,
    "tariff": (
        "wind_lkr_per_kwh",
        "wind_components",
        "solar_bess_priority_components",
        "solar_bess_other_components",
        "floating_priority_components",
        "floating_other_components",
        "pucsl_round_trip_efficiency",
        "component_check_tolerance_lkr_per_kwh",
        "contract_years",
        "one_time_adjustment_weights",
    ),
    "revenue_bases": ("base", "sensitivities"),
    "window": ("utc_hours",),
    "limits": ("standardised_ppa_mw", "readings"),
    "profile": (
        "reference_config",
        "reference_point",
        "transfer_summary",
        "reference_height_m",
        "hub_height_m",
        "rotor_diameter_m",
        "rated_mw",
        "air_density_kgm3",
        "cut_in_ms",
        "cut_out_ms",
        "power_loss_fractions",
    ),
    "battery": (
        "duration_h_for_tariff",
        "usd_per_kwh",
        "om_usd_per_dc_kwh_year",
        "dc_per_nominal",
        "round_trip_efficiency",
        "black_start_reserve_mwh",
    ),
    "options": None,
    "down_ramp": (
        "substation_limit_mw_per_min",
        "illustrative_other_wind_mw",
        "supplier",
    ),
    "monte_carlo": (
        "seed",
        "n_trials",
        "sampler",
        "rte",
        "residual_fade",
        "wind_yield_sigma",
        "rte_grid",
    ),
    "output": ("summary_json",),
}
SUPPLIER_KEYS = (
    "offer_usd_per_dc_kwh",
    "dc_block_usd_per_dc_kwh",
    "ac_skid_usd",
    "ac_skid_mw",
    "ems_usd",
    "install_transport_share",
    "service_share_of_cif_per_year",
    "usable_per_dc",
    "smallest_block_dc_mwh",
    "power_cell_premium",
)
SCHEMA_VERSION = "blue_whale_wind_bess_options_v1"
OPTION_KEYS = ("name", "power_mw", "energy_mwh", "operation")


def validate_config(
    cfg: Mapping[str, Any], *, schema_version: str = SCHEMA_VERSION
) -> None:
    """Refuse a config with a missing or unknown key, or an inconsistent option list.

    ``schema_version`` is the value the config must carry: the single-site config's by
    default, or the one the scenario-driven runner gives the config it builds (#1578 U2).

    Raises:
        ValueError: On any missing or unknown key, a schema mismatch, an unknown revenue
            basis or operation, a duplicate option name or a non-positive option size.
    """
    keys = set(cfg)
    if keys != set(CONFIG_KEYS):
        raise ValueError(
            f"config keys differ: missing {sorted(set(CONFIG_KEYS) - keys)}, "
            f"unknown {sorted(keys - set(CONFIG_KEYS))}"
        )
    if cfg["schema_version"] != schema_version:
        raise ValueError(f"schema_version must be {schema_version}")
    for block, expected in CONFIG_KEYS.items():
        if expected is not None and set(cfg[block]) != set(expected):
            raise ValueError(
                f"{block}: missing {sorted(set(expected) - set(cfg[block]))}, "
                f"unknown {sorted(set(cfg[block]) - set(expected))}"
            )
    bases = [cfg["revenue_bases"]["base"], *cfg["revenue_bases"]["sensitivities"]]
    if any(b not in REVENUE_BASES for b in bases) or len(set(bases)) != len(bases):
        raise ValueError(f"revenue bases must be distinct members of {REVENUE_BASES}")
    names: List[str] = []
    for opt in cfg["options"]:
        if set(opt) != set(OPTION_KEYS):
            raise ValueError(f"option keys must be exactly {OPTION_KEYS}")
        if opt["operation"] not in OPERATIONS:
            raise ValueError(f"option {opt['name']}: unknown operation")
        if float(opt["power_mw"]) <= 0 or float(opt["energy_mwh"]) <= 0:
            raise ValueError(f"option {opt['name']}: sizes must be positive")
        names.append(str(opt["name"]))
    if len(set(names)) != len(names):
        raise ValueError("option names must be unique")
    supplier = cfg["down_ramp"]["supplier"]
    if set(supplier) != set(SUPPLIER_KEYS):
        raise ValueError(
            f"down_ramp.supplier: missing {sorted(set(SUPPLIER_KEYS) - set(supplier))}, "
            f"unknown {sorted(set(supplier) - set(SUPPLIER_KEYS))}"
        )
    nested = {
        "battery.usd_per_kwh": (cfg["battery"]["usd_per_kwh"], {"low", "mode", "high"}),
        "monte_carlo.rte": (cfg["monte_carlo"]["rte"], {"low", "high"}),
        "monte_carlo.residual_fade": (
            cfg["monte_carlo"]["residual_fade"],
            {"low", "mode", "high"},
        ),
        "tariff.one_time_adjustment_weights": (
            cfg["tariff"]["one_time_adjustment_weights"],
            {"lkr_usd", "ccpi"},
        ),
    }
    for name, (block, allowed) in nested.items():
        if set(block) != allowed:
            raise ValueError(f"{name} must hold exactly {sorted(allowed)}")
    for name, reading in cfg["limits"]["readings"].items():
        if set(reading) != {"export_cap_mw"}:
            raise ValueError(f"limits.readings.{name} must hold export_cap_mw only")


# ---------------------------------------------------------------------------
# Tariff basis
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PeakRate:
    """A peak (Prioritized Feed-in Time) rate as non-escalable and escalable parts (LKR/kWh)."""

    non_escalable: float
    escalable: float

    @property
    def total(self) -> float:
        """The whole rate."""
        return self.non_escalable + self.escalable


def bess_component(
    priority: Sequence[float], other: Sequence[float], pucsl_rte: float
) -> Tuple[float, float]:
    """The BESS component of a Table 7 line: priority - other / RTE, per tariff component.

    Args:
        priority: (non-escalable, escalable O&M) at the Prioritized Feed-in Time.
        other: (non-escalable, escalable O&M) at other periods (the standalone R_charging).
        pucsl_rte: The round-trip efficiency PUCSL used (s.2.2.3.5).

    Raises:
        ValueError: If the inputs are not two positive pairs or the RTE is outside (0, 1].
    """
    if len(priority) != 2 or len(other) != 2:
        raise ValueError("tariff components must be (non-escalable, escalable) pairs")
    if not 0.0 < pucsl_rte <= 1.0:
        raise ValueError(f"PUCSL round-trip efficiency {pucsl_rte} is outside (0, 1]")
    if min(*priority, *other) < 0:
        raise ValueError("tariff components must be non-negative")
    return (
        float(priority[0]) - float(other[0]) / pucsl_rte,
        float(priority[1]) - float(other[1]) / pucsl_rte,
    )


def whole_wind_peak_rate(
    wind: Sequence[float], component: Sequence[float], pucsl_rte: float
) -> PeakRate:
    """The solar + BESS formula with the wind tariff as R_charging.

    Non-escalable: wind_non_escalable / RTE + component_non_escalable; escalable:
    wind_escalable / RTE + component_escalable (the component's own escalable part is
    PUCSL's rounding remainder, kept, not dropped).
    """
    return PeakRate(
        non_escalable=float(wind[0]) / pucsl_rte + float(component[0]),
        escalable=float(wind[1]) / pucsl_rte + float(component[1]),
    )


def stacked_rate(wind: Sequence[float], component: Sequence[float]) -> PeakRate:
    """The wind tariff plus the BESS component, per discharged kWh.

    The component's own escalable part (PUCSL's rounding remainder) is kept, as in
    :func:`whole_wind_peak_rate`.
    """
    return PeakRate(
        non_escalable=float(wind[0]) + float(component[0]),
        escalable=float(wind[1]) + float(component[1]),
    )


def derive_rates(tariff: Mapping[str, Any]) -> Dict[str, PeakRate]:
    """Every rate the options use, from the config's ``tariff`` block.

    The BESS component is derived from both Table 7 lines (ground mounted and floating) and
    the two must agree within the configured tolerance, per component.

    Raises:
        ValueError: If the two lines disagree or the wind components do not sum to the tariff.
    """
    rte = float(tariff["pucsl_round_trip_efficiency"])
    tol = float(tariff["component_check_tolerance_lkr_per_kwh"])
    ground = bess_component(
        tariff["solar_bess_priority_components"],
        tariff["solar_bess_other_components"],
        rte,
    )
    floating = bess_component(
        tariff["floating_priority_components"], tariff["floating_other_components"], rte
    )
    if abs(ground[0] - floating[0]) > tol or abs(ground[1] - floating[1]) > tol:
        raise ValueError(
            f"BESS components disagree: ground {ground}, floating {floating}"
        )
    wind_c = [float(x) for x in tariff["wind_components"]]
    if not math.isclose(sum(wind_c), float(tariff["wind_lkr_per_kwh"]), abs_tol=1e-9):
        raise ValueError("wind components do not sum to the wind tariff")
    component = PeakRate(*ground)
    wind = PeakRate(*wind_c)
    return {
        "wind": wind,
        "bess_component": component,
        "bess_component_floating": PeakRate(*floating),
        "whole_wind_peak_rate": whole_wind_peak_rate(wind_c, ground, rte),
        "stacked": stacked_rate(wind_c, ground),
    }


def one_time_adjustment_factor(
    weights: Mapping[str, float], *, lkr_usd_depreciation: float, ccpi_inflation: float
) -> float:
    """Table 7 note [1]'s single adjustment after 12 months, for one year of each path."""
    w_fx, w_cpi = float(weights["lkr_usd"]), float(weights["ccpi"])
    if not math.isclose(w_fx + w_cpi, 1.0, abs_tol=1e-9):
        raise ValueError("one-time adjustment weights must sum to 1")
    return w_fx * (1.0 + lkr_usd_depreciation) + w_cpi * (1.0 + ccpi_inflation)


# ---------------------------------------------------------------------------
# Hourly turbine profile (shape only)
# ---------------------------------------------------------------------------
def parameter_digest(block: Mapping[str, Any]) -> str:
    """SHA-256 of a NASA POWER ``properties.parameter`` block, as the met-mast config pins it."""
    text = json.dumps(block, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def load_reference_ws50(
    directory: Path,
    *,
    subdir: str,
    first_year: int,
    last_year: int,
    pins: Mapping[str, str],
    latitude_deg_n: float,
    longitude_deg_e: float,
) -> Tuple[List[str], FloatArray]:
    """Read and content-check the pinned yearly NASA POWER files; return UTC stamps and WS50M.

    Raises:
        ValueError: On a digest mismatch, a fill value or a file at another point.
        FileNotFoundError: If a year's file is missing.
    """
    stamps: List[str] = []
    speeds: List[float] = []
    for year in range(first_year, last_year + 1):
        doc = json.loads((directory / subdir / f"wsd_{year}.json").read_text())
        block = doc["properties"]["parameter"]
        if parameter_digest(block) != pins[str(year)]:
            raise ValueError(f"reference {year} does not match its pin")
        lon, lat = doc["geometry"]["coordinates"][:2]
        if abs(lat - latitude_deg_n) > 1e-3 or abs(lon - longitude_deg_e) > 1e-3:
            raise ValueError(f"reference {year} is not at the configured point")
        for key in sorted(block["WS50M"]):
            value = float(block["WS50M"][key])
            if value < 0:
                raise ValueError(f"reference {year} carries a fill value at {key}")
            stamps.append(key)
            speeds.append(value)
    return stamps, np.asarray(speeds, dtype=np.float64)


def generic_power_mw(
    speed_ms: FloatArray,
    *,
    cp: float,
    rotor_diameter_m: float,
    air_density_kgm3: float,
    rated_mw: float,
    cut_in_ms: float,
    cut_out_ms: float,
) -> FloatArray:
    """A generic Cp-limited curve: 0.5 rho A Cp v^3, clipped at rated, zero outside cut-in/out."""
    area = math.pi * (rotor_diameter_m / 2.0) ** 2
    p = 0.5 * air_density_kgm3 * area * cp * speed_ms**3 / 1e6
    p = np.minimum(p, rated_mw)
    p[(speed_ms < cut_in_ms) | (speed_ms > cut_out_ms)] = 0.0
    return p


def calibrate_cp(speed_ms: FloatArray, target_gross_cf: float, **curve: float) -> float:
    """The Cp at which the generic curve's mean output equals ``target_gross_cf`` x rated.

    Raises:
        ValueError: If no Cp up to the Betz limit reaches the target.
    """
    rated = float(curve["rated_mw"])

    def cf(cp: float) -> float:
        return float(generic_power_mw(speed_ms, cp=cp, **curve).mean()) / rated

    lo, hi = 1e-6, 16.0 / 27.0
    if cf(hi) < target_gross_cf:
        raise ValueError("target gross capacity factor is above the Betz-limited curve")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if cf(mid) < target_gross_cf else (lo, mid)
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DispatchResult:
    """Mean-year and per-year battery energy (MWh) for each size."""

    delivered_mwh: FloatArray
    charged_mwh: FloatArray
    delivered_min_year_mwh: FloatArray
    years: Tuple[int, ...]


def dispatch(
    wind_mw: FloatArray,
    stamps_utc: Sequence[str],
    *,
    power_mw: Sequence[float],
    energy_mwh: Sequence[float],
    round_trip_efficiency: Union[float, Sequence[float]],
    window_utc_hours: Sequence[int],
    export_cap_mw: Optional[float],
    reserve_mwh: Union[float, Sequence[float]] = 0.0,
) -> DispatchResult:
    """Charge from the turbine only, outside the window; discharge only in the window.

    Every loss is booked on charge (input x RTE is stored; the nameplate is delivered energy).
    Charging is limited by the battery power and the turbine output; discharge by the power,
    the state of charge and the export headroom ``export_cap_mw - wind`` (``None``: no cap).
    The turbine is never curtailed for the battery. Leftover energy carries to the next day.
    ``round_trip_efficiency`` is one value or one per size, so a Monte Carlo runs in one pass.
    ``reserve_mwh`` (one value or one per size) is a state-of-charge floor that discharge for
    revenue never draws below: the energy held for black start or down-ramp firming. It is
    charged first, like any other energy, and never released in this dispatch.
    """
    p = np.asarray(power_mw, dtype=np.float64)
    e = np.asarray(energy_mwh, dtype=np.float64)
    if p.ndim != 1 or p.shape != e.shape or (p < 0).any() or (e < 0).any():
        raise ValueError("power and energy must be equal-length non-negative arrays")
    rte = np.broadcast_to(np.asarray(round_trip_efficiency, dtype=np.float64), p.shape)
    if (rte <= 0.0).any() or (rte > 1.0).any():
        raise ValueError("round-trip efficiency must be in (0, 1]")
    floor = np.broadcast_to(np.asarray(reserve_mwh, dtype=np.float64), p.shape)
    if (floor < 0.0).any() or (floor > e).any():
        raise ValueError("the reserve must be in [0, energy]")
    hours = np.array([int(s[8:10]) for s in stamps_utc])
    years = np.array([int(s[:4]) for s in stamps_utc])
    window = np.isin(hours, np.asarray(window_utc_hours))
    uniq = tuple(sorted(set(years.tolist())))
    d = {y: np.zeros_like(p) for y in uniq}
    c = {y: np.zeros_like(p) for y in uniq}
    soc = np.zeros_like(p)
    cap = math.inf if export_cap_mw is None else float(export_cap_mw)
    for i in range(len(wind_mw)):
        w = float(wind_mw[i])
        if window[i]:
            out = np.minimum(
                np.minimum(p, max(cap - w, 0.0)), np.maximum(soc - floor, 0.0)
            )
            soc -= out
            d[years[i]] += out
        else:
            inp = np.minimum(np.minimum(p, w), (e - soc) / rte)
            soc = np.minimum(soc + inp * rte, e)
            c[years[i]] += inp
    dm = np.mean([d[y] for y in uniq], axis=0)
    cm = np.mean([c[y] for y in uniq], axis=0)
    return DispatchResult(dm, cm, np.min([d[y] for y in uniq], axis=0), uniq)


# ---------------------------------------------------------------------------
# Engine mapping
# ---------------------------------------------------------------------------
def _set_dotted(scenario: Dict[str, Any], dotted: str, value: Any) -> None:
    node = scenario
    parts = dotted.split(".")
    for key in parts[:-1]:
        node = node[key]
    if parts[-1] not in node:
        raise KeyError(f"scenario has no {dotted}")
    node[parts[-1]] = value


def scenario_with_battery(
    scenario: Mapping[str, Any],
    *,
    power_mw: float,
    energy_mwh: float,
    operation: str,
    usd_per_kwh: float,
    om_usd_per_dc_kwh_year: float,
    dc_per_nominal: float,
    round_trip_efficiency: float,
    delivered_mwh: float,
    charged_mwh: float,
    peak_rate: PeakRate,
    wind_rate: PeakRate,
    contract_years: int,
    window_wind_mwh: float = 0.0,
    residual_fade: float = 0.0,
    wind_yield_multiplier: float = 1.0,
    scenario_overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """The wind scenario carrying one battery, for ``evaluate_with_overrides``.

    Mapping: the wind capacity factor falls by the round-trip loss (charged - delivered), for
    the whole term (after the BESS contract the discharged energy earns the standalone wind
    tariff, PUCSL Table 7 note [2]); ``bess_1`` (``energy_tariff``) is paid the peak rate's
    premium over the wind tariff on the delivered kWh for ``contract_years``. A ``held`` battery
    is never cycled: capex and O&M only. ``window_wind_mwh`` > 0 also pays the premium on the
    turbine's own window exports (the all-window-exports reading).

    ``bess_1`` carries ``availability_factor`` 1.0 (ASSUMPTION: no further availability
    derate, since the delivered energy already comes from the hourly dispatch) and
    ``availability_pct`` 97.0, which the energy-tariff revenue does not read.

    Conservative simplifications, stated rather than modelled: the battery keeps cycling (and
    losing the round trip) after the contract, where an operator would hold it; standby and
    auxiliary load (BMS, HVAC) is excluded for every option.

    Raises:
        ValueError: On an unknown operation, a negative premium or inconsistent energy.
    """
    if operation not in OPERATIONS:
        raise ValueError(f"operation {operation!r} is not one of {OPERATIONS}")
    # #1823: the battery is added to the wind-only case, so a scenario's own headline battery
    # request is dropped first (one already carried into the figures is refused).
    s: Dict[str, Any] = copy.deepcopy(strip_headline_option(scenario))
    for key, value in (scenario_overrides or {}).items():
        _set_dotted(s, key, value)
    wind = s["generation"]["technologies"]["wind"]
    cap_mw = float(wind["capacity_mw"])
    wind["capacity_factor"] = float(wind["capacity_factor"]) * wind_yield_multiplier
    if power_mw <= 0.0:
        s["project"]["capacity_factor"] = wind["capacity_factor"]
        return s
    if operation == "held":
        delivered_mwh = charged_mwh = window_wind_mwh = 0.0
    if delivered_mwh < 0 or charged_mwh < delivered_mwh:
        raise ValueError("delivered energy must be in [0, charged]")
    capex = energy_mwh * 1000.0 * usd_per_kwh
    s["capex"]["usd_total"] = float(s["capex"]["usd_total"]) + capex
    s["capex"]["capex_per_kw_usd"] = s["capex"]["usd_total"] / (cap_mw * 1000.0)
    om = energy_mwh * 1000.0 * dc_per_nominal * om_usd_per_dc_kwh_year
    s["opex"]["currency_split"]["components"].append(
        {"name": "bess_om", "usd_per_year": om, "usd_share": 0.0}
    )
    s["opex"]["usd_per_year"] = float(s["opex"]["usd_per_year"]) + om
    s["opex"]["opex_per_kw_yr_usd"] = s["opex"]["usd_per_year"] / (cap_mw * 1000.0)
    wind["capacity_factor"] -= (charged_mwh - delivered_mwh) / (cap_mw * HOURS_PER_YEAR)
    s["project"]["capacity_factor"] = wind["capacity_factor"]
    premium = PeakRate(
        peak_rate.non_escalable - wind_rate.non_escalable,
        peak_rate.escalable - wind_rate.escalable,
    )
    if premium.total < 0:
        raise ValueError("the peak rate is below the wind tariff")
    paid = delivered_mwh + window_wind_mwh
    cycled = operation == "cycled" and paid > 0
    s["generation"]["technologies"]["bess_1"] = {
        "type": "bess",
        "power_mw": power_mw,
        "energy_mwh": energy_mwh,
        "duration_h": energy_mwh / power_mw,
        "capex_usd": capex,
        "availability_pct": 97.0,
        "revenue": {
            "model": "energy_tariff",
            "tariff_lkr_per_kwh": premium.total if cycled else 0.0,
            "escalable_om_lkr_per_kwh": (
                min(max(premium.escalable, 0.0), premium.total) if cycled else 0.0
            ),
            "cycles_per_year": (
                paid / (energy_mwh * round_trip_efficiency) if cycled else 1.0
            ),
            "round_trip_efficiency": round_trip_efficiency,
            "availability_factor": 1.0,
            "contract_years": contract_years,
            "mdsc_fade_pct_annual": residual_fade,
        },
    }
    return s


def battery_pretax(
    *,
    energy_mwh: float,
    usd_per_kwh: float,
    om_usd_per_dc_kwh_year: float,
    dc_per_nominal: float,
    delivered_mwh: float,
    charged_mwh: float,
    peak_rate: PeakRate,
    wind_rate: PeakRate,
    contract_years: int,
    term_years: int,
    lkr_per_usd: float,
    index_rate: float,
    pre_operation_years: int,
    opex_escalation: float,
    capex_price_factor: float,
    construction_years: int,
    discount_rate: float,
) -> Dict[str, Optional[float]]:
    """The battery's own pre-tax cash flow (USD): capex at the draw, then margin less O&M.

    Revenue in a contract year is delivered x peak rate - charged x wind tariff, each with its
    escalable part indexed at ``index_rate`` from the tariff base year; after the contract the
    delivered energy earns the wind tariff. No tax, debt or CFADS haircut.

    ``capex_price_factor`` is the engine's own price-year escalation of the capex
    (``capex.price_basis``), so the battery is priced at the same draw as in the engine.
    """
    capex = energy_mwh * 1000.0 * usd_per_kwh * capex_price_factor
    flows = [-capex] + [0.0] * (construction_years - 1)
    for year in range(1, term_years + 1):
        idx = (1.0 + index_rate) ** (pre_operation_years + year - 1)
        wind_lkr = wind_rate.non_escalable + wind_rate.escalable * idx
        peak_lkr = (
            peak_rate.non_escalable + peak_rate.escalable * idx
            if year <= contract_years
            else wind_lkr
        )
        revenue = (
            (delivered_mwh * peak_lkr - charged_mwh * wind_lkr) * 1000.0 / lkr_per_usd
        )
        om = (
            energy_mwh
            * 1000.0
            * dc_per_nominal
            * om_usd_per_dc_kwh_year
            * (1.0 + opex_escalation) ** (pre_operation_years + year - 1)
        )
        flows.append(revenue - om)
    rate_of_return = calculate_irr(flows)
    return {
        "npv_usd": calculate_npv(flows, discount_rate),
        "irr": None if rate_of_return is None else float(rate_of_return),
        "capex_usd_at_draw": capex,
        "year1_net_usd": flows[construction_years],
    }


def down_ramp_firming(rated_mw: float, ramp_mw_per_min: float) -> Dict[str, float]:
    """Worst-case firming of a full drop from rated at an allowed ramp: power and energy."""
    if ramp_mw_per_min <= 0:
        raise ValueError("ramp rate must be positive")
    minutes = rated_mw / ramp_mw_per_min
    return {
        "power_mw": rated_mw,
        "energy_mwh": rated_mw * minutes / 2.0 / 60.0,
        "minutes": minutes,
    }


def _all_in_factor(
    supplier: Mapping[str, Any], all_in_usd_per_kwh_mode: float
) -> float:
    """All-in / CIF: the repository's all-in mode over the offer per usable kWh.

    The offer per usable kWh is the offer per DC kWh over the published (rounded) usable
    fraction (owner decision, 2026-11-15).
    """
    usable = float(supplier["usable_per_dc"])
    return all_in_usd_per_kwh_mode / (float(supplier["offer_usd_per_dc_kwh"]) / usable)


def bottom_up_price(
    supplier: Mapping[str, Any],
    *,
    power_mw: float,
    energy_mwh: float,
    all_in_usd_per_kwh_mode: float,
) -> Dict[str, float]:
    """Price a battery bottom-up from the supplier's lines; CIF and all-in (USD).

    The skid is taken pro rata by power, the EMS once per site, and the DC energy for
    ``energy_mwh`` usable at the offer's DC rate, plus the installation and transport share.
    All-in uses the same factor as :func:`firming_unit_prices`. The flat per-kWh mode prices a
    battery as a slice of a 4-hour product, so it understates the power-related and per-site
    cost of a short-duration unit; this is the comparison.

    Raises:
        ValueError: If the power or the energy is not positive.
    """
    if power_mw <= 0.0 or energy_mwh <= 0.0:
        raise ValueError("bottom-up power and energy must be positive")
    usable = float(supplier["usable_per_dc"])
    soft = 1.0 + float(supplier["install_transport_share"])
    cif = (
        float(supplier["ac_skid_usd"]) * power_mw / float(supplier["ac_skid_mw"])
        + float(supplier["ems_usd"])
        + energy_mwh / usable * 1000.0 * float(supplier["dc_block_usd_per_dc_kwh"])
    ) * soft
    all_in = cif * _all_in_factor(supplier, all_in_usd_per_kwh_mode)
    return {
        "cif_usd": cif,
        "all_in_usd": all_in,
        "all_in_usd_per_kwh": all_in / (energy_mwh * 1000.0),
    }


def firming_unit_prices(
    supplier: Mapping[str, Any],
    *,
    power_mw: float,
    energy_mwh: float,
    all_in_usd_per_kwh_mode: float,
) -> Dict[str, Dict[str, float]]:
    """Price a held firming unit two ways from a supplier offer; CIF, all-in and O&M (USD).

    ``power_heavy_cells_x{k}``: one AC skid (needs ``power_mw`` <= the skid), the EMS, and the
    DC energy for ``energy_mwh`` usable at the offer's DC rate times a power-cell premium ``k``,
    plus the installation and transport share. ``smallest_block``: the supplier's smallest
    block with one skid at the flat offer rate per DC kWh. All-in = CIF x
    ``all_in_usd_per_kwh_mode`` / the offer's CIF per usable kWh, which is the offer per DC
    kWh over the published (rounded) usable fraction. O&M = a generic service share of CIF a
    year (an assumption, not from the offer).

    Raises:
        ValueError: If the power exceeds one skid or an input is not positive.
    """
    skid_mw = float(supplier["ac_skid_mw"])
    if not 0.0 < power_mw <= skid_mw or energy_mwh <= 0.0:
        raise ValueError("firming power must be in (0, one skid] and energy positive")
    usable = float(supplier["usable_per_dc"])
    soft = 1.0 + float(supplier["install_transport_share"])
    factor = _all_in_factor(supplier, all_in_usd_per_kwh_mode)
    service = float(supplier["service_share_of_cif_per_year"])
    dc_kwh = energy_mwh / usable * 1000.0
    out: Dict[str, Dict[str, float]] = {}
    for k in supplier["power_cell_premium"]:
        cif = (
            float(supplier["ac_skid_usd"])
            + float(supplier["ems_usd"])
            + dc_kwh * float(supplier["dc_block_usd_per_dc_kwh"]) * float(k)
        ) * soft
        out[f"power_heavy_cells_x{float(k):g}"] = {
            "power_mw": power_mw,
            "energy_mwh": energy_mwh,
            "cif_usd": cif,
            "all_in_usd": cif * factor,
            "om_usd_per_year": cif * service,
        }
    block_dc = float(supplier["smallest_block_dc_mwh"])
    cif = block_dc * 1000.0 * float(supplier["offer_usd_per_dc_kwh"])
    out["smallest_block"] = {
        "power_mw": power_mw,
        "energy_mwh": block_dc * usable,
        "cif_usd": cif,
        "all_in_usd": cif * factor,
        "om_usd_per_year": cif * service,
    }
    return out


__all__ = [
    "DispatchResult",
    "PeakRate",
    "REVENUE_BASES",
    "battery_pretax",
    "bess_component",
    "bottom_up_price",
    "calibrate_cp",
    "derive_rates",
    "dispatch",
    "down_ramp_firming",
    "firming_unit_prices",
    "generic_power_mw",
    "load_reference_ws50",
    "one_time_adjustment_factor",
    "parameter_digest",
    "scenario_with_battery",
    "stacked_rate",
    "validate_config",
    "whole_wind_peak_rate",
]
