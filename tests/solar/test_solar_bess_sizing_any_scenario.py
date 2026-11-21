"""PV + BESS sizing for any scenario that declares a ``solar_storage_sizing`` block (#1578 U3).

The oracle is the single-site script: the config built from the scenario's block and the method
config equals ``conf/blue_whale_solar_bess_project_sizing.yaml``, and a reduced run through
the block reproduces the same reduced run through that config, point for point. Runs here
use reduced grids and trial counts (TEST-03).
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.site_analysis_blocks import resolve_site_analysis_block
from solar_resource import pv_bess_sizing_runner as runner

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
NO_BLOCK_SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
SITE_CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess_project_sizing.yaml"
METHOD_CONF = REPO_ROOT / "conf" / "solar_bess_sizing.yaml"
SCRIPT = REPO_ROOT / "scripts" / "run_solar_bess_sizing_v14.py"
SINGLE_SITE_SCRIPT = REPO_ROOT / "scripts" / "run_blue_whale_pv_bess_sizing_v14.py"
POLICY = REPO_ROOT / "config" / "stochastic_test_policy.yaml"

#: One grid point: the committed size.
ONE_POINT = {"pv_tables": [107], "pv_ac_mw": [3.5], "bess_power_mw": [0.1]}
#: Spec keys that name the code, commit and timing of a run rather than its result.
VOLATILE_SPEC = (
    "git_sha",
    "code_sha256",
    "inputs_digest",
    "runtime_s",
    "result_sha256",
    "sizing_config_sha256",
)


def _yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _hard_cap() -> int:
    return int(_yaml(POLICY)["ordinary_suite"]["hard_max_model_evaluations"])


def _method() -> Dict[str, Any]:
    return _yaml(METHOD_CONF)["method"]


def _site_cfg() -> Dict[str, Any]:
    return {k: v for k, v in _yaml(SITE_CONF).items() if k not in ("defaults", "hydra")}


def _reduce(block_or_cfg: Dict[str, Any]) -> None:
    """One grid point, no one-at-a-time cases or break-even searches."""
    block_or_cfg["grid"].update(ONE_POINT)
    block_or_cfg["sensitivities"]["one_at_a_time"] = []
    block_or_cfg["sensitivities"]["break_even"] = []


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


# ------------------------------------------------------------------ the oracle


def test_block_built_config_equals_the_single_site_config() -> None:
    block = resolve_site_analysis_block(_yaml(SCENARIO), runner.BLOCK)
    assert block is not None
    built = runner.config_from_block(block, _method(), scenario_label=_rel(SCENARIO))
    legacy = _site_cfg()
    assert set(built) == set(legacy)
    # Only the schema's site prefix differs: the block's config is the generic family.
    assert built["schema_version"] == "solar_bess_project_sizing_v1"
    assert legacy["schema_version"].endswith("_" + built["schema_version"])
    for key in legacy:
        if key != "schema_version":
            assert built[key] == legacy[key], key


#: Block keys that describe the run rather than size it: the run reads ``site``, ``notes``
#: and ``limitations`` itself, and the rest are provenance.
_ENVELOPE_KEYS = {
    "site",
    "retrieved",
    "sources",
    "method_config",
    "notes",
    "limitations",
}


def _numeric_leaves(node: Any, path: tuple = ()) -> list[tuple]:
    if isinstance(node, dict):
        return [p for k, v in node.items() for p in _numeric_leaves(v, (*path, k))]
    if isinstance(node, list):
        return [p for i, v in enumerate(node) for p in _numeric_leaves(v, (*path, i))]
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return [path]
    return []


def _at(node: Any, path: tuple) -> Any:
    for key in path:
        node = node[key]
    return node


def test_every_block_number_reaches_the_built_config() -> None:
    """Every key of the block is either envelope or sizing input, and every number of the
    sizing inputs reaches the built config at its own path, so no block value is silently
    dropped or replaced by a fixed one."""
    block = resolve_site_analysis_block(_yaml(SCENARIO), runner.BLOCK)
    assert block is not None
    assert set(block) == _ENVELOPE_KEYS | set(runner.BLOCK_SIZING_KEYS)
    sized = {k: block[k] for k in runner.BLOCK_SIZING_KEYS}
    leaves = _numeric_leaves(sized)
    assert len(leaves) > 50
    moved = copy.deepcopy(sized)
    for n, path in enumerate(leaves):
        parent = _at(moved, path[:-1])
        parent[path[-1]] = 7_000_000.0 + n
    built = runner.config_from_block(moved, _method(), scenario_label="x")
    for n, path in enumerate(leaves):
        assert _at(built, path) == 7_000_000.0 + n, path


def test_block_run_reproduces_the_single_site_run() -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    scenario = _yaml(SCENARIO)
    _reduce(scenario[runner.BLOCK])
    method = _method()
    method["monte_carlo"]["n_trials"] = 2
    new = runner.run_solar_bess_sizing_for_scenario(
        scenario, method, scenario_label=_rel(SCENARIO), script=SCRIPT
    )
    legacy_cfg = _site_cfg()
    _reduce(legacy_cfg)
    legacy_cfg["monte_carlo"]["n_trials"] = 2
    old = runner.run(
        legacy_cfg,
        config_label="legacy",
        script=SINGLE_SITE_SCRIPT,
        limitations=list(scenario[runner.BLOCK]["limitations"]),
    )
    assert new["status"] == "completed"
    assert new["config"] == f"{_rel(SCENARIO)}#solar_storage_sizing"
    assert new["points"] and new["points"] == old["points"]
    assert new["recommendation"] == old["recommendation"]
    assert new["sensitivities"] == old["sensitivities"]
    keep = {k: v for k, v in new["spec"].items() if k not in VOLATILE_SPEC}
    assert keep == {k: v for k, v in old["spec"].items() if k not in VOLATILE_SPEC}
    assert new["spec"]["effective_evaluations"] * 2 <= _hard_cap()
    # The single-site script's own stated limitations are the block's.
    cli = _load(SINGLE_SITE_SCRIPT)
    assert [*cli.LIMITATIONS, *cli.PROJECT_LIMITATIONS] == new["spec"]["limitations"]


def _load(path: Path) -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_block_moves_the_result() -> None:
    """Non-vacuous: the run reads the block, not the single-site config."""
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    method = _method()
    method["monte_carlo"]["n_trials"] = 2
    base = _yaml(SCENARIO)
    _reduce(base[runner.BLOCK])
    moved = copy.deepcopy(base)
    moved[runner.BLOCK]["plant"]["grid_civils_development_usd"] = 3000000.0
    a, b = (
        runner.run_solar_bess_sizing_for_scenario(
            s, method, scenario_label=_rel(SCENARIO), script=SCRIPT
        )
        for s in (base, moved)
    )
    npv = [r["points"][0]["base"]["project_npv"] for r in (a, b)]
    assert npv[1] < npv[0]
    assert a["block_sha256"] != b["block_sha256"]


# ------------------------------------------------------------- applicability


def test_scenario_without_block_is_not_applicable() -> None:
    out = runner.run_solar_bess_sizing_for_scenario(
        _yaml(NO_BLOCK_SCENARIO),
        _method(),
        scenario_label=_rel(NO_BLOCK_SCENARIO),
        script=SCRIPT,
    )
    assert out == {
        "schema": runner.SUMMARY_SCHEMA,
        "analysis": "PV + BESS sizing and dispatch",
        "scenario": _rel(NO_BLOCK_SCENARIO),
        "status": "not_applicable",
        "reason": "the scenario declares no solar_storage_sizing block",
    }


def test_malformed_block_fails_loud_before_any_run() -> None:
    scenario = _yaml(SCENARIO)
    scenario[runner.BLOCK]["readings"]["committed"] = "C"
    del scenario[runner.BLOCK]["plant"]["bess_dc_per_nominal"]
    with pytest.raises(ValueError) as err:
        runner.run_solar_bess_sizing_for_scenario(
            scenario, _method(), scenario_label=_rel(SCENARIO), script=SCRIPT
        )
    assert "solar_storage_sizing.readings.committed" in str(err.value)
    assert "solar_storage_sizing.plant.bess_dc_per_nominal" in str(err.value)


@pytest.mark.parametrize("missing", runner.METHOD_KEYS)
def test_method_config_must_hold_its_keys(missing: str) -> None:
    method = _method()
    del method[missing]
    block = _yaml(SCENARIO)[runner.BLOCK]
    with pytest.raises(ValueError, match="method config lacks"):
        runner.config_from_block(block, method, scenario_label="x")


# ------------------------------------------------- the summary's reading names


def test_grid_columns_follow_the_readings() -> None:
    assert runner.grid_columns(["A", "B"]) == runner.GRID_COLUMNS
    cols = [c for c, _ in runner.grid_columns(["low", "mid", "high"])]
    at = cols.index("meets_4h_rule")
    assert cols[at + 1 : at + 4] == ["eligible_low", "eligible_mid", "eligible_high"]
    assert "eligible_A" not in cols
    assert len(cols) == len(runner.GRID_COLUMNS) + 1


def test_concise_summary_names_each_reading() -> None:
    size = {"pv_tables": 10, "pv_ac_mw": 1.0, "bess_power_mw": 0.5}
    point = {
        **size,
        "evaluated": True,
        "eligible_by_reading": {"low": True, "high": False},
    }
    out = {
        "config": "c",
        "statistics_convention": "s",
        "spec": {},
        "recommendation": {
            "by_reading": {"low": {"size": size}, "high": {"size": None}},
            "revenue_max_any_reading": {"size": None},
        },
        "points": [point],
        "sensitivities": {
            "rte": {
                "label": "x",
                "rows": [
                    {
                        "size": size,
                        "eligible_by_reading": {"low": True, "high": False},
                        "unit_pretax_npv_usd": 1.0,
                        "project_npv": 2.0,
                        "year1_unit_revenue_lkr": 3.0,
                    }
                ],
            }
        },
    }
    summary = runner.concise_project_summary(out)
    grid = dict(
        zip(summary["grid"]["columns"], summary["grid"]["rows"][0], strict=True)
    )
    assert (grid["eligible_low"], grid["eligible_high"]) == (True, False)
    sens = summary["sensitivities"]["rte"]
    assert sens["columns"][3:5] == ["eligible_low", "eligible_high"]
    assert sens["rows"] == [[10, 1.0, 0.5, True, False, 1.0, 2.0, 3.0]]
    assert summary["named_points"] == [point]


# ------------------------------------------------------------------- the CLI


def _cli(tmp_path: Path, *args: str) -> Dict[str, Any]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert isinstance(out, dict)
    return out


def test_cli_reports_a_scenario_without_the_block_as_not_applicable(
    tmp_path: Path,
) -> None:
    out = _cli(tmp_path, f"scenario={_rel(NO_BLOCK_SCENARIO)}")
    assert out["status"] == "not_applicable"
    assert not (tmp_path / "outputs").exists() and not (tmp_path / ".hydra").exists()


def test_cli_sizes_any_scenario_with_the_block(tmp_path: Path) -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    scenario = _yaml(SCENARIO)
    _reduce(scenario[runner.BLOCK])
    path = tmp_path / "reduced.yaml"
    path.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
    summary = tmp_path / "summary.json"
    out = _cli(
        tmp_path,
        f"scenario={path}",
        "method.monte_carlo.n_trials=2",
        f"output.summary_json={summary}",
    )
    assert out["status"] == "completed"
    assert out["spec"]["effective_evaluations"] <= _hard_cap()
    assert out["spec"]["inputs_sha256"][str(path)]
    # MRM-02: the any-scenario script and the moved runner are in the code digest.
    files = out["spec"]["code_sha256"]["files"]
    assert "scripts/run_solar_bess_sizing_v14.py" in files
    assert "solar_resource/pv_bess_sizing_runner.py" in files
    written = json.loads(summary.read_text())
    assert written["config"] == f"{path}#solar_storage_sizing"
    assert written["grid"]["columns"] == [c for c, _ in runner.GRID_COLUMNS]
    assert written["recommendation"] == out["recommendation"]


def test_cli_refuses_a_wrong_method_schema(tmp_path: Path) -> None:
    cli = _load(SCRIPT)
    with pytest.raises(ValueError, match="schema_version must be"):
        cli.run({"schema_version": "other", "method": {}, "scenario": "x"})
    with pytest.raises(ValueError, match="scenario=<path> is required"):
        cli.run({"schema_version": cli.METHOD_SCHEMA, "method": {}, "scenario": None})
    with pytest.raises(ValueError, match="method must be a mapping"):
        cli.run({"schema_version": cli.METHOD_SCHEMA, "method": None, "scenario": "x"})
