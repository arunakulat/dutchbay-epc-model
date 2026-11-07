#!/usr/bin/env python3
"""Hydra CLI: Blue Whale single-turbine yield, coastal placement, setbacks, shadow flicker.

Reads ``conf/blue_whale_wind_siting.yaml`` and prints one JSON object of derived results
(CLI-01, CLI-03). The power curve is confidential: it is read from a path outside the
repository, de-rated by clipping, integrated, and discarded. No curve value, no derived
curve and no hash of the file is written or printed.

The yield reuses the repository's wind maths rather than adding any:
:func:`analytics.wind.aep_tornado.gross_aep_farm_gwh` integrates the curve over the
Weibull, :func:`wind_resource.bankable_aep.density_velocity_factor` corrects it to site
air density, :func:`analytics.wind.losses_model.apply_losses` applies the loss stack, and
:func:`wind_resource.bankable_aep.gross_aep_weibull`, an independently written integrator,
checks the gross figure (TEST-01).

Usage::

    BLUE_WHALE_POWER_CURVE_CSV=/outside/the/repo/curve.csv \\
        .venv/bin/python scripts/run_blue_whale_wind_siting_v14.py
"""

from __future__ import annotations

import csv
import json
import logging
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import hydra
import numpy as np
import yaml
from omegaconf import DictConfig, OmegaConf

from analytics.gis.shadow_flicker import (
    CoastalSetbackConfig,
    LocalFrame,
    ShadowFlickerConfig,
    TipSetbackConfig,
    TurbineGeometry,
    coast_aligned_square_lot,
    coastline_lines_east_north,
    flicker_grid,
    grid_summary,
    place_at_coastal_setback,
    receptor_as_dict,
    receptor_flicker,
    site_feature_collection,
    solar_path,
    sunny_steps,
    tip_height_setback,
)
from analytics.wind.aep_tornado import gross_aep_farm_gwh
from analytics.wind.losses_model import HOURS_PER_YEAR, apply_losses
from wind_resource.bankable_aep import density_velocity_factor, gross_aep_weibull

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Private power curve
# ---------------------------------------------------------------------------
def load_private_power_curve(
    path: Optional[str], *, repo_root: Path = REPO_ROOT
) -> Tuple[np.ndarray, np.ndarray]:
    """Read a power curve CSV from outside the repository.

    The file may carry ``#`` comment lines and must have ``wind_speed_ms`` and
    ``power_kw`` columns. Any other column is ignored and never read into memory.

    Args:
        path: Path to the CSV, or ``None``.
        repo_root: Repository root; a path inside it is refused so that a copy of a
            confidential curve cannot be staged by accident.

    Returns:
        Wind speeds (m/s) and powers (kW).

    Raises:
        ValueError: If no path is given, the path lies inside the repository, or the
            curve is malformed.
        FileNotFoundError: If the file does not exist.
    """
    if not path:
        raise ValueError(
            "No power curve: set BLUE_WHALE_POWER_CURVE_CSV or pass "
            "turbine.power_curve_csv=<path outside the repository>."
        )
    resolved = Path(path).expanduser().resolve()
    if resolved.is_relative_to(repo_root.resolve()):
        raise ValueError(
            "The power curve must be read from outside the repository; refusing a path "
            "inside it."
        )
    if not resolved.is_file():
        raise FileNotFoundError(f"power curve not found: {resolved}")
    ws: list[float] = []
    pw: list[float] = []
    with resolved.open(newline="") as fh:
        rows = csv.DictReader(line for line in fh if not line.lstrip().startswith("#"))
        fieldnames = rows.fieldnames or []
        if "wind_speed_ms" not in fieldnames or "power_kw" not in fieldnames:
            raise ValueError("power curve needs wind_speed_ms and power_kw columns")
        for row in rows:
            ws.append(float(row["wind_speed_ms"]))
            pw.append(float(row["power_kw"]))
    w = np.asarray(ws, dtype=np.float64)
    p = np.asarray(pw, dtype=np.float64)
    if len(w) < 2 or np.any(np.diff(w) <= 0) or np.any(p < 0) or not np.any(p > 0):
        raise ValueError(
            "power curve must have >= 2 rows, strictly increasing wind speed, "
            "non-negative power and some positive power"
        )
    return w, p


def derate_by_clipping(power_kw: np.ndarray, derated_power_kw: float) -> np.ndarray:
    """Clip a power curve at the de-rated power.

    Args:
        power_kw: Power at each wind speed.
        derated_power_kw: Ceiling.

    Returns:
        ``min(power, ceiling)`` element-wise.
    """
    if derated_power_kw <= 0:
        raise ValueError("derated_power_kw must be positive")
    clipped: np.ndarray = np.asarray(
        np.minimum(power_kw, derated_power_kw), dtype=np.float64
    )
    return clipped


def weibull_scale_at_height(
    scale_ref_ms: float, ref_height_m: float, hub_height_m: float, shear_exponent: float
) -> float:
    """Move a Weibull scale to another height with the power-law shear profile.

    The shape parameter is held constant, the usual simplification for a modest change
    of height.

    Args:
        scale_ref_ms: Weibull A at the reference height.
        ref_height_m: Reference height.
        hub_height_m: Target height.
        shear_exponent: Power-law exponent.

    Returns:
        Weibull A at the target height.
    """
    if ref_height_m <= 0 or hub_height_m <= 0:
        raise ValueError("heights must be positive")
    return float(scale_ref_ms * (hub_height_m / ref_height_m) ** shear_exponent)


def operating_probability(
    wind_speed_ms: np.ndarray,
    power_kw: np.ndarray,
    weibull_a: float,
    weibull_k: float,
    density_factor: float,
) -> float:
    """Probability that hub-height wind lies in the curve's producing range.

    The range runs from the lowest wind speed with positive power to the last tabulated
    speed, both moved to site density the same way the yield is.

    Args:
        wind_speed_ms: Curve wind speeds.
        power_kw: Curve powers.
        weibull_a: Hub-height Weibull A.
        weibull_k: Weibull k.
        density_factor: IEC 61400-12-1 velocity factor.

    Returns:
        ``P(cut_in <= v <= cut_out)`` under the Weibull.
    """
    producing = wind_speed_ms[power_kw > 0]
    lo = float(producing.min()) / density_factor
    hi = float(wind_speed_ms.max()) / density_factor

    def cdf(v: float) -> float:
        return 1.0 - math.exp(-((v / weibull_a) ** weibull_k))

    return cdf(hi) - cdf(lo)


def single_turbine_yield(
    wind_speed_ms: np.ndarray,
    power_kw: np.ndarray,
    *,
    derated_power_kw: float,
    weibull_a_hub: float,
    weibull_k: float,
    rho_site_kgm3: float,
    rho_curve_kgm3: float,
    losses: Mapping[str, Any],
    integrator_tolerance_pct: float,
) -> Dict[str, Any]:
    """Gross and net yield of one de-rated turbine, with the integrator cross-check.

    Args:
        wind_speed_ms: Curve wind speeds.
        power_kw: Curve powers (before de-rating).
        derated_power_kw: De-rated rating; also the capacity-factor denominator.
        weibull_a_hub: Weibull A at hub height.
        weibull_k: Weibull k.
        rho_site_kgm3: Site air density.
        rho_curve_kgm3: Air density the curve is stated at.
        losses: Loss stack for :func:`analytics.wind.losses_model.apply_losses`.
        integrator_tolerance_pct: Largest allowed gap between the two integrators.

    Returns:
        Derived scalars only.

    Raises:
        ValueError: If the two integrators disagree by more than the tolerance.
    """
    clipped = derate_by_clipping(power_kw, derated_power_kw)
    factor = density_velocity_factor(rho_site_kgm3, rho_curve_kgm3)
    gross = gross_aep_farm_gwh(
        weibull_a_hub, weibull_k, wind_speed_ms / factor, clipped, 1
    )
    oracle = gross_aep_weibull(
        wind_speed_ms=[float(v) for v in wind_speed_ms],
        power_kw=[float(p) for p in clipped],
        weibull_a=weibull_a_hub,
        weibull_k=weibull_k,
        rated_power_kw=derated_power_kw,
        n_turbines=1,
        cut_in_ms=0.0,
        cut_out_ms=float(wind_speed_ms.max()) / factor,
        rho_site_kgm3=rho_site_kgm3,
        rho_ref_kgm3=rho_curve_kgm3,
    ).aep_gwh_farm
    gap_pct = 100.0 * abs(gross - oracle) / oracle
    if gap_pct > integrator_tolerance_pct:
        raise ValueError(
            f"gross AEP integrators disagree by {gap_pct:.4f}% "
            f"(> {integrator_tolerance_pct}%)"
        )
    net = apply_losses(gross, losses)
    capacity_mw = derated_power_kw / 1000.0
    return {
        "gross_aep_gwh": gross,
        "net_aep_gwh": net.net_aep_gwh,
        "gross_capacity_factor": gross * 1000.0 / (capacity_mw * HOURS_PER_YEAR),
        "net_capacity_factor": net.net_aep_gwh
        * 1000.0
        / (capacity_mw * HOURS_PER_YEAR),
        "total_loss_pct": net.total_loss_pct,
        "loss_retention_by_line": dict(net.components),
        "density_velocity_factor": factor,
        "integrator_gap_pct": gap_pct,
    }


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------
def _repo_path(rel: str) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else REPO_ROOT / path


def _json_matches(expected: Any, actual: Any, *, abs_tol: float = 1e-9) -> bool:
    """Compare two parsed JSON trees with a tight absolute tolerance on floats."""
    if type(expected) is not type(actual):
        if (
            isinstance(expected, (int, float))
            and not isinstance(expected, bool)
            and isinstance(actual, (int, float))
            and not isinstance(actual, bool)
        ):
            return math.isclose(
                float(expected), float(actual), rel_tol=0.0, abs_tol=abs_tol
            )
        return False
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return False
        return all(
            _json_matches(expected[k], actual[k], abs_tol=abs_tol) for k in expected
        )
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return False
        return all(
            _json_matches(e, a, abs_tol=abs_tol)
            for e, a in zip(expected, actual, strict=True)
        )
    if isinstance(expected, float):
        return math.isclose(expected, actual, rel_tol=0.0, abs_tol=abs_tol)
    return bool(expected == actual)


def resource_basis(resource_cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Read the wind basis and loss stack from the source scenario.

    Args:
        resource_cfg: The ``resource`` block of the CLI config.

    Returns:
        Weibull A and k, their reference height, shear exponent, site density, and the
        loss stack with the configured overrides applied.
    """
    scenario_path = str(resource_cfg["source_scenario"])
    scen = yaml.safe_load(_repo_path(scenario_path).read_text())
    wind = scen["wind_resource"]
    losses = dict(scen["resource"]["losses"])
    losses.update(dict(resource_cfg["loss_overrides"]))
    return {
        "source_scenario": scenario_path,
        "weibull_a_ref_ms": float(wind["weibull_a"]),
        "weibull_k": float(wind["weibull_k"]),
        "reference_height_m": float(scen["resource"]["era5"]["hub_height_m"]),
        "shear_exponent": float(wind["shear_exponent"]),
        "air_density_site_kgm3": float(wind["air_density_kgm3"]),
        "losses": losses,
    }


def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Run the whole screen from a resolved config mapping.

    Args:
        cfg: The resolved CLI config.

    Returns:
        The JSON-serialisable summary.
    """
    site = cfg["site"]
    tcfg = cfg["turbine"]
    turbine = TurbineGeometry(
        hub_height_m=float(tcfg["hub_height_m"]),
        rotor_diameter_m=float(tcfg["rotor_diameter_m"]),
    )
    derated_kw = float(tcfg["derated_power_kw"])
    basis = resource_basis(cfg["resource"])

    # Yield
    ws, pw = load_private_power_curve(tcfg["power_curve_csv"])
    a_hub = weibull_scale_at_height(
        basis["weibull_a_ref_ms"],
        basis["reference_height_m"],
        turbine.hub_height_m,
        basis["shear_exponent"],
    )
    yield_ = single_turbine_yield(
        ws,
        pw,
        derated_power_kw=derated_kw,
        weibull_a_hub=a_hub,
        weibull_k=basis["weibull_k"],
        rho_site_kgm3=basis["air_density_site_kgm3"],
        rho_curve_kgm3=float(tcfg["power_curve_air_density_kgm3"]),
        losses=basis["losses"],
        integrator_tolerance_pct=float(cfg["resource"]["integrator_tolerance_pct"]),
    )
    p_operating = operating_probability(
        ws, pw, a_hub, basis["weibull_k"], yield_["density_velocity_factor"]
    )
    del ws, pw  # the curve goes no further

    # Placement and lot
    frame = LocalFrame(
        float(site["reference_lat_deg"]), float(site["reference_lon_deg"])
    )
    coast_doc = json.loads(_repo_path(str(site["coastline_geojson"])).read_text())
    lines = coastline_lines_east_north(coast_doc, frame)
    coastal = CoastalSetbackConfig.from_mapping(cfg["coastal_setback"])
    placement = place_at_coastal_setback(
        lines,
        north_m=0.0,
        min_distance_m=coastal.tower_distance_from_coastline_m,
        search_east_m=float(site["placement_search_east_m"]),
    )
    lot = coast_aligned_square_lot(
        lines,
        north_m=0.0,
        area_m2=float(site["lot_area_m2"]),
        sample_step_m=float(site["coastline_sample_step_m"]),
    )
    tower = (placement.turbine_east_m, placement.turbine_north_m)
    tip = tip_height_setback(
        lot, tower, turbine, TipSetbackConfig.from_mapping(cfg["tip_setback"])
    )
    lon_t, lat_t = frame.to_lon_lat(*tower)

    site_doc = site_feature_collection(
        frame=frame,
        lot=lot,
        placement=placement,
        properties={
            "name": "Blue Whale Lot 5B (PLACEHOLDER, NOT SURVEYED)",
            "surveyed": False,
            "placeholder": True,
            "input_owed": "B03 (site survey with WGS84 coordinates)",
            "area_m2": float(site["lot_area_m2"]),
            "side_m": lot.side_m,
            "west_edge_bearing_deg": lot.edge_bearing_deg,
            "derivation": (
                "Square of the deeded area (9.3077 ha). Its west edge is the "
                "total-least-squares line through the OpenStreetMap coastline within half "
                "a side of the point where the coastline crosses DutchBay T2's latitude "
                "(8.292500 N); the edge is centred on that point and the lot extends "
                "landward. Generated by scripts/run_blue_whale_wind_siting_v14.py from "
                "conf/blue_whale_wind_siting.yaml."
            ),
            "every_result_depends_on_this_placeholder": True,
        },
        turbine_properties={
            "name": "Blue Whale turbine (PLACEHOLDER POSITION)",
            "placeholder": True,
            "derivation": (
                "Westernmost point on T2's latitude at least "
                f"{coastal.tower_distance_from_coastline_m:g} m from the OpenStreetMap "
                "coastline (CZ&CRMP 2024-2029 segment 2 setback, measured from the "
                "coastline as a bound because the vegetation line is not mapped)."
            ),
        },
        decimals=int(site["geojson_decimals"]),
    )
    committed = _repo_path(str(site["site_geojson"]))
    matches = committed.is_file() and _json_matches(
        json.loads(committed.read_text()), site_doc
    )

    # Shadow flicker
    fcfg = ShadowFlickerConfig.from_mapping(cfg["shadow_flicker"])
    sun = solar_path(lat_t, lon_t, fcfg)
    sunny = (
        sunny_steps(
            sun, str(_repo_path(fcfg.sunshine_tmy_csv)), fcfg.sunshine_dni_threshold_wm2
        )
        if fcfg.sunshine_tmy_csv
        else None
    )
    p_op = p_operating if sunny is not None else None
    receptors = [
        receptor_as_dict(
            receptor_flicker(
                name,
                pt,
                tower_en=tower,
                turbine=turbine,
                cfg=fcfg,
                sun=sun,
                sunny=sunny,
                operating_probability=p_op,
            )
        )
        for name, pt in lot.receptors().items()
    ]
    grid = flicker_grid(
        tower_en=tower,
        turbine=turbine,
        cfg=fcfg,
        sun=sun,
        sunny=sunny,
        operating_probability=p_op,
    )

    out_cfg = cfg["output"]
    if out_cfg.get("site_geojson"):
        path = _repo_path(str(out_cfg["site_geojson"]))
        path.write_text(json.dumps(site_doc, indent=2) + "\n")
    if out_cfg.get("flicker_grid_csv"):
        _write_grid_csv(_repo_path(str(out_cfg["flicker_grid_csv"])), grid)

    version = (REPO_ROOT / "VERSION").read_text().strip()
    return {
        "model_version": version,
        "config": "conf/blue_whale_wind_siting.yaml",
        "placeholder_site": True,
        "caveat": (
            "Every figure depends on a placeholder lot (assumed square) and an "
            "OpenStreetMap coastline; no survey exists (input B03)."
        ),
        "turbine": {
            "model": str(tcfg["model"]),
            "derated_power_mw": derated_kw / 1000.0,
            "derate_rule": "power curve clipped at the de-rated power (assumption)",
            "hub_height_m": turbine.hub_height_m,
            "rotor_diameter_m": turbine.rotor_diameter_m,
            "tip_height_m": turbine.tip_height_m,
            "lat_deg": lat_t,
            "lon_deg": lon_t,
            "east_of_reference_m": tower[0],
            "north_of_reference_m": tower[1],
        },
        "resource": {
            "source_scenario": basis["source_scenario"],
            "weibull_a_ref_ms": basis["weibull_a_ref_ms"],
            "reference_height_m": basis["reference_height_m"],
            "shear_exponent": basis["shear_exponent"],
            "weibull_a_hub_ms": a_hub,
            "weibull_k": basis["weibull_k"],
            "air_density_site_kgm3": basis["air_density_site_kgm3"],
            "air_density_curve_kgm3": float(tcfg["power_curve_air_density_kgm3"]),
            "losses": basis["losses"],
            "operating_probability": p_operating,
        },
        "yield": yield_,
        "coastal_placement": {
            "setback": {
                "reservation_m": coastal.reservation_m,
                "restricted_m": coastal.restricted_m,
                "seaward_reference_offset_m": coastal.seaward_reference_offset_m,
                "foundation_clearance_m": coastal.foundation_clearance_m,
                "source": coastal.source,
            },
            "coastline_crossing_east_of_reference_m": placement.coastline_crossing_east_m,
            "tower_distance_to_coastline_m": placement.distance_to_coastline_m,
            "tower_distance_to_setback_line_m": placement.distance_to_coastline_m
            - coastal.seaward_reference_offset_m
            - coastal.total_setback_m,
            "rotor_reach_seaward_of_coastline_m": max(
                turbine.rotor_radius_m - placement.distance_to_coastline_m, 0.0
            ),
            "rotor_reach_seaward_of_setback_line_m": max(
                turbine.rotor_radius_m
                - (
                    placement.distance_to_coastline_m
                    - coastal.seaward_reference_offset_m
                    - coastal.total_setback_m
                ),
                0.0,
            ),
        },
        "lot": {
            "area_m2": float(site["lot_area_m2"]),
            "side_m": lot.side_m,
            "west_edge_bearing_deg": lot.edge_bearing_deg,
            "west_edge_max_deviation_from_coastline_m": lot.edge_max_deviation_m,
            "site_geojson_matches_committed": matches,
        },
        "tip_setback": {
            "multiple": float(cfg["tip_setback"]["tip_height_multiple"]),
            "source": str(cfg["tip_setback"]["source"]),
            **asdict(tip),
        },
        "shadow_flicker": {
            "receptors": receptors,
            "grid": grid_summary(grid, fcfg),
            "sun_steps_above_floor": int(sun.elevation_deg.size),
        },
    }


def _write_grid_csv(path: Path, grid: list[Any]) -> None:
    """Write the flicker grid as CSV (east/north offsets from the tower)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        fh.write(
            "# Blue Whale shadow-flicker grid. PLACEHOLDER SITE: offsets are metres from "
            "the placeholder turbine position. Generated by "
            "scripts/run_blue_whale_wind_siting_v14.py (conf/blue_whale_wind_siting.yaml).\n"
        )
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(
            [
                "east_m",
                "north_m",
                "worst_case_hours_per_year",
                "worst_case_max_minutes_per_day",
                "expected_hours_per_year",
            ]
        )
        for g in grid:
            writer.writerow(
                [
                    f"{g.east_m:.0f}",
                    f"{g.north_m:.0f}",
                    f"{g.worst_case_hours_per_year:.2f}",
                    f"{g.worst_case_max_minutes_per_day:.0f}",
                    (
                        ""
                        if g.expected_hours_per_year is None
                        else f"{g.expected_hours_per_year:.2f}"
                    ),
                ]
            )


@hydra.main(
    version_base="1.3", config_path="../conf", config_name="blue_whale_wind_siting"
)
def main(cfg: DictConfig) -> None:
    """Run the screen and print one JSON object.

    Args:
        cfg: Hydra-composed config.

    Raises:
        TypeError: If the config does not resolve to a mapping.
    """
    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    print(json.dumps(run(raw), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
