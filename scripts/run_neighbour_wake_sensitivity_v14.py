#!/usr/bin/env python3
"""Hydra CLI: one turbine's wake loss from the neighbouring turbines around it (#1887).

Reads ``conf/neighbour_wake_sensitivity.yaml`` (which composes a wake re-baseline config for
the layout and proxy machine) and prints one JSON object (CLI-01, CLI-03). The summary path,
the counted turbine, the wind-resource summary and every label come from that config; this
script names no site (#1759, #1775).

The turbine named by ``waked_id`` is the only one counted; every other turbine in the layout
stands in the flow and wakes it. The incident wind is the counted turbine's own long-term
resource, read from a committed met-mast transfer summary (omnidirectional Weibull and the
sector frequency rose under ``resource_block``) and pinned by SHA-256. Reported: the wake
loss and its sectors, the relative change in net energy if applied, the same loss scaled
by the re-baseline's live-to-basis ratio, the implied wake-model uncertainty under a stated
convention, and sensitivities to machine geometry, turbulence intensity and deficit model.

A labelled sensitivity only: no scenario input, budget value or KPI changes. No wake maths
is written here: :func:`wind_resource.bankable_aep.model_wake_loss` runs every case (via the
re-baseline script's runner) and the re-baseline's own projection places the layout.

Usage::

    .venv/bin/python scripts/run_neighbour_wake_sensitivity_v14.py
    .venv/bin/python scripts/run_neighbour_wake_sensitivity_v14.py \\
        neighbour_wake.summary_json=<path>
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Mapping

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.power_curves.oem_parser import (
    IEC_REFERENCE_AIR_DENSITY_KGM3,
    parse_power_curve,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _rebaseline() -> ModuleType:
    """The #1577 re-baseline script, for its layout projection and its loss runner."""
    path = REPO_ROOT / "scripts" / "run_dutchbay_wake_rebaseline_v14.py"
    spec = importlib.util.spec_from_file_location("_wake_rebaseline_1577", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transferred_resource(path: Path, block_key: str) -> Dict[str, Any]:
    """Omni Weibull and the sector frequency rose under ``block_key``, with the SHA-256."""
    raw = path.read_bytes()
    lt = json.loads(raw)[block_key]
    rose = sorted(lt["rose"], key=lambda s: int(s["sector"]))
    freq = [float(s["frequency"]) for s in rose]
    total = sum(freq)
    return {
        "weibull_a": float(lt["weibull_a_ms"]),
        "weibull_k": float(lt["weibull_k"]),
        "wind_rose_freq": [f / total for f in freq],
        "sector_centre_deg": [float(s["centre_deg"]) for s in rose],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Run every case and return the summary."""
    rb = _rebaseline()
    base = cfg["wake_rebaseline"]
    block = cfg["neighbour_wake"]
    decimals = int(block["output_decimals"])
    c = parse_power_curve(
        str(base["turbine"]["curve_key"]),
        air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3,
    )
    curve: Dict[str, List[float]] = {
        key: [float(v) for v in c[key]]
        for key in ("wind_speed_ms", "power_kw", "thrust_coefficient")
    }
    layout = rb.project_layout(base["layout"]["turbines"])
    waked = str(block["waked_id"])
    if waked not in layout["ids"]:
        raise ValueError(f"waked_id {waked!r} is not in the layout")
    counted = [i == waked for i in layout["ids"]]
    res_path = REPO_ROOT / str(block["resource_summary"])
    res = transferred_resource(res_path, str(block["resource_block"]))

    def case(geometry: str, ti: float, model: str) -> Dict[str, Any]:
        turbine = dict(block["geometries"][geometry])
        resource = {
            "weibull_a": res["weibull_a"],
            "weibull_k": res["weibull_k"],
            "wind_rose_freq": res["wind_rose_freq"],
            "turbulence_intensity": ti,
            "deficit_model": model,
        }
        out = rb._loss(curve, turbine, resource, layout["x_m"], layout["y_m"], counted)
        (t,) = [p for p in out["_per_turbine"] if p.counted]
        return {
            "geometry": geometry,
            "turbulence_intensity": ti,
            "deficit_model": model,
            "wake_loss_pct": round(float(out["wake_loss_pct"]), decimals),
            "sector_wake_loss_pct": [
                round(v, decimals) for v in t.sector_wake_loss_pct
            ],
        }

    g0 = str(block["primary_geometry"])
    ti0 = float(block["primary_turbulence_intensity"])
    m0 = str(block["primary_deficit_model"])
    primary = case(g0, ti0, m0)
    loss = float(primary["wake_loss_pct"])
    db_path = REPO_ROOT / str(block["dutchbay_wake_summary"])
    db_raw = db_path.read_bytes()
    scale = float(json.loads(db_raw)["per_turbine_sensitivity"]["scale_to_basis"])
    fraction = float(block["wake_uncertainty_fraction_of_loss"])
    neighbours = []
    i = layout["ids"].index(waked)
    for j, tid in enumerate(layout["ids"]):
        if j == i:
            continue
        dx = layout["x_m"][j] - layout["x_m"][i]
        dy = layout["y_m"][j] - layout["y_m"][i]
        neighbours.append((tid, (dx * dx + dy * dy) ** 0.5))
    neighbours.sort(key=lambda p: p[1])
    return {
        "work_item": "#1887",
        "label": str(block["label"]),
        "waked_id": waked,
        "resource": {
            "source": str(block["resource_summary"]),
            "source_sha256": res["sha256"],
            "basis": f"{block['resource_block']} omni Weibull and sector frequency rose",
            "weibull_a_ms": res["weibull_a"],
            "weibull_k": res["weibull_k"],
            "sector_centre_deg": res["sector_centre_deg"],
        },
        "nearest_neighbours_m": [
            {"id": tid, "distance_m": round(d, 1)} for tid, d in neighbours[:3]
        ],
        "primary": primary,
        "net_energy_relative_change_if_applied_pct": round(-loss, decimals),
        "scaled_to_dutchbay_basis": {
            "wake_loss_pct": round(loss * scale, decimals),
            "scale_to_basis": scale,
            "source": str(block["dutchbay_wake_summary"]),
            "source_sha256": hashlib.sha256(db_raw).hexdigest(),
            "note": str(block["scaled_note"]),
        },
        "implied_wake_model_uncertainty_pct": {
            "value": round(loss * fraction, decimals),
            "fraction_of_loss": fraction,
            "committed_wake_model_pct": 0.0,
            "note": str(block["uncertainty_note"]),
        },
        "sensitivities": {
            "geometry": [case(g, ti0, m0) for g in block["geometries"]],
            "turbulence_intensity": [
                case(g0, float(ti), m0) for ti in block["turbulence_intensity"]
            ],
            "deficit_model": [case(g0, ti0, str(m)) for m in block["deficit_models"]],
        },
    }


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="neighbour_wake_sensitivity",
)
def main(cfg: DictConfig) -> None:
    """Run the sensitivity, print one JSON object, and write it when asked.

    Args:
        cfg: Hydra config composed from ``conf/neighbour_wake_sensitivity.yaml``.

    Raises:
        TypeError: If the config does not resolve to a mapping.
    """
    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    result = run(copy.deepcopy(raw))
    text = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    out = raw["neighbour_wake"].get("summary_json")
    if out:
        target = Path(str(out))
        if not target.is_absolute():
            target = REPO_ROOT / target
        target.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
