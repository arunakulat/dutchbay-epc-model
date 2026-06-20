"""End-to-end GIS export with an injected synthetic source (no network). Issue #20."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("rasterio")  # the writer needs the [gis] extra

from analytics.gis.gis_export import default_era5_source, run_gis_export  # noqa: E402
from wind_resource.era5_grid import CellResult, GridSpec  # noqa: E402


def _synthetic_source(spec: GridSpec):
    """Stand-in for the live ERA5 fetch: a smooth west→east gradient per cell."""
    west = spec.center_lon - spec.span_deg / 2.0
    return [
        CellResult(lat, lon, 7.0 + (lon - west) * 1.5, 0.30, 17.5)
        for lat, lon in spec.cell_centers()
    ]


def _cfg(tmp_path):
    out = tmp_path / "gis"
    return {
        "crs": "EPSG:4326",
        "out_dir": str(out),
        "manifest_path": str(out / "DataLake_Manifest_All.json"),
        "center_lat": 8.27,
        "center_lon": 79.75,
        "grids": [
            {"name": "coarse", "n": 3, "cell_deg": 0.25, "mode": "native"},
            {"name": "fine", "n": 3, "cell_deg": 0.05, "mode": "interpolated", "source": "coarse"},
        ],
    }


def test_run_gis_export_writes_coarse_and_fine(tmp_path):
    import rasterio

    summary = run_gis_export(_cfg(tmp_path), source=_synthetic_source)
    assert set(summary["grids"]) == {"coarse", "fine"}

    out_dir = Path(summary["grids"]["coarse"]["files"]["ws150_mean"]).parent
    assert len(sorted(out_dir.glob("*.tif"))) == 6  # 2 grids × 3 variables

    with rasterio.open(summary["grids"]["fine"]["files"]["ws150_mean"]) as src:
        assert src.crs.to_string() == "EPSG:4326"
        assert src.shape == (3, 3)

    doc = json.loads(Path(summary["manifest_path"]).read_text())
    names = {d["name"] for d in doc["datasets"]}
    assert names == {"DutchBay/GIS/coarse", "DutchBay/GIS/fine"}

    fine = next(d for d in doc["datasets"] if d["name"].endswith("fine"))
    assert fine["gis"]["resolution_deg"] == 0.05
    assert fine["provenance"]["method"] == "bilinear_downscale_of_era5"

    coarse = next(d for d in doc["datasets"] if d["name"].endswith("coarse"))
    assert coarse["gis"]["resolution_deg"] == 0.25
    assert coarse["provenance"]["method"] == "era5_native_point_sample"


def test_run_gis_export_manifest_idempotent(tmp_path):
    cfg = _cfg(tmp_path)
    run_gis_export(cfg, source=_synthetic_source)
    summary = run_gis_export(cfg, source=_synthetic_source)  # re-run
    doc = json.loads(Path(summary["manifest_path"]).read_text())
    assert len(doc["datasets"]) == 2  # no duplication


# ── ARCH-01 / CESSPIT: gis.era5 turbine/site identity is config-required ─────────

_VALID_ERA5 = {
    "start_year": 2020,
    "end_year": 2024,
    "hub_height_m": 150,
    "turbine_model": "iea_reference_10mw",
    "num_turbines": 15,
}


def test_default_era5_source_builds_from_complete_block():
    """A complete gis.era5 block yields a usable source provider (no fetch yet)."""
    src = default_era5_source(dict(_VALID_ERA5))
    assert callable(src)


@pytest.mark.parametrize("missing", ["hub_height_m", "turbine_model", "num_turbines"])
def test_default_era5_source_requires_turbine_identity(missing):
    """Omitting any turbine/site identity field must raise — no EN-171/23/150 fallback."""
    bad = {k: v for k, v in _VALID_ERA5.items() if k != missing}
    with pytest.raises(KeyError, match=missing):
        default_era5_source(bad)
