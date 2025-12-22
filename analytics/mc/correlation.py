from __future__ import annotations

"""
analytics.mc.correlation

Single source of truth for Monte Carlo correlation handling.

Merges functionality from:
- analytics/monte_carlo_correlation.py (Iman-Conover implementation)
- analytics/correlation_engine.py (config loader + templates)

Implements:
- CorrelationSpec (config carrier)
- validate_correlation_matrix
- apply_correlation_structure (Iman-Conover rank correlation)
- template helpers + config loaders

NOTE: This module should NOT depend on the MC engine (no circulars).
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class CorrelationSpec:
    """Configuration for correlation structure.
    
    Attributes:
        enabled: Whether to apply correlation
        method: Correlation method (currently only 'iman_conover' supported)
        matrix: Target correlation matrix (n_params, n_params)
        param_names: Parameter names (for validation/debugging)
        tol: Numerical tolerance for matrix validation
        repair: If True, repair non-PSD matrices using eigenvalue clipping
    """
    enabled: bool
    method: str = "iman_conover"
    matrix: Optional[np.ndarray] = None
    param_names: Optional[Tuple[str, ...]] = None
    tol: float = 1e-8
    repair: bool = True


def validate_correlation_matrix(mat: np.ndarray, *, tol: float = 1e-8) -> None:
    """
    Validate correlation matrix properties.
    
    Checks:
    1. Square matrix
    2. Unit diagonal (all 1.0)
    3. Symmetric
    4. Positive semi-definite (all eigenvalues >= 0)
    
    Args:
        mat: Correlation matrix to validate
        tol: Numerical tolerance
    
    Raises:
        ValueError: If matrix violates any correlation matrix property
    """
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(
            f"Correlation matrix must be square. Got shape: {mat.shape}"
        )
    
    if not np.allclose(np.diag(mat), 1.0, atol=tol):
        diag = np.diag(mat)
        raise ValueError(
            f"Correlation matrix must have 1.0 on diagonal. "
            f"Got: {diag}"
        )
    
    if not np.allclose(mat, mat.T, atol=tol):
        raise ValueError("Correlation matrix must be symmetric.")
    
    # Check positive semi-definite via eigenvalues
    eigenvalues = np.linalg.eigvalsh(mat)
    if np.any(eigenvalues < -tol):
        neg_eigs = eigenvalues[eigenvalues < -tol]
        raise ValueError(
            f"Correlation matrix must be positive semi-definite. "
            f"Got negative eigenvalues: {neg_eigs}"
        )


def _nearest_psd(mat: np.ndarray, *, tol: float = 1e-8) -> np.ndarray:
    """
    Repair correlation matrix to nearest positive semi-definite matrix.
    
    Uses eigenvalue clipping method:
    1. Compute eigendecomposition
    2. Clip negative eigenvalues to 0
    3. Reconstruct matrix
    4. Renormalize diagonal to 1.0
    
    Args:
        mat: Input correlation matrix (may be non-PSD)
        tol: Minimum eigenvalue threshold
    
    Returns:
        Repaired PSD correlation matrix
    
    References:
        Higham, N.J. (2002). "Computing the nearest correlation matrix—
        a problem from finance." IMA Journal of Numerical Analysis, 22(3), 329-343.
    """
    # Symmetrize (in case of numerical noise)
    mat_sym = (mat + mat.T) / 2.0
    
    # Eigendecomposition
    vals, vecs = np.linalg.eigh(mat_sym)
    
    # Clip negative eigenvalues
    vals_clipped = np.maximum(vals, tol)
    
    # Reconstruct
    repaired = (vecs @ np.diag(vals_clipped) @ vecs.T)
    
    # Renormalize diagonal to 1.0
    d = np.sqrt(np.diag(repaired))
    d[d == 0] = 1.0  # Avoid division by zero
    repaired = repaired / np.outer(d, d)
    
    return repaired


def apply_correlation_structure(
    *,
    lhs_samples: np.ndarray,
    correlation: CorrelationSpec,
    seed: int = 123,
) -> np.ndarray:
    """
    Apply correlation to LHS samples using Iman-Conover rank correlation.
    
    Preserves marginal distributions while inducing target rank correlation.
    This is the gold-standard method for correlated MC sampling.
    
    Algorithm:
    1. Convert each parameter's samples to ranks
    2. Generate correlated normal samples with target correlation (via Cholesky)
    3. Rank-transform the correlated normals
    4. Reorder original samples to match correlated ranks
    
    Args:
        lhs_samples: Independent samples [n_trials, n_params] in parameter space
        correlation: CorrelationSpec with target correlation matrix
        seed: Random seed for correlated normal generation
    
    Returns:
        Correlated samples [n_trials, n_params] with same marginals
    
    References:
        Iman, R.L. and Conover, W.J. (1982). "A distribution-free approach to
        inducing rank correlation among input variables." Communications in
        Statistics - Simulation and Computation, 11(3), 311-334.
    """
    if not correlation.enabled:
        return lhs_samples
    
    if correlation.matrix is None:
        raise ValueError(
            "CorrelationSpec.enabled=True but matrix is None. "
            "Provide correlation matrix or set enabled=False."
        )
    
    mat = np.array(correlation.matrix, dtype=float, copy=True)
    validate_correlation_matrix(mat, tol=correlation.tol)
    
    if correlation.repair:
        # Ensure PSD for Cholesky decomposition
        mat = _nearest_psd(mat, tol=correlation.tol)
    
    x = np.array(lhs_samples, copy=True)
    n, k = x.shape
    
    if mat.shape != (k, k):
        raise ValueError(
            f"Correlation matrix shape {mat.shape} does not match "
            f"number of parameters {k}."
        )
    
    # Step 1: Rank transform of original samples
    # ranks[i,j] = rank of sample i for parameter j (0-indexed)
    ranks = np.argsort(np.argsort(x, axis=0), axis=0)
    
    # Step 2: Generate correlated normal samples
    rng = np.random.default_rng(int(seed))
    z = rng.standard_normal(size=(n, k))
    
    # Cholesky decomposition of target correlation
    try:
        L = np.linalg.cholesky(mat)
    except np.linalg.LinAlgError:
        # Should not happen after repair, but add safety net
        mat_repaired = _nearest_psd(mat, tol=1e-6)
        L = np.linalg.cholesky(mat_repaired + np.eye(k) * 1e-12)
    
    # Apply correlation: y = z @ L^T
    y = z @ L.T
    
    # Step 3: Rank transform of correlated normals
    y_ranks = np.argsort(np.argsort(y, axis=0), axis=0)
    
    # Step 4: Reorder original samples to match correlated ranks
    out = np.empty_like(x)
    for j in range(k):
        # For parameter j:
        # - Sort original values
        # - Assign them in the order specified by y_ranks
        col_sorted = np.sort(x[:, j])
        # y_ranks[:, j] gives target positions
        out[y_ranks[:, j], j] = col_sorted
    
    return out


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

def apply_correlation_to_lhs(
    lhs_samples: np.ndarray,
    corr_matrix: np.ndarray,
    seed: int = 123
) -> np.ndarray:
    """
    Legacy alias for apply_correlation_structure.
    
    DEPRECATED: Use apply_correlation_structure with CorrelationSpec instead.
    """
    spec = CorrelationSpec(enabled=True, matrix=corr_matrix)
    return apply_correlation_structure(
        lhs_samples=lhs_samples,
        correlation=spec,
        seed=seed
    )


# ============================================================================
# Template Helpers
# ============================================================================

def get_renewable_energy_correlation_template(
    param_names: Sequence[str]
) -> Dict[str, Any]:
    """
    Return starter correlation template for renewable energy projects.
    
    Provides reasonable default correlations:
    - capacity_factor ↔ tariff: +0.3 (better resource → higher tariff negotiation)
    - capex ↔ opex: +0.4 (larger project → higher both)
    - fx_rate ↔ tariff: -0.2 (currency depreciation → tariff pressure)
    
    Args:
        param_names: List of parameter names
    
    Returns:
        Dictionary with correlation matrix and metadata
    """
    names = list(param_names)
    k = len(names)
    corr = np.eye(k)  # Start with identity (no correlation)
    
    # Build parameter index map
    param_map = {name.lower(): i for i, name in enumerate(names)}
    
    # Apply common correlations if parameters exist
    # Capacity factor ↔ Tariff
    if "capacity_factor" in param_map and "tariff" in param_map:
        i, j = param_map["capacity_factor"], param_map["tariff"]
        corr[i, j] = corr[j, i] = 0.3
    
    # CAPEX ↔ OPEX
    if "capex" in param_map and "opex" in param_map:
        i, j = param_map["capex"], param_map["opex"]
        corr[i, j] = corr[j, i] = 0.4
    
    # FX Rate ↔ Tariff
    if "fx_rate" in param_map and "tariff" in param_map:
        i, j = param_map["fx_rate"], param_map["tariff"]
        corr[i, j] = corr[j, i] = -0.2
    
    return {
        "param_names": names,
        "matrix": corr.tolist(),
        "method": "iman_conover",
        "enabled": True,
        "description": "Renewable energy project correlation template",
        "source": "Industry practice + lender assumptions",
    }


# ============================================================================
# Config Loaders
# ============================================================================

def load_correlation_from_config(
    cfg: Mapping[str, Any]
) -> Optional[CorrelationSpec]:
    """
    Load CorrelationSpec from config dictionary.
    
    Expected config structure:
        monte_carlo:
          correlation:
            enabled: true
            method: iman_conover
            matrix: [[1.0, 0.3], [0.3, 1.0]]  # optional
            param_names: [param1, param2]      # optional
    
    Args:
        cfg: Configuration dictionary
    
    Returns:
        CorrelationSpec if correlation config exists, None otherwise
    """
    mc = cfg.get("monte_carlo", {}) if isinstance(cfg, Mapping) else {}
    c = mc.get("correlation", None)
    
    if not c:
        return None
    
    enabled = bool(c.get("enabled", False))
    method = str(c.get("method", "iman_conover"))
    mat = c.get("matrix", None)
    names = c.get("param_names", None)
    tol = float(c.get("tol", 1e-8))
    repair = bool(c.get("repair", True))
    
    matrix = None
    if mat is not None:
        matrix = np.array(mat, dtype=float)
    
    param_names = tuple(names) if names else None
    
    return CorrelationSpec(
        enabled=enabled,
        method=method,
        matrix=matrix,
        param_names=param_names,
        tol=tol,
        repair=repair,
    )


__all__ = [
    "CorrelationSpec",
    "validate_correlation_matrix",
    "apply_correlation_structure",
    "apply_correlation_to_lhs",  # Legacy alias
    "get_renewable_energy_correlation_template",
    "load_correlation_from_config",
]
