"""Tests for the wind-only battery options (analytics.wind.wind_bess_options and its Hydra CLI).

Oracles do not come from the code under test (TEST-01):

* PUCSL's closed form for the BESS component, priority - other / RTE, worked by hand from the
  Table 7 lines (47.08 - 18.00 / 0.90 = 27.08 for ground mounted, 53.28 - 23.58 / 0.90 = 27.08
  for floating), and the whole wind peak rate 20.80 / 0.90 + 27.08 + 4.93 / 0.90;
* a hand-worked dispatch on a constant-wind synthetic day (charge hours, export headroom and
  state of charge carried to the next day);
* hand-worked dispatches that bind the turbine's output on charge and hold a black-start
  reserve on discharge;
* the closed-form ramp triangle rated x minutes / 2 for the down-ramp firming energy;
* a hand-built pre-tax cash flow for the battery's own view, and a hand-built supplier price;
* responsiveness of the engine (ARCH-04): a higher peak rate raises project NPV, a held battery
  lowers it, and a zero battery leaves the wind scenario's KPIs unchanged.

The NASA POWER reference is not in the repository, so the profile tests run on synthetic files
(pinned with an independently computed digest) and the CLI test on a synthetic profile. The
committed summary is checked against the committed config and scenario bytes, and one option's
committed figures are recomputed through the engine from the committed energies.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional

import numpy as np
import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.storage_headline import strip_headline_option
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
    """The options analysis's wind-only case: the scenario without its headline battery."""
    scenario: Dict[str, Any] = strip_headline_option(
        yaml.safe_load((REPO / _cfg()["scenario"]).read_text())
    )
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
    # Stacked keeps the component's escalable remainder, as the whole rate does.
    assert rates["stacked"].total == pytest.approx(
        25.73 + 27.08 + (3.02 - 2.72 / 0.9), abs=1e-9
    )
    assert rates["stacked"].escalable == pytest.approx(4.93 + 3.02 - 2.72 / 0.9)
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
        (lambda c: c["down_ramp"]["supplier"].update({"extra": 1}), "supplier"),
        (lambda c: c["down_ramp"]["supplier"].pop("usable_per_dc"), "supplier"),
        (lambda c: c["battery"]["usd_per_kwh"].update({"p99": 1.0}), "usd_per_kwh"),
        (lambda c: c["monte_carlo"]["rte"].pop("high"), "monte_carlo.rte"),
        (lambda c: c["monte_carlo"]["residual_fade"].update({"x": 0}), "residual_fade"),
        (
            lambda c: c["tariff"]["one_time_adjustment_weights"].update({"usd": 0}),
            "one_time_adjustment_weights",
        ),
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


def test_generic_curve_is_zero_outside_cut_in_and_cut_out() -> None:
    curve = {
        "rotor_diameter_m": 100.0,
        "air_density_kgm3": 1.2,
        "rated_mw": 3.0,
        "cut_in_ms": 3.0,
        "cut_out_ms": 25.0,
    }
    speeds = np.array([2.9, 4.0, 20.0, 25.1])
    out = wbo.generic_power_mw(speeds, cp=0.4, **curve)
    area = math.pi * 50.0**2
    assert out[0] == 0.0 and out[3] == 0.0
    assert out[1] == pytest.approx(0.5 * 1.2 * area * 0.4 * 4.0**3 / 1e6)
    assert out[2] == 3.0


def _digest(block: Dict[str, Any]) -> str:
    text = json.dumps(block, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _write_power_year(
    root: Path, year: int, speeds: List[float], lon: float, lat: float
) -> str:
    block = {
        "WS50M": {f"{year}0101{h:02d}": v for h, v in enumerate(speeds)},
    }
    doc = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat, 10.0]},
        "properties": {"parameter": block},
    }
    (root / "pt").mkdir(exist_ok=True)
    (root / "pt" / f"wsd_{year}.json").write_text(json.dumps(doc))
    return _digest(block)


def test_reference_loader_checks_pin_point_and_fill(tmp_path: Path) -> None:
    pins = {
        "2015": _write_power_year(tmp_path, 2015, [5.0, 6.0], 79.75, 8.29),
        "2016": _write_power_year(tmp_path, 2016, [7.0, 8.0], 79.75, 8.29),
    }
    kw: Dict[str, Any] = {
        "subdir": "pt",
        "first_year": 2015,
        "last_year": 2016,
        "latitude_deg_n": 8.29,
        "longitude_deg_e": 79.75,
    }
    stamps, ws = wbo.load_reference_ws50(tmp_path, pins=pins, **kw)
    assert stamps == ["2015010100", "2015010101", "2016010100", "2016010101"]
    assert ws.tolist() == [5.0, 6.0, 7.0, 8.0]
    with pytest.raises(ValueError, match="pin"):
        wbo.load_reference_ws50(tmp_path, pins=pins | {"2016": "0" * 64}, **kw)
    with pytest.raises(ValueError, match="point"):
        wbo.load_reference_ws50(tmp_path, pins=pins, **(kw | {"latitude_deg_n": 8.40}))
    pins["2016"] = _write_power_year(tmp_path, 2016, [7.0, -999.0], 79.75, 8.29)
    with pytest.raises(ValueError, match="fill"):
        wbo.load_reference_ws50(tmp_path, pins=pins, **kw)


def _synthetic_profile_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Dict[str, Any]:
    """A pinned two-year reference, its config and a transfer summary, all in tmp_path."""
    rng = np.random.default_rng(5)
    pins: Dict[str, str] = {}
    root = tmp_path / "power"
    root.mkdir()
    for year in (2015, 2016):
        speeds = [round(float(v), 2) for v in rng.rayleigh(6.0, 24)]
        block = {"WS50M": {f"{year}0101{h:02d}": v for h, v in enumerate(speeds)}}
        doc = {
            "geometry": {"coordinates": [79.75, 8.29, 10.0]},
            "properties": {"parameter": block},
        }
        (root / "pt").mkdir(exist_ok=True)
        (root / "pt" / f"wsd_{year}.json").write_text(json.dumps(doc))
        pins[str(year)] = _digest(block)
    ref = {
        "reference": {
            "dir_env": "WIND_BESS_TEST_POWER_DIR",
            "height_m": 50.0,
            "first_year": 2015,
            "last_year": 2016,
            "points": {
                "turbine": {
                    "subdir": "pt",
                    "latitude_deg_n": 8.29,
                    "longitude_deg_e": 79.75,
                    "parameter_sha256": pins,
                }
            },
        }
    }
    ref_path = tmp_path / "ref.yaml"
    ref_path.write_text(yaml.safe_dump(ref))
    summary = {
        "shear": {"extrapolation": {"alpha_all": 0.2}},
        "long_term_130m": {"mean_speed_ms": 8.0},
        "yield": {"gross_capacity_factor": 0.45, "total_loss_pct": 12.0},
    }
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary))
    monkeypatch.setenv("WIND_BESS_TEST_POWER_DIR", str(root))
    cfg = _cfg()
    cfg["profile"] |= {
        "reference_config": str(ref_path),
        "transfer_summary": str(summary_path),
    }
    scenario = _scenario()
    scenario["generation"]["technologies"]["wind"]["capacity_factor"] = 0.45 * 0.88
    return {"cfg": cfg, "scenario": scenario}


def test_profile_window_exports_are_net_and_the_cf_guard_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    inputs = _synthetic_profile_inputs(tmp_path, monkeypatch)
    prof = cli.build_profile(inputs["cfg"], inputs["scenario"])
    assert prof["checks"]["gross_cf"] == pytest.approx(0.45, abs=1e-6)
    window = np.isin([int(s[8:10]) for s in prof["stamps"]], [12, 13, 14, 15])
    poi_window_per_year = float(prof["poi_mw"][window].sum()) / 2.0
    # Window exports carry the total loss (time and power); the POI profile only the power
    # losses (electrical 2%, other 1%).
    assert prof["window_wind_mwh"] / poi_window_per_year == pytest.approx(
        (1 - 0.12) / (0.98 * 0.99)
    )
    inputs["scenario"]["generation"]["technologies"]["wind"]["capacity_factor"] += 0.01
    with pytest.raises(ValueError, match="reproduce"):
        cli.build_profile(inputs["cfg"], inputs["scenario"])


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


def test_dispatch_charge_is_limited_by_the_turbine() -> None:
    stamps = _stamps(2)
    wind = np.full(len(stamps), 0.3)
    res = wbo.dispatch(
        wind,
        stamps,
        power_mw=[1.0],
        energy_mwh=[4.0],
        round_trip_efficiency=0.8,
        window_utc_hours=[12, 13, 14, 15],
        export_cap_mw=None,
    )
    # Day 1: hours 0-11 take 0.3 MW in (3.6 in, 2.88 stored), all of it out in the window;
    # hours 16-23 take 2.4 in (1.92 stored). Day 2: 2.6 in fills it to 4 by hour 9, 4 out in
    # the window, then 2.4 in again.
    assert res.delivered_mwh[0] == pytest.approx(2.88 + 4.0)
    assert res.charged_mwh[0] == pytest.approx(3.6 + 2.4 + 2.6 + 2.4)


def test_dispatch_never_draws_below_the_black_start_reserve() -> None:
    stamps = _stamps(2)
    wind = np.full(len(stamps), 5.0)
    res = wbo.dispatch(
        wind,
        stamps,
        power_mw=[1.0],
        energy_mwh=[4.0],
        round_trip_efficiency=0.8,
        window_utc_hours=[12, 13, 14, 15],
        export_cap_mw=None,
        reserve_mwh=1.0,
    )
    # Fill 4 (5 in); 3 out each window, leaving the 1 MWh reserve; refill 3 (3.75 in) twice.
    assert res.delivered_mwh[0] == pytest.approx(6.0)
    assert res.charged_mwh[0] == pytest.approx(5.0 + 3.75 + 3.75)
    many = _stamps(28)
    varied = np.random.default_rng(9).uniform(0.0, 9.5, len(many))
    sizes = {"power_mw": [0.5, 2.0], "energy_mwh": [2.0, 8.0]}
    held = wbo.dispatch(
        varied,
        many,
        round_trip_efficiency=0.85,
        window_utc_hours=[12, 13, 14, 15],
        export_cap_mw=None,
        reserve_mwh=[0.5, 3.0],
        **sizes,
    )
    assert (held.delivered_mwh <= 28 * (np.array([2.0, 8.0]) - [0.5, 3.0]) + 1e-9).all()
    with pytest.raises(ValueError, match="reserve"):
        wbo.dispatch(
            varied,
            many,
            round_trip_efficiency=0.85,
            window_utc_hours=[12],
            export_cap_mw=None,
            reserve_mwh=2.5,
            power_mw=[0.5],
            energy_mwh=[2.0],
        )


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
        supplier, power_mw=9.5, energy_mwh=0.8, all_in_usd_per_kwh_mode=140.0
    )
    dc_kwh = 0.8 / supplier["usable_per_dc"] * 1000
    cif = (
        supplier["ac_skid_usd"]
        + supplier["ems_usd"]
        + dc_kwh * supplier["dc_block_usd_per_dc_kwh"]
    ) * (1 + supplier["install_transport_share"])
    unit = prices["power_heavy_cells_x1"]
    assert unit["cif_usd"] == pytest.approx(cif)
    assert unit["all_in_usd"] == pytest.approx(cif * 140.0 / (90.0009 / 0.91))
    assert unit["om_usd_per_year"] == pytest.approx(cif * 0.02)
    assert prices["power_heavy_cells_x3"]["cif_usd"] > unit["cif_usd"]
    block = prices["smallest_block"]
    assert supplier["smallest_block_dc_mwh"] == 20.0
    assert supplier["usable_per_dc"] == 0.91
    assert block["cif_usd"] == pytest.approx(20_000 * supplier["offer_usd_per_dc_kwh"])
    assert block["energy_mwh"] == pytest.approx(18.2)
    assert block["om_usd_per_year"] == pytest.approx(block["cif_usd"] * 0.02)
    with pytest.raises(ValueError, match="one skid"):
        wbo.firming_unit_prices(
            supplier, power_mw=12.0, energy_mwh=0.8, all_in_usd_per_kwh_mode=140.0
        )


def test_bottom_up_price_follows_the_hand_build_up() -> None:
    supplier = _cfg()["down_ramp"]["supplier"]
    out = wbo.bottom_up_price(
        supplier, power_mw=0.5, energy_mwh=0.5, all_in_usd_per_kwh_mode=140.0
    )
    # Skid pro rata by power, the EMS once per site, the DC energy at the offer's DC rate.
    cif = (
        supplier["ac_skid_usd"] * 0.5 / supplier["ac_skid_mw"]
        + supplier["ems_usd"]
        + 0.5 / supplier["usable_per_dc"] * 1000 * supplier["dc_block_usd_per_dc_kwh"]
    ) * (1 + supplier["install_transport_share"])
    assert out["cif_usd"] == pytest.approx(cif)
    assert out["all_in_usd"] == pytest.approx(cif * 140.0 / (90.0009 / 0.91))
    assert out["all_in_usd_per_kwh"] == pytest.approx(out["all_in_usd"] / 500.0)
    # A short unit carries the per-site and power cost, so it costs more per kWh than the
    # flat mode; a long one less.
    assert out["all_in_usd_per_kwh"] > 140.0
    long = wbo.bottom_up_price(
        supplier, power_mw=10.0, energy_mwh=40.0, all_in_usd_per_kwh_mode=140.0
    )
    assert long["all_in_usd_per_kwh"] < 140.0
    with pytest.raises(ValueError, match="positive"):
        wbo.bottom_up_price(
            supplier, power_mw=0.0, energy_mwh=0.5, all_in_usd_per_kwh_mode=140.0
        )


def test_battery_pretax_matches_a_hand_built_cash_flow() -> None:
    out = wbo.battery_pretax(
        energy_mwh=1.0,
        usd_per_kwh=100.0,
        om_usd_per_dc_kwh_year=2.0,
        dc_per_nominal=1.0,
        delivered_mwh=100.0,
        charged_mwh=125.0,
        peak_rate=wbo.PeakRate(50.0, 0.0),
        wind_rate=wbo.PeakRate(20.0, 0.0),
        contract_years=2,
        term_years=3,
        lkr_per_usd=100.0,
        index_rate=0.0,
        pre_operation_years=0,
        opex_escalation=0.0,
        capex_price_factor=1.05,
        construction_years=1,
        discount_rate=0.10,
    )
    # Contract years: (100 x 50 - 125 x 20) MWh-LKR x 1000 / 100 = 25,000, less O&M 2,000.
    # Year 3 (after the contract): (100 x 20 - 125 x 20) x 10 = -5,000, less 2,000.
    # Capex is priced at the draw by the engine's price-year factor: 100,000 x 1.05.
    flows = [-105_000.0, 23_000.0, 23_000.0, -7_000.0]
    assert out["capex_usd_at_draw"] == pytest.approx(105_000.0)
    assert out["year1_net_usd"] == pytest.approx(23_000.0)
    assert out["npv_usd"] == pytest.approx(
        sum(f / 1.1**t for t, f in enumerate(flows)), abs=1e-6
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
    # Escalable premium: the whole rate's escalable part less the wind tariff's 4.93.
    assert rev["escalable_om_lkr_per_kwh"] == pytest.approx(
        4.93 / 0.9 + (3.02 - 2.72 / 0.9) - 4.93, abs=1e-9
    )
    assert rev["contract_years"] == 15
    # O&M: 2 MWh x 1000 x 1.1 DC x 1.80 USD per DC kWh-year, in the opex total too.
    om = 2000 * 1.1 * 1.8
    assert s["opex"]["usd_per_year"] - scenario["opex"][
        "usd_per_year"
    ] == pytest.approx(om)
    assert s["opex"]["currency_split"]["components"][-1] == {
        "name": "bess_om",
        "usd_per_year": pytest.approx(om),
        "usd_share": 0.0,
    }
    held_s = _with(scenario, operation="held")
    held = held_s["generation"]["technologies"]["bess_1"]["revenue"]
    assert held["tariff_lkr_per_kwh"] == 0.0
    # A held battery is never cycled, whatever energies are passed: no round-trip loss.
    assert held_s["generation"]["technologies"]["wind"]["capacity_factor"] == cf0
    exports = _with(scenario, window_wind_mwh=7000.0)["generation"]["technologies"][
        "bess_1"
    ]["revenue"]
    assert exports["cycles_per_year"] == pytest.approx((700.0 + 7000.0) / (2.0 * 0.85))
    with pytest.raises(ValueError, match="below"):
        _with(scenario, peak_rate=wbo.PeakRate(10.0, 0.0))


def test_engine_responds_to_the_battery_and_the_rate() -> None:
    scenario = _scenario()
    wind_only = _engine_project_value(scenario)
    assert _engine_project_value(_with(scenario, power_mw=0.0)) == pytest.approx(
        wind_only
    )
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
    # A tiny held battery above 0.5 MW: the cheapest option, but outside reading A, so it
    # must never be the recommendation.
    cfg["options"].append(
        {
            "name": "held_0_6_0_1",
            "power_mw": 0.6,
            "energy_mwh": 0.1,
            "operation": "held",
        }
    )
    cfg["monte_carlo"] |= {"n_trials": 8, "rte_grid": [0.85]}
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
    # The CLI prices the battery's own pre-tax capex at the engine's price-year factor.
    from finance.capex_price_basis import capex_escalation_factor

    basis = capex_escalation_factor(_scenario())
    assert basis is not None and float(basis["factor"]) != 1.0
    mode = cfg["battery"]["usd_per_kwh"]["mode"]
    for name, opt in out["options"].items():
        capex = opt["readings"]["B"]["battery_pretax_base_basis"]["capex_usd_at_draw"]
        assert capex == pytest.approx(
            opt["energy_mwh"] * 1000.0 * mode * float(basis["factor"]), rel=1e-12
        ), name
    firming = out["down_ramp_illustrative"]["firming_unit_base_basis"]
    for unit in firming.values():
        assert unit["kpis"]["delta_project_npv_vs_wind_only"] < 0
    assert firming["smallest_block_cycled|C"]["delivered_mwh_per_year"] > 0
    # The cycled block keeps the black-start reserve plus the down-ramp energy.
    assert firming["smallest_block_cycled|C"]["reserve_mwh"] == pytest.approx(
        0.5 + 9.5 * 9.95 / 2 / 60
    )
    block_reserve = 0.5 + 9.5 * 9.95 / 2 / 60
    held_back = wbo.dispatch(
        wind,
        stamps,
        power_mw=[9.5],
        energy_mwh=[18.2],
        round_trip_efficiency=0.85,
        window_utc_hours=[12, 13, 14, 15],
        export_cap_mw=None,
        reserve_mwh=block_reserve,
    )
    assert firming["smallest_block_cycled|C"][
        "delivered_mwh_per_year"
    ] == pytest.approx(float(held_back.delivered_mwh[0]))
    for reading in ("B", "C"):
        rr = row["readings"][reading]
        assert rr["black_start_reserve_mwh"] == 0.5
        assert rr["delivered_mwh_per_year"] <= 14 * (2.0 - 0.5) + 1e-9
        assert (
            rr["without_reserve_base_basis"]["delivered_mwh_per_year"]
            >= rr["delivered_mwh_per_year"]
        )
    # The recommendation is the best base-basis option that fits reading A, read off the rows.
    fitting = {
        name: r["readings"]["B"]["bases"]["whole_wind_peak_rate"][
            "delta_project_npv_vs_wind_only"
        ]
        for name, r in out["options"].items()
        if r["fits_reading_A_turbine_plus_battery_le_limit"]
    }
    assert out["recommended_option_reading_A"] == max(fitting, key=fitting.__getitem__)
    cheapest = out["options"]["held_0_6_0_1"]
    assert cheapest["fits_reading_A_turbine_plus_battery_le_limit"] is False
    assert cheapest["readings"]["B"]["bases"]["whole_wind_peak_rate"][
        "delta_project_npv_vs_wind_only"
    ] > max(fitting.values())
    # The pinned column re-runs the engine with the discount rate held at wind-only's.
    rate = out["wind_only"]["discount_rate_used"]
    pinned = {"wacc.drives_discount_rate": False, "returns.project_discount_rate": rate}
    for name in ("held_0_5_0_5", "cycled_0_5_2"):
        rr = out["options"][name]["readings"]["B"]
        value = _engine_project_value(
            _option_scenario(out["options"][name], rr, overrides=pinned)
        )
        assert value - out["wind_only"]["project_npv"] == pytest.approx(
            rr["pinned_discount_rate_delta_project_npv_base_basis"], rel=1e-9
        )
        assert rr["pinned_discount_rate_delta_project_npv_base_basis"] != pytest.approx(
            rr["bases"]["whole_wind_peak_rate"]["delta_project_npv_vs_wind_only"]
        )
    # Every Monte Carlo trial is measured against wind-only at the same wind yield, so a held
    # battery (capex and O&M only) never beats it.
    held_mc = out["monte_carlo_base_basis"]["held_0_5_0_5"][
        "delta_project_npv_vs_wind_only"
    ]
    assert held_mc["share_positive"] == 0.0 and held_mc["max"] < 0.0


def test_committed_summary_pins_the_committed_inputs() -> None:
    summary = json.loads(SUMMARY.read_text())
    assert summary["config_sha256"] == hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    scenario_path = REPO / _cfg()["scenario"]
    assert (
        summary["scenario_sha256"]
        == hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    )
    assert summary["revenue_bases"]["base"] == "whole_wind_peak_rate"
    # The firming unit is sized by the ramp triangle (its prices are the owner-approved
    # generic supplier figures in the config).
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


def _option_scenario(
    row: Dict[str, Any],
    reading: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
    usd_per_kwh: Optional[float] = None,
) -> Dict[str, Any]:
    """The wind scenario with one summary option, built from its reported energies."""
    cfg = _cfg()
    rates = wbo.derive_rates(cfg["tariff"])
    bcfg = cfg["battery"]
    return wbo.scenario_with_battery(
        _scenario(),
        power_mw=row["power_mw"],
        energy_mwh=row["energy_mwh"],
        operation=row["operation"],
        usd_per_kwh=bcfg["usd_per_kwh"]["mode"] if usd_per_kwh is None else usd_per_kwh,
        om_usd_per_dc_kwh_year=bcfg["om_usd_per_dc_kwh_year"],
        dc_per_nominal=bcfg["dc_per_nominal"],
        round_trip_efficiency=bcfg["round_trip_efficiency"],
        delivered_mwh=reading["delivered_mwh_per_year"],
        charged_mwh=reading["charged_mwh_per_year"],
        peak_rate=rates["whole_wind_peak_rate"],
        wind_rate=rates["wind"],
        contract_years=cfg["tariff"]["contract_years"],
        scenario_overrides=overrides,
    )


def test_committed_option_figures_reproduce_through_the_engine() -> None:
    summary = json.loads(SUMMARY.read_text())
    bcfg = _cfg()["battery"]
    wind_only = summary["wind_only"]["project_npv"]
    for name in ("cycled_0_5_2", "held_0_5_0_5"):
        row = summary["options"][name]
        rr = row["readings"]["B"]
        delta = _engine_project_value(_option_scenario(row, rr)) - wind_only
        committed = rr["bases"]["whole_wind_peak_rate"][
            "delta_project_npv_vs_wind_only"
        ]
        assert delta == pytest.approx(committed, rel=1e-9)
        assert delta < 0
    cycled = summary["options"]["cycled_0_5_2"]["readings"]["B"]
    assert cycled["black_start_reserve_mwh"] == bcfg["black_start_reserve_mwh"]
    assert summary["recommended_option_reading_A"] == "held_0_5_0_5"


def test_cli_refuses_a_scenario_the_engine_would_escalate_automatically() -> None:
    cli = _cli()
    scenario = _scenario()
    scenario.setdefault("finance", {})["capex_usd"] = scenario["capex"]["usd_total"]
    with pytest.raises(ValueError, match="automatically"):
        cli._kpis(scenario)


def test_committed_capex_and_service_figures_recompute_from_the_config() -> None:
    from finance.capex_price_basis import capex_escalation_factor

    summary = json.loads(SUMMARY.read_text())
    cfg = _cfg()
    mode = cfg["battery"]["usd_per_kwh"]["mode"]
    basis = capex_escalation_factor(_scenario())
    factor = 1.0 if basis is None else float(basis["factor"])
    assert factor != 1.0  # the scenario declares a price basis, so the pin bites
    for row in summary["options"].values():
        for rr in row["readings"].values():
            assert rr["battery_pretax_base_basis"][
                "capex_usd_at_draw"
            ] == pytest.approx(row["energy_mwh"] * 1000.0 * mode * factor, rel=1e-12)
    supplier = cfg["down_ramp"]["supplier"]
    service = supplier["service_share_of_cif_per_year"]
    firming = summary["down_ramp_illustrative"]["firming_unit_base_basis"]
    for unit in firming.values():
        assert unit["om_usd_per_year"] == pytest.approx(
            unit["cif_usd"] * service, rel=1e-12
        )
    block = firming["smallest_block"]
    assert block["cif_usd"] == pytest.approx(
        supplier["smallest_block_dc_mwh"] * 1000.0 * supplier["offer_usd_per_dc_kwh"]
    )
    assert block["all_in_usd"] == pytest.approx(
        block["cif_usd"] * mode / (supplier["offer_usd_per_dc_kwh"] / 0.91), rel=1e-12
    )


def test_committed_bottom_up_rows_recompute_through_the_engine() -> None:
    summary = json.loads(SUMMARY.read_text())
    cfg = _cfg()
    supplier = cfg["down_ramp"]["supplier"]
    mode = cfg["battery"]["usd_per_kwh"]["mode"]
    wind_only = summary["wind_only"]["project_npv"]
    for row in summary["options"].values():
        expected = wbo.bottom_up_price(
            supplier,
            power_mw=row["power_mw"],
            energy_mwh=row["energy_mwh"],
            all_in_usd_per_kwh_mode=mode,
        )
        for key, value in expected.items():
            assert row["bottom_up_price"][key] == pytest.approx(value, rel=1e-12)
    held = summary["options"]["held_0_5_0_5"]
    rr = held["readings"]["B"]
    delta = (
        _engine_project_value(
            _option_scenario(
                held, rr, usd_per_kwh=held["bottom_up_price"]["all_in_usd_per_kwh"]
            )
        )
        - wind_only
    )
    committed = rr["bottom_up_price_base_basis"]["delta_project_npv_vs_wind_only"]
    assert delta == pytest.approx(committed, rel=1e-9)

    # What the doc says about the bottom-up price (reading B): the held 0.5 / 0.5 unit stays
    # the cheapest option, no option beats wind-only, and only held 1 / 1 and cycled 1 / 4
    # swap places against the flat price.
    def ranked(key: str) -> List[str]:
        def value(name: str) -> float:
            readings = summary["options"][name]["readings"]["B"]
            if key == "flat":
                return float(
                    readings["bases"]["whole_wind_peak_rate"][
                        "delta_project_npv_vs_wind_only"
                    ]
                )
            return float(
                readings["bottom_up_price_base_basis"]["delta_project_npv_vs_wind_only"]
            )

        return sorted(summary["options"], key=value, reverse=True)

    flat, bottom_up = ranked("flat"), ranked("bottom_up")
    assert flat[0] == bottom_up[0] == "held_0_5_0_5"
    assert summary["recommended_option_reading_A"] == "held_0_5_0_5"
    for row in summary["options"].values():
        assert (
            row["readings"]["B"]["bottom_up_price_base_basis"][
                "delta_project_npv_vs_wind_only"
            ]
            < 0.0
        )
    # The order below the first place depends on where the all-in factor is
    # calibrated (#1578 D-2), so only what holds under both calibrations is pinned.


def test_cli_refuses_to_write_a_summary_from_an_overridden_config() -> None:
    cli = _cli()
    raw = copy.deepcopy(_cfg())
    raw["output"]["summary_json"] = "somewhere.json"
    cli._refuse_overrides(raw)  # only output.* differs: accepted
    raw["down_ramp"]["supplier"]["usable_per_dc"] = 0.90
    with pytest.raises(ValueError, match="committed config"):
        cli._refuse_overrides(raw)


def test_cli_main_refuses_an_overridden_config_before_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The entry point itself, not only the helper, must refuse an overridden config.

    ``run`` is replaced by a recorder, so the test fails if ``main`` stops calling
    ``_refuse_overrides`` before it runs and writes the summary.
    """
    from omegaconf import OmegaConf

    cli = _cli()
    calls: List[Any] = []

    def fake_run(cfg: Any) -> Dict[str, Any]:
        calls.append(cfg)
        return {"ran": True}

    monkeypatch.setattr(cli, "run", fake_run)
    target = tmp_path / "summary.json"

    clean = copy.deepcopy(_cfg())
    clean["output"]["summary_json"] = str(target)
    cli.main(OmegaConf.create(clean))  # only output.* differs: runs and writes
    assert len(calls) == 1
    assert json.loads(target.read_text()) == {"ran": True}

    target.unlink()
    overridden = copy.deepcopy(clean)
    overridden["down_ramp"]["supplier"]["usable_per_dc"] = 0.90
    with pytest.raises(ValueError, match="committed config"):
        cli.main(OmegaConf.create(overridden))
    assert len(calls) == 1  # refused before ``run``
    assert not target.exists()
