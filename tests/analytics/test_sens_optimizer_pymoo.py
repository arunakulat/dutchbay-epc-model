"""Behavior tests for the OPT-IN pymoo (NSGA-II) Pareto backend (#603).

Gated on the optional dependency: ``pytest.importorskip("pymoo")`` skips the
whole module cleanly when pymoo is absent (CASPER). The missing-dependency
fail-loud guard path is covered WITHOUT pymoo in
test_sens_optimizer_coverage.py.

``analytics.evaluation_v14.evaluate_with_overrides`` is monkeypatched to a
deterministic synthetic evaluator, so no engine/scenario evaluation runs here.
Under test are the backend's mechanics: gateway-only evaluation, the existing
ParetoPoint/ParetoResult contracts, frontier consistency with
``pareto_frontier()``, determinism by seed, evaluation-budget enforcement
(``n_samples`` bounded by ``max_points``), bounds handling, and global-RNG
hygiene (snapshot/restore around the seeded pymoo run).

KPI-neutral: this is an additive, opt-in analysis backend; the deterministic
base case is never touched (no canonical-KPI assertions belong here).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pytest

pytest.importorskip("pymoo")  # optional dependency (CASPER); skip cleanly if absent

from analytics.sensitivity import optimizer as opt  # noqa: E402
from analytics.sensitivity.optimizer import (  # noqa: E402
    ObjectiveSpec,
    ParameterGridSpec,
    ParetoResult,
    pareto_frontier,
    run_pareto_search,
)

# ---------------------------------------------------------------------------
# Synthetic evaluator: a deterministic function of the override values with a
# genuine IRR-vs-DSCR trade-off along the first axis, so the frontier is
# non-trivial.
# ---------------------------------------------------------------------------


def _fake_eval(
    *,
    config_path: Optional[str] = None,
    raw_config: Optional[Mapping[str, Any]] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    ov = dict(overrides or {})
    x = float(ov.get("ka", 0.0))
    y = float(ov.get("kb", 0.0))
    return {
        "kpis": {
            "project_irr": 0.05 + 0.010 * x - 0.002 * y,
            "min_dscr": 2.0 - 0.10 * x + 0.050 * y,
        }
    }


def _grid_two() -> List[ParameterGridSpec]:
    return [
        ParameterGridSpec(name="a", override_key="ka", values=(0.0, 10.0)),
        ParameterGridSpec(name="b", override_key="kb", values=(-5.0, 5.0)),
    ]


def _objectives() -> List[ObjectiveSpec]:
    return [
        ObjectiveSpec(metric_key="project_irr", direction="max"),
        ObjectiveSpec(metric_key="min_dscr", direction="max"),
    ]


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    seed: int = 123,
    n_samples: int = 24,
    max_points: int = 100,
    pop_size: int = 6,
    **kwargs: Any,
) -> ParetoResult:
    monkeypatch.setattr(opt, "evaluate_with_overrides", _fake_eval)
    return run_pareto_search(
        base_config={"finance": {"tariff_usd": 1.0}},
        objectives=_objectives(),
        grid=_grid_two(),
        plan_kind="pymoo",
        n_samples=n_samples,
        max_points=max_points,
        seed=seed,
        pop_size=pop_size,
        **kwargs,
    )


def _point_key(p: Any) -> Tuple[str, Tuple[Tuple[str, float], ...]]:
    return (p.label, tuple(sorted((k, float(v)) for k, v in p.objectives.items())))


# ---------------------------------------------------------------------------
# Contracts, metadata, bounds
# ---------------------------------------------------------------------------


def test_pymoo_backend_contracts_metadata_and_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = _run(monkeypatch)
    assert isinstance(res, ParetoResult)
    assert res.metadata["plan_kind"] == "pymoo"
    assert res.metadata["algorithm"] == "nsga2"
    assert res.metadata["seed"] == 123
    assert res.metadata["pop_size"] == 6
    assert res.metadata["n_gen"] == 4  # 24 // 6
    assert res.metadata["evaluation_budget"] == 24
    assert res.metadata["max_points"] == 100
    assert res.metadata["n_points"] == len(res.points_all)
    assert res.metadata["n_pareto"] == len(res.points_pareto)
    # Existing contracts: every point is a ParetoPoint with both objectives,
    # override keys mapped from the grid, KPIs attached by default, and a
    # decision vector inside the declared [min(values), max(values)] box.
    assert len(res.points_all) >= 6  # at least the initial population
    for p in res.points_all:
        assert set(p.overrides) == {"ka", "kb"}
        assert 0.0 <= float(p.overrides["ka"]) <= 10.0
        assert -5.0 <= float(p.overrides["kb"]) <= 5.0
        assert set(p.objectives) == {"project_irr", "min_dscr"}
        assert p.kpis  # attach_kpis=True by default
        assert "a~" in p.label and "b~" in p.label


def test_pymoo_backend_attach_kpis_false(monkeypatch: pytest.MonkeyPatch) -> None:
    res = _run(monkeypatch, attach_kpis=False)
    assert all(p.kpis == {} for p in res.points_all)


# ---------------------------------------------------------------------------
# Frontier: non-domination consistent with the module's own pareto_frontier()
# ---------------------------------------------------------------------------


def test_pymoo_backend_frontier_matches_pareto_frontier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = _run(monkeypatch)
    objs = _objectives()
    expected = pareto_frontier(list(res.points_all), objs)
    assert {_point_key(p) for p in res.points_pareto} == {
        _point_key(p) for p in expected
    }
    # Independent non-domination check: no evaluated point strictly dominates
    # any frontier point (both objectives are "max" here).
    for fp in res.points_pareto:
        for q in res.points_all:
            ge_all = all(
                q.objectives[o.metric_key] >= fp.objectives[o.metric_key] for o in objs
            )
            gt_any = any(
                q.objectives[o.metric_key] > fp.objectives[o.metric_key] for o in objs
            )
            assert not (ge_all and gt_any), "frontier point is dominated"


# ---------------------------------------------------------------------------
# Determinism by seed
# ---------------------------------------------------------------------------


def test_pymoo_backend_deterministic_by_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    res1 = _run(monkeypatch, seed=7)
    res2 = _run(monkeypatch, seed=7)
    seq1 = [(p.label, tuple(sorted(p.overrides.items()))) for p in res1.points_all]
    seq2 = [(p.label, tuple(sorted(p.overrides.items()))) for p in res2.points_all]
    assert seq1 == seq2
    assert [_point_key(p) for p in res1.points_pareto] == [
        _point_key(p) for p in res2.points_pareto
    ]
    # A different seed explores different candidates (continuous sampling; a
    # collision of the full evaluated sequence has ~zero probability).
    res3 = _run(monkeypatch, seed=8)
    seq3 = [(p.label, tuple(sorted(p.overrides.items()))) for p in res3.points_all]
    assert seq1 != seq3


def test_pymoo_backend_restores_global_rng_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    random.seed(4242)
    np.random.seed(2424)
    py_before = random.getstate()
    np_before = np.random.get_state()
    _run(monkeypatch)
    assert random.getstate() == py_before
    np_after = np.random.get_state()
    assert np_before[0] == np_after[0]
    assert np.array_equal(np_before[1], np_after[1])
    assert np_before[2:] == np_after[2:]


# ---------------------------------------------------------------------------
# Budget enforcement: n_samples is the evaluation budget, capped by max_points
# ---------------------------------------------------------------------------


def test_pymoo_backend_respects_evaluation_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = _run(monkeypatch, n_samples=10, pop_size=4)
    # pop=4, n_gen=10//4=2 -> at most 8 <= 10 engine evaluations.
    assert res.metadata["pop_size"] == 4
    assert res.metadata["n_gen"] == 2
    assert len(res.points_all) <= 10


def test_pymoo_backend_clamps_pop_size_to_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = _run(monkeypatch, n_samples=4, pop_size=32)
    assert res.metadata["pop_size"] == 4
    assert res.metadata["n_gen"] == 1
    assert len(res.points_all) <= 4


def test_pymoo_backend_n_samples_exceeding_max_points_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="n_samples must be <= max_points"):
        _run(monkeypatch, n_samples=200, max_points=100)


def test_pymoo_backend_n_samples_too_small_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="n_samples >= 2"):
        _run(monkeypatch, n_samples=1)


def test_pymoo_backend_pop_size_too_small_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="pop_size must be >= 2"):
        _run(monkeypatch, pop_size=1)


def test_pymoo_backend_degenerate_range_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(opt, "evaluate_with_overrides", _fake_eval)
    grid = [
        ParameterGridSpec(name="a", override_key="ka", values=(0.0, 10.0)),
        ParameterGridSpec(name="b", override_key="kb", values=(2.0, 2.0)),
    ]
    with pytest.raises(ValueError, match="degenerate range"):
        run_pareto_search(
            base_config={},
            objectives=_objectives(),
            grid=grid,
            plan_kind="pymoo",
            n_samples=8,
            max_points=100,
        )
