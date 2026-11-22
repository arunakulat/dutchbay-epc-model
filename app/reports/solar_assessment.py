"""Solar PV assessment report for any scenario (#1784).

The owner ruled on 2026-11-16 that all code must be available to any scenario. This module is
the shared form of a report that was first written for one site: it reads every input from the
scenario it is given, runs the platform's analyses on that scenario, and renders a DutchBay
Presentation Layer (DBPL) PDF (``DBPL-01``, ``docs/dbpl_styleguide.md``).

Analyses, each on the live engine:

1. Solar resource: the pvlib producer (``solar_resource``) on the scenario's
   ``resource.solar`` block, beside the capacity factor the scenario finances.
2. Deterministic finance: ``run_v14_pipeline`` on the scenario as written.
3. Tariff sweep, and the breakeven tariffs from ``solve_tariff_breakeven``.
4. Capex sweep.
5. Monte Carlo over the scenario's own ``monte_carlo.parameters``, toy fallback off.
6. One-way sensitivity (``analytics.core.sensitivity_runner``).
7. Gearing optimisation on equity NPV under the scenario's ``Financing_Terms.target_dscr``.
8. The DSCR sizing-target sweep, on a dual-DSCR copy of the scenario.
9. A regional GHI map with a GeoTIFF (NASA POWER) and an imagery close-up (contextily).

The owner's "write figures, list failure" ruling applies: an analysis that cannot run on the
scenario, or a map whose network source is unreachable, is listed with its reason and the
report is still written.
"""

from __future__ import annotations

import copy
import json
import math
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

#: The gearing and DSCR-target optimisations rank on equity NPV (#1456, #1522 A-3):
#: ``optimize_parameter`` warns when a caller ranks on IRR.
OPTIMISATION_OBJECTIVE = "equity_npv"

#: Multiples of the scenario's own tariff and capex that the sweeps visit.
TARIFF_FACTORS = (0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0)
CAPEX_FACTORS = (0.75, 0.875, 1.0, 1.1, 1.25)
#: The breakeven search brackets, as multiples of the scenario's tariff. The second is tried
#: when the first fails, for a scenario whose IRR is undefined at the lower bound.
BREAKEVEN_BRACKETS = ((0.5, 6.0), (1.0, 6.0))
GEARING_RANGE = (0.30, 0.75)
DSCR_TARGETS = (1.05, 1.10, 1.20, 1.30, 1.40, 1.50, 1.60)
#: Regional map window: half-width and grid step in degrees around the site.
MAP_HALF_WIDTH_DEG = 1.5
MAP_STEP_DEG = 0.5

_KPI_KEYS = (
    "project_irr",
    "equity_irr",
    "project_npv",
    "equity_npv",
    "min_dscr",
    "avg_dscr",
    "max_debt_usd",
    "discount_rate_used",
    "equity_covenant_locked_years",
    "equity_sponsor_cure_usd",
)


# ── Monte Carlo summary ────────────────────────────────────────────────────────


def _defined_sample(values: Any) -> list[float]:
    """Keep a metric's finite trial values; an undefined KPI is None, never zero (#1474)."""
    out: list[float] = []
    for value in values or []:
        if value is None:
            continue
        number = float(value)
        if math.isfinite(number):
            out.append(number)
    return out


def _trial_coverage(values: Any, defined: list[float]) -> Dict[str, int]:
    """The denominator behind a statistic, in the same keys as analytics.mc.exports."""
    total = len(values or [])
    return {
        "defined_trials": len(defined),
        "total_trials": total,
        "unavailable_trials": total - len(defined),
    }


def _summarise_mc_irr(
    trials: Dict[str, Any], iterations: int, failed: int
) -> Dict[str, Any]:
    """Summarise project and equity IRR, each on its own defined trials.

    MonteCarloResult.trials keeps one aligned row per trial and stores an undefined KPI as
    None (#1474). Each statistic is computed from that metric's defined sample and returned
    with its coverage. A metric with no defined trial gets None statistics.
    """
    import numpy as np

    raw_irr = trials.get("project_irr", []) or []
    raw_eqi = trials.get("equity_irr", []) or []
    irr = _defined_sample(raw_irr)
    eqi = _defined_sample(raw_eqi)
    return {
        "n": iterations,
        "failed": failed,
        "coverage": {
            "project_irr": _trial_coverage(raw_irr, irr),
            "equity_irr": _trial_coverage(raw_eqi, eqi),
        },
        "proj_irr": (
            {
                q: float(np.percentile(irr, p))
                for q, p in (("p10", 10), ("p50", 50), ("p90", 90))
            }
            if irr
            else {}
        ),
        "proj_mean": float(np.mean(irr)) if irr else None,
        "p_below_0": float(np.mean([x < 0 for x in irr])) if irr else None,
        "eq_p50": float(np.percentile(eqi, 50)) if eqi else None,
        "eq_p_below_0": float(np.mean([x < 0 for x in eqi])) if eqi else None,
        "_irr_trials": irr,
    }


# ── scenario access ────────────────────────────────────────────────────────────


def load_scenario(path: str | Path) -> Dict[str, Any]:
    """Load a scenario as the engine evaluates it, as a plain mutable dict.

    #1899: a declared ``capex.price_basis`` is applied, so the assessment reads the
    capex the engine finances (``analytics.evaluation_v14.evaluated_scenario_config``).
    """
    from analytics.evaluation_v14 import evaluated_scenario_config
    from analytics.scenario_loader import load_scenario_config

    return copy.deepcopy(
        evaluated_scenario_config(dict(load_scenario_config(str(path))))
    )


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def scenario_tariff(cfg: Mapping[str, Any]) -> float:
    """The fixed LKR/kWh tariff the sweeps and breakevens move."""
    tariff = cfg.get("tariff")
    value = _number(tariff.get("lkr_per_kwh")) if isinstance(tariff, Mapping) else None
    if value is None or value <= 0:
        raise ValueError("the scenario declares no positive tariff.lkr_per_kwh")
    return value


def scenario_covenant(cfg: Mapping[str, Any]) -> float:
    """The scenario's DSCR sizing target, which the gearing optimisation must hold."""
    terms = cfg.get("Financing_Terms")
    value = _number(terms.get("target_dscr")) if isinstance(terms, Mapping) else None
    if value is None or value <= 0:
        raise ValueError(
            "the scenario declares no positive Financing_Terms.target_dscr"
        )
    return value


def scenario_capex(cfg: Mapping[str, Any]) -> float:
    from finance.capex_price_basis import refuse_unapplied_price_basis

    refuse_unapplied_price_basis(cfg, "the solar assessment")
    capex = cfg.get("capex")
    value = _number(capex.get("usd_total")) if isinstance(capex, Mapping) else None
    if value is None or value <= 0:
        raise ValueError("the scenario declares no positive capex.usd_total")
    return value


def declared_capacity_factor(cfg: Mapping[str, Any]) -> Optional[float]:
    """The solar capacity factor the scenario finances (per-technology first)."""
    gen = cfg.get("generation")
    techs = gen.get("technologies") if isinstance(gen, Mapping) else None
    solar = techs.get("solar") if isinstance(techs, Mapping) else None
    if isinstance(solar, Mapping) and _number(solar.get("capacity_factor")) is not None:
        return _number(solar.get("capacity_factor"))
    project = cfg.get("project")
    return (
        _number(project.get("capacity_factor"))
        if isinstance(project, Mapping)
        else None
    )


def with_tariff(cfg: Mapping[str, Any], tariff: float) -> Dict[str, Any]:
    out = copy.deepcopy(dict(cfg))
    out["tariff"]["lkr_per_kwh"] = float(tariff)
    return out


def with_capex_factor(cfg: Mapping[str, Any], factor: float) -> Dict[str, Any]:
    """Scale the total capex and every number that reconciles to it by ``factor``."""
    out = copy.deepcopy(dict(cfg))
    capex = out["capex"]
    for key in ("usd_total", "capex_per_kw_usd"):
        if _number(capex.get(key)) is not None:
            capex[key] = float(capex[key]) * factor
    breakdown = capex.get("breakdown")
    if isinstance(breakdown, dict):
        for key, value in breakdown.items():
            if _number(value) is not None:
                breakdown[key] = float(value) * factor
    return out


# ── the analyses ───────────────────────────────────────────────────────────────


def kpis(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Run the deterministic pipeline once and keep the figures the report quotes."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    res = run_v14_pipeline(config=copy.deepcopy(dict(cfg)))
    k = res["kpis"]
    out: Dict[str, Any] = {key: k.get(key) for key in _KPI_KEYS}
    eq = res.get("equity_distribution") or {}
    summary = eq.get("equity_summary") or {}
    out["equity_discount_rate_used"] = (eq.get("metadata") or {}).get("discount_rate")
    out["lockup_threshold"] = summary.get("min_dscr_threshold")
    out["equity_sign_changes"] = summary.get("equity_cashflow_sign_changes")
    return out


def _resource(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    from solar_resource import SolarResourceConfig, compute_solar_aep

    spec = SolarResourceConfig.from_scenario(cfg)
    pv = compute_solar_aep(spec)
    return {
        "latitude": float(spec.latitude),
        "longitude": float(spec.longitude),
        "dc_capacity_mw": float(spec.dc_capacity_mw),
        "tilt_deg": float(spec.tilt_deg),
        "azimuth_deg": float(spec.azimuth_deg),
        "ghi_kwh_m2": float(pv.ghi_kwh_m2),
        "poa_kwh_m2": float(pv.poa_kwh_m2),
        "producer_cf": float(pv.capacity_factor),
        "specific_yield_kwh_per_kwp": float(pv.specific_yield_kwh_per_kwp),
        "annual_energy_gwh": float(pv.annual_energy_gwh),
        "declared_cf": declared_capacity_factor(cfg),
    }


def _tariff_sweep(cfg: Mapping[str, Any]) -> List[Dict[str, Any]]:
    base = scenario_tariff(cfg)
    rows = []
    for factor in TARIFF_FACTORS:
        k = kpis(with_tariff(cfg, base * factor))
        rows.append(
            {
                "factor": factor,
                "tariff": base * factor,
                "projIRR": k["project_irr"],
                "eqIRR": k["equity_irr"],
                "npv": k["project_npv"],
                "dscr": k["min_dscr"],
            }
        )
    return rows


def _breakevens(
    scenario_path: str, cfg: Mapping[str, Any], base: Mapping[str, Any]
) -> Dict[str, Any]:
    """Breakeven tariffs from the shared solver, with each result's own status."""
    from analytics.core.parameter_solvers import solve_tariff_breakeven

    tariff = scenario_tariff(cfg)
    hurdle = _number(base.get("discount_rate_used"))
    targets = [("project_npv", 0.0, "Project NPV = 0")]
    if hurdle is not None:
        # The engine re-derives the project discount rate at each tariff, so the IRR target is
        # the base case's rate held fixed, and the label says so with the figure. The point
        # where project IRR equals the rate in force at that tariff is the NPV = 0 breakeven
        # (#1785 assurance F1).
        targets.insert(
            0,
            (
                "project_irr",
                hurdle,
                f"Project IRR = base-case discount rate ({hurdle:.2%})",
            ),
        )
    out: Dict[str, Any] = {}
    for metric, target, label in targets:
        result = None
        for lo, hi in BREAKEVEN_BRACKETS:
            result = solve_tariff_breakeven(
                scenario_path,
                metric=metric,
                target_value=target,
                bounds=(tariff * lo, tariff * hi),
            )
            if result.status == "converged":
                break
        assert result is not None
        out[metric] = {
            "label": label,
            "target": target,
            "status": result.status,
            "tariff_lkr": result.breakeven_value,
            "bracket": list(
                result.bracket
                or (
                    tariff * BREAKEVEN_BRACKETS[-1][0],
                    tariff * BREAKEVEN_BRACKETS[-1][1],
                )
            ),
        }
    return out


def _capex_sweep(cfg: Mapping[str, Any]) -> List[Dict[str, Any]]:
    capex = scenario_capex(cfg)
    rows = []
    for factor in CAPEX_FACTORS:
        k = kpis(with_capex_factor(cfg, factor))
        rows.append(
            {
                "factor": factor,
                "capex_usd": capex * factor,
                "projIRR": k["project_irr"],
                "npv": k["project_npv"],
                "dscr": k["min_dscr"],
            }
        )
    return rows


def _monte_carlo(cfg: Mapping[str, Any], trials: int) -> Dict[str, Any]:
    from analytics.mc.engine import run_monte_carlo_analysis

    block = cfg.get("monte_carlo")
    if not isinstance(block, Mapping) or not block.get("parameters"):
        raise ValueError("the scenario declares no monte_carlo.parameters")
    mc_cfg = copy.deepcopy(dict(cfg))
    # A report MC must not fall back to the toy engine (lender guard).
    mc_cfg["monte_carlo"]["allow_toy_fallback"] = False
    mc = run_monte_carlo_analysis(base_config=mc_cfg, n_trials=int(trials), seed=123)
    summary = _summarise_mc_irr(mc.trials, mc.iterations, mc.failed_iterations)
    summary["parameters"] = [str(p.get("name")) for p in block["parameters"]]
    return summary


def _sensitivity(scenario_path: str, cfg: Mapping[str, Any]) -> List[Dict[str, Any]]:
    from analytics.core.sensitivity_runner import run_sensitivity_analysis

    # A per-technology scenario now runs too: the capacity-factor shock scales each
    # technology with the project figure (#1787).
    suite = run_sensitivity_analysis(scenario_path, metric="project_irr")
    rows: List[Dict[str, Any]] = []
    for tr in suite.tornado_results:
        shock = tr.shock_results[0]
        low, high = _number(shock.low_case), _number(shock.high_case)
        # An undefined IRR is undefined, never zero (#1474): the impact is undefined too.
        impact = abs(high - low) if low is not None and high is not None else None
        rows.append(
            {
                "param": tr.label or shock.label or shock.variable_name or "driver",
                "base": _number(tr.base_metric),
                "low": low,
                "high": high,
                "impact": impact,
            }
        )
    rows.sort(key=lambda d: (d["impact"] is None, -(d["impact"] or 0.0)))
    return rows


#: Two debt-ratio ceilings whose debt raised differs by less than this share of capex raise
#: the same debt: the ceiling does not bind between them.
CEILING_BIND_TOLERANCE = 1e-4


def _gearing(scenario_path: str, cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Sweep the scenario's debt-ratio ceiling and record the debt each point actually raises.

    ``Financing_Terms.debt_ratio`` is a ceiling. A scenario that sizes its debt to a DSCR
    target (``debt_sizing: dual_dscr``) may never reach it, so each point also records the
    realised gearing (``max_debt_usd`` over capex). When the ceiling binds at no point, every
    point raises the same debt and no gearing optimum is reported (#1785 domain D-1): the
    report must not name a gearing the sweep did not reach.
    """
    from analytics.optimization_v14 import optimize_parameter

    covenant = scenario_covenant(cfg)
    capex = scenario_capex(cfg)
    terms = cfg.get("Financing_Terms")
    sizing = terms.get("debt_sizing") if isinstance(terms, Mapping) else None
    # Constrain on the per-period sculpt floor (min_dscr_period), not the fold-corrected
    # headline min_dscr, which an interest-only lead-in can push below the target even when
    # the sculpt holds it in every operating period (#790).
    opt = optimize_parameter(
        scenario_path,
        param_path="Financing_Terms.debt_ratio",
        objective_key=OPTIMISATION_OBJECTIVE,
        lower=GEARING_RANGE[0],
        upper=GEARING_RANGE[1],
        direction="max",
        n_steps=10,
        constraint_key="min_dscr_period",
        constraint_min=covenant,
    )
    curve = []
    for p in opt.curve:
        c = copy.deepcopy(dict(cfg))
        c["Financing_Terms"]["debt_ratio"] = float(p.value)
        k = kpis(c)
        curve.append(
            {
                "x": float(p.value),
                "realised": (_number(k.get("max_debt_usd")) or 0.0) / capex,
                "obj": float(p.objective),
                "feasible": bool(p.feasible),
                "eqIRR": k["equity_irr"],
                "cure": float(k["equity_sponsor_cure_usd"] or 0.0),
            }
        )
    realised = [p["realised"] for p in curve]
    cap_binds = bool(realised) and (
        max(realised) - min(realised) > CEILING_BIND_TOLERANCE
    )
    best = None
    if opt.best is not None and cap_binds:
        point = next(p for p in curve if p["x"] == float(opt.best.value))
        best = {
            "x": point["x"],
            "realised": point["realised"],
            "obj": float(opt.best.objective),
        }
    return {
        "objective_key": OPTIMISATION_OBJECTIVE,
        "covenant": covenant,
        "debt_sizing": str(sizing) if sizing is not None else None,
        "cap_binds": cap_binds,
        "curve": curve,
        "best": best,
    }


def _dscr_targets(cfg: Mapping[str, Any], work_dir: Path) -> Dict[str, Any]:
    import yaml

    from analytics.optimization_v14 import optimize_parameter

    capex = scenario_capex(cfg)
    sculpt = copy.deepcopy(dict(cfg))
    sculpt["Financing_Terms"]["debt_sizing"] = "dual_dscr"
    sweep = []
    for target in DSCR_TARGETS:
        c = copy.deepcopy(sculpt)
        c["Financing_Terms"]["target_dscr"] = target
        k = kpis(c)
        sweep.append(
            {
                "target_dscr": target,
                "gearing": (_number(k.get("max_debt_usd")) or 0.0) / capex,
                "min_dscr": k["min_dscr"],
                "projIRR": k["project_irr"],
                "eqIRR": k["equity_irr"],
                "eqNPV": k["equity_npv"],
                "locked_years": int(k["equity_covenant_locked_years"] or 0),
                "lockup": _number(k.get("lockup_threshold")),
            }
        )
    path = work_dir / "dscr_sculpt_scenario.yaml"
    path.write_text(yaml.safe_dump(sculpt, sort_keys=False), encoding="utf-8")
    opt = optimize_parameter(
        str(path),
        param_path="Financing_Terms.target_dscr",
        objective_key=OPTIMISATION_OBJECTIVE,
        lower=DSCR_TARGETS[0],
        upper=DSCR_TARGETS[-1],
        direction="max",
        n_steps=12,
    )
    best = (
        {"target": float(opt.best.value), "obj": float(opt.best.objective)}
        if opt.best
        else None
    )
    lockups = [d["lockup"] for d in sweep if d["lockup"] is not None]
    return {
        "sweep": sweep,
        "objective_key": OPTIMISATION_OBJECTIVE,
        "best": best,
        "lockup_covenant": lockups[0] if lockups else None,
    }


def run_assessment(
    scenario_path: str | Path, *, trials: int, work_dir: Path
) -> Dict[str, Any]:
    """Run every analysis on one scenario.

    Returns the results with a ``not_run`` list: each analysis that could not run on this
    scenario is listed with its reason, and the others still run.
    """
    path = str(scenario_path)
    cfg = load_scenario(path)
    work_dir.mkdir(parents=True, exist_ok=True)
    raw_project = cfg.get("project")
    project: Mapping[str, Any] = raw_project if isinstance(raw_project, Mapping) else {}
    R: Dict[str, Any] = {
        "scenario_path": path,
        "scenario_name": str(project.get("name") or Path(path).stem),
        "trials": int(trials),
        "not_run": [],
    }

    def step(key: str, label: str, fn: Callable[[], Any]) -> None:
        try:
            R[key] = fn()
        except Exception as exc:  # write figures, list failure (owner ruling)
            R["not_run"].append(
                {"analysis": label, "reason": f"{type(exc).__name__}: {exc}"}
            )

    step("resource", "Solar resource (pvlib producer)", lambda: _resource(cfg))
    step("base", "Deterministic finance", lambda: kpis(cfg))
    step("tariff_sweep", "Tariff sweep", lambda: _tariff_sweep(cfg))
    if "base" in R:
        step(
            "breakeven", "Breakeven tariffs", lambda: _breakevens(path, cfg, R["base"])
        )
    step("capex_sweep", "Capex sweep", lambda: _capex_sweep(cfg))
    step("mc", "Monte Carlo", lambda: _monte_carlo(cfg, trials))
    step("sensitivity", "One-way sensitivity", lambda: _sensitivity(path, cfg))
    step("optimization", "Gearing optimisation", lambda: _gearing(path, cfg))
    step("dscr", "DSCR sizing-target sweep", lambda: _dscr_targets(cfg, work_dir))
    return R


# ── maps ───────────────────────────────────────────────────────────────────────


def _nasa_power_annual_ghi(lat: float, lon: float) -> float:
    url = (
        "https://power.larc.nasa.gov/api/temporal/climatology/point?"
        "parameters=ALLSKY_SFC_SW_DWN&community=RE"
        f"&latitude={lat:.2f}&longitude={lon:.2f}&format=JSON"
    )
    # The URL is a fixed https literal; only the two coordinates, formatted as numbers, vary.
    with urllib.request.urlopen(  # nosec B310 - fixed https NASA POWER literal
        url, timeout=20
    ) as response:
        data = json.load(response)
    return float(data["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]["ANN"]) * 365.0


def make_location_map(
    lat: float,
    lon: float,
    charts: Path,
    *,
    fetch: Callable[[float, float], float] = _nasa_power_annual_ghi,
) -> Path:
    """Map regional annual GHI around the site and write the grid as a GeoTIFF.

    The grid is NASA POWER's all-sky climatology at ``MAP_STEP_DEG`` spacing within
    ``MAP_HALF_WIDTH_DEG`` of the site. Raises when the source is unreachable, so the
    caller lists the map as not drawn.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from analytics.gis.geotiff_export import write_geotiff

    n = int(round(2 * MAP_HALF_WIDTH_DEG / MAP_STEP_DEG)) + 1
    lats = lat - MAP_HALF_WIDTH_DEG + MAP_STEP_DEG * np.arange(n)
    lons = lon - MAP_HALF_WIDTH_DEG + MAP_STEP_DEG * np.arange(n)
    grid = np.array([[fetch(float(la), float(lo)) for lo in lons] for la in lats])
    half = MAP_STEP_DEG / 2
    bbox = (lons[0] - half, lats[0] - half, lons[-1] + half, lats[-1] + half)
    write_geotiff(
        grid[::-1, :].astype("float32"),
        bbox,
        str(charts / "site_region_ghi.tif"),
        provenance={
            "source": "NASA POWER ALLSKY_SFC_SW_DWN climatology",
            "units": "kWh/m2/yr",
            "generated_by": "DutchBay v14 solar assessment",
        },
    )
    west, south, east, north = bbox
    fig, ax = plt.subplots(figsize=(6.0, 5.4))
    im = ax.imshow(
        grid,
        origin="lower",
        extent=(west, east, south, north),
        cmap="YlOrRd",
        aspect="equal",
        alpha=0.92,
    )
    ax.plot(lon, lat, marker="*", ms=18, color="#1f3a5f", mec="white", mew=1.2)
    ax.annotate(
        f"site {lat:.3f}, {lon:.3f}",
        xy=(lon, lat),
        xytext=(6, 6),
        textcoords="offset points",
        fontsize=8,
        color="#1f3a5f",
    )
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label("Annual GHI (kWh/m2/yr)")
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")
    out = charts / "00_location_map.png"
    fig.tight_layout()
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return out


def make_site_context_map(lat: float, lon: float, charts: Path) -> Path:
    """An imagery close-up of the site coordinate (contextily). Raises when unavailable."""
    import contextily as cx  # type: ignore[import-untyped,unused-ignore]
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    half = 0.018  # about 2 km either side
    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    ax.set_xlim(lon - half, lon + half)
    ax.set_ylim(lat - half, lat + half)
    try:
        cx.add_basemap(
            ax,
            crs="EPSG:4326",
            source=cx.providers.Esri.WorldImagery,
            zoom=16,
            attribution_size=5,
        )
    except Exception:
        plt.close(fig)
        raise
    ax.plot(lon, lat, marker="*", ms=26, color="#ffd400", mec="#1f3a5f", mew=1.6)
    ax.set_xticks([])
    ax.set_yticks([])
    out = charts / "00b_site_context.png"
    fig.tight_layout()
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return out


def make_maps(R: Dict[str, Any], charts: Path) -> Dict[str, Path]:
    """Draw the maps the resource step allows; list each one that cannot be drawn."""
    resource = R.get("resource")
    if not resource:
        return {}
    maps: Dict[str, Path] = {}
    for key, label, fn in (
        ("location", "Regional GHI map", make_location_map),
        ("context", "Site imagery map", make_site_context_map),
    ):
        try:
            maps[key] = fn(resource["latitude"], resource["longitude"], charts)
        except Exception as exc:
            R["not_run"].append(
                {"analysis": label, "reason": f"{type(exc).__name__}: {exc}"}
            )
    return maps


# ── charts ─────────────────────────────────────────────────────────────────────

_NAVY, _TEAL, _AMBER, _RED, _GREY = (
    "#1f3a5f",
    "#2a9d8f",
    "#e9a23b",
    "#c1432e",
    "#888888",
)


def _pct_points(values: Sequence[Optional[float]]) -> List[float]:
    return [v * 100 if v is not None else math.nan for v in values]


def make_charts(R: Mapping[str, Any], charts: Path) -> Dict[str, Path]:
    """Draw one chart per analysis that ran. Returns the files by analysis key."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    out: Dict[str, Path] = {}
    base = R.get("base") or {}
    disc = _number(base.get("discount_rate_used"))

    def save(fig: Any, key: str, name: str) -> None:
        path = charts / f"{name}.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        out[key] = path

    if R.get("tariff_sweep"):
        ts = R["tariff_sweep"]
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax2 = ax.twinx()
        x = [s["tariff"] for s in ts]
        ax.plot(x, _pct_points([s["projIRR"] for s in ts]), "-o", color=_NAVY)
        ax2.plot(
            x,
            [s["dscr"] if s["dscr"] is not None else math.nan for s in ts],
            "-s",
            color=_AMBER,
        )
        if disc is not None:
            ax.axhline(
                disc * 100,
                color=_RED,
                ls=":",
                lw=1.2,
                label=f"Base-case discount rate ({disc:.2%})",
            )
            ax.legend(loc="upper left", fontsize=7, frameon=False)
        for be in (R.get("breakeven") or {}).values():
            if be.get("tariff_lkr") is not None:
                ax.axvline(be["tariff_lkr"], color=_GREY, ls="--", lw=1)
        ax.set_xlabel("Fixed tariff (LKR/kWh)")
        ax.set_ylabel("Project IRR (%)", color=_NAVY)
        ax2.set_ylabel("Minimum DSCR (x)", color=_AMBER)
        save(fig, "tariff_sweep", "02_tariff_sweep")

    mc = R.get("mc") or {}
    if mc.get("_irr_trials"):
        irr = np.array(mc["_irr_trials"]) * 100
        fig, ax = plt.subplots(figsize=(7, 3.4))
        ax.hist(irr, bins=40, color=_TEAL, edgecolor="white", alpha=0.85)
        for q in ("p10", "p50", "p90"):
            ax.axvline(mc["proj_irr"][q] * 100, color=_NAVY, ls="--", lw=1.2)
        if disc is not None:
            ax.axvline(
                disc * 100,
                color=_RED,
                ls=":",
                lw=1.4,
                label=f"Base-case discount rate ({disc:.2%})",
            )
            ax.legend(loc="upper right", fontsize=7, frameon=False)
        ax.set_xlabel("Project IRR (%)")
        ax.set_ylabel("Trials")
        save(fig, "mc", "03_mc_irr")

    sens = [
        d
        for d in R.get("sensitivity") or []
        if d["impact"] is not None and d["impact"] > 0
    ]
    if sens:
        fig, ax = plt.subplots(figsize=(7, 3.2))
        y = np.arange(len(sens))
        for i, d in enumerate(reversed(sens)):
            lo, hi = sorted([(d["low"] or 0.0) * 100, (d["high"] or 0.0) * 100])
            ax.barh(y[i], hi - lo, left=lo, color=_TEAL, edgecolor=_NAVY, height=0.6)
        if sens[0]["base"] is not None:
            ax.axvline(sens[0]["base"] * 100, color=_RED, lw=1.4)
        ax.set_yticks(y)
        ax.set_yticklabels([d["param"] for d in reversed(sens)])
        ax.set_xlabel("Project IRR (%)")
        save(fig, "sensitivity", "04_tornado")

    opt = R.get("optimization") or {}
    if opt.get("curve"):
        curve = opt["curve"]
        fig, ax = plt.subplots(figsize=(7, 3.4))
        ax.plot(
            [p["x"] * 100 for p in curve],
            [p["obj"] / 1e6 for p in curve],
            "-",
            color=_NAVY,
            alpha=0.5,
        )
        for feasible, colour, marker in ((True, _TEAL, "o"), (False, _RED, "x")):
            pts = [p for p in curve if p["feasible"] is feasible]
            ax.scatter(
                [p["x"] * 100 for p in pts],
                [p["obj"] / 1e6 for p in pts],
                color=colour,
                marker=marker,
                zorder=5,
            )
        if opt.get("best"):
            ax.scatter(
                [opt["best"]["x"] * 100],
                [opt["best"]["obj"] / 1e6],
                edgecolor=_AMBER,
                facecolor="none",
                s=160,
                lw=2,
                zorder=6,
            )
        ax.set_xlabel("Debt-ratio ceiling (%)")
        ax.set_ylabel("Equity NPV (USD M)")
        save(fig, "optimization", "05_gearing")

    if R.get("capex_sweep"):
        cs = R["capex_sweep"]
        fig, ax = plt.subplots(figsize=(7, 3.2))
        ax2 = ax.twinx()
        x = [c["capex_usd"] / 1e6 for c in cs]
        ax.plot(x, _pct_points([c["projIRR"] for c in cs]), "-o", color=_NAVY)
        ax2.plot(
            x,
            [c["dscr"] if c["dscr"] is not None else math.nan for c in cs],
            "-s",
            color=_AMBER,
        )
        ax.set_xlabel("Capex (USD M)")
        ax.set_ylabel("Project IRR (%)", color=_NAVY)
        ax2.set_ylabel("Minimum DSCR (x)", color=_AMBER)
        save(fig, "capex_sweep", "06_capex")

    dscr = (R.get("dscr") or {}).get("sweep")
    if dscr:
        fig, ax = plt.subplots(figsize=(7, 3.4))
        ax2 = ax.twinx()
        x = [d["target_dscr"] for d in dscr]
        ax.plot(
            x,
            _pct_points([d["projIRR"] for d in dscr]),
            "-o",
            color=_NAVY,
            label="Project IRR",
        )
        ax.plot(
            x,
            _pct_points([d["eqIRR"] for d in dscr]),
            "-s",
            color=_RED,
            label="Equity IRR",
        )
        ax2.plot(
            x, [d["gearing"] * 100 for d in dscr], "--^", color=_AMBER, label="Gearing"
        )
        ax.set_xlabel("DSCR sizing target (x)")
        ax.set_ylabel("IRR (%)")
        ax2.set_ylabel("Solved gearing (%)", color=_AMBER)
        ax.legend(loc="upper left", fontsize=7)
        save(fig, "dscr", "07_dscr_targets")
    return out


# ── formatting ─────────────────────────────────────────────────────────────────

UNDEFINED = "undefined"


def fmt_pct(x: Any, dp: int = 1) -> str:
    value = _number(x)
    return UNDEFINED if value is None else f"{value * 100:.{dp}f}%"


def fmt_usd_m(x: Any) -> str:
    value = _number(x)
    if value is None:
        return UNDEFINED
    return f"-USD {abs(value) / 1e6:.2f}M" if value < 0 else f"USD {value / 1e6:.2f}M"


def fmt_x(x: Any) -> str:
    value = _number(x)
    return UNDEFINED if value is None else f"{value:.2f}x"


def fmt_num(x: Any, dp: int = 2) -> str:
    value = _number(x)
    return UNDEFINED if value is None else f"{value:,.{dp}f}"


def optimisation_caption(opt: Mapping[str, Any]) -> str:
    """The gearing finding, stated from the run (#1456: ranked on equity NPV).

    It names only a gearing the sweep reached. When the debt-ratio ceiling binds at no point
    (a scenario sized to its DSCR target), it says so and reports the debt actually raised.
    """
    curve = opt.get("curve") or []
    lo = min((p["x"] for p in curve), default=float("nan"))
    hi = max((p["x"] for p in curve), default=float("nan"))
    text = (
        f"Equity NPV against the debt-ratio ceiling under the scenario's "
        f"{fmt_x(opt.get('covenant'))} minimum per-period DSCR; the optimiser ranks on equity "
        "NPV, not equity IRR (#1456). "
    )
    if curve and opt.get("cap_binds") is False:
        sizing = opt.get("debt_sizing")
        sized = f"sizes its debt by {sizing}" if sizing else "sizes its debt"
        return text + (
            f"The scenario {sized} to its {fmt_x(opt.get('covenant'))} DSCR target, so the "
            f"ceiling does not bind: every ceiling from {lo:.0%} to {hi:.0%} raises the same "
            f"debt, {curve[0]['realised']:.1%} of capex, with equity NPV "
            f"{fmt_usd_m(curve[0]['obj'])}. No gearing optimum is reported."
        )
    best = opt.get("best")
    if best is None:
        return text + f"No ceiling from {lo:.0%} to {hi:.0%} meets the covenant."
    return text + (
        f"Best feasible ceiling {best['x']:.0%}, which raises debt of "
        f"{best['realised']:.1%} of capex, equity NPV {fmt_usd_m(best['obj'])}."
    )


def dscr_target_caption(dscr: Mapping[str, Any]) -> str:
    """The DSCR sizing-target finding, flagged when it sits at the sweep's edge or below the
    scenario's lock-up covenant (#1785 domain D-3)."""
    best = dscr.get("best")
    if not best:
        return "No DSCR target in the sweep gives a defined equity NPV optimum."
    target = float(best["target"])
    text = f"Best target on equity NPV: {target:.2f}x ({fmt_usd_m(best['obj'])})."
    edges = (DSCR_TARGETS[0], DSCR_TARGETS[-1])
    if any(math.isclose(target, e) for e in edges):
        text += (
            f" It sits at the edge of the {DSCR_TARGETS[0]:.2f}x-{DSCR_TARGETS[-1]:.2f}x "
            "sweep, so the sweep does not bracket an optimum."
        )
    lockup = _number(dscr.get("lockup_covenant"))
    if lockup is not None and target < lockup:
        text += (
            f" It is below the scenario's {lockup:.2f}x lock-up covenant, so distributions "
            "lock up in the years shown; the target is not a recommended sizing."
        )
    return text


# ── the DBPL document ──────────────────────────────────────────────────────────


def _figure(path: Optional[Path], alt: str) -> Any:
    from markupsafe import Markup, escape

    if path is None:
        return None
    return Markup('<img src="{}" alt="{}" style="width:100%">').format(
        escape(path.name), escape(alt)
    )


def _table(
    columns: Sequence[str], rows: Sequence[Sequence[Any]], **extra: Any
) -> Dict[str, Any]:
    numeric = extra.pop("numeric_indices", list(range(1, len(columns))))
    return {
        "columns": list(columns),
        "rows": [{"cells": [str(c) for c in r]} for r in rows],
        "numeric_indices": numeric,
        **extra,
    }


def as_dbpl_document(
    R: Mapping[str, Any],
    figures: Mapping[str, Path],
    *,
    issue_date: str,
    provenance_lines: Sequence[str] = (),
) -> Dict[str, Any]:
    """Project the assessment into the DBPL document model (``dbpl_base.html.j2``)."""
    name = str(R["scenario_name"])
    sections: List[Dict[str, Any]] = []
    ran = [label for key, label in _ANALYSES if key in R]
    sections.append(
        {
            "heading": "Scope and basis",
            "intro": (
                f"Every figure in this report is computed by the model from the scenario "
                f"file {R['scenario_path']}. No figure is typed in. The report runs the same "
                "analyses on any scenario that declares their inputs."
            ),
            "points": [f"Ran: {label}." for label in ran]
            + [f"Not run: {n['analysis']} ({n['reason']})." for n in R["not_run"]],
        }
    )
    res = R.get("resource")
    if res:
        section: Dict[str, Any] = {
            "heading": "Site and solar resource",
            "intro": (
                "The pvlib producer models the plant from the scenario's resource.solar block. "
                "Its capacity factor validates the one the scenario finances; it does not "
                "replace it."
            ),
            "table": _table(
                ["Item", "Value"],
                [
                    [
                        "Latitude, longitude (deg)",
                        f"{res['latitude']:.4f}, {res['longitude']:.4f}",
                    ],
                    ["DC capacity (MWp)", fmt_num(res["dc_capacity_mw"], 1)],
                    [
                        "Tilt / azimuth (deg)",
                        f"{res['tilt_deg']:.1f} / {res['azimuth_deg']:.1f}",
                    ],
                    ["Annual GHI (kWh/m2)", fmt_num(res["ghi_kwh_m2"], 0)],
                    [
                        "Plane-of-array insolation (kWh/m2)",
                        fmt_num(res["poa_kwh_m2"], 0),
                    ],
                    [
                        "Specific yield (kWh/kWp)",
                        fmt_num(res["specific_yield_kwh_per_kwp"], 0),
                    ],
                    ["Producer capacity factor (DC)", fmt_pct(res["producer_cf"], 2)],
                    [
                        "Financed capacity factor (scenario)",
                        fmt_pct(res["declared_cf"], 2),
                    ],
                    [
                        "Producer annual energy (GWh)",
                        fmt_num(res["annual_energy_gwh"], 1),
                    ],
                ],
                caption="Solar resource and yield",
                source="solar_resource.compute_solar_aep on the scenario's resource.solar block.",
            ),
        }
        if "location" in figures:
            section["exhibit"] = {
                "title": "Regional annual GHI around the site",
                "finding": "NASA POWER all-sky climatology; the star marks the scenario's coordinate.",
                "figure": _figure(figures["location"], "Regional GHI map"),
            }
        sections.append(section)
        if "context" in figures:
            sections.append(
                {
                    "heading": "Site imagery",
                    "exhibit": {
                        "title": "Imagery around the scenario's coordinate",
                        "finding": "Esri World Imagery, about 2 km either side of the coordinate.",
                        "figure": _figure(figures["context"], "Site imagery map"),
                    },
                }
            )
    base = R.get("base")
    if base:
        sections.append(
            {
                "heading": "Deterministic finance",
                "table": _table(
                    ["KPI", "Value"],
                    [
                        ["Project IRR", fmt_pct(base["project_irr"])],
                        ["Equity IRR", fmt_pct(base["equity_irr"])],
                        ["Project NPV", fmt_usd_m(base["project_npv"])],
                        ["Equity NPV", fmt_usd_m(base["equity_npv"])],
                        ["Minimum DSCR", fmt_x(base["min_dscr"])],
                        ["Average DSCR", fmt_x(base["avg_dscr"])],
                        ["Debt", fmt_usd_m(base["max_debt_usd"])],
                        [
                            "Project discount rate",
                            fmt_pct(base["discount_rate_used"], 2),
                        ],
                    ],
                    caption="The scenario as written",
                    source="analytics.pipeline_v14_enhanced.run_v14_pipeline.",
                ),
            }
        )
    if R.get("tariff_sweep"):
        be = R.get("breakeven") or {}
        notes = [
            f"{b['label']}: "
            + (
                f"{b['tariff_lkr']:.2f} LKR/kWh"
                if b["tariff_lkr"] is not None
                else f"not found ({b['status']}) in {b['bracket'][0]:.2f} to {b['bracket'][1]:.2f} LKR/kWh"
            )
            for b in be.values()
        ]
        if "project_irr" in be:
            notes.append(
                "The engine re-derives the project discount rate at each tariff. The IRR "
                "breakeven holds the base case's rate fixed; the tariff at which project IRR "
                "equals the rate in force at that tariff is the NPV = 0 breakeven."
            )
        sections.append(
            {
                "heading": "Tariff sweep and breakevens",
                "exhibit": _exhibit(
                    figures,
                    "tariff_sweep",
                    "Project IRR and minimum DSCR against the fixed tariff",
                ),
                "table": _table(
                    [
                        "Tariff (LKR/kWh)",
                        "x scenario",
                        "Project IRR",
                        "Equity IRR",
                        "Project NPV",
                        "Min DSCR",
                    ],
                    [
                        [
                            fmt_num(s["tariff"]),
                            f"{s['factor']:.2f}",
                            fmt_pct(s["projIRR"]),
                            fmt_pct(s["eqIRR"]),
                            fmt_usd_m(s["npv"]),
                            fmt_x(s["dscr"]),
                        ]
                        for s in R["tariff_sweep"]
                    ],
                    numeric_indices=[0, 1, 2, 3, 4, 5],
                    caption="Tariff sweep",
                    notes=notes or None,
                    source="Breakevens from analytics.core.parameter_solvers.solve_tariff_breakeven.",
                ),
            }
        )
    if R.get("capex_sweep"):
        sections.append(
            {
                "heading": "Capex sensitivity",
                "exhibit": _exhibit(
                    figures, "capex_sweep", "Project IRR and minimum DSCR against capex"
                ),
                "table": _table(
                    ["Capex", "x scenario", "Project IRR", "Project NPV", "Min DSCR"],
                    [
                        [
                            fmt_usd_m(c["capex_usd"]),
                            f"{c['factor']:.3f}",
                            fmt_pct(c["projIRR"]),
                            fmt_usd_m(c["npv"]),
                            fmt_x(c["dscr"]),
                        ]
                        for c in R["capex_sweep"]
                    ],
                    numeric_indices=[0, 1, 2, 3, 4],
                    caption="Capex sweep at the scenario's tariff",
                ),
            }
        )
    mc = R.get("mc")
    if mc:
        cov = mc["coverage"]
        p = mc["proj_irr"]
        sections.append(
            {
                "heading": "Monte Carlo",
                "intro": "Drivers: "
                + ", ".join(mc["parameters"])
                + ". Toy fallback is off.",
                "exhibit": _exhibit(figures, "mc", "Distribution of project IRR"),
                "table": _table(
                    ["Statistic", "Value"],
                    [
                        ["Trials (failed)", f"{mc['n']} ({mc['failed']})"],
                        [
                            "Project IRR defined in",
                            f"{cov['project_irr']['defined_trials']} of {cov['project_irr']['total_trials']} trials",
                        ],
                        [
                            "Project IRR P10 / P50 / P90",
                            " / ".join(
                                fmt_pct(p.get(q)) for q in ("p10", "p50", "p90")
                            ),
                        ],
                        ["P(project IRR < 0)", fmt_pct(mc["p_below_0"], 0)],
                        [
                            "Equity IRR defined in",
                            f"{cov['equity_irr']['defined_trials']} of {cov['equity_irr']['total_trials']} trials",
                        ],
                        ["Equity IRR P50", fmt_pct(mc["eq_p50"])],
                    ],
                    caption="Monte Carlo summary",
                    notes=[
                        "Each statistic uses only the trials where its metric is defined (#1474)."
                    ],
                ),
            }
        )
    if R.get("sensitivity"):
        sections.append(
            {
                "heading": "One-way sensitivity",
                "exhibit": _exhibit(
                    figures, "sensitivity", "Project IRR range for each driver"
                ),
                "table": _table(
                    ["Driver", "Low case", "High case", "Swing (pp)"],
                    [
                        [
                            d["param"],
                            fmt_pct(d["low"]),
                            fmt_pct(d["high"]),
                            (
                                UNDEFINED
                                if d["impact"] is None
                                else f"{d['impact'] * 100:.2f}"
                            ),
                        ]
                        for d in R["sensitivity"]
                    ],
                    caption="Project IRR",
                ),
            }
        )
    opt = R.get("optimization")
    if opt:
        exhibit = _exhibit(figures, "optimization", "Equity NPV against gearing")
        if exhibit:
            exhibit["finding"] = optimisation_caption(opt)
        sections.append(
            {
                "heading": "Gearing optimisation",
                "intro": optimisation_caption(opt),
                "exhibit": exhibit,
                "table": _table(
                    [
                        "Debt-ratio ceiling",
                        "Debt raised (% of capex)",
                        "Equity NPV",
                        "Equity IRR",
                        "Sponsor cures",
                        "Meets covenant",
                    ],
                    [
                        [
                            f"{p['x']:.0%}",
                            f"{p['realised']:.1%}",
                            fmt_usd_m(p["obj"]),
                            fmt_pct(p["eqIRR"]),
                            fmt_usd_m(p["cure"]),
                            "yes" if p["feasible"] else "no",
                        ]
                        for p in opt["curve"]
                    ],
                    numeric_indices=[0, 1, 2, 3, 4],
                    caption="Gearing sweep",
                ),
            }
        )
    dscr = R.get("dscr")
    if dscr:
        sections.append(
            {
                "heading": "DSCR sizing target",
                "intro": dscr_target_caption(dscr),
                "exhibit": _exhibit(
                    figures,
                    "dscr",
                    "IRR and solved gearing against the DSCR sizing target",
                ),
                "table": _table(
                    [
                        "Target",
                        "Gearing",
                        "Min DSCR",
                        "Project IRR",
                        "Equity IRR",
                        "Equity NPV",
                        "Lock-up years",
                    ],
                    [
                        [
                            f"{d['target_dscr']:.2f}x",
                            f"{d['gearing']:.0%}",
                            fmt_x(d["min_dscr"]),
                            fmt_pct(d["projIRR"]),
                            fmt_pct(d["eqIRR"]),
                            fmt_usd_m(d["eqNPV"]),
                            str(d["locked_years"]),
                        ]
                        for d in dscr["sweep"]
                    ],
                    numeric_indices=[0, 1, 2, 3, 4, 5, 6],
                    caption="Dual-DSCR sizing at each target",
                ),
            }
        )
    if R["not_run"]:
        sections.append(
            {
                "heading": "Analyses not run",
                "table": _table(
                    ["Analysis", "Reason"],
                    [[n["analysis"], n["reason"]] for n in R["not_run"]],
                    numeric_indices=[],
                    caption="Listed so that a missing figure is never silent",
                ),
            }
        )
    return {
        "title": f"Solar PV assessment - {name}",
        "banner": f"MODEL-DERIVED SCREENING | NOT A LENDER REPRESENTATION | {name}",
        "document_id": f"DBAY-SPA-{Path(str(R['scenario_path'])).stem.upper()}",
        "version": "v1.0",
        "issue_date": issue_date,
        "headline_caveat": (
            "Screening figures computed from the named scenario. They support no lender "
            "representation, and no quarterly CFADS or intra-year DSCR figure is stated (F-5)."
        ),
        "section_caveat": "MODEL-DERIVED FROM THE NAMED SCENARIO / NOT A LENDER REPRESENTATION",
        "first_section_number": 1,
        "sections": sections,
        "provenance_lines": tuple(provenance_lines),
    }


_ANALYSES = (
    ("resource", "Solar resource (pvlib producer)"),
    ("base", "Deterministic finance"),
    ("tariff_sweep", "Tariff sweep"),
    ("breakeven", "Breakeven tariffs"),
    ("capex_sweep", "Capex sweep"),
    ("mc", "Monte Carlo"),
    ("sensitivity", "One-way sensitivity"),
    ("optimization", "Gearing optimisation"),
    ("dscr", "DSCR sizing-target sweep"),
)


def _exhibit(figures: Mapping[str, Path], key: str, title: str) -> Dict[str, Any]:
    return (
        {"title": title, "figure": _figure(figures.get(key), title)}
        if key in figures
        else {}
    )


def render_html(doc: Mapping[str, Any]) -> str:
    from jinja2 import Environment, FileSystemLoader

    template_dir = Path(__file__).resolve().parent / "dbpl" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("dbpl_base.html.j2").render(doc=doc)


def write_report(
    scenario_path: str | Path,
    out_dir: Path,
    *,
    trials: int,
    issue_date: str,
    draw_maps: bool = True,
) -> Dict[str, Path]:
    """Run, chart and render one scenario's assessment into ``out_dir``.

    Writes ``results.json``, the charts, ``report.html`` and the DBPL PDF. The PDF needs the
    complete ``[report]`` extra; ``render_dbpl_pdf`` raises when it is missing.
    """
    from app.reports.dbpl import render_dbpl_pdf

    charts = out_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    R = run_assessment(scenario_path, trials=trials, work_dir=out_dir / "work")
    figures: Dict[str, Path] = dict(make_maps(R, charts)) if draw_maps else {}
    if not draw_maps and R.get("resource"):
        R["not_run"].append({"analysis": "Maps", "reason": "not requested"})
    figures.update(make_charts(R, charts))
    results = out_dir / "results.json"
    results.write_text(json.dumps(R, indent=1, default=float), encoding="utf-8")

    doc = as_dbpl_document(R, figures, issue_date=issue_date)
    first = render_dbpl_pdf(render_html(doc), base_url=str(charts) + "/")
    doc = as_dbpl_document(
        R, figures, issue_date=issue_date, provenance_lines=first.provenance_lines()
    )
    html = render_html(doc)
    (out_dir / "report.html").write_text(html, encoding="utf-8")
    pdf = out_dir / f"solar_assessment_{Path(str(scenario_path)).stem}.pdf"
    pdf.write_bytes(render_dbpl_pdf(html, base_url=str(charts) + "/").pdf)
    return {"results": results, "pdf": pdf, "html": out_dir / "report.html"}
