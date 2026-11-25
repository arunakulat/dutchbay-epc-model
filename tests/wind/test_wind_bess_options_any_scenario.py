"""Tests for the wind battery options and the equipment parity for any scenario (#1578 U2, #1755)."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import numpy as np
import pytest
import yaml

from analytics.wind import wind_bess_options_runner as runner
from finance.capex_price_basis import capex_escalation_factor

REPO = Path(__file__).resolve().parents[2]
SCENARIO_REL = "scenarios/blue_whale_wind_lot5b_2026.yaml"
SCENARIO = REPO / SCENARIO_REL
METHOD_CONFIG = REPO / "conf" / "wind_bess_options.yaml"
UNIVERSAL_SCRIPT = REPO / "scripts" / "run_wind_bess_options_v14.py"
LENDER_REL = "scenarios/dutchbay_lendercase_2025Q4.yaml"


def _yaml(path: Path) -> Dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _scenario() -> Dict[str, Any]:
    return _yaml(SCENARIO)


def _method() -> Dict[str, Any]:
    method: Dict[str, Any] = _yaml(METHOD_CONFIG)["method"]
    return method


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stamps(days: int) -> List[str]:
    return [f"202601{d + 1:02d}{h:02d}" for d in range(days) for h in range(24)]


def _fake_profile(seen: List[Dict[str, Any]]) -> Any:
    stamps = _stamps(14)
    wind = np.clip(np.random.default_rng(7).normal(4.6, 3.0, len(stamps)), 0.0, 9.2)

    def build(cfg: Any, scenario: Any) -> Dict[str, Any]:
        seen.append(copy.deepcopy(cfg))
        return {
            "stamps": stamps,
            "poi_mw": wind,
            "window_wind_mwh": 7000.0,
            "checks": {},
        }

    return build


def _small(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """The committed scenario with two options and a short Monte Carlo, for speed."""
    out = copy.deepcopy(scenario)
    options = out["storage_options"]["sizes"]["options"]
    out["storage_options"]["sizes"]["options"] = [
        o for o in options if o["id"] in ("held_0_5_0_5", "cycled_0_5_2")
    ]
    return out


def _short_method() -> Dict[str, Any]:
    method = _method()
    method["monte_carlo"] = dict(method["monte_carlo"]) | {
        "n_trials": 8,
        "rte_grid": [0.85],
    }
    return method


# ---------------------------------------------------------------------------
# Wind battery options
# ---------------------------------------------------------------------------
def test_block_built_config_follows_the_block() -> None:
    """Values the single-site config shares with the block still come from the block."""
    scenario = _scenario()
    block = copy.deepcopy(scenario["storage_options"])
    block["uncertainty"]["wind_yield_sigma"] = 0.2
    block["grid_limits"]["export_cap_readings"] = {"only": 7.5}
    block["tariff"]["one_time_adjustment_weights"] = {"lkr_usd": 0.5, "ccpi": 0.5}
    block["sizes"]["options"][0]["operation"] = "cycled"
    cfg = runner.config_from_block(
        scenario, block, _method(), scenario_label=SCENARIO_REL
    )
    assert cfg["monte_carlo"]["wind_yield_sigma"] == 0.2
    assert cfg["limits"]["readings"] == {"only": {"export_cap_mw": 7.5}}
    assert cfg["tariff"]["one_time_adjustment_weights"] == {"lkr_usd": 0.5, "ccpi": 0.5}
    assert cfg["options"][0]["operation"] == "cycled"
    assert cfg["tariff"]["wind_lkr_per_kwh"] == float(scenario["tariff"]["lkr_per_kwh"])


#: Envelope keys: the block's provenance, not inputs of the options.
_ENVELOPE_KEYS = {"site", "retrieved", "sources", "method_config", "notes"}
#: Block leaves the run reads itself rather than through the built config.
_READ_BY_THE_RUN = {("hourly_profile", "high_output_check_mw")}


def test_every_block_number_reaches_the_built_config() -> None:
    """#1797 assurance A-1: move every numeric leaf of the block; each must arrive.

    A value hard-coded in ``config_from_block`` that equals today's block value passes the
    equality oracle; here each leaf takes a distinct sentinel, so a hard-coded value drops
    its sentinel and the test names the leaf.
    """
    scenario = _scenario()
    block = copy.deepcopy(scenario["storage_options"])
    sentinels: Dict[float, tuple] = {}

    def move(node: Any, path: tuple) -> Any:
        if isinstance(node, dict):
            return {
                k: v if not path and k in _ENVELOPE_KEYS else move(v, (*path, k))
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [move(v, (*path, i)) for i, v in enumerate(node)]
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            value = 10_000.0 + len(sentinels) + 0.125
            sentinels[value] = path
            return value
        return node

    moved = move(block, ())
    assert len(sentinels) > 50
    cfg = runner.config_from_block(
        scenario, moved, _method(), scenario_label=SCENARIO_REL
    )
    arrived: List[float] = []

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)
        elif isinstance(node, float):
            arrived.append(node)

    collect(cfg)
    missing = {sentinels[v] for v in sentinels if v not in arrived}
    assert missing == _READ_BY_THE_RUN
    # Each arrives once: no block value is copied into two config keys.
    assert sorted(v for v in arrived if v in sentinels) == sorted(
        v for v in sentinels if sentinels[v] not in _READ_BY_THE_RUN
    )


def test_scenario_without_the_block_is_not_applicable() -> None:
    lender = _yaml(REPO / LENDER_REL)
    out = runner.run_wind_bess_options_for_scenario(
        lender, _method(), scenario_label=LENDER_REL
    )
    assert out["status"] == "not_applicable"
    assert out["schema"] == runner.SUMMARY_SCHEMA
    assert "storage_options" in out["reason"]


def test_malformed_block_fails_loud() -> None:
    scenario = _scenario()
    del scenario["storage_options"]["firming_supplier"]
    with pytest.raises(ValueError, match="storage_options.firming_supplier"):
        runner.run_wind_bess_options_for_scenario(
            scenario, _method(), scenario_label=SCENARIO_REL
        )


def test_incomplete_method_config_is_refused() -> None:
    scenario = _scenario()
    method = _method()
    del method["monte_carlo"]
    with pytest.raises(ValueError, match="monte_carlo"):
        runner.config_from_block(
            scenario, scenario["storage_options"], method, scenario_label=SCENARIO_REL
        )


def test_default_profile_uses_the_block_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: List[Dict[str, Any]] = []
    fake = _fake_profile([])
    thresholds: List[float] = []

    def spy(cfg: Any, scenario: Any, *, high_output_check_mw: float) -> Dict[str, Any]:
        seen.append(cfg)
        thresholds.append(high_output_check_mw)
        return fake(cfg, scenario)

    monkeypatch.setattr(runner, "build_profile", spy)
    scenario = _small(_scenario())
    scenario["storage_options"]["hourly_profile"]["high_output_check_mw"] = 7.25
    out = runner.run_wind_bess_options_for_scenario(
        scenario, _short_method(), scenario_label=SCENARIO_REL
    )
    assert out["status"] == "completed"
    assert thresholds == [7.25]
    assert seen[0]["profile"]["transfer_summary"] == (
        scenario["storage_options"]["hourly_profile"]["transfer_summary"]
    )


def test_end_to_end_on_a_synthetic_profile_follows_the_block() -> None:
    scenario = _small(_scenario())
    seen: List[Dict[str, Any]] = []
    out = runner.run_wind_bess_options_for_scenario(
        scenario,
        _short_method(),
        scenario_label=SCENARIO_REL,
        profile_builder=_fake_profile(seen),
    )
    json.dumps(runner.json_clean(out), allow_nan=False)
    assert out["status"] == "completed"
    assert out["schema"] == runner.SUMMARY_SCHEMA
    assert out["site"] == scenario["storage_options"]["site"]
    assert out["hold"] == _method()["hold"]
    assert set(out["options"]) == {"held_0_5_0_5", "cycled_0_5_2"}
    assert set(out["options"]["cycled_0_5_2"]["readings"]) == set(
        scenario["storage_options"]["grid_limits"]["export_cap_readings"]
    )
    assert out["scenario_sha256"] == runner.sha256_file(SCENARIO)
    # Hand-worked capex: energy x the block's mode price x the engine's price-year factor.
    basis = capex_escalation_factor(_scenario())
    assert basis is not None
    mode = scenario["storage_options"]["technology"]["battery"]["usd_per_kwh"]["mode"]
    for name, row in out["options"].items():
        capex = row["readings"]["B"]["battery_pretax_base_basis"]["capex_usd_at_draw"]
        assert capex == pytest.approx(
            row["energy_mwh"] * 1000.0 * mode * float(basis["factor"]), rel=1e-12
        ), name


def test_figures_respond_to_the_block() -> None:
    """ARCH-04: a dearer battery lowers every option's value; options follow the block."""
    base = _small(_scenario())
    dear = copy.deepcopy(base)
    price = dear["storage_options"]["technology"]["battery"]["usd_per_kwh"]
    for key in ("low", "mode", "high"):
        price[key] = price[key] * 1.5
    dear["storage_options"]["sizes"]["options"].append(
        {"id": "extra_1_2", "power_mw": 1.0, "energy_mwh": 2.0, "operation": "cycled"}
    )
    runs = {}
    for name, scenario in (("base", base), ("dear", dear)):
        runs[name] = runner.run_wind_bess_options_for_scenario(
            scenario,
            _short_method(),
            scenario_label=SCENARIO_REL,
            profile_builder=_fake_profile([]),
        )
    assert "extra_1_2" in runs["dear"]["options"]
    assert runs["base"]["block_sha256"] != runs["dear"]["block_sha256"]
    for name in ("held_0_5_0_5", "cycled_0_5_2"):
        value = {
            k: r["options"][name]["readings"]["B"]["bases"]["whole_wind_peak_rate"][
                "delta_project_npv_vs_wind_only"
            ]
            for k, r in runs.items()
        }
        assert value["dear"] < value["base"], name


def test_universal_runner_guards() -> None:
    cli = _load(UNIVERSAL_SCRIPT, "run_wind_bess_options_v14")
    raw = _yaml(METHOD_CONFIG)
    raw.pop("defaults", None)
    raw.pop("hydra", None)
    with pytest.raises(ValueError, match="scenario=<path> is required"):
        cli.run(copy.deepcopy(raw))
    with pytest.raises(ValueError, match="schema_version"):
        cli.run(copy.deepcopy(raw) | {"schema_version": "x", "scenario": LENDER_REL})
    with pytest.raises(ValueError, match="method must be a mapping"):
        cli.run(copy.deepcopy(raw) | {"method": None, "scenario": LENDER_REL})


def test_universal_cli_reports_not_applicable_for_a_scenario_without_the_block() -> (
    None
):
    proc = subprocess.run(
        [sys.executable, str(UNIVERSAL_SCRIPT), f"scenario={LENDER_REL}"],
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)},
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "not_applicable"
    assert payload["scenario"] == LENDER_REL


def test_runner_and_method_config_hold_no_site_literal() -> None:
    for path in (
        REPO / "analytics" / "wind" / "wind_bess_options_runner.py",
        METHOD_CONFIG,
        UNIVERSAL_SCRIPT,
    ):
        text = path.read_text(encoding="utf-8").lower()
        for literal in ("blue whale", "blue_whale", "kalpitiya", "puttalam", "lot 5b"):
            assert literal not in text, (path.name, literal)
