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

GWTF: config-first, fully typed, fail-loud on bad input (CESSPIT), no ``argparse``/
``input()``, pure/unit-testable (no network, no finance imports).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np

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


def build_wind_rose(
    wd_series: Sequence[float],
    n_sectors: int = 12,
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

    Raises:
        ValueError: If ``n_sectors < 1``, or if no valid (non-NaN) directions
            remain after filtering (fail loud — never emit an empty rose).
    """
    if n_sectors < 1:
        raise ValueError(f"n_sectors must be >= 1, got {n_sectors}")

    arr = np.asarray(list(wd_series), dtype=float)
    arr = arr[~np.isnan(arr)]
    n_samples = int(arr.size)
    if n_samples == 0:
        raise ValueError(
            "wind rose needs at least one non-NaN wind direction; got none."
        )

    width = 360.0 / n_sectors
    # Centre the first sector on North: shift by half a sector so a bearing of
    # 0 deg falls in sector 0, then floor-divide into sector indices.
    wrapped = np.mod(arr, 360.0)
    idx = np.floor(np.mod(wrapped + width / 2.0, 360.0) / width).astype(int)
    idx = np.clip(idx, 0, n_sectors - 1)

    counts = np.bincount(idx, minlength=n_sectors)[:n_sectors].astype(int)
    freq = counts.astype(float) / float(n_samples)

    centers: List[float] = [round(i * width, 4) for i in range(n_sectors)]
    labels: List[str] = [_sector_label(c, n_sectors) for c in centers]
    prevailing = centers[int(np.argmax(counts))]

    return {
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


__all__ = ["build_wind_rose", "ROSE_PROVENANCE_NOTE"]
