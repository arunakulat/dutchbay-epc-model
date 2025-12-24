# ruff: noqa: E402
"""Latin Hypercube Sampling and sampler utilities.

Keep sampling logic pure, fast, and numpy-based.
No business logic or scenario interpretation here.
"""

from typing import Sequence, Tuple

import numpy as np


def generate_lhs_samples(
    *,
    n_trials: int,
    bounds: Sequence[Tuple[float, float]],
    seed: int,
    common_random_numbers: bool = True,
) -> np.ndarray:
    """Generate Latin Hypercube samples.
    
    Args:
        n_trials: Number of trials
        bounds: List of (low, high) for each parameter
        seed: Random seed for reproducibility
        common_random_numbers: If True, use stable RNG per parameter
        
    Returns:
        Array of shape [n_trials, n_params] with LHS samples
        
    Example:
        >>> bounds = [(0.8, 1.2), (0.9, 1.1)]  # capex, tariff multipliers
        >>> samples = generate_lhs_samples(
        ...     n_trials=1000,
        ...     bounds=bounds,
        ...     seed=42,
        ... )
        >>> samples.shape
        (1000, 2)
    """
    n = int(n_trials)
    n_params = len(bounds)
    
    rng = np.random.default_rng(seed)
    
    # LHS grid: divide [0,1] into n_trials segments
    samples = np.zeros((n, n_params))
    
    for i in range(n_params):
        low, high = bounds[i]
        
        # Generate LHS indices [0, 1, ..., n-1]
        indices = np.arange(n)
        if not common_random_numbers:
            rng.shuffle(indices)
        
        # Map to [0,1] uniform within each segment
        uniform = (indices + rng.uniform(size=n)) / n
        
        # Scale to parameter bounds
        samples[:, i] = low + uniform * (high - low)
    
    # Final shuffle (optional - breaks CRN structure if enabled)
    if not common_random_numbers:
        rng.shuffle(samples)
    
    return samples
