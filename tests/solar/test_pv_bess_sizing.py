"""Tests for the Blue Whale solar + BESS sizing (``solar_resource.pv_bess_sizing``).

``TEST-01`` oracles that did not originate in this change:

* PR 2's scalar dispatcher (``solar_resource.pv_bess_dispatch.dispatch`` and
  ``summarise``) is the oracle for the array dispatcher;
* the engine (``evaluate_with_overrides``, pre-existing) must make project NPV fall as
  either capex rises (a monotonicity property);
* the unit-only NPV meets the closed-form annuity on a degenerate flat case, and the
  Monte Carlo collapses to its base case when every draw equals the base;
* the triangular inverse CDF meets its closed form, and the seeded draws reproduce.

``TEST-03``: every test here runs at most 200 model evaluations (a dispatched path plus an
engine evaluation); the counts are asserted against ``config/stochastic_test_policy.yaml``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest
import yaml

from finance.irr import npv
from solar_resource import pv_bess_dispatch as pbd
from solar_resource import pv_bess_sizing as sz

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess.yaml"
SIZING_CONF = REPO_ROOT / "conf" / "blue_whale_pv_bess_sizing.yaml"
PRICING_CONF = REPO_ROOT / "conf" / "blue_whale_pv_bess_pricing.yaml"
SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"
SUMMARY = REPO_ROOT / "docs" / "blue_whale" / "pv_bess_sizing_summary.json"
SCRIPT = REPO_ROOT / "scripts" / "run_blue_whale_pv_bess_sizing_v14.py"
POLICY = REPO_ROOT / "config" / "stochastic_test_policy.yaml"


def _yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


def _hard_cap() -> int:
    return int(_yaml(POLICY)["ordinary_suite"]["hard_max_model_evaluations"])


@pytest.fixture(scope="module")
def unit() -> Dict[str, Any]:
    return _yaml(UNIT_CONF)


@pytest.fixture(scope="module")
def pricing() -> sz.Pricing:
    return sz.Pricing.from_mapping(_yaml(PRICING_CONF))


@pytest.fixture(scope="module")
def tmy_pv(unit: Dict[str, Any]) -> pbd.HourlyPv:
    pytest.importorskip("pvlib")
    from analytics.gis.pv_array_layout import (
        ArrayConfig,
        ModuleSpec,
        StringDesignConfig,
        design_string,
        size_array,
    )

    module = ModuleSpec.from_mapping(unit["module"])
    strings = design_string(
        module, StringDesignConfig.from_mapping(unit["string_design"])
    )
    array = ArrayConfig.from_mapping(unit["array"])
    sizing = size_array(module, strings, array)
    solar = pbd.with_array(
        unit["pv_yield"]["resource_solar"],
        dc_capacity_mw=sizing.dc_capacity_mw,
        dc_ac_ratio=sizing.dc_ac_ratio,
        tilt_deg=array.tilt_deg,
        azimuth_deg=array.azimuth_deg,
        gamma_pdc_per_c=module.temp_coeff_pmax_pct_per_c / 100.0,
    )
    return pbd.hourly_pv(solar)


def _bess(unit: Dict[str, Any], energy: float, rte: float) -> pbd.BessConfig:
    raw = {**unit["bess"], "energy_mwh": energy, "round_trip_efficiency": rte}
    return pbd.BessConfig.from_mapping(raw)


# ---------------------------------------------------------------------------
# The array dispatcher against PR 2's scalar dispatcher
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("policy", ["fill", "evening_need"])
def test_dispatch_columns_reproduces_the_pr2_dispatcher(
    unit: Dict[str, Any], tmy_pv: pbd.HourlyPv, policy: str
) -> None:
    dcfg = pbd.DispatchConfig.from_mapping(
        {**unit["dispatch"], "charge_policy": policy}
    )
    tariff = pbd.TariffConfig.from_mapping(unit["tariff"])
    cols = [
        (0.99, 30.0, 0.85),
        (0.90, 20.0, 0.85),
        (1.07, 30.0, 0.82),
        (0.95, 10.0, 0.88),
    ]
    sums = sz.dispatch_columns(
        tmy_pv.ac_mw,
        tmy_pv.timestamps_utc,
        scale=np.array([c[0] for c in cols]),
        energy_mwh=np.array([c[1] for c in cols]),
        round_trip_efficiency=np.array([c[2] for c in cols]),
        bess=_bess(unit, 30.0, 0.85),
        cfg=dcfg,
    )
    for j, (scale, energy, rte) in enumerate(cols):
        bess = _bess(unit, energy, rte)
        for year in (1, 16):  # inside and after the priority term
            ref = pbd.summarise(
                pbd.dispatch(tmy_pv.ac_mw * scale, tmy_pv.timestamps_utc, bess, dcfg),
                bess,
                dcfg,
                tariff,
                year=year,
                pv_factor=scale,
            )
            got = sz.annual_energy(
                sums,
                j,
                windows=dcfg.windows,
                tariff=tariff,
                year=year,
                pv_factor=scale,
                usable_mwh=bess.usable_mwh,
                discharge_efficiency=bess.discharge_efficiency,
            )
            a, b = pbd.as_dict(got), pbd.as_dict(ref)
            assert a.keys() == b.keys()
            for key, val in b.items():
                if isinstance(val, dict):
                    for k2, v2 in val.items():
                        assert a[key][k2] == pytest.approx(v2, rel=1e-10, abs=1e-8), (
                            j,
                            key,
                            k2,
                        )
                else:
                    assert a[key] == pytest.approx(val, rel=1e-10, abs=1e-8), (j, key)


def _synthetic_day(days: int = 4) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01T00:00", periods=24 * days, freq="h", tz="UTC")


def test_curtailment_removes_only_direct_export_outside_the_windows(
    unit: Dict[str, Any],
) -> None:
    idx = _synthetic_day()
    local = idx.tz_convert("Asia/Colombo")
    # PV at 8 MW from 06:30 to 16:30 local: more than the 5 MW battery and limit take.
    pv = np.where((local.hour * 60 + local.minute >= 390) & (local.hour < 16), 8.0, 0.0)
    dcfg = pbd.DispatchConfig.from_mapping(unit["dispatch"])
    kw: Dict[str, Any] = dict(
        scale=np.array([1.0]),
        energy_mwh=np.array([30.0]),
        round_trip_efficiency=np.array([0.85]),
        bess=_bess(unit, 30.0, 0.85),
        cfg=dcfg,
    )
    base = sz.dispatch_columns(pv, idx, **kw)
    cut = sz.dispatch_columns(pv, idx, curtailment_fraction=0.125, **kw)
    out0 = float(base.pv_export_mwh_by_window["outside"][0])
    assert out0 > 0
    assert float(cut.pv_export_mwh_by_window["outside"][0]) == pytest.approx(
        out0 * 0.875
    )
    assert float(cut.charge_mwh[0]) == pytest.approx(float(base.charge_mwh[0]))
    for name in ("evening", "morning"):
        assert float(cut.discharge_mwh_by_window[name][0]) == pytest.approx(
            float(base.discharge_mwh_by_window[name][0])
        )
    # Energy balance: PV = charge + export + curtailed in both.
    for s in (base, cut):
        exported = sum(float(v[0]) for v in s.pv_export_mwh_by_window.values())
        assert float(s.pv_mwh[0]) == pytest.approx(
            float(s.charge_mwh[0]) + exported + float(s.curtailed_mwh[0])
        )
    with pytest.raises(ValueError):
        sz.dispatch_columns(pv, idx, curtailment_fraction=1.0, **kw)


# ---------------------------------------------------------------------------
# Distributions, draws and prices
# ---------------------------------------------------------------------------
def test_triangular_ppf_closed_form() -> None:
    t = sz.Triangular(78.75, 135.0, 143.41)
    fc = (135.0 - 78.75) / (143.41 - 78.75)
    assert t.ppf(np.array([0.0, fc, 1.0])) == pytest.approx([78.75, 135.0, 143.41])
    # Vector-only statistics (no model run): the sample mean meets (a + b + c) / 3.
    u = (np.arange(200_000) + 0.5) / 200_000
    assert float(t.ppf(u).mean()) == pytest.approx(
        (78.75 + 135.0 + 143.41) / 3, rel=1e-4
    )
    assert sz.Triangular(0.0, 0.0, 2.0).ppf(np.array([0.0, 0.75]))[1] == pytest.approx(
        1.0
    )
    with pytest.raises(ValueError):
        sz.Triangular.from_mapping({"low": 2.0, "mode": 1.0, "high": 3.0}, "t")


def test_draws_are_seeded_and_row_zero_is_the_base_case(pricing: sz.Pricing) -> None:
    unc = sz.Uncertainty.from_mapping(_yaml(SIZING_CONF)["uncertainty"])
    kw: Dict[str, Any] = dict(
        n_trials=16, pricing=pricing, uncertainty=unc, base_rte=0.85, with_base=True
    )
    a = sz.draw_trials(seed=7, **kw)
    b = sz.draw_trials(seed=7, **kw)
    c = sz.draw_trials(seed=8, **kw)
    assert a.n == 17
    for k in sz.DIMENSIONS:
        assert np.array_equal(a.values[k], b.values[k])
        assert not np.array_equal(a.values[k][1:], c.values[k][1:])
    # Re-pinned for PR 6 capex: the blended BESS mode. Before: 135.0 (the NSO 250 base).
    assert a.values["bess_usd_per_kwh"][0] == 140.74
    assert a.values["bess_usd_per_kwh"][0] == pricing.bess_usd_per_kwh.mode
    assert a.values["module_fob_usd_per_wp"][0] == pricing.module_fob_usd_per_wp.mode
    assert a.values["yield_multiplier"][0] == 1.0
    assert a.values["residual_fade_pct_per_year"][0] == 0.0
    lo, hi = pricing.bess_usd_per_kwh.low, pricing.bess_usd_per_kwh.high
    assert (
        (a.values["bess_usd_per_kwh"] >= lo) & (a.values["bess_usd_per_kwh"] <= hi)
    ).all()


def test_pricing_is_strict_and_reproduces_the_public_bess_build_up() -> None:
    raw = _yaml(PRICING_CONF)
    sz.Pricing.from_mapping(raw)
    bad = copy.deepcopy(raw)
    bad["extra"] = 1
    with pytest.raises(ValueError, match="unknown keys"):
        sz.Pricing.from_mapping(bad)
    bad = copy.deepcopy(raw)
    # PR 6 capex: 135.0 (was 120.0, which now lies below the blended low and trips the
    # triangular check first); it still disagrees with the build-up.
    bad["bess"]["all_in_usd_per_kwh"]["mode"] = 135.0
    with pytest.raises(ValueError, match="build-up"):
        sz.Pricing.from_mapping(bad)
    bad = copy.deepcopy(raw)
    bad["sources"]["OPIS-2026-07-28"]["verbatim"] = []
    with pytest.raises(ValueError, match="verbatim"):
        sz.Pricing.from_mapping(bad)
    # (99.50 + 14.00 + 8.00) / (1 - 0.10) = 135.00, the public all-in.
    assert (99.50 + 14.00 + 8.00) / 0.9 == pytest.approx(135.0)
    # PR 6 capex: the blended build-up in the config reproduces the blended mode, to the
    # parser's tolerance: (103.55 + 15.12 + 8.00) / (1 - 0.10) = 140.744 against 140.74.
    bess = raw["bess"]
    assert bess["equipment_usd_per_kwh_base"] == 103.55
    assert (103.55 + 15.12 + 8.00) / 0.9 == pytest.approx(
        bess["all_in_usd_per_kwh"]["mode"], abs=0.01
    )


def test_inverter_matches_the_pr2_string_and_rejects_a_bad_one(
    pricing: sz.Pricing,
) -> None:
    kw: Dict[str, Any] = dict(
        voc_cold_v=1461.7,
        vmp_hot_v=1076.0,
        vmp_stc_v=1206.5,
        imp_a=15.55,
        isc_a=16.22,
        ac_capacity_mw=5.0,
    )
    m = sz.match_inverter(pricing.inverter, strings=320, **kw)
    assert (
        m.ok and m.inverter_count == 17 and m.fleet_nominal_ac_mw == pytest.approx(5.1)
    )
    # 65 A per MPPT // 15.55 A = 4 strings per tracker, 6 trackers: 24 strings.
    assert m.strings_per_mppt_max == 4 and m.string_capacity_per_inverter == 24
    assert m.strings_per_inverter_max == 19
    assert sz.match_inverter(pricing.inverter, strings=374, **kw).ok  # DC/AC 1.4
    too_many = sz.match_inverter(pricing.inverter, strings=17 * 24 + 1, **kw)
    assert not too_many.checks["strings_fit_inputs_within_current_limit"]
    hot = sz.match_inverter(
        pricing.inverter, strings=320, **{**kw, "voc_cold_v": 1520.0}
    )
    assert not hot.ok and not hot.checks["voc_cold_within_max_dc_voltage"]


# ---------------------------------------------------------------------------
# Unit-only metric: closed form
# ---------------------------------------------------------------------------
def test_unit_pretax_npv_meets_the_annuity_closed_form() -> None:
    r, n, lag = 0.1133, 20, 1
    capex, rev_lkr, fx, opex = 7.0e6, 300.0e6, 333.79, 0.15e6
    flows = sz.unit_pretax_cashflows_usd(
        [rev_lkr] * n,
        capex_usd=capex,
        opex_usd_year1=opex,
        opex_escalation_pct=0.0,
        lkr_per_usd=fx,
        construction_years=lag,
    )
    a = rev_lkr / fx - opex
    annuity = (1.0 - (1.0 + r) ** -n) / r
    assert npv(r, flows) == pytest.approx(
        -capex + a * annuity / (1.0 + r) ** lag, rel=1e-12
    )
    grown = sz.unit_pretax_cashflows_usd(
        [0.0, 0.0],
        capex_usd=0.0,
        opex_usd_year1=100.0,
        opex_escalation_pct=5.0,
        lkr_per_usd=fx,
        construction_years=0,
    )
    assert grown == pytest.approx([0.0, -100.0, -105.0])


# ---------------------------------------------------------------------------
# One grid point through the engine
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def point_ctx(
    unit: Dict[str, Any], pricing: sz.Pricing, tmy_pv: pbd.HourlyPv
) -> tuple[sz.Context, sz.PointInputs]:
    from analytics.gis.pv_array_layout import ModuleSpec

    scenario = _yaml(SCENARIO)
    w = scenario["generation"]["technologies"]["wind"]
    ctx = sz.Context(
        scenario=scenario,
        bess_template=pbd.BessConfig.from_mapping(unit["bess"]),
        dispatch=pbd.DispatchConfig.from_mapping(unit["dispatch"]),
        tariff=pbd.TariffConfig.from_mapping(unit["tariff"]),
        wind=pbd.WindBlock(
            w["capacity_mw"], w["capacity_factor"], w["degradation_pct"]
        ),
        pricing=pricing,
        grid_civils_development_usd=2.0e6,
        fixed_opex_usd_per_year=0.5e6,
    )
    module = ModuleSpec.from_mapping(unit["module"])
    point = sz.PointInputs(
        dc_ac_ratio=1.2,
        dc_mwp=6.0032,
        ac_capacity_mw=5.0,
        bess_power_mw=5.0,
        bess_energy_mwh=20.0,
        pv_base_mw=tmy_pv.ac_mw,
        timestamps_utc=tmy_pv.timestamps_utc,
        warranty=tuple(module.warranted_power_fraction(y) for y in range(1, 21)),
        inverter_count=17,
        inverter_kw=300.0,
    )
    return ctx, point


def _trials(pricing: sz.Pricing, rows: int, **override: list[float]) -> sz.Trials:
    base = {
        "module_fob_usd_per_wp": pricing.module_fob_usd_per_wp.mode,
        "inverter_usd_per_wac": pricing.inverter_usd_per_wac.mode,
        "bop_usd_per_wp": pricing.bop_usd_per_wp.mode,
        "bess_usd_per_kwh": pricing.bess_usd_per_kwh.mode,
        "yield_multiplier": 1.0,
        "round_trip_efficiency": 0.85,
        "residual_fade_pct_per_year": 0.0,
    }
    vals = {k: np.full(rows, v, dtype=float) for k, v in base.items()}
    for k, v in override.items():
        vals[k] = np.asarray(v, dtype=float)
    return sz.Trials(values=vals)


def test_project_npv_falls_with_either_capex(
    point_ctx: tuple[sz.Context, sz.PointInputs], pricing: sz.Pricing
) -> None:
    ctx, point = point_ctx
    t = _trials(pricing, 3, bess_usd_per_kwh=[80.0, 110.0, 140.0])
    res = sz.evaluate_point(ctx, point, t, has_base=False)
    npvs = res.trials["project_npv"]
    assert npvs[0] > npvs[1] > npvs[2]
    assert res.trials["unit_pretax_npv_usd"][0] > res.trials["unit_pretax_npv_usd"][2]
    t = _trials(pricing, 2, bop_usd_per_wp=[0.36, 0.54])
    res = sz.evaluate_point(ctx, point, t, has_base=False)
    assert res.trials["project_npv"][0] > res.trials["project_npv"][1]
    # And it rises with the yield (the revenue side responds too).
    t = _trials(pricing, 2, yield_multiplier=[0.95, 1.05])
    res = sz.evaluate_point(ctx, point, t, has_base=False)
    assert res.trials["project_npv"][1] > res.trials["project_npv"][0]
    assert 3 + 2 + 2 <= _hard_cap()


def test_degenerate_monte_carlo_collapses_to_the_base_case(
    point_ctx: tuple[sz.Context, sz.PointInputs], pricing: sz.Pricing
) -> None:
    ctx, point = point_ctx
    res = sz.evaluate_point(ctx, point, _trials(pricing, 4), has_base=True)
    for m in ("project_npv", "project_irr", "unit_pretax_npv_usd"):
        assert len(res.trials[m]) == 3
        stats = sz.summarise_metric(res.trials[m])
        assert stats["p50"] == pytest.approx(res.base[m], rel=1e-12)
        assert stats["p90"] == pytest.approx(stats["p10"], rel=1e-12)
    # The base case's engine fields reproduce PR 2's dispatcher at this size.
    eng = res.base["engine"]
    assert eng["engine_revenue_lkr"][0] == pytest.approx(
        eng["dispatcher_revenue_lkr"][0], rel=1e-12
    )
    assert eng["max_later_year_gap_pct"] <= 0.5


def test_summary_statistics_follow_the_exceedance_convention() -> None:
    s = sz.summarise_metric(list(range(1, 102)))
    assert s["p50"] == 51.0 and s["p90"] == 11.0 and s["p10"] == 91.0
    assert sz.summarise_metric([float("nan")]) == {"n": 0.0}


# ---------------------------------------------------------------------------
# The run, its config and the committed result
# ---------------------------------------------------------------------------
def _small_cfg() -> Dict[str, Any]:
    cfg = {
        k: v for k, v in _yaml(SIZING_CONF).items() if k not in ("defaults", "hydra")
    }
    cfg["grid"] = {
        "dc_ac_ratios": [1.2, 1.4],
        "bess_energy_mwh": [20.0, 30.0],
        "bess_power_mw": 5.0,
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 6}
    return cfg


def _read_repo(rel: str) -> Any:
    text = (REPO_ROOT / rel).read_text()
    return (
        json.loads(text)
        if rel.endswith((".json", ".geojson"))
        else yaml.safe_load(text)
    )


def test_small_run_counts_its_evaluations_truthfully(unit: Dict[str, Any]) -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    cfg = _small_cfg()
    calls = {"n": 0}

    def counting(**kw: Any) -> Any:
        calls["n"] += 1
        from analytics.evaluation_v14 import evaluate_with_overrides

        return evaluate_with_overrides(**kw)

    run = sz.run_sizing(
        cfg,
        unit_cfg=unit,
        pricing_cfg=_yaml(PRICING_CONF),
        scenario=_yaml(SCENARIO),
        site=sz.site_context(unit, _read_repo),
        evaluator=counting,
    )
    assert run.spec["seed"] == cfg["monte_carlo"]["seed"]
    assert run.spec["requested_trials_per_point"] == 6
    assert run.effective_evaluations == calls["n"] == 4 * (6 + 1) + 4
    assert calls["n"] <= _hard_cap()
    rec = run.recommendation
    chosen = [
        p
        for p in run.points
        if p["dc_ac_ratio_target"] == rec["dc_ac_ratio"]
        and p["bess_energy_mwh"] == rec["bess_energy_mwh"]
    ]
    assert len(chosen) == 1 and chosen[0]["eligible"]
    best = max(p["metrics"]["project_npv"]["p50"] for p in run.points if p["eligible"])
    assert rec["objective_value"] == best
    assert run.curtailment is not None and len(run.curtailment["rows"]) == 4
    assert all("_trials" not in p for p in run.points)
    # 20 MWh delivers 17 MWh, short of the 20 MWh window: evaluated, not eligible.
    by_e = {p["bess_energy_mwh"]: p["meets_dispatch_rule"] for p in run.points}
    assert by_e == {20.0: False, 30.0: True}
    assert rec["bess_energy_mwh"] == 30.0
    assert rec["unconstrained_best"]["objective_value"] >= rec["objective_value"]


def test_priority_window_capability_closed_form(unit: Dict[str, Any]) -> None:
    dcfg = pbd.DispatchConfig.from_mapping(unit["dispatch"])
    for energy, rte in ((30.0, 0.85), (10.0, 0.85), (24.0, 0.85), (23.0, 0.88)):
        cap = sz.priority_window_capability(
            energy_mwh=energy, power_mw=5.0, bess=_bess(unit, energy, rte), cfg=dcfg
        )
        assert cap["priority_window_hours"] == 4.0
        assert cap["window_takes_mwh"] == 20.0
        assert cap["deliverable_mwh"] == pytest.approx(energy * rte)
        assert cap["deliverable_hours_at_power"] == pytest.approx(energy * rte / 5.0)
    # The 4 h threshold sits at 20 / 0.85 = 23.53 MWh.
    assert 23.0 * 0.85 / 5.0 < 4.0 < 24.0 * 0.85 / 5.0


def test_the_turbine_is_not_a_sizing_variable(unit: Dict[str, Any]) -> None:
    scenario = _yaml(SCENARIO)
    scenario["generation"]["technologies"]["wind"]["capex_usd"] = 11.0e6
    with pytest.raises(ValueError, match="not a sizing variable"):
        sz.run_sizing(
            _small_cfg(),
            unit_cfg=unit,
            pricing_cfg=_yaml(PRICING_CONF),
            scenario=scenario,
            site={},
        )
    bad = _small_cfg()
    bad["monte_carlo"]["seed"] = True
    with pytest.raises(ValueError, match="seed"):
        sz.run_sizing(
            bad,
            unit_cfg=unit,
            pricing_cfg=_yaml(PRICING_CONF),
            scenario=_yaml(SCENARIO),
            site={},
        )


def test_committed_summary_carries_a_truthful_spec_and_the_recommendation() -> None:
    summary = json.loads(SUMMARY.read_text())
    spec = summary["spec"]
    n = spec["requested_trials_per_point"]
    curt = summary["curtailment_scenario"]
    rows = 0 if curt is None else len(curt["rows"])
    assert (
        spec["effective_evaluations"] == spec["grid_points_evaluated"] * (n + 1) + rows
    )
    assert spec["seed"] == _yaml(SIZING_CONF)["monte_carlo"]["seed"]
    rec = _yaml(SIZING_CONF)["recommendation"]
    assert rec["dc_ac_ratio"] == summary["recommendation"]["dc_ac_ratio"]
    assert rec["bess_energy_mwh"] == summary["recommendation"]["bess_energy_mwh"]
    fits = [p for p in summary["points"] if p["eligible"]]
    best = max(fits, key=lambda p: p["metrics"]["project_npv"]["p50"])
    assert (best["dc_ac_ratio_target"], best["bess_energy_mwh"]) == (
        rec["dc_ac_ratio"],
        rec["bess_energy_mwh"],
    )
    # The committed summary was produced from the committed pricing config.
    import hashlib

    digest = hashlib.sha256(PRICING_CONF.read_bytes()).hexdigest()
    assert spec["inputs_sha256"]["conf/blue_whale_pv_bess_pricing.yaml"] == digest


def test_scenario_carries_the_recommended_base_case() -> None:
    summary = json.loads(SUMMARY.read_text())
    rec = summary["recommendation"]
    point = next(
        p
        for p in summary["points"]
        if p["dc_ac_ratio_target"] == rec["dc_ac_ratio"]
        and p["bess_energy_mwh"] == rec["bess_energy_mwh"]
    )
    scen = _yaml(SCENARIO)
    techs = scen["generation"]["technologies"]
    eng = point["base"]["engine"]
    solar, b = techs["solar"], techs["bess_1"]
    assert solar["capex_usd"] == pytest.approx(point["capex_usd_base"]["pv"], abs=0.5)
    assert b["capex_usd"] == pytest.approx(point["capex_usd_base"]["bess"], abs=0.5)
    assert b["energy_mwh"] == rec["bess_energy_mwh"]
    assert b["duration_h"] == pytest.approx(rec["bess_energy_mwh"] / b["power_mw"])
    assert solar["capacity_factor"] == pytest.approx(
        eng["solar_capacity_factor"], abs=5e-7
    )
    assert b["revenue"]["cycles_per_year"] == pytest.approx(
        eng["bess_cycles_per_year"], abs=5e-5
    )

    # PR 5 (met-mast transfer) moved the hybrid's wind CF after this sizing ran, so the
    # tariff is checked against the blend formula on the CURRENT wind CF; the same formula
    # on PR 3's frozen wind CF must still reproduce PR 3's frozen tariff (the original
    # oracle, kept rather than dropped).
    def blend(wind_cf: float) -> float:
        e_w = techs["wind"]["capacity_mw"] * wind_cf
        e_s = solar["capacity_mw"] * eng["solar_capacity_factor"]
        return (e_w * 25.73 + e_s * 20.72) / (e_w + e_s)

    # PR 6 capex re-ran this sizing on the current hybrid, so the committed summary's engine
    # tariff is again the blend on the CURRENT wind CF (PR 3's original oracle, restored).
    # PR 5's frozen check is kept as a closed form against PR 3's frozen tariff value,
    # 24.785983774583563 (the summary no longer records it).
    assert blend(0.374256) == pytest.approx(24.785983774583563, abs=5e-5)
    assert eng["tariff_lkr_per_kwh"] == pytest.approx(
        blend(techs["wind"]["capacity_factor"]), abs=5e-5
    )
    assert scen["tariff"]["lkr_per_kwh"] == pytest.approx(
        eng["tariff_lkr_per_kwh"], abs=5e-5
    )
    assert scen["tariff"]["lkr_per_kwh"] == pytest.approx(
        blend(techs["wind"]["capacity_factor"]), abs=5e-5
    )
    assert scen["capex"]["usd_total"] == pytest.approx(
        sum(techs[t]["capex_usd"] for t in ("wind", "solar", "bess_1")) + 2.0e6
    )


def test_hydra_entrypoint_prints_one_json_object(tmp_path: Path) -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "monte_carlo.n_trials=2",
            "grid.dc_ac_ratios=[1.2]",
            "grid.bess_energy_mwh=[30.0]",
            "curtailment_scenario.enabled=false",
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out["config"] == "conf/blue_whale_pv_bess_sizing.yaml"
    assert out["spec"]["effective_evaluations"] == 3 <= _hard_cap()
    assert out["spec"]["seed"] == 20261101
    assert len(out["points"]) == 1 and math.isfinite(
        out["points"][0]["metrics"]["project_npv"]["p50"]
    )
    assert not (tmp_path / "outputs").exists() and not (tmp_path / ".hydra").exists()


def test_cli_module_loads_without_running() -> None:
    spec = importlib.util.spec_from_file_location("bw_sizing_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    assert callable(cli.run)
