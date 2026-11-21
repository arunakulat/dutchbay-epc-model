#!/usr/bin/env python3
"""Hydra CLI: investigate the gap between the frozen and the live wake loss (#1589).

The lender basis carries a farm wake loss re-derived from a frozen 15-turbine value by the
ratio of two live PyWake runs (#1577, ``scripts/run_dutchbay_wake_rebaseline_v14.py``). The
same live model reports an absolute loss on the recorded layout about two and a half times
the frozen value. This script decomposes that gap on the re-baseline's own inputs
(``conf/dutchbay_wake_14_turbines.yaml``, composed by ``conf/dutchbay_wake_gap_1589.yaml``)
and prints one JSON object (CLI-01, CLI-03). The committed results are
``docs/wind/dutchbay_wake_gap_1589_summary.json``.

What it reports:

- each turbine's nearest neighbour, in metres, rotor diameters and bearing;
- a two-by-two of layout (the synthetic single row the frozen value cites, or the
  recorded layout) against wind rose (uniform, or the configured rose), all turbines;
- the live loss over the counted turbines with each external waker standing and waking,
  and each turbine's own live loss;
- sweeps of rotor diameter (a spacing-in-diameters sensitivity at fixed curves), ambient
  turbulence intensity and deficit model;
- the relative change in P50 and P90 energy if the live loss replaced the basis, as a
  disclosed sensitivity only.

It changes no input of any scenario. No wake maths is written here:
:func:`wind_resource.bankable_aep.model_wake_loss` runs every case, and the layout
projection is the re-baseline script's own.

Usage::

    .venv/bin/python scripts/analyze_dutchbay_wake_deficit_gap_1589.py
    .venv/bin/python scripts/analyze_dutchbay_wake_deficit_gap_1589.py \\
        wake_gap.summary_json=docs/wind/dutchbay_wake_gap_1589_summary.json
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import logging
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Sequence

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.power_curves.oem_parser import (
    IEC_REFERENCE_AIR_DENSITY_KGM3,
    parse_power_curve,
)
from wind_resource.bankable_aep import (
    UncertaintyBudget,
    exceedance_levels,
    gaussian_k_star,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

LABEL = (
    "Investigation and disclosed sensitivity only (#1589). The lender basis is the "
    "re-baselined wake loss of the wake_rebaseline config, and is not changed here. Live "
    "figures use the configured turbine curves ({curve_key}) and the configured wind "
    "resource, not measured site wind or turbulence data."
)


def _rebaseline() -> ModuleType:
    """The #1577 re-baseline script, for its layout projection and its loss runner."""
    path = REPO_ROOT / "scripts" / "run_dutchbay_wake_rebaseline_v14.py"
    spec = importlib.util.spec_from_file_location("_wake_rebaseline_1577", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def nearest_neighbours(
    ids: Sequence[str],
    roles: Sequence[str],
    x_m: Sequence[float],
    y_m: Sequence[float],
    rotor_diameter_m: float,
) -> List[Dict[str, Any]]:
    """Each turbine's nearest neighbour: distance in metres and rotor diameters, bearing.

    The bearing is from the turbine to its neighbour, degrees clockwise from north, so a
    neighbour at 200 deg stands downwind of the turbine when the wind blows from about 20
    deg, and upwind when it blows from about 200 deg.
    """
    rows: List[Dict[str, Any]] = []
    for i, tid in enumerate(ids):
        best: Optional[tuple[float, float, str]] = None
        for j, other in enumerate(ids):
            if i == j:
                continue
            dx, dy = x_m[j] - x_m[i], y_m[j] - y_m[i]
            dist = math.hypot(dx, dy)
            if best is None or dist < best[0]:
                bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
                best = (dist, bearing, other)
        assert best is not None
        rows.append(
            {
                "id": tid,
                "role": roles[i],
                "nearest_id": best[2],
                "distance_m": round(best[0], 1),
                "distance_rotor_diameters": round(best[0] / rotor_diameter_m, 2),
                "bearing_deg": round(best[1], 1),
            }
        )
    return rows


def _sha256(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()


def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Run the investigation and return the JSON-serialisable summary.

    Args:
        cfg: The resolved Hydra config, with the ``wake_rebaseline`` and ``wake_gap``
            blocks.

    Returns:
        The summary: spacing, the layout-by-rose decomposition, the live losses, the
        sweeps and the bankable sensitivity, with the pinned input hashes.
    """
    rb = _rebaseline()
    block = cfg["wake_rebaseline"]
    gap = cfg["wake_gap"]
    turbine = dict(block["turbine"])
    resource = dict(block["resource"])
    frozen = float(block["frozen_wake_15_pct"])
    decimals = int(block["output_decimals"])
    d_ref = float(turbine["rotor_diameter_m"])

    c = parse_power_curve(
        str(turbine["curve_key"]), air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    curve: Dict[str, List[float]] = {
        key: [float(v) for v in c[key]]
        for key in ("wind_speed_ms", "power_kw", "thrust_coefficient")
    }

    layout = rb.project_layout(block["layout"]["turbines"])
    ids, roles = layout["ids"], layout["roles"]
    x_m, y_m = layout["x_m"], layout["y_m"]
    counted = [r != "external_waker" for r in roles]

    row_cfg = block["synthetic_row"]
    n_row = int(row_cfg["n_turbines"])
    row_x = [0.0] * n_row
    row_y = [float(row_cfg["spacing_m"]) * (n_row - 1 - i) for i in range(n_row)]
    row_counted = [i != int(row_cfg["external_waker_index"]) for i in range(n_row)]

    n_sectors = len(resource["wind_rose_freq"])
    uniform = dict(resource, wind_rose_freq=[1.0] * n_sectors)

    def loss(
        res: Mapping[str, Any],
        xs: Sequence[float],
        ys: Sequence[float],
        flags: Optional[Sequence[bool]],
        turb: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        return dict(rb._loss(curve, turb or turbine, res, xs, ys, flags))

    def pct(case: Mapping[str, Any]) -> float:
        return round(float(case["wake_loss_pct"]), decimals)

    # Layout x rose, all 15 turbines.
    grid = {
        "synthetic_row_uniform_rose": loss(uniform, row_x, row_y, None),
        "synthetic_row_site_rose": loss(resource, row_x, row_y, None),
        "recorded_layout_uniform_rose": loss(uniform, x_m, y_m, None),
        "recorded_layout_site_rose": loss(resource, x_m, y_m, None),
    }
    g = {k: float(v["wake_loss_pct"]) for k, v in grid.items()}

    # The counted turbines, each external waker standing and waking (the basis's own case).
    real_counted = loss(resource, x_m, y_m, counted)
    row_counted_case = loss(resource, row_x, row_y, row_counted)
    live_counted = float(real_counted["wake_loss_pct"])
    ratio = live_counted / g["recorded_layout_site_rose"]
    basis = round(frozen * ratio, decimals)

    per_turbine = {
        ids[t.index]: round(t.wake_loss_pct, decimals)
        for t in real_counted["_per_turbine"]
        if t.counted
    }
    lo_id = min(per_turbine, key=lambda k: per_turbine[k])
    hi_id = max(per_turbine, key=lambda k: per_turbine[k])

    spacing = nearest_neighbours(ids, roles, x_m, y_m, d_ref)
    counted_spacing = [
        s["distance_rotor_diameters"] for s in spacing if s["role"] != "external_waker"
    ]

    rotor_sweep = []
    for d in [float(v) for v in gap["rotor_diameter_m"]]:
        turb = dict(turbine, rotor_diameter_m=d)
        rotor_sweep.append(
            {
                "rotor_diameter_m": d,
                "counted_nearest_neighbour_min_rotor_diameters": round(
                    min(
                        s["distance_m"]
                        for s in spacing
                        if s["role"] != "external_waker"
                    )
                    / d,
                    2,
                ),
                "all_turbines_pct": pct(loss(resource, x_m, y_m, None, turb)),
                "counted_t2_waking_pct": pct(loss(resource, x_m, y_m, counted, turb)),
            }
        )

    ti_sweep = []
    for ti in [float(v) for v in gap["turbulence_intensity"]]:
        res = dict(resource, turbulence_intensity=ti)
        ti_sweep.append(
            {
                "turbulence_intensity": ti,
                "k_star": round(gaussian_k_star(ti), 4),
                "all_turbines_pct": pct(loss(res, x_m, y_m, None)),
                "counted_t2_waking_pct": pct(loss(res, x_m, y_m, counted)),
            }
        )

    model_sweep = []
    for model in [str(v) for v in gap["deficit_models"]]:
        res = dict(resource, deficit_model=model)
        case = loss(res, x_m, y_m, counted)
        model_sweep.append(
            {
                "deficit_model": model,
                "model_name": case["deficit_model"],
                "all_turbines_pct": pct(loss(res, x_m, y_m, None)),
                "counted_t2_waking_pct": pct(case),
            }
        )

    # Bankable sensitivity. Gross energy and the non-wake losses are the same in both
    # cases, so net energy scales by the ratio of wake retentions; the exceedance levels
    # are proportional to P50 (checked here, not assumed), so P90 moves by the same ratio.
    factor = (1.0 - live_counted / 100.0) / (1.0 - basis / 100.0)
    budget = UncertaintyBudget()
    at_basis, at_live = exceedance_levels(1.0, budget), exceedance_levels(
        factor, budget
    )
    rel = {
        name: round(
            (getattr(at_live, name) / getattr(at_basis, name) - 1.0) * 100.0, decimals
        )
        for name in ("p50_gwh", "p90_1yr_gwh", "p90_life_gwh")
    }

    def strip(case: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "wake_loss_pct": pct(case),
            "n_turbines_counted": case["n_turbines_counted"],
            "deficit_model": case["deficit_model"],
        }

    return {
        "work_item": "#1589",
        "label": LABEL.format(curve_key=turbine["curve_key"]),
        "inputs_sha256": {
            str(rel_path): _sha256(str(rel_path)) for rel_path in gap["pinned_inputs"]
        },
        "frozen_wake_15_pct": frozen,
        "basis_wake_14_pct": basis,
        "live": {
            "recorded_layout_all_turbines_pct": pct(grid["recorded_layout_site_rose"]),
            "recorded_layout_counted_t2_waking_pct": round(live_counted, decimals),
            "synthetic_row_all_turbines_pct": pct(grid["synthetic_row_site_rose"]),
            "synthetic_row_counted_t2_waking_pct": pct(row_counted_case),
        },
        "layout_by_rose_all_turbines": {k: strip(v) for k, v in grid.items()},
        "attribution_pp": {
            "frozen_to_live_synthetic_row": round(
                g["synthetic_row_site_rose"] - frozen, decimals
            ),
            "layout_under_site_rose": round(
                g["recorded_layout_site_rose"] - g["synthetic_row_site_rose"], decimals
            ),
            "layout_under_uniform_rose": round(
                g["recorded_layout_uniform_rose"] - g["synthetic_row_uniform_rose"],
                decimals,
            ),
            "site_rose_on_recorded_layout": round(
                g["recorded_layout_site_rose"] - g["recorded_layout_uniform_rose"],
                decimals,
            ),
            "site_rose_on_synthetic_row": round(
                g["synthetic_row_site_rose"] - g["synthetic_row_uniform_rose"], decimals
            ),
            "total_frozen_to_live_recorded": round(
                g["recorded_layout_site_rose"] - frozen, decimals
            ),
        },
        "spacing": {
            "rotor_diameter_m": d_ref,
            "synthetic_row_spacing_rotor_diameters": round(
                float(row_cfg["spacing_m"]) / d_ref, 2
            ),
            "counted_nearest_neighbour_rotor_diameters_min": min(counted_spacing),
            "counted_nearest_neighbour_rotor_diameters_max": max(counted_spacing),
            "turbines": spacing,
        },
        "per_turbine_live_pct": per_turbine,
        "per_turbine_live_range": {
            "lowest": {"id": lo_id, "pct": per_turbine[lo_id]},
            "highest": {"id": hi_id, "pct": per_turbine[hi_id]},
        },
        "rotor_diameter_sweep": rotor_sweep,
        "turbulence_intensity_sweep": ti_sweep,
        "deficit_model_sweep": model_sweep,
        "bankable_sensitivity": {
            "basis_wake_pct": basis,
            "live_wake_pct": round(live_counted, decimals),
            "net_energy_factor": round(factor, 6),
            "relative_change_pct": rel,
            "note": (
                "Relative change only: gross energy, the non-wake losses and the "
                "uncertainty budget are unchanged, so every exceedance level moves by "
                "the same factor. A sensitivity, not a lender figure."
            ),
        },
    }


@hydra.main(
    version_base="1.3", config_path="../conf", config_name="dutchbay_wake_gap_1589"
)
def main(cfg: DictConfig) -> None:
    """Run the investigation, print one JSON object, and write it when asked.

    Args:
        cfg: Hydra config composed from ``conf/dutchbay_wake_gap_1589.yaml``.

    Raises:
        TypeError: If the config does not resolve to a mapping.
    """
    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    result = run(copy.deepcopy(raw))
    text = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    out = raw["wake_gap"].get("summary_json")
    if out:
        target = Path(str(out))
        if not target.is_absolute():
            target = REPO_ROOT / target
        target.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
