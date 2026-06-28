"""Smoke test for the config-driven, ERA5-fitted-Weibull Kalpitiya 160 m scenario.

Encodes the lesson: hub height is YAML-sourced (no Python override) and the Weibull is
OPTIMIZED (fitted from live ERA5 2020-2024), not the declared k=2.1 which overstated AEP.
Guards the reference scenario against rot + against a silent revert to hand-set parameters.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = REPO_ROOT / "scenarios" / "kalpitiya_lendercase_160m_fitted.yaml"


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_scenario_config(str(SCENARIO))


def test_hub_height_is_yaml_sourced_and_consistent(cfg: dict) -> None:
    """160 m comes from config, consistently across turbine / turbines / era5."""
    assert cfg["turbine"]["hub_height_m"] == 160
    assert cfg["resource"]["turbines"]["hub_height_m"] == 160
    assert cfg["resource"]["era5"]["hub_height_m"] == 160  # cross-asserted by the adapter


def test_weibull_is_the_fitted_optimum_not_the_declared(cfg: dict) -> None:
    """The Weibull is the ERA5-fitted shape (k~2.66), NOT the declared k=2.1."""
    k = float(cfg["wind_resource"]["weibull_k"])
    a = float(cfg["wind_resource"]["weibull_a"])
    assert k == pytest.approx(2.664, abs=0.03)  # fitted, far above the declared 2.1
    assert k > 2.4
    assert a == pytest.approx(8.259, abs=0.05)


def test_scenario_passes_schemas(cfg: dict) -> None:
    validate_config_for_v14(cfg, str(SCENARIO), ["era5", "wind"])  # must not raise


def test_pipeline_runs_config_driven(cfg: dict) -> None:
    """The finance pipeline runs straight from the YAML (no Python overrides)."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    # honest fitted-Weibull economics at 160 m, at the corrected FX 333.79, the 2026-06
    # construction-lag/off-by-one project-discounting fix (audit finding 2.0) AND the M3e
    # degradation re-baseline (0.005 -> 0.5, honest 0.5%/yr aging). After the 5.9% FX-drift
    # re-baseline (fx.annual_depr 0.03 -> 0.0589, data-derived from BIS 2005-2026 LKR
    # depreciation), the flat-LKR tariff erodes faster in USD terms: project IRR ~3.12%
    # after PR-A's fabricated-levy removal (still below the ~8.0% WACC). Levered equity IRR
    # is NEGATIVE at ~-1.03% — PR-A's 15% dividend WHT pushes it down (the IDC shield only
    # partly offsets); project IRR is upstream of the equity waterfall.
    assert kpis["project_irr"] == pytest.approx(0.0312, abs=0.01)
    assert kpis["equity_irr"] == pytest.approx(-0.0103, abs=0.01)
    assert kpis["equity_irr"] < kpis["project_irr"]  # levered equity below the project return
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)
