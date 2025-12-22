from __future__ import annotations

"""
analytics.mc.samplers

Sampling utilities for Monte Carlo analysis.
Canonical implementation: Latin Hypercube Sampling (LHS).

Keep import-light: numpy only.
No CLI deps, no side effects.
"""

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
    Generate Latin Hypercube Sampling samples within specified bounds.
    
    LHS provides better space-filling properties than pure random sampling,
    improving convergence for Monte Carlo analysis.
    
    Args:
        n_trials: Number of samples to generate
        bounds: List of (low, high) tuples for each parameter
        seed: Random seed for reproducibility
        common_random_numbers: If True, use single RNG for all dimensions
            (better for variance reduction across scenarios)
    
    Returns:
        Array of shape [n_trials, n_params] with samples in specified bounds
    
    Example:
        >>> bounds = [(0.0, 1.0), (100.0, 200.0), (0.05, 0.15)]
        >>> samples = generate_lhs_samples(n_trials=1000, bounds=bounds, seed=42)
        >>> samples.shape
        (1000, 3)
    
    References:
        McKay, M.D., et al. (1979). "A Comparison of Three Methods for Selecting
        Values of Input Variables in the Analysis of Output from a Computer Code."
        Technometrics, 21(2), 239-245.
    """
    n = int(n_trials)
    if n <= 0:
        raise ValueError(f"n_trials must be > 0, got {n}")
    
    k = len(bounds)
    if k == 0:
        raise ValueError("bounds must be non-empty")
    
    # Validate bounds
    for i, (lo, hi) in enumerate(bounds):
        if not (lo < hi):
            raise ValueError(
                f"Invalid bounds for parameter {i}: [{lo}, {hi}]. "
                f"Lower bound must be strictly less than upper bound."
            )
    
    rng = np.random.default_rng(int(seed))
    
    # Generate LHS in unit hypercube [0,1]^k
    # Divide [0,1] into n equal-probability intervals
    cut = np.linspace(0.0, 1.0, n + 1)
    
    # For each interval, sample uniformly within it
    u = rng.uniform(size=(n, k))
    a = cut[:-1]  # interval starts: [0/n, 1/n, ..., (n-1)/n]
    b = cut[1:]   # interval ends:   [1/n, 2/n, ..., n/n]
    
    # Broadcast intervals to match u shape
    intervals = np.column_stack([a, b])  # [n, 2]
    
    # Sample within each interval
    lhs_unit = np.empty((n, k), dtype=float)
    for j in range(k):
        # Permute intervals for this dimension
        if common_random_numbers:
            perm = rng.permutation(n)
        else:
            # Independent RNG per dimension (less correlation between params)
            dim_rng = np.random.default_rng(int(seed + j))
            perm = dim_rng.permutation(n)
        
        # Sample uniformly within permuted intervals
        for i in range(n):
            interval_idx = perm[i]
            lhs_unit[i, j] = a[interval_idx] + u[i, j] * (b[interval_idx] - a[interval_idx])
    
    # Scale from [0,1] to parameter bounds
    out = np.empty_like(lhs_unit)
    for j, (lo, hi) in enumerate(bounds):
        out[:, j] = lo + lhs_unit[:, j] * (hi - lo)
    
    return out


def generate_sobol_samples(
    *,
    n_trials: int,
    bounds: Sequence[Tuple[float, float]],
    seed: int = 123,
) -> np.ndarray:
    """
    Generate Sobol sequence samples (quasi-random low-discrepancy sequence).
    
    Sobol sequences provide better uniformity than LHS for high-dimensional
    problems, but require n_trials to be a power of 2 for optimal properties.
    
    Args:
        n_trials: Number of samples (prefer powers of 2)
        bounds: List of (low, high) tuples for each parameter
        seed: Random seed (for skip parameter in Sobol)
    
    Returns:
        Array of shape [n_trials, n_params]
    
    Note:
        Requires scipy. Falls back to LHS if scipy unavailable.
    """
    try:
        from scipy.stats import qmc
        
        k = len(bounds)
        sampler = qmc.Sobol(d=k, seed=int(seed))
        
        # Generate samples in [0,1]
        sobol_unit = sampler.random(n=int(n_trials))
        
        # Scale to bounds
        out = np.empty_like(sobol_unit)
        for j, (lo, hi) in enumerate(bounds):
            out[:, j] = lo + sobol_unit[:, j] * (hi - lo)
        
        return out
    
    except ImportError:
        # Fallback to LHS if scipy not available
        return generate_lhs_samples(
            n_trials=n_trials,
            bounds=bounds,
            seed=seed,
            common_random_numbers=True,
        )


__all__ = [
    "generate_lhs_samples",
    "generate_sobol_samples",
]
