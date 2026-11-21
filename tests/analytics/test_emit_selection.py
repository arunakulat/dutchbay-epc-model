"""Tests for the emit_all switch and per-emitter planning (#1756)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

import pytest
import yaml
from omegaconf import OmegaConf

import run_full_pipeline_v14 as rfp
from analytics.emit_selection import (
    EMIT_ALL_DEFAULT,
    EMIT_FLAGS,
    STATUS_FAILED,
    STATUS_NOT_RUN,
    STATUS_OFF,
    STATUS_RUN,
    WRITE_ARTIFACTS_OFF_REASON,
    plan_emitters,
    plan_report,
)

#: A scenario file that exists, for a well-formed tech_comparison entry.
_EXISTING_CONFIG = str(
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)

_ALL_INPUTS_SCENARIO: Dict[str, Any] = {
    "monte_carlo": {"parameters": [{"name": "x"}]},
    "interaction_grid": {"metric": "project_irr"},
    "grid": {"study_enabled": True},
}
_ALL_INPUTS_CFG: Dict[str, Any] = {
    "emit_all": True,
    "tech_comparison": {"scenarios": [{"label": "a", "config": _EXISTING_CONFIG}]},
}


def _runs(plan: Dict[str, Any]) -> Dict[str, bool]:
    return {flag: decision.run for flag, decision in plan.items()}


def test_emit_all_is_on_by_default() -> None:
    """Owner ruling 2026-11-16: the analyses run for every scenario unless switched off."""
    assert EMIT_ALL_DEFAULT is True
    plan = plan_emitters(OmegaConf.create({}), {})
    assert list(plan) == list(EMIT_FLAGS)
    assert {d.source for d in plan.values()} == {"emit_all"}
    assert plan["emit_executive_workbook"].run
    # Every emitter that does not run says why.
    for decision in plan.values():
        assert decision.run or (decision.status == STATUS_NOT_RUN and decision.reason)


def test_unset_emit_all_needs_the_scenario() -> None:
    with pytest.raises(ValueError, match="effective scenario"):
        plan_emitters(OmegaConf.create({}))


def test_emit_all_off_runs_nothing_and_needs_no_scenario() -> None:
    plan = plan_emitters(OmegaConf.create({"emit_all": False}))
    assert list(plan) == list(EMIT_FLAGS)
    assert not any(_runs(plan).values())
    assert {d.status for d in plan.values()} == {STATUS_OFF}


def test_write_artifacts_false_switches_nothing_on_under_emit_all() -> None:
    """#1760 assurance L-1: a run that writes no files writes no report under emit_all."""
    cfg = OmegaConf.create({"emit_executive_workbook": True})
    plan = plan_emitters(cfg, None, write_artifacts=False)
    assert _runs(plan) == {
        flag: flag == "emit_executive_workbook" for flag in EMIT_FLAGS
    }
    for flag in EMIT_FLAGS[1:]:
        assert plan[flag].status == STATUS_NOT_RUN
        assert plan[flag].reason == WRITE_ARTIFACTS_OFF_REASON


def test_single_switch_behaves_as_before() -> None:
    plan = plan_emitters({"emit_all": False, "emit_grid_screen": True})
    assert _runs(plan) == {flag: flag == "emit_grid_screen" for flag in EMIT_FLAGS}
    assert plan["emit_grid_screen"].source == "explicit"


def test_emit_all_runs_every_emitter_whose_inputs_are_present() -> None:
    plan = plan_emitters(_ALL_INPUTS_CFG, _ALL_INPUTS_SCENARIO)
    assert all(_runs(plan).values())
    assert {d.source for d in plan.values()} == {"emit_all"}


def test_emit_all_lists_absent_inputs_as_not_run_with_reasons() -> None:
    plan = plan_emitters({"emit_all": True}, {})
    assert plan["emit_executive_workbook"].status == STATUS_RUN
    not_run = {f: d.reason for f, d in plan.items() if d.status == STATUS_NOT_RUN}
    # The workbook and the lender report (#1752) apply to every run with figures.
    assert plan["emit_lender_report"].status == STATUS_RUN
    assert set(not_run) == set(EMIT_FLAGS) - {
        "emit_executive_workbook",
        "emit_lender_report",
    }
    assert "monte_carlo.parameters" in str(not_run["emit_capital_risk_report"])
    assert "interaction_grid" in str(not_run["emit_interaction_grid"])
    assert "tech_comparison.scenarios" in str(not_run["emit_tech_comparison"])
    assert "study_enabled" in str(not_run["emit_grid_screen"])


def test_explicit_switch_wins_over_emit_all() -> None:
    cfg = {**_ALL_INPUTS_CFG, "emit_grid_screen": False}
    plan = plan_emitters(cfg, _ALL_INPUTS_SCENARIO)
    assert plan["emit_grid_screen"].run is False
    assert plan["emit_grid_screen"].source == "explicit"
    assert plan["emit_tech_comparison"].run is True


def test_explicit_true_is_attempted_even_without_inputs() -> None:
    """An explicit opt-in keeps failing loud in the emitter, as before #1756."""
    plan = plan_emitters({"emit_all": True, "emit_grid_screen": True}, {})
    assert plan["emit_grid_screen"].run is True
    assert plan["emit_grid_screen"].status == STATUS_RUN


def test_empty_tech_comparison_list_is_not_applicable() -> None:
    plan = plan_emitters({"emit_all": True, "tech_comparison": {"scenarios": []}}, {})
    assert plan["emit_tech_comparison"].status == STATUS_NOT_RUN


@pytest.mark.parametrize(
    ("scenarios", "type_name"),
    [(5, "int"), ("a.yaml", "str"), ({"label": "a"}, "DictConfig")],
)
def test_malformed_tech_comparison_list_is_listed_not_raised(
    scenarios: Any, type_name: str
) -> None:
    """Assurance review L-1 at 43a58859: a malformed value is listed, never raised."""
    cfg = OmegaConf.create(
        {"emit_all": True, "tech_comparison": {"scenarios": scenarios}}
    )
    decision = plan_emitters(cfg, {})["emit_tech_comparison"]
    assert decision.status == STATUS_NOT_RUN
    assert decision.reason == (
        "tech_comparison.scenarios must be a list of {label, config} entries; "
        f"got {type_name}"
    )


#: Malformed ``tech_comparison`` blocks (#1760 domain D-1 at fce4232a): the whole block's
#: shape, not just ``.scenarios``. Each pairs the block with the start of the plan's reason.
_MALFORMED_TECH_COMPARISON = [
    ([1, 2], "tech_comparison must be a mapping with a scenarios list; got ListConfig"),
    (5, "tech_comparison must be a mapping with a scenarios list; got int"),
    ("a.yaml", "tech_comparison must be a mapping with a scenarios list; got str"),
    ({"path": "x.html"}, "the run config lists no tech_comparison.scenarios"),
    ({"scenarios": [5]}, "tech_comparison.scenarios[0] must be a mapping"),
    (
        {"scenarios": [{"config": _EXISTING_CONFIG}]},
        "tech_comparison.scenarios[0] must declare a non-empty 'label'",
    ),
    (
        {"scenarios": [{"label": "a"}]},
        "tech_comparison.scenarios[0] ('a') must declare a 'config' path",
    ),
    (
        {"scenarios": [{"label": "a", "config": "no/such/scenario.yaml"}]},
        "tech_comparison.scenarios[0] ('a') config path does not exist",
    ),
]


@pytest.mark.parametrize(("block", "reason"), _MALFORMED_TECH_COMPARISON)
def test_a_malformed_tech_comparison_block_is_listed_not_raised(
    block: Any, reason: str
) -> None:
    """#1760 domain D-1 at fce4232a: list, scalar and missing-key shapes are all listed."""
    cfg = OmegaConf.create({"emit_all": True, "tech_comparison": block})
    decision = plan_emitters(cfg, {})["emit_tech_comparison"]
    assert decision.status == STATUS_NOT_RUN
    assert decision.reason is not None and decision.reason.startswith(reason)


@pytest.mark.parametrize(("block", "reason"), _MALFORMED_TECH_COMPARISON)
def test_the_plan_and_the_emitter_refuse_the_same_blocks(
    block: Any, reason: str
) -> None:
    """The plan mirrors the emitter's resolver, so what it lists the emitter would refuse."""
    from app.reports.tech_comparison_emit import resolve_tech_comparison_scenarios

    cfg = OmegaConf.create({"tech_comparison": block})
    node = cfg.tech_comparison
    with pytest.raises((ValueError, AttributeError, TypeError)):
        resolve_tech_comparison_scenarios(
            node.get("scenarios", None) if isinstance(node, Mapping) else node
        )


def test_a_well_formed_tech_comparison_block_runs_in_both() -> None:
    from app.reports.tech_comparison_emit import resolve_tech_comparison_scenarios

    block = {"scenarios": [{"label": "a", "config": _EXISTING_CONFIG}]}
    cfg = OmegaConf.create({"emit_all": True, "tech_comparison": block})
    assert plan_emitters(cfg, {})["emit_tech_comparison"].status == STATUS_RUN
    assert resolve_tech_comparison_scenarios(cfg.tech_comparison.scenarios) == [
        ("a", _EXISTING_CONFIG)
    ]


def test_disabled_grid_study_is_not_applicable() -> None:
    plan = plan_emitters({"emit_all": True}, {"grid": {"study_enabled": False}})
    assert plan["emit_grid_screen"].status == STATUS_NOT_RUN


@pytest.mark.parametrize("key", ["emit_all", "emit_grid_screen"])
def test_non_boolean_switch_is_refused(key: str) -> None:
    with pytest.raises(ValueError, match=key):
        plan_emitters({key: "yes"}, {})


def test_emit_all_without_a_scenario_is_refused() -> None:
    with pytest.raises(ValueError, match="effective scenario"):
        plan_emitters({"emit_all": True})


def test_plan_report_is_json_ready() -> None:
    report = plan_report(plan_emitters({"emit_all": True}, {}))
    assert json.loads(json.dumps(report)) == report
    assert report["emit_executive_workbook"] == {"status": "run", "source": "emit_all"}
    assert report["emit_grid_screen"]["status"] == "not_run"


# --------------------------------------------------------------------------------------------
# The CLI path, with the finance engine and every emitter replaced by recording stubs.
# --------------------------------------------------------------------------------------------

_STUB_RESULT: Dict[str, Any] = {"status": "success", "kpis": {"project_irr": 0.1}}


def _fake_engine(*, config: Any, validation_mode: Any, validation_modules: Any) -> Any:
    return copy.deepcopy(_STUB_RESULT)


def _install_recording_emitters(
    monkeypatch: pytest.MonkeyPatch, calls: List[str], fail: str | None = None
) -> None:
    def make(name: str) -> Any:
        def emitter(result: Any, *args: Any, **kwargs: Any) -> Path:
            calls.append(name)
            if name == fail:
                raise RuntimeError(f"{name} failed")
            out = Path(str(args[-1] if args else kwargs.get("output_html_path")))
            return out

        return emitter

    import app.reports.capital_risk_emit as cr
    import app.reports.grid_screening_emit as gs
    import app.reports.interaction_grid_emit as ig
    import app.reports.lender_report_emit as lr
    import app.reports.tech_comparison_emit as tc

    def lender(result: Any, *args: Any, **kwargs: Any) -> Any:
        out = make("emit_lender_report")(result, *args, **kwargs)
        return lr.LenderReportOutput(
            html_path=out, pdf_path=None, pdf_not_written="stub", sections_not_run=()
        )

    monkeypatch.setattr(rfp, "run_v14_pipeline", _fake_engine)
    monkeypatch.setattr(
        rfp, "emit_executive_workbook_from_pipeline", make("emit_executive_workbook")
    )
    monkeypatch.setattr(
        cr,
        "emit_capital_risk_report_from_pipeline",
        make("emit_capital_risk_report"),
    )
    monkeypatch.setattr(lr, "emit_lender_report_from_pipeline", lender)
    monkeypatch.setattr(
        ig, "emit_interaction_grid_report_from_pipeline", make("emit_interaction_grid")
    )
    monkeypatch.setattr(
        tc, "emit_tech_comparison_report_from_pipeline", make("emit_tech_comparison")
    )
    monkeypatch.setattr(
        gs, "emit_grid_screening_report_from_pipeline", make("emit_grid_screen")
    )


def _run_cli(tmp_path: Path, scenario: Dict[str, Any], **overrides: Any) -> None:
    """Run the CLI with stubs. It writes files unless ``write_artifacts=False`` is passed,
    because under emit_all a run that writes no files runs no emitter (#1760 L-1)."""
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(scenario), encoding="utf-8")
    base: Dict[str, Any] = {
        "config": str(path),
        "validation_mode": "off",
        "validation_modules": None,
        "export_dir": str(tmp_path / "run"),
        "write_artifacts": True,
        "wind_assessment_json": None,
        "wind_auto_orchestrate": False,
        "solar_assessment_json": None,
    }
    base.update(overrides)
    rfp.cli.__wrapped__(OmegaConf.create(base))


def test_cli_default_runs_what_applies_and_records_the_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With emit_all unset, the run behaves as emit_all=true (owner ruling 2026-11-16)."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(tmp_path, {"scenario_name": "t", "grid": {"study_enabled": True}})
    out = json.loads(capsys.readouterr().out)
    assert calls == [
        "emit_executive_workbook",
        "emit_lender_report",
        "emit_grid_screen",
    ]
    assert out["emitters"]["emit_capital_risk_report"]["status"] == STATUS_NOT_RUN
    assert out["kpis"] == _STUB_RESULT["kpis"]


def test_cli_emit_all_off_runs_no_emitter_and_records_no_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(tmp_path, {"scenario_name": "t", **_ALL_INPUTS_SCENARIO}, emit_all=False)
    out = json.loads(capsys.readouterr().out)
    assert calls == []
    assert "emitters" not in out
    assert out["kpis"] == _STUB_RESULT["kpis"]


def test_cli_emit_all_runs_what_applies_and_lists_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {"scenario_name": "t", "grid": {"study_enabled": True}},
        emit_all=True,
    )
    out = json.loads(capsys.readouterr().out)
    assert calls == [
        "emit_executive_workbook",
        "emit_lender_report",
        "emit_grid_screen",
    ]
    assert out["emitters"]["emit_capital_risk_report"]["status"] == "not_run"
    assert out["emitters"]["emit_interaction_grid"]["status"] == "not_run"
    assert out["emitters"]["emit_tech_comparison"]["status"] == "not_run"
    assert out["emitters"]["emit_grid_screen"] == {
        "status": "run",
        "source": "emit_all",
    }
    assert out["kpis"] == _STUB_RESULT["kpis"]


def test_cli_emit_all_with_every_input_runs_all_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {"scenario_name": "t", **_ALL_INPUTS_SCENARIO},
        emit_all=True,
        tech_comparison=_ALL_INPUTS_CFG["tech_comparison"],
    )
    capsys.readouterr()
    assert calls == list(EMIT_FLAGS)


def test_cli_explicit_false_wins_under_emit_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {"scenario_name": "t", **_ALL_INPUTS_SCENARIO},
        emit_all=True,
        emit_grid_screen=False,
        emit_executive_workbook=False,
    )
    out = json.loads(capsys.readouterr().out)
    assert "emit_grid_screen" not in calls
    assert "emit_executive_workbook" not in calls
    assert out["emitters"]["emit_grid_screen"] == {
        "status": "off",
        "source": "explicit",
    }


def test_cli_default_records_a_failed_emitter_and_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Under emit_all, a failing emitter is listed as failed; the figures are still written."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls, fail="emit_executive_workbook")
    _run_cli(
        tmp_path,
        {"scenario_name": "t", "grid": {"study_enabled": True}},
        write_artifacts=True,
    )
    out = json.loads(capsys.readouterr().out)
    # The failure does not stop the emitters after it.
    assert calls == [
        "emit_executive_workbook",
        "emit_lender_report",
        "emit_grid_screen",
    ]
    failed = out["emitters"]["emit_executive_workbook"]
    assert failed == {
        "status": STATUS_FAILED,
        "source": "emit_all",
        "reason": "RuntimeError: emit_executive_workbook failed",
    }
    assert out["emitters"]["emit_grid_screen"]["status"] == STATUS_RUN
    run_dir = tmp_path / "run"
    assert json.loads((run_dir / "kpis.json").read_text()) == _STUB_RESULT["kpis"]
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["emitters"]["emit_executive_workbook"]["status"] == STATUS_FAILED


@pytest.mark.parametrize(
    ("failing", "expected_calls"),
    [
        (
            "emit_grid_screen",
            ["emit_executive_workbook", "emit_lender_report", "emit_grid_screen"],
        ),
        # The workbook is the one emitter every default run that writes files reaches
        # (assurance F-2, M20): switched on explicitly, its failure still stops the run.
        ("emit_executive_workbook", ["emit_executive_workbook"]),
    ],
)
def test_cli_explicit_emitter_failure_stops_the_run_after_the_figures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failing: str,
    expected_calls: List[str],
) -> None:
    """An emitter switched on explicitly still stops the run; the figures are already on disk."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls, fail=failing)
    with pytest.raises(SystemExit) as excinfo:
        _run_cli(
            tmp_path,
            {"scenario_name": "t", "grid": {"study_enabled": True}},
            emit_all=True,
            write_artifacts=True,
            **{failing: True},
        )
    assert excinfo.value.code == 1
    assert calls == expected_calls
    assert f"{failing} failed" in capsys.readouterr().out
    run_dir = tmp_path / "run"
    assert json.loads((run_dir / "kpis.json").read_text()) == _STUB_RESULT["kpis"]
    assert not (run_dir / "summary.json").exists()


@pytest.mark.parametrize(
    "monte_carlo",
    [{"n_trials": 100}, {"parameters": []}, {"parameters": None}, {}],
)
def test_monte_carlo_block_without_parameters_is_not_run(monte_carlo: Any) -> None:
    """A monte_carlo block alone is not an input (assurance F-2, M05).

    A committed scenario carries a monte_carlo block with no parameters, so the
    check reads ``parameters``, not the block's presence.
    """
    plan = plan_emitters({"emit_all": True}, {"monte_carlo": monte_carlo})
    decision = plan["emit_capital_risk_report"]
    assert decision.status == STATUS_NOT_RUN
    assert decision.reason == (
        "the scenario declares no monte_carlo.parameters to sample"
    )


@pytest.mark.parametrize(
    ("parameters", "fragment"),
    [
        ({"capacity_factor_std": 0.05}, "must be a LIST"),
        ([{"low": 0.1, "high": 0.2}], "must be a mapping with a 'name' key"),
        ([{"name": "x", "low": 0.3, "high": 0.2}], "well-ordered"),
    ],
)
def test_unreadable_monte_carlo_parameters_are_listed_not_run(
    parameters: Any, fragment: str
) -> None:
    """The engine's own parser reads the parameters before the run (FRAMEWORK-02)."""
    plan = plan_emitters(
        {"emit_all": True}, {"monte_carlo": {"parameters": parameters}}
    )
    decision = plan["emit_capital_risk_report"]
    assert decision.status == STATUS_NOT_RUN
    assert decision.reason is not None
    assert decision.reason.startswith(
        "the Monte Carlo engine cannot read monte_carlo.parameters: "
    )
    assert fragment in decision.reason


@pytest.mark.parametrize(
    ("parameters", "error"),
    [
        ([{"name": "x", "low": None, "high": 0.2}], "TypeError"),
        ([{"name": "x", "low": "abc", "high": 0.2}], "ValueError"),
        ([{"name": "x", "low": 0.1, "high": [0.2]}], "TypeError"),
        (5, "TypeError"),
        ("x_std", "MonteCarloConfigError"),
    ],
)
def test_any_unreadable_monte_carlo_parameters_are_listed_not_run(
    parameters: Any, error: str
) -> None:
    """Domain review F-1: whatever the parser raises is listed, never raised."""
    plan = plan_emitters(
        {"emit_all": True}, {"monte_carlo": {"parameters": parameters}}
    )
    decision = plan["emit_capital_risk_report"]
    assert decision.status == STATUS_NOT_RUN
    assert decision.reason is not None
    assert decision.reason.startswith(
        f"the Monte Carlo engine cannot read monte_carlo.parameters: {error}: "
    )


def test_cli_default_with_a_null_monte_carlo_bound_writes_figures_and_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Domain review F-1 probe P1, end to end through the CLI (owner ruling 07:15Z)."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {
            "scenario_name": "t",
            "monte_carlo": {"parameters": [{"name": "x", "low": None, "high": 0.2}]},
        },
        write_artifacts=True,
    )
    out = json.loads(capsys.readouterr().out)
    assert calls == ["emit_executive_workbook", "emit_lender_report"]
    assert out["emitters"]["emit_capital_risk_report"]["status"] == STATUS_NOT_RUN
    run_dir = tmp_path / "run"
    assert json.loads((run_dir / "kpis.json").read_text()) == _STUB_RESULT["kpis"]
    assert (run_dir / "summary.json").exists()


def test_cli_default_with_a_malformed_tech_comparison_list_writes_figures_and_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Assurance review L-1 at 43a58859: the early plan must not stop the run (07:15Z ruling)."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {"scenario_name": "t"},
        write_artifacts=True,
        tech_comparison={"scenarios": 5},
    )
    out = json.loads(capsys.readouterr().out)
    assert calls == ["emit_executive_workbook", "emit_lender_report"]
    entry = out["emitters"]["emit_tech_comparison"]
    assert entry["status"] == STATUS_NOT_RUN
    assert entry["reason"].endswith("got int")
    run_dir = tmp_path / "run"
    assert json.loads((run_dir / "kpis.json").read_text()) == _STUB_RESULT["kpis"]
    assert (run_dir / "summary.json").exists()


@pytest.mark.parametrize(
    "block",
    [[1, 2], 5, {"scenarios": [{"label": "a"}]}],
    ids=["list", "scalar", "no-config"],
)
def test_cli_default_with_a_malformed_tech_comparison_block_writes_figures_and_completes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    block: Any,
) -> None:
    """#1760 domain D-1 at fce4232a: the run exits normally with its figures, as main does."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path, {"scenario_name": "t"}, write_artifacts=True, tech_comparison=block
    )
    out = json.loads(capsys.readouterr().out)
    assert calls == ["emit_executive_workbook", "emit_lender_report"]
    assert out["emitters"]["emit_tech_comparison"]["status"] == STATUS_NOT_RUN
    run_dir = tmp_path / "run"
    assert json.loads((run_dir / "kpis.json").read_text()) == _STUB_RESULT["kpis"]
    assert (run_dir / "summary.json").exists()


def test_cli_writes_the_figures_before_the_emitter_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whatever the plan does, the figures are already on disk (owner ruling 07:15Z)."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    real_plan = rfp.plan_emitters

    def plan_that_fails_on_the_scenario(
        cfg: Any, scenario: Any = None, **kwargs: Any
    ) -> Any:
        if scenario:
            raise RuntimeError("planning failed")
        return real_plan(cfg, scenario, **kwargs)

    monkeypatch.setattr(rfp, "plan_emitters", plan_that_fails_on_the_scenario)
    with pytest.raises(SystemExit):
        _run_cli(tmp_path, {"scenario_name": "t"}, write_artifacts=True)
    run_dir = tmp_path / "run"
    assert json.loads((run_dir / "kpis.json").read_text()) == _STUB_RESULT["kpis"]
    assert calls == []


_STALE_CAPITAL_RISK = ("capital_risk_report.html", "npv_distribution_equity_npv.png")


def _plant_stale_capital_risk(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in _STALE_CAPITAL_RISK:
        (run_dir / name).write_text("earlier run", encoding="utf-8")


def test_cli_default_removes_an_earlier_run_s_output_for_an_emitter_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Domain review F-2: a shared export dir must not keep another run's report."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    _plant_stale_capital_risk(run_dir)
    (run_dir / "unrelated.txt").write_text("kept", encoding="utf-8")
    _run_cli(tmp_path, {"scenario_name": "t"}, write_artifacts=True)
    out = json.loads(capsys.readouterr().out)
    for name in _STALE_CAPITAL_RISK:
        assert not (run_dir / name).exists(), name
    assert (run_dir / "unrelated.txt").exists()
    entry = out["emitters"]["emit_capital_risk_report"]
    assert entry["status"] == STATUS_NOT_RUN
    assert entry["removed_stale_outputs"] == list(_STALE_CAPITAL_RISK)
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["emitters"]["emit_capital_risk_report"] == entry


def test_cli_default_removes_an_earlier_run_s_output_for_an_emitter_that_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls, fail="emit_executive_workbook")
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "executive_workbook.xlsx").write_text("earlier run", encoding="utf-8")
    _run_cli(tmp_path, {"scenario_name": "t"}, write_artifacts=True)
    out = json.loads(capsys.readouterr().out)
    assert not (run_dir / "executive_workbook.xlsx").exists()
    entry = out["emitters"]["emit_executive_workbook"]
    assert entry["status"] == STATUS_FAILED
    assert entry["removed_stale_outputs"] == ["executive_workbook.xlsx"]


def test_cli_emit_all_off_keeps_every_earlier_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """emit_all=false clears no output of an emitter it does not attempt."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    _plant_stale_capital_risk(run_dir)
    _run_cli(tmp_path, {"scenario_name": "t"}, write_artifacts=True, emit_all=False)
    capsys.readouterr()
    for name in _STALE_CAPITAL_RISK:
        assert (run_dir / name).read_text(encoding="utf-8") == "earlier run", name


@pytest.mark.parametrize(
    "scenario",
    [
        {"scenario_name": "t"},
        {"scenario_name": "t", "monte_carlo": {"parameters": [{"name": "x"}]}},
    ],
    ids=["not-run", "run"],
)
def test_cli_default_clears_the_default_path_when_a_path_is_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    scenario: Dict[str, Any],
) -> None:
    """#1760 domain D-2 at fce4232a: under emit_all the default path is the run's own.

    With the report sent to a configured path, this run never writes the default path, so an
    earlier run's report and PNG there are cleared and listed, whether the emitter ran or not.
    The configured path itself is never touched.
    """
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    _plant_stale_capital_risk(run_dir)
    configured = tmp_path / "elsewhere" / "capital_risk_report.html"
    configured.parent.mkdir()
    configured.write_text("the caller's", encoding="utf-8")
    _run_cli(
        tmp_path,
        scenario,
        write_artifacts=True,
        capital_risk_report={"path": str(configured)},
    )
    out = json.loads(capsys.readouterr().out)
    for name in _STALE_CAPITAL_RISK:
        assert not (run_dir / name).exists(), name
    assert configured.read_text(encoding="utf-8") == "the caller's"
    entry = out["emitters"]["emit_capital_risk_report"]
    expected = STATUS_RUN if "monte_carlo" in scenario else STATUS_NOT_RUN
    assert entry["status"] == expected
    assert ("emit_capital_risk_report" in calls) is (expected == STATUS_RUN)
    assert entry["removed_stale_outputs"] == list(_STALE_CAPITAL_RISK)
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["emitters"]["emit_capital_risk_report"] == entry


def test_cli_default_clears_default_files_beside_a_configured_path_when_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#1760 domain D-1 at 7c595118: a configured path in the run's own directory.

    Only the configured file is the caller's. An earlier run's default report and PNG beside
    it are cleared and listed when the emitter does not run.
    """
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    _plant_stale_capital_risk(run_dir)
    configured = run_dir / "custom_cr.html"
    configured.write_text("the caller's", encoding="utf-8")
    _run_cli(
        tmp_path,
        {"scenario_name": "t"},
        write_artifacts=True,
        capital_risk_report={"path": str(configured)},
    )
    out = json.loads(capsys.readouterr().out)
    for name in _STALE_CAPITAL_RISK:
        assert not (run_dir / name).exists(), name
    assert configured.read_text(encoding="utf-8") == "the caller's"
    entry = out["emitters"]["emit_capital_risk_report"]
    assert entry["status"] == STATUS_NOT_RUN
    assert entry["removed_stale_outputs"] == list(_STALE_CAPITAL_RISK)


def test_cli_default_keeps_the_companion_file_a_configured_emitter_writes_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The emitter runs to a configured path in the run's directory and writes its PNG there,
    at the default PNG path. The earlier default report is cleared and listed; the PNG this
    run wrote is kept and is not listed as removed."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)

    def write_report(result: Any, *args: Any, **kwargs: Any) -> Path:
        calls.append("emit_capital_risk_report")
        out = Path(str(args[-1] if args else kwargs.get("output_html_path")))
        out.write_text("this run", encoding="utf-8")
        (out.parent / "npv_distribution_equity_npv.png").write_text(
            "this run", encoding="utf-8"
        )
        return out

    import app.reports.capital_risk_emit as cr

    monkeypatch.setattr(cr, "emit_capital_risk_report_from_pipeline", write_report)
    run_dir = tmp_path / "run"
    _plant_stale_capital_risk(run_dir)
    configured = run_dir / "custom_cr.html"
    _run_cli(
        tmp_path,
        {"scenario_name": "t", "monte_carlo": {"parameters": [{"name": "x"}]}},
        write_artifacts=True,
        capital_risk_report={"path": str(configured)},
    )
    out = json.loads(capsys.readouterr().out)
    assert "emit_capital_risk_report" in calls
    assert configured.read_text(encoding="utf-8") == "this run"
    assert not (run_dir / "capital_risk_report.html").exists()
    png = run_dir / "npv_distribution_equity_npv.png"
    assert png.read_text(encoding="utf-8") == "this run"
    entry = out["emitters"]["emit_capital_risk_report"]
    assert entry["status"] == STATUS_RUN
    assert entry["removed_stale_outputs"] == ["capital_risk_report.html"]


def test_cli_default_clears_the_default_workbook_beside_a_configured_workbook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#1760 domain D-1 at 7c595118: a workbook configured at <export>/custom_wb.xlsx."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "executive_workbook.xlsx").write_text("earlier run", encoding="utf-8")
    configured = run_dir / "custom_wb.xlsx"
    configured.write_text("the caller's", encoding="utf-8")
    _run_cli(
        tmp_path,
        {"scenario_name": "t"},
        write_artifacts=True,
        executive_workbook_path=str(configured),
    )
    out = json.loads(capsys.readouterr().out)
    assert "emit_executive_workbook" in calls
    assert not (run_dir / "executive_workbook.xlsx").exists()
    assert configured.read_text(encoding="utf-8") == "the caller's"
    entry = out["emitters"]["emit_executive_workbook"]
    assert entry["removed_stale_outputs"] == ["executive_workbook.xlsx"]


def test_cli_default_removes_an_earlier_run_s_output_for_an_emitter_switched_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Domain review D-1: emit_all on with emit_capital_risk_report=false (the fast run)."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    _plant_stale_capital_risk(run_dir)
    _run_cli(
        tmp_path,
        {"scenario_name": "t", "monte_carlo": {"parameters": [{"name": "x"}]}},
        write_artifacts=True,
        emit_capital_risk_report=False,
    )
    out = json.loads(capsys.readouterr().out)
    assert "emit_capital_risk_report" not in calls
    for name in _STALE_CAPITAL_RISK:
        assert not (run_dir / name).exists(), name
    entry = out["emitters"]["emit_capital_risk_report"]
    assert entry["status"] == "off"
    assert entry["source"] == "explicit"
    assert entry["removed_stale_outputs"] == list(_STALE_CAPITAL_RISK)
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["emitters"]["emit_capital_risk_report"] == entry


# --------------------------------------------------------------------------------------------
# #1760 assurance M-1 and L-1: one rule for which default-path files a run owns.
# --------------------------------------------------------------------------------------------


def _plant(run_dir: Path, *names: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (run_dir / name).write_text("earlier run", encoding="utf-8")


def test_cli_by_name_failure_under_emit_all_leaves_no_earlier_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """M-1: an emitter switched on by name that fails stops the run (exit 1), and nothing an
    earlier run wrote is left beside this run's figures: not summary.json, not the failed
    emitter's report, not a not-run emitter's report, and not the report of an emitter that
    would have run after the failure."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls, fail="emit_capital_risk_report")
    run_dir = tmp_path / "run"
    _plant(
        run_dir,
        "summary.json",
        *_STALE_CAPITAL_RISK,
        "tech_comparison_report.html",
        "grid_screening_report.html",
        "unrelated.txt",
    )
    with pytest.raises(SystemExit) as excinfo:
        _run_cli(
            tmp_path,
            {
                "scenario_name": "t",
                "monte_carlo": {"parameters": [{"name": "x"}]},
                "grid": {"study_enabled": True},
            },
            emit_capital_risk_report=True,
        )
    capsys.readouterr()
    assert excinfo.value.code == 1
    assert calls == ["emit_executive_workbook", "emit_capital_risk_report"]
    assert json.loads((run_dir / "kpis.json").read_text()) == _STUB_RESULT["kpis"]
    for name in (
        "summary.json",
        *_STALE_CAPITAL_RISK,
        "tech_comparison_report.html",
        "grid_screening_report.html",
    ):
        assert not (run_dir / name).exists(), name
    assert (run_dir / "unrelated.txt").exists()


def test_cli_by_name_failure_with_emit_all_off_clears_only_its_own_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """M-1 with emit_all=false: the attempted emitter clears its own default outputs first,
    summary.json is removed when the figures are written, and nothing else is touched.
    """
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls, fail="emit_capital_risk_report")
    run_dir = tmp_path / "run"
    _plant(run_dir, "summary.json", *_STALE_CAPITAL_RISK, "tech_comparison_report.html")
    with pytest.raises(SystemExit):
        _run_cli(
            tmp_path,
            {"scenario_name": "t"},
            emit_all=False,
            emit_capital_risk_report=True,
        )
    capsys.readouterr()
    assert calls == ["emit_capital_risk_report"]
    for name in ("summary.json", *_STALE_CAPITAL_RISK):
        assert not (run_dir / name).exists(), name
    assert (run_dir / "tech_comparison_report.html").read_text(
        encoding="utf-8"
    ) == "earlier run"


def test_cli_default_clears_what_a_failed_emitter_wrote_before_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)

    def half_written_workbook(result: Any, out: Path, **kwargs: Any) -> Path:
        Path(out).write_text("half written", encoding="utf-8")
        raise RuntimeError("workbook failed")

    monkeypatch.setattr(
        rfp, "emit_executive_workbook_from_pipeline", half_written_workbook
    )
    _run_cli(tmp_path, {"scenario_name": "t"})
    out = json.loads(capsys.readouterr().out)
    assert not (tmp_path / "run" / "executive_workbook.xlsx").exists()
    entry = out["emitters"]["emit_executive_workbook"]
    assert entry["status"] == STATUS_FAILED
    assert entry["removed_stale_outputs"] == ["executive_workbook.xlsx"]


def test_cli_default_without_write_artifacts_writes_no_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """L-1: with write_artifacts=false a default run writes nothing into export_dir, as on
    main, and lists every emitter as not run with the reason."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    _plant(run_dir, *_STALE_CAPITAL_RISK)
    _run_cli(
        tmp_path,
        {"scenario_name": "t", "grid": {"study_enabled": True}},
        write_artifacts=False,
    )
    out = json.loads(capsys.readouterr().out)
    assert calls == []
    assert {entry["status"] for entry in out["emitters"].values()} == {STATUS_NOT_RUN}
    assert {entry["reason"] for entry in out["emitters"].values()} == {
        WRITE_ARTIFACTS_OFF_REASON
    }
    assert sorted(path.name for path in run_dir.iterdir()) == sorted(
        _STALE_CAPITAL_RISK
    )


def test_cli_without_write_artifacts_still_runs_a_switch_set_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {"scenario_name": "t"},
        write_artifacts=False,
        emit_executive_workbook=True,
    )
    out = json.loads(capsys.readouterr().out)
    assert calls == ["emit_executive_workbook"]
    assert out["emitters"]["emit_executive_workbook"]["status"] == STATUS_RUN


# --------------------------------------------------------------------------------------------
# #1760 domain D-2 at 7c595118: an applicability check that raises is listed, not raised.
# --------------------------------------------------------------------------------------------


def test_plan_lists_an_unresolvable_interpolation_with_its_reason() -> None:
    cfg = OmegaConf.create({"tech_comparison": {"scenarios": "${no_such_key}"}})
    plan = plan_emitters(cfg, {"scenario_name": "t"})
    decision = plan["emit_tech_comparison"]
    assert decision.run is False
    assert decision.status == STATUS_NOT_RUN
    assert decision.source == "emit_all"
    assert decision.reason is not None
    assert decision.reason.startswith(
        "the run config's inputs for emit_tech_comparison cannot be read: "
    )
    assert "no_such_key" in decision.reason
    assert plan["emit_executive_workbook"].run is True


def test_plan_lists_any_applicability_error_with_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analytics.emit_selection as es

    def boom(scenario: Mapping[str, Any], cfg: Any) -> None:
        raise KeyError("missing input")

    monkeypatch.setitem(es.APPLICABILITY, "emit_interaction_grid", boom)
    decision = plan_emitters({}, {"scenario_name": "t"})["emit_interaction_grid"]
    assert decision.status == STATUS_NOT_RUN
    assert decision.reason == (
        "the run config's inputs for emit_interaction_grid cannot be read: "
        "KeyError: 'missing input'"
    )


def test_cli_default_with_an_unresolvable_tech_comparison_writes_its_figures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """On 7c595118 the early plan raised and the run exited before its figures."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {"scenario_name": "t"},
        tech_comparison={"scenarios": "${no_such_key}"},
    )
    out = json.loads(capsys.readouterr().out)
    assert "emit_tech_comparison" not in calls
    entry = out["emitters"]["emit_tech_comparison"]
    assert entry["status"] == STATUS_NOT_RUN
    assert "no_such_key" in entry["reason"]
    assert out["kpis"] == _STUB_RESULT["kpis"]
    assert (tmp_path / "run" / "summary.json").is_file()


def test_removed_stale_outputs_are_listed_relative_to_the_export_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#1760 assurance L-1 at 7c595118: the grid screen's two reports share a file name."""
    from analytics.contracts_v14 import QSTS_SYNTHETIC_OUTPUT_CLASS

    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    nested = run_dir / QSTS_SYNTHETIC_OUTPUT_CLASS
    nested.mkdir(parents=True)
    (run_dir / "grid_screening_report.html").write_text("earlier run", encoding="utf-8")
    (nested / "grid_screening_report.html").write_text("earlier run", encoding="utf-8")
    _run_cli(tmp_path, {"scenario_name": "t"}, write_artifacts=True)
    out = json.loads(capsys.readouterr().out)
    entry = out["emitters"]["emit_grid_screen"]
    assert entry["status"] == STATUS_NOT_RUN
    assert entry["removed_stale_outputs"] == [
        "grid_screening_report.html",
        f"{QSTS_SYNTHETIC_OUTPUT_CLASS}/grid_screening_report.html",
    ]
    assert not (nested / "grid_screening_report.html").exists()


# --------------------------------------------------------------------------------------------
# #1760 assurance M-2 at cf357629: a config read between the figures and summary.json that is
# not inside an emitter never stops the run.
# --------------------------------------------------------------------------------------------

_UNSET_ENV = "DUTCHBAY_TEST_1760_UNSET_VARIABLE"
_UNRESOLVABLE = "${oc.env:" + _UNSET_ENV + "}"

_UNREADABLE_KEYS = [
    ("capital_risk_report", "path"),
    ("capital_risk_report", "npv_metric"),
    ("tech_comparison", "path"),
    ("interaction_grid_report", "path"),
    ("grid_screen_report", "path"),
    ("lender_report", "path"),
]
#: Keys the lender report (#1752) reads itself, inside its emitter: under emit_all it is
#: recorded as failed and the run goes on.
_READ_BY_THE_LENDER_REPORT = {
    ("capital_risk_report", "npv_metric"),
    ("lender_report", "path"),
}
_MODES = {
    "default": {},
    "emit_all_off": {"emit_all": False},
    "no_write_artifacts": {"write_artifacts": False},
}


@pytest.mark.parametrize("mode", sorted(_MODES))
@pytest.mark.parametrize(
    "block,key", _UNREADABLE_KEYS, ids=[f"{b}.{k}" for b, k in _UNREADABLE_KEYS]
)
def test_an_unresolvable_emitter_key_never_stops_a_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    block: str,
    key: str,
    mode: str,
) -> None:
    monkeypatch.delenv(_UNSET_ENV, raising=False)
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(
        tmp_path,
        {"scenario_name": "t"},
        **{block: {key: _UNRESOLVABLE}},
        **_MODES[mode],
    )
    out = json.loads(capsys.readouterr().out)
    assert out["kpis"] == _STUB_RESULT["kpis"]
    run_dir = tmp_path / "run"
    if mode == "no_write_artifacts":
        assert not (run_dir / "summary.json").exists()
        assert calls == []
    else:
        assert (run_dir / "kpis.json").is_file()
        assert (run_dir / "summary.json").is_file()
    if mode == "default":
        lender_fails = (block, key) in _READ_BY_THE_LENDER_REPORT
        assert calls == ["emit_executive_workbook"] + (
            [] if lender_fails else ["emit_lender_report"]
        )
        assert out["emitters"]["emit_executive_workbook"]["status"] == STATUS_RUN
        assert out["emitters"]["emit_lender_report"]["status"] == (
            STATUS_FAILED if lender_fails else STATUS_RUN
        )
    if mode == "emit_all_off":
        assert calls == []


def test_an_explicit_emitter_with_an_unresolvable_path_stops_and_keeps_its_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outside emit_all, an emitter switched on by name whose path cannot be read fails as it
    did before #1756, and its default-path file is left alone: the path was configured.
    """
    monkeypatch.delenv(_UNSET_ENV, raising=False)
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    earlier = run_dir / "interaction_grid_report.html"
    earlier.write_text("earlier run", encoding="utf-8")
    with pytest.raises(SystemExit) as stopped:
        _run_cli(
            tmp_path,
            {"scenario_name": "t", "interaction_grid": {}},
            emit_all=False,
            emit_interaction_grid=True,
            interaction_grid_report={"path": _UNRESOLVABLE},
        )
    capsys.readouterr()
    assert stopped.value.code == 1
    assert calls == []
    assert earlier.read_text(encoding="utf-8") == "earlier run"
    assert (run_dir / "kpis.json").is_file()


def test_a_scenario_that_cannot_be_read_again_lists_every_default_emitter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The re-plan reads the effective scenario again after the figures; if that read
    fails, each emitter emit_all would switch on is listed as not run and the run goes on.
    A switch set by name keeps its own decision."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)

    def unreadable(path: Any) -> Any:
        raise OSError("scenario gone")

    monkeypatch.setattr(rfp, "load_scenario_config", unreadable)
    _run_cli(tmp_path, {"scenario_name": "t"}, emit_grid_screen=False)
    out = json.loads(capsys.readouterr().out)
    assert calls == []
    assert out["kpis"] == _STUB_RESULT["kpis"]
    for flag in EMIT_FLAGS:
        entry = out["emitters"][flag]
        if flag == "emit_grid_screen":
            assert entry == {"status": STATUS_OFF, "source": "explicit"}
            continue
        assert entry["status"] == STATUS_NOT_RUN
        assert entry["reason"] == (
            "the effective scenario cannot be read again to plan the emitters: "
            "OSError: scenario gone"
        )
    assert (tmp_path / "run" / "summary.json").is_file()
