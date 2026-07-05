"""Ingest Global Wind Atlas 250 m GeoTIFFs as an external reference layer (issue #828).

The Global Wind Atlas (GWA, DTU) publishes ~250 m rasters (mean wind speed,
wind-power-density, ...) built from the numerical wind-atlas chain
(ERA5 -> WRF 3 km -> DTU generalization -> WAsP microscale). This module registers a
**locally supplied** GWA GeoTIFF as a *reference / visualization* raster layer in the
issue-#20 GIS export stack: it clips (and, if needed, reprojects) the raster to the
site bounding box, then writes a provenance-stamped GeoTIFF plus a ``DataLake`` manifest
entry via the existing :mod:`analytics.gis.geotiff_export` helpers.

KPI-NEUTRAL: this is an external reference layer only. It is deliberately NOT wired into
the AEP/finance path and is clearly distinguished (in every provenance block) from the
interpolated ERA5 "fine" grid, which is a bilinear downscale — not a measured or atlas
field. Wiring GWA into the AEP/KPI path is out of scope here and would need a separate,
oracle-gated dolphin.

CASPER: ``rasterio`` is an optional ``[gis]`` dependency, guarded at call time via
:func:`analytics.gis.geotiff_export._require_rasterio` (so the base install never needs
GDAL). CCCDIR / CESSPIT: the source path, bbox, output paths and CRS are all
config-supplied — nothing about the site geometry or files is hardcoded here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

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

#: Human-readable source stamp recorded in every ingested layer's provenance.
GWA_SOURCE = "Global Wind Atlas 250 m (DTU)"

#: GWA native resolution in metres (Davis et al., BAMS 2023).
GWA_RESOLUTION_M = 250.0

#: The unambiguous "this is a reference layer" note carried on every ingested raster,
#: so a downstream consumer (or a lender reading the manifest) can never mistake a GWA
#: layer for the interpolated ERA5 "fine" grid.
GWA_REFERENCE_NOTE = (
    "external high-res reference / visualization layer (Global Wind Atlas 250 m, DTU); "
    "NOT the interpolated ERA5 'fine' grid and NOT wired into the AEP/KPI path"
)


def gwa_provenance(
    variable: str,
    source_path: str | Path,
    extra: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the provenance block for one ingested GWA layer.

    The block records the DTU source, the native 250 m resolution and an explicit
    reference-layer note that distinguishes it from the ERA5 fine interpolation. Extra
    key/values (e.g. the GWA ``variable`` short name or download date) are merged in.
    """
    prov: Dict[str, Any] = {
        "method": "gwa_250m_reference_ingest",
        "source": GWA_SOURCE,
        "source_path": str(source_path),
        "resolution_m": GWA_RESOLUTION_M,
        "variable": variable,
        "reference_layer": True,
        "wired_into_aep": False,
        "note": GWA_REFERENCE_NOTE,
    }
    if extra:
        prov.update({k: v for k, v in extra.items()})
    return prov


def _clip_reproject(
    source_path: str | Path,
    bbox: BBox,
    dst_crs: str,
) -> Tuple[np.ndarray, BBox]:
    """Read a GWA GeoTIFF, clip to ``bbox`` (in ``dst_crs``) and reproject if needed.

    Returns the north-up clipped float32 array and the achieved ``(west, south, east,
    north)`` bounds (which snap to the source pixel grid, so they may differ from the
    requested bbox by up to one cell). The band is read north-up (row 0 = north edge),
    matching :func:`analytics.gis.geotiff_export.write_geotiff`.
    """
    rasterio = _require_rasterio()
    from rasterio.crs import CRS
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds as window_from_bounds

    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError(
            f"bbox must be (west, south, east, north) with west<east and south<north, "
            f"got {bbox!r}"
        )

    with rasterio.open(source_path) as src:
        src_crs = src.crs
        target = CRS.from_string(dst_crs)
        # Express the requested (dst_crs) bbox in the source CRS so the read window is
        # correct even when the GWA tile is delivered in a different projection.
        if src_crs is not None and src_crs != target:
            src_bounds = transform_bounds(target, src_crs, west, south, east, north)
        else:
            src_bounds = (west, south, east, north)

        window = window_from_bounds(*src_bounds, transform=src.transform)
        arr = src.read(1, window=window, boundless=True, fill_value=float("nan"))
        win_transform = src.window_transform(window)
        rows, cols = arr.shape
        # Bounds achieved by the pixel-aligned window (source CRS).
        s_w, s_n = win_transform * (0, 0)
        s_e, s_s = win_transform * (cols, rows)

        if src_crs is not None and src_crs != target:
            out_bounds = transform_bounds(src_crs, target, s_w, s_s, s_e, s_n)
        else:
            out_bounds = (s_w, s_s, s_e, s_n)

    arr = np.asarray(arr, dtype="float32")
    o_w, o_s, o_e, o_n = out_bounds
    return arr, (float(o_w), float(o_s), float(o_e), float(o_n))


def ingest_gwa_layer(
    source_path: str | Path,
    variable: str,
    bbox: BBox,
    out_path: str | Path,
    crs: str = DEFAULT_CRS,
    extra_provenance: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Clip one local GWA GeoTIFF to ``bbox`` and write a provenance-stamped layer.

    Args:
        source_path: LOCAL path to a Global Wind Atlas 250 m GeoTIFF. Never fetched over
            the network here (CESSPIT — an offline, deterministic ingest).
        variable: GWA variable short name (e.g. ``"wind_speed"`` / ``"power_density"``),
            used in the output filename and provenance.
        bbox: ``(west, south, east, north)`` clip window in ``crs`` units.
        out_path: Output ``.tif`` path for the clipped reference layer.
        crs: Target CRS (default EPSG:4326, QGIS-friendly).
        extra_provenance: Optional extra key/values merged into the provenance block.

    Returns:
        ``{"variable", "path", "bbox", "provenance"}`` for the written layer.
    """
    arr, achieved_bbox = _clip_reproject(source_path, bbox, crs)
    provenance = gwa_provenance(variable, source_path, extra_provenance)
    provenance["requested_bbox"] = list(bbox)
    provenance["achieved_bbox"] = list(achieved_bbox)
    written = write_geotiff(
        arr, achieved_bbox, out_path, crs=crs, provenance=provenance
    )
    return {
        "variable": variable,
        "path": str(written),
        "bbox": list(achieved_bbox),
        "provenance": provenance,
    }


def run_gwa_ingest(gwa_cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Ingest one or more local GWA layers from a ``gwa:`` config block + manifest them.

    Args:
        gwa_cfg: Config block with:
            - ``bbox``: ``[west, south, east, north]`` clip window (required).
            - ``out_dir``: directory for the written reference GeoTIFFs (required).
            - ``manifest_path``: ``DataLake_Manifest_All.json`` path (required).
            - ``layers``: list of ``{name, source_path, variable?}`` (required, non-empty).
            - ``crs``: optional target CRS (default EPSG:4326).
            - ``manifest_name``: optional manifest dataset name
              (default ``"DutchBay/GIS/gwa_250m_reference"``).

    Returns:
        Summary: ``{"crs", "layers": {name: {...}}, "manifest_path"}``.

    Raises:
        KeyError / ValueError: on a missing or empty required field (CESSPIT — no silent
            defaults for the site geometry or the source files).
    """
    crs = str(gwa_cfg.get("crs", DEFAULT_CRS))
    bbox_raw = gwa_cfg["bbox"]
    bbox: BBox = (
        float(bbox_raw[0]),
        float(bbox_raw[1]),
        float(bbox_raw[2]),
        float(bbox_raw[3]),
    )
    out_dir = Path(gwa_cfg["out_dir"])
    manifest_path = gwa_cfg["manifest_path"]
    manifest_name = str(gwa_cfg.get("manifest_name", "DutchBay/GIS/gwa_250m_reference"))

    layers = list(gwa_cfg["layers"])
    if not layers:
        raise ValueError("gwa.layers must be a non-empty list of GWA layer specs")

    paths: Dict[str, str] = {}
    variables: list[str] = []
    layer_summ: Dict[str, Any] = {}
    layer_prov: Dict[str, Any] = {}
    for layer in layers:
        name = str(layer["name"])
        variable = str(layer.get("variable", name))
        source_path = layer["source_path"]
        out_path = out_dir / f"gwa_{name}.tif"
        result = ingest_gwa_layer(
            source_path,
            variable,
            bbox,
            out_path,
            crs=crs,
            extra_provenance=layer.get("provenance"),
        )
        paths[variable] = result["path"]
        variables.append(variable)
        layer_summ[name] = result
        layer_prov[variable] = result["provenance"]

    entry = build_manifest_entry(
        name=manifest_name,
        bbox=bbox,
        resolution_deg=_metres_to_deg(GWA_RESOLUTION_M, bbox),
        variables=tuple(variables),
        paths=paths,
        provenance={
            "method": "gwa_250m_reference_ingest",
            "source": GWA_SOURCE,
            "resolution_m": GWA_RESOLUTION_M,
            "reference_layer": True,
            "wired_into_aep": False,
            "note": GWA_REFERENCE_NOTE,
            "layers": layer_prov,
        },
        crs=crs,
    )
    manifest = append_manifest(manifest_path, [entry])
    logger.info(
        "GWA ingest: wrote %d reference layers to %s (manifest %s)",
        len(layers),
        out_dir,
        manifest,
    )
    return {
        "crs": crs,
        "layers": layer_summ,
        "manifest_path": str(manifest),
    }


def _metres_to_deg(metres: float, bbox: BBox) -> float:
    """Approximate a metre resolution as degrees at the bbox centre latitude.

    A coarse informational figure for the manifest's ``resolution_deg`` field only (the
    authoritative native resolution is ``resolution_m`` in provenance); one degree of
    latitude ~= 111_320 m. This never touches a raster or a KPI.
    """
    return float(metres) / 111_320.0
