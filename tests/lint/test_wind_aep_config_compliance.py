"""ARCH-01 / CESSPIT compliance fence for the wind / AEP surface.

Mirrors the established per-module ``TestNonHardcodedValues`` fences
(tests/lint/test_{refinancing,equity_distribution}_v14_compliance.py) but for the
wind/AEP modules, and strengthens them to the **fail-loud** contract: the turbine /
site identity parameters must be supplied from config, with NO silent fallback to the
legacy EN-171 6.5 MW / 23-turbine / 150 m values.

Two layers:
  1. Behaviour — a config missing a critical identity field RAISES (not defaults).
  2. Source scan — the specific masking-default literals cannot reappear, and the
     cross-engine ``HOURS_PER_YEAR`` constant stays unified.

This makes the no-silent-fallback rule regression-proof, not a one-time cleanup.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.wind.aep_summary_builder import build_aep_summary_from_config
from analytics.wind.aep_tornado import tornado_from_config
from wind_resource.energy_calculator import EnergyCalculator

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture(scope="module")
def scenario() -> dict:
    return load_scenario_config(str(LENDER_CONFIG))


# ── Layer 1: fail-loud behaviour (no silent default) ────────────────────────────


class TestNoSilentDefaults:
    """Critical turbine/site identity must come from config or raise."""

    def test_energy_calculator_requires_num_turbines(self) -> None:
        df = pd.DataFrame({"ws_150m": np.full(24, 8.0)})
        with pytest.raises(ValueError, match="num_turbines is required"):
            EnergyCalculator(df=df, ws_column="ws_150m", turbine_model="iea_reference_10mw")

    def test_tornado_requires_curve_key(self, scenario: dict) -> None:
        bad = copy.deepcopy(scenario)
        del bad["resource"]["power_curve"]["curve_key"]
        with pytest.raises(KeyError, match="curve_key"):
            tornado_from_config(bad)

    def test_tornado_requires_hub_height(self, scenario: dict) -> None:
        """The tornado shear driver must use THIS project's hub height, not 150 m."""
        bad = copy.deepcopy(scenario)
        del bad["resource"]["turbines"]["hub_height_m"]
        with pytest.raises(KeyError, match="hub_height_m"):
            tornado_from_config(bad)

    def test_aep_summary_requires_hub_height(self, scenario: dict) -> None:
        bad = copy.deepcopy(scenario)
        del bad["resource"]["turbines"]["hub_height_m"]
        with pytest.raises(KeyError, match="hub_height_m"):
            build_aep_summary_from_config(bad)

    def test_wind_pipeline_requires_turbine_identity(self) -> None:
        """WindPipeline (public API) must not default to DutchBay turbine/hub/count."""
        from wind_resource.wind_pipeline import WindPipeline

        with pytest.raises(TypeError):
            WindPipeline(location={"name": "x", "lat": 1.0, "lon": 2.0})

    def test_era5_request_config_requires_turbine_identity(self) -> None:
        """Direct construction (not just from_yaml) must require turbine identity."""
        from wind_resource.era5_retrieval import ERA5RequestConfig

        with pytest.raises(TypeError):
            ERA5RequestConfig(
                project_name="x", latitude=1.0, longitude=2.0,
                start_year=2020, end_year=2024,
            )

    def test_lender_scenario_still_builds(self, scenario: dict) -> None:
        """The compliant lender scenario provides every field — no raise, 473.8 GWh."""
        summary = build_aep_summary_from_config(scenario)
        assert summary["net_site_aep_gwh"] == pytest.approx(473.8, abs=1.0)  # ERA5-fitted


# ── Layer 2: source scan (masking literals can't creep back) ────────────────────


def _src(rel: str) -> str:
    return (REPO_ROOT / rel).read_text()


class TestNoMaskingDefaultLiterals:
    """Greppable guards: the removed legacy fallbacks must stay removed."""

    def test_energy_calculator_has_no_num_turbines_default(self) -> None:
        assert "num_turbines: int = 15" not in _src("wind_resource/energy_calculator.py")

    def test_tornado_from_config_has_no_curve_key_fallback(self) -> None:
        src = _src("analytics/wind/aep_tornado.py")
        assert 'get("curve_key", CANONICAL_CURVE_KEY)' not in src

    def test_tornado_has_no_baked_alt_curve(self) -> None:
        """The power-curve driver's alternative machine is config-driven, not baked."""
        assert 'alt_curve_key: str = "ge_cypress' not in _src("analytics/wind/aep_tornado.py")

    def test_mc_aep_has_no_hardcoded_envision_curve(self) -> None:
        """The MC-AEP engine must load THIS project's curve_key, not a baked Envision curve."""
        assert "parse_envision_en171_curve" not in _src("analytics/wind/mc_aep_weibull.py")

    def test_monte_carlo_aep_uses_centralised_losses_and_required_curve(self) -> None:
        """No scattered loss magic numbers, no silent fallback to the legacy curve."""
        src = _src("analytics/simulation/monte_carlo_aep.py")
        assert 'wake_loss_pct", 8.0' not in src  # uses DEFAULT_WIND_LOSSES
        assert "or CANONICAL_CURVE_KEY" not in src  # power_curve_key is required

    def test_pipeline_aep_v14_uses_centralised_losses(self) -> None:
        assert 'wake_loss_pct", 8.0' not in _src("analytics/wind/pipeline_aep_v14.py")

    def test_summary_builder_has_no_hub_height_fallback(self) -> None:
        assert 'get("hub_height_m", 150' not in _src("analytics/wind/aep_summary_builder.py")

    def test_era5_from_yaml_has_no_turbine_identity_fallbacks(self) -> None:
        src = _src("wind_resource/era5_retrieval.py")
        assert 'get("model", "envision' not in src
        assert 'get("num_turbines", 23)' not in src
        assert 'get("hub_height_m", 150' not in src

    def test_wind_pipeline_has_no_turbine_identity_defaults(self) -> None:
        """The general-purpose WindPipeline must bake no DutchBay turbine/hub/count."""
        src = _src("wind_resource/wind_pipeline.py")
        assert "hub_height: float = 150" not in src
        assert "turbine_model: str = 'envision" not in src
        assert "num_turbines: int = 15" not in src

    def test_era5_dataclass_has_no_turbine_identity_defaults(self) -> None:
        """ERA5RequestConfig identity fields are required (no direct-construction bypass)."""
        src = _src("wind_resource/era5_retrieval.py")
        assert 'turbine_model: str = "envision' not in src
        assert "num_turbines: int = 23" not in src
        assert "hub_height_m: float = 150" not in src

    def test_gis_default_era5_source_has_no_identity_fallbacks(self) -> None:
        """gis_export.default_era5_source is a THIRD construction site for ERA5RequestConfig:
        it must not re-introduce the EN-171/23/150 .get() fallbacks #226 removed."""
        src = _src("analytics/gis/gis_export.py")
        assert 'get("hub_height_m", 150' not in src
        assert 'get("turbine_model", "envision' not in src
        assert 'get("num_turbines", 23)' not in src


def test_hours_per_year_is_unified() -> None:
    """The bankable and analytic engines must use the same year length (was 8766 vs 8760)."""
    import analytics.wind.aep_tornado as tornado
    import analytics.wind.losses_model as losses
    import wind_resource.bankable_aep as bankable

    assert (
        bankable.HOURS_PER_YEAR
        == tornado.HOURS_PER_YEAR
        == losses.HOURS_PER_YEAR
        == 8760.0
    )
