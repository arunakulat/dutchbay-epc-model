"""Smoke test for the config-driven Mullikulam 2x50 MW (Mannar) scenario.

A NEW project/location opened from JSON: Musali DS, Mannar (8.82N / 79.96E), Vestas
V150-5.6 proxy for the EN-156/5.0 spec turbine, hub 125 m (tip 200 <= 220, clearance
50 >= 25), Weibull FITTED from live ERA5 2020-2024 @125 m (the "hub YAML-sourced +
Weibull optimized" lesson), USD 3.96 c/kWh tariff (= 11.88 LKR at 300 FX).

Guards the reference scenario against rot and against a silent revert of any of these
config-sourced identity fields to a hand-set or Kalpitiya-inherited value.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml"
# #996 D3b: the financial-KPI oracle lives in a golden fixture, not the scenario.
EXPECTED_KPIS = (
    REPO_ROOT / "tests" / "fixtures" / "finance" / "mullikulam_expected_kpis.json"
)


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_scenario_config(str(SCENARIO))


def test_location_and_turbine_are_yaml_sourced(cfg: dict) -> None:
    """Mannar location + Vestas V150-5.6 identity comes from config, consistently."""
    assert cfg["resource"]["era5"]["latitude"] == pytest.approx(8.82, abs=0.001)
    assert cfg["resource"]["era5"]["longitude"] == pytest.approx(79.96, abs=0.001)
    assert cfg["turbine"]["n_turbines"] == 10
    assert cfg["turbine"]["rotor_diameter_m"] == 150  # <= 160 m spec cap
    assert cfg["turbine"]["rated_power_mw"] == pytest.approx(5.6, abs=0.01)
    # Identity must be Mannar/56 MW, NOT a Kalpitiya/159.6 MW lender inheritance.
    # (capacity_mw drives revenue: capacity x CF x 8760, so a stale 159.6 silently
    # inflated generation ~3x — this guards against that regression recurring.)
    assert "Mannar" in cfg["project"]["location"]
    assert "Kalpitiya" not in cfg["project"]["location"]
    assert cfg["project"]["capacity_mw"] == pytest.approx(56.0, abs=0.01)


def test_hub_height_is_yaml_sourced_and_consistent(cfg: dict) -> None:
    """125 m comes from config, consistently across turbine / turbines / era5."""
    assert cfg["turbine"]["hub_height_m"] == 125
    assert cfg["resource"]["turbines"]["hub_height_m"] == 125
    assert cfg["resource"]["era5"]["hub_height_m"] == 125  # cross-asserted by adapter
    # tip = hub + rotor/2 = 200 m <= 220 m; clearance = hub - rotor/2 = 50 m >= 25 m
    tip = cfg["turbine"]["hub_height_m"] + cfg["turbine"]["rotor_diameter_m"] / 2
    clearance = cfg["turbine"]["hub_height_m"] - cfg["turbine"]["rotor_diameter_m"] / 2
    assert tip <= 220
    assert clearance >= 25


def test_weibull_is_the_era5_fitted_optimum(cfg: dict) -> None:
    """The Weibull is the ERA5-fitted Mannar shape, NOT a Kalpitiya-inherited value."""
    a = float(cfg["wind_resource"]["weibull_a"])
    k = float(cfg["wind_resource"]["weibull_k"])
    assert a == pytest.approx(7.97, abs=0.05)
    assert k == pytest.approx(2.506, abs=0.05)
    assert float(cfg["wind_resource"]["mean_wind_speed_ms"]) == pytest.approx(
        7.07, abs=0.1
    )


def test_tariff_is_the_usd_bid_in_lkr(cfg: dict) -> None:
    """3.96 USD c/kWh bid carried as 13.22 LKR/kWh at the corrected FX 333.79.

    (Was 11.88 = 0.0396 x the stale 300; the USD bid is preserved at the real rate.)
    """
    assert float(cfg["tariff"]["lkr_per_kwh"]) == pytest.approx(13.22, abs=0.001)


def test_curve_is_the_registered_approved_source(cfg: dict) -> None:
    """The Vestas curve resolves to its approved-source manifest id (global-reuse)."""
    from analytics.loader.aep_loader import APPROVED_SOURCES

    pc = cfg["resource"]["power_curve"]
    assert pc["curve_key"] == "vestas_v150_5p6"
    assert pc["source_id"] == "OEM_VESTAS_V150_56_PC"
    assert APPROVED_SOURCES[pc["source_id"]]["curve_key"] == "vestas_v150_5p6"


def test_scenario_passes_schemas(cfg: dict) -> None:
    validate_config_for_v14(cfg, str(SCENARIO), ["era5", "wind"])  # must not raise


def test_pipeline_runs_config_driven(cfg: dict) -> None:
    """The finance pipeline runs straight from the YAML (no Python overrides)."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    # HONEST economics for one 56 MW Lot at Mannar (CF ~0.27) at the real 3.96 USc/kWh
    # WindForce bid: the project is uneconomic (LCOE ~5.5c > tariff). The earlier
    # project_irr~0.108 / equity_irr>0 asserts were an artifact of a 3x-inflated
    # capacity_mw (159.6 vs the real 56) — see the scenario's expected_results note.
    # M3e: degradation 0.005 -> 0.5 (honest 0.5%/yr aging) deepened it, and the IRR-floor
    # fix lets the project IRR report its true NEGATIVE value rather than 0.0.
    # TLCF-EXPIRY re-baseline (Wave-1 audit) deepened the already-negative economics
    # (losses now expire after the SL 6-year window, raising later-year cash tax). The
    # round-5 #5 interest-tax-shield fix then lifted equity slightly (the deal has little
    # taxable income to shield). The 5.9% FX-drift re-baseline (fx.annual_depr 0.03 -> 0.0589,
    # data-derived BIS 2005-2026 LKR depreciation) deepened it further as the flat-LKR
    # revenue erodes faster in USD terms: current projIRR -6.68%, eqIRR -15.76%. The fixes
    # only bite scenarios with persistent unused losses; the canonical wind lendercase is byte-identical.
    assert kpis["project_irr"] == pytest.approx(-0.0668, abs=0.005)
    assert kpis["project_irr"] < 0.0  # below break-even even undiscounted
    assert kpis["equity_irr"] == pytest.approx(
        -0.1732, abs=0.01
    )  # PR-B UIP LKR rate deepens it
    assert kpis["equity_irr"] < 0.0  # equity-destroying at the 3.96c bid
    assert kpis["project_npv"] < 0.0
    assert kpis["min_dscr"] == pytest.approx(
        1.30, abs=0.02
    )  # sizer holds DSCR, sizes debt down


def test_expected_results_block_matches_live_engine() -> None:
    """Bind the scenario's expected_results financial pins to the live engine so they cannot
    silently drift again (round-7 stale-pin fix). The mullikulam expected_results had gone
    stale — its LLCR/PLCR predated PR #389 and no test read the block."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    exp = json.loads(EXPECTED_KPIS.read_text())
    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    # #996 D3b: financial KPIs come from the fixture; the scenario keeps net_aep (runtime).
    scen_er = load_scenario_config(str(SCENARIO))["expected_results"]
    assert "net_aep_p50_gwh" in scen_er and "net_aep_p90_gwh" in scen_er
    assert "project_irr" not in scen_er and "equity_moic" not in scen_er
    assert kpis["project_irr"] == pytest.approx(exp["project_irr"], abs=2e-3)
    assert kpis["equity_irr"] == pytest.approx(exp["equity_irr"], abs=2e-3)
    assert kpis["project_npv"] / 1e6 == pytest.approx(exp["project_npv_m_usd"], abs=0.1)
    assert kpis["equity_npv"] / 1e6 == pytest.approx(exp["equity_npv_m_usd"], abs=0.1)
    assert kpis["equity_moic"] == pytest.approx(exp["equity_moic"], abs=2e-3)
    assert kpis["min_dscr"] == pytest.approx(exp["min_dscr"], abs=1e-2)
    assert kpis["avg_dscr"] == pytest.approx(exp["avg_dscr"], abs=2e-3)
    assert kpis["llcr"] == pytest.approx(exp["llcr"], abs=2e-3)
    assert kpis["plcr"] == pytest.approx(exp["plcr"], abs=2e-3)
