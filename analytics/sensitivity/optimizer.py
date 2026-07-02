"""
analytics.sensitivity.optimizer

Pareto-style multi-objective "optimizer" for v14 scenarios.

Intent
- Explore trade-offs across multiple metrics (e.g., IRR vs DSCR) by evaluating
  a bounded set of scenarios produced from parameter grids or sampled plans,
  or (opt-in) by an adaptive NSGA-II search (pymoo backend, plan_kind="pymoo").
- Produce a Pareto-efficient set (non-dominated frontier).
- Stay GWTF/CASPER friendly:
    * No CLI code
    * No pipeline imports (evaluation only via analytics.evaluation_v14.evaluate_with_overrides)
    * Import-safe (no pandas hard dependency; optional. pymoo is OPTIONAL too:
      call-time _require_pymoo() gate, never imported by the default plans)
    * Deterministic given seed + config + plan

Typical uses
- "Tariff vs Debt ratio" trade-offs
- "CAPEX vs DSCR" stress trade-offs
- "FX depreciation vs IRR downside" trade-offs

Public API (keep stable)
- run_pareto_search(...)
- pareto_frontier(...)
- export_pareto_table(...)

IMPORTANT:
- This module performs multi-scenario evaluation and can be compute-heavy.
  It intentionally enforces plan-size bounds to avoid accidental blow-ups.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from itertools import product
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from analytics.evaluation_v14 import evaluate_with_overrides

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore[assignment]


# -----------------------------
# Contracts / small data models
# -----------------------------


@dataclass(frozen=True)
class ObjectiveSpec:
    """
    Defines an objective metric for Pareto optimization.

    metric_key: KPI key in evaluation output (kpis dict)
    direction: "max" or "min"
    """

    metric_key: str
    direction: str = "max"  # "max" | "min"


@dataclass(frozen=True)
class ParameterGridSpec:
    """
    Defines a parameter to sweep.

    override_key: key passed into evaluate_with_overrides(overrides=...)
      - can be a dotted path if your override patcher supports it
    values: explicit numeric values to test
    """

    name: str
    override_key: str
    values: Tuple[float, ...]


@dataclass(frozen=True)
class ParetoPoint:
    """
    A single evaluated point in objective space.
    """

    label: str
    overrides: Mapping[str, Any]
    objectives: Mapping[str, float]  # metric_key -> value
    kpis: Mapping[str, Any]  # full KPI dict (for export/audit)


@dataclass(frozen=True)
class ParetoResult:
    """
    Output bundle.
    """

    objectives: Tuple[ObjectiveSpec, ...]
    grid: Tuple[ParameterGridSpec, ...]
    points_all: Tuple[ParetoPoint, ...]
    points_pareto: Tuple[ParetoPoint, ...]
    metadata: Mapping[str, Any]


# -----------------------------
# Core helpers
# -----------------------------


def _deepcopy_cfg(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(dict(cfg))


def _extract_kpis(out: Mapping[str, Any]) -> Mapping[str, Any]:
    k = out.get("kpis", out)
    if not isinstance(k, Mapping):
        raise TypeError(
            "Evaluation output must be a mapping or contain a 'kpis' mapping."
        )
    return k


def _get_scalar(kpis: Mapping[str, Any], key: str) -> float:
    if key not in kpis:
        raise KeyError(f"Missing KPI '{key}' in evaluation output.")
    v = kpis[key]
    try:
        return float(v)
    except Exception as e:
        raise TypeError(f"KPI '{key}' is not numeric: {v!r}") from e


def _normalize_for_dominance(value: float, direction: str) -> float:
    """
    Convert objective to a "larger is better" score space.
    For minimization objectives, invert sign.
    """
    d = direction.lower().strip()
    if d == "max":
        return float(value)
    if d == "min":
        return -float(value)
    raise ValueError(f"Objective direction must be 'max' or 'min', got: {direction!r}")


def pareto_frontier(
    points: Sequence[ParetoPoint], objectives: Sequence[ObjectiveSpec]
) -> List[ParetoPoint]:
    """
    Compute non-dominated frontier.
    A point A dominates B if it is >= in all normalized objectives and > in at least one.
    """
    if not points:
        return []

    obj_keys = [o.metric_key for o in objectives]
    directions = [o.direction for o in objectives]

    # Build normalized matrix: shape (n, m)
    mat = np.zeros((len(points), len(objectives)), dtype=float)
    for i, p in enumerate(points):
        for j, (k, d) in enumerate(zip(obj_keys, directions)):
            mat[i, j] = _normalize_for_dominance(float(p.objectives[k]), d)

    n = mat.shape[0]
    is_efficient = np.ones(n, dtype=bool)

    for i in range(n):
        if not is_efficient[i]:
            continue
        # Any point that is >= in all dims and > in at least one dim dominates i
        # We can mark i dominated by checking other points against i.
        for j in range(n):
            if i == j or not is_efficient[i]:
                continue
            ge_all = np.all(mat[j] >= mat[i])
            gt_any = np.any(mat[j] > mat[i])
            if ge_all and gt_any:
                is_efficient[i] = False
                break

    return [p for p, ok in zip(points, is_efficient) if ok]


# -----------------------------
# Plan builders (bounded)
# -----------------------------


def build_grid_plan(
    grid: Sequence[ParameterGridSpec],
    *,
    max_points: int = 5000,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Build a Cartesian grid plan with safety bound.

    Returns list of (label, overrides).
    """
    if not grid:
        raise ValueError("grid must be non-empty")

    sizes = [len(g.values) for g in grid]
    total = 1
    for s in sizes:
        total *= max(1, int(s))
    if total > int(max_points):
        raise ValueError(
            f"Grid size {total} exceeds max_points={max_points}. "
            "Reduce parameter values or increase max_points explicitly."
        )

    plan: List[Tuple[str, Dict[str, Any]]] = []

    # Deterministic ordering: iterate product in given grid order
    for combo in product(*[g.values for g in grid]):
        overrides: Dict[str, Any] = {}
        label_parts: List[str] = []
        for g, v in zip(grid, combo):
            overrides[g.override_key] = float(v)
            label_parts.append(f"{g.name}={v}")
        plan.append((";".join(label_parts), overrides))

    return plan


def build_lhs_plan(
    grid: Sequence[ParameterGridSpec],
    *,
    n_samples: int,
    seed: int = 123,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Build a bounded LHS-like plan over each parameter's [min(values), max(values)] range.
    Useful when full grid explodes.

    Note: This is NOT full LHS over arbitrary distributions; it's a lightweight bounded sampler.
    """
    if not grid:
        raise ValueError("grid must be non-empty")
    n = int(n_samples)
    if n <= 0:
        raise ValueError("n_samples must be > 0")

    rng = np.random.default_rng(int(seed))
    plan: List[Tuple[str, Dict[str, Any]]] = []

    # Build stratified samples in [0,1] per dimension
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.uniform(size=(n, len(grid)))
    a = cut[:n]
    b = cut[1:]
    pts = u * (b - a)[:, None] + a[:, None]

    # Permute per dimension for LHS-like
    lhs = np.zeros_like(pts)
    for j in range(len(grid)):
        lhs[:, j] = pts[rng.permutation(n), j]

    for i in range(n):
        overrides: Dict[str, Any] = {}
        label_parts: List[str] = []
        for j, g in enumerate(grid):
            lo = float(min(g.values))
            hi = float(max(g.values))
            v = lo + float(lhs[i, j]) * (hi - lo)
            overrides[g.override_key] = v
            label_parts.append(f"{g.name}~{v:.6g}")
        plan.append((";".join(label_parts), overrides))

    return plan


# -----------------------------
# Optional pymoo backend (opt-in; CASPER call-time gate)
# -----------------------------


def _require_pymoo() -> None:
    """Fail loud (CASPER) when the optional pymoo dependency is missing.

    Raises:
        ImportError: pymoo is not importable. The message carries the exact
            install commands; the default 'grid'/'lhs' plans never call this.
    """
    try:
        import pymoo  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "The 'pymoo' Pareto backend requires pymoo. Install the optional "
            'extra (`pip install -e ".[pareto]"`) or `pip install pymoo`. It is '
            "an OPTIONAL dependency — the base finance install and the default "
            "'grid'/'lhs' plans never need it."
        ) from exc


def _run_pymoo_search(
    *,
    base_cfg: Dict[str, Any],
    objectives: Sequence[ObjectiveSpec],
    grid: Sequence[ParameterGridSpec],
    n_samples: int,
    max_points: int,
    seed: int,
    pop_size: int,
    attach_kpis: bool,
) -> ParetoResult:
    """Adaptive NSGA-II Pareto search over the grid's parameter ranges (pymoo).

    Maps each :class:`ParameterGridSpec` to one continuous decision variable on
    ``[min(values), max(values)]`` — the same range convention as
    :func:`build_lhs_plan` (intermediate grid values are not used) — and lets
    NSGA-II allocate the evaluation budget adaptively instead of spending it on
    a fixed plan. Useful for >=2-parameter trade-offs where the Cartesian grid
    explodes past ``max_points`` and a coarse grid or the lightweight LHS
    sampler under-resolves the frontier.

    Every candidate is evaluated ONLY via
    ``analytics.evaluation_v14.evaluate_with_overrides`` (CCCDIR gateway), and
    the returned frontier is recomputed over ALL evaluated points with this
    module's own :func:`pareto_frontier`, so dominance semantics are identical
    to the 'grid'/'lhs' plans and results use the existing
    :class:`ParetoPoint`/:class:`ParetoResult` contracts.

    Budget: the engine is called at most ``n_samples`` times
    (``n_samples <= max_points`` is enforced, keeping ``max_points`` the hard
    evaluation-budget cap shared with the other plans). Internally the run is
    shaped as ``pop x n_gen`` with ``pop = min(pop_size, n_samples)`` and
    ``n_gen = n_samples // pop``, so the budget cannot be overshot.

    Determinism: deterministic for a fixed ``seed`` (and pymoo version). pymoo
    seeds the process-global ``random``/``numpy.random`` state; both states are
    snapshot before and restored after the run so callers' RNG streams are not
    perturbed (MRM-01).

    Args:
        base_cfg: Deep-copied scenario config mapping (v14 raw config).
        objectives: Non-empty objective specs ("max"/"min" per metric).
        grid: Non-empty parameter specs; each needs a non-degenerate range.
        n_samples: Total evaluation budget (>= 2 and <= max_points).
        max_points: Hard evaluation-budget cap shared with the other plans.
        seed: RNG seed for the NSGA-II run.
        pop_size: NSGA-II population size (>= 2; clamped to the budget).
        attach_kpis: Attach the full KPI dict to each point when True.

    Returns:
        ParetoResult with all evaluated points, the non-dominated frontier, and
        run metadata (plan_kind='pymoo', algorithm='nsga2', budget shape).

    Raises:
        ImportError: pymoo is not installed (CASPER call-time gate).
        ValueError: degenerate parameter range or an inconsistent budget.
    """
    _require_pymoo()

    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.core.problem import Problem
    from pymoo.optimize import minimize as pymoo_minimize

    budget = int(n_samples)
    if budget > int(max_points):
        raise ValueError("n_samples must be <= max_points")
    if budget < 2:
        raise ValueError("pymoo backend requires n_samples >= 2")
    if int(pop_size) < 2:
        raise ValueError("pop_size must be >= 2")

    lows: List[float] = []
    highs: List[float] = []
    for g in grid:
        lo = float(min(g.values))
        hi = float(max(g.values))
        if not hi > lo:
            raise ValueError(
                f"Parameter {g.name!r} has a degenerate range [{lo}, {hi}]; "
                "the pymoo backend needs min(values) < max(values). Pin fixed "
                "parameters in base_config instead of sweeping them."
            )
        lows.append(lo)
        highs.append(hi)

    pop = min(int(pop_size), budget)
    n_gen = max(1, budget // pop)

    n_obj = len(objectives)
    evaluated: List[ParetoPoint] = []

    class _GatewayProblem(Problem):  # type: ignore[misc]
        """pymoo Problem evaluating candidates via the v14 gateway (CCCDIR)."""

        def __init__(self) -> None:
            super().__init__(
                n_var=len(grid),
                n_obj=n_obj,
                xl=np.asarray(lows, dtype=float),
                xu=np.asarray(highs, dtype=float),
            )

        def _evaluate(
            self, x: Any, out: Dict[str, Any], *args: Any, **kwargs: Any
        ) -> None:
            """Evaluate a candidate matrix; record points and fill out['F']."""
            xs = np.atleast_2d(np.asarray(x, dtype=float))
            f_mat = np.zeros((xs.shape[0], n_obj), dtype=float)
            for i in range(xs.shape[0]):
                overrides: Dict[str, Any] = {}
                label_parts: List[str] = []
                for j, g in enumerate(grid):
                    v = float(xs[i, j])
                    overrides[g.override_key] = v
                    label_parts.append(f"{g.name}~{v:.6g}")
                out_eval = evaluate_with_overrides(
                    config_path=None,
                    raw_config=base_cfg,
                    overrides=overrides,
                )
                kpis = _extract_kpis(out_eval)
                obj_vals: Dict[str, float] = {}
                for k, o in enumerate(objectives):
                    val = _get_scalar(kpis, o.metric_key)
                    obj_vals[o.metric_key] = val
                    # pymoo minimizes: negate the larger-is-better normalization.
                    f_mat[i, k] = -_normalize_for_dominance(val, o.direction)
                evaluated.append(
                    ParetoPoint(
                        label=";".join(label_parts),
                        overrides=dict(overrides),
                        objectives=obj_vals,
                        kpis=dict(kpis) if attach_kpis else {},
                    )
                )
            out["F"] = f_mat

    # pymoo seeds the process-global RNGs; snapshot + restore them (MRM-01).
    py_state = random.getstate()
    np_state = np.random.get_state()
    try:
        pymoo_minimize(
            _GatewayProblem(),
            NSGA2(pop_size=pop),
            ("n_gen", int(n_gen)),
            seed=int(seed),
            verbose=False,
        )
    finally:
        random.setstate(py_state)
        np.random.set_state(np_state)

    points = list(evaluated)
    pareto = pareto_frontier(points, objectives)

    meta: Dict[str, Any] = {
        "engine": "analytics.sensitivity.optimizer",
        "plan_kind": "pymoo",
        "algorithm": "nsga2",
        "seed": int(seed),
        "pop_size": int(pop),
        "n_gen": int(n_gen),
        "evaluation_budget": int(budget),
        "n_points": int(len(points)),
        "n_pareto": int(len(pareto)),
        "max_points": int(max_points),
    }

    return ParetoResult(
        objectives=tuple(objectives),
        grid=tuple(grid),
        points_all=tuple(points),
        points_pareto=tuple(pareto),
        metadata=meta,
    )


# -----------------------------
# Orchestration
# -----------------------------


def run_pareto_search(
    *,
    base_config: Mapping[str, Any],
    objectives: Sequence[ObjectiveSpec],
    grid: Sequence[ParameterGridSpec],
    plan_kind: str = "grid",  # "grid" | "lhs" | "pymoo" (opt-in)
    max_points: int = 5000,
    n_samples: int = 500,
    seed: int = 123,
    attach_kpis: bool = True,
    pop_size: int = 32,
) -> ParetoResult:
    """
    Run a bounded Pareto search and return both all points and the Pareto frontier.

    plan_kind:
        - "grid" (default): exhaustive Cartesian plan via :func:`build_grid_plan`.
        - "lhs": bounded LHS-like sampling via :func:`build_lhs_plan`
          (``n_samples`` evaluations).
        - "pymoo": OPT-IN adaptive NSGA-II search over each parameter's
          ``[min(values), max(values)]`` range (see :func:`_run_pymoo_search`).
          Requires the optional pymoo dependency (``pip install -e ".[pareto]"``;
          CASPER call-time gate). Budget = ``n_samples`` (must be
          ``<= max_points``); ``pop_size`` shapes the NSGA-II population and is
          ignored by "grid"/"lhs".
    """
    if not objectives:
        raise ValueError("objectives must be non-empty")
    if not grid:
        raise ValueError("grid must be non-empty")

    base_cfg = _deepcopy_cfg(base_config)

    kind = plan_kind.lower().strip()
    if kind == "pymoo":
        # Opt-in adaptive backend; never reached unless explicitly requested.
        return _run_pymoo_search(
            base_cfg=base_cfg,
            objectives=objectives,
            grid=grid,
            n_samples=n_samples,
            max_points=max_points,
            seed=seed,
            pop_size=pop_size,
            attach_kpis=attach_kpis,
        )
    if kind == "grid":
        plan = build_grid_plan(grid, max_points=max_points)
    elif kind == "lhs":
        if n_samples > max_points:
            raise ValueError("n_samples must be <= max_points")
        plan = build_lhs_plan(grid, n_samples=n_samples, seed=seed)
    else:
        raise ValueError(
            f"plan_kind must be 'grid', 'lhs', or 'pymoo', got: {plan_kind!r}"
        )

    points: List[ParetoPoint] = []

    for label, overrides in plan:
        out = evaluate_with_overrides(
            config_path=None,
            raw_config=base_cfg,
            overrides=overrides,
        )
        kpis = _extract_kpis(out)

        obj_vals: Dict[str, float] = {}
        for o in objectives:
            obj_vals[o.metric_key] = _get_scalar(kpis, o.metric_key)

        points.append(
            ParetoPoint(
                label=label,
                overrides=dict(overrides),
                objectives=obj_vals,
                kpis=dict(kpis) if attach_kpis else {},
            )
        )

    pareto = pareto_frontier(points, objectives)

    meta: Dict[str, Any] = {
        "engine": "analytics.sensitivity.optimizer",
        "plan_kind": kind,
        "seed": int(seed),
        "n_points": int(len(points)),
        "n_pareto": int(len(pareto)),
        "max_points": int(max_points),
    }

    return ParetoResult(
        objectives=tuple(objectives),
        grid=tuple(grid),
        points_all=tuple(points),
        points_pareto=tuple(pareto),
        metadata=meta,
    )


# -----------------------------
# Exports (optional pandas)
# -----------------------------


def export_pareto_table(
    result: ParetoResult,
    *,
    which: str = "pareto",  # "pareto" | "all"
) -> Any:
    """
    Return a pandas DataFrame (if available) or list-of-dicts with key fields.
    """
    pts = (
        result.points_pareto if which.lower().strip() == "pareto" else result.points_all
    )

    rows: List[Dict[str, Any]] = []
    obj_keys = [o.metric_key for o in result.objectives]
    for p in pts:
        r: Dict[str, Any] = {"label": p.label}
        # objectives
        for k in obj_keys:
            r[k] = p.objectives.get(k)
        # override keys (flatten)
        for ok, ov in p.overrides.items():
            r[f"ov::{ok}"] = ov
        rows.append(r)

    if pd is not None:
        return pd.DataFrame(rows)
    return rows
