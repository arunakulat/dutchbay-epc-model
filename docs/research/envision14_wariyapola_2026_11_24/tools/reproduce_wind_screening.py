"""Screen-only PyWake reproducibility harness. Never writes confidential curve rows.

Use a private 45-row OEM power/Ct CSV from an environment variable. All
output destinations MUST be outside the repository. This tool is not a model
promotion, does not create P50/P90 lender evidence, and does not alter YAML.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np
import yaml
from py_wake.literature.gaussian_models import Bastankhah_PorteAgel_2014
from py_wake.site import UniformWeibullSite
from py_wake.wind_turbines import WindTurbine
from py_wake.wind_turbines.power_ct_functions import PowerCtTabular
from pyproj import Transformer

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]


def _load_curve(
    path: Path, power_cap: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with path.open() as stream:
        r = list(
            csv.DictReader(
                line for line in stream if line.strip() and not line.startswith("#")
            )
        )
    ws = np.array([float(x["wind_speed_ms"]) for x in r])
    p = np.array([min(float(x["power_kw"]), power_cap) for x in r])
    ct = np.array([float(x["thrust_coefficient"]) for x in r])
    if len(ws) < 10 or not np.all(np.diff(ws) > 0) or not np.all((ct >= 0) & (ct <= 1)):
        raise ValueError("invalid OEM curve geometry / thrust data")
    if np.max(p) > power_cap:
        raise ValueError("power cap violated")
    return ws, p, ct


def execute(cfg: dict, curve: Path, repo: Path) -> dict:
    with (repo / cfg["resource"]["rose_csv"]).open() as f:
        rose = list(
            csv.DictReader(
                line for line in f if line.strip() and not line.startswith("#")
            )
        )
    layout = yaml.safe_load((repo / cfg["site_layout"]).read_text())["wake_rebaseline"]
    turbines = layout["layout"]["turbines"]
    count = np.array([p["role"] == "counted" for p in turbines], dtype=bool)
    assert (
        len(turbines) == 15
        and count.sum() == 14
        and turbines[1]["id"] == "T2"
        and not count[1]
    )
    freq = np.array([float(x["frequency"]) for x in rose])
    freq = freq / freq.sum()
    A = np.array([float(x["weibull_a_ms"]) for x in rose])
    K = np.array([float(x["weibull_k"]) for x in rose])
    assert len(freq) == 16
    c = cfg["turbine"]
    ws, p, ct = _load_curve(curve, float(c["derate_clip_kw"]))
    wt = WindTurbine(
        name=c["model"] + " capped at 9.5 MW (ASSUMED)",
        diameter=float(c["rotor_diameter_m"]),
        hub_height=float(c["hub_height_m"]),
        powerCtFunction=PowerCtTabular(ws, p * 1000, "w", ct),
    )
    proj = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
    x, y = proj.transform(
        [t["lon_deg"] for t in turbines], [t["lat_deg"] for t in turbines]
    )
    x = np.array(x)
    y = np.array(y)
    transfer = json.loads((repo / cfg["resource"]["transfer_summary"]).read_text())
    non_wake_retention = 1 - float(transfer["yield"]["total_loss_pct"]) / 100

    def once(
        label: str,
        ti: float,
        xc: np.ndarray,
        yc: np.ndarray,
        mask: np.ndarray,
        freq: np.ndarray,
        A: np.ndarray,
        K: np.ndarray,
    ) -> dict:
        site = UniformWeibullSite(p_wd=freq, a=A, k=K, ti=ti)
        model = Bastankhah_PorteAgel_2014(site, wt, k=0.38 * ti + 0.004)
        sim = model(xc, yc)
        gross_by = np.asarray(sim.aep(with_wake_loss=False).sum(["wd", "ws"]).values)
        waked_by = np.asarray(sim.aep().sum(["wd", "ws"]).values)
        gross = float(gross_by[mask].sum())
        waked = float(waked_by[mask].sum())
        if gross <= 0 or not 0 < waked <= gross:
            raise ValueError("nonphysical wake energy")
        return {
            "case": label,
            "turbulence_intensity": ti,
            "n_counted": int(mask.sum()),
            "flow_turbines": len(mask),
            "gross_gwh": gross,
            "waked_gwh": waked,
            "wake_loss_pct": 100 * (1 - waked / gross),
            "net_screening_gwh": waked * non_wake_retention,
        }

    cases = []
    for ti in cfg["model"]["ti_cases"]:
        cases.append(once("MCP_NASA_T2_external", float(ti), x, y, count, freq, A, K))
        cases.append(
            once(
                "MCP_NASA_T2_absent",
                float(ti),
                x[count],
                y[count],
                np.ones(14, dtype=bool),
                freq,
                A,
                K,
            )
        )
    old = layout["resource"]
    old_freq = np.array(old["wind_rose_freq"], dtype=float)
    old_freq /= old_freq.sum()
    cases.append(
        once(
            "LEGACY_ERA5_T2_external",
            float(cfg["model"]["historical_era5_ti"]),
            x,
            y,
            count,
            old_freq,
            np.full(12, float(old["weibull_a"])),
            np.full(12, float(old["weibull_k"])),
        )
    )
    return {
        "status": "SCREENING_NOT_LENDER_GRADE",
        "source": "public frozen MCP/NASA 16-sector aggregate and EIA-derived site layout; private OEM curve supplied only at runtime",
        "turbine": {
            "model": c["model"],
            "nameplate_mw": 14 * float(c["nameplate_kw"]) / 1000,
            "derated_max_mw": 14 * float(c["derate_clip_kw"]) / 1000,
            "hub_height_m": c["hub_height_m"],
            "rotor_diameter_m": c["rotor_diameter_m"],
        },
        "non_wake_retention": non_wake_retention,
        "cases": cases,
        "hold": [
            "partial mast campaign",
            "MERRA-2/ERA5 divergence",
            "no certified OEM derated curve",
            "wake and turbine loading independent review needed",
            "not a P50/P90 or lender AEP",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=PACKAGE / "wind_screen_config.yaml")
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--curve", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text())
    source = a.curve or Path(os.environ.get(cfg["turbine"]["curve_environment"], ""))
    if not source.is_file():
        raise SystemExit("Private OEM curve not supplied: set env or --curve; refusing")
    out = a.output.resolve()
    if out.is_relative_to(a.repo.resolve()):
        raise SystemExit("Refusing to write derived/private output inside repository")
    r = execute(cfg, source, a.repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": r["status"],
                "cases": len(r["cases"]),
                "output_outside_repo": True,
                "primary": r["cases"][2],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
