"""End-to-end: the #884 (D8) opt-in caller wires the advisory grid-screening report into the CLI.

The CARDINAL RULE these tests pin: the grid study is ADVISORY (bankable=false) and NEVER feeds
finance. So:

  * ``emit_grid_screen:false`` (the default) is a pure no-op — no ``grid_screening_report_path`` in
    the CLI JSON output, and the committed finance KPIs pass through BYTE-IDENTICAL;
  * ``emit_grid_screen:true`` on a grid-enabled scenario writes ONLY an additional advisory HTML
    artifact and echoes its path — the SAME finance KPIs still pass through UNCHANGED (the grid
    report never mutates the finance result);
  * the rendered report carries the un-suppressible SCREENING-not-bankable + EMT-gap caveat.

The finance engine is stubbed (a fixed result dict) so the test is fast and the byte-identity of
the finance KPIs is asserted directly — the grid emitter runs for real against a grid-enabled
scenario (closed-form screens; no [grid] extra needed).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import yaml
from omegaconf import OmegaConf

import run_full_pipeline_v14 as rfp
from tests._canon import LENDER_EQUITY_IRR, LENDER_MIN_DSCR, LENDER_PROJECT_IRR

REPO_ROOT = Path(__file__).resolve().parents[2]

# The committed finance KPIs the stub returns — the byte-identity yardstick. If the grid report
# ever mutated the finance result, one of these would change.
_STUB_KPIS: Dict[str, Any] = {
    "scenario_name": "grid_test",
    "project_irr": LENDER_PROJECT_IRR,
    "equity_irr": LENDER_EQUITY_IRR,
    "min_dscr": LENDER_MIN_DSCR,
}
_STUB_RESULT: Dict[str, Any] = {"status": "success", "kpis": dict(_STUB_KPIS)}


def _grid_enabled_scenario(tmp_path: Path) -> Path:
    """A minimal grid-enabled scenario the closed-form screens can consume (no [grid] extra)."""
    cfg = {
        "scenario_name": "grid_test",
        "grid": {
            "study_enabled": True,
            "allow_unvalidated_grid": True,
            "poc_voltage_kv": 33.0,
            "source_fault_level_mva": 900.0,
            "source_rx": 0.083,
            "connection_r_ohm": 0.6,
            "connection_x_ohm": 6.0,
            "plant_rating_mva": 159.6,
            "poc": {
                "bus_name": "Test POC",
                "nominal_kv": 33.0,
                "plant_rated_mva": 159.6,
            },
            "thevenin": {
                "short_circuit_mva_min": 700.0,
                "short_circuit_mva_max": 1100.0,
                "x_r": 12.0,
                "assumption_basis": "screening_estimate",
            },
            "scr": {"gfl_min": 3.0, "gfl_comfortable": 5.0},
            "gridcode": {"pf_range": [-0.95, 0.95], "rc_k_factor": 2.0},
        },
    }
    path = tmp_path / "grid_scenario.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _run_cli(overrides: Dict[str, Any]) -> None:
    """Drive the undecorated Hydra cli() with a plain OmegaConf config (mirrors the sibling harness)."""
    base = {
        "config": overrides.pop("config", ""),
        "validation_mode": "off",
        "validation_modules": None,
        "export_dir": overrides.pop("export_dir", "_out/test"),
        "write_artifacts": False,
        "wind_assessment_json": None,
        "wind_auto_orchestrate": False,
        "adapter_mode": "fill_if_absent",
        "wind_tolerance_pct": 0.5,
        "wind_export_scenario": "P75",
        "solar_assessment_json": None,
        "solar_adapter_mode": "fill_if_absent",
        "solar_tolerance_pct": 0.5,
        "solar_export_scenario": "P50",
        "solar_technology": "solar",
        "emit_grid_screen": False,
        "grid_screen_report": None,
    }
    base.update(overrides)
    rfp.cli.__wrapped__(OmegaConf.create(base))


def _fake_engine(*, config, validation_mode, validation_modules):
    return copy.deepcopy(_STUB_RESULT)


def test_default_off_is_noop_and_kpis_byte_identical(
    tmp_path, monkeypatch, capsys
) -> None:
    """emit_grid_screen:false → no grid path echoed AND the finance KPIs are byte-identical."""
    monkeypatch.setattr(rfp, "run_v14_pipeline", _fake_engine)
    scenario = _grid_enabled_scenario(tmp_path)
    _run_cli({"config": str(scenario), "export_dir": str(tmp_path / "run")})
    out = json.loads(capsys.readouterr().out)
    # No grid report emitted when the flag is off.
    assert "grid_screening_report_path" not in out
    # The finance KPIs pass through unchanged — the cardinal byte-identity guarantee.
    assert out["kpis"] == _STUB_KPIS


def test_emit_on_writes_report_and_leaves_finance_unchanged(
    tmp_path, monkeypatch, capsys
) -> None:
    """emit_grid_screen:true → an advisory report is written; the finance KPIs are STILL unchanged."""
    monkeypatch.setattr(rfp, "run_v14_pipeline", _fake_engine)
    scenario = _grid_enabled_scenario(tmp_path)
    gs_path = tmp_path / "grid_screening_report.html"
    _run_cli(
        {
            "config": str(scenario),
            "export_dir": str(tmp_path / "run"),
            "emit_grid_screen": True,
            "grid_screen_report": {"path": str(gs_path)},
        }
    )
    out = json.loads(capsys.readouterr().out)
    # The advisory report was written and its path echoed.
    assert out["grid_screening_report_path"] == str(gs_path)
    assert gs_path.exists()
    # The grid report NEVER touches finance: the same KPIs pass through byte-identical.
    assert out["kpis"] == _STUB_KPIS
    # The rendered report carries the un-suppressible caveat.
    html = gs_path.read_text(encoding="utf-8")
    assert "SCREENING / DESIGN-STAGE ONLY" in html
    assert "EMT GAP" in html


def test_emit_on_defaults_path_under_export_dir(tmp_path, monkeypatch, capsys) -> None:
    """With no explicit path, the report defaults to <export_dir>/grid_screening_report.html."""
    monkeypatch.setattr(rfp, "run_v14_pipeline", _fake_engine)
    scenario = _grid_enabled_scenario(tmp_path)
    export_dir = tmp_path / "run"
    _run_cli(
        {
            "config": str(scenario),
            "export_dir": str(export_dir),
            "emit_grid_screen": True,
        }
    )
    out = json.loads(capsys.readouterr().out)
    expected = export_dir / "grid_screening_report.html"
    assert out["grid_screening_report_path"] == str(expected)
    assert expected.exists()
