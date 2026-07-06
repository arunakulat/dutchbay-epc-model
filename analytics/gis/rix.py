"""RIX / ΔRIX terrain-ruggedness envelope diagnostic (issue #831, epic #827).

Compute the **Ruggedness Index (RIX)** — the fraction of terrain within a radius of a
point that is steeper than a critical slope — from the SLOPE raster produced by the DEM
ingester (:mod:`analytics.gis.dem_ingest`, #829), report **ΔRIX** between a predictor
(reference/mast) point and each turbine point, and **disclose** when the linear-flow /
reanalysis assumptions (WAsP / ERA5-style) are outside their operational envelope.

Research grounding (Mortensen, Bowen & Antoniou 2006, DTU/Risø): WAsP prediction error is
log-linear in ΔRIX, and **|ΔRIX| > ~5%** is the operational threshold above which a
terrain (BZ / orographic) correction is needed. For DutchBay's flat coastal sites RIX is
expected to be low, so the diagnostic typically CONFIRMS the linear/reanalysis assumptions
are adequate — itself a bankable disclosure.

RIX convention: the critical slope is conventionally **0.3 (≈16.7°)** — the value at which
WAsP's flow model starts to separate. The DEM slope raster is in **degrees** (see
:func:`analytics.gis.dem_ingest.slope_aspect_hillshade`), so this module takes the
critical slope as a rise/run **ratio** (config-first, default 0.3) and converts it to a
degree threshold internally (``atan(ratio)``) before comparing against the raster — the
raster is never re-interpreted.

CASPER: pure numpy — no optional dependency needed for the point/array computation. The
OPTIONAL raster/manifest export reuses the issue-#20 helpers
(:mod:`analytics.gis.geotiff_export`), which CASPER-guard ``rasterio``. CCCDIR /
config-first (ARCH-01): critical slope, radius and the disclosure threshold are all
arg/config-supplied — nothing site-specific is hardcoded. KPI-neutral: a read-only GIS
diagnostic, not wired into the finance/AEP pipeline.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

#: Conventional RIX critical slope as a rise/run ratio (WAsP: 0.3 ≈ 16.7° ≈ 17°). The
#: fraction of terrain steeper than this is the RIX. Config-overridable.
DEFAULT_CRITICAL_SLOPE = 0.3

#: Default RIX neighbourhood radius, in the SAME units as the point/pixel coordinates
#: passed to :func:`rix_at_point` (i.e. pixels for an index-space call, metres for a
#: metre-spaced grid). Config-first — a site supplies its own radius.
DEFAULT_RADIUS = 10.0

#: |ΔRIX| disclosure threshold (fraction). Above this, the linear-flow / reanalysis
#: envelope is exceeded and a terrain correction is indicated (Mortensen et al. 2006,
#: ~5%). Config-overridable.
DEFAULT_DELTA_RIX_THRESHOLD = 0.05

Point = Tuple[float, float]  # (row, col) in the slope raster's index space


def critical_slope_ratio_to_degrees(critical_slope: float) -> float:
    """Convert a rise/run critical-slope RATIO to the degree threshold of the raster.

    The DEM slope raster is in degrees, so a ratio critical slope (e.g. 0.3) is compared
    as ``atan(0.3) ≈ 16.7°``. A caller who already has a degree threshold can bypass this.
    """
    return math.degrees(math.atan(float(critical_slope)))


def rix_at_point(
    slope: np.ndarray,
    center: Point,
    radius: float = DEFAULT_RADIUS,
    critical_slope: float = DEFAULT_CRITICAL_SLOPE,
    *,
    pixel_size: Tuple[float, float] = (1.0, 1.0),
    critical_slope_is_degrees: bool = False,
) -> float:
    """Ruggedness Index at ``center``: fraction of terrain within ``radius`` steeper than
    the critical slope.

    Args:
        slope: 2-D SLOPE raster in **degrees** (the :mod:`analytics.gis.dem_ingest`
            output; row 0 == north, same grid as the elevation input).
        center: ``(row, col)`` of the point of interest in the raster's index space.
        radius: Neighbourhood radius, in the units of ``pixel_size`` (default: pixels,
            since ``pixel_size`` defaults to one unit per pixel). Cells whose centre is
            within this Euclidean radius of ``center`` form the RIX window.
        critical_slope: Critical slope as a rise/run RATIO by default (0.3 ≈ 16.7°),
            converted to a degree threshold internally. Set ``critical_slope_is_degrees``
            to pass a degree threshold directly.
        pixel_size: ``(drow, dcol)`` physical cell size (e.g. metres). The radius is
            measured in these units, so a metre radius over a metre-spaced grid works
            directly. Defaults to unit pixels.
        critical_slope_is_degrees: When True, ``critical_slope`` is already a degree
            threshold and no ratio→degree conversion is applied.

    Returns:
        RIX in ``[0, 1]``: (# cells in the window with ``slope > threshold``) /
        (# cells in the window). A perfectly flat neighbourhood gives 0.0; a
        neighbourhood entirely steeper than the critical slope gives 1.0. Returns
        ``float('nan')`` if the window is empty (radius smaller than one cell) — an
        honest "undefined", never a silent 0.

    NaN slope cells (e.g. DEM nodata) are excluded from BOTH the numerator and the
    denominator, so RIX is the fraction of *valid* terrain that is steep.
    """
    arr = np.asarray(slope, dtype="float64")
    if arr.ndim != 2:
        raise ValueError(f"expected a 2-D slope raster, got shape {arr.shape}")
    if radius <= 0.0:
        raise ValueError(f"radius must be positive, got {radius}")

    threshold_deg = (
        float(critical_slope)
        if critical_slope_is_degrees
        else critical_slope_ratio_to_degrees(critical_slope)
    )

    nrows, ncols = arr.shape
    row0, col0 = float(center[0]), float(center[1])
    drow, dcol = float(pixel_size[0]), float(pixel_size[1])

    rows = np.arange(nrows, dtype="float64")[:, None]
    cols = np.arange(ncols, dtype="float64")[None, :]
    dist = np.hypot((rows - row0) * drow, (cols - col0) * dcol)
    window = dist <= radius

    valid = window & np.isfinite(arr)
    denom = int(valid.sum())
    if denom == 0:
        return float("nan")
    steep = valid & (arr > threshold_deg)
    return float(int(steep.sum()) / denom)


def delta_rix(rix_predictor: float, rix_target: float) -> float:
    """ΔRIX = RIX(target/turbine) − RIX(predictor/reference-mast).

    Positive means the turbine sits in MORE rugged terrain than the mast the wind climate
    was measured/modelled at, so the (linear-flow) prediction tends to UNDER-predict —
    this is the WAsP RIX-correction sign convention (Mortensen et al. 2006).
    """
    return float(rix_target) - float(rix_predictor)


@dataclass(frozen=True)
class RixDisclosure:
    """A single predictor→target RIX/ΔRIX envelope disclosure.

    KPI-neutral: purely a reported set of numbers plus a boolean envelope flag; it never
    alters any AEP or financial quantity.
    """

    rix_predictor: float
    rix_target: float
    delta_rix: float
    threshold: float
    exceeds_threshold: bool
    critical_slope: float
    radius: float
    #: Human-readable envelope note (bankable disclosure text).
    note: str
    #: Optional label for the target (e.g. a turbine id).
    target_label: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly dict (for a report block / manifest entry)."""
        return asdict(self)


def _envelope_note(exceeds: bool, delta: float, threshold: float) -> str:
    """Bankable disclosure text for the ΔRIX envelope check."""
    pct = abs(delta) * 100.0
    thr_pct = threshold * 100.0
    if exceeds:
        return (
            f"|ΔRIX| = {pct:.1f}% EXCEEDS the {thr_pct:.0f}% envelope: the terrain "
            "complexity between the reference/mast and the turbine is outside the "
            "linear-flow / reanalysis (WAsP / ERA5) operational envelope — a terrain "
            "(orographic / BZ) speed-up correction is indicated (Mortensen et al. 2006)."
        )
    return (
        f"|ΔRIX| = {pct:.1f}% is within the {thr_pct:.0f}% envelope: the linear-flow / "
        "reanalysis (WAsP / ERA5) assumptions are adequate between the reference/mast and "
        "the turbine — no terrain correction indicated (Mortensen et al. 2006)."
    )


def assess_delta_rix(
    rix_predictor: float,
    rix_target: float,
    *,
    threshold: float = DEFAULT_DELTA_RIX_THRESHOLD,
    critical_slope: float = DEFAULT_CRITICAL_SLOPE,
    radius: float = DEFAULT_RADIUS,
    target_label: str = "",
) -> RixDisclosure:
    """Build a :class:`RixDisclosure` for a predictor→target pair, firing the flag when
    ``|ΔRIX| > threshold``.

    Config-first: ``threshold`` (default 5%), ``critical_slope`` and ``radius`` are all
    arg-supplied. The ``critical_slope`` / ``radius`` are carried through only for
    provenance (they must match the values RIX was computed with).
    """
    d = delta_rix(rix_predictor, rix_target)
    exceeds = abs(d) > float(threshold)
    return RixDisclosure(
        rix_predictor=float(rix_predictor),
        rix_target=float(rix_target),
        delta_rix=d,
        threshold=float(threshold),
        exceeds_threshold=exceeds,
        critical_slope=float(critical_slope),
        radius=float(radius),
        note=_envelope_note(exceeds, d, float(threshold)),
        target_label=str(target_label),
    )


@dataclass(frozen=True)
class RixReport:
    """A full RIX/ΔRIX diagnostic block: the reference RIX plus a disclosure per turbine.

    KPI-neutral read-only diagnostic (issue #831). ``any_exceeds`` is a convenience roll-up
    for a lender-facing "all turbines within envelope?" badge.
    """

    reference_label: str
    reference_rix: float
    critical_slope: float
    critical_slope_deg: float
    radius: float
    threshold: float
    disclosures: List[RixDisclosure] = field(default_factory=list)

    @property
    def any_exceeds(self) -> bool:
        """True if ANY turbine's |ΔRIX| exceeds the envelope threshold."""
        return any(d.exceeds_threshold for d in self.disclosures)

    def as_dict(self) -> Dict[str, Any]:
        """JSON-friendly dict for a report block / manifest ``rix`` entry."""
        return {
            "reference_label": self.reference_label,
            "reference_rix": self.reference_rix,
            "critical_slope": self.critical_slope,
            "critical_slope_deg": self.critical_slope_deg,
            "radius": self.radius,
            "threshold": self.threshold,
            "any_exceeds_threshold": self.any_exceeds,
            "disclosures": [d.as_dict() for d in self.disclosures],
        }


def build_rix_report(
    slope: np.ndarray,
    reference: Point,
    turbines: Sequence[Point],
    *,
    turbine_labels: Sequence[str] | None = None,
    reference_label: str = "reference_mast",
    radius: float = DEFAULT_RADIUS,
    critical_slope: float = DEFAULT_CRITICAL_SLOPE,
    threshold: float = DEFAULT_DELTA_RIX_THRESHOLD,
    pixel_size: Tuple[float, float] = (1.0, 1.0),
    critical_slope_is_degrees: bool = False,
) -> RixReport:
    """Compute the RIX at a reference point and each turbine, and the ΔRIX disclosures.

    Config-first (ARCH-01): ``radius``, ``critical_slope`` and ``threshold`` all flow in
    from args/config. Pure/read-only — computes numbers only; writes nothing. KPI-neutral.

    Args:
        slope: 2-D SLOPE raster in degrees (the dem_ingest output).
        reference: ``(row, col)`` of the reference/mast point (the wind-climate predictor).
        turbines: ``(row, col)`` points for each turbine (the prediction targets).
        turbine_labels: Optional labels aligned with ``turbines``.
        reference_label: Label for the reference point.
        radius / critical_slope / threshold / pixel_size / critical_slope_is_degrees:
            See :func:`rix_at_point` and :func:`assess_delta_rix`.
    """
    ref_rix = rix_at_point(
        slope,
        reference,
        radius=radius,
        critical_slope=critical_slope,
        pixel_size=pixel_size,
        critical_slope_is_degrees=critical_slope_is_degrees,
    )
    labels = list(turbine_labels) if turbine_labels is not None else []
    disclosures: List[RixDisclosure] = []
    for idx, pt in enumerate(turbines):
        t_rix = rix_at_point(
            slope,
            pt,
            radius=radius,
            critical_slope=critical_slope,
            pixel_size=pixel_size,
            critical_slope_is_degrees=critical_slope_is_degrees,
        )
        label = labels[idx] if idx < len(labels) else f"turbine_{idx}"
        disclosures.append(
            assess_delta_rix(
                ref_rix,
                t_rix,
                threshold=threshold,
                critical_slope=critical_slope,
                radius=radius,
                target_label=label,
            )
        )

    threshold_deg = (
        float(critical_slope)
        if critical_slope_is_degrees
        else critical_slope_ratio_to_degrees(critical_slope)
    )
    report = RixReport(
        reference_label=reference_label,
        reference_rix=ref_rix,
        critical_slope=float(critical_slope),
        critical_slope_deg=threshold_deg,
        radius=float(radius),
        threshold=float(threshold),
        disclosures=disclosures,
    )
    logger.info(
        "RIX diagnostic: reference RIX=%.4f, %d turbine(s), %d outside %.0f%% envelope",
        ref_rix if math.isfinite(ref_rix) else float("nan"),
        len(disclosures),
        sum(d.exceeds_threshold for d in disclosures),
        float(threshold) * 100.0,
    )
    return report


def rix_field(
    slope: np.ndarray,
    radius: float = DEFAULT_RADIUS,
    critical_slope: float = DEFAULT_CRITICAL_SLOPE,
    *,
    pixel_size: Tuple[float, float] = (1.0, 1.0),
    critical_slope_is_degrees: bool = False,
) -> np.ndarray:
    """Compute a full RIX raster: the RIX at EVERY cell of ``slope``.

    A pure/optional convenience for the raster export (below) and for visual QGIS overlay.
    Each output cell holds the RIX of the neighbourhood centred on it. This is O(N * window)
    and intended for the modest site tiles the DEM ingester produces, not a national DEM.

    Empty windows (should not occur for ``radius >= 1`` cell) become ``nan``.
    """
    arr = np.asarray(slope, dtype="float64")
    if arr.ndim != 2:
        raise ValueError(f"expected a 2-D slope raster, got shape {arr.shape}")
    nrows, ncols = arr.shape
    out = np.empty((nrows, ncols), dtype="float32")
    for r in range(nrows):
        for c in range(ncols):
            out[r, c] = rix_at_point(
                arr,
                (r, c),
                radius=radius,
                critical_slope=critical_slope,
                pixel_size=pixel_size,
                critical_slope_is_degrees=critical_slope_is_degrees,
            )
    return out


def export_rix_raster(
    slope: np.ndarray,
    bbox: Tuple[float, float, float, float],
    out_path: str,
    *,
    radius: float = DEFAULT_RADIUS,
    critical_slope: float = DEFAULT_CRITICAL_SLOPE,
    threshold: float = DEFAULT_DELTA_RIX_THRESHOLD,
    pixel_size: Tuple[float, float] = (1.0, 1.0),
    critical_slope_is_degrees: bool = False,
    crs: str | None = None,
    extra_provenance: Mapping[str, Any] | None = None,
) -> str:
    """OPTIONAL: write a RIX raster GeoTIFF + ``.prov.json`` sidecar via the #20 helpers.

    Kept optional and separate from the core point/array computation (which needs no
    optional dependency). Reuses :func:`analytics.gis.geotiff_export.write_geotiff`, so
    ``rasterio`` is CASPER-guarded there. KPI-neutral: writes a diagnostic layer only.
    """
    from analytics.gis.geotiff_export import DEFAULT_CRS, write_geotiff

    field_arr = rix_field(
        slope,
        radius=radius,
        critical_slope=critical_slope,
        pixel_size=pixel_size,
        critical_slope_is_degrees=critical_slope_is_degrees,
    )
    threshold_deg = (
        float(critical_slope)
        if critical_slope_is_degrees
        else critical_slope_ratio_to_degrees(critical_slope)
    )
    provenance: Dict[str, Any] = {
        "variable": "rix",
        "method": "ruggedness_index_fraction_steeper_than_critical_slope",
        "note": (
            "RIX = fraction of terrain within radius steeper than the critical slope, from "
            "the DEM slope raster (#829). Envelope threshold |ΔRIX| flags where linear-flow "
            "/ reanalysis (WAsP / ERA5) assumptions need a terrain correction (Mortensen et "
            "al. 2006). KPI-neutral read-only diagnostic (#831)."
        ),
        "critical_slope_ratio": (
            None if critical_slope_is_degrees else float(critical_slope)
        ),
        "critical_slope_deg": threshold_deg,
        "radius": float(radius),
        "delta_rix_threshold": float(threshold),
    }
    if extra_provenance:
        provenance.update(dict(extra_provenance))
    write_geotiff(
        field_arr,
        bbox,
        out_path,
        crs=crs if crs is not None else DEFAULT_CRS,
        provenance=provenance,
    )
    return out_path


__all__: List[str] = [
    "DEFAULT_CRITICAL_SLOPE",
    "DEFAULT_DELTA_RIX_THRESHOLD",
    "DEFAULT_RADIUS",
    "RixDisclosure",
    "RixReport",
    "assess_delta_rix",
    "build_rix_report",
    "critical_slope_ratio_to_degrees",
    "delta_rix",
    "export_rix_raster",
    "rix_at_point",
    "rix_field",
]
