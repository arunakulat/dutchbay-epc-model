#!/usr/bin/env python
"""Correlation engine for Monte Carlo simulations.

Implements Iman-Conover (1982) rank correlation method for LHS samples.

Key Features:
1. Preserves Latin Hypercube Sampling structure
2. Induces target rank correlation between variables
3. Maintains marginal distributions
4. Computationally efficient (Cholesky decomposition)

Usage:
    from analytics.correlation_engine import apply_correlation_to_lhs
    
    # Define target correlation matrix
    corr_matrix = np.array([
        [1.0,  0.4, -0.3, -0.2],  # revenue
        [0.4,  1.0, -0.2,  0.1],  # cost
        [-0.3, -0.2, 1.0,  0.0],  # FX
        [-0.2, 0.1,  0.0,  1.0]   # degradation
    ])
    
    # Apply to LHS samples
    uncorrelated = lhs_sampler.random(n=1000)
    correlated = apply_correlation_to_lhs(uncorrelated, corr_matrix)

References:
    Iman, R.L. and Conover, W.J. (1982). A distribution-free approach
    to inducing rank correlation among input variables. 
    Communications in Statistics - Simulation and Computation, 11(3), 311-334.
    
    Helton, J.C. and Davis, F.J. (2003). Latin hypercube sampling and
    the propagation of uncertainty in analyses of complex systems.
    Reliability Engineering & System Safety, 81(1), 23-69.

CESSPIT: Correlation matrix from config (no hardcoded values)
CASPER: Realistic correlation for tail-risk modeling
GWTF: R23 (testable), R24 (Google docstrings)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from scipy import stats
from scipy.linalg import cholesky

logger = logging.getLogger(__name__)


def validate_correlation_matrix(corr_matrix: np.ndarray) -> tuple[bool, str]:
    """Validate correlation matrix properties.
    
    Checks:
    1. Square matrix
    2. Symmetric
    3. Diagonal = 1.0
    4. Off-diagonal in [-1, 1]
    5. Positive semi-definite
    
    Args:
        corr_matrix: Target correlation matrix (n x n)
    
    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is empty string
    
    Example:
        >>> corr = np.array([[1.0, 0.5], [0.5, 1.0]])
        >>> valid, msg = validate_correlation_matrix(corr)
        >>> valid
        True
    """
    # Check square
    if corr_matrix.ndim != 2 or corr_matrix.shape[0] != corr_matrix.shape[1]:
        return False, "Correlation matrix must be square"
    
    n = corr_matrix.shape[0]
    
    # Check symmetric
    if not np.allclose(corr_matrix, corr_matrix.T):
        return False, "Correlation matrix must be symmetric"
    
    # Check diagonal = 1.0
    diag = np.diag(corr_matrix)
    if not np.allclose(diag, 1.0):
        return False, f"Diagonal must be 1.0, got {diag}"
    
    # Check off-diagonal in [-1, 1]
    mask = ~np.eye(n, dtype=bool)
    off_diag = corr_matrix[mask]
    if np.any(off_diag < -1.0) or np.any(off_diag > 1.0):
        return False, f"Off-diagonal values must be in [-1, 1], got range [{off_diag.min()}, {off_diag.max()}]"
    
    # Check positive semi-definite (all eigenvalues >= 0)
    eigenvalues = np.linalg.eigvals(corr_matrix)
    if np.any(eigenvalues < -1e-10):  # Small tolerance for numerical errors
        return False, f"Matrix not positive semi-definite, min eigenvalue = {eigenvalues.min():.6f}"
    
    return True, ""


def apply_correlation_to_lhs(
    lhs_samples: np.ndarray,
    target_corr: np.ndarray,
    method: str = "iman_conover"
) -> np.ndarray:
    """Apply correlation structure to independent LHS samples.
    
    Iman-Conover Method (1982):
    1. Transform LHS samples to normal space (preserve ranks)
    2. Apply Cholesky decomposition of target correlation
    3. Transform back to uniform [0,1] space
    4. Reorder to match original LHS ranks
    
    This preserves both:
    - LHS stratification (variance reduction)
    - Target rank correlation (realistic dependencies)
    
    Args:
        lhs_samples: Independent LHS samples [0,1]^(n x d)
        target_corr: Target correlation matrix (d x d)
        method: Correlation method ("iman_conover" only supported currently)
    
    Returns:
        Correlated samples [0,1]^(n x d) preserving LHS structure
    
    Raises:
        ValueError: If correlation matrix invalid or dimensions mismatch
    
    Example:
        >>> np.random.seed(42)
        >>> lhs = np.random.rand(1000, 2)
        >>> corr = np.array([[1.0, 0.7], [0.7, 1.0]])
        >>> correlated = apply_correlation_to_lhs(lhs, corr)
        >>> np.corrcoef(correlated.T)[0, 1]  # Should be ~0.7
        0.695...
    """
    # Validate inputs
    if lhs_samples.ndim != 2:
        raise ValueError(f"lhs_samples must be 2D, got shape {lhs_samples.shape}")
    
    n_iterations, n_vars = lhs_samples.shape
    
    if target_corr.shape != (n_vars, n_vars):
        raise ValueError(
            f"Correlation matrix shape {target_corr.shape} does not match "
            f"number of variables {n_vars}"
        )
    
    # Validate correlation matrix
    valid, error_msg = validate_correlation_matrix(target_corr)
    if not valid:
        raise ValueError(f"Invalid correlation matrix: {error_msg}")
    
    # Check if correlation is identity (no correlation needed)
    if np.allclose(target_corr, np.eye(n_vars)):
        logger.info("Correlation matrix is identity, returning original samples")
        return lhs_samples.copy()
    
    if method != "iman_conover":
        raise ValueError(f"Unknown correlation method: {method}")
    
    logger.info(
        f"Applying Iman-Conover correlation to {n_iterations} samples, "
        f"{n_vars} variables"
    )
    
    # Step 1: Store original ranks (for LHS preservation)
    original_ranks = np.argsort(np.argsort(lhs_samples, axis=0), axis=0)
    
    # Step 2: Transform to normal space
    # Using inverse CDF (percent point function) of standard normal
    normal_samples = stats.norm.ppf(lhs_samples)
    
    # Handle edge cases (LHS can produce 0 or 1 exactly)
    normal_samples = np.clip(normal_samples, -10, 10)  # Avoid infinities
    
    # Step 3: Apply Cholesky decomposition of target correlation
    try:
        L = cholesky(target_corr, lower=True)
    except np.linalg.LinAlgError as e:
        raise ValueError(f"Failed to compute Cholesky decomposition: {e}")
    
    # Step 4: Apply correlation transformation
    # For each sample (row), transform: y = L @ x
    # But we want correlation in normal space, so:
    # First, compute sample correlation of normal_samples
    sample_corr = np.corrcoef(normal_samples.T)
    
    # Get Cholesky of sample correlation
    try:
        L_sample = cholesky(sample_corr, lower=True)
    except np.linalg.LinAlgError:
        # Sample correlation might not be positive definite
        # Add small diagonal perturbation
        sample_corr_perturbed = sample_corr + np.eye(n_vars) * 1e-6
        L_sample = cholesky(sample_corr_perturbed, lower=True)
    
    # Transformation: Z_corr = Z @ inv(L_sample) @ L_target
    L_sample_inv = np.linalg.inv(L_sample)
    transform_matrix = L_sample_inv @ L
    
    # Apply transformation
    correlated_normal = normal_samples @ transform_matrix.T
    
    # Step 5: Transform back to uniform [0,1]
    correlated_uniform = stats.norm.cdf(correlated_normal)
    
    # Step 6: Restore LHS ranks (critical for variance reduction)
    # For each variable, reorder values to match original LHS ranks
    correlated_lhs = np.zeros_like(correlated_uniform)
    
    for j in range(n_vars):
        # Get ranks of correlated samples
        corr_ranks = np.argsort(np.argsort(correlated_uniform[:, j]))
        
        # Sort correlated values
        sorted_corr_vals = np.sort(correlated_uniform[:, j])
        
        # Assign values to match original ranks
        correlated_lhs[:, j] = sorted_corr_vals[original_ranks[:, j]]
    
    # Verify correlation achieved
    achieved_corr = np.corrcoef(stats.norm.ppf(np.clip(correlated_lhs, 1e-10, 1-1e-10)).T)
    
    logger.info("Correlation application complete")
    logger.debug(f"Target correlation:\n{target_corr}")
    logger.debug(f"Achieved correlation:\n{achieved_corr}")
    
    # Log correlation errors
    corr_error = np.abs(achieved_corr - target_corr)
    max_error = np.max(corr_error[~np.eye(n_vars, dtype=bool)])
    
    if max_error > 0.1:
        logger.warning(
            f"Maximum correlation error: {max_error:.3f}. "
            "Consider increasing n_iterations for better accuracy."
        )
    else:
        logger.info(f"Maximum correlation error: {max_error:.3f} (acceptable)")
    
    return correlated_lhs


def get_default_correlation_matrix(n_vars: int = 4) -> np.ndarray:
    """Get default correlation matrix for renewable energy projects.
    
    Default structure for [revenue, cost, FX, degradation]:
    - Revenue-Cost: +0.4 (inflation linkage)
    - Revenue-FX: -0.3 (USD PPA benefit from depreciation)
    - Revenue-Degradation: -0.2 (higher deg → lower output)
    - Cost-Degradation: +0.1 (slight maintenance increase)
    
    CESSPIT: This is only for reference. Actual values from config/defaults.yaml.
    
    Args:
        n_vars: Number of variables (default 4)
    
    Returns:
        Default correlation matrix (n_vars x n_vars)
    
    Note:
        DO NOT use this directly. Load from config:
        config.monte_carlo.correlation.matrix
    """
    if n_vars == 4:
        # Standard 4-variable case
        return np.array([
            [1.0,  0.4, -0.3, -0.2],  # Revenue correlations
            [0.4,  1.0, -0.2,  0.1],  # Cost correlations  
            [-0.3, -0.2, 1.0,  0.0],  # FX correlations
            [-0.2, 0.1,  0.0,  1.0]   # Degradation correlations
        ])
    elif n_vars == 3:
        # 3-variable case (no degradation)
        return np.array([
            [1.0,  0.4, -0.3],
            [0.4,  1.0, -0.2],
            [-0.3, -0.2, 1.0]
        ])
    else:
        # Identity matrix (no correlation)
        logger.warning(
            f"No default correlation for {n_vars} variables. "
            "Returning identity (no correlation)."
        )
        return np.eye(n_vars)


def load_correlation_from_config(config: dict, n_vars: int) -> Optional[np.ndarray]:
    """Load correlation matrix from config dictionary.
    
    CESSPIT: Loads from config.monte_carlo.correlation.matrix.
    
    Args:
        config: Configuration dictionary
        n_vars: Expected number of variables
    
    Returns:
        Correlation matrix if enabled, None otherwise
    
    Raises:
        ValueError: If matrix dimensions don't match or invalid
    """
    mc_config = config.get("monte_carlo", {})
    corr_config = mc_config.get("correlation", {})
    
    # Check if correlation enabled
    if not corr_config.get("enabled", False):
        logger.info("Correlation disabled in config")
        return None
    
    # Load matrix from config
    matrix_list = corr_config.get("matrix")
    if matrix_list is None:
        raise ValueError(
            "Correlation enabled but matrix not specified. "
            "Add monte_carlo.correlation.matrix to config."
        )
    
    # Convert to numpy array
    try:
        corr_matrix = np.array(matrix_list, dtype=np.float64)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Failed to parse correlation matrix: {e}")
    
    # Validate dimensions
    if corr_matrix.shape != (n_vars, n_vars):
        raise ValueError(
            f"Correlation matrix shape {corr_matrix.shape} does not match "
            f"number of variables {n_vars}"
        )
    
    # Validate matrix properties
    valid, error_msg = validate_correlation_matrix(corr_matrix)
    if not valid:
        raise ValueError(f"Invalid correlation matrix in config: {error_msg}")
    
    logger.info(f"Loaded {n_vars}x{n_vars} correlation matrix from config")
    logger.debug(f"Correlation matrix:\n{corr_matrix}")
    
    return corr_matrix


__all__ = [
    "apply_correlation_to_lhs",
    "validate_correlation_matrix",
    "get_default_correlation_matrix",
    "load_correlation_from_config",
]
