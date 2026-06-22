"""Coverage for analytics.mc.correlation — Iman-Conover rank correlation for MC.

Exercises validation (square/diagonal/symmetry raises), the nearest-PSD eigenvalue
repair, the full apply_correlation_structure pipeline (disabled passthrough, missing
matrix raise, shape-mismatch raise, correlated reordering), the back-compat alias,
the starter template, and the permissive config loader. All deterministic; the module
is self-contained (no network / config / matplotlib), so only small synthetic
correlation matrices are needed.
"""

from __future__ import annotations

import numpy as np
import pytest

from analytics.mc.correlation import (
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


def test_load_config_full_spec() -> None:
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
