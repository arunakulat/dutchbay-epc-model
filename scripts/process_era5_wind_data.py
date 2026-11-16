"""
ERA5 wind data processing for a wind farm's turbine positions.
==============================================================
Extracts wind speed data from an ERA5 NetCDF and extrapolates it to the hub height at each
counted turbine position of a layout file.

The layout comes from configuration, never from this script (#1775): a YAML file holding a
``layout.turbines`` list, at its top level or under one top-level block, each entry with
``id``, ``lat_deg``, ``lon_deg`` and an optional ``role``. Only ``role: counted`` entries (or
entries without a role) are processed; an ``external_waker`` stands in the flow but belongs
to another project, so it is listed and skipped. The hub height comes from the same block's
``turbine.hub_height_m`` and is required: no hub height is assumed. DutchBay's layout is
``conf/dutchbay_wake_14_turbines.yaml``.

Usage::

    python scripts/process_era5_wind_data.py <era5.nc> <layout.yaml> [<output_dir>]

Author: DutchBay EPC Model Team
Date: 2025-12-21
Sprint: 10 (Wind AEP Pipeline)
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple, cast

import numpy as np
import pandas as pd
import xarray as xr
import yaml

#: The role of a turbine whose energy belongs to the layout's own project.
COUNTED_ROLE = "counted"


@dataclass
class WindStats:
    """Wind statistics for a turbine location."""

    turbine_id: str
    latitude: float
    longitude: float
    hub_height_m: float
    mean_ws_hub: float
    std_ws_hub: float
    min_ws_hub: float
    max_ws_hub: float
    mean_alpha: float
    p50_ws_hub: float
    p75_ws_hub: float
    p90_ws_hub: float
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
    ds: xr.Dataset,
    time_dim: str,
    turbine_id: str,
    lat: float,
    lon: float,
    hub_height_m: float,
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

    # Extrapolate to the layout's hub height
    ws_hub, alpha = extrapolate_to_hub_height(ws10, ws100, 10, 100, hub_height_m)

    # Create dataframe
    df = pd.DataFrame(
        {
            "timestamp": location_data[time_dim].values,
            "turbine_id": turbine_id,
            "latitude": lat,
            "longitude": lon,
            "ws_10m": ws10,
            "ws_100m": ws100,
            "ws_hub": ws_hub,
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
        hub_height_m=float(hub_height_m),
        mean_ws_hub=float(np.mean(ws_hub)),
        std_ws_hub=float(np.std(ws_hub)),
        min_ws_hub=float(np.min(ws_hub)),
        max_ws_hub=float(np.max(ws_hub)),
        mean_alpha=float(np.mean(alpha)),
        p50_ws_hub=float(np.percentile(ws_hub, 50)),
        p75_ws_hub=float(np.percentile(ws_hub, 75)),
        p90_ws_hub=float(np.percentile(ws_hub, 90)),
        hours_data=len(ws_hub),
    )

    print(f"  ✓ Mean wind speed at {hub_height_m:g} m: {stats.mean_ws_hub:.2f} m/s")
    print(f"  ✓ Mean wind shear alpha: {stats.mean_alpha:.3f}")

    return df, stats


def _layout_holder(layout_file: str) -> Mapping[str, Any]:
    """The one mapping in ``layout_file`` that holds ``layout`` (top level or one block)."""
    doc = yaml.safe_load(Path(layout_file).read_text(encoding="utf-8"))
    if not isinstance(doc, Mapping):
        raise ValueError(f"{layout_file}: must hold a mapping")
    holders: List[Mapping[str, Any]] = []
    if isinstance(doc.get("layout"), Mapping):
        holders.append(doc)
    holders += [
        v
        for v in doc.values()
        if isinstance(v, Mapping) and isinstance(v.get("layout"), Mapping)
    ]
    if len(holders) != 1:
        raise ValueError(
            f"{layout_file}: expected exactly one layout.turbines list, "
            f"found {len(holders)}"
        )
    return holders[0]


def load_hub_height(layout_file: str) -> float:
    """Read the hub height (m) from ``turbine.hub_height_m`` beside the layout.

    Args:
        layout_file: The layout YAML (see :func:`load_turbine_layout`).

    Returns:
        The hub height in metres.

    Raises:
        ValueError: The layout's block declares no positive ``turbine.hub_height_m``.
    """
    turbine = _layout_holder(layout_file).get("turbine")
    raw = turbine.get("hub_height_m") if isinstance(turbine, Mapping) else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
        raise ValueError(
            f"{layout_file}: turbine.hub_height_m must be a positive number beside the "
            f"layout (got {raw!r}); no hub height is assumed"
        )
    return float(raw)


def load_turbine_layout(
    layout_file: str,
) -> Tuple[Dict[str, Tuple[float, float]], List[str]]:
    """Read the counted turbine positions from a layout YAML.

    Args:
        layout_file: A YAML file with a ``layout.turbines`` list at its top level or under
            exactly one top-level block.

    Returns:
        ``{id: (lat_deg, lon_deg)}`` for the counted turbines in file order, and the ids of
        the turbines skipped as another project's ``external_waker``.

    Raises:
        ValueError: The file holds no single ``layout.turbines`` list, an entry is malformed,
            an id repeats, a role is unknown, or no turbine is counted.
    """
    turbines = _layout_holder(layout_file)["layout"].get("turbines")
    if not isinstance(turbines, list) or not turbines:
        raise ValueError(f"{layout_file}: layout.turbines must be a non-empty list")
    counted: Dict[str, Tuple[float, float]] = {}
    skipped: List[str] = []
    for i, t in enumerate(turbines):
        if not isinstance(t, Mapping) or not {"id", "lat_deg", "lon_deg"} <= set(t):
            raise ValueError(
                f"{layout_file}: layout.turbines[{i}] needs id, lat_deg and lon_deg"
            )
        tid = str(t["id"])
        if tid in counted or tid in skipped:
            raise ValueError(f"{layout_file}: turbine id {tid!r} repeats")
        role = str(t.get("role", COUNTED_ROLE))
        if role == COUNTED_ROLE:
            counted[tid] = (float(t["lat_deg"]), float(t["lon_deg"]))
        elif role == "external_waker":
            skipped.append(tid)
        else:
            raise ValueError(f"{layout_file}: turbine {tid}: unknown role {role!r}")
    if not counted:
        raise ValueError(f"{layout_file}: no counted turbine")
    return counted, skipped


def main(
    netcdf_file: str, layout_file: str, output_dir_name: str = "wind_data_output"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Main processing pipeline."""
    print("=" * 70)
    print("ERA5 wind data processing at the counted turbine positions")
    print("=" * 70)

    turbine_locations, skipped = load_turbine_layout(layout_file)
    hub_height_m = load_hub_height(layout_file)
    output_dir = Path(output_dir_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir.absolute()}")

    # Load ERA5 data
    ds, time_dim = load_era5_netcdf(netcdf_file)

    # Process all turbines (ERA5 timeseries is single location - use center point)
    # We'll use the same wind data for all turbines as ERA5 is ~31km resolution
    print("\nNote: ERA5 timeseries data is for a single location (~31km grid).")
    print(
        f"Using this data for all {len(turbine_locations)} counted turbine locations "
        "(acceptable for site assessment)."
    )
    if skipped:
        print(f"Skipped as another project's turbines: {', '.join(skipped)}")

    all_data = []
    all_stats = []

    for turbine_id, (lat, lon) in turbine_locations.items():
        df, stats = process_turbine_location(
            ds, time_dim, turbine_id, lat, lon, hub_height_m
        )
        all_data.append(df)
        all_stats.append(stats)

    # Combine all turbine data
    df_combined = pd.concat(all_data, ignore_index=True)

    # Add temporal features
    df_combined["year"] = pd.to_datetime(df_combined["timestamp"]).dt.year
    df_combined["month"] = pd.to_datetime(df_combined["timestamp"]).dt.month
    df_combined["hour"] = pd.to_datetime(df_combined["timestamp"]).dt.hour

    # Save hourly data
    hourly_file = output_dir / "wind_hub_hourly.csv"
    df_combined.to_csv(hourly_file, index=False)
    print(f"\n✓ Saved hourly data: {hourly_file}")
    print(f"  Records: {len(df_combined):,}")

    # Save summary statistics
    stats_df = pd.DataFrame([vars(s) for s in all_stats])
    stats_file = output_dir / "wind_hub_summary.csv"
    stats_df.to_csv(stats_file, index=False)
    print(f"\n✓ Saved summary statistics: {stats_file}")

    # Calculate monthly averages per turbine
    monthly = (
        df_combined.groupby(["turbine_id", "month"])["ws_hub"].mean().reset_index()
    )
    monthly_file = output_dir / "wind_hub_monthly.csv"
    monthly.to_csv(monthly_file, index=False)
    print(f"✓ Saved monthly averages: {monthly_file}")

    # Calculate site-wide average
    site_avg = df_combined.groupby("timestamp")["ws_hub"].mean()
    site_stats = {
        "layout_file": layout_file,
        "turbines_counted": len(turbine_locations),
        "turbines_skipped": skipped,
        "hub_height_m": hub_height_m,
        "mean_ws_hub": float(site_avg.mean()),
        "std_ws_hub": float(site_avg.std()),
        "p50_ws_hub": float(site_avg.quantile(0.50)),
        "p75_ws_hub": float(site_avg.quantile(0.75)),
        "p90_ws_hub": float(site_avg.quantile(0.90)),
        "hours_of_data": len(site_avg),
        "years_of_data": len(site_avg) / 8760,
    }

    site_file = output_dir / "site_average.json"
    with open(site_file, "w") as f:
        json.dump(site_stats, f, indent=2)
    print(f"✓ Saved site average: {site_file}")

    # Print summary
    print("\n" + "=" * 70)
    print(f"SUMMARY - Wind Speed at {hub_height_m:g} m Hub Height")
    print("=" * 70)
    print(
        f"Data period: {site_stats['years_of_data']:.1f} years ({site_stats['hours_of_data']:,} hours)"
    )
    print(
        f"Site Average: {site_stats['mean_ws_hub']:.2f} ± {site_stats['std_ws_hub']:.2f} m/s"
    )
    print(f"P50 (Median): {site_stats['p50_ws_hub']:.2f} m/s")
    print(f"P75: {site_stats['p75_ws_hub']:.2f} m/s")
    print(f"P90: {site_stats['p90_ws_hub']:.2f} m/s")
    print("=" * 70)
    print(f"\nAll output files saved to: {output_dir.absolute()}")

    ds.close()

    return df_combined, stats_df


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:])
