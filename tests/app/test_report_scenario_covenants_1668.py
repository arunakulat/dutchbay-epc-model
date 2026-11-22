"""The lender report tests the scenario's own covenant thresholds (#1668).

Owner decision on #1668 (2026-11-14): the report's minimum-DSCR floor is the scenario's
``constraints.min_dscr_covenant`` (1.30x for the lender case), not the 1.20x report
default, and the balloon ceiling is the scenario's ``constraints.max_balloon_pct`` (10%),
not 40%. A threshold the scenario does not declare keeps the report default, and the
report says which source each threshold came from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_config import load_report_config
from app.reports.report_model import _scenario_covenants, build_report_context

GENERATED_AT = "2026-11-14T00:00:00+00:00"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LENDER_CFG = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _defaults():
    return load_report_config().covenants


def test_report_defaults_are_unchanged_and_marked_as_defaults() -> None:
    defaults = _defaults()
    assert defaults.min_dscr_floor == pytest.approx(1.20)
    assert defaults.max_balloon_pct == pytest.approx(0.40)
    assert defaults.min_dscr_floor_source == "report_defaults"
    assert defaults.max_balloon_pct_source == "report_defaults"


def test_scenario_constraints_set_both_thresholds() -> None:
    covenants = _scenario_covenants(
        _defaults(),
        {"constraints": {"min_dscr_covenant": 1.3, "max_balloon_pct": 0.1}},
    )
    assert covenants.min_dscr_floor == pytest.approx(1.30)
    assert covenants.min_dscr_floor_source == "scenario"
    assert covenants.max_balloon_pct == pytest.approx(0.10)
    assert covenants.max_balloon_pct_source == "scenario"
    # The DSCR target is not part of #1668 and keeps the report default.
    assert covenants.min_dscr_target == _defaults().min_dscr_target


@pytest.mark.parametrize(
    "scenario",
    [
        None,
        {},
        {"constraints": None},
        {"constraints": {}},
        {"constraints": {"min_dscr_covenant": "n/a", "max_balloon_pct": True}},
        {"constraints": {"min_dscr_covenant": float("nan")}},
    ],
)
def test_undeclared_or_non_numeric_thresholds_keep_the_report_defaults(
    scenario: Any,
) -> None:
    defaults = _defaults()
    covenants = _scenario_covenants(defaults, scenario)
    assert covenants.min_dscr_floor == defaults.min_dscr_floor
    assert covenants.max_balloon_pct == defaults.max_balloon_pct
    assert covenants.min_dscr_floor_source == "report_defaults"
    assert covenants.max_balloon_pct_source == "report_defaults"


def test_one_declared_threshold_does_not_pull_in_the_other() -> None:
    covenants = _scenario_covenants(
        _defaults(), {"constraints": {"min_dscr_covenant": 1.25}}
    )
    assert covenants.min_dscr_floor == pytest.approx(1.25)
    assert covenants.min_dscr_floor_source == "scenario"
    assert covenants.max_balloon_pct == pytest.approx(0.40)
    assert covenants.max_balloon_pct_source == "report_defaults"
    # Assurance AF-2: a scenario floor never overwrites the report-default target.
    assert covenants.min_dscr_target == pytest.approx(_defaults().min_dscr_target)
    assert covenants.min_dscr_target != pytest.approx(1.25)


def test_a_min_dscr_between_the_two_floors_now_breaches() -> None:
    """1.22x met the old 1.20x default; it breaches the scenario's 1.30x covenant."""
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis={"min_dscr": 1.22}
    )
    without = build_report_context(case, generated_at=GENERATED_AT)
    assert without.verdict.dscr_covenant_met is True

    scenario: Dict[str, Any] = {"constraints": {"min_dscr_covenant": 1.3}}
    ctx = build_report_context(
        case, generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.covenants.min_dscr_floor == pytest.approx(1.30)
    assert ctx.verdict.dscr_covenant_met is False
    assert any(
        "breaches the 1.30x lock-up covenant (the scenario's covenant" in note
        for note in ctx.verdict.notes
    )


def test_lender_case_report_tests_the_scenario_covenant() -> None:
    scenario = yaml.safe_load(_LENDER_CFG.read_text(encoding="utf-8"))
    # #1845 sizes the lender case to the annual covenant, which meets 1.30. This test is
    # about reporting a breach, so it runs the lender case on the per-period sizing basis
    # that motivated #1668 (year-1 fold below the covenant).
    config = load_scenario_config(_LENDER_CFG)
    config["Financing_Terms"]["sizing_dscr_basis"] = "period"
    full = evaluate_with_overrides(raw_config=config, return_full_result=True)
    case = CaseResult.from_pipeline_result(full, scenario_variant="lendercase")
    min_dscr = case.kpis["min_dscr"]
    assert 1.20 <= min_dscr < 1.30, "the case that motivated #1668"

    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        scenario_config=scenario,
        debt_result=full["debt_result"],
        run_result=full,
    )
    assert ctx.covenants.min_dscr_floor == pytest.approx(1.30)
    assert ctx.covenants.max_balloon_pct == pytest.approx(0.10)
    assert ctx.verdict.dscr_covenant_met is False
    assert ctx.verdict.balloon_within_limit is False
    # The breach also raises the IC summary's high-severity covenant flag (#706).
    assert ctx.ic_summary is not None
    dscr_flags = [
        flag
        for flag in ctx.ic_summary.red_flags
        if flag.kind == "covenant_breach" and "Minimum DSCR" in flag.detail
    ]
    assert [flag.severity for flag in dscr_flags] == ["high"]
    # Owner wording (2026-11-15): the scenario's DSCR covenant is a lock-up covenant.
    assert dscr_flags[0].detail.endswith("breaches the lock-up covenant.")
    assert not any("lender floor" in note for note in ctx.verdict.notes)

    text = " ".join(render_report_html(ctx).split())
    assert "&ge; 1.30x lock-up covenant (scenario)" in text
    assert "&le; 10% ceiling (scenario covenant)" in text


@pytest.mark.parametrize(
    ("min_dscr", "met"),
    # Assurance AS-4: the tolerance is the engine's 1e-9, so 1e-8 below the covenant
    # is a breach.
    [(1.2999999999999998, True), (1.30, True), (1.3 - 1e-8, False), (1.2999, False)],
)
def test_a_dscr_sculpted_to_the_covenant_meets_it(min_dscr: float, met: bool) -> None:
    """Sculpt noise (1.2999999999999998) at a 1.30 covenant is not a breach."""
    case = CaseResult(
        status="success", scenario_variant="sculpted", kpis={"min_dscr": min_dscr}
    )
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        scenario_config={"constraints": {"min_dscr_covenant": 1.3}},
    )
    assert ctx.verdict.dscr_covenant_met is met


def test_a_scenario_without_constraints_renders_report_default_labels() -> None:
    """Assurance AS-4: the "report default" label is rendered, not only stored."""
    scenario = yaml.safe_load(_LENDER_CFG.read_text(encoding="utf-8"))
    full = evaluate_with_overrides(str(_LENDER_CFG), return_full_result=True)
    case = CaseResult.from_pipeline_result(full, scenario_variant="lendercase")
    scenario.pop("constraints", None)
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        scenario_config=scenario,
        debt_result=full["debt_result"],
        run_result=full,
    )
    text = " ".join(render_report_html(ctx).split())
    assert "&ge; 1.20x lender floor (report default)" in text
    assert "&le; 40% ceiling (report default)" in text
    # The report default keeps its own name, and the target says where it comes from.
    assert any(
        "1.20x lender floor (report default; report-default target 1.30x)" in note
        for note in ctx.verdict.notes
    )


@pytest.mark.parametrize(
    ("min_dscr", "shown"),
    [
        (1.2973, "1.297"),  # assurance AF-1: the web lendercase route's value
        (1.3 - 1e-8, "1.29999999"),
        (1.2999999999999998, "1.30"),  # within the tolerance: met, kept at 2 dp
        (1.22, "1.22"),
    ],
)
def test_a_breach_never_prints_the_covenant_as_the_dscr(
    min_dscr: float, shown: str
) -> None:
    """A DSCR just under 1.30x must not read "1.30x breaches the 1.30x ..." (AF-1)."""
    case = CaseResult(
        status="success", scenario_variant="near", kpis={"min_dscr": min_dscr}
    )
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        scenario_config={"constraints": {"min_dscr_covenant": 1.3}},
    )
    rel = "meets" if ctx.verdict.dscr_covenant_met else "breaches"
    assert any(
        note.startswith(f"Minimum DSCR {shown}x {rel} the 1.30x lock-up covenant")
        for note in ctx.verdict.notes
    )
    assert ctx.ic_summary is not None
    flags = [
        flag.detail
        for flag in ctx.ic_summary.red_flags
        if flag.kind == "covenant_breach" and "Minimum DSCR" in flag.detail
    ]
    expected = (
        []
        if ctx.verdict.dscr_covenant_met
        else [f"Minimum DSCR {shown}x breaches the lock-up covenant."]
    )
    assert flags == expected
