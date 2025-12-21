"""ERA5 Wind Data Fetcher with Copernicus CDS API Integration.

This module provides automated download and processing of ERA5 reanalysis
wind data from the Copernicus Climate Data Store (CDS). It handles:
- Wind speed/direction at 10m and 100m heights
- Hub height extrapolation using power law
- Local caching to avoid redundant downloads
- Metadata tracking for reproducibility

Typical usage:
    >>> from wind_resource import ERA5Fetcher
    >>> fetcher = ERA5Fetcher(cache_dir='inputs/wind_data')
    >>> location = {'name': 'DutchBay', 'lat': 8.33, 'lon': 79.76}
    >>> data_file = fetcher.download_wind_data(
    ...     location=location,
    ...     start_date='2014-12-01',
    ...     end_date='2025-12-31'
    ... )

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    import cdsapi
    import xarray as xr
    CDS_AVAILABLE = True
except ImportError:
    CDS_AVAILABLE = False
    logging.warning("cdsapi or xarray not available. ERA5 download will fail.")

logger = logging.getLogger(__name__)


class ERA5Fetcher:
    """Fetch and process ERA5 wind data from Copernicus CDS.
    
    This class manages the complete workflow of downloading ERA5 reanalysis
    wind data, converting it to useful formats, and caching results for
    efficient reuse.
    
    Attributes:
        cache_dir: Directory for storing downloaded and processed data.
        metadata_dir: Directory for download metadata and logs.
        
    Example:
        >>> fetcher = ERA5Fetcher()
        >>> location = {'name': 'Site1', 'lat': 8.33, 'lon': 79.76}
        >>> csv_file = fetcher.download_wind_data(
        ...     location=location,
        ...     start_date='2020-01-01',
        ...     end_date='2020-12-31'
        ... )
    """
    
    def __init__(self, cache_dir: str = "inputs/wind_data") -> None:
        """Initialize ERA5 fetcher.
        
        Args:
            cache_dir: Directory path for caching downloaded data.
                Will be created if it doesn't exist.
                
        Raises:
            ImportError: If cdsapi or xarray packages are not installed.
        """
        if not CDS_AVAILABLE:
            raise ImportError(
                "ERA5Fetcher requires 'cdsapi' and 'xarray' packages. "
                "Install with: pip install cdsapi xarray netcdf4"
            )
        
        self.cache_dir = Path(cache_dir)
        self.metadata_dir = self.cache_dir / "metadata"
        
        # Create directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ERA5Fetcher initialized with cache: {self.cache_dir}")
    
    def download_wind_data(
        self,
        location: Dict[str, Any],
        start_date: str,
        end_date: str,
        force_download: bool = False
    ) -> Path:
        """Download ERA5 wind data for a specific location and time period.
        
        Downloads u/v wind components at 10m and 100m heights, converts to
        wind speed and direction, and saves as CSV. Uses local cache to avoid
        redundant downloads.
        
        Args:
            location: Dictionary with keys 'name', 'lat', 'lon'.
                Example: {'name': 'DutchBay', 'lat': 8.33, 'lon': 79.76}
            start_date: Start date in 'YYYY-MM-DD' format.
            end_date: End date in 'YYYY-MM-DD' format (inclusive).
            force_download: If True, re-download even if cached file exists.
                Default is False.
                
        Returns:
            Path to the cached CSV file containing processed wind data.
            Columns include: timestamp, u10, v10, u100, v100, ws_10m, 
            ws_100m, wd_10m, wd_100m, alpha (wind shear).
            
        Raises:
            ValueError: If location dict is missing required keys.
            RuntimeError: If CDS API request fails.
            
        Example:
            >>> location = {'name': 'MySite', 'lat': 8.5, 'lon': 80.0}
            >>> csv_file = fetcher.download_wind_data(
            ...     location=location,
            ...     start_date='2020-01-01',
            ...     end_date='2020-12-31'
            ... )
            >>> print(f"Data saved to: {csv_file}")
        """
        # Validate location
        required_keys = ['name', 'lat', 'lon']
        if not all(k in location for k in required_keys):
            raise ValueError(
                f"location must contain keys: {required_keys}. "
                f"Got: {list(location.keys())}"
            )
        
        # Generate cache filename
        cache_file = self.cache_dir / (
            f"era5_{location['name'].lower()}_"
            f"{start_date}_to_{end_date}.csv"
        )
        
        # Check cache
        if cache_file.exists() and not force_download:
            logger.info(f"Using cached data: {cache_file}")
            return cache_file
        
        logger.info(f"Downloading ERA5 data for {location['name']}...")
        logger.info(f"  Period: {start_date} to {end_date}")
        logger.info(f"  Location: {location['lat']:.2f}°N, {location['lon']:.2f}°E")
        
        # Download from CDS API
        nc_file = self._download_from_cds(
            location=location,
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert to CSV
        df = self._convert_netcdf_to_dataframe(nc_file)
        
        # Calculate wind speed and direction
        df = self._calculate_wind_metrics(df)
        
        # Save to CSV
        df.to_csv(cache_file, index=False)
        logger.info(f"Saved processed data: {cache_file}")
        
        # Save metadata
        self._save_metadata(location, start_date, end_date, cache_file)
        
        return cache_file
    
    def _download_from_cds(
        self,
        location: Dict[str, Any],
        start_date: str,
        end_date: str
    ) -> Path:
        """Download raw NetCDF data from Copernicus CDS.
        
        Args:
            location: Location dictionary.
            start_date: Start date string.
            end_date: End date string.
            
        Returns:
            Path to downloaded NetCDF file.
            
        Raises:
            RuntimeError: If CDS API request fails.
        """
        nc_file = self.cache_dir / (
            f"era5_{location['name'].lower()}_raw.nc"
        )
        
        # Define area: [N, W, S, E] with 0.5° buffer
        area = [
            location['lat'] + 0.5,
            location['lon'] - 0.5,
            location['lat'] - 0.5,
            location['lon'] + 0.5
        ]
        
        # CDS API request
        client = cdsapi.Client()
        
        try:
            client.retrieve(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': [
                        '10m_u_component_of_wind',
                        '10m_v_component_of_wind',
                        '100m_u_component_of_wind',
                        '100m_v_component_of_wind',
                    ],
                    'year': self._get_years(start_date, end_date),
                    'month': [f'{m:02d}' for m in range(1, 13)],
                    'day': [f'{d:02d}' for d in range(1, 32)],
                    'time': [f'{h:02d}:00' for h in range(24)],
                    'area': area,
                    'format': 'netcdf',
                },
                str(nc_file)
            )
        except Exception as e:
            raise RuntimeError(
                f"CDS API download failed: {e}. "
                "Check ~/.cdsapirc credentials and CDS status."
            ) from e
        
        logger.info(f"Downloaded NetCDF: {nc_file}")
        return nc_file
    
    @staticmethod
    def _get_years(start_date: str, end_date: str) -> list[str]:
        """Extract list of years from date range.
        
        Args:
            start_date: Start date 'YYYY-MM-DD'.
            end_date: End date 'YYYY-MM-DD'.
            
        Returns:
            List of year strings, e.g. ['2020', '2021'].
        """
        start_year = int(start_date.split('-')[0])
        end_year = int(end_date.split('-')[0])
        return [str(y) for y in range(start_year, end_year + 1)]
    
    def _convert_netcdf_to_dataframe(self, nc_file: Path) -> pd.DataFrame:
        """Convert NetCDF to pandas DataFrame.
        
        Args:
            nc_file: Path to NetCDF file.
            
        Returns:
            DataFrame with columns: timestamp, u10, v10, u100, v100.
        """
        ds = xr.open_dataset(nc_file)
        
        # Extract nearest point (should be single point due to small area)
        df = ds.to_dataframe().reset_index()
        
        # Rename columns
        df = df.rename(columns={
            'time': 'timestamp',
            'u10': 'u10',
            'v10': 'v10',
            'u100': 'u100',
            'v100': 'v100'
        })
        
        # Keep only required columns
        df = df[['timestamp', 'u10', 'v10', 'u100', 'v100']].copy()
        
        return df
    
    @staticmethod
    def _calculate_wind_metrics(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate wind speed, direction, and shear from u/v components.
        
        Args:
            df: DataFrame with u10, v10, u100, v100 columns.
            
        Returns:
            DataFrame with added columns: ws_10m, ws_100m, wd_10m, 
            wd_100m, alpha.
        """
        # Wind speed (m/s)
        df['ws_10m'] = np.sqrt(df['u10']**2 + df['v10']**2)
        df['ws_100m'] = np.sqrt(df['u100']**2 + df['v100']**2)
        
        # Wind direction (degrees, meteorological convention)
        df['wd_10m'] = (180 + np.rad2deg(np.arctan2(df['u10'], df['v10']))) % 360
        df['wd_100m'] = (180 + np.rad2deg(np.arctan2(df['u100'], df['v100']))) % 360
        
        # Wind shear exponent (alpha)
        # ws(h) = ws_ref * (h / h_ref)^alpha
        # alpha = ln(ws_100 / ws_10) / ln(100 / 10)
        with np.errstate(divide='ignore', invalid='ignore'):
            df['alpha'] = np.log(df['ws_100m'] / df['ws_10m']) / np.log(10.0)
        
        # Clip alpha to reasonable range
        df['alpha'] = df['alpha'].clip(0.05, 0.40)
        df['alpha'] = df['alpha'].fillna(0.143)  # Default for missing
        
        return df
    
    def extrapolate_to_hub_height(
        self,
        df: pd.DataFrame,
        hub_height: float = 150.0
    ) -> pd.DataFrame:
        """Extrapolate wind speed to hub height using power law.
        
        Uses the power law: ws(h) = ws_ref * (h / h_ref)^alpha
        where alpha is the wind shear exponent calculated from 10m and 100m data.
        
        Args:
            df: DataFrame with ws_100m and alpha columns.
            hub_height: Target hub height in meters. Must be > 100m.
                Default is 150.0.
                
        Returns:
            DataFrame with added column 'ws_{hub_height}m' containing
            extrapolated wind speeds.
            
        Raises:
            ValueError: If hub_height <= 100m or required columns missing.
            
        Example:
            >>> df_extrapolated = fetcher.extrapolate_to_hub_height(
            ...     df,
            ...     hub_height=150.0
            ... )
            >>> print(df_extrapolated['ws_150m'].mean())
        """
        if hub_height <= 100:
            raise ValueError(
                f"hub_height must be > 100m. Got: {hub_height}m. "
                "Use ws_100m or ws_10m for lower heights."
            )
        
        required = ['ws_100m', 'alpha']
        if not all(col in df.columns for col in required):
            raise ValueError(
                f"DataFrame must contain columns: {required}. "
                f"Got: {list(df.columns)}"
            )
        
        col_name = f'ws_{int(hub_height)}m'
        
        # Power law extrapolation from 100m
        df[col_name] = df['ws_100m'] * (hub_height / 100.0) ** df['alpha']
        
        logger.info(
            f"Extrapolated to {hub_height}m: "
            f"mean = {df[col_name].mean():.2f} m/s"
        )
        
        return df
    
    def _save_metadata(
        self,
        location: Dict[str, Any],
        start_date: str,
        end_date: str,
        cache_file: Path
    ) -> None:
        """Save download metadata for reproducibility.
        
        Args:
            location: Location dictionary.
            start_date: Start date string.
            end_date: End date string.
            cache_file: Path to cached CSV file.
        """
        metadata = {
            'location': location,
            'start_date': start_date,
            'end_date': end_date,
            'download_timestamp': datetime.now().isoformat(),
            'cache_file': str(cache_file),
            'source': 'ERA5 Reanalysis via Copernicus CDS',
            'spatial_resolution': '~31km (0.25°)',
            'temporal_resolution': 'hourly'
        }
        
        metadata_file = self.metadata_dir / f"{cache_file.stem}_metadata.json"
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.debug(f"Saved metadata: {metadata_file}")
