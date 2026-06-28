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

from analytics.mc.correlation import CorrelationSpec
from analytics.mc.engine import MonteCarloEngine

_SCENARIO = Path(__file__).resolve().parents[2] / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


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


def test_no_correlation_block_is_independent() -> None:
    # Byte-identical default: no block -> no spec -> independent sampling.
    assert MonteCarloEngine(_load(), seed=1)._correlation is None


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


def test_correlation_changes_trial_outcomes() -> None:
    # Same seed, with vs without the correlation block -> different joint draws -> different
    # per-trial KPI sequence. Proves the matrix is live, not ignored.
    logging.disable(logging.WARNING)
    try:
        indep = MonteCarloEngine(_load(), seed=123).run(n_trials=64)
        corr = MonteCarloEngine(_with_correlation(_load()), seed=123).run(n_trials=64)
        a = [x for x in (indep.trials or {}).get("project_irr", []) if x is not None]
        b = [x for x in (corr.trials or {}).get("project_irr", []) if x is not None]
        assert len(a) == len(b) == 64
        assert a != b  # correlation rearranged the joint sample -> outcomes differ
    finally:
        logging.disable(logging.NOTSET)
