"""Clip wind/AEP rasters to a project-boundary polygon (issue #825, revives #21).

Issue #21 ("Sprint 10 - Add Dutch Bay project polygon and clip wind/AEP") was closed
2025-12-23 as completed but was **never implemented** (a false-green closure): the #20 /
PR #204 GeoTIFF exporter writes only full-grid rasters, and no ``clip_to_polygon`` or
project-boundary geometry ever existed. This module supplies both halves:

* :func:`clip_to_polygon` masks a single-band GeoTIFF to a polygon via
  :func:`rasterio.mask.mask`, writing a clipped GeoTIFF (out-of-polygon cells set to the
  raster's nodata), a ``<path>.prov.json`` sidecar and (optionally) a
  ``DataLake_Manifest_All.json`` entry -- reusing the existing #20 helpers in
  :mod:`analytics.gis.geotiff_export`.
* :func:`clipped_domain_stats` computes an in-polygon, area-weighted stats block
  (mean / min / max / valid cell count) over the surviving cells.

KPI-NEUTRAL: this is an add-only GIS/reporting layer. The clipped rasters and stats feed
QGIS / lender reporting only; no finance, AEP or energy calculation reads them, so the
committed KPI oracle is unchanged.

CASPER: ``rasterio`` (and the ``shapely`` geometry it wraps) is an optional ``[gis]``
dependency, guarded at call time via
:func:`analytics.gis.geotiff_export._require_rasterio` -- exactly like the exporter, so
the base install never needs GDAL. CCCDIR / config-first: raster paths, the polygon and
output paths are all argument/config supplied; nothing site-specific is hardcoded here.
"""

from __future__ import annotations

import json
import numbers
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

import numpy as np

from analytics.gis.geotiff_export import (
    DEFAULT_CRS,
    BBox,
    _require_rasterio,
    append_manifest,
    build_manifest_entry,
)

#: A GeoJSON-like polygon: either a mapping with ``type``/``coordinates`` (a Polygon or
#: MultiPolygon geometry, or a Feature / FeatureCollection wrapping one) or the bare ring
#: coordinate list ``[[[lon, lat], ...]]``.
PolygonLike = Union[Mapping[str, Any], Sequence[Any]]


def _check_coordinate_tree(node: Any) -> None:
    """Recursively assert ``node`` is a nested list bottoming out in numeric positions.

    Descends the GeoJSON coordinate nesting (MultiPolygon -> polygon -> ring -> position)
    and raises ``ValueError`` on any mapping, string or bare scalar found where a numeric
    position (or a list of them) is expected. This is the pre-flight guard that keeps a
    malformed geometry out of rasterio's Cython bounds walk (see :func:`_validate_geometry`).
    """
    if isinstance(node, (str, bytes, Mapping)):
        raise ValueError(
            f"malformed geometry coordinates: found a {type(node).__name__} where a "
            "numeric position or a list of positions was expected"
        )
    if not isinstance(node, Sequence):
        raise ValueError(
            f"malformed geometry coordinates: found a non-sequence {node!r}"
        )
    if len(node) == 0:
        raise ValueError("malformed geometry coordinates: empty coordinate list")
    # A position leaf is a sequence of real numbers: (lon, lat) or (lon, lat, z).
    if all(isinstance(x, numbers.Real) and not isinstance(x, bool) for x in node):
        if len(node) < 2:
            raise ValueError(
                f"malformed geometry coordinates: position {list(node)!r} has fewer "
                "than two ordinates"
            )
        return
    # Otherwise a nesting level (polygons / rings): recurse into each child.
    for child in node:
        _check_coordinate_tree(child)


def _validate_geometry(geom: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a concrete Polygon/MultiPolygon geometry's coordinate tree, then return it.

    rasterio feeds GeoJSON ``coordinates`` straight to a Cython bounds walk
    (``rasterio.features._bounds``) that dereferences each leaf as a C double. A stray
    mapping or string among the coordinates -- e.g. an already-extracted geometry that was
    accidentally double-wrapped into ``coordinates: [ {geom} ]`` -- is read as a raw
    pointer and SEGFAULTS the interpreter (exit 139): an uncatchable, whole-process crash
    at ``mask() -> raster_geometry_mask -> geometry_window -> bounds``. Validating the
    structure in pure Python first converts that hard crash into a loud, catchable
    ``ValueError`` (CESSPIT fail-loud), so no malformed geometry ever reaches the C
    extension.
    """
    _check_coordinate_tree(geom.get("coordinates"))
    return geom


def _extract_geometries(polygon: PolygonLike) -> List[Dict[str, Any]]:
    """Normalise ``polygon`` to a list of GeoJSON Polygon/MultiPolygon geometry mappings.

    Accepts a bare ring coordinate list, a Polygon/MultiPolygon geometry, a single
    ``Feature``, a ``FeatureCollection``, or an already-extracted *list* of any of these
    (e.g. the return value of :func:`load_polygon`). Raising loudly on an empty /
    unrecognised input is a CESSPIT posture: a clip against no geometry is a config error,
    not a silent no-op that would look like "everything masked".

    The function is idempotent -- ``_extract_geometries(_extract_geometries(x))`` equals
    ``_extract_geometries(x)`` -- and that property is load-bearing: :func:`clip_to_polygon`
    re-extracts whatever it is handed, so feeding it the already-extracted output of
    :func:`load_polygon` must NOT double-wrap the geometry list into a
    ``{"type": "Polygon", "coordinates": [ {geom} ]}`` mapping. That double-wrap is a
    malformed geometry that SEGFAULTS GDAL's coordinate-bounds walk (the bug this guards).
    """
    # A non-string, non-mapping Sequence is either an already-extracted list of
    # geometry/feature mappings (idempotent re-extraction) or a bare ring coordinate list.
    if isinstance(polygon, Sequence) and not isinstance(polygon, (str, bytes, Mapping)):
        items = list(polygon)
        if items and all(isinstance(item, Mapping) for item in items):
            # A list of geometry/feature mappings -> re-extract each. This is what makes
            # clip_to_polygon(load_polygon(...)) safe: the loaded geometries are
            # re-normalised, not wrapped as a bare ring into a malformed polygon.
            nested: List[Dict[str, Any]] = []
            for item in items:
                nested.extend(_extract_geometries(item))
            return nested
        # A bare ring coordinate list -> wrap as a Polygon geometry.
        return [_validate_geometry({"type": "Polygon", "coordinates": items})]

    if not isinstance(polygon, Mapping):
        raise TypeError(f"unsupported polygon type: {type(polygon)!r}")

    gtype = polygon.get("type")
    if gtype == "FeatureCollection":
        geoms: List[Dict[str, Any]] = []
        for feat in polygon.get("features", []):
            geoms.extend(_extract_geometries(feat))
        if not geoms:
            raise ValueError("FeatureCollection carries no features to clip against")
        return geoms
    if gtype == "Feature":
        geom = polygon.get("geometry")
        if geom is None:
            raise ValueError("Feature has no geometry to clip against")
        return _extract_geometries(geom)
    if gtype in ("Polygon", "MultiPolygon"):
        return [_validate_geometry(dict(polygon))]

    raise ValueError(
        f"unsupported GeoJSON type {gtype!r}; expected Polygon/MultiPolygon/Feature/"
        "FeatureCollection or a bare ring coordinate list"
    )


def load_polygon(path: str | Path) -> List[Dict[str, Any]]:
    """Load a GeoJSON file and return its clip geometries (see :func:`_extract_geometries`)."""
    doc = json.loads(Path(path).read_text())
    return _extract_geometries(doc)


def clipped_domain_stats(
    values: np.ndarray, nodata: float
) -> Dict[str, Optional[float]]:
    """Plain (unweighted) in-polygon stats over the surviving (non-nodata) cells.

    This standalone helper is raster-only and bbox-free, so the returned ``mean`` is the
    *plain cell mean* of the surviving cells (each cell counts equally). The area-weighting
    step lives in :func:`clip_to_polygon`, which knows the clipped bbox and OVERWRITES this
    ``mean`` with a ``cos(latitude)`` area-weighted value -- a first-order equal-area
    correction (on a north-up EPSG:4326 grid a degree of longitude subtends less ground
    toward the poles). ``min``/``max``/``count`` are unaffected by weighting and are the
    same here and in the summary.

    Args:
        values: 2-D clipped raster (out-of-polygon cells already set to ``nodata``).
        nodata: The nodata sentinel (``NaN`` or a finite value) marking masked-out cells.

    Returns:
        ``{"mean", "min", "max", "count"}``. ``count`` is the number of valid in-polygon
        cells; ``mean``/``min``/``max`` are ``None`` when nothing survives the clip (an
        empty intersection is disclosed, not reported as ``0.0``).
    """
    arr = np.asarray(values, dtype="float64")
    if arr.ndim != 2:
        raise ValueError(f"expected a 2-D array, got shape {arr.shape}")

    if np.isnan(nodata):
        valid = ~np.isnan(arr)
    else:
        valid = arr != nodata
    valid &= ~np.isnan(arr)

    count = int(valid.sum())
    if count == 0:
        return {"mean": None, "min": None, "max": None, "count": 0}

    # This helper stays raster-only and bbox-free, so ``mean`` here is the plain cell mean
    # of the surviving cells; :func:`clip_to_polygon` overwrites it with the cos(latitude)
    # area-weighted mean once the clipped bbox is known (keeping the label honest).
    vals = arr[valid]
    return {
        "mean": float(vals.mean()),
        "min": float(vals.min()),
        "max": float(vals.max()),
        "count": count,
    }


def _area_weighted_mean(
    values: np.ndarray, valid: np.ndarray, bbox: BBox
) -> Optional[float]:
    """cos(latitude) area-weighted mean of ``values`` over ``valid`` cells for a geo bbox.

    Returns ``None`` when no cell is valid. For a projected (metres) CRS the caller passes
    a bbox whose latitudes are large map coordinates; guard against a degenerate weight by
    falling back to a plain mean if the cosine weights collapse.
    """
    nrows, ncols = values.shape
    _, south, _, north = bbox
    # Row-centre latitudes, north-up (row 0 == north edge).
    row_edges = np.linspace(north, south, nrows + 1)
    row_centres = 0.5 * (row_edges[:-1] + row_edges[1:])
    weights_1d = np.cos(np.deg2rad(np.clip(row_centres, -89.9999, 89.9999)))
    weights = np.broadcast_to(weights_1d[:, None], values.shape)

    w = weights[valid]
    v = values[valid]
    wsum = float(w.sum())
    if not np.isfinite(wsum) or wsum <= 0:
        return float(v.mean()) if v.size else None
    return float((w * v).sum() / wsum)


def clip_to_polygon(
    raster_path: str | Path,
    polygon: PolygonLike,
    out_path: str | Path,
    crs: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
    manifest_name: str = "DutchBay/GIS/clipped",
    variable: str = "value",
    provenance: Optional[Mapping[str, Any]] = None,
    all_touched: bool = False,
) -> Dict[str, Any]:
    """Clip a single-band GeoTIFF to ``polygon`` and export the clipped raster + stats.

    Out-of-polygon cells are set to the source raster's nodata (or ``NaN`` if it declares
    none). The clipped GeoTIFF is written with a north-up affine over the *clipped* window,
    a ``<out_path>.prov.json`` sidecar and, when ``manifest_path`` is given, a
    ``DataLake_Manifest_All.json`` entry -- all via the #20 helpers.

    Args:
        raster_path: LOCAL path to a single-band GeoTIFF (e.g. a #20 WS150/CF/AEP export).
            No network; a fetch step is a separate concern.
        polygon: The clip geometry -- a GeoJSON Polygon/MultiPolygon/Feature/
            FeatureCollection mapping, or a bare ring coordinate list. Its coordinates MUST
            already be in the raster's CRS (both EPSG:4326 in the DutchBay pipeline). This
            is a documented contract, not a detected one: a bare ring carries no CRS and
            GeoJSON per RFC 7946 is WGS84, so a polygon in a different CRS cannot be
            distinguished here -- reproject the geometry to the raster CRS before calling
            (e.g. ``rasterio.warp.transform_geom``).
        out_path: Output ``.tif`` path for the clipped raster.
        crs: Optional CRS *label* for the output; defaults to the input raster's CRS (or
            :data:`analytics.gis.geotiff_export.DEFAULT_CRS`). This is a label, NOT a
            reprojection: the clip runs in the raster's native CRS, so a ``crs`` that
            disagrees with the source raster's CRS would mislabel the output GeoTIFF
            (tag claiming one CRS over a transform still in another). To avoid that
            footgun, a disagreeing ``crs`` raises ``ValueError`` (CESSPIT — fail loud, no
            silent mislabel). Reproject the raster first if you need a different CRS.
        manifest_path: If given, append/refresh a manifest entry.
        manifest_name: Dataset name used in the manifest entry.
        variable: Variable label for the clipped band (e.g. ``"ws150"``/``"aep"``), used in
            the manifest ``variables`` list and file map.
        provenance: Optional extra provenance key/values merged into the sidecar/tags.
        all_touched: rasterio ``mask`` semantics -- when ``True``, every cell the polygon
            *touches* is kept; when ``False`` (default) only cells whose centre falls inside
            are kept. Recorded in provenance so the pixel-inclusion rule is auditable.

    Returns:
        Summary dict: ``clipped_path``, ``bbox`` (of the clipped window), ``crs``,
        ``variable``, ``nodata``, a ``stats`` block (see :func:`clipped_domain_stats`;
        ``mean`` is the cos-latitude area-weighted mean) and (if written) ``manifest_path``.

    Raises:
        ValueError: if the ``crs`` override disagrees with the source raster's CRS (this
            function labels, it does not reproject), or if the clip geometry does not
            overlap the raster.
    """
    rasterio = _require_rasterio()
    from rasterio.crs import CRS
    from rasterio.mask import mask as rio_mask

    geometries = _extract_geometries(polygon)

    src_path = Path(raster_path)
    with rasterio.open(src_path) as src:
        src_crs = src.crs.to_string() if src.crs is not None else DEFAULT_CRS
        # CESSPIT / fail-loud: `crs` is an output LABEL, not a reprojection. If the caller
        # passes a CRS that disagrees with the raster's actual CRS, refuse rather than write
        # a mislabeled GeoTIFF (tag says one CRS while the transform stays in another).
        if crs is not None and src.crs is not None:
            if CRS.from_string(str(crs)) != src.crs:
                raise ValueError(
                    f"crs override {crs!r} disagrees with the source raster CRS "
                    f"{src_crs!r}; clip_to_polygon labels but does not reproject. "
                    "Reproject the raster first (e.g. rasterio.warp) or drop the override."
                )
        src_nodata = src.nodata
        # crop=True trims the output to the polygon's bounding window; filled=True sets
        # out-of-polygon cells to nodata. NaN is the exporter's nodata convention.
        nodata = float(src_nodata) if src_nodata is not None else float("nan")
        clipped, clip_transform = rio_mask(
            src,
            geometries,
            crop=True,
            filled=True,
            nodata=nodata,
            all_touched=all_touched,
        )

    band = np.asarray(clipped[0], dtype="float32")
    nrows, ncols = band.shape

    # Derive the clipped-window bbox from the returned affine transform (north-up).
    west = clip_transform.c
    north = clip_transform.f
    east = west + clip_transform.a * ncols
    south = north + clip_transform.e * nrows  # transform.e is negative (north-up)
    bbox: BBox = (west, south, east, north)

    out_crs = str(crs) if crs is not None else src_crs

    # Valid = in-polygon, non-nodata cells.
    if np.isnan(nodata):
        valid = ~np.isnan(band.astype("float64"))
    else:
        valid = (band != nodata) & ~np.isnan(band.astype("float64"))

    stats = clipped_domain_stats(band, nodata)
    # Replace the plain-mean with the cos(latitude) area-weighted mean now that we know the
    # clipped bbox (keeps the "area-weighted" label honest).
    if stats["count"]:
        stats["mean"] = _area_weighted_mean(band.astype("float64"), valid, bbox)

    prov: Dict[str, Any] = {
        "method": "rasterio_mask_clip_to_polygon",
        "source_raster": str(src_path),
        "variable": variable,
        "polygon_geometry_count": len(geometries),
        "all_touched": all_touched,
        "nodata": "nan" if np.isnan(nodata) else nodata,
        "in_polygon_cell_count": stats["count"],
        "note": (
            "KPI-neutral boundary clip (issue #825, revives #21); clipped raster + stats "
            "feed QGIS/lender reporting only, not any AEP/energy/finance calc. The polygon "
            "CRS is assumed equal to the raster CRS."
        ),
    }
    if provenance:
        prov.update(dict(provenance))

    written = _write_clipped_geotiff(band, bbox, out_path, out_crs, nodata, prov)

    summary: Dict[str, Any] = {
        "clipped_path": str(written),
        "bbox": list(bbox),
        "crs": out_crs,
        "variable": variable,
        "nodata": "nan" if np.isnan(nodata) else nodata,
        "stats": stats,
    }

    if manifest_path is not None:
        resolution = (east - west) / ncols if ncols else 0.0
        entry = build_manifest_entry(
            name=manifest_name,
            bbox=bbox,
            resolution_deg=resolution,
            variables=(variable,),
            paths={variable: str(written)},
            provenance={**prov, "clipped_domain_stats": stats},
            crs=out_crs,
        )
        manifest = append_manifest(manifest_path, [entry])
        summary["manifest_path"] = str(manifest)

    return summary


def _write_clipped_geotiff(
    band: np.ndarray,
    bbox: BBox,
    out_path: str | Path,
    crs: str,
    nodata: float,
    provenance: Mapping[str, Any],
) -> Path:
    """Write the clipped single-band float32 GeoTIFF + ``.prov.json`` sidecar.

    Mirrors :func:`analytics.gis.geotiff_export.write_geotiff` but writes the caller's
    explicit ``nodata`` (which may be a finite source nodata, not only ``NaN``) so the
    masked cells round-trip faithfully.
    """
    rasterio = _require_rasterio()
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    arr = np.asarray(band, dtype="float32")
    nrows, ncols = arr.shape
    west, south, east, north = bbox
    transform = from_bounds(west, south, east, north, ncols, nrows)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out,
        "w",
        driver="GTiff",
        height=nrows,
        width=ncols,
        count=1,
        dtype="float32",
        crs=CRS.from_string(crs),
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)
        dst.update_tags(**{k: str(v) for k, v in provenance.items()})

    Path(f"{out}.prov.json").write_text(json.dumps(dict(provenance), indent=2))
    return out
