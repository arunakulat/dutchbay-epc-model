"""GeoTIFF writer + manifest tests (issue #20). Rasterio round-trip; CASPER-skip if absent."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip(
    "rasterio"
)  # CASPER: skip when the [gis] extra is absent

from analytics.gis.geotiff_export import (  # noqa: E402
    DEFAULT_CRS,
    append_manifest,
    build_manifest_entry,
    export_grid_rasters,
    write_geotiff,
)

BBOX = (79.375, 7.895, 80.125, 8.645)  # ~0.75 deg box centred on Kalpitiya
VARS = ("ws150_mean", "capacity_factor", "aep_per_turbine")


def test_write_geotiff_roundtrip(tmp_path):
    arr = np.arange(9, dtype="float32").reshape(3, 3)
    out = write_geotiff(arr, BBOX, tmp_path / "ws.tif", provenance={"method": "test"})
    with rasterio.open(out) as src:
        assert src.crs.to_string() == DEFAULT_CRS
        assert src.shape == (3, 3)
        assert src.count == 1
        assert src.dtypes[0] == "float32"
        assert np.array_equal(src.read(1), arr)
        assert [round(b, 3) for b in src.bounds] == [round(b, 3) for b in BBOX]
        # north-up: upper-left pixel (col=0,row=0) maps to (west, north)
        west, north = src.transform * (0, 0)
        assert (round(west, 3), round(north, 3)) == (BBOX[0], BBOX[3])
    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["method"] == "test"


def test_write_geotiff_rejects_non_2d(tmp_path):
    with pytest.raises(ValueError):
        write_geotiff(np.zeros((2, 2, 2), dtype="float32"), BBOX, tmp_path / "x.tif")


def test_export_grid_rasters_one_file_per_variable(tmp_path):
    grids = {v: np.full((3, 3), i + 1, dtype="float32") for i, v in enumerate(VARS)}
    paths = export_grid_rasters(grids, BBOX, tmp_path, prefix="dutchbay_coarse")
    assert set(paths) == set(VARS)
    for v in VARS:
        assert Path(paths[v]).name == f"dutchbay_coarse_{v}.tif"
        with rasterio.open(paths[v]) as src:
            assert src.shape == (3, 3)


def test_append_manifest_idempotent(tmp_path):
    entry = build_manifest_entry(
        "DutchBay/GIS/coarse",
        BBOX,
        0.25,
        VARS,
        {v: f"{v}.tif" for v in VARS},
        provenance={"method": "test"},
    )
    manifest = tmp_path / "DataLake_Manifest_All.json"
    append_manifest(manifest, [entry])
    append_manifest(manifest, [entry])  # re-append the same name → no duplication
    doc = json.loads(manifest.read_text())
    matching = [d for d in doc["datasets"] if d["name"] == "DutchBay/GIS/coarse"]
    assert len(matching) == 1
    entry0 = matching[0]
    assert entry0["gis"]["crs"] == DEFAULT_CRS
    assert entry0["gis"]["resolution_deg"] == 0.25
    assert set(entry0["variables"]) == set(VARS)
