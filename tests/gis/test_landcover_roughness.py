"""ESA WorldCover land-cover -> z0 reclass + export tests (issue #830).

Builds a SYNTHETIC land-cover raster in-test (a few known ESA WorldCover class codes),
asserts the reclass maps each class to the expected z0, and that the z0 GeoTIFF +
``.prov.json`` sidecar (and manifest entry) are written. No network, no large files.
CASPER-skips when the ``[gis]`` extra (rasterio) is absent.
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
from analytics.gis.landcover_roughness import (  # noqa: E402
    DEFAULT_LANDCOVER_Z0,
    DEFAULT_Z0_FALLBACK,
    DEFAULT_Z0_TABLE_ID,
    LANDCOVER_SOURCE,
    export_roughness_raster,
    reclass_landcover_to_z0,
)

BBOX = (79.375, 7.895, 80.125, 8.645)  # ~0.75 deg box centred on Kalpitiya


def _write_synthetic_landcover(path: Path, classes: np.ndarray) -> Path:
    """Write a synthetic single-band uint8 ESA-WorldCover-style land-cover GeoTIFF."""
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    nrows, ncols = classes.shape
    west, south, east, north = BBOX
    transform = from_bounds(west, south, east, north, ncols, nrows)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=nrows,
        width=ncols,
        count=1,
        dtype="uint8",
        crs=CRS.from_string(DEFAULT_CRS),
        transform=transform,
    ) as dst:
        dst.write(classes.astype("uint8"), 1)
    return path


def test_reclass_maps_each_class_to_expected_z0():
    # Tree cover / Grassland / Built-up / Water — four known ESA WorldCover codes.
    codes = np.array([[10, 30], [50, 80]], dtype="uint8")
    z0, unmapped = reclass_landcover_to_z0(codes)
    assert unmapped == []
    expected = np.array(
        [
            [DEFAULT_LANDCOVER_Z0[10], DEFAULT_LANDCOVER_Z0[30]],
            [DEFAULT_LANDCOVER_Z0[50], DEFAULT_LANDCOVER_Z0[80]],
        ],
        dtype="float32",
    )
    assert z0.dtype == np.float32
    assert np.array_equal(z0, expected)


def test_reclass_reports_unmapped_code_with_fallback():
    # 200 is not an ESA WorldCover class → reported as unmapped, assigned fallback z0.
    codes = np.array([[10, 200]], dtype="uint16")
    z0, unmapped = reclass_landcover_to_z0(codes)
    assert unmapped == [200]
    assert z0[0, 0] == pytest.approx(DEFAULT_LANDCOVER_Z0[10])
    assert z0[0, 1] == pytest.approx(DEFAULT_Z0_FALLBACK)


def test_reclass_config_override_replaces_default():
    # A config table (string keys, as from YAML) fully replaces the default table.
    codes = np.array([[10, 30]], dtype="uint8")
    z0, unmapped = reclass_landcover_to_z0(codes, z0_table={"10": 1.5, "30": 0.02})
    assert unmapped == []
    assert z0[0, 0] == pytest.approx(1.5)
    assert z0[0, 1] == pytest.approx(0.02)


def test_reclass_rejects_non_2d():
    with pytest.raises(ValueError):
        reclass_landcover_to_z0(np.zeros((2, 2, 2), dtype="uint8"))


def test_export_writes_z0_geotiff_and_prov_sidecar(tmp_path):
    codes = np.array([[10, 20, 30], [40, 50, 60], [80, 90, 95]], dtype="uint8")
    lc = _write_synthetic_landcover(tmp_path / "worldcover.tif", codes)

    out = tmp_path / "dutchbay_roughness_z0.tif"
    manifest = tmp_path / "DataLake_Manifest_All.json"
    summary = export_roughness_raster(lc, out, manifest_path=manifest)

    assert summary["z0_path"] == str(out)
    assert summary["unmapped_codes"] == []
    assert summary["z0_table_id"] == DEFAULT_Z0_TABLE_ID

    with rasterio.open(out) as src:
        assert src.count == 1
        assert src.dtypes[0] == "float32"
        z0 = src.read(1)
        # spot-check reclass round-trip through the GeoTIFF
        assert z0[0, 0] == pytest.approx(DEFAULT_LANDCOVER_Z0[10])
        assert z0[1, 1] == pytest.approx(DEFAULT_LANDCOVER_Z0[50])
        assert z0[2, 2] == pytest.approx(DEFAULT_LANDCOVER_Z0[95])
        # z0 raster is co-registered with the input land-cover bbox
        assert [round(b, 3) for b in src.bounds] == [round(b, 3) for b in BBOX]

    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["source"] == LANDCOVER_SOURCE
    assert prov["z0_table_id"] == DEFAULT_Z0_TABLE_ID
    assert prov["z0_units"] == "metres"


def test_export_manifest_entry_written(tmp_path):
    codes = np.array([[10, 30], [50, 80]], dtype="uint8")
    lc = _write_synthetic_landcover(tmp_path / "worldcover.tif", codes)
    out = tmp_path / "z0.tif"
    manifest = tmp_path / "DataLake_Manifest_All.json"
    summary = export_roughness_raster(
        lc, out, manifest_path=manifest, manifest_name="DutchBay/GIS/roughness_z0"
    )
    assert summary["manifest_path"] == str(manifest)

    doc = json.loads(manifest.read_text())
    matching = [d for d in doc["datasets"] if d["name"] == "DutchBay/GIS/roughness_z0"]
    assert len(matching) == 1
    entry = matching[0]
    assert entry["variables"] == ["z0"]
    assert entry["gis"]["crs"] == DEFAULT_CRS
    assert entry["provenance"]["source"] == LANDCOVER_SOURCE


def test_export_config_override_recorded_in_provenance(tmp_path):
    codes = np.array([[10, 30]], dtype="uint8")
    lc = _write_synthetic_landcover(tmp_path / "worldcover.tif", codes)
    out = tmp_path / "z0.tif"
    summary = export_roughness_raster(lc, out, z0_table={"10": 0.9, "30": 0.04})
    assert summary["z0_table_id"] == "config_override"
    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["z0_table_id"] == "config_override"
    with rasterio.open(out) as src:
        z0 = src.read(1)
        assert z0[0, 0] == pytest.approx(0.9)
        assert z0[0, 1] == pytest.approx(0.04)
