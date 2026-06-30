"""
analytics.mc.correlation

Single source of truth for Monte Carlo correlation handling.

Implements:
- CorrelationSpec (config carrier)
- validate_correlation_matrix
- apply_correlation_structure (Iman-Conover rank correlation)
- template helpers + config loaders

NOTE: This module should NOT depend on the MC engine (no circulars).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, cast

import numpy as np


@dataclass(frozen=True)
class CorrelationSpec:
    enabled: bool
    method: str = "iman_conover"  # future: gaussian_copula, cholesky
    matrix: Optional[np.ndarray] = None
    param_names: Optional[Tuple[str, ...]] = None

    # optional: tolerance and repair flags
    tol: float = 1e-8
    repair: bool = True


def validate_correlation_matrix(mat: np.ndarray, *, tol: float = 1e-8) -> None:
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError("Correlation matrix must be square.")
    if not np.allclose(np.diag(mat), 1.0, atol=tol):
        raise ValueError("Correlation matrix must have 1.0 on the diagonal.")
    if not np.allclose(mat, mat.T, atol=tol):
        raise ValueError("Correlation matrix must be symmetric.")


def _nearest_psd(mat: np.ndarray) -> np.ndarray:
    """
    Minimal nearest-PSD repair (eigenvalue clipping).
    Good enough for correlation repair; keep deterministic.
    """
    vals, vecs = np.linalg.eigh(mat)
    vals = np.clip(vals, 0.0, None)
    repaired = vecs @ np.diag(vals) @ vecs.T
    # re-normalize to unit diagonal
    d = np.sqrt(np.diag(repaired))
    d[d == 0] = 1.0
    repaired = repaired / np.outer(d, d)
    return cast("np.ndarray", repaired)


def apply_correlation_structure(
    *,
    lhs_samples: np.ndarray,
    correlation: CorrelationSpec,
    seed: int = 123,
) -> np.ndarray:
    """
    Apply correlation to an LHS sample matrix using Iman-Conover rank correlation.

    Inputs:
      lhs_samples: shape [n_trials, n_params], assumed iid-ish (LHS in [low,high] domain)
      correlation.matrix: target correlation matrix over parameters

    Output:
      correlated_samples: same shape

    Canonical, tested implementation: nearest-PSD repair + Cholesky factorisation +
    rank-reordering (Iman-Conover) to induce the target correlation while preserving
    each input's marginal distribution.
    """
    if not correlation.enabled:
        return lhs_samples
    if correlation.matrix is None:
        raise ValueError("CorrelationSpec.enabled=True but matrix is None.")

    mat = np.array(correlation.matrix, dtype=float, copy=True)
    validate_correlation_matrix(mat, tol=correlation.tol)

    if correlation.repair:
        # Ensure PSD-ish for decomposition steps
        mat = _nearest_psd(mat)

    # Skeleton IC method:
    # 1) convert each column to ranks
    # 2) generate correlated normal scores using Cholesky of target corr
    # 3) reorder samples to match correlated ranks
    x = np.array(lhs_samples, copy=True)
    n, k = x.shape
    if mat.shape != (k, k):
        raise ValueError(
            f"Correlation matrix shape {mat.shape} does not match samples columns {k}."
        )

    # correlated normals
    rng = np.random.default_rng(int(seed))
    z = rng.standard_normal(size=(n, k))
    # Cholesky may fail if mat not PSD; nearest_psd should help.
    L = np.linalg.cholesky(mat + np.eye(k) * 1e-12)
    y = z @ L.T

    # ranks of correlated normals
    y_ranks = np.argsort(np.argsort(y, axis=0), axis=0)

    # reorder each column of x by y_ranks
    out = np.empty_like(x)
    for j in range(k):
        # map: target order is y_ranks; pick from x sorted by original ranks
        col_sorted = np.sort(x[:, j])
        out[y_ranks[:, j], j] = col_sorted

    return out


# Back-compat aliases (some older scripts use these names)
def apply_correlation_to_lhs(
    lhs_samples: np.ndarray, corr_matrix: np.ndarray, seed: int = 123
) -> np.ndarray:
    spec = CorrelationSpec(enabled=True, matrix=corr_matrix)
    return apply_correlation_structure(
        lhs_samples=lhs_samples, correlation=spec, seed=seed
    )


def get_renewable_energy_correlation_template(
    param_names: Sequence[str],
) -> Dict[str, Any]:
    """
    Return a starter template (identity matrix) that callers can customize.
    """
    names = list(param_names)
    k = len(names)
    return {
        "param_names": names,
        "matrix": np.eye(k).tolist(),
        "method": "iman_conover",
        "enabled": True,
    }


def load_correlation_from_config(cfg: Mapping[str, Any]) -> Optional[CorrelationSpec]:
    """
    Load CorrelationSpec from a config dict.
    Keep this permissive but explicit.
    """
    mc = cfg.get("monte_carlo", {}) if isinstance(cfg, Mapping) else {}
    c = mc.get("correlation", None)
    if not c:
        return None

    enabled = bool(c.get("enabled", False))
    method = str(c.get("method", "iman_conover"))
    mat = c.get("matrix", None)
    names = c.get("param_names", None)

    matrix = None
    if mat is not None:
        matrix = np.array(mat, dtype=float)

    param_names = tuple(names) if names else None
    return CorrelationSpec(
        enabled=enabled, method=method, matrix=matrix, param_names=param_names
    )


def align_correlation_to_params(
    spec: Optional[CorrelationSpec], active_param_names: Sequence[str]
) -> Optional[CorrelationSpec]:
    """Re-index a CorrelationSpec's matrix onto the engine's ACTIVE parameter set.

    A scenario authors its correlation matrix against the parameters it declares (in order),
    naming them in ``spec.param_names``. But a consumer can OVERRIDE ``monte_carlo.parameters``
    to a different/smaller set (e.g. the fx-calibration mode samples a single ``fx_calibrated``
    driver) while inheriting the scenario's ``correlation`` block. The full matrix would then
    not match the active column count and ``apply_correlation_structure`` would raise.

    This builds an ``n_active x n_active`` matrix in ``active_param_names`` order: an entry is
    taken from ``spec.matrix`` when BOTH active params are named in ``spec.param_names``, else
    it defaults to the identity (uncorrelated). If fewer than two active params carry any
    off-diagonal correlation, the result is the identity (independent sampling). Returns the
    spec unchanged when there is no matrix/param_names to align, or it already matches.
    """
    if spec is None or spec.matrix is None or not spec.enabled:
        return spec
    active = list(active_param_names)
    k = len(active)
    src_names = list(spec.param_names) if spec.param_names else None
    # Without names we cannot safely re-index; defer to the existing exact-shape check.
    if src_names is None:
        return spec
    if list(src_names) == active:
        return spec  # already aligned (the common case) -> byte-identical
    src_index = {name: i for i, name in enumerate(src_names)}
    aligned = np.eye(k, dtype=float)
    src = np.asarray(spec.matrix, dtype=float)
    for a in range(k):
        ia = src_index.get(active[a])
        if ia is None:
            continue
        for b in range(a + 1, k):
            ib = src_index.get(active[b])
            if ib is None:
                continue
            aligned[a][b] = aligned[b][a] = float(src[ia][ib])
    return CorrelationSpec(
        enabled=spec.enabled,
        method=spec.method,
        matrix=aligned,
        param_names=tuple(active),
        tol=spec.tol,
        repair=spec.repair,
    )
