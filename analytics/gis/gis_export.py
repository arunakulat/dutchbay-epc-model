"""Orchestrate the issue-#20 GIS export: coarse + fine ws150/CF/AEP GeoTIFFs + manifest.

Driven entirely by a scenario ``gis:`` block. The native (coarse) grids are sampled
from ERA5 (one real point per cell); each interpolated (fine) grid is a bilinear
downscale of its named native source. The cell-result *source* is injectable so the
pipeline is unit-testable with no network call; the default source does the live ERA5
fetch (slow, ``[wind]`` extra + ``~/.cdsapirc``).

GWTF: config-first, fully typed, Hydra/OmegaConf CLI (no ``argparse``/``input()``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

import numpy as np

from analytics.gis.geotiff_export import (DEFAULT_CRS, append_manifest,
                                          build_manifest_entry,
                                          export_grid_rasters)
from wind_resource.era5_grid import (GRID_VARIABLES, CellResult, GridSpec,
                                     assemble_grids, downscale_bilinear,
                                     fetch_cell_results)

logger = logging.getLogger(__name__)

#: A provider mapping a grid spec to its per-cell ERA5 results.
CellSource = Callable[[GridSpec], List[CellResult]]


def grid_specs(gis_cfg: Mapping[str, Any]) -> List[GridSpec]:
    """Build the ordered list of :class:`GridSpec` from the ``gis.grids`` config."""
    lat = float(gis_cfg["center_lat"])
    lon = float(gis_cfg["center_lon"])
    specs: List[GridSpec] = []
    for grid in gis_cfg["grids"]:
        specs.append(
            GridSpec(
                name=str(grid["name"]),
                center_lat=lat,
                center_lon=lon,
                n=int(grid.get("n", 3)),
                cell_deg=float(grid["cell_deg"]),
                mode=str(grid.get("mode", "native")),
            )
        )
    return specs


def default_era5_source(era5_cfg: Mapping[str, Any]) -> CellSource:
    """Build a live-ERA5 :data:`CellSource` from a ``gis.era5`` config block.

    Turbine/site identity (hub height, turbine model, turbine count) is
    config-REQUIRED — no silent fallback to a specific machine/hub (ARCH-01 /
    CESSPIT), matching :func:`wind_resource.arco_assessment.era5_config_from_scenario`
    and ``ERA5RequestConfig.from_yaml``. A misconfigured ``gis.era5`` block must fail
    loud, not compute a wind grid for the wrong turbine/hub.

    Raises:
        KeyError: if any required ``gis.era5`` identity field is absent.
    """
    from wind_resource.era5_retrieval import ERA5RequestConfig

    base = ERA5RequestConfig(
        project_name=str(era5_cfg.get("project_name", "site")),
        latitude=0.0,  # replaced per cell
        longitude=0.0,
        start_year=int(era5_cfg["start_year"]),
        end_year=int(era5_cfg["end_year"]),
        hub_height_m=float(era5_cfg["hub_height_m"]),
        output_dir=str(era5_cfg.get("output_dir", "outputs/era5_grid_cache")),
        turbine_model=str(era5_cfg["turbine_model"]),
        num_turbines=int(era5_cfg["num_turbines"]),
    )

    def _source(spec: GridSpec) -> List[CellResult]:
        return fetch_cell_results(spec, base)

    return _source


def run_gis_export(
    gis_cfg: Mapping[str, Any],
    source: Optional[CellSource] = None,
) -> Dict[str, Any]:
    """Build + write the coarse and fine GeoTIFFs and a manifest from a ``gis:`` block.

    Args:
        gis_cfg: The scenario ``gis:`` block — ``center_lat``/``center_lon``, ``grids``
            (each ``name``/``cell_deg``/``mode`` and, for ``interpolated``, ``source``),
            ``out_dir``, ``manifest_path``, optional ``crs`` and ``era5``.
        source: Optional ``GridSpec -> [CellResult]`` provider. Defaults to a live ERA5
            fetch built from ``gis_cfg['era5']``; tests/demos inject a synthetic one.

    Returns:
        Summary: per-grid bbox / resolution / written file paths + the manifest path.
    """
    crs = str(gis_cfg.get("crs", DEFAULT_CRS))
    out_dir = Path(gis_cfg["out_dir"])
    manifest_path = gis_cfg["manifest_path"]
    specs = grid_specs(gis_cfg)
    by_name = {s.name: s for s in specs}
    grid_cfg_by_name = {str(g["name"]): g for g in gis_cfg["grids"]}

    if source is None:
        source = default_era5_source(gis_cfg["era5"])

    # 1) Native grids — sample ERA5 at each cell centre.
    native_grids: Dict[str, Dict[str, np.ndarray]] = {}
    for spec in specs:
        if spec.mode == "native":
            native_grids[spec.name] = assemble_grids(source(spec), spec.n)

    # 2) Write every grid (native directly; interpolated as a downscale of its source).
    entries: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"grids": {}, "manifest_path": str(manifest_path)}

    for spec in specs:
        if spec.mode == "native":
            grids = native_grids[spec.name]
            provenance = {
                "method": "era5_native_point_sample",
                "source_grid": spec.name,
                "cell_deg": spec.cell_deg,
                "note": "one ERA5 point per cell (native ~0.25 deg reanalysis)",
            }
        else:
            src_name = str(grid_cfg_by_name[spec.name].get("source", "coarse"))
            if src_name not in native_grids:
                raise KeyError(
                    f"fine grid '{spec.name}' references unknown native source '{src_name}'"
                )
            grids = downscale_bilinear(native_grids[src_name], by_name[src_name], spec)
            provenance = {
                "method": "bilinear_downscale_of_era5",
                "source_grid": src_name,
                "cell_deg": spec.cell_deg,
                "note": "interpolated from native ERA5 ~0.25 deg; NOT a measured sub-grid field",
            }

        bbox = spec.bbox()
        paths = export_grid_rasters(
            grids, bbox, out_dir, prefix=f"dutchbay_{spec.name}", crs=crs, provenance=provenance
        )
        entries.append(
            build_manifest_entry(
                name=f"DutchBay/GIS/{spec.name}",
                bbox=bbox,
                resolution_deg=spec.cell_deg,
                variables=GRID_VARIABLES,
                paths=paths,
                provenance=provenance,
                crs=crs,
            )
        )
        summary["grids"][spec.name] = {
            "bbox": list(bbox),
            "resolution_deg": spec.cell_deg,
            "mode": spec.mode,
            "files": paths,
        }

    manifest = append_manifest(manifest_path, entries)
    summary["manifest_path"] = str(manifest)
    logger.info("GIS export: wrote %d grids to %s (manifest %s)", len(specs), out_dir, manifest)
    return summary


def main() -> None:  # pragma: no cover - config-driven CLI (no argparse)
    """Config-driven entry point. Reads a scenario YAML and runs the live ERA5 export."""
    import json
    import os

    from omegaconf import OmegaConf

    cfg_path = os.environ.get(
        "GIS_EXPORT_CONFIG", "wind_resource/config/gis_export_dutchbay.yaml"
    )
    full = OmegaConf.to_container(OmegaConf.load(cfg_path), resolve=True)
    assert isinstance(full, dict)
    gis_cfg = full.get("gis", full)  # dedicated file OR a scenario `gis:` block
    summary = run_gis_export(gis_cfg)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
