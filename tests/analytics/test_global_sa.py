"""Global sensitivity (SALib Morris/Sobol) — analytics/sensitivity/global_sa.py.

- Closed-form: Sobol recovers the known Ishigami interaction structure (x3 has ~0 first-order
  but material total-order — a pure interaction the one-way tornado cannot see).
- Engine smoke: Morris screening runs through the canonical evaluate_with_overrides gateway
  on the lender case and ranks the known-dominant drivers (tariff / capex) at the top.
- build_problem contract: skips fx_calibrated drivers; requires >=2 sweepable drivers.

KPI-neutral: this is an additive, read-only analysis layer; the deterministic base case is
never touched (no canonical-KPI assertions belong here).
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("SALib")  # optional dependency (CASPER); skip cleanly if absent

from pathlib import Path  # noqa: E402

from analytics.sensitivity.global_sa import (  # noqa: E402
    GlobalSAProblem,
    build_problem,
    run_morris,
    run_sobol,
)

REPO = Path(__file__).resolve().parents[2]
LENDER = str(REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _ishigami(overrides):
    """Standard SALib test function f(x1,x2,x3) = sin x1 + a sin^2 x2 + b x3^4 sin x1.

    Known Sobol (a=7, b=0.1): S1 ~= [0.314, 0.442, 0.0]; ST ~= [0.557, 0.442, 0.244].
    x3 is the diagnostic case: ~0 first-order, but ~0.24 total-order (pure interaction).
    """
    a, b = 7.0, 0.1
    x1, x2, x3 = overrides["x1"], overrides["x2"], overrides["x3"]
    return {"y": math.sin(x1) + a * math.sin(x2) ** 2 + b * (x3**4) * math.sin(x1)}


def test_sobol_recovers_ishigami_interaction_structure() -> None:
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    res = run_sobol(problem=prob, evaluate_fn=_ishigami, metrics=("y",), n=512, seed=1)
    d = res["metrics"]["y"]["drivers"]
    # x1, x2 carry real first-order variance.
    assert d["x1"]["S1"] > 0.2
    assert d["x2"]["S1"] > 0.3
    # x3: ~0 first-order, but materially interactive (ST >> S1).
    assert abs(d["x3"]["S1"]) < 0.1
    assert d["x3"]["ST"] > 0.1
    assert d["x3"]["interactive"] is True
    assert res["metrics"]["y"]["interactions_present"] is True
    # Total-order dominates first-order for every driver (variance accounting).
    for name in prob.names:
        assert d[name]["ST"] >= d[name]["S1"] - 0.05


def test_build_problem_skips_fx_calibrated() -> None:
    params = [
        {"name": "project.capacity_factor", "low": 0.30, "high": 0.36},
        {"name": "fx.start_lkr_per_usd", "distribution": "fx_calibrated"},
        {"name": "capex.usd_total", "low": 1.0e8, "high": 1.2e8},
    ]
    prob = build_problem("ignored.yaml", params=params)
    assert prob.names == ["project.capacity_factor", "capex.usd_total"]
    assert prob.skipped == ["fx.start_lkr_per_usd"]


def test_build_problem_requires_two_drivers() -> None:
    with pytest.raises(ValueError, match=">=2 sweepable drivers"):
        build_problem("ignored.yaml", params=[{"name": "x", "low": 0.0, "high": 1.0}])


def test_build_problem_requires_both_bounds() -> None:
    """A parameter that omits a bound must fail with an actionable ValueError naming
    the field (CASPER), not the bare TypeError that float(None) used to raise."""
    with pytest.raises(ValueError, match="both a low/min and a high/max"):
        build_problem(
            "ignored.yaml",
            params=[
                {"name": "a", "low": 0.0, "high": 1.0},
                {"name": "b", "low": 0.0},  # missing high/max -> float(None) pre-fix
            ],
        )


def test_morris_smoke_lendercase_ranks_dominant_drivers() -> None:
    res = run_morris(LENDER, n_trajectories=4, metrics=("project_irr",), seed=1)
    assert res["n_runs"] == 4 * (res["problem"]["num_vars"] + 1)
    ranking = res["metrics"]["project_irr"]["ranking"]
    # tariff and capex are the model's known dominant project-IRR drivers; one should top it.
    assert ranking[0] in {"tariff.lkr_per_kwh", "capex.usd_total"}
