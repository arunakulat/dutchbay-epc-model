"""ERA5 grid spec / assembly / downscale tests (issue #20). No network — synthetic cells."""

from __future__ import annotations

import numpy as np
import pytest

from wind_resource.era5_grid import (
    GRID_VARIABLES,
    CellResult,
    GridSpec,
    assemble_grids,
    downscale_bilinear,
)


def _synthetic_cells(spec: GridSpec):
    """A west→east ws gradient, with CF/AEP tracking it (for orientation checks)."""
    west = spec.center_lon - spec.span_deg / 2.0
    cells = []
    for lat, lon in spec.cell_centers():
        ws = 7.0 + (lon - west) * 2.0
        cells.append(CellResult(lat, lon, ws, 0.30 + (ws - 7.5) * 0.02, 17.0 + (ws - 7.5)))
    return cells


def test_gridspec_bbox_span_and_centers():
    spec = GridSpec("coarse", 8.27, 79.75, n=3, cell_deg=0.25)
    assert round(spec.span_deg, 6) == 0.75
    west, south, east, north = spec.bbox()
    assert round(west, 3) == 79.375 and round(north, 3) == 8.645
    centers = spec.cell_centers()
    assert len(centers) == 9
    assert centers[0][0] > centers[-1][0]   # row 0 is north of the last row
    assert centers[0][1] < centers[2][1]    # col 0 is west of col 2 in the top row


def test_assemble_grids_shape_dtype_and_orientation():
    spec = GridSpec("coarse", 8.27, 79.75)
    grids = assemble_grids(_synthetic_cells(spec), spec.n)
    assert set(grids) == set(GRID_VARIABLES)
    for var in GRID_VARIABLES:
        assert grids[var].shape == (3, 3)
        assert grids[var].dtype == np.dtype("float32")
    assert grids["ws150_mean"][0, 0] < grids["ws150_mean"][0, 2]  # west < east


def test_assemble_wrong_cell_count_raises():
    spec = GridSpec("coarse", 8.27, 79.75)
    with pytest.raises(ValueError):
        assemble_grids(_synthetic_cells(spec)[:8], spec.n)


def test_downscale_bilinear_bounded_and_centered():
    coarse_spec = GridSpec("coarse", 8.27, 79.75, n=3, cell_deg=0.25)
    fine_spec = GridSpec("fine", 8.27, 79.75, n=3, cell_deg=0.05, mode="interpolated")
    coarse = assemble_grids(_synthetic_cells(coarse_spec), coarse_spec.n)
    fine = downscale_bilinear(coarse, coarse_spec, fine_spec)
    for var in GRID_VARIABLES:
        assert fine[var].shape == (3, 3)
        # interpolation within the coarse field stays within its value range
        assert coarse[var].min() - 1e-3 <= float(fine[var].min())
        assert float(fine[var].max()) <= coarse[var].max() + 1e-3
    # the fine centre cell ≈ the coarse centre cell
    assert abs(float(fine["ws150_mean"][1, 1]) - float(coarse["ws150_mean"][1, 1])) < 0.4


def test_gridspec_validation():
    with pytest.raises(ValueError):
        GridSpec("x", 0.0, 0.0, mode="bogus")
    with pytest.raises(ValueError):
        GridSpec("x", 0.0, 0.0, cell_deg=0.0)
    with pytest.raises(ValueError):
        GridSpec("x", 0.0, 0.0, n=1)
