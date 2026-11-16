"""Tests for the emit_all switch and per-emitter planning (#1756)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml
from omegaconf import OmegaConf

import run_full_pipeline_v14 as rfp
from analytics.emit_selection import (
    EMIT_FLAGS,
    STATUS_NOT_RUN,
    STATUS_OFF,
    STATUS_RUN,
    plan_emitters,
    plan_report,
)

_ALL_INPUTS_SCENARIO: Dict[str, Any] = {
    "monte_carlo": {"parameters": [{"name": "x"}]},
    "interaction_grid": {"metric": "project_irr"},
    "grid": {"study_enabled": True},
}
_ALL_INPUTS_CFG: Dict[str, Any] = {
    "emit_all": True,
    "tech_comparison": {"scenarios": [{"label": "a", "config": "a.yaml"}]},
}


def _runs(plan: Dict[str, Any]) -> Dict[str, bool]:
    return {flag: decision.run for flag, decision in plan.items()}


def test_default_runs_nothing_and_needs_no_scenario() -> None:
    plan = plan_emitters(OmegaConf.create({}))
    assert list(plan) == list(EMIT_FLAGS)
    assert not any(_runs(plan).values())
    assert {d.status for d in plan.values()} == {STATUS_OFF}


def test_single_switch_behaves_as_before() -> None:
    plan = plan_emitters({"emit_grid_screen": True})
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


def test_cli_default_runs_no_emitter_and_records_no_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls)
    _run_cli(tmp_path, {"scenario_name": "t", **_ALL_INPUTS_SCENARIO})
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


def test_cli_emit_all_stops_when_an_applicable_emitter_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: List[str] = []
    _install_recording_emitters(monkeypatch, calls, fail="emit_grid_screen")
    with pytest.raises(SystemExit) as excinfo:
        _run_cli(
            tmp_path,
            {"scenario_name": "t", "grid": {"study_enabled": True}},
            emit_all=True,
        )
    assert excinfo.value.code == 1
    assert calls == ["emit_executive_workbook", "emit_grid_screen"]
    assert "emit_grid_screen failed" in capsys.readouterr().out
