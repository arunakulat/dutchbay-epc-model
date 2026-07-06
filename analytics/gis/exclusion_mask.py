"""Constraint/exclusion mask -> buildable-area raster for wind siting (issue #833, epic #827).

Build a Boolean **BUILDABLE-AREA** mask (``True`` == a turbine may be sited on the cell)
from three config-first constraint families and rasterise it to a provenance-stamped
Boolean GeoTIFF plus a ``DataLake_Manifest_All.json`` entry (reusing the #20 exporter
helpers):

1. **Setback buffers** — dwellings, roads, grid lines, or any point/line feature class,
   each buffered by its own per-class setback distance (``shapely.buffer``). The union of
   all buffers is a "no-build" zone (noise/safety/wayleave standoff).
2. **Protected-area / wetland polygons** — hard exclusion areas taken verbatim (Ramsar
   wetlands, sanctuaries, forest reserves — a Kalpitiya-relevant concern). No buffer; the
   polygon itself is excluded.
3. **Slope threshold** — cells whose terrain slope exceeds ``slope_max`` degrees are
   excluded, from the #829 DEM slope layer (array or GeoTIFF). Buildable requires
   ``slope <= slope_max``.

The exclusions are **unioned** into a single no-build mask; the buildable mask is its
logical complement (``True`` == buildable). An optional boundary polygon further clips the
buildable area to the lease/site boundary (cells outside the boundary are not buildable).

CASPER: ``rasterio`` and ``shapely`` are optional ``[gis]`` dependencies, guarded at call
time via :func:`analytics.gis.geotiff_export._require_rasterio` and
:func:`_require_shapely` (so the base finance install never needs the GIS toolchain).
CCCDIR / config-first (ARCH-01, CESSPIT): every distance, threshold, geometry, output
path, CRS and extent is arg/config-supplied — nothing about a particular site is hardcoded
here except the EPSG:4326 default the GIS stack already standardises on. KPI-neutral: a
pure GIS siting layer, not wired into the finance pipeline.

The optional boundary clip is the in-memory-grid analogue of
:func:`analytics.gis.boundary_clip.clip_to_polygon` (#825, which clips a raster *file*); it
is kept self-contained here so this module does not hard-depend on #825 having merged.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

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

#: The single Boolean layer this module produces. Kept as a one-tuple so the manifest
#: exporter (which is variable-oriented) stays uniform with the other GIS datasets.
MASK_VARIABLE = "buildable"
MASK_VARIABLES: Tuple[str, ...] = (MASK_VARIABLE,)

#: GeoJSON-like geometry: a mapping with ``type``/``coordinates`` (or a Feature /
#: FeatureCollection wrapping one), or a bare coordinate sequence. Point features are
#: ``[lon, lat]``; line features are ``[[lon, lat], ...]``; polygons are
#: ``[[[lon, lat], ...]]`` rings.
GeometryLike = Any


def _require_shapely() -> Any:
    """Return the ``shapely`` module or raise an actionable CASPER error if absent."""
    try:
        import shapely  # noqa: F401

        return shapely
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The exclusion mask requires the [gis] extra (shapely): "
            "pip install 'shapely>=2.0'  (or  pip install -e '.[gis]')."
        ) from exc


def _to_shapely_geometry(geom: GeometryLike) -> Any:
    """Coerce a GeoJSON mapping OR a bare coordinate sequence to a shapely geometry.

    Accepts:
      * a shapely geometry (returned unchanged),
      * a GeoJSON mapping (``Point``/``LineString``/``Polygon``/``MultiPolygon``/… or a
        ``Feature`` wrapping one) — via ``shapely.geometry.shape``,
      * a bare point ``[lon, lat]``, line ``[[lon, lat], ...]`` or polygon ring
        ``[[[lon, lat], ...]]`` coordinate sequence — the shape is inferred from nesting
        depth.

    CESSPIT / fail-loud: an unrecognised structure raises rather than silently producing an
    empty geometry that would look like "nothing excluded".
    """
    _require_shapely()
    from shapely.geometry import LineString, Point, Polygon
    from shapely.geometry import shape as shp_shape
    from shapely.geometry.base import BaseGeometry

    if isinstance(geom, BaseGeometry):
        return geom

    if isinstance(geom, Mapping):
        gtype = geom.get("type")
        if gtype == "Feature":
            inner = geom.get("geometry")
            if inner is None:
                raise ValueError("Feature has no geometry")
            return _to_shapely_geometry(inner)
        return shp_shape(geom)

    if isinstance(geom, Sequence) and not isinstance(geom, (str, bytes)):
        seq = list(geom)
        if not seq:
            raise ValueError("empty coordinate sequence")
        depth = _nesting_depth(seq)
        if depth == 1:  # [lon, lat]
            return Point(float(seq[0]), float(seq[1]))
        if depth == 2:  # [[lon, lat], ...]
            return LineString([(float(x), float(y)) for x, y in seq])
        if depth == 3:  # [[[lon, lat], ...]] ring(s)
            return Polygon(seq[0], holes=seq[1:] if len(seq) > 1 else None)
        raise ValueError(f"unsupported coordinate nesting depth {depth}")

    raise TypeError(f"unsupported geometry type: {type(geom)!r}")


def _nesting_depth(seq: Any) -> int:
    """Depth of the leftmost list nesting (``[lon,lat]``->1, ring->2, polygon->3)."""
    depth = 0
    node: Any = seq
    while isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
        depth += 1
        if not node:
            break
        node = node[0]
    return depth


def build_setback_zone(
    features: Sequence[GeometryLike],
    setback_distance: float,
) -> Any:
    """Union of ``features`` each buffered by ``setback_distance`` (a no-build zone).

    Args:
        features: point/line (or polygon) geometries for one class (e.g. dwellings).
        setback_distance: buffer radius in the geometry's CRS units (e.g. degrees for
            EPSG:4326, or metres for a projected CRS). A ``0`` buffer keeps the bare
            geometry (only exact cells touched).

    Returns:
        A single shapely geometry (the unary union of the buffered features). An empty
        ``features`` list yields an empty geometry (excludes nothing) — the caller decides
        whether an empty class is legitimate.
    """
    _require_shapely()
    from shapely.geometry import GeometryCollection
    from shapely.ops import unary_union

    if not features:
        return GeometryCollection()
    buffered = [
        _to_shapely_geometry(f).buffer(float(setback_distance)) for f in features
    ]
    return unary_union(buffered)


def build_exclusion_geometry(
    setbacks: Mapping[str, Mapping[str, Any]] | None = None,
    protected_areas: Sequence[GeometryLike] | None = None,
) -> Any:
    """Union every setback buffer and protected-area polygon into one no-build geometry.

    Args:
        setbacks: ``{class_name: {"features": [...], "distance": d}}`` — each feature class
            buffered by its own ``distance`` (see :func:`build_setback_zone`).
        protected_areas: exclusion polygons taken verbatim (no buffer) — wetlands,
            sanctuaries, forest reserves, etc.

    Returns:
        A single shapely geometry: the union of all setback zones and protected areas. When
        both inputs are empty the result is an empty geometry (nothing vector-excluded);
        the slope mask is applied separately in :func:`build_buildable_mask`.
    """
    _require_shapely()
    from shapely.geometry import GeometryCollection
    from shapely.ops import unary_union

    pieces: List[Any] = []
    for cls_name, spec in (setbacks or {}).items():
        feats = spec.get("features", [])
        dist = float(spec.get("distance", 0.0))
        zone = build_setback_zone(feats, dist)
        if not zone.is_empty:
            pieces.append(zone)
        logger.debug(
            "setback class %s: %d features buffered by %s", cls_name, len(feats), dist
        )
    for poly in protected_areas or []:
        geom = _to_shapely_geometry(poly)
        if not geom.is_empty:
            pieces.append(geom)

    if not pieces:
        return GeometryCollection()
    return unary_union(pieces)


def _load_slope_array(slope: np.ndarray | str | Path) -> np.ndarray:
    """Return a 2-D slope-degree array from an array or a GeoTIFF path (#829 output)."""
    if isinstance(slope, (str, Path)):
        rasterio = _require_rasterio()
        with rasterio.open(slope) as src:
            arr = src.read(1)
        return np.asarray(arr, dtype="float64")
    arr = np.asarray(slope, dtype="float64")
    if arr.ndim != 2:
        raise ValueError(f"expected a 2-D slope grid, got shape {arr.shape}")
    return arr


def _rasterize_geometry(
    geometry: Any,
    bbox: BBox,
    shape: Tuple[int, int],
    all_touched: bool = True,
) -> np.ndarray:
    """Rasterise ``geometry`` onto a north-up grid; ``True`` where the geometry covers a cell.

    ``all_touched=True`` (the default) marks every cell the geometry touches — the
    conservative posture for a *no-build* zone (a partially-covered cell is excluded).
    """
    _require_shapely()
    _require_rasterio()
    from rasterio.features import rasterize
    from rasterio.transform import from_bounds
    from shapely.geometry import mapping

    nrows, ncols = shape
    if geometry.is_empty:
        return np.zeros(shape, dtype=bool)
    west, south, east, north = bbox
    transform = from_bounds(west, south, east, north, ncols, nrows)
    burned = rasterize(
        [(mapping(geometry), 1)],
        out_shape=shape,
        transform=transform,
        fill=0,
        all_touched=all_touched,
        dtype="uint8",
    )
    return np.asarray(burned, dtype=bool)


def build_buildable_mask(
    slope: np.ndarray | str | Path,
    bbox: BBox,
    *,
    slope_max: float,
    setbacks: Mapping[str, Mapping[str, Any]] | None = None,
    protected_areas: Sequence[GeometryLike] | None = None,
    boundary: GeometryLike | None = None,
    all_touched: bool = True,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Compute the Boolean buildable-area mask over the slope grid's extent.

    A cell is **buildable** (``True``) iff ALL hold:
      * its slope ``<= slope_max`` degrees,
      * it lies OUTSIDE every setback buffer and protected-area polygon, and
      * (if ``boundary`` is given) it lies INSIDE the boundary polygon.

    Args:
        slope: 2-D slope-degree array or a slope GeoTIFF path (#829 output). Its shape and
            ``bbox`` define the mask grid.
        bbox: ``(west, south, east, north)`` for the slope grid, in ``slope``'s CRS.
        slope_max: maximum buildable slope in degrees (config-supplied; no default).
        setbacks / protected_areas: see :func:`build_exclusion_geometry`.
        boundary: optional lease/site boundary polygon; cells outside it are not buildable.
        all_touched: rasterisation inclusion rule for the *exclusion* zones — ``True``
            (default) excludes any cell a no-build geometry touches (conservative).

    Returns:
        ``(mask, diagnostics)`` — ``mask`` is a Boolean array (``True`` == buildable) the
        same shape as the slope grid; ``diagnostics`` records per-constraint excluded-cell
        counts and the resulting buildable fraction for provenance/audit.
    """
    slope_arr = _load_slope_array(slope)
    shape = slope_arr.shape

    # 1. Slope constraint: buildable where slope <= slope_max (NaN slope -> not buildable).
    steep = ~(slope_arr <= float(slope_max))  # True where excluded (incl. NaN)

    # 2 & 3. Vector exclusions (setbacks + protected areas) rasterised to the grid.
    exclusion_geom = build_exclusion_geometry(
        setbacks=setbacks, protected_areas=protected_areas
    )
    vector_excluded = _rasterize_geometry(
        exclusion_geom, bbox, shape, all_touched=all_touched
    )

    no_build = steep | vector_excluded
    buildable = ~no_build

    # 4. Optional boundary clip: keep only cells inside the boundary polygon.
    boundary_applied = False
    if boundary is not None:
        inside = _boundary_inside_mask(boundary, bbox, shape)
        buildable = buildable & inside
        boundary_applied = True

    total = int(buildable.size)
    diagnostics: Dict[str, Any] = {
        "slope_max_deg": float(slope_max),
        "cells_total": total,
        "cells_excluded_steep": int(steep.sum()),
        "cells_excluded_vector": int(vector_excluded.sum()),
        "cells_buildable": int(buildable.sum()),
        "buildable_fraction": (float(buildable.sum()) / total) if total else 0.0,
        "boundary_clip_applied": boundary_applied,
        "all_touched": bool(all_touched),
        "setback_classes": sorted((setbacks or {}).keys()),
        "protected_area_count": len(protected_areas or []),
    }
    return buildable, diagnostics


def _boundary_inside_mask(
    boundary: GeometryLike, bbox: BBox, shape: Tuple[int, int]
) -> np.ndarray:
    """Boolean mask, ``True`` where a cell lies INSIDE the boundary polygon.

    The sibling :func:`analytics.gis.boundary_clip.clip_to_polygon` (issue #825) performs
    the equivalent clip on a raster *file* (out-of-polygon cells -> nodata); this in-memory
    grid analogue rasterises the boundary directly with ``all_touched=False``, so a boundary
    cell must have its centre inside to count as in-bounds — the standard "keep interior"
    clip semantics. Kept self-contained here so the mask does not hard-depend on #825 having
    merged; a downstream caller that already has a #825-clipped raster can skip ``boundary``.
    """
    geom = _to_shapely_geometry(boundary)
    return _rasterize_geometry(geom, bbox, shape, all_touched=False)


def _mask_provenance(
    bbox: BBox,
    diagnostics: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build the provenance block stamped on the buildable GeoTIFF + manifest entry."""
    west, south, east, north = bbox
    return {
        "layer": "buildable_area_mask",
        "method": "union(setback_buffers, protected_areas, slope>slope_max) -> complement",
        "note": (
            "Boolean buildable-area siting mask (issue #833): True == a turbine may be "
            "sited on the cell. Exclusions = per-class setback buffers (shapely.buffer) "
            "UNION protected-area/wetland polygons UNION cells with slope > slope_max "
            "(from the #829 DEM slope layer); buildable is the complement, optionally "
            "clipped to a site boundary. KPI-neutral GIS layer, not wired into finance."
        ),
        "slope_source": "analytics.gis.dem_ingest slope layer (#829)",
        "clip_bbox": {"west": west, "south": south, "east": east, "north": north},
        **{k: diagnostics[k] for k in diagnostics},
    }


def run_exclusion_mask(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the buildable-area mask and write a Boolean GeoTIFF + prov sidecar + manifest.

    Config-first (ARCH-01 / CESSPIT — no silent defaults for the load-bearing fields):

    Required config keys:
        ``slope_path`` OR ``slope_array``: the #829 slope-degree GeoTIFF path (or a 2-D
            array, mainly for tests).
        ``bbox``: ``[west, south, east, north]`` of the slope grid.
        ``slope_max``: maximum buildable slope in degrees.
        ``out_path``: output ``.tif`` path for the Boolean mask.
        ``manifest_path``: ``DataLake_Manifest_All.json`` path.

    Optional config keys (documented defaults):
        ``setbacks``: ``{class: {"features": [...], "distance": d}}`` setback buffers.
        ``protected_areas``: list of exclusion polygons (no buffer).
        ``boundary``: optional site-boundary polygon to clip the buildable area to.
        ``all_touched``: exclusion rasterisation rule (default ``True`` — conservative).
        ``crs``: output CRS (default EPSG:4326).
        ``dataset_name``: manifest dataset name (default ``"DutchBay/GIS/buildable"``).

    Returns:
        Summary: ``{bbox, resolution_deg, slope_max_deg, buildable_fraction, file,
        manifest_path, diagnostics}``. Add-only + not wired into finance -> KPI-neutral.
    """
    if "slope_path" in cfg:
        slope: np.ndarray | str | Path = str(cfg["slope_path"])
    elif "slope_array" in cfg:
        slope = np.asarray(cfg["slope_array"], dtype="float64")
    else:
        raise KeyError("exclusion mask config needs 'slope_path' or 'slope_array'")

    raw_bbox = cfg["bbox"]
    bbox: BBox = (
        float(raw_bbox[0]),
        float(raw_bbox[1]),
        float(raw_bbox[2]),
        float(raw_bbox[3]),
    )
    slope_max = float(cfg["slope_max"])
    out_path = Path(cfg["out_path"])
    manifest_path = cfg["manifest_path"]

    crs = str(cfg.get("crs", DEFAULT_CRS))
    dataset_name = str(cfg.get("dataset_name", "DutchBay/GIS/buildable"))
    all_touched = bool(cfg.get("all_touched", True))
    setbacks = cfg.get("setbacks")
    protected_areas = cfg.get("protected_areas")
    boundary = cfg.get("boundary")

    mask, diagnostics = build_buildable_mask(
        slope,
        bbox,
        slope_max=slope_max,
        setbacks=setbacks,
        protected_areas=protected_areas,
        boundary=boundary,
        all_touched=all_touched,
    )

    provenance = _mask_provenance(bbox, diagnostics)

    # Write the Boolean mask as a float32 GeoTIFF (0.0/1.0) — the #20 exporter's dtype, so
    # the layer round-trips through the same manifest/QGIS stack as every other GIS field.
    write_geotiff(
        mask.astype("float32"), bbox, out_path, crs=crs, provenance=provenance
    )

    nrows, ncols = mask.shape
    dx = (bbox[2] - bbox[0]) / float(ncols)

    entry = build_manifest_entry(
        name=dataset_name,
        bbox=bbox,
        resolution_deg=dx,
        variables=MASK_VARIABLES,
        paths={MASK_VARIABLE: str(out_path)},
        provenance=provenance,
        crs=crs,
    )
    manifest = append_manifest(manifest_path, [entry])

    logger.info(
        "exclusion mask: %d/%d cells buildable (%.1f%%) -> %s (manifest %s)",
        diagnostics["cells_buildable"],
        diagnostics["cells_total"],
        100.0 * diagnostics["buildable_fraction"],
        out_path,
        manifest,
    )
    return {
        "bbox": list(bbox),
        "resolution_deg": dx,
        "slope_max_deg": slope_max,
        "buildable_fraction": diagnostics["buildable_fraction"],
        "file": str(out_path),
        "manifest_path": str(manifest),
        "diagnostics": diagnostics,
    }


def main() -> None:  # pragma: no cover - config-driven CLI (no argparse)
    """Config-driven entry point. Reads an exclusion-mask YAML and builds the mask."""
    import json
    import os

    from omegaconf import OmegaConf

    cfg_path = os.environ.get(
        "EXCLUSION_MASK_CONFIG", "wind_resource/config/exclusion_mask.yaml"
    )
    full = OmegaConf.to_container(OmegaConf.load(cfg_path), resolve=True)
    assert isinstance(full, dict)
    mask_cfg = full.get("exclusion_mask", full)
    summary = run_exclusion_mask(mask_cfg)
    print(json.dumps(summary, indent=2, default=str))


__all__: List[str] = [
    "MASK_VARIABLE",
    "MASK_VARIABLES",
    "build_buildable_mask",
    "build_exclusion_geometry",
    "build_setback_zone",
    "run_exclusion_mask",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
