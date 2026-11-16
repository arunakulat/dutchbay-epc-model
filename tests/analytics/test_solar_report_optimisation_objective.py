"""The solar assessment report ranks its optimisations on equity NPV (#1522 A-3).

#1456 decided that optimisers rank on equity NPV, because equity IRR can order
candidates backwards when equity cash flows change sign more than once. The two
capital-structure optimisers follow it. The solar assessment report still ranked its
gearing and DSCR-target optimisations on ``equity_irr``, which #1522's assurance lane
recorded as A-3. On this report the two measures pick different DSCR targets.

``TEST-01`` oracle that did not originate in this change: the source of the shared report
module itself (``app/reports/solar_assessment.py`` since #1784), read with ``ast``, so every
``optimize_parameter`` call is checked without the report's optional extras.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "app" / "reports" / "solar_assessment.py"
)


def _load_module() -> Any:
    from app.reports import solar_assessment

    return solar_assessment


def _optimise_calls() -> list[ast.Call]:
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "optimize_parameter"
    ]


def test_every_report_optimisation_ranks_on_equity_npv() -> None:
    mod = _load_module()
    assert mod.OPTIMISATION_OBJECTIVE == "equity_npv"
    calls = _optimise_calls()
    assert len(calls) == 2  # gearing and the DSCR target
    for call in calls:
        objective = {kw.arg: kw.value for kw in call.keywords}["objective_key"]
        assert isinstance(objective, ast.Name), ast.dump(objective)
        assert objective.id == "OPTIMISATION_OBJECTIVE"


def test_the_script_names_no_irr_objective() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    assert 'objective_key="equity_irr"' not in source
    assert "objective_key='equity_irr'" not in source


def _opt(best: Dict[str, float] | None) -> Dict[str, Any]:
    curve = [
        {
            "x": x,
            "obj": -7e6 + x * 1e6,
            "feasible": best is not None,
            "eqIRR": None,
            "cure": 0.0,
        }
        for x in (0.3, 0.5, 0.75)
    ]
    return {
        "objective_key": "equity_npv",
        "covenant": 1.3,
        "curve": curve,
        "best": best,
    }


def test_the_caption_states_the_npv_optimum_from_the_run() -> None:
    caption = _load_module().optimisation_caption(_opt({"x": 0.5, "obj": -6.5e6}))
    assert "ranks on equity NPV, not equity IRR (#1456)" in caption
    assert caption.endswith("Best feasible gearing 50%, equity NPV -USD 6.50M.")


def test_the_caption_says_so_when_no_gearing_meets_the_covenant() -> None:
    caption = _load_module().optimisation_caption(_opt(None))
    assert caption.endswith("No gearing from 30% to 75% meets the covenant.")
    assert "35%" not in caption  # the old fixed caption's claim


def test_the_pdf_captions_the_gearing_chart_from_the_run() -> None:
    mod = _load_module()
    opt = _opt({"x": 0.5, "obj": -6.5e6})
    doc = mod.as_dbpl_document(
        {
            "scenario_name": "Any",
            "scenario_path": "scenarios/example.yaml",
            "not_run": [],
            "optimization": opt,
        },
        {},
        issue_date="2026-11-16",
    )
    gearing = next(s for s in doc["sections"] if s["heading"] == "Gearing optimisation")
    assert gearing["intro"] == mod.optimisation_caption(opt)
    assert "1.30x minimum per-period DSCR" in gearing["intro"]
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "feasible only below ~35% gearing" not in source
    assert '"Equity IRR (%)"' not in source  # the chart's axis follows the objective
