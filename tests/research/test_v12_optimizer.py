"""Smoke tests for the restored V12 multi-objective capital-structure optimiser.

`scripts/research/optimization.py` was unimportable on main (its `legacy_v12` /
`charts` siblings had been deleted in the Sprint 9 legacy purge). The siblings are
restored here from git history and several latent bugs were fixed so the tool runs:
  - the Pareto path passed a dict to build_financial_model (expects dataclasses),
  - it did float(None) on non-convergent grid points,
  - the V12 IRR solver returned None for project_irr (brentq's wide bracket
    overflows on 20-yr project streams) — now has a numpy-financial fallback.

These tests assert the tool IMPORTS and RUNS end-to-end with the expected result
SHAPE. They deliberately do NOT pin the V12 model's economic values: it is a
vintage (150 MW-era) research instrument whose absolute numbers are not canonical
(the live economics are analytics.optimization_v14 / the v14 pipeline).
"""
from __future__ import annotations

import pytest

pytest.importorskip("scipy")
pytest.importorskip("pandas")
pytest.importorskip("matplotlib")

from scripts.research import optimization as opt  # noqa: E402
from scripts.research.legacy_v12 import (  # noqa: E402
    build_financial_model,
    create_default_debt_structure,
    create_default_parameters,
)


def test_module_imports():
    # Regression for the ModuleNotFoundError that made this unimportable on main.
    for name in ("optimize_capital_structure", "optimize_debt_pareto"):
        assert hasattr(opt, name)


def test_build_financial_model_returns_both_irrs():
    # Regression for project_irr coming back None (brentq overflow) on defaults.
    res = build_financial_model(create_default_parameters(), create_default_debt_structure())
    assert res["equity_irr"] is not None and res["equity_irr"] > 0
    assert res["project_irr"] is not None and res["project_irr"] > 0


def test_optimize_capital_structure_runs():
    res = opt.optimize_capital_structure(
        objective="equity_irr", constraints={"min_irr": 0.10, "min_dscr": 1.30}
    )
    assert res["convergence"] is True
    for k in (
        "optimal_debt_ratio", "optimal_usd_pct", "optimal_dfi_pct",
        "optimized_equity_irr", "optimized_project_irr", "optimized_min_dscr",
    ):
        assert k in res
    assert 0.0 <= res["optimal_debt_ratio"] <= 1.0


def test_optimize_debt_pareto_produces_frontier():
    # Regression for the dict-arg bug + the float(None) crash on the Pareto path.
    res = opt.optimize_debt_pareto(
        grid_dr="0.50:0.80:0.10", grid_tenor="10:16:2", grid_grace="0:1:1"
    )
    assert res["grid_count"] > 0
    assert res["frontier_count"] > 0
    pt = res["frontier"][0]
    for k in ("debt_ratio", "tenor_years", "equity_irr", "min_dscr", "project_irr", "npv_12pct"):
        assert k in pt
    assert pt["project_irr"] is not None
