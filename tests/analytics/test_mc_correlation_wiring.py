"""monte_carlo.correlation is wired into the live MC engine (audit #9/#31).

The complete, tested correlation facility (analytics.mc.correlation) was reachable by NO live
path: the engine took a CorrelationSpec only as a constructor arg, and run_monte_carlo_analysis
defaulted it to None, so an authored `monte_carlo.correlation` matrix with enabled: true was
silently ignored and every driver sampled independently. The engine now falls back to
load_correlation_from_config(base_config) when no spec is passed explicitly.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path

import numpy as np
import yaml

from analytics.mc.correlation import (
    CorrelationSpec,
    align_correlation_to_params,
    apply_correlation_structure,
)
from analytics.mc.engine import MonteCarloEngine

_SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def _load() -> dict:
    return yaml.safe_load(_SCENARIO.read_text())


def _with_correlation(cfg: dict, rho: float = 0.8) -> dict:
    cfg = copy.deepcopy(cfg)
    names = [p["name"] for p in cfg["monte_carlo"]["parameters"]]
    k = len(names)
    mat = np.eye(k)
    i, j = names.index("capex.usd_total"), names.index("project.capacity_factor")
    mat[i][j] = mat[j][i] = rho
    cfg["monte_carlo"]["correlation"] = {
        "enabled": True,
        "method": "iman_conover",
        "matrix": mat.tolist(),
        "param_names": names,
    }
    return cfg


def _without_correlation(cfg: dict) -> dict:
    """Strip the scenario's default correlation block -> the independent baseline.

    The lender scenario now ships a documented default correlation (MC-7, #487), so the
    'no block' contract is exercised against an explicitly-stripped copy rather than the
    scenario as-authored.
    """
    cfg = copy.deepcopy(cfg)
    cfg["monte_carlo"].pop("correlation", None)
    return cfg


def test_no_correlation_block_is_independent() -> None:
    # Byte-identical default: no block -> no spec -> independent sampling.
    assert MonteCarloEngine(_without_correlation(_load()), seed=1)._correlation is None


def test_lender_scenario_ships_default_correlation() -> None:
    # MC-7 (#487): the canonical lender scenario now declares a default correlation, so the
    # dormant Iman-Conover machinery is live by default (no longer silently independent).
    spec = MonteCarloEngine(_load(), seed=1)._correlation
    assert spec is not None and spec.enabled is True
    assert spec.matrix is not None
    n_params = len(_load()["monte_carlo"]["parameters"])
    assert spec.matrix.shape == (n_params, n_params)
    # the two documented off-diagonals are present and symmetric
    names = [p["name"] for p in _load()["monte_carlo"]["parameters"]]
    ci, oi = names.index("capex.usd_total"), names.index("opex.usd_per_year")
    cf, cu = names.index("project.capacity_factor"), names.index(
        "project.curtailment_pct"
    )
    assert spec.matrix[ci][oi] == spec.matrix[oi][ci] == 0.35
    assert spec.matrix[cf][cu] == spec.matrix[cu][cf] == 0.20


def test_config_correlation_is_loaded() -> None:
    eng = MonteCarloEngine(_with_correlation(_load()), seed=1)
    assert eng._correlation is not None
    assert eng._correlation.enabled is True
    assert eng._correlation.matrix is not None


def test_explicit_spec_overrides_config() -> None:
    # An explicitly-passed spec wins over the config block (explicit > config).
    eng = MonteCarloEngine(
        _with_correlation(_load()), seed=1, correlation=CorrelationSpec(enabled=False)
    )
    assert eng._correlation is not None
    assert eng._correlation.enabled is False


def test_align_correlation_to_params_is_identity_when_already_matched() -> None:
    names = ("a", "b", "c")
    mat = np.array([[1.0, 0.4, 0.0], [0.4, 1.0, 0.2], [0.0, 0.2, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat, param_names=names)
    out = align_correlation_to_params(spec, list(names))
    assert out is spec  # same order -> unchanged (byte-identical path)


def test_align_correlation_to_params_subsets_and_reorders() -> None:
    names = ("a", "b", "c")
    mat = np.array([[1.0, 0.4, 0.7], [0.4, 1.0, 0.2], [0.7, 0.2, 1.0]])
    spec = CorrelationSpec(
        enabled=True, matrix=mat, param_names=names, method="gaussian_copula"
    )
    # Active set is a reordered subset {c, a}: the (a,c)=0.7 pair must survive, reordered.
    out = align_correlation_to_params(spec, ["c", "a"])
    assert out is not None and out.matrix is not None
    assert out.matrix.shape == (2, 2)
    assert out.matrix[0][1] == out.matrix[1][0] == 0.7  # (c,a) preserved
    assert out.param_names == ("c", "a")
    assert out.method == "gaussian_copula"  # method survives re-indexing (#601)


def test_align_correlation_to_params_identity_when_active_param_absent() -> None:
    names = ("a", "b")
    mat = np.array([[1.0, 0.5], [0.5, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat, param_names=names)
    # A single active param that IS named -> 1x1 identity (no self-correlation), no crash.
    out = align_correlation_to_params(spec, ["a"])
    assert out is not None and out.matrix is not None
    assert out.matrix.shape == (1, 1) and out.matrix[0][0] == 1.0
    # An active param NOT in the spec -> still identity, uncorrelated.
    out2 = align_correlation_to_params(spec, ["a", "z"])
    assert out2 is not None and out2.matrix is not None
    assert out2.matrix[0][1] == out2.matrix[1][0] == 0.0


def test_correlation_changes_trial_outcomes() -> None:
    # Same seed, with vs without the correlation block -> different joint draws -> different
    # per-trial KPI sequence. Proves the matrix is live, not ignored.
    logging.disable(logging.WARNING)
    try:
        indep = MonteCarloEngine(_without_correlation(_load()), seed=123).run(
            n_trials=64
        )
        corr = MonteCarloEngine(_with_correlation(_load()), seed=123).run(n_trials=64)
        a = [x for x in (indep.trials or {}).get("project_irr", []) if x is not None]
        b = [x for x in (corr.trials or {}).get("project_irr", []) if x is not None]
        assert len(a) == len(b) == 64
        assert a != b  # correlation rearranged the joint sample -> outcomes differ
    finally:
        logging.disable(logging.NOTSET)


def _induced_spearman(out: np.ndarray, i: int, j: int) -> float:
    """Spearman rank correlation between two columns via rank-Pearson (no scipy dep)."""
    ri = np.argsort(np.argsort(out[:, i]))
    rj = np.argsort(np.argsort(out[:, j]))
    return float(np.corrcoef(ri, rj)[0, 1])


def test_iman_conover_induces_target_correlation() -> None:
    """The INDUCED Spearman must match the target, not merely differ from baseline.

    Regression guard for audit D1 (#570): the reorder was a scatter-by-rank (inverse
    permutation), so the induced correlation collapsed to ~0 while metadata claimed
    ``correlation_enabled=true``. The old form here would yield ~0.0; the gather-by-rank
    fix reproduces the target within sampling tolerance. This asserts the induction
    itself, which the pre-existing ``a != b`` wiring test could never catch.
    """
    rng = np.random.default_rng(7)
    n, target = 4000, 0.6
    lhs = rng.random((n, 2))  # iid uniforms stand in for the LHS marginals
    mat = np.array([[1.0, target], [target, 1.0]])
    spec = CorrelationSpec(enabled=True, matrix=mat, param_names=("a", "b"))

    out = apply_correlation_structure(lhs_samples=lhs, correlation=spec, seed=42)

    induced = _induced_spearman(out, 0, 1)
    assert abs(induced - target) < 0.05, f"induced Spearman {induced:.3f} != {target}"
    # Marginals must be preserved exactly (a pure reordering of each column).
    assert np.allclose(np.sort(out[:, 0]), np.sort(lhs[:, 0]))
    assert np.allclose(np.sort(out[:, 1]), np.sort(lhs[:, 1]))


def test_iman_conover_preserves_independence_at_zero_target() -> None:
    """A zero-correlation target must stay ~independent (no spurious induced correlation)."""
    rng = np.random.default_rng(11)
    n = 4000
    lhs = rng.random((n, 2))
    mat = np.eye(2)
    spec = CorrelationSpec(enabled=True, matrix=mat, param_names=("a", "b"))
    out = apply_correlation_structure(lhs_samples=lhs, correlation=spec, seed=42)
    assert abs(_induced_spearman(out, 0, 1)) < 0.06


# --------------------------------------------------------------------------- #
# Gaussian copula (#601, opt-in)                                              #
# --------------------------------------------------------------------------- #
def test_gaussian_copula_induces_target_spearman() -> None:
    """The copula's induced Spearman lands on the latent-normal mapping.

    The matrix parameterizes the copula on the LATENT-NORMAL scale, so the
    induced Spearman concentrates at (6/pi)*arcsin(rho/2) — for rho=0.6 that is
    ~0.582, slightly BELOW the nominal entry (documented, both methods share
    this distortion). With the exact-normal-scores construction the only noise
    left is the rank conversion, so a tight tolerance holds; the value must also
    sit within the looser practical tolerance of the nominal target.
    """
    rng = np.random.default_rng(7)
    n, target = 4000, 0.6
    lhs = rng.random((n, 2))
    mat = np.array([[1.0, target], [target, 1.0]])
    spec = CorrelationSpec(
        enabled=True, matrix=mat, param_names=("a", "b"), method="gaussian_copula"
    )

    out = apply_correlation_structure(lhs_samples=lhs, correlation=spec, seed=42)

    induced = _induced_spearman(out, 0, 1)
    latent = 6.0 / np.pi * np.arcsin(target / 2.0)  # ~0.58192
    assert abs(induced - latent) < 0.03, f"induced {induced:.3f} != latent {latent:.3f}"
    assert abs(induced - target) < 0.05, f"induced {induced:.3f} !~ nominal {target}"
    # Marginals must be preserved exactly (a pure reordering of each column).
    assert np.allclose(np.sort(out[:, 0]), np.sort(lhs[:, 0]))
    assert np.allclose(np.sort(out[:, 1]), np.sort(lhs[:, 1]))


def test_gaussian_copula_scatter_tighter_than_iman_conover() -> None:
    """Exact normal scores beat raw scores: less seed-to-seed dependence scatter.

    Iman-Conover recorrelates RAW normal draws, so the induced Spearman inherits
    the O(1/sqrt(n)) sampling error of the draws' own correlation; the copula
    whitens that error away first. Over a FIXED seed set (deterministic, MRM-01)
    the copula's induced-Spearman spread around the latent target must be
    strictly tighter than Iman-Conover's (measured at n=500: std ~0.011 vs
    ~0.030).
    """
    n, target = 500, 0.6
    lhs = np.random.default_rng(9).random((n, 2))
    mat = np.array([[1.0, target], [target, 1.0]])
    ic_spec = CorrelationSpec(enabled=True, matrix=mat, param_names=("a", "b"))
    gc_spec = CorrelationSpec(
        enabled=True, matrix=mat, param_names=("a", "b"), method="gaussian_copula"
    )
    ic_vals = []
    gc_vals = []
    for seed in range(20):
        ic_vals.append(
            _induced_spearman(
                apply_correlation_structure(
                    lhs_samples=lhs, correlation=ic_spec, seed=seed
                ),
                0,
                1,
            )
        )
        gc_vals.append(
            _induced_spearman(
                apply_correlation_structure(
                    lhs_samples=lhs, correlation=gc_spec, seed=seed
                ),
                0,
                1,
            )
        )
    assert float(np.std(gc_vals)) < float(np.std(ic_vals))


def _with_method(cfg: dict, method: str) -> dict:
    cfg = _with_correlation(cfg)
    cfg["monte_carlo"]["correlation"]["method"] = method
    return cfg


def test_engine_round_trips_gaussian_copula_method() -> None:
    # config -> load_correlation_from_config -> align_correlation_to_params keeps
    # the opt-in method string intact on the engine's live spec.
    eng = MonteCarloEngine(_with_method(_load(), "gaussian_copula"), seed=1)
    assert eng._correlation is not None
    assert eng._correlation.enabled is True
    assert eng._correlation.method == "gaussian_copula"


def test_engine_gaussian_copula_changes_trial_outcomes_vs_iman_conover() -> None:
    # Same seed, same matrix, different method -> different joint draws -> different
    # per-trial KPI sequence. Proves the dispatch is live end-to-end in the engine.
    logging.disable(logging.WARNING)
    try:
        ic = MonteCarloEngine(_with_method(_load(), "iman_conover"), seed=123).run(
            n_trials=32
        )
        gc = MonteCarloEngine(_with_method(_load(), "gaussian_copula"), seed=123).run(
            n_trials=32
        )
        a = [x for x in (ic.trials or {}).get("project_irr", []) if x is not None]
        b = [x for x in (gc.trials or {}).get("project_irr", []) if x is not None]
        assert len(a) == len(b) == 32
        assert a != b  # the copula rearranged the joint sample -> outcomes differ
    finally:
        logging.disable(logging.NOTSET)
