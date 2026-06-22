"""Coverage tests for analytics.sensitivity.optimizer.

Exercises the bounded Pareto optimizer end to end with small synthetic inputs:
plan builders (grid + LHS), the non-dominated frontier algorithm, the
orchestration control flow, every documented ``raise``, and both export paths
(pandas DataFrame and the list-of-dicts fallback).

The only compute-heavy / pipeline dependency is
``analytics.evaluation_v14.evaluate_with_overrides``; it is monkeypatched to a
deterministic synthetic evaluator so the tests stay fast and reproducible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pytest

from analytics.sensitivity import optimizer as opt
from analytics.sensitivity.optimizer import (
    ObjectiveSpec,
    ParameterGridSpec,
    ParetoPoint,
    ParetoResult,
    build_grid_plan,
    build_lhs_plan,
    export_pareto_table,
    pareto_frontier,
    run_pareto_search,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# Synthetic evaluator: maps an override value to deterministic KPIs.
# ---------------------------------------------------------------------------


def _make_fake_eval(wrap_kpis: bool = True):
    """Return a fake evaluate_with_overrides.

    irr increases with the override value; dscr decreases with it, so the two
    objectives genuinely trade off and the Pareto frontier is non-trivial.
    """

    def _fake(
        *,
        config_path: Optional[str] = None,
        raw_config: Optional[Mapping[str, Any]] = None,
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        overrides = overrides or {}
        x = float(next(iter(overrides.values()))) if overrides else 0.0
        kpis = {
            "project_irr": 0.05 + 0.01 * x,
            "min_dscr": 2.0 - 0.1 * x,
            "name": "synthetic",
        }
        if wrap_kpis:
            return {"kpis": kpis}
        return kpis

    return _fake


def _grid_one() -> list[ParameterGridSpec]:
    return [
        ParameterGridSpec(
            name="tariff", override_key="finance.tariff_usd", values=(1.0, 2.0, 3.0)
        )
    ]


def _objectives() -> list[ObjectiveSpec]:
    return [
        ObjectiveSpec(metric_key="project_irr", direction="max"),
        ObjectiveSpec(metric_key="min_dscr", direction="min"),
    ]


# ---------------------------------------------------------------------------
# pareto_frontier
# ---------------------------------------------------------------------------


def _pt(label: str, irr: float, dscr: float) -> ParetoPoint:
    return ParetoPoint(
        label=label,
        overrides={"k": 0.0},
        objectives={"project_irr": irr, "min_dscr": dscr},
        kpis={},
    )


def test_pareto_frontier_empty_returns_empty() -> None:
    assert pareto_frontier([], _objectives()) == []


def test_pareto_frontier_drops_dominated_point() -> None:
    objs = [
        ObjectiveSpec(metric_key="project_irr", direction="max"),
        ObjectiveSpec(metric_key="min_dscr", direction="max"),
    ]
    best = _pt("best", irr=0.10, dscr=2.0)
    dominated = _pt("dominated", irr=0.05, dscr=1.0)
    front = pareto_frontier([best, dominated], objs)
    labels = {p.label for p in front}
    assert labels == {"best"}


def test_pareto_frontier_keeps_tradeoff_points() -> None:
    # Two non-dominated points: one high IRR/low DSCR, one low IRR/high DSCR.
    objs = _objectives()  # irr max, dscr min
    a = _pt("hi_irr", irr=0.10, dscr=1.9)  # better irr, better (lower) dscr
    b = _pt("lo_irr", irr=0.06, dscr=1.4)  # worse irr, even better dscr
    front = pareto_frontier([a, b], objs)
    assert {p.label for p in front} == {"hi_irr", "lo_irr"}


# ---------------------------------------------------------------------------
# _normalize_for_dominance / _extract_kpis / _get_scalar
# ---------------------------------------------------------------------------


def test_normalize_for_dominance_directions() -> None:
    assert opt._normalize_for_dominance(3.0, "max") == 3.0
    assert opt._normalize_for_dominance(3.0, "MIN") == -3.0
    with pytest.raises(ValueError, match="must be 'max' or 'min'"):
        opt._normalize_for_dominance(1.0, "sideways")


def test_extract_kpis_unwraps_and_raises() -> None:
    assert opt._extract_kpis({"kpis": {"a": 1}}) == {"a": 1}
    # No 'kpis' key -> returns the mapping itself.
    assert opt._extract_kpis({"a": 1}) == {"a": 1}
    with pytest.raises(TypeError, match="must be a mapping"):
        opt._extract_kpis({"kpis": [1, 2, 3]})


def test_get_scalar_missing_and_non_numeric() -> None:
    with pytest.raises(KeyError, match="Missing KPI"):
        opt._get_scalar({"a": 1.0}, "b")
    with pytest.raises(TypeError, match="not numeric"):
        opt._get_scalar({"a": "not-a-number"}, "a")
    assert opt._get_scalar({"a": "2.5"}, "a") == 2.5


# ---------------------------------------------------------------------------
# build_grid_plan
# ---------------------------------------------------------------------------


def test_build_grid_plan_cartesian_and_labels() -> None:
    grid = [
        ParameterGridSpec(name="a", override_key="ka", values=(1.0, 2.0)),
        ParameterGridSpec(name="b", override_key="kb", values=(10.0, 20.0)),
    ]
    plan = build_grid_plan(grid)
    assert len(plan) == 4
    label0, ov0 = plan[0]
    assert label0 == "a=1.0;b=10.0"
    assert ov0 == {"ka": 1.0, "kb": 10.0}


def test_build_grid_plan_empty_grid_raises() -> None:
    with pytest.raises(ValueError, match="grid must be non-empty"):
        build_grid_plan([])


def test_build_grid_plan_exceeds_max_points_raises() -> None:
    grid = [
        ParameterGridSpec(name="a", override_key="ka", values=(1.0, 2.0, 3.0)),
        ParameterGridSpec(name="b", override_key="kb", values=(1.0, 2.0, 3.0)),
    ]
    with pytest.raises(ValueError, match="exceeds max_points"):
        build_grid_plan(grid, max_points=4)


# ---------------------------------------------------------------------------
# build_lhs_plan
# ---------------------------------------------------------------------------


def test_build_lhs_plan_shape_bounds_and_determinism() -> None:
    grid = [
        ParameterGridSpec(name="a", override_key="ka", values=(0.0, 10.0)),
        ParameterGridSpec(name="b", override_key="kb", values=(-5.0, 5.0)),
    ]
    plan = build_lhs_plan(grid, n_samples=6, seed=7)
    assert len(plan) == 6
    for label, ov in plan:
        assert set(ov) == {"ka", "kb"}
        assert 0.0 <= ov["ka"] <= 10.0
        assert -5.0 <= ov["kb"] <= 5.0
        assert "a~" in label and "b~" in label
    # Same seed -> identical samples.
    plan2 = build_lhs_plan(grid, n_samples=6, seed=7)
    assert [o for _, o in plan] == [o for _, o in plan2]


def test_build_lhs_plan_empty_grid_raises() -> None:
    with pytest.raises(ValueError, match="grid must be non-empty"):
        build_lhs_plan([], n_samples=3)


def test_build_lhs_plan_nonpositive_samples_raises() -> None:
    with pytest.raises(ValueError, match="n_samples must be > 0"):
        build_lhs_plan(_grid_one(), n_samples=0)


# ---------------------------------------------------------------------------
# run_pareto_search — orchestration
# ---------------------------------------------------------------------------


def test_run_pareto_search_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opt, "evaluate_with_overrides", _make_fake_eval())
    res = run_pareto_search(
        base_config={"finance": {"tariff_usd": 1.0}},
        objectives=_objectives(),
        grid=_grid_one(),
        plan_kind="grid",
    )
    assert isinstance(res, ParetoResult)
    assert res.metadata["plan_kind"] == "grid"
    assert res.metadata["n_points"] == 3
    assert len(res.points_all) == 3
    assert 1 <= res.metadata["n_pareto"] <= 3
    # KPIs attached by default.
    assert all(p.kpis for p in res.points_all)


def test_run_pareto_search_lhs_and_no_attach_kpis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(opt, "evaluate_with_overrides", _make_fake_eval())
    res = run_pareto_search(
        base_config={"finance": {"tariff_usd": 1.0}},
        objectives=_objectives(),
        grid=_grid_one(),
        plan_kind="LHS",  # exercises .lower().strip()
        n_samples=4,
        max_points=10,
        seed=99,
        attach_kpis=False,
    )
    assert res.metadata["plan_kind"] == "lhs"
    assert res.metadata["n_points"] == 4
    # attach_kpis=False -> empty kpis dicts.
    assert all(p.kpis == {} for p in res.points_all)


def test_run_pareto_search_handles_unwrapped_kpis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Evaluator returns a flat kpis mapping (no 'kpis' wrapper).
    monkeypatch.setattr(opt, "evaluate_with_overrides", _make_fake_eval(wrap_kpis=False))
    res = run_pareto_search(
        base_config={"finance": {"tariff_usd": 1.0}},
        objectives=[ObjectiveSpec(metric_key="project_irr", direction="max")],
        grid=_grid_one(),
    )
    assert res.metadata["n_points"] == 3


def test_run_pareto_search_empty_objectives_raises() -> None:
    with pytest.raises(ValueError, match="objectives must be non-empty"):
        run_pareto_search(base_config={}, objectives=[], grid=_grid_one())


def test_run_pareto_search_empty_grid_raises() -> None:
    with pytest.raises(ValueError, match="grid must be non-empty"):
        run_pareto_search(base_config={}, objectives=_objectives(), grid=[])


def test_run_pareto_search_lhs_samples_exceed_max_points_raises() -> None:
    with pytest.raises(ValueError, match="n_samples must be <= max_points"):
        run_pareto_search(
            base_config={},
            objectives=_objectives(),
            grid=_grid_one(),
            plan_kind="lhs",
            n_samples=50,
            max_points=10,
        )


def test_run_pareto_search_bad_plan_kind_raises() -> None:
    with pytest.raises(ValueError, match="plan_kind must be 'grid' or 'lhs'"):
        run_pareto_search(
            base_config={},
            objectives=_objectives(),
            grid=_grid_one(),
            plan_kind="random",
        )


def test_run_pareto_search_with_canonical_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Uses the real canonical config object as base_config (deep-copied
    # internally) while keeping evaluation mocked for speed/determinism.
    from analytics.scenario_loader import load_scenario_config

    cfg = load_scenario_config(str(LENDER))
    base = cfg if isinstance(cfg, Mapping) else getattr(cfg, "__dict__", {"x": 1})
    monkeypatch.setattr(opt, "evaluate_with_overrides", _make_fake_eval())
    res = run_pareto_search(
        base_config=dict(base) if isinstance(base, Mapping) else {"x": 1},
        objectives=_objectives(),
        grid=_grid_one(),
    )
    assert res.metadata["engine"] == "analytics.sensitivity.optimizer"
    assert res.metadata["n_points"] == 3


# ---------------------------------------------------------------------------
# export_pareto_table
# ---------------------------------------------------------------------------


def _toy_result() -> ParetoResult:
    objs = tuple(_objectives())
    pts = (
        ParetoPoint(
            label="p0",
            overrides={"ka": 1.0},
            objectives={"project_irr": 0.06, "min_dscr": 1.9},
            kpis={},
        ),
        ParetoPoint(
            label="p1",
            overrides={"ka": 2.0},
            objectives={"project_irr": 0.07, "min_dscr": 1.8},
            kpis={},
        ),
    )
    return ParetoResult(
        objectives=objs,
        grid=tuple(_grid_one()),
        points_all=pts,
        points_pareto=pts[:1],
        metadata={},
    )


def test_export_pareto_table_dataframe_pareto() -> None:
    pd = pytest.importorskip("pandas")
    df = export_pareto_table(_toy_result(), which="pareto")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1  # only the pareto subset
    assert "label" in df.columns
    assert "project_irr" in df.columns
    assert "ov::ka" in df.columns


def test_export_pareto_table_all_selects_full_set() -> None:
    df = export_pareto_table(_toy_result(), which="all")
    assert len(df) == 2


def test_export_pareto_table_fallback_without_pandas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the no-pandas branch -> returns list-of-dicts.
    monkeypatch.setattr(opt, "pd", None)
    rows = export_pareto_table(_toy_result(), which="all")
    assert isinstance(rows, list)
    assert rows[0]["label"] == "p0"
    assert rows[0]["project_irr"] == 0.06
    assert rows[0]["ov::ka"] == 1.0
    assert len(rows) == 2
