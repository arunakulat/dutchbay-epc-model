"""GeoTIFF export for QGIS (issue #20): write n×n raster fields + a data-lake manifest.

Writes single-band float32 GeoTIFFs (one per variable) with an EPSG:4326 affine
transform derived from the grid bbox, plus a ``DataLake_Manifest_All.json`` entry
carrying ``gis.extent`` / ``gis.resolution`` / ``variables`` and a #18-style provenance
block.

CASPER: ``rasterio`` is an optional ``[gis]`` dependency, guarded at call time via
:func:`_require_rasterio` (so the base install never needs GDAL). CCCDIR: every output
path / CRS / extent is config-supplied — nothing hardcoded here except the EPSG:4326
default the issue specifies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

import numpy as np

#: CRS mandated by issue #20 (QGIS-friendly geographic coordinates).
DEFAULT_CRS = "EPSG:4326"

BBox = Tuple[float, float, float, float]  # (west, south, east, north)


def _require_rasterio() -> Any:
    """Return the ``rasterio`` module or raise an actionable CASPER error if absent."""
    try:
        import rasterio  # noqa: F401

        return rasterio
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "GeoTIFF export requires the [gis] extra: "
            "pip install 'rasterio>=1.3'  (or  pip install -e '.[gis]')."
        ) from exc


def write_geotiff(
    array: np.ndarray,
    bbox: BBox,
    path: str | Path,
    crs: str = DEFAULT_CRS,
    provenance: Mapping[str, Any] | None = None,
) -> Path:
    """Write a single-band float32 GeoTIFF with a north-up affine transform.

    Args:
        array: 2-D field; row 0 is the north (top) edge of ``bbox``.
        bbox: ``(west, south, east, north)`` in ``crs`` units.
        path: Output ``.tif`` path (parent dirs are created).
        crs: Coordinate reference system (default EPSG:4326).
        provenance: Optional key/values written both as GeoTIFF tags and a
            ``<path>.prov.json`` sidecar (#18 provenance discipline).

    Returns:
        The written path.
    """
    rasterio = _require_rasterio()
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    arr = np.asarray(array, dtype="float32")
    if arr.ndim != 2:
        raise ValueError(f"expected a 2-D array, got shape {arr.shape}")
    nrows, ncols = arr.shape
    west, south, east, north = bbox
    transform = from_bounds(west, south, east, north, ncols, nrows)

    out = Path(path)
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
        nodata=float("nan"),
    ) as dst:
        dst.write(arr, 1)
        if provenance:
            dst.update_tags(**{k: str(v) for k, v in provenance.items()})

    if provenance is not None:
        Path(f"{out}.prov.json").write_text(json.dumps(dict(provenance), indent=2))
    return out


def export_grid_rasters(
    grids: Mapping[str, np.ndarray],
    bbox: BBox,
    out_dir: str | Path,
    prefix: str,
    crs: str = DEFAULT_CRS,
    provenance: Mapping[str, Any] | None = None,
) -> Dict[str, str]:
    """Write one GeoTIFF per variable to ``out_dir/{prefix}_{variable}.tif``.

    Returns ``{variable: path}``.
    """
    paths: Dict[str, str] = {}
    for var, arr in grids.items():
        tif = Path(out_dir) / f"{prefix}_{var}.tif"
        var_prov = {**dict(provenance or {}), "variable": var}
        write_geotiff(arr, bbox, tif, crs=crs, provenance=var_prov)
        paths[var] = str(tif)
    return paths


def build_manifest_entry(
    name: str,
    bbox: BBox,
    resolution_deg: float,
    variables: Tuple[str, ...],
    paths: Mapping[str, str],
    provenance: Mapping[str, Any] | None = None,
    crs: str = DEFAULT_CRS,
) -> Dict[str, Any]:
    """Build a single ``DataLake_Manifest_All.json`` dataset entry for a grid."""
    west, south, east, north = bbox
    return {
        "name": name,
        "gis": {
            "extent": {"west": west, "south": south, "east": east, "north": north},
            "resolution_deg": resolution_deg,
            "crs": crs,
        },
        "variables": list(variables),
        "files": {v: paths[v] for v in variables if v in paths},
        "provenance": dict(provenance or {}),
    }


def append_manifest(manifest_path: str | Path, entries: list[Dict[str, Any]]) -> Path:
    """Create or update ``DataLake_Manifest_All.json`` with the given dataset entries.

    Idempotent: an existing dataset with the same ``name`` is replaced (not duplicated),
    so re-running the export does not bloat the manifest.
    """
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        doc = json.loads(path.read_text())
    else:
        doc = {"schema": "DataLake_Manifest_All", "datasets": []}
    doc.setdefault("datasets", [])
    new_names = {e["name"] for e in entries}
    doc["datasets"] = [
        d for d in doc["datasets"] if d.get("name") not in new_names
    ] + list(entries)
    path.write_text(json.dumps(doc, indent=2))
    return path
