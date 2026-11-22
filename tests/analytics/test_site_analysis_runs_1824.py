"""One runner for every site analysis, with code and config digests (#1824)."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import math
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import yaml

from analytics import site_analysis_runs as runs
from analytics.site_analysis_blocks import (
    SITE_ANALYSIS_BLOCKS,
    resolve_site_analysis_block,
)

ROOT = Path(__file__).resolve().parents[2]
WIND = Path("scenarios/blue_whale_wind_lot5b_2026.yaml")
BASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")


def _scenario(rel: Path) -> Dict[str, Any]:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def test_every_site_analysis_has_a_runner_whose_files_exist() -> None:
    assert tuple(runs.SITE_ANALYSIS_RUNS) == SITE_ANALYSIS_BLOCKS
    for block, spec in runs.SITE_ANALYSIS_RUNS.items():
        assert spec.block == block
        assert spec.mode in (runs.MODE_LIVE, runs.MODE_SUMMARY)
        assert (ROOT / spec.default_method_config).is_file(), block
        assert spec.code_files, block
        for rel in spec.code_files:
            assert (ROOT / rel).is_file(), rel


def test_provenance_digests_the_code_the_scenario_and_every_named_input() -> None:
    scenario = _scenario(WIND)
    block = resolve_site_analysis_block(scenario, "equipment_cost_parity")
    assert block is not None
    prov = runs.provenance("equipment_cost_parity", block, ROOT / WIND)
    assert prov["schema"] == runs.PROVENANCE_SCHEMA
    assert set(prov["code"]["files"]) == {"analytics/wind/equipment_parity.py"}
    config = set(prov["config"]["files"])
    # The scenario file, the method config the block names, and each file the block names.
    assert WIND.as_posix() in config
    assert block["method_config"] in config
    assert block["energy_summary"] in config
    assert block["capex_config"] in config
    import hashlib

    for rel, digest in {**prov["code"]["files"], **prov["config"]["files"]}.items():
        assert digest == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _prov() -> Dict[str, Any]:
    scenario = _scenario(WIND)
    block = resolve_site_analysis_block(scenario, "equipment_cost_parity")
    assert block is not None
    return runs.provenance("equipment_cost_parity", block, ROOT / WIND)


def test_a_matching_provenance_is_not_stale() -> None:
    prov = _prov()
    assert runs.stale_reasons(copy.deepcopy(prov), prov) == []


@pytest.mark.parametrize("part", ["code", "config"])
def test_a_changed_file_is_named_as_the_reason(part: str) -> None:
    prov = _prov()
    old = copy.deepcopy(prov)
    rel = sorted(old[part]["files"])[0]
    old[part]["files"][rel] = "0" * 64
    reasons = runs.stale_reasons(old, prov)
    assert reasons == [f"{part} file changed since the summary: {rel}"]


def test_a_file_read_now_or_no_longer_read_is_named() -> None:
    prov = _prov()
    old = copy.deepcopy(prov)
    dropped = sorted(old["config"]["files"])[0]
    del old["config"]["files"][dropped]
    old["config"]["files"]["conf/gone.yaml"] = "1" * 64
    reasons = runs.stale_reasons(old, prov)
    assert f"config file not in the summary: {dropped}" in reasons
    assert "config file no longer read: conf/gone.yaml" in reasons


def test_a_tree_that_disagrees_with_its_files_is_stale() -> None:
    prov = _prov()
    old = copy.deepcopy(prov)
    old["code"]["tree"] = "f" * 64
    assert runs.stale_reasons(old, prov) == [
        "the summary's code tree digest does not match its files"
    ]


@pytest.mark.parametrize(
    "recorded",
    [None, {}, {"schema": "other"}, "text"],
)
def test_a_summary_without_checkable_provenance_is_stale(recorded: Any) -> None:
    assert runs.stale_reasons(recorded, _prov()) == [
        "the summary records no provenance this report can check"
    ]


def test_a_summary_missing_one_digest_says_which() -> None:
    prov = _prov()
    old = copy.deepcopy(prov)
    del old["code"]
    assert runs.stale_reasons(old, prov) == ["the summary records no code digest"]


def test_a_scenario_without_the_block_is_not_applicable_and_unstamped() -> None:
    result = runs.run_site_analysis("storage_options", _scenario(BASE), BASE)
    assert result == {
        "status": "not_applicable",
        "reason": "the scenario declares no storage_options block",
    }


def test_a_live_run_is_stamped_with_the_digests_it_ran_with() -> None:
    scenario = _scenario(WIND)
    result = runs.run_site_analysis("equipment_cost_parity", scenario, WIND)
    assert result["status"] == "completed"
    assert result["provenance"] == _prov()


def test_the_effective_scenario_is_what_runs() -> None:
    # A report passes the run's effective scenario; the analysis must read it, not the file.
    scenario = _scenario(BASE)
    changed = copy.deepcopy(scenario)
    changed["capex"]["usd_total"] = float(changed["capex"]["usd_total"]) * 1.5
    base = runs.run_site_analysis("financing_screening", scenario, BASE)
    moved = runs.run_site_analysis("financing_screening", changed, BASE)
    assert base["scenario_inputs_applied"]["capex_usd"] != (
        moved["scenario_inputs_applied"]["capex_usd"]
    )


def test_an_unknown_analysis_is_refused() -> None:
    with pytest.raises(KeyError, match="unknown site analysis block"):
        runs.run_site_analysis("met_mast", _scenario(WIND), WIND)


def test_summary_path_is_keyed_by_scenario_stem_and_block() -> None:
    assert runs.summary_path(WIND, "storage_options") == (
        ROOT / "docs/site_analyses/blue_whale_wind_lot5b_2026/storage_options.json"
    )


def test_json_ready_writes_strict_json() -> None:
    out = runs.json_ready(
        {
            "nan": float("nan"),
            "inf": math.inf,
            "dec": Decimal("1.2345678901234567890123"),
            "np": np.float64(0.5),
            "npint": np.int64(3),
            "day": dt.date(2026, 11, 21),
            "nested": [{"x": (1, 2)}],
        }
    )
    assert out == {
        "nan": None,
        "inf": None,
        "dec": "1.2345678901234567890123",
        "np": 0.5,
        "npint": 3,
        "day": "2026-11-21",
        "nested": [{"x": [1, 2]}],
    }
    with pytest.raises(TypeError, match="cannot write object"):
        runs.json_ready(object())


def test_write_and_load_summary_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b.json"
    runs.write_summary({"z": 1, "a": float("nan")}, target)
    assert target.read_text(encoding="utf-8") == '{\n  "a": null,\n  "z": 1\n}\n'
    assert runs.load_summary(target) == {"a": None, "z": 1}
    assert runs.load_summary(tmp_path / "missing.json") is None
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must hold a JSON object"):
        runs.load_summary(tmp_path / "list.json")


def _script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "run_site_analysis_v14", ROOT / "scripts" / "run_site_analysis_v14.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_script_refuses_an_unknown_analysis_or_a_missing_scenario() -> None:
    script = _script()
    with pytest.raises(ValueError, match="analysis must be one of"):
        script.run({"analysis": "met_mast", "scenario": WIND.as_posix()})
    with pytest.raises(ValueError, match="scenario=<path> is required"):
        script.run({"analysis": "storage_options", "scenario": None})


def test_the_script_writes_a_stamped_summary_where_reports_read_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _script()
    target = ROOT / "docs" / "site_analyses" / "_test_1824" / "x.json"
    monkeypatch.setattr(script, "summary_path", lambda path, block: target)
    written: Dict[str, Any] = {}

    def fake_write(result: Any, where: Path) -> None:
        written["result"], written["where"] = result, where

    monkeypatch.setattr(script, "write_summary", fake_write)
    out = script.run(
        {
            "analysis": "equipment_cost_parity",
            "scenario": WIND.as_posix(),
            "write": True,
        }
    )
    assert out == {"written": "docs/site_analyses/_test_1824/x.json"}
    assert written["where"] == target
    assert written["result"]["provenance"] == _prov()


def test_the_script_will_not_write_a_summary_for_an_absent_block() -> None:
    script = _script()
    with pytest.raises(ValueError, match="declares no storage_options block"):
        script.run(
            {"analysis": "storage_options", "scenario": BASE.as_posix(), "write": True}
        )
