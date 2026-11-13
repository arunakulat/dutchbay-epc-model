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

PR 7 (the owner's 5 MW / 20 MWh battery, ranked on the after-tax project NPV) adds:

* ``finance.irr.npv`` over the capex and the engine's post-tax CFADS reproduces the objective
  on the committed scenario, and CFADS = pre-tax CFADS - tax - haircut year by year;
* reading A at its limit (PV AC + BESS power = 10 MW exactly) and E = 4P at every point of
  the fixed-battery run; the choice is the best P50 of the metric the config names;
* at production scale, the fixed-battery run and the full grid (two runs, one seed) carry
  identical statistics at every size both evaluate;
* the cost of the owner's choice is recomputed from the two committed summaries.

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
FIXED_CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess_fixed_bess_sizing.yaml"
FIXED_SUMMARY = (
    REPO_ROOT / "docs" / "blue_whale" / "solar_bess_fixed_bess_sizing_summary.json"
)
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
SOLAR_BESS_PINS = {
    "project_npv": -5579964.010141663,
    "equity_npv": -6167136.817522649,
    "equity_irr": None,
    "min_dscr": 0.868213653807526,
}
# The basis the sizing runs priced (v0.3 to v0.7): opex in one currency, BESS O&M at USD
# 2.5/kWh-yr, the engine's default of 2 construction periods (from 15.20.0 the scenario sets 1,
# B30), and flat tariffs (no L-9 indexation of the escalable O&M parts; from 15.21.0 the scenario
# indexes them). From 15.22.0 the solar O&M is on 152 tables (257,030; was 256,655 on 151).
SIZING_OPEX_BASIS = {
    "opex.currency_split": None,
    "opex.usd_per_year": 257030,
    "Financing_Terms.construction_periods": 2,
    # #1570: the count must equal the declared build time, so the basis states both.
    "timeline.construction_years": 2,
    "tariff.om_indexation": None,
    "generation.technologies.bess_1.revenue.escalable_om_lkr_per_kwh": None,
    # #1569: the sizing priced capex and opex as stated, with no price dates.
    "capex.price_basis": None,
    "opex.price_year": None,
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
WIND_PINS = {
    "project_irr": 0.12408437995891264,
    "equity_irr": 0.10545894876814677,
    "min_dscr": 0.8671021075351333,
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
    seen_overrides: list[Dict[str, Any]] = []

    def counting(**kw: Any) -> Any:
        calls["n"] += 1
        seen_overrides.append(kw["overrides"])
        return evaluate_with_overrides(**kw)

    first = _run(_small(), site, counting)
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
    # The objective the run used is the one the config selects (PR 7: after-tax project NPV).
    assert spec["objective"] == {
        "metric": cfg["objective"]["metric"],
        "statistic": cfg["objective"]["statistic"],
    }
    assert spec["objective"] == {"metric": "project_npv", "statistic": "p50"}
    # PR 7: this full-grid run is the value-based reference; the scenario commits the owner's
    # 5 MW / 20 MWh from the fixed-battery run (test_fixed_bess_*). Before PR 7 the roles were
    # "committed" and "alternative".
    for role in ("value_based", "value_based_other_reading"):
        want = cfg["recommendation"][role]
        got = summary["recommendation"]["by_reading"][want["reading"]]["size"]
        assert (got["pv_tables"], got["pv_ac_mw"], got["bess_power_mw"]) == (
            want["pv_tables"],
            want["pv_ac_mw"],
            want["bess_power_mw"],
        ), role
    assert (
        cfg["recommendation"]["value_based"]["reading"] == cfg["readings"]["committed"]
    )
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


# ---------------------------------------------------------------------------
# PR 7: the owner's 5 MW / 20 MWh battery, its PV DC and the cost of the choice
# ---------------------------------------------------------------------------
def _fixed_cfg() -> Dict[str, Any]:
    """The fixed-battery config as Hydra composes it: the project config, then this file."""
    from omegaconf import OmegaConf

    child = _yaml(FIXED_CONF)
    assert child["defaults"] == ["blue_whale_solar_bess_project_sizing", "_self_"]
    merged = OmegaConf.merge(
        OmegaConf.create(_project_cfg()),
        OmegaConf.create({k: v for k, v in child.items() if k != "defaults"}),
    )
    out = OmegaConf.to_container(merged, resolve=True)
    assert isinstance(out, dict)
    return {str(k): v for k, v in out.items()}


def _fixed_summary() -> Dict[str, Any]:
    data = json.loads(FIXED_SUMMARY.read_text())
    assert isinstance(data, dict)
    return data


def _rows_of(summary: Dict[str, Any]) -> list[Dict[str, Any]]:
    grid = summary["grid"]
    return [dict(zip(grid["columns"], row, strict=True)) for row in grid["rows"]]


def _key(entry: Dict[str, Any]) -> tuple[Any, Any, Any]:
    return (entry["pv_tables"], entry["pv_ac_mw"], entry["bess_power_mw"])


def test_fixed_bess_config_composes_as_hydra_does() -> None:
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf

    with initialize_config_dir(config_dir=str(REPO_ROOT / "conf"), version_base="1.3"):
        composed = compose(config_name="blue_whale_solar_bess_fixed_bess_sizing")
    raw = OmegaConf.to_container(composed, resolve=True)
    assert isinstance(raw, dict)
    raw.pop("hydra", None)
    fixed = _fixed_cfg()
    assert raw == fixed
    # Only the grid and the recommendation differ from the full project config: the same
    # seed, trials, ranges, plant lines, readings and objective.
    project = _project_cfg()
    assert {k for k in project if project[k] != fixed[k]} == {"grid", "recommendation"}
    grid = fixed["grid"]
    assert grid["bess_power_mw"] == [5.0] and grid["pv_ac_mw"] == [5.0]
    assert grid["bess_duration_h"] == 4.0
    assert (grid["min_dc_ac_ratio"], grid["max_dc_ac_ratio"]) == (1.0, 1.5)


def test_fixed_bess_summary_holds_the_owners_battery_and_chooses_the_pv() -> None:
    summary = _fixed_summary()
    spec = summary["spec"]
    cfg = _fixed_cfg()
    n = spec["requested_trials_per_point"]
    pts = spec["grid_points_evaluated"]
    assert summary["config"] == "conf/blue_whale_solar_bess_fixed_bess_sizing.yaml"
    assert spec["effective_evaluations"] == pts * (n + 1) + 2 * pts
    assert spec["seed"] == cfg["monte_carlo"]["seed"] == 20261101
    assert spec["seed"] == _summary()["spec"]["seed"]
    assert n == cfg["monte_carlo"]["n_trials"] == 256
    assert spec["objective"] == {"metric": "project_npv", "statistic": "p50"}
    # The turbine on DutchBay T2 (15.22.0) moves its crane pad onto the lot's west side and
    # its shadow onto the array, so the lot holds 186 tables (191 before).
    assert spec["land_max_tables_by_bess_power_mw"] == {"5.0": 186}
    rows = _rows_of(summary)
    # Every whole table count from DC/AC 1.0 at 5 MW AC to 191, once each; the five above the
    # lot's maximum are listed as not fitting and are not evaluated.
    assert sorted(r["pv_tables"] for r in rows) == list(range(134, 192))
    assert {r["pv_tables"] for r in rows if not r["fits"]} == set(range(187, 192))
    assert 133 * 37.52 / 5000.0 < 1.0 <= 134 * 37.52 / 5000.0
    for r in rows:
        # The owner's battery, E = 4P: 5 MW / 20 MWh.
        assert (r["bess_power_mw"], r["bess_energy_mwh"]) == (5.0, 20.0)
        assert r["bess_energy_mwh"] == 4.0 * r["bess_power_mw"]
        # Reading A at its limit: PV AC + BESS power equals 10 MW exactly, and is allowed.
        assert r["pv_ac_mw"] + r["bess_power_mw"] == 10.0
        assert r["eligible_A"] == r["fits"]
        assert 1.0 <= r["dc_ac_ratio"] <= 1.5 and r["meets_4h_rule"]
    eligible = [r for r in rows if r["eligible_A"]]
    assert len(eligible) == pts
    best = max(eligible, key=lambda r: r["project_npv_p50"])
    rec = summary["recommendation"]["by_reading"]["A"]
    assert _key(best) == _key(rec["size"])
    for role in ("committed", "alternative"):
        want = cfg["recommendation"][role]
        got = summary["recommendation"]["by_reading"][want["reading"]]["size"]
        assert _key(got) == _key(want), role
    assert cfg["recommendation"]["committed"]["reading"] == cfg["readings"]["committed"]
    # The objective's P50 and P90 at the choice are that row's, and the unit's pre-tax NPV
    # is reported beside it.
    stats = rec["objective_statistics"]
    assert (stats["p50"], stats["p90"]) == (
        best["project_npv_p50"],
        best["project_npv_p90"],
    )
    beside = rec["reported_beside"]
    assert set(beside) == set(cfg["objective"]["report_beside"])
    assert beside["unit_pretax_npv_usd"]["p50"] == best["unit_pretax_npv_usd_p50"]
    assert beside["unit_pretax_npv_usd"]["p90"] == best["unit_pretax_npv_usd_p90"]


def test_fixed_bess_run_reproduces_the_full_grid_at_every_shared_point() -> None:
    """MRM-01 at production scale: two runs with the same seed draw the same trials, so the
    sizes both evaluate (5 MW AC, 5 MW / 20 MWh at 134, 147, 160, 174 and 186 tables) carry
    identical statistics."""
    full = {_key(r): r for r in _grid_rows()}
    shared = [r for r in _rows_of(_fixed_summary()) if _key(r) in full]
    assert sorted(r["pv_tables"] for r in shared) == [134, 147, 160, 174, 186]
    for r in shared:
        assert r == full[_key(r)], _key(r)


def test_strategic_cost_is_the_gap_between_the_two_summaries() -> None:
    rec = _fixed_cfg()["recommendation"]
    vb = rec["value_based"]
    full = _summary()
    assert vb["summary"] == str(SUMMARY.relative_to(REPO_ROOT))
    assert _key(full["recommendation"]["by_reading"][vb["reading"]]["size"]) == _key(vb)
    value = next(r for r in _grid_rows() if _key(r) == _key(vb))
    committed = next(
        r for r in _rows_of(_fixed_summary()) if _key(r) == _key(rec["committed"])
    )
    cost = rec["strategic_cost_usd"]
    assert set(cost) == {
        "project_npv_p50",
        "project_npv_p90",
        "unit_pretax_npv_usd_p50",
        "unit_pretax_npv_usd_p90",
    }
    for key, recorded in cost.items():
        assert recorded == pytest.approx(value[key] - committed[key], abs=0.5), key
    # The value-based size is the full grid's best, so the owner's battery costs value.
    assert value["project_npv_p50"] >= committed["project_npv_p50"]
    assert cost["project_npv_p50"] > 0.0


def _small_fixed(seed: int = 20261101, metric: str | None = None) -> Dict[str, Any]:
    cfg = _fixed_cfg()
    cfg["grid"] = {**cfg["grid"], "pv_tables": [134, 160, "land_max"]}
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
    beside = _fixed_cfg()["objective"]["report_beside"]
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
        assert r["cfads_usd"] == pytest.approx(
            (r["posttax_cfads_lkr"] - r["risk_haircut_amount_lkr"]) / r["fx_rate"],
            rel=1e-12,
        )
    assert sum(r["tax_lkr"] for r in rows) > 0.0
    # Responsiveness at a held discount rate: a higher tax rate lowers the objective. (With
    # the build-up WACC driving the rate, tax also lowers the rate; see the PR's challenge
    # points.)
    held = {"wacc.drives_discount_rate": False}
    untaxed = _kpis(SOLAR_BESS, {**held, "tax.corporate_tax_rate": 0.0})
    taxed = _kpis(SOLAR_BESS, {**held, "tax.corporate_tax_rate": 0.30})
    assert taxed["project_npv"] < untaxed["project_npv"]
    # The scenario reproduces the committed point's base case through the engine, on the
    # opex basis the sizing priced (v0.3: one currency, BESS O&M at USD 2.5/kWh-yr). From
    # v0.5 the scenario carries the opex currency split and the new BESS O&M rate (lower, and in
    # LKR); from v0.6 it indexes the PUCSL escalable O&M parts (L-9). The sizing has not been
    # re-run on either (scenario comments, opex and tariff blocks).
    point = _committed_point()
    sized = _kpis(SOLAR_BESS, SIZING_OPEX_BASIS)
    assert sized["project_npv"] == pytest.approx(point["base"]["project_npv"], rel=1e-4)
    # On the stated prices the v0.5+ opex and L-9 indexation beat the sizing basis; the 2026
    # price dates (#1569: capex escalated to the 2028 draw, opex and the O&M index from 2026)
    # then lower the scenario below it.
    undated = _kpis(
        SOLAR_BESS,
        {
            "capex.price_basis": None,
            "opex.price_year": None,
            "tariff.om_indexation.pre_operation_years": 0,
        },
    )
    assert undated["project_npv"] > sized["project_npv"]
    assert kpis["project_npv"] < undated["project_npv"]


def _committed_point() -> Dict[str, Any]:
    # PR 7: the committed size comes from the fixed-battery run (owner decision 1); before
    # PR 7 it came from the full grid's choice under reading A (SUMMARY).
    summary = _fixed_summary()
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
