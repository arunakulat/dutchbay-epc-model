"""The solar assessment report summarises nullable MC trial arrays per metric (#1474).

At the report's default 1,000 trials (seed 123) equity IRR is undefined in 999 trials
while project IRR is defined in all of them. Before this summary filtered each metric,
``np.percentile`` and ``x < 0`` raised ``TypeError`` on the None entries. The arrays here
are built through ``aggregate_trials`` so they carry the engine's real nullable shape.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

from analytics.contracts_v14 import MonteCarloResult
from analytics.mc.aggregate import aggregate_trials
from analytics.mc.exports import _trial_coverage as exports_trial_coverage

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "generate_solar_assessment_report.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("gen_solar_report_mc", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _result(rows: list[dict[str, float | None]]) -> MonteCarloResult:
    return aggregate_trials(
        trial_metrics=rows,
        base_config={},
        param_names=["capex.usd_total"],
        samples=np.zeros((len(rows), 1)),
        meta={"seed": 123, "n_trials": len(rows)},
    )


def _rows(n: int, equity_defined_at: set[int]) -> list[dict[str, float | None]]:
    return [
        {
            "project_irr": -0.05 + 0.04 * i / n,
            "equity_irr": -0.25 if i in equity_defined_at else None,
            "dscr_min": 1.2,
        }
        for i in range(n)
    ]


def test_equity_undefined_in_999_of_1000_trials_does_not_raise() -> None:
    m = _load_module()
    result = _result(_rows(1000, {7}))
    assert sum(v is None for v in result.trials["equity_irr"]) == 999

    mc = m._summarise_mc_irr(result.trials, result.iterations, result.failed_iterations)

    assert mc["coverage"]["project_irr"] == {
        "defined_trials": 1000,
        "total_trials": 1000,
        "unavailable_trials": 0,
    }
    assert mc["coverage"]["equity_irr"] == {
        "defined_trials": 1,
        "total_trials": 1000,
        "unavailable_trials": 999,
    }
    project = [v for v in result.trials["project_irr"] if v is not None]
    assert mc["proj_irr"]["p50"] == float(np.percentile(project, 50))
    assert mc["p_below_0"] == float(np.mean([x < 0 for x in project]))
    assert len(mc["_irr_trials"]) == 1000
    assert mc["eq_p50"] == -0.25
    assert mc["eq_p_below_0"] == 1.0


def test_all_undefined_equity_reports_none_not_zero() -> None:
    m = _load_module()
    result = _result(_rows(20, set()))

    mc = m._summarise_mc_irr(result.trials, result.iterations, result.failed_iterations)

    assert mc["coverage"]["equity_irr"]["defined_trials"] == 0
    assert mc["eq_p50"] is None
    assert mc["eq_p_below_0"] is None
    assert mc["proj_irr"]["p10"] is not None


def test_coverage_uses_the_same_counts_as_the_exports_module() -> None:
    m = _load_module()
    result = _result(_rows(50, {0, 3, 49}))

    mc = m._summarise_mc_irr(result.trials, result.iterations, result.failed_iterations)

    for key in ("project_irr", "equity_irr"):
        assert mc["coverage"][key] == exports_trial_coverage(result, key)
