"""Tests for the met-mast transfer (analytics.wind.met_mast_transfer and its Hydra CLI).

The mast record and the OEM power curve are private, so every test here runs on SYNTHETIC
data. The oracles do not come from the code under test (TEST-01):

* a synthetic sector-wise linear relation whose slopes and intercepts are known, recovered
  by both transfer methods (and by OLS under noise);
* the closed-form Weibull mean ``A * Gamma(1 + 1/k)`` and a seeded Weibull sample;
* the pre-existing, independently written integrator
  ``wind_resource.bankable_aep.gross_aep_weibull``, kept off the production path;
* power-law shear, an S2 tide and a clock offset planted in synthetic series;
* invariants: sector frequencies sum to 1, AEP rises with the speed scale, a pure
  rotation is recovered as the veer, an edge-on rotor casts no shadow, and every step is
  deterministic (no stochastic step exists, so reproducibility is identity of outputs).

Two tests read the committed outputs: the scenarios must carry the summary's derived CF
and AEP, and the rose table must equal the summary. One test re-runs the real transfer and
is skipped unless the three private inputs are configured on the host.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest
import yaml

from analytics.gis import shadow_flicker as sf
from analytics.wind import met_mast_transfer as mmt
from wind_resource.bankable_aep import gross_aep_weibull

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_blue_whale_met_mast_transfer_v14.py"
CONF = REPO_ROOT / "conf" / "blue_whale_met_mast_transfer.yaml"
SUMMARY = REPO_ROOT / "docs" / "blue_whale" / "met_mast_transfer_summary.json"
ROSE_CSV = REPO_ROOT / "docs" / "blue_whale" / "met_mast_wind_rose_130m.csv"
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
HYBRID = REPO_ROOT / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"

WS = np.arange(3.0, 25.01, 0.5)


def _load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("met_mast_transfer_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _curve() -> np.ndarray:
    """A generic 9.5 MW-class shape. Not derived from any OEM document."""
    rated, v_in, v_r = 9500.0, 3.0, 11.0
    p = rated * np.clip((WS**3 - v_in**3) / (v_r**3 - v_in**3), 0.0, 1.0)
    return np.asarray(p, dtype=np.float64)


# ---------------------------------------------------------------------------
# Sectors and circular statistics
# ---------------------------------------------------------------------------
def test_sector_index_edges_and_wrap() -> None:
    d = np.array([0.0, 11.2499, 11.25, 348.75, 359.9, 360.0, -5.0, 225.0])
    assert mmt.sector_index(d, 16).tolist() == [0, 0, 1, 0, 0, 0, 0, 10]
    assert mmt.angular_difference_deg(10.0, 350.0) == pytest.approx(20.0)
    assert mmt.angular_difference_deg(350.0, 10.0) == pytest.approx(-20.0)
    assert mmt.circular_mean_deg([350.0, 10.0]) == pytest.approx(0.0, abs=1e-9) or (
        mmt.circular_mean_deg([350.0, 10.0]) == pytest.approx(360.0)
    )
    with pytest.raises(ValueError):
        mmt.sector_index(d, 0)


def test_sector_frequencies_sum_to_one() -> None:
    rng = np.random.default_rng(7)
    d = rng.uniform(0, 360, 5000)
    v = rng.weibull(2.0, 5000) * 8.0
    assert mmt.sector_frequencies(d, 16).sum() == pytest.approx(1.0)
    rose = mmt.sector_rose(v, d, 16)
    assert sum(r["frequency"] for r in rose) == pytest.approx(1.0)
    assert sum(r["energy_share"] for r in rose) == pytest.approx(1.0)
    month = rng.integers(1, 13, 5000)
    op = (v > 3.0).astype(float)
    w = mmt.month_sector_weights(month, d, op, 16)
    assert w.shape == (12, 16)
    assert np.all(w.sum(1) <= 1.0 + 1e-12)
    for m in range(1, 13):
        assert w[m - 1].sum() == pytest.approx(op[month == m].mean())


# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------
def _synthetic_concurrent(noise: float, seed: int = 11) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    n = 8000
    d = rng.uniform(0, 360, n)
    r = rng.weibull(2.2, n) * 7.0
    sec = mmt.sector_index(d, 16)
    slope = 1.0 + 0.03 * np.arange(16)
    intercept = 0.1 * (np.arange(16) - 8)
    m = slope[sec] * r + intercept[sec] + rng.normal(0.0, noise, n)
    return {"m": m, "r": r, "d": d, "slope": slope, "intercept": intercept}


@pytest.mark.parametrize("method", ["variance_ratio", "linear_regression"])
def test_noise_free_mcp_recovers_the_planted_sector_relation(method: str) -> None:
    s = _synthetic_concurrent(noise=0.0)
    fits, omni = mmt.fit_sector_mcp(
        s["m"],
        s["r"],
        s["d"],
        n_sectors=16,
        method=method,
        min_sector_hours=50,
        min_sector_r_squared=0.3,
    )
    assert omni.sector == -1 and omni.n == s["m"].size
    for f in fits:
        assert f.source == "sector"
        assert f.slope == pytest.approx(s["slope"][f.sector], rel=1e-9)
        assert f.intercept == pytest.approx(s["intercept"][f.sector], abs=1e-9)
        assert f.r_squared == pytest.approx(1.0)
        assert f.residual_std_ms == pytest.approx(0.0, abs=1e-9)
    pred = mmt.predict_by_sector(s["r"], s["d"], fits)
    assert np.allclose(pred, np.clip(s["m"], 0.0, None))


def test_ols_recovers_slopes_under_noise_and_variance_ratio_inflates_them() -> None:
    s = _synthetic_concurrent(noise=1.0)
    ols, _ = mmt.fit_sector_mcp(
        s["m"],
        s["r"],
        s["d"],
        n_sectors=16,
        method="linear_regression",
        min_sector_hours=50,
        min_sector_r_squared=0.3,
    )
    vr, _ = mmt.fit_sector_mcp(
        s["m"],
        s["r"],
        s["d"],
        n_sectors=16,
        method="variance_ratio",
        min_sector_hours=50,
        min_sector_r_squared=0.3,
    )
    for o, v in zip(ols, vr, strict=True):
        assert o.slope == pytest.approx(s["slope"][o.sector], rel=0.06)
        # Variance ratio = slope / r for an exact linear model plus noise.
        assert v.slope > o.slope
        assert v.slope == pytest.approx(o.slope / math.sqrt(o.r_squared), rel=1e-9)


def test_sparse_or_weak_sectors_fall_back_to_the_omni_fit() -> None:
    s = _synthetic_concurrent(noise=0.0)
    keep = ~((mmt.sector_index(s["d"], 16) == 3) & (np.arange(s["d"].size) % 10 != 0))
    fits, omni = mmt.fit_sector_mcp(
        s["m"][keep],
        s["r"][keep],
        s["d"][keep],
        n_sectors=16,
        method="variance_ratio",
        min_sector_hours=200,
        min_sector_r_squared=0.3,
    )
    assert fits[3].source == "omni"
    assert (fits[3].slope, fits[3].intercept) == (omni.slope, omni.intercept)
    assert fits[4].source == "sector"
    with pytest.raises(ValueError, match="finite"):
        mmt.fit_sector_mcp(
            np.array([1.0, np.nan]),
            np.array([1.0, 2.0]),
            np.array([0.0, 0.0]),
            n_sectors=16,
            method="variance_ratio",
            min_sector_hours=1,
            min_sector_r_squared=0.0,
        )


def test_correlation_gate_refuses_a_weak_relation() -> None:
    rng = np.random.default_rng(3)
    idx = pd.date_range("2025-01-01", periods=24 * 60, freq="1h")
    ref = rng.weibull(2, idx.size) * 7
    j = pd.DataFrame({"WS50M": ref, "v120": rng.permutation(ref)}, index=idx)
    gate = {"min_hourly_r_squared": 0.49, "min_daily_r": 0.8}
    with pytest.raises(ValueError, match="too weak"):
        cli.correlation_gate(j, "v120", gate)
    j["v120"] = 1.2 * ref + rng.normal(0, 0.3, idx.size)
    out = cli.correlation_gate(j, "v120", gate)
    assert out["hourly_r_squared"] > 0.9 and out["days"] == 60


# ---------------------------------------------------------------------------
# Direction transfer
# ---------------------------------------------------------------------------
def test_a_pure_rotation_is_recovered_as_veer_and_quantiles() -> None:
    rng = np.random.default_rng(5)
    ref = rng.uniform(0, 360, 4000)
    target = np.mod(ref - 12.0, 360.0)
    veer, omni, _ = mmt.sector_veer(target, ref, n_sectors=16, min_sector_hours=10)
    assert omni == pytest.approx(-12.0)
    assert np.allclose(veer, -12.0)
    q, _ = mmt.direction_residual_quantiles(
        target, ref, n_sectors=16, min_sector_hours=10, n_quantiles=7
    )
    assert np.allclose(q, -12.0)
    src, d = mmt.expand_by_direction_quantiles(ref[:5], q)
    assert src.tolist() == [i for i in range(5) for _ in range(7)]
    assert np.allclose(mmt.angular_difference_deg(d, ref[src]), -12.0)
    assert np.allclose(mmt.continuous_veer(ref, np.full(16, -12.0)), -12.0)


def test_quantile_expansion_reproduces_the_conditional_rose() -> None:
    rng = np.random.default_rng(9)
    ref = rng.uniform(180, 270, 20000)
    target = np.mod(ref + rng.normal(-8.0, 15.0, ref.size), 360.0)
    q, _ = mmt.direction_residual_quantiles(
        target, ref, n_sectors=16, min_sector_hours=200, n_quantiles=20
    )
    _, d = mmt.expand_by_direction_quantiles(ref, q)
    err = np.abs(mmt.sector_frequencies(d, 16) - mmt.sector_frequencies(target, 16))
    assert err.max() < 0.01
    # A single mean rotation concentrates the rose instead.
    veer, _, _ = mmt.sector_veer(target, ref, n_sectors=16, min_sector_hours=200)
    rotated = ref + veer[mmt.sector_index(ref, 16)]
    err_mean = np.abs(
        mmt.sector_frequencies(rotated, 16) - mmt.sector_frequencies(target, 16)
    )
    assert err_mean.max() > err.max()


def test_continuous_veer_refuses_a_fold_over() -> None:
    v = np.zeros(16)
    v[4], v[5] = 10.0, -15.0
    with pytest.raises(ValueError, match="monotone"):
        mmt.continuous_veer([0.0], v)


def test_sector_speed_ratio_recovers_a_planted_gradient() -> None:
    rng = np.random.default_rng(2)
    d = rng.uniform(0, 360, 6000)
    m = rng.weibull(2, 6000) * 7
    gain = 1.0 + 0.01 * mmt.sector_index(d, 16)
    ratio, omni = mmt.sector_speed_ratio(
        m * gain, m, d, n_sectors=16, min_sector_hours=50
    )
    assert np.allclose(ratio, 1.0 + 0.01 * np.arange(16))
    assert omni == pytest.approx((m * gain).mean() / m.mean())


# ---------------------------------------------------------------------------
# Shear, distributions, turbulence
# ---------------------------------------------------------------------------
def test_power_law_shear_is_recovered_and_inverted() -> None:
    assert mmt.shear_exponent(8.0, 8.0 * 1.2**0.14, 100, 120) == pytest.approx(0.14)
    h = [30, 50, 80, 100, 120]
    assert mmt.log_law_fit_exponent(h, [7 * (x / 30) ** 0.2 for x in h]) == (
        pytest.approx(0.2)
    )
    rng = np.random.default_rng(4)
    n = 4000
    lo = rng.uniform(4, 12, n)
    day = rng.random(n) < 0.5
    alpha_true = np.where(day, 0.05, 0.15)
    hi = lo * 1.2**alpha_true
    d = rng.uniform(0, 360, n)
    t = mmt.shear_table(
        lo,
        hi,
        d,
        day,
        h_low=100,
        h_high=120,
        n_sectors=16,
        min_cell_hours=20,
        min_speed_ms=3.0,
    )
    assert t["alpha_day"] == pytest.approx(0.05, abs=1e-9)
    assert t["alpha_night"] == pytest.approx(0.15, abs=1e-9)
    out = mmt.apply_shear(lo, d, day, t["alpha"], h_from=100, h_to=120)
    assert np.allclose(out, hi)


def test_weibull_closed_form_mean_and_sector_fit() -> None:
    a, k = 9.0, 2.5
    assert mmt.weibull_mean(a, k) == pytest.approx(a * math.gamma(1 + 1 / k))
    rng = np.random.default_rng(1)
    v = a * rng.weibull(k, 200000)
    rose = mmt.sector_rose(v, np.full(v.size, 225.0), 16)
    row = rose[10]
    assert row["frequency"] == 1.0 and row["energy_share"] == 1.0
    assert row["weibull_a_ms"] == pytest.approx(a, rel=0.01)
    assert row["weibull_k"] == pytest.approx(k, rel=0.01)
    assert row["mean_speed_ms"] == pytest.approx(mmt.weibull_mean(a, k), rel=0.01)
    assert all(r["weibull_a_ms"] is None for i, r in enumerate(rose) if i != 10)


def test_turbulence_closed_form() -> None:
    mean = np.array([5.0, 5.5, 5.2, 10.0, 10.5, 2.0])
    sd = mean * np.array([0.10, 0.12, 0.08, 0.07, 0.07, 0.5])
    t = mmt.turbulence_table(
        mean,
        sd,
        np.zeros(6),
        bin_edges_ms=[3, 6, 9, 12],
        n_sectors=16,
        min_speed_ms=3.0,
        min_count=2,
    )
    b0 = t["by_speed_bin"][0]
    ti = np.array([0.10, 0.12, 0.08])
    assert b0["n"] == 3
    assert b0["ti_mean"] == pytest.approx(ti.mean())
    assert b0["ti_representative"] == pytest.approx(ti.mean() + 1.28 * ti.std())
    assert t["by_speed_bin"][1]["n"] == 0 and "ti_mean" not in t["by_speed_bin"][1]
    assert t["n_valid"] == 5  # the 2 m/s row is below the floor


def test_jackknife_and_energy_sensitivity_closed_forms() -> None:
    assert mmt.jackknife_std([1.0, 2.0, 3.0]) == pytest.approx(math.sqrt(4 / 3))
    assert mmt.energy_sensitivity(lambda s: 5.0 * s**3) == pytest.approx(3.0)
    with pytest.raises(ValueError):
        mmt.jackknife_std([1.0])


# ---------------------------------------------------------------------------
# Yield
# ---------------------------------------------------------------------------
def test_sector_weighted_yield_equals_the_independent_integrator() -> None:
    p = _curve()
    rose = [
        {"sector": s, "frequency": 1 / 16, "weibull_a_ms": 9.0, "weibull_k": 2.4}
        for s in range(16)
    ]
    got = mmt.sector_weighted_gross_aep_gwh(rose, WS, p, 1.0)
    oracle = gross_aep_weibull(
        wind_speed_ms=WS.tolist(),
        power_kw=p.tolist(),
        weibull_a=9.0,
        weibull_k=2.4,
        rated_power_kw=9500.0,
        n_turbines=1,
        cut_in_ms=0.0,
        cut_out_ms=float(WS.max()),
        rho_site_kgm3=1.225,
        rho_ref_kgm3=1.225,
    ).aep_gwh_farm
    assert got == pytest.approx(oracle, rel=1e-3)
    two = [dict(r) for r in rose]
    for r in two[:8]:
        r["weibull_a_ms"] = 7.0
    for r in two[8:]:
        r["weibull_a_ms"] = 11.0
    mixed = mmt.sector_weighted_gross_aep_gwh(two, WS, p, 1.0)
    halves = [
        gross_aep_weibull(
            wind_speed_ms=WS.tolist(),
            power_kw=p.tolist(),
            weibull_a=a,
            weibull_k=2.4,
            rated_power_kw=9500.0,
            n_turbines=1,
            cut_in_ms=0.0,
            cut_out_ms=float(WS.max()),
            rho_site_kgm3=1.225,
            rho_ref_kgm3=1.225,
        ).aep_gwh_farm
        for a in (7.0, 11.0)
    ]
    assert mixed == pytest.approx(0.5 * sum(halves), rel=1e-3)


def test_aep_rises_with_the_speed_scale_and_refuses_a_missing_fit() -> None:
    p = _curve()
    rng = np.random.default_rng(8)
    v = rng.weibull(2.5, 30000) * 8.0
    d = rng.uniform(0, 360, v.size)
    out = []
    for scale in (0.8, 0.9, 1.0, 1.1, 1.2):
        rose = mmt.sector_rose(v * scale, d, 16)
        out.append(mmt.sector_weighted_gross_aep_gwh(rose, WS, p, 1.0))
        ts = mmt.time_series_gross_aep_gwh(v * scale, WS, p, 1.0)
        assert out[-1] == pytest.approx(ts, rel=0.03)
    assert all(b > a for a, b in zip(out, out[1:], strict=False))
    bad = [{"sector": 0, "frequency": 1.0, "weibull_a_ms": None, "weibull_k": None}]
    with pytest.raises(ValueError, match="no Weibull"):
        mmt.sector_weighted_gross_aep_gwh(bad, WS, p, 1.0)


# ---------------------------------------------------------------------------
# Hourly aggregation and the clock-offset evidence
# ---------------------------------------------------------------------------
def test_hourly_means_keep_only_complete_hours_and_vector_average() -> None:
    idx = pd.date_range("2025-06-01 05:30", periods=12, freq="10min")
    f = pd.DataFrame(
        {"v": np.arange(12, dtype=float), "d": [350.0, 10.0] * 6}, index=idx
    )
    f.loc[idx[7], "v"] = np.nan
    hr = mmt.hourly_means(
        f,
        speed_columns={"v": "v"},
        direction_columns={"d": "d"},
        clock_offset_minutes=330,
        samples_per_hour=6,
    )
    assert list(hr.index) == [
        pd.Timestamp("2025-06-01 00:00"),
        pd.Timestamp("2025-06-01 01:00"),
    ]
    assert hr["v"].iloc[0] == pytest.approx(2.5)
    assert np.isnan(hr["v"].iloc[1])
    assert mmt.angular_difference_deg(hr["d"].iloc[0], 0.0) == pytest.approx(
        0.0, abs=1e-9
    )


def test_s2_phase_and_clock_offset_are_recovered() -> None:
    h = np.arange(0, 24, 1 / 6)
    y = (
        100
        + 0.15 * np.cos(2 * np.pi * (h - 9.6) / 12)
        + 0.05 * np.cos(2 * np.pi * (h - 5.0) / 24)
    )
    out = mmt.harmonic_phase_hours(y, h, 12.0)
    assert out["max_at_h"] == pytest.approx(9.6, abs=1e-6)
    assert out["amplitude"] == pytest.approx(0.15, abs=1e-9)
    assert mmt.harmonic_phase_hours(y, h, 24.0)["max_at_h"] == pytest.approx(5.0)
    rng = np.random.default_rng(12)
    utc = pd.date_range("2025-04-01", periods=24 * 60, freq="1h")
    ref = pd.Series(
        pd.Series(rng.normal(0, 1, utc.size))
        .rolling(5, min_periods=1)
        .mean()
        .to_numpy()
        + 7,
        index=utc,
    )
    ten = ref.resample("10min").ffill()
    mast = pd.Series(ten.to_numpy(), index=ten.index + pd.Timedelta(minutes=330))
    scan = mmt.offset_correlation_scan(mast, ref, [0, 300, 330, 360, 480], 6)
    best = max(scan, key=lambda r: r["pearson_r"])
    assert best["offset_h"] == pytest.approx(5.5)


def _synthetic_mast_for_timezone(offset_min: int) -> Dict[str, Any]:
    rng = np.random.default_rng(21)
    utc = pd.date_range("2025-04-01", "2025-07-31 23:00", freq="1h")
    base = pd.Series(rng.normal(0, 1, utc.size)).rolling(4, min_periods=1).mean()
    ws = 7 + 1.5 * base.to_numpy()
    wd = np.mod(225 + 20 * np.sin(2 * np.pi * (utc.hour + 5.3) / 24), 360)
    ref = pd.DataFrame({"WS50M": ws, "WD50M": wd}, index=utc)
    ten = ref.resample("10min").ffill()
    clock = ten.index + pd.Timedelta(minutes=offset_min)
    lst_h = (ten.index.hour + ten.index.minute / 60 + 79.70815 / 15) % 24
    mast = pd.DataFrame(
        {
            "Speed 80 m Avg [m/s]": ten["WS50M"].to_numpy(),
            "Speed 100 m Avg [m/s]": ten["WS50M"].to_numpy() * 1.05,
            "Direction 80 m Avg [°]": ten["WD50M"].to_numpy(),
            "Pressure 10 m Avg [kPa]": 100.9
            + 0.15 * np.cos(2 * np.pi * (lst_h - 10.0) / 12),
            "Temp 10 m Avg [℃]": 28 + 3 * np.cos(2 * np.pi * (lst_h - 14.0) / 24),
        },
        index=clock,
    )
    return {"mast": mast, "ref": ref}


def test_timezone_evidence_accepts_the_true_offset_and_refuses_a_wrong_one() -> None:
    raw = yaml.safe_load(CONF.read_text())
    s = _synthetic_mast_for_timezone(330)
    tz = dict(raw["timezone"])
    tz["scan_offsets_minutes"] = {"start": 0, "stop": 600, "step": 30}
    out = cli.timezone_evidence(s["mast"], s["ref"], raw["mast"], tz)
    assert out["s2_implied_clock_offset_h"] == pytest.approx(5.5, abs=0.01)
    assert out["hourly_speed_correlation_peak_offset_h"] == pytest.approx(5.5)
    wrong = dict(tz)
    wrong["clock_offset_minutes"] = 480
    wrong["candidate_offsets_minutes"] = [0, 330, 480]
    with pytest.raises(ValueError, match="does not support"):
        cli.timezone_evidence(s["mast"], s["ref"], raw["mast"], wrong)


# ---------------------------------------------------------------------------
# Inputs and boundaries
# ---------------------------------------------------------------------------
def test_reference_loader_refuses_altered_or_misplaced_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", REPO_ROOT)
    block = {
        "WS50M": {"2015010100": 5.0, "2015010101": 6.0},
        "WD50M": {"2015010100": 200.0, "2015010101": 210.0},
        "WS10M": {"2015010100": 4.0, "2015010101": 4.5},
    }
    doc = {
        "geometry": {"type": "Point", "coordinates": [79.708, 8.056, 55.0]},
        "properties": {"parameter": block},
    }
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "wsd_2015.json").write_text(json.dumps(doc))
    cfg = {
        "dir": str(tmp_path),
        "dir_env": "X",
        "first_year": 2015,
        "last_year": 2015,
        "points": {
            "mast": {
                "subdir": "p",
                "latitude_deg_n": 8.056318,
                "longitude_deg_e": 79.70815,
                "parameter_sha256": {"2015": cli.parameter_digest(block)},
            }
        },
    }
    assert len(cli.load_reference(cfg, "mast")) == 2
    cfg["points"]["mast"]["parameter_sha256"]["2015"] = "0" * 64
    with pytest.raises(ValueError, match="pin"):
        cli.load_reference(cfg, "mast")
    cfg["points"]["mast"]["parameter_sha256"]["2015"] = cli.parameter_digest(block)
    cfg["points"]["mast"]["latitude_deg_n"] = 8.3
    with pytest.raises(ValueError, match="configured point"):
        cli.load_reference(cfg, "mast")


def test_private_inputs_are_refused_from_inside_the_repository() -> None:
    with pytest.raises(ValueError, match="outside the repository"):
        cli._outside_repo(str(CONF), "source", "X")
    with pytest.raises(ValueError, match="No source"):
        cli._outside_repo(None, "source", "X")
    pin = cli.private_source_pin(
        REPO_ROOT
        / "docs"
        / "source_materials"
        / "met_mast_617725_2025"
        / "PRIVATE_SOURCE_MANIFEST.sha256"
    )
    assert pin == "a19963698f6d7e1085f8c66bb1810ecc1e8937e7f004ab25b81539bfd2e2cd46"


def test_json_clean_is_strict() -> None:
    out = cli.json_clean({"a": float("nan"), "b": [np.float64(1.5), np.int64(2)]})
    assert out == {"a": None, "b": [1.5, 2]}
    json.dumps(out, allow_nan=False)


# ---------------------------------------------------------------------------
# Yawed rotor shadow
# ---------------------------------------------------------------------------
def _sun(el_deg: float, az_deg: float, n: int = 4) -> sf.SunPath:
    return sf.SunPath(
        elevation_deg=np.full(n, el_deg),
        azimuth_deg=np.full(n, az_deg),
        day_index=np.zeros(n, dtype=np.int64),
        utc_hour_key=np.full(n, 60112, dtype=np.int64),
        step_minutes=60.0,
        n_days=1,
    )


def test_yawed_rotor_shadow_closed_forms() -> None:
    turbine = sf.TurbineGeometry(hub_height_m=130.0, rotor_diameter_m=206.0)
    # Sun due east at 20 degrees: the shadow of the hub falls west, at H' / tan(el).
    el = 20.0
    reach = (130.0 - 2.0) / math.tan(math.radians(el))
    receptor = (-reach, 0.0)
    sun = _sun(el, 90.0)
    kw = dict(turbine=turbine, receptor_height_m=2.0, max_distance_m=2060.0, sun=sun)
    facing = sf.oriented_shadow_mask(receptor, rotor_axis_deg=90.0, **kw)
    assert facing.all()
    assert sf.shadow_mask(receptor, **kw).all()
    edge_on = sf.oriented_shadow_mask(receptor, rotor_axis_deg=0.0, **kw)
    assert not edge_on.any()
    # Off the hub's shadow by more than the yawed disc's half-width: no shadow.
    side = (-reach, 103.0 * math.cos(math.radians(60)) + 5.0)
    assert not sf.oriented_shadow_mask(side, rotor_axis_deg=150.0, **kw).any()
    assert sf.oriented_shadow_mask(side, rotor_axis_deg=90.0, **kw).all()


def test_expected_hours_with_orientation_is_linear_and_bounded() -> None:
    turbine = sf.TurbineGeometry(hub_height_m=130.0, rotor_diameter_m=206.0)
    raw = yaml.safe_load(
        (REPO_ROOT / "conf" / "blue_whale_wind_siting.yaml").read_text()
    )
    cfg = sf.ShadowFlickerConfig.from_mapping(raw["shadow_flicker"])
    el = 20.0
    reach = (130.0 - 2.0) / math.tan(math.radians(el))
    sun = _sun(el, 90.0)
    sunny = np.ones(4, dtype=bool)
    w = np.zeros((12, 16))
    w[5, 4] = 1.0  # June, rotor axis East: faces the sun
    kw = dict(tower_en=(0.0, 0.0), turbine=turbine, cfg=cfg, sun=sun, sunny=sunny)
    full = sf.expected_hours_with_orientation(
        (-reach, 0.0), month_sector_weights=w, sub_directions_per_sector=1, **kw
    )
    assert full == pytest.approx(4.0)
    half = sf.expected_hours_with_orientation(
        (-reach, 0.0), month_sector_weights=w / 2, sub_directions_per_sector=1, **kw
    )
    assert half == pytest.approx(2.0)
    w2 = np.zeros((12, 16))
    w2[5, 0] = 1.0  # rotor axis North: edge-on to an eastern sun
    assert sf.expected_hours_with_orientation(
        (-reach, 0.0), month_sector_weights=w2, sub_directions_per_sector=1, **kw
    ) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        sf.expected_hours_with_orientation(
            (-reach, 0.0), month_sector_weights=w * 2, sub_directions_per_sector=1, **kw
        )


# ---------------------------------------------------------------------------
# Heights, sectors, day window and the turbine point come from the config
# (#1538 domain D-1)
# ---------------------------------------------------------------------------
def _planted_mast(mcfg: Dict[str, Any], alpha: float, days: int) -> pd.DataFrame:
    """A 10-minute mast record whose mean speeds follow one power law exactly."""
    idx = pd.date_range("2025-04-01", periods=days * 144, freq="10min")
    rng = np.random.default_rng(1538)
    base = 6.0 + rng.uniform(-1.0, 1.0, len(idx))  # speed at 100 m
    cols: Dict[str, Any] = {
        name: base * (float(h) / 100.0) ** alpha
        for h, name in mcfg["speed_avg"].items()
    }
    cols[mcfg["direction"]] = np.linspace(0.0, 359.9, len(idx)) % 360.0
    return pd.DataFrame(cols, index=idx)


def test_measured_profiles_read_the_configured_pair_window_and_sectors() -> None:
    raw = yaml.safe_load(CONF.read_text())
    mcfg, shear = raw["mast"], raw["shear"]
    n = int(raw["mcp"]["n_sectors"])
    days = 70  # about 630 rows per 22.5 degree sector: above the 600-row floor
    mast = _planted_mast(mcfg, alpha=0.21, days=days)
    got = cli.measured_profiles(mast, mcfg, shear, n)
    # The committed config's keys are the ones the summary has always carried.
    assert got["alpha_100_120"] == pytest.approx(0.21, abs=1e-12)
    assert set(got["day_night_local_06_18"]) == {"day", "night"}
    assert got["day_night_local_06_18"]["day"]["n_10min"] == days * 12 * 6
    assert [r["label"] for r in got["by_sector_80m_direction"]] == list(mmt.COMPASS_16)
    assert all(
        r["alpha_100_120"] == pytest.approx(0.21, abs=1e-12)
        for r in got["by_sector_80m_direction"]
    )
    assert sorted(got["diurnal_mean_ms_by_local_hour"]) == ["100", "120"]
    # Change the config and the profile follows it.
    # The window is 10 hours here, not 12, so the day count shows the window is applied
    # and not only named (#1585 assurance A-2(a)).
    moved = dict(shear, low_height_m=80.0, day_start_local_h=8, day_end_local_h=18)
    alt = cli.measured_profiles(mast, mcfg, moved, 8)
    assert "alpha_100_120" not in alt
    assert alt["alpha_80_120"] == pytest.approx(0.21, abs=1e-12)
    assert alt["day_night_local_08_18"]["day"]["n_10min"] == days * 10 * 6
    assert alt["day_night_local_08_18"]["night"]["n_10min"] == days * 14 * 6
    assert [r["label"] for r in alt["by_sector_80m_direction"]] == [
        str(i) for i in range(8)
    ]
    assert sorted(alt["diurnal_mean_ms_by_local_hour"]) == ["120", "80"]
    # A sector reports a pair exponent only with shear.min_cell_hours of rows.
    sparse = dict(shear, min_cell_hours=10_000)
    assert all(
        r["alpha_100_120"] is None
        for r in cli.measured_profiles(mast, mcfg, sparse, n)["by_sector_80m_direction"]
    )
    with pytest.raises(ValueError, match="no mast.speed_avg channel at 90 m"):
        cli.measured_profiles(mast, mcfg, dict(shear, low_height_m=90.0), n)


def test_the_turbine_reference_point_must_be_the_placed_turbine() -> None:
    raw = yaml.safe_load(CONF.read_text())
    s_cfg = yaml.safe_load((REPO_ROOT / raw["turbine"]["siting_config"]).read_text())
    lat, lon = cli.check_turbine_reference_point(raw, s_cfg)
    assert (lat, lon) == pytest.approx((8.2925, 79.7547), abs=1e-9)
    moved = json.loads(json.dumps(raw))
    moved["reference"]["points"]["turbine"][
        "longitude_deg_e"
    ] = 79.752666  # the #1530 spot
    with pytest.raises(ValueError, match="not where the siting config places"):
        cli.check_turbine_reference_point(moved, s_cfg)
    # A latitude-only move is caught too (#1585 domain D-3).
    north = json.loads(json.dumps(raw))
    north["reference"]["points"]["turbine"]["latitude_deg_n"] += 1e-5
    with pytest.raises(ValueError, match="not where the siting config places"):
        cli.check_turbine_reference_point(north, s_cfg)
    # Moving the turbine in the siting config is caught the same way.
    s_moved = json.loads(json.dumps(s_cfg))
    s_moved["site"]["turbine_placement"] = "coastal_setback"
    with pytest.raises(ValueError, match="not where the siting config places"):
        cli.check_turbine_reference_point(raw, s_moved)


def test_the_script_carries_no_hub_height_literal() -> None:
    """130 m lives in shear.hub_height_m; the script reads it (#1538 domain D-1)."""
    import ast

    hub = float(yaml.safe_load(CONF.read_text())["shear"]["hub_height_m"])
    tree = ast.parse(SCRIPT.read_text())
    literals = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
        and float(node.value) == hub
    ]
    assert literals == []


def test_committed_summary_keys_follow_the_configured_hub_height() -> None:
    raw = yaml.safe_load(CONF.read_text())
    tag = f"{float(raw['shear']['hub_height_m']):g}"
    summary = json.loads(SUMMARY.read_text())
    assert f"long_term_{tag}m" in summary
    assert f"weibull_a_{tag}m_ms" in summary["yield"]["era5_weibull_basis_1530"]


# ---------------------------------------------------------------------------
# The chain's shear pair, the shear term and the remaining mast heights come from the
# config (#1585 domain D-1, D-2 and assurance A-2)
# ---------------------------------------------------------------------------
_PLANTED_ALPHA_80 = 0.35  # the 80 m channel breaks the 100-120 m power law on purpose


def _planted_chain(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Hourly reference and a 10-minute mast whose 100-120 m shear is exactly 0.2.

    The 80 m channel follows a different exponent, so a shear table that reads the
    100 m column under an 80 m label gives a different answer from one that reads 80 m.
    """
    utc = pd.date_range("2025-04-01", "2025-06-30 23:00", freq="1h")
    rng = np.random.default_rng(1585)
    ref = pd.DataFrame(
        {
            "WS50M": 6.0 + 2.0 * rng.random(utc.size),
            "WD50M": rng.uniform(0.0, 360.0, utc.size),
        },
        index=utc,
    )
    ten = ref.resample("10min").ffill()
    mcfg = raw["mast"]
    v100 = ten["WS50M"].to_numpy() * 1.1
    cols: Dict[str, Any] = {}
    for h, name in mcfg["speed_avg"].items():
        a = _PLANTED_ALPHA_80 if float(h) == 80.0 else 0.2
        cols[name] = v100 * (float(h) / 100.0) ** a
    cols[mcfg["direction"]] = ten["WD50M"].to_numpy()
    cols[mcfg["direction_120m"]] = ten["WD50M"].to_numpy()
    return {"mast": pd.DataFrame(cols, index=ten.index), "ref": ref}


def _chain_shear(raw: Dict[str, Any], planted: Dict[str, Any]) -> Dict[str, Any]:
    chain = cli.Chain(raw, planted["mast"], planted["ref"], planted["ref"])
    out = chain.run(
        height=int(raw["mcp"]["primary_height_m"]),
        method=raw["mcp"]["method"],
        window=[2025, 2025],
        offset_min=0,
    )
    shear: Dict[str, Any] = out["shear"]
    return shear


def test_the_chain_shear_reads_the_configured_pair() -> None:
    raw = yaml.safe_load(CONF.read_text())
    planted = _planted_chain(raw)
    assert _chain_shear(raw, planted)["alpha_all"] == pytest.approx(0.2, abs=1e-12)
    # Move the low height to 80 m: the table must read the 80 m speeds, not the 100 m
    # speeds under an 80 m label (#1585 domain D-1).
    moved = json.loads(json.dumps(raw))
    moved["shear"]["low_height_m"] = 80.0
    expected = (0.2 * math.log(1.2) - _PLANTED_ALPHA_80 * math.log(0.8)) / math.log(1.5)
    mislabelled = 0.2 * math.log(1.2) / math.log(1.5)
    got = _chain_shear(moved, planted)["alpha_all"]
    assert got == pytest.approx(expected, abs=1e-12)
    assert abs(got - mislabelled) > 0.1
    moved["shear"]["low_height_m"] = 90.0
    with pytest.raises(ValueError, match="no mast.speed_avg channel at 90 m"):
        _chain_shear(moved, planted)


def test_shear_uncertainty_closed_form_and_base_height() -> None:
    # Two equally weighted exponents 0.1 and 0.3: standard deviation 0.1.
    got = cli.shear_uncertainty_pct(
        [[0.1, 0.3]], [[5, 5]], from_height_m=120.0, hub_height_m=130.0
    )
    assert got == pytest.approx(100.0 * math.log(130.0 / 120.0) * 0.1, rel=1e-12)
    # Extrapolating from 100 m is a longer lever, so the term is larger.
    longer = cli.shear_uncertainty_pct(
        [[0.1, 0.3]], [[5, 5]], from_height_m=100.0, hub_height_m=130.0
    )
    assert longer == pytest.approx(100.0 * math.log(1.3) * 0.1, rel=1e-12)
    # The run takes the base height from the correlated height, mcp.primary_height_m
    # (#1585 domain D-2), not from the top of the measured shear pair.
    src = SCRIPT.read_text()
    assert 'from_height_m=float(m["primary_height_m"])' in src
    assert 'high_height_m"])) * a_std' not in src


def _planted_density_mast(raw: Dict[str, Any]) -> pd.DataFrame:
    mcfg = raw["mast"]
    idx = pd.date_range("2025-04-01", periods=144, freq="10min")
    temps = {"10": 30.0, "120": 25.0}
    cols: Dict[str, Any] = {
        mcfg["pressure_10m_kpa"]: np.full(idx.size, 100.5),
        mcfg["humidity_10m_pct"]: np.full(idx.size, 70.0),
    }
    for h, name in mcfg["temperature_c"].items():
        cols[name] = np.full(idx.size, temps[h])
    return pd.DataFrame(cols, index=idx)


def test_air_density_reads_the_configured_channels() -> None:
    raw = yaml.safe_load(CONF.read_text())
    mast = _planted_density_mast(raw)
    hub = float(raw["shear"]["hub_height_m"])
    heights = {k: float(v) for k, v in raw["air_density"].items()}
    got = cli.air_density(mast, raw["mast"], hub, **heights)
    # The committed summary's basis text is what the committed config produces.
    summary = json.loads(SUMMARY.read_text())
    assert got["basis"] == summary["air_density"]["basis"]
    assert got["n_10min"] == 144
    # Reading the 10 m temperature (30 C) as the air temperature gives thinner air than
    # the 120 m channel (25 C): the configured height decides which channel is read.
    warm = cli.air_density(
        mast, raw["mast"], hub, **{**heights, "temperature_height_m": 10.0}
    )
    assert warm["mean_kgm3"] < got["mean_kgm3"]
    assert "T(10 m), humidity" in warm["basis"]
    with pytest.raises(ValueError, match="no mast.temperature_c channel at 80 m"):
        cli.air_density(
            mast, raw["mast"], hub, **{**heights, "temperature_height_m": 80.0}
        )


def test_timezone_evidence_reads_the_configured_channels() -> None:
    raw = yaml.safe_load(CONF.read_text())
    s = _synthetic_mast_for_timezone(330)
    tz = dict(raw["timezone"])
    tz["scan_offsets_minutes"] = {"start": 0, "stop": 600, "step": 30}
    out = cli.timezone_evidence(s["mast"], s["ref"], raw["mast"], tz)
    # The committed summary carries the same keys as the committed config produces.
    summary = json.loads(SUMMARY.read_text())
    assert set(out) == set(summary["timezone"])
    for key, value in (
        ("scan_speed_height_m", 90),
        ("anomaly_speed_height_m", 90),
    ):
        with pytest.raises(ValueError, match="no mast.speed_avg channel at 90 m"):
            cli.timezone_evidence(s["mast"], s["ref"], raw["mast"], {**tz, key: value})
    with pytest.raises(ValueError, match="no mast.temperature_c channel at 50 m"):
        cli.timezone_evidence(
            s["mast"], s["ref"], raw["mast"], {**tz, "temperature_height_m": 50}
        )


def test_committed_turbulence_keys_follow_the_configured_heights() -> None:
    raw = yaml.safe_load(CONF.read_text())
    summary = json.loads(SUMMARY.read_text())
    assert sorted(summary["turbulence"]) == sorted(
        f"{cli._channel_key(raw['mast']['speed_avg'], float(h))}m"
        for h in raw["turbulence"]["heights_m"]
    )
    for h in raw["turbulence"]["heights_m"]:
        cli._channel_key(raw["mast"]["speed_sd"], float(h), "mast.speed_sd")


def test_the_script_names_no_mast_speed_or_temperature_channel() -> None:
    """Every mast speed and temperature height is read from the config (#1585 A-2)."""
    import ast

    raw = yaml.safe_load(CONF.read_text())
    mcfg = raw["mast"]
    keys = set(mcfg["speed_avg"]) | set(mcfg["speed_sd"]) | set(mcfg["temperature_c"])
    banned = keys | {f"v{k}" for k in keys}
    tree = ast.parse(SCRIPT.read_text())
    hits = [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in banned
    ]
    assert hits == []
    for gone in ("temperature_10m_c", "temperature_120m_c"):
        assert gone not in SCRIPT.read_text()


# ---------------------------------------------------------------------------
# Committed outputs and scenarios
# ---------------------------------------------------------------------------
def test_scenarios_carry_the_summary_yield_and_the_hold() -> None:
    summary = json.loads(SUMMARY.read_text())
    y = summary["yield"]
    for path in (WIND, HYBRID):
        scen = yaml.safe_load(path.read_text())
        wind = scen["generation"]["technologies"]["wind"]
        assert wind["capacity_factor"] == pytest.approx(
            y["net_capacity_factor"], abs=5e-7
        )
        assert wind["aep_gwh"] == pytest.approx(y["net_aep_gwh"], abs=0.005)
        text = path.read_text()
        assert "NOT LENDER-GRADE" in text
        assert "met_mast_transfer" in text
    assert "HOLD" in summary["hold"]
    assert summary["mast_source"]["sha256_verified"] is True
    gates = summary["mcp"]["correlation_gates"]
    raw = yaml.safe_load(CONF.read_text())["mcp"]
    for gate in gates.values():
        assert gate["hourly_r_squared"] >= raw["min_hourly_r_squared"]
        assert gate["daily_r"] >= raw["min_daily_r"]


def test_committed_rose_is_consistent() -> None:
    summary = json.loads(SUMMARY.read_text())
    rose = summary["long_term_130m"]["rose"]
    assert sum(r["frequency"] for r in rose) == pytest.approx(1.0)
    assert sum(r["energy_share"] for r in rose) == pytest.approx(1.0)
    weighted = sum(r["frequency"] * r["mean_speed_ms"] for r in rose)
    assert weighted == pytest.approx(summary["long_term_130m"]["mean_speed_ms"])
    rows = pd.read_csv(ROSE_CSV, comment="#")
    assert len(rows) == 16
    for r, c in zip(rose, rows.itertuples(), strict=True):
        assert c.label == r["label"]
        assert c.frequency == pytest.approx(r["frequency"], abs=5e-7)
        assert c.weibull_a_ms == pytest.approx(r["weibull_a_ms"], abs=5e-5)
        assert c.weibull_k == pytest.approx(r["weibull_k"], abs=5e-5)


def test_summary_publishes_aggregates_only() -> None:
    """No list in the summary is long enough to be an hourly or 10-minute series."""

    def longest(x: Any) -> int:
        if isinstance(x, dict):
            return max((longest(v) for v in x.values()), default=0)
        if isinstance(x, list):
            return max([len(x)] + [longest(v) for v in x])
        return 0

    assert longest(json.loads(SUMMARY.read_text())) <= 64


_PRIVATE = (
    "DUTCHBAY_MET_MAST_617725_SOURCE",
    "DUTCHBAY_NASA_POWER_DIR",
    "BLUE_WHALE_POWER_CURVE_CSV",
)


@pytest.mark.skipif(
    not all(os.environ.get(k) for k in _PRIVATE),
    reason="needs the private mast, the reference files and the confidential curve",
)
def test_rerun_reproduces_the_committed_summary() -> None:
    from omegaconf import OmegaConf

    raw = OmegaConf.to_container(OmegaConf.load(CONF), resolve=True)
    assert isinstance(raw, dict)
    raw["output"] = {"summary_json": None, "rose_csv": None, "rose_png": None}
    out = cli.run(raw)
    committed = json.loads(SUMMARY.read_text())
    got = json.loads(json.dumps(out, sort_keys=True))
    assert got == committed
    assert (
        hashlib.sha256(json.dumps(got, sort_keys=True).encode()).hexdigest()
        == hashlib.sha256(json.dumps(committed, sort_keys=True).encode()).hexdigest()
    )
