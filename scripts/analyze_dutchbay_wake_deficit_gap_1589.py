#!/usr/bin/env python3
"""Hydra CLI: audit and decompose the DutchBay PyWake wake deficit gap (#1589).

Reads ``conf/dutchbay_wake_14_turbines.yaml`` and emits a structured JSON report
explaining the ~12 pp gap between the bankable frozen wake calibration (7.28% / 7.32%)
and live PyWake aerodynamic simulation (19.33% / 19.44%) on the recorded layout.

Usage::

    .venv/bin/python scripts/analyze_dutchbay_wake_deficit_gap_1589.py
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, List, Mapping, Sequence

import hydra
import numpy as np
from omegaconf import DictConfig, OmegaConf

from analytics.gis.shadow_flicker import LocalFrame
from analytics.power_curves.oem_parser import (
    IEC_REFERENCE_AIR_DENSITY_KGM3,
    parse_power_curve,
)
from wind_resource.bankable_aep import (
    UncertaintyBudget,
    exceedance_levels,
    gaussian_k_star,
    model_wake_loss,
)

_ROLES = ("dutchbay", "external_waker")


def project_layout(
    turbines: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Project the WGS84 turbine list to local metres about its centroid.

    Args:
        turbines: Entries with ``id``, ``lat_deg``, ``lon_deg`` and ``role``.

    Returns:
        ``ids``, ``x_m``, ``y_m`` and ``roles`` lists in input order, and the frame origin.

    Raises:
        ValueError: On an unknown role or a repeated id.
    """
    ids = [str(t["id"]) for t in turbines]
    if len(set(ids)) != len(ids):
        raise ValueError(f"turbine ids repeat: {ids}")
    roles = [str(t["role"]) for t in turbines]
    for tid, role in zip(ids, roles, strict=True):
        if role not in _ROLES:
            raise ValueError(f"turbine {tid}: role {role!r} is not one of {_ROLES}")
    lats = [float(t["lat_deg"]) for t in turbines]
    lons = [float(t["lon_deg"]) for t in turbines]
    frame = LocalFrame(
        origin_lat_deg=float(np.mean(lats)), origin_lon_deg=float(np.mean(lons))
    )
    xy = [frame.to_east_north(lon, lat) for lat, lon in zip(lats, lons, strict=True)]
    return {
        "ids": ids,
        "roles": roles,
        "x_m": [p[0] for p in xy],
        "y_m": [p[1] for p in xy],
        "origin_lat_deg": frame.origin_lat_deg,
        "origin_lon_deg": frame.origin_lon_deg,
    }


def compute_gap_analysis(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Execute the factorial wake deficit decomposition across layout, rose, and proxy.

    Args:
        cfg: Resolved Hydra dictionary containing the ``wake_rebaseline`` block.

    Returns:
        JSON-serialisable dictionary detailing pairwise spacing, factorial decomposition,
        rotor size sensitivities, and bankable P50/P90 impacts.
    """
    block = cfg["wake_rebaseline"]
    turbine = block["turbine"]
    resource = block["resource"]
    d_ref = float(turbine["rotor_diameter_m"])
    hub_m = float(turbine["hub_height_m"])
    frozen_15 = float(block["frozen_wake_15_pct"])

    c = parse_power_curve(
        str(turbine["curve_key"]), air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    ws = [float(v) for v in c["wind_speed_ms"]]
    pw = [float(v) for v in c["power_kw"]]
    ct = [float(v) for v in c["thrust_coefficient"]]

    rose = [float(v) for v in resource["wind_rose_freq"]]
    a = float(resource["weibull_a"])
    k = float(resource["weibull_k"])
    ti = float(resource["turbulence_intensity"])

    # 1. Project real layout
    layout = project_layout(block["layout"]["turbines"])
    x_real = layout["x_m"]
    y_real = layout["y_m"]
    ids = layout["ids"]
    roles = layout["roles"]
    n_turbines = len(ids)

    # Calculate nearest-neighbor distances and bearings
    pairwise_spacing: List[Dict[str, Any]] = []
    for i in range(n_turbines):
        dists: List[tuple[float, float, str]] = []
        for j in range(n_turbines):
            if i == j:
                continue
            dx = x_real[j] - x_real[i]
            dy = y_real[j] - y_real[i]
            dist = math.hypot(dx, dy)
            bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
            dists.append((dist, bearing, ids[j]))
        dists.sort()
        nearest = dists[0]
        pairwise_spacing.append(
            {
                "id": ids[i],
                "role": roles[i],
                "nearest_neighbor_id": nearest[2],
                "distance_m": round(nearest[0], 2),
                "distance_diameters": round(nearest[0] / d_ref, 2),
                "bearing_deg": round(nearest[1], 1),
            }
        )

    # 2. Base runs (15 turbines)
    res_real_sw = model_wake_loss(
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=d_ref,
        hub_height_m=hub_m,
        layout_x_m=x_real,
        layout_y_m=y_real,
        weibull_a=a,
        weibull_k=k,
        wind_rose_freq=rose,
        turbulence_intensity=ti,
        deficit_model="bastankhah",
    )

    res_real_omni = model_wake_loss(
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=d_ref,
        hub_height_m=hub_m,
        layout_x_m=x_real,
        layout_y_m=y_real,
        weibull_a=a,
        weibull_k=k,
        wind_rose_freq=None,
        turbulence_intensity=ti,
        deficit_model="bastankhah",
    )

    # Synthetic row layout (650m N-S spacing)
    row_x = [0.0] * n_turbines
    row_y = [650.0 * (n_turbines - 1 - i) for i in range(n_turbines)]
    res_row_sw = model_wake_loss(
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=d_ref,
        hub_height_m=hub_m,
        layout_x_m=row_x,
        layout_y_m=row_y,
        weibull_a=a,
        weibull_k=k,
        wind_rose_freq=rose,
        turbulence_intensity=ti,
        deficit_model="bastankhah",
    )

    res_row_omni = model_wake_loss(
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=d_ref,
        hub_height_m=hub_m,
        layout_x_m=row_x,
        layout_y_m=row_y,
        weibull_a=a,
        weibull_k=k,
        wind_rose_freq=None,
        turbulence_intensity=ti,
        deficit_model="bastankhah",
    )

    # 3. Rotor diameter proxy sensitivity
    rotor_sensitivities: Dict[str, float] = {}
    for d_test in (120.0, 140.0, 160.0, 180.0, 198.0):
        r = model_wake_loss(
            wind_speed_ms=ws,
            power_kw=pw,
            thrust_coefficient=ct,
            rotor_diameter_m=d_test,
            hub_height_m=hub_m,
            layout_x_m=x_real,
            layout_y_m=y_real,
            weibull_a=a,
            weibull_k=k,
            wind_rose_freq=rose,
            turbulence_intensity=ti,
            deficit_model="bastankhah",
        )
        rotor_sensitivities[f"rotor_{int(d_test)}m_pct"] = round(r.wake_loss_pct, 2)

    # 4. Turbulence intensity sensitivity
    ti_sensitivities: Dict[str, float] = {}
    for ti_val in (0.06, 0.08, 0.10, 0.12, 0.14):
        r = model_wake_loss(
            wind_speed_ms=ws,
            power_kw=pw,
            thrust_coefficient=ct,
            rotor_diameter_m=d_ref,
            hub_height_m=hub_m,
            layout_x_m=x_real,
            layout_y_m=y_real,
            weibull_a=a,
            weibull_k=k,
            wind_rose_freq=rose,
            turbulence_intensity=ti_val,
            deficit_model="bastankhah",
        )
        ti_sensitivities[f"ti_{ti_val:.2f}_kstar_{gaussian_k_star(ti_val):.4f}"] = (
            round(r.wake_loss_pct, 2)
        )

    # 5. 14-turbines case (T2 waking)
    counted_14 = [r != "external_waker" for r in roles]
    res_14 = model_wake_loss(
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=d_ref,
        hub_height_m=hub_m,
        layout_x_m=x_real,
        layout_y_m=y_real,
        weibull_a=a,
        weibull_k=k,
        wind_rose_freq=rose,
        turbulence_intensity=ti,
        deficit_model="bastankhah",
        counted=counted_14,
    )

    # 6. Bankable P50/P90 sensitivity
    non_wake_ret = 0.97 * 0.98 * 0.98 * 0.99
    gross_14_gwh = res_14.aep_gross_gwh
    budget = UncertaintyBudget()

    # Case A: Frozen calibration (7.32%)
    p50_frozen = gross_14_gwh * (1.0 - 0.0732) * non_wake_ret
    exc_frozen = exceedance_levels(p50_frozen, budget)

    # Case B: Live PyWake (19.44%)
    p50_live = gross_14_gwh * (1.0 - (res_14.wake_loss_pct / 100.0)) * non_wake_ret
    exc_live = exceedance_levels(p50_live, budget)

    return {
        "work_item": "#1589",
        "frozen_wake_15_pct": frozen_15,
        "live_wake_15_pct": round(res_real_sw.wake_loss_pct, 2),
        "live_wake_14_pct": round(res_14.wake_loss_pct, 2),
        "gap_attribution": {
            "layout_geometry_pp": round(
                res_real_omni.wake_loss_pct - res_row_omni.wake_loss_pct, 2
            ),
            "wind_rose_directional_penalty_pp": round(
                res_real_sw.wake_loss_pct - res_real_omni.wake_loss_pct, 2
            ),
            "synthetic_row_wake_pct": round(res_row_sw.wake_loss_pct, 2),
            "real_layout_wake_pct": round(res_real_sw.wake_loss_pct, 2),
        },
        "pairwise_spacing": pairwise_spacing,
        "rotor_diameter_sensitivities_pct": rotor_sensitivities,
        "turbulence_intensity_sensitivities_pct": ti_sensitivities,
        "bankable_sensitivity": {
            "frozen_7_32_pct": {
                "wake_loss_pct": 7.32,
                "p50_net_gwh": round(exc_frozen.p50_gwh, 2),
                "p90_1yr_net_gwh": round(exc_frozen.p90_1yr_gwh, 2),
                "p90_life_net_gwh": round(exc_frozen.p90_life_gwh, 2),
            },
            "live_19_44_pct": {
                "wake_loss_pct": round(res_14.wake_loss_pct, 2),
                "p50_net_gwh": round(exc_live.p50_gwh, 2),
                "p90_1yr_net_gwh": round(exc_live.p90_1yr_gwh, 2),
                "p90_life_net_gwh": round(exc_live.p90_life_gwh, 2),
            },
            "p50_delta_gwh": round(exc_live.p50_gwh - exc_frozen.p50_gwh, 2),
            "p50_delta_pct": round(
                (exc_live.p50_gwh - exc_frozen.p50_gwh) / exc_frozen.p50_gwh * 100.0, 2
            ),
        },
    }


@hydra.main(
    version_base="1.3", config_path="../conf", config_name="dutchbay_wake_14_turbines"
)
def main(cfg: DictConfig) -> None:
    """Run the wake deficit gap analysis and output JSON."""
    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected Hydra config to resolve to a dictionary")
    result = compute_gap_analysis(raw)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
