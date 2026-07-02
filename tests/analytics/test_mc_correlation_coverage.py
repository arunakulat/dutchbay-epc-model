"""Coverage for analytics.mc.correlation — MC dependence structures.

Exercises validation (square/diagonal/symmetry raises), the nearest-PSD eigenvalue
repair, the full apply_correlation_structure pipeline (disabled passthrough, missing
matrix raise, shape-mismatch raise, correlated reordering), the method dispatch
(#601: default Iman-Conover pinned bit-for-bit, the opt-in exact-normal-scores
Gaussian copula, and the fail-loud contract for unrecognized methods), the
back-compat alias, the starter template, and the permissive config loader. All
deterministic (MRM-01); the module is self-contained (no network / config /
matplotlib), so only small synthetic correlation matrices are needed.
"""

from __future__ import annotations

import numpy as np
import pytest

from analytics.mc.correlation import (
    SUPPORTED_CORRELATION_METHODS,
    CorrelationSpec,
    _nearest_psd,
    apply_correlation_structure,
    apply_correlation_to_lhs,
    get_renewable_energy_correlation_template,
    load_correlation_from_config,
    validate_correlation_matrix,
)


# --------------------------------------------------------------------------- #
# validate_correlation_matrix                                                 #
# --------------------------------------------------------------------------- #
def test_validate_accepts_valid_matrix() -> None:
    mat = np.array([[1.0, 0.4], [0.4, 1.0]])
    # No raise => returns None.
    assert validate_correlation_matrix(mat) is None


def test_validate_rejects_non_square() -> None:
    with pytest.raises(ValueError, match="square"):
        validate_correlation_matrix(np.array([[1.0, 0.0, 0.0]]))


def test_validate_rejects_three_dimensional() -> None:
    with pytest.raises(ValueError, match="square"):
        validate_correlation_matrix(np.ones((2, 2, 2)))


def test_validate_rejects_bad_diagonal() -> None:
    mat = np.array([[1.0, 0.2], [0.2, 0.5]])
    with pytest.raises(ValueError, match="diagonal"):
        validate_correlation_matrix(mat)


def test_validate_rejects_asymmetric() -> None:
    mat = np.array([[1.0, 0.3], [0.9, 1.0]])
    with pytest.raises(ValueError, match="symmetric"):
        validate_correlation_matrix(mat)


# --------------------------------------------------------------------------- #
# _nearest_psd                                                                #
# --------------------------------------------------------------------------- #
def test_nearest_psd_keeps_psd_matrix_and_unit_diagonal() -> None:
    mat = np.array([[1.0, 0.5], [0.5, 1.0]])
    out = _nearest_psd(mat)
    assert out.shape == (2, 2)
    np.testing.assert_allclose(np.diag(out), 1.0, atol=1e-10)
    np.testing.assert_allclose(out, mat, atol=1e-10)


def test_nearest_psd_repairs_non_psd_matrix() -> None:
    # This 3x3 has a negative eigenvalue (indefinite) but unit diagonal + symmetric.
    mat = np.array(
        [
            [1.0, 0.9, -0.9],
            [0.9, 1.0, 0.9],
            [-0.9, 0.9, 1.0],
        ]
    )
    assert np.min(np.linalg.eigvalsh(mat)) < 0.0  # confirm it starts non-PSD
    out = _nearest_psd(mat)
    # Repaired matrix is PSD (eigenvalues clipped at 0) ...
    assert np.min(np.linalg.eigvalsh(out)) >= -1e-8
    # ... and re-normalized to unit diagonal.
    np.testing.assert_allclose(np.diag(out), 1.0, atol=1e-8)


def test_nearest_psd_handles_zero_eigenvalue_diagonal_guard() -> None:
    # A rank-deficient (degenerate) matrix exercises the d[d == 0] = 1.0 guard
    # path: a zero block on the diagonal after clipping would otherwise divide by 0.
    mat = np.zeros((2, 2))
    out = _nearest_psd(mat)
    # All-zero input -> sqrt(diag)=0 -> guard replaces with 1.0 -> output stays finite.
    assert np.all(np.isfinite(out))
    np.testing.assert_allclose(out, np.zeros((2, 2)), atol=1e-12)


# --------------------------------------------------------------------------- #
# apply_correlation_structure                                                 #
# --------------------------------------------------------------------------- #
def _lhs(n: int, k: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random(size=(n, k))


def test_apply_disabled_returns_input_unchanged() -> None:
    samples = _lhs(16, 2)
    spec = CorrelationSpec(enabled=False)
    out = apply_correlation_structure(lhs_samples=samples, correlation=spec)
    # Identity object passthrough when disabled.
    assert out is samples


def test_apply_enabled_without_matrix_raises() -> None:
    spec = CorrelationSpec(enabled=True, matrix=None)
    with pytest.raises(ValueError, match="matrix is None"):
        apply_correlation_structure(lhs_samples=_lhs(8, 2), correlation=spec)


def test_apply_shape_mismatch_raises() -> None:
    # 3x3 correlation but only 2 sample columns.
    mat = np.eye(3)
    spec = CorrelationSpec(enabled=True, matrix=mat)
    with pytest.raises(ValueError, match="does not match samples columns"):
        apply_correlation_structure(lhs_samples=_lhs(10, 2), correlation=spec)


def test_apply_preserves_shape_and_marginals() -> None:
    samples = _lhs(64, 2, seed=1)
    mat = np.array([[1.0, 0.8], [0.8, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat)
    out = apply_correlation_structure(lhs_samples=samples, correlation=spec, seed=42)

    assert out.shape == samples.shape
    # Iman-Conover only reorders within each column => marginals are preserved.
    for j in range(samples.shape[1]):
        np.testing.assert_allclose(np.sort(out[:, j]), np.sort(samples[:, j]))


def test_apply_runs_full_pipeline_and_permutes_rows() -> None:
    # The current implementation is a documented skeleton: it sorts each column and
    # scatters by the ranks of correlated normals. We assert the observable, stable
    # behaviour — it executes end to end, preserves marginals exactly, and actually
    # permutes the rows (output is not a no-op copy of the input order).
    samples = _lhs(200, 2, seed=5)
    mat = np.array([[1.0, 0.85], [0.85, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat)
    out = apply_correlation_structure(lhs_samples=samples, correlation=spec, seed=7)

    assert out.shape == samples.shape
    # Marginals preserved (only a within-column reordering happened).
    for j in range(samples.shape[1]):
        np.testing.assert_allclose(np.sort(out[:, j]), np.sort(samples[:, j]))
    # Rows were genuinely reordered (not returned in input order).
    assert not np.allclose(out, samples)


def test_apply_with_repair_disabled_still_runs() -> None:
    # repair=False skips _nearest_psd; a valid PSD matrix still decomposes.
    samples = _lhs(32, 2, seed=3)
    mat = np.array([[1.0, 0.3], [0.3, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat, repair=False)
    out = apply_correlation_structure(lhs_samples=samples, correlation=spec, seed=9)
    assert out.shape == samples.shape


def test_apply_repairs_non_psd_target_via_nearest_psd() -> None:
    # An indefinite target with repair=True (default) must be repaired before Cholesky,
    # otherwise the decomposition would fail.
    samples = _lhs(40, 3, seed=11)
    mat = np.array(
        [
            [1.0, 0.9, -0.9],
            [0.9, 1.0, 0.9],
            [-0.9, 0.9, 1.0],
        ]
    )
    spec = CorrelationSpec(enabled=True, matrix=mat, repair=True)
    out = apply_correlation_structure(lhs_samples=samples, correlation=spec, seed=13)
    assert out.shape == samples.shape


# --------------------------------------------------------------------------- #
# method dispatch (#601): fail-loud contract + Gaussian copula                #
# --------------------------------------------------------------------------- #
def test_apply_unknown_method_fails_loud() -> None:
    # CESSPIT: an unrecognized method must raise at apply time, not silently run
    # Iman-Conover while the config claims a different dependence structure.
    mat = np.array([[1.0, 0.4], [0.4, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat, method="not_a_method")
    with pytest.raises(ValueError, match="not_a_method"):
        apply_correlation_structure(lhs_samples=_lhs(16, 2), correlation=spec)


def test_apply_disabled_spec_ignores_unknown_method() -> None:
    # The fail-loud contract is an APPLY-time contract: a disabled spec stays a
    # passthrough regardless of its method string (nothing is applied).
    samples = _lhs(8, 2)
    spec = CorrelationSpec(enabled=False, method="not_a_method")
    assert apply_correlation_structure(lhs_samples=samples, correlation=spec) is samples


def test_apply_method_is_case_and_whitespace_normalized() -> None:
    # " Gaussian_Copula " normalizes to the supported token (config ergonomics).
    samples = _lhs(32, 2, seed=19)
    mat = np.array([[1.0, 0.5], [0.5, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat, method=" Gaussian_Copula ")
    out = apply_correlation_structure(lhs_samples=samples, correlation=spec, seed=3)
    ref = apply_correlation_structure(
        lhs_samples=samples,
        correlation=CorrelationSpec(enabled=True, matrix=mat, method="gaussian_copula"),
        seed=3,
    )
    np.testing.assert_array_equal(out, ref)


def test_supported_methods_registry_matches_contract() -> None:
    assert SUPPORTED_CORRELATION_METHODS == ("iman_conover", "gaussian_copula")


def test_iman_conover_default_path_matches_reference_algorithm() -> None:
    """Pin the DEFAULT path bit-for-bit against an inline reference implementation.

    The #601 method dispatch must leave the historical Iman-Conover path
    byte-identical: same rng consumption, same Cholesky, same gather-by-rank.
    The reference below reproduces that exact operation sequence independently;
    any drift in the default path (an extra rng draw, a reordered op) breaks
    exact equality here.
    """
    samples = _lhs(64, 3, seed=17)
    target = np.array(
        [
            [1.0, 0.5, 0.2],
            [0.5, 1.0, 0.0],
            [0.2, 0.0, 1.0],
        ]
    )
    spec = CorrelationSpec(enabled=True, matrix=target)  # default method
    out = apply_correlation_structure(lhs_samples=samples, correlation=spec, seed=99)

    # Reference: the legacy single-path algorithm, replicated operation-for-operation.
    mat = _nearest_psd(np.array(target, dtype=float, copy=True))  # repair=True default
    rng = np.random.default_rng(99)
    z = rng.standard_normal(size=(64, 3))
    chol = np.linalg.cholesky(mat + np.eye(3) * 1e-12)
    y = z @ chol.T
    ranks = np.argsort(np.argsort(y, axis=0), axis=0)
    expected = np.empty_like(samples)
    for j in range(3):
        expected[:, j] = np.sort(samples[:, j])[ranks[:, j]]
    np.testing.assert_array_equal(out, expected)


def _gc_spec(mat: np.ndarray) -> CorrelationSpec:
    return CorrelationSpec(enabled=True, matrix=mat, method="gaussian_copula")


def test_gaussian_copula_preserves_marginals_exactly() -> None:
    # The copula's empirical-quantile map is a pure within-column permutation:
    # sorted columns must be IDENTICAL (not merely close) to the input's.
    samples = _lhs(256, 3, seed=23)
    mat = np.array(
        [
            [1.0, 0.7, 0.0],
            [0.7, 1.0, -0.3],
            [0.0, -0.3, 1.0],
        ]
    )
    out = apply_correlation_structure(
        lhs_samples=samples, correlation=_gc_spec(mat), seed=31
    )
    assert out.shape == samples.shape
    for j in range(samples.shape[1]):
        np.testing.assert_array_equal(np.sort(out[:, j]), np.sort(samples[:, j]))


def test_gaussian_copula_seed_determinism() -> None:
    # MRM-01: identical inputs + seed => bit-identical output; a different seed
    # must produce a different joint arrangement.
    samples = _lhs(128, 2, seed=29)
    mat = np.array([[1.0, 0.6], [0.6, 1.0]])
    a = apply_correlation_structure(
        lhs_samples=samples, correlation=_gc_spec(mat), seed=42
    )
    b = apply_correlation_structure(
        lhs_samples=samples, correlation=_gc_spec(mat), seed=42
    )
    c = apply_correlation_structure(
        lhs_samples=samples, correlation=_gc_spec(mat), seed=43
    )
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_gaussian_copula_dispatch_differs_from_iman_conover() -> None:
    # The dispatch is real: same inputs + seed, different methods => different
    # joint arrangements (the copula whitens the scores before recorrelating).
    samples = _lhs(512, 2, seed=37)
    mat = np.array([[1.0, 0.6], [0.6, 1.0]])
    gc = apply_correlation_structure(
        lhs_samples=samples, correlation=_gc_spec(mat), seed=7
    )
    ic = apply_correlation_structure(
        lhs_samples=samples,
        correlation=CorrelationSpec(enabled=True, matrix=mat),
        seed=7,
    )
    assert not np.array_equal(gc, ic)


def test_gaussian_copula_requires_more_trials_than_params() -> None:
    # n_trials <= n_params makes the scores' sample covariance singular, so the
    # exact whitening is undefined: fail loud with an actionable message.
    samples = _lhs(3, 3, seed=41)
    with pytest.raises(ValueError, match="n_trials > n_params"):
        apply_correlation_structure(
            lhs_samples=samples, correlation=_gc_spec(np.eye(3)), seed=1
        )


def test_gaussian_copula_single_param_is_supported() -> None:
    # k=1 degenerate case: a 1x1 identity target still runs (pure permutation).
    samples = _lhs(16, 1, seed=43)
    out = apply_correlation_structure(
        lhs_samples=samples, correlation=_gc_spec(np.eye(1)), seed=11
    )
    np.testing.assert_array_equal(np.sort(out[:, 0]), np.sort(samples[:, 0]))


# --------------------------------------------------------------------------- #
# apply_correlation_to_lhs (back-compat alias)                                #
# --------------------------------------------------------------------------- #
def test_back_compat_alias_matches_structure_call() -> None:
    samples = _lhs(48, 2, seed=2)
    mat = np.array([[1.0, 0.6], [0.6, 1.0]])
    alias_out = apply_correlation_to_lhs(samples, mat, seed=21)

    spec = CorrelationSpec(enabled=True, matrix=mat)
    direct_out = apply_correlation_structure(
        lhs_samples=samples, correlation=spec, seed=21
    )
    np.testing.assert_allclose(alias_out, direct_out)


# --------------------------------------------------------------------------- #
# get_renewable_energy_correlation_template                                   #
# --------------------------------------------------------------------------- #
def test_template_returns_identity_starter() -> None:
    names = ["aep", "capex", "opex"]
    tmpl = get_renewable_energy_correlation_template(names)
    assert tmpl["param_names"] == names
    assert tmpl["method"] == "iman_conover"
    assert tmpl["enabled"] is True
    # Identity matrix as nested lists, k == len(names).
    np.testing.assert_allclose(np.array(tmpl["matrix"]), np.eye(len(names)))


# --------------------------------------------------------------------------- #
# load_correlation_from_config                                                #
# --------------------------------------------------------------------------- #
def test_load_config_returns_none_when_not_a_mapping() -> None:
    # Non-mapping cfg => mc defaults to {} => correlation None => returns None.
    assert load_correlation_from_config([]) is None  # type: ignore[arg-type]


def test_load_config_returns_none_when_no_correlation_block() -> None:
    assert load_correlation_from_config({"monte_carlo": {}}) is None


def test_load_config_returns_none_when_correlation_falsey() -> None:
    assert load_correlation_from_config({"monte_carlo": {"correlation": {}}}) is None


def test_load_config_full_spec_unknown_method_fails_loud_at_apply() -> None:
    # The loader stays permissive (round-trips any method string verbatim), but
    # APPLYING an unrecognized method now fails loud (#601). Before the dispatch,
    # method='cholesky' silently ran Iman-Conover while the config claimed
    # otherwise.
    cfg = {
        "monte_carlo": {
            "correlation": {
                "enabled": True,
                "method": "cholesky",
                "matrix": [[1.0, 0.5], [0.5, 1.0]],
                "param_names": ["aep", "capex"],
            }
        }
    }
    spec = load_correlation_from_config(cfg)
    assert spec is not None
    assert spec.enabled is True
    assert spec.method == "cholesky"
    assert spec.param_names == ("aep", "capex")
    assert spec.matrix is not None
    np.testing.assert_allclose(spec.matrix, np.array([[1.0, 0.5], [0.5, 1.0]]))
    with pytest.raises(ValueError, match="cholesky"):
        apply_correlation_structure(lhs_samples=_lhs(8, 2), correlation=spec)


def test_load_config_round_trips_gaussian_copula_method() -> None:
    # The opt-in method string survives the config -> CorrelationSpec round trip
    # and dispatches cleanly at apply time.
    cfg = {
        "monte_carlo": {
            "correlation": {
                "enabled": True,
                "method": "gaussian_copula",
                "matrix": [[1.0, 0.5], [0.5, 1.0]],
                "param_names": ["aep", "capex"],
            }
        }
    }
    spec = load_correlation_from_config(cfg)
    assert spec is not None
    assert spec.method == "gaussian_copula"
    out = apply_correlation_structure(
        lhs_samples=_lhs(32, 2, seed=47), correlation=spec, seed=5
    )
    assert out.shape == (32, 2)


def test_load_config_defaults_when_keys_absent() -> None:
    # Correlation block present + truthy but missing optional keys exercises the
    # defaulting branches (enabled->False, method->iman_conover, matrix/names->None).
    cfg = {"monte_carlo": {"correlation": {"some_flag": 1}}}
    spec = load_correlation_from_config(cfg)
    assert spec is not None
    assert spec.enabled is False
    assert spec.method == "iman_conover"
    assert spec.matrix is None
    assert spec.param_names is None
