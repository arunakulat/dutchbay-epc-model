#!/usr/bin/env python3
"""Hydra CLI: re-derive the DutchBay frozen wake loss for 14 turbines (#1577).

Reads ``conf/dutchbay_wake_14_turbines.yaml`` and prints one JSON object (CLI-01, CLI-03).
The committed results are ``docs/wind/dutchbay_14_turbine_wake_summary.json``.

The Blue Whale turbine stands on DutchBay T2 (#1568), and DutchBay drops to 14 turbines
(owner, 2026-11-08). The frozen 15-turbine wake loss is scaled by the ratio of two live
PyWake runs on the same inputs: the loss over the 14 DutchBay turbines with a turbine still
standing at T2, over the loss of all 15. The T2 turbine is modelled with DutchBay's own
reference machine as a proxy (the conf explains why). Two sensitivities are reported: T2
removed from the flow, and the synthetic single row the frozen value cites.

No wake maths is written here: :func:`wind_resource.bankable_aep.model_wake_loss` runs every
case and :class:`analytics.gis.shadow_flicker.LocalFrame` projects the layout.

Usage::

    .venv/bin/python scripts/run_dutchbay_wake_rebaseline_v14.py
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence

import hydra
import numpy as np
from omegaconf import DictConfig, OmegaConf

from analytics.gis.shadow_flicker import LocalFrame
from analytics.power_curves.oem_parser import (
    IEC_REFERENCE_AIR_DENSITY_KGM3,
    parse_power_curve,
)
from wind_resource.bankable_aep import model_wake_loss

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


def _loss(
    curve: Mapping[str, List[float]],
    turbine: Mapping[str, Any],
    resource: Mapping[str, Any],
    x_m: Sequence[float],
    y_m: Sequence[float],
    counted: Optional[Sequence[bool]],
) -> Dict[str, Any]:
    res = model_wake_loss(
        wind_speed_ms=curve["wind_speed_ms"],
        power_kw=curve["power_kw"],
        thrust_coefficient=curve["thrust_coefficient"],
        rotor_diameter_m=float(turbine["rotor_diameter_m"]),
        hub_height_m=float(turbine["hub_height_m"]),
        layout_x_m=x_m,
        layout_y_m=y_m,
        weibull_a=float(resource["weibull_a"]),
        weibull_k=float(resource["weibull_k"]),
        wind_rose_freq=[float(v) for v in resource["wind_rose_freq"]],
        turbulence_intensity=float(resource["turbulence_intensity"]),
        deficit_model=str(resource["deficit_model"]),
        counted=counted,
    )
    return {
        "wake_loss_pct": res.wake_loss_pct,
        "n_turbines_counted": res.n_turbines,
        "aep_gross_gwh": res.aep_gross_gwh,
        "aep_wake_gwh": res.aep_wake_gwh,
        "deficit_model": res.deficit_model,
    }


def _three_cases(
    curve: Mapping[str, List[float]],
    turbine: Mapping[str, Any],
    resource: Mapping[str, Any],
    x_m: Sequence[float],
    y_m: Sequence[float],
    waker: Sequence[bool],
) -> Dict[str, Any]:
    counted = [not w for w in waker]
    keep_x = [x for x, w in zip(x_m, waker, strict=True) if not w]
    keep_y = [y for y, w in zip(y_m, waker, strict=True) if not w]
    all_15 = _loss(curve, turbine, resource, x_m, y_m, None)
    with_waker = _loss(curve, turbine, resource, x_m, y_m, counted)
    removed = _loss(curve, turbine, resource, keep_x, keep_y, None)
    return {
        "all_15": all_15,
        "dutchbay_14_t2_waking": with_waker,
        "dutchbay_14_t2_removed": removed,
        "ratio_t2_waking": with_waker["wake_loss_pct"] / all_15["wake_loss_pct"],
        "ratio_t2_removed": removed["wake_loss_pct"] / all_15["wake_loss_pct"],
    }


def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Run the re-baseline and return the derived results.

    Args:
        cfg: The resolved Hydra config (``wake_rebaseline`` block).

    Returns:
        A JSON-serialisable mapping: the layout, each case and the re-baselined wake loss.
    """
    block = cfg["wake_rebaseline"]
    turbine = block["turbine"]
    resource = block["resource"]
    frozen = float(block["frozen_wake_15_pct"])
    decimals = int(block["output_decimals"])

    c = parse_power_curve(
        str(turbine["curve_key"]), air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    curve: Dict[str, List[float]] = {
        key: [float(v) for v in c[key]]
        for key in ("wind_speed_ms", "power_kw", "thrust_coefficient")
    }

    layout = project_layout(block["layout"]["turbines"])
    waker = [r == "external_waker" for r in layout["roles"]]
    real = _three_cases(curve, turbine, resource, layout["x_m"], layout["y_m"], waker)

    row_cfg = block["synthetic_row"]
    n_row = int(row_cfg["n_turbines"])
    row_x = [0.0] * n_row
    # North end first, so index 0 is T1 and index 1 is T2.
    row_y = [float(row_cfg["spacing_m"]) * (n_row - 1 - i) for i in range(n_row)]
    row_waker = [i == int(row_cfg["external_waker_index"]) for i in range(n_row)]
    row = _three_cases(curve, turbine, resource, row_x, row_y, row_waker)

    rebaselined = round(frozen * real["ratio_t2_waking"], decimals)
    sens_removed = round(frozen * real["ratio_t2_removed"], decimals)
    sens_row = round(frozen * row["ratio_t2_waking"], decimals)
    layout_out: List[Dict[str, Any]] = [
        {"id": i, "role": r, "x_m": round(x, 2), "y_m": round(y, 2)}
        for i, r, x, y in zip(
            layout["ids"], layout["roles"], layout["x_m"], layout["y_m"], strict=True
        )
    ]
    return {
        "work_item": "#1577",
        "frozen_wake_15_pct": frozen,
        "wake_loss_14_pct": rebaselined,
        "method": (
            "frozen_wake_15_pct x (live PyWake loss over the 14 DutchBay turbines with T2 "
            "standing and waking / live loss over all 15), real layout"
        ),
        "sensitivities_pct": {
            "t2_removed_from_flow_real_layout": sens_removed,
            "t2_waking_synthetic_row": sens_row,
        },
        "frame_origin": {
            "lat_deg": layout["origin_lat_deg"],
            "lon_deg": layout["origin_lon_deg"],
        },
        "layout": layout_out,
        "real_layout": real,
        "synthetic_row": row,
        "t2_proxy_note": (
            "The turbine at T2 is modelled with the IEA 10 MW reference machine as a proxy "
            "for the Blue Whale machine, whose curves are confidential and not read."
        ),
    }


@hydra.main(
    version_base="1.3", config_path="../conf", config_name="dutchbay_wake_14_turbines"
)
def main(cfg: DictConfig) -> None:
    """Run the re-baseline and print one JSON object.

    Args:
        cfg: Hydra config composed from ``conf/dutchbay_wake_14_turbines.yaml``.

    Raises:
        TypeError: If the config does not resolve to a mapping.
    """
    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    print(json.dumps(run(raw), sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
