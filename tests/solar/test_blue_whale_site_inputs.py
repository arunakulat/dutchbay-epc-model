"""Blue Whale PR 6: the capex blend and the solar resource summary.

TEST-01 oracles that did not originate with the module under test:

* the levy cascade against :func:`finance.import_levies.capex_uplift_lines_usd`;
* the stepped pvlib chain against :func:`solar_resource.pv_producer.compute_solar_aep`;
* the pvlib plane-of-array irradiation against an isotropic-sky closed form written here;
* the landed-cost arithmetic recomputed in closed form from the published components;
* invariants: blend weights sum to one, specific yield = energy / kWp, PR = yield / POA,
  monthly sums equal the annual totals, cases are ordered low <= mode <= high.

The private anchors are never in this repository. Tests that need values use a synthetic set;
the one test that reproduces the committed blend runs only when the private file is supplied
through ``DUTCHBAY_BLUE_WHALE_PRIVATE_ANCHORS`` (a path outside the repository).
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import yaml

from finance.import_levies import capex_uplift_lines_usd, resolve_indirect_taxes
from solar_resource import blue_whale_site_inputs as si

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF = REPO_ROOT / "conf" / "blue_whale_capex_solar_resource.yaml"
PRICING = REPO_ROOT / "conf" / "blue_whale_pv_bess_pricing.yaml"
CAPEX_SUMMARY = REPO_ROOT / "docs" / "blue_whale" / "capex_blend_summary.json"
SOLAR_SUMMARY = REPO_ROOT / "docs" / "blue_whale" / "solar_resource_summary.json"
SOLAR_CSV = REPO_ROOT / "docs" / "blue_whale" / "solar_resource_monthly.csv"
CLI = REPO_ROOT / "scripts" / "run_blue_whale_capex_solar_resource_v14.py"
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
HYBRID = REPO_ROOT / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"
SOLAR_BESS = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
PRIVATE_ENV = "DUTCHBAY_BLUE_WHALE_PRIVATE_ANCHORS"

#: Synthetic stand-ins for the private anchors (NOT the private values).
SYNTH_VALUES = {"W-DB150-DEV": 600.0, "W-DB150-DEV-BOP": 300.0, "B-OEMH": 90.0}
SYNTH_SHARES = {"B-OEMH": 0.8, "B-ENV10": 0.8, "B-ENV11": 0.8}


def _yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _cli() -> Any:
    spec = importlib.util.spec_from_file_location("bw_pr6_cli", CLI)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cfg() -> Dict[str, Any]:
    return _yaml(CONF)


@pytest.fixture(scope="module")
def postures(cfg: Dict[str, Any]) -> Dict[str, si.LevyPosture]:
    return si.parse_levy_postures(cfg["levy_postures"])


# ---------------------------------------------------------------------------
# Configuration and disclosure structure
# ---------------------------------------------------------------------------
def test_blend_weights_sum_to_one(cfg: Dict[str, Any]) -> None:
    wind = cfg["wind"]
    supply = [wind["turbine_supply"]["web"]["weight"]] + [
        a["weight"] for a in wind["turbine_supply"]["anchors"].values()
    ]
    bop = [a["weight"] for a in wind["bop"]["anchors"].values()]
    eq = cfg["bess"]["equipment"]
    bess = [eq["web"]["weight"]] + [a["weight"] for a in eq["anchors"].values()]
    for weights in (supply, bop, bess):
        assert si.blend_weights_ok(weights)
        assert math.fsum(weights) == pytest.approx(1.0, abs=1e-12)
    # Negative control: a weight off by 1% is refused by the blend.
    bad = copy.deepcopy(cfg["wind"])
    bad["turbine_supply"]["web"]["weight"] = 0.51
    with pytest.raises(ValueError, match="sum to 1"):
        si.wind_all_in(
            bad, si.parse_levy_postures(cfg["levy_postures"]), 6.722, SYNTH_VALUES
        )


def test_private_anchors_carry_no_value_in_the_repository(cfg: Dict[str, Any]) -> None:
    anchors = {
        **cfg["wind"]["turbine_supply"]["anchors"],
        **cfg["wind"]["bop"]["anchors"],
        **cfg["bess"]["equipment"]["anchors"],
    }
    private = {k: a for k, a in anchors.items() if a["kind"] == "private"}
    assert sorted(private) == ["B-OEMH", "W-DB150-DEV", "W-DB150-DEV-BOP"]
    for name, anchor in private.items():
        assert not any(k.startswith("usd_per") for k in anchor), name
        assert anchor["handling_note"] in (
            "DUTCHBAY150MW-PACKAGE-HANDLING-2026-09-21",
            "NSO250MW-OFFERS-HANDLING-2026-09-04",
        )
    # Negative control: a value smuggled into a private anchor is refused.
    bad = copy.deepcopy(cfg["wind"])
    bad["turbine_supply"]["anchors"]["W-DB150-DEV"]["usd_per_kw"] = 1.0
    with pytest.raises(ValueError, match="must not carry a value"):
        si.wind_all_in(
            bad, si.parse_levy_postures(cfg["levy_postures"]), 6.722, SYNTH_VALUES
        )
    # And a private anchor that was not supplied is refused, not silently dropped.
    with pytest.raises(ValueError, match="not supplied"):
        si.wind_all_in(
            cfg["wind"], si.parse_levy_postures(cfg["levy_postures"]), 6.722, {}
        )


def test_cli_refuses_a_private_file_inside_the_repository(cfg: Dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="outside the repository"):
        _cli().run_capex(cfg, str(REPO_ROOT / "conf" / "anything.yaml"))
    with pytest.raises(ValueError, match="required"):
        _cli().run_capex(cfg, None)


def test_config_is_strict(
    cfg: Dict[str, Any], postures: Dict[str, si.LevyPosture]
) -> None:
    bad = copy.deepcopy(cfg["bess"])
    bad["extra"] = 1
    with pytest.raises(ValueError, match="unknown"):
        si.bess_all_in(bad, postures, 6.722, SYNTH_VALUES, SYNTH_SHARES)
    bad = copy.deepcopy(cfg["wind"])
    bad["epc_margin_pct"] = {"low": 0.1, "mode": 0.05, "high": 0.08}
    with pytest.raises(ValueError, match="low <= mode <= high"):
        si.wind_all_in(bad, postures, 6.722, SYNTH_VALUES)


# ---------------------------------------------------------------------------
# Landed cost: independent oracles
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("posture", ["bonded", "prudent", "full_stack_paid"])
def test_levies_match_finance_import_levies(
    postures: Dict[str, si.LevyPosture], posture: str
) -> None:
    p = postures[posture]
    cif, domestic = 480.0, 360.0
    duties, vat = si.levy_lines(cif, domestic, p)
    block = {
        "taxes_indirect": {
            "import_share_pct": cif / (cif + domestic),
            "cid_pct": p.cid_pct,
            "pal_pct": p.pal_pct,
            "sscl_import_pct": p.sscl_import_pct,
            "vat_capex_pct": p.vat_pct,
            "vat_on_full_capex": p.vat_on_domestic,
            "vat_on_duties": True,
            "vat_opex_pct": 0.0,
            "relief": {
                "bonded_scheme": False,
                "vat_capex_relieved": p.vat_relieved,
                "vat_opex_relieved": True,
            },
        }
    }
    indirect = resolve_indirect_taxes(block)
    assert indirect is not None
    lines = capex_uplift_lines_usd(cif + domestic, indirect)
    assert duties == pytest.approx(
        lines["cid_usd"] + lines["pal_usd"] + lines["sscl_import_usd"], rel=1e-12
    )
    assert vat == pytest.approx(lines["vat_capex_usd"], rel=1e-12, abs=1e-12)


def test_wind_landed_cost_in_closed_form(
    cfg: Dict[str, Any], postures: Dict[str, si.LevyPosture]
) -> None:
    w = cfg["wind"]
    fx = float(cfg["fx"]["cny_per_usd"])
    got = si.wind_all_in(w, postures, fx, SYNTH_VALUES)["mode"]
    # Closed form, written out here with the synthetic private anchors.
    kb = w["turbine_supply"]["anchors"]["W-KB-TENDER"]["usd_per_kw"] * 1.06
    cif = (0.5 * 2700.0 / fx + 0.25 * kb + 0.25 * 600.0) * 1.005
    duties = cif * (0.0 + 0.05 + 0.025)
    k = 0.6 + 0.4 * (50.0 / 9.5) ** 0.3
    bop = (345.99107142857144 + 300.0 + 197.1875) / 3.0 * k
    wrap = (cif + 40.0) * 0.05
    expected = cif + duties + 40.0 + wrap + bop
    assert got["all_in_usd_per_kw"] == pytest.approx(expected, rel=1e-12)
    assert got["single_machine_factor"] == pytest.approx(k, rel=1e-12)
    # The knowledge base's restatements of the public anchors.
    assert kb / 1.06 == pytest.approx(389.80 * 50.0 / 56.0)
    assert w["bop"]["anchors"]["W-MULLIKULAM-WBS-BOP"]["usd_per_kw"] == pytest.approx(
        (3028800 + 2019200 + 2019200 + 1211520 + 807680 + 1009600 + 946500) / 56000.0
    )


def test_bess_landed_cost_in_closed_form(
    cfg: Dict[str, Any], postures: Dict[str, si.LevyPosture]
) -> None:
    b = cfg["bess"]
    fx = float(cfg["fx"]["cny_per_usd"])
    got = si.bess_all_in(b, postures, fx, SYNTH_VALUES, SYNTH_SHARES)["mode"]
    web = 0.53 * 1000.0 / 1.13 / fx * 1.10 * 1.04
    cif = 0.5 * web + 0.125 * 99.50 + 0.125 * 98.68 + 0.25 * 90.0 * 1.04
    landed = cif * 1.075
    expected = ((landed + 14.0) * 1.08 + 8.0) / 0.9
    assert got["all_in_usd_per_kwh"] == pytest.approx(expected, rel=1e-12)
    assert got["dc_block_share"] == pytest.approx(0.5 * 0.9 + 0.5 * 0.8, rel=1e-12)
    parts = (
        got["landed_equipment_usd_per_kwh"]
        + got["bop_usd_per_kwh"]
        + got["epc_margin_usd_per_kwh"]
        + got["augmentation_usd_per_kwh"]
        + got["land_and_auxiliaries_usd_per_kwh"]
    )
    assert parts == pytest.approx(got["all_in_usd_per_kwh"], rel=1e-12)
    build = si.pricing_build_up(got, 0.10)
    assert (
        build["equipment_usd_per_kwh_base"]
        + build["bop_usd_per_kwh_base"]
        + build["augmentation_reserve_usd_per_kwh_base"]
    ) / 0.9 == pytest.approx(got["all_in_usd_per_kwh"], rel=1e-12)


def test_cases_are_ordered_and_respond_to_their_drivers(
    cfg: Dict[str, Any], postures: Dict[str, si.LevyPosture]
) -> None:
    fx = float(cfg["fx"]["cny_per_usd"])
    wind = si.wind_all_in(cfg["wind"], postures, fx, SYNTH_VALUES)
    bess = si.bess_all_in(cfg["bess"], postures, fx, SYNTH_VALUES, SYNTH_SHARES)
    for res, key in ((wind, "all_in_usd_per_kw"), (bess, "all_in_usd_per_kwh")):
        assert res["low"][key] < res["mode"][key] < res["high"][key]
    # Responsiveness (TEST-01): a dearer FOB or a dearer private anchor raises the blend.
    dear = copy.deepcopy(cfg["wind"])
    dear["turbine_supply"]["web"]["cny_per_kw"]["mode"] = 2900.0
    assert (
        si.wind_all_in(dear, postures, fx, SYNTH_VALUES)["mode"]["all_in_usd_per_kw"]
        > wind["mode"]["all_in_usd_per_kw"]
    )
    more = {**SYNTH_VALUES, "B-OEMH": 100.0}
    assert (
        si.bess_all_in(cfg["bess"], postures, fx, more, SYNTH_SHARES)["mode"][
            "all_in_usd_per_kwh"
        ]
        > bess["mode"]["all_in_usd_per_kwh"]
    )
    assert si.single_machine_factor(50.0, 50.0, 0.7, 0.4) == pytest.approx(1.0)
    assert si.single_machine_factor(50.0, 9.5, 0.7, 0.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# The committed blend and everything that consumes it
# ---------------------------------------------------------------------------
def test_committed_capex_summary_is_internally_consistent() -> None:
    doc = json.loads(CAPEX_SUMMARY.read_text(encoding="utf-8"))
    assert doc["config_sha256"] == hashlib.sha256(CONF.read_bytes()).hexdigest()
    assert "a reader may be able to back out a private input" in doc["disclosure_note"]
    land = _yaml(CONF)["bess"]["land_and_auxiliaries_share"]
    for c in si.CASES:
        w = doc["wind_usd_per_kw"][c]
        assert w["all_in_usd_per_kw"] == pytest.approx(
            w["turbine_cif_usd_per_kw"]
            + w["duties_usd_per_kw"]
            + w["vat_usd_per_kw"]
            + w["inland_transport_usd_per_kw"]
            + w["epc_wrap_usd_per_kw"]
            + w["bop_single_usd_per_kw"],
            rel=1e-12,
        )
        b = doc["bess_usd_per_kwh_contracted"][c]
        vat_on_import = (
            b["landed_equipment_usd_per_kwh"]
            - b["equipment_cif_usd_per_kwh"]
            - b["duties_usd_per_kwh"]
        )
        pre_land = (
            b["landed_equipment_usd_per_kwh"]
            + b["bop_usd_per_kwh"]
            + b["epc_margin_usd_per_kwh"]
            + (b["vat_usd_per_kwh"] - vat_on_import)
            + b["augmentation_usd_per_kwh"]
        )
        assert b["all_in_usd_per_kwh"] == pytest.approx(
            pre_land / (1.0 - land), rel=1e-12
        )
        assert b["land_and_auxiliaries_usd_per_kwh"] == pytest.approx(
            b["all_in_usd_per_kwh"] - pre_land, rel=1e-9
        )
        assert b["dc_block_cif_usd_per_kwh"] + b["pcs_ems_cif_usd_per_kwh"] == (
            pytest.approx(b["equipment_cif_usd_per_kwh"], rel=1e-12)
        )


def test_pricing_config_and_scenarios_carry_the_blend() -> None:
    doc = json.loads(CAPEX_SUMMARY.read_text(encoding="utf-8"))
    pricing = _yaml(PRICING)
    bess = doc["bess_usd_per_kwh_contracted"]
    for c in si.CASES:
        assert pricing["bess"]["all_in_usd_per_kwh"][c] == round(
            bess[c]["all_in_usd_per_kwh"], 2
        )
    wind = doc["wind_usd_per_kw"]
    assert pricing["wind"]["capex_usd_per_kw"] == round(
        wind["mode"]["all_in_usd_per_kw"], 2
    )
    assert pricing["wind"]["public_range_usd_per_kw"] == [
        round(wind["low"]["all_in_usd_per_kw"], 2),
        round(wind["high"]["all_in_usd_per_kw"], 2),
    ]
    build = doc["pricing_build_up_mode"]
    for key in ("equipment_usd_per_kwh_base", "bop_usd_per_kwh_base"):
        assert pricing["bess"][key] == round(build[key], 2)
    per_kw = pricing["wind"]["capex_usd_per_kw"]
    per_kwh = pricing["bess"]["all_in_usd_per_kwh"]["mode"]
    for path in (WIND, HYBRID):
        techs = _yaml(path)["generation"]["technologies"]
        assert techs["wind"]["capex_usd"] == round(
            per_kw * 1000.0 * techs["wind"]["capacity_mw"]
        )
    for path in (HYBRID, SOLAR_BESS):
        b = _yaml(path)["generation"]["technologies"]["bess_1"]
        assert b["capex_usd"] == round(per_kwh * 1000.0 * b["energy_mwh"])
    for path in (WIND, HYBRID, SOLAR_BESS):
        scen = _yaml(path)
        techs = scen["generation"]["technologies"]
        assert (
            scen["capex"]["usd_total"]
            == sum(t.get("capex_usd", 0) for t in techs.values()) + 2_000_000
        )


@pytest.mark.skipif(
    not os.environ.get(PRIVATE_ENV), reason="private anchors not supplied"
)
def test_rerun_with_the_private_anchors_reproduces_the_committed_blend() -> None:
    cfg = _yaml(CONF)
    got = _cli().run_capex(cfg, os.environ[PRIVATE_ENV])
    doc = json.loads(CAPEX_SUMMARY.read_text(encoding="utf-8"))
    for key in (
        "wind_usd_per_kw",
        "bess_usd_per_kwh_contracted",
        "pricing_build_up_mode",
    ):
        assert got[key] == doc[key]


# ---------------------------------------------------------------------------
# Solar resource
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def solar() -> Dict[str, Any]:
    pytest.importorskip("pvlib")
    return _cli().run_solar(_yaml(CONF))


def test_stepped_chain_reproduces_the_repository_producer(
    solar: Dict[str, Any],
) -> None:
    # run_solar raises if the stepped chain and compute_solar_aep differ by more than 1e-9.
    at_tmy = solar["at_tmy_point"]
    assert at_tmy["relative_difference_to_producer"] < 1e-12
    assert at_tmy["annual"]["net_ac_mwh"] / 1000.0 == pytest.approx(
        at_tmy["producer_annual_energy_gwh"], rel=1e-12
    )


def test_isotropic_poa_matches_an_independent_closed_form(
    solar: Dict[str, Any],
) -> None:
    ann = solar["at_pv_centroid"]["annual"]
    assert ann["poa_isotropic_closed_form_kwh_m2"] == pytest.approx(
        ann["poa_isotropic_pvlib_kwh_m2"], rel=1e-9
    )
    # Hay-Davies adds circumsolar gain over the isotropic sky at an 8 deg tilt, by little.
    assert 0.0 < ann["poa_kwh_m2"] / ann["poa_isotropic_pvlib_kwh_m2"] - 1.0 < 0.01
    # A one-hour hand check of the closed form: sun at zenith 30 deg due south, 8 deg tilt.
    one = si.isotropic_poa_w_m2(
        np.array([800.0]),
        np.array([700.0]),
        np.array([194.0]),
        np.array([30.0]),
        np.array([180.0]),
        8.0,
        180.0,
        0.25,
    )[0]
    b = math.radians(8.0)
    hand = (
        700.0 * math.cos(math.radians(22.0))
        + 194.0 * (1 + math.cos(b)) / 2
        + 800.0 * 0.25 * (1 - math.cos(b)) / 2
    )
    assert one == pytest.approx(hand, rel=1e-12)


def test_yield_identities(solar: Dict[str, Any]) -> None:
    ann = solar["at_pv_centroid"]["annual"]
    dc_kwp = solar["array"]["dc_mwp"] * 1000.0
    assert ann["specific_yield_kwh_per_kwp"] == pytest.approx(
        ann["net_ac_mwh"] * 1000.0 / dc_kwp, rel=1e-12
    )
    assert ann["performance_ratio"] == pytest.approx(
        ann["specific_yield_kwh_per_kwp"] / ann["poa_kwh_m2"], rel=1e-12
    )
    assert ann["capacity_factor_dc"] == pytest.approx(
        ann["net_ac_mwh"] / (solar["array"]["dc_mwp"] * 8760.0), rel=1e-12
    )
    assert ann["capacity_factor_ac"] == pytest.approx(
        ann["capacity_factor_dc"] * solar["array"]["dc_mwp"] / solar["array"]["ac_mw"],
        rel=1e-12,
    )
    loss = solar["at_pv_centroid"]["loss_breakdown_of_reference"]
    assert 1.0 + loss["total"] == pytest.approx(ann["performance_ratio"], rel=1e-12)
    assert loss["system_losses"] + loss["temperature_and_irradiance"] + loss[
        "inverter_efficiency_and_clipping"
    ] == pytest.approx(loss["total"], rel=1e-12)
    months = solar["at_pv_centroid"]["monthly"]
    for key in ("ghi_kwh_m2", "dni_kwh_m2", "dhi_kwh_m2", "poa_kwh_m2"):
        assert math.fsum(m[key] for m in months) == pytest.approx(ann[key], rel=1e-12)
    assert math.fsum(m["net_ac_mwh"] for m in months) == pytest.approx(
        ann["net_ac_mwh"], rel=1e-12
    )
    # The scenario header's PV energy before the warranted year-1 1% (9.2224 GWh).
    assert solar["at_tmy_point"]["annual"]["net_ac_mwh"] == pytest.approx(
        9222.4, abs=0.05
    )


def test_committed_solar_outputs_match_a_rerun(solar: Dict[str, Any]) -> None:
    doc = json.loads(SOLAR_SUMMARY.read_text(encoding="utf-8"))
    assert doc["config_sha256"] == hashlib.sha256(CONF.read_bytes()).hexdigest()
    fresh = json.loads(json.dumps(solar, sort_keys=True, allow_nan=False))
    assert {k: v for k, v in doc.items() if k != "config_sha256"} == fresh
    header = SOLAR_CSV.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("month,ghi_kwh_m2,dni_kwh_m2,dhi_kwh_m2,poa_kwh_m2")
    assert len(SOLAR_CSV.read_text(encoding="utf-8").splitlines()) == 13
    site = doc["site"]
    assert site["distance_to_turbine_m"] < 200.0
    assert site["tmy_database"].startswith("PVGIS-ERA5")
