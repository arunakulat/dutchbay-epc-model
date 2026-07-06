"""Project-boundary polygon clip tests (issue #825, revives #21).

Builds a SYNTHETIC full-grid GeoTIFF in-test and a small polygon covering only part of
it, then asserts: cells outside the polygon are masked to nodata, inside cells are
preserved, the clipped-domain stats block (area-weighted mean / min / max / count) is
correct, CRS handling, and the ``DataLake_Manifest_All.json`` entry. No network, no large
files. CASPER-skips when the ``[gis]`` extra (rasterio) is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip(
    "rasterio"
)  # CASPER: skip when the [gis] extra is absent

from analytics.gis.boundary_clip import (  # noqa: E402
    clip_to_polygon,
    clipped_domain_stats,
    load_polygon,
)
from analytics.gis.geotiff_export import DEFAULT_CRS  # noqa: E402

# A 4x4 raster over a 4-degree box; each cell spans exactly 1 degree so the polygon can be
# aligned to cell centres for an unambiguous in/out count.
BBOX = (79.0, 8.0, 83.0, 12.0)  # (west, south, east, north)
NODATA = float("nan")


def _write_synthetic_raster(path: Path, values: np.ndarray) -> Path:
    """Write a single-band float32 GeoTIFF (north-up) over :data:`BBOX`."""
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    nrows, ncols = values.shape
    west, south, east, north = BBOX
    transform = from_bounds(west, south, east, north, ncols, nrows)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=nrows,
        width=ncols,
        count=1,
        dtype="float32",
        crs=CRS.from_string(DEFAULT_CRS),
        transform=transform,
        nodata=NODATA,
    ) as dst:
        dst.write(values.astype("float32"), 1)
    return path


# A polygon covering the SOUTH-WEST 2x2 quadrant of the 4x4 grid. Cell centres are at
# lon 79.5/80.5/81.5/82.5 and lat 11.5/10.5/9.5/8.5 (row 0 == north). This box
# (lon 79..81, lat 8..10) contains exactly the 4 cells with centres at lon 79.5/80.5 and
# lat 8.5/9.5 -> the bottom-left 2x2 block.
SW_QUADRANT = {
    "type": "Polygon",
    "coordinates": [
        [
            [79.0, 8.0],
            [81.0, 8.0],
            [81.0, 10.0],
            [79.0, 10.0],
            [79.0, 8.0],
        ]
    ],
}


def _grid_1to16() -> np.ndarray:
    """Row-major 1..16 field so masked/kept cells are individually identifiable."""
    return np.arange(1, 17, dtype="float32").reshape(4, 4)


def test_outside_polygon_masked_inside_preserved(tmp_path):
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped.tif"

    summary = clip_to_polygon(src, SW_QUADRANT, out, variable="ws150")
    assert summary["stats"]["count"] == 4

    with rasterio.open(out) as ds:
        clipped = ds.read(1)
        assert ds.count == 1
        assert ds.dtypes[0] == "float32"
        # crop=True trims to the polygon window -> a 2x2 clipped raster.
        assert clipped.shape == (2, 2)
        # The SW quadrant of the 4x4 grid is rows 2..3, cols 0..1 -> values 9,10,13,14.
        kept = np.array([[9.0, 10.0], [13.0, 14.0]], dtype="float32")
        assert np.array_equal(clipped, kept)
        # No nodata inside a fully-covered window.
        assert not np.isnan(clipped).any()


def test_partial_cover_masks_out_of_polygon_cells(tmp_path):
    # A polygon covering only the single bottom-LEFT cell (centre lon 79.5, lat 8.5).
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped_one.tif"
    one_cell = {
        "type": "Polygon",
        "coordinates": [
            [[79.0, 8.0], [80.0, 8.0], [80.0, 9.0], [79.0, 9.0], [79.0, 8.0]]
        ],
    }
    summary = clip_to_polygon(src, one_cell, out, variable="aep")

    with rasterio.open(out) as ds:
        clipped = ds.read(1)
    # Only the bottom-left cell (value 13) survives; the rest of its 1x1 window is it alone.
    assert clipped.shape == (1, 1)
    assert clipped[0, 0] == pytest.approx(13.0)
    assert summary["stats"]["count"] == 1
    assert summary["stats"]["min"] == pytest.approx(13.0)
    assert summary["stats"]["max"] == pytest.approx(13.0)


def test_clipped_stats_area_weighted_mean(tmp_path):
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped.tif"
    summary = clip_to_polygon(src, SW_QUADRANT, out, variable="cf")

    stats = summary["stats"]
    kept = np.array([9.0, 10.0, 13.0, 14.0])
    assert stats["count"] == 4
    assert stats["min"] == pytest.approx(9.0)
    assert stats["max"] == pytest.approx(14.0)
    # Area-weighted mean weights the two rows by cos(lat); it must sit between the plain
    # mean and be pulled toward the (larger-weight) lower-latitude row's values.
    plain_mean = float(kept.mean())  # 11.5
    # cos-weight row centres 9.5 (south, values 13,14) heavier than 10.5? No: cos DEcreases
    # with |lat|, so the SOUTHERN row (lat 9.5) has the LARGER weight -> mean > plain mean.
    assert stats["mean"] > plain_mean
    assert stats["mean"] == pytest.approx(11.5, abs=0.05)  # tiny correction at this lat


def test_empty_intersection_reports_none(tmp_path):
    # A polygon entirely outside the raster -> rasterio raises; assert we surface it, not a
    # silent all-nodata raster. rasterio.mask raises ValueError on a disjoint geometry.
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped.tif"
    far = {
        "type": "Polygon",
        "coordinates": [
            [[10.0, 1.0], [11.0, 1.0], [11.0, 2.0], [10.0, 2.0], [10.0, 1.0]]
        ],
    }
    with pytest.raises(ValueError, match="do not overlap"):
        clip_to_polygon(src, far, out, variable="ws150")


def test_clipped_domain_stats_helper_empty_returns_none():
    # Pure helper: an all-nodata array reports None stats + count 0 (not a fake 0.0 mean).
    arr = np.full((2, 2), np.nan, dtype="float32")
    stats = clipped_domain_stats(arr, float("nan"))
    assert stats == {"mean": None, "min": None, "max": None, "count": 0}


def test_clipped_domain_stats_helper_finite_nodata():
    arr = np.array([[1.0, -9999.0], [3.0, 5.0]], dtype="float32")
    stats = clipped_domain_stats(arr, -9999.0)
    assert stats["count"] == 3
    assert stats["min"] == pytest.approx(1.0)
    assert stats["max"] == pytest.approx(5.0)
    assert stats["mean"] == pytest.approx((1.0 + 3.0 + 5.0) / 3.0)


def test_prov_sidecar_and_crs(tmp_path):
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped.tif"
    summary = clip_to_polygon(src, SW_QUADRANT, out, variable="ws150")

    assert summary["crs"] == DEFAULT_CRS
    with rasterio.open(out) as ds:
        assert ds.crs.to_string() == DEFAULT_CRS

    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["method"] == "rasterio_mask_clip_to_polygon"
    assert prov["variable"] == "ws150"
    assert prov["in_polygon_cell_count"] == 4
    assert prov["all_touched"] is False


def test_crs_override_agreeing_is_accepted(tmp_path):
    # An override that AGREES with the raster CRS is fine (it is just a label).
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped.tif"
    summary = clip_to_polygon(src, SW_QUADRANT, out, crs="EPSG:4326", variable="ws150")
    assert summary["crs"] == "EPSG:4326"


def test_crs_override_mismatch_fails_loud(tmp_path):
    # A DISAGREEING crs override must raise, not write a mislabeled GeoTIFF: clip_to_polygon
    # labels but never reprojects (CESSPIT fail-loud). The raster is EPSG:4326.
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped.tif"
    with pytest.raises(ValueError, match="disagrees with the source raster CRS"):
        clip_to_polygon(src, SW_QUADRANT, out, crs="EPSG:3857", variable="ws150")
    # And nothing was written.
    assert not out.exists()


def test_manifest_entry_written(tmp_path):
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    out = tmp_path / "clipped.tif"
    manifest = tmp_path / "DataLake_Manifest_All.json"
    summary = clip_to_polygon(
        src,
        SW_QUADRANT,
        out,
        variable="ws150",
        manifest_path=manifest,
        manifest_name="DutchBay/GIS/clipped_ws150",
    )
    assert summary["manifest_path"] == str(manifest)

    doc = json.loads(manifest.read_text())
    matching = [d for d in doc["datasets"] if d["name"] == "DutchBay/GIS/clipped_ws150"]
    assert len(matching) == 1
    entry = matching[0]
    assert entry["variables"] == ["ws150"]
    assert entry["gis"]["crs"] == DEFAULT_CRS
    assert entry["provenance"]["method"] == "rasterio_mask_clip_to_polygon"
    # The clipped-domain stats travel with the manifest entry.
    assert entry["provenance"]["clipped_domain_stats"]["count"] == 4


def test_all_touched_keeps_touched_cells(tmp_path):
    # all_touched=True keeps every cell the polygon touches. A polygon nicked into the
    # top-right cell's footprint keeps more cells than centre-in (all_touched=False).
    values = _grid_1to16()
    src = _write_synthetic_raster(tmp_path / "field.tif", values)
    # Polygon straddling the boundary between the 4 SW cells and reaching into neighbours.
    straddle = {
        "type": "Polygon",
        "coordinates": [
            [[79.0, 8.0], [81.5, 8.0], [81.5, 10.5], [79.0, 10.5], [79.0, 8.0]]
        ],
    }
    out_ct = tmp_path / "centre.tif"
    out_at = tmp_path / "touched.tif"
    s_centre = clip_to_polygon(src, straddle, out_ct, all_touched=False)
    s_touched = clip_to_polygon(src, straddle, out_at, all_touched=True)
    assert s_touched["stats"]["count"] >= s_centre["stats"]["count"]


def test_load_polygon_from_geojson_file(tmp_path):
    # The committed project-area geojson (FeatureCollection) loads to one clip geometry.
    repo_geojson = (
        Path(__file__).resolve().parents[2]
        / "wind_resource"
        / "config"
        / "DutchBay_ProjectArea.geojson"
    )
    geoms = load_polygon(repo_geojson)
    assert len(geoms) == 1
    assert geoms[0]["type"] == "Polygon"

    # And it is usable as a clip polygon over a raster spanning the DutchBay centroid.
    doc = json.loads(repo_geojson.read_text())
    props = doc["features"][0]["properties"]
    assert "illustrative placeholder boundary" in props["note"].lower()
    assert props["surveyed"] is False
