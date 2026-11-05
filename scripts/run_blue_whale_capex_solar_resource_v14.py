#!/usr/bin/env python3
"""Hydra CLI: Blue Whale PR 6 capex blend and solar resource.

Reads ``conf/blue_whale_capex_solar_resource.yaml`` and prints one JSON object (CLI-01,
CLI-03) with two parts:

* ``capex``: the wind single-turbine and BESS all-in capex (low, mode, high) from
  :func:`solar_resource.blue_whale_site_inputs.wind_all_in` and
  :func:`solar_resource.blue_whale_site_inputs.bess_all_in`, and the four pricing build-up
  lines. It needs the private anchors, read from ``private_anchors_path`` (a file OUTSIDE the
  repository, refused otherwise); only blended results are printed or written.
* ``solar``: the resource and yield at the PV centroid from
  :func:`solar_resource.blue_whale_site_inputs.solar_resource_summary`, the same chain at the
  TMY's own point checked against :func:`solar_resource.pv_producer.compute_solar_aep`, and
  the cross-check table (PVGIS, Global Solar Atlas, NASA POWER) frozen in the config.

Usage::

    .venv/bin/python scripts/run_blue_whale_capex_solar_resource_v14.py \\
        private_anchors_path=/outside/the/repo/blue_whale_private_anchors.yaml \\
        output.capex_summary_json=docs/blue_whale/capex_blend_summary.json \\
        output.solar_summary_json=docs/blue_whale/solar_resource_summary.json \\
        output.solar_monthly_csv=docs/blue_whale/solar_resource_monthly.csv
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import hydra
import yaml
from omegaconf import DictConfig, OmegaConf

from solar_resource.blue_whale_site_inputs import (
    CASES,
    bess_all_in,
    parse_levy_postures,
    pricing_build_up,
    solar_resource_summary,
    wind_all_in,
)
from solar_resource.pv_producer import (
    SolarResourceConfig,
    _load_tmy,
    compute_solar_aep,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The stepped chain must reproduce the producer's annual energy to this relative tolerance.
PRODUCER_PARITY = 1e-9

#: Days per year for converting NASA POWER's kWh/m2/day.
DAYS_PER_YEAR = 365.0


def _repo_path(rel: str) -> Path:
    """Resolve a config path against the repository root."""
    p = Path(rel)
    return p if p.is_absolute() else REPO_ROOT / p


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance on the mean Earth sphere (6,371,008.8 m)."""
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r * math.asin(math.sqrt(a))


def private_anchor_values(raw: Mapping[str, Any]) -> Dict[str, Dict[str, float]]:
    """Normalise the private file's raw figures to the blend's units.

    Returns:
        ``values`` (USD/kW or USD/kWh contracted by anchor name) and ``dc_share`` (the DC
        block's share of equipment by anchor name).
    """
    if raw.get("schema_version") != "blue_whale_private_anchors_v1":
        raise ValueError(
            "private anchors: schema_version must be blue_whale_private_anchors_v1"
        )
    a = raw["anchors"]
    db = a["W-DB150-DEV"]
    kw = float(db["turbine_units"]) * float(db["unit_rating_kw"])
    mult = float(db["unit_multiplier_usd"])
    oemh = a["B-OEMH"]
    values = {
        "W-DB150-DEV": float(db["turbine_equipment"]) * mult / kw,
        "W-DB150-DEV-BOP": (
            float(db["wind_plant_total"]) - float(db["turbine_equipment"])
        )
        * mult
        / kw,
        "B-OEMH": float(oemh["total_usd"]) / float(oemh["contracted_kwh"]),
    }
    dc_share = {
        name: float(a[name]["dc_block_usd"]) / float(a[name]["total_usd"])
        for name in ("B-OEMH", "B-ENV10", "B-ENV11")
    }
    return {"values": values, "dc_share": dc_share}


def run_capex(cfg: Mapping[str, Any], private_path: Optional[str]) -> Dict[str, Any]:
    """The blended capex (no private figure in the result)."""
    if not private_path:
        raise ValueError("private_anchors_path is required for the capex blend")
    path = Path(private_path).resolve()
    if REPO_ROOT.resolve() in path.parents:
        raise ValueError("private_anchors_path must be outside the repository")
    priv = private_anchor_values(yaml.safe_load(path.read_text(encoding="utf-8")))
    postures = parse_levy_postures(cfg["levy_postures"])
    fx = float(cfg["fx"]["cny_per_usd"])
    wind = wind_all_in(cfg["wind"], postures, fx, priv["values"])
    bess = bess_all_in(cfg["bess"], postures, fx, priv["values"], priv["dc_share"])
    land = float(cfg["bess"]["land_and_auxiliaries_share"])
    return {
        "disclosure_note": " ".join(str(cfg["disclosure_note"]).split()),
        "fx_cny_per_usd": fx,
        "wind_usd_per_kw": wind,
        "bess_usd_per_kwh_contracted": bess,
        "pricing_build_up_mode": pricing_build_up(bess["mode"], land),
        "levy_posture_by_case": {
            "wind": dict(cfg["wind"]["levy_posture"]),
            "bess": dict(cfg["bess"]["levy_posture"]),
        },
        "private_anchor_count": len(priv["values"]) + len(priv["dc_share"]),
    }


def run_solar(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """The solar resource summary and the cross-check table."""
    sr = cfg["solar_resource"]
    unit = yaml.safe_load(_repo_path(sr["unit_config"]).read_text(encoding="utf-8"))
    rs = unit["pv_yield"]["resource_solar"]
    array = unit["array"]
    gamma = float(unit["module"]["temp_coeff_pmax_pct_per_c"]) / 100.0
    tmy = _load_tmy(str(rs["tmy_path"]))
    common: Dict[str, Any] = dict(
        altitude_m=float(rs["altitude_m"]),
        timezone=str(rs["timezone"]),
        tilt_deg=float(array["tilt_deg"]),
        azimuth_deg=float(array["azimuth_deg"]),
        dc_mwp=float(sr["dc_mwp"]),
        ac_mw=float(sr["ac_mw"]),
        inverter_eff_nom=float(sr["inverter_eff_nom"]),
        gamma_pdc_per_c=gamma,
        system_loss_pct=float(rs["system_loss_pct"]),
        albedo=float(sr["albedo"]),
    )
    site = sr["site"]
    at_centroid = solar_resource_summary(
        tmy,
        latitude=float(site["latitude"]),
        longitude=float(site["longitude"]),
        **common,
    )
    at_tmy = solar_resource_summary(
        tmy, latitude=float(rs["latitude"]), longitude=float(rs["longitude"]), **common
    )
    producer = compute_solar_aep(
        SolarResourceConfig(
            latitude=float(rs["latitude"]),
            longitude=float(rs["longitude"]),
            annual_ghi_kwh_m2=float(rs["annual_ghi_kwh_m2"]),
            dc_capacity_mw=float(sr["dc_mwp"]),
            timezone=str(rs["timezone"]),
            altitude_m=float(rs["altitude_m"]),
            tilt_deg=float(array["tilt_deg"]),
            azimuth_deg=float(array["azimuth_deg"]),
            dc_ac_ratio=float(sr["dc_mwp"]) / float(sr["ac_mw"]),
            gamma_pdc_per_c=gamma,
            system_loss_pct=float(rs["system_loss_pct"]),
            inverter_eff_nom=float(sr["inverter_eff_nom"]),
            tmy_path=str(rs["tmy_path"]),
        )
    )
    stepped_gwh = at_tmy["annual"]["net_ac_mwh"] / 1000.0
    rel = abs(stepped_gwh - producer.annual_energy_gwh) / producer.annual_energy_gwh
    if rel > PRODUCER_PARITY:
        raise RuntimeError(f"stepped chain differs from the producer by {rel:.3e}")
    cc = sr["cross_checks"]
    ann = at_centroid["annual"]
    nasa = cc["nasa_power"]
    nasa_2015 = sum(nasa["annual_2015_2025_kwh_m2_day"]) / len(
        nasa["annual_2015_2025_kwh_m2_day"]
    )
    table: List[Dict[str, Any]] = [
        {
            "source": "pvlib on the frozen PVGIS-ERA5 TMY (this run)",
            "ghi_kwh_m2": ann["ghi_kwh_m2"],
            "dni_kwh_m2": ann["dni_kwh_m2"],
            "dhi_kwh_m2": ann["dhi_kwh_m2"],
            "poa_kwh_m2": ann["poa_kwh_m2"],
            "specific_yield_kwh_per_kwp": ann["specific_yield_kwh_per_kwp"],
        },
        {
            "source": "PVGIS 5.3 PVcalc, PVGIS-ERA5 2005-2023, 8 deg, 14% loss",
            "ghi_kwh_m2": None,
            "dni_kwh_m2": None,
            "dhi_kwh_m2": None,
            "poa_kwh_m2": cc["pvgis"]["h_i_y_kwh_m2"],
            "specific_yield_kwh_per_kwp": cc["pvgis"]["e_y_kwh_per_kwp"],
        },
        {
            "source": "Global Solar Atlas (Solargis 2.2.68), optimum tilt 9 deg, GSA losses",
            "ghi_kwh_m2": cc["global_solar_atlas"]["ghi_kwh_m2"],
            "dni_kwh_m2": cc["global_solar_atlas"]["dni_kwh_m2"],
            "dhi_kwh_m2": cc["global_solar_atlas"]["dif_kwh_m2"],
            "poa_kwh_m2": cc["global_solar_atlas"]["gti_opta_kwh_m2"],
            "specific_yield_kwh_per_kwp": cc["global_solar_atlas"]["pvout_kwh_per_kwp"],
        },
        {
            "source": "NASA POWER SYN1DEG climatology 2001-2025",
            "ghi_kwh_m2": nasa["ghi_kwh_m2_day"] * DAYS_PER_YEAR,
            "dni_kwh_m2": nasa["dni_kwh_m2_day"] * DAYS_PER_YEAR,
            "dhi_kwh_m2": nasa["dhi_kwh_m2_day"] * DAYS_PER_YEAR,
            "poa_kwh_m2": None,
            "specific_yield_kwh_per_kwp": None,
        },
        {
            "source": "NASA POWER SYN1DEG annual mean 2015-2025",
            "ghi_kwh_m2": nasa_2015 * DAYS_PER_YEAR,
            "dni_kwh_m2": None,
            "dhi_kwh_m2": None,
            "poa_kwh_m2": None,
            "specific_yield_kwh_per_kwp": None,
        },
    ]
    for row in table:
        for key in ("ghi_kwh_m2", "specific_yield_kwh_per_kwp", "poa_kwh_m2"):
            val, ref = row[key], table[0][key]
            row[f"{key}_vs_pvlib"] = None if val is None else val / ref - 1.0
    return {
        "site": {
            "pv_centroid": [float(site["latitude"]), float(site["longitude"])],
            "distance_to_turbine_m": _haversine_m(
                site["latitude"],
                site["longitude"],
                site["turbine_latitude"],
                site["turbine_longitude"],
            ),
            "distance_to_tmy_point_m": _haversine_m(
                site["latitude"],
                site["longitude"],
                site["tmy_latitude"],
                site["tmy_longitude"],
            ),
            "tmy_path": str(rs["tmy_path"]),
            "tmy_sha256": _sha256(_repo_path(str(rs["tmy_path"]))),
            "tmy_database": "PVGIS-ERA5 (2005-2023), per the PVGIS 5.3 TMY API metadata",
        },
        "array": {
            "module": unit["module"]["name"],
            "dc_mwp": float(sr["dc_mwp"]),
            "ac_mw": float(sr["ac_mw"]),
            "tilt_deg": float(array["tilt_deg"]),
            "azimuth_deg": float(array["azimuth_deg"]),
            "inverter_eff_nom": float(sr["inverter_eff_nom"]),
            "gamma_pdc_per_c": gamma,
            "system_loss_pct": float(rs["system_loss_pct"]),
            "transposition": "Hay-Davies",
            "cell_temperature": "Faiman",
        },
        "at_pv_centroid": at_centroid,
        "at_tmy_point": {
            "annual": at_tmy["annual"],
            "producer_annual_energy_gwh": producer.annual_energy_gwh,
            "relative_difference_to_producer": rel,
        },
        "cross_checks": table,
    }


def _write_monthly_csv(path: Path, solar: Mapping[str, Any]) -> None:
    rows = solar["at_pv_centroid"]["monthly"]
    gsa = solar["_gsa_monthly"]
    pvgis = solar["_pvgis_monthly"]
    nasa = solar["_nasa_monthly"]
    fields = [
        "month",
        "ghi_kwh_m2",
        "dni_kwh_m2",
        "dhi_kwh_m2",
        "poa_kwh_m2",
        "net_ac_mwh",
        "specific_yield_kwh_per_kwp",
        "performance_ratio",
        "pvgis_h_i_kwh_m2",
        "pvgis_e_kwh_per_kwp",
        "gsa_ghi_kwh_m2",
        "gsa_pvout_kwh_per_kwp",
        "nasa_ghi_kwh_m2_day",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(fields)
        for i, r in enumerate(rows):
            w.writerow(
                [int(r["month"])]
                + [repr(float(r[k])) for k in fields[1:8]]
                + [
                    repr(float(pvgis[0][i])),
                    repr(float(pvgis[1][i])),
                    repr(float(gsa[0][i])),
                    repr(float(gsa[1][i])),
                    repr(float(nasa[i])),
                ]
            )


@hydra.main(
    version_base=None,
    config_path="../conf",
    config_name="blue_whale_capex_solar_resource",
)
def main(cfg: DictConfig) -> None:
    """Run both parts and print one JSON object."""
    container = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(container, dict)
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    if raw.get("schema_version") != "blue_whale_capex_solar_resource_v1":
        raise ValueError("schema_version must be blue_whale_capex_solar_resource_v1")
    capex = run_capex(raw, raw.get("private_anchors_path"))
    solar = run_solar(raw)
    out_cfg = raw["output"]
    cfg_sha = _sha256(REPO_ROOT / "conf" / "blue_whale_capex_solar_resource.yaml")
    if out_cfg.get("capex_summary_json"):
        doc = {"config_sha256": cfg_sha, "cases": list(CASES), **capex}
        _repo_path(out_cfg["capex_summary_json"]).write_text(
            json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    if out_cfg.get("solar_summary_json"):
        doc = {"config_sha256": cfg_sha, **solar}
        _repo_path(out_cfg["solar_summary_json"]).write_text(
            json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    if out_cfg.get("solar_monthly_csv"):
        cc = raw["solar_resource"]["cross_checks"]
        _write_monthly_csv(
            _repo_path(out_cfg["solar_monthly_csv"]),
            {
                **solar,
                "_gsa_monthly": (
                    cc["global_solar_atlas"]["ghi_monthly_kwh_m2"],
                    cc["global_solar_atlas"]["pvout_monthly_kwh_per_kwp"],
                ),
                "_pvgis_monthly": (
                    cc["pvgis"]["h_i_m_kwh_m2"],
                    cc["pvgis"]["e_m_kwh_per_kwp"],
                ),
                "_nasa_monthly": cc["nasa_power"]["ghi_monthly_kwh_m2_day"],
            },
        )
    print(json.dumps({"capex": capex, "solar": solar}, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
