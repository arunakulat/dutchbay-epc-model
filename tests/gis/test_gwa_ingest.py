"""GWA 250 m reference-layer ingest tests (issue #828).

Builds a TINY synthetic GeoTIFF in-test (no network, no large files) that stands in for a
Global Wind Atlas download, then asserts the ingest clips to the site bbox, writes a
provenance-stamped reference layer + ``.prov.json`` sidecar, and emits a DataLake manifest
entry that is clearly labelled as an external reference (NOT the ERA5 fine grid).
CASPER-skip when the ``[gis]`` extra is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip(
    "rasterio"
)  # CASPER: skip when the [gis] extra is absent

from analytics.gis.geotiff_export import DEFAULT_CRS  # noqa: E402
from analytics.gis.gwa_ingest import (  # noqa: E402
    GWA_SOURCE,
    gwa_provenance,
    ingest_gwa_layer,
    run_gwa_ingest,
)

# A ~1.0 deg synthetic "GWA tile" covering the Kalpitiya box; the clip bbox is a strict
# sub-window of it, so we can verify the read window really trims the source.
TILE_BBOX = (79.0, 7.5, 80.0, 8.5)  # (west, south, east, north)
CLIP_BBOX = (79.375, 7.895, 79.875, 8.395)


def _write_synthetic_tile(path: Path, bbox=TILE_BBOX, n=20) -> Path:
    """Write an n×n single-band float32 GeoTIFF standing in for a GWA download."""
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    west, south, east, north = bbox
    # A recognisable gradient so a mis-clip would be detectable.
    arr = np.arange(n * n, dtype="float32").reshape(n, n)
    transform = from_bounds(west, south, east, north, n, n)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=n,
        width=n,
        count=1,
        dtype="float32",
        crs=CRS.from_string(DEFAULT_CRS),
        transform=transform,
    ) as dst:
        dst.write(arr, 1)
    return path


def test_gwa_provenance_labels_reference_not_era5():
    prov = gwa_provenance("wind_speed", "/data/gwa_ws.tif")
    assert prov["source"] == GWA_SOURCE
    assert prov["resolution_m"] == 250.0
    assert prov["reference_layer"] is True
    assert prov["wired_into_aep"] is False
    # The note must make the ERA5-fine distinction explicit and unmistakable.
    assert "ERA5" in prov["note"] and "reference" in prov["note"].lower()
    assert "AEP" in prov["note"]


def test_ingest_clips_and_writes_prov_sidecar(tmp_path):
    src = _write_synthetic_tile(tmp_path / "gwa_source.tif")
    out = tmp_path / "gwa_wind_speed.tif"
    result = ingest_gwa_layer(src, "wind_speed", CLIP_BBOX, out)

    assert Path(result["path"]) == out
    with rasterio.open(out) as ds:
        assert ds.crs.to_string() == DEFAULT_CRS
        assert ds.count == 1
        assert ds.dtypes[0] == "float32"
        # Clipped output is strictly smaller than the 20×20 source tile.
        assert ds.shape[0] < 20 and ds.shape[1] < 20
        assert ds.shape[0] > 0 and ds.shape[1] > 0
        # Achieved bounds sit within (or on) the source tile and near the request.
        w, s, e, n = ds.bounds
        assert TILE_BBOX[0] - 1e-6 <= w < e <= TILE_BBOX[2] + 1e-6
        assert TILE_BBOX[1] - 1e-6 <= s < n <= TILE_BBOX[3] + 1e-6

    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["source"] == GWA_SOURCE
    assert prov["variable"] == "wind_speed"
    assert prov["reference_layer"] is True
    assert prov["requested_bbox"] == list(CLIP_BBOX)


def test_run_gwa_ingest_writes_manifest_with_reference_label(tmp_path):
    src = _write_synthetic_tile(tmp_path / "gwa_source.tif")
    manifest_path = tmp_path / "DataLake_Manifest_All.json"
    cfg = {
        "bbox": list(CLIP_BBOX),
        "out_dir": str(tmp_path / "gwa_out"),
        "manifest_path": str(manifest_path),
        "layers": [
            {"name": "wind_speed", "source_path": str(src), "variable": "ws100_mean"},
        ],
    }
    summary = run_gwa_ingest(cfg)

    assert "wind_speed" in summary["layers"]
    layer_path = Path(summary["layers"]["wind_speed"]["path"])
    assert layer_path.exists() and layer_path.name == "gwa_wind_speed.tif"

    doc = json.loads(manifest_path.read_text())
    matching = [
        d for d in doc["datasets"] if d["name"] == "DutchBay/GIS/gwa_250m_reference"
    ]
    assert len(matching) == 1
    entry = matching[0]
    assert entry["gis"]["crs"] == DEFAULT_CRS
    assert "ws100_mean" in entry["variables"]
    assert entry["provenance"]["source"] == GWA_SOURCE
    assert entry["provenance"]["reference_layer"] is True
    assert entry["provenance"]["wired_into_aep"] is False
    assert "ERA5" in entry["provenance"]["note"]


def test_run_gwa_ingest_is_idempotent(tmp_path):
    src = _write_synthetic_tile(tmp_path / "gwa_source.tif")
    manifest_path = tmp_path / "DataLake_Manifest_All.json"
    cfg = {
        "bbox": list(CLIP_BBOX),
        "out_dir": str(tmp_path / "gwa_out"),
        "manifest_path": str(manifest_path),
        "layers": [{"name": "wind_speed", "source_path": str(src)}],
    }
    run_gwa_ingest(cfg)
    run_gwa_ingest(cfg)  # re-run → manifest name replaced, not duplicated
    doc = json.loads(manifest_path.read_text())
    names = [d["name"] for d in doc["datasets"]]
    assert names.count("DutchBay/GIS/gwa_250m_reference") == 1


def test_run_gwa_ingest_rejects_empty_layers(tmp_path):
    cfg = {
        "bbox": list(CLIP_BBOX),
        "out_dir": str(tmp_path / "gwa_out"),
        "manifest_path": str(tmp_path / "DataLake_Manifest_All.json"),
        "layers": [],
    }
    with pytest.raises(ValueError):
        run_gwa_ingest(cfg)


def test_ingest_rejects_degenerate_bbox(tmp_path):
    src = _write_synthetic_tile(tmp_path / "gwa_source.tif")
    with pytest.raises(ValueError):
        ingest_gwa_layer(src, "wind_speed", (80.0, 8.0, 79.0, 8.5), tmp_path / "x.tif")


def _write_mercator_tile(path: Path, latlon_bbox=TILE_BBOX, n=40, value=7.25) -> Path:
    """Write a constant-value single-band GeoTIFF in EPSG:3857 (Web Mercator).

    The tile's extent is the EPSG:4326 ``latlon_bbox`` transformed into Web Mercator, so
    a 4326 target bbox forces the differing-CRS warp branch. A constant field lets us
    assert the value survives the reprojection exactly (up to nodata edges).
    """
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds
    from rasterio.warp import transform_bounds

    web = CRS.from_epsg(3857)
    wgs = CRS.from_string(DEFAULT_CRS)
    m_w, m_s, m_e, m_n = transform_bounds(wgs, web, *latlon_bbox)
    arr = np.full((n, n), value, dtype="float32")
    transform = from_bounds(m_w, m_s, m_e, m_n, n, n)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=n,
        width=n,
        count=1,
        dtype="float32",
        crs=web,
        transform=transform,
    ) as dst:
        dst.write(arr, 1)
    return path


def test_ingest_reprojects_non_4326_source_to_target_crs(tmp_path):
    # Source in Web Mercator (EPSG:3857); target bbox in EPSG:4326 → forces the warp path.
    const = 7.25
    src = _write_mercator_tile(tmp_path / "gwa_merc.tif", value=const)
    out = tmp_path / "gwa_ws_reproj.tif"
    result = ingest_gwa_layer(src, "wind_speed", CLIP_BBOX, out, crs=DEFAULT_CRS)
    assert Path(result["path"]) == out

    with rasterio.open(out) as ds:
        # Reprojected + clipped: output CRS is the requested target, not the source.
        assert ds.crs.to_string() == DEFAULT_CRS
        assert ds.crs.to_epsg() == 4326
        assert ds.count == 1 and ds.dtypes[0] == "float32"
        # Sane dimensions.
        assert ds.shape[0] > 1 and ds.shape[1] > 1
        # Output extent lies within (or on) the requested 4326 bbox.
        w, s, e, n = ds.bounds
        assert CLIP_BBOX[0] - 1e-6 <= w < e <= CLIP_BBOX[2] + 1e-6
        assert CLIP_BBOX[1] - 1e-6 <= s < n <= CLIP_BBOX[3] + 1e-6

        data = ds.read(1)
        finite = data[np.isfinite(data)]
        # The constant field must survive the warp: every interpolated cell equals the
        # source constant (bilinear of equal neighbours), and min/max stay in range.
        assert finite.size > 0
        assert np.allclose(finite, const, atol=1e-3)
        assert float(finite.min()) >= const - 1e-3
        assert float(finite.max()) <= const + 1e-3

    # Provenance still stamps the reference labelling on the reprojected layer.
    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["source"] == GWA_SOURCE
    assert prov["reference_layer"] is True
    assert prov["requested_bbox"] == list(CLIP_BBOX)
