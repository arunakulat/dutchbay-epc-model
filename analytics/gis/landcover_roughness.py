"""ESA WorldCover ~10 m land-cover -> roughness-length (z0) raster (issue #830).

Foundation item (2) of the roughness epic #827. Ingests an ESA WorldCover land-cover
GeoTIFF for the site bbox, applies a documented land-cover-class -> aerodynamic
roughness-length (z0, metres) lookup, and exports a provenance-stamped z0 GeoTIFF plus a
``DataLake_Manifest_All.json`` entry via the existing #20 helpers
(:mod:`analytics.gis.geotiff_export`).

KPI-NEUTRAL: this is an add-only raster layer. The z0 field is *not* consumed by any
energy/AEP calculation here. A later, separately-gated dolphin may feed z0 into a log-law
hub-height wind profile -- that would be KPI-moving and is out of scope for #830.

Roughness-length lookup (metres)
--------------------------------
The default table maps each ESA WorldCover class code to a representative aerodynamic
roughness length. Values follow the WMO / Davenport-Wieringa roughness classification
(Wieringa, 1992, *J. Wind Eng. Ind. Aerodyn.* 41; WMO-No. 8, CIMO Guide, Table on effective
terrain roughness) as adopted for satellite land-cover in wind resource assessment (the
Global Wind Atlas v3/v4 pipeline reclassifies ESA WorldCover ~10 m to z0 for exactly this
purpose; see Davis et al., 2023, *Global Wind Atlas v3*, DTU Wind Energy):

===== =========================== ========= ================================
 code  ESA WorldCover class         z0 (m)    Davenport-Wieringa class
===== =========================== ========= ================================
   10  Tree cover                    0.60     8 closed (dense forest/orchard)
   20  Shrubland                     0.20     6 rough (bushes, young forest)
   30  Grassland                     0.03     4 roughly open (grass, few obst.)
   40  Cropland                      0.10     5 rough (mature crops, hedges)
   50  Built-up                      0.80     8 closed (built-up, suburbs)
   60  Bare / sparse vegetation      0.005    3 open (short grass, bare soil)
   70  Snow and ice                  0.001    2 smooth (snow, mud flats)
   80  Permanent water bodies        0.0002   1 sea (open water; WMO 2e-4)
   90  Herbaceous wetland            0.05     4-5 (marsh vegetation)
   95  Mangroves                     0.50     7-8 (tall dense coastal forest)
  100  Moss and lichen               0.03     4 (tundra / low vegetation)
===== =========================== ========= ================================

The open-water value (2e-4 m) is the WMO neutral-fetch sea roughness; it is a nominal
land-cover value, not a wind-speed-dependent Charnock roughness.

.. note::
   CORINE-based land-cover -> z0 tables (e.g. Silva et al., 2007) are a useful *schema*
   reference but are **Europe-only and 100 m** resolution -- too coarse to resolve the
   10-100 m variability micro-siting needs, and not calibrated for Sri Lankan land cover.
   ESA WorldCover ~10 m is preferred here (per GWA v4, which adopted ESA WorldCover ~10 m
   for the same reason). Any project-specific override belongs in config, not in this
   default table.

CASPER: ``rasterio`` is an optional ``[gis]`` dependency, guarded at call time via
:func:`analytics.gis.geotiff_export._require_rasterio`. CCCDIR / config-first: the
land-cover path, bbox, output paths and the class->z0 table are all config/arg supplied;
the only thing hardcoded here is the cited :data:`DEFAULT_LANDCOVER_Z0` default table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import numpy as np

from analytics.gis.geotiff_export import (
    DEFAULT_CRS,
    BBox,
    _require_rasterio,
    append_manifest,
    build_manifest_entry,
    write_geotiff,
)

#: Provenance id/source for the default land-cover -> z0 lookup table.
DEFAULT_Z0_TABLE_ID = "wmo_davenport_wieringa_esa_worldcover_v1"
DEFAULT_Z0_TABLE_SOURCE = (
    "WMO/Davenport-Wieringa roughness classification (Wieringa 1992; WMO-No.8 CIMO Guide) "
    "reclassified for ESA WorldCover ~10 m as in the Global Wind Atlas v3/v4 pipeline"
)

#: ESA WorldCover source label recorded in provenance.
LANDCOVER_SOURCE = "ESA WorldCover ~10 m"

#: Default ESA WorldCover class-code -> aerodynamic roughness length z0 (metres).
#: Keys are the ESA WorldCover (v100/v200) discrete class codes. Cited in the module
#: docstring. Config may override any/all entries; missing classes fall back to
#: :data:`DEFAULT_Z0_FALLBACK` (documented, not silent -- the class code is recorded).
DEFAULT_LANDCOVER_Z0: Dict[int, float] = {
    10: 0.60,  # Tree cover
    20: 0.20,  # Shrubland
    30: 0.03,  # Grassland
    40: 0.10,  # Cropland
    50: 0.80,  # Built-up
    60: 0.005,  # Bare / sparse vegetation
    70: 0.001,  # Snow and ice
    80: 0.0002,  # Permanent water bodies
    90: 0.05,  # Herbaceous wetland
    95: 0.50,  # Mangroves
    100: 0.03,  # Moss and lichen
}

#: Fallback z0 (metres) for any land-cover code absent from the active table. Uses the
#: grassland value as a neutral "roughly open" terrain default; the unmapped codes are
#: reported by :func:`reclass_landcover_to_z0` rather than silently swallowed.
DEFAULT_Z0_FALLBACK = 0.03


def _table_from_config(
    z0_table: Optional[Mapping[Any, float]],
) -> Dict[int, float]:
    """Normalise a config/arg class->z0 table to ``{int code: float z0}``.

    Accepts the :data:`DEFAULT_LANDCOVER_Z0` default when ``z0_table`` is ``None`` and
    coerces string keys (as they arrive from YAML/JSON config) to ``int`` codes. A
    config table is used as-is (it fully replaces the default) so an operator can pin a
    site-specific mapping without inheriting defaults they did not intend.
    """
    if z0_table is None:
        return dict(DEFAULT_LANDCOVER_Z0)
    return {int(code): float(z0) for code, z0 in z0_table.items()}


def reclass_landcover_to_z0(
    landcover: np.ndarray,
    z0_table: Optional[Mapping[Any, float]] = None,
    fallback_z0: float = DEFAULT_Z0_FALLBACK,
) -> tuple[np.ndarray, list[int]]:
    """Map an integer land-cover-class array to a float32 z0 (metres) array.

    Args:
        landcover: 2-D array of ESA WorldCover class codes (integers).
        z0_table: Optional class-code -> z0 mapping. Defaults to
            :data:`DEFAULT_LANDCOVER_Z0`. String keys (YAML/JSON) are coerced to ``int``.
        fallback_z0: z0 assigned to any class code absent from the table.

    Returns:
        ``(z0_array, unmapped_codes)`` -- the float32 z0 raster (same shape as
        ``landcover``) and the sorted list of distinct class codes that were not in the
        table (assigned ``fallback_z0``). The unmapped list is a CESSPIT disclosure: a
        code missing from the table is reported, never silently defaulted away.
    """
    codes = np.asarray(landcover)
    if codes.ndim != 2:
        raise ValueError(f"expected a 2-D land-cover array, got shape {codes.shape}")

    table = _table_from_config(z0_table)
    z0 = np.full(codes.shape, float(fallback_z0), dtype="float32")
    present = np.unique(codes)
    unmapped: list[int] = []
    for code in present:
        icode = int(code)
        if icode in table:
            z0[codes == code] = table[icode]
        else:
            unmapped.append(icode)
    return z0, sorted(unmapped)


def _read_landcover_geotiff(path: str | Path) -> tuple[np.ndarray, BBox, str]:
    """Read an ESA WorldCover GeoTIFF: return ``(class_array, bbox, crs)``.

    CASPER-guards rasterio at call time. The bbox is derived from the raster bounds so
    the exported z0 raster is co-registered with the input land cover.
    """
    rasterio = _require_rasterio()
    src_path = Path(path)
    with rasterio.open(src_path) as src:
        classes = src.read(1)
        b = src.bounds  # (left, bottom, right, top) == (west, south, east, north)
        bbox: BBox = (b.left, b.bottom, b.right, b.top)
        crs = src.crs.to_string() if src.crs is not None else DEFAULT_CRS
    return classes, bbox, crs


def export_roughness_raster(
    landcover_path: str | Path,
    out_path: str | Path,
    z0_table: Optional[Mapping[Any, float]] = None,
    fallback_z0: float = DEFAULT_Z0_FALLBACK,
    bbox: Optional[BBox] = None,
    crs: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
    manifest_name: str = "DutchBay/GIS/roughness_z0",
) -> Dict[str, Any]:
    """Reclass an ESA WorldCover GeoTIFF to z0 and export a provenance-stamped GeoTIFF.

    Args:
        landcover_path: LOCAL path to an ESA WorldCover ~10 m land-cover GeoTIFF (no
            network; a fetch/clip step is a separate concern).
        out_path: Output ``.tif`` path for the z0 raster.
        z0_table: Optional config class-code -> z0 (metres) override. Defaults to the
            cited :data:`DEFAULT_LANDCOVER_Z0`.
        fallback_z0: z0 for land-cover codes absent from the table.
        bbox: Optional explicit ``(west, south, east, north)`` override; by default the
            input raster's own bounds are used so z0 is co-registered with land cover.
        crs: Optional CRS override; defaults to the input raster's CRS (or EPSG:4326).
        manifest_path: If given, append/refresh a ``DataLake_Manifest_All.json`` entry.
        manifest_name: Dataset name used in the manifest entry.

    Returns:
        Summary dict: ``z0_path``, ``bbox``, ``crs``, ``unmapped_codes``,
        ``z0_table_id`` and (if written) ``manifest_path``.
    """
    classes, src_bbox, src_crs = _read_landcover_geotiff(landcover_path)
    out_bbox: BBox = tuple(bbox) if bbox is not None else src_bbox  # type: ignore[assignment]
    out_crs = str(crs) if crs is not None else src_crs

    z0, unmapped = reclass_landcover_to_z0(
        classes, z0_table=z0_table, fallback_z0=fallback_z0
    )

    provenance: Dict[str, Any] = {
        "method": "landcover_reclass_to_roughness_length",
        "source": LANDCOVER_SOURCE,
        "landcover_path": str(landcover_path),
        "z0_table_id": DEFAULT_Z0_TABLE_ID if z0_table is None else "config_override",
        "z0_table_source": DEFAULT_Z0_TABLE_SOURCE,
        "z0_units": "metres",
        "fallback_z0": float(fallback_z0),
        "unmapped_codes": ",".join(str(c) for c in unmapped),
        "note": (
            "KPI-neutral roughness layer; not wired into any AEP/energy calc. "
            "CORINE-based z0 tables are Europe-only 100 m; ESA WorldCover ~10 m preferred "
            "for Sri Lanka."
        ),
    }

    written = write_geotiff(z0, out_bbox, out_path, crs=out_crs, provenance=provenance)

    summary: Dict[str, Any] = {
        "z0_path": str(written),
        "bbox": list(out_bbox),
        "crs": out_crs,
        "unmapped_codes": unmapped,
        "z0_table_id": provenance["z0_table_id"],
    }

    if manifest_path is not None:
        # Approximate square-pixel resolution in CRS units for the manifest.
        west, south, east, north = out_bbox
        nrows, ncols = z0.shape
        resolution = (east - west) / ncols if ncols else 0.0
        entry = build_manifest_entry(
            name=manifest_name,
            bbox=out_bbox,
            resolution_deg=resolution,
            variables=("z0",),
            paths={"z0": str(written)},
            provenance=provenance,
            crs=out_crs,
        )
        manifest = append_manifest(manifest_path, [entry])
        summary["manifest_path"] = str(manifest)

    return summary
