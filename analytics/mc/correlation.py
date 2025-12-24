"""Correlation structure for Monte Carlo sampling.

Implements Iman-Conover rank correlation method for inducing
correlation structure on independent LHS samples.

References:
    Iman, R. L., & Conover, W. J. (1982). A distribution-free approach
    to inducing rank correlation among input variables. Communications
    in Statistics-Simulation and Computation, 11(3), 311-334.

DOLPHIN #10b: Removed unused `ranks` variable in _apply_iman_conover_correlation
DOLPHIN #10d: Removed unused imports (Any, Optional)
"""

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class CorrelationSpec:
    """Correlation specification between parameters.
    
    Attributes:
        param_pairs: List of (param1, param2, correlation) tuples
            where correlation is between -1 and 1.
        
    Example:
        >>> spec = CorrelationSpec(param_pairs=[
        ...     ("capex", "opex", 0.6),
        ...     ("capacity_factor", "tariff", -0.3),
        ... ])
    """
    param_pairs: Sequence[Tuple[str, str, float]]


def apply_correlation_structure(
    samples: Mapping[str, Sequence[float]],
    correlation_spec: CorrelationSpec,
) -> Dict[str, Sequence[float]]:
    """Apply correlation structure to independent samples.
    
    Uses Iman-Conover method to induce rank correlation.
    
    Args:
        samples: Independent samples {param: [values]}
        correlation_spec: Desired correlation structure
        
    Returns:
        Correlated samples {param: [values]}
        
    Example:
        >>> samples = {"capex": [100, 110, 120], "opex": [10, 11, 12]}
        >>> spec = CorrelationSpec([("capex", "opex", 0.8)])
        >>> correlated = apply_correlation_structure(samples, spec)
    """
    # Extract parameter names and sample matrix
    param_names = list(samples.keys())
    x = np.column_stack([samples[p] for p in param_names])
    
    # Build correlation matrix
    n_params = len(param_names)
    corr_matrix = np.eye(n_params)
    
    for param1, param2, corr in correlation_spec.param_pairs:
        i = param_names.index(param1)
        j = param_names.index(param2)
        corr_matrix[i, j] = corr
        corr_matrix[j, i] = corr  # Symmetric
    
    # Apply Iman-Conover
    x_correlated = _apply_iman_conover_correlation(x, corr_matrix)
    
    # Return as dict
    return {
        param: x_correlated[:, i].tolist()
        for i, param in enumerate(param_names)
    }


def _apply_iman_conover_correlation(
    x: np.ndarray,
    target_corr: np.ndarray,
) -> np.ndarray:
    """Apply Iman-Conover rank correlation method.
    
    Args:
        x: Input samples (n_samples, n_params)
        target_corr: Target correlation matrix (n_params, n_params)
        
    Returns:
        Correlated samples (n_samples, n_params)
    """
    # Rank transformation applied via argsort
    # correlated normals
    z = np.random.multivariate_normal(
        mean=np.zeros(x.shape[1]),
        cov=target_corr,
        size=x.shape[0],
    )
    
    # Match ranks
    x_sorted = np.sort(x, axis=0)
    z_ranks = np.argsort(np.argsort(z, axis=0), axis=0)
    
    # Reorder x to match z's rank structure
    x_correlated = np.zeros_like(x)
    for col in range(x.shape[1]):
        x_correlated[:, col] = x_sorted[z_ranks[:, col], col]
    
    return x_correlated
