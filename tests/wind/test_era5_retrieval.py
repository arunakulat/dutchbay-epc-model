"""Tests for the config-driven ERA5 retrieval feature (issue #177).

The live CDS retrieval is not exercised in CI; the processing + AEP path is tested on a
synthetic ERA5-like dataset, and config + credential handling are unit-tested.
"""

from __future__ import annotations

import stat

import numpy as np
import pandas as pd
import pytest

from wind_resource.era5_retrieval import (
    ERA5RequestConfig,
    build_hub_height_series,
    compute_site_aep,
    ensure_cdsapirc,
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
    )


def test_config_from_yaml(tmp_path):
    yml = tmp_path / "req.yaml"
    yml.write_text(
        "project:\n  name: X\n  latitude: 8.27\n  longitude: 79.75\n"
        "download:\n  years:\n    start: 2020\n    end: 2024\n"
        "turbine:\n  num_turbines: 23\n"
    )
    c = ERA5RequestConfig.from_yaml(str(yml))
    assert c.project_name == "X"
    assert c.latitude == 8.27
    assert (c.start_year, c.end_year) == (2020, 2024)
    assert c.date_range == "2020-01-01/2024-12-31"


def test_build_hub_height_series(tmp_path, cfg):
    nc = _synthetic_era5_nc(tmp_path)
    df = build_hub_height_series(nc, cfg)
    assert len(df) == 168
    assert "ws_150m" in df.columns
    assert df["wind_shear_alpha"].between(cfg.alpha_min, cfg.alpha_max).all()
    assert df["ws_150m"].mean() > 0


def test_compute_site_aep(tmp_path, cfg):
    nc = _synthetic_era5_nc(tmp_path, hours=8760)
    df = build_hub_height_series(nc, cfg)
    res = compute_site_aep(df, cfg)
    assert res["net_aep_p50_gwh"] > 0
    assert 0.0 < res["capacity_factor_p50"] < 1.0
    assert res["hours"] == 8760


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
