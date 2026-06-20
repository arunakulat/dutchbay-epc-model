"""Monte Carlo AEP from an ECMWF-derived Weibull (#24).

Fits a Weibull (A scale, k shape) to a hub-height (ws150) wind-speed series — in
production from :mod:`wind_resource.era5_retrieval` (ECMWF ERA5) — then samples
plausible annual resources around the fit, computes each synthetic year's net AEP
through the certified OEM curve + loss stack, and reports the bankability
exceedance percentiles (P50/P75/P90/P99) plus a summary CSV.

P-values use the wind **exceedance** convention: P90 is the AEP exceeded in 90%
of years — i.e. the 10th percentile of the distribution (conservative).

Method note: each Monte-Carlo draw is a plausible annual Weibull resource
``(A_i, k_i)``; its AEP is computed analytically via the OEM curve
(:func:`analytics.wind.aep_tornado.gross_aep_farm_gwh`), so the base case is
method-consistent with the canonical ~402.6 GWh, and the spread reflects
resource uncertainty (not Monte-Carlo sampling noise).

Context:
    Sprint 10 - Issue #24 (Monte Carlo AEP from ECMWF-derived Weibull).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gamma
from pathlib import Path
from typing import Any, Dict, Mapping

import numpy as np
import pandas as pd

from analytics.power_curves.oem_parser import parse_power_curve
from analytics.wind.aep_tornado import gross_aep_farm_gwh
from analytics.wind.losses_model import apply_losses

# Exceedance percentile -> distribution percentile (P90 = 10th pct, conservative).
EXCEEDANCE_TO_PERCENTILE = {"p50": 50.0, "p75": 25.0, "p90": 10.0, "p99": 1.0}


@dataclass(frozen=True)
class WeibullFit:
    """A Weibull fit to a wind-speed series."""

    a: float  # scale (m/s)
    k: float  # shape
    mean_ws: float
    n_obs: int


def fit_weibull_from_series(ws: Any) -> WeibullFit:
    """Fit a Weibull to a wind-speed series by the Justus method of moments.

    Args:
        ws: 1-D array-like of wind speeds (m/s) — e.g. ECMWF ws150.

    Returns:
        A :class:`WeibullFit` (scale ``a``, shape ``k``, mean, sample count).

    Raises:
        ValueError: If there are fewer than 10 valid samples or the mean is ≤ 0.
    """
    arr = np.asarray(ws, dtype=float)
    arr = arr[np.isfinite(arr) & (arr >= 0.0)]
    if arr.size < 10:
        raise ValueError(
            f"Need >=10 valid wind-speed samples to fit Weibull, got {arr.size}"
        )
    mean = float(arr.mean())
    std = float(arr.std())
    if mean <= 0.0:
        raise ValueError("Mean wind speed must be positive to fit a Weibull")
    k = float((std / mean) ** -1.086)  # Justus (1978) approximation
    a = mean / gamma(1.0 + 1.0 / k)
    return WeibullFit(a=a, k=k, mean_ws=mean, n_obs=int(arr.size))


def run_mc_aep(
    fit: WeibullFit,
    *,
    n_turbines: int,
    capacity_mw: float,
    losses: Mapping[str, Any],
    curve_key: str,
    n_samples: int = 2000,
    weibull_uncertainty_pct: float = 6.0,
    air_density_kgm3: float = 1.225,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run the Monte-Carlo AEP simulation around a Weibull fit.

    Args:
        fit: The Weibull fit (from :func:`fit_weibull_from_series`).
        n_turbines: Number of turbines.
        curve_key: power_curves.yaml slug for THIS project's turbine (required;
            from resource.power_curve.curve_key — no hardcoded Envision curve).
        capacity_mw: Per-turbine rated capacity (MW) — unused by the analytic AEP
            but kept for interface clarity / future CF reporting.
        losses: ``resource.losses`` mapping applied via the #23 losses model.
        n_samples: Monte-Carlo sample count.
        weibull_uncertainty_pct: ± relative 1-sigma on A and k.
        air_density_kgm3: Air density for the OEM curve. Defaults to the IEC
            reference (1.225) to match the canonical AEP basis; the site-density
            correction is not applied in the canonical v14 chain (tracked
            separately). Pass the site value (e.g. 1.15) to apply it.
        seed: RNG seed (reproducible).

    Returns:
        Dict with ``percentiles`` (p50/p75/p90/p99, exceedance), ``mean``,
        ``std``, ``cv``, ``n_samples`` and the ``weibull_fit``.
    """
    rng = np.random.RandomState(seed)
    curve = parse_power_curve(curve_key, air_density_kgm3=air_density_kgm3)
    curve_ws = curve["wind_speed_ms"].to_numpy()
    curve_power = curve["power_kw"].to_numpy()

    sigma = weibull_uncertainty_pct / 100.0
    a_samples = np.clip(rng.normal(fit.a, fit.a * sigma, n_samples), 1.0, 20.0)
    k_samples = np.clip(rng.normal(fit.k, fit.k * sigma, n_samples), 1.2, 4.0)

    aeps = np.empty(n_samples, dtype=float)
    for i in range(n_samples):
        gross = gross_aep_farm_gwh(
            float(a_samples[i]), float(k_samples[i]), curve_ws, curve_power, n_turbines
        )
        aeps[i] = apply_losses(gross, losses).net_aep_gwh

    percentiles = {
        name: float(np.percentile(aeps, p))
        for name, p in EXCEEDANCE_TO_PERCENTILE.items()
    }
    mean = float(aeps.mean())
    std = float(aeps.std())
    return {
        "percentiles": percentiles,
        "mean": mean,
        "std": std,
        "cv": std / mean if mean else 0.0,
        "n_samples": n_samples,
        "weibull_fit": {"a": fit.a, "k": fit.k, "mean_ws": fit.mean_ws},
    }


def write_mc_summary_csv(results: Mapping[str, Any], output_path: str) -> Path:
    """Write the MC-AEP summary to CSV (e.g. ``DutchBay_AEP_MC_Summary.csv``)."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    p = results["percentiles"]
    rows = [
        {"metric": "P50_net_aep_gwh", "value": round(p["p50"], 3)},
        {"metric": "P75_net_aep_gwh", "value": round(p["p75"], 3)},
        {"metric": "P90_net_aep_gwh", "value": round(p["p90"], 3)},
        {"metric": "P99_net_aep_gwh", "value": round(p["p99"], 3)},
        {"metric": "mean_net_aep_gwh", "value": round(results["mean"], 3)},
        {"metric": "std_net_aep_gwh", "value": round(results["std"], 3)},
        {"metric": "cv", "value": round(results["cv"], 4)},
        {"metric": "weibull_a", "value": round(results["weibull_fit"]["a"], 3)},
        {"metric": "weibull_k", "value": round(results["weibull_fit"]["k"], 3)},
        {"metric": "n_samples", "value": int(results["n_samples"])},
    ]
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


__all__ = [
    "WeibullFit",
    "EXCEEDANCE_TO_PERCENTILE",
    "fit_weibull_from_series",
    "run_mc_aep",
    "write_mc_summary_csv",
]
