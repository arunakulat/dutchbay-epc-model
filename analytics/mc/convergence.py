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
a reader can compare it to a target precision. NB tail statistics (P95/P99/ES) converge
slower than the mean, so a tight mean-CI does NOT certify the tails.

Keep import-light: numpy only.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

import numpy as np

#: Two-sided 95% normal quantile (z for a 95% confidence interval).
Z_95 = 1.959963984540054


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
