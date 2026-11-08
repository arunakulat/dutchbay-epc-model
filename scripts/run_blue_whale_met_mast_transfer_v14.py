#!/usr/bin/env python3
"""Hydra CLI: transfer met-mast export 617725 to the Blue Whale turbine and re-derive its yield.

Reads ``conf/blue_whale_met_mast_transfer.yaml`` and prints one JSON object of aggregates
(CLI-01, CLI-03). Three inputs come from outside the repository: the private 10-minute mast
export (hash-checked against the package's ``PRIVATE_SOURCE_MANIFEST.sha256``), the public
NASA POWER hourly reference (content-checked against the pins in the config) and the
confidential OEM power curve. No interval row, no hourly series derived from the mast, no
curve value and no hash of the curve is written or printed: only sector, monthly, diurnal,
bin and scalar aggregates leave the run.

The method lives in :mod:`analytics.wind.met_mast_transfer`; yield and the #1530 basis reuse
the siting CLI's helpers (``scripts/run_blue_whale_wind_siting_v14.py``) and
:mod:`wind_resource.bankable_aep`; the shadow-flicker expected case reuses
:mod:`analytics.gis.shadow_flicker`.

Usage::

    DUTCHBAY_MET_MAST_617725_SOURCE=/private/617725数据导出.txt \\
    DUTCHBAY_NASA_POWER_DIR=/path/to/power \\
    BLUE_WHALE_POWER_CURVE_CSV=/outside/the/repo/curve.csv \\
        .venv/bin/python scripts/run_blue_whale_met_mast_transfer_v14.py
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import logging
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import hydra
import numpy as np
import pandas as pd
import yaml
from omegaconf import DictConfig, OmegaConf

from analytics.wind import met_mast_transfer as mmt
from analytics.wind.losses_model import HOURS_PER_YEAR, apply_losses
from wind_resource.bankable_aep import (
    UncertaintyBudget,
    density_velocity_factor,
    exceedance_levels,
)
from wind_resource.weibull_fit import fit_weibull_on_series

REPO_ROOT = Path(__file__).resolve().parents[1]
SITING_SCRIPT = REPO_ROOT / "scripts" / "run_blue_whale_wind_siting_v14.py"
HOLD = (
    "HOLD: not lender-grade. A 232-day, monsoon-weighted, pre-filtered and undocumented "
    "mast record, transferred 26.7 km through a reanalysis to a placeholder site. The "
    "met-mast package's HOLD on annual, P50/P90 and lender use stands."
)


def _load_siting_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "blue_whale_wind_siting_cli", SITING_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SITING_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_clean(value: Any) -> Any:
    """Strict-JSON form: NaN and infinities become ``None``; numpy scalars become Python."""
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _dt(index: Any) -> pd.DatetimeIndex:
    """The index as a ``DatetimeIndex`` (typing aid; raises if it is not one)."""
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("expected a DatetimeIndex")
    return index


def _repo_path(rel: str) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else REPO_ROOT / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _outside_repo(raw: Optional[str], what: str, env: str) -> Path:
    if not raw:
        raise ValueError(f"No {what}: set {env} to a path outside the repository.")
    path = Path(raw).expanduser().resolve()
    if path.is_relative_to(REPO_ROOT.resolve()):
        raise ValueError(f"The {what} must be read from outside the repository.")
    if not path.exists():
        raise FileNotFoundError(f"{what} not found: {path}")
    return path


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def private_source_pin(manifest: Path) -> str:
    """The SHA-256 recorded in the package's private-source manifest (one entry)."""
    entries = [
        line.split()[0]
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    if len(entries) != 1:
        raise ValueError("private-source manifest must hold exactly one entry")
    return entries[0]


def load_mast(cfg: Mapping[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Read, verify and QC the private mast export.

    Returns:
        The QC'd assessment-window frame on the mast clock and a provenance record.

    Raises:
        ValueError: On a size or hash mismatch (the run's first stop condition).
    """
    path = _outside_repo(cfg["source_path"], "met-mast source", cfg["source_env"])
    expected = private_source_pin(_repo_path(cfg["private_manifest"]))
    size = path.stat().st_size
    actual = _sha256(path)
    if size != int(cfg["size_bytes"]) or actual != expected:
        raise ValueError(
            f"met-mast source does not match the package pin (size {size}, "
            f"sha256 {actual}); stopping"
        )
    frame = pd.read_csv(
        path, sep="\t", skiprows=int(cfg["header_lines"]), low_memory=False
    )
    frame.index = pd.DatetimeIndex(
        pd.to_datetime(frame.pop("Date/Time"), errors="raise")
    )
    start = pd.Timestamp(cfg["assessment_start_local"])
    frame = frame.loc[frame.index >= start].apply(pd.to_numeric, errors="raise")
    lo, hi = cfg["speed_range_ms"]
    flagged = 0
    for col in list(cfg["speed_avg"].values()) + list(cfg["speed_sd"].values()):
        bad = (frame[col] < lo) | (frame[col] > hi)
        flagged += int(bad.sum())
        frame.loc[bad, col] = np.nan
    dlo, dhi = cfg["direction_range_deg"]
    for col in (cfg["direction"], cfg["direction_120m"]):
        bad = (frame[col] < dlo) | (frame[col] > dhi)
        flagged += int(bad.sum())
        frame.loc[bad, col] = np.nan
    tlo, thi = cfg["temperature_valid_range_c"]
    for col in (cfg["temperature_10m_c"], cfg["temperature_120m_c"]):
        frame.loc[(frame[col] < tlo) | (frame[col] > thi), col] = np.nan
    return frame, {
        "sha256_verified": actual == expected,
        "sha256": actual,
        "size_bytes": size,
        "assessment_rows": int(len(frame)),
        "assessment_start_local": str(start),
        "assessment_end_local": str(frame.index.max()),
        "speed_or_direction_values_flagged_by_range": flagged,
    }


def parameter_digest(block: Mapping[str, Any]) -> str:
    """SHA-256 of a POWER ``properties.parameter`` block in canonical JSON."""
    raw = json.dumps(block, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_reference(cfg: Mapping[str, Any], point: str) -> pd.DataFrame:
    """Read and content-check one reference point's yearly POWER files.

    Raises:
        ValueError: On a digest mismatch, a fill value, a missing year or a point that
            is not where the config says.
    """
    base = _outside_repo(cfg["dir"], "NASA POWER directory", cfg["dir_env"])
    pcfg = cfg["points"][point]
    frames: List[pd.DataFrame] = []
    for year in range(int(cfg["first_year"]), int(cfg["last_year"]) + 1):
        doc = json.loads((base / pcfg["subdir"] / f"wsd_{year}.json").read_text())
        block = doc["properties"]["parameter"]
        if parameter_digest(block) != pcfg["parameter_sha256"][str(year)]:
            raise ValueError(f"reference {point} {year} does not match its pin")
        lon, lat = doc["geometry"]["coordinates"][:2]
        if (
            abs(lat - pcfg["latitude_deg_n"]) > 1e-3
            or abs(lon - pcfg["longitude_deg_e"]) > 1e-3
        ):
            raise ValueError(f"reference {point} {year} is not at the configured point")
        idx = pd.to_datetime(list(block["WS50M"]), format="%Y%m%d%H")
        f = pd.DataFrame({k: list(v.values()) for k, v in block.items()}, index=idx)
        if (f == -999.0).any().any():
            raise ValueError(f"reference {point} {year} carries fill values")
        frames.append(f)
    return pd.concat(frames)


# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------
def _uv(speed: pd.Series, direction: pd.Series) -> Tuple[pd.Series, pd.Series]:
    r = np.radians(direction)
    return -speed * np.sin(r), -speed * np.cos(r)


def timezone_evidence(
    mast: pd.DataFrame,
    ref: pd.DataFrame,
    mcfg: Mapping[str, Any],
    tcfg: Mapping[str, Any],
) -> Dict[str, Any]:
    """Recompute the clock-offset evidence and check the configured offset against it.

    Raises:
        ValueError: If the evidence does not support the configured offset (the run's
            timezone stop condition).
    """
    lon = float(mcfg["longitude_deg_e"])
    mi = _dt(mast.index)
    hour = mi.hour + mi.minute / 60.0
    p = mmt.harmonic_phase_hours(mast[mcfg["pressure_10m_kpa"]], hour, 12.0)
    t = mmt.harmonic_phase_hours(mast[mcfg["temperature_10m_c"]], hour, 24.0)
    implied = p["max_at_h"] - float(tcfg["s2_solar_time_of_maximum_h"]) + lon / 15.0
    by_month = []
    for _, g in mast.groupby(mi.month):
        if len(g) < 144 * 20:
            continue
        gi = _dt(g.index)
        hh = gi.hour + gi.minute / 60.0
        by_month.append(
            mmt.harmonic_phase_hours(g[mcfg["pressure_10m_kpa"]], hh, 12.0)["max_at_h"]
        )
    spd = mast[mcfg["speed_avg"]["100"]]
    sc = tcfg["scan_offsets_minutes"]
    scan = mmt.offset_correlation_scan(
        spd,
        ref["WS50M"],
        list(range(int(sc["start"]), int(sc["stop"]) + 1, int(sc["step"]))),
        int(mcfg["samples_per_hour"]),
    )
    best = max(scan, key=lambda r: r["pearson_r"])
    configured = int(tcfg["clock_offset_minutes"])
    at_cfg = next(r for r in scan if int(round(r["offset_h"] * 60)) == configured)
    ru, rv = _uv(ref["WS50M"], ref["WD50M"])
    candidates = []
    for off in tcfg["candidate_offsets_minutes"]:
        hr = mmt.hourly_means(
            mast,
            speed_columns={"v": mcfg["speed_avg"]["80"]},
            direction_columns={"d": mcfg["direction"]},
            clock_offset_minutes=int(off),
            samples_per_hour=int(mcfg["samples_per_hour"]),
        )
        mu, mv = _uv(hr["v"], hr["d"])
        w = int(tcfg["anomaly_window_h"])
        j = pd.concat(
            [
                mmt.subdaily_anomaly(mu, w),
                mmt.subdaily_anomaly(mv, w),
                mmt.subdaily_anomaly(ru, w),
                mmt.subdaily_anomaly(rv, w),
            ],
            axis=1,
            join="inner",
        ).dropna()
        j.columns = ["mu", "mv", "ru", "rv"]
        row = (
            next(r for r in scan if int(round(r["offset_h"] * 60)) == int(off))
            if any(int(round(r["offset_h"] * 60)) == int(off) for r in scan)
            else None
        )
        candidates.append(
            {
                "offset_h": int(off) / 60.0,
                "hourly_speed_r": None if row is None else row["pearson_r"],
                "subdaily_u_component_r": float(j.mu.corr(j.ru)),
                "subdaily_v_component_r": float(j.mv.corr(j.rv)),
                "s2_pressure_maximum_local_solar_h": (
                    p["max_at_h"] - int(off) / 60.0 + lon / 15.0
                )
                % 12.0,
                "temperature_maximum_local_solar_h": (
                    t["max_at_h"] - int(off) / 60.0 + lon / 15.0
                )
                % 24.0,
            }
        )
    ok_s2 = abs(implied - configured / 60.0) <= float(tcfg["s2_tolerance_h"])
    ok_r = best["pearson_r"] - at_cfg["pearson_r"] <= float(
        tcfg["correlation_tolerance"]
    )
    if not (ok_s2 and ok_r):
        raise ValueError(
            "the clock-offset evidence does not support the configured offset; stopping "
            f"(S2-implied {implied:.2f} h, correlation peak {best['offset_h']:.2f} h)"
        )
    return {
        "configured_clock_offset_h": configured / 60.0,
        "finding": "mast clock = UTC+05:30 (Sri Lanka Standard Time)",
        "s2_pressure_tide_maximum_mast_clock_h": p["max_at_h"],
        "s2_amplitude_kpa": p["amplitude"],
        "s2_maximum_mast_clock_h_by_month": by_month,
        "s2_assumed_local_solar_time_of_maximum_h": float(
            tcfg["s2_solar_time_of_maximum_h"]
        ),
        "s2_implied_clock_offset_h": implied,
        "temperature_10m_daily_maximum_mast_clock_h": t["max_at_h"],
        "hourly_speed_correlation_peak_offset_h": best["offset_h"],
        "hourly_speed_correlation_peak_r": best["pearson_r"],
        "hourly_speed_correlation_at_configured_offset": at_cfg["pearson_r"],
        "candidates": candidates,
        "checks": {"s2_within_tolerance": ok_s2, "correlation_within_tolerance": ok_r},
    }


# ---------------------------------------------------------------------------
# The transfer chain
# ---------------------------------------------------------------------------
def concurrent_hours(
    mast: pd.DataFrame, ref: pd.DataFrame, mcfg: Mapping[str, Any], offset_min: int
) -> pd.DataFrame:
    """Complete mast hours (UTC) joined to the reference at the mast."""
    hr = mmt.hourly_means(
        mast,
        speed_columns={f"v{h}": c for h, c in mcfg["speed_avg"].items()},
        direction_columns={"d80": mcfg["direction"], "d120": mcfg["direction_120m"]},
        clock_offset_minutes=offset_min,
        samples_per_hour=int(mcfg["samples_per_hour"]),
    )
    return hr.join(ref, how="inner")


def is_day(
    index_utc: pd.DatetimeIndex, offset_min: int, start_h: int, end_h: int
) -> np.ndarray:
    """Local-clock day flag for UTC hour starts (the hour's midpoint decides)."""
    local = index_utc + pd.Timedelta(minutes=offset_min + 30)
    h = local.hour
    return np.asarray((h >= start_h) & (h < end_h))


def correlation_gate(
    j: pd.DataFrame, col: str, cfg: Mapping[str, Any]
) -> Dict[str, float]:
    """Hourly and daily correlation; raise if either is below its threshold."""
    x = j[[col, "WS50M"]].dropna()
    r2 = mmt.pearson_r(x[col].to_numpy(), x["WS50M"].to_numpy()) ** 2
    daily = x.resample("1D").agg(["mean", "count"])
    keep = daily[(col, "count")] >= 18
    dm = daily.loc[keep]
    r_daily = mmt.pearson_r(
        dm[(col, "mean")].to_numpy(), dm[("WS50M", "mean")].to_numpy()
    )
    if r2 < float(cfg["min_hourly_r_squared"]) or r_daily < float(cfg["min_daily_r"]):
        raise ValueError(
            f"concurrent correlation too weak for a transfer at {col}: hourly R^2 "
            f"{r2:.3f}, daily r {r_daily:.3f}; stopping"
        )
    return {
        "hourly_r_squared": r2,
        "daily_r": r_daily,
        "days": int(keep.sum()),
        "hours": int(len(x)),
    }


class Chain:
    """One configured transfer: mast fit -> long-term -> 130 m -> turbine site."""

    def __init__(
        self,
        cfg: Mapping[str, Any],
        mast: pd.DataFrame,
        rm: pd.DataFrame,
        rt: pd.DataFrame,
    ) -> None:
        self.cfg = cfg
        self.mast = mast
        self.rm = rm
        self.rt = rt
        self.n = int(cfg["mcp"]["n_sectors"])

    def run(
        self,
        *,
        height: int,
        method: str,
        window: Sequence[int],
        offset_min: int,
        sectors: bool = True,
        exclude_month: Optional[int] = None,
        bias_correct_sparse: bool = False,
    ) -> Dict[str, Any]:
        """Run the chain and return the turbine-site long-term series and its tables."""
        c, m = self.cfg, self.cfg["mcp"]
        j = concurrent_hours(self.mast, self.rm, c["mast"], offset_min)
        col = f"v{height}"
        x = j.dropna(subset=[col, "WS50M", "WD50M"])
        if exclude_month is not None:
            x = x.loc[_dt(x.index).month != exclude_month]
        fits, omni = mmt.fit_sector_mcp(
            x[col].to_numpy(),
            x["WS50M"].to_numpy(),
            x["WD50M"].to_numpy(),
            n_sectors=self.n,
            method=method,
            min_sector_hours=int(m["min_sector_hours"]) if sectors else 10**9,
            min_sector_r_squared=float(m["min_sector_r_squared"]),
        )
        if bias_correct_sparse:
            # Sensitivity: a sector on the omnidirectional fallback that still holds a few
            # concurrent hours keeps the fallback slope but takes its own mean bias.
            floor = int(m["sparse_bias_min_hours"])
            fits = [
                (
                    dataclasses.replace(f, intercept=f.intercept + f.mean_bias_ms)
                    if f.source == "omni" and f.n >= floor
                    else f
                )
                for f in fits
            ]
        xd = j.dropna(subset=["d80", "WD50M"])
        if exclude_month is not None:
            xd = xd.loc[_dt(xd.index).month != exclude_month]
        veer, veer_omni, _ = mmt.sector_veer(
            xd["d80"].to_numpy(),
            xd["WD50M"].to_numpy(),
            n_sectors=self.n,
            min_sector_hours=int(m["min_sector_hours"]),
        )
        dq, _ = mmt.direction_residual_quantiles(
            xd["d80"].to_numpy(),
            xd["WD50M"].to_numpy(),
            n_sectors=self.n,
            min_sector_hours=int(m["min_sector_hours"]),
            n_quantiles=int(m["direction_quantiles"]),
        )
        s = c["shear"]
        sh = j.dropna(subset=["v100", "v120", "d80"])
        shear = mmt.shear_table(
            sh["v100"].to_numpy(),
            sh["v120"].to_numpy(),
            sh["d80"].to_numpy(),
            is_day(
                _dt(sh.index),
                offset_min,
                int(s["day_start_local_h"]),
                int(s["day_end_local_h"]),
            ),
            h_low=float(s["low_height_m"]),
            h_high=float(s["high_height_m"]),
            n_sectors=self.n,
            min_cell_hours=int(s["min_cell_hours"]),
            min_speed_ms=float(s["min_speed_ms"]),
        )
        y0, y1 = int(window[0]), int(window[1])
        years = _dt(self.rm.index).year
        lt_m = self.rm.loc[(years >= y0) & (years <= y1)]
        lt_t = self.rt.loc[lt_m.index]
        ref_d = lt_m["WD50M"].to_numpy()
        v_hour = mmt.predict_by_sector(lt_m["WS50M"].to_numpy(), ref_d, fits)
        src, d_mast = mmt.expand_by_direction_quantiles(ref_d, dq)
        index = lt_m.index[src]
        sec_ref = mmt.sector_index(ref_d, self.n)[src]
        day = is_day(
            _dt(index),
            offset_min,
            int(s["day_start_local_h"]),
            int(s["day_end_local_h"]),
        )
        v130 = mmt.apply_shear(
            v_hour[src],
            d_mast,
            day,
            shear["alpha"],
            h_from=float(height),
            h_to=float(s["hub_height_m"]),
        )
        ratio, ratio_omni = mmt.sector_speed_ratio(
            lt_t["WS50M"].to_numpy(),
            lt_m["WS50M"].to_numpy(),
            ref_d,
            n_sectors=self.n,
            min_sector_hours=int(c["transfer"]["min_sector_hours"]),
        )
        tveer, tveer_omni, _ = mmt.sector_veer(
            lt_t["WD50M"].to_numpy(),
            ref_d,
            n_sectors=self.n,
            min_sector_hours=int(c["transfer"]["min_sector_hours"]),
        )
        v_site = v130 * ratio[sec_ref]
        d_site = np.mod(d_mast + mmt.continuous_veer(ref_d, tveer)[src], 360.0)
        # In-sample check of the direction method: the measured 80 m rose over the
        # concurrent hours against the rose the method predicts from the reference.
        csrc, cdir = mmt.expand_by_direction_quantiles(xd["WD50M"].to_numpy(), dq)
        obs = mmt.sector_frequencies(xd["d80"].to_numpy(), self.n)
        pred = mmt.sector_frequencies(cdir, self.n)
        mean_veer = mmt.sector_frequencies(
            xd["WD50M"].to_numpy()
            + veer[mmt.sector_index(xd["WD50M"].to_numpy(), self.n)],
            self.n,
        )
        return {
            "fits": fits,
            "omni": omni,
            "concurrent": x,
            "veer": veer,
            "veer_omni": veer_omni,
            "direction_quantiles": dq,
            "shear": shear,
            "ratio": ratio,
            "ratio_omni": ratio_omni,
            "transfer_veer": tveer,
            "transfer_veer_omni": tveer_omni,
            "index": index,
            "speed": v_site,
            "direction": d_site,
            "speed_mast_130": v130,
            "direction_mast": d_mast,
            "lt_ref_mast": lt_m,
            "copies": int(m["direction_quantiles"]),
            "speed_mast_measured_height": v_hour,
            "direction_check": {
                "observed_80m": obs.tolist(),
                "quantile_method": pred.tolist(),
                "mean_veer_only": mean_veer.tolist(),
                "max_abs_error_quantile_method": float(np.abs(pred - obs).max()),
                "max_abs_error_mean_veer_only": float(np.abs(mean_veer - obs).max()),
            },
        }


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------
def fit_rows(fits: Sequence[mmt.SectorFit]) -> List[Dict[str, Any]]:
    """JSON rows of the sector fits."""
    return [
        {
            "sector": f.sector,
            "label": mmt.COMPASS_16[f.sector] if f.sector >= 0 else "omni",
            "n_hours": f.n,
            "source": f.source,
            "slope": f.slope,
            "intercept_ms": f.intercept,
            "r_squared": f.r_squared,
            "residual_std_ms": f.residual_std_ms,
            "mean_bias_ms": f.mean_bias_ms,
            "mast_mean_ms": f.mast_mean_ms,
            "reference_mean_ms": f.reference_mean_ms,
        }
        for f in fits
    ]


def local_index(index_utc: pd.DatetimeIndex, offset_min: int) -> pd.DatetimeIndex:
    """UTC hour starts to local hour starts."""
    return index_utc + pd.Timedelta(minutes=offset_min)


def measured_profiles(mast: pd.DataFrame, mcfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Shear profile, day/night and diurnal means measured at the mast (mast clock)."""
    cols = mcfg["speed_avg"]
    common = mast.dropna(subset=list(cols.values()))
    heights = [float(h) for h in cols]
    means = [float(common[c].mean()) for c in cols.values()]
    sec = mmt.sector_index(common[mcfg["direction"]].to_numpy(), 16)
    by_sector = []
    for s in range(16):
        g = common[sec == s]
        by_sector.append(
            {
                "sector": s,
                "label": mmt.COMPASS_16[s],
                "n_10min": int(len(g)),
                "mean_ms_by_height": {
                    h: (float(g[c].mean()) if len(g) else None) for h, c in cols.items()
                },
                "alpha_100_120": (
                    mmt.shear_exponent(
                        float(g[cols["100"]].mean()),
                        float(g[cols["120"]].mean()),
                        100,
                        120,
                    )
                    if len(g) >= 600
                    else None
                ),
            }
        )
    ci = _dt(common.index)
    day = (ci.hour >= 6) & (ci.hour < 18)
    dn = {}
    for name, sel in (("day", day), ("night", ~day)):
        g = common[sel]
        dn[name] = {
            "n_10min": int(len(g)),
            "mean_ms_by_height": {h: float(g[c].mean()) for h, c in cols.items()},
            "alpha_log_fit_30_120": mmt.log_law_fit_exponent(
                heights, [float(g[c].mean()) for c in cols.values()]
            ),
            "alpha_100_120": mmt.shear_exponent(
                float(g[cols["100"]].mean()), float(g[cols["120"]].mean()), 100, 120
            ),
        }
    diurnal = {}
    for h in ("100", "120"):
        s = mast[cols[h]].dropna()
        diurnal[h] = mmt.profile_means(s.to_numpy(), s.index.hour, list(range(24)))
    return {
        "basis": "10-minute rows with all five mean speeds present, assessment window",
        "n_10min": int(len(common)),
        "heights_m": heights,
        "concurrent_mean_ms": means,
        "alpha_log_fit_30_120": mmt.log_law_fit_exponent(heights, means),
        "alpha_log_fit_80_120": mmt.log_law_fit_exponent(heights[2:], means[2:]),
        "alpha_100_120": mmt.shear_exponent(means[3], means[4], 100, 120),
        "by_sector_80m_direction": by_sector,
        "day_night_local_06_18": dn,
        "diurnal_mean_ms_by_local_hour": diurnal,
    }


def air_density(
    mast: pd.DataFrame, mcfg: Mapping[str, Any], hub_m: float
) -> Dict[str, Any]:
    """Mean moist-air density at hub height from the mast's pressure, temperature and RH."""
    p = mast[mcfg["pressure_10m_kpa"]] * 1000.0
    t120 = mast[mcfg["temperature_120m_c"]]
    t10 = mast[mcfg["temperature_10m_c"]]
    rh = mast[mcfg["humidity_10m_pct"]].clip(0, 100)
    ok = p.notna() & t120.notna() & t10.notna() & rh.notna() & (p > 90000)
    e = rh[ok] / 100.0 * 610.94 * np.exp(17.625 * t10[ok] / (t10[ok] + 243.04))
    q_ratio = 0.622 * e / (p[ok] - 0.378 * e)
    tk = t120[ok] + 273.15
    tv = tk * (1 + 0.61 * q_ratio)
    p_hub = p[ok] * np.exp(-9.80665 * (hub_m - 10.0) / (287.05 * tv))
    rho = p_hub / (287.05 * tv)
    return {
        "basis": "p(10 m) moved hydrostatically to hub height, T(120 m), humidity from RH(10 m) at T(10 m)",
        "n_10min": int(ok.sum()),
        "mean_kgm3": float(rho.mean()),
        "monthly_mean_kgm3": {
            str(k): float(v) for k, v in rho.groupby(rho.index.month).mean().items()
        },
        "note": "covers 21 March - 8 November only (hot months); not an annual mean",
    }


# ---------------------------------------------------------------------------
# Rose figure and table
# ---------------------------------------------------------------------------
def write_rose_csv(path: Path, rose: Sequence[Mapping[str, Any]], header: str) -> None:
    """Write the 16-sector rose (aggregates only)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {header}"]
    lines.append(
        "sector,label,centre_deg,frequency,mean_speed_ms,weibull_a_ms,weibull_k,energy_share"
    )
    for r in rose:
        lines.append(
            f"{r['sector']},{r['label']},{r['centre_deg']:.1f},{r['frequency']:.6f},"
            f"{r['mean_speed_ms']:.4f},{r['weibull_a_ms']:.4f},{r['weibull_k']:.4f},{r['energy_share']:.6f}"
        )
    path.write_text("\n".join(lines) + "\n")


def write_rose_png(path: Path, rose: Sequence[Mapping[str, Any]], footer: str) -> None:
    """Two single-series polar panels: frequency and wind-energy share by sector."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, muted, series = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6"
    theta = np.radians([r["centre_deg"] for r in rose])
    width = np.radians(360.0 / len(rose)) * 0.86
    fig, axes = plt.subplots(
        1, 2, subplot_kw={"projection": "polar"}, figsize=(8.0, 4.6), dpi=90
    )
    fig.patch.set_facecolor(surface)
    for ax, key, title in (
        (axes[0], "frequency", "Frequency of hours (%)"),
        (axes[1], "energy_share", "Share of wind energy, v³ (%)"),
    ):
        vals = np.array([100.0 * r[key] for r in rose])
        ax.set_facecolor(surface)
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_axisbelow(True)
        ax.bar(theta, vals, width=width, color=series, edgecolor=surface, linewidth=1.0)
        ax.set_xticks(theta[::2])
        ax.set_xticklabels([r["label"] for r in rose][::2], color=muted, fontsize=8)
        ax.tick_params(axis="y", colors=muted, labelsize=7)
        ax.grid(color="#d9d8d3", linewidth=0.5)
        ax.spines["polar"].set_color("#d9d8d3")
        ax.set_title(title, color=ink, fontsize=10, pad=12)
        top = int(np.argmax(vals))
        ax.annotate(
            f"{rose[top]['label']} {vals[top]:.1f}%",
            xy=(theta[top], vals[top]),
            xytext=(theta[top], vals[top] * 1.12),
            color=ink,
            fontsize=8,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.2", "fc": surface, "ec": "none"},
        )
        ax.set_ylim(0, vals.max() * 1.25)
    fig.suptitle(
        "Blue Whale turbine site, 130 m, long-term (MCP of met mast 617725)",
        color=ink,
        fontsize=11,
    )
    fig.text(0.5, 0.015, footer, ha="center", color=muted, fontsize=6.5, wrap=True)
    fig.subplots_adjust(left=0.05, right=0.95, top=0.82, bottom=0.12, wspace=0.35)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=surface, metadata={"Software": None})
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------
def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:  # noqa: C901 - one linear pipeline
    """Run the transfer, yield, uncertainty and flicker; return the JSON summary."""
    siting = _load_siting_cli()
    mcfg, tz = cfg["mast"], cfg["timezone"]
    mast, mast_prov = load_mast(mcfg)
    rm = load_reference(cfg["reference"], "mast")
    rt = load_reference(cfg["reference"], "turbine")
    tz_ev = timezone_evidence(mast, rm, mcfg, tz)
    off = int(tz["clock_offset_minutes"])
    m = cfg["mcp"]
    chain = Chain(cfg, mast, rm, rt)
    window = m["long_term_window"]
    prim_h, sens_h = int(m["primary_height_m"]), int(m["sensitivity_height_m"])

    j = concurrent_hours(mast, rm, mcfg, off)
    gates = {f"{h}m": correlation_gate(j, f"v{h}", m) for h in (prim_h, sens_h)}
    base = chain.run(height=prim_h, method=m["method"], window=window, offset_min=off)
    x = base["concurrent"]
    campaign = mmt.campaign_record(
        x[f"v{prim_h}"].to_numpy(),
        x["WS50M"].to_numpy(),
        base["lt_ref_mast"]["WS50M"].to_numpy(),
        m["method"],
    )
    v, d, idx = base["speed"], base["direction"], base["index"]
    n = int(m["n_sectors"])
    rose = mmt.sector_rose(v, d, n)
    for r in rose:  # equivalent hours: each long-term hour is carried as K equal copies
        r["hours"] = r["hours"] / base["copies"]
    omni_fit = fit_weibull_on_series(pd.DataFrame({"v": v}), ws_column="v")
    loc = local_index(idx, off)
    monthly = mmt.profile_means(v, loc.month, list(range(1, 13)))
    diurnal = mmt.profile_means(v, loc.hour, list(range(24)))
    # Calendar years in UTC: the window is whole UTC years, so a local-time year
    # would leave a five-hour fragment at the end.
    annual = pd.Series(v, index=idx).groupby(idx.year).mean()
    iav_cov = float(annual.std(ddof=1) / annual.mean())

    # Yield (#1530's density and loss stack, from the siting config's source scenario)
    s_cfg = yaml.safe_load(_repo_path(cfg["turbine"]["siting_config"]).read_text())
    basis = siting.resource_basis(s_cfg["resource"])
    t_cfg = cfg["turbine"]
    ws, pw = siting.load_private_power_curve(t_cfg["power_curve_csv"])
    clipped = siting.derate_by_clipping(pw, float(t_cfg["rated_power_kw"]))
    factor = density_velocity_factor(
        basis["air_density_site_kgm3"], float(t_cfg["power_curve_air_density_kgm3"])
    )
    cap_mw = float(t_cfg["rated_power_kw"]) / 1000.0

    def gross_of(r: Sequence[Mapping[str, Any]]) -> float:
        return mmt.sector_weighted_gross_aep_gwh(r, ws, clipped, factor)

    def net(gross: float) -> float:
        return float(apply_losses(gross, basis["losses"]).net_aep_gwh)

    def cf(aep: float) -> float:
        return aep * 1000.0 / (cap_mw * HOURS_PER_YEAR)

    gross = gross_of(rose)
    gross_ts = mmt.time_series_gross_aep_gwh(v, ws, clipped, factor)
    omni_yield = siting.single_turbine_yield(
        ws,
        pw,
        derated_power_kw=float(t_cfg["rated_power_kw"]),
        weibull_a_hub=omni_fit.weibull_a,
        weibull_k=omni_fit.weibull_k,
        rho_site_kgm3=basis["air_density_site_kgm3"],
        rho_curve_kgm3=float(t_cfg["power_curve_air_density_kgm3"]),
        losses=basis["losses"],
        integrator_tolerance_pct=float(t_cfg["integrator_tolerance_pct"]),
    )
    net_p50 = net(gross)
    a_hub_1530 = siting.weibull_scale_at_height(
        basis["weibull_a_ref_ms"],
        basis["reference_height_m"],
        130.0,
        basis["shear_exponent"],
    )
    era5 = siting.single_turbine_yield(
        ws,
        pw,
        derated_power_kw=float(t_cfg["rated_power_kw"]),
        weibull_a_hub=a_hub_1530,
        weibull_k=basis["weibull_k"],
        rho_site_kgm3=basis["air_density_site_kgm3"],
        rho_curve_kgm3=float(t_cfg["power_curve_air_density_kgm3"]),
        losses=basis["losses"],
        integrator_tolerance_pct=float(t_cfg["integrator_tolerance_pct"]),
    )
    producing = ws[clipped > 0]
    cut_in, cut_out = float(producing.min()) / factor, float(ws.max()) / factor
    p_op_1530 = siting.operating_probability(
        ws, pw, a_hub_1530, basis["weibull_k"], factor
    )
    operating = mmt.operating_fraction(v, cut_in, cut_out)
    del pw  # only the clipped curve is used below, and only inside this run

    def scaled_gross(scale: float) -> float:
        return gross_of(
            [{**r, "weibull_a_ms": (r["weibull_a_ms"] or 0.0) * scale} for r in rose]
        )

    sens_s = mmt.energy_sensitivity(scaled_gross)

    # Sensitivities
    def summarise(res: Dict[str, Any]) -> Dict[str, float]:
        r = mmt.sector_rose(res["speed"], res["direction"], n)
        g = gross_of(r)
        return {
            "mean_speed_ms": float(np.mean(res["speed"])),
            "gross_aep_gwh": g,
            "net_aep_gwh": net(g),
            "net_capacity_factor": cf(net(g)),
        }

    sens: Dict[str, Dict[str, float]] = {}
    sens["primary"] = summarise(base)
    sens[f"height_{sens_h}m"] = summarise(
        chain.run(height=sens_h, method=m["method"], window=window, offset_min=off)
    )
    sens["method_" + m["sensitivity_method"]] = summarise(
        chain.run(
            height=prim_h, method=m["sensitivity_method"], window=window, offset_min=off
        )
    )
    sens["omnidirectional_transfer"] = summarise(
        chain.run(
            height=prim_h,
            method=m["method"],
            window=window,
            offset_min=off,
            sectors=False,
        )
    )
    for w in m["sensitivity_windows"]:
        sens[f"window_{w[0]}_{w[1]}"] = summarise(
            chain.run(height=prim_h, method=m["method"], window=w, offset_min=off)
        )
    for o in tz["sensitivity_offsets_minutes"]:
        sens[f"clock_offset_{int(o)}min"] = summarise(
            chain.run(
                height=prim_h, method=m["method"], window=window, offset_min=int(o)
            )
        )
    no_transfer = dict(base)
    no_transfer["speed"] = base["speed_mast_130"]
    no_transfer["direction"] = base["direction_mast"]
    sens["no_site_transfer_mast_at_130m"] = summarise(no_transfer)
    rho_mast = air_density(mast, mcfg, 130.0)["mean_kgm3"]
    f_mast = density_velocity_factor(
        rho_mast, float(t_cfg["power_curve_air_density_kgm3"])
    )
    g_rho = mmt.sector_weighted_gross_aep_gwh(rose, ws, clipped, f_mast)
    sens["air_density_mast_record_mean"] = {
        "air_density_kgm3": rho_mast,
        "mean_speed_ms": float(np.mean(v)),
        "gross_aep_gwh": g_rho,
        "net_aep_gwh": net(g_rho),
        "net_capacity_factor": cf(net(g_rho)),
    }
    sparse = chain.run(
        height=prim_h,
        method=m["method"],
        window=window,
        offset_min=off,
        bias_correct_sparse=True,
    )
    sens["sparse_sector_bias_corrected"] = summarise(sparse)
    jk_months = sorted(set(x.index.month))
    jk = [
        float(
            np.mean(
                chain.run(
                    height=prim_h,
                    method=m["method"],
                    window=window,
                    offset_min=off,
                    exclude_month=mo,
                )["speed"]
            )
        )
        for mo in jk_months
    ]

    # Uncertainty (speed % -> energy % by the sensitivity)
    u = cfg["uncertainty"]
    mean_v = float(np.mean(v))
    omni = base["omni"]
    days = gates[f"{prim_h}m"]["days"]
    corr_pct = 100.0 * omni.residual_std_ms / math.sqrt(days) / omni.mast_mean_ms
    season_pct = 100.0 * mmt.jackknife_std(jk) / mean_v
    wins = [sens["primary"]["mean_speed_ms"]] + [
        sens[f"window_{w[0]}_{w[1]}"]["mean_speed_ms"] for w in m["sensitivity_windows"]
    ]
    window_pct = math.hypot(
        100.0 * (max(wins) - min(wins)) / 2.0 / mean_v,
        100.0 * iav_cov / math.sqrt(len(annual)),
    )
    tz_vals = [
        sens[f"clock_offset_{int(o)}min"]["mean_speed_ms"]
        for o in tz["sensitivity_offsets_minutes"]
    ]
    tz_pct = 100.0 * (max(tz_vals) - min(tz_vals)) / 2.0 / mean_v
    alpha = np.asarray(base["shear"]["alpha"], dtype=float)
    cnt = np.asarray(base["shear"]["n"], dtype=float)
    a_mean = float((alpha * cnt).sum() / cnt.sum())
    a_std = float(math.sqrt((((alpha - a_mean) ** 2) * cnt).sum() / cnt.sum()))
    shear_pct = 100.0 * math.log(130.0 / 120.0) * a_std
    method_e_pct = (
        100.0
        * abs(
            sens["primary"]["net_aep_gwh"]
            - sens["method_" + m["sensitivity_method"]]["net_aep_gwh"]
        )
        / 2.0
        / net_p50
    )
    sparse_e_pct = (
        100.0
        * abs(
            sens["primary"]["net_aep_gwh"]
            - sens["sparse_sector_bias_corrected"]["net_aep_gwh"]
        )
        / net_p50
    )
    lt_e = math.sqrt(
        (sens_s * corr_pct) ** 2
        + (sens_s * season_pct) ** 2
        + (sens_s * window_pct) ** 2
        + (sens_s * tz_pct) ** 2
        + method_e_pct**2
        + sparse_e_pct**2
    )
    budget = UncertaintyBudget(
        wind_measurement_pct=sens_s * float(u["measurement_speed_pct"]),
        long_term_pct=lt_e,
        vertical_extrapolation_pct=sens_s * shear_pct,
        horizontal_flow_pct=sens_s * float(u["transfer_speed_pct"]),
        power_curve_pct=float(u["power_curve_energy_pct"]),
        wake_model_pct=0.0,
        interannual_variability_pct=sens_s * 100.0 * iav_cov,
    )
    exc = exceedance_levels(
        net_p50,
        budget,
        life_years=int(u["life_years"]),
        correlation=float(u["inter_category_correlation"]),
    )
    resource_only = math.sqrt(
        budget.wind_measurement_pct**2
        + lt_e**2
        + budget.vertical_extrapolation_pct**2
        + budget.horizontal_flow_pct**2
    )

    evidence = change_evidence(
        base=base,
        x=x,
        prim_h=prim_h,
        off=off,
        era5=era5,
        a_hub_1530=a_hub_1530,
        k_1530=float(basis["weibull_k"]),
        omni_fit=omni_fit,
        rose=rose,
        gross_of=gross_of,
        net=net,
        cf=cf,
        sens=sens,
        ws=ws,
        clipped=clipped,
        factor=factor,
    )

    # Shadow flicker: worst case, #1530's expected case, and the oriented expected case
    flicker = shadow_flicker(cfg, s_cfg, v, d, loc, operating, p_op_1530)

    # Turbulence (10-minute aggregates)
    tcfg = cfg["turbulence"]
    ti = {}
    for h in ("100", "120"):
        ti[f"{h}m"] = mmt.turbulence_table(
            mast[mcfg["speed_avg"][h]].to_numpy(),
            mast[mcfg["speed_sd"][h]].to_numpy(),
            mast[mcfg["direction"]].to_numpy(),
            bin_edges_ms=tcfg["bin_edges_ms"],
            n_sectors=n,
            min_speed_ms=float(tcfg["min_speed_ms"]),
            min_count=int(tcfg["min_count"]),
        )

    version = (REPO_ROOT / "VERSION").read_text().strip()
    out: Dict[str, Any] = {
        "schema": "dutchbay.epc.blue_whale_met_mast_transfer.v1",
        "model_version": version,
        "config": "conf/blue_whale_met_mast_transfer.yaml",
        "hold": HOLD,
        "work_item": "https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6556910250",
        "mast_source": {**mast_prov, "manifest": mcfg["private_manifest"]},
        "reference": {
            k: cfg["reference"][k]
            for k in (
                "name",
                "api",
                "request",
                "api_version",
                "retrieved",
                "height_m",
                "first_year",
                "last_year",
            )
        },
        "timezone": tz_ev,
        "mcp": {
            "method": m["method"],
            "n_sectors": n,
            "sectored_by": "reference (MERRA-2 WD50M at the mast cell) direction",
            "target_height_m": prim_h,
            "correlation_gates": gates,
            "campaign": campaign,
            "omni": fit_rows([base["omni"]])[0],
            "sectors": fit_rows(base["fits"]),
            "direction_veer_mast80_minus_reference_deg": base["veer"].tolist(),
            "direction_veer_omni_deg": base["veer_omni"],
            "direction_residual_quantiles_deg": base["direction_quantiles"].tolist(),
            "direction_method_check_concurrent": base["direction_check"],
            "concurrent_months": jk_months,
        },
        "site_transfer": {
            "basis": "MERRA-2 turbine cell / mast cell, by mast-cell direction sector, long-term window",
            "speed_ratio_by_sector": base["ratio"].tolist(),
            "speed_ratio_omni": base["ratio_omni"],
            "direction_veer_by_sector_deg": base["transfer_veer"].tolist(),
            "direction_veer_omni_deg": base["transfer_veer_omni"],
        },
        "shear": {
            "extrapolation": base["shear"],
            "measured": measured_profiles(mast, mcfg),
        },
        "long_term_130m": {
            "window": list(window),
            "hours": int(len(v)) // base["copies"],
            "direction_copies_per_hour": base["copies"],
            "mean_speed_ms": mean_v,
            "weibull_a_ms": omni_fit.weibull_a,
            "weibull_k": omni_fit.weibull_k,
            "weibull_mean_ms": mmt.weibull_mean(omni_fit.weibull_a, omni_fit.weibull_k),
            "weibull_energy_gof_pct": omni_fit.energy_gof_pct,
            "annual_mean_ms": {str(k): float(val) for k, val in annual.items()},
            "interannual_cov": iav_cov,
            "rose": rose,
            "monthly_mean_ms_local": monthly,
            "diurnal_mean_ms_local_hour": diurnal,
        },
        "turbulence": ti,
        "air_density": {
            **air_density(mast, mcfg, 130.0),
            "model_value_kgm3": basis["air_density_site_kgm3"],
        },
        "yield": {
            "basis": "frequency-weighted sector Weibulls at 130 m; curve clipped at 9.5 MW; #1530 density and losses",
            "gross_aep_gwh": gross,
            "net_aep_gwh": net_p50,
            "gross_capacity_factor": cf(gross),
            "net_capacity_factor": cf(net_p50),
            "total_loss_pct": float(
                apply_losses(gross, basis["losses"]).total_loss_pct
            ),
            "cross_check_time_series_gross_aep_gwh": gross_ts,
            "cross_check_omni_weibull_gross_aep_gwh": omni_yield["gross_aep_gwh"],
            "omni_weibull_integrator_gap_pct": omni_yield["integrator_gap_pct"],
            "operating_fraction": float(operating.mean()),
            "speed_to_energy_sensitivity": sens_s,
            "era5_weibull_basis_1530": {
                "weibull_a_130m_ms": a_hub_1530,
                "weibull_k": basis["weibull_k"],
                "mean_speed_130m_ms": mmt.weibull_mean(a_hub_1530, basis["weibull_k"]),
                "gross_aep_gwh": era5["gross_aep_gwh"],
                "net_aep_gwh": era5["net_aep_gwh"],
                "net_capacity_factor": era5["net_capacity_factor"],
                "operating_probability": p_op_1530,
            },
        },
        "sensitivities": sens,
        "change_evidence": evidence,
        "uncertainty": {
            "speed_pct": {
                "measurement": float(u["measurement_speed_pct"]),
                "mcp_correlation": corr_pct,
                "concurrency_seasonal_jackknife": season_pct,
                "long_term_window": window_pct,
                "clock_offset": tz_pct,
                "shear_extrapolation": shear_pct,
                "transfer_distance": float(u["transfer_speed_pct"]),
            },
            "energy_pct": {
                "mcp_method": method_e_pct,
                "sparse_sector_extrapolation": sparse_e_pct,
                "long_term_combined": lt_e,
                "resource_combined": resource_only,
                "budget": {k: getattr(budget, k) for k in budget.__dataclass_fields__},
            },
            "jackknife_month_mean_speed_ms": dict(
                zip([str(x_) for x_ in jk_months], jk, strict=True)
            ),
            "sigma_1yr_pct": exc.sigma_1yr_pct,
            "sigma_life_pct": exc.sigma_life_pct,
            "p50_net_gwh": exc.p50_gwh,
            "p75_1yr_net_gwh": exc.p75_gwh,
            "p90_1yr_net_gwh": exc.p90_1yr_gwh,
            "p90_life_net_gwh": exc.p90_life_gwh,
            "life_years": exc.life_years,
        },
        "shadow_flicker": flicker,
    }
    out = json_clean(out)
    o = cfg["output"]
    footer = (
        f"{HOLD} Model {version}; config conf/blue_whale_met_mast_transfer.yaml; "
        "scenario scenarios/blue_whale_wind_lot5b_2026.yaml."
    )
    if o.get("rose_csv"):
        write_rose_csv(
            _repo_path(o["rose_csv"]),
            rose,
            f"Blue Whale 130 m long-term wind rose (aggregates). Model {version}. "
            "conf/blue_whale_met_mast_transfer.yaml. " + HOLD,
        )
    if o.get("rose_png"):
        write_rose_png(_repo_path(o["rose_png"]), rose, footer)
    if o.get("summary_json"):
        p = _repo_path(o["summary_json"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1, sort_keys=True, allow_nan=False) + "\n")
    return out


def change_evidence(
    *,
    base: Mapping[str, Any],
    x: pd.DataFrame,
    prim_h: int,
    off: int,
    era5: Mapping[str, Any],
    a_hub_1530: float,
    k_1530: float,
    omni_fit: Any,
    rose: Sequence[Mapping[str, Any]],
    gross_of: Callable[[Sequence[Mapping[str, Any]]], float],
    net: Callable[[float], float],
    cf: Callable[[float], float],
    sens: Mapping[str, Mapping[str, float]],
    ws: np.ndarray,
    clipped: np.ndarray,
    factor: float,
) -> Dict[str, Any]:
    """Decompose the change from #1530's ERA5 basis and show the long-term correction.

    Steps change one thing at a time, each through the same density and loss stack:
    #1530's ERA5 Weibull; its shape with the new long-term mean; the new omnidirectional
    Weibull; the new sector Weibulls. The long-term correction is shown month by month,
    because the transfer is applied hour by hour to every long-term hour, so each calendar
    month enters with its own reference hours and calendar weight.
    """
    from analytics.wind.aep_tornado import gross_aep_farm_gwh

    def omni_net(a: float, k: float) -> float:
        return net(gross_aep_farm_gwh(a, k, ws / factor, clipped, 1))

    mean_new = float(np.mean(base["speed"]))
    a_shape = mean_new / math.gamma(1.0 + 1.0 / k_1530)
    steps = [
        {
            "step": "1530 ERA5 Weibull at 130 m",
            "mean_speed_ms": mmt.weibull_mean(a_hub_1530, k_1530),
            "weibull_a_ms": a_hub_1530,
            "weibull_k": k_1530,
            "net_aep_gwh": float(era5["net_aep_gwh"]),
        },
        {
            "step": "ERA5 shape (k) with the transferred long-term mean speed",
            "mean_speed_ms": mean_new,
            "weibull_a_ms": a_shape,
            "weibull_k": k_1530,
            "net_aep_gwh": omni_net(a_shape, k_1530),
        },
        {
            "step": "transferred long-term omnidirectional Weibull",
            "mean_speed_ms": mmt.weibull_mean(omni_fit.weibull_a, omni_fit.weibull_k),
            "weibull_a_ms": omni_fit.weibull_a,
            "weibull_k": omni_fit.weibull_k,
            "net_aep_gwh": omni_net(omni_fit.weibull_a, omni_fit.weibull_k),
        },
        {
            "step": "transferred long-term 16 sector Weibulls (primary)",
            "mean_speed_ms": mean_new,
            "net_aep_gwh": net(gross_of(rose)),
        },
    ]
    for i, st in enumerate(steps):
        st["net_capacity_factor"] = cf(st["net_aep_gwh"])
        st["delta_from_previous_gwh"] = (
            0.0 if i == 0 else st["net_aep_gwh"] - steps[i - 1]["net_aep_gwh"]
        )

    # Speed level, in the order the chain builds it.
    v_h = base["speed_mast_measured_height"]
    lt = base["lt_ref_mast"]
    level = {
        "reference_mast_cell_50m_long_term_ms": float(lt["WS50M"].mean()),
        f"mast_{prim_h}m_long_term_ms": float(np.mean(v_h)),
        "mast_130m_long_term_ms": float(np.mean(base["speed_mast_130"])),
        "turbine_130m_long_term_ms": mean_new,
        "shear_factor_mean": float(np.mean(base["speed_mast_130"]) / np.mean(v_h)),
        "site_transfer_factor_mean": float(mean_new / np.mean(base["speed_mast_130"])),
        "1530_era5_130m_ms": mmt.weibull_mean(a_hub_1530, k_1530),
    }

    # Long-term correction of the concurrent period, overall and by calendar month.
    measured = x[f"v{prim_h}"]
    pred_conc = mmt.predict_by_sector(
        x["WS50M"].to_numpy(), x["WD50M"].to_numpy(), base["fits"]
    )
    lt_local = _dt(lt.index) + pd.Timedelta(minutes=off)
    x_local = _dt(x.index) + pd.Timedelta(minutes=off)
    months = []
    for mo in range(1, 13):
        sel_lt = lt_local.month == mo
        sel_x = x_local.month == mo
        row: Dict[str, Any] = {
            "month": mo,
            "long_term_hours_share": float(sel_lt.mean()),
            "concurrent_hours_share": float(sel_x.mean()),
            f"long_term_mast_{prim_h}m_ms": float(np.mean(v_h[sel_lt])),
            "long_term_reference_ms": float(lt["WS50M"][sel_lt].mean()),
        }
        if sel_x.any():
            row[f"measured_2025_mast_{prim_h}m_ms"] = float(measured[sel_x].mean())
            row["predicted_2025_same_hours_ms"] = float(pred_conc[sel_x].mean())
            row["reference_2025_same_hours_ms"] = float(x["WS50M"][sel_x].mean())
            row["long_term_over_measured_2025"] = (
                row[f"long_term_mast_{prim_h}m_ms"]
                / row[f"measured_2025_mast_{prim_h}m_ms"]
            )
        months.append(row)
    lt_mean = float(np.mean(v_h))
    weighted = sum(
        r["long_term_hours_share"] * r[f"long_term_mast_{prim_h}m_ms"] for r in months
    )
    correction = {
        f"measured_concurrent_mast_{prim_h}m_mean_ms": float(measured.mean()),
        "predicted_concurrent_same_hours_mean_ms": float(pred_conc.mean()),
        f"long_term_mast_{prim_h}m_mean_ms": lt_mean,
        "long_term_correction_factor": lt_mean / float(measured.mean()),
        "reference_long_term_over_concurrent": float(
            lt["WS50M"].mean() / x["WS50M"].mean()
        ),
        f"long_term_mast_{prim_h}m_concurrent_months_only_ms": float(
            np.mean(v_h[np.isin(lt_local.month, sorted(set(x_local.month)))])
        ),
        "by_month": months,
        "monsoon_weighting_check": {
            "long_term_hours_shares_sum": float(
                sum(r["long_term_hours_share"] for r in months)
            ),
            "max_abs_long_term_share_minus_calendar_share": float(
                max(
                    abs(
                        r["long_term_hours_share"]
                        - pd.Timestamp(2001, r["month"], 1).days_in_month / 365.0
                    )
                    for r in months
                )
            ),
            "calendar_weighted_monthly_means_ms": weighted,
            "equals_long_term_mean": abs(weighted - lt_mean) < 1e-9,
            "months_without_concurrent_data": [
                r["month"] for r in months if r["concurrent_hours_share"] == 0.0
            ],
        },
    }
    return {
        "aep_decomposition": steps,
        "speed_level": level,
        "density_effect_gwh": 0.0,
        "loss_stack_effect_gwh": 0.0,
        "density_and_losses_note": "both bases use #1530's 1.15 kg/m3 and 7.77% loss stack; sensitivity air_density_mast_record_mean shows the mast's own density",
        "long_term_correction": correction,
        "sensitivity_2016_2025": dict(sens["window_2016_2025"]),
        "sensitivity_era5_shape_with_mast_mean": steps[1],
    }


def shadow_flicker(
    cfg: Mapping[str, Any],
    s_cfg: Mapping[str, Any],
    v: np.ndarray,
    d: np.ndarray,
    loc: pd.DatetimeIndex,
    operating: np.ndarray,
    p_op_1530: float,
) -> Dict[str, Any]:
    """Worst case, #1530's expected case and the yawed, long-term expected case."""
    from analytics.gis import shadow_flicker as sf

    site = s_cfg["site"]
    frame = sf.LocalFrame(
        float(site["reference_lat_deg"]), float(site["reference_lon_deg"])
    )
    lines = sf.coastline_lines_east_north(
        json.loads(_repo_path(site["coastline_geojson"]).read_text()), frame
    )
    coastal = sf.CoastalSetbackConfig.from_mapping(s_cfg["coastal_setback"])
    placement = sf.place_turbine(
        lines,
        rule=str(site["turbine_placement"]),
        min_distance_m=coastal.tower_distance_from_coastline_m,
        search_east_m=float(site["placement_search_east_m"]),
    )
    lot = sf.coast_aligned_square_lot(
        lines,
        north_m=0.0,
        area_m2=float(site["lot_area_m2"]),
        sample_step_m=float(site["coastline_sample_step_m"]),
    )
    tower = (placement.turbine_east_m, placement.turbine_north_m)
    lon_t, lat_t = frame.to_lon_lat(*tower)
    turbine = sf.TurbineGeometry(
        hub_height_m=float(s_cfg["turbine"]["hub_height_m"]),
        rotor_diameter_m=float(s_cfg["turbine"]["rotor_diameter_m"]),
    )
    fcfg = sf.ShadowFlickerConfig.from_mapping(s_cfg["shadow_flicker"])
    sun = sf.solar_path(lat_t, lon_t, fcfg)
    if not fcfg.sunshine_tmy_csv:
        raise ValueError("the expected case needs the siting config's sunshine record")
    sunny = sf.sunny_steps(
        sun, str(_repo_path(fcfg.sunshine_tmy_csv)), fcfg.sunshine_dni_threshold_wm2
    )
    weights = mmt.month_sector_weights(
        loc.month, d, operating, int(cfg["mcp"]["n_sectors"])
    )
    p_op_new = float(operating.mean())
    rows = []
    for name, pt in lot.receptors().items():
        old = sf.receptor_flicker(
            name,
            pt,
            tower_en=tower,
            turbine=turbine,
            cfg=fcfg,
            sun=sun,
            sunny=sunny,
            operating_probability=p_op_1530,
        )
        same = sf.receptor_flicker(
            name,
            pt,
            tower_en=tower,
            turbine=turbine,
            cfg=fcfg,
            sun=sun,
            sunny=sunny,
            operating_probability=p_op_new,
        )
        yawed = sf.expected_hours_with_orientation(
            pt,
            tower_en=tower,
            turbine=turbine,
            cfg=fcfg,
            sun=sun,
            sunny=sunny,
            month_sector_weights=weights,
            sub_directions_per_sector=int(
                cfg["shadow_flicker"]["sub_directions_per_sector"]
            ),
        )
        rows.append(
            {
                "name": name,
                "distance_m": old.distance_m,
                "worst_case_hours_per_year": old.worst_case_hours_per_year,
                "worst_case_max_minutes_per_day": old.worst_case_max_minutes_per_day,
                "expected_1530_hours_per_year": old.expected_hours_per_year,
                "expected_no_yaw_long_term_operating_hours_per_year": same.expected_hours_per_year,
                "expected_yawed_long_term_hours_per_year": yawed,
                "exceeds_expected_limit_yawed": yawed
                > fcfg.expected_hours_per_year_limit,
            }
        )
    return {
        "receptors": rows,
        "expected_hours_per_year_limit": fcfg.expected_hours_per_year_limit,
        "operating_probability_1530": p_op_1530,
        "operating_fraction_long_term": p_op_new,
        "method": (
            "rotor disc yawed to the long-term wind direction (month x sector, "
            f"{int(cfg['shadow_flicker']['sub_directions_per_sector'])} yaw angles per sector), "
            "turning only when hub speed is in the curve's producing range, sunny steps only"
        ),
    }


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="blue_whale_met_mast_transfer",
)
def main(cfg: DictConfig) -> None:
    """Run the transfer and print one JSON object."""
    logging.disable(logging.WARNING)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    out = run(raw)
    print(json.dumps(out, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
