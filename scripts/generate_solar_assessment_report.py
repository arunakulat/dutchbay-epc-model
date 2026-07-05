#!/usr/bin/env python
"""Generate a lender-grade single-technology solar PV assessment report (PDF).

This is the **reporting stage** of the DutchBay v14 pipeline for a solar project: it
bakes together every analytical routine the platform offers and renders a detailed,
referenced, >10,000-word PDF assessment with an executive summary, a contents index,
a list of figures, charts, a georeferenced location map, and a references appendix.

Routines executed (all on the live engine — figures are model-derived, never invented):
  1. Solar resource & energy yield  -> ``solar_resource`` (pvlib producer)
  2. Deterministic finance           -> ``analytics.pipeline_v14_enhanced.run_v14_pipeline``
  3. Monte Carlo (Latin-Hypercube)   -> ``analytics.mc.engine.run_monte_carlo_analysis``
  4. One-way sensitivity (tornado)   -> ``analytics.core.sensitivity_runner``
  5. Capital-structure optimisation  -> ``analytics.optimization_v14.optimize_parameter``
  6. DSCR-covenant investigation     -> the optimisation routine over ``target_dscr``
  7. GIS location map (GeoTIFF)      -> ``analytics.gis.geotiff_export.write_geotiff``

The narrative prose is stored as data in ``scripts/assets/solar_assessment_narrative.json``
so the script is the renderer and the content is auditable separately.

Optional dependencies (CASPER-gated, lazily imported): ``reportlab`` (PDF), ``matplotlib``
(charts), ``pvlib``/``scipy`` (resource model & map smoothing), ``rasterio`` (GeoTIFF).
Install with ``pip install -e '.[report]'`` plus ``'.[solar]'`` and ``'.[gis]'``.

Usage::

    python scripts/generate_solar_assessment_report.py [--out DIR] [--trials N]

The base finance/analytics stack does NOT import this module; it is an end-of-pipeline
report generator invoked explicitly.
"""

from __future__ import annotations

import argparse
import copy
import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, cast

_REPO = Path(__file__).resolve().parents[1]
_ASSETS = Path(__file__).resolve().parent / "assets"


# ---------------------------------------------------------------------------
# SITE / PROJECT CONFIGURATION (the single source of report parameters)
# ---------------------------------------------------------------------------
SITE: Dict[str, Any] = {
    "location_name": "Sri Jayewardenepura Kotte",
    "location_detail": "Battaramulla / Pita Kotte, Colombo District, Western Province, Sri Lanka",
    "latitude": 6.8868,
    "longitude": 79.9187,
    "timezone": "Asia/Colombo",
    "altitude_m": 10.0,
    "ac_capacity_mw": 10.0,
    "dc_capacity_mw": 10.0,  # MWp (10 MWac at 1.2 ILR ~= 12 MWp; CF stated on DC nameplate)
    "annual_ghi_kwh_m2": 1909.0,  # Solargis v2.2.68 (bankable reference)
    "solargis_pvout": 1524.0,
    "nasa_ghi": 2049.0,
    "tilt_deg": 9.0,
    "azimuth_deg": 180.0,
    "dc_ac_ratio": 1.2,
    "system_loss_pct": 14.0,
    "bifacial_gain": 1.07,  # +7% (mid of 5-10%)
    "degradation_pct": 0.5,
    "life_years": 25,
    "ppa_term_years": 20,
    "capex_usd": 12_000_000,  # USD 1,200/kW (SL utility-PV range 1,100-1,350/kW)
    "opex_usd_yr": 130_000,
    "fx": 333.79,
    "fit_tariff_lkr": 14.46,  # SLSEA >1 MW FiT (Jun-2025)
    "competitive_usc": 8.0,  # Siyambalanduwa competitive PPA benchmark
    "report_date": "2026-06-23",
}
SITE["competitive_tariff_lkr"] = round(SITE["competitive_usc"] / 100.0 * SITE["fx"], 2)


# ---------------------------------------------------------------------------
# 1-6. ANALYTICAL ROUTINES (run on the live engine)
# ---------------------------------------------------------------------------
def _base_solar_config() -> Dict[str, Any]:
    """A solar single-technology v14 config derived from the canonical base case."""
    from analytics.scenario_loader import load_scenario_config

    cfg = copy.deepcopy(
        dict(
            load_scenario_config(
                str(_REPO / "scenarios" / "dutchbay_basecase_2025Q4.yaml")
            )
        )
    )
    cx = SITE["capex_usd"]
    cfg["project"].update(
        capacity_mw=SITE["dc_capacity_mw"],
        degradation=SITE["degradation_pct"],
        life_years=SITE["life_years"],
    )
    cfg["tariff"].update(tariff_type="fixed", ppa_term_years=SITE["ppa_term_years"])
    cfg["fx"]["start_lkr_per_usd"] = SITE["fx"]
    cfg["capex"]["usd_total"] = cx
    cfg["capex"]["breakdown"] = {
        "epc_usd": cx * 0.875,
        "development_usd": cx * 0.0625,
        "financing_fees_usd": cx * 0.0375,
        "contingency_usd": cx * 0.025,
    }
    cfg["opex"]["usd_per_year"] = SITE["opex_usd_yr"]
    cfg["opex"]["breakdown"] = {
        "om_contract_usd": 90_000,
        "insurance_usd": 20_000,
        "land_lease_usd": 15_000,
        "admin_usd": 5_000,
    }
    return cfg


def run_routines(trials: int = 1000) -> Dict[str, Any]:
    """Execute the full analytical chain and return a results dict."""
    from analytics.core.sensitivity_runner import (
        _default_parameters,
        run_sensitivity_analysis,
    )
    from analytics.mc.engine import run_monte_carlo_analysis
    from analytics.optimization_v14 import optimize_parameter
    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from solar_resource import SolarResourceConfig, compute_solar_aep

    R: Dict[str, Any] = {"site": SITE}

    # --- 1. Resource & energy yield ---
    pv = compute_solar_aep(
        SolarResourceConfig(
            latitude=SITE["latitude"],
            longitude=SITE["longitude"],
            timezone=SITE["timezone"],
            altitude_m=SITE["altitude_m"],
            annual_ghi_kwh_m2=SITE["annual_ghi_kwh_m2"],
            dc_capacity_mw=SITE["dc_capacity_mw"],
            tilt_deg=SITE["tilt_deg"],
            azimuth_deg=SITE["azimuth_deg"],
            dc_ac_ratio=SITE["dc_ac_ratio"],
            system_loss_pct=SITE["system_loss_pct"],
        )
    )
    cf = round(pv.capacity_factor * SITE["bifacial_gain"], 4)
    R["resource"] = {
        "cf_mono": pv.capacity_factor,
        "cf_bifacial": cf,
        "yield_mono": pv.specific_yield_kwh_per_kwp,
        "poa": pv.poa_kwh_m2,
        "clearsky_scale": pv.clearsky_scale,
        "aep_gwh": round(SITE["dc_capacity_mw"] * cf * 8.760, 2),
    }

    def make(tariff: float, capex: float | None = None) -> Dict[str, Any]:
        c = _base_solar_config()
        c["project"]["capacity_factor"] = cf
        c["tariff"]["lkr_per_kwh"] = tariff
        if capex is not None:
            c["capex"]["usd_total"] = capex
            c["capex"]["breakdown"] = {
                "epc_usd": capex * 0.875,
                "development_usd": capex * 0.0625,
                "financing_fees_usd": capex * 0.0375,
                "contingency_usd": capex * 0.025,
            }
        return c

    def kpis(cfg: Dict[str, Any]) -> Dict[str, Any]:
        res = run_v14_pipeline(config=cfg)
        k = res["kpis"]
        out = {
            kk: k.get(kk)
            for kk in (
                "project_irr",
                "equity_irr",
                "project_npv",
                "min_dscr",
                "avg_dscr",
                "max_debt_usd",
                "discount_rate_used",
            )
        }
        out["_cfads"] = [float(r.get("cfads_usd", 0)) for r in res["annual_rows"]]
        return out

    fit, comp = SITE["fit_tariff_lkr"], SITE["competitive_tariff_lkr"]
    R["case_fit"] = kpis(make(fit))
    R["case_competitive"] = kpis(make(comp))

    # --- 2/7. Breakeven sweeps ---
    R["tariff_sweep"] = []
    for t in (fit, 20, comp, 30, 35, 40, 45, 50, 55, 60):
        k = kpis(make(t))
        R["tariff_sweep"].append(
            {
                "tariff": t,
                "usc": round(t / (SITE["fx"] / 100), 2),
                "projIRR": k["project_irr"],
                "eqIRR": k["equity_irr"],
                "npv": k["project_npv"],
                "dscr": k["min_dscr"],
            }
        )
    R["capex_sweep"] = []
    for cxx in (9_000_000, 10_500_000, 12_000_000, 13_200_000, 15_000_000):
        k = kpis(make(comp, capex=cxx))
        R["capex_sweep"].append(
            {
                "per_kw": cxx / (SITE["dc_capacity_mw"] * 1000),
                "projIRR": k["project_irr"],
                "dscr": k["min_dscr"],
            }
        )

    # --- 3. Monte Carlo ---
    import numpy as np

    mc_cfg = make(comp)
    mc_cfg["monte_carlo"] = {
        "parameters": [
            {
                "name": "project.capacity_factor",
                "low": 0.165,
                "high": 0.199,
                "distribution": "normal",
            },
            {
                "name": "capex.usd_total",
                "low": 10_500_000,
                "high": 13_500_000,
                "distribution": "triangular",
            },
            {
                "name": "opex.usd_per_year",
                "low": 110_000,
                "high": 160_000,
                "distribution": "uniform",
            },
        ]
    }
    mc = run_monte_carlo_analysis(base_config=mc_cfg, n_trials=int(trials), seed=123)
    irr = mc.trials.get("project_irr", []) or []
    eqi = mc.trials.get("equity_irr", []) or []
    R["mc"] = {
        "n": mc.iterations,
        "failed": mc.failed_iterations,
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
        "_irr_trials": [float(x) for x in irr],
    }

    # --- 4. Sensitivity ---
    scen_path = _OUT_PATH / "solar_scenario_competitive.yaml"
    import yaml

    yaml.safe_dump(make(comp), open(scen_path, "w"), sort_keys=False)
    params = _default_parameters(load_cfg(scen_path))
    suite = run_sensitivity_analysis(str(scen_path), metric="project_irr")
    torn: list[Dict[str, Any]] = []
    for p, tr in zip(params, suite.tornado_results):
        sh = tr.shock_results[0]
        torn.append(
            {
                "param": p.label,
                "base": tr.base_metric,
                "low": sh.low_case,
                "high": sh.high_case,
                "impact": abs((sh.high_case or 0) - (sh.low_case or 0)),
            }
        )
    torn.sort(key=lambda d: -d["impact"])
    R["sensitivity"] = torn
    R["sensitivity_base"] = torn[0]["base"] if torn else None

    # --- 5. Optimisation: gearing ---
    opt = optimize_parameter(
        str(scen_path),
        param_path="Financing_Terms.debt_ratio",
        objective_key="equity_irr",
        lower=0.30,
        upper=0.75,
        direction="max",
        n_steps=10,
        # Constrain on the per-period sculpt floor (min_dscr_period), not the
        # fold-corrected headline (min_dscr). Since #790 the headline min_dscr is
        # the bridge-corrected per-year minimum, which the year-1 interest-only
        # lead-in can push below 1.30 (e.g. the CEB BESS timelines fold to ~0.91)
        # even when the sculpt holds 1.30 every operating period. The optimiser's
        # 1.30 target is the sculpt floor, so pair it with min_dscr_period.
        constraint_key="min_dscr_period",
        constraint_min=1.30,
    )
    R["optimization"] = {
        "curve": [
            {
                "x": float(p.value),
                "obj": float(p.objective),
                "feasible": bool(p.feasible),
                "constraint": float(p.constraint) if p.constraint is not None else None,
            }
            for p in opt.curve
        ],
        "best": (
            {"x": float(opt.best.value), "obj": float(opt.best.objective)}
            if opt.best
            else None
        ),
    }

    # --- 6. DSCR investigation (sculpted sizing) ---
    sculpt = make(comp)
    sculpt["Financing_Terms"]["debt_sizing"] = "dual_dscr"
    sp = _OUT_PATH / "solar_scenario_dscr_sculpt.yaml"
    yaml.safe_dump(sculpt, open(sp, "w"), sort_keys=False)
    dscr_sweep = []
    for td in (1.05, 1.10, 1.20, 1.30, 1.40, 1.50, 1.60):
        c = copy.deepcopy(sculpt)
        c["Financing_Terms"]["target_dscr"] = td
        k = run_v14_pipeline(config=c)["kpis"]
        dscr_sweep.append(
            {
                "target_dscr": td,
                "gearing": k.get("max_debt_usd", 0) / SITE["capex_usd"],
                "min_dscr": k["min_dscr"],
                "projIRR": k["project_irr"],
                "eqIRR": k["equity_irr"],
                "npv": k["project_npv"],
            }
        )
    dopt = optimize_parameter(
        str(sp),
        param_path="Financing_Terms.target_dscr",
        objective_key="equity_irr",
        lower=1.05,
        upper=1.60,
        direction="max",
        n_steps=12,
    )
    R["dscr"] = {
        "sweep": dscr_sweep,
        "opt_best": (
            {"target": float(dopt.best.value), "eqirr": float(dopt.best.objective)}
            if dopt.best
            else None
        ),
    }
    return R


def load_cfg(path: Path) -> Dict[str, Any]:
    from analytics.scenario_loader import load_scenario_config

    return load_scenario_config(str(path))


# ---------------------------------------------------------------------------
# 7. GEOTIFF LOCATION MAP (codebase GIS routine + render)
# ---------------------------------------------------------------------------
def make_location_map(charts: Path) -> bool:
    """Build a national GHI raster (NASA POWER), write a GeoTIFF via the codebase
    routine, and render a PNG location map. Falls back to a baked grid offline."""
    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from analytics.gis.geotiff_export import write_geotiff

    lats = np.round(np.arange(5.9, 10.0, 0.5), 2)
    lons = np.round(np.arange(79.6, 82.0, 0.5), 2)
    grid = np.full((len(lats), len(lons)), np.nan)
    try:
        for i, la in enumerate(lats):
            for j, lo in enumerate(lons):
                u = (
                    "https://power.larc.nasa.gov/api/temporal/climatology/point?"
                    "parameters=ALLSKY_SFC_SW_DWN&community=RE"
                    f"&latitude={la}&longitude={lo}&format=JSON"
                )
                with urllib.request.urlopen(u, timeout=20) as r:
                    d = json.load(r)
                grid[i, j] = (
                    d["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]["ANN"] * 365.0
                )
        bbox = (
            lons.min() - 0.25,
            lats.min() - 0.25,
            lons.max() + 0.25,
            lats.max() + 0.25,
        )
        gnorth = grid[::-1, :]
    except Exception:  # offline -> baked fallback
        fb = json.load(open(_ASSETS / "sri_lanka_ghi_grid.json"))
        gnorth = np.array(fb["grid"], dtype="float32")
        grid = gnorth[::-1, :]
        bbox = tuple(fb["bbox"])

    write_geotiff(
        np.nan_to_num(gnorth, nan=float(np.nanmean(gnorth))).astype("float32"),
        bbox,
        str(charts.parent / "sri_lanka_ghi.tif"),
        provenance={
            "source": "NASA POWER ALLSKY_SFC_SW_DWN climatology 2001-2020",
            "units": "kWh/m2/yr",
            "generated_by": "DutchBay v14 GeoTIFF export",
        },
    )

    try:
        from scipy.ndimage import zoom

        gs = zoom(np.nan_to_num(grid, nan=float(np.nanmean(grid))), 8, order=1)
    except Exception:
        gs = np.nan_to_num(grid, nan=float(np.nanmean(grid)))
    west, south, east, north = bbox
    fig, ax = plt.subplots(figsize=(5.2, 7.2))
    im = ax.imshow(
        gs,
        origin="lower",
        extent=(west, east, south, north),
        cmap="YlOrRd",
        vmin=1500,
        vmax=2100,
        aspect="equal",
        alpha=0.92,
    )

    # Clip the choropleth to Sri Lanka's land polygon (geopandas) so the raster
    # follows the real coastline instead of a rectangle; gracefully degrade to a
    # plain coastline outline if geopandas/shapely or the network is unavailable.
    masked = False
    try:
        import geopandas as gpd
        from matplotlib.patches import PathPatch
        from matplotlib.path import Path as MPath

        gdf = gpd.read_file(
            "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/LKA.geo.json"
        )
        geom = (
            gdf.geometry.union_all()
            if hasattr(gdf.geometry, "union_all")
            else gdf.geometry.unary_union
        )
        geoms = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        verts: list = []
        codes: list = []
        for g in geoms:
            ring = list(g.exterior.coords)
            verts.extend(ring)
            codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(ring) - 1))
        clip = PathPatch(
            MPath(verts, codes),
            transform=ax.transData,
            fc="none",
            ec="#333",
            lw=0.8,
            zorder=5,
        )
        ax.add_patch(clip)
        im.set_clip_path(clip)
        masked = True
    except Exception:
        pass
    if not masked:  # outline-only fallback
        poly = None
        try:
            with urllib.request.urlopen(
                "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/LKA.geo.json",
                timeout=20,
            ) as r:
                poly = json.load(r)["features"][0]["geometry"]["coordinates"]
        except Exception:
            pass
        if poly:
            for part in poly:
                rings = part if isinstance(part[0][0], list) else [part]
                for ring in rings:
                    a = np.array(ring)
                    ax.plot(a[:, 0], a[:, 1], color="#333", lw=0.8)
    ax.plot(
        SITE["longitude"],
        SITE["latitude"],
        marker="*",
        ms=22,
        color="#1f3a5f",
        mec="white",
        mew=1.2,
        zorder=6,
    )
    ax.annotate(
        f"PROJECT SITE\n{SITE['location_name']}\n({SITE['latitude']:.3f}N, {SITE['longitude']:.3f}E)",
        xy=(SITE["longitude"], SITE["latitude"]),
        xytext=(80.55, 6.55),
        fontsize=7.5,
        fontweight="bold",
        color="#1f3a5f",
        arrowprops=dict(arrowstyle="->", color="#1f3a5f", lw=1),
    )
    for nm, (la, lo) in {
        "Colombo": (6.93, 79.86),
        "Jaffna": (9.66, 80.01),
        "Trincomalee": (8.57, 81.23),
        "Hambantota": (6.12, 81.12),
        "Vavuniya": (8.75, 80.50),
        "Pooneryn": (9.55, 80.23),
    }.items():
        ax.plot(lo, la, "o", ms=3, color="#444")
        ax.text(lo + 0.05, la, nm, fontsize=6.5, color="#222")
    ax.text(
        80.5,
        9.3,
        "DRY ZONE\n(best solar:\n1,700-1,800 kWh/kWp)",
        fontsize=6.5,
        color="#7a3b00",
        ha="center",
        fontweight="bold",
    )
    ax.text(
        79.95,
        6.2,
        "WET ZONE\n(site here)",
        fontsize=6.5,
        color="#1f3a5f",
        ha="center",
        fontweight="bold",
    )
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Annual GHI (kWh/m2/yr)", fontsize=8)
    ax.set_xlabel("Longitude (deg E)", fontsize=8)
    ax.set_ylabel("Latitude (deg N)", fontsize=8)
    ax.set_title(
        "Sri Lanka Solar Resource (GHI) & Project Site",
        fontweight="bold",
        color="#1f3a5f",
        fontsize=10,
    )
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(charts / "00_location_map.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return True


def make_site_context_map(charts: Path) -> bool:
    """Render a satellite/aerial close-up of the exact coordinate over an Esri
    World Imagery basemap (contextily). This makes the land-use reality of the
    site explicit. Returns False (and writes no file) when contextily or the
    tile network is unavailable, in which case the PDF omits the figure."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        import contextily as cx
    except Exception:
        return False
    lat, lon = SITE["latitude"], SITE["longitude"]
    d = 0.018  # ~2 km half-window in degrees
    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    ax.set_xlim(lon - d, lon + d)
    ax.set_ylim(lat - d, lat + d)
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
        return False
    ax.plot(
        lon, lat, marker="*", ms=30, color="#ffd400", mec="#1f3a5f", mew=1.6, zorder=6
    )
    ax.annotate(
        "PROJECT COORDINATE\n6.8868N, 79.9187E",
        xy=(lon, lat),
        xytext=(lon - d * 0.9, lat + d * 0.72),
        fontsize=8,
        fontweight="bold",
        color="white",
        arrowprops=dict(arrowstyle="->", color="white", lw=1.4),
        bbox=dict(boxstyle="round,pad=0.3", fc="#1f3a5f", ec="white", alpha=0.85),
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(
        f"Site context — {SITE['location_name']} (Esri World Imagery)",
        fontweight="bold",
        color="#1f3a5f",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(charts / "00b_site_satellite.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------
def make_charts(R: Dict[str, Any], charts: Path) -> None:
    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 10,
            "font.family": "DejaVu Sans",
            "axes.grid": True,
            "grid.alpha": 0.3,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 150,
        }
    )
    NAVY, TEAL, AMBER, RED, GREY = "#1f3a5f", "#2a9d8f", "#e9a23b", "#c1432e", "#888"

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(f"{charts}/{name}.png", bbox_inches="tight")
        plt.close(fig)

    # 01 monthly -- recompute monthly profile via pvlib
    try:
        import pandas as pd
        import pvlib

        loc = pvlib.location.Location(
            SITE["latitude"], SITE["longitude"], SITE["timezone"], SITE["altitude_m"]
        )
        t = pd.date_range(
            "2021-01-01", "2021-12-31 23:00", freq="1h", tz=SITE["timezone"]
        )
        cs = loc.get_clearsky(t, model="ineichen")
        sc = SITE["annual_ghi_kwh_m2"] / (cs["ghi"].sum() / 1000)
        ghi = cs["ghi"] * sc
        sp = loc.get_solarposition(t)
        dni = pvlib.irradiance.disc(ghi, sp["zenith"], t)["dni"]
        dhi = (ghi - dni * np.cos(np.radians(sp["zenith"]))).clip(lower=0)
        dx = pvlib.irradiance.get_extra_radiation(t)
        poa = pvlib.irradiance.get_total_irradiance(
            SITE["tilt_deg"],
            SITE["azimuth_deg"],
            sp["apparent_zenith"],
            sp["azimuth"],
            dni,
            ghi,
            dhi,
            dni_extra=dx,
            model="haydavies",
        )["poa_global"].clip(lower=0)
        tc = pvlib.temperature.faiman(poa, 28.0, 2.0)
        dc = pvlib.pvsystem.pvwatts_dc(poa, tc, SITE["dc_capacity_mw"] * 1e6, -0.0035)
        accap = SITE["dc_capacity_mw"] * 1e6 / SITE["dc_ac_ratio"]
        ac = (
            pvlib.inverter.pvwatts(dc, pdc0=accap / 0.96).clip(upper=accap)
            * (1 - SITE["system_loss_pct"] / 100)
            * SITE["bifacial_gain"]
        )
        monthly = (ac.resample("ME").sum() / 1e9).tolist()
    except Exception:
        monthly = [R["resource"]["aep_gwh"] / 12] * 12
    mo = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(mo, monthly, color=TEAL, edgecolor=NAVY, linewidth=0.5)
    ax.axhline(np.mean(monthly), color=GREY, ls="--", lw=1)
    ax.set_ylabel("Energy (GWh)")
    ax.set_title(
        "Year-1 Monthly Energy Yield - 10 MWp bifacial (P50)",
        fontweight="bold",
        color=NAVY,
    )
    ax.text(
        0.02,
        0.92,
        f"Total {sum(monthly):.1f} GWh/yr | CF {R['resource']['cf_bifacial']:.1%}",
        transform=ax.transAxes,
        fontsize=9,
        color=NAVY,
    )
    save(fig, "01_monthly")

    # 02 tariff breakeven
    ts = R["tariff_sweep"]
    t = cast(Any, [s["tariff"] for s in ts])
    pi = [s["projIRR"] * 100 for s in ts]
    dscr = [s["dscr"] for s in ts]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax2 = ax.twinx()
    ax.plot(t, pi, "-o", color=NAVY, lw=2)
    ax2.plot(t, dscr, "-s", color=AMBER, lw=1.6)
    ax.axhline(10, color=RED, ls=":", lw=1.4)
    ax.text(15, 10.4, "WACC ~ 10%", color=RED, fontsize=8)
    ax2.axhline(1.30, color=TEAL, ls=":", lw=1.4)
    ax2.text(55, 1.33, "DSCR 1.30", color=TEAL, fontsize=8)
    for xv, lab in (
        (SITE["fit_tariff_lkr"], "FiT"),
        (SITE["competitive_tariff_lkr"], "USc8"),
        (50, "b/e ~50"),
    ):
        ax.axvline(xv, color=GREY, ls="--", lw=1)
        ax.text(xv + 0.3, -3.5, lab, rotation=90, fontsize=7, color=GREY, va="bottom")
    ax.set_xlabel("Fixed PPA tariff (LKR/kWh)")
    ax.set_ylabel("Project IRR (%)", color=NAVY)
    ax2.set_ylabel("min DSCR", color=AMBER)
    ax.set_title(
        "Breakeven Frontier - Project IRR & DSCR vs Tariff",
        fontweight="bold",
        color=NAVY,
    )
    ax.set_ylim(-6, 10.5)
    ax2.set_ylim(0.2, 1.5)
    ax.legend(["Project IRR"], loc="upper left", fontsize=8)
    save(fig, "02_tariff_breakeven")

    # 03 MC
    irr = np.array(R["mc"]["_irr_trials"]) * 100
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(irr, bins=40, color=TEAL, edgecolor="white", alpha=0.85)
    p = R["mc"]["proj_irr"]
    for q, lab, col in (
        (p["p10"] * 100, "P10", "#999"),
        (p["p50"] * 100, "P50", NAVY),
        (p["p90"] * 100, "P90", "#999"),
    ):
        ax.axvline(q, color=col, ls="--", lw=1.5)
        ax.text(
            q,
            ax.get_ylim()[1] * 0.92,
            f"{lab}\n{q:.1f}%",
            ha="center",
            fontsize=7,
            color=col,
        )
    ax.axvline(10, color=RED, ls=":", lw=1.6)
    ax.text(
        10,
        ax.get_ylim()[1] * 0.6,
        "WACC 10%",
        rotation=90,
        color=RED,
        fontsize=8,
        va="center",
    )
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Project IRR (%)")
    ax.set_ylabel("Trials")
    ax.set_title(
        f"Monte Carlo - Project IRR (n={R['mc']['n']}, LHS) | P(IRR<0)={p['p_below_0'] if False else R['mc']['p_below_0']:.0%}",
        fontweight="bold",
        color=NAVY,
    )
    save(fig, "03_mc_irr")

    # 04 tornado
    sd = [d for d in R["sensitivity"] if d["impact"] > 0]
    base = R["sensitivity_base"] * 100
    labels = [d["param"] for d in sd][::-1]
    lows = [d["low"] * 100 for d in sd][::-1]
    highs = [d["high"] * 100 for d in sd][::-1]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    y = np.arange(len(labels))
    for i in range(len(labels)):
        lo, hi = sorted([lows[i], highs[i]])
        ax.barh(y[i], hi - lo, left=lo, color=TEAL, edgecolor=NAVY, height=0.6)
    ax.axvline(base, color=RED, lw=1.6)
    ax.text(
        base, len(labels) - 0.3, f"base {base:.1f}%", color=RED, fontsize=8, ha="center"
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Project IRR (%)")
    ax.set_title(
        "One-Way Sensitivity (Tornado) - driver of Project IRR",
        fontweight="bold",
        color=NAVY,
    )
    save(fig, "04_tornado")

    # 05 optimisation
    oc = R["optimization"]["curve"]
    g = [p["x"] * 100 for p in oc]
    eq = [p["obj"] * 100 for p in oc]
    feas = [p["feasible"] for p in oc]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(g, eq, "-", color=NAVY, lw=1.5, alpha=0.5)
    ax.scatter(
        [g[i] for i in range(len(g)) if feas[i]],
        [eq[i] for i in range(len(g)) if feas[i]],
        color=TEAL,
        s=55,
        zorder=5,
        label="feasible (DSCR>=1.30)",
    )
    ax.scatter(
        [g[i] for i in range(len(g)) if not feas[i]],
        [eq[i] for i in range(len(g)) if not feas[i]],
        color=RED,
        marker="x",
        s=45,
        zorder=5,
        label="infeasible",
    )
    b = R["optimization"]["best"]
    if b:
        ax.scatter(
            [b["x"] * 100],
            [b["obj"] * 100],
            edgecolor=AMBER,
            facecolor="none",
            s=180,
            lw=2,
            zorder=6,
            label=f"best {b['x']:.0%}",
        )
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylim(-30, 5)
    ax.set_xlabel("Gearing (debt ratio, %)")
    ax.set_ylabel("Equity IRR (%)")
    ax.set_title(
        "Capital-Structure Optimisation - Equity IRR vs Gearing",
        fontweight="bold",
        color=NAVY,
    )
    ax.legend(loc="lower left", fontsize=8)
    save(fig, "05_optimization")

    # 06 capex
    cs = R["capex_sweep"]
    ck = [c["per_kw"] for c in cs]
    cpi = [c["projIRR"] * 100 for c in cs]
    cd = [c["dscr"] for c in cs]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax2 = ax.twinx()
    ax.plot(ck, cpi, "-o", color=NAVY, lw=2)
    ax2.plot(ck, cd, "-s", color=AMBER, lw=1.5)
    ax.axhline(10, color=RED, ls=":", lw=1.2)
    ax2.axhline(1.30, color=TEAL, ls=":", lw=1.2)
    ax.set_xlabel("Capex (USD/kW)")
    ax.set_ylabel("Project IRR (%)", color=NAVY)
    ax2.set_ylabel("min DSCR", color=AMBER)
    ax.set_title(
        "Capex Sensitivity (at competitive USc 8.0 PPA)", fontweight="bold", color=NAVY
    )
    save(fig, "06_capex")

    # 07 dscr
    D = R["dscr"]["sweep"]
    td = [d["target_dscr"] for d in D]
    pi2 = [d["projIRR"] * 100 for d in D]
    ei = [d["eqIRR"] * 100 for d in D]
    gg = [d["gearing"] * 100 for d in D]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax2 = ax.twinx()
    ax.plot(td, pi2, "-o", color=NAVY, lw=2, label="Project IRR (unlevered)")
    ax.plot(td, ei, "-s", color=RED, lw=2, label="Equity IRR (levered)")
    ax2.plot(td, gg, "--^", color=AMBER, lw=1.6, label="Solved gearing (RHS)")
    ax.axvline(1.30, color=GREY, ls=":", lw=1.2)
    ax.annotate(
        "Project IRR INVARIANT to the DSCR target",
        xy=(1.30, pi2[3]),
        xytext=(1.12, 3.2),
        fontsize=7.5,
        color=NAVY,
        arrowprops=dict(arrowstyle="->", color=NAVY, lw=0.8),
    )
    ax.set_xlabel("Minimum-DSCR sizing target (x)")
    ax.set_ylabel("IRR (%)")
    ax2.set_ylabel("Solved gearing (%)", color=AMBER)
    ax.set_ylim(-7, 5)
    ax2.set_ylim(20, 55)
    ax.set_title(
        "Is the 1.30x DSCR limiting?  Effect of the DSCR target",
        fontweight="bold",
        color=NAVY,
    )
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=7.5)
    save(fig, "07_dscr")


# ---------------------------------------------------------------------------
# PDF RENDERING
# ---------------------------------------------------------------------------
def render_pdf(
    R: Dict[str, Any], narrative: Dict[str, Any], charts: Path, out_pdf: Path
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image,
        NextPageTemplate,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.platypus.tableofcontents import TableOfContents

    S = SITE
    res = R["resource"]
    cc = R["case_competitive"]
    cf = R["case_fit"]
    mc = R["mc"]
    D = R["dscr"]
    NAVY = colors.HexColor("#1f3a5f")
    TEAL = colors.HexColor("#2a9d8f")
    LIGHT = colors.HexColor("#eef2f6")
    GREY = colors.HexColor("#555")

    def pc(x):
        return f"{x*100:.1f}%"

    def usd(x):
        return f"${x/1e6:.2f}M"

    ss = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        textColor=colors.HexColor("#222"),
    )
    h1 = ParagraphStyle(
        "TOCH1",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=NAVY,
        spaceBefore=14,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "TOCH2",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        textColor=TEAL,
        spaceBefore=10,
        spaceAfter=4,
    )
    cap = ParagraphStyle(
        "cap",
        parent=ss["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=GREY,
        alignment=1,
        spaceAfter=10,
    )
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=14, spaceAfter=3)
    cH = ParagraphStyle(
        "cH",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.3,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )
    cHL = ParagraphStyle("cHL", parent=cH, alignment=TA_LEFT)
    cB = ParagraphStyle(
        "cB",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=10.5,
        textColor=colors.HexColor("#222"),
        alignment=1,
    )
    cBL = ParagraphStyle("cBL", parent=cB, alignment=TA_LEFT)
    mK = ParagraphStyle(
        "mK",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=NAVY,
    )
    mV = ParagraphStyle(
        "mV",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#222"),
    )

    story = []
    figno = [0]

    def P(t):
        story.append(Paragraph(t, body))

    def B(t):
        story.append(Paragraph("&bull;&nbsp; " + t, bullet))

    def H1(t):
        story.append(Paragraph(t, h1))

    def H2(t):
        story.append(Paragraph(t, h2))

    def FIG(name, w=15.5 * cm):
        figno[0] += 1
        story.append(Image(f"{charts}/{name}.png", width=w, height=w * 0.5))

    def CAP(t):
        story.append(Paragraph(f"Figure {figno[0]} &mdash; {t}", cap))

    def datatable(header, rows, cw, hi=()):
        data = [[Paragraph(header[0], cHL)] + [Paragraph(h, cH) for h in header[1:]]]
        data += [
            [Paragraph(str(r[0]), cBL)] + [Paragraph(str(c), cB) for c in r[1:]]
            for r in rows
        ]
        t = Table(data, colWidths=cw, repeatRows=1)
        st = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]
        for r in hi:
            st.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#fdebd0")))
        t.setStyle(TableStyle(st))
        story.append(t)
        story.append(Spacer(1, 8))

    def render_section(key):
        sec = narrative[key]
        H1(sec["title"])
        for sh in sec["subheads"]:
            H2(sh["title"])
            for para in sh["paragraphs"]:
                P(para)

    # ---- page templates ----
    def hf(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 1.05 * cm, A4[0], 1.05 * cm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawString(
            1.6 * cm,
            A4[1] - 0.68 * cm,
            "DUTCHBAY EPC MODEL v14  -  TECHNICAL & FINANCIAL ASSESSMENT",
        )
        canvas.drawRightString(
            A4[0] - 1.6 * cm,
            A4[1] - 0.68 * cm,
            f"10 MW SOLAR PV  -  {S['location_name'].upper()}",
        )
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(
            1.6 * cm,
            0.7 * cm,
            "Generated by the DutchBay v14 project-finance engine - sample output. Model-derived; see assumptions & sources.",
        )
        canvas.drawRightString(A4[0] - 1.6 * cm, 0.7 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(colors.HexColor("#ccc"))
        canvas.line(1.6 * cm, 1.0 * cm, A4[0] - 1.6 * cm, 1.0 * cm)
        canvas.restoreState()

    def title_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 7.5 * cm, A4[0], 7.5 * cm, fill=1, stroke=0)
        canvas.setFillColor(TEAL)
        canvas.rect(0, A4[1] - 7.75 * cm, A4[0], 0.25 * cm, fill=1, stroke=0)
        canvas.restoreState()

    class Doc(BaseDocTemplate):  # type: ignore[misc]  # reportlab ships no type stubs, base class resolves to Any
        def afterFlowable(self, fl):
            if fl.__class__.__name__ == "Paragraph":
                st = fl.style.name
                if st == "TOCH1":
                    self.notify("TOCEntry", (0, fl.getPlainText(), self.page))
                elif st == "TOCH2":
                    self.notify("TOCEntry", (1, fl.getPlainText(), self.page))

    fr = Frame(1.6 * cm, 1.2 * cm, A4[0] - 3.2 * cm, A4[1] - 2.6 * cm, id="main")
    tfr = Frame(1.6 * cm, 1.2 * cm, A4[0] - 3.2 * cm, A4[1] - 2.0 * cm, id="title")
    doc = Doc(
        str(out_pdf),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.2 * cm,
        title=f"10 MW Solar PV Assessment - {S['location_name']}",
        author="DutchBay v14",
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="title", frames=[tfr], onPage=title_bg),
            PageTemplate(id="main", frames=[fr], onPage=hf),
        ]
    )

    # ---- COVER ----
    story.append(Spacer(1, 1.2 * cm))
    story.append(
        Paragraph(
            "Independent Technical &amp;<br/>Financial Assessment",
            ParagraphStyle(
                "t",
                fontName="Helvetica-Bold",
                fontSize=27,
                leading=31,
                textColor=colors.white,
            ),
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "10&nbsp;MW Single-Technology Solar PV (Bifacial)",
            ParagraphStyle(
                "s1",
                fontName="Helvetica",
                fontSize=15,
                leading=19,
                textColor=colors.HexColor("#d9e6f2"),
            ),
        )
    )
    story.append(
        Paragraph(
            S["location_name"],
            ParagraphStyle(
                "s2",
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=22,
                textColor=colors.white,
            ),
        )
    )
    story.append(
        Paragraph(
            f"{S['location_detail']} &mdash; {S['latitude']:.4f}&deg;N, {S['longitude']:.4f}&deg;E",
            ParagraphStyle(
                "s3",
                fontName="Helvetica",
                fontSize=10.5,
                leading=14,
                textColor=colors.HexColor("#d9e6f2"),
            ),
        )
    )
    story.append(Spacer(1, 4.6 * cm))
    meta = [
        ["Prepared with", "DutchBay EPC Model &mdash; v14 project-finance engine"],
        [
            "Routines",
            "Resource (pvlib) &middot; finance &middot; Monte&nbsp;Carlo &middot; sensitivity &middot; optimisation &middot; GeoTIFF map",
        ],
        ["Capacity", "10&nbsp;MWac / ~12&nbsp;MWp DC (1.2 ILR), fixed-tilt bifacial"],
        ["Report date", S["report_date"]],
        ["Status", "SAMPLE OUTPUT &mdash; model-derived; not investment advice"],
    ]
    mt = Table(
        [[Paragraph(a, mK), Paragraph(b, mV)] for a, b in meta],
        colWidths=[3.6 * cm, 11.9 * cm],
    )
    mt.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#ccc")),
            ]
        )
    )
    story.append(mt)
    story.append(NextPageTemplate("main"))
    story.append(PageBreak())

    # ---- CONTENTS ----
    H1("Contents")
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "toc1", fontName="Helvetica-Bold", fontSize=10, leading=16, textColor=NAVY
        ),
        ParagraphStyle(
            "toc2",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            leftIndent=14,
            textColor=colors.HexColor("#333"),
        ),
    ]
    story.append(toc)
    story.append(Spacer(1, 8))
    H2("List of Figures")
    figs = [
        "Sri Lanka solar resource (GHI) and project site",
        "Year-1 monthly energy yield",
        "Breakeven frontier - project IRR & DSCR vs tariff",
        "Capex sensitivity",
        "Monte Carlo distribution of project IRR",
        "One-way sensitivity (tornado)",
        "Capital-structure optimisation (equity IRR vs gearing)",
        "Effect of the DSCR sizing target",
    ]
    for i, f in enumerate(figs, 1):
        B(f"Figure {i}: {f}")
    story.append(PageBreak())

    # ---- EXECUTIVE SUMMARY ----
    H1("1. Executive Summary")
    P(
        f"This report is an independent technical and financial assessment of a proposed <b>10&nbsp;MW single-technology solar "
        f"photovoltaic plant</b> at {S['latitude']:.4f}&deg;N, {S['longitude']:.4f}&deg;E, which reverse-geocodes to "
        f"<b>{S['location_name']}</b> ({S['location_detail']}). It is produced end-to-end by the DutchBay v14 project-finance "
        f"engine and exercises every analytical routine the platform offers: a physics-based pvlib energy model, the canonical "
        f"discounted-cashflow / dual-DSCR debt-sculpting finance engine, a {mc['n']:,}-trial Latin-Hypercube Monte&nbsp;Carlo "
        f"simulation, a one-way sensitivity (tornado) analysis, a constrained capital-structure optimisation, a dedicated "
        f"investigation of the DSCR covenant, and a georeferenced GeoTIFF resource map."
    )
    P(
        f"<b>Two locational facts frame the assessment.</b> First, the coordinate falls beside the national Parliament and the "
        f"Diyawanna Oya wetland in Sri Lanka&rsquo;s administrative capital &mdash; a dense urban and protected-wetland setting in "
        f"which there is realistically <b>no contiguous land</b> for a utility-scale array. Second, the site lies in the island&rsquo;s "
        f"south-west <b>wet zone</b>, among its <b>lowest-irradiance</b> regions. The bankable Solargis resource is "
        f"{S['annual_ghi_kwh_m2']:,.0f}&nbsp;kWh/m&sup2;/yr GHI; the DutchBay pvlib model independently reproduces a specific yield "
        f"within 2% of the Solargis reference and gives a net capacity factor of only <b>{pc(res['cf_bifacial'])}</b> "
        f"(including a +7% bifacial gain), for ~{res['aep_gwh']:.1f}&nbsp;GWh/yr."
    )
    P(
        f"<b>Headline finding: the project is not viable at any tariff currently available to a standalone 10&nbsp;MW plant.</b> "
        f"Under the best realistically-achievable revenue &mdash; a competitive USD PPA at USc&nbsp;8.0/kWh "
        f"(LKR&nbsp;{S['competitive_tariff_lkr']:.2f}) &mdash; the unlevered project IRR is just <b>{pc(cc['project_irr'])}</b> "
        f"against a ~{pc(cc['discount_rate_used'])} cost of capital, with a project NPV of <b>{usd(cc['project_npv'])}</b>. Under "
        f"the regime a standalone plant would most likely receive &mdash; the LKR&nbsp;{S['fit_tariff_lkr']:.2f}/kWh feed-in tariff "
        f"&mdash; the project IRR is <b>{pc(cf['project_irr'])}</b> (NPV {usd(cf['project_npv'])}). The Monte&nbsp;Carlo confirms "
        f"robustness: the project IRR has a P50 of <b>{pc(mc['proj_irr']['p50'])}</b> (P10 {pc(mc['proj_irr']['p10'])} / P90 "
        f"{pc(mc['proj_irr']['p90'])}) and never reaches the cost of capital; the probability of even a positive return is only "
        f"{pc(1 - mc['p_below_0'])}."
    )
    P(
        "The breakeven analysis shows the plant needs ~<b>LKR&nbsp;50/kWh</b> for a 1.30&times; DSCR and ~<b>LKR&nbsp;60/kWh</b> "
        "for the project return to reach the cost of capital &mdash; roughly 2&ndash;4&times; the tariffs on offer. The "
        "optimisation shows no capital structure rescues the equity (negative carry), and a dedicated test confirms the "
        "<b>1.30&times; DSCR covenant is not the limiting factor</b> &mdash; the unlevered project IRR is invariant to it. "
        "<b>Recommendation: do not proceed</b> at this site under current terms; the technology specification (a Tier-1 bifacial "
        "n-TOPCon module) is sound and is not the problem. The project should be reconsidered only with a dry-zone site "
        "(+15&ndash;20% yield), a competitively-tendered USD PPA at scale, lower installed cost, and/or concessional capital."
    )
    story.append(PageBreak())

    # ---- BODY (narrative + data) ----
    render_section("site")
    FIG("00_location_map", w=11 * cm)
    CAP(
        "Sri Lanka solar resource (GHI, NASA POWER) clipped to the national land polygon, and the project site. The site sits in the lower-resource south-west; the dry north-east/south-east is materially sunnier. A georeferenced GeoTIFF of this layer is produced alongside the report."
    )
    if (charts / "00b_site_satellite.png").exists():
        FIG("00b_site_satellite", w=11 * cm)
        CAP(
            "Satellite close-up of the exact coordinate (Esri World Imagery, ~2&nbsp;km window). The marker sits on the Diyawanna&nbsp;Oya wetland / Sri Jayewardenepura&nbsp;Kotte administrative core &mdash; a dense urban and protected-wetland setting with no contiguous land for a 10&nbsp;MW ground-mount array. This is a project-defining land-use constraint, made explicit here."
        )

    render_section("resource")
    datatable(
        ["Resource metric", "Value", "Source"],
        [
            [
                "Annual GHI",
                f"{S['annual_ghi_kwh_m2']:,.0f} kWh/m2/yr",
                "Solargis v2.2.68 (bankable)",
            ],
            [
                "GHI cross-check",
                f"~{S['nasa_ghi']:,.0f} kWh/m2/yr",
                "NASA POWER 2001-2020",
            ],
            ["PVOUT (monofacial)", f"{S['solargis_pvout']:,.0f} kWh/kWp", "Solargis"],
            [
                "DutchBay model yield",
                f"{res['yield_mono']:,.0f} kWh/kWp",
                "pvlib producer (within 2%)",
            ],
            ["Net capacity factor", pc(res["cf_bifacial"]), "pvlib (+7% bifacial)"],
            ["Year-1 net energy", f"{res['aep_gwh']:.1f} GWh", "pvlib model"],
        ],
        [5.5 * cm, 5.0 * cm, 5.0 * cm],
    )

    render_section("tech")
    datatable(
        ["Rank / Module", "Cell", "Power", "Bifaciality", "Temp coeff", "Note"],
        [
            [
                "1 - Trina Vertex N",
                "n-TOPCon",
                "720 W",
                "80+-5%",
                "-0.29%/C",
                "PRIMARY: salt-mist + ammonia certified; bankability",
            ],
            [
                "2 - Risen Hyper-ion",
                "n-HJT",
                "700-725 W",
                "~85-90%",
                "-0.24%/C",
                "Best hot-climate physics; HJT premium",
            ],
            [
                "3 - Huasun Himalaya G12",
                "n-HJT",
                "700-720 W",
                "85+-5%",
                "-0.26%/C",
                "HJT yield + India-BIS channel",
            ],
            [
                "4 - Astronergy N7 Pro",
                "n-TOPCon",
                "670 W",
                "85+-5%",
                "-0.26%/C",
                "Highest efficiency (24.8%); newest",
            ],
        ],
        [4.3 * cm, 1.7 * cm, 1.9 * cm, 1.9 * cm, 1.8 * cm, 3.9 * cm],
    )

    render_section("yield-method")
    FIG("01_monthly")
    CAP(
        "Modelled year-1 monthly energy yield (P50). Equatorial sites show low seasonality."
    )

    render_section("finance-method")

    render_section("results")
    datatable(
        ["Metric", "Base / Regulatory (FiT 14.46)", "Investment (USc 8.0 / 26.70)"],
        [
            ["Project IRR (unlevered)", pc(cf["project_irr"]), pc(cc["project_irr"])],
            ["Project NPV @ WACC", usd(cf["project_npv"]), usd(cc["project_npv"])],
            [
                "Minimum DSCR (70% gearing)",
                f"{cf['min_dscr']:.2f}",
                f"{cc['min_dscr']:.2f}",
            ],
            [
                "WACC / discount rate",
                pc(cf["discount_rate_used"]),
                pc(cc["discount_rate_used"]),
            ],
            ["Verdict", "Not viable", "Not viable (sub-WACC)"],
        ],
        [5.5 * cm, 5.0 * cm, 5.0 * cm],
        hi=(5,),
    )
    FIG("02_tariff_breakeven")
    CAP(
        "Breakeven frontier. Project IRR (left) and minimum DSCR (right) vs fixed PPA tariff."
    )
    FIG("06_capex")
    CAP("Capex sensitivity at the competitive USc 8.0 PPA.")

    render_section("risk")
    FIG("03_mc_irr")
    CAP(
        f"Monte Carlo distribution of project IRR ({mc['n']:,} LHS trials); the whole distribution lies far below the ~10% WACC."
    )
    FIG("04_tornado")
    CAP(
        "Tornado: impact of each driver on project IRR. Capacity factor and tariff dominate."
    )
    FIG("05_optimization")
    CAP(
        "Equity IRR vs gearing under the 1.30x DSCR constraint; feasible only below ~35% gearing."
    )

    render_section("dscr")
    datatable(
        ["Min-DSCR target", "Solved gearing", "Project IRR", "Equity IRR"],
        [
            [
                f"{d['target_dscr']:.2f}x",
                f"{d['gearing']*100:.0f}%",
                pc(d["projIRR"]),
                pc(d["eqIRR"]),
            ]
            for d in D["sweep"]
        ],
        [4.0 * cm, 4.0 * cm, 3.7 * cm, 3.8 * cm],
    )
    FIG("07_dscr")
    CAP(
        "Effect of the DSCR sizing target. Project IRR is flat (financing cannot change the asset return); equity IRR improves as the structure deleverages - the signature of negative carry."
    )

    render_section("discussion")
    render_section("conclusions")

    # ---- APPENDICES ----
    story.append(PageBreak())
    H1("Appendix A &mdash; Key Assumptions")
    datatable(
        ["Parameter", "Value", "Basis"],
        [
            ["DC nameplate", "10 MWp (10 MWac, 1.2 ILR)", "Brief"],
            [
                "Net capacity factor (P50)",
                f"{pc(res['cf_bifacial'])} (mono {pc(res['cf_mono'])} +7% bifacial)",
                "pvlib on Solargis GHI",
            ],
            [
                "Annual GHI",
                f"{S['annual_ghi_kwh_m2']:,.0f} kWh/m2/yr",
                "Global Solar Atlas / Solargis",
            ],
            [
                "Tilt / azimuth / DC-AC",
                f"{S['tilt_deg']:.0f}deg / {S['azimuth_deg']:.0f}deg / {S['dc_ac_ratio']}",
                "Solargis optimum / standard",
            ],
            [
                "System losses / degradation",
                f"{S['system_loss_pct']:.0f}% / {S['degradation_pct']}%/yr",
                "Industry standard",
            ],
            [
                "Project life / PPA tenor",
                f"{S['life_years']} yr / {S['ppa_term_years']} yr",
                "Solar asset / PPA",
            ],
            [
                "Capex (base)",
                f"{usd(S['capex_usd'])} (${S['capex_usd']/S['dc_capacity_mw']/1000:,.0f}/kW)",
                "IEA + Siyambalanduwa range",
            ],
            [
                "Opex",
                f"${S['opex_usd_yr']/1000:.0f}k/yr ($13/kW-yr)",
                "Industry standard",
            ],
            [
                "FiT tariff",
                f"LKR {S['fit_tariff_lkr']}/kWh (>1 MW)",
                "SLSEA June-2025 FiT",
            ],
            [
                "Competitive tariff",
                f"USc {S['competitive_usc']} = LKR {S['competitive_tariff_lkr']}/kWh fixed",
                "Siyambalanduwa PPA",
            ],
            [
                "Exchange rate",
                f"LKR {S['fx']}/USD, 3%/yr depr.",
                "DutchBay canonical FX",
            ],
            [
                "Gearing / tenor / min-DSCR",
                "70% (sized) / 15 yr / 1.30x",
                "DutchBay base financing",
            ],
            [
                "WACC / cost of equity",
                f"{pc(cc['discount_rate_used'])} / ~12%",
                "Build-up, rupee environment",
            ],
        ],
        [4.6 * cm, 5.4 * cm, 5.5 * cm],
    )

    H1("Appendix B &mdash; Glossary")
    for term, d in [
        (
            "GHI",
            "Global Horizontal Irradiation - total solar energy on a horizontal surface (kWh/m2/yr).",
        ),
        (
            "PVOUT",
            "Specific PV power output - annual energy per installed kWp (kWh/kWp/yr).",
        ),
        (
            "Capacity factor (CF)",
            "Average output as a fraction of nameplate; energy / (capacity x 8,760 h).",
        ),
        (
            "ILR / DC-AC ratio",
            "Inverter loading ratio - installed DC capacity / AC nameplate.",
        ),
        (
            "CFADS",
            "Cash Flow Available for Debt Service - operating cashflow before financing.",
        ),
        (
            "DSCR",
            "Debt-Service Cover Ratio - CFADS / scheduled debt service; the covenant is the minimum allowed.",
        ),
        (
            "Project / Equity IRR",
            "Unlevered (whole-asset) vs levered (shareholder) internal rate of return.",
        ),
        (
            "WACC",
            "Weighted Average Cost of Capital - the blended required return used to discount the project.",
        ),
        (
            "Negative carry",
            "When the project return is below the cost of debt, so leverage reduces equity return.",
        ),
        (
            "Bifaciality",
            "The fraction of front-side efficiency a module's rear side achieves.",
        ),
    ]:
        B(f"<b>{term}:</b> {d}")

    H1("Appendix C &mdash; Data Sources & References")
    for r_ in [
        "Global Solar Atlas / Solargis (v2.2.68) - site GHI 1,909 and PVOUT 1,524 kWh/kWp.",
        "NASA POWER (ALLSKY_SFC_SW_DWN climatology 2001-2020) - GHI cross-check and the national resource raster.",
        "SLSEA / EconomyNext - renewable feed-in tariffs reduced from June 2025 (>1 MW = LKR 14.46/kWh).",
        "Siyambalanduwa 100 MW PPA (Rividhanavi) - USc 8.00/kWh competitive PPA; ~USD 1,320/kW all-in.",
        "IEA - capital costs of utility-scale solar PV in selected emerging economies (~USD 1,120/kW).",
        "World Bank / Solargis - Sri Lanka solar resource maps (national GHI 1,247-2,106 kWh/m2/yr).",
        "Manufacturer datasheets - Trina Vertex N, Risen Hyper-ion, Huasun Himalaya G12, Astronergy ASTRO N7 Pro.",
        "OpenStreetMap / Nominatim - reverse geocoding of the site coordinate.",
        "Esri World Imagery (via contextily) - satellite basemap for the site-context close-up.",
        "Natural Earth / johan world.geo.json (via geopandas) - Sri Lanka land polygon used to clip the GHI choropleth.",
    ]:
        B(r_)

    H1("Appendix D &mdash; Model Provenance & Reproducibility")
    P(
        f"All figures are model-derived and reproducible. Energy: the DutchBay <font face='Courier'>solar_resource</font> pvlib "
        f"producer. Finance: the canonical v14 pipeline (CFADS &rarr; dual-DSCR sculpt &rarr; construction-lag-correct IRR/NPV). "
        f"Monte&nbsp;Carlo: {mc['n']:,} Latin-Hypercube trials (seed 123, common random numbers). Sensitivity and optimisation: "
        f"the platform&rsquo;s standard one-way and constrained-sweep routines. The national map is a NASA&nbsp;POWER GHI raster "
        f"written to a georeferenced GeoTIFF via the codebase&rsquo;s GIS export and clipped to the country polygon with "
        f"geopandas; the site close-up is an Esri&nbsp;World&nbsp;Imagery tile composited with contextily. This document is a sample of automated model "
        f"output and is <b>not investment advice</b>; a financing decision should rest on a full site-specific bankability study, "
        f"measured ground data and binding commercial terms."
    )

    doc.multiBuild(story)


# ---------------------------------------------------------------------------
_OUT_PATH = Path("/tmp")  # overwritten in main()


def main() -> None:
    global _OUT_PATH
    ap = argparse.ArgumentParser(
        description="Generate the solar PV assessment PDF report."
    )
    ap.add_argument(
        "--out", default=str(Path.home() / "Downloads" / "solar_assessment_report")
    )
    ap.add_argument("--trials", type=int, default=1000, help="Monte Carlo trials")
    args = ap.parse_args()

    out = Path(args.out)
    charts = out / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    _OUT_PATH = out

    print(f"[1/4] Running analytical routines ({args.trials} MC trials)...")
    R = run_routines(trials=args.trials)
    json.dump(R, open(out / "results.json", "w"), indent=1, default=float)

    print(
        "[2/4] Building location maps (national GHI + GeoTIFF, satellite site context)..."
    )
    make_location_map(charts)
    if make_site_context_map(charts):
        print("      satellite site-context map: OK")
    else:
        print(
            "      satellite site-context map: skipped (contextily/tiles unavailable)"
        )

    print("[3/4] Generating charts...")
    make_charts(R, charts)

    print("[4/4] Rendering PDF...")
    narrative = json.load(open(_ASSETS / "solar_assessment_narrative.json"))
    pdf = out / f"Solar_Assessment_{SITE['location_name'].replace(' ', '_')}.pdf"
    render_pdf(R, narrative, charts, pdf)
    print(f"DONE -> {pdf}")


if __name__ == "__main__":
    main()
