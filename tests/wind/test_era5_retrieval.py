"""Tests for the config-driven ERA5 retrieval feature (issues #177, #178).

The live CDS retrieval is not exercised in CI; the processing + AEP path, the
``latest`` reference resolution + vintage, and the coverage guard are unit-tested on a
synthetic ERA5-like dataset.
"""

from __future__ import annotations

import datetime as dt
import stat

import numpy as np
import pandas as pd
import pytest

from wind_resource.era5_retrieval import (
    ERA5CoverageError,
    ERA5RequestConfig,
    _met_direction_deg,
    build_hub_height_series,
    build_production_wind_rose,
    compute_site_aep,
    ensure_cdsapirc,
    expected_hours_for_years,
    validate_coverage,
)


def _synthetic_era5_nc(tmp_path, hours: int = 168):
    """Write a tiny ERA5-timeseries-like NetCDF (u/v at 10m & 100m + sp)."""
    import xarray as xr

    t = pd.date_range("2023-01-01", periods=hours, freq="h")
    rng = np.random.default_rng(42)
    ws100 = rng.weibull(2.5, hours) * 8.0  # ~7 m/s mean at 100 m
    ws10 = ws100 / (100.0 / 10.0) ** 0.12  # implied shear alpha ~0.12
    ds = xr.Dataset(
        {
            "u10": ("valid_time", ws10 * 0.8),
            "v10": ("valid_time", ws10 * 0.6),
            "u100": ("valid_time", ws100 * 0.8),
            "v100": ("valid_time", ws100 * 0.6),
            "sp": ("valid_time", np.full(hours, 101000.0)),
        },
        coords={"valid_time": t, "latitude": 8.25, "longitude": 79.75},
    )
    path = tmp_path / "era5_ts.nc"
    ds.to_netcdf(path)
    return path


@pytest.fixture
def cfg() -> ERA5RequestConfig:
    return ERA5RequestConfig(
        project_name="Test Site",
        latitude=8.27,
        longitude=79.75,
        start_year=2023,
        end_year=2023,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
    )


def test_config_from_yaml_fixed(tmp_path):
    yml = tmp_path / "req.yaml"
    yml.write_text(
        "project:\n  name: X\n  latitude: 8.27\n  longitude: 79.75\n"
        "download:\n  years:\n    start: 2020\n    end: 2024\n"
        # Turbine identity is config-required (ARCH-01: no EN-171/23/150 defaults).
        "turbine:\n  model: iea_reference_10mw\n  num_turbines: 15\n  hub_height_m: 150\n"
    )
    c = ERA5RequestConfig.from_yaml(str(yml))
    assert c.project_name == "X"
    assert c.latitude == 8.27
    assert (c.start_year, c.end_year) == (2020, 2024)
    assert c.reference_mode == "fixed"
    assert c.date_range == "2020-01-01/2024-12-31"


def test_latest_reference_resolution(tmp_path):
    yml = tmp_path / "req.yaml"
    yml.write_text(
        "project:\n  name: L\n  latitude: 8.27\n  longitude: 79.75\n"
        "download:\n  reference:\n    mode: latest\n    n_years: 20\n    end_year_lag: 2\n"
        "turbine:\n  model: iea_reference_10mw\n  num_turbines: 15\n  hub_height_m: 150\n"
    )
    c = ERA5RequestConfig.from_yaml(str(yml))
    end = dt.date.today().year - 2
    assert c.reference_mode == "latest"
    assert (c.start_year, c.end_year) == (end - 19, end)
    assert c.end_year - c.start_year + 1 == 20
    assert c.resolved_at  # vintage timestamp recorded


def test_expected_hours_leap_aware():
    assert expected_hours_for_years(2023, 2023) == 8760
    assert expected_hours_for_years(2024, 2024) == 8784  # leap year
    assert expected_hours_for_years(2005, 2024) == 175320  # 20 yr, 5 leap


def test_build_hub_height_series(tmp_path, cfg):
    nc = _synthetic_era5_nc(tmp_path)
    df = build_hub_height_series(nc, cfg)
    assert len(df) == 168
    assert "ws_150m" in df.columns
    assert df["wind_shear_alpha"].between(cfg.alpha_min, cfg.alpha_max).all()
    assert df["ws_150m"].mean() > 0


def test_met_direction_convention_matches_fetcher_formula():
    # Wind blowing FROM the west (u<0, v=0) is a westerly => 270 deg in met convention.
    # (u,v) is the vector the wind blows TOWARD; a westerly moves air eastward (u>0),
    # so u>0, v=0 gives 270 deg. Cross-check the four cardinal cases against the exact
    # formula reused from era5_fetcher._calculate_wind_metrics (issue #853.1).
    u = np.array([0.0, 5.0, 0.0, -5.0])  # toward N, E, S, W
    v = np.array([5.0, 0.0, -5.0, 0.0])
    wd = _met_direction_deg(u, v)
    # Air moving toward North came FROM South => 180; toward East came from West => 270;
    # toward South came from North => 0/360; toward West came from East => 90.
    np.testing.assert_allclose(wd, [180.0, 270.0, 0.0, 90.0], atol=1e-9)
    # Identical to the legacy gridded fetcher's own formula on the same inputs.
    expected = (180.0 + np.rad2deg(np.arctan2(u, v))) % 360.0
    np.testing.assert_allclose(wd, expected, atol=1e-12)


def test_build_hub_height_series_carries_direction(tmp_path, cfg):
    # The production series now exports met-convention wind DIRECTION at 10 m and 100 m,
    # derived from the SAME u/v components as the speed (issue #853.1) — display/derivation
    # only. The synthetic NC fixes (u,v) = (0.8, 0.6)*ws, a constant SW-ish bearing.
    nc = _synthetic_era5_nc(tmp_path)
    df = build_hub_height_series(nc, cfg)
    assert {"wd_10m", "wd_100m"}.issubset(df.columns)
    assert df["wd_10m"].between(0.0, 360.0).all()
    assert df["wd_100m"].between(0.0, 360.0).all()
    # u=0.8, v=0.6 (both proportional at 10 m and 100 m) => a single, IDENTICAL bearing.
    expected = float((180.0 + np.rad2deg(np.arctan2(0.8, 0.6))) % 360.0)
    assert df["wd_10m"].std() == pytest.approx(0.0, abs=1e-9)
    assert df["wd_10m"].iloc[0] == pytest.approx(expected, abs=1e-6)
    assert df["wd_100m"].iloc[0] == pytest.approx(expected, abs=1e-6)


def test_compute_site_aep(tmp_path, cfg):
    nc = _synthetic_era5_nc(tmp_path, hours=8760)
    df = build_hub_height_series(nc, cfg)
    res = compute_site_aep(df, cfg)
    assert res["net_aep_p50_gwh"] > 0
    assert 0.0 < res["capacity_factor_p50"] < 1.0
    assert res["hours"] == 8760


def _directional_era5_nc(tmp_path, hours: int = 168):
    """A synthetic ERA5-timeseries NC whose winds ROTATE through all bearings.

    Sweeps a full 360-deg rotation across the hours (and holds a strong, above-calm
    speed) so the derived rose populates every sector and the energy enrichment is
    exercised — unlike the constant-direction :func:`_synthetic_era5_nc`.
    """
    import xarray as xr

    t = pd.date_range("2023-01-01", periods=hours, freq="h")
    ang = np.linspace(0.0, 2.0 * np.pi, hours, endpoint=False)
    speed100 = 10.0  # well above the 2 m/s calm cut-off so nothing is dropped
    u100 = speed100 * np.cos(ang)
    v100 = speed100 * np.sin(ang)
    # 10 m winds share the direction (same angle) at a lower speed => a sane shear.
    speed10 = speed100 / (100.0 / 10.0) ** 0.14
    ds = xr.Dataset(
        {
            "u10": ("valid_time", speed10 * np.cos(ang)),
            "v10": ("valid_time", speed10 * np.sin(ang)),
            "u100": ("valid_time", u100),
            "v100": ("valid_time", v100),
            "sp": ("valid_time", np.full(hours, 101000.0)),
        },
        coords={"valid_time": t, "latitude": 8.25, "longitude": 79.75},
    )
    path = tmp_path / "era5_dir.nc"
    ds.to_netcdf(path)
    return path


def test_build_production_wind_rose_from_series(tmp_path, cfg):
    # A rose derived from the REAL production series (issue #853.1): reuses the canonical
    # build_wind_rose with the #826 speed enrichment. Display/derivation only.
    nc = _directional_era5_nc(tmp_path, hours=360)
    df = build_hub_height_series(nc, cfg)
    rose = build_production_wind_rose(df, cfg)
    # Default 12 sectors (config-first override honoured elsewhere).
    assert rose["n_sectors"] == 12
    assert len(rose["frequency"]) == 12
    # Full-rotation winds => every sector populated (no empty bin) and freq sums to 1.
    assert all(c > 0 for c in rose["count"])
    # Per-sector freqs are each rounded to 6dp, so the sum is 1.0 within rounding slack.
    assert sum(rose["frequency"]) == pytest.approx(1.0, abs=1e-4)
    assert sum(rose["count"]) == 360
    # Speed enrichment (#826) present since ws_series was supplied; no calm samples at 10 m/s.
    assert rose["n_calm"] == 0
    assert "energy_frequency" in rose and "sector_weibull" in rose
    assert rose["provenance_note"]  # coarse single-cell ERA5 caveat


def test_build_production_wind_rose_honours_config_sectors(tmp_path):
    c = ERA5RequestConfig(
        project_name="S",
        latitude=8.27,
        longitude=79.75,
        start_year=2023,
        end_year=2023,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        wind_rose_sectors=8,
    )
    nc = _directional_era5_nc(tmp_path, hours=240)
    df = build_hub_height_series(nc, c)
    rose = build_production_wind_rose(df, c)
    assert rose["n_sectors"] == 8
    assert len(rose["sector_deg"]) == 8


def test_wind_rose_sectors_config_default_and_override(tmp_path):
    yml = tmp_path / "req.yaml"
    yml.write_text(
        "project:\n  name: X\n  latitude: 8.27\n  longitude: 79.75\n"
        "download:\n  years:\n    start: 2023\n    end: 2023\n  wind_rose_sectors: 16\n"
        "turbine:\n  model: iea_reference_10mw\n  num_turbines: 15\n  hub_height_m: 150\n"
    )
    assert ERA5RequestConfig.from_yaml(str(yml)).wind_rose_sectors == 16
    # Absent key => the build_wind_rose-matching default of 12.
    yml2 = tmp_path / "req2.yaml"
    yml2.write_text(
        "project:\n  name: X\n  latitude: 8.27\n  longitude: 79.75\n"
        "download:\n  years:\n    start: 2023\n    end: 2023\n"
        "turbine:\n  model: iea_reference_10mw\n  num_turbines: 15\n  hub_height_m: 150\n"
    )
    assert ERA5RequestConfig.from_yaml(str(yml2)).wind_rose_sectors == 12


def test_validate_coverage_complete(tmp_path, cfg):
    nc = _synthetic_era5_nc(tmp_path, hours=8760)  # full 2023
    df = build_hub_height_series(nc, cfg)
    info = validate_coverage(df, cfg)
    assert info["coverage_complete"]
    assert info["expected_hours"] == 8760
    assert info["missing_hours"] == 0


def test_validate_coverage_short_raises(tmp_path, cfg):
    nc = _synthetic_era5_nc(tmp_path, hours=8640)  # 120 h short (latency edge)
    df = build_hub_height_series(nc, cfg)
    with pytest.raises(ERA5CoverageError, match="coverage incomplete"):
        validate_coverage(df, cfg)


def test_validate_coverage_warn_only(tmp_path):
    c = ERA5RequestConfig(
        project_name="W",
        latitude=8.27,
        longitude=79.75,
        start_year=2023,
        end_year=2023,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        strict_coverage=False,
    )
    nc = _synthetic_era5_nc(tmp_path, hours=8640)
    df = build_hub_height_series(nc, c)
    info = validate_coverage(df, c)  # warns, does not raise
    assert not info["coverage_complete"]
    assert info["missing_hours"] == 120


def test_ensure_cdsapirc_writes_from_args(tmp_path):
    rc = tmp_path / ".cdsapirc"
    ensure_cdsapirc(url="https://example/api", key="tok", path=str(rc))
    assert rc.exists() and "tok" in rc.read_text()
    assert stat.S_IMODE(rc.stat().st_mode) == 0o600


def test_ensure_cdsapirc_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CDSAPI_URL", raising=False)
    monkeypatch.delenv("CDSAPI_KEY", raising=False)
    with pytest.raises(FileNotFoundError):
        ensure_cdsapirc(path=str(tmp_path / "nope.cdsapirc"))
