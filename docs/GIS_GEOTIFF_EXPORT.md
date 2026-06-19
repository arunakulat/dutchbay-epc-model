# GIS GeoTIFF Export (issue #20)

Export the DutchBay wind/energy layers as **QGIS-ready GeoTIFFs**: `ws150_mean`,
`capacity_factor` and `aep_per_turbine`, on an `EPSG:4326` raster, at **two scales**:

| Grid | Resolution | Extent | Source |
|------|-----------|--------|--------|
| **coarse** | ≈0.25° (~28 km) native ERA5 | ≈0.75° / ~80 km box | one real ERA5 point sampled per cell |
| **fine** | ≈0.05° (~5 km), wind-farm scale | ≈0.15° box, centred on site | **bilinear downscale** of the coarse ERA5 field |

> **Honesty (provenance, #18):** the coarse grid is genuine reanalysis (one ERA5 point
> per cell). The fine grid is a *smooth interpolation* of the 0.25° field — **not** a
> measured ~5 km observation; each raster carries a `.prov.json` sidecar and a manifest
> `provenance` block saying so. ERA5 cannot resolve sub-0.25° detail.

## Dependency

`rasterio` is an opt-in **`[gis]` extra** (its wheels bundle GDAL — no system GDAL/apt):

```bash
pip install -e ".[gis]"        # or ".[wind,gis]" to also drive the live ERA5 fetch
```

The export code guards the import (`analytics.gis.geotiff_export._require_rasterio`,
CASPER), so the base finance install never needs the GIS toolchain.

## Run it

Config-first (`wind_resource/config/gis_export_dutchbay.yaml`; the same `gis:` shape may
live under a scenario):

```bash
# Live ERA5 (needs the [wind] extra + ~/.cdsapirc; one ERA5 fetch per coarse cell — slow)
GIS_EXPORT_CONFIG=wind_resource/config/gis_export_dutchbay.yaml \
  python -m analytics.gis.gis_export
```

Or programmatically, injecting your own per-cell source (e.g. for tests/offline):

```python
from analytics.gis.gis_export import run_gis_export
summary = run_gis_export(gis_cfg, source=my_cell_source)   # source: GridSpec -> [CellResult]
```

Outputs land under `outputs/gis/dutchbay/` (gitignored): 6 GeoTIFFs
(`dutchbay_{coarse,fine}_{ws150_mean,capacity_factor,aep_per_turbine}.tif`) plus
`outputs/gis/DataLake_Manifest_All.json` carrying `gis.extent` / `gis.resolution` /
`variables` per grid. Re-running is idempotent (entries replaced, not duplicated). Sync
`outputs/gis/` to the real `Curated/GIS/DutchBay/Rasters/` data lake when ready.

## How CF/AEP per cell are computed

The coarse source reuses the canonical point pipeline unchanged — ERA5 u/v →
power-law shear to 150 m (`wind_resource.era5_retrieval.build_hub_height_series`) →
net AEP/CF through the project power curve and loss stack
(`EnergyCalculator` via `compute_site_aep`). So a cell's energy uses the *same* physics
as the headline site AEP; only the location changes.

## QGIS smoke-test (manual)

Drag the six `.tif` files into QGIS (they self-locate via the embedded `EPSG:4326`
georeferencing) and confirm the layers render over Dutch Bay / Kalpitiya. This is the one
step that can't be automated.

## Tests

`tests/gis/` — rasterio round-trip (CRS/shape/values/north-up), grid assembly +
orientation, bilinear-downscale bounds, and an end-to-end `run_gis_export` with an
injected synthetic source (no network). All skip cleanly if `rasterio` is absent (CASPER).
