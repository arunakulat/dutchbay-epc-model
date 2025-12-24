# ruff: noqa: E402
from __future__ import annotations

"""
analytics.sensitivity.optimizer

Pareto-style multi-objective "optimizer" for v14 scenarios.

Intent
- Explore trade-offs across multiple metrics (e.g., IRR vs DSCR) by evaluating
  a bounded set of scenarios produced from parameter grids or sampled plans.
- Produce a Pareto-efficient set (non-dominated frontier).
- Stay GWTF/CASPER friendly:
    * No CLI code
    * No pipeline imports (evaluation only via analytics.evaluation_v14.evaluate_with_overrides)
    * Import-safe (no pandas hard dependency; optional)
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

from dataclasses import dataclass
from itertools import product
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import copy
import math
import numpy as np

from analytics.evaluation_v14 import evaluate_with_overrides

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore


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
    objectives: Mapping[str, float]   # metric_key -> value
    kpis: Mapping[str, Any]           # full KPI dict (for export/audit)


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
        raise TypeError("Evaluation output must be a mapping or contain a 'kpis' mapping.")
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


def pareto_frontier(points: Sequence[ParetoPoint], objectives: Sequence[ObjectiveSpec]) -> List[ParetoPoint]:
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
# Orchestration
# -----------------------------

def run_pareto_search(
    *,
    base_config: Mapping[str, Any],
    objectives: Sequence[ObjectiveSpec],
    grid: Sequence[ParameterGridSpec],
    plan_kind: str = "grid",  # "grid" | "lhs"
    max_points: int = 5000,
    n_samples: int = 500,
    seed: int = 123,
    attach_kpis: bool = True,
) -> ParetoResult:
    """
    Run a bounded Pareto search and return both all points and the Pareto frontier.
    """
    if not objectives:
        raise ValueError("objectives must be non-empty")
    if not grid:
        raise ValueError("grid must be non-empty")

    base_cfg = _deepcopy_cfg(base_config)

    kind = plan_kind.lower().strip()
    if kind == "grid":
        plan = build_grid_plan(grid, max_points=max_points)
    elif kind == "lhs":
        if n_samples > max_points:
            raise ValueError("n_samples must be <= max_points")
        plan = build_lhs_plan(grid, n_samples=n_samples, seed=seed)
    else:
        raise ValueError(f"plan_kind must be 'grid' or 'lhs', got: {plan_kind!r}")

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
    pts = result.points_pareto if which.lower().strip() == "pareto" else result.points_all

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
