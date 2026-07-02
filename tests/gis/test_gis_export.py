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
            {
                "name": "fine",
                "n": 3,
                "cell_deg": 0.05,
                "mode": "interpolated",
                "source": "coarse",
            },
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
    # Re-run keeps exactly ONE representativeness verdict per grid — no accumulation.
    for d in doc["datasets"]:
        assert isinstance(d["spatial_representativeness"], dict)
        assert d["spatial_representativeness"]["assessed"] is True


# ── WIND-10 (#484): spatial representativeness wired into the export + manifest ──


def _representative_source(spec: GridSpec):
    """A gentle west→east gradient — within tolerance, so representative == True."""
    west = spec.center_lon - spec.span_deg / 2.0
    return [
        CellResult(lat, lon, 8.0 + (lon - west) * 0.2, 0.30, 17.5)
        for lat, lon in spec.cell_centers()
    ]


def _non_representative_source(spec: GridSpec):
    """A steep west→east gradient — the site cell is NOT representative (spread fires)."""
    west = spec.center_lon - spec.span_deg / 2.0
    return [
        CellResult(lat, lon, 5.0 + (lon - west) * 12.0, 0.33, 18.0)
        for lat, lon in spec.cell_centers()
    ]


def test_representative_neighbourhood_flows_to_summary_and_manifest(tmp_path):
    summary = run_gis_export(_cfg(tmp_path), source=_representative_source)

    # Attached to the returned per-grid summary (native + interpolated inherit).
    coarse_sr = summary["grids"]["coarse"]["spatial_representativeness"]
    assert coarse_sr["assessed"] is True
    assert coarse_sr["representative"] is True
    assert coarse_sr["grid"] == "coarse"
    # A fine grid carries its native source's verdict.
    assert summary["grids"]["fine"]["spatial_representativeness"]["grid"] == "coarse"

    # And to the DataLake manifest entry.
    doc = json.loads(Path(summary["manifest_path"]).read_text())
    coarse = next(d for d in doc["datasets"] if d["name"].endswith("coarse"))
    assert coarse["spatial_representativeness"]["assessed"] is True
    assert coarse["spatial_representativeness"]["representative"] is True


def test_non_representative_neighbourhood_is_flagged_in_manifest(tmp_path):
    summary = run_gis_export(_cfg(tmp_path), source=_non_representative_source)

    coarse_sr = summary["grids"]["coarse"]["spatial_representativeness"]
    assert coarse_sr["assessed"] is True
    assert coarse_sr["spread_pct"] > coarse_sr["spread_tol_pct"]
    assert coarse_sr["representative"] is False

    doc = json.loads(Path(summary["manifest_path"]).read_text())
    coarse = next(d for d in doc["datasets"] if d["name"].endswith("coarse"))
    assert coarse["spatial_representativeness"]["representative"] is False


def test_even_n_native_grid_records_explicit_unassessed(tmp_path):
    """An even-n native grid has no centre cell — explicit assessed:False, not a silent skip."""
    cfg = _cfg(tmp_path)
    cfg["grids"] = [{"name": "coarse", "n": 2, "cell_deg": 0.25, "mode": "native"}]
    summary = run_gis_export(cfg, source=_representative_source)

    sr = summary["grids"]["coarse"]["spatial_representativeness"]
    assert sr["assessed"] is False
    assert "even n=2" in sr["reason"]

    doc = json.loads(Path(summary["manifest_path"]).read_text())
    coarse = next(d for d in doc["datasets"] if d["name"].endswith("coarse"))
    assert coarse["spatial_representativeness"]["assessed"] is False


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
