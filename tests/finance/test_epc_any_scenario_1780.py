"""Any scenario can run the EPC construction margin from its ``epc`` block (#1780).

The owner ruled on 2026-11-16 that all code must be available to any scenario. The margin
model used to be reachable only from a standalone script that read one site's scenario.
These tests pin the scenario contract: pre-flight, the pipeline's ``epc_margin`` entry
beside the scenario's own figures, and an EPC-only scenario through the main CLI.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml
from omegaconf import OmegaConf

import run_full_pipeline_v14 as rfp
from finance.epc_margin import (
    STATUS_FAILED,
    STATUS_RUN,
    compute_epc_margin,
    epc_margin_result,
    epc_only_result,
    is_epc_only_scenario,
    validate_epc_block,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EPC_ONLY_SCENARIO = REPO_ROOT / "scenarios" / "kolonnawa_epc_100mw.yaml"
OPERATING_SCENARIO = REPO_ROOT / "scenarios" / "ceb_bess_10mw_capacity_charge.yaml"
MODULE = REPO_ROOT / "finance" / "epc_margin.py"


def _block(**overrides: Any) -> Dict[str, Any]:
    block: Dict[str, Any] = {
        "description": "generic EPC supply contract",
        "contract_value_usd": 1_000_000,
        "cost": {"equipment_usd": 700_000, "install_usd": 150_000},
        "construction_months": 12,
        "payment_schedule": [{"month": 0, "pct": 0.2}, {"month": 12, "pct": 0.8}],
    }
    block.update(overrides)
    return block


def _errors(config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    validate_epc_block(config, errors)
    return errors


# ── the module names no site or utility ────────────────────────────────────────


def test_module_names_no_site_or_utility() -> None:
    text = MODULE.read_text(encoding="utf-8")
    for pattern in (r"kolonnawa", r"\bCEB\b", r"sri lanka", r"tender"):
        assert not re.search(pattern, text, flags=re.IGNORECASE), pattern


def test_the_standalone_script_is_retired() -> None:
    assert not (REPO_ROOT / "scripts" / "run_epc_margin.py").exists()


# ── pre-flight contract ────────────────────────────────────────────────────────


def test_preflight_is_present_only() -> None:
    assert _errors({"project": {}}) == []


def test_preflight_accepts_a_good_block() -> None:
    assert _errors({"epc": _block()}) == []


@pytest.mark.parametrize(
    ("block", "message"),
    [
        ("not a mapping", "epc must be a mapping"),
        (_block(margin_pct=0.1), "unknown key"),
        (_block(contract_value_usd=0), "contract_value_usd"),
        (_block(cost={}), "epc.cost"),
        (_block(construction_months=0), "construction_months"),
        (_block(payment_schedule=[{"month": 0, "pct": 0.5}]), "sum to"),
    ],
)
def test_preflight_refuses_a_bad_block(block: Any, message: str) -> None:
    errors = _errors({"epc": block})
    assert errors and message in errors[0]


def test_schema_guard_runs_the_epc_check() -> None:
    from analytics import schema_guard

    errors: List[str] = []
    schema_guard._validate_epc_block({"epc": _block(margin_pct=0.1)}, errors)
    assert errors and "unknown key" in errors[0]
    errors = []
    schema_guard._validate_epc_block({"project": {}}, errors)
    assert errors == []


# ── EPC-only detection and result entries ──────────────────────────────────────


def test_epc_only_detection() -> None:
    assert is_epc_only_scenario({"epc": _block()})
    assert is_epc_only_scenario({"epc": _block(), "metadata": {"version": "1"}})
    assert not is_epc_only_scenario({"epc": _block(), "project": {}})
    assert not is_epc_only_scenario({"project": {}})
    assert not is_epc_only_scenario(None)
    raw = yaml.safe_load(EPC_ONLY_SCENARIO.read_text(encoding="utf-8"))
    assert is_epc_only_scenario(raw)
    operating = yaml.safe_load(OPERATING_SCENARIO.read_text(encoding="utf-8"))
    assert not is_epc_only_scenario(operating)


def test_result_entry_carries_every_margin_figure() -> None:
    config = {"epc": _block()}
    entry = epc_margin_result(config)
    assert entry is not None and entry["status"] == STATUS_RUN
    direct = compute_epc_margin(config)
    assert entry["gross_margin"] == pytest.approx(direct.gross_margin)
    assert entry["total_cost"] == pytest.approx(850_000)
    assert entry["gross_margin"] == pytest.approx(150_000)
    assert entry["peak_working_capital"] == pytest.approx(direct.peak_working_capital)
    assert entry["monthly_net_cashflow"] == direct.monthly_net_cashflow
    assert epc_margin_result({"project": {}}) is None


def test_epc_only_result_success_and_failure() -> None:
    ok = epc_only_result({"epc": _block()}, "x.yaml")
    assert ok["status"] == "success"
    assert ok["scenario_kind"] == "epc_only"
    assert ok["config_path"] == "x.yaml"
    assert ok["epc_margin"]["status"] == STATUS_RUN
    bad = epc_only_result({"epc": _block(construction_months=0)}, "x.yaml")
    assert bad["status"] == "error"
    assert "construction_months" in bad["error"]
    assert bad["epc_margin"]["status"] == STATUS_FAILED


# ── the pipeline, for an operating scenario that declares the block ────────────


def _operating_with_block(tmp_path: Path, block: Any) -> Path:
    raw = copy.deepcopy(yaml.safe_load(OPERATING_SCENARIO.read_text(encoding="utf-8")))
    if block is not None:
        raw["epc"] = block
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_pipeline_adds_nothing_without_the_block(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    result = run_v14_pipeline_enhanced(str(_operating_with_block(tmp_path, None)))
    assert result["status"] == "success"
    assert "epc_margin" not in result


def test_pipeline_reports_the_margin_beside_unchanged_figures(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    base = run_v14_pipeline_enhanced(str(_operating_with_block(tmp_path, None)))
    result = run_v14_pipeline_enhanced(str(_operating_with_block(tmp_path, _block())))
    assert result["status"] == "success"
    entry = result["epc_margin"]
    assert entry["status"] == STATUS_RUN
    assert entry["gross_margin"] == pytest.approx(150_000)
    for key in ("kpis", "annual_rows", "debt_result", "equity_distribution"):
        assert result[key] == base[key], key


def test_pipeline_preflight_refuses_a_bad_block(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    path = _operating_with_block(tmp_path, _block(margin_pct=0.1))
    with pytest.raises(Exception, match="epc has unknown key"):
        run_v14_pipeline_enhanced(str(path))


def test_pipeline_with_validation_off_lists_a_bad_block_and_keeps_the_figures(
    tmp_path: Path,
) -> None:
    """Write the figures, list the failure (owner ruling 2026-11-16)."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    base = run_v14_pipeline_enhanced(
        str(_operating_with_block(tmp_path, None)), validation_mode="off"
    )
    result = run_v14_pipeline_enhanced(
        str(_operating_with_block(tmp_path, _block(construction_months=0))),
        validation_mode="off",
    )
    assert result["status"] == "success"
    assert result["epc_margin"]["status"] == STATUS_FAILED
    assert "construction_months" in result["epc_margin"]["reason"]
    assert result["kpis"] == base["kpis"]


# ── an EPC-only scenario through the main CLI ──────────────────────────────────


def _run_cli(config: Path, tmp_path: Path, write_artifacts: bool = False) -> None:
    rfp.cli.__wrapped__(
        OmegaConf.create(
            {
                "config": str(config),
                "validation_mode": "strict",
                "validation_modules": None,
                "export_dir": str(tmp_path / "out"),
                "write_artifacts": write_artifacts,
            }
        )
    )


def test_main_cli_runs_the_committed_epc_only_scenario(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_cli(EPC_ONLY_SCENARIO, tmp_path, write_artifacts=True)
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "success"
    assert out["scenario_kind"] == "epc_only"
    raw = yaml.safe_load(EPC_ONLY_SCENARIO.read_text(encoding="utf-8"))
    direct = compute_epc_margin(raw)
    assert out["epc_margin"]["gross_margin"] == pytest.approx(direct.gross_margin)
    assert out["epc_margin"]["peak_working_capital"] == pytest.approx(
        direct.peak_working_capital
    )
    written = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert written == out


def test_main_cli_exits_1_on_a_bad_epc_only_scenario(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "epc_only.yaml"
    path.write_text(yaml.safe_dump({"epc": _block(construction_months=0)}))
    with pytest.raises(SystemExit) as info:
        _run_cli(path, tmp_path)
    assert info.value.code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error"
    assert "construction_months" in out["error"]


# ── #1782 review follow-ups: the EPC-only route keeps #1760's run rules ─────────


def _run_cli_with(config: Path, tmp_path: Path, **extra: Any) -> None:
    cfg = {
        "config": str(config),
        "validation_mode": "strict",
        "validation_modules": None,
        "export_dir": str(tmp_path / "out"),
        "write_artifacts": True,
    }
    cfg.update(extra)
    rfp.cli.__wrapped__(OmegaConf.create(cfg))


def test_epc_only_run_lists_every_emitter_as_not_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from analytics.emit_selection import EMIT_FLAGS

    _run_cli_with(EPC_ONLY_SCENARIO, tmp_path)
    out = json.loads(capsys.readouterr().out)
    assert set(out["emitters"]) == set(EMIT_FLAGS)
    for entry in out["emitters"].values():
        assert entry["status"] == "not_run"
        assert entry["reason"] == rfp.EPC_ONLY_EMITTER_REASON


def test_epc_only_run_keeps_a_switch_turned_off_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_cli_with(EPC_ONLY_SCENARIO, tmp_path, emit_grid_screen=False)
    out = json.loads(capsys.readouterr().out)
    assert out["emitters"]["emit_grid_screen"]["status"] == "off"


def test_epc_only_run_with_emit_all_off_lists_no_emitters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_cli_with(EPC_ONLY_SCENARIO, tmp_path, emit_all=False)
    out = json.loads(capsys.readouterr().out)
    assert "emitters" not in out


def test_epc_only_run_refuses_a_bad_switch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="emit_all must be true, false or null"):
        _run_cli_with(EPC_ONLY_SCENARIO, tmp_path, emit_all="banana")
    assert not (tmp_path / "out" / "summary.json").exists()


def test_epc_only_summary_carries_a_run_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_cli_with(EPC_ONLY_SCENARIO, tmp_path)
    out = json.loads(capsys.readouterr().out)
    assert out["run_manifest"]["config_sha256"]
    assert json.loads((tmp_path / "out" / "summary.json").read_text()) == out


def test_epc_only_summary_follows_run_scoping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_cli_with(EPC_ONLY_SCENARIO, tmp_path, run_scoped=True, run_id="probe")
    capsys.readouterr()
    assert not (tmp_path / "out" / "summary.json").exists()
    assert list((tmp_path / "out").rglob("summary.json"))


def test_a_failed_epc_only_run_leaves_no_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "summary.json").write_text('{"from": "an earlier run"}')
    path = tmp_path / "epc_only.yaml"
    path.write_text(yaml.safe_dump({"epc": _block(construction_months=0)}))
    with pytest.raises(SystemExit):
        _run_cli_with(path, tmp_path)
    capsys.readouterr()
    assert not (out_dir / "summary.json").exists()


def test_an_unreadable_file_falls_through_to_the_pipeline(tmp_path: Path) -> None:
    from omegaconf import OmegaConf as OC

    missing = tmp_path / "missing.yaml"
    assert rfp._run_epc_only_scenario(OC.create({}), str(missing)) is False
    bad = tmp_path / "bad.yaml"
    bad.write_text("epc: [unclosed\n")
    assert rfp._run_epc_only_scenario(OC.create({}), str(bad)) is False


def test_a_cost_total_that_is_not_finite_is_refused() -> None:
    block = _block(cost={"a_usd": 1.7e308, "b_usd": 1.7e308})
    with pytest.raises(ValueError, match="not finite"):
        compute_epc_margin({"epc": block})


def test_a_null_irr_carries_its_reason() -> None:
    from finance.epc_margin import IRR_NOTE

    raw = yaml.safe_load(EPC_ONLY_SCENARIO.read_text(encoding="utf-8"))
    entry = epc_margin_result(raw)
    assert entry is not None and entry["annualized_irr"] is None
    assert entry["irr_note"] == IRR_NOTE
    assert "irr_note" not in (epc_margin_result({"epc": _block()}) or {})
