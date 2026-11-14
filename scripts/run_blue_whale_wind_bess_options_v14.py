#!/usr/bin/env python3
"""Hydra CLI: battery options for the separate 9.5 MW Blue Whale wind project (no solar).

Reads ``conf/blue_whale_wind_bess_options.yaml`` and prints one JSON object (CLI-01, CLI-03).
Every KPI comes from :func:`analytics.evaluation_v14.evaluate_with_overrides` on the wind
scenario (ARCH-04); :mod:`analytics.wind.wind_bess_options` builds each scenario.

One input comes from outside the repository: the public NASA POWER hourly reference at the
turbine point, content-checked against the pins in ``conf/blue_whale_met_mast_transfer.yaml``.
It only shapes the hour-by-hour charge and export headroom; the engine keeps the scenario's
own energy. Nothing private is read.

Usage::

    DUTCHBAY_NASA_POWER_DIR=/path/to/power \\
        .venv/bin/python scripts/run_blue_whale_wind_bess_options_v14.py \\
        output.summary_json=docs/blue_whale/wind_bess_options_summary.json
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import hydra
import numpy as np
import yaml
from omegaconf import DictConfig, OmegaConf
from scipy.stats import norm, qmc

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.wind import wind_bess_options as wbo

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "conf" / "blue_whale_wind_bess_options.yaml"
KPIS = ("project_npv", "equity_npv", "min_dscr", "project_irr", "equity_irr")
HOLD = (
    "SCREENING ONLY, not lender-grade. PUCSL's BESS tariff names solar PV only: every wind + "
    "BESS revenue basis here is a working assumption. The wind yield carries the met-mast "
    "HOLD (no measured Dutch Bay wind, no P90 for lenders); the hourly shape is a generic "
    "curve on a reanalysis; F-5 (no quarterly CFADS or intra-year DSCR figure supports a "
    "lender representation), #1110 and v15.6.1 stand. The 40 MW black-start battery is "
    "UNCONFIRMED (PUCSL discussions only, no document)."
)


def json_clean(value: Any) -> Any:
    """Strict-JSON form: NaN and infinities become ``None``; numpy scalars become Python."""
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _repo_path(rel: str) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else REPO_ROOT / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _nasa_dir(env: str) -> Path:
    raw = os.environ.get(env)
    if not raw:
        raise ValueError(
            f"No NASA POWER directory: set {env} to a path outside the repository."
        )
    path = Path(raw).expanduser().resolve()
    if path.is_relative_to(REPO_ROOT.resolve()):
        raise ValueError("The NASA POWER directory must be outside the repository.")
    return path


def _kpis(scenario: Mapping[str, Any]) -> Dict[str, float]:
    k = evaluate_with_overrides(raw_config=dict(scenario), overrides={})
    out = {m: float(k[m]) if k.get(m) is not None else math.nan for m in KPIS}
    out["discount_rate_used"] = float(k["discount_rate_used"])
    return out


def _rate(r: wbo.PeakRate) -> Dict[str, float]:
    return {
        "non_escalable": r.non_escalable,
        "escalable": r.escalable,
        "total": r.total,
    }


def _bisect(
    fn: Callable[[float], float], lo: float, hi: float, tol: float
) -> Optional[float]:
    """The root of a monotone ``fn`` in [lo, hi], or ``None`` when it does not change sign."""
    f_lo, f_hi = fn(lo), fn(hi)
    if f_lo == 0.0:
        return lo
    if (f_lo > 0) == (f_hi > 0):
        return None
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if (fn(mid) > 0) == (f_lo > 0):
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
def build_profile(
    cfg: Mapping[str, Any], scenario: Mapping[str, Any]
) -> Dict[str, Any]:
    """Hourly turbine output (MW at the connection point) and the checks behind it.

    Raises:
        ValueError: If the committed yield does not reproduce the scenario's capacity factor.
    """
    pcfg = cfg["profile"]
    ref = yaml.safe_load(_repo_path(pcfg["reference_config"]).read_text())["reference"]
    point = ref["points"][pcfg["reference_point"]]
    stamps, ws = wbo.load_reference_ws50(
        _nasa_dir(ref["dir_env"]),
        subdir=point["subdir"],
        first_year=int(ref["first_year"]),
        last_year=int(ref["last_year"]),
        pins=point["parameter_sha256"],
        latitude_deg_n=float(point["latitude_deg_n"]),
        longitude_deg_e=float(point["longitude_deg_e"]),
    )
    if float(ref["height_m"]) != float(pcfg["reference_height_m"]):
        raise ValueError("profile.reference_height_m differs from the reference config")
    summary = json.loads(_repo_path(pcfg["transfer_summary"]).read_text())
    alpha = float(summary["shear"]["extrapolation"]["alpha_all"])
    mean_hub = float(summary["long_term_130m"]["mean_speed_ms"])
    gross_cf = float(summary["yield"]["gross_capacity_factor"])
    total_loss = float(summary["yield"]["total_loss_pct"]) / 100.0
    wind = scenario["generation"]["technologies"]["wind"]
    if abs(gross_cf * (1.0 - total_loss) - float(wind["capacity_factor"])) > 5e-6:
        raise ValueError(
            "the transfer summary does not reproduce the scenario's wind CF"
        )
    if float(wind["capacity_mw"]) != float(pcfg["rated_mw"]):
        raise ValueError("profile.rated_mw differs from the scenario's wind capacity")
    hub = (
        ws * (float(pcfg["hub_height_m"]) / float(pcfg["reference_height_m"])) ** alpha
    )
    hub = hub * mean_hub / float(hub.mean())
    curve = {
        "rotor_diameter_m": float(pcfg["rotor_diameter_m"]),
        "air_density_kgm3": float(pcfg["air_density_kgm3"]),
        "rated_mw": float(pcfg["rated_mw"]),
        "cut_in_ms": float(pcfg["cut_in_ms"]),
        "cut_out_ms": float(pcfg["cut_out_ms"]),
    }
    cp = wbo.calibrate_cp(hub, gross_cf, **curve)
    gross = wbo.generic_power_mw(hub, cp=cp, **curve)
    poi = gross * float(np.prod([1.0 - f for f in pcfg["power_loss_fractions"]]))
    hours = np.array([int(s[8:10]) for s in stamps])
    window = np.isin(hours, np.asarray(cfg["window"]["utc_hours"]))
    n_years = len({s[:4] for s in stamps})
    return {
        "stamps": stamps,
        "poi_mw": poi,
        "window_wind_mwh": float((gross[window] * (1.0 - total_loss)).sum()) / n_years,
        "checks": {
            "hours": len(stamps),
            "first_utc": stamps[0],
            "last_utc": stamps[-1],
            "shear_alpha": alpha,
            "hub_mean_speed_ms": float(hub.mean()),
            "generic_cp": cp,
            "gross_cf": float(gross.mean()) / curve["rated_mw"],
            "target_gross_cf": gross_cf,
            "net_cf_scenario": float(wind["capacity_factor"]),
            "poi_peak_mw": float(poi.max()),
            "window_share_of_net_energy": float(gross[window].sum() / gross.sum()),
            "window_mean_poi_mw": float(poi[window].mean()),
            "window_hours_poi_above_9_mw_share": float((poi[window] > 9.0).mean()),
        },
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:  # noqa: C901 - one linear report
    """Evaluate every option under every reading and revenue basis; return the summary."""
    wbo.validate_config(cfg)
    scen_path = _repo_path(cfg["scenario"])
    scenario = yaml.safe_load(scen_path.read_text())
    tcfg = cfg["tariff"]
    if float(scenario["tariff"]["lkr_per_kwh"]) != float(tcfg["wind_lkr_per_kwh"]):
        raise ValueError("tariff.wind_lkr_per_kwh differs from the scenario's tariff")
    oi = scenario["tariff"]["om_indexation"]
    if float(oi["escalable_om_lkr_per_kwh"]) != float(tcfg["wind_components"][1]):
        raise ValueError(
            "tariff.wind_components escalable part differs from the scenario"
        )
    rates = wbo.derive_rates(tcfg)
    wind_rate = rates["wind"]

    # Index paths, as the scenario's own (tariff.om_indexation, opex, capex.price_basis).
    ccpi = float(oi["ccpi_inflation_pct"]) / 100.0
    usd_inf = float(oi["usd_inflation_pct"]) / 100.0
    depr_raw = oi["lkr_usd_depreciation_pct"]
    depr = (
        (1 + ccpi) / (1 + usd_inf) - 1
        if depr_raw == "relative_ppp"
        else float(depr_raw) / 100
    )
    index_rate = float(oi["ccpi_weight"]) * ccpi + float(oi["lkr_usd_weight"]) * depr
    adj = wbo.one_time_adjustment_factor(
        tcfg["one_time_adjustment_weights"],
        lkr_usd_depreciation=depr,
        ccpi_inflation=ccpi,
    )
    comp = rates["bess_component"]
    adjusted_component = wbo.PeakRate(comp.non_escalable * adj, comp.escalable)
    rte_pucsl = float(tcfg["pucsl_round_trip_efficiency"])
    peak_rates: Dict[str, wbo.PeakRate] = {
        "whole_wind_peak_rate": rates["whole_wind_peak_rate"],
        "stacked": rates["stacked"],
        "whole_wind_peak_rate_on_all_window_exports": rates["whole_wind_peak_rate"],
    }
    adjusted_whole = wbo.whole_wind_peak_rate(
        [wind_rate.non_escalable, wind_rate.escalable],
        [adjusted_component.non_escalable, adjusted_component.escalable],
        rte_pucsl,
    )

    prof = build_profile(cfg, scenario)
    bcfg = cfg["battery"]
    rte = float(bcfg["round_trip_efficiency"])
    price = bcfg["usd_per_kwh"]
    readings = {k: v["export_cap_mw"] for k, v in cfg["limits"]["readings"].items()}
    options = [dict(o) for o in cfg["options"]]
    cycled = [o for o in options if o["operation"] == "cycled"]
    window_hours = cfg["window"]["utc_hours"]
    cap_mw = float(scenario["generation"]["technologies"]["wind"]["capacity_mw"])
    a_limit = float(cfg["limits"]["standardised_ppa_mw"]) - cap_mw

    def run_dispatch(
        opts: List[Dict[str, Any]], rtes: Any, cap: Optional[float]
    ) -> wbo.DispatchResult:
        return wbo.dispatch(
            prof["poi_mw"],
            prof["stamps"],
            power_mw=[float(o["power_mw"]) for o in opts],
            energy_mwh=[float(o["energy_mwh"]) for o in opts],
            round_trip_efficiency=rtes,
            window_utc_hours=window_hours,
            export_cap_mw=cap,
        )

    disp = {r: run_dispatch(cycled, rte, cap) for r, cap in readings.items()}

    def energy(opt: Mapping[str, Any], reading: str) -> Tuple[float, float, float]:
        if opt["operation"] != "cycled":
            return 0.0, 0.0, 0.0
        i = next(j for j, o in enumerate(cycled) if o["name"] == opt["name"])
        d = disp[reading]
        return (
            float(d.delivered_mwh[i]),
            float(d.charged_mwh[i]),
            float(d.delivered_min_year_mwh[i]),
        )

    def scen(
        opt: Mapping[str, Any],
        *,
        delivered: float,
        charged: float,
        basis: str,
        peak: Optional[wbo.PeakRate] = None,
        usd_per_kwh: Optional[float] = None,
        rte_: float = rte,
        fade: float = 0.0,
        ym: float = 1.0,
    ) -> Dict[str, Any]:
        return wbo.scenario_with_battery(
            scenario,
            power_mw=float(opt["power_mw"]),
            energy_mwh=float(opt["energy_mwh"]),
            operation=str(opt["operation"]),
            usd_per_kwh=float(price["mode"] if usd_per_kwh is None else usd_per_kwh),
            om_usd_per_dc_kwh_year=float(bcfg["om_usd_per_dc_kwh_year"]),
            dc_per_nominal=float(bcfg["dc_per_nominal"]),
            round_trip_efficiency=rte_,
            delivered_mwh=delivered,
            charged_mwh=charged,
            peak_rate=peak_rates[basis] if peak is None else peak,
            wind_rate=wind_rate,
            contract_years=int(tcfg["contract_years"]),
            window_wind_mwh=(
                prof["window_wind_mwh"]
                if basis == "whole_wind_peak_rate_on_all_window_exports"
                else 0.0
            ),
            residual_fade=fade,
            wind_yield_multiplier=ym,
        )

    wind_only = _kpis(scenario)
    rate = wind_only["discount_rate_used"]
    timeline = scenario["timeline"]

    def pretax(
        opt: Mapping[str, Any], delivered: float, charged: float, peak: wbo.PeakRate
    ) -> Dict[str, Any]:
        return wbo.battery_pretax(
            energy_mwh=float(opt["energy_mwh"]),
            usd_per_kwh=float(price["mode"]),
            om_usd_per_dc_kwh_year=float(bcfg["om_usd_per_dc_kwh_year"]),
            dc_per_nominal=float(bcfg["dc_per_nominal"]),
            delivered_mwh=delivered,
            charged_mwh=charged,
            peak_rate=peak if opt["operation"] == "cycled" else wind_rate,
            wind_rate=wind_rate,
            contract_years=int(tcfg["contract_years"]),
            term_years=int(timeline["ops_years"]),
            lkr_per_usd=float(scenario["fx"]["start_lkr_per_usd"]),
            index_rate=index_rate,
            pre_operation_years=int(oi["pre_operation_years"]),
            opex_escalation=float(
                scenario["opex"]["currency_split"]["lkr_escalation_pct"]
            )
            / 100,
            capex_escalation=float(scenario["capex"]["price_basis"]["escalation_pct"])
            / 100,
            construction_years=int(timeline["construction_years"]),
            discount_rate=rate,
        )

    base_basis = cfg["revenue_bases"]["base"]
    bases = [base_basis, *cfg["revenue_bases"]["sensitivities"]]
    base_peak = peak_rates[base_basis]
    out_opts: Dict[str, Any] = {}
    for opt in options:
        row: Dict[str, Any] = {
            "power_mw": opt["power_mw"],
            "energy_mwh": opt["energy_mwh"],
            "operation": opt["operation"],
            "capex_usd_at_mode": float(opt["energy_mwh"])
            * 1000.0
            * float(price["mode"]),
            "fits_reading_A_turbine_plus_battery_le_limit": float(opt["power_mw"])
            <= a_limit + 1e-9,
            "readings": {},
        }
        for reading in readings:
            d, c, dmin = energy(opt, reading)
            rr: Dict[str, Any] = {
                "delivered_mwh_per_year": d,
                "charged_mwh_per_year": c,
                "delivered_min_year_mwh": dmin,
                "equivalent_full_cycles_per_year": d / float(opt["energy_mwh"]),
                "bases": {},
            }
            for basis in bases:
                k = _kpis(scen(opt, delivered=d, charged=c, basis=basis))
                k["delta_project_npv_vs_wind_only"] = (
                    k["project_npv"] - wind_only["project_npv"]
                )
                k["delta_equity_npv_vs_wind_only"] = (
                    k["equity_npv"] - wind_only["equity_npv"]
                )
                rr["bases"][basis] = k
            rr["battery_pretax_base_basis"] = pretax(opt, d, c, peak_rates[base_basis])
            adj_k = _kpis(
                scen(opt, delivered=d, charged=c, basis=base_basis, peak=adjusted_whole)
            )
            rr["one_time_adjustment_base_basis"] = {
                "delta_project_npv_vs_wind_only": adj_k["project_npv"]
                - wind_only["project_npv"],
                "equity_irr": adj_k["equity_irr"],
            }

            def gap_price(
                p: float, o: Mapping[str, Any] = opt, d_: float = d, c_: float = c
            ) -> float:
                k_ = _kpis(
                    scen(o, delivered=d_, charged=c_, basis=base_basis, usd_per_kwh=p)
                )
                return k_["project_npv"] - wind_only["project_npv"]

            rr["break_even_usd_per_kwh_base_basis"] = _bisect(
                gap_price, 0.01, 1000.0, 0.01
            )
            if opt["operation"] == "cycled":

                def gap_rate(
                    x: float, o: Mapping[str, Any] = opt, d_: float = d, c_: float = c
                ) -> float:
                    pk = wbo.PeakRate(base_peak.non_escalable + x, base_peak.escalable)
                    k_ = _kpis(
                        scen(o, delivered=d_, charged=c_, basis=base_basis, peak=pk)
                    )
                    return k_["project_npv"] - wind_only["project_npv"]

                x = _bisect(
                    gap_rate, -base_peak.non_escalable + wind_rate.total, 500.0, 1e-3
                )
                rr["break_even_peak_rate_lkr_per_kwh_base_basis"] = (
                    None if x is None else base_peak.total + x
                )
            row["readings"][reading] = rr
        out_opts[opt["name"]] = row

    # RTE grid (base basis, cycled options): one dispatch per grid point and reading.
    rte_grid: Dict[str, Any] = {}
    for reading, cap in readings.items():
        for r_ in cfg["monte_carlo"]["rte_grid"]:
            dg = run_dispatch(cycled, float(r_), cap)
            for i, opt in enumerate(cycled):
                k = _kpis(
                    scen(
                        opt,
                        delivered=float(dg.delivered_mwh[i]),
                        charged=float(dg.charged_mwh[i]),
                        basis=base_basis,
                        rte_=float(r_),
                    )
                )
                rte_grid.setdefault(opt["name"], {}).setdefault(reading, {})[
                    str(r_)
                ] = (k["project_npv"] - wind_only["project_npv"])

    # Monte Carlo (base basis): capex, battery RTE, residual fade and wind yield, LHS.
    mc = cfg["monte_carlo"]
    if mc["sampler"] != "lhs":
        raise ValueError("monte_carlo.sampler must be lhs")
    n = int(mc["n_trials"])
    u = qmc.LatinHypercube(d=4, seed=int(mc["seed"])).random(n)

    def tri(q: np.ndarray, lo: float, mode: float, hi: float) -> np.ndarray:
        cut = (mode - lo) / (hi - lo)
        return np.where(
            q < cut,
            lo + np.sqrt(q * (hi - lo) * (mode - lo)),
            hi - np.sqrt((1 - q) * (hi - lo) * (hi - mode)),
        )

    sig = float(mc["wind_yield_sigma"])
    draws = {
        "usd_per_kwh": tri(
            u[:, 0], float(price["low"]), float(price["mode"]), float(price["high"])
        ),
        "rte": float(mc["rte"]["low"])
        + (float(mc["rte"]["high"]) - float(mc["rte"]["low"])) * u[:, 1],
        "fade": (
            tri(
                u[:, 2],
                float(mc["residual_fade"]["low"]),
                float(mc["residual_fade"]["mode"]),
                float(mc["residual_fade"]["high"]),
            )
            if float(mc["residual_fade"]["high"]) > float(mc["residual_fade"]["low"])
            else np.full(n, float(mc["residual_fade"]["low"]))
        ),
        "wind_yield_multiplier": np.clip(
            1 + sig * norm.ppf(np.clip(u[:, 3], 1e-9, 1 - 1e-9)),
            1 - 3 * sig,
            1 + 3 * sig,
        ),
    }
    wind_mc = np.array(
        [
            _kpis(
                wbo.scenario_with_battery(
                    scenario,
                    power_mw=0.0,
                    energy_mwh=0.0,
                    operation="held",
                    usd_per_kwh=0.0,
                    om_usd_per_dc_kwh_year=0.0,
                    dc_per_nominal=1.0,
                    round_trip_efficiency=rte,
                    delivered_mwh=0.0,
                    charged_mwh=0.0,
                    peak_rate=wind_rate,
                    wind_rate=wind_rate,
                    contract_years=int(tcfg["contract_years"]),
                    wind_yield_multiplier=float(draws["wind_yield_multiplier"][j]),
                )
            )["project_npv"]
            for j in range(n)
        ]
    )
    mc_out: Dict[str, Any] = {
        "wind_only_project_npv": {
            "p50": float(np.percentile(wind_mc, 50)),
            "p90": float(np.percentile(wind_mc, 10)),
        }
    }
    for reading, cap in readings.items():
        tiled = [o for o in cycled for _ in range(n)]
        rtes = np.tile(draws["rte"], len(cycled))
        dm = run_dispatch(tiled, rtes, cap)
        for opt in options:
            if opt["operation"] == "held" and reading != next(iter(readings)):
                continue
            rows: List[Dict[str, float]] = []
            for j in range(n):
                if opt["operation"] == "cycled":
                    i = [o["name"] for o in cycled].index(opt["name"]) * n + j
                    d, c = float(dm.delivered_mwh[i]), float(dm.charged_mwh[i])
                else:
                    d = c = 0.0
                rows.append(
                    _kpis(
                        scen(
                            opt,
                            delivered=d,
                            charged=c,
                            basis=base_basis,
                            usd_per_kwh=float(draws["usd_per_kwh"][j]),
                            rte_=float(draws["rte"][j]),
                            fade=float(draws["fade"][j]),
                            ym=float(draws["wind_yield_multiplier"][j]),
                        )
                    )
                )
            gap = np.array([r["project_npv"] for r in rows]) - wind_mc
            key = (
                opt["name"]
                if opt["operation"] == "held"
                else f"{opt['name']}|{reading}"
            )
            mc_out[key] = {
                "delta_project_npv_vs_wind_only": {
                    "p50": float(np.percentile(gap, 50)),
                    "p90": float(np.percentile(gap, 10)),
                    "max": float(gap.max()),
                    "share_positive": float((gap > 0).mean()),
                },
                "equity_irr_p50": float(
                    np.nanpercentile([r["equity_irr"] for r in rows], 50)
                ),
                "min_dscr_p50": float(
                    np.nanpercentile([r["min_dscr"] for r in rows], 50)
                ),
            }

    dr = cfg["down_ramp"]
    total_rated = [cap_mw + float(x) for x in dr["illustrative_other_wind_mw"]]
    down_ramp = {
        str(x): wbo.down_ramp_firming(
            cap_mw, float(dr["substation_limit_mw_per_min"]) * cap_mw / tot
        )
        for x, tot in zip(dr["illustrative_other_wind_mw"], total_rated, strict=True)
    }
    worst = down_ramp[str(dr["illustrative_other_wind_mw"][-1])]
    prices = wbo.firming_unit_prices(
        dr["supplier"],
        power_mw=float(worst["power_mw"]),
        energy_mwh=float(worst["energy_mwh"]),
        all_in_usd_per_contracted_kwh=float(price["mode"]),
    )

    def firming_kpis(
        unit: Mapping[str, float], operation: str, reading: Optional[str]
    ) -> Dict[str, Any]:
        e_unit = float(unit["energy_mwh"])
        d = c = 0.0
        if operation == "cycled" and reading is not None:
            res = wbo.dispatch(
                prof["poi_mw"],
                prof["stamps"],
                power_mw=[float(unit["power_mw"])],
                energy_mwh=[e_unit],
                round_trip_efficiency=rte,
                window_utc_hours=window_hours,
                export_cap_mw=readings[reading],
            )
            d, c = float(res.delivered_mwh[0]), float(res.charged_mwh[0])
        k = _kpis(
            wbo.scenario_with_battery(
                scenario,
                power_mw=float(unit["power_mw"]),
                energy_mwh=e_unit,
                operation=operation,
                usd_per_kwh=float(unit["all_in_usd"]) / (e_unit * 1000.0),
                om_usd_per_dc_kwh_year=float(unit["om_usd_per_year"])
                / (e_unit * 1000.0),
                dc_per_nominal=1.0,
                round_trip_efficiency=rte,
                delivered_mwh=d,
                charged_mwh=c,
                peak_rate=peak_rates[base_basis],
                wind_rate=wind_rate,
                contract_years=int(tcfg["contract_years"]),
            )
        )
        k["delta_project_npv_vs_wind_only"] = (
            k["project_npv"] - wind_only["project_npv"]
        )
        k["delta_equity_npv_vs_wind_only"] = k["equity_npv"] - wind_only["equity_npv"]
        return dict(unit) | {
            "operation": operation,
            "delivered_mwh_per_year": d,
            "charged_mwh_per_year": c,
            "kpis": k,
        }

    firming: Dict[str, Any] = {
        name: firming_kpis(unit, "held", None) for name, unit in prices.items()
    }
    for reading in readings:
        firming[f"smallest_block_cycled|{reading}"] = firming_kpis(
            prices["smallest_block"], "cycled", reading
        )
    down_ramp["firming_unit_base_basis"] = firming

    return {
        "schema": "blue_whale_wind_bess_options_summary_v1",
        "hold": HOLD,
        "config_sha256": _sha256(CONFIG),
        "scenario_sha256": _sha256(scen_path),
        "transfer_summary_sha256": _sha256(
            _repo_path(cfg["profile"]["transfer_summary"])
        ),
        "model_version": (REPO_ROOT / "VERSION").read_text().strip(),
        "tariff": {
            "wind": _rate(wind_rate),
            "bess_component_ground": _rate(comp),
            "bess_component_floating": _rate(rates["bess_component_floating"]),
            "whole_wind_peak_rate": _rate(rates["whole_wind_peak_rate"]),
            "stacked": _rate(rates["stacked"]),
            "one_time_adjustment_factor": adj,
            "bess_component_after_adjustment": _rate(adjusted_component),
            "whole_wind_peak_rate_after_adjustment": _rate(adjusted_whole),
            "escalable_index_rate": index_rate,
        },
        "revenue_bases": {"base": base_basis, "sensitivities": bases[1:]},
        "profile": prof["checks"]
        | {"window_wind_mwh_per_year": prof["window_wind_mwh"]},
        "wind_only": wind_only,
        "options": out_opts,
        "rte_grid_delta_project_npv_base_basis": rte_grid,
        "monte_carlo_base_basis": {"n_trials": n, "seed": int(mc["seed"])} | mc_out,
        "down_ramp_illustrative": down_ramp,
    }


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="blue_whale_wind_bess_options",
)
def main(cfg: DictConfig) -> None:
    """Run every option and print one JSON object."""
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    summary_path = raw["output"]["summary_json"]
    out = json_clean(run(copy.deepcopy(raw)))
    text = json.dumps(out, sort_keys=True, allow_nan=False)
    if summary_path:
        _repo_path(summary_path).write_text(
            json.dumps(out, sort_keys=True, indent=1, allow_nan=False) + "\n"
        )
    print(text)


if __name__ == "__main__":
    main()
