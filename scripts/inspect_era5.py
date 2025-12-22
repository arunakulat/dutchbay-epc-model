"""
ERA5 NetCDF Structure Inspector - Fixed
"""

import numpy as np
import xarray as xr

# Load the NetCDF file
ds = xr.open_dataset("reanalysis-era5-single-levels-timeseries-sfcaey35zsb.nc")

print("=" * 70)
print("ERA5 DATASET STRUCTURE")
print("=" * 70)

print("\nDimensions:")
for dim, size in ds.sizes.items():
    print(f"  {dim}: {size}")

print("\nCoordinates:")
for coord in ds.coords:
    coord_data = ds.coords[coord]
    if coord_data.size > 0:
        if coord_data.ndim == 0:
            print(f"  {coord}: {coord_data.values} (scalar)")
        else:
            print(
                f"  {coord}: shape={coord_data.shape}, first={coord_data.values[0]}, last={coord_data.values[-1]}"
            )

print("\nData Variables:")
for var in ds.data_vars:
    print(f"  {var}: dims={ds[var].dims}, shape={ds[var].shape}")

print("\n" + "=" * 70)
print("FULL DATASET INFO:")
print("=" * 70)
print(ds)

ds.close()
