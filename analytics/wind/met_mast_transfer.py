"""Sector-wise measure-correlate-predict and site transfer for a short met-mast record.

A short on-site record (here the 232-day met-mast export 617725) is correlated with a
concurrent long-term reference (NASA POWER / MERRA-2 hourly) by direction sector, the
fitted transfer is applied to the whole long-term reference, and the long-term prediction
is carried to a second site through the reference's own site-to-mast relationship, then
to hub height on the mast's measured shear. Every step is a pure function of arrays so
it can be tested on synthetic data; the private mast record and the confidential power
curve never enter this module (``FRAMEWORK-01``: no I/O here).

Reuse (``FRAMEWORK-03``): the transfer kernels are :func:`wind_resource.mcp.variance_ratio_transfer`,
:func:`wind_resource.mcp.linear_regression_transfer` and :func:`wind_resource.mcp.pearson_r`;
the campaign-adequacy record is :func:`wind_resource.mcp.run_mcp`'s; Weibull fits are
:func:`wind_resource.weibull_fit.fit_weibull_on_series`; gross yield is
:func:`analytics.wind.aep_tornado.gross_aep_farm_gwh`. This module adds the sector
book-keeping, the circular statistics, the clock-offset evidence, the shear and transfer
tables, and the profile, turbulence and uncertainty aggregates.

Method choices are config-driven (``conf/blue_whale_met_mast_transfer.yaml``,
``FRAMEWORK-02``); no step is stochastic, so no seed is needed (``MRM-01``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt
import pandas as pd

from analytics.wind.aep_tornado import gross_aep_farm_gwh
from wind_resource.mcp import (
    linear_regression_transfer,
    pearson_r,
    run_mcp,
    variance_ratio_transfer,
)
from wind_resource.weibull_fit import fit_weibull_on_series

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

#: 16-point compass labels, North-centred sectors (met convention).
COMPASS_16: Tuple[str, ...] = (
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


# ---------------------------------------------------------------------------
# Circular statistics and sectors
# ---------------------------------------------------------------------------
def sector_index(direction_deg: npt.ArrayLike, n_sectors: int) -> IntArray:
    """North-centred sector index of each met-convention direction.

    Args:
        direction_deg: Directions in degrees (0 = North, clockwise).
        n_sectors: Number of equal sectors.

    Returns:
        Integer sector indices in ``[0, n_sectors)``.

    Raises:
        ValueError: If ``n_sectors`` is not positive.
    """
    if n_sectors < 1:
        raise ValueError("n_sectors must be >= 1")
    width = 360.0 / n_sectors
    d = np.mod(np.asarray(direction_deg, dtype=np.float64) + width / 2.0, 360.0)
    idx = np.floor(d / width).astype(np.int64)
    return np.asarray(np.clip(idx, 0, n_sectors - 1), dtype=np.int64)


def angular_difference_deg(a_deg: npt.ArrayLike, b_deg: npt.ArrayLike) -> FloatArray:
    """Signed smallest difference ``a - b`` in degrees, in ``[-180, 180)``."""
    a = np.asarray(a_deg, dtype=np.float64)
    b = np.asarray(b_deg, dtype=np.float64)
    return np.asarray(np.mod(a - b + 180.0, 360.0) - 180.0, dtype=np.float64)


def circular_mean_deg(direction_deg: npt.ArrayLike) -> float:
    """Unit-vector mean of directions in degrees, in ``[0, 360)``; NaN when empty."""
    d = np.radians(np.asarray(direction_deg, dtype=np.float64))
    if d.size == 0:
        return float("nan")
    s, c = float(np.sin(d).mean()), float(np.cos(d).mean())
    return float(np.mod(np.degrees(np.arctan2(s, c)), 360.0))


def vector_mean_direction_deg(sin_mean: FloatArray, cos_mean: FloatArray) -> FloatArray:
    """Direction of averaged unit vectors (degrees, ``[0, 360)``)."""
    return np.asarray(
        np.mod(np.degrees(np.arctan2(sin_mean, cos_mean)), 360.0), dtype=np.float64
    )


# ---------------------------------------------------------------------------
# Hourly aggregation of a sub-hourly record
# ---------------------------------------------------------------------------
def hourly_means(
    frame: pd.DataFrame,
    *,
    speed_columns: Mapping[str, str],
    direction_columns: Mapping[str, str],
    clock_offset_minutes: int,
    samples_per_hour: int,
) -> pd.DataFrame:
    """Average a sub-hourly record to complete UTC hours.

    Speeds are arithmetic means; directions are unit-vector means. An hour is kept for a
    channel only when it holds every expected sample of that channel.

    Args:
        frame: Record indexed by its own (local) beginning-of-interval timestamps.
        speed_columns: Output name -> source speed column.
        direction_columns: Output name -> source direction column.
        clock_offset_minutes: The record's clock minus UTC, in minutes.
        samples_per_hour: Samples a complete hour holds.

    Returns:
        Hourly frame indexed by UTC hour start, one column per output name (NaN where
        incomplete).
    """
    if samples_per_hour < 1:
        raise ValueError("samples_per_hour must be >= 1")
    utc_index = pd.DatetimeIndex(frame.index) - pd.Timedelta(
        minutes=clock_offset_minutes
    )
    out: Dict[str, pd.Series] = {}
    for name, col in speed_columns.items():
        s = pd.Series(frame[col].to_numpy(dtype=np.float64), index=utc_index)
        g = s.resample("1h")
        mean, count = g.mean(), g.count()
        out[name] = mean.where(count == samples_per_hour)
    for name, col in direction_columns.items():
        rad = np.radians(frame[col].to_numpy(dtype=np.float64))
        sn = pd.Series(np.sin(rad), index=utc_index).resample("1h")
        cs = pd.Series(np.cos(rad), index=utc_index).resample("1h")
        count = pd.Series(rad, index=utc_index).resample("1h").count()
        sm, cm = sn.mean(), cs.mean()
        d = pd.Series(
            vector_mean_direction_deg(
                sm.to_numpy(dtype=np.float64), cm.to_numpy(dtype=np.float64)
            ),
            index=sm.index,
        )
        out[name] = d.where(count == samples_per_hour)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Clock-offset evidence
# ---------------------------------------------------------------------------
def harmonic_phase_hours(
    values: npt.ArrayLike, hour_of_day: npt.ArrayLike, period_h: float
) -> Dict[str, float]:
    """Least-squares fit of a mean plus 24 h and ``period_h`` harmonics.

    Args:
        values: Observations.
        hour_of_day: Clock hour of each observation (fractional, ``[0, 24)``).
        period_h: Period of the harmonic whose phase is reported (24 or 12).

    Returns:
        ``max_at_h`` (the first clock time of the harmonic's maximum) and ``amplitude``.
    """
    y = np.asarray(values, dtype=np.float64)
    h = np.asarray(hour_of_day, dtype=np.float64)
    ok = np.isfinite(y) & np.isfinite(h)
    y, h = y[ok], h[ok]
    w1 = 2.0 * np.pi * h / 24.0
    w2 = 2.0 * np.pi * h / 12.0
    design = np.column_stack(
        [np.ones_like(h), np.cos(w1), np.sin(w1), np.cos(w2), np.sin(w2)]
    )
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    if period_h == 24.0:
        c, s = coef[1], coef[2]
    elif period_h == 12.0:
        c, s = coef[3], coef[4]
    else:
        raise ValueError("period_h must be 24 or 12")
    phase = math.atan2(float(s), float(c)) % (2.0 * math.pi)
    return {
        "max_at_h": phase / (2.0 * math.pi) * period_h,
        "amplitude": math.hypot(float(c), float(s)),
    }


def offset_correlation_scan(
    mast_speed: pd.Series,
    reference_speed: pd.Series,
    offsets_minutes: Sequence[int],
    samples_per_hour: int,
) -> List[Dict[str, float]]:
    """Hourly correlation of mast and reference speed for each candidate clock offset.

    Args:
        mast_speed: Sub-hourly mast speed on the mast's clock.
        reference_speed: Hourly reference speed indexed by UTC hour start.
        offsets_minutes: Candidate ``mast clock - UTC`` offsets.
        samples_per_hour: Samples in a complete mast hour.

    Returns:
        One row per offset: ``offset_h``, ``pearson_r``, ``n``.
    """
    rows: List[Dict[str, float]] = []
    frame = mast_speed.to_frame("v")
    for off in offsets_minutes:
        hr = hourly_means(
            frame,
            speed_columns={"v": "v"},
            direction_columns={},
            clock_offset_minutes=int(off),
            samples_per_hour=samples_per_hour,
        )["v"]
        j = pd.concat([hr, reference_speed], axis=1, join="inner").dropna()
        r = pearson_r(j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy())
        rows.append({"offset_h": off / 60.0, "pearson_r": r, "n": float(len(j))})
    return rows


def subdaily_anomaly(series: pd.Series, window_h: int) -> pd.Series:
    """Departure from a centred running mean: the sub-daily (diurnal) content."""
    roll = series.rolling(window_h + 1, center=True, min_periods=window_h - 4).mean()
    return series - roll


# ---------------------------------------------------------------------------
# Sector MCP
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SectorFit:
    """The transfer used in one reference-direction sector.

    Attributes:
        sector: Sector index.
        n: Concurrent hours in the sector.
        slope: Transfer slope.
        intercept: Transfer intercept (m/s).
        r_squared: Squared Pearson correlation in the sector.
        residual_std_ms: Standard deviation of mast minus transferred reference.
        mean_bias_ms: Mean of mast minus transferred reference.
        mast_mean_ms: Mean mast speed.
        reference_mean_ms: Mean reference speed.
        source: ``"sector"`` when fitted in the sector, ``"omni"`` when the
            omnidirectional fit stands in.
    """

    sector: int
    n: int
    slope: float
    intercept: float
    r_squared: float
    residual_std_ms: float
    mean_bias_ms: float
    mast_mean_ms: float
    reference_mean_ms: float
    source: str


def fit_transfer(mast: FloatArray, ref: FloatArray, method: str) -> Tuple[float, float]:
    """Transfer ``(slope, intercept)`` by the named method (reused kernels)."""
    if method == "variance_ratio":
        return variance_ratio_transfer(mast, ref)
    if method == "linear_regression":
        return linear_regression_transfer(mast, ref)
    raise ValueError(f"unknown MCP method {method!r}")


def _residuals(
    mast: FloatArray, ref: FloatArray, slope: float, intercept: float
) -> Tuple[float, float]:
    if mast.size == 0:
        return float("nan"), float("nan")
    res = mast - (slope * ref + intercept)
    return float(res.std()), float(res.mean())


def fit_sector_mcp(
    mast: npt.ArrayLike,
    ref_speed: npt.ArrayLike,
    ref_direction_deg: npt.ArrayLike,
    *,
    n_sectors: int,
    method: str,
    min_sector_hours: int,
    min_sector_r_squared: float,
) -> Tuple[List[SectorFit], SectorFit]:
    """Fit a transfer per reference-direction sector, with an omnidirectional fallback.

    A sector with fewer than ``min_sector_hours`` concurrent hours, or whose correlation
    falls below ``min_sector_r_squared``, uses the omnidirectional transfer instead; its
    statistics are still reported.

    Args:
        mast: Concurrent mast speeds.
        ref_speed: Concurrent reference speeds.
        ref_direction_deg: Concurrent reference directions.
        n_sectors: Number of sectors.
        method: ``variance_ratio`` or ``linear_regression``.
        min_sector_hours: Fewest hours for a sector's own fit.
        min_sector_r_squared: Lowest R^2 for a sector's own fit.

    Returns:
        The per-sector fits and the omnidirectional fit.
    """
    m = np.asarray(mast, dtype=np.float64)
    r = np.asarray(ref_speed, dtype=np.float64)
    d = np.asarray(ref_direction_deg, dtype=np.float64)
    if not (m.shape == r.shape == d.shape):
        raise ValueError("mast, reference speed and direction must align")
    if not np.all(np.isfinite(m) & np.isfinite(r) & np.isfinite(d)):
        raise ValueError("concurrent series must be finite; drop gaps first")
    o_slope, o_int = fit_transfer(m, r, method)
    o_std, o_bias = _residuals(m, r, o_slope, o_int)
    omni = SectorFit(
        sector=-1,
        n=int(m.size),
        slope=o_slope,
        intercept=o_int,
        r_squared=pearson_r(m, r) ** 2,
        residual_std_ms=o_std,
        mean_bias_ms=o_bias,
        mast_mean_ms=float(m.mean()),
        reference_mean_ms=float(r.mean()),
        source="omni",
    )
    sec = sector_index(d, n_sectors)
    fits: List[SectorFit] = []
    for s in range(n_sectors):
        sel = sec == s
        ms, rs = m[sel], r[sel]
        n = int(sel.sum())
        r2 = pearson_r(ms, rs) ** 2 if n > 2 else 0.0
        own = n >= min_sector_hours and r2 >= min_sector_r_squared and rs.std() > 0
        if own:
            slope, intercept = fit_transfer(ms, rs, method)
            source = "sector"
        else:
            slope, intercept, source = o_slope, o_int, "omni"
        std, bias = _residuals(ms, rs, slope, intercept)
        fits.append(
            SectorFit(
                sector=s,
                n=n,
                slope=slope,
                intercept=intercept,
                r_squared=r2,
                residual_std_ms=std,
                mean_bias_ms=bias,
                mast_mean_ms=float(ms.mean()) if n else float("nan"),
                reference_mean_ms=float(rs.mean()) if n else float("nan"),
                source=source,
            )
        )
    return fits, omni


def predict_by_sector(
    ref_speed: npt.ArrayLike,
    ref_direction_deg: npt.ArrayLike,
    fits: Sequence[SectorFit],
) -> FloatArray:
    """Apply each sector's transfer to the long-term reference; clip at zero."""
    r = np.asarray(ref_speed, dtype=np.float64)
    sec = sector_index(ref_direction_deg, len(fits))
    slope = np.array([f.slope for f in fits])[sec]
    intercept = np.array([f.intercept for f in fits])[sec]
    return np.asarray(np.clip(slope * r + intercept, 0.0, None), dtype=np.float64)


def campaign_record(
    mast: npt.ArrayLike, ref: npt.ArrayLike, ref_long_term: npt.ArrayLike, method: str
) -> Dict[str, Any]:
    """The omnidirectional :func:`wind_resource.mcp.run_mcp` record (campaign adequacy).

    The campaign is below the 12-month bankable span by construction, so the
    disclosure opt-out is passed and recorded rather than hidden.
    """
    res = run_mcp(
        np.asarray(mast, dtype=np.float64).tolist(),
        np.asarray(ref, dtype=np.float64).tolist(),
        np.asarray(ref_long_term, dtype=np.float64).tolist(),
        method=method,
        allow_below_bankable=True,
    )
    out = res.as_dict()
    out["allow_below_bankable"] = True
    return out


# ---------------------------------------------------------------------------
# Veer, site transfer and shear
# ---------------------------------------------------------------------------
def sector_veer(
    target_direction_deg: npt.ArrayLike,
    ref_direction_deg: npt.ArrayLike,
    *,
    n_sectors: int,
    min_sector_hours: int,
) -> Tuple[FloatArray, float, IntArray]:
    """Circular-mean ``target - reference`` direction offset by reference sector.

    Sectors with fewer than ``min_sector_hours`` samples take the all-sector value.

    Returns:
        Per-sector veer (degrees), the all-sector veer, and per-sector counts.
    """
    t = np.asarray(target_direction_deg, dtype=np.float64)
    r = np.asarray(ref_direction_deg, dtype=np.float64)
    diff = angular_difference_deg(t, r)
    omni = float(angular_difference_deg(circular_mean_deg(diff), 0.0))
    sec = sector_index(r, n_sectors)
    veer = np.full(n_sectors, omni)
    counts = np.bincount(sec, minlength=n_sectors).astype(np.int64)
    for s in range(n_sectors):
        if counts[s] >= min_sector_hours:
            veer[s] = float(
                angular_difference_deg(circular_mean_deg(diff[sec == s]), 0.0)
            )
    return veer, omni, counts


def continuous_veer(
    direction_deg: npt.ArrayLike, veer_by_sector: npt.ArrayLike
) -> FloatArray:
    """Veer at each direction, interpolated linearly between sector centres (circular).

    A step function of sector veers would push every hour of a sector by the same angle
    and leave gaps or pile-ups at sector edges; interpolating keeps the rotated
    directions continuous.

    Raises:
        ValueError: If the rotation ``d -> d + veer(d)`` would not be monotone (adjacent
            sector veers falling by a full sector width or more), which would reorder
            directions.
    """
    veer = np.asarray(veer_by_sector, dtype=np.float64)
    n = veer.size
    width = 360.0 / n
    if np.any(np.diff(np.r_[veer, veer[0]]) <= -width):
        raise ValueError("sector veers would fold directions over; not monotone")
    d = np.mod(np.asarray(direction_deg, dtype=np.float64), 360.0)
    centres = np.arange(n + 1) * width
    return np.asarray(np.interp(d, centres, np.r_[veer, veer[0]]), dtype=np.float64)


def direction_residual_quantiles(
    target_direction_deg: npt.ArrayLike,
    ref_direction_deg: npt.ArrayLike,
    *,
    n_sectors: int,
    min_sector_hours: int,
    n_quantiles: int,
) -> Tuple[FloatArray, IntArray]:
    """Mid-point quantiles of ``target - reference`` direction, by reference sector.

    A single mean veer applied to every hour collapses the scatter of the measured
    direction about the reference and concentrates the rose. Carrying ``n_quantiles``
    equally weighted copies of each long-term hour, rotated by these quantiles,
    reproduces the measured conditional direction distribution instead; it is
    deterministic. A sector with fewer than ``min_sector_hours`` concurrent hours takes
    the quantiles of all sectors pooled.

    Returns:
        ``[n_sectors][n_quantiles]`` offsets (degrees) and per-sector counts.
    """
    if n_quantiles < 1:
        raise ValueError("n_quantiles must be >= 1")
    diff = angular_difference_deg(target_direction_deg, ref_direction_deg)
    sec = sector_index(ref_direction_deg, n_sectors)
    q = (np.arange(n_quantiles) + 0.5) / n_quantiles

    def quantiles(x: FloatArray) -> FloatArray:
        centre = float(angular_difference_deg(circular_mean_deg(x), 0.0))
        rel = angular_difference_deg(x, centre)
        return np.asarray(np.quantile(rel, q) + centre, dtype=np.float64)

    pooled = quantiles(diff)
    out = np.tile(pooled, (n_sectors, 1))
    counts = np.bincount(sec, minlength=n_sectors).astype(np.int64)
    for s in range(n_sectors):
        if counts[s] >= min_sector_hours:
            out[s] = quantiles(diff[sec == s])
    return out, counts


def expand_by_direction_quantiles(
    ref_direction_deg: npt.ArrayLike, offsets: FloatArray
) -> Tuple[IntArray, FloatArray]:
    """Repeat each hour once per quantile and rotate its direction by that quantile.

    Returns:
        The source-hour index of each copy and the rotated direction (degrees).
    """
    d = np.asarray(ref_direction_deg, dtype=np.float64)
    k = offsets.shape[1]
    src = np.repeat(np.arange(d.size, dtype=np.int64), k)
    which = np.tile(np.arange(k), d.size)
    sec = sector_index(d, offsets.shape[0])[src]
    return src, np.asarray(
        np.mod(d[src] + offsets[sec, which], 360.0), dtype=np.float64
    )


def sector_frequencies(direction_deg: npt.ArrayLike, n_sectors: int) -> FloatArray:
    """Share of samples in each sector (sums to 1)."""
    sec = sector_index(direction_deg, n_sectors)
    return np.asarray(
        np.bincount(sec, minlength=n_sectors) / sec.size, dtype=np.float64
    )


def sector_speed_ratio(
    site_speed: npt.ArrayLike,
    mast_speed: npt.ArrayLike,
    mast_direction_deg: npt.ArrayLike,
    *,
    n_sectors: int,
    min_sector_hours: int,
) -> Tuple[FloatArray, float]:
    """Ratio of mean site to mean mast speed by mast-direction sector.

    Returns:
        Per-sector ratios and the all-sector ratio (used where a sector is sparse).
    """
    s = np.asarray(site_speed, dtype=np.float64)
    m = np.asarray(mast_speed, dtype=np.float64)
    sec = sector_index(mast_direction_deg, n_sectors)
    omni = float(s.mean() / m.mean())
    ratio = np.full(n_sectors, omni)
    for k in range(n_sectors):
        sel = sec == k
        if sel.sum() >= min_sector_hours and m[sel].mean() > 0:
            ratio[k] = float(s[sel].mean() / m[sel].mean())
    return ratio, omni


def shear_exponent(v_low: float, v_high: float, h_low: float, h_high: float) -> float:
    """Power-law exponent between two heights from their mean speeds."""
    if min(v_low, v_high, h_low, h_high) <= 0 or h_low == h_high:
        raise ValueError("speeds and heights must be positive and heights distinct")
    return math.log(v_high / v_low) / math.log(h_high / h_low)


def shear_table(
    v_low: npt.ArrayLike,
    v_high: npt.ArrayLike,
    direction_deg: npt.ArrayLike,
    is_day: npt.ArrayLike,
    *,
    h_low: float,
    h_high: float,
    n_sectors: int,
    min_cell_hours: int,
    min_speed_ms: float,
) -> Dict[str, Any]:
    """Shear exponent by sector and day/night from concurrent mean speeds.

    Only rows with both speeds at or above ``min_speed_ms`` enter. A cell with fewer
    than ``min_cell_hours`` rows takes its day/night all-sector value.

    Returns:
        ``alpha`` (``[2][n_sectors]``, row 0 night, row 1 day), ``n`` (same shape),
        ``alpha_day``, ``alpha_night`` and ``alpha_all``.
    """
    lo = np.asarray(v_low, dtype=np.float64)
    hi = np.asarray(v_high, dtype=np.float64)
    day = np.asarray(is_day, dtype=bool)
    sec = sector_index(direction_deg, n_sectors)
    ok = np.isfinite(lo) & np.isfinite(hi) & (lo >= min_speed_ms) & (hi >= min_speed_ms)
    alpha_all = shear_exponent(
        float(lo[ok].mean()), float(hi[ok].mean()), h_low, h_high
    )
    by_dn: List[float] = []
    for flag in (False, True):
        sel = ok & (day == flag)
        by_dn.append(
            shear_exponent(float(lo[sel].mean()), float(hi[sel].mean()), h_low, h_high)
            if sel.sum() >= min_cell_hours
            else alpha_all
        )
    alpha = np.zeros((2, n_sectors))
    count = np.zeros((2, n_sectors), dtype=np.int64)
    for i, flag in enumerate((False, True)):
        for s in range(n_sectors):
            sel = ok & (day == flag) & (sec == s)
            count[i, s] = int(sel.sum())
            alpha[i, s] = (
                shear_exponent(
                    float(lo[sel].mean()), float(hi[sel].mean()), h_low, h_high
                )
                if sel.sum() >= min_cell_hours
                else by_dn[i]
            )
    return {
        "alpha": alpha.tolist(),
        "n": count.tolist(),
        "alpha_night": by_dn[0],
        "alpha_day": by_dn[1],
        "alpha_all": alpha_all,
    }


def apply_shear(
    speed: npt.ArrayLike,
    direction_deg: npt.ArrayLike,
    is_day: npt.ArrayLike,
    alpha: Sequence[Sequence[float]],
    *,
    h_from: float,
    h_to: float,
) -> FloatArray:
    """Move speeds from ``h_from`` to ``h_to`` with the sector and day/night exponents."""
    a = np.asarray(alpha, dtype=np.float64)
    sec = sector_index(direction_deg, a.shape[1])
    row = np.asarray(is_day, dtype=bool).astype(np.int64)
    factor = (h_to / h_from) ** a[row, sec]
    return np.asarray(np.asarray(speed, dtype=np.float64) * factor, dtype=np.float64)


def log_law_fit_exponent(
    heights_m: Sequence[float], speeds_ms: Sequence[float]
) -> float:
    """Least-squares power-law exponent through several heights' mean speeds."""
    lh = np.log(np.asarray(heights_m, dtype=np.float64))
    lv = np.log(np.asarray(speeds_ms, dtype=np.float64))
    slope, _ = np.polyfit(lh, lv, 1)
    return float(slope)


# ---------------------------------------------------------------------------
# Distribution summaries
# ---------------------------------------------------------------------------
def weibull_mean(a: float, k: float) -> float:
    """Closed-form Weibull mean ``A * Gamma(1 + 1/k)``."""
    return float(a * math.gamma(1.0 + 1.0 / k))


def sector_rose(
    speed: npt.ArrayLike, direction_deg: npt.ArrayLike, n_sectors: int
) -> List[Dict[str, Any]]:
    """Frequency, mean speed, Weibull and cube-of-speed share per sector.

    The ``energy_share`` is each sector's share of ``sum(v^3)``: wind-energy flux, not
    turbine output.
    """
    v = np.asarray(speed, dtype=np.float64)
    sec = sector_index(direction_deg, n_sectors)
    cube_total = float((v**3).sum())
    rows: List[Dict[str, Any]] = []
    for s in range(n_sectors):
        sel = sec == s
        vs = v[sel]
        row: Dict[str, Any] = {
            "sector": s,
            "label": COMPASS_16[s] if n_sectors == 16 else str(s),
            "centre_deg": s * 360.0 / n_sectors,
            "hours": int(sel.sum()),
            "frequency": float(sel.mean()),
            "mean_speed_ms": float(vs.mean()) if vs.size else float("nan"),
            "energy_share": float((vs**3).sum()) / cube_total if cube_total else 0.0,
            "weibull_a_ms": None,
            "weibull_k": None,
        }
        if (vs > 0).sum() >= 10:
            fit = fit_weibull_on_series(pd.DataFrame({"v": vs}), ws_column="v")
            row["weibull_a_ms"] = fit.weibull_a
            row["weibull_k"] = fit.weibull_k
        rows.append(row)
    return rows


def turbulence_table(
    mean_ms: npt.ArrayLike,
    sd_ms: npt.ArrayLike,
    direction_deg: npt.ArrayLike,
    *,
    bin_edges_ms: Sequence[float],
    n_sectors: int,
    min_speed_ms: float,
    min_count: int,
) -> Dict[str, Any]:
    """Turbulence intensity ``sd / mean`` by speed bin and by sector.

    Representative TI is ``mean + 1.28 * std`` of TI in the bin (the IEC 61400-1 90th
    percentile form). Bins with fewer than ``min_count`` samples report counts only.
    """
    m = np.asarray(mean_ms, dtype=np.float64)
    sd = np.asarray(sd_ms, dtype=np.float64)
    ok = np.isfinite(m) & np.isfinite(sd) & (m >= min_speed_ms)
    ti = np.where(ok, sd / np.where(m > 0, m, np.nan), np.nan)
    edges = np.asarray(bin_edges_ms, dtype=np.float64)
    by_bin: List[Dict[str, Any]] = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        sel = ok & (m >= lo) & (m < hi)
        t = ti[sel]
        row: Dict[str, Any] = {"bin_lo_ms": float(lo), "bin_hi_ms": float(hi)}
        row["n"] = int(sel.sum())
        if t.size >= min_count:
            row["ti_mean"] = float(t.mean())
            row["ti_std"] = float(t.std())
            row["ti_representative"] = float(t.mean() + 1.28 * t.std())
        by_bin.append(row)
    sec = sector_index(direction_deg, n_sectors)
    by_sector: List[Dict[str, Any]] = []
    for s in range(n_sectors):
        sel = ok & (sec == s)
        t = ti[sel]
        row = {"sector": s, "n": int(sel.sum())}
        if t.size >= min_count:
            row["ti_mean"] = float(t.mean())
            row["ti_p90"] = float(np.quantile(t, 0.9))
        by_sector.append(row)
    return {"by_speed_bin": by_bin, "by_sector": by_sector, "n_valid": int(ok.sum())}


# ---------------------------------------------------------------------------
# Yield
# ---------------------------------------------------------------------------
def sector_weighted_gross_aep_gwh(
    rose: Sequence[Mapping[str, Any]],
    curve_ws_ms: FloatArray,
    curve_power_kw: FloatArray,
    density_factor: float,
) -> float:
    """Gross AEP of one turbine as the frequency-weighted sum of sector Weibull yields.

    A sector without a Weibull fit must carry zero frequency.
    """
    total = 0.0
    for row in rose:
        f = float(row["frequency"])
        if f == 0.0:
            continue
        a, k = row["weibull_a_ms"], row["weibull_k"]
        if a is None or k is None:
            raise ValueError(f"sector {row['sector']} has frequency but no Weibull")
        total += f * gross_aep_farm_gwh(
            float(a), float(k), curve_ws_ms / density_factor, curve_power_kw, 1
        )
    return total


def time_series_gross_aep_gwh(
    speed_ms: npt.ArrayLike,
    curve_ws_ms: FloatArray,
    curve_power_kw: FloatArray,
    density_factor: float,
) -> float:
    """Gross AEP of one turbine as the mean curve power over an hourly series."""
    v = np.asarray(speed_ms, dtype=np.float64) * density_factor
    p = np.interp(v, curve_ws_ms, curve_power_kw, left=0.0, right=0.0)
    return float(p.mean()) * 8760.0 / 1e6


def energy_sensitivity(
    aep_of_scale: Any, base_scale: float = 1.0, step: float = 0.01
) -> float:
    """``d ln(AEP) / d ln(speed)`` by a central difference of a callable.

    Args:
        aep_of_scale: Callable returning AEP for a multiplicative speed scale.
        base_scale: Scale at which to evaluate.
        step: Relative step.

    Returns:
        The dimensionless speed-to-energy sensitivity.
    """
    up = float(aep_of_scale(base_scale * (1.0 + step)))
    dn = float(aep_of_scale(base_scale * (1.0 - step)))
    return math.log(up / dn) / math.log((1.0 + step) / (1.0 - step))


def jackknife_std(estimates: Sequence[float]) -> float:
    """Jackknife standard error of leave-one-group-out estimates."""
    e = np.asarray(estimates, dtype=np.float64)
    n = e.size
    if n < 2:
        raise ValueError("need at least two leave-one-out estimates")
    return float(math.sqrt((n - 1) / n * float(((e - e.mean()) ** 2).sum())))


def operating_fraction(
    speed_ms: npt.ArrayLike, cut_in_ms: float, cut_out_ms: float
) -> FloatArray:
    """Boolean-as-float: hub speed inside the producing range ``[cut_in, cut_out]``."""
    v = np.asarray(speed_ms, dtype=np.float64)
    return np.asarray((v >= cut_in_ms) & (v <= cut_out_ms), dtype=np.float64)


def month_sector_weights(
    month: npt.ArrayLike,
    direction_deg: npt.ArrayLike,
    operating: npt.ArrayLike,
    n_sectors: int,
) -> FloatArray:
    """``P(sector and operating | month)`` as a ``[12][n_sectors]`` array."""
    mo = np.asarray(month, dtype=np.int64)
    sec = sector_index(direction_deg, n_sectors)
    op = np.asarray(operating, dtype=np.float64)
    w = np.zeros((12, n_sectors))
    for m in range(1, 13):
        sel = mo == m
        if not sel.any():
            raise ValueError(f"no hours in month {m}")
        w[m - 1] = (
            np.bincount(sec[sel], weights=op[sel], minlength=n_sectors) / sel.sum()
        )
    return w


def profile_means(
    speed_ms: npt.ArrayLike, key: npt.ArrayLike, keys: Sequence[int]
) -> List[Optional[float]]:
    """Mean speed for each key value (``None`` where the key is absent)."""
    v = np.asarray(speed_ms, dtype=np.float64)
    k = np.asarray(key)
    out: List[Optional[float]] = []
    for kk in keys:
        sel = k == kk
        out.append(float(v[sel].mean()) if sel.any() else None)
    return out


__all__ = [
    "COMPASS_16",
    "SectorFit",
    "angular_difference_deg",
    "apply_shear",
    "campaign_record",
    "circular_mean_deg",
    "continuous_veer",
    "direction_residual_quantiles",
    "energy_sensitivity",
    "expand_by_direction_quantiles",
    "fit_sector_mcp",
    "fit_transfer",
    "harmonic_phase_hours",
    "hourly_means",
    "jackknife_std",
    "log_law_fit_exponent",
    "month_sector_weights",
    "offset_correlation_scan",
    "operating_fraction",
    "predict_by_sector",
    "profile_means",
    "sector_index",
    "sector_frequencies",
    "sector_rose",
    "sector_speed_ratio",
    "sector_veer",
    "sector_weighted_gross_aep_gwh",
    "shear_exponent",
    "shear_table",
    "subdaily_anomaly",
    "time_series_gross_aep_gwh",
    "turbulence_table",
    "vector_mean_direction_deg",
    "weibull_mean",
]
