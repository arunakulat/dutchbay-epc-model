"""Tests for the scenario-driven FX and tenor screening (#1578 U4).

The oracle is the single-site run: the ``financing_screening`` block that the base-case
scenario now carries must reproduce ``run_comprehensive_screening`` on
``conf/blue_whale_fx_tenor_screening.yaml`` exactly, figure for figure.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.finance import blue_whale_fx_tenor_screening as single_site
from analytics.finance import fx_tenor_screening as fx
from analytics.finance.fx_tenor_screening import (
    SCENARIO_INPUT_KEYS,
    SUMMARY_SCHEMA,
    compute_fx_tenor_screening_from_block,
    run_fx_tenor_screening_for_scenario,
    scenario_screening_inputs,
)
from finance.capex_price_basis import apply_capex_price_basis

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_CONF = REPO_ROOT / "conf" / "blue_whale_fx_tenor_screening.yaml"
METHOD_CONF = REPO_ROOT / "conf" / "fx_tenor_screening.yaml"
BASECASE = REPO_ROOT / "scenarios" / "dutchbay_basecase_2025Q4.yaml"
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
#: A scenario whose tariff has a fixed part and an indexed O&M part (L-9).
TWO_PART_SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
MODULE = REPO_ROOT / "analytics" / "finance" / "fx_tenor_screening.py"
SHIM = REPO_ROOT / "analytics" / "finance" / "blue_whale_fx_tenor_screening.py"
RUNNER = REPO_ROOT / "scripts" / "run_fx_tenor_screening_v14.py"
SINGLE_SITE_SCRIPT = REPO_ROOT / "scripts" / "run_blue_whale_fx_tenor_screening_v14.py"

#: sha256 of the single-site script's stdout on main 61fb72c5, before #1578 U4. The move to
#: the site-neutral module must not change a byte of it.
SINGLE_SITE_STDOUT_SHA256 = (
    "5d6d3588c08914348e76757b747caf11b7f17b41ee75cb2dac2f0f65f667a75c"
)

#: Keys only the single-site output carries: its case labels and site turbine count.
_LABEL_KEYS = ("case_type", "turbine_count", "description", "overrides")


def _yaml(path: Path) -> Dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _method() -> Dict[str, Any]:
    return _yaml(METHOD_CONF)["method"]


def _basecase() -> Dict[str, Any]:
    return _yaml(BASECASE)


def _figures(result: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in result.items() if k not in _LABEL_KEYS}


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("run_fx_tenor_screening_v14", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(scenario: Dict[str, Any]) -> Dict[str, Any]:
    return run_fx_tenor_screening_for_scenario(
        scenario, _method(), scenario_label="test"
    )


# ------------------------------------------------------------------ the oracle


def test_scenario_block_reproduces_the_single_site_result_exactly() -> None:
    legacy = single_site.run_comprehensive_screening(_yaml(SITE_CONF))
    new = _run(_basecase())
    assert new["status"] == "completed"
    assert new["scenario_inputs_applied"] == legacy["governed_inputs_applied"]
    assert _figures(new["base_case"]) == _figures(
        legacy["governed_basecase_14turbine_15year_screening"]
    )
    assert _figures(new["tenor_variants"]["dfi_10y_ppa_12y_tail_2y"]) == _figures(
        legacy["governed_basecase_14turbine_10year_screening"]
    )
    assert _figures(new["sensitivities"]["handoff_sensitivity"]) == _figures(
        legacy["sensitivity_14turbine_15year_screening"]
    )
    assert new["fixed_debt_fx_stress"] == legacy["fixed_debt_fx_stress_summary"]
    assert new["fx_cagr_windows"] == legacy["fx_metrics"]
    assert new["hold_caveat"] == legacy["f5_hold_caveat"]
    assert new["engine_path_status"] == legacy["engine_path_status"]
    assert new["engine_path_note"] == legacy["engine_path_note"]


def test_block_carries_the_single_site_assumptions() -> None:
    """Each moved value equals the single-site config's, so the two cannot drift apart."""
    conf = _yaml(SITE_CONF)
    block = _basecase()["financing_screening"]
    params = conf["screening_parameters"]
    assert block["debt"] == {
        "dfi_share": params["dfi_share"],
        "dfi_rate_decimal": params["dfi_rate_decimal"],
        "local_rate_decimal": params["local_rate_decimal"],
        "dfi_tenor_years": params["dfi_tenor_years"],
        "local_tenor_years": params["local_tenor_years"],
        "lender_tail_years": params["lender_tail_years"],
        "annual_credit_fee_decimal": params["annual_credit_fee_decimal"],
    }
    assert block["fx_history"]["observations"] == conf["fx_observations"]
    assert block["fx_history"]["cagr_windows"] == conf["fx_cagr_benchmark_windows"]
    stress = conf["stress_grid"]
    assert block["fixed_debt_stress"] == {
        "held_debt_usd": stress["held_debt_usd"],
        "operating_year": stress["shock_operating_year"],
        "depreciation_rates": stress["depreciation_rates"],
        "shock_decimals": stress["shock_decimals"],
    }
    case = conf["cases"]["14_governed_basecase"]
    assert block["generation"]["p50_gwh"] == case["p50_gwh"]
    assert block["generation"]["assumed_downside_gwh"] == case["assumed_downside_gwh"]
    sensitivity = conf["cases"]["14_handoff_sensitivity"]
    moved = block["sensitivities"][0]
    for key in SCENARIO_INPUT_KEYS:
        assert moved.get(key) == sensitivity.get(key), key


# ------------------------------------------------------------- applicability


def test_scenario_without_block_is_not_applicable() -> None:
    out = _run(_yaml(LENDER_SCENARIO))
    assert out["status"] == "not_applicable"
    assert out["reason"] == "the scenario declares no financing_screening block"
    assert out["schema"] == SUMMARY_SCHEMA
    assert "HOLD (F-5, #1110, v15.6.1)" in out["hold_caveat"]


def test_malformed_block_fails_loud() -> None:
    scenario = _basecase()
    scenario["financing_screening"]["label"] = "lender"
    with pytest.raises(ValueError, match="financing_screening.label"):
        _run(scenario)


def test_a_missing_scenario_input_is_named() -> None:
    scenario = _basecase()
    del scenario["fx"]["annual_depr"]
    with pytest.raises(KeyError, match="fx.annual_depr"):
        scenario_screening_inputs(scenario)


# --------------------------------------------- two-part tariff (#1796 domain R1)


def _two_part_with_block() -> Dict[str, Any]:
    """The two-part-tariff scenario with the base case's block, less its O&M rate."""
    scenario = _yaml(TWO_PART_SCENARIO)
    assert "financing_screening" not in scenario
    block = copy.deepcopy(_basecase()["financing_screening"])
    del block["tariff_om_escalation_decimal"]
    scenario["financing_screening"] = block
    # #1899: the screening reads the capex the engine finances.
    return apply_capex_price_basis(scenario)


def test_an_indexed_om_part_is_split_and_escalated_as_the_engine_does() -> None:
    """The screening tariff equals the engine's in every year, on a two-part tariff."""
    from finance.tariff_indexation import (
        resolve_om_indexation,
        tariff_lkr_per_kwh_for_year,
    )

    scenario = _two_part_with_block()
    tariff = float(scenario["tariff"]["lkr_per_kwh"])
    indexation = resolve_om_indexation(scenario, base_tariff_lkr_per_kwh=tariff)
    assert indexation is not None
    escalable = indexation.escalable_om_lkr_per_kwh
    assert 0.0 < escalable < tariff and indexation.annual_rate > 0.0
    assert indexation.pre_operation_years > 0  # the year-1 index is not 1

    inputs = scenario_screening_inputs(scenario)
    assert inputs["tariff_fixed_lkr_per_kwh"] == pytest.approx(tariff - escalable)
    assert inputs["tariff_om_escalation_decimal"] == indexation.annual_rate
    cfg = fx.screening_config_from_block(inputs, scenario["financing_screening"])
    assert cfg["tariff_om_escalation_decimal"] == indexation.annual_rate
    rows = fx.evaluate_dual_currency_screening(cfg, 0.0)
    assert len(rows) == int(scenario["tariff"]["ppa_term_years"])
    for row in rows:
        engine = tariff_lkr_per_kwh_for_year(tariff, indexation, row["year"] - 1)
        assert row["tariff_lkr_per_kwh"] == pytest.approx(engine, rel=1e-12), row[
            "year"
        ]
    # Non-vacuous: the last year's tariff is above the flat contracted tariff.
    assert rows[-1]["tariff_lkr_per_kwh"] > tariff * 1.01


def test_the_indexed_om_part_moves_the_screening_result() -> None:
    scenario = _two_part_with_block()
    indexed = compute_fx_tenor_screening_from_block(
        scenario, scenario["financing_screening"]
    )
    flat = copy.deepcopy(scenario)
    del flat["tariff"]["om_indexation"]
    flat["financing_screening"]["tariff_om_escalation_decimal"] = 0.0
    held = compute_fx_tenor_screening_from_block(flat, flat["financing_screening"])
    assert "tariff_om_escalation_decimal" not in held["scenario_inputs_applied"]
    assert (
        indexed["base_case"]["p50"]["min_dscr"] > held["base_case"]["p50"]["min_dscr"]
    )


def test_the_om_escalation_is_stated_once() -> None:
    """Scenario and block may not both state the O&M rate, and one of them must."""
    scenario = _two_part_with_block()
    scenario["financing_screening"]["tariff_om_escalation_decimal"] = 0.0
    with pytest.raises(ValueError, match="tariff.om_indexation already sets"):
        _run(scenario)
    flat = _basecase()
    del flat["financing_screening"]["tariff_om_escalation_decimal"]
    with pytest.raises(ValueError, match="required when the scenario declares no"):
        _run(flat)


def test_a_malformed_om_indexation_fails_loud() -> None:
    scenario = _two_part_with_block()
    scenario["tariff"]["om_indexation"]["escalable_om_lkr_per_kwh"] = 1.0e6
    with pytest.raises(ValueError, match="exceeds"):
        scenario_screening_inputs(scenario)


# ------------------------------------------------------------ responsiveness


def test_results_follow_the_scenario_and_the_block() -> None:
    base = compute_fx_tenor_screening_from_block(
        _basecase(), _basecase()["financing_screening"]
    )

    cheaper = _basecase()
    cheaper["capex"]["usd_total"] = 120_000_000
    out = compute_fx_tenor_screening_from_block(cheaper, cheaper["financing_screening"])
    assert out["scenario_inputs_applied"]["capex_usd"] == 120_000_000.0
    assert out["base_case"]["equity_capex_balance_usd"] != pytest.approx(
        base["base_case"]["equity_capex_balance_usd"]
    )

    weaker = _basecase()
    weaker["financing_screening"]["generation"]["p50_gwh"] = 400.0
    out = compute_fx_tenor_screening_from_block(weaker, weaker["financing_screening"])
    assert out["base_case"]["debt_usd"] < base["base_case"]["debt_usd"]


def test_a_sensitivity_overrides_only_what_it_names() -> None:
    scenario = _basecase()
    block = copy.deepcopy(scenario["financing_screening"])
    block["sensitivities"] = [
        {"id": "capex_only", "description": "capex only", "capex_usd": 150_000_000}
    ]
    out = compute_fx_tenor_screening_from_block(scenario, block)
    assert out["sensitivities"]["capex_only"]["overrides"] == {"capex_usd": 150_000_000}
    # The scenario's own capex is 150m, so naming the same figure changes nothing.
    assert _figures(out["sensitivities"]["capex_only"]) == _figures(out["base_case"])


def test_optional_parts_may_be_left_out() -> None:
    scenario = _basecase()
    block = scenario["financing_screening"]
    for key in ("tenor_variants", "sensitivities", "fixed_debt_stress", "fx_history"):
        del block[key]
    out = _run(scenario)
    assert out["status"] == "completed"
    assert out["tenor_variants"] == {}
    assert out["sensitivities"] == {}
    assert out["fixed_debt_fx_stress"] == []
    assert out["fx_history"] == []
    assert out["fx_cagr_windows"] == []


def test_the_fixed_debt_stress_uses_the_blocks_operating_year() -> None:
    scenario = _basecase()
    scenario["financing_screening"]["fixed_debt_stress"]["operating_year"] = 3
    out = _run(scenario)
    assert {row["shock_operating_year"] for row in out["fixed_debt_fx_stress"]} == {3}


def test_a_tenor_variant_is_checked_against_its_own_ppa_term() -> None:
    """A variant's debt must end its lender tail before the variant's PPA does."""
    scenario = _basecase()
    scenario["financing_screening"]["tenor_variants"] = [
        {
            "id": "too_long",
            "dfi_tenor_years": 11,
            "ppa_years": 12,
            "lender_tail_years": 2,
        }
    ]
    with pytest.raises(ValueError, match="exceeds contracted revenue less lender tail"):
        _run(scenario)


# ----------------------------------------------------------- the single-site shim


def test_shim_re_exports_the_moved_functions() -> None:
    for name in (
        "annuity",
        "amortize_tranche",
        "compute_fx_cagr",
        "evaluate_dual_currency_screening",
        "size_debt_screening",
        "run_fixed_debt_stress",
        "compute_fx_history_metrics",
        "DEFAULT_F5_HOLD_CAVEAT",
    ):
        assert getattr(single_site, name) is getattr(fx, name), name


def test_single_site_run_needs_its_scenario_named() -> None:
    raw = _yaml(SITE_CONF)
    del raw["governed_scenario_path"]
    with pytest.raises(KeyError, match="governed_scenario_path"):
        single_site.run_comprehensive_screening(raw)
    assert not hasattr(single_site, "DEFAULT_GOVERNED_SCENARIO_PATH")


def test_single_site_script_output_is_byte_identical() -> None:
    """The single-site script prints exactly the bytes it printed before #1578 U4."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, str(SINGLE_SITE_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=True,
        timeout=300,
    )
    assert hashlib.sha256(proc.stdout).hexdigest() == SINGLE_SITE_STDOUT_SHA256


# --------------------------------------------------------------------- runner


def test_runner_refuses_a_wrong_schema_bad_method_or_no_scenario(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    raw = _yaml(METHOD_CONF)
    raw["scenario"] = str(LENDER_SCENARIO)
    raw["schema_version"] = "fx_tenor_screening_method_v0"
    with pytest.raises(ValueError, match="schema_version"):
        runner.run(raw)

    raw = _yaml(METHOD_CONF)
    raw["scenario"] = str(LENDER_SCENARIO)
    raw["method"]["extra"] = 1
    with pytest.raises(ValueError, match="method must hold exactly"):
        runner.run(raw)

    raw = _yaml(METHOD_CONF)
    with pytest.raises(ValueError, match="scenario=<path> is required"):
        runner.run(raw)

    listed = tmp_path / "list.yaml"
    listed.write_text("- not\n- a mapping\n", encoding="utf-8")
    raw["scenario"] = str(listed)
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        runner.run(raw)


@pytest.mark.parametrize(
    ("scenario", "status"),
    [
        ("scenarios/dutchbay_basecase_2025Q4.yaml", "completed"),
        ("scenarios/dutchbay_lendercase_2025Q4.yaml", "not_applicable"),
    ],
)
def test_runner_cli_runs_any_scenario(scenario: str, status: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, str(RUNNER), f"scenario={scenario}"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == status
    assert payload["scenario"] == scenario


def test_universal_module_and_runner_hold_no_site_name_or_path() -> None:
    for path in (MODULE, RUNNER, METHOD_CONF):
        source = path.read_text(encoding="utf-8").lower()
        for literal in (
            "blue_whale",
            "blue whale",
            "dutchbay_",
            "dutch bay",
            "kalpitiya",
            "mannar",
            "14-turbine",
            "scenarios/dutchbay",
        ):
            assert literal not in source, (path.name, literal)
