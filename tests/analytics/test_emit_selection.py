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
    assert set(not_run) == set(EMIT_FLAGS) - {"emit_executive_workbook"}
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
    import app.reports.tech_comparison_emit as tc

    monkeypatch.setattr(rfp, "run_v14_pipeline", _fake_engine)
    monkeypatch.setattr(
        rfp, "emit_executive_workbook_from_pipeline", make("emit_executive_workbook")
    )
    monkeypatch.setattr(
        cr,
        "emit_capital_risk_report_from_pipeline",
        make("emit_capital_risk_report"),
    )
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
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(scenario), encoding="utf-8")
    base: Dict[str, Any] = {
        "config": str(path),
        "validation_mode": "off",
        "validation_modules": None,
        "export_dir": str(tmp_path / "run"),
        "write_artifacts": False,
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
    assert calls == ["emit_executive_workbook", "emit_grid_screen"]
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
    assert calls == ["emit_executive_workbook", "emit_grid_screen"]
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
    assert calls == ["emit_executive_workbook", "emit_grid_screen"]
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
        ("emit_grid_screen", ["emit_executive_workbook", "emit_grid_screen"]),
        # The workbook is the one emitter every default run reaches (assurance
        # F-2, M20): switched on explicitly, its failure still stops the run.
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
    assert calls == ["emit_executive_workbook"]
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
    assert calls == ["emit_executive_workbook"]
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
    assert calls == ["emit_executive_workbook"]
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

    def plan_that_fails_on_the_scenario(cfg: Any, scenario: Any = None) -> Any:
        if scenario:
            raise RuntimeError("planning failed")
        return real_plan(cfg, scenario)

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
    """emit_all=false clears nothing."""
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


def test_cli_default_keeps_files_beside_a_configured_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A configured path in the run's own directory: its companion PNG there is kept."""
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    run_dir = tmp_path / "run"
    _plant_stale_capital_risk(run_dir)
    _run_cli(
        tmp_path,
        {"scenario_name": "t"},
        write_artifacts=True,
        capital_risk_report={"path": str(run_dir / "my_report.html")},
    )
    out = json.loads(capsys.readouterr().out)
    for name in _STALE_CAPITAL_RISK:
        assert (run_dir / name).read_text(encoding="utf-8") == "earlier run", name
    assert "removed_stale_outputs" not in out["emitters"]["emit_capital_risk_report"]


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
