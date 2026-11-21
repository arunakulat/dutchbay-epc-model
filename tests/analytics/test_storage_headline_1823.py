"""A scenario's held battery option in its headline KPIs (#1823).

``storage_options.headline_option`` names one held option of the wind battery options block.
The evaluation then carries that battery (capex and O&M only, no storage tariff), built by the
same ``scenario_with_battery`` the options analysis uses, so the headline KPIs equal that
analysis's committed figures for the option. A scenario without the declaration evaluates
exactly as before, and the options analysis still compares every option with wind-only.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides, evaluated_scenario_config
from analytics.site_analysis_blocks import resolve_site_analysis_block
from analytics.storage_headline import (
    APPLIED_KEY,
    HEADLINE_KEY,
    TARIFF_BASIS,
    apply_headline_storage_option,
    declares_headline_option,
    strip_headline_option,
)

REPO = Path(__file__).resolve().parents[2]
WIND = REPO / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
BASE = REPO / "scenarios" / "dutchbay_basecase_2025Q4.yaml"
SUMMARY = REPO / "docs" / "blue_whale" / "wind_bess_options_summary.json"
KPI_KEYS = (
    "project_irr",
    "equity_irr",
    "project_npv",
    "equity_npv",
    "min_dscr",
    "discount_rate_used",
)


def _load(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def summary() -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return data


def test_the_committed_scenario_names_the_recommended_held_option(
    summary: Dict[str, Any],
) -> None:
    block = _load(WIND)["storage_options"]
    assert block[HEADLINE_KEY] == summary["recommended_option_reading_A"]
    option = summary["options"][block[HEADLINE_KEY]]
    assert option["operation"] == "held"
    assert option["fits_reading_A_turbine_plus_battery_le_limit"] is True


def test_headline_kpis_equal_the_options_analysis_figures(
    summary: Dict[str, Any],
) -> None:
    """The oracle: the committed options summary's figures for the held option."""
    got = evaluate_with_overrides(str(WIND), overrides={})
    name = _load(WIND)["storage_options"][HEADLINE_KEY]
    for reading in summary["options"][name]["readings"].values():
        want = reading["bases"]["whole_wind_peak_rate"]
        for key in KPI_KEYS:
            assert got[key] == pytest.approx(want[key], rel=1e-12), key


def test_the_options_analysis_still_compares_with_wind_only(
    summary: Dict[str, Any],
) -> None:
    wind_only = evaluate_with_overrides(
        raw_config=strip_headline_option(_load(WIND)), overrides={}
    )
    for key in KPI_KEYS:
        assert wind_only[key] == pytest.approx(summary["wind_only"][key], rel=1e-12)
    headline = evaluate_with_overrides(str(WIND), overrides={})
    assert headline["project_npv"] < wind_only["project_npv"]


def test_a_scenario_without_the_declaration_is_unchanged() -> None:
    base = _load(BASE)
    assert not declares_headline_option(base)
    assert apply_headline_storage_option(base) == base
    no_headline = strip_headline_option(_load(WIND))
    assert apply_headline_storage_option(no_headline) == no_headline


def test_the_battery_is_added_once_and_recorded() -> None:
    raw = _load(WIND)
    block = resolve_site_analysis_block(raw, "storage_options")
    assert block is not None
    option = next(
        o
        for o in block["sizes"]["options"]
        if o["id"] == raw["storage_options"][HEADLINE_KEY]
    )
    battery = block["technology"]["battery"]
    capex = option["energy_mwh"] * 1000.0 * battery["usd_per_kwh"]["mode"]
    om = (
        option["energy_mwh"]
        * 1000.0
        * battery["dc_per_nominal"]
        * battery["om_usd_per_dc_kwh_year"]
    )

    once = apply_headline_storage_option(raw)
    assert apply_headline_storage_option(once) == once
    assert once["capex"]["usd_total"] == pytest.approx(
        raw["capex"]["usd_total"] + capex
    )
    assert once["opex"]["usd_per_year"] == pytest.approx(
        raw["opex"]["usd_per_year"] + om
    )
    bess = once["generation"]["technologies"]["bess_1"]
    assert bess["capex_usd"] == pytest.approx(capex)
    assert bess["revenue"]["tariff_lkr_per_kwh"] == 0.0
    assert (
        once["generation"]["technologies"]["wind"]["capacity_factor"]
        == raw["generation"]["technologies"]["wind"]["capacity_factor"]
    )
    record = once["storage_options"][APPLIED_KEY]
    assert HEADLINE_KEY not in once["storage_options"]
    assert record["capex_usd"] == pytest.approx(capex)
    assert record["om_usd_per_year"] == pytest.approx(om)
    assert record["combined_capacity_mw"] <= record["export_limit_mw"]
    assert record["tariff_basis"] == TARIFF_BASIS
    # The input is not mutated, and the applied form still validates.
    assert HEADLINE_KEY in raw["storage_options"]
    assert resolve_site_analysis_block(once, "storage_options") is not None
    with pytest.raises(ValueError, match="already carries the battery"):
        strip_headline_option(once)


def test_the_reload_gateway_and_batch_surface_carry_the_battery() -> None:
    raw = _load(WIND)
    evaluated = evaluated_scenario_config(raw)
    assert "bess_1" in evaluated["generation"]["technologies"]
    assert evaluated_scenario_config(evaluated) == evaluated

    from analytics.scenario_analytics import ScenarioAnalytics

    result = ScenarioAnalytics(scenarios_dir=WIND.parent)._run_single(WIND)
    assert result.fail_reason is None
    full = evaluate_with_overrides(str(WIND), overrides={}, return_full_result=True)
    assert isinstance(full, dict)
    assert result.run_manifest is not None
    assert result.run_manifest["config_sha256"] == full["run_manifest"]["config_sha256"]


def _with_headline(name: str) -> Dict[str, Any]:
    raw = copy.deepcopy(_load(WIND))
    raw["storage_options"][HEADLINE_KEY] = name
    return raw


def test_a_cycled_or_unknown_option_is_refused() -> None:
    raw = _load(WIND)
    cycled = next(
        o["id"]
        for o in raw["storage_options"]["sizes"]["options"]
        if o["operation"] == "cycled"
    )
    with pytest.raises(ValueError, match="must be held"):
        apply_headline_storage_option(_with_headline(cycled))
    with pytest.raises(ValueError, match="no option has id"):
        apply_headline_storage_option(_with_headline("no_such_option"))
    both = _load(WIND)
    both["storage_options"][APPLIED_KEY] = {"id": "x"}
    with pytest.raises(ValueError, match="exclusive"):
        apply_headline_storage_option(both)


def test_a_battery_above_the_export_limit_is_refused() -> None:
    raw = _load(WIND)
    raw["storage_options"]["grid_limits"]["export_limit_mw"] = 9.75
    with pytest.raises(ValueError, match="above grid_limits.export_limit_mw"):
        apply_headline_storage_option(raw)


def test_capex_it_cannot_add_to_is_refused() -> None:
    native = _load(WIND)
    native["capex"]["input"] = {"currency": "LKR", "amount": 1.0}
    with pytest.raises(ValueError, match="native-currency capex.input"):
        apply_headline_storage_option(native)
    alias = _load(WIND)
    alias["capex"].pop("usd_total")
    with pytest.raises(ValueError, match="capex.usd_total"):
        apply_headline_storage_option(alias)


def test_undeclared_per_kw_figures_stay_undeclared() -> None:
    raw = _load(WIND)
    raw["capex"].pop("capex_per_kw_usd")
    raw["opex"].pop("opex_per_kw_yr_usd")
    out = apply_headline_storage_option(raw)
    assert "capex_per_kw_usd" not in out["capex"]
    assert "opex_per_kw_yr_usd" not in out["opex"]
    declared = apply_headline_storage_option(_load(WIND))
    assert declared["capex"]["capex_per_kw_usd"] == pytest.approx(
        declared["capex"]["usd_total"]
        / (declared["generation"]["technologies"]["wind"]["capacity_mw"] * 1000.0)
    )
