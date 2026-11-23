"""Run the wind battery options for one options config (#1578 U2).

The evaluation behind both the single-site options script and the scenario-driven runner
(``scripts/run_wind_bess_options_v14.py scenario=<path>``), moved here unchanged from the
single-site script. :func:`run_options` evaluates every battery option under every reading of
the export limit and every revenue basis, through
:func:`analytics.evaluation_v14.evaluate_with_overrides` on the wind scenario (ARCH-04), and
returns the figures. Each caller adds its own provenance and hold text.

:func:`config_from_block` builds the options config from a scenario's ``storage_options``
block (:mod:`analytics.site_analysis_blocks`) and the method config, and
:func:`run_wind_bess_options_for_scenario` runs it for any scenario, or reports the analysis
as not applicable when the scenario has no block. No site name, path or figure is held here
(``ARCH-01``).

One input comes from outside the repository: the public NASA POWER hourly reference at the
turbine point named by the block's ``hourly_profile``, content-checked against the pins in
the reference config it names. It shapes the hour-by-hour charge and export headroom only;
the engine keeps the scenario's own energy. Nothing private is read.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import numpy as np
import yaml
from scipy.stats import norm, qmc

from analytics.evaluation_v14 import evaluate_with_overrides, evaluated_scenario_config
from analytics.storage_headline import strip_headline_option
from analytics.wind import wind_bess_options as wbo

REPO_ROOT = Path(__file__).resolve().parents[2]
KPIS = ("project_npv", "equity_npv", "min_dscr", "project_irr", "equity_irr")


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


def repo_path(rel: str) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else REPO_ROOT / path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nasa_dir(env: str) -> Path:
    raw = os.environ.get(env)
    if not raw:
        raise ValueError(
            f"No NASA POWER directory: set {env} to a path outside the repository."
        )
    path = Path(raw).expanduser().resolve()
    if path.is_relative_to(REPO_ROOT.resolve()):
        raise ValueError("The NASA POWER directory must be outside the repository.")
    return path


def price_basis_applied(scenario: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The capex price-year escalation the engine applies to ``scenario``, or ``None``.

    Read through :func:`analytics.evaluation_v14.evaluated_scenario_config`, the gateway's
    view of the scenario as the engine prices it (native capex normalised first, then the
    ``capex.price_basis`` block applied), so this module imports no finance code
    (FRAMEWORK-03). ``None`` when the scenario declares no price basis.
    """
    capex = evaluated_scenario_config(dict(scenario)).get("capex")
    applied = capex.get("price_basis_applied") if isinstance(capex, Mapping) else None
    return dict(applied) if isinstance(applied, Mapping) else None


def kpis(scenario: Mapping[str, Any]) -> Dict[str, float]:
    # Every capex amount here is priced through capex.usd_total. Refuse a scenario in which
    # the engine would escalate some other capex key automatically (#1704), so the summary
    # can never absorb that escalation unrecorded.
    if (price_basis_applied(scenario) or {}).get("automatically_escalated"):
        raise ValueError("a capex amount would be escalated automatically (#1704)")
    k = evaluate_with_overrides(raw_config=dict(scenario), overrides={})
    out = {m: float(k[m]) if k.get(m) is not None else math.nan for m in KPIS}
    out["discount_rate_used"] = float(k["discount_rate_used"])
    return out


def rate_parts(r: wbo.PeakRate) -> Dict[str, float]:
    return {
        "non_escalable": r.non_escalable,
        "escalable": r.escalable,
        "total": r.total,
    }


def bisect_root(
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
    cfg: Mapping[str, Any],
    scenario: Mapping[str, Any],
    *,
    high_output_check_mw: float,
) -> Dict[str, Any]:
    """Hourly turbine output (MW at the connection point) and the checks behind it.

    ``high_output_check_mw`` names the output level whose share of window hours is reported
    as a check (``window_hours_poi_above_<x>_mw_share``).

    Raises:
        ValueError: If the committed yield does not reproduce the scenario's capacity factor.
    """
    pcfg = cfg["profile"]
    ref = yaml.safe_load(repo_path(pcfg["reference_config"]).read_text())["reference"]
    point = ref["points"][pcfg["reference_point"]]
    stamps, ws = wbo.load_reference_ws50(
        nasa_dir(ref["dir_env"]),
        subdir=point["subdir"],
        first_year=int(ref["first_year"]),
        last_year=int(ref["last_year"]),
        pins=point["parameter_sha256"],
        latitude_deg_n=float(point["latitude_deg_n"]),
        longitude_deg_e=float(point["longitude_deg_e"]),
    )
    if float(ref["height_m"]) != float(pcfg["reference_height_m"]):
        raise ValueError("profile.reference_height_m differs from the reference config")
    summary = json.loads(repo_path(pcfg["transfer_summary"]).read_text())
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
            f"window_hours_poi_above_{high_output_check_mw:g}_mw_share": float(
                (poi[window] > high_output_check_mw).mean()
            ),
        },
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run_options(  # noqa: C901 - one linear report
    cfg: Mapping[str, Any],
    *,
    schema_version: str,
    profile_builder: Callable[[Mapping[str, Any], Mapping[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate every option under every reading and revenue basis; return the figures.

    Args:
        cfg: The options config in the shape :func:`wbo.validate_config` checks.
        schema_version: The ``schema_version`` the config must carry.
        profile_builder: Builds the hourly profile from ``(cfg, scenario)``; normally
            :func:`build_profile` with the site's high-output check bound.

    Returns:
        Every figure of the summary. The caller adds its own provenance and hold text.
    """
    wbo.validate_config(cfg, schema_version=schema_version)
    scen_path = repo_path(cfg["scenario"])
    # #1823: every option is measured against the wind-only case, so a scenario that carries
    # one held option in its headline KPIs is read here without that request.
    scenario = strip_headline_option(yaml.safe_load(scen_path.read_text()))
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

    prof = profile_builder(cfg, scenario)
    bcfg = cfg["battery"]
    rte = float(bcfg["round_trip_efficiency"])
    price = bcfg["usd_per_kwh"]
    readings = {k: v["export_cap_mw"] for k, v in cfg["limits"]["readings"].items()}
    options = [dict(o) for o in cfg["options"]]
    cycled = [o for o in options if o["operation"] == "cycled"]
    window_hours = cfg["window"]["utc_hours"]
    cap_mw = float(scenario["generation"]["technologies"]["wind"]["capacity_mw"])
    a_limit = float(cfg["limits"]["standardised_ppa_mw"]) - cap_mw

    reserve = float(bcfg["black_start_reserve_mwh"])

    def run_dispatch(
        opts: List[Dict[str, Any]],
        rtes: Any,
        cap: Optional[float],
        floor: Optional[float] = None,
    ) -> wbo.DispatchResult:
        return wbo.dispatch(
            prof["poi_mw"],
            prof["stamps"],
            power_mw=[float(o["power_mw"]) for o in opts],
            energy_mwh=[float(o["energy_mwh"]) for o in opts],
            round_trip_efficiency=rtes,
            window_utc_hours=window_hours,
            export_cap_mw=cap,
            reserve_mwh=reserve if floor is None else floor,
        )

    # Every cycled option keeps the black-start reserve; the no-reserve run is reported only
    # to show what giving up the function would be worth.
    disp = {r: run_dispatch(cycled, rte, cap) for r, cap in readings.items()}
    disp_free = {r: run_dispatch(cycled, rte, cap, 0.0) for r, cap in readings.items()}

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
        overrides: Optional[Mapping[str, Any]] = None,
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
            scenario_overrides=overrides,
        )

    wind_only = kpis(scenario)
    rate = wind_only["discount_rate_used"]
    # The scenario's WACC moves with gearing, so a battery also re-discounts the whole wind
    # project. Pinning the rate at the wind-only value isolates the battery's own effect.
    pinned = {"wacc.drives_discount_rate": False, "returns.project_discount_rate": rate}
    timeline = scenario["timeline"]
    # The engine's own capex price-year escalation (capex.price_basis), for the battery's
    # pre-tax view; 1.0 when the scenario declares no price basis.
    basis = price_basis_applied(scenario)
    capex_factor = 1.0 if basis is None else float(basis["factor"])

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
            capex_price_factor=capex_factor,
            construction_years=int(timeline["construction_years"]),
            discount_rate=rate,
        )

    base_basis = cfg["revenue_bases"]["base"]
    bases = [base_basis, *cfg["revenue_bases"]["sensitivities"]]
    base_peak = peak_rates[base_basis]
    supplier = cfg["down_ramp"]["supplier"]
    out_opts: Dict[str, Any] = {}
    for opt in options:
        bottom_up = wbo.bottom_up_price(
            supplier,
            power_mw=float(opt["power_mw"]),
            energy_mwh=float(opt["energy_mwh"]),
            all_in_usd_per_kwh_mode=float(price["mode"]),
        )
        row: Dict[str, Any] = {
            "power_mw": opt["power_mw"],
            "energy_mwh": opt["energy_mwh"],
            "operation": opt["operation"],
            "capex_usd_at_mode": float(opt["energy_mwh"])
            * 1000.0
            * float(price["mode"]),
            "fits_reading_A_turbine_plus_battery_le_limit": float(opt["power_mw"])
            <= a_limit + 1e-9,
            "bottom_up_price": bottom_up,
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
            if opt["operation"] == "cycled":
                i_free = [o["name"] for o in cycled].index(opt["name"])
                d0 = float(disp_free[reading].delivered_mwh[i_free])
                c0 = float(disp_free[reading].charged_mwh[i_free])
                k0 = kpis(scen(opt, delivered=d0, charged=c0, basis=base_basis))
                rr["black_start_reserve_mwh"] = reserve
                rr["without_reserve_base_basis"] = {
                    "delivered_mwh_per_year": d0,
                    "delta_project_npv_vs_wind_only": k0["project_npv"]
                    - wind_only["project_npv"],
                }
            kp = kpis(
                scen(opt, delivered=d, charged=c, basis=base_basis, overrides=pinned)
            )
            rr["pinned_discount_rate_delta_project_npv_base_basis"] = (
                kp["project_npv"] - wind_only["project_npv"]
            )
            for basis in bases:
                k = kpis(scen(opt, delivered=d, charged=c, basis=basis))
                k["delta_project_npv_vs_wind_only"] = (
                    k["project_npv"] - wind_only["project_npv"]
                )
                k["delta_equity_npv_vs_wind_only"] = (
                    k["equity_npv"] - wind_only["equity_npv"]
                )
                rr["bases"][basis] = k
            rr["battery_pretax_base_basis"] = pretax(opt, d, c, peak_rates[base_basis])
            kb = kpis(
                scen(
                    opt,
                    delivered=d,
                    charged=c,
                    basis=base_basis,
                    usd_per_kwh=bottom_up["all_in_usd_per_kwh"],
                )
            )
            rr["bottom_up_price_base_basis"] = {
                "delta_project_npv_vs_wind_only": kb["project_npv"]
                - wind_only["project_npv"],
                "equity_irr": kb["equity_irr"],
            }
            adj_k = kpis(
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
                k_ = kpis(
                    scen(o, delivered=d_, charged=c_, basis=base_basis, usd_per_kwh=p)
                )
                return k_["project_npv"] - wind_only["project_npv"]

            rr["break_even_usd_per_kwh_base_basis"] = bisect_root(
                gap_price, 0.01, 1000.0, 0.01
            )
            if opt["operation"] == "cycled":

                def gap_rate(
                    x: float, o: Mapping[str, Any] = opt, d_: float = d, c_: float = c
                ) -> float:
                    pk = wbo.PeakRate(base_peak.non_escalable + x, base_peak.escalable)
                    k_ = kpis(
                        scen(o, delivered=d_, charged=c_, basis=base_basis, peak=pk)
                    )
                    return k_["project_npv"] - wind_only["project_npv"]

                x = bisect_root(
                    gap_rate, -base_peak.non_escalable + wind_rate.total, 500.0, 1e-3
                )
                rr["break_even_peak_rate_lkr_per_kwh_base_basis"] = (
                    None if x is None else base_peak.total + x
                )
            row["readings"][reading] = rr
        out_opts[opt["name"]] = row

    # The cheapest option that keeps the function and fits every reading of the limit.
    first = next(iter(readings))
    fitting = {
        n: r["readings"][first]["bases"][base_basis]["delta_project_npv_vs_wind_only"]
        for n, r in out_opts.items()
        if r["fits_reading_A_turbine_plus_battery_le_limit"]
    }
    recommended = max(fitting, key=lambda n: fitting[n]) if fitting else None

    # RTE grid (base basis, cycled options): one dispatch per grid point and reading.
    rte_grid: Dict[str, Any] = {}
    for reading, cap in readings.items():
        for r_ in cfg["monte_carlo"]["rte_grid"]:
            dg = run_dispatch(cycled, float(r_), cap)
            for i, opt in enumerate(cycled):
                k = kpis(
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
            kpis(
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
                    kpis(
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
        all_in_usd_per_kwh_mode=float(price["mode"]),
    )

    # A cycled firming unit keeps both the ramp energy and the black-start reserve in hand.
    firming_reserve = reserve + float(worst["energy_mwh"])

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
                reserve_mwh=firming_reserve,
            )
            d, c = float(res.delivered_mwh[0]), float(res.charged_mwh[0])
        k = kpis(
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
            "reserve_mwh": firming_reserve if operation == "cycled" else None,
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
        "tariff": {
            "wind": rate_parts(wind_rate),
            "bess_component_ground": rate_parts(comp),
            "bess_component_floating": rate_parts(rates["bess_component_floating"]),
            "whole_wind_peak_rate": rate_parts(rates["whole_wind_peak_rate"]),
            "stacked": rate_parts(rates["stacked"]),
            "one_time_adjustment_factor": adj,
            "bess_component_after_adjustment": rate_parts(adjusted_component),
            "whole_wind_peak_rate_after_adjustment": rate_parts(adjusted_whole),
            "escalable_index_rate": index_rate,
        },
        "revenue_bases": {"base": base_basis, "sensitivities": bases[1:]},
        "profile": prof["checks"]
        | {"window_wind_mwh_per_year": prof["window_wind_mwh"]},
        "wind_only": wind_only,
        "options": out_opts,
        "recommended_option_reading_A": recommended,
        "wind_only_pinned_discount_rate": kpis(
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
                scenario_overrides=pinned,
            )
        ),
        "rte_grid_delta_project_npv_base_basis": rte_grid,
        "monte_carlo_base_basis": {"n_trials": n, "seed": int(mc["seed"])} | mc_out,
        "down_ramp_illustrative": down_ramp,
    }


# ---------------------------------------------------------------------------
# Scenario-driven entry point (#1578 U2)
# ---------------------------------------------------------------------------

#: The block this analysis reads (:mod:`analytics.site_analysis_blocks`).
BLOCK = "storage_options"
#: The ``schema_version`` of the options config :func:`config_from_block` builds.
CONFIG_SCHEMA = "dutchbay.wind_bess_options.config.v1"
SUMMARY_SCHEMA = "dutchbay.wind_bess_options.v1"
#: Keys the method config's ``method`` mapping must hold.
METHOD_KEYS = ("hold", "revenue_bases", "monte_carlo")


def config_from_block(
    scenario: Mapping[str, Any],
    block: Mapping[str, Any],
    method: Mapping[str, Any],
    *,
    scenario_label: str,
    summary_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the options config :func:`run_options` reads from a scenario's block.

    The site inputs come from the block, the wind tariff from the scenario itself, and the
    revenue bases and Monte Carlo settings from the method config.

    Raises:
        ValueError: The method config lacks a key it must hold.
    """
    missing = [k for k in METHOD_KEYS if k not in method]
    if missing:
        raise ValueError(f"method config lacks {missing}")
    tech = block["technology"]
    turbine = tech["wind_turbine"]
    battery = tech["battery"]
    profile = block["hourly_profile"]
    tariff = block["tariff"]
    limits = block["grid_limits"]
    mc = dict(method["monte_carlo"])
    mc["wind_yield_sigma"] = block["uncertainty"]["wind_yield_sigma"]
    return {
        "schema_version": CONFIG_SCHEMA,
        "scenario": scenario_label,
        "retrieved": str(block["retrieved"]),
        "sources": list(block["sources"]),
        "tariff": {
            "wind_lkr_per_kwh": float(scenario["tariff"]["lkr_per_kwh"]),
            "wind_components": list(tariff["wind_components"]),
            "solar_bess_priority_components": list(
                tariff["storage_priority_components"]
            ),
            "solar_bess_other_components": list(tariff["storage_other_components"]),
            "floating_priority_components": list(
                tariff["cross_check_priority_components"]
            ),
            "floating_other_components": list(tariff["cross_check_other_components"]),
            "pucsl_round_trip_efficiency": tariff["round_trip_efficiency_basis"],
            "component_check_tolerance_lkr_per_kwh": tariff[
                "component_check_tolerance"
            ],
            "contract_years": tariff["contract_years"],
            "one_time_adjustment_weights": dict(tariff["one_time_adjustment_weights"]),
        },
        "revenue_bases": copy.deepcopy(dict(method["revenue_bases"])),
        "window": {"utc_hours": list(tariff["priority_window_utc_hours"])},
        "limits": {
            "standardised_ppa_mw": limits["export_limit_mw"],
            "readings": {
                str(name): {"export_cap_mw": cap}
                for name, cap in limits["export_cap_readings"].items()
            },
        },
        "profile": {
            "reference_config": profile["reference_config"],
            "reference_point": profile["reference_point"],
            "transfer_summary": profile["transfer_summary"],
            "reference_height_m": profile["reference_height_m"],
            "hub_height_m": turbine["hub_height_m"],
            "rotor_diameter_m": turbine["rotor_diameter_m"],
            "rated_mw": turbine["rated_mw"],
            "air_density_kgm3": turbine["air_density_kgm3"],
            "cut_in_ms": turbine["cut_in_ms"],
            "cut_out_ms": turbine["cut_out_ms"],
            "power_loss_fractions": list(turbine["power_loss_fractions"]),
        },
        "battery": {
            "duration_h_for_tariff": battery["duration_h_for_tariff"],
            "usd_per_kwh": dict(battery["usd_per_kwh"]),
            "om_usd_per_dc_kwh_year": battery["om_usd_per_dc_kwh_year"],
            "dc_per_nominal": battery["dc_per_nominal"],
            "round_trip_efficiency": battery["round_trip_efficiency"],
            "black_start_reserve_mwh": battery["black_start_reserve_mwh"],
        },
        "options": [
            {
                "name": str(o["id"]),
                "power_mw": o["power_mw"],
                "energy_mwh": o["energy_mwh"],
                "operation": o["operation"],
            }
            for o in block["sizes"]["options"]
        ],
        "down_ramp": {
            "substation_limit_mw_per_min": limits["ramp_limit_mw_per_min"],
            "illustrative_other_wind_mw": list(limits["illustrative_other_wind_mw"]),
            "supplier": copy.deepcopy(dict(block["firming_supplier"])),
        },
        "monte_carlo": mc,
        "output": {"summary_json": summary_json},
    }


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, default=str, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_wind_bess_options_for_scenario(
    scenario: Mapping[str, Any],
    method: Mapping[str, Any],
    *,
    scenario_label: str,
    profile_builder: Optional[
        Callable[[Mapping[str, Any], Mapping[str, Any]], Dict[str, Any]]
    ] = None,
) -> Dict[str, Any]:
    """Run the wind battery options for one scenario, or report them as not applicable.

    A scenario with a ``storage_options`` block gets ``"status": "completed"`` and every
    figure :func:`run_options` returns; one without it gets ``"status": "not_applicable"``
    and the reason, never an error. ``scenario_label`` must be the scenario's path (repository
    relative or absolute): the evaluation re-reads the scenario from it.

    Raises:
        ValueError: The block is present but malformed (every problem is listed), or the
            method config is incomplete.
    """
    from analytics.site_analysis_blocks import (
        STATUS_NOT_APPLICABLE,
        resolve_site_analysis_block,
    )
    from analytics.tariff_legal_status import storage_options_tariff_legal_status

    common: Dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "analysis": "wind battery options",
        "scenario": scenario_label,
        "hold": str(method["hold"]),
    }
    block = resolve_site_analysis_block(scenario, BLOCK)
    if block is None:
        return {
            **common,
            "status": STATUS_NOT_APPLICABLE,
            "reason": f"the scenario declares no {BLOCK} block",
        }
    cfg = config_from_block(scenario, block, method, scenario_label=scenario_label)
    threshold = float(block["hourly_profile"]["high_output_check_mw"])

    def default_profile(c: Mapping[str, Any], s: Mapping[str, Any]) -> Dict[str, Any]:
        return build_profile(c, s, high_output_check_mw=threshold)

    figures = run_options(
        cfg,
        schema_version=CONFIG_SCHEMA,
        profile_builder=profile_builder or default_profile,
    )
    bases = [
        figures["revenue_bases"]["base"],
        *figures["revenue_bases"]["sensitivities"],
    ]
    tariff_status = storage_options_tariff_legal_status(
        scenario, Path(scenario_label).stem, bases
    )
    return {
        **common,
        "status": "completed",
        "site": dict(block["site"]),
        "notes": block.get("notes"),
        "block_sha256": _digest(block),
        "method_sha256": _digest(method),
        "scenario_sha256": sha256_file(repo_path(scenario_label)),
        "transfer_summary_sha256": sha256_file(
            repo_path(cfg["profile"]["transfer_summary"])
        ),
        "model_version": (REPO_ROOT / "VERSION").read_text().strip(),
        "tariff_legal_status": tariff_status,
        **figures,
    }
