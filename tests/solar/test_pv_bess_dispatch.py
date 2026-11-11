"""Tests for solar_resource.pv_bess_dispatch and scripts/run_blue_whale_solar_bess_v14.py.

The oracles do not come from the code under test:

* the repository's producer, ``solar_resource.pv_producer.compute_solar_aep``, which
  predates this change: the hourly series must sum to its annual energy;
* a closed form for a day with ample PV: evening discharge
  ``min(window hours x power, energy x RTE)``, then the morning takes the residue, so the
  day's discharge is ``min(energy x RTE, both windows' energy)``;
* hourly invariants over the whole TMY year: ``charge + direct export + curtailment = PV``,
  the state-of-charge balance, the power and export limits, and no charging in a window;
* the engine's own BESS revenue (``finance.bess_revenue``, pre-existing) for the
  energy-tariff formula the engine mapping relies on;
* hostile controls for window misalignment, overlapping windows and grid charging.
"""

from __future__ import annotations

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

from solar_resource import pv_bess_dispatch as pbd

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess.yaml"
SCRIPT = REPO_ROOT / "scripts" / "run_blue_whale_solar_bess_v14.py"
SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"
SIZING = REPO_ROOT / "conf" / "blue_whale_pv_bess_sizing.yaml"
PRICING = REPO_ROOT / "conf" / "blue_whale_pv_bess_pricing.yaml"


def sized_conf() -> Dict[str, Any]:
    """This unit config at the size PR 3 chose, which the scenario carries (v0.6).

    ``conf/blue_whale_solar_bess.yaml`` keeps the owner-brief design (DC/AC 1.2, 30 MWh,
    PVWatts' 96% inverter efficiency); the recommendation in the sizing config and the
    matched inverter's European efficiency in the pricing config override it here.
    """
    conf = yaml.safe_load(CONF.read_text())
    rec = yaml.safe_load(SIZING.read_text())["recommendation"]
    inverter = yaml.safe_load(PRICING.read_text())["inverter"]
    conf["array"]["dc_ac_ratio"] = rec["dc_ac_ratio"]
    conf["bess"]["energy_mwh"] = rec["bess_energy_mwh"]
    conf["pv_yield"]["resource_solar"]["inverter_eff_nom"] = inverter[
        "european_efficiency"
    ]
    return conf


def _load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("blue_whale_solar_bess_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cfg() -> Dict[str, Any]:
    data = yaml.safe_load(CONF.read_text())
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def bess(cfg: Dict[str, Any]) -> pbd.BessConfig:
    return pbd.BessConfig.from_mapping(cfg["bess"])


@pytest.fixture(scope="module")
def dcfg(cfg: Dict[str, Any]) -> pbd.DispatchConfig:
    return pbd.DispatchConfig.from_mapping(cfg["dispatch"])


@pytest.fixture(scope="module")
def tariff(cfg: Dict[str, Any]) -> pbd.TariffConfig:
    return pbd.TariffConfig.from_mapping(cfg["tariff"])


@pytest.fixture(scope="module")
def cli_out() -> Dict[str, Any]:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    out = _load_cli().run(yaml.safe_load(CONF.read_text()))
    assert isinstance(out, dict)
    return out


@pytest.fixture(scope="module")
def unshaded_cli_out() -> Dict[str, Any]:
    """The unit with the turbine shadow switched off (the hourly PV is the producer's)."""
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    conf = yaml.safe_load(CONF.read_text())
    conf["pv_yield"]["turbine_shading_modelled"] = False
    conf["pv_yield"]["turbine_shading"] = None
    out = _load_cli().run(conf)
    assert isinstance(out, dict)
    return out


@pytest.fixture(scope="module")
def sized_cli_out() -> Dict[str, Any]:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    out = _load_cli().run(sized_conf())
    assert isinstance(out, dict)
    return out


def _hours(days: int) -> Any:
    import pandas as pd

    return pd.date_range("2026-01-01 00:00", periods=24 * days, freq="1h", tz="UTC")


def _ample_pv(days: int, mw: float = 5.0) -> np.ndarray:
    """``mw`` from 07:30 to 17:30 local (UTC 02:00-12:00), zero otherwise."""
    pv = np.zeros(24 * days)
    for d in range(days):
        pv[24 * d + 2 : 24 * d + 12] = mw
    return pv


# ---------------------------------------------------------------------------
# Hourly PV against the pre-existing producer
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "extra",
    [
        {},
        {
            "system_loss_pct": None,
            "losses": {"soiling_pct": 2.0, "dc_wiring_loss_pct": 1.5},
        },
    ],
)
def test_hourly_pv_sums_to_the_producer(
    cfg: Dict[str, Any], extra: Dict[str, Any]
) -> None:
    pytest.importorskip("pvlib")
    from solar_resource.pv_producer import compute_solar_aep

    block = dict(cfg["pv_yield"]["resource_solar"])
    block.update(extra)
    block = {k: v for k, v in block.items() if v is not None}
    solar = pbd.with_array(
        block,
        dc_capacity_mw=6.0032,
        dc_ac_ratio=1.20064,
        tilt_deg=8.0,
        azimuth_deg=180.0,
        gamma_pdc_per_c=-0.0026,
    )
    pv = pbd.hourly_pv(solar)
    aep = compute_solar_aep(solar)
    assert pv.annual_mwh / 1000.0 == pytest.approx(aep.annual_energy_gwh, rel=1e-12)
    assert pv.ac_mw.size == 8760
    assert pv.ac_mw.max() <= pv.ac_nameplate_mw * pv.loss_factor + 1e-9
    assert (pv.dc_clipped_mw >= 0).all()


def test_with_array_refuses_a_restated_key(cfg: Dict[str, Any]) -> None:
    block = {**cfg["pv_yield"]["resource_solar"], "tilt_deg": 10.0}
    with pytest.raises(ValueError, match="must not state"):
        pbd.with_array(
            block,
            dc_capacity_mw=6.0,
            dc_ac_ratio=1.2,
            tilt_deg=8.0,
            azimuth_deg=180.0,
            gamma_pdc_per_c=-0.0026,
        )


def test_hourly_pv_needs_a_tmy(cfg: Dict[str, Any]) -> None:
    block = {
        k: v for k, v in cfg["pv_yield"]["resource_solar"].items() if k != "tmy_path"
    }
    solar = pbd.with_array(
        block,
        dc_capacity_mw=6.0,
        dc_ac_ratio=1.2,
        tilt_deg=8.0,
        azimuth_deg=180.0,
        gamma_pdc_per_c=-0.0026,
    )
    with pytest.raises(ValueError, match="tmy_path"):
        pbd.hourly_pv(solar)


# ---------------------------------------------------------------------------
# Closed-form dispatch oracles
# ---------------------------------------------------------------------------
def test_ample_pv_day_closed_form(
    bess: pbd.BessConfig, dcfg: pbd.DispatchConfig, tariff: pbd.TariffConfig
) -> None:
    days = 5
    s = pbd.dispatch(_ample_pv(days), _hours(days), bess, dcfg)
    rte, energy = 0.85, 30.0
    evening_cap, morning_cap = 4 * 5.0, 2 * 5.0
    evening = min(evening_cap, energy * rte)  # 20
    morning = min(morning_cap, (energy - evening / rte) * rte)  # 5.5
    assert evening + morning == pytest.approx(
        min(energy * rte, evening_cap + morning_cap)
    )
    for d in range(days):
        day = slice(24 * d, 24 * (d + 1))
        win = s.window[day]
        assert s.discharge_mw[day][win == 1].sum() == pytest.approx(evening)
        assert s.discharge_mw[day][win == 0].sum() == pytest.approx(morning)
        # The battery refills from empty each day: 30 MWh of the 50 MWh of PV.
        assert s.charge_mw[day].sum() == pytest.approx(energy)
        assert s.pv_export_mw[day].sum() == pytest.approx(50.0 - energy)
    summary = pbd.summarise(s, bess, dcfg, tariff)
    assert summary.equivalent_full_cycles == pytest.approx(days * 25.5 / (30.0 * 0.85))
    assert summary.revenue_lkr_by_rate["priority"] == pytest.approx(
        days * 20.0 * 1000.0 * 50.10
    )
    assert summary.revenue_lkr_by_rate["other"] == pytest.approx(
        days * (5.5 + 20.0) * 1000.0 * 20.72
    )


def test_deliverable_energy_reading_fills_both_windows(
    cfg: Dict[str, Any], dcfg: pbd.DispatchConfig
) -> None:
    # charge_efficiency = RTE: 30 MWh read as deliverable energy, so 6 h x 5 MW = 30 MWh.
    b = pbd.BessConfig.from_mapping({**cfg["bess"], "charge_efficiency": 0.85})
    s = pbd.dispatch(_ample_pv(3), _hours(3), b, dcfg)
    day = slice(24, 48)
    assert s.discharge_mw[day].sum() == pytest.approx(30.0)
    assert s.charge_mw[day].sum() == pytest.approx(30.0 / 0.85)


def test_export_limit_curtails(cfg: Dict[str, Any], bess: pbd.BessConfig) -> None:
    d = pbd.DispatchConfig.from_mapping({**cfg["dispatch"], "export_limit_mw": 2.0})
    pv = _ample_pv(2)
    s = pbd.dispatch(pv, _hours(2), bess, d)
    assert s.curtailed_mw.sum() > 0
    assert (s.pv_export_mw + s.discharge_mw <= 2.0 + 1e-12).all()
    assert s.discharge_mw.max() == pytest.approx(2.0)


def test_evening_need_policy_charges_only_the_evening(
    cfg: Dict[str, Any], bess: pbd.BessConfig
) -> None:
    d = pbd.DispatchConfig.from_mapping(
        {**cfg["dispatch"], "charge_policy": "evening_need"}
    )
    s = pbd.dispatch(_ample_pv(3), _hours(3), bess, d)
    assert s.soc_end_mwh.max() == pytest.approx(20.0 / 0.85)
    day = slice(24, 48)
    assert s.discharge_mw[day][s.window[day] == 1].sum() == pytest.approx(20.0)
    assert s.discharge_mw[day][s.window[day] == 0].sum() == pytest.approx(0.0)


def test_priority_term_expires(
    bess: pbd.BessConfig, dcfg: pbd.DispatchConfig, tariff: pbd.TariffConfig
) -> None:
    s = pbd.dispatch(_ample_pv(2), _hours(2), bess, dcfg)
    inside = pbd.summarise(s, bess, dcfg, tariff, year=15)
    after = pbd.summarise(s, bess, dcfg, tariff, year=16)
    assert inside.export_mwh_by_rate["priority"] > 0
    assert after.export_mwh_by_rate["priority"] == 0.0
    assert after.revenue_lkr == pytest.approx(
        after.unit_export_mwh * 1000.0 * tariff.other_lkr_per_kwh
    )


# ---------------------------------------------------------------------------
# Hostile controls
# ---------------------------------------------------------------------------
def test_misaligned_window_is_refused(
    cfg: Dict[str, Any], bess: pbd.BessConfig
) -> None:
    windows = {
        "evening": {"start_local": "17:00", "end_local": "21:00", "rate": "priority"}
    }
    d = pbd.DispatchConfig.from_mapping({**cfg["dispatch"], "windows": windows})
    with pytest.raises(ValueError, match="step boundary"):
        pbd.dispatch(_ample_pv(1), _hours(1), bess, d)


def test_overlapping_windows_and_grid_charging_are_refused(cfg: Dict[str, Any]) -> None:
    windows = {
        "a": {"start_local": "17:30", "end_local": "21:30", "rate": "priority"},
        "b": {"start_local": "20:30", "end_local": "22:30", "rate": "other"},
    }
    with pytest.raises(ValueError, match="overlap"):
        pbd.DispatchConfig.from_mapping({**cfg["dispatch"], "windows": windows})
    with pytest.raises(ValueError, match="grid_charging"):
        pbd.BessConfig.from_mapping({**cfg["bess"], "grid_charging": True})
    with pytest.raises(ValueError, match="charge_policy"):
        pbd.DispatchConfig.from_mapping(
            {**cfg["dispatch"], "charge_policy": "arbitrage"}
        )
    with pytest.raises(ValueError, match="unknown keys"):
        pbd.TariffConfig.from_mapping({**cfg["tariff"], "night_lkr_per_kwh": 1.0})


# ---------------------------------------------------------------------------
# Negative controls for every refusal guard (#1531 assurance A-3). Each case first
# shows the committed block is accepted, then that one changed value is refused with
# that guard's own message, so the guard and nothing else is what refuses it.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"charge_efficiency": 0.80}, r"charge_efficiency must lie in \[RTE, 1\]"),
        ({"charge_efficiency": 1.01}, r"charge_efficiency must lie in \[RTE, 1\]"),
        (
            {"round_trip_efficiency": 1.02, "charge_efficiency": 1.0},
            "round_trip_efficiency must be <= 1",
        ),
        ({"min_soc_fraction": -0.1}, "bess.min_soc_fraction out of range"),
        ({"min_soc_fraction": 0.5, "max_soc_fraction": 0.5}, "min_soc_fraction <"),
        ({"max_soc_fraction": 1.1}, "max_soc_fraction <= 1"),
        ({"energy_mwh": 0.0}, "bess.energy_mwh"),
    ],
)
def test_bess_guards_refuse_each_bad_value(
    cfg: Dict[str, Any], changes: Dict[str, Any], message: str
) -> None:
    assert pbd.BessConfig.from_mapping(cfg["bess"]).round_trip_efficiency == 0.85
    with pytest.raises(ValueError, match=message):
        pbd.BessConfig.from_mapping({**cfg["bess"], **changes})


def _window(**changes: Any) -> Dict[str, Any]:
    return {"start_local": "17:30", "end_local": "21:30", "rate": "priority", **changes}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"windows": {}}, "non-empty mapping"),
        ({"windows": [_window()]}, "non-empty mapping"),
        ({"windows": {"evening": {"start_local": "17:30"}}}, "needs exactly"),
        ({"windows": {"evening": _window(extra=1)}}, "needs exactly"),
        ({"windows": {"evening": _window(start_local="5pm")}}, "must be HH:MM"),
        (
            {"windows": {"evening": _window(end_local="17:30")}},
            "end must be after start",
        ),
        ({"windows": {"evening": _window(end_local="01:00")}}, "no midnight wrap"),
        ({"windows": {"evening": _window(rate="peak")}}, "rate must be one of"),
        ({"cyclic_soc_max_iterations": 0}, "positive integer"),
        ({"cyclic_soc_max_iterations": 2.5}, "positive integer"),
        ({"cyclic_soc_max_iterations": True}, "positive integer"),
        ({"export_limit_mw": 0.0}, "dispatch.export_limit_mw"),
    ],
)
def test_dispatch_config_guards_refuse_each_bad_value(
    cfg: Dict[str, Any], changes: Dict[str, Any], message: str
) -> None:
    assert len(pbd.DispatchConfig.from_mapping(cfg["dispatch"]).windows) == 2
    with pytest.raises(ValueError, match=message):
        pbd.DispatchConfig.from_mapping({**cfg["dispatch"], **changes})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"priority_term_years": 0}, "positive integer"),
        ({"priority_term_years": 15.5}, "positive integer"),
        ({"priority_term_years": True}, "positive integer"),
        ({"priority_lkr_per_kwh": 20.0}, "priority rate is below the other rate"),
    ],
)
def test_tariff_guards_refuse_each_bad_value(
    cfg: Dict[str, Any], changes: Dict[str, Any], message: str
) -> None:
    assert pbd.TariffConfig.from_mapping(cfg["tariff"]).priority_term_years == 15
    with pytest.raises(ValueError, match=message):
        pbd.TariffConfig.from_mapping({**cfg["tariff"], **changes})


def test_dispatcher_input_guards(
    bess: pbd.BessConfig, dcfg: pbd.DispatchConfig
) -> None:
    import pandas as pd

    pv, hours = _ample_pv(2), _hours(2)
    assert pbd.dispatch(pv, hours, bess, dcfg).iterations >= 1
    with pytest.raises(ValueError, match="one value per timestamp"):
        pbd.dispatch(pv[:-1], hours, bess, dcfg)
    with pytest.raises(ValueError, match="one value per timestamp"):
        pbd.dispatch(pv[:1], hours[:1], bess, dcfg)
    gappy = hours.delete(5)
    with pytest.raises(ValueError, match="consecutive hourly timestamps"):
        pbd.dispatch(pv[:-1], gappy, bess, dcfg)
    half_hourly = pd.date_range("2026-01-01", periods=len(pv), freq="30min", tz="UTC")
    with pytest.raises(ValueError, match="consecutive hourly timestamps"):
        pbd.dispatch(pv, half_hourly, bess, dcfg)
    for bad in (-1e-9, float("nan"), float("inf")):
        hostile = pv.copy()
        hostile[3] = bad
        with pytest.raises(ValueError, match="finite and non-negative"):
            pbd.dispatch(hostile, hours, bess, dcfg)


def test_cyclic_state_that_does_not_converge_is_refused(
    cfg: Dict[str, Any], bess: pbd.BessConfig
) -> None:
    converged = pbd.dispatch(
        _ample_pv(2), _hours(2), bess, pbd.DispatchConfig.from_mapping(cfg["dispatch"])
    )
    # The first pass starts empty and ends holding energy, so it needs a second pass.
    assert converged.iterations >= 2
    one_pass = pbd.DispatchConfig.from_mapping(
        {**cfg["dispatch"], "cyclic_soc_max_iterations": 1}
    )
    with pytest.raises(ValueError, match="did not converge"):
        pbd.dispatch(_ample_pv(2), _hours(2), bess, one_pass)


# ---------------------------------------------------------------------------
# One priority-term rule (#1531 assurance A-4): summarise books energy by
# TariffConfig.rate_name, and TariffConfig.rate prices that name.
# ---------------------------------------------------------------------------
def test_summarise_and_rate_share_one_priority_term_rule(
    bess: pbd.BessConfig, dcfg: pbd.DispatchConfig, tariff: pbd.TariffConfig
) -> None:
    s = pbd.dispatch(_ample_pv(2), _hours(2), bess, dcfg)
    term = tariff.priority_term_years
    for year in (1, term, term + 1, term + 10):
        summary = pbd.summarise(s, bess, dcfg, tariff, year=year)
        expected = {
            "priority": 0.0,
            "other": summary.pv_export_mwh_by_window["outside"],
        }
        revenue = (
            summary.pv_export_mwh_by_window["outside"]
            * 1000.0
            * tariff.rate(None, year)
        )
        for k, w in enumerate(dcfg.windows):
            mwh = summary.discharge_mwh_by_window[w.name]
            mwh += summary.pv_export_mwh_by_window[w.name]
            expected[tariff.rate_name(w.rate, year)] += mwh
            revenue += mwh * 1000.0 * tariff.rate(w.rate, year)
        assert summary.export_mwh_by_rate == pytest.approx(expected, rel=1e-12)
        assert summary.revenue_lkr == pytest.approx(revenue, rel=1e-12)
    assert tariff.rate_name("priority", term) == "priority"
    assert tariff.rate_name("priority", term + 1) == "other"
    assert tariff.rate_name("other", 1) == "other"
    assert tariff.rate_name(None, 1) == "other"
    assert tariff.rate("priority", 1) == tariff.priority_lkr_per_kwh
    assert tariff.rate("priority", term + 1) == tariff.other_lkr_per_kwh


# ---------------------------------------------------------------------------
# The TMY year: invariants and the committed result
# ---------------------------------------------------------------------------
def test_tmy_year_invariants(
    unshaded_cli_out: Dict[str, Any],
    cfg: Dict[str, Any],
    bess: pbd.BessConfig,
    dcfg: pbd.DispatchConfig,
) -> None:
    # The oracle is the producer's own hourly chain, so the unit is run unshaded here; the
    # turbine-shadow derate (input B33) is checked against it in the next test.
    cli_out = unshaded_cli_out
    solar = pbd.with_array(
        cfg["pv_yield"]["resource_solar"],
        dc_capacity_mw=cli_out["array"]["dc_capacity_mw"],
        dc_ac_ratio=cli_out["array"]["dc_ac_ratio"],
        tilt_deg=8.0,
        azimuth_deg=180.0,
        gamma_pdc_per_c=-0.0026,
    )
    pv = pbd.hourly_pv(solar)
    s = pbd.dispatch(pv.ac_mw * 0.99, pv.timestamps_utc, bess, dcfg)
    np.testing.assert_allclose(
        s.charge_mw + s.pv_export_mw + s.curtailed_mw, s.pv_mw, rtol=0, atol=1e-12
    )
    prev = np.concatenate([[s.initial_soc_mwh], s.soc_end_mwh[:-1]])
    np.testing.assert_allclose(
        s.soc_end_mwh,
        prev
        + s.charge_mw * bess.charge_efficiency
        - s.discharge_mw / bess.discharge_efficiency,
        rtol=0,
        atol=1e-9,
    )
    assert abs(s.soc_end_mwh[-1] - s.initial_soc_mwh) <= 1e-9
    assert (s.soc_end_mwh >= -1e-12).all() and (s.soc_end_mwh <= 30.0 + 1e-12).all()
    assert (s.charge_mw <= 5.0 + 1e-12).all() and (s.discharge_mw <= 5.0 + 1e-12).all()
    assert (s.pv_export_mw + s.discharge_mw <= 5.0 + 1e-12).all()
    assert (s.charge_mw[s.window >= 0] == 0).all()
    assert (s.discharge_mw[s.window < 0] == 0).all()
    # Energy conservation over the cyclic year: charge x RTE = discharge.
    assert s.discharge_mw.sum() == pytest.approx(s.charge_mw.sum() * 0.85, rel=1e-12)
    y1 = cli_out["dispatch"]["year1"]
    assert y1["discharge_mwh"] == pytest.approx(float(s.discharge_mw.sum()), rel=1e-12)
    assert y1["pv_export_mwh"] + y1["charge_mwh"] + y1[
        "curtailed_mwh"
    ] == pytest.approx(y1["pv_mwh"], rel=1e-12)


def test_turbine_shadow_derates_the_pv_before_dispatch(
    cli_out: Dict[str, Any], unshaded_cli_out: Dict[str, Any]
) -> None:
    """Input B33: the unit's PV is the producer's, less the turbine's shadow, hour by hour.

    The oracle is the unshaded run: the shaded year-1 PV must be the unshaded one less the
    reported AC loss, the loss must be positive and below the optical upper bound times
    the multiplier, and the battery must see the shaded PV (its year-1 balance closes on
    it).
    """
    shaded, plain = cli_out["pv_yield"], unshaded_cli_out["pv_yield"]
    assert shaded["turbine_shading_modelled"] is True
    assert plain["turbine_shading_modelled"] is False
    assert plain["turbine_shading"] is None
    rep = shaded["turbine_shading"]
    assert rep["irradiance_basis"] == "TMY" and rep["yaw_basis"] == "wind_rose"
    assert rep["tables"] == cli_out["array"]["tables"]
    loss = rep["ac_energy_loss"]
    multiplier = rep["electrical_mismatch_multiplier"]
    assert 0.0 < loss < rep["optical_loss_rotor_yawed_to_sun"] * multiplier * 1.5
    # The blades are counted only outside the tower strip, so the parts add up.
    assert rep["optical_tower"] + rep["optical_rotor"] == pytest.approx(
        rep["optical_loss"], rel=1e-9
    )
    assert rep["optical_rotor"] < rep["optical_rotor_yawed_to_sun"]
    assert rep["optical_loss_rotor_yawed_to_sun"] == pytest.approx(
        rep["optical_tower"] + rep["optical_rotor_yawed_to_sun"], rel=1e-12
    )
    # The parity check stays on the producer's unshaded series.
    assert shaded["hourly_sum_gwh"] == pytest.approx(plain["hourly_sum_gwh"], rel=1e-15)
    assert shaded["shaded_annual_energy_gwh"] == pytest.approx(
        plain["hourly_sum_gwh"] * (1.0 - loss), rel=1e-12
    )
    y1s, y1p = cli_out["dispatch"]["year1"], unshaded_cli_out["dispatch"]["year1"]
    assert y1s["pv_mwh"] == pytest.approx(y1p["pv_mwh"] * (1.0 - loss), rel=1e-12)
    assert y1s["pv_export_mwh"] + y1s["charge_mwh"] + y1s[
        "curtailed_mwh"
    ] == pytest.approx(y1s["pv_mwh"], rel=1e-12)
    assert y1s["revenue_lkr"] < y1p["revenue_lkr"]


def test_engine_bess_formula_matches_finance_bess_revenue(
    cli_out: Dict[str, Any],
) -> None:
    from finance.bess_revenue import bess_revenue_lkr_for_year, resolve_bess_specs

    e = cli_out["engine"]
    block = {
        "type": "bess",
        "power_mw": 5.0,
        "energy_mwh": 30.0,
        "duration_h": 6.0,
        "capex_usd": 1.0,
        "revenue": {
            "model": "energy_tariff",
            "tariff_lkr_per_kwh": e["bess_tariff_lkr_per_kwh"],
            "cycles_per_year": e["bess_cycles_per_year"],
            "round_trip_efficiency": 0.85,
            "availability_factor": 1.0,
            "contract_years": 15,
            "mdsc_fade_pct_annual": e["bess_mdsc_fade_pct_annual"],
        },
    }
    specs = resolve_bess_specs(
        {
            "generation": {"technologies": {"bess_1": block}},
            "project": {"life_years": 20},
        }
    )
    for year in (1, 2, 10, 15, 16, 20):
        assert bess_revenue_lkr_for_year(specs, year - 1) == pytest.approx(
            pbd.engine_bess_revenue_lkr(
                energy_mwh=30.0,
                cycles_per_year=e["bess_cycles_per_year"],
                round_trip_efficiency=0.85,
                tariff_lkr_per_kwh=e["bess_tariff_lkr_per_kwh"],
                fade=e["bess_mdsc_fade_pct_annual"],
                contract_years=15,
                year=year,
            ),
            rel=1e-12,
        )


def test_geometric_rate_matching_sum_closed_form() -> None:
    series = [100.0 * (1 - 0.004) ** t for t in range(20)]
    assert pbd.geometric_rate_matching_sum(series) == pytest.approx(0.004, rel=1e-9)
    assert pbd.geometric_rate_matching_sum([5.0, 5.0, 6.0]) == 0.0
    with pytest.raises(ValueError):
        pbd.geometric_rate_matching_sum([])


def test_engine_mapping_reproduces_the_dispatcher(cli_out: Dict[str, Any]) -> None:
    e = cli_out["engine"]
    assert e["engine_revenue_lkr"][0] == pytest.approx(
        e["dispatcher_revenue_lkr"][0], rel=1e-12
    )
    assert e["max_later_year_gap_pct"] <= 0.5
    assert e["bess_tariff_lkr_per_kwh"] == pytest.approx(50.10 - 20.72)
    path = cli_out["degradation_path"]
    assert [p["pv_factor"] for p in path][:2] == pytest.approx([0.99, 0.9865])
    assert (
        path[15]["priority_export_mwh"] == 0.0
    )  # year 16: the priority term has ended
    assert all(
        a["unit_export_mwh"] > b["unit_export_mwh"] for a, b in zip(path, path[1:])
    )


def test_scenario_carries_the_derived_unit(sized_cli_out: Dict[str, Any]) -> None:
    # From v0.6 the scenario carries the unit at PR 3's recommended size, so this
    # dispatcher is run at that size (sized_conf) rather than at the owner-brief design.
    scen = yaml.safe_load(SCENARIO.read_text())
    techs = scen["generation"]["technologies"]
    e = sized_cli_out["engine"]
    rec = yaml.safe_load(SIZING.read_text())["recommendation"]
    bess_all_in = yaml.safe_load(PRICING.read_text())["bess"]["all_in_usd_per_kwh"]
    solar, b = techs["solar"], techs["bess_1"]
    assert solar["capacity_mw"] == e["solar_capacity_mw"] == 5.0
    assert solar["capacity_factor"] == pytest.approx(
        e["solar_capacity_factor"], abs=5e-7
    )
    assert solar["degradation_pct"] == pytest.approx(
        e["solar_degradation_pct"], abs=5e-7
    )
    assert solar["aep_gwh"] == pytest.approx(e["solar_aep_gwh"], abs=0.005)
    energy = float(rec["bess_energy_mwh"])
    assert (b["power_mw"], b["energy_mwh"], b["duration_h"]) == (
        5.0,
        energy,
        energy / 5.0,
    )
    assert sized_cli_out["array"]["dc_ac_ratio"] == pytest.approx(
        rec["dc_ac_ratio"], abs=0.01
    )
    rev = b["revenue"]
    assert rev["model"] == "energy_tariff"
    assert rev["tariff_lkr_per_kwh"] == pytest.approx(e["bess_tariff_lkr_per_kwh"])
    assert rev["cycles_per_year"] == pytest.approx(e["bess_cycles_per_year"], abs=5e-5)
    assert rev["mdsc_fade_pct_annual"] == pytest.approx(
        e["bess_mdsc_fade_pct_annual"], abs=5e-7
    )
    assert rev["round_trip_efficiency"] == 0.85 and rev["contract_years"] == 15
    # The BESS all-in mode of the pricing config: PR 3 cited the public NSO 250 base, USD
    # 135.00/kWh; PR 6 capex replaced it with the blended mode (USD 140.74/kWh).
    assert b["capex_usd"] == pytest.approx(energy * 1000.0 * bess_all_in["mode"])
    assert scen["tariff"]["lkr_per_kwh"] == pytest.approx(
        e["tariff_lkr_per_kwh"], abs=5e-5
    )
    assert scen["project"]["capacity_factor"] == pytest.approx(
        e["project_capacity_factor"], abs=5e-7
    )
    assert scen["capex"]["usd_total"] == pytest.approx(
        sum(techs[t]["capex_usd"] for t in ("wind", "solar", "bess_1")) + 2.0e6
    )


def test_committed_outputs_regenerate(tmp_path: Path) -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    raw = yaml.safe_load(CONF.read_text())
    raw["output"] = {
        "hourly_csv": str(tmp_path / "hourly.csv"),
        "layout_geojson": str(tmp_path / "layout.geojson"),
    }
    out = _load_cli().run(raw)
    assert out["site_fit"]["fits"] is True
    committed_csv = REPO_ROOT / "docs" / "blue_whale" / "pv_bess_hourly_tmy.csv"
    committed_geo = REPO_ROOT / "docs" / "blue_whale" / "pv_bess_layout_lot5b.geojson"
    assert (tmp_path / "hourly.csv").read_text() == committed_csv.read_text()
    assert json.loads((tmp_path / "layout.geojson").read_text()) == json.loads(
        committed_geo.read_text()
    )


def test_hydra_entrypoint_prints_one_json_object(tmp_path: Path) -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "pv_yield.degradation_years=2"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out["config"] == "conf/blue_whale_solar_bess.yaml"
    assert len(out["degradation_path"]) == 2
    assert not (tmp_path / "outputs").exists() and not (tmp_path / ".hydra").exists()
