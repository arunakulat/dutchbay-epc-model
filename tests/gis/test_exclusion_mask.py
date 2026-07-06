"""Constraint/exclusion buildable-area mask tests (issue #833).

Fully synthetic: a small EPSG:4326 grid, hand-placed point/line/polygon features and a
ramped slope grid let us assert, cell-by-cell, that setback buffers, protected-area
polygons and steep (slope > slope_max) cells are excluded while open, gentle cells are
kept. No network, no real tiles. Rasterio/shapely round-trips are CASPER-skipped when the
``[gis]`` extra is absent.

Grid convention (north-up): row 0 is the NORTH edge; row index increases southward,
column index increases eastward — matching the #20 exporter and the #829 DEM layers.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")  # CASPER: skip when the [gis] extra is absent
pytest.importorskip("shapely")  # CASPER: shapely is part of the [gis] toolchain

import rasterio  # noqa: E402

from analytics.gis.exclusion_mask import (  # noqa: E402
    MASK_VARIABLE,
    MASK_VARIABLES,
    build_buildable_mask,
    build_exclusion_geometry,
    build_setback_zone,
    run_exclusion_mask,
)
from analytics.gis.geotiff_export import DEFAULT_CRS  # noqa: E402

# A 10x10 grid over a 1.0-deg box -> 0.1-deg pixels. Cell centres sit at west+0.05+0.1*col,
# north-0.05-0.1*row, so cell (row, col) centre = (79.05 + 0.1*col, 8.95 - 0.1*row).
BBOX = (79.0, 8.0, 80.0, 9.0)  # (west, south, east, north)
NROWS = NCOLS = 10


def _cell_centre(row: int, col: int) -> tuple[float, float]:
    """Longitude/latitude of the centre of cell (row, col) for BBOX/NROWS/NCOLS."""
    west, south, east, north = BBOX
    dx = (east - west) / NCOLS
    dy = (north - south) / NROWS
    lon = west + dx * (col + 0.5)
    lat = north - dy * (row + 0.5)
    return lon, lat


def _flat_slope(value: float = 0.0) -> np.ndarray:
    return np.full((NROWS, NCOLS), value, dtype="float64")


# --------------------------------------------------------------------------------------
# Buffer geometry
# --------------------------------------------------------------------------------------


def test_setback_buffer_geometry_contains_and_excludes_by_distance():
    """A point buffered by d contains points within d and excludes those beyond it."""
    from shapely.geometry import Point

    centre = [79.5, 8.5]
    zone = build_setback_zone([centre], setback_distance=0.15)
    assert not zone.is_empty
    # A point 0.1 deg away (< 0.15) is inside the buffer; one 0.3 deg away is outside.
    assert zone.contains(Point(79.5 + 0.1, 8.5))
    assert not zone.contains(Point(79.5 + 0.3, 8.5))


def test_empty_feature_class_yields_empty_zone():
    zone = build_setback_zone([], setback_distance=0.2)
    assert zone.is_empty


def test_line_feature_buffer_is_a_corridor():
    """A line (road/grid) buffered by d excludes a strip either side of the line."""
    from shapely.geometry import Point

    road = [[79.2, 8.5], [79.8, 8.5]]  # horizontal line at lat 8.5
    zone = build_setback_zone([road], setback_distance=0.08)
    assert zone.contains(Point(79.5, 8.5 + 0.05))  # just above the line, within buffer
    assert not zone.contains(Point(79.5, 8.5 + 0.5))  # far above, outside buffer


def test_build_exclusion_geometry_unions_setbacks_and_protected():
    """The combined no-build geometry covers both a setback point and a protected polygon."""
    from shapely.geometry import Point

    protected = {
        "type": "Polygon",
        "coordinates": [
            [[79.1, 8.1], [79.3, 8.1], [79.3, 8.3], [79.1, 8.3], [79.1, 8.1]]
        ],
    }
    geom = build_exclusion_geometry(
        setbacks={"dwellings": {"features": [[79.7, 8.7]], "distance": 0.1}},
        protected_areas=[protected],
    )
    assert geom.contains(Point(79.7, 8.7))  # inside the dwelling setback
    assert geom.contains(Point(79.2, 8.2))  # inside the protected polygon


# --------------------------------------------------------------------------------------
# Mask logic
# --------------------------------------------------------------------------------------


def test_slope_threshold_excludes_steep_cells_keeps_gentle():
    """Cells with slope > slope_max are not buildable; cells <= slope_max are (no vectors)."""
    slope = _flat_slope(5.0)
    slope[3, 3] = 20.0  # one steep cell
    slope[7, 7] = 12.0  # another steep cell
    mask, diag = build_buildable_mask(slope, BBOX, slope_max=10.0)

    assert mask[3, 3] == False  # noqa: E712 - steep excluded
    assert mask[7, 7] == False  # noqa: E712
    assert mask[0, 0] == True  # noqa: E712 - gentle kept
    assert diag["cells_excluded_steep"] == 2
    assert diag["cells_buildable"] == NROWS * NCOLS - 2


def test_nan_slope_is_not_buildable():
    """A NaN slope cell (nodata) is excluded — buildable requires slope <= slope_max."""
    slope = _flat_slope(2.0)
    slope[5, 5] = np.nan
    mask, diag = build_buildable_mask(slope, BBOX, slope_max=15.0)
    assert mask[5, 5] == False  # noqa: E712
    assert diag["cells_excluded_steep"] == 1


def test_setback_excludes_cells_near_a_dwelling():
    """A dwelling point with a setback excludes the cells its buffer covers, keeps the rest."""
    slope = _flat_slope(1.0)
    # Place a dwelling at the centre of cell (2, 2); buffer 0.05 deg (~half a cell) so it
    # excludes (2,2) but leaves a distant cell (8,8) buildable.
    lon, lat = _cell_centre(2, 2)
    mask, diag = build_buildable_mask(
        slope,
        BBOX,
        slope_max=30.0,
        setbacks={"dwellings": {"features": [[lon, lat]], "distance": 0.05}},
    )
    assert mask[2, 2] == False  # noqa: E712 - inside the setback
    assert mask[8, 8] == True  # noqa: E712 - far away, kept
    assert diag["cells_excluded_vector"] >= 1
    assert diag["setback_classes"] == ["dwellings"]


def test_protected_area_polygon_excludes_covered_cells():
    """A protected polygon excludes the cells it covers regardless of slope."""
    slope = _flat_slope(0.0)  # perfectly flat -> slope never excludes
    # Polygon covering the NW block roughly rows 0-2, cols 0-2.
    protected = {
        "type": "Polygon",
        "coordinates": [
            [[79.0, 8.7], [79.3, 8.7], [79.3, 9.0], [79.0, 9.0], [79.0, 8.7]]
        ],
    }
    mask, diag = build_buildable_mask(
        slope, BBOX, slope_max=45.0, protected_areas=[protected]
    )
    assert mask[0, 0] == False  # noqa: E712 - inside protected NW block
    assert mask[1, 1] == False  # noqa: E712
    assert mask[9, 9] == True  # noqa: E712 - SE corner, outside protected block
    assert diag["protected_area_count"] == 1
    assert diag["cells_excluded_vector"] >= 4


def test_boundary_clip_keeps_only_inside_cells():
    """An optional boundary polygon makes cells outside it non-buildable."""
    slope = _flat_slope(0.0)
    # Boundary covering only the SE quarter (cols 5-9, rows 5-9 roughly).
    boundary = {
        "type": "Polygon",
        "coordinates": [
            [[79.5, 8.0], [80.0, 8.0], [80.0, 8.5], [79.5, 8.5], [79.5, 8.0]]
        ],
    }
    mask, diag = build_buildable_mask(slope, BBOX, slope_max=45.0, boundary=boundary)
    assert diag["boundary_clip_applied"] is True
    assert mask[8, 8] == True  # noqa: E712 - inside SE boundary
    assert mask[0, 0] == False  # noqa: E712 - NW, outside boundary
    assert mask[1, 8] == False  # noqa: E712 - north strip, outside boundary


def test_combined_constraints_only_open_gentle_cells_survive():
    """Steep, setback and protected cells all drop out; an open gentle cell remains."""
    slope = _flat_slope(3.0)
    slope[0, 0] = 40.0  # steep
    dwelling_lon, dwelling_lat = _cell_centre(0, 9)  # NE corner cell
    protected = {
        "type": "Polygon",
        "coordinates": [
            [[79.0, 8.0], [79.2, 8.0], [79.2, 8.2], [79.0, 8.2], [79.0, 8.0]]
        ],
    }  # SW corner block
    mask, diag = build_buildable_mask(
        slope,
        BBOX,
        slope_max=10.0,
        setbacks={
            "dwellings": {"features": [[dwelling_lon, dwelling_lat]], "distance": 0.04}
        },
        protected_areas=[protected],
    )
    assert mask[0, 0] == False  # noqa: E712 - steep
    assert mask[0, 9] == False  # noqa: E712 - dwelling setback (NE)
    assert mask[9, 0] == False  # noqa: E712 - protected (SW)
    # A central open, gentle cell survives every constraint.
    assert mask[5, 5] == True  # noqa: E712
    assert 0.0 < diag["buildable_fraction"] < 1.0


# --------------------------------------------------------------------------------------
# End-to-end run_exclusion_mask (GeoTIFF + prov + manifest)
# --------------------------------------------------------------------------------------


def test_run_exclusion_mask_writes_boolean_geotiff_prov_and_manifest(tmp_path):
    """End-to-end: a Boolean mask GeoTIFF + .prov.json sidecar + a manifest entry."""
    slope = _flat_slope(2.0)
    slope[4, 4] = 25.0  # one steep cell excluded
    out = tmp_path / "buildable.tif"
    manifest = tmp_path / "DataLake_Manifest_All.json"

    summary = run_exclusion_mask(
        {
            "slope_array": slope.tolist(),
            "bbox": list(BBOX),
            "slope_max": 10.0,
            "out_path": str(out),
            "manifest_path": str(manifest),
            "setbacks": {
                "roads": {"features": [[[79.2, 8.5], [79.8, 8.5]]], "distance": 0.03}
            },
        }
    )

    assert out.exists()
    assert summary["slope_max_deg"] == 10.0
    assert 0.0 < summary["buildable_fraction"] < 1.0
    assert set(MASK_VARIABLES) == {MASK_VARIABLE}

    # The raster is a 0.0/1.0 Boolean field on the slope grid, EPSG:4326.
    with rasterio.open(out) as src:
        assert src.crs.to_string() == DEFAULT_CRS
        assert src.shape == (NROWS, NCOLS)
        band = src.read(1)
    assert set(np.unique(band)).issubset({0.0, 1.0})
    assert band[4, 4] == 0.0  # the steep cell is not buildable

    # Provenance sidecar records the method + diagnostics.
    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["layer"] == "buildable_area_mask"
    assert prov["cells_excluded_steep"] == 1
    assert "roads" in prov["setback_classes"]

    # Manifest entry is present and idempotent-named.
    doc = json.loads(manifest.read_text())
    entry = [d for d in doc["datasets"] if d["name"] == "DutchBay/GIS/buildable"]
    assert len(entry) == 1
    assert entry[0]["variables"] == list(MASK_VARIABLES)
    assert entry[0]["gis"]["crs"] == DEFAULT_CRS


def test_run_exclusion_mask_requires_a_slope_source(tmp_path):
    """CESSPIT: a config with neither slope_path nor slope_array is a loud error."""
    with pytest.raises(KeyError):
        run_exclusion_mask(
            {
                "bbox": list(BBOX),
                "slope_max": 10.0,
                "out_path": str(tmp_path / "x.tif"),
                "manifest_path": str(tmp_path / "m.json"),
            }
        )


def test_run_exclusion_mask_reads_slope_from_geotiff(tmp_path):
    """The slope layer can be a GeoTIFF path (the #829 DEM output), not just an array."""
    from analytics.gis.geotiff_export import write_geotiff

    slope = _flat_slope(1.0)
    slope[6, 6] = 30.0
    slope_tif = tmp_path / "slope.tif"
    write_geotiff(slope.astype("float32"), BBOX, slope_tif, provenance={"src": "test"})

    summary = run_exclusion_mask(
        {
            "slope_path": str(slope_tif),
            "bbox": list(BBOX),
            "slope_max": 10.0,
            "out_path": str(tmp_path / "buildable.tif"),
            "manifest_path": str(tmp_path / "m.json"),
        }
    )
    assert summary["diagnostics"]["cells_excluded_steep"] == 1
