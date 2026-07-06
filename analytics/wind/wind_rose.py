"""Directional wind-rose OUTPUT builder — display/provenance only (issue #742).

Bins a series of met-convention wind directions (degrees, 0 = North, 90 = East,
the ``wd_10m``/``wd_100m`` columns produced by
:meth:`wind_resource.era5_fetcher.ERA5DataFetcher._calculate_wind_metrics`) into
``n_sectors`` equal-width directional sectors and returns the per-sector
frequency. This is a **pure output** artifact for the AEP-summary provenance /
diagnostics block: it consumes no finance config and feeds no cashflow or billed
quantity. It never scales the AEP.

Honesty (WIND-provenance discipline): a rose built from **single grid-cell ERA5
reanalysis** is directionally COARSE — it is one 0.25° reanalysis point, NOT a
directionally mast-validated on-site measurement. The returned block labels itself
as such (:data:`ROSE_PROVENANCE_NOTE`) so a lender never mistakes it for a
bankable, measurement-based rose.

Optional speed enrichment (issue #826, KPI-neutral): when a co-indexed wind-SPEED
series is supplied, the rose additionally reports per-sector **mean speed**, an
**energy rose** (per-sector fraction of the total energy flux, weighted by
frequency × ⟨v³⟩), and an optional **sectorwise Weibull** ``(A, k)`` fit. Calm
samples (speed ≤ ``calm_limit``) are excluded first. This is still display /
provenance only — it constructs a vector, it does not feed the wake loss or scale
the AEP. When NO speed series is supplied the output is byte-identical to the
original direction-only rose.

GWTF: config-first, fully typed, fail-loud on bad input (CESSPIT), no ``argparse``/
``input()``, pure/unit-testable (no network, no finance imports).
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats

#: Default calm-wind cut-off (m/s). When a wind-SPEED series is supplied, samples
#: at or below this speed are excluded before binning: calm air carries no reliable
#: direction and no meaningful energy. This ~2 m/s value is an **independent**
#: general met convention (roughly a light-breeze floor, below typical turbine
#: cut-in) — it is **NOT** a ``python-windrose`` default, whose ``calm_limit``
#: defaults to ``None`` (i.e. no calm filtering). We disclose our own choice rather
#: than silently inherit a library one.
DEFAULT_CALM_LIMIT_MS: float = 2.0

#: Minimum in-sector sample count required to attempt a per-sector Weibull MLE.
#: Below this the 2-parameter fit is too unstable to be meaningful, so the sector
#: reports ``None`` (fail-soft — a sparse sector never crashes the rose).
_MIN_SECTOR_WEIBULL_N: int = 10

#: Minimum coefficient of variation (std / mean) a sector's speeds must have before
#: a Weibull MLE is attempted. Near-constant data (CV below this) drives the shape
#: ``k`` toward a physically meaningless spike (order 1e5+) and trips a scipy
#: "catastrophic cancellation" warning; such a sector reports ``None`` instead.
_MIN_SECTOR_WEIBULL_CV: float = 1e-3

#: Plausibility cap on the fitted Weibull shape ``k``. Real onshore wind ``k`` is
#: ~1.5–3; anything above this is a degenerate fit, not a physical shape, and is
#: rejected (report ``None``) so a bogus millions-scale ``k`` can never reach a
#: display block.
_MAX_SECTOR_WEIBULL_K: float = 50.0

#: Compass labels for the canonical 8/16-sector roses (met convention, N = 0°).
_COMPASS_16: tuple[str, ...] = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)

#: Provenance caveat stamped into every rose block (#742 honesty discipline).
ROSE_PROVENANCE_NOTE: str = (
    "Directional frequencies derived from single grid-cell ERA5 reanalysis "
    "(~0.25 deg), not directionally mast-validated on-site measurement; "
    "coarse — indicative of prevailing sector only."
)


def _sector_label(center_deg: float, n_sectors: int) -> str:
    """Compass label for a sector centre when it maps cleanly onto the 16-point rose.

    Returns a compass abbreviation (``"N"``, ``"SSW"``, ...) for the 8- and
    16-sector cases (whose centres align with the 16-point compass); otherwise
    an empty string (numeric ``sector_deg`` still fully identifies the sector).
    """
    if n_sectors in (8, 16):
        step = 16 // n_sectors
        idx = int(round(center_deg / 22.5)) % 16
        if idx % step == 0:
            return _COMPASS_16[idx]
    return ""


def _sector_index(wrapped_deg: np.ndarray, n_sectors: int) -> np.ndarray:
    """Map wrapped-into-[0,360) bearings onto North-centred sector indices.

    Shared by the direction-only and speed-enriched paths so both bin identically:
    shift by half a sector so a bearing of 0 deg lands in sector 0, floor-divide,
    then clip to guard the ``360.0``/rounding edge.
    """
    width = 360.0 / n_sectors
    idx = np.floor(np.mod(wrapped_deg + width / 2.0, 360.0) / width).astype(int)
    # np.clip is typed as returning Any under strict mypy; pin to a concrete
    # int ndarray so the declared return type is not Any (warn_return_any).
    return np.asarray(np.clip(idx, 0, n_sectors - 1), dtype=int)


def _sector_weibull(speeds: np.ndarray) -> Optional[Dict[str, float]]:
    """Per-sector 2-parameter Weibull ``(A, k)`` MLE, or ``None`` if too sparse.

    Uses the repo convention ``scipy.stats.weibull_min.fit(x, floc=0)`` (identical
    to :mod:`wind_resource.weibull_fit`): the returned ``shape`` is ``k`` and the
    returned ``scale`` is the Weibull ``A`` (m/s). Reports ``None`` (never raises) for
    any sector that is:

    - too sparse (< :data:`_MIN_SECTOR_WEIBULL_N` positive samples);
    - near-constant (coefficient of variation < :data:`_MIN_SECTOR_WEIBULL_CV`) —
      whose MLE otherwise emits a millions-scale, physically meaningless ``k``;
    - a fit that fails / warns (scipy ``RuntimeWarning`` is promoted to an error),
      returns non-finite params, or returns an implausible shape
      (``k`` > :data:`_MAX_SECTOR_WEIBULL_K`).
    """
    positive = speeds[speeds > 0.0]
    if positive.size < _MIN_SECTOR_WEIBULL_N:
        return None

    # Degenerate/near-constant guard: a sector whose speeds are almost identical has
    # no real Weibull shape — the MLE drives ``k`` toward a meaningless spike (order
    # 1e5+) that IS finite and positive (so it would escape the checks below) and
    # trips scipy's "catastrophic cancellation" moment warning. Reject before fitting.
    mean_v = float(positive.mean())
    if mean_v <= 0.0 or float(positive.std()) / mean_v < _MIN_SECTOR_WEIBULL_CV:
        return None

    # Promote scipy's numerical-instability RuntimeWarning to an error so a bogus fit
    # can never hide behind a silently-swallowed warning; treat it as "no fit".
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            shape_k, _loc, scale_a = stats.weibull_min.fit(positive, floc=0)
    except Exception:  # pragma: no cover - guarded above; belt-and-braces
        return None

    if not (np.isfinite(shape_k) and np.isfinite(scale_a)) or scale_a <= 0.0:
        return None
    # Plausibility cap: reject a non-physical shape (real onshore k ~1.5–3).
    if shape_k > _MAX_SECTOR_WEIBULL_K:
        return None
    return {
        "weibull_a": round(float(scale_a), 4),
        "weibull_k": round(float(shape_k), 4),
    }


def build_wind_rose(
    wd_series: Sequence[float],
    n_sectors: int = 12,
    ws_series: Optional[Sequence[float]] = None,
    calm_limit: float = DEFAULT_CALM_LIMIT_MS,
) -> Dict[str, Any]:
    """Bin met-convention wind directions into ``n_sectors`` → directional frequency.

    Directions are wrapped into ``[0, 360)`` and assigned to equal-width sectors
    CENTRED on ``0, 360/n, 2*360/n, ...`` degrees (so the first sector straddles
    North, the standard wind-rose convention). NaNs are dropped.

    Args:
        wd_series: Wind directions in degrees, met convention (0 = North,
            clockwise), e.g. an ERA5 ``wd_100m`` column.
        n_sectors: Number of equal-width sectors (default 12 → 30° each). Common
            choices: 8 (45°), 12 (30°), 16 (22.5°).
        ws_series: OPTIONAL co-indexed wind SPEEDS (m/s). When supplied, calm
            samples (``speed <= calm_limit``) are excluded before binning and the
            rose is enriched with per-sector mean speed, an energy rose, and a
            sectorwise Weibull fit (see Returns). Must be the same length as
            ``wd_series``. When ``None`` (default) the output is byte-identical to
            the original direction-only rose.
        calm_limit: Calm-wind cut-off in m/s (default :data:`DEFAULT_CALM_LIMIT_MS`
            = 2.0). Only used when ``ws_series`` is supplied. See that constant for
            why ~2 m/s is an INDEPENDENT met convention, not a windrose default.

    Returns:
        A pure, JSON-serialisable dict:

        - ``n_sectors``: the sector count.
        - ``sector_width_deg``: sector width (``360 / n_sectors``).
        - ``sector_deg``: list of sector CENTRE bearings.
        - ``sector_label``: compass labels (``""`` when a sector centre does not
          map onto the 16-point compass).
        - ``count``: per-sector sample counts.
        - ``frequency``: per-sector fraction of valid samples (sums to 1.0).
        - ``n_samples``: number of valid (non-NaN) directions binned.
        - ``prevailing_sector_deg``: centre bearing of the most frequent sector.
        - ``provenance_note``: the single-cell ERA5 honesty caveat
          (:data:`ROSE_PROVENANCE_NOTE`).

        When ``ws_series`` is supplied, the following ADDITIONAL keys appear
        (the keys above keep the same meaning, now over the calm-filtered subset):

        - ``calm_limit_ms``: the calm cut-off applied.
        - ``n_calm``: number of samples dropped as calm (``speed <= calm_limit``).
        - ``mean_speed_ms``: per-sector mean wind speed (m/s); ``0.0`` for an empty
          sector.
        - ``energy_frequency``: per-sector share of the total wind-energy flux,
          ``fᵢ·⟨vᵢ³⟩`` normalised to sum 1.0 (the "energy rose"). Differs from
          ``frequency`` whenever the per-sector mean cube of speed varies.
        - ``sector_weibull``: per-sector ``{"weibull_a", "weibull_k"}`` MLE fit, or
          ``None`` for a sector with fewer than ~10 positive samples.

    Raises:
        ValueError: If ``n_sectors < 1``; if no valid direction survives filtering
            (fail loud — never emit an empty rose); or, when ``ws_series`` is
            supplied, if it is not the same length as ``wd_series``.
    """
    if n_sectors < 1:
        raise ValueError(f"n_sectors must be >= 1, got {n_sectors}")

    arr = np.asarray(list(wd_series), dtype=float)

    speeds: Optional[np.ndarray] = None
    if ws_series is not None:
        speeds = np.asarray(list(ws_series), dtype=float)
        if speeds.shape != arr.shape:
            raise ValueError(
                "ws_series must be the same length as wd_series; "
                f"got {speeds.size} speeds for {arr.size} directions."
            )

    # Drop NaN directions (and, when speeds are supplied, any sample whose speed is
    # NaN or at/below the calm cut-off) BEFORE binning — calm air has no reliable
    # direction and contributes no energy.
    if speeds is None:
        valid = ~np.isnan(arr)
    else:
        valid = ~np.isnan(arr) & ~np.isnan(speeds) & (speeds > calm_limit)

    n_calm = 0
    if speeds is not None:
        # Count of dropped-as-calm samples: finite direction & speed, but calm.
        n_calm = int(
            np.count_nonzero(
                ~np.isnan(arr) & ~np.isnan(speeds) & (speeds <= calm_limit)
            )
        )
        speeds = speeds[valid]
    arr = arr[valid]

    n_samples = int(arr.size)
    if n_samples == 0:
        raise ValueError(
            "wind rose needs at least one non-NaN wind direction; got none."
        )

    width = 360.0 / n_sectors
    # Centre the first sector on North: shift by half a sector so a bearing of
    # 0 deg falls in sector 0, then floor-divide into sector indices.
    wrapped = np.mod(arr, 360.0)
    idx = _sector_index(wrapped, n_sectors)

    counts = np.bincount(idx, minlength=n_sectors)[:n_sectors].astype(int)
    freq = counts.astype(float) / float(n_samples)

    centers: List[float] = [round(i * width, 4) for i in range(n_sectors)]
    labels: List[str] = [_sector_label(c, n_sectors) for c in centers]
    prevailing = centers[int(np.argmax(counts))]

    rose: Dict[str, Any] = {
        "n_sectors": int(n_sectors),
        "sector_width_deg": round(width, 4),
        "sector_deg": centers,
        "sector_label": labels,
        "count": [int(c) for c in counts.tolist()],
        "frequency": [round(f, 6) for f in freq.tolist()],
        "n_samples": n_samples,
        "prevailing_sector_deg": prevailing,
        "provenance_note": ROSE_PROVENANCE_NOTE,
    }

    if speeds is None:
        return rose

    # --- Speed enrichment (issue #826): mean speed, energy rose, sector Weibull ---
    mean_speed: List[float] = []
    mean_cube: np.ndarray = np.zeros(n_sectors, dtype=float)
    sector_weibull: List[Optional[Dict[str, float]]] = []
    for s in range(n_sectors):
        in_sector = speeds[idx == s]
        if in_sector.size == 0:
            mean_speed.append(0.0)
            sector_weibull.append(None)
            # mean_cube stays 0.0 → an empty sector carries no energy weight.
            continue
        mean_speed.append(round(float(in_sector.mean()), 4))
        mean_cube[s] = float(np.mean(in_sector**3))
        sector_weibull.append(_sector_weibull(in_sector))

    # Energy rose: each sector's share of total wind-power flux ∝ fᵢ · ⟨vᵢ³⟩.
    # freq already carries the per-sector frequency fᵢ; multiply by the in-sector
    # mean cube of speed and renormalise so the vector sums to 1.
    energy_weight = freq * mean_cube
    total_energy = float(energy_weight.sum())
    if total_energy > 0.0:
        energy_freq = energy_weight / total_energy
    else:  # pragma: no cover - only if every surviving speed is exactly 0
        energy_freq = np.zeros(n_sectors, dtype=float)

    rose["calm_limit_ms"] = round(float(calm_limit), 4)
    rose["n_calm"] = n_calm
    rose["mean_speed_ms"] = mean_speed
    rose["energy_frequency"] = [round(f, 6) for f in energy_freq.tolist()]
    rose["sector_weibull"] = sector_weibull
    return rose


__all__ = [
    "build_wind_rose",
    "ROSE_PROVENANCE_NOTE",
    "DEFAULT_CALM_LIMIT_MS",
]
