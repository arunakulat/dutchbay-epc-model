"""Analytic gross farm AEP: a Weibull resource integrated over a power curve.

This is the main wind engine's home for the integral that the AEP summary builder
(:mod:`wind_resource.aep_summary`), the AEP tornado and Monte Carlo modules in
``analytics/wind/``, the met-mast transfer and the Blue Whale wind scripts all share.
It moved here from ``analytics/wind/aep_tornado.py`` unchanged (#1615, owner ruling of
2026-11-16), so every live caller imports it from ``wind_resource/``.
``analytics.wind.aep_tornado`` re-exports these names, so there is one implementation.

Context:
    Sprint 10 - Issue #25 (AEP tornado sensitivities); moved under #1615.
"""

from __future__ import annotations

import numpy as np

HOURS_PER_YEAR = 8760.0
# Fine wind-speed grid (m/s) for the analytic Weibull integral. Starts just above 0 (not
# 0.0): the Weibull pdf (v/a)**(k-1) is +inf at v=0 for shape k<1, which would poison the
# trapezoid normalisation and return NaN gross AEP. The 1e-4 floor (the bankable engine
# uses 0.01) keeps the integral finite for all k; for k>=1 the pdf is ~0 near zero so the
# floor shifts net AEP by <1e-3 GWh/turbine — negligible at reporting precision (canonical
# base AEP 473.84 GWh unchanged) but NOT bit-for-bit identical to a 0.01 lower bound.
_WS_GRID = np.arange(1e-4, 30.0001, 0.05)


def _weibull_pdf(v: np.ndarray, a: float, k: float) -> np.ndarray:
    pdf = (k / a) * (v / a) ** (k - 1.0) * np.exp(-((v / a) ** k))
    return np.asarray(pdf, dtype=float)


def gross_aep_farm_gwh(
    weibull_a: float,
    weibull_k: float,
    curve_ws: np.ndarray,
    curve_power_kw: np.ndarray,
    n_turbines: int,
) -> float:
    """Analytic gross farm AEP (GWh) from a Weibull and a power curve.

    Shared with the #24 Monte-Carlo AEP module so both use the same method.

    WIND-3 (#484): cut-out is handled IMPLICITLY here via ``np.interp(..., right=0.0)`` — the
    supplied power curve must already encode the cut-out (its last point is the cut-out speed,
    above which interp returns 0). ``wind_resource.bankable_aep.gross_aep_weibull`` instead
    zeroes power EXPLICITLY outside ``[cut_in, cut_out]``. The two agree to well within 0.1%
    on every curve in the store, so this is a documented, bounded modelling-style difference,
    not a bug; the committed headline (464.3 GWh) is the FROZEN
    ``aep_summary_dutchbay_10mw.json`` value and is unaffected by either integrator at runtime.

    That agreement is now EXECUTED rather than asserted here (#1281):
    ``tests/analytics/test_gross_aep_integrator_parity.py`` pins it at 0.05% across the whole
    curve store and a sweep of the plausible site resource range. This is the module a reader
    should open for the live gross-AEP maths — ``bankable_aep`` carries the cross-check
    implementation, deliberately kept off the production path so it can act as its oracle.
    """
    pdf = _weibull_pdf(_WS_GRID, weibull_a, weibull_k)
    pdf = pdf / float(np.trapezoid(pdf, _WS_GRID))  # renormalise over the grid
    power = np.interp(_WS_GRID, curve_ws, curve_power_kw, left=0.0, right=0.0)
    mean_power_kw = float(np.trapezoid(power * pdf, _WS_GRID))
    per_turbine_gwh = mean_power_kw * HOURS_PER_YEAR / 1e6
    return per_turbine_gwh * n_turbines


__all__ = ["HOURS_PER_YEAR", "gross_aep_farm_gwh"]
