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

from analytics.mc.correlation import CorrelationSpec, align_correlation_to_params
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
    spec = CorrelationSpec(enabled=True, matrix=mat, param_names=names)
    # Active set is a reordered subset {c, a}: the (a,c)=0.7 pair must survive, reordered.
    out = align_correlation_to_params(spec, ["c", "a"])
    assert out is not None and out.matrix is not None
    assert out.matrix.shape == (2, 2)
    assert out.matrix[0][1] == out.matrix[1][0] == 0.7  # (c,a) preserved
    assert out.param_names == ("c", "a")


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
