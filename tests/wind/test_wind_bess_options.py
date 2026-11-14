"""Tests for the wind-only battery options (analytics.wind.wind_bess_options and its Hydra CLI).

Oracles do not come from the code under test (TEST-01):

* PUCSL's closed form for the BESS component, priority - other / RTE, worked by hand from the
  Table 7 lines (47.08 - 18.00 / 0.90 = 27.08 for ground mounted, 53.28 - 23.58 / 0.90 = 27.08
  for floating), and the whole wind peak rate 20.80 / 0.90 + 27.08 + 4.93 / 0.90;
* a hand-worked dispatch on a constant-wind synthetic day (charge hours, export headroom and
  state of charge carried to the next day);
* the closed-form ramp triangle rated x minutes / 2 for the down-ramp firming energy;
* responsiveness of the engine (ARCH-04): a higher peak rate raises project NPV, a held battery
  lowers it, and a zero battery leaves the wind scenario's KPIs unchanged.

The NASA POWER reference is not in the repository, so the CLI test runs on a synthetic profile;
the committed summary is checked against the committed config and scenario bytes.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

import numpy as np
import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.wind import wind_bess_options as wbo

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "conf" / "blue_whale_wind_bess_options.yaml"
SCRIPT = REPO / "scripts" / "run_blue_whale_wind_bess_options_v14.py"
SUMMARY = REPO / "docs" / "blue_whale" / "wind_bess_options_summary.json"


def _cfg() -> Dict[str, Any]:
    raw: Dict[str, Any] = yaml.safe_load(CONFIG.read_text())
    raw.pop("defaults")
    raw.pop("hydra")
    return raw


def _scenario() -> Dict[str, Any]:
    scenario: Dict[str, Any] = yaml.safe_load((REPO / _cfg()["scenario"]).read_text())
    return scenario


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wind_bess_options_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stamps(days: int, year: int = 2026) -> List[str]:
    return [f"{year}01{d + 1:02d}{h:02d}" for d in range(days) for h in range(24)]


# ---------------------------------------------------------------------------
# Tariff
# ---------------------------------------------------------------------------
def test_bess_component_matches_pucsl_closed_form_for_both_lines() -> None:
    ground = wbo.bess_component([47.08, 3.02], [18.00, 2.72], 0.90)
    floating = wbo.bess_component([53.28, 4.36], [23.58, 3.92], 0.90)
    assert ground[0] == pytest.approx(27.08, abs=1e-9)
    assert floating[0] == pytest.approx(27.08, abs=1e-9)
    assert ground[1] == pytest.approx(3.02 - 2.72 / 0.9, abs=1e-12)


def test_derive_rates_builds_the_whole_wind_peak_rate_and_the_stacked_rate() -> None:
    rates = wbo.derive_rates(_cfg()["tariff"])
    assert rates["whole_wind_peak_rate"].total == pytest.approx(
        20.80 / 0.9 + 27.08 + (3.02 - 2.72 / 0.9) + 4.93 / 0.9, abs=1e-9
    )
    assert rates["whole_wind_peak_rate"].total == pytest.approx(55.67, abs=0.005)
    assert rates["stacked"].total == pytest.approx(25.73 + 27.08, abs=1e-9)
    assert rates["wind"].total == pytest.approx(25.73)


def test_derive_rates_refuses_disagreeing_table_7_lines() -> None:
    tariff = copy.deepcopy(_cfg()["tariff"])
    tariff["floating_priority_components"] = [53.40, 4.36]
    with pytest.raises(ValueError, match="disagree"):
        wbo.derive_rates(tariff)


def test_one_time_adjustment_is_the_weighted_index() -> None:
    depr = 1.05 / 1.025 - 1
    factor = wbo.one_time_adjustment_factor(
        {"lkr_usd": 0.70, "ccpi": 0.30}, lkr_usd_depreciation=depr, ccpi_inflation=0.05
    )
    assert factor == pytest.approx(0.70 * (1 + depr) + 0.30 * 1.05)
    assert 27.08 * factor == pytest.approx(27.95, abs=0.005)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def test_committed_config_validates() -> None:
    wbo.validate_config(_cfg())


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda c: c.update({"surprise": 1}), "unknown"),
        (lambda c: c.pop("window"), "missing"),
        (lambda c: c["battery"].update({"extra": 1}), "unknown"),
        (lambda c: c["revenue_bases"].update({"base": "invented"}), "revenue bases"),
        (lambda c: c["options"].append(dict(c["options"][0])), "unique"),
    ],
)
def test_config_refuses_missing_unknown_and_inconsistent_keys(
    mutate: Any, message: str
) -> None:
    cfg = _cfg()
    mutate(cfg)
    with pytest.raises(ValueError, match=message):
        wbo.validate_config(cfg)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
def test_calibrated_cp_hits_the_target_and_stays_below_betz() -> None:
    speeds = np.random.default_rng(7).rayleigh(7.0, 20_000)
    curve = {
        "rotor_diameter_m": 206.0,
        "air_density_kgm3": 1.15,
        "rated_mw": 9.5,
        "cut_in_ms": 3.0,
        "cut_out_ms": 25.0,
    }
    cp = wbo.calibrate_cp(speeds, 0.40, **curve)
    assert 0.0 < cp < 16.0 / 27.0
    assert wbo.generic_power_mw(speeds, cp=cp, **curve).mean() / 9.5 == pytest.approx(
        0.40, abs=1e-6
    )
    with pytest.raises(ValueError, match="Betz"):
        wbo.calibrate_cp(speeds, 0.99, **curve)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
def test_dispatch_matches_a_hand_worked_constant_wind_day() -> None:
    stamps = _stamps(2)
    wind = np.full(len(stamps), 5.0)
    kw: Dict[str, Any] = {
        "round_trip_efficiency": 0.8,
        "window_utc_hours": [12, 13, 14, 15],
    }
    free = wbo.dispatch(
        wind, stamps, power_mw=[1.0], energy_mwh=[4.0], export_cap_mw=None, **kw
    )
    # 4 MWh stored needs 5 MWh in (hours 0-4); 4 window hours at 1 MW empty it; it refills
    # after each window, so 3 fills of 5 MWh and 2 discharges of 4 (4 MWh left at the end).
    assert free.delivered_mwh[0] == pytest.approx(8.0)
    assert free.charged_mwh[0] == pytest.approx(15.0)
    capped = wbo.dispatch(
        wind, stamps, power_mw=[1.0], energy_mwh=[4.0], export_cap_mw=5.5, **kw
    )
    # Headroom 0.5 MW: 2 MWh out on day 1 (2 left), refill 2 MWh (2.5 in), 2 MWh out on day 2,
    # refill again.
    assert capped.delivered_mwh[0] == pytest.approx(4.0)
    assert capped.charged_mwh[0] == pytest.approx(5.0 + 2.5 + 2.5)


def test_dispatch_invariants_on_a_varying_profile() -> None:
    stamps = _stamps(28)
    wind = np.random.default_rng(3).uniform(0.0, 9.5, len(stamps))
    sizes = {"power_mw": [0.0, 0.5, 2.0, 10.0], "energy_mwh": [0.0, 2.0, 8.0, 40.0]}
    hours = [12, 13, 14, 15]
    res = wbo.dispatch(
        wind,
        stamps,
        round_trip_efficiency=0.85,
        window_utc_hours=hours,
        export_cap_mw=10.0,
        **sizes,
    )
    assert res.delivered_mwh[0] == 0.0 and res.charged_mwh[0] == 0.0
    # Conservation: delivered never exceeds what was stored.
    assert (res.delivered_mwh <= 0.85 * res.charged_mwh + 1e-9).all()
    # At most one full cycle a day, and never more than the headroom allows.
    assert (res.delivered_mwh <= 28 * np.asarray(sizes["energy_mwh"]) + 1e-9).all()
    window = np.isin([int(s[8:10]) for s in stamps], hours)
    assert (res.delivered_mwh <= np.maximum(10.0 - wind[window], 0).sum() + 1e-9).all()
    # A per-size RTE gives the same answer as one call per RTE.
    both = wbo.dispatch(
        wind,
        stamps,
        power_mw=[2.0, 2.0],
        energy_mwh=[8.0, 8.0],
        round_trip_efficiency=[0.80, 0.90],
        window_utc_hours=hours,
        export_cap_mw=None,
    )
    for i, rte in enumerate((0.80, 0.90)):
        one = wbo.dispatch(
            wind,
            stamps,
            power_mw=[2.0],
            energy_mwh=[8.0],
            round_trip_efficiency=rte,
            window_utc_hours=hours,
            export_cap_mw=None,
        )
        assert both.delivered_mwh[i] == pytest.approx(one.delivered_mwh[0])


def test_down_ramp_firming_is_the_ramp_triangle() -> None:
    share = 10.0 * 9.5 / 99.5
    firm = wbo.down_ramp_firming(9.5, share)
    assert firm["minutes"] == pytest.approx(9.95)
    assert firm["energy_mwh"] == pytest.approx(9.5 * 9.95 / 2 / 60)


def test_firming_unit_prices_follow_the_hand_build_up() -> None:
    supplier = _cfg()["down_ramp"]["supplier"]
    prices = wbo.firming_unit_prices(
        supplier, power_mw=9.5, energy_mwh=0.8, all_in_usd_per_contracted_kwh=140.0
    )
    dc_kwh = 0.8 / supplier["usable_per_dc"] * 1000
    cif = (
        supplier["ac_skid_usd"]
        + supplier["ems_usd"]
        + dc_kwh * supplier["dc_block_usd_per_dc_kwh"]
    ) * (1 + supplier["install_transport_share"])
    unit = prices["power_heavy_cells_x1"]
    assert unit["cif_usd"] == pytest.approx(cif)
    assert unit["all_in_usd"] == pytest.approx(
        cif * 140.0 / supplier["cif_usd_per_contracted_kwh"]
    )
    assert unit["om_usd_per_year"] == pytest.approx(cif * 0.02)
    assert prices["power_heavy_cells_x3"]["cif_usd"] > unit["cif_usd"]
    block = prices["smallest_block"]
    assert block["cif_usd"] == pytest.approx(20_101 * supplier["offer_usd_per_dc_kwh"])
    with pytest.raises(ValueError, match="one skid"):
        wbo.firming_unit_prices(
            supplier, power_mw=12.0, energy_mwh=0.8, all_in_usd_per_contracted_kwh=140.0
        )


# ---------------------------------------------------------------------------
# Engine mapping (ARCH-04)
# ---------------------------------------------------------------------------
def _with(scenario: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    cfg = _cfg()
    rates = wbo.derive_rates(cfg["tariff"])
    base: Dict[str, Any] = {
        "power_mw": 0.5,
        "energy_mwh": 2.0,
        "operation": "cycled",
        "usd_per_kwh": 140.74,
        "om_usd_per_dc_kwh_year": 1.8,
        "dc_per_nominal": 1.1,
        "round_trip_efficiency": 0.85,
        "delivered_mwh": 700.0,
        "charged_mwh": 830.0,
        "peak_rate": rates["whole_wind_peak_rate"],
        "wind_rate": rates["wind"],
        "contract_years": 15,
    }
    base.update(kw)
    return wbo.scenario_with_battery(scenario, **base)


def _engine_project_value(s: Dict[str, Any]) -> float:
    return float(evaluate_with_overrides(raw_config=s, overrides={})["project_npv"])


def test_scenario_mapping_books_capex_loss_and_premium() -> None:
    scenario = _scenario()
    s = _with(scenario)
    cf0 = float(scenario["generation"]["technologies"]["wind"]["capacity_factor"])
    cf1 = float(s["generation"]["technologies"]["wind"]["capacity_factor"])
    assert cf0 - cf1 == pytest.approx(130.0 / (9.5 * 8760))
    assert s["capex"]["usd_total"] - scenario["capex"]["usd_total"] == pytest.approx(
        2000 * 140.74
    )
    rev = s["generation"]["technologies"]["bess_1"]["revenue"]
    assert rev["tariff_lkr_per_kwh"] == pytest.approx(55.6667 - 25.73, abs=1e-3)
    assert rev["cycles_per_year"] == pytest.approx(700.0 / (2.0 * 0.85))
    held = _with(scenario, operation="held")["generation"]["technologies"]["bess_1"][
        "revenue"
    ]
    assert held["tariff_lkr_per_kwh"] == 0.0


def test_engine_responds_to_the_battery_and_the_rate() -> None:
    scenario = _scenario()
    wind_only = _engine_project_value(scenario)
    assert _engine_project_value(_with(scenario, power_mw=0.0)) == pytest.approx(wind_only)
    assert _engine_project_value(_with(scenario, operation="held")) < wind_only
    low = _engine_project_value(_with(scenario))
    high = _engine_project_value(_with(scenario, peak_rate=wbo.PeakRate(70.0, 5.48)))
    assert high > low


# ---------------------------------------------------------------------------
# CLI and committed summary
# ---------------------------------------------------------------------------
def test_cli_runs_end_to_end_on_a_synthetic_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _cli()
    stamps = _stamps(14)
    wind = np.clip(np.random.default_rng(11).normal(4.6, 3.0, len(stamps)), 0.0, 9.2)

    def fake_profile(cfg: Any, scenario: Any) -> Dict[str, Any]:
        return {
            "stamps": stamps,
            "poi_mw": wind,
            "window_wind_mwh": 7000.0,
            "checks": {},
        }

    monkeypatch.setattr(cli, "build_profile", fake_profile)
    cfg = _cfg()
    cfg["options"] = [
        o for o in cfg["options"] if o["name"] in ("held_0_5_0_5", "cycled_0_5_2")
    ]
    cfg["monte_carlo"] |= {"n_trials": 4, "rte_grid": [0.85]}
    out = cli.json_clean(cli.run(cfg))
    json.dumps(out, allow_nan=False)
    row = out["options"]["cycled_0_5_2"]
    assert row["fits_reading_A_turbine_plus_battery_le_limit"] is True
    for reading in ("B", "C"):
        bases = row["readings"][reading]["bases"]
        assert set(bases) == set(wbo.REVENUE_BASES)
        assert (
            bases["whole_wind_peak_rate"]["delta_project_npv_vs_wind_only"]
            > bases["stacked"]["delta_project_npv_vs_wind_only"]
        )
    firming = out["down_ramp_illustrative"]["firming_unit_base_basis"]
    for unit in firming.values():
        assert unit["kpis"]["delta_project_npv_vs_wind_only"] < 0
    assert firming["smallest_block_cycled|C"]["delivered_mwh_per_year"] > 0


def test_committed_summary_pins_the_committed_inputs() -> None:
    summary = json.loads(SUMMARY.read_text())
    assert summary["config_sha256"] == hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    scenario_path = REPO / _cfg()["scenario"]
    assert (
        summary["scenario_sha256"]
        == hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    )
    assert summary["revenue_bases"]["base"] == "whole_wind_peak_rate"
    # No private price is committed for the down-ramp unit.
    firming = summary["down_ramp_illustrative"]["firming_unit_base_basis"]
    assert firming["power_heavy_cells_x1"]["energy_mwh"] == pytest.approx(
        9.5 * 9.95 / 2 / 60
    )
    wind_only = evaluate_with_overrides(raw_config=_scenario(), overrides={})
    assert summary["wind_only"]["project_npv"] == pytest.approx(
        float(wind_only["project_npv"]), rel=1e-9
    )
    assert math.isclose(
        summary["profile"]["gross_cf"],
        summary["profile"]["target_gross_cf"],
        abs_tol=1e-6,
    )
