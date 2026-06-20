"""Smoke test for the config-driven Mullikulam 2x50 MW (Mannar) scenario.

A NEW project/location opened from JSON: Musali DS, Mannar (8.82N / 79.96E), Vestas
V150-5.6 proxy for the EN-156/5.0 spec turbine, hub 125 m (tip 200 <= 220, clearance
50 >= 25), Weibull FITTED from live ERA5 2020-2024 @125 m (the "hub YAML-sourced +
Weibull optimized" lesson), USD 3.96 c/kWh tariff (= 11.88 LKR at 300 FX).

Guards the reference scenario against rot and against a silent revert of any of these
config-sourced identity fields to a hand-set or Kalpitiya-inherited value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml"


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
    assert float(cfg["wind_resource"]["mean_wind_speed_ms"]) == pytest.approx(7.07, abs=0.1)


def test_tariff_is_the_usd_bid_in_lkr(cfg: dict) -> None:
    """3.96 USD c/kWh bid carried as 11.88 LKR/kWh (the field revenue actually reads)."""
    assert float(cfg["tariff"]["lkr_per_kwh"]) == pytest.approx(11.88, abs=0.001)


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
    # honest fitted-Weibull economics for one 50 MW lot at Mannar (CF ~0.27)
    assert kpis["project_irr"] == pytest.approx(0.1083, abs=0.01)
    assert kpis["equity_irr"] > 0.0
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)
