"""Shared exceedance-probability primitives (P50/P75/P90 build-up).

A single, dependency-free home for the normal-distribution exceedance z-scores and
the P_x formula used by BOTH resource producers' IEC-style uncertainty build-ups
(``wind_resource.bankable_aep`` and ``solar_resource.exceedance``). Keeping one table
here — rather than a copy per technology — means a future edit can never let the wind
and solar exceedance maths silently diverge (DRY / CCCDIR). A parity test pins both
producers to this table.

Convention (matching IEC 61400-15-2 for wind and IEC 61724-1 / IEA-PVPS Task 13 for
solar): exceedance levels are normal-distribution quantiles applied to a P50 mean with a
relative (percent-of-P50) 1-sigma::

    P_x = P50 * (1 - z_x * sigma_pct / 100)

so a higher exceedance probability (P90 ⊃ P75 ⊃ P50) yields a *lower* energy. This is
the bankable (lender) convention; it is deliberately the normal, not lognormal, model —
the same choice both producers make.
"""

from __future__ import annotations

from typing import Mapping

__all__ = ["EXCEEDANCE_Z", "exceedance_value"]

#: Normal-distribution z-scores for one-sided exceedance probabilities P_x.
#: ``z_50 = 0`` (the mean), ``z_90 = 1.2816`` (the lender-standard downside), etc.
EXCEEDANCE_Z: Mapping[int, float] = {
    50: 0.0,
    75: 0.6745,
    90: 1.2816,
    95: 1.6449,
    99: 2.3263,
}


def exceedance_value(p50: float, sigma_pct: float, z: float) -> float:
    """Return the P_x value for a P50 mean, a relative 1-sigma, and a z-score.

    Args:
        p50: The P50 (median/mean) quantity (any unit; GWh in the producers).
        sigma_pct: The combined 1-sigma uncertainty as a percent of ``p50``.
        z: The exceedance z-score (e.g. ``EXCEEDANCE_Z[90]``).

    Returns:
        ``p50 * (1 - z * sigma_pct / 100)`` — the same unit as ``p50``.
    """
    return p50 * (1.0 - z * sigma_pct / 100.0)
