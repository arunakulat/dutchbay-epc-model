"""DEM ingest + terrain derivatives for the site bbox (issue #829, epic #827).

Load a **Copernicus GLO-30** (30 m) digital elevation model — SRTM 1-arcsec as the
documented fallback — from a LOCAL GeoTIFF, clip it to a config bounding box, and derive
**slope, aspect and hillshade** layers with numpy (Horn's 1981 3x3 kernel — the same
math GDAL's ``gdaldem`` uses). Each of the four layers (elevation, slope, aspect,
hillshade) is written back out as a provenance-stamped GeoTIFF plus a
``DataLake_Manifest_All.json`` entry, reusing the issue-#20 exporter helpers.

This is the terrain foundation the RIX ruggedness diagnostic (#831) and the
slope-threshold siting mask (#833) consume, so the slope layer (degrees, north-up,
same grid as the elevation input) is kept clean and directly reusable.

CASPER: ``rasterio`` is an optional ``[gis]`` dependency, guarded at call time via
:func:`analytics.gis.geotiff_export._require_rasterio` (so the base finance install never
needs GDAL). CCCDIR / config-first (ARCH-01): the DEM path, bbox, sun azimuth/altitude,
z-factor, output dir, manifest path and CRS are all config/arg-supplied — nothing about a
particular site or tile is hardcoded here. KPI-neutral: a pure GIS layer, not wired into
the finance pipeline.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np

from analytics.gis.geotiff_export import (
    DEFAULT_CRS,
    BBox,
    _require_rasterio,
    append_manifest,
    build_manifest_entry,
    write_geotiff,
)

logger = logging.getLogger(__name__)

#: DEM sources this ingester records in provenance. GLO-30 is the primary; SRTM the
#: documented fallback (issue #829). The value is recorded verbatim in the ``.prov.json``
#: sidecar so a downstream reader (RIX #831, siting mask #833) knows which DEM it is on.
DEM_SOURCES = {
    "glo30": "Copernicus GLO-30 DEM",
    "srtm": "SRTM 1-arcsec",
}
DEFAULT_DEM_SOURCE = "glo30"

#: Default sun geometry for the hillshade (a conventional NW illumination). Overridable
#: from config so a site can request its own azimuth/altitude.
DEFAULT_SUN_AZIMUTH_DEG = 315.0
DEFAULT_SUN_ALTITUDE_DEG = 45.0

#: Terrain layers this module derives, in a stable order.
TERRAIN_VARIABLES: Tuple[str, ...] = ("elevation", "slope", "aspect", "hillshade")


def _pixel_size_deg(bbox: BBox, nrows: int, ncols: int) -> Tuple[float, float]:
    """Return ``(dx, dy)`` pixel size in bbox units from the north-up affine.

    ``dx`` is the west-east cell width, ``dy`` the north-south cell height; both positive.
    """
    west, south, east, north = bbox
    dx = (east - west) / float(ncols)
    dy = (north - south) / float(nrows)
    return dx, dy


def _horn_gradients(
    z: np.ndarray, dx: float, dy: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Horn's 1981 3x3 finite-difference gradients of a north-up elevation grid.

    ``z`` is row-0 == north (top). Returns ``(dz_dx, dz_dy)`` where ``dz_dx`` increases
    to the east and ``dz_dy`` increases to the north — matching ``gdaldem``'s convention.
    Edges use replicated padding (``np.pad(mode="edge")``) so the output keeps the input
    shape without introducing spurious boundary slopes.
    """
    p = np.pad(z.astype("float64"), 1, mode="edge")
    # 3x3 neighbourhood (a b c / d e f / g h i); row index increases southward.
    a = p[:-2, :-2]
    b = p[:-2, 1:-1]
    c = p[:-2, 2:]
    d = p[1:-1, :-2]
    f = p[1:-1, 2:]
    g = p[2:, :-2]
    h = p[2:, 1:-1]
    i = p[2:, 2:]

    dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * dx)
    # Row index increases southward, so a positive northward gradient is (top - bottom).
    dz_dy = ((a + 2.0 * b + c) - (g + 2.0 * h + i)) / (8.0 * dy)
    return dz_dx, dz_dy


def slope_aspect_hillshade(
    elevation: np.ndarray,
    dx: float,
    dy: float,
    *,
    z_factor: float = 1.0,
    sun_azimuth_deg: float = DEFAULT_SUN_AZIMUTH_DEG,
    sun_altitude_deg: float = DEFAULT_SUN_ALTITUDE_DEG,
) -> Dict[str, np.ndarray]:
    """Derive slope (deg), aspect (deg) and hillshade (0-255) from an elevation grid.

    Args:
        elevation: 2-D north-up elevation grid (row 0 == north).
        dx: West-east pixel size in the SAME units as ``elevation`` values (so slope is
            dimensionless before ``atan``; e.g. for a projected DEM both are metres).
        dy: North-south pixel size, same units.
        z_factor: Vertical exaggeration / unit-conversion factor applied to elevation
            before the gradient (GDAL's ``-z`` — e.g. to reconcile degree-spaced pixels
            with metre elevations). Defaults to 1.0 (no scaling).
        sun_azimuth_deg: Illumination azimuth, degrees clockwise from north.
        sun_altitude_deg: Illumination altitude above the horizon, degrees.

    Returns:
        ``{"slope": deg, "aspect": deg, "hillshade": 0-255}`` — each the same shape as
        ``elevation``. Slope is ``atan(sqrt((dz/dx)^2 + (dz/dy)^2))`` in degrees; a flat
        cell has slope 0 and (by GDAL convention) aspect ``-1``. Aspect is degrees
        clockwise from north (the downslope-facing direction). Hillshade is the standard
        Lambertian shaded relief.
    """
    z = np.asarray(elevation, dtype="float64") * float(z_factor)
    if z.ndim != 2:
        raise ValueError(f"expected a 2-D elevation grid, got shape {z.shape}")

    dz_dx, dz_dy = _horn_gradients(z, dx, dy)

    grad = np.hypot(dz_dx, dz_dy)
    slope_rad = np.arctan(grad)
    slope_deg = np.degrees(slope_rad)

    # Aspect: compass bearing (deg clockwise from north) the slope faces. GDAL convention:
    # aspect = 90 - atan2(dz_dy, -dz_dx), wrapped to [0, 360); a flat cell -> -1.
    aspect = np.mod(90.0 - np.degrees(np.arctan2(dz_dy, -dz_dx)), 360.0)
    aspect = np.where(grad == 0.0, -1.0, aspect)

    # Standard Lambertian hillshade (GDAL formula), clamped to 0-255.
    zenith_rad = math.radians(90.0 - sun_altitude_deg)
    azimuth_rad = math.radians(360.0 - sun_azimuth_deg + 90.0)
    aspect_rad = np.arctan2(dz_dy, -dz_dx)
    shaded = math.cos(zenith_rad) * np.cos(slope_rad) + math.sin(zenith_rad) * np.sin(
        slope_rad
    ) * np.cos(azimuth_rad - aspect_rad)
    hillshade = np.clip(255.0 * shaded, 0.0, 255.0)

    return {
        "slope": slope_deg.astype("float32"),
        "aspect": aspect.astype("float32"),
        "hillshade": hillshade.astype("float32"),
    }


def load_dem(path: str | Path, bbox: BBox | None = None) -> Tuple[np.ndarray, BBox]:
    """Load a local DEM GeoTIFF and (optionally) clip it to ``bbox``.

    NEVER fetches from the network — the DEM tile is a LOCAL config/arg path (mosaicing of
    remote tiles happens out of band; this ingester consumes an already-local file). When
    ``bbox`` is ``None`` the full raster extent is returned.

    Args:
        path: Local ``.tif`` DEM path.
        bbox: Optional ``(west, south, east, north)`` clip window in the DEM CRS.

    Returns:
        ``(elevation, bbox)`` — the (clipped) north-up elevation grid and its actual bbox.
    """
    rasterio = _require_rasterio()
    from rasterio.windows import from_bounds as window_from_bounds

    with rasterio.open(path) as src:
        if bbox is None:
            arr = src.read(1)
            b = src.bounds
            out_bbox: BBox = (b.left, b.bottom, b.right, b.top)
        else:
            west, south, east, north = bbox
            window = window_from_bounds(
                west, south, east, north, transform=src.transform
            )
            window = window.round_offsets().round_lengths()
            arr = src.read(1, window=window)
            win_transform = src.window_transform(window)
            nrows, ncols = arr.shape
            w, n = win_transform * (0, 0)
            e, s = win_transform * (ncols, nrows)
            out_bbox = (w, s, e, n)
    return np.asarray(arr, dtype="float32"), out_bbox


def derive_terrain_layers(
    elevation: np.ndarray,
    bbox: BBox,
    *,
    z_factor: float = 1.0,
    sun_azimuth_deg: float = DEFAULT_SUN_AZIMUTH_DEG,
    sun_altitude_deg: float = DEFAULT_SUN_ALTITUDE_DEG,
) -> Dict[str, np.ndarray]:
    """Return ``{elevation, slope, aspect, hillshade}`` grids for an elevation array.

    Pixel size is derived from ``bbox`` and the array shape (north-up). The returned
    ``elevation`` is the input unchanged (float32); the three derivatives come from
    :func:`slope_aspect_hillshade`.
    """
    elev = np.asarray(elevation, dtype="float32")
    nrows, ncols = elev.shape
    dx, dy = _pixel_size_deg(bbox, nrows, ncols)
    derived = slope_aspect_hillshade(
        elev,
        dx,
        dy,
        z_factor=z_factor,
        sun_azimuth_deg=sun_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg,
    )
    return {"elevation": elev, **derived}


def _terrain_provenance(
    source: str,
    bbox: BBox,
    *,
    sun_azimuth_deg: float,
    sun_altitude_deg: float,
    z_factor: float,
) -> Dict[str, Any]:
    """Build the shared provenance block for the four terrain layers."""
    src_label = DEM_SOURCES.get(source, source)
    west, south, east, north = bbox
    return {
        "source": src_label,
        "method": "horn_1981_3x3_slope_aspect_hillshade",
        "note": (
            "elevation clipped from a local DEM tile; slope(deg)/aspect(deg)/hillshade "
            "derived with Horn's 3x3 kernel (same math as gdaldem). Terrain input for "
            "the RIX diagnostic (#831) and slope-threshold siting mask (#833)."
        ),
        "clip_bbox": {"west": west, "south": south, "east": east, "north": north},
        "sun_azimuth_deg": sun_azimuth_deg,
        "sun_altitude_deg": sun_altitude_deg,
        "z_factor": z_factor,
    }


def run_dem_ingest(dem_cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Ingest a local DEM and write elevation/slope/aspect/hillshade GeoTIFFs + manifest.

    Config-first (ARCH-01 / CESSPIT — no silent defaults for the load-bearing fields):

    Required config keys:
        ``dem_path``: local DEM GeoTIFF.
        ``out_dir``: directory for the four output GeoTIFFs.
        ``manifest_path``: ``DataLake_Manifest_All.json`` path.

    Optional config keys (documented defaults):
        ``bbox``: ``[west, south, east, north]`` clip window (default: full DEM extent).
        ``source``: ``"glo30"`` (default) or ``"srtm"`` — provenance label only.
        ``sun_azimuth_deg`` / ``sun_altitude_deg``: hillshade sun geometry.
        ``z_factor``: elevation scaling before the gradient (default 1.0).
        ``crs``: output CRS (default EPSG:4326).
        ``prefix``: output filename prefix (default ``"dutchbay_dem"``).
        ``dataset_name``: manifest dataset name (default ``"DutchBay/GIS/terrain"``).

    Returns:
        Summary: ``{bbox, resolution_deg, source, variables, files, manifest_path}``.
        Add-only + not wired into the finance pipeline, so KPI-neutral.
    """
    dem_path = dem_cfg["dem_path"]
    out_dir = Path(dem_cfg["out_dir"])
    manifest_path = dem_cfg["manifest_path"]

    source = str(dem_cfg.get("source", DEFAULT_DEM_SOURCE))
    crs = str(dem_cfg.get("crs", DEFAULT_CRS))
    prefix = str(dem_cfg.get("prefix", "dutchbay_dem"))
    dataset_name = str(dem_cfg.get("dataset_name", "DutchBay/GIS/terrain"))
    sun_azimuth_deg = float(dem_cfg.get("sun_azimuth_deg", DEFAULT_SUN_AZIMUTH_DEG))
    sun_altitude_deg = float(dem_cfg.get("sun_altitude_deg", DEFAULT_SUN_ALTITUDE_DEG))
    z_factor = float(dem_cfg.get("z_factor", 1.0))

    raw_bbox = dem_cfg.get("bbox")
    clip_bbox: BBox | None = (
        (
            float(raw_bbox[0]),
            float(raw_bbox[1]),
            float(raw_bbox[2]),
            float(raw_bbox[3]),
        )
        if raw_bbox is not None
        else None
    )

    elevation, bbox = load_dem(dem_path, clip_bbox)
    grids = derive_terrain_layers(
        elevation,
        bbox,
        z_factor=z_factor,
        sun_azimuth_deg=sun_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg,
    )

    provenance = _terrain_provenance(
        source,
        bbox,
        sun_azimuth_deg=sun_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg,
        z_factor=z_factor,
    )

    nrows, ncols = elevation.shape
    dx, _dy = _pixel_size_deg(bbox, nrows, ncols)

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}
    for var in TERRAIN_VARIABLES:
        tif = out_dir / f"{prefix}_{var}.tif"
        var_prov = {**provenance, "variable": var}
        write_geotiff(grids[var], bbox, tif, crs=crs, provenance=var_prov)
        paths[var] = str(tif)

    entry = build_manifest_entry(
        name=dataset_name,
        bbox=bbox,
        resolution_deg=dx,
        variables=TERRAIN_VARIABLES,
        paths=paths,
        provenance=provenance,
        crs=crs,
    )
    manifest = append_manifest(manifest_path, [entry])

    logger.info(
        "DEM ingest: wrote %d terrain layers to %s (source=%s, manifest %s)",
        len(TERRAIN_VARIABLES),
        out_dir,
        provenance["source"],
        manifest,
    )
    return {
        "bbox": list(bbox),
        "resolution_deg": dx,
        "source": provenance["source"],
        "variables": list(TERRAIN_VARIABLES),
        "files": paths,
        "manifest_path": str(manifest),
    }


def main() -> None:  # pragma: no cover - config-driven CLI (no argparse)
    """Config-driven entry point. Reads a DEM ingest YAML and runs the local ingest."""
    import json
    import os

    from omegaconf import OmegaConf

    cfg_path = os.environ.get(
        "DEM_INGEST_CONFIG", "wind_resource/config/dem_ingest.yaml"
    )
    full = OmegaConf.to_container(OmegaConf.load(cfg_path), resolve=True)
    assert isinstance(full, dict)
    dem_cfg = full.get("dem", full)
    summary = run_dem_ingest(dem_cfg)
    print(json.dumps(summary, indent=2, default=str))


__all__: List[str] = [
    "DEM_SOURCES",
    "TERRAIN_VARIABLES",
    "derive_terrain_layers",
    "load_dem",
    "run_dem_ingest",
    "slope_aspect_hillshade",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
