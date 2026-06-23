"""
ERA5 Wind Data Processing for Dutch Bay Wind Farm
==================================================
Extracts wind speed data from ERA5 NetCDF and extrapolates to 150m hub height.

Author: DutchBay EPC Model Team
Date: 2025-12-21
Sprint: 10 (Wind AEP Pipeline)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, cast

import numpy as np
import pandas as pd
import xarray as xr

# Dutch Bay turbine coordinates (from ENVISION_ROAD-DATA.pdf)
TURBINE_LOCATIONS = {
    "T1": (8.297753, 79.756695),
    "T2": (8.292500, 79.754700),
    "T3": (8.288099, 79.752885),
    "T4": (8.282523, 79.750837),
    "T5": (8.278638, 79.747152),
    "T6": (8.279222, 79.753385),
    "T7": (8.274800, 79.745500),
    "T8": (8.275226, 79.754207),
    "T9": (8.270700, 79.744700),
    "T10": (8.270049, 79.752069),
    "T11": (8.268449, 79.748162),
    "T12": (8.263538, 79.743361),
    "T13": (8.259128, 79.742588),
    "T14": (8.254646, 79.746097),
    "T15": (8.252500, 79.741500),
}

HUB_HEIGHT = 150  # meters


@dataclass
class WindStats:
    """Wind statistics for a turbine location."""

    turbine_id: str
    latitude: float
    longitude: float
    mean_ws_150m: float
    std_ws_150m: float
    min_ws_150m: float
    max_ws_150m: float
    mean_alpha: float
    p50_ws_150m: float
    p75_ws_150m: float
    p90_ws_150m: float
    hours_data: int


def load_era5_netcdf(filepath: str) -> Tuple[xr.Dataset, str]:
    """Load ERA5 NetCDF file."""
    print(f"Loading ERA5 data from: {filepath}")
    ds = xr.open_dataset(filepath)
    print(f"✓ Loaded dataset with variables: {list(ds.data_vars)}")

    # Find time dimension (could be 'time' or 'valid_time')
    time_dim = None
    if "time" in ds.coords:
        time_dim = "time"
    elif "valid_time" in ds.coords:
        time_dim = "valid_time"
    else:
        raise ValueError(
            f"Cannot find time dimension. Available coords: {list(ds.coords)}"
        )

    print(f"✓ Time dimension: {time_dim}")
    print(f"✓ Time range: {ds[time_dim].values[0]} to {ds[time_dim].values[-1]}")
    print(f"✓ Number of time steps: {len(ds[time_dim])}")

    return ds, time_dim


def calculate_wind_speed(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Calculate wind speed magnitude from u/v components."""
    return cast(np.ndarray, np.sqrt(u**2 + v**2))


def extrapolate_to_hub_height(
    ws_low: np.ndarray,
    ws_high: np.ndarray,
    h_low: float,
    h_high: float,
    h_target: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extrapolate wind speed to target height using power law.

    Power law: ws(h) = ws(href) * (h/href)^alpha
    Alpha (wind shear coefficient) calculated from two known heights.
    """
    # Calculate alpha from two known heights
    with np.errstate(divide="ignore", invalid="ignore"):
        alpha = np.log(ws_high / ws_low) / np.log(h_high / h_low)

    # Constrain alpha to reasonable range (0.05 to 0.40 for coastal areas)
    alpha = np.clip(alpha, 0.05, 0.40)

    # Extrapolate to target height
    ws_target = ws_high * (h_target / h_high) ** alpha

    return ws_target, alpha


def process_turbine_location(
    ds: xr.Dataset, time_dim: str, turbine_id: str, lat: float, lon: float
) -> Tuple[pd.DataFrame, WindStats]:
    """Process wind data for a single turbine location."""
    print(f"Processing {turbine_id} at ({lat:.6f}, {lon:.6f})")

    # Select nearest grid point
    # ERA5 timeseries data is already extracted for a single point
    location_data = ds

    # Check available variables
    available_vars = list(location_data.data_vars)
    print(f"  Available variables: {available_vars}")

    # Try different ERA5 variable naming conventions
    u_vars = ["u100", "u100m", "u_component_of_wind_100m", "100m_u_component_of_wind"]
    v_vars = ["v100", "v100m", "v_component_of_wind_100m", "100m_v_component_of_wind"]
    u10_vars = ["u10", "u10m", "u_component_of_wind_10m", "10m_u_component_of_wind"]
    v10_vars = ["v10", "v10m", "v_component_of_wind_10m", "10m_v_component_of_wind"]

    # Find correct variable names
    u100_var = next((v for v in u_vars if v in available_vars), None)
    v100_var = next((v for v in v_vars if v in available_vars), None)
    u10_var = next((v for v in u10_vars if v in available_vars), None)
    v10_var = next((v for v in v10_vars if v in available_vars), None)

    if not all([u100_var, v100_var, u10_var, v10_var]):
        raise ValueError(
            f"Cannot find required wind variables. Available: {available_vars}"
        )

    # Extract wind components
    u100 = location_data[u100_var].values
    v100 = location_data[v100_var].values
    u10 = location_data[u10_var].values
    v10 = location_data[v10_var].values

    # Calculate wind speeds
    ws100 = calculate_wind_speed(u100, v100)
    ws10 = calculate_wind_speed(u10, v10)

    # Extrapolate to 150m hub height
    ws150, alpha = extrapolate_to_hub_height(ws10, ws100, 10, 100, HUB_HEIGHT)

    # Create dataframe
    df = pd.DataFrame(
        {
            "timestamp": location_data[time_dim].values,
            "turbine_id": turbine_id,
            "latitude": lat,
            "longitude": lon,
            "ws_10m": ws10,
            "ws_100m": ws100,
            "ws_150m": ws150,
            "wind_shear_alpha": alpha,
            "u_100m": u100,
            "v_100m": v100,
        }
    )

    # Calculate statistics
    stats = WindStats(
        turbine_id=turbine_id,
        latitude=lat,
        longitude=lon,
        mean_ws_150m=float(np.mean(ws150)),
        std_ws_150m=float(np.std(ws150)),
        min_ws_150m=float(np.min(ws150)),
        max_ws_150m=float(np.max(ws150)),
        mean_alpha=float(np.mean(alpha)),
        p50_ws_150m=float(np.percentile(ws150, 50)),
        p75_ws_150m=float(np.percentile(ws150, 75)),
        p90_ws_150m=float(np.percentile(ws150, 90)),
        hours_data=len(ws150),
    )

    print(f"  ✓ Mean wind speed at 150m: {stats.mean_ws_150m:.2f} m/s")
    print(f"  ✓ Mean wind shear alpha: {stats.mean_alpha:.3f}")

    return df, stats


def main():
    """Main processing pipeline."""
    print("=" * 70)
    print("ERA5 Wind Data Processing for Dutch Bay Wind Farm")
    print("=" * 70)

    # File paths
    netcdf_file = "reanalysis-era5-single-levels-timeseries-sfcaey35zsb.nc"
    output_dir = Path("wind_data_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir.absolute()}")

    # Load ERA5 data
    ds, time_dim = load_era5_netcdf(netcdf_file)

    # Process all turbines (ERA5 timeseries is single location - use center point)
    # We'll use the same wind data for all turbines as ERA5 is ~31km resolution
    print("\nNote: ERA5 timeseries data is for a single location (~31km grid).")
    print(
        "Using this data for all 15 turbine locations (acceptable for site assessment)."
    )

    all_data = []
    all_stats = []

    for turbine_id, (lat, lon) in TURBINE_LOCATIONS.items():
        df, stats = process_turbine_location(ds, time_dim, turbine_id, lat, lon)
        all_data.append(df)
        all_stats.append(stats)

    # Combine all turbine data
    df_combined = pd.concat(all_data, ignore_index=True)

    # Add temporal features
    df_combined["year"] = pd.to_datetime(df_combined["timestamp"]).dt.year
    df_combined["month"] = pd.to_datetime(df_combined["timestamp"]).dt.month
    df_combined["hour"] = pd.to_datetime(df_combined["timestamp"]).dt.hour

    # Save hourly data
    hourly_file = output_dir / "dutchbay_wind_150m_hourly.csv"
    df_combined.to_csv(hourly_file, index=False)
    print(f"\n✓ Saved hourly data: {hourly_file}")
    print(f"  Records: {len(df_combined):,}")

    # Save summary statistics
    stats_df = pd.DataFrame([vars(s) for s in all_stats])
    stats_file = output_dir / "dutchbay_wind_150m_summary.csv"
    stats_df.to_csv(stats_file, index=False)
    print(f"\n✓ Saved summary statistics: {stats_file}")

    # Calculate monthly averages per turbine
    monthly = (
        df_combined.groupby(["turbine_id", "month"])["ws_150m"].mean().reset_index()
    )
    monthly_file = output_dir / "dutchbay_wind_150m_monthly.csv"
    monthly.to_csv(monthly_file, index=False)
    print(f"✓ Saved monthly averages: {monthly_file}")

    # Calculate site-wide average
    site_avg = df_combined.groupby("timestamp")["ws_150m"].mean()
    site_stats = {
        "site": "Dutch Bay (15 turbines)",
        "mean_ws_150m": float(site_avg.mean()),
        "std_ws_150m": float(site_avg.std()),
        "p50_ws_150m": float(site_avg.quantile(0.50)),
        "p75_ws_150m": float(site_avg.quantile(0.75)),
        "p90_ws_150m": float(site_avg.quantile(0.90)),
        "hours_of_data": len(site_avg),
        "years_of_data": len(site_avg) / 8760,
    }

    site_file = output_dir / "dutchbay_site_average.json"
    with open(site_file, "w") as f:
        json.dump(site_stats, f, indent=2)
    print(f"✓ Saved site average: {site_file}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY - Wind Speed at 150m Hub Height")
    print("=" * 70)
    print(
        f"Data period: {site_stats['years_of_data']:.1f} years ({site_stats['hours_of_data']:,} hours)"
    )
    print(
        f"Site Average: {site_stats['mean_ws_150m']:.2f} ± {site_stats['std_ws_150m']:.2f} m/s"
    )
    print(f"P50 (Median): {site_stats['p50_ws_150m']:.2f} m/s")
    print(f"P75: {site_stats['p75_ws_150m']:.2f} m/s")
    print(f"P90: {site_stats['p90_ws_150m']:.2f} m/s")
    print("=" * 70)
    print(f"\nAll output files saved to: {output_dir.absolute()}")

    ds.close()

    return df_combined, stats_df


if __name__ == "__main__":
    df, stats = main()
