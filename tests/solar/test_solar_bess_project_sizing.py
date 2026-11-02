"""Tests for the separate Blue Whale solar + BESS project (PR 4) and its sizing.

``TEST-01`` oracles that did not originate in this change:

* PR 2's scalar dispatcher (``solar_resource.pv_bess_dispatch.dispatch``/``summarise``) is
  the oracle for the array dispatcher with every loss booked on charge, and for the
  engine's revenue on the new scenario (through PR 2's unit CLI);
* closed forms: a full 4 h battery delivers exactly ``4 x P`` in the 17:30-21:30 window and
  draws ``4 x P / RTE`` from the PV; the PUCSL consultation's own tariff formula
  (standalone / RTE + BESS component) reproduces its proposed priority tariff; the wind
  project's year-1 revenue is capacity x CF x 8760 x 25.73;
* invariants over every grid point of the committed run: energy = 4 x power, and no point
  eligible under reading A has PV AC + BESS power above 10 MW;
* the seeded run reproduces itself, and a different seed changes the draws.

``TEST-03``: every test here runs at most 200 model evaluations, asserted against
``config/stochastic_test_policy.yaml``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from solar_resource import pv_bess_dispatch as pbd
from solar_resource import pv_bess_sizing as sz

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess.yaml"
PROJECT_CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess_project_sizing.yaml"
REG_CONF = REPO_ROOT / "conf" / "blue_whale_pucsl_fit_2026.yaml"
PRICING_CONF = REPO_ROOT / "conf" / "blue_whale_pv_bess_pricing.yaml"
SOLAR_BESS = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
HYBRID = REPO_ROOT / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"
SUMMARY = REPO_ROOT / "docs" / "blue_whale" / "solar_bess_project_sizing_summary.json"
UNIT_CLI = REPO_ROOT / "scripts" / "run_blue_whale_solar_bess_v14.py"
POLICY = REPO_ROOT / "config" / "stochastic_test_policy.yaml"

# Pinned at 15.15.0 (v0.1 of each new scenario). TEST-01 responsiveness guards below.
# The solar + BESS project's 20-year CFADS does not recover its capex, so the engine finds
# no project IRR and its KPI reader reports 0.0 (undefined); its NPVs are pinned instead.
SOLAR_BESS_PINS = {
    "project_npv": -4771737.166012999,
    "equity_npv": -5196732.668408366,
    "equity_irr": -0.03275959163948128,
    "min_dscr": 0.8675297318839426,
}
# WIND_PINS re-pinned at 15.16.0 for the PR 5 met-mast transfer (wind v0.2: CF 0.374256 ->
# 0.487560). Before, at 15.15.0 (v0.1): project IRR 0.04085210230412145, equity IRR
# 0.014728921618622381, min DSCR 0.868369272868335.
WIND_PINS = {
    "project_irr": 0.07798231364379474,
    "equity_irr": 0.053445387955278756,
    "min_dscr": 0.8682973694248998,
}


def _yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


def _hard_cap() -> int:
    return int(_yaml(POLICY)["ordinary_suite"]["hard_max_model_evaluations"])


def _project_cfg() -> Dict[str, Any]:
    return {
        k: v for k, v in _yaml(PROJECT_CONF).items() if k not in ("defaults", "hydra")
    }


def _project_unit() -> Dict[str, Any]:
    return sz.apply_unit_overrides(_yaml(UNIT_CONF), _project_cfg()["unit_overrides"])


def _kpis(path: Path, overrides: Dict[str, Any] | None = None) -> Dict[str, float]:
    out = evaluate_with_overrides(str(path), overrides=overrides or {})
    return {k: float(v) for k, v in out.items() if isinstance(v, (int, float))}


# ---------------------------------------------------------------------------
# The regulatory basis and the overrides
# ---------------------------------------------------------------------------
def test_regulatory_basis_meets_the_consultations_own_closed_forms() -> None:
    raw = _yaml(REG_CONF)
    reg = sz.RegulatoryBasis.from_mapping(raw)
    assert reg.discharge_duration_h == 4.0 and reg.losses_on_charge
    assert (reg.window_start_local, reg.window_end_local) == ("17:30", "21:30")
    assert reg.priority_lkr_per_kwh == pytest.approx(47.08 + 3.02)
    assert reg.other_lkr_per_kwh == pytest.approx(18.00 + 2.72)
    assert reg.wind_lkr_per_kwh == pytest.approx(20.80 + 4.93)
    assert reg.contract_years == 15 and reg.max_capacity_mw == 10.0
    # Consultation Annex 2 s.3.1: 21.58 / 0.90 + 27.57 = 51.55, its proposed PFT tariff.
    assert 21.58 / 0.90 + 27.57 == pytest.approx(51.55, abs=0.005)
    # Negative controls: each closed form fires.
    bad = copy.deepcopy(raw)
    bad["consultation_reference_case"]["round_trip_efficiency"] = 0.95
    with pytest.raises(ValueError, match="priority tariff"):
        sz.RegulatoryBasis.from_mapping(bad)
    bad = copy.deepcopy(raw)
    bad["tariff_lkr_per_kwh"]["components"]["solar_bess_priority"] = [47.08, 3.20]
    with pytest.raises(ValueError, match="solar_bess_priority"):
        sz.RegulatoryBasis.from_mapping(bad)
    bad = copy.deepcopy(raw)
    bad["consultation_reference_case"]["first_year_discharge_gwh"] = 1.241
    with pytest.raises(ValueError, match="first-year discharge"):
        sz.RegulatoryBasis.from_mapping(bad)
    bad = copy.deepcopy(raw)
    del bad["sources"]["SL-ELECTRICITY-ACT-36-2024"]["verbatim"]
    with pytest.raises(ValueError, match="verbatim"):
        sz.RegulatoryBasis.from_mapping(bad)


def test_regulatory_check_refuses_a_config_that_departs_from_the_rules() -> None:
    reg = sz.RegulatoryBasis.from_mapping(_yaml(REG_CONF))
    unit = _project_unit()
    kw: Dict[str, Any] = dict(
        dispatch=pbd.DispatchConfig.from_mapping(unit["dispatch"]),
        tariff=pbd.TariffConfig.from_mapping(unit["tariff"]),
        bess=pbd.BessConfig.from_mapping(unit["bess"]),
        duration_h=4.0,
    )
    reg.check(**kw)  # the committed project config passes
    with pytest.raises(ValueError, match="4.0 h"):
        reg.check(**{**kw, "duration_h": 6.0})
    # PR 2's unit config keeps the morning window: refused for the project.
    pr2 = _yaml(UNIT_CONF)
    with pytest.raises(ValueError, match="one priority window"):
        reg.check(
            **{**kw, "dispatch": pbd.DispatchConfig.from_mapping(pr2["dispatch"])}
        )
    # PR 2's loss-on-discharge convention: refused (the nameplate is delivered energy).
    with pytest.raises(ValueError, match="charge_efficiency"):
        reg.check(**{**kw, "bess": pbd.BessConfig.from_mapping(pr2["bess"])})
    wrong = pbd.TariffConfig.from_mapping(
        {**unit["tariff"], "priority_lkr_per_kwh": 51.55}
    )
    with pytest.raises(ValueError, match="Annex 2"):
        reg.check(**{**kw, "tariff": wrong})


def test_unit_overrides_replace_only_existing_keys() -> None:
    unit = _project_unit()
    assert list(unit["dispatch"]["windows"]) == ["evening"]
    assert unit["dispatch"]["export_limit_mw"] == 10.0
    assert unit["bess"]["charge_efficiency"] == unit["bess"]["round_trip_efficiency"]
    assert _yaml(UNIT_CONF)["bess"]["charge_efficiency"] == 1.0  # PR 2 file untouched
    with pytest.raises(ValueError, match="not in the unit config"):
        sz.apply_unit_overrides(_yaml(UNIT_CONF), {"bess.new_key": 1})
    with pytest.raises(ValueError, match="not in the unit config"):
        sz.apply_unit_overrides(_yaml(UNIT_CONF), {"nothing.here": 1})


def test_reading_a_and_b_admit_what_they_say() -> None:
    cfg = _project_cfg()["readings"]
    a = {k: cfg["A"][k] for k in sz.READING_KEYS}
    b = {k: cfg["B"][k] for k in sz.READING_KEYS}
    kw = dict(export_limit_mw=10.0)
    assert sz.reading_allows(a, pv_ac_mw=5.0, bess_power_mw=5.0, **kw)
    assert not sz.reading_allows(a, pv_ac_mw=5.5, bess_power_mw=5.0, **kw)
    assert sz.reading_allows(b, pv_ac_mw=7.0, bess_power_mw=9.0, **kw)
    assert not sz.reading_allows(b, pv_ac_mw=7.0, bess_power_mw=10.5, **kw)
    # B relies on the export limit: a dispatch not held to 10 MW is not reading B.
    assert not sz.reading_allows(
        b, pv_ac_mw=7.0, bess_power_mw=9.0, export_limit_mw=12.0
    )
    # A reading with neither a combined nor an export limit admits nothing.
    loose = {**b, "max_export_mw": None}
    assert not sz.reading_allows(loose, pv_ac_mw=1.0, bess_power_mw=1.0, **kw)


# ---------------------------------------------------------------------------
# The 4 h rule against PR 2's dispatcher and closed forms
# ---------------------------------------------------------------------------
def _days(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01T00:00", periods=24 * n, freq="h", tz="UTC")


def test_a_full_4h_battery_delivers_4p_in_the_window_and_draws_4p_over_rte() -> None:
    unit = _project_unit()
    idx = _days(5)
    local = idx.tz_convert("Asia/Colombo")
    minute = local.hour * 60 + local.minute
    # 8 MW of PV from 06:30 to 16:30 local: far more than the battery needs.
    pv = np.where((minute >= 390) & (minute < 990), 8.0, 0.0)
    dcfg = pbd.DispatchConfig.from_mapping(unit["dispatch"])
    tariff = pbd.TariffConfig.from_mapping(unit["tariff"])
    for power, rte in ((4.5, 0.85), (2.0, 0.82), (9.0, 0.88)):
        bess = pbd.BessConfig.from_mapping(
            {
                **unit["bess"],
                "power_mw": power,
                "energy_mwh": 4.0 * power,
                "round_trip_efficiency": rte,
                "charge_efficiency": rte,
            }
        )
        series = pbd.dispatch(pv, idx, bess, dcfg)
        year = pbd.summarise(series, bess, dcfg, tariff)
        days = 5
        assert year.discharge_mwh == pytest.approx(4.0 * power * days)
        assert year.charge_mwh == pytest.approx(4.0 * power / rte * days)
        assert year.export_mwh_by_rate["priority"] == pytest.approx(4.0 * power * days)
        # Every window hour runs at full power; no discharge outside it.
        in_window = series.window >= 0
        assert np.allclose(series.discharge_mw[in_window], power)
        assert not series.discharge_mw[~in_window].any()
        # The array dispatcher agrees with the scalar oracle, losses on charge.
        sums = sz.dispatch_columns(
            pv,
            idx,
            scale=np.array([1.0]),
            energy_mwh=np.array([4.0 * power]),
            round_trip_efficiency=np.array([rte]),
            bess=bess,
            cfg=dcfg,
            charge_efficiency=np.array([rte]),
        )
        assert float(sums.discharge_mwh_by_window["evening"][0]) == pytest.approx(
            year.discharge_mwh
        )
        assert float(sums.charge_mwh[0]) == pytest.approx(year.charge_mwh)


@pytest.fixture(scope="module")
def tmy_pv() -> pbd.HourlyPv:
    pytest.importorskip("pvlib")
    from analytics.gis.pv_array_layout import (
        ArrayConfig,
        ModuleSpec,
        StringDesignConfig,
        design_string,
        size_array,
    )

    unit = _project_unit()
    module = ModuleSpec.from_mapping(unit["module"])
    strings = design_string(
        module, StringDesignConfig.from_mapping(unit["string_design"])
    )
    arr = ArrayConfig.from_mapping(
        {**unit["array"], "ac_capacity_mw": 6.0, "dc_ac_ratio": 191 * 37520.0 / 6.0e6}
    )
    sizing = size_array(module, strings, arr)
    assert sizing.tables == 191
    solar = pbd.with_array(
        {**unit["pv_yield"]["resource_solar"], "inverter_eff_nom": 0.988},
        dc_capacity_mw=sizing.dc_capacity_mw,
        dc_ac_ratio=sizing.dc_ac_ratio,
        tilt_deg=arr.tilt_deg,
        azimuth_deg=arr.azimuth_deg,
        gamma_pdc_per_c=module.temp_coeff_pmax_pct_per_c / 100.0,
    )
    return pbd.hourly_pv(solar)


def test_array_dispatcher_with_losses_on_charge_reproduces_pr2_on_the_tmy(
    tmy_pv: pbd.HourlyPv,
) -> None:
    unit = _project_unit()
    dcfg = pbd.DispatchConfig.from_mapping(unit["dispatch"])
    tariff = pbd.TariffConfig.from_mapping(unit["tariff"])
    cols = [(0.99, 4.0, 0.85), (1.05, 5.0, 0.82), (0.93, 9.0, 0.88), (0.99, 1.0, 0.85)]
    template = pbd.BessConfig.from_mapping(unit["bess"])
    sums = sz.dispatch_columns(
        tmy_pv.ac_mw,
        tmy_pv.timestamps_utc,
        scale=np.array([c[0] for c in cols]),
        energy_mwh=np.array([4.0 * c[1] for c in cols]),
        round_trip_efficiency=np.array([c[2] for c in cols]),
        bess=pbd.BessConfig.from_mapping({**unit["bess"], "power_mw": 4.0}),
        cfg=dcfg,
        charge_efficiency=np.array([c[2] for c in cols]),
    )
    # Different powers need their own call; check each column's power separately.
    for j, (scale, power, rte) in enumerate(cols):
        bess = pbd.BessConfig.from_mapping(
            {
                **unit["bess"],
                "power_mw": power,
                "energy_mwh": 4.0 * power,
                "round_trip_efficiency": rte,
                "charge_efficiency": rte,
            }
        )
        one = sz.dispatch_columns(
            tmy_pv.ac_mw,
            tmy_pv.timestamps_utc,
            scale=np.array([scale]),
            energy_mwh=np.array([4.0 * power]),
            round_trip_efficiency=np.array([rte]),
            bess=bess,
            cfg=dcfg,
            charge_efficiency=np.array([rte]),
        )
        ref = pbd.summarise(
            pbd.dispatch(tmy_pv.ac_mw * scale, tmy_pv.timestamps_utc, bess, dcfg),
            bess,
            dcfg,
            tariff,
            pv_factor=scale,
        )
        got = sz.annual_energy(
            one,
            0,
            windows=dcfg.windows,
            tariff=tariff,
            year=1,
            pv_factor=scale,
            usable_mwh=bess.usable_mwh,
            discharge_efficiency=bess.discharge_efficiency,
        )
        assert got.revenue_lkr == pytest.approx(ref.revenue_lkr, rel=1e-10)
        assert got.charge_mwh == pytest.approx(ref.charge_mwh, rel=1e-10)
        assert got.discharge_mwh == pytest.approx(ref.discharge_mwh, rel=1e-10)
        assert got.curtailed_mwh == pytest.approx(ref.curtailed_mwh, abs=1e-8)
        if power == 4.0:  # the shared-power call agrees for its own power
            assert float(sums.charge_mwh[j]) == pytest.approx(ref.charge_mwh, rel=1e-10)
    assert template.discharge_efficiency == pytest.approx(1.0)
    # A charge efficiency below a column's RTE is refused.
    with pytest.raises(ValueError, match="charge_efficiency"):
        sz.dispatch_columns(
            tmy_pv.ac_mw,
            tmy_pv.timestamps_utc,
            scale=np.array([1.0]),
            energy_mwh=np.array([16.0]),
            round_trip_efficiency=np.array([0.88]),
            bess=template,
            cfg=dcfg,
            charge_efficiency=np.array([0.85]),
        )


# ---------------------------------------------------------------------------
# A small run: truthful counts and seed reproducibility
# ---------------------------------------------------------------------------
def _small(seed: int = 20261101) -> Dict[str, Any]:
    cfg = _project_cfg()
    cfg["grid"] = {
        **cfg["grid"],
        "pv_tables": ["land_max"],
        "pv_ac_mw": [5.0, 6.0],
        "bess_power_mw": [4.0, 5.0],
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 4, "seed": seed}
    return cfg


def _read_repo(rel: str) -> Any:
    text = (REPO_ROOT / rel).read_text()
    return (
        json.loads(text)
        if rel.endswith((".json", ".geojson"))
        else yaml.safe_load(text)
    )


@pytest.fixture(scope="module")
def site() -> Dict[str, Any]:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    return sz.site_context(_yaml(UNIT_CONF), _read_repo)


def _run(cfg: Dict[str, Any], site: Dict[str, Any], evaluator: Any) -> sz.SizingRun:
    return sz.run_project_sizing(
        cfg,
        unit_cfg=_yaml(UNIT_CONF),
        pricing_cfg=_yaml(PRICING_CONF),
        regulatory_cfg=_yaml(REG_CONF),
        scenario=_yaml(SOLAR_BESS),
        site=site,
        evaluator=evaluator,
    )


def test_small_run_is_truthful_reproducible_and_obeys_both_readings(
    site: Dict[str, Any],
) -> None:
    calls = {"n": 0}

    def counting(**kw: Any) -> Any:
        calls["n"] += 1
        return evaluate_with_overrides(**kw)

    first = _run(_small(), site, counting)
    n_points = first.spec["grid_points_evaluated"]
    assert n_points == 4
    # 4 points x (4 trials + base) + 4 curtailment + 4 RTE-sensitivity cases.
    assert first.effective_evaluations == calls["n"] == 4 * 5 + 4 + 4
    again = _run(_small(), site, evaluate_with_overrides)
    other = _run(_small(seed=7), site, evaluate_with_overrides)
    assert 2 * calls["n"] + other.effective_evaluations <= _hard_cap()
    assert json.dumps(first.points, sort_keys=True) == json.dumps(
        again.points, sort_keys=True
    )
    assert first.recommendation == again.recommendation
    p50 = [p["metrics"]["unit_pretax_npv_usd"]["p50"] for p in first.points]
    assert p50 != [p["metrics"]["unit_pretax_npv_usd"]["p50"] for p in other.points]
    # The base case does not depend on the seed.
    assert [p["base"]["unit_pretax_npv_usd"] for p in first.points] == [
        p["base"]["unit_pretax_npv_usd"] for p in other.points
    ]
    by = {(p["pv_ac_mw"], p["bess_power_mw"]): p for p in first.points}
    assert not by[(6.0, 5.0)]["eligible_by_reading"]["A"]  # 11 MW under reading A
    assert by[(6.0, 5.0)]["eligible_by_reading"]["B"]
    rec = first.recommendation["by_reading"]
    a = rec["A"]["size"]
    assert a["pv_ac_mw"] + a["bess_power_mw"] <= 10.0
    assert rec["B"]["objective_value"] >= rec["A"]["objective_value"]
    for p in first.points:
        assert p["bess_energy_mwh"] == pytest.approx(4.0 * p["bess_power_mw"])
        assert p["meets_4h_rule"]


def test_project_sizing_refuses_the_turbine_and_a_bad_duration(
    site: Dict[str, Any],
) -> None:
    hybrid = _yaml(HYBRID)
    with pytest.raises(ValueError, match="must not carry the turbine"):
        sz.run_project_sizing(
            _small(),
            unit_cfg=_yaml(UNIT_CONF),
            pricing_cfg=_yaml(PRICING_CONF),
            regulatory_cfg=_yaml(REG_CONF),
            scenario=hybrid,
            site=site,
        )
    bad = _small()
    bad["grid"]["bess_duration_h"] = 6.0
    with pytest.raises(ValueError, match="PUCSL"):
        _run(bad, site, evaluate_with_overrides)
    bad = _small()
    bad["readings"]["B"]["max_export_mw"] = 12.0
    with pytest.raises(ValueError, match="statutory limit"):
        _run(bad, site, evaluate_with_overrides)


# ---------------------------------------------------------------------------
# The committed run and the scenarios it writes
# ---------------------------------------------------------------------------
def _summary() -> Dict[str, Any]:
    data = json.loads(SUMMARY.read_text())
    assert isinstance(data, dict)
    return data


def test_committed_summary_is_truthful_and_matches_the_config() -> None:
    summary = _summary()
    spec = summary["spec"]
    cfg = _project_cfg()
    n = spec["requested_trials_per_point"]
    pts = spec["grid_points_evaluated"]
    assert spec["effective_evaluations"] == pts * (n + 1) + 2 * pts
    assert spec["git_sha"] != "unknown" and spec["result_sha256"]
    assert spec["seed"] == cfg["monte_carlo"]["seed"] == 20261101
    assert n == cfg["monte_carlo"]["n_trials"] == 256
    assert spec["losses_on_charge"] and spec["bess_duration_h"] == 4.0
    assert spec["export_limit_mw"] == 10.0
    assert [w["name"] for w in spec["dispatch_windows"]] == ["evening"]
    for role in ("committed", "alternative"):
        want = cfg["recommendation"][role]
        got = summary["recommendation"]["by_reading"][want["reading"]]["size"]
        assert (got["pv_tables"], got["pv_ac_mw"], got["bess_power_mw"]) == (
            want["pv_tables"],
            want["pv_ac_mw"],
            want["bess_power_mw"],
        ), role
    assert cfg["recommendation"]["committed"]["reading"] == cfg["readings"]["committed"]
    import hashlib

    for rel in (
        "conf/blue_whale_pv_bess_pricing.yaml",
        "conf/blue_whale_pucsl_fit_2026.yaml",
        "conf/blue_whale_solar_bess.yaml",
    ):
        digest = hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        assert spec["inputs_sha256"][rel] == digest, rel


def _grid_rows() -> list[Dict[str, Any]]:
    grid = _summary()["grid"]
    return [dict(zip(grid["columns"], row, strict=True)) for row in grid["rows"]]


def test_every_committed_point_obeys_the_4h_rule_and_its_readings() -> None:
    summary = _summary()
    limit = 10.0
    rows = _grid_rows()
    assert len(rows) == summary["spec"]["grid_points"]
    for p in rows:
        assert p["bess_energy_mwh"] == pytest.approx(4.0 * p["bess_power_mw"])
        assert p["meets_4h_rule"]
        assert 1.0 - 1e-9 <= p["dc_ac_ratio"] <= 1.5 + 1e-9
        if p["eligible_A"]:
            assert p["pv_ac_mw"] + p["bess_power_mw"] <= limit + 1e-9
            assert p["fits"]
        if p["eligible_B"]:
            assert p["pv_ac_mw"] <= limit and p["bess_power_mw"] <= limit
    rec = summary["recommendation"]
    for name in ("A", "B"):
        size = rec["by_reading"][name]["size"]
        ok = [r for r in rows if r[f"eligible_{name}"]]
        best = max(ok, key=lambda r: r["unit_pretax_npv_usd_p50"])
        assert (best["pv_tables"], best["pv_ac_mw"], best["bess_power_mw"]) == (
            size["pv_tables"],
            size["pv_ac_mw"],
            size["bess_power_mw"],
        ), name
    a = rec["by_reading"]["A"]["size"]
    assert a["pv_ac_mw"] + a["bess_power_mw"] <= limit
    land_max = summary["spec"]["land_max_tables_by_bess_power_mw"]
    lm = rec["by_reading"]["A"]["land_max_pv"]["size"]
    assert lm["pv_tables"] == land_max[str(lm["bess_power_mw"])]
    rev = rec["revenue_max_any_reading"]
    assert rev["allowed_by_reading"]["B"]
    if not rev["allowed_by_reading"]["A"]:
        assert rev["size"]["pv_ac_mw"] + rev["size"]["bess_power_mw"] > limit


def _committed_point() -> Dict[str, Any]:
    summary = _summary()
    size = summary["recommendation"]["by_reading"]["A"]["size"]
    return next(
        p
        for p in summary["named_points"]
        if (p["pv_tables"], p["pv_ac_mw"], p["bess_power_mw"])
        == (size["pv_tables"], size["pv_ac_mw"], size["bess_power_mw"])
    )


def test_solar_bess_scenario_carries_the_committed_base_case() -> None:
    point = _committed_point()
    scen = _yaml(SOLAR_BESS)
    techs = scen["generation"]["technologies"]
    assert set(techs) == {"solar", "bess_1"}
    eng = point["base"]["engine"]
    solar, b = techs["solar"], techs["bess_1"]
    assert solar["capacity_mw"] == point["pv_ac_mw"] == scen["project"]["capacity_mw"]
    assert b["power_mw"] == point["bess_power_mw"]
    assert b["energy_mwh"] == pytest.approx(4.0 * b["power_mw"])
    assert b["duration_h"] == 4.0
    assert solar["capex_usd"] == pytest.approx(point["capex_usd_base"]["pv"], abs=0.5)
    assert b["capex_usd"] == pytest.approx(point["capex_usd_base"]["bess"], abs=0.5)
    assert solar["capacity_factor"] == pytest.approx(
        eng["solar_capacity_factor"], abs=5e-7
    )
    assert scen["project"]["capacity_factor"] == solar["capacity_factor"]
    assert b["revenue"]["cycles_per_year"] == pytest.approx(
        eng["bess_cycles_per_year"], abs=5e-5
    )
    assert b["revenue"]["mdsc_fade_pct_annual"] == pytest.approx(
        eng["bess_mdsc_fade_pct_annual"], abs=5e-7
    )
    assert b["revenue"]["tariff_lkr_per_kwh"] == pytest.approx(50.10 - 20.72)
    assert scen["tariff"]["lkr_per_kwh"] == pytest.approx(eng["tariff_lkr_per_kwh"])
    assert scen["capex"]["usd_total"] == pytest.approx(
        solar["capex_usd"] + b["capex_usd"] + 2.0e6
    )
    for path in (SOLAR_BESS, WIND, HYBRID):
        assert "contiguous" in path.read_text(), path.name


def test_solar_bess_engine_revenue_equals_the_pr2_dispatcher() -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    spec = importlib.util.spec_from_file_location("bw_unit_cli_pr4", UNIT_CLI)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    point = _committed_point()
    conf = _project_unit()
    inverter = _yaml(PRICING_CONF)["inverter"]
    conf["array"]["ac_capacity_mw"] = point["pv_ac_mw"]
    conf["array"]["dc_ac_ratio"] = point["dc_ac_ratio"]
    conf["bess"]["power_mw"] = point["bess_power_mw"]
    conf["bess"]["energy_mwh"] = point["bess_energy_mwh"]
    conf["pv_yield"]["resource_solar"]["inverter_eff_nom"] = inverter[
        "european_efficiency"
    ]
    conf["engine"]["scenario"] = str(SOLAR_BESS.relative_to(REPO_ROOT))
    out = cli.run(conf)
    assert out["array"]["tables"] == point["pv_tables"]
    dispatcher = out["engine"]["dispatcher_revenue_lkr"]
    full = evaluate_with_overrides(
        str(SOLAR_BESS), overrides={}, return_full_result=True
    )
    assert isinstance(full, dict)
    rows = full["annual_rows"]
    assert len(rows) == len(dispatcher) == 20
    engine = [r["generation_revenue_lkr"] + r["bess_revenue_lkr"] for r in rows]
    assert engine[0] == pytest.approx(dispatcher[0], rel=1e-4)
    tol = conf["engine"]["later_year_revenue_tolerance_pct"] / 100.0
    for year, (e, d) in enumerate(zip(engine, dispatcher, strict=True), start=1):
        assert e == pytest.approx(d, rel=tol), year
    assert rows[14]["bess_revenue_lkr"] > 0 and rows[15]["bess_revenue_lkr"] == 0
    # The dispatcher's own year 1: one window, no morning discharge, delivered = 4 x P
    # on a full day, so the year's discharge is at most 365 x 4 x P.
    y1 = out["dispatch"]["year1"]
    assert list(y1["discharge_mwh_by_window"]) == ["evening"]
    assert y1["discharge_mwh"] <= 365 * point["bess_energy_mwh"] + 1e-6


# ---------------------------------------------------------------------------
# KPI pins with responsiveness guards
# ---------------------------------------------------------------------------
def test_solar_bess_kpi_pins_and_responsiveness() -> None:
    base = _kpis(SOLAR_BESS)
    for key, pinned in SOLAR_BESS_PINS.items():
        assert base[key] == pytest.approx(pinned, rel=1e-9, abs=1e-12), key
    # No project IRR: the 20-year CFADS sum is below the capex, so NPV < 0 at every rate.
    assert base["project_irr"] == 0.0
    full = evaluate_with_overrides(
        str(SOLAR_BESS), overrides={}, return_full_result=True
    )
    assert isinstance(full, dict)
    assert "project_irr" not in full["metrics"]
    cfads = sum(r["cfads_usd"] for r in full["annual_rows"])
    assert cfads < _yaml(SOLAR_BESS)["capex"]["usd_total"]
    scen = _yaml(SOLAR_BESS)
    techs = scen["generation"]["technologies"]
    rev = techs["bess_1"]["revenue"]
    lower = _kpis(
        SOLAR_BESS,
        {
            "generation.technologies.bess_1.revenue.tariff_lkr_per_kwh": rev[
                "tariff_lkr_per_kwh"
            ]
            * 0.5
        },
    )
    assert lower["project_npv"] < base["project_npv"]
    extra = techs["bess_1"]["capex_usd"] * 0.2
    dearer = _kpis(
        SOLAR_BESS,
        {
            "generation.technologies.bess_1.capex_usd": techs["bess_1"]["capex_usd"]
            + extra,
            "capex.usd_total": scen["capex"]["usd_total"] + extra,
        },
    )
    assert dearer["project_npv"] < base["project_npv"]
    cf = techs["solar"]["capacity_factor"] * 1.05
    brighter = _kpis(
        SOLAR_BESS,
        {
            "generation.technologies.solar.capacity_factor": cf,
            "project.capacity_factor": cf,
        },
    )
    assert brighter["project_npv"] > base["project_npv"]


def test_wind_project_revenue_closed_form_pins_and_responsiveness() -> None:
    scen = _yaml(WIND)
    techs = scen["generation"]["technologies"]
    assert set(techs) == {"wind"}
    reg = sz.RegulatoryBasis.from_mapping(_yaml(REG_CONF))
    assert scen["tariff"]["lkr_per_kwh"] == reg.wind_lkr_per_kwh
    hybrid_wind = _yaml(HYBRID)["generation"]["technologies"]["wind"]
    for key in ("capacity_mw", "capacity_factor", "aep_gwh", "capex_usd"):
        assert techs["wind"][key] == hybrid_wind[key], key
    full = evaluate_with_overrides(str(WIND), overrides={}, return_full_result=True)
    assert isinstance(full, dict)
    w = techs["wind"]
    assert full["annual_rows"][0]["generation_revenue_lkr"] == pytest.approx(
        w["capacity_mw"] * w["capacity_factor"] * 8760.0 * 1000.0 * 25.73, rel=1e-9
    )
    base = _kpis(WIND)
    for key, pinned in WIND_PINS.items():
        assert base[key] == pytest.approx(pinned, rel=1e-9, abs=1e-12), key
    cf = w["capacity_factor"] * 1.05
    windier = _kpis(
        WIND,
        {
            "generation.technologies.wind.capacity_factor": cf,
            "project.capacity_factor": cf,
        },
    )
    assert windier["project_irr"] > base["project_irr"]
    cheaper = _kpis(WIND, {"tariff.lkr_per_kwh": 25.73 * 0.9})
    assert cheaper["project_irr"] < base["project_irr"]
