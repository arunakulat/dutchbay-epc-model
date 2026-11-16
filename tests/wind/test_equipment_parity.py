"""Tests for the scenario-driven equipment-cost parity analysis (#1755)."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.wind import blue_whale_equipment_parity as single_site
from analytics.wind.equipment_parity import (
    RESULT_SCHEMA,
    run_equipment_parity_for_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_CONF = REPO_ROOT / "conf" / "blue_whale_equipment_parity.yaml"
METHOD_CONF = REPO_ROOT / "conf" / "equipment_parity.yaml"
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
MODULE = REPO_ROOT / "analytics" / "wind" / "equipment_parity.py"
RUNNER = REPO_ROOT / "scripts" / "run_equipment_parity_v14.py"


def _yaml(path: Path) -> Dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _method() -> Dict[str, Any]:
    return _yaml(METHOD_CONF)["method"]


def _block_from_single_site_conf() -> Dict[str, Any]:
    """The single-site conf's inputs, expressed as an ``equipment_cost_parity`` block."""
    cfg = _yaml(SITE_CONF)
    bw = cfg["blue_whale"]
    return {
        "site": {"name": "Single-site conf", "location": "As in the single-site conf"},
        "retrieved": "2026-11-14",
        "sources": [str(cfg["mannar_benchmark"]["source"])],
        "energy_summary": bw["summary_json_path"],
        "capex_config": bw["capex_solar_resource_config"],
        "operating_life_years": bw["operating_life_years"],
        "loss_retention_factors": bw["loss_retention_factors"],
        "benchmark": {"name": "Benchmark project", **cfg["mannar_benchmark"]},
        "sensitivity_premium_pct": cfg["sensitivity_premium_pct"],
        "cost_buildup_packages": cfg["cost_buildup_packages"],
    }


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("run_equipment_parity_v14", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_method_reference_rows_match_the_single_site_conf() -> None:
    assert (
        _method()["reference_scaling_counterexample"]
        == _yaml(SITE_CONF)["ashuri_2016_counterexample"]
    )
    assert (
        _method()["hours_per_year"] == _yaml(SITE_CONF)["blue_whale"]["hours_per_year"]
    )


def test_scenario_block_reproduces_the_single_site_result_exactly() -> None:
    """Oracle: the block-driven run equals the single-site run under the key map."""
    scenario = {
        "project": {"name": "x"},
        "equipment_cost_parity": _block_from_single_site_conf(),
    }
    out = run_equipment_parity_for_scenario(scenario, _method(), REPO_ROOT)
    assert out["status"] == "completed"
    assert out["schema"] == RESULT_SCHEMA

    legacy = single_site.compute_equipment_parity(_yaml(SITE_CONF), REPO_ROOT)
    universal = out["equipment_parity"]
    renamed = {single_site.TOP_KEY_MAP.get(k, k): v for k, v in universal.items()}
    renamed["results"] = {
        single_site.RESULT_KEY_MAP[k] if k in single_site.RESULT_KEY_MAP else k: v
        for k, v in universal["results"].items()
    }
    renamed["sensitivity_cases"] = [
        {single_site.CASE_KEY_MAP.get(k, k): v for k, v in case.items()}
        for case in universal["sensitivity_cases"]
    ]
    assert json.dumps(renamed, sort_keys=True) == json.dumps(legacy, sort_keys=True)

    packages = _yaml(SITE_CONF)["cost_buildup_packages"]
    for route in ("road", "marine"):
        expected = single_site.evaluate_cost_buildup(packages, route)
        got = dict(out["cost_buildup"][route])
        assert got.pop("schema") == "cost_buildup_evaluation.v1"
        expected.pop("schema")
        assert got == expected


def test_key_maps_cover_every_renamed_result() -> None:
    scenario = {"equipment_cost_parity": _block_from_single_site_conf()}
    universal = run_equipment_parity_for_scenario(scenario, _method(), REPO_ROOT)
    keys = set(universal["equipment_parity"]["results"])
    site_named = {
        k for k in keys if k.startswith(("benchmark_", "site_", "reference_"))
    }
    assert site_named <= set(single_site.RESULT_KEY_MAP)


def test_scenario_without_block_is_not_applicable() -> None:
    scenario = _yaml(LENDER_SCENARIO)
    out = run_equipment_parity_for_scenario(
        scenario, _method(), REPO_ROOT, scenario_label="the lender case"
    )
    assert out == {
        "schema": RESULT_SCHEMA,
        "status": "not_applicable",
        "reason": "no equipment_cost_parity block in the lender case",
    }


def test_malformed_block_fails_loud() -> None:
    block = _block_from_single_site_conf()
    block["benchmark"]["turbine_count"] = 0
    with pytest.raises(ValueError, match=r"benchmark\.turbine_count"):
        run_equipment_parity_for_scenario(
            {"equipment_cost_parity": block}, _method(), REPO_ROOT
        )


def test_benchmark_without_historical_capacity_omits_that_result() -> None:
    block = _block_from_single_site_conf()
    block["benchmark"].pop("historical_unreconciled_capacity_mw")
    out = run_equipment_parity_for_scenario(
        {"equipment_cost_parity": block}, _method(), REPO_ROOT
    )
    results = out["equipment_parity"]["results"]
    assert "benchmark_equipment_usd_per_kw_historical_unreconciled" not in results
    assert "benchmark_equipment_usd_per_kw" in results


def test_results_follow_the_block_not_a_fixed_site() -> None:
    """TEST-01 responsiveness: a different benchmark moves the parity threshold."""
    block = _block_from_single_site_conf()
    base = run_equipment_parity_for_scenario(
        {"equipment_cost_parity": copy.deepcopy(block)}, _method(), REPO_ROOT
    )
    block["benchmark"]["turbine_supply_usd"] = (
        2 * block["benchmark"]["turbine_supply_usd"]
    )
    doubled = run_equipment_parity_for_scenario(
        {"equipment_cost_parity": block}, _method(), REPO_ROOT
    )
    b = base["equipment_parity"]["results"][
        "same_usd_per_mwh_parity_equipment_cost_usd"
    ]
    d = doubled["equipment_parity"]["results"][
        "same_usd_per_mwh_parity_equipment_cost_usd"
    ]
    assert float(d) == pytest.approx(2 * float(b))


def test_runner_reads_the_scenario_file(tmp_path: Path) -> None:
    scenario_path = tmp_path / "with_block.yaml"
    scenario_path.write_text(
        yaml.safe_dump({"equipment_cost_parity": _block_from_single_site_conf()}),
        encoding="utf-8",
    )
    runner = _load_runner()
    raw = _yaml(METHOD_CONF)
    raw["scenario"] = str(scenario_path)
    out = runner.run(raw)
    assert out["status"] == "completed"
    assert out["scenario"] == str(scenario_path)

    raw["scenario"] = None
    with pytest.raises(ValueError, match="scenario=<path> is required"):
        runner.run(raw)


def test_runner_cli_reports_not_applicable_for_a_committed_scenario() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "scenario=scenarios/dutchbay_lendercase_2025Q4.yaml",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "not_applicable"
    assert payload["scenario"] == "scenarios/dutchbay_lendercase_2025Q4.yaml"


def test_universal_module_holds_no_site_name_or_path() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    for literal in (
        "blue_whale",
        "blue whale",
        "mannar",
        "dutchbay",
        "dutch bay",
        "kalpitiya",
        "lot 5b",
        "conf/",
        "scenarios/",
        "docs/",
    ):
        assert literal not in source, literal
