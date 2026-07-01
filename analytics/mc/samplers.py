"""
analytics.mc.samplers

Sampling utilities (LHS baseline + optional Sobol QMC).
Keep the module top-level import-light: numpy only. Sobol imports scipy.stats.qmc
lazily inside the function (CASPER: an optional facility fails at call-time, not import,
so an install without the QMC path still imports this module).
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np


def generate_lhs_samples(
    *,
    n_trials: int,
    bounds: Sequence[Tuple[float, float]],
    seed: int = 123,
    common_random_numbers: bool = True,
) -> np.ndarray:
    """
    Latin Hypercube sampler — the canonical, tested LHS implementation: one stratified
    draw per [i/n, (i+1)/n] interval per dimension (no column reuse).

    Returns: array shape [n_trials, n_params] sampled uniformly within bounds.
    """
    n = int(n_trials)
    if n <= 0:
        raise ValueError("n_trials must be > 0")
    k = len(bounds)
    if k == 0:
        raise ValueError("bounds must be non-empty")

    rng = np.random.default_rng(int(seed))

    # LHS in [0,1]
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.uniform(size=(n, k))
    a = cut[:n]
    b = cut[1:]
    pts = (
        u * (b - a)[:, None] + a[:, None]
    )  # [n,1] broadcast -> [n,k] via later operations

    # independent random permutations per dimension
    lhs = np.zeros((n, k), dtype=float)
    for j in range(k):
        perm = (
            rng.permutation(n)
            if common_random_numbers
            else np.random.default_rng(int(seed + j)).permutation(n)
        )
        # Take dimension j's OWN stratified column (was column 0 for every j, which made
        # every dimension reuse the same stratified values — a degenerate Latin Hypercube
        # where all parameters were perfectly correlated; audit R1).
        lhs[:, j] = pts[perm, j]

    # scale to bounds
    out = np.empty_like(lhs)
    for j, (lo, hi) in enumerate(bounds):
        out[:, j] = lo + lhs[:, j] * (hi - lo)

    return out


def generate_sobol_samples(
    *,
    n_trials: int,
    bounds: Sequence[Tuple[float, float]],
    seed: int = 123,
) -> np.ndarray:
    """
    Sobol' low-discrepancy (quasi-Monte-Carlo) sampler — an OPT-IN alternative to LHS.

    Why opt-in, not the default: a scrambled Sobol' net has star-discrepancy ~O((log n)^d / n)
    versus plain Monte-Carlo's O(n^-1/2) RMSE, an advantage realised for *smooth, low-effective-
    dimension* integrands. DutchBay's binding KPIs are NOT smooth in the drivers — min_dscr is
    clamped at the covenant floor and equity_irr kinks where debt is sized — so QMC buys little
    there and can even alias against the sequence's structure. Kept as an honest convergence
    *option* for the smoother KPIs (project_npv, mean project_irr), never the silent default.
    See #589 and the 2026-07-02 SOTA link-research digest (which flags the naive "O(1/N)" gloss).

    Power-of-two contract: a scrambled Sobol' net keeps its balance/discrepancy guarantee only
    at ``n = 2**m`` (SciPy warns, and the property is genuinely lost, if you truncate to a
    non-power-of-2 subset). So a requested ``n_trials`` is rounded UP to the next power of two
    and ALL 2**m points are returned — truncating back would discard exactly the low-discrepancy
    advantage the caller opted in for. The engine records requested-vs-used n in metadata.

    Caveat — correlation: if the engine subsequently applies a correlation matrix (Iman-Conover
    rank-reordering), the per-column *marginals* survive but the *joint* low-discrepancy structure
    is destroyed. The engine emits a one-time warning when Sobol is combined with an enabled
    correlation block; the balance benefit then only accrues to the marginals.

    Returns: array shape [2**ceil(log2(n_trials)), n_params], scaled uniformly within bounds.
    A pinned dimension (lo == hi, an accepted config shape) yields a constant column — the same
    affine map LHS uses, so Sobol never fails on a config LHS accepts.
    """
    n = int(n_trials)
    if n <= 0:
        raise ValueError("n_trials must be > 0")
    k = len(bounds)
    if k == 0:
        raise ValueError("bounds must be non-empty")

    try:
        from scipy.stats import qmc  # lazy: keep module import numpy-only (CASPER)
    except ImportError as exc:  # pragma: no cover - scipy is a core dep in practice
        raise RuntimeError(
            "Sobol QMC sampling requires SciPy (scipy.stats.qmc). Install scipy, "
            "or use the default monte_carlo.sampler: lhs."
        ) from exc

    m = max(0, int(math.ceil(math.log2(n))))  # smallest m with 2**m >= n
    engine = qmc.Sobol(d=k, scramble=True, rng=np.random.default_rng(int(seed)))
    unit = engine.random_base2(m)  # exactly 2**m points, balance preserved

    # Scale with the SAME per-dimension affine map generate_lhs_samples uses (lo + u*(hi-lo))
    # rather than qmc.scale: qmc.scale requires STRICT lo < hi and raises a raw, param-anonymous
    # ValueError on a pinned driver (lo == hi), which the engine's bounds validator explicitly
    # accepts (low <= high). The affine map handles a pinned dimension exactly (constant column),
    # so Sobol never crashes on a config LHS runs fine on (CASPER; Fable review #589).
    out = np.empty_like(unit)
    for j, (lo, hi) in enumerate(bounds):
        out[:, j] = float(lo) + unit[:, j] * (float(hi) - float(lo))
    return out
