"""Hydra CLI for ERA5 Wind Data Download.

Downloads ERA5 reanalysis wind data from Copernicus CDS and extrapolates
to hub height. Follows GWTF R3 (Hydra-only) and CLI-03 (JSON-first) compliance.

Usage:
    Basic (uses DutchBay location from locations.yaml):
        python run_wind_download_v14.py location=dutchbay
    
    With custom parameters:
        python run_wind_download_v14.py \
            location=dutchbay \
            hub_height=120 \
            force_download=true
    
    Different date range:
        python run_wind_download_v14.py \
            location=dutchbay \
            start_date=2020-01-01 \
            end_date=2020-12-31

Output:
    JSON to stdout with:
    - status: 'success' or 'error'
    - location: Location name
    - data_file: Path to processed CSV file
    - mean_ws: Mean wind speed at hub height
    - summary_stats: Wind speed statistics

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0 (GWTF R3, CLI-03 Compliant)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import hydra
import pandas as pd
import yaml
from omegaconf import DictConfig

from wind_resource import ERA5Fetcher

logger = logging.getLogger(__name__)

# Remember original working directory (Hydra changes it)
_ORIG_CWD = Path.cwd()


@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="wind_download",
)
def cli(cfg: DictConfig) -> None:
    """Hydra CLI entry point for ERA5 wind data download.

    Args:
        cfg: Hydra configuration from conf/wind_download.yaml.

    Returns:
        None. Prints JSON result to stdout.

    Raises:
        SystemExit: If required parameters missing or errors occur.
    """
    # Undo Hydra's job-chdir to work from repo root
    os.chdir(_ORIG_CWD)

    # Validate required parameter
    location_name = cfg.get("location")
    if not location_name:
        error_result = {
            "status": "error",
            "error": "Missing required parameter 'location'",
            "usage": "python run_wind_download_v14.py location=dutchbay",
            "available_locations": _get_available_locations(),
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)

    try:
        # Load location from config
        locations_file = Path("wind_resource/config/locations.yaml")
        if not locations_file.exists():
            raise FileNotFoundError(f"Locations config not found: {locations_file}")

        with open(locations_file) as f:
            locations = yaml.safe_load(f)

        if location_name not in locations:
            error_result = {
                "status": "error",
                "error": f"Unknown location: {location_name}",
                "available_locations": list(locations.keys()),
            }
            print(json.dumps(error_result, indent=2))
            raise SystemExit(1)

        location = locations[location_name]

        # Extract parameters from config
        start_date = cfg.get("start_date")
        end_date = cfg.get("end_date")
        hub_height = float(cfg.get("hub_height"))
        force_download = bool(cfg.get("force_download", False))
        cache_dir = cfg.get("cache_dir")
        output_dir = Path(cfg.get("output_dir"))

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 70)
        logger.info("ERA5 WIND DATA DOWNLOAD")
        logger.info("=" * 70)
        logger.info(
            f"Location: {location_name} ({location['lat']:.2f}°N, {location['lon']:.2f}°E)"
        )
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Hub height: {hub_height}m")

        # Initialize fetcher
        fetcher = ERA5Fetcher(cache_dir=cache_dir)

        # Download ERA5 data
        logger.info("\n[Step 1/3] Downloading ERA5 data...")
        data_file = fetcher.download_wind_data(
            location=location,
            start_date=start_date,
            end_date=end_date,
            force_download=force_download,
        )

        # Load data
        logger.info("\n[Step 2/3] Loading and processing data...")
        df = pd.read_csv(data_file)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Extrapolate to hub height
        logger.info(f"\n[Step 3/3] Extrapolating to {hub_height}m hub height...")
        df = fetcher.extrapolate_to_hub_height(df, hub_height=hub_height)

        # Save processed data
        ws_column = f"ws_{int(hub_height)}m"
        output_file = (
            output_dir
            / f"{location_name}_wind_{int(hub_height)}m_{start_date}_to_{end_date}.csv"
        )
        df.to_csv(output_file, index=False)

        # Calculate summary statistics
        mean_ws = float(df[ws_column].mean())
        std_ws = float(df[ws_column].std())
        min_ws = float(df[ws_column].min())
        max_ws = float(df[ws_column].max())
        p50_ws = float(df[ws_column].quantile(0.50))
        p90_ws = float(df[ws_column].quantile(0.90))

        # Build success result (JSON-first, CLI-03 compliance)
        result = {
            "status": "success",
            "location": {
                "name": location_name,
                "lat": location["lat"],
                "lon": location["lon"],
            },
            "parameters": {
                "start_date": start_date,
                "end_date": end_date,
                "hub_height_m": hub_height,
                "force_download": force_download,
            },
            "output_files": {
                "raw_data": str(data_file),
                "processed_data": str(output_file),
            },
            "data_summary": {
                "total_hours": len(df),
                "mean_ws": round(mean_ws, 2),
                "std_ws": round(std_ws, 2),
                "min_ws": round(min_ws, 2),
                "max_ws": round(max_ws, 2),
                "p50_ws": round(p50_ws, 2),
                "p90_ws": round(p90_ws, 2),
            },
            "message": f"✓ Successfully downloaded and processed ERA5 data for {location_name}",
        }

        logger.info("\n" + "=" * 70)
        logger.info(f"✓ Download complete: {output_file}")
        logger.info(f"  Mean wind speed: {mean_ws:.2f} m/s at {hub_height}m")
        logger.info("=" * 70)

        # Output JSON (CLI-03 compliance)
        print(json.dumps(result, indent=2, sort_keys=True))

    except Exception as e:
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "location": location_name if "location_name" in locals() else None,
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Error during wind data download")
        raise SystemExit(1) from e


def _get_available_locations() -> list[str]:
    """Get list of available locations from config.

    Returns:
        List of location names, or empty list if config not found.
    """
    try:
        locations_file = Path("wind_resource/config/locations.yaml")
        if locations_file.exists():
            with open(locations_file) as f:
                locations = yaml.safe_load(f)
            return list(locations.keys())
        return []
    except Exception:
        return []


if __name__ == "__main__":
    cli()
