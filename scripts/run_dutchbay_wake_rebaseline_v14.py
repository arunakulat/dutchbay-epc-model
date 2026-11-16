#!/usr/bin/env python3
"""Hydra CLI: re-derive the DutchBay frozen wake loss for 14 turbines (#1577).

Reads ``conf/dutchbay_wake_14_turbines.yaml`` and prints one JSON object (CLI-01, CLI-03).
The committed results are ``docs/wind/dutchbay_14_turbine_wake_summary.json``.

The Blue Whale turbine stands on DutchBay T2 (#1568), and DutchBay drops to 14 turbines
(owner, 2026-11-08). The frozen 15-turbine wake loss is scaled by the ratio of two live
PyWake runs on the same inputs: the loss over the 14 DutchBay turbines with a turbine still
standing at T2, over the loss of all 15. The T2 turbine is modelled with DutchBay's own
reference machine as a proxy (the conf explains why). Two sensitivities are reported: T2
removed from the flow, and the synthetic single row the frozen value cites. A third block,
``per_turbine_sensitivity``, gives each turbine's live wake loss and its waked rose as a
labelled resource sensitivity (#1589); setting ``wake_rebaseline.per_turbine_rose_png`` also
draws the roses.

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

#: counted = the scenario's own turbines, whose energy is counted (#1775: the role names
#: no site); external_waker = stands in the flow and is not counted.
_ROLES = ("counted", "external_waker")


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
        "_per_turbine": res.per_turbine,
    }


#: The per-turbine block is a labelled resource sensitivity, never the lender basis (#1589).
PER_TURBINE_LABEL = (
    "Resource sensitivity, not the lender basis. Live PyWake wake loss for each turbine on "
    "the real layout, with T2 standing and waking. The lender basis is wake_loss_14_pct. "
    "The live model's farm loss over the counted turbines is far above the frozen value it "
    "scales, and that gap is open in #1589, so the live figures are shown beside a share "
    "scaled to the lender basis: each turbine's live loss times wake_loss_14_pct over the "
    "live farm loss, which keeps the farm total on the basis."
)


def per_turbine_block(
    ids: Sequence[str],
    roles: Sequence[str],
    case: Mapping[str, Any],
    basis_pct: float,
    n_sectors: int,
    decimals: int,
) -> Dict[str, Any]:
    """Each turbine's live wake loss, its loss scaled to the lender basis, and its roses.

    Args:
        ids: Turbine ids in layout order.
        roles: Each turbine's role, aligned to ``ids``.
        case: A :func:`_loss` result whose ``_per_turbine`` covers the same layout.
        basis_pct: The farm wake loss the lender case carries (``wake_loss_14_pct``).
        n_sectors: Wind-rose sectors, North-centred.
        decimals: Rounding for the printed figures.

    Returns:
        A JSON-serialisable block with the label, the scale factor and one row per turbine.
    """
    live_farm = float(case["wake_loss_pct"])
    scale = basis_pct / live_farm if live_farm > 0 else 0.0
    rows = []
    for t in case["_per_turbine"]:
        rows.append(
            {
                "id": ids[t.index],
                "role": roles[t.index],
                "counted": t.counted,
                "live_wake_loss_pct": round(t.wake_loss_pct, decimals),
                "scaled_to_basis_pct": (
                    round(t.wake_loss_pct * scale, decimals) if t.counted else None
                ),
                "sector_wake_loss_pct": [
                    round(v, decimals) for v in t.sector_wake_loss_pct
                ],
                "waked_energy_rose": [round(v, 4) for v in t.sector_energy_share],
            }
        )
    return {
        "label": PER_TURBINE_LABEL,
        "work_item": "#1589",
        "live_farm_wake_loss_pct": round(live_farm, decimals),
        "basis_wake_loss_pct": basis_pct,
        "scale_to_basis": round(scale, 6),
        "sector_deg": [round(i * 360.0 / n_sectors, 2) for i in range(n_sectors)],
        "turbines": rows,
    }


def _public(case: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in case.items() if not k.startswith("_")}


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
        "all_15": _public(all_15),
        "dutchbay_14_t2_waking": _public(with_waker),
        "dutchbay_14_t2_removed": _public(removed),
        "_t2_waking": with_waker,
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
    per_turbine = per_turbine_block(
        layout["ids"],
        layout["roles"],
        real.pop("_t2_waking"),
        rebaselined,
        len(resource["wind_rose_freq"]),
        decimals,
    )
    row.pop("_t2_waking")
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
        "per_turbine_sensitivity": per_turbine,
        "real_layout": real,
        "synthetic_row": row,
        "t2_proxy_note": (
            "The turbine at T2 is modelled with the IEA 10 MW reference machine as a proxy "
            "for the other project's machine there, whose curves are confidential and not "
            "read."
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
    result = run(raw)
    rose_png = raw["wake_rebaseline"].get("per_turbine_rose_png")
    if rose_png:
        from app.reports.wind_rose_plot import render_turbine_wake_roses_png

        block = result["per_turbine_sensitivity"]
        render_turbine_wake_roses_png(
            block["turbines"],
            block["sector_deg"],
            str(rose_png),
            title=PER_TURBINE_LABEL,
        )
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
