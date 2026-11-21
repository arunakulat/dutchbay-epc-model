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

PR 7 (ranked on the after-tax project NPV) adds:

* ``finance.irr.npv`` over the capex and the engine's post-tax CFADS reproduces the objective
  on the committed scenario, and CFADS = pre-tax CFADS - tax - haircut year by year;
* reading A at its limit (PV AC + BESS power = 10 MW exactly) and E = 4P at every point of
  a one-battery run; the choice is the best P50 of the metric the config names.

The battery optimisation (owner, 2026-11-07: "Whatever the optimiser picks") adds:

* the battery's O&M on DC kWh matches the scenario's ``bess_om`` component;
* a shifted case moves only its named input, and refuses the rest;
* the one-at-a-time cases and the break-even searches are counted, and respond to their
  inputs; the committed scenario reproduces the chosen point's base case with no override.

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
# Re-pinned at 15.17.0 for PR 6 capex: the blended BESS price re-sized the project (v0.2:
# 107 tables, 3.5 MW AC, 1.0 MW / 4.0 MWh). Before, at 15.15.0-15.16.0 (v0.1): project NPV
# -4771737.166012999, equity NPV -5196732.668408366, equity IRR -0.03275959163948128, min DSCR
# 0.8675297318839426.
# Re-pinned at 15.18.0 for PR 7: the owner's battery, 5.0 MW / 20.0 MWh, with the PV DC chosen
# on the after-tax project NPV (v0.3: 151 tables, 5.0 MW AC). Before, at 15.17.0 (v0.2): project
# NPV -4027655.5031581176, equity NPV -4094171.9053015206, equity IRR -0.11324848332854087, min
# DSCR 0.8669721833235606.
# Re-pinned for #1398 (P2-F3-01 debt-service shortfall carried as sponsor cure in years 1 and
# 16-20; before: equity NPV -5395403.401365028, equity IRR -0.03575607324588892).
# Re-pinned at 15.19.0 for the turbine's shadow on the PV (input B33; v0.4, size unchanged at
# 151 tables). Before, at 15.18.0 after #1398 (v0.3): project NPV -4992408.759406766, equity
# NPV -5564410.144390165, equity IRR -0.08317620969932149, min DSCR 0.867987057099332.
# Re-pinned at 15.20.0 for the opex currency split (v0.5: BESS O&M at USD 1.80/kWh-yr on
# 22,000 kWh DC, converted to LKR at the wind project's value date, 333.79; every line in LKR)
# and one construction period (Financing_Terms.construction_periods 1 = B30; the engine
# defaulted to 2).
# Before, at 15.19.0 (v0.4, the turbine's shadow): project NPV -4997611.258776674, equity NPV
# -5568837.4281859165, equity IRR -0.0843625813445068, min DSCR 0.8676222789656864.
# Re-pinned at 15.21.0 for the PUCSL escalable O&M indexation (L-9, v0.6: the 2.72 other-period
# O&M part and the premium's 0.30 indexed at 3.21%/yr). Before, at 15.20.0 (v0.5): project NPV
# -4517260.638496677, equity NPV -5146449.112710573, equity IRR -0.06998004779138234, min DSCR
# 0.8673920535047875.
# Re-pinned at 15.22.0 for the turbine standing on DutchBay T2 (v0.7: the shadow moves and the
# fixed-battery run picks 152 tables; solar O&M on 5,703.04 kWp). Before, at 15.21.0 (v0.6):
# project NPV -4439869.942132653, equity NPV -5073779.560724569, equity IRR
# -0.051245236683051254, min DSCR 0.8673920535047875.
# Re-pinned at 15.26.0 for the 2026 price dates (#1569, v0.8: capex escalated 5%/yr to the
# 2028 draw, x 1.1025; opex and the PUCSL O&M index escalated from 2026, three years before the
# 2029 COD). The equity cash flows then have no IRR: their NPV is negative at every rate (the
# sponsor cures in years 16-20 outweigh the distributions at any negative rate). Before, at
# 15.24.0 (v0.7): project NPV -4439999.608625973, equity NPV -5075831.700126602, equity IRR
# -0.04998720726172046, min DSCR 0.8681005901376199.
# Re-pinned for the battery search (v0.9: 107 tables, 3.5 MW AC and 0.1 MW / 0.4 MWh, the
# search grid's floor on every decision variable, sized on this scenario's own basis; owner,
# 2026-11-07: "Whatever the optimiser picks"; 2026-11-14: "Battery floor 0.1 MW, PV
# unchanged"). Equity IRR stays undefined. Before (v0.8): project NPV -5579964.010141663,
# equity NPV -6167136.817522649, min DSCR 0.868213653807526. (A first v0.9 at the 0.5 MW
# floor, never on main: project NPV -4518152.075386281, equity NPV -4628674.688512776, min
# DSCR 0.8702721240311019.)
# Re-pinned for v0.10 (#1578 L-11: the battery's fade and its year-14 augmentation, with the
# price's augmentation reserve removed; the size is unchanged). Before (v0.9): project NPV
# -4477786.514808497, equity NPV -4557056.390826946, min DSCR 0.8716987467623586.
SOLAR_BESS_PINS = {
    "project_npv": -4479213.671770833,
    "equity_npv": -4557963.632064052,
    "equity_irr": None,
    "min_dscr": 0.8719255106683012,
}
# WIND_PINS re-pinned at 15.16.0 for the PR 5 met-mast transfer (wind v0.2: CF 0.374256 ->
# 0.487560). Before, at 15.15.0 (v0.1): project IRR 0.04085210230412145, equity IRR
# 0.014728921618622381, min DSCR 0.868369272868335.
# Re-pinned at 15.17.0 for PR 6 capex (wind v0.3: turbine capex 12,350,000 -> 8,899,980,
# blended). Before, at 15.16.0 (v0.2): project IRR 0.07798231364379474, equity IRR
# 0.053445387955278756, min DSCR 0.8682973694248998.
# Re-pinned for #1398 (P2-F3-01 debt-service shortfall carried as sponsor cure in year 1;
# before: equity IRR 0.09064100100108274).
# Re-pinned at 15.20.0 for the opex currency split (wind v0.4: wind O&M 70% USD / 30% LKR,
# overhead LKR; the USD share on a relative-PPP LKR depreciation path, 1.05 / 1.025 - 1) and
# one construction period (Financing_Terms.construction_periods 1 = B30; the engine defaulted to 2).
# Before (v0.3): project IRR 0.10808262995624021, equity IRR 0.0863203211939878, min DSCR
# 0.8679985938194438.
# Re-pinned at 15.21.0 for the PUCSL escalable O&M indexation (L-9, wind v0.5: the 4.93 O&M
# part indexed at 3.21%/yr). Before, at 15.20.0 (v0.4): project IRR 0.1240563483741687,
# equity IRR 0.10542705973481747, min DSCR 0.8668689564723109.
# Re-pinned at 15.26.0 for the 2026 price dates (#1569, wind v0.6: capex escalated 5% to the
# 2027 draw; opex and the PUCSL O&M index escalated from 2026, two years before the 2028 COD).
# Before, at 15.24.0 (v0.5): project IRR 0.13126573271197758, equity IRR 0.11548743505017844,
# min DSCR 0.8668689564723109.
# Re-pinned for #1823 (wind v0.7: the held 0.5 MW / 0.5 MWh battery joins the headline KPIs,
# capex and O&M only, built as the wind battery options analysis builds it; these equal that
# analysis's figures for the held_0_5_0_5 option). Before (v0.6): project IRR
# 0.12408437995891264, equity IRR 0.10545894876814677, min DSCR 0.8671021075351333.
WIND_PINS = {
    "project_irr": 0.12313073791413345,
    "equity_irr": 0.10415918282280123,
    "min_dscr": 0.8678182687044798,
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
    cfg = _quiet(_project_cfg())
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
    seen_overrides: list[Dict[str, Any]] = []

    def counting(**kw: Any) -> Any:
        calls["n"] += 1
        seen_overrides.append(kw["overrides"])
        return evaluate_with_overrides(**kw)

    first = _run(_small(), site, counting)
    assert first.spec["opex_basis"]["pre_cod_years"] == 3
    assert first.spec["opex_basis"]["dc_per_nominal"] == pytest.approx(1.1)
    assert first.spec["opex_basis"]["components"][1]["usd_per_unit_year"] == 1.8
    n_points = first.spec["grid_points_evaluated"]
    assert n_points == 4
    # 4 points x (4 trials + base) + 4 curtailment + 4 RTE-sensitivity cases.
    assert first.effective_evaluations == calls["n"] == 4 * 5 + 4 + 4
    for overrides in seen_overrides:
        components = overrides["opex.currency_split.components"]
        assert components[1]["units"] == pytest.approx(
            overrides["generation.technologies.bess_1.energy_mwh"] * 1100
        )
        assert overrides["opex.usd_per_year"] == pytest.approx(
            150000 + 10 * components[0]["units"] + 1.8 * components[1]["units"]
        )
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


def test_shaded_pv_follows_each_points_table_packing(
    site: Dict[str, Any],
) -> None:
    """The PV cache keys on the table packing when the turbine's shadow is modelled (B33).

    At 185 tables and 5 MW AC, the 1 MW and the 3 MW BESS footprints pack the tables
    differently, so the shadow falls on different tables. Unshaded, the two points share
    one PV series; shaded, each must get its own. A cache that ignored the packing would
    hand the 3 MW point the 1 MW point's series.
    """
    assert site["shading"] is not None
    cfg = _small()
    cfg["grid"] = {
        **cfg["grid"],
        "pv_tables": [185],
        "pv_ac_mw": [5.0],
        "bess_power_mw": [1.0, 3.0],
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 1}

    def pv_by_power(s: Dict[str, Any]) -> Dict[float, float]:
        run = _run(cfg, s, evaluate_with_overrides)
        assert len(run.points) == 2
        return {p["bess_power_mw"]: p["pv_ac_mwh_factor_1"] for p in run.points}

    unshaded = pv_by_power({**site, "shading": None})
    assert unshaded[1.0] == unshaded[3.0]
    shaded = pv_by_power(site)
    assert shaded[1.0] != shaded[3.0]
    for power in (1.0, 3.0):
        assert unshaded[power] * 0.99 < shaded[power] < unshaded[power]


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
# 2026-11-07: the battery as a decision variable, its sensitivities and break-even values
# ---------------------------------------------------------------------------
def _context() -> sz.Context:
    """The project's base context, built without the site (no evaluation needed)."""
    unit = _project_unit()
    return sz.Context(
        scenario=_yaml(SOLAR_BESS),
        bess_template=pbd.BessConfig.from_mapping(unit["bess"]),
        dispatch=pbd.DispatchConfig.from_mapping(unit["dispatch"]),
        tariff=pbd.TariffConfig.from_mapping(unit["tariff"]),
        wind=pbd.WindBlock(capacity_mw=0.0, capacity_factor=0.0, degradation_pct=0.0),
        pricing=sz.Pricing.from_mapping(_yaml(PRICING_CONF)),
        grid_civils_development_usd=2.0e6,
        fixed_opex_usd_per_year=150000.0,
        losses_on_charge=True,
        project_opex=sz.project_opex_basis(
            _yaml(SOLAR_BESS),
            _project_cfg()["plant"]["bess_dc_per_nominal"],
            150000.0,
        ),
        battery_health=sz.BatteryHealth.from_mapping(_project_cfg()["battery_health"]),
    )


def _base_trial(ctx: sz.Context) -> sz.Trials:
    trials = sz.draw_trials(
        n_trials=1,
        seed=20261101,
        pricing=ctx.pricing,
        uncertainty=sz.Uncertainty.from_mapping(_project_cfg()["uncertainty"]),
        base_rte=ctx.bess_template.round_trip_efficiency,
        with_base=True,
    )
    return sz.Trials(values={k: v[:1] for k, v in trials.values.items()})


def test_shifted_case_moves_only_the_named_input_and_refuses_the_rest() -> None:
    ctx = _context()
    base = _base_trial(ctx)

    def shift(**kw: Any) -> tuple[sz.Context, sz.Trials]:
        return sz.shifted_case(ctx, base, kw, where="t")

    c, t = shift(bess_usd_per_kwh=99.0)
    assert float(t.values["bess_usd_per_kwh"][0]) == 99.0 and c == ctx
    # The battery O&M shift replaces the scenario bess_om rate per DC kWh (#1646's basis),
    # so the priced O&M at a size moves by the rate change x nominal x the DC ratio.
    assert ctx.project_opex is not None
    c, t = shift(bess_opex_usd_per_dc_kwh_year=2.0)
    assert c.project_opex is not None
    assert c.project_opex.components[1]["usd_per_unit_year"] == 2.0
    assert c.project_opex.components[0] == ctx.project_opex.components[0]
    assert c.project_opex.components[2] == ctx.project_opex.components[2]
    rate = ctx.project_opex.components[1]["usd_per_unit_year"]
    ratio = ctx.project_opex.dc_per_nominal
    total, _, _ = c.project_opex.at_size(4.0, 2.0)
    before, _, _ = ctx.project_opex.at_size(4.0, 2.0)
    assert total - before == pytest.approx((2.0 - rate) * 2000.0 * ratio)
    assert c.pricing == ctx.pricing
    assert c.tariff == ctx.tariff and c.scenario == ctx.scenario
    c, t = shift(priority_lkr_per_kwh=60.0, priority_term_years=20)
    assert (c.tariff.priority_lkr_per_kwh, c.tariff.priority_term_years) == (60.0, 20)
    assert c.tariff.other_lkr_per_kwh == ctx.tariff.other_lkr_per_kwh
    c, t = shift(round_trip_efficiency=0.82)
    assert float(t.values["round_trip_efficiency"][0]) == 0.82
    c, t = shift(scenario={"tax.corporate_tax_rate": 0.0})
    assert c.scenario["tax"]["corporate_tax_rate"] == 0.0
    assert ctx.scenario["tax"]["corporate_tax_rate"] == 0.30  # the base is not mutated
    # Every other trial input keeps its base value.
    for key, arr in t.values.items():
        assert np.array_equal(arr, base.values[key]), key
    # Negative controls, each observed to fire.
    for bad, match in (
        ({"bess_capex": 99.0}, "unknown inputs"),
        ({}, "moves no input"),
        ({"scenario": {"tax.no_such_rate": 0.0}}, "not in the scenario"),
        ({"priority_lkr_per_kwh": 10.0}, "below the other rate"),
        ({"round_trip_efficiency": 1.2}, "not physical"),
        ({"priority_term_years": 1.5}, "positive integer"),
    ):
        with pytest.raises(ValueError, match=match):
            sz.shifted_case(ctx, base, bad, where="t")
    import dataclasses

    with pytest.raises(ValueError, match="scenario O&M basis"):
        sz.shifted_case(
            dataclasses.replace(ctx, project_opex=None),
            base,
            {"bess_opex_usd_per_dc_kwh_year": 2.0},
            where="t",
        )
    for raw, match in (
        ([{"name": "a", "bess_usd_per_kwh": 1.0}] * 2, "duplicate"),
        ([{"name": "a"}], "unknown inputs"),
        ([{"bess_usd_per_kwh": 1.0}], "string name"),
    ):
        with pytest.raises(ValueError, match=match):
            sz._one_at_a_time_cases(raw)
    for raw, match in (
        ([{"input": "tax", "low": 0.0, "high": 1.0, "tolerance": 0.1}], "input"),
        (
            [{"input": "bess_usd_per_kwh", "low": 2.0, "high": 1.0, "tolerance": 0.1}],
            "low",
        ),
        ([{"input": "bess_usd_per_kwh", "low": 1.0, "high": 2.0}], "break_even"),
    ):
        with pytest.raises(ValueError, match=match):
            sz._break_even_specs(raw)


def test_battery_sensitivities_and_break_even_are_counted_and_responsive(
    site: Dict[str, Any],
) -> None:
    calls = {"n": 0}

    def counting(**kw: Any) -> Any:
        calls["n"] += 1
        return evaluate_with_overrides(**kw)

    cfg = _project_cfg()
    cfg["grid"] = {
        **cfg["grid"],
        "pv_tables": [107],
        "pv_ac_mw": [3.5],
        "bess_power_mw": [0.5, 2.0],
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 1}
    cfg["curtailment_scenario"] = {**cfg["curtailment_scenario"], "enabled": False}
    cfg["sensitivities"] = {
        **cfg["sensitivities"],
        "one_at_a_time": [
            {"name": "tariff_up", "priority_lkr_per_kwh": 60.0},
            {"name": "capex_up", "bess_usd_per_kwh": 250.0},
        ],
        "break_even": [
            # Brackets the sign change: 3 bisection steps to a 20 USD/kWh bracket.
            {
                "input": "bess_usd_per_kwh",
                "low": 60.0,
                "high": 202.51,
                "tolerance": 20.0,
            },
            # No sign change in a narrow range: two sweeps, no value.
            {
                "input": "priority_lkr_per_kwh",
                "low": 50.1,
                "high": 50.2,
                "tolerance": 1.0,
            },
        ],
    }
    run = _run(cfg, site, counting)
    # 2 points x (1 trial + base) + 2 RTE cases + 2 cases x 2 points + break-even
    # (5 + 2 sweeps of the 2 points).
    assert run.spec["break_even_evaluations"] == (5 + 2) * 2
    assert run.effective_evaluations == calls["n"] == 2 * 2 + 2 + 2 * 2 + 14
    assert calls["n"] <= _hard_cap()
    sens = run.curtailment
    assert sens is not None
    oat = sens["one_at_a_time"]
    base = {
        r["size"]["bess_power_mw"]: r["project_npv"]
        for r in oat["base"]["battery_profile"]["A"]
    }
    assert base == {p["bess_power_mw"]: p["base"]["project_npv"] for p in run.points}
    up = {
        r["size"]["bess_power_mw"]: r["project_npv"]
        for r in oat["cases"]["tariff_up"]["battery_profile"]["A"]
    }
    dear = {
        r["size"]["bess_power_mw"]: r["project_npv"]
        for r in oat["cases"]["capex_up"]["battery_profile"]["A"]
    }
    for p in (0.5, 2.0):
        assert up[p] > base[p]  # a higher evening rate pays the battery more
        assert dear[p] < base[p]  # a dearer battery costs more
    # The dearer battery hurts the larger one more (capex scales with energy).
    assert base[2.0] - dear[2.0] > base[0.5] - dear[0.5] > 0.0
    chosen = run.recommendation["by_reading"]["A"]["size"]["bess_power_mw"]
    found, none = sens["break_even"]
    assert found["chosen_bess_power_mw"] == chosen
    lo, hi = found["bracket"]
    assert hi - lo <= 20.0 and lo <= found["value"] <= hi
    # Cheap storage favours the other battery; the dearest favours the chosen one.
    assert found["gap_at_low"] > 0.0 > found["gap_at_high"]
    assert found["other_battery_takes_over_at"]["bess_power_mw"] != chosen
    assert none["value"] is None and none["bracket"] is None
    assert (none["gap_at_low"] > 0.0) == (none["gap_at_high"] > 0.0)
    # The battery value curve: one row per battery, the chosen one paired against each.
    profile = run.recommendation["by_reading"]["A"]["battery_profile"]
    assert [r["size"]["bess_power_mw"] for r in profile] == [0.5, 2.0]
    for r in profile:
        point = next(p for p in run.points if _key(p) == _key(r["size"]))
        assert r["p50"] == point["metrics"]["project_npv"]["p50"]
        if r["size"]["bess_power_mw"] == chosen:
            assert r["choice_against_this"] is None
        else:
            assert (
                0.0
                <= r["choice_against_this"]["share_of_trials_at_least_as_good"]
                <= 1.0
            )
    # Every decision variable's grid edge is flagged (DOM-1691-04). PV is a single value,
    # so it is at both edges; the battery is at exactly one edge or neither.
    edge = run.recommendation["by_reading"]["A"]["any_pv"]["at_grid_edge"]
    assert set(edge) == {"pv_tables", "pv_ac_mw", "bess_power_mw"}
    assert edge["pv_tables"] == edge["pv_ac_mw"] == {"minimum": True, "maximum": True}
    assert edge["bess_power_mw"] == {"minimum": chosen == 0.5, "maximum": chosen == 2.0}


def test_break_even_bracket_straddles_the_crossing_on_an_independent_path(
    site: Dict[str, Any],
) -> None:
    """#1691 assurance N-1: the bisection's final bracket must straddle the sign change.

    The search's own ``gap_at_low``/``gap_at_high`` are the endpoint gaps, so they cannot
    show a wrong bracket. The check re-prices the battery at the two bracket ends through
    the one-at-a-time cases (a separate code path) and recomputes the gap from their
    battery profiles. Two PV sizes make the chosen battery's own value the best of its PVs;
    a third battery outside reading A must stay out of the committed reading's gap.
    """
    cfg = _project_cfg()
    cfg["grid"] = {
        **cfg["grid"],
        "pv_tables": [107, 120],
        "pv_ac_mw": [3.5],
        "bess_power_mw": [0.5, 1.0, 1.5, 2.0],
    }
    cfg["readings"] = {
        **cfg["readings"],
        # 3.5 MW AC + 2.0 MW > 5.0 MW: 2.0 MW is outside reading A, inside reading B.
        "A": {**cfg["readings"]["A"], "max_pv_ac_plus_bess_mw": 5.0},
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 1}
    cfg["curtailment_scenario"] = {**cfg["curtailment_scenario"], "enabled": False}
    spec = {"input": "bess_usd_per_kwh", "low": 40.0, "high": 202.51, "tolerance": 4.0}
    cfg["sensitivities"] = {
        **cfg["sensitivities"],
        "one_at_a_time": [],
        "break_even": [spec],
    }
    run = _run(cfg, site, evaluate_with_overrides)
    committed = run.recommendation["committed_reading"]
    assert committed == "A"
    outside_a = [
        p for p in run.points if p["bess_power_mw"] == 2.0 and p["metrics"] is not None
    ]
    assert outside_a and not any(p["eligible_by_reading"]["A"] for p in outside_a)
    assert any(p["eligible_by_reading"]["B"] for p in outside_a)
    (found,) = run.curtailment["break_even"]
    chosen = found["chosen_bess_power_mw"]
    lo, hi = found["bracket"]
    assert hi - lo <= spec["tolerance"] and lo <= found["value"] <= hi

    cfg["sensitivities"] = {
        **cfg["sensitivities"],
        "one_at_a_time": [
            {"name": "at_low", "bess_usd_per_kwh": lo},
            {"name": "at_high", "bess_usd_per_kwh": hi},
            {"name": "search_low", "bess_usd_per_kwh": spec["low"]},
            {"name": "search_high", "bess_usd_per_kwh": spec["high"]},
        ],
        "break_even": [],
    }
    check = _run(cfg, site, evaluate_with_overrides)
    cases = check.curtailment["one_at_a_time"]["cases"]

    def gap_and_other(case: str) -> tuple[float, Dict[str, Any]]:
        rows = cases[case]["battery_profile"][committed]
        assert 2.0 not in {r["size"]["bess_power_mw"] for r in rows}
        own = next(r for r in rows if r["size"]["bess_power_mw"] == chosen)
        other = max(
            (r for r in rows if r["size"]["bess_power_mw"] != chosen),
            key=lambda r: r["project_npv"],
        )
        return other["project_npv"] - own["project_npv"], other["size"]

    # The search's endpoint gaps, recomputed under reading A only: a battery outside
    # the committed reading must not enter the gap.
    for case, key in (("search_low", "gap_at_low"), ("search_high", "gap_at_high")):
        assert gap_and_other(case)[0] == pytest.approx(found[key], rel=1e-12, abs=1e-6)
    g_lo, other_lo = gap_and_other("at_low")
    g_hi, other_hi = gap_and_other("at_high")
    # Opposite signs: the crossing lies inside the reported bracket.
    assert (g_lo > 0.0) != (g_hi > 0.0)
    assert (g_lo > 0.0) == (found["gap_at_low"] > 0.0)
    # The battery that takes over is the best other battery on the side where it wins.
    assert found["other_battery_takes_over_at"] == (
        other_lo if g_lo > 0.0 else other_hi
    )


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
    # Each point: the trials and the base case, then the RTE case, the curtailment case and
    # the one-at-a-time cases (sensitivity_cases_per_point); then the break-even searches.
    oat = len(cfg["sensitivities"]["one_at_a_time"])
    assert spec["sensitivity_cases_per_point"] == 2 + oat == 20
    assert (
        spec["effective_evaluations"]
        == pts * (n + 1)
        + spec["sensitivity_cases_per_point"] * pts
        + spec["break_even_evaluations"]
    )
    assert spec["git_sha"] != "unknown" and spec["result_sha256"]
    assert spec["seed"] == cfg["monte_carlo"]["seed"] == 20261101
    assert n == cfg["monte_carlo"]["n_trials"] == 256
    assert spec["losses_on_charge"] and spec["bess_duration_h"] == 4.0
    assert spec["export_limit_mw"] == 10.0
    assert [w["name"] for w in spec["dispatch_windows"]] == ["evening"]
    # The objective the run used is the one the config selects (PR 7: after-tax project NPV).
    assert spec["objective"] == {
        "metric": cfg["objective"]["metric"],
        "statistic": cfg["objective"]["statistic"],
    }
    assert spec["objective"] == {"metric": "project_npv", "statistic": "p50"}
    # 2026-11-07 (owner: "Whatever the optimiser picks"): this run's choice is committed to
    # the scenario. Under PR 7 the roles were "value_based" and "value_based_other_reading"
    # (reported only), and before PR 7 "committed" and "alternative".
    for role in ("committed", "other_reading"):
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
        # PR 7 oracle change (challenge point): the objective is the after-tax project NPV
        # (owner decision 2), so the choice is the best P50 project NPV. Before PR 7 this
        # line ranked on unit_pretax_npv_usd_p50; that oracle is kept below, against the
        # alternative the summary now reports for PR 4's objective.
        best = max(ok, key=lambda r: r["project_npv_p50"])
        assert (best["pv_tables"], best["pv_ac_mw"], best["bess_power_mw"]) == (
            size["pv_tables"],
            size["pv_ac_mw"],
            size["bess_power_mw"],
        ), name
        old = max(ok, key=lambda r: r["unit_pretax_npv_usd_p50"])
        alt = next(
            a
            for a in rec["by_reading"][name]["alternatives"]
            if (a["metric"], a["statistic"]) == ("unit_pretax_npv_usd", "p50")
        )["size"]
        assert (old["pv_tables"], old["pv_ac_mw"], old["bess_power_mw"]) == (
            alt["pv_tables"],
            alt["pv_ac_mw"],
            alt["bess_power_mw"],
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


def _key(entry: Dict[str, Any]) -> tuple[Any, Any, Any]:
    return (entry["pv_tables"], entry["pv_ac_mw"], entry["bess_power_mw"])


def _quiet(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """``cfg`` without the one-at-a-time cases and break-even searches (counted runs)."""
    cfg["sensitivities"] = {
        **cfg["sensitivities"],
        "one_at_a_time": [],
        "break_even": [],
    }
    return cfg


def _small_fixed(seed: int = 20261101, metric: str | None = None) -> Dict[str, Any]:
    """One battery (5 MW / 20 MWh at 5 MW AC, reading A at its limit), three PV sizes.

    PR 7's fixed battery, kept as a reduced grid that puts reading A exactly at its limit.
    """
    cfg = _quiet(_project_cfg())
    cfg["grid"] = {
        **cfg["grid"],
        "pv_tables": [134, 160, "land_max"],
        "pv_ac_mw": [5.0],
        "bess_power_mw": [5.0],
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 4, "seed": seed}
    if metric is not None:
        cfg["objective"] = {**cfg["objective"], "metric": metric}
    return cfg


def test_objective_follows_the_config_and_pr4s_objective_stays_selectable(
    site: Dict[str, Any],
) -> None:
    calls = {"n": 0}

    def counting(**kw: Any) -> Any:
        calls["n"] += 1
        return evaluate_with_overrides(**kw)

    new = _run(_small_fixed(), site, counting)
    old = _run(_small_fixed(metric="unit_pretax_npv_usd"), site, counting)
    again = _run(_small_fixed(), site, counting)
    other = _run(_small_fixed(seed=7), site, counting)
    # 4 runs x (3 points x (4 trials + base) + 3 curtailment + 3 RTE cases).
    assert calls["n"] == 4 * (3 * 5 + 3 + 3) <= _hard_cap()
    beside = _project_cfg()["objective"]["report_beside"]
    for run, metric in ((new, "project_npv"), (old, "unit_pretax_npv_usd")):
        assert run.spec["objective"] == {"metric": metric, "statistic": "p50"}
        rec = run.recommendation["by_reading"]["A"]
        ok = [p for p in run.points if p["eligible_by_reading"]["A"] and p["metrics"]]
        best = max(ok, key=lambda p: p["metrics"][metric]["p50"])
        assert _key(best) == _key(rec["size"])
        assert rec["objective_statistics"] == best["metrics"][metric]
        assert rec["objective_value"] == best["metrics"][metric]["p50"]
        assert list(rec["reported_beside"]) == list(beside)
        for m in beside:
            assert rec["reported_beside"][m] == best["metrics"][m]
    # The objective ranks the points; it changes no point's statistics.
    assert json.dumps(new.points, sort_keys=True) == json.dumps(
        old.points, sort_keys=True
    )
    assert (
        new.recommendation["by_reading"]["A"]["objective_value"]
        != old.recommendation["by_reading"]["A"]["objective_value"]
    )
    # Seed reproducibility, and a different seed draws differently.
    assert json.dumps(new.points, sort_keys=True) == json.dumps(
        again.points, sort_keys=True
    )
    assert [p["metrics"]["project_npv"]["p50"] for p in new.points] != [
        p["metrics"]["project_npv"]["p50"] for p in other.points
    ]
    for p in new.points:
        assert p["bess_energy_mwh"] == 4.0 * p["bess_power_mw"] == 20.0
        assert p["pv_ac_mw"] + p["bess_power_mw"] == 10.0
        assert p["allowed_by_reading"]["A"] and p["eligible_by_reading"]["A"]
    # Negative controls: an unknown objective or reported metric is refused before any
    # evaluation.
    n_before = calls["n"]
    for bad in (
        {"metric": "after_tax_npv"},
        {"statistic": "p95"},
        {"report_beside": ["project_npv_after_tax"]},
    ):
        cfg = _small_fixed()
        cfg["objective"] = {**cfg["objective"], **bad}
        with pytest.raises(ValueError, match="objective"):
            _run(cfg, site, counting)
    assert calls["n"] == n_before


def test_after_tax_objective_is_recomputed_from_the_engine_cfads_by_finance_irr() -> (
    None
):
    """The objective is the after-tax project NPV: the committed scenario's ``project_npv``
    equals ``finance.irr.npv`` over the capex and the engine's post-tax, haircut CFADS.
    """
    from finance.irr import npv

    full = evaluate_with_overrides(
        str(SOLAR_BESS), overrides={}, return_full_result=True
    )
    assert isinstance(full, dict)
    kpis, rows = full["kpis"], full["annual_rows"]
    lag = int(full["debt_result"]["construction_years"])
    # #1569: usd_total is priced in 2026 and spent in the one construction year, 2028
    # (COD 2029 - 1), so the engine escalates it two years at 5% (capex.price_basis).
    capex = _yaml(SOLAR_BESS)["capex"]["usd_total"] * 1.05 ** (2028 - 2026)
    flows = [-capex] + [0.0] * lag + [r["cfads_usd"] for r in rows]
    assert npv(kpis["discount_rate_used"], flows) == pytest.approx(
        kpis["project_npv"], rel=1e-12
    )
    for r in rows:
        # CFADS is after corporate tax and the risk haircut.
        assert r["posttax_cfads_lkr"] == pytest.approx(
            r["pretax_cfads_lkr"] - r["tax_lkr"], abs=1e-6
        )
        # #1578 L-11 (v0.10): and after the battery's augmentation in its year.
        assert r["cfads_usd"] == pytest.approx(
            (
                r["posttax_cfads_lkr"]
                - r["risk_haircut_amount_lkr"]
                - r["bess_augmentation_capex_lkr"]
            )
            / r["fx_rate"],
            rel=1e-12,
        )
    assert [i + 1 for i, r in enumerate(rows) if r["bess_augmentation_capex_lkr"]] == [
        14
    ]
    # At the grid-floor size (v0.9, v0.10) the project never has a taxable profit, so its after-tax
    # objective equals the pre-tax one (#1691: disclosed in STATUS). Under v0.8 tax was paid.
    assert sum(r["tax_lkr"] for r in rows) == 0.0
    # Responsiveness at a held discount rate, where tax bites (a 30 LKR/kWh generation tariff):
    # tax is paid, and a higher tax rate lowers the objective. (With the build-up WACC driving
    # the rate, tax also lowers the rate; see the PR's challenge points.)
    held = {"wacc.drives_discount_rate": False, "tariff.lkr_per_kwh": 30.0}
    dear = evaluate_with_overrides(
        str(SOLAR_BESS), overrides=held, return_full_result=True
    )
    assert isinstance(dear, dict)
    assert sum(r["tax_lkr"] for r in dear["annual_rows"]) > 0.0
    untaxed = _kpis(SOLAR_BESS, {**held, "tax.corporate_tax_rate": 0.0})
    taxed = _kpis(SOLAR_BESS, {**held, "tax.corporate_tax_rate": 0.30})
    assert taxed["project_npv"] < untaxed["project_npv"]
    # The scenario reproduces the committed point's base case through the engine as it
    # stands: from v0.8 the sizing prices the scenario's own basis (opex currency split, BESS
    # O&M at USD 1.80/kWh-yr DC, one construction period, the indexed O&M tariff parts), so
    # no override is needed (under v0.3-v0.7 the sizing basis had to be re-imposed). The
    # residual is the rounding of the scenario's derived fields.
    point = _committed_point()
    assert kpis["project_npv"] == pytest.approx(point["base"]["project_npv"], rel=1e-6)


def _committed_point() -> Dict[str, Any]:
    # The full grid's choice under reading A (SUMMARY), written to the scenario from v0.8.
    # Under PR 7 it came from the retired fixed-battery run (the owner's 5 MW / 20 MWh).
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
    # #1578 L-11: the scenario's augmentation is the point's base case, and each event
    # restores the engine's own SoH that year, so it moves the cash only.
    health = point["base"]["battery_health"]
    events = b["revenue"]["augmentation_schedule"]
    by_year = health["augmentation_capex_usd_by_year"]
    assert [e["year"] for e in events] == [int(y) for y in by_year] == [14]
    for e in events:
        assert e["capex_usd"] == pytest.approx(by_year[str(e["year"])], abs=0.005)
        assert e["restore_to_soh"] == pytest.approx(
            (1.0 - eng["bess_mdsc_fade_pct_annual"]) ** (e["year"] - 1), abs=5e-7
        )
    assert health["reserve_removed_usd_per_kwh"] == pytest.approx(8.00 / 0.90)
    assert scen["tariff"]["lkr_per_kwh"] == pytest.approx(eng["tariff_lkr_per_kwh"])
    assert scen["capex"]["usd_total"] == pytest.approx(
        solar["capex_usd"] + b["capex_usd"] + 2.0e6
    )
    for path in (SOLAR_BESS, WIND, HYBRID):
        assert "contiguous" in path.read_text(), path.name


def test_live_floor_point_reproduces_the_pins_through_the_l11_wiring(
    site: Dict[str, Any],
) -> None:
    """#1578 L-11, live: the committed floor point's base case, evaluated now (#1711 N-1).

    The other L-11 tests call the pieces directly or read the committed summary, which is
    static. This one runs the sizing path for one trial at the floor (107 tables, 3.5 MW AC,
    0.1 MW / 0.4 MWh) and checks what reaches the engine against oracles that do not come from
    the sizing code:

    * the base case's project NPV equals ``SOLAR_BESS_PINS`` (the committed scenario through
      the engine, no override) to a few dollars (the scenario rounds its inputs);
    * the BESS capex is 400 kWh at the pricing config's all-in mode less its augmentation
      reserve grossed up by land and auxiliaries (8.00 / 0.90);
    * the engine's schedule is one event before year 14, which would start at ``1 - 13 f``
      (``f`` the config's fade), adding ``13 f`` of the nameplate at the config's
      augmentation price per kWh (closed form);
    * the one trial, whose residual fade is positive, moves the event earlier than the base.
    """
    seen: list[Dict[str, Any]] = []

    def capturing(**kw: Any) -> Any:
        seen.append(kw["overrides"])
        return evaluate_with_overrides(**kw)

    cfg = _quiet(_project_cfg())
    cfg["grid"] = {
        **cfg["grid"],
        "pv_tables": [107],
        "pv_ac_mw": [3.5],
        "bess_power_mw": [0.1],
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 1}
    cfg["curtailment_scenario"] = {**cfg["curtailment_scenario"], "enabled": False}
    run = _run(cfg, site, capturing)
    # One point x (base + 1 trial) + its RTE-sensitivity case.
    assert run.effective_evaluations == len(seen) == 3 <= _hard_cap()

    project = _project_cfg()
    health = project["battery_health"]
    bess_price = _yaml(PRICING_CONF)["bess"]
    reserve = bess_price["augmentation_reserve_usd_per_kwh_base"] / (
        1.0 - bess_price["land_and_auxiliaries_share_base"]
    )
    kwh = 0.4 * 1000.0
    added = 13.0 * health["fade_pct_per_year"] / 100.0
    expected_event = added * kwh * health["augmentation_usd_per_kwh"]
    # Year 13 starts at or above the trigger, year 14 below it.
    assert added - 1.0 / 13.0 * added <= 1.0 - health["augment_below_soh"] < added

    point = run.points[0]
    base = point["base"]
    assert base["project_npv"] == pytest.approx(SOLAR_BESS_PINS["project_npv"], abs=5.0)
    assert base["min_dscr"] == pytest.approx(SOLAR_BESS_PINS["min_dscr"], abs=1e-5)

    schedule_key = "generation.technologies.bess_1.revenue.augmentation_schedule"
    capex_key = "generation.technologies.bess_1.capex_usd"
    # The base case is the point's first evaluation (row 0 of the trials).
    base_overrides = seen[0]
    assert base_overrides[capex_key] == pytest.approx(
        kwh * (bess_price["all_in_usd_per_kwh"]["mode"] - reserve), abs=0.01
    )
    base_events = base_overrides[schedule_key]
    assert [e["year"] for e in base_events] == [14]
    assert base_events[0]["capex_usd"] == pytest.approx(expected_event, abs=0.01)

    trial_overrides = [o for o in seen if o[schedule_key] != base_events]
    assert len(trial_overrides) == 1
    trial_events = trial_overrides[0][schedule_key]
    assert trial_events and trial_events[0]["year"] < 14
    assert trial_events[0]["capex_usd"] > 0.0


def _indexed_dispatcher_revenue(out: Dict[str, Any], scen: Dict[str, Any]) -> list:
    """The hourly dispatcher's revenue with the Annex 2 escalable O&M parts indexed (L-9).

    Each exported kWh earns ``escalable x (index - 1)`` more than the flat rate: 2.72
    (ground solar, other periods) on every unit kWh, plus 0.30 on a priority kWh (the
    priority rate's 3.02 = 2.72 / 0.90, less 2.72), with ``index = (1 + g) ** (year + 2)``
    (from the 2026 price date to a 2029 COD, #1569)
    and ``g`` written out in closed form from the scenario's inputs, apart from
    ``finance.tariff_indexation`` (TEST-01). The project has no wind.
    """
    ix = scen["tariff"]["om_indexation"]
    assert ix["basis"] == "ccpi_fx_weighted"
    assert ix["lkr_usd_depreciation_pct"] == "relative_ppp"
    ccpi = ix["ccpi_inflation_pct"] / 100.0
    fx = (1.0 + ccpi) / (1.0 + ix["usd_inflation_pct"] / 100.0) - 1.0
    g = ix["ccpi_weight"] * ccpi + ix["lkr_usd_weight"] * fx
    indexed = []
    for year, (rev, step) in enumerate(
        zip(
            out["engine"]["dispatcher_revenue_lkr"],
            out["degradation_path"],
            strict=True,
        ),
        start=1,
    ):
        assert step["year"] == year
        assert rev == pytest.approx(step["revenue_lkr"], rel=1e-12)  # no wind
        # #1569: the index starts at the 2026 price date, three years before the 2029 COD.
        uplift = (1.0 + g) ** (year - 1 + (2029 - 2026)) - 1.0
        indexed.append(
            rev
            + uplift
            * 1000.0
            * (step["unit_export_mwh"] * 2.72 + step["priority_export_mwh"] * 0.30)
        )
    return indexed


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
    # L-9: the dispatcher prices at the flat Annex 2 rates; the scenario indexes their
    # escalable O&M parts (solar 2.72, priority premium 0.30) yearly.
    dispatcher = _indexed_dispatcher_revenue(out, _yaml(SOLAR_BESS))
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
    reported = evaluate_with_overrides(
        str(SOLAR_BESS), overrides={}, return_full_result=True
    )
    assert isinstance(reported, dict)
    for key, pinned in SOLAR_BESS_PINS.items():
        if pinned is None:
            # The engine reports the key as None; the evaluation summary leaves it out.
            assert key in reported["kpis"] and reported["kpis"][key] is None, key
            assert key not in base, key
            continue
        assert base[key] == pytest.approx(pinned, rel=1e-9, abs=1e-12), key
    # No project IRR resolves (#1494). The 20-year CFADS sum is below the capex, so the NPV
    # is negative at every non-negative rate, but the CFADS turn negative after the 15-year
    # priority term, so the NPV changes sign twice at negative rates (near -25% and -0.5%
    # on the 15.22.0 scenario, v0.7).
    # The solver resolves no single rate, and the KPI surface reports that as undefined
    # (None), not the 0.0 it used to substitute. The numeric surface drops a None KPI.
    assert "project_irr" not in base
    full = evaluate_with_overrides(
        str(SOLAR_BESS), overrides={}, return_full_result=True
    )
    assert isinstance(full, dict)
    assert full["kpis"]["project_irr"] is None
    assert full["kpis"]["project_irr_status"] == "undefined"
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
    # #1569: operating year 1 (2028) carries two years of the 3.21%/yr index on the 4.93
    # escalable O&M part, from the 2026 price date (g in closed form, as the L-9 tests).
    g = 0.30 * 0.05 + 0.70 * (1.05 / 1.025 - 1.0)
    rate_y1 = 25.73 + 4.93 * ((1.0 + g) ** (2028 - 2026) - 1.0)
    assert full["annual_rows"][0]["generation_revenue_lkr"] == pytest.approx(
        w["capacity_mw"] * w["capacity_factor"] * 8760.0 * 1000.0 * rate_y1, rel=1e-9
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
    # PR 6 capex: the pins also move with the blended turbine capex (TEST-01).
    dearer = _kpis(
        WIND,
        {
            "generation.technologies.wind.capex_usd": w["capex_usd"] * 1.1,
            "capex.usd_total": scen["capex"]["usd_total"] + w["capex_usd"] * 0.1,
        },
    )
    assert dearer["project_irr"] < base["project_irr"]
