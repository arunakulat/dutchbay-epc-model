# ruff: noqa: E402
from __future__ import annotations

"""
analytics.mc.samplers

Latin Hypercube and related sampler utilities.
Keeps the sampling logic separate from the main engine.
"""

from typing import Sequence, Tuple

import numpy as np
from scipy.stats import qmc  # type: ignore


def generate_lhs_samples(
    n_trials: int,
    bounds: Sequence[Tuple[float, float]],
    *,
    seed: int = 123,
    common_random_numbers: bool = True,
) -> np.ndarray:
    """
    Generate Latin Hypercube Sampling (LHS) within given bounds.
    
    Args:
        n_trials: number of samples
        bounds: list of (low, high) for each dimension
        seed: random seed
        common_random_numbers: if True, uses consistent RNG for reproducibility
        
    Returns:
        np.ndarray of shape (n_trials, n_dims)
    """
    n = int(n_trials)
    d = len(bounds)
    if d == 0:
        raise ValueError("bounds must be non-empty")
    if n <= 0:
        raise ValueError("n_trials must be positive")

    # Construct LHS sampler
    sampler = qmc.LatinHypercube(d=d, seed=int(seed) if common_random_numbers else None)
    unit_samples = sampler.random(n=n)  # shape: (n, d) in [0,1]^d

    # Scale to bounds
    samples = np.empty((n, d), dtype=float)
    for i, (lo, hi) in enumerate(bounds):
        samples[:, i] = float(lo) + unit_samples[:, i] * (float(hi) - float(lo))

    return samples
