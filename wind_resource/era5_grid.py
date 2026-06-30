"""ERA5 gridded (n×n) wind/AEP fields for GIS export (issue #20).

Builds **coarse** (native-ERA5 ≈0.25°) and **fine** (downscaled ≈0.05° wind-farm
scale) n×n grids of ``ws150_mean`` / ``capacity_factor`` / ``aep_per_turbine`` over a
project site, by sampling the existing ERA5 point pipeline at the grid-cell centres
and reusing :class:`~wind_resource.energy_calculator.EnergyCalculator` for net AEP/CF
(via :func:`wind_resource.era5_retrieval.compute_site_aep`).

Two honest resolutions (issue #20 — "coarse first, then narrow to wind-farm scale"):

- **coarse** (``mode="native"``): one real ERA5 point per cell, ``cell_deg`` ≈ 0.25°
  (native reanalysis). Genuine spatial variation across the ~0.75° box.
- **fine** (``mode="interpolated"``): a **bilinear downscale** of the coarse field onto
  a tighter ``cell_deg`` ≈ 0.05° grid centred on the site. This is a smooth
  interpolation of the 0.25° reanalysis — NOT a measured sub-grid observation — and is
  labelled as such in the export provenance (#18 discipline).

GWTF: config-first, fully typed, no hardcoded site constants, no ``argparse``/``input()``.
The live CDS fetch (:func:`fetch_cell_results`) reuses the ``[wind]`` extra + credentials
in ``~/.cdsapirc``; the pure assembly/downscale functions take injected results so they
are unit-testable without any network call.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Tuple

import numpy as np

#: The three raster variables exported for QGIS (issue #20).
GRID_VARIABLES: Tuple[str, ...] = ("ws150_mean", "capacity_factor", "aep_per_turbine")


@dataclass(frozen=True)
class GridSpec:
    """An n×n sampling grid centred on a project site.

    Attributes:
        name: Grid label (e.g. ``"coarse"`` / ``"fine"``); used in filenames + manifest.
        center_lat: Site centre latitude (degrees, WGS84).
        center_lon: Site centre longitude (degrees, WGS84).
        n: Grid size per side (3 → a 3×3 grid).
        cell_deg: Cell size in degrees (≈0.25 native ERA5; ≈0.05 wind-farm scale).
        mode: ``"native"`` (sample ERA5 at each cell centre) or ``"interpolated"``
            (bilinear downscale of a coarse grid — see :func:`downscale_bilinear`).
    """

    name: str
    center_lat: float
    center_lon: float
    n: int = 3
    cell_deg: float = 0.25
    mode: str = "native"

    def __post_init__(self) -> None:
        if self.n < 2:
            raise ValueError(f"grid n must be >= 2, got {self.n}")
        if self.cell_deg <= 0.0:
            raise ValueError(f"cell_deg must be > 0, got {self.cell_deg}")
        if self.mode not in ("native", "interpolated"):
            raise ValueError(
                f"mode must be 'native' or 'interpolated', got {self.mode}"
            )

    @property
    def span_deg(self) -> float:
        """Total grid extent per side in degrees."""
        return self.cell_deg * self.n

    def bbox(self) -> Tuple[float, float, float, float]:
        """Bounding box ``(west, south, east, north)`` in degrees."""
        half = self.span_deg / 2.0
        return (
            self.center_lon - half,
            self.center_lat - half,
            self.center_lon + half,
            self.center_lat + half,
        )

    def cell_centers(self) -> List[Tuple[float, float]]:
        """Row-major ``(lat, lon)`` cell centres, north→south then west→east.

        Row 0 is the northernmost row, matching a north-up GeoTIFF where raster row 0
        is the top (north) edge.
        """
        half = self.span_deg / 2.0
        lats = [
            self.center_lat + half - (i + 0.5) * self.cell_deg for i in range(self.n)
        ]
        lons = [
            self.center_lon - half + (j + 0.5) * self.cell_deg for j in range(self.n)
        ]
        return [(la, lo) for la in lats for lo in lons]


@dataclass(frozen=True)
class CellResult:
    """Per-cell ERA5-derived wind/AEP result."""

    lat: float
    lon: float
    ws150_mean: float
    capacity_factor: float
    aep_per_turbine_gwh: float


def assemble_grids(cells: List[CellResult], n: int) -> Dict[str, np.ndarray]:
    """Reshape row-major per-cell results into ``n×n`` float32 arrays per variable."""
    if len(cells) != n * n:
        raise ValueError(f"expected {n * n} cells for a {n}x{n} grid, got {len(cells)}")
    ws = np.array([c.ws150_mean for c in cells], dtype="float32").reshape(n, n)
    cf = np.array([c.capacity_factor for c in cells], dtype="float32").reshape(n, n)
    aep = np.array([c.aep_per_turbine_gwh for c in cells], dtype="float32").reshape(
        n, n
    )
    return {"ws150_mean": ws, "capacity_factor": cf, "aep_per_turbine": aep}


def spatial_representativeness(
    cells: List[CellResult],
    n: int,
    *,
    spread_tol_pct: float = 15.0,
    deviation_tol_pct: float = 8.0,
) -> Dict[str, Any]:
    """Is the site's ERA5 cell REPRESENTATIVE of its neighbourhood? (WIND-10, #484).

    A single-cell assessment silently assumes the site cell typifies the surrounding
    resource. On a steep wind gradient (coastline, ridge) that can bias the AEP. Given an
    ``n×n`` (odd ``n``) neighbourhood of ``CellResult`` cells, this computes the hub-height
    wind-speed SPREAD across the neighbourhood ``100*(max-min)/mean`` and the centre cell's
    DEVIATION from the neighbourhood mean ``100*(centre-mean)/mean``, and flags
    ``representative`` when both are within tolerance. It is a read-only diagnostic — it does
    NOT alter the AEP; a fired flag is a prompt to review siting/measurement, not an automatic
    adjustment.
    """
    if len(cells) != n * n:
        raise ValueError(f"expected {n * n} cells for a {n}x{n} grid, got {len(cells)}")
    if n % 2 == 0:
        raise ValueError(
            f"need an odd grid size for a well-defined centre cell, got n={n}"
        )
    arr = np.asarray([c.ws150_mean for c in cells], dtype=float)
    center_ws = float(arr[(n // 2) * n + (n // 2)])
    nbhd_mean = float(arr.mean())
    if nbhd_mean <= 0.0:
        raise ValueError(
            "neighbourhood mean wind speed must be > 0 to assess representativeness"
        )
    spread_pct = 100.0 * (float(arr.max()) - float(arr.min())) / nbhd_mean
    deviation_pct = 100.0 * (center_ws - nbhd_mean) / nbhd_mean
    return {
        "assessed": True,
        "n_cells": n * n,
        "center_ws150_ms": round(center_ws, 4),
        "neighbourhood_mean_ws150_ms": round(nbhd_mean, 4),
        "spread_pct": round(spread_pct, 4),
        "center_deviation_pct": round(deviation_pct, 4),
        "spread_tol_pct": float(spread_tol_pct),
        "deviation_tol_pct": float(deviation_tol_pct),
        "representative": bool(
            spread_pct <= spread_tol_pct and abs(deviation_pct) <= deviation_tol_pct
        ),
    }


def downscale_bilinear(
    coarse: Dict[str, np.ndarray],
    coarse_spec: GridSpec,
    fine_spec: GridSpec,
) -> Dict[str, np.ndarray]:
    """Bilinearly interpolate each coarse field onto the fine grid's cell centres.

    The fine grid must lie within the coarse grid's extent. The result is a smooth
    ERA5 *downscale* (gradient inherited from the 0.25° field), NOT a measured sub-grid
    observation — the GIS export stamps this in provenance.

    Args:
        coarse: ``{variable: n×n array}`` from :func:`assemble_grids` (north-up rows).
        coarse_spec: The coarse grid's spec (provides cell-centre coordinates).
        fine_spec: The (tighter, centred) fine grid to interpolate onto.

    Returns:
        ``{variable: m×m array}`` on the fine grid (north-up rows), float32.
    """
    from scipy.interpolate import RegularGridInterpolator

    half = coarse_spec.span_deg / 2.0
    # Coarse cell-centre coordinates. Rows run north→south, so latitudes descend.
    clats_desc = np.array(
        [
            coarse_spec.center_lat + half - (i + 0.5) * coarse_spec.cell_deg
            for i in range(coarse_spec.n)
        ]
    )
    clons = np.array(
        [
            coarse_spec.center_lon - half + (j + 0.5) * coarse_spec.cell_deg
            for j in range(coarse_spec.n)
        ]
    )
    lat_asc = clats_desc[::-1]  # RegularGridInterpolator needs strictly ascending axes
    fine_pts = np.array(fine_spec.cell_centers())  # (m*m, 2) as (lat, lon)

    out: Dict[str, np.ndarray] = {}
    for var, grid in coarse.items():
        grid_asc = grid[::-1, :]  # flip rows to ascending-lat order
        interp = RegularGridInterpolator(
            (lat_asc, clons),
            grid_asc,
            method="linear",
            bounds_error=False,
            fill_value=None,
        )
        vals = interp(fine_pts).astype("float32").reshape(fine_spec.n, fine_spec.n)
        out[var] = vals
    return out


def fetch_cell_results(
    spec: GridSpec,
    base_request: Any,
) -> List[CellResult]:  # pragma: no cover - exercised only via a live CDS fetch
    """Sample the ERA5 point pipeline at each grid-cell centre (LIVE CDS).

    Reuses ``retrieve_era5_timeseries`` → ``build_hub_height_series`` →
    ``compute_site_aep`` per cell (so the Weibull/power-curve/loss physics is the same
    as the canonical site AEP). One ERA5 download per cell — slow; NOT run in CI.

    Args:
        spec: The grid to sample (``mode="native"``).
        base_request: A ``wind_resource.era5_retrieval.ERA5RequestConfig`` providing the
            turbine model, hub height, period and output dir; its lat/lon are replaced
            per cell.

    Returns:
        Row-major list of :class:`CellResult`, one per cell centre.
    """
    from wind_resource.era5_retrieval import (
        build_hub_height_series,
        compute_site_aep,
        retrieve_era5_timeseries,
    )

    if spec.mode != "native":
        raise ValueError(
            "fetch_cell_results requires a 'native' grid; downscale the fine grid"
        )

    results: List[CellResult] = []
    n_turb = max(1, int(getattr(base_request, "num_turbines", 1)))
    for lat, lon in spec.cell_centers():
        cfg = replace(
            base_request,
            latitude=lat,
            longitude=lon,
            project_name=f"{base_request.project_name}_{spec.name}_{lat:.3f}_{lon:.3f}",
        )
        nc_path = retrieve_era5_timeseries(cfg)
        series = build_hub_height_series(nc_path, cfg)
        aep = compute_site_aep(series, cfg)
        results.append(
            CellResult(
                lat=lat,
                lon=lon,
                ws150_mean=float(aep["mean_ws_hub_ms"]),
                capacity_factor=float(aep["capacity_factor_p50"]),
                aep_per_turbine_gwh=round(float(aep["net_aep_p50_gwh"]) / n_turb, 3),
            )
        )
    return results
