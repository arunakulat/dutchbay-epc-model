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

from analytics.wind.equipment_parity import (
    RESULT_SCHEMA,
    compute_equipment_parity_from_block,
    run_equipment_parity_for_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
METHOD_CONF = REPO_ROOT / "conf" / "equipment_parity.yaml"
WIND_SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
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
    """Return a copy of the wind scenario's ``equipment_cost_parity`` block."""
    return copy.deepcopy(_yaml(WIND_SCENARIO)["equipment_cost_parity"])


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("run_equipment_parity_v14", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _parity(block: Dict[str, Any]) -> Dict[str, Any]:
    return compute_equipment_parity_from_block(block, _method(), REPO_ROOT)


def _break_even_case(out: Dict[str, Any]) -> Dict[str, str]:
    premium = out["results"]["break_even_equipment_price_per_mw_premium_pct"]
    (case,) = [
        c
        for c in out["sensitivity_cases"]
        if c["assumed_equipment_price_per_mw_change_pct"] == premium
    ]
    return case


@pytest.mark.parametrize(
    ("site_life", "benchmark_life"), [(25, 20), (20, 25), (20, 20)]
)
def test_break_even_is_at_parity_whatever_the_two_lives(
    site_life: int, benchmark_life: int
) -> None:
    """D-1: at the break-even premium the cost per lifetime MWh equals the benchmark's."""
    block = _block_from_single_site_conf()
    block["operating_life_years"] = site_life
    block["benchmark"]["operating_life_years"] = benchmark_life
    out = _parity(block)
    case = _break_even_case(out)
    assert abs(float(case["change_vs_benchmark_pct"])) < 1e-30
    assert float(case["equipment_cost_usd"]) == pytest.approx(
        float(out["results"]["same_usd_per_mwh_parity_equipment_cost_usd"]), rel=1e-12
    )


def test_reference_rows_use_the_authors_life_not_the_site_life() -> None:
    """D-2: the reference rows follow the method's common life, never the site's."""
    block = _block_from_single_site_conf()
    base = _parity(copy.deepcopy(block))["reference_scaling_counterexample"]
    block["operating_life_years"] = 25
    longer = _parity(block)["reference_scaling_counterexample"]
    assert longer == base

    method = _method()
    method["reference_scaling_common_life_years"] = 25
    rows = compute_equipment_parity_from_block(
        _block_from_single_site_conf(), method, REPO_ROOT
    )["reference_scaling_counterexample"]
    key = "authors_common_life_equipment_usd_per_mwh"
    assert float(rows[0][key]) == pytest.approx(float(base[0][key]) * 20 / 25)


def test_hold_status_comes_from_the_energy_summary() -> None:
    """D-3: the result states the summary's own hold field, and no fixed status text."""
    block = _block_from_single_site_conf()
    out = _parity(block)
    summary = json.loads((REPO_ROOT / block["energy_summary"]).read_text("utf-8"))
    assert out["site_aep_hold_status"] == summary["hold"].strip()
    assert "HOLD" not in out["purpose"]
    assert "met-mast" not in out["purpose"].lower()


def test_runner_refuses_a_wrong_schema_or_a_non_mapping_scenario(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    raw = _yaml(METHOD_CONF)
    raw["scenario"] = str(LENDER_SCENARIO)
    raw["schema_version"] = "equipment_parity_method_v0"
    with pytest.raises(ValueError, match="schema_version"):
        runner.run(raw)

    listed = tmp_path / "list.yaml"
    listed.write_text("- not\n- a mapping\n", encoding="utf-8")
    raw = _yaml(METHOD_CONF)
    raw["scenario"] = str(listed)
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        runner.run(raw)


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
        "met-mast",
        "met_mast",
        "conf/",
        "scenarios/",
        "docs/",
    ):
        assert literal not in source, literal
