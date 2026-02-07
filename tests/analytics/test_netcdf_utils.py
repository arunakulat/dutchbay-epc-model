#!/usr/bin/env python
"""Test suite for NetCDF wind resource processing utilities.

Tests hub height extrapolation, shear exponent validation, CRS detection,
and Weibull parameter fitting.

Run:
    pytest tests/analytics/test_netcdf_utils.py -v --cov=analytics.gis.netcdf_utils

Coverage Target: >85%
Test Count: 12 test cases

Context:
    Sprint 17 - Issue #19: NetCDF Wind Resource Processing
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from analytics.gis.netcdf_utils import (
    SHEAR_EXPONENTS_IEC,
    compute_weibull_parameters,
    gis_netcdf_profile,
    grid_stats,
    ws150_from_10_100,
)


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_era5_dataset():
    """Create mock ECMWF ERA5 NetCDF dataset."""
    # Create coordinate arrays
    lon = np.arange(79.5, 82.0, 0.25)  # Dutch Bay region
    lat = np.arange(6.5, 10.0, 0.25)
    time = np.arange(0, 8760)  # 1 year hourly

    # Create wind component arrays (u/v at 10m and 100m)
    np.random.seed(42)
    shape = (len(time), len(lat), len(lon))

    u10 = 5.0 + 2.0 * np.random.randn(*shape)
    v10 = 3.0 + 1.5 * np.random.randn(*shape)
    u100 = u10 * 1.3  # Higher wind at 100m
    v100 = v10 * 1.3

    # Create xarray Dataset
    ds = xr.Dataset(
        {
            "u10": (["time", "latitude", "longitude"], u10),
            "v10": (["time", "latitude", "longitude"], v10),
            "u100": (["time", "latitude", "longitude"], u100),
            "v100": (["time", "latitude", "longitude"], v100),
        },
        coords={
            "longitude": lon,
            "latitude": lat,
            "time": time,
        },
    )

    ds.attrs["crs"] = "EPSG:4326"

    return ds


@pytest.fixture
def weibull_wind_timeseries():
    """Generate wind speed timeseries from Weibull distribution."""
    np.random.seed(44)
    # k=2.0, A=7.5 m/s
    return np.random.weibull(2.0, 8760) * 7.5


# ═════════════════════════════════════════════════════════════════════════════
# NETCDF PROFILE TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_gis_netcdf_profile(mock_era5_dataset):
    """Test extraction of CRS, bounds, and metadata from NetCDF."""
    profile = gis_netcdf_profile(mock_era5_dataset)

    assert profile["crs"] == "EPSG:4326"
    assert len(profile["bounds"]) == 4
    assert profile["bounds"][0] == 79.5  # lon_min
    assert profile["bounds"][3] == 9.75  # lat_max

    assert "dims" in profile
    assert profile["dims"]["time"] == 8760

    assert "variables" in profile
    assert "u10" in profile["variables"]
    assert "u100" in profile["variables"]


def test_grid_resolution_detection(mock_era5_dataset):
    """Test grid resolution detection."""
    profile = gis_netcdf_profile(mock_era5_dataset)

    assert profile["grid_resolution"] is not None
    dlon, dlat = profile["grid_resolution"]

    # ERA5 typically 0.25° resolution
    assert abs(dlon - 0.25) < 0.01
    assert abs(dlat - 0.25) < 0.01


# ═════════════════════════════════════════════════════════════════════════════
# HUB HEIGHT EXTRAPOLATION TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_ws150_extrapolation_power_law(mock_era5_dataset):
    """Test power law extrapolation from 100m to 150m."""
    ws150 = ws150_from_10_100(
        mock_era5_dataset,
        z_hub_m=150.0,
        shear_exponent=0.14,
        method="power_law"
    )

    # Check output structure
    assert ws150.name == "ws150"
    assert ws150.attrs["hub_height_m"] == 150.0
    assert ws150.attrs["shear_exponent"] == 0.14
    assert ws150.attrs["method"] == "power_law_extrapolation"

    # Wind speed at 150m should be higher than 100m
    u100 = mock_era5_dataset["u100"]
    v100 = mock_era5_dataset["v100"]
    ws100 = np.sqrt(u100**2 + v100**2)

    assert ws150.mean() > ws100.mean()


def test_shear_exponent_estimation(mock_era5_dataset):
    """Test automatic shear exponent estimation from 10m/100m."""
    ws150 = ws150_from_10_100(
        mock_era5_dataset,
        z_hub_m=150.0,
        shear_exponent=None,  # Auto-estimate
        method="power_law"
    )

    # Should have estimated shear exponent
    assert "shear_exponent_mean" in ws150.attrs
    alpha_mean = ws150.attrs["shear_exponent_mean"]

    # Typical range for open terrain
    assert 0.10 <= alpha_mean <= 0.25


def test_shear_exponent_validation():
    """Test that invalid shear exponents are rejected."""
    mock_ds = xr.Dataset(
        {
            "u10": (["time"], np.full(100, 5.0)),
            "v10": (["time"], np.full(100, 3.0)),
            "u100": (["time"], np.full(100, 6.5)),
            "v100": (["time"], np.full(100, 3.9)),
        },
        coords={"time": np.arange(100)}
    )

    # Shear exponent too high
    with pytest.raises(ValueError, match="Shear exponent must be in"):
        ws150_from_10_100(mock_ds, z_hub_m=150, shear_exponent=0.6)

    # Shear exponent negative
    with pytest.raises(ValueError, match="Shear exponent must be in"):
        ws150_from_10_100(mock_ds, z_hub_m=150, shear_exponent=-0.1)


def test_missing_wind_components():
    """Test error handling when required wind components missing."""
    mock_ds = xr.Dataset(
        {"u10": (["time"], np.full(100, 5.0))},  # Missing v10, u100, v100
        coords={"time": np.arange(100)}
    )

    with pytest.raises(ValueError, match="Missing required variables"):
        ws150_from_10_100(mock_ds, z_hub_m=150)


# ═════════════════════════════════════════════════════════════════════════════
# GRID STATISTICS TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_grid_stats_computation(mock_era5_dataset):
    """Test per-cell mean/std statistics."""
    ws150 = ws150_from_10_100(mock_era5_dataset, z_hub_m=150, shear_exponent=0.14)

    stats_df = grid_stats(ws150, dim="time")

    # Should have statistics for each grid cell
    assert len(stats_df) > 0
    assert "lon" in stats_df.columns
    assert "lat" in stats_df.columns
    assert "mean" in stats_df.columns
    assert "std" in stats_df.columns
    assert "min" in stats_df.columns
    assert "max" in stats_df.columns
    assert "count" in stats_df.columns

    # All statistics should be positive
    assert (stats_df["mean"] > 0).all()
    assert (stats_df["std"] >= 0).all()
    assert (stats_df["count"] == 8760).all()  # All timesteps valid


def test_grid_stats_missing_coords():
    """Test error when coordinates not detected."""
    mock_da = xr.DataArray(
        np.random.randn(100, 10),
        dims=["time", "x_unknown"],
        coords={"time": np.arange(100), "x_unknown": np.arange(10)}
    )

    with pytest.raises(ValueError, match="Could not detect lon/lat"):
        grid_stats(mock_da, dim="time")


# ═════════════════════════════════════════════════════════════════════════════
# WEIBULL FITTING TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_weibull_parameter_fitting(weibull_wind_timeseries):
    """Test Weibull A and k parameter fitting."""
    A, k = compute_weibull_parameters(weibull_wind_timeseries)

    # Should recover approximate original parameters (A=7.5, k=2.0)
    assert 6.5 <= A <= 8.5  # Allow ±1 m/s tolerance
    assert 1.8 <= k <= 2.2  # Allow ±0.2 tolerance

    # A should be close to mean wind speed
    mean_ws = weibull_wind_timeseries.mean()
    assert abs(A - mean_ws) / mean_ws < 0.15  # Within 15%


def test_weibull_with_zero_winds():
    """Test Weibull fitting with some zero wind speeds."""
    ws = np.concatenate([np.zeros(100), np.random.weibull(2.0, 500) * 7.0])

    A, k = compute_weibull_parameters(ws)

    # Should still fit successfully (zeros removed)
    assert A > 0
    assert k > 0


def test_weibull_all_zeros():
    """Test error handling with all-zero wind speeds."""
    ws = np.zeros(1000)

    with pytest.raises(ValueError, match="No valid wind speed data"):
        compute_weibull_parameters(ws)


# ═════════════════════════════════════════════════════════════════════════════
# IEC SHEAR EXPONENT TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_iec_shear_exponents():
    """Test that IEC 61400-1 shear exponents are defined."""
    assert "offshore" in SHEAR_EXPONENTS_IEC
    assert "open_rural" in SHEAR_EXPONENTS_IEC
    assert "agricultural" in SHEAR_EXPONENTS_IEC

    # Offshore should be lowest
    assert SHEAR_EXPONENTS_IEC["offshore"] < SHEAR_EXPONENTS_IEC["open_rural"]

    # Forest should be highest
    assert SHEAR_EXPONENTS_IEC["forest"] > SHEAR_EXPONENTS_IEC["suburban"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=analytics.gis.netcdf_utils"])
