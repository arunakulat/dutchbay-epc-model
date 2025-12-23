#!/usr/bin/env python
"""NetCDF wind resource processing utilities for ERA5/ECMWF reanalysis data.

Implements hub height extrapolation following NREL best practices and
IEC 61400-1 wind resource characterization methodology.

Usage:
    from analytics.gis.netcdf_utils import ws150_from_10_100, gis_netcdf_profile
    
    import xarray as xr
    
    # Load ECMWF ERA5 NetCDF
    ds = xr.open_dataset('era5_wind_2020_2024.nc')
    
    # Extract geospatial profile
    profile = gis_netcdf_profile(ds)
    print(f"CRS: {profile['crs']}, Bounds: {profile['bounds']}")
    
    # Extrapolate to 150m hub height
    ws150_da = ws150_from_10_100(
        ds,
        z_hub_m=150,
        shear_exponent=0.14,  # IEC 61400-1 default for rural terrain
        method='power_law'
    )
    
    # Compute grid statistics
    stats_df = grid_stats(ws150_da)

References:
    - NREL TP-5000-88588: Resource Assessment for Distributed Wind Energy
    - IEC 61400-1 Ed4: Wind resource characterization for power performance
    - Copernicus ERA5 reanalysis: https://cds.climate.copernicus.eu/
    - NREL System Advisor Model (SAM) wind module methodology

Context:
    Sprint 17 - Issue #19: NetCDF Wind Resource Processing
    Part of GIS → EPC resource loader pipeline for DutchBay 150 MW project
    
GWTF Compliance:
    Module import must be safe even when optional geo deps are absent.
    If optional dependencies (e.g., pyproj) are required for a function,
    raise a clear ImportError at call-time (not import-time).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr

# Optional dependency: pyproj for CRS transformations
try:
    from pyproj import CRS  # type: ignore[import-untyped]
    _PYPROJ_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    CRS = None  # type: ignore[assignment,misc]
    _PYPROJ_AVAILABLE = False

logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# CONSTANTS AND DEFAULTS
# ═════════════════════════════════════════════════════════════════════════════

# IEC 61400-1 Ed4 recommended shear exponents by terrain type
SHEAR_EXPONENTS_IEC = {
    "offshore": 0.10,
    "open_rural": 0.14,
    "agricultural": 0.16,
    "suburban": 0.20,
    "forest": 0.25,
}

# Valid shear exponent range (physically realistic)
SHEAR_EXP_MIN = 0.0
SHEAR_EXP_MAX = 0.5

# Standard measurement heights in ERA5/MERRA-2
STANDARD_HEIGHTS_M = [10, 50, 100, 150, 200]


def _require_pyproj() -> None:
    """Guard for optional dependency pyproj.
    
    Raises:
        ImportError: if pyproj is not installed.
    """
    if not _PYPROJ_AVAILABLE:
        raise ImportError(
            "pyproj is required for CRS/coordinate transforms. "
            "Install with: pip install pyproj"
        )


def gis_netcdf_profile(ds: xr.Dataset) -> Dict[str, Any]:
    """Extract CRS, bounds, dimensions, variables, and time range from NetCDF.
    
    Supports ECMWF ERA5, MERRA-2, and NREL Wind Toolkit (WTK) formats.
    
    Args:
        ds: xarray Dataset from NetCDF file
    
    Returns:
        Dictionary with:
            - crs: CRS string (EPSG code or WKT)
            - bounds: (lon_min, lat_min, lon_max, lat_max)
            - dims: Dimension names and sizes
            - variables: List of data variable names
            - time_range: (start_date, end_date) if time dimension exists
            - grid_resolution: (dlon, dlat) in degrees
    
    Example:
        >>> ds = xr.open_dataset('era5_wind_dutchbay.nc')
        >>> profile = gis_netcdf_profile(ds)
        >>> profile['crs']
        'EPSG:4326'
        >>> profile['bounds']
        (79.5, 6.5, 82.0, 10.0)  # Dutch Bay region, Sri Lanka
    """
    profile: Dict[str, Any] = {}
    
    # Detect CRS (most wind datasets use WGS84 / EPSG:4326)
    if hasattr(ds, 'crs'):
        profile['crs'] = str(ds.crs)
    elif 'spatial_ref' in ds.attrs:
        profile['crs'] = ds.attrs['spatial_ref']
    else:
        # Default assumption for ERA5/MERRA-2
        profile['crs'] = 'EPSG:4326'
        logger.warning("CRS not found in NetCDF, assuming EPSG:4326 (WGS84)")
    
    # Detect coordinate names (ERA5 uses 'longitude'/'latitude', WTK uses 'lon'/'lat')
    lon_names = ['longitude', 'lon', 'x']
    lat_names = ['latitude', 'lat', 'y']
    
    lon_var = None
    lat_var = None
    
    for name in lon_names:
        if name in ds.coords:
            lon_var = name
            break
    
    for name in lat_names:
        if name in ds.coords:
            lat_var = name
            break
    
    if lon_var is None or lat_var is None:
        raise ValueError(
            f"Could not detect lon/lat coordinates in NetCDF. "
            f"Available coords: {list(ds.coords.keys())}"
        )
    
    # Extract bounds
    lon_vals = ds[lon_var].values
    lat_vals = ds[lat_var].values
    
    profile['bounds'] = (
        float(lon_vals.min()),
        float(lat_vals.min()),
        float(lon_vals.max()),
        float(lat_vals.max())
    )
    
    # Grid resolution
    if len(lon_vals) > 1:
        dlon = float(np.median(np.diff(lon_vals)))
        dlat = float(np.median(np.diff(lat_vals)))
        profile['grid_resolution'] = (abs(dlon), abs(dlat))
    else:
        profile['grid_resolution'] = None
    
    # Dimensions
    profile['dims'] = {name: int(size) for name, size in ds.dims.items()}
    
    # Data variables
    profile['variables'] = list(ds.data_vars.keys())
    
    # Time range
    if 'time' in ds.coords:
        time_vals = pd.to_datetime(ds['time'].values)
        profile['time_range'] = (
            str(time_vals.min()),
            str(time_vals.max())
        )
        profile['time_steps'] = len(time_vals)
    else:
        profile['time_range'] = None
        profile['time_steps'] = None
    
    logger.info(
        f"NetCDF Profile: CRS={profile['crs']}, "
        f"Bounds={profile['bounds']}, "
        f"Grid Resolution={profile['grid_resolution']}, "
        f"Time Steps={profile['time_steps']}"
    )
    
    return profile


def ws150_from_10_100(
    ds: xr.Dataset,
    z_hub_m: float = 150.0,
    shear_exponent: Optional[float] = None,
    method: str = 'power_law',
    u10_var: str = 'u10',
    u100_var: str = 'u100',
    v10_var: str = 'v10',
    v100_var: str = 'v100'
) -> xr.DataArray:
    """Extrapolate wind speed from 10m/100m to hub height using power law.
    
    Implements IEC 61400-1 Ed4 wind shear extrapolation methodology:
        V(h) = V(h_ref) * (h / h_ref) ^ α
    
    where α is the shear exponent (default 0.14 for rural terrain).
    
    Args:
        ds: xarray Dataset with u/v wind components at 10m and 100m
        z_hub_m: Target hub height (m). Default 150m for Envision EN-171-6.5
        shear_exponent: Power law shear exponent. If None, estimated from
            10m and 100m wind speeds. Valid range: [0.0, 0.5]
        method: Extrapolation method ('power_law' only for now)
        u10_var: Name of u-component at 10m variable
        u100_var: Name of u-component at 100m variable
        v10_var: Name of v-component at 10m variable
        v100_var: Name of v-component at 100m variable
    
    Returns:
        xarray DataArray with wind speed at hub height (m/s)
    
    Raises:
        ValueError: If required variables missing or shear exponent invalid
    
    Example:
        >>> ds = xr.open_dataset('era5_wind_2020_2024.nc')
        >>> ws150 = ws150_from_10_100(ds, z_hub_m=150, shear_exponent=0.14)
        >>> ws150.mean().values
        7.42  # Mean wind speed at 150m hub height
    
    References:
        - IEC 61400-1 Ed4 Section 6.3 - Wind shear
        - NREL SAM Wind Module - Hub height extrapolation
    """
    if method != 'power_law':
        raise ValueError(f"Only 'power_law' method supported, got '{method}'")
    
    # Check required variables
    required_vars = [u10_var, u100_var, v10_var, v100_var]
    missing = [v for v in required_vars if v not in ds.data_vars]
    if missing:
        raise ValueError(
            f"Missing required variables in NetCDF: {missing}. "
            f"Available: {list(ds.data_vars.keys())}"
        )
    
    # Compute wind speed magnitude at 10m and 100m
    ws10 = np.sqrt(ds[u10_var]**2 + ds[v10_var]**2)
    ws100 = np.sqrt(ds[u100_var]**2 + ds[v100_var]**2)
    
    # Estimate shear exponent if not provided
    if shear_exponent is None:
        # α = ln(ws100 / ws10) / ln(100 / 10)
        # Avoid division by zero
        ws10_safe = ws10.where(ws10 > 0.1, 0.1)
        alpha = np.log(ws100 / ws10_safe) / np.log(100.0 / 10.0)
        
        # Clip to physically realistic range
        alpha = alpha.clip(SHEAR_EXP_MIN, SHEAR_EXP_MAX)
        
        logger.info(
            f"Estimated shear exponent α: mean={float(alpha.mean()):.3f}, "
            f"std={float(alpha.std()):.3f}"
        )
    else:
        # Validate provided shear exponent
        if not (SHEAR_EXP_MIN <= shear_exponent <= SHEAR_EXP_MAX):
            raise ValueError(
                f"Shear exponent must be in [{SHEAR_EXP_MIN}, {SHEAR_EXP_MAX}], "
                f"got {shear_exponent}"
            )
        alpha = shear_exponent
        logger.info(f"Using provided shear exponent α = {alpha}")
    
    # Extrapolate to hub height using power law from 100m reference
    # V(h_hub) = V(100m) * (h_hub / 100) ^ α
    ws_hub = ws100 * (z_hub_m / 100.0) ** alpha
    
    # Add metadata
    ws_hub.name = f'ws{int(z_hub_m)}'
    ws_hub.attrs['long_name'] = f'Wind speed at {z_hub_m}m hub height'
    ws_hub.attrs['units'] = 'm/s'
    ws_hub.attrs['hub_height_m'] = z_hub_m
    ws_hub.attrs['method'] = 'power_law_extrapolation'
    ws_hub.attrs['reference_height_m'] = 100.0
    if isinstance(alpha, (int, float)):
        ws_hub.attrs['shear_exponent'] = float(alpha)
    else:
        ws_hub.attrs['shear_exponent_mean'] = float(alpha.mean())
    ws_hub.attrs['iec_standard'] = 'IEC 61400-1 Ed4 Section 6.3'
    
    logger.info(
        f"Extrapolated wind speed to {z_hub_m}m hub height: "
        f"mean={float(ws_hub.mean()):.2f} m/s, "
        f"max={float(ws_hub.max()):.2f} m/s"
    )
    
    return ws_hub


def grid_stats(da: xr.DataArray, dim: str = 'time') -> pd.DataFrame:
    """Compute per-cell mean and standard deviation statistics.
    
    Args:
        da: xarray DataArray (e.g., wind speed at hub height)
        dim: Dimension to aggregate over (default 'time')
    
    Returns:
        DataFrame with columns:
            - lon: Longitude
            - lat: Latitude
            - mean: Mean value
            - std: Standard deviation
            - min: Minimum value
            - max: Maximum value
            - count: Number of valid samples
    
    Example:
        >>> ws150 = ws150_from_10_100(ds, z_hub_m=150)
        >>> stats = grid_stats(ws150, dim='time')
        >>> stats.head()
           lon   lat   mean   std   min   max  count
        0  79.5  6.5   7.42  2.31  1.20 18.50   8760
        1  79.5  6.6   7.38  2.28  1.15 18.30   8760
    """
    # Detect coordinate names
    lon_names = ['longitude', 'lon', 'x']
    lat_names = ['latitude', 'lat', 'y']
    
    lon_var = None
    lat_var = None
    
    for name in lon_names:
        if name in da.coords:
            lon_var = name
            break
    
    for name in lat_names:
        if name in da.coords:
            lat_var = name
            break
    
    if lon_var is None or lat_var is None:
        raise ValueError(
            f"Could not detect lon/lat coordinates. "
            f"Available: {list(da.coords.keys())}"
        )
    
    # Compute statistics along time dimension
    mean_da = da.mean(dim=dim)
    std_da = da.std(dim=dim)
    min_da = da.min(dim=dim)
    max_da = da.max(dim=dim)
    count_da = da.count(dim=dim)
    
    # Stack into DataFrame
    df = pd.DataFrame({
        'lon': mean_da[lon_var].values.ravel(),
        'lat': mean_da[lat_var].values.ravel(),
        'mean': mean_da.values.ravel(),
        'std': std_da.values.ravel(),
        'min': min_da.values.ravel(),
        'max': max_da.values.ravel(),
        'count': count_da.values.ravel(),
    })
    
    # Remove NaN rows
    df = df.dropna()
    
    logger.info(
        f"Grid statistics computed: {len(df)} cells, "
        f"mean wind speed {df['mean'].mean():.2f} m/s"
    )
    
    return df


def compute_weibull_parameters(
    ws_timeseries: np.ndarray
) -> Tuple[float, float]:
    """Fit Weibull A and k parameters from wind speed timeseries.
    
    Uses maximum likelihood estimation (MLE) for robust parameter fitting.
    Weibull distribution: f(v; A, k) = (k/A) * (v/A)^(k-1) * exp(-(v/A)^k)
    
    Args:
        ws_timeseries: Wind speed timeseries (m/s), 1D array
    
    Returns:
        Tuple of (A, k) where:
            - A: Scale parameter (m/s), approximately mean wind speed
            - k: Shape parameter (dimensionless), typically 1.5-3.0 for wind
    
    Example:
        >>> ws = np.random.weibull(2.0, 8760) * 7.5
        >>> A, k = compute_weibull_parameters(ws)
        >>> print(f"Weibull A={A:.2f} m/s, k={k:.2f}")
        Weibull A=6.65 m/s, k=2.01
    
    References:
        - IEC 61400-1 Ed4 Annex C - Weibull distribution for wind resource
        - NREL SAM Weibull parameter estimation
    """
    from scipy.stats import weibull_min
    
    # Remove zeros and negative values
    ws_clean = ws_timeseries[ws_timeseries > 0]
    
    if len(ws_clean) == 0:
        raise ValueError("No valid wind speed data (all zeros or negative)")
    
    # Fit Weibull distribution using MLE
    shape, loc, scale = weibull_min.fit(ws_clean, floc=0)
    
    # Weibull parameters: k = shape, A = scale
    k = shape
    A = scale
    
    logger.info(
        f"Weibull fit: A={A:.2f} m/s, k={k:.2f} "
        f"(mean wind speed: {ws_clean.mean():.2f} m/s)"
    )
    
    return A, k


__all__ = [
    "SHEAR_EXPONENTS_IEC",
    "gis_netcdf_profile",
    "ws150_from_10_100",
    "grid_stats",
    "compute_weibull_parameters",
]
