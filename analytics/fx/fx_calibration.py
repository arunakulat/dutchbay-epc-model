"""Calibrate the Monte-Carlo USD/LKR FX driver from historical market data.

Turns a provenance-bearing historical series (:mod:`analytics.fx.fx_history`) into
a calibrated FX spec — drift + volatility + a crisis-regime mixture — that the
Monte-Carlo engine samples instead of the hand-authored uniform bound
``fx.start_lkr_per_usd ∈ [300, 367]`` (which had zero empirical provenance). It
folds GBM-drift / regime / crisis maths into the live analytics layer.

What it produces
----------------
For the 1-year-ahead spot (the level the MC perturbs around today's pinned spot):

    spot = pinned_spot · exp(Z),   Z ~ mixture of two log-normal regimes

* **normal regime** (weight ``1 − crisis_prob``): mean = long-run annual drift,
  vol = the post-crisis "target-band" regime's annualised σ — ordinary-times risk;
* **crisis regime** (weight ``crisis_prob``): mean = drift + the realised crisis
  log-depreciation, vol = the 2022 float regime's annualised σ — the fat tail.

Plus a data-derived **drift** (``annual_depr = exp(µ_longrun) − 1``) that replaces
the hand-set 3 %/yr depreciation.

Regime segmentation (Sri Lanka USD/LKR; see the FX data-source research brief)
-----------------------------------------------------------------------------
* ``managed_float``    2005-01 → 2020-08  (pre-crisis managed float)
* ``noncredible_peg``  2020-09 → 2022-03-06  **EXCLUDED from vol** — the LKR-200 ban
  made the official rate artificially smooth (25-30 % kerb premium); its low vol is
  not real risk.
* ``float_crisis``     2022-03-07 → 2022-05-12  (the float: ~200 → ~360, the fat tail)
* ``target_band``      2022-05-13 → present  (daily middle-rate band + 2023-24 recovery)

The full regime-switching *path* simulation (Markov state per period) is a
documented future enhancement; v1 delivers a regime-aware *mixture* of the
1-year spot (distribution + drift + crisis tail), which is the material lender win.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Any, Mapping, Sequence

from analytics.fx.fx_history import (
    FXHistorySeries,
    _annualization_factor,
    resolve_fx_history,
    to_periodic,
)

logger = logging.getLogger(__name__)

#: Ordered regime windows (name, start inclusive, end inclusive or ``None`` = open).
DEFAULT_REGIMES: tuple[tuple[str, str, str | None], ...] = (
    ("managed_float", "2005-01-01", "2020-08-31"),
    ("noncredible_peg", "2020-09-01", "2022-03-06"),
    ("float_crisis", "2022-03-07", "2022-05-12"),
    ("target_band", "2022-05-13", None),
)

#: Regimes excluded from volatility/drift estimation (artificially-smooth official rate).
DEFAULT_EXCLUDED_REGIMES: frozenset[str] = frozenset({"noncredible_peg"})

#: The regime whose σ represents ordinary-times ("normal") FX risk.
NORMAL_REGIME = "target_band"
#: The regime whose σ + realised shift represent the crisis tail.
CRISIS_REGIME = "float_crisis"

_EPS = 1e-9
_CRISIS_PROB_FLOOR = 0.01
_CRISIS_PROB_CAP = 0.25


@dataclass(frozen=True)
class RegimeStats:
    """Annualised drift/vol for one regime, from log-returns within its window."""

    name: str
    start: str
    end: str | None
    n_returns: int
    mu_annual: float  # annualised mean log-return (depreciation drift)
    sigma_annual: float  # annualised stdev of log-returns
    cumulative_log_return: float  # realised log-move across the window

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "n_returns": self.n_returns,
            "mu_annual": round(self.mu_annual, 6),
            "sigma_annual": round(self.sigma_annual, 6),
            "cumulative_log_return": round(self.cumulative_log_return, 6),
        }


@dataclass(frozen=True)
class FXCalibration:
    """Calibrated FX spec for the Monte-Carlo spot driver."""

    pinned_spot: float
    horizon_years: float
    frequency: str
    provider: str
    long_run_drift_annual: float  # µ (log) over usable regimes
    annual_depr: float  # exp(µ) − 1, the decimal drift for fx.annual_depr
    crisis_prob: float  # annual probability weight of the crisis component
    crisis_log_shift: float  # additional mean log-depreciation in a crisis draw
    sigma_normal_1y: float  # 1-yr σ of the normal regime
    sigma_crisis_1y: float  # 1-yr σ of the crisis regime
    regimes: tuple[RegimeStats, ...] = field(default_factory=tuple)
    n_observations: int = 0
    date_range: tuple[str, str] = ("", "")

    def as_dict(self) -> dict[str, Any]:
        return {
            "pinned_spot": self.pinned_spot,
            "horizon_years": self.horizon_years,
            "frequency": self.frequency,
            "provider": self.provider,
            "long_run_drift_annual": round(self.long_run_drift_annual, 6),
            "annual_depr": round(self.annual_depr, 6),
            "crisis_prob": round(self.crisis_prob, 6),
            "crisis_log_shift": round(self.crisis_log_shift, 6),
            "sigma_normal_1y": round(self.sigma_normal_1y, 6),
            "sigma_crisis_1y": round(self.sigma_crisis_1y, 6),
            "n_observations": self.n_observations,
            "date_range": list(self.date_range),
            "regimes": [r.as_dict() for r in self.regimes],
        }

    def sampler(self) -> "CalibratedFXSampler":
        return CalibratedFXSampler(self)


def _in_window(date_str: str, start: str, end: str | None) -> bool:
    return date_str >= start and (end is None or date_str <= end)


def _log_returns(
    dates: Sequence[str], rates: Sequence[float]
) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for i in range(1, len(rates)):
        prev, cur = rates[i - 1], rates[i]
        if prev > 0 and cur > 0:
            out.append((dates[i], math.log(cur / prev)))
    return out


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def calibrate_fx(
    series: FXHistorySeries,
    *,
    pinned_spot: float,
    horizon_years: float = 1.0,
    frequency: str = "weekly",
    regimes: Sequence[tuple[str, str, str | None]] = DEFAULT_REGIMES,
    excluded_regimes: frozenset[str] = DEFAULT_EXCLUDED_REGIMES,
) -> FXCalibration:
    """Calibrate drift + vol + crisis mixture from a historical series.

    Args:
        series: provenance-bearing daily history (LKR per USD).
        pinned_spot: today's anchor spot the MC perturbs around (e.g. 333.79).
        horizon_years: forward horizon for the spot shock (1.0 = one year).
        frequency: return frequency for vol estimation ("weekly" recommended;
            "daily"/"monthly" supported). Must be at least weekly per the spec.
    """
    if pinned_spot <= 0:
        raise ValueError("pinned_spot must be > 0")
    if horizon_years <= 0:
        raise ValueError("horizon_years must be > 0")

    keys, vals = to_periodic(series, frequency)
    returns = _log_returns(keys, vals)
    ppy = _annualization_factor(frequency)

    regime_stats: list[RegimeStats] = []
    usable_returns: list[float] = []
    by_name: dict[str, RegimeStats] = {}
    for name, start, end in regimes:
        r_in = [r for (d, r) in returns if _in_window(d, start, end)]
        # realised log-move across the window (first→last level in-window)
        lv = [v for (k, v) in zip(keys, vals) if _in_window(k, start, end)]
        cum = (
            math.log(lv[-1] / lv[0])
            if len(lv) >= 2 and lv[0] > 0 and lv[-1] > 0
            else 0.0
        )
        mu_ann = _mean(r_in) * ppy
        sigma_ann = _stdev(r_in) * math.sqrt(ppy)
        rs = RegimeStats(name, start, end, len(r_in), mu_ann, sigma_ann, cum)
        regime_stats.append(rs)
        by_name[name] = rs
        if name not in excluded_regimes:
            usable_returns.extend(r_in)

    # Long-run drift = annualised mean log-return over usable (non-peg) regimes.
    long_run_mu = _mean(usable_returns) * ppy
    annual_depr = math.exp(long_run_mu) - 1.0

    # Volatility components (fall back to the usable-sample σ if a regime is too thin).
    overall_sigma = _stdev(usable_returns) * math.sqrt(ppy)
    normal = by_name.get(NORMAL_REGIME)
    crisis = by_name.get(CRISIS_REGIME)
    sigma_normal_ann = (
        normal.sigma_annual if (normal and normal.n_returns >= 2) else overall_sigma
    )
    sigma_crisis_ann = (
        crisis.sigma_annual
        if (crisis and crisis.n_returns >= 2)
        else max(overall_sigma, sigma_normal_ann)
    )

    # Crisis annual probability ≈ (#crisis regimes observed) / usable years, clamped.
    span_years = max(1.0, _series_span_years(series))
    n_crisis = 1 if (crisis and crisis.n_returns >= 2) else 0
    crisis_prob = (
        min(_CRISIS_PROB_CAP, max(_CRISIS_PROB_FLOOR, n_crisis / span_years))
        if n_crisis
        else 0.0
    )
    crisis_log_shift = crisis.cumulative_log_return if crisis else 0.0

    h = math.sqrt(horizon_years)
    return FXCalibration(
        pinned_spot=float(pinned_spot),
        horizon_years=float(horizon_years),
        frequency=frequency,
        provider=series.provider,
        long_run_drift_annual=long_run_mu,
        annual_depr=annual_depr,
        crisis_prob=crisis_prob,
        crisis_log_shift=crisis_log_shift,
        sigma_normal_1y=sigma_normal_ann * h,
        sigma_crisis_1y=sigma_crisis_ann * h,
        regimes=tuple(regime_stats),
        n_observations=len(series.rates),
        date_range=series.date_range,
    )


def _series_span_years(series: FXHistorySeries) -> float:
    y0 = int(series.dates[0][:4])
    y1 = int(series.dates[-1][:4])
    return max(1.0, float(y1 - y0))


def calibrate_from_config(
    config: Mapping[str, Any], pinned_spot: float
) -> FXCalibration:
    """Resolve the configured vintage and calibrate, reading any overrides under
    ``monte_carlo.fx_calibration`` (horizon_years, frequency)."""
    series = resolve_fx_history(config)
    mc = config.get("monte_carlo") if isinstance(config, Mapping) else None
    fxc = mc.get("fx_calibration") if isinstance(mc, Mapping) else {}
    fxc = fxc if isinstance(fxc, Mapping) else {}
    return calibrate_fx(
        series,
        pinned_spot=float(fxc.get("pinned_spot", pinned_spot)),
        horizon_years=float(fxc.get("horizon_years", 1.0)),
        frequency=str(fxc.get("frequency", "weekly")),
    )


class CalibratedFXSampler:
    """Maps a unit draw ``u ∈ [0,1]`` to a calibrated 1-yr spot (mixture inverse-CDF).

    Keeping the draw a unit uniform lets the MC engine source it from the existing
    stratified-LHS / common-random-number / correlation machinery: the calibrated
    distribution shape lives here, not in the sampler.
    """

    def __init__(self, calibration: FXCalibration) -> None:
        self.c = calibration
        # The LEVEL shock is centred on TODAY's spot (mean 0): the forward
        # depreciation trend is delivered separately via ``drift`` → fx.annual_depr
        # (the cashflow curve applies (1+annual_depr)^t). Centring the level on
        # pinned·(1+drift) would double-count the drift. The crisis component adds
        # the realised crisis log-depreciation as a downside-tail mean shift.
        self._normal = NormalDist(0.0, max(calibration.sigma_normal_1y, _EPS))
        self._crisis = NormalDist(
            calibration.crisis_log_shift, max(calibration.sigma_crisis_1y, _EPS)
        )

    @property
    def drift(self) -> float:
        """The data-derived ``fx.annual_depr`` decimal."""
        return self.c.annual_depr

    def _mixture_cdf(self, z: float) -> float:
        wc = self.c.crisis_prob
        return wc * self._crisis.cdf(z) + (1.0 - wc) * self._normal.cdf(z)

    def spot_from_unit(self, u: float) -> float:
        """True (monotone) inverse-CDF of the two-regime log-normal mixture.

        Inverts the mixture CDF in log-space by bisection so the mapping is
        monotone increasing in ``u`` — preserving the engine's LHS stratification
        and rank-correlation (a bucket-assignment sampler would not be monotone).
        The crisis tail therefore lands in the upper quantiles (high ``u`` → larger
        LKR/USD = rupee depreciation).
        """
        u = min(1.0 - _EPS, max(_EPS, float(u)))
        spread = 12.0 * max(self._normal.stdev, self._crisis.stdev)
        lo = min(self._normal.mean, self._crisis.mean) - spread
        hi = max(self._normal.mean, self._crisis.mean) + spread
        for _ in range(64):
            mid = 0.5 * (lo + hi)
            if self._mixture_cdf(mid) < u:
                lo = mid
            else:
                hi = mid
        return self.c.pinned_spot * math.exp(0.5 * (lo + hi))


__all__ = [
    "DEFAULT_REGIMES",
    "DEFAULT_EXCLUDED_REGIMES",
    "NORMAL_REGIME",
    "CRISIS_REGIME",
    "RegimeStats",
    "FXCalibration",
    "CalibratedFXSampler",
    "calibrate_fx",
    "calibrate_from_config",
]
