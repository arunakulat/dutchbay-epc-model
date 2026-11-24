"""Screen-only PyWake reproducibility harness. Never writes confidential curve rows.

Use a private 45-row OEM power/Ct CSV from an environment variable. All
output destinations MUST be outside the repository. This tool is not a model
promotion, does not create P50/P90 lender evidence, and does not alter YAML.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import yaml
from path_guard import require_external_path
from py_wake.literature.gaussian_models import Bastankhah_PorteAgel_2014
from py_wake.site import UniformWeibullSite
from py_wake.wind_turbines import WindTurbine
from py_wake.wind_turbines.power_ct_functions import PowerCtTabular
from pyproj import Transformer

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]


def _load_curve(
    path: Path, power_cap: float, expected_nameplate_kw: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with path.open() as stream:
        r = list(
            csv.DictReader(
                line for line in stream if line.strip() and not line.startswith("#")
            )
        )
    ws = np.array([float(x["wind_speed_ms"]) for x in r])
    raw_kw = np.array([float(x["power_kw"]) for x in r])
    ct = np.array([float(x["thrust_coefficient"]) for x in r])
    if (
        len(ws) != 45
        or not all(np.all(np.isfinite(x)) for x in (ws, raw_kw, ct))
        or not np.all(np.diff(ws) > 0)
        or abs(ws[0] - 3.0) > 1e-9
        or abs(ws[-1] - 25.0) > 1e-9
        or not np.allclose(np.diff(ws), 0.5, atol=1e-9, rtol=0.0)
        or np.min(raw_kw) < 0
        or not np.all((ct >= 0) & (ct < 1))
    ):
        raise ValueError("invalid OEM curve geometry / units / thrust data")
    # Deliberately check the UNCLIPPED OEM values.  A 'power_kw' file filled
    # with watts or MW must fail rather than become plausible by clipping.
    if not 0.99 * expected_nameplate_kw <= raw_kw.max() <= 1.01 * expected_nameplate_kw:
        raise ValueError("OEM curve power_kw peak inconsistent with 10.5 MW model")
    if not 0 < power_cap <= expected_nameplate_kw:
        raise ValueError("invalid derated active-power limit")
    p = np.minimum(raw_kw, power_cap)
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
    if not (
        len(turbines) == 15
        and count.sum() == 14
        and turbines[1]["id"] == "T2"
        and not count[1]
    ):
        raise ValueError("not the declared 14 counted WTG + external T2 layout")
    freq = np.array([float(x["frequency"]) for x in rose])
    if (
        not np.all(np.isfinite(freq))
        or np.any(freq < 0)
        or not 0.99 < freq.sum() < 1.01
    ):
        raise ValueError("invalid directional sector frequencies")
    freq = freq / freq.sum()
    A = np.array([float(x["weibull_a_ms"]) for x in rose])
    K = np.array([float(x["weibull_k"]) for x in rose])
    if len(freq) != 16 or not all(
        np.all(np.isfinite(v)) and np.all(v > 0) for v in (A, K)
    ):
        raise ValueError("invalid 16-sector Weibull parameters")
    c = cfg["turbine"]
    ws, p, ct = _load_curve(curve, float(c["derate_clip_kw"]), float(c["nameplate_kw"]))
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
    # Review-triggered, deliberately non-adopted stress cases. The farm's
    # measured energy-bearing sector TI is nearer 0.07--0.085 than the 0.10
    # legacy engine default. Rotate the complete distribution +/- 22.5 deg
    # without mutating the original 16-sector wind rose (not an uncertainty
    # distribution, just a directional adverse-case test).
    robustness_cases = [
        once("MCP_NASA_T2_external_TI_site_0p070", 0.07, x, y, count, freq, A, K),
        once("MCP_NASA_T2_external_TI_site_0p085", 0.085, x, y, count, freq, A, K),
    ]
    for steps, name in [(-1, "minus_22p5deg"), (1, "plus_22p5deg")]:
        robustness_cases.append(
            once(
                "MCP_NASA_T2_external_rose_" + name,
                0.07,
                x,
                y,
                count,
                np.roll(freq, steps),
                np.roll(A, steps),
                np.roll(K, steps),
            )
        )
    excluded = {"T1", "T13", "T14", "T15"}
    flow = np.array([t["id"] not in excluded for t in turbines], dtype=bool)
    if flow.sum() != 11 or count[flow].sum() != 10:
        raise ValueError("TEC uncertainty sensitivity has unexpected counted layout")
    robustness_cases.append(
        once(
            "MCP_NASA_TEC_open_T1_T13_T14_T15_excluded_TI_0p070",
            0.07,
            x[flow],
            y[flow],
            count[flow],
            freq,
            A,
            K,
        )
    )
    return {
        "status": "SCREENING_NOT_LENDER_GRADE",
        "robustness_cases": robustness_cases,
        "robustness_use": "Review-targeted non-bankable TI/direction/TEC sensitivities, not probabilistic bounds",
        "source_limitations": [
            "Bastankhah-PorteAgel far-wake model not validated near 2.2 rotor diameters",
            "9.5 MW assumed cap changes power but retains 10.5 MW Ct, not a real derated curve",
            "site mast directional residual and seasonal incomplete campaign not propagated",
            "legacy ERA5 12-sector distribution is NOT like-for-like with NASA 16-sector transfer",
        ],
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
            "9.5 MW clipped power with unmodified 10.5 MW Ct; no certified OEM derated operating mode",
            "partial mast TI is not a justified uniform farm TI",
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
    if a.repo.resolve() != REPO.resolve():
        raise SystemExit(
            "Input --repo override rejected: only the running checkout is authoritative"
        )
    if not source.is_file():
        raise SystemExit("Private OEM curve not supplied: set env or --curve; refusing")
    if source.resolve().is_relative_to(REPO.resolve()):
        raise SystemExit(
            "Private OEM power/Ct input found inside public checkout: refusing"
        )
    digest_env_name = cfg["turbine"]["curve_sha256_environment"]
    expected_digest = os.environ.get(digest_env_name, "").strip().lower()
    if len(expected_digest) != 64 or any(
        x not in "0123456789abcdef" for x in expected_digest
    ):
        raise SystemExit("Private OEM SHA256 fingerprint must be supplied at runtime")
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_digest:
        raise SystemExit("Private OEM source SHA256 mismatch: refusing")
    try:
        out = require_external_path(a.output, declared_repo=a.repo)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
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
