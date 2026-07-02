"""
analytics.mc.convergence

Post-hoc Monte Carlo convergence diagnostics. Read-only: computes a running-estimate and
confidence-interval half-width trace from the FINAL per-trial arrays. It does NOT change
``n_trials`` or any KPI band — an early-stopping rule that truncated the run would move the
reported P50/P90 bands (KPI-affecting) and is deliberately out of scope. This only tells a
reader whether the chosen ``n_trials`` sufficed for a given metric on a given scenario.

Method (equivalent to a Welford online accumulator over the same arrays): at each
checkpoint ``k`` the CI half-width is the Monte Carlo standard error of the mean scaled to
a ``z``-level two-sided normal CI, ``err_k = z * sd_k / sqrt(k)`` (see the SAS DO-Loop
convergence-monitoring note). ``final_rel_ci_halfwidth = err_N / |mean_N|`` is the headline:
a reader can compare it to a target precision. NB tail statistics (P95/P99/ES, where
ES = Expected Shortfall, a.k.a. CVaR) converge slower than the mean, so a tight mean-CI
does NOT certify the tails: a 1% tail at n=1000 trials rests on only ~10 raw trials
(see the small-sample caveats at the CVaR/ES surfaces, e.g.
``analytics.core.risk_metrics.TailRiskAnalyzer.calculate_var_cvar``, #600).

Because the mean CI above does NOT certify the tails, :func:`percentile_ci_diagnostic`
(#642) adds a *distribution-free* confidence interval for the percentiles a lender actually
reads (P90/P95 of each metric) plus a Wilson-score CI for a covenant breach probability.
The percentile CI is the classic binomial order-statistic interval (Conover, *Practical
Nonparametric Statistics*; Hahn & Meeker, *Statistical Intervals*): for the ``p``-quantile
from ``n`` sorted trials ``X_(1) <= ... <= X_(n)``, a two-sided ``(1 - alpha)`` interval is
``[X_(l), X_(u)]`` with ranks ``l, u`` chosen so a ``Binomial(n, p)`` count falls in
``[l, u)`` with probability ``>= 1 - alpha``. We use the standard normal approximation to
those ranks, ``rank ~ n*p +/- z*sqrt(n*p*(1-p))`` — no distributional assumption on the
metric itself (unlike the mean CI's i.i.d.-normal SE), which is the whole point for a
lender-facing tail claim. It is distribution-free but still an *approximation* on an
LHS/Iman-Conover design (a prefix subset of an LHS design is not itself LHS), same caveat
as the mean trace. When ``n`` is too small to place the required upper rank (``ceil`` bound
> ``n``) or lower rank (< 1), that bound is reported as ``None`` — loud omission, never a
silent clamp to the min/max order statistic (which would understate the interval and mis-
certify the tail). Student-t (vs normal ``z``) small-``k`` widening is intentionally out of
scope here: it is a refinement of the *mean* SE (a normal-theory statistic) and does not
apply to the distribution-free order-statistic ranks — the ~4% t-vs-z widening noted for the
mean trace has no order-statistic analogue.

Keep import-light: numpy only.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

#: Two-sided 95% normal quantile (z for a 95% confidence interval).
Z_95 = 1.959963984540054

#: Percentiles for which :func:`percentile_ci_diagnostic` emits an order-statistic CI by
#: default. P90/P95 are the bands a lender reads (downside on a return-style metric lives in
#: the lower tail; a DSCR covenant is read at its low percentile). Chosen so the reported CI
#: brackets the same percentiles the aggregator already surfaces.
DEFAULT_CI_PERCENTILES: Tuple[int, ...] = (90, 95)


def convergence_diagnostic(
    trials: Mapping[str, Sequence[float]],
    *,
    z: float = Z_95,
    min_n: int = 30,
    max_checkpoints: int = 12,
) -> Dict[str, Any]:
    """Per-metric convergence trace: running mean + CI half-width (``z*sd/sqrt(k)``) vs k.

    Args:
        trials: ``{metric: [per-trial values]}`` (``None``/non-finite entries are dropped).
        z: Two-sided normal quantile for the CI (default 95%).
        min_n: Minimum trials before a metric is diagnosed (too few → skipped).
        max_checkpoints: Number of (log-spaced) checkpoints, always ending at ``n``.

    Returns:
        ``{metric: {statistic:"mean", n, z, checkpoints, mean_trace, ci_halfwidth_trace,
        final_mean, final_ci_halfwidth, final_rel_ci_halfwidth}}``. Metrics with fewer than
        ``min_n`` finite trials are omitted. ``final_rel_ci_halfwidth`` is ``None`` when the
        mean is within one half-width of zero (its sign is not even resolved, so a *relative*
        precision is undefined — use ``final_ci_halfwidth`` there); this matters because the
        committed lender IRRs sit near zero.

    Caveats:
        The half-width is the i.i.d. normal standard error of the mean; the engine samples via
        LHS (optionally Iman-Conover-reordered), so it is an *approximation* (typically
        conservative) and a prefix subset of an LHS design is not itself an LHS design. The
        normal ``z`` slightly understates the interval at small ``k`` (Student-t at k=30 is
        ~4% wider). It bounds the MEAN only — tail statistics (P90/P95/P99/ES) converge slower,
        so a tight ``final_rel_ci_halfwidth`` does NOT certify the bands a lender reads.
    """
    min_n = max(1, int(min_n))
    out: Dict[str, Any] = {}
    for metric, values in trials.items():
        arr = np.asarray([float(v) for v in values if v is not None], dtype=float)
        arr = arr[np.isfinite(arr)]
        n = int(arr.size)
        if n < max(2, min_n):
            continue

        ks = np.unique(
            np.geomspace(min_n, n, num=min(int(max_checkpoints), n)).astype(int)
        )
        ks = ks[(ks >= min_n) & (ks <= n)]
        if ks.size == 0 or int(ks[-1]) != n:
            ks = np.append(ks, n)

        mean_trace: list[float] = []
        hw_trace: list[float] = []
        for k in ks:
            sub = arr[: int(k)]
            m = float(sub.mean())
            sd = float(sub.std(ddof=1)) if int(k) > 1 else 0.0
            mean_trace.append(m)
            hw_trace.append(float(z * sd / np.sqrt(int(k))))

        final_mean = mean_trace[-1]
        final_hw = hw_trace[-1]
        # Relative precision is only meaningful when the mean is resolved away from zero.
        # Within one half-width of zero the sign is not even certain, so |mean| in the
        # denominator would blow up to a spurious huge number (e.g. for a near-zero IRR) —
        # report None there rather than clamp silently.
        rel: float | None = (
            None if abs(final_mean) <= final_hw else float(final_hw / abs(final_mean))
        )
        out[str(metric)] = {
            "statistic": "mean",
            "n": n,
            "z": float(z),
            "checkpoints": [int(k) for k in ks],
            "mean_trace": mean_trace,
            "ci_halfwidth_trace": hw_trace,
            "final_mean": final_mean,
            "final_ci_halfwidth": final_hw,
            "final_rel_ci_halfwidth": rel,
        }
    return out


def _order_stat_ci_ranks(
    n: int, p: float, z: float
) -> Tuple[Optional[int], Optional[int]]:
    """1-indexed lower/upper order-statistic ranks for a two-sided ``z``-level p-quantile CI.

    Normal approximation to the binomial order-statistic interval (Conover; Hahn & Meeker):
    a ``Binomial(n, p)`` count has mean ``n*p`` and sd ``sqrt(n*p*(1-p))``, so the CI is
    ``[X_(l), X_(u)]`` with ``l = floor(n*p - z*sd)`` and ``u = ceil(n*p + z*sd)`` (widen
    outward — floor the lower, ceil the upper — so coverage is conservative, never anti-
    conservative). Returns 1-indexed ranks; ``None`` for a bound that falls outside
    ``[1, n]`` (n too small to place it), so the caller omits it loudly rather than clamping
    to the extreme order statistic.
    """
    sd = float(np.sqrt(n * p * (1.0 - p)))
    lo_rank = int(np.floor(n * p - z * sd))
    hi_rank = int(np.ceil(n * p + z * sd))
    lo = lo_rank if lo_rank >= 1 else None
    hi = hi_rank if hi_rank <= n else None
    return lo, hi


def _wilson_interval(k: int, n: int, z: float) -> Tuple[float, float]:
    """Two-sided Wilson score interval for a binomial proportion ``k/n`` (pure numpy).

    Preferred over the normal Wald interval for proportions near 0/1 (a rare covenant
    breach), where Wald degenerates to a zero-width or out-of-[0,1] band. Deterministic and
    distribution-free.
    """
    if n <= 0:
        return (0.0, 0.0)
    phat = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * float(np.sqrt(phat * (1.0 - phat) / n + z2 / (4.0 * n * n)))
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return (lo, hi)


def percentile_ci_diagnostic(
    trials: Mapping[str, Sequence[float]],
    *,
    percentiles: Sequence[int] = DEFAULT_CI_PERCENTILES,
    z: float = Z_95,
    min_n: int = 30,
    breach_thresholds: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Distribution-free order-statistic CI for the P90/P95 (the band a lender reads).

    Complements :func:`convergence_diagnostic` (which bounds only the mean): the reported
    tail percentiles converge slower than the mean, so this certifies the tail directly with
    a binomial order-statistic interval (no distributional assumption on the metric). See the
    module docstring for the method and the ``None``-omission convention.

    Args:
        trials: ``{metric: [per-trial values]}`` (``None``/non-finite entries are dropped).
        percentiles: Percentile levels (in 0-100) to bracket, default P90 and P95.
        z: Two-sided normal quantile for the CI (default 95%).
        min_n: Minimum finite trials before a metric is diagnosed (too few → skipped).
        breach_thresholds: Optional ``{metric: threshold}``; when a metric matches, a Wilson
            CI for ``P(value < threshold)`` (a downside covenant breach) is added under
            ``breach_probability_ci``. No threshold → no breach block (never invented).

    Returns:
        ``{metric: {statistic:"percentile_ci", n, z, percentiles: {p: {point, ci_lower,
        ci_upper, rank_lower, rank_upper}}, [breach_probability_ci]}}``. A percentile whose
        upper (or lower) rank cannot be placed at this ``n`` reports that bound as ``None``
        (with its rank ``None``); the ``point`` estimate is always present. Metrics with
        fewer than ``min_n`` finite trials are omitted entirely.
    """
    min_n = max(1, int(min_n))
    levels = sorted({int(p) for p in percentiles if 0 < int(p) < 100})
    thresholds = breach_thresholds or {}
    out: Dict[str, Any] = {}
    for metric, values in trials.items():
        arr = np.asarray([float(v) for v in values if v is not None], dtype=float)
        arr = arr[np.isfinite(arr)]
        n = int(arr.size)
        if n < max(2, min_n):
            continue
        srt = np.sort(arr)

        per_level: Dict[str, Any] = {}
        for p in levels:
            q = p / 100.0
            # Point estimate uses the same linear-interpolation quantile the aggregator
            # reports, so the CI brackets the number the lender actually sees.
            point = float(np.quantile(srt, q))
            lo_rank, hi_rank = _order_stat_ci_ranks(n, q, z)
            # 1-indexed rank -> 0-indexed order statistic.
            ci_lower = float(srt[lo_rank - 1]) if lo_rank is not None else None
            ci_upper = float(srt[hi_rank - 1]) if hi_rank is not None else None
            per_level[str(p)] = {
                "point": point,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "rank_lower": lo_rank,
                "rank_upper": hi_rank,
            }

        entry: Dict[str, Any] = {
            "statistic": "percentile_ci",
            "n": n,
            "z": float(z),
            "percentiles": per_level,
        }

        thr = thresholds.get(str(metric))
        if thr is not None:
            thr = float(thr)
            breaches = int(np.count_nonzero(srt < thr))
            b_lo, b_hi = _wilson_interval(breaches, n, z)
            entry["breach_probability_ci"] = {
                "threshold": thr,
                "point": breaches / n,
                "ci_lower": b_lo,
                "ci_upper": b_hi,
                "n_breaches": breaches,
                "method": "wilson",
            }

        out[str(metric)] = entry
    return out
