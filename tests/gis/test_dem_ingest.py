"""DEM ingest + terrain-derivative tests (issue #829).

Fully synthetic: a known linear ramp lets us assert the derived slope against its
analytic value, and an east-rising ramp pins the aspect convention. No network, no real
tiles. Rasterio round-trips are CASPER-skipped when the ``[gis]`` extra is absent.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")  # CASPER: skip when [gis] is absent

from analytics.gis.dem_ingest import (  # noqa: E402
    DEFAULT_DEM_SOURCE,
    DEM_SOURCES,
    METRES_PER_DEG_LAT,
    METRES_PER_DEG_LON_EQUATOR,
    TERRAIN_VARIABLES,
    derive_terrain_layers,
    load_dem,
    run_dem_ingest,
    slope_aspect_hillshade,
)
from analytics.gis.geotiff_export import (  # noqa: E402
    DEFAULT_CRS,
    write_geotiff,
)

# A ~0.03 deg box; ncols/nrows chosen so pixel size is a clean number.
BBOX = (79.400, 7.900, 79.460, 7.960)  # (west, south, east, north), 0.06 deg span
NROWS, NCOLS = 6, 6  # -> dx = dy = 0.01 deg


def _analytic_slope_deg(rise_per_pixel: float, pixel_size: float) -> float:
    """Slope (deg) of a planar ramp rising ``rise_per_pixel`` per pixel of width ``pixel_size``."""
    return math.degrees(math.atan(rise_per_pixel / pixel_size))


def test_slope_matches_analytic_ramp():
    """Slope of a perfect east-rising planar ramp equals atan(rise/run) on interior cells."""
    dx = dy = 0.01
    rise_per_pixel = 5.0  # elevation units per column step
    # z increases with column index (eastward). Row-invariant plane.
    cols = np.arange(NCOLS, dtype="float64")
    elevation = np.tile(cols * rise_per_pixel, (NROWS, 1))

    out = slope_aspect_hillshade(elevation, dx, dy)
    slope = out["slope"]
    expected = _analytic_slope_deg(rise_per_pixel, dx)

    # Interior cells (Horn's kernel is exact on a plane away from replicated edges).
    interior = slope[1:-1, 1:-1]
    assert np.allclose(interior, expected, atol=1e-4)


def test_slope_geographic_crs_auto_converts_to_metres():
    """A GEOGRAPHIC (deg-spaced) DEM ramp: slope matches the METRE-space analytic value.

    This pins the auto-conversion: without it, a 0.01-deg pixel treated as 0.01 metres
    would report a near-vertical (~89.9 deg) slope for a 5 m/pixel rise. With the
    latitude-aware degree->metre conversion the slope is the physically correct
    atan(rise / dx_metres).
    """
    rise_per_pixel = 5.0  # metres per column step
    cols = np.arange(NCOLS, dtype="float64")
    elevation = np.tile(cols * rise_per_pixel, (NROWS, 1)).astype("float32")

    grids = derive_terrain_layers(elevation, BBOX, is_geographic=True)
    slope = grids["slope"]

    # Reconstruct the expected metre pixel size the module should have used.
    west, south, east, north = BBOX
    dx_deg = (east - west) / NCOLS
    mean_lat = 0.5 * (south + north)
    dx_m = dx_deg * METRES_PER_DEG_LON_EQUATOR * math.cos(math.radians(mean_lat))
    expected = math.degrees(math.atan(rise_per_pixel / dx_m))

    interior = slope[1:-1, 1:-1]
    assert np.allclose(interior, expected, atol=1e-3)
    # And it is NOT the (wrong) consistent-units answer.
    wrong = _analytic_slope_deg(rise_per_pixel, dx_deg)
    assert not np.isclose(interior.mean(), wrong, atol=1.0)
    # The lat-aware dy factor is the fixed WGS84 value.
    assert METRES_PER_DEG_LAT == 110540.0


def test_explicit_z_factor_overrides_geographic_auto_conversion():
    """An explicit z_factor skips the auto-conversion (raw spacing, GDAL -z semantics)."""
    rise_per_pixel = 5.0
    cols = np.arange(NCOLS, dtype="float64")
    elevation = np.tile(cols * rise_per_pixel, (NROWS, 1)).astype("float32")

    # z_factor=1.0 explicit -> raw degree spacing, so we get the consistent-units answer.
    grids = derive_terrain_layers(elevation, BBOX, is_geographic=True, z_factor=1.0)
    dx_deg = (BBOX[2] - BBOX[0]) / NCOLS
    expected_raw = _analytic_slope_deg(rise_per_pixel, dx_deg)
    interior = grids["slope"][1:-1, 1:-1]
    assert np.allclose(interior, expected_raw, atol=1e-3)


def test_aspect_east_rising_faces_west():
    """An east-rising ramp faces downhill to the WEST -> aspect ~270 deg on interior cells."""
    dx = dy = 0.01
    cols = np.arange(NCOLS, dtype="float64")
    elevation = np.tile(cols * 3.0, (NROWS, 1))
    out = slope_aspect_hillshade(elevation, dx, dy)
    interior = out["aspect"][1:-1, 1:-1]
    assert np.allclose(interior, 270.0, atol=1e-3)


def test_flat_grid_zero_slope_and_flat_aspect():
    """A flat DEM -> zero slope everywhere and the GDAL flat-aspect sentinel (-1)."""
    elevation = np.full((NROWS, NCOLS), 42.0, dtype="float64")
    out = slope_aspect_hillshade(elevation, 0.01, 0.01)
    assert np.allclose(out["slope"], 0.0, atol=1e-9)
    assert np.all(out["aspect"] == -1.0)


def test_hillshade_in_byte_range():
    """Hillshade stays within the 0-255 shaded-relief range for a non-trivial ramp."""
    cols = np.arange(NCOLS, dtype="float64")
    elevation = np.tile(cols * 10.0, (NROWS, 1))
    out = slope_aspect_hillshade(elevation, 0.01, 0.01)
    assert out["hillshade"].min() >= 0.0
    assert out["hillshade"].max() <= 255.0


def test_slope_rejects_non_2d():
    with pytest.raises(ValueError):
        slope_aspect_hillshade(np.zeros((2, 2, 2)), 0.01, 0.01)


def test_derive_terrain_layers_shapes_and_keys():
    """derive_terrain_layers returns all four layers on the input grid shape."""
    cols = np.arange(NCOLS, dtype="float64")
    elevation = np.tile(cols * 2.0, (NROWS, 1)).astype("float32")
    grids = derive_terrain_layers(elevation, BBOX)
    assert set(grids) == set(TERRAIN_VARIABLES)
    for var in TERRAIN_VARIABLES:
        assert grids[var].shape == (NROWS, NCOLS)
    # elevation is passed through unchanged.
    assert np.array_equal(grids["elevation"], elevation)


def test_load_dem_full_and_clip(tmp_path):
    """A local DEM round-trips; a clip window returns the requested sub-extent."""
    elevation = np.arange(NROWS * NCOLS, dtype="float32").reshape(NROWS, NCOLS)
    dem = tmp_path / "dem.tif"
    write_geotiff(elevation, BBOX, dem, provenance={"source": "synthetic"})

    full, full_bbox, is_geographic = load_dem(dem)
    assert full.shape == (NROWS, NCOLS)
    assert [round(b, 4) for b in full_bbox] == [round(b, 4) for b in BBOX]
    # write_geotiff stamps EPSG:4326 -> a geographic CRS.
    assert is_geographic is True

    # Clip to the western half.
    west, south, east, north = BBOX
    clip = (west, south, (west + east) / 2.0, north)
    sub, sub_bbox, _ = load_dem(dem, clip)
    assert sub.shape[0] == NROWS
    assert sub.shape[1] == NCOLS // 2
    assert round(sub_bbox[2], 4) == round((west + east) / 2.0, 4)


def _write_ramp_dem(path: Path, rise_per_pixel: float = 5.0) -> None:
    cols = np.arange(NCOLS, dtype="float32")
    elevation = np.tile(cols * rise_per_pixel, (NROWS, 1)).astype("float32")
    write_geotiff(elevation, BBOX, path, provenance={"source": "synthetic-ramp"})


def test_run_dem_ingest_writes_layers_manifest_and_prov(tmp_path):
    """End-to-end: four GeoTIFFs + prov sidecars + a manifest entry, KPI-neutral."""
    dem = tmp_path / "dem.tif"
    _write_ramp_dem(dem)
    out_dir = tmp_path / "terrain"
    manifest = tmp_path / "DataLake_Manifest_All.json"

    summary = run_dem_ingest(
        {
            "dem_path": str(dem),
            "out_dir": str(out_dir),
            "manifest_path": str(manifest),
            "bbox": list(BBOX),
            "source": "glo30",
            "sun_azimuth_deg": 315.0,
            "sun_altitude_deg": 45.0,
        }
    )

    assert set(summary["variables"]) == set(TERRAIN_VARIABLES)
    for var in TERRAIN_VARIABLES:
        tif = out_dir / f"dutchbay_dem_{var}.tif"
        assert tif.exists()
        prov = json.loads(Path(f"{tif}.prov.json").read_text())
        assert prov["source"] == DEM_SOURCES["glo30"]
        assert prov["variable"] == var
        assert prov["method"] == "horn_1981_3x3_slope_aspect_hillshade"
        with rasterio.open(tif) as src:
            assert src.crs.to_string() == DEFAULT_CRS
            assert src.shape == (NROWS, NCOLS)

    # The DEM is EPSG:4326 (geographic), so slope uses the auto-converted METRE spacing —
    # the physically correct value for the RIX/siting input, not the raw-degree answer.
    with rasterio.open(out_dir / "dutchbay_dem_slope.tif") as src:
        slope = src.read(1)
    west, south, east, north = BBOX
    dx_deg = (east - west) / NCOLS
    mean_lat = 0.5 * (south + north)
    dx_m = dx_deg * METRES_PER_DEG_LON_EQUATOR * math.cos(math.radians(mean_lat))
    expected = math.degrees(math.atan(5.0 / dx_m))
    assert np.allclose(slope[1:-1, 1:-1], expected, atol=1e-3)

    # Provenance records that the auto-conversion fired (default, no explicit z_factor).
    slope_prov = json.loads(
        Path(f"{out_dir / 'dutchbay_dem_slope.tif'}.prov.json").read_text()
    )
    assert slope_prov["pixel_spacing_auto_converted_to_metres"] is True

    doc = json.loads(manifest.read_text())
    entry = [d for d in doc["datasets"] if d["name"] == "DutchBay/GIS/terrain"]
    assert len(entry) == 1
    assert set(entry[0]["variables"]) == set(TERRAIN_VARIABLES)
    assert entry[0]["provenance"]["source"] == DEM_SOURCES["glo30"]


def test_run_dem_ingest_default_source_label(tmp_path):
    """The default source resolves to the GLO-30 provenance label."""
    dem = tmp_path / "dem.tif"
    _write_ramp_dem(dem)
    summary = run_dem_ingest(
        {
            "dem_path": str(dem),
            "out_dir": str(tmp_path / "t"),
            "manifest_path": str(tmp_path / "m.json"),
        }
    )
    assert summary["source"] == DEM_SOURCES[DEFAULT_DEM_SOURCE]


def test_srtm_fallback_source_label(tmp_path):
    """The SRTM fallback records the SRTM 1-arcsec provenance label."""
    dem = tmp_path / "dem.tif"
    _write_ramp_dem(dem)
    summary = run_dem_ingest(
        {
            "dem_path": str(dem),
            "out_dir": str(tmp_path / "t"),
            "manifest_path": str(tmp_path / "m.json"),
            "source": "srtm",
        }
    )
    assert summary["source"] == DEM_SOURCES["srtm"]
