"""Fit a 2-parameter Weibull to a wind-speed series + drift vs a declared baseline.

The ARCO single-point ERA5 path (:mod:`wind_resource.era5_retrieval`) produces an
hourly hub-height wind-speed *timeseries*; the canonical lender AEP engine
(:func:`analytics.wind.aep_summary_builder.build_aep_summary_from_config`) instead
consumes a *declared* Weibull ``(A, k)``. This module bridges the two: it fits an
``(A_fit, k_fit)`` on the ARCO series (same MLE as
:meth:`wind_resource.wind_analyzer.WindAnalyzer.fit_weibull` — ``scipy weibull_min``
with ``floc=0``) and reports the **drift** of that fit against the scenario's
declared ``wind_resource.weibull_a/k``.

Per project policy the fit does NOT overwrite the declared baseline (which backs the
auditable 483.6 GWh headline). It runs in VALIDATE mode: surface the drift so silent
resource erosion is caught; adopting a new ``(A, k)`` is a deliberate, dated config
edit, not an automatic side effect.

GWTF: config-first, fully typed, no hardcoded site constants.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats

#: Weibull scale parameter A == scipy ``weibull_min`` ``scale``; shape k == ``c``.
FitMethod = str


@dataclass(frozen=True)
class WeibullFit:
    """An MLE Weibull fit on a wind-speed series (A = scale m/s, k = shape)."""

    weibull_a: float  # scale (m/s)
    weibull_k: float  # shape (dimensionless)
    mean_ws_ms: float
    std_ws_ms: float  # Weibull-implied std (consistent with A,k), not raw sample std
    r_squared: float
    ks_pvalue: float
    n_samples: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "weibull_a": round(self.weibull_a, 4),
            "weibull_k": round(self.weibull_k, 4),
            "mean_ws_ms": round(self.mean_ws_ms, 4),
            "std_ws_ms": round(self.std_ws_ms, 4),
            "r_squared": round(self.r_squared, 5),
            "ks_pvalue": round(self.ks_pvalue, 5),
            "n_samples": self.n_samples,
        }


@dataclass(frozen=True)
class WeibullDrift:
    """Relative drift of a fitted Weibull vs the declared scenario baseline."""

    a_declared: float
    k_declared: float
    a_fit: float
    k_fit: float
    a_drift_pct: float
    k_drift_pct: float
    tolerance_pct: float
    within_tolerance: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "a_declared": self.a_declared,
            "k_declared": self.k_declared,
            "a_fit": round(self.a_fit, 4),
            "k_fit": round(self.k_fit, 4),
            "a_drift_pct": round(self.a_drift_pct, 3),
            "k_drift_pct": round(self.k_drift_pct, 3),
            "tolerance_pct": self.tolerance_pct,
            "within_tolerance": self.within_tolerance,
        }


def weibull_std(weibull_a: float, weibull_k: float) -> float:
    """Standard deviation implied by a Weibull ``(A, k)`` (m/s).

    ``std = A * sqrt(Γ(1 + 2/k) - Γ(1 + 1/k)^2)``. Used for the ``ws150_std_ms``
    interface field so it is consistent with the fitted distribution rather than the
    raw (clipped) sample std.
    """
    g1 = math.gamma(1.0 + 1.0 / weibull_k)
    g2 = math.gamma(1.0 + 2.0 / weibull_k)
    return float(weibull_a) * math.sqrt(max(g2 - g1 * g1, 0.0))


def fit_weibull_on_series(
    series: pd.DataFrame, ws_column: str, method: FitMethod = "mle"
) -> WeibullFit:
    """Fit a 2-parameter Weibull to ``series[ws_column]`` (MLE, ``floc=0``).

    Mirrors :meth:`wind_resource.wind_analyzer.WindAnalyzer.fit_weibull` so the fitted
    ``(A, k)`` are method-consistent with the rest of the wind stack.

    Raises:
        ValueError: if ``method`` is unsupported, the column is missing, or the series
            has no finite positive wind speeds to fit.
    """
    if method != "mle":
        raise ValueError(f"Unsupported Weibull fit method: {method!r} (only 'mle').")
    if ws_column not in series.columns:
        raise ValueError(f"Series has no column {ws_column!r}; got {list(series.columns)}.")

    ws_data = pd.to_numeric(series[ws_column], errors="coerce").dropna()
    ws_data = ws_data[ws_data > 0.0]
    if len(ws_data) < 2:
        raise ValueError(
            f"Need >=2 positive wind speeds to fit a Weibull; got {len(ws_data)}."
        )
    arr = np.asarray(ws_data, dtype=float)

    shape_k, _loc, scale_c = stats.weibull_min.fit(arr, floc=0)

    sorted_ws = np.sort(arr)
    theoretical_cdf = stats.weibull_min.cdf(sorted_ws, shape_k, loc=0, scale=scale_c)
    empirical_cdf = np.arange(1, len(sorted_ws) + 1) / len(sorted_ws)
    ss_res = float(np.sum((empirical_cdf - theoretical_cdf) ** 2))
    ss_tot = float(np.sum((empirical_cdf - np.mean(empirical_cdf)) ** 2))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    _ks_stat, ks_pvalue = stats.kstest(
        arr, lambda x: stats.weibull_min.cdf(x, shape_k, loc=0, scale=scale_c)
    )

    return WeibullFit(
        weibull_a=float(scale_c),
        weibull_k=float(shape_k),
        mean_ws_ms=float(arr.mean()),
        std_ws_ms=weibull_std(float(scale_c), float(shape_k)),
        r_squared=float(r_squared),
        ks_pvalue=float(ks_pvalue),
        n_samples=int(len(arr)),
    )


def weibull_drift(
    a_fit: float,
    k_fit: float,
    a_declared: float,
    k_declared: float,
    tolerance_pct: float,
) -> WeibullDrift:
    """Relative drift of a fitted ``(A, k)`` against the declared baseline.

    Drift is ``100 * (fit - declared) / declared`` for each parameter; the result is
    ``within_tolerance`` when BOTH absolute drifts are <= ``tolerance_pct``. This is a
    VALIDATE-mode signal — it never mutates the declared values.
    """
    a_drift = 100.0 * (a_fit - a_declared) / a_declared
    k_drift = 100.0 * (k_fit - k_declared) / k_declared
    within = abs(a_drift) <= tolerance_pct and abs(k_drift) <= tolerance_pct
    return WeibullDrift(
        a_declared=float(a_declared),
        k_declared=float(k_declared),
        a_fit=float(a_fit),
        k_fit=float(k_fit),
        a_drift_pct=float(a_drift),
        k_drift_pct=float(k_drift),
        tolerance_pct=float(tolerance_pct),
        within_tolerance=bool(within),
    )


__all__ = [
    "WeibullFit",
    "WeibullDrift",
    "weibull_std",
    "fit_weibull_on_series",
    "weibull_drift",
]
