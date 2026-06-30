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
    spatial_representativeness,
)


def _uniform_cells(n: int, ws: float = 8.0):
    return [CellResult(0.0, 0.0, ws, 0.33, 18.0) for _ in range(n * n)]


def _synthetic_cells(spec: GridSpec):
    """A west→east ws gradient, with CF/AEP tracking it (for orientation checks)."""
    west = spec.center_lon - spec.span_deg / 2.0
    cells = []
    for lat, lon in spec.cell_centers():
        ws = 7.0 + (lon - west) * 2.0
        cells.append(
            CellResult(lat, lon, ws, 0.30 + (ws - 7.5) * 0.02, 17.0 + (ws - 7.5))
        )
    return cells


def test_gridspec_bbox_span_and_centers():
    spec = GridSpec("coarse", 8.27, 79.75, n=3, cell_deg=0.25)
    assert round(spec.span_deg, 6) == 0.75
    west, south, east, north = spec.bbox()
    assert round(west, 3) == 79.375 and round(north, 3) == 8.645
    centers = spec.cell_centers()
    assert len(centers) == 9
    assert centers[0][0] > centers[-1][0]  # row 0 is north of the last row
    assert centers[0][1] < centers[2][1]  # col 0 is west of col 2 in the top row


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
    assert (
        abs(float(fine["ws150_mean"][1, 1]) - float(coarse["ws150_mean"][1, 1])) < 0.4
    )


def test_gridspec_validation():
    with pytest.raises(ValueError):
        GridSpec("x", 0.0, 0.0, mode="bogus")
    with pytest.raises(ValueError):
        GridSpec("x", 0.0, 0.0, cell_deg=0.0)
    with pytest.raises(ValueError):
        GridSpec("x", 0.0, 0.0, n=1)


# ── WIND-10 (#484): spatial representativeness diagnostic ──────────────────────
def test_representativeness_uniform_neighbourhood_is_representative():
    chk = spatial_representativeness(_uniform_cells(3), 3)
    assert chk["assessed"] is True
    assert chk["spread_pct"] == 0.0
    assert chk["center_deviation_pct"] == 0.0
    assert chk["representative"] is True


def test_representativeness_steep_gradient_is_flagged():
    # A strong west->east gradient (centre cell well off the neighbourhood mean) must FAIL.
    spec = GridSpec("fine", 8.27, 79.75, n=3, cell_deg=0.25)
    cells = []
    west = spec.center_lon - spec.span_deg / 2.0
    for lat, lon in spec.cell_centers():
        ws = 5.0 + (lon - west) * 12.0  # steep gradient across the 3 columns
        cells.append(CellResult(lat, lon, ws, 0.33, 18.0))
    chk = spatial_representativeness(cells, 3)
    assert chk["spread_pct"] > 15.0
    assert chk["representative"] is False


def test_representativeness_uses_center_cell_deviation():
    # Bulk neighbourhood ~8 m/s but the CENTRE cell is an outlier -> deviation flag fires
    # even if the overall spread were modest.
    cells = [CellResult(0.0, 0.0, 8.0, 0.33, 18.0) for _ in range(9)]
    cells[4] = CellResult(0.0, 0.0, 9.2, 0.33, 18.0)  # centre is +~14% vs mean
    chk = spatial_representativeness(cells, 3, spread_tol_pct=100.0)
    assert chk["center_deviation_pct"] > 8.0
    assert chk["representative"] is False


def test_representativeness_rejects_even_n_and_wrong_count():
    with pytest.raises(ValueError, match="odd grid size"):
        spatial_representativeness(_uniform_cells(2), 2)
    with pytest.raises(ValueError, match="expected"):
        spatial_representativeness(_uniform_cells(3)[:8], 3)
