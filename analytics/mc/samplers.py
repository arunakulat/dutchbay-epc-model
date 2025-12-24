# ruff: noqa: E402
from __future__ import annotations

"""
analytics.mc.samplers

Sampling utilities (LHS baseline).
Keep import-light: numpy only.
"""

from typing import List, Sequence, Tuple

import numpy as np


def generate_lhs_samples(
    *,
    n_trials: int,
    bounds: Sequence[Tuple[float, float]],
    seed: int = 123,
    common_random_numbers: bool = True,
) -> np.ndarray:
    """
    Minimal LHS sampler. Replace with your more advanced implementation if you already have it.

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
    pts = u * (b - a)[:, None] + a[:, None]  # [n,1] broadcast -> [n,k] via later operations

    # independent random permutations per dimension
    lhs = np.zeros((n, k), dtype=float)
    for j in range(k):
        perm = rng.permutation(n) if common_random_numbers else np.random.default_rng(int(seed + j)).permutation(n)
        lhs[:, j] = pts[perm, 0]  # take the single column

    # scale to bounds
    out = np.empty_like(lhs)
    for j, (lo, hi) in enumerate(bounds):
        out[:, j] = lo + lhs[:, j] * (hi - lo)

    return out
