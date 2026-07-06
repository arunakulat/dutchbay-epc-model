"""GIS-MCDM wind-siting suitability surface: AHP weights + Weighted Linear Combination (#834).

Foundation item ⑤ of the siting epic #827. Combines the criterion rasters produced by the
upstream foundation dolphins -- wind resource (GWA, #828), slope (DEM, #829), roughness z0
(#830) -- into a single **siting-suitability surface** in ``[0, 1]`` via the standard
GIS-MCDM recipe:

1. **Normalise** each criterion raster to a ``[0, 1]`` *suitability* using config-first
   breakpoints and a per-criterion *direction of preference* (``"benefit"`` -> higher raw is
   better, e.g. wind speed; ``"cost"`` -> higher raw is worse, e.g. slope, roughness).
2. **AHP** (Analytic Hierarchy Process) pairwise-comparison weights from a config matrix ->
   a priority (weight) vector, together with the **Consistency Ratio (CR)**; ``CR > 0.10``
   is flagged per Saaty's threshold.
3. **Weighted Linear Combination (WLC)** -> ``suitability = sum_i weight_i * normalised_i``.
4. **Boolean exclusion mask** (#833) applied as a *hard veto*: ``suitability = 0`` wherever
   the mask marks a cell not buildable. Exclusion is applied last, after scoring, exactly as
   in the wind-farm-siting MCDM literature (Boolean constraints first-class, weighted scoring
   second; Cunden et al. 2020, *Energy* 205:118533, Mauritius wind-farm siting).

The suitability GeoTIFF, its ``.prov.json`` provenance sidecar and a
``DataLake_Manifest_All.json`` entry are written via the existing #20 helpers
(:mod:`analytics.gis.geotiff_export`).

KPI-NEUTRAL: this is an add-only analytic/GIS layer. The suitability surface is a
siting-decision aid; it is *not* consumed by any AEP / cash-flow / IRR calculation. No
finance contract, scenario or KPI is touched.

Design notes
------------
* **Inputs, not imports.** The criterion rasters and the exclusion mask arrive as plain
  ``numpy`` arrays (documented shapes) -- this module does **not** import #828/#829/#830/#833,
  so it composes with whatever produced those layers (or with synthetic test fixtures). The
  caller is responsible for co-registering the rasters (same shape / grid) before combination.
* **Config-first (CCCDIR / CESSPIT).** Criterion directions, normalisation breakpoints and the
  AHP pairwise matrix are all arguments. The only hardcoded constant is the Saaty Random
  Index table (:data:`SAATY_RANDOM_INDEX`), which is a fixed statistical reference, not a
  project parameter.
* **CASPER.** ``rasterio`` is guarded at call time via
  :func:`analytics.gis.geotiff_export._require_rasterio`; the pure-``numpy`` math functions
  (normalisation, AHP, WLC) need no GIS toolchain and are independently testable.

AHP references
--------------
Saaty, T.L. (1980, 2008) *The Analytic Hierarchy Process*. Priority vector = the principal
right eigenvector of the pairwise matrix, approximated here by the *normalised-column mean*
(a.k.a. mean of normalised columns / arithmetic-mean method), which is exact for a perfectly
consistent matrix and a well-established close approximation otherwise. Consistency:
``CI = (lambda_max - n) / (n - 1)`` and ``CR = CI / RI(n)`` with ``RI`` from Saaty's Random
Index table; a matrix is accepted when ``CR <= 0.10``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.gis.geotiff_export import (
    DEFAULT_CRS,
    BBox,
    append_manifest,
    build_manifest_entry,
    write_geotiff,
)

#: Saaty's Random (Consistency) Index RI(n): the mean CI of a large sample of random
#: reciprocal pairwise matrices of order ``n``. Index 0/1 (n=1,2) are 0 by construction
#: (a 1x1 or 2x2 reciprocal matrix is always perfectly consistent). Values for n=3..10 are
#: Saaty's canonical figures (Saaty 1980; widely tabulated, e.g. Saaty 2008 *Int. J.
#: Services Sciences* 1(1) Table). Used as the denominator of the Consistency Ratio.
SAATY_RANDOM_INDEX: Dict[int, float] = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
}

#: Saaty's acceptance threshold for the Consistency Ratio: matrices with ``CR <= 0.10`` are
#: deemed acceptably consistent; above it the pairwise judgements should be revised.
CR_ACCEPTANCE_THRESHOLD = 0.10

#: Allowed per-criterion directions of preference.
BENEFIT = "benefit"  # higher raw value -> more suitable (e.g. wind speed)
COST = "cost"  # higher raw value -> less suitable (e.g. slope, roughness)
_VALID_DIRECTIONS = (BENEFIT, COST)


def normalise_criterion(
    raster: np.ndarray,
    direction: str,
    low: float,
    high: float,
) -> np.ndarray:
    """Linearly rescale a criterion raster to a ``[0, 1]`` suitability score.

    A cell's raw value is mapped onto ``[0, 1]`` between the config breakpoints
    ``low`` and ``high`` and clipped to that range (value-function normalisation --
    the standard WLC approach, robust to per-tile min/max drift that plain
    min-max scaling would suffer):

    * ``direction == "benefit"`` (higher is better): ``s = clip((x - low) / (high - low))``
      so ``x <= low -> 0`` and ``x >= high -> 1``.
    * ``direction == "cost"`` (higher is worse): the benefit score is inverted,
      ``s = 1 - clip((x - low) / (high - low))`` so ``x <= low -> 1`` and ``x >= high -> 0``.

    ``NaN`` cells (e.g. nodata) propagate as ``NaN`` and are the caller's concern; the
    exclusion mask is the intended mechanism for removing non-buildable cells.

    Args:
        raster: 2-D array of raw criterion values.
        direction: ``"benefit"`` or ``"cost"``.
        low: Raw value mapped to the low end of the ramp.
        high: Raw value mapped to the high end of the ramp. Must differ from ``low``.

    Returns:
        A float32 suitability raster in ``[0, 1]`` (NaNs preserved), same shape as input.
    """
    arr = np.asarray(raster, dtype="float64")
    if arr.ndim != 2:
        raise ValueError(f"expected a 2-D criterion raster, got shape {arr.shape}")
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(
            f"direction must be one of {_VALID_DIRECTIONS!r}, got {direction!r}"
        )
    if high == low:
        raise ValueError(
            f"normalisation breakpoints must differ (low={low}, high={high})"
        )

    frac = (arr - low) / (high - low)
    frac = np.clip(frac, 0.0, 1.0)
    if direction == COST:
        frac = 1.0 - frac
    return frac.astype("float32")


def ahp_priority_vector(
    matrix: np.ndarray,
) -> Tuple[np.ndarray, float, float, float]:
    """Derive AHP priority weights + consistency diagnostics from a pairwise matrix.

    The priority (weight) vector is the *normalised-column mean* estimate of the principal
    right eigenvector: normalise each column to sum 1, then average the rows. This is exact
    for a perfectly consistent matrix and a standard close approximation otherwise. Weights
    are returned already summing to 1.

    Consistency follows Saaty:

    * ``lambda_max = mean_i( (A w)_i / w_i )`` (the principal eigenvalue estimate),
    * ``CI = (lambda_max - n) / (n - 1)`` (Consistency Index),
    * ``CR = CI / RI(n)`` (Consistency Ratio), with ``RI`` from
      :data:`SAATY_RANDOM_INDEX`. For ``n <= 2`` (``RI == 0``) the matrix is consistent by
      construction and ``CR`` is returned as ``0.0``.

    Args:
        matrix: An ``n x n`` positive reciprocal pairwise-comparison matrix
            (``a_ij = importance of i over j``, ``a_ji = 1 / a_ij``, diagonal 1).

    Returns:
        ``(weights, consistency_ratio, consistency_index, lambda_max)``:

        * ``weights`` -- float64 priority vector of length ``n``, summing to 1.
        * ``consistency_ratio`` -- CR (0.0 when ``RI(n) == 0``).
        * ``consistency_index`` -- CI.
        * ``lambda_max`` -- principal eigenvalue estimate.

    Raises:
        ValueError: if ``matrix`` is not square 2-D, not positive, or has no RI entry.
    """
    a = np.asarray(matrix, dtype="float64")
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise ValueError(f"pairwise matrix must be square 2-D, got shape {a.shape}")
    n = a.shape[0]
    if n == 0:
        raise ValueError("pairwise matrix must be non-empty")
    if not np.all(a > 0):
        raise ValueError("pairwise-comparison entries must all be positive")
    if n not in SAATY_RANDOM_INDEX:
        raise ValueError(
            f"no Saaty Random Index for n={n}; supported n in "
            f"{sorted(SAATY_RANDOM_INDEX)}"
        )

    col_sums = a.sum(axis=0)
    normalised = a / col_sums  # each column now sums to 1
    weights = normalised.mean(axis=1)  # row-wise mean of normalised columns
    weights = weights / weights.sum()  # guard against float drift; sum -> 1

    # Principal eigenvalue estimate: lambda_max = mean( (A w) / w ).
    aw = a @ weights
    lambda_max = float(np.mean(aw / weights))

    if n <= 2:
        # A reciprocal matrix of order <= 2 is always perfectly consistent; RI == 0 would
        # make CR a 0/0. Report CI ~ 0 and CR 0.0 explicitly.
        consistency_index = 0.0
        consistency_ratio = 0.0
    else:
        consistency_index = (lambda_max - n) / (n - 1)
        ri = SAATY_RANDOM_INDEX[n]
        consistency_ratio = consistency_index / ri if ri > 0 else 0.0

    return weights, float(consistency_ratio), float(consistency_index), lambda_max


def weighted_linear_combination(
    normalised: Sequence[np.ndarray],
    weights: Sequence[float],
) -> np.ndarray:
    """Combine normalised ``[0, 1]`` criterion rasters by their weights (WLC).

    Computes ``suitability = sum_i weight_i * normalised_i``. With inputs in ``[0, 1]`` and
    weights summing to 1 the output is itself in ``[0, 1]``. Weights are *not* re-normalised
    here -- pass an AHP priority vector (already summing to 1) from
    :func:`ahp_priority_vector`.

    Args:
        normalised: Sequence of co-registered ``[0, 1]`` suitability rasters (identical shape).
        weights: One weight per raster, same length and order as ``normalised``.

    Returns:
        A float32 WLC suitability raster, same shape as the inputs.

    Raises:
        ValueError: on length mismatch, empty input, or non-matching raster shapes.
    """
    if len(normalised) == 0:
        raise ValueError("weighted_linear_combination requires >= 1 criterion raster")
    if len(normalised) != len(weights):
        raise ValueError(
            f"got {len(normalised)} rasters but {len(weights)} weights; must match"
        )
    stack = [np.asarray(r, dtype="float64") for r in normalised]
    shape = stack[0].shape
    for i, r in enumerate(stack):
        if r.shape != shape:
            raise ValueError(
                f"criterion raster {i} has shape {r.shape}, expected {shape} "
                "(rasters must be co-registered / same grid)"
            )
    acc = np.zeros(shape, dtype="float64")
    for w, r in zip(weights, stack, strict=True):
        acc = acc + float(w) * r
    return acc.astype("float32")


def apply_exclusion_veto(
    suitability: np.ndarray,
    exclusion_mask: np.ndarray,
    excluded_value: bool = True,
) -> np.ndarray:
    """Zero out non-buildable cells: a hard Boolean veto over the WLC surface.

    Wherever ``exclusion_mask`` marks a cell excluded, ``suitability`` is set to ``0`` --
    a category-0 result no weighting can rescue, matching the "constraints as veto" step in
    Boolean-then-weighted MCDM siting.

    Args:
        suitability: 2-D WLC suitability raster.
        exclusion_mask: 2-D Boolean-like array, same shape as ``suitability``. Cells equal
            to ``excluded_value`` are vetoed.
        excluded_value: The mask value that means "excluded / not buildable" (default
            ``True``). Set ``False`` if the input mask is a *buildable* (inclusion) mask.

    Returns:
        A float32 suitability raster with excluded cells set to 0.
    """
    suit = np.asarray(suitability, dtype="float64")
    mask = np.asarray(exclusion_mask)
    if suit.shape != mask.shape:
        raise ValueError(
            f"exclusion mask shape {mask.shape} != suitability shape {suit.shape}"
        )
    excluded = mask.astype(bool) == bool(excluded_value)
    out = suit.copy()
    out[excluded] = 0.0
    return out.astype("float32")


def build_suitability_surface(
    criteria: Mapping[str, np.ndarray],
    directions: Mapping[str, str],
    breakpoints: Mapping[str, Tuple[float, float]],
    pairwise_matrix: np.ndarray,
    criterion_order: Sequence[str],
    exclusion_mask: Optional[np.ndarray] = None,
    excluded_value: bool = True,
) -> Dict[str, Any]:
    """End-to-end GIS-MCDM: normalise -> AHP-weight -> WLC -> exclusion veto.

    Pure-``numpy``, no I/O -- the raster-writing wrapper is
    :func:`export_suitability_surface`. Config-first: every criterion's direction, its
    normalisation breakpoints and the AHP pairwise matrix are arguments.

    Args:
        criteria: ``{name: 2-D raw criterion raster}``. All rasters must be co-registered.
        directions: ``{name: "benefit" | "cost"}`` for every criterion.
        breakpoints: ``{name: (low, high)}`` normalisation ramp per criterion.
        pairwise_matrix: ``n x n`` AHP pairwise-comparison matrix, in ``criterion_order``.
        criterion_order: The criterion names in the same row/col order as
            ``pairwise_matrix``; also fixes the weight-to-criterion mapping.
        exclusion_mask: Optional Boolean veto mask (same shape as the rasters).
        excluded_value: Mask value meaning "excluded" (default ``True``).

    Returns:
        Dict with ``suitability`` (float32 raster), ``weights`` (``{name: weight}``),
        ``consistency_ratio``, ``consistency_index``, ``lambda_max``,
        ``consistency_ok`` (``CR <= 0.10``), ``normalised`` (``{name: raster}``) and
        ``criterion_order``.

    Raises:
        ValueError: on unknown/missing criteria, order/size mismatch, or bad config.
    """
    order = list(criterion_order)
    if len(order) != len(set(order)):
        raise ValueError(f"criterion_order has duplicates: {order}")
    missing = [c for c in order if c not in criteria]
    if missing:
        raise ValueError(f"criteria missing rasters for: {missing}")
    matrix = np.asarray(pairwise_matrix, dtype="float64")
    if matrix.shape != (len(order), len(order)):
        raise ValueError(
            f"pairwise_matrix shape {matrix.shape} != ({len(order)}, {len(order)}) "
            "implied by criterion_order"
        )

    normalised: Dict[str, np.ndarray] = {}
    for name in order:
        if name not in directions:
            raise ValueError(f"no direction of preference for criterion {name!r}")
        if name not in breakpoints:
            raise ValueError(f"no normalisation breakpoints for criterion {name!r}")
        low, high = breakpoints[name]
        normalised[name] = normalise_criterion(
            criteria[name], directions[name], low, high
        )

    weights_vec, cr, ci, lam = ahp_priority_vector(matrix)
    weights = {name: float(w) for name, w in zip(order, weights_vec, strict=True)}

    suitability = weighted_linear_combination(
        [normalised[name] for name in order],
        [weights[name] for name in order],
    )

    if exclusion_mask is not None:
        suitability = apply_exclusion_veto(
            suitability, exclusion_mask, excluded_value=excluded_value
        )

    return {
        "suitability": suitability,
        "weights": weights,
        "consistency_ratio": cr,
        "consistency_index": ci,
        "lambda_max": lam,
        "consistency_ok": cr <= CR_ACCEPTANCE_THRESHOLD,
        "normalised": normalised,
        "criterion_order": order,
    }


def export_suitability_surface(
    criteria: Mapping[str, np.ndarray],
    directions: Mapping[str, str],
    breakpoints: Mapping[str, Tuple[float, float]],
    pairwise_matrix: np.ndarray,
    criterion_order: Sequence[str],
    bbox: BBox,
    out_path: str | Path,
    exclusion_mask: Optional[np.ndarray] = None,
    excluded_value: bool = True,
    crs: str = DEFAULT_CRS,
    manifest_path: Optional[str | Path] = None,
    manifest_name: str = "DutchBay/GIS/suitability",
) -> Dict[str, Any]:
    """Compute the MCDM suitability surface and export a provenance-stamped GeoTIFF.

    Wraps :func:`build_suitability_surface` with the #20 raster/manifest helpers. Writes the
    suitability GeoTIFF, its ``.prov.json`` sidecar (via :func:`write_geotiff`) and -- when
    ``manifest_path`` is given -- a ``DataLake_Manifest_All.json`` entry.

    Args:
        criteria, directions, breakpoints, pairwise_matrix, criterion_order,
        exclusion_mask, excluded_value: see :func:`build_suitability_surface`.
        bbox: ``(west, south, east, north)`` for the (co-registered) criterion grid.
        out_path: Output ``.tif`` path for the suitability raster.
        crs: CRS for the export (default EPSG:4326).
        manifest_path: If given, append/refresh a manifest entry.
        manifest_name: Dataset name for the manifest entry.

    Returns:
        The :func:`build_suitability_surface` result dict augmented with
        ``suitability_path``, ``bbox``, ``crs``, ``consistency_warning`` (a message string
        when ``CR > 0.10``, else ``None``) and, if written, ``manifest_path``. The raster
        arrays (``suitability`` and ``normalised``) remain available to the caller.
    """
    result = build_suitability_surface(
        criteria=criteria,
        directions=directions,
        breakpoints=breakpoints,
        pairwise_matrix=pairwise_matrix,
        criterion_order=criterion_order,
        exclusion_mask=exclusion_mask,
        excluded_value=excluded_value,
    )

    cr = result["consistency_ratio"]
    consistency_warning: Optional[str] = None
    if cr > CR_ACCEPTANCE_THRESHOLD:
        consistency_warning = (
            f"AHP consistency ratio CR={cr:.4f} exceeds Saaty's "
            f"{CR_ACCEPTANCE_THRESHOLD:.2f} threshold; revise the pairwise judgements "
            "before trusting these weights."
        )

    order = result["criterion_order"]
    provenance: Dict[str, Any] = {
        "method": "gis_mcdm_ahp_weighted_linear_combination",
        "criteria": ",".join(order),
        "directions": ",".join(f"{c}={directions[c]}" for c in order),
        "breakpoints": ",".join(
            f"{c}=[{breakpoints[c][0]},{breakpoints[c][1]}]" for c in order
        ),
        "weights": ",".join(f"{c}={result['weights'][c]:.6f}" for c in order),
        "ahp_lambda_max": f"{result['lambda_max']:.6f}",
        "ahp_consistency_index": f"{result['consistency_index']:.6f}",
        "ahp_consistency_ratio": f"{cr:.6f}",
        "ahp_consistency_ok": str(result["consistency_ok"]),
        "ahp_priority_method": "normalised_column_mean",
        "cr_threshold": f"{CR_ACCEPTANCE_THRESHOLD:.2f}",
        "exclusion_applied": str(exclusion_mask is not None),
        "note": (
            "KPI-neutral GIS-MCDM siting-suitability surface (AHP weights + WLC, Boolean "
            "exclusion veto). Not consumed by any AEP/energy/finance calc. "
            "Method transfer only from Cunden et al. 2020 (Energy 118533) -- flat coastal "
            "DutchBay, not mountainous terrain."
        ),
    }
    if consistency_warning is not None:
        provenance["ahp_consistency_warning"] = consistency_warning

    written = write_geotiff(
        result["suitability"], bbox, out_path, crs=crs, provenance=provenance
    )

    result["suitability_path"] = str(written)
    result["bbox"] = list(bbox)
    result["crs"] = crs
    result["consistency_warning"] = consistency_warning

    if manifest_path is not None:
        west, south, east, north = bbox
        nrows, ncols = result["suitability"].shape
        resolution = (east - west) / ncols if ncols else 0.0
        entry = build_manifest_entry(
            name=manifest_name,
            bbox=bbox,
            resolution_deg=resolution,
            variables=("suitability",),
            paths={"suitability": str(written)},
            provenance=provenance,
            crs=crs,
        )
        manifest = append_manifest(manifest_path, [entry])
        result["manifest_path"] = str(manifest)

    return result
