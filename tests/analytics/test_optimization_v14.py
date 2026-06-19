#!/usr/bin/env python
"""Tests for the optimization_v14 facade (#30).

Structural tests (robust to model nonlinearity): the sweep runs over the v14
pipeline, records a full curve, applies the KPI constraint, and selects the best
feasible point in the requested direction.

Context:
    Sprint 11 - Issue #30 (optimization_v14 using evaluate_with_overrides).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.optimization_v14 import OptimizationResult, optimize_parameter

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Sweep the gearing cap; equity IRR is the objective, min DSCR the constraint.
COMMON = dict(
    config_path=LENDER_CONFIG,
    param_path="Financing_Terms.debt_ratio",
    objective_key="equity_irr",
    lower=0.45,
    upper=0.70,
    n_steps=5,
)


def test_sweep_runs_and_curve_length() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=1.20)
    assert isinstance(res, OptimizationResult)
    assert len(res.curve) == 5
    assert res.best is not None


def test_best_is_max_feasible() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=1.20)
    feasible = [p for p in res.curve if p.feasible]
    assert res.best is not None
    assert res.best.objective == max(p.objective for p in feasible)
    assert res.best.feasible


def test_min_direction_selects_lowest() -> None:
    res = optimize_parameter(**COMMON, direction="min")
    assert res.best is not None
    assert res.best.objective == min(p.objective for p in res.curve)


def test_no_constraint_all_feasible() -> None:
    res = optimize_parameter(**COMMON)
    assert all(p.feasible for p in res.curve)
    assert all(p.constraint is None for p in res.curve)
    assert res.best is not None
    assert res.best.objective == max(p.objective for p in res.curve)


def test_constraint_recorded() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=1.20)
    assert all(p.constraint is not None for p in res.curve)


def test_impossible_constraint_returns_no_best() -> None:
    res = optimize_parameter(**COMMON, constraint_key="min_dscr", constraint_min=99.0)
    assert res.best is None
    assert all(not p.feasible for p in res.curve)


def test_invalid_direction_raises() -> None:
    with pytest.raises(ValueError, match="direction must be"):
        optimize_parameter(**COMMON, direction="sideways")


def test_too_few_steps_raises() -> None:
    args = dict(COMMON)
    args["n_steps"] = 1
    with pytest.raises(ValueError, match="n_steps must be"):
        optimize_parameter(**args)
