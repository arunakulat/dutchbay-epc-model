"""
analytics.mc.correlation

Single source of truth for Monte Carlo correlation handling.

Implements:
- CorrelationSpec (config carrier)
- validate_correlation_matrix
- apply_correlation_structure (method dispatch: Iman-Conover rank correlation by
  default; opt-in exact-normal-scores Gaussian copula; unknown methods fail loud)
- template helpers + config loaders

NOTE: This module should NOT depend on the MC engine (no circulars).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, cast

import numpy as np

#: Dependence-induction methods apply_correlation_structure can dispatch to.
#: Anything else fails loud at apply time (CESSPIT) — a config typo must not
#: silently run Iman-Conover while claiming another structure.
SUPPORTED_CORRELATION_METHODS: Tuple[str, ...] = ("iman_conover", "gaussian_copula")


@dataclass(frozen=True)
class CorrelationSpec:
    enabled: bool
    # "iman_conover" (default) or opt-in "gaussian_copula"; see
    # SUPPORTED_CORRELATION_METHODS and the apply_correlation_structure docstring.
    method: str = "iman_conover"
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


def _exact_normal_scores(z: np.ndarray, chol_target: np.ndarray) -> np.ndarray:
    """Recorrelate raw normal scores so their SAMPLE correlation is exactly the target.

    Whitens the centred score matrix against its own sample covariance (Cholesky
    solve), then recorrelates with the target Cholesky factor. The result's sample
    Pearson correlation equals ``chol_target @ chol_target.T`` exactly (to floating
    point), removing the O(1/sqrt(n)) sampling error the raw draws carry.

    Args:
      z: raw standard-normal draws, shape [n_trials, n_params].
      chol_target: lower Cholesky factor of the target correlation matrix.

    Returns:
      Correlated normal scores, shape [n_trials, n_params].

    Raises:
      ValueError: if n_trials <= n_params (the sample covariance of the scores is
        singular, so the exact whitening step is undefined).
    """
    n, k = z.shape
    if n <= k:
        raise ValueError(
            "method='gaussian_copula' requires n_trials > n_params for the exact "
            f"normal-scores whitening (got n_trials={n}, n_params={k})."
        )
    centred = z - z.mean(axis=0, keepdims=True)
    # Denominator is irrelevant: only the RANKS of the scores are consumed downstream,
    # and a uniform covariance rescale cannot change them.
    sample_cov = (centred.T @ centred) / float(n)
    try:
        chol_sample = np.linalg.cholesky(sample_cov)
    except np.linalg.LinAlgError as exc:  # pragma: no cover - n > k makes this a.s. PD
        raise ValueError(
            "method='gaussian_copula' whitening failed: the raw normal scores have "
            "a singular sample covariance; increase n_trials."
        ) from exc
    whitened = np.linalg.solve(chol_sample, centred.T).T  # sample cov == identity
    return cast("np.ndarray", whitened @ chol_target.T)


def apply_correlation_structure(
    *,
    lhs_samples: np.ndarray,
    correlation: CorrelationSpec,
    seed: int = 123,
) -> np.ndarray:
    """
    Apply a dependence structure to an LHS/QMC sample matrix, dispatching on
    ``correlation.method``. Both methods only reorder values WITHIN each column
    (a pure permutation), so every marginal distribution is preserved exactly.

    Methods:
      - ``iman_conover`` (default; bit-identical to the historical single-path code):
        Iman-Conover rank reordering. Correlated normal scores ``y = z @ L.T`` are
        built from the RAW standard-normal draws and each sample column is gathered
        by the score column's ranks. APPROXIMATE Spearman (per the SOTA link-research
        digest): the raw scores carry O(1/sqrt(n)) sampling error in their own
        correlation, so the induced rank correlation scatters around the target.
      - ``gaussian_copula`` (opt-in): Gaussian-copula dependence with EXACT normal
        scores. The raw draws are whitened against their own sample covariance and
        recorrelated (see ``_exact_normal_scores``), so the scores' sample Pearson
        correlation equals the target exactly; each column is then quantile-mapped
        onto its empirical marginal. Because the normal CDF is strictly monotone,
        that quantile map reduces to the same gather-by-rank, keeping the marginals
        exact. The matrix parameterizes the copula on the LATENT-NORMAL scale, so
        the induced Spearman is (6/pi)*arcsin(rho/2) — e.g. a 0.60 entry induces
        ~0.582, slightly BELOW the nominal entry.
        Requires n_trials > n_params (fails loud otherwise).

    Limitations (honest, per the SOTA link-research corrections):
      - A Gaussian copula has ZERO asymptotic tail dependence for |rho| < 1: it
        CANNOT capture joint tail-crisis co-movement (e.g. FX-crisis x curtailment
        striking together). That motivation requires a t-copula or another
        tail-dependent family — an explicit NON-GOAL here, left as a follow-up.
      - Iman-Conover remains the default and is approximate in Spearman terms; the
        copula option removes the score-correlation sampling error, not the
        arcsin(rho/2) latent-scale distortion (which both methods share).

    Determinism (MRM-01): all randomness comes from ``np.random.default_rng(seed)``;
    identical inputs + seed => identical output for both methods.

    Inputs:
      lhs_samples: shape [n_trials, n_params], assumed iid-ish (LHS in [low,high] domain)
      correlation.matrix: target correlation matrix over parameters

    Output:
      correlated_samples: same shape

    Raises:
      ValueError: enabled without a matrix; matrix/sample shape mismatch; an
        unrecognized ``correlation.method`` (fail loud — unknown methods previously
        fell through to Iman-Conover silently); gaussian_copula with
        n_trials <= n_params.
    """
    if not correlation.enabled:
        return lhs_samples
    if correlation.matrix is None:
        raise ValueError("CorrelationSpec.enabled=True but matrix is None.")

    method = str(correlation.method).strip().lower()
    if method not in SUPPORTED_CORRELATION_METHODS:
        raise ValueError(
            f"Unsupported CorrelationSpec.method {correlation.method!r}: expected one "
            f"of {list(SUPPORTED_CORRELATION_METHODS)}. Unrecognized methods "
            "previously ran Iman-Conover silently; they now fail loud (CESSPIT) so a "
            "config typo cannot masquerade as a deliberately-chosen dependence "
            "structure."
        )

    mat = np.array(correlation.matrix, dtype=float, copy=True)
    validate_correlation_matrix(mat, tol=correlation.tol)

    if correlation.repair:
        # Ensure PSD-ish for decomposition steps
        mat = _nearest_psd(mat)

    # Shared skeleton:
    # 1) generate correlated normal scores using Cholesky of target corr
    #    (raw scores for iman_conover; exactly-recorrelated scores for
    #    gaussian_copula)
    # 2) convert the score columns to ranks
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
    if method == "gaussian_copula":
        y = _exact_normal_scores(z, L)
    else:  # iman_conover — the historical path, kept bit-identical
        y = z @ L.T

    # ranks of correlated normals
    y_ranks = np.argsort(np.argsort(y, axis=0), axis=0)

    # Reorder each column of x so its rank vector matches the correlated
    # normals' rank vector (Iman-Conover gather; for gaussian_copula this same
    # gather IS the empirical-quantile map since Phi is monotone). This is a
    # GATHER by rank: row i receives the marginal value whose ascending rank
    # equals ``y_ranks[i, j]``, giving ``out[:, j]`` a rank vector identical to
    # ``y[:, j]`` and therefore the target Spearman correlation, while
    # preserving the exact marginal.
    #
    # The previous SCATTER form ``out[y_ranks[:, j], j] = col_sorted`` applied the
    # INVERSE permutation, so the induced correlation collapsed to ~0 while the
    # ``correlation_enabled`` metadata claimed otherwise (audit D1, #570).
    out = np.empty_like(x)
    for j in range(k):
        col_sorted = np.sort(x[:, j])
        out[:, j] = col_sorted[y_ranks[:, j]]

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
