"""Tests for the solar PV P50/P75/P90 exceedance build-up (#469 — SOLAR-2).

All pure (no pvlib): the exceedance maths consumes a P50 energy and a budget. One gated
test exercises the compute_solar_aep emit_exceedance integration (needs the [solar] extra).
"""

from __future__ import annotations

import math

import pytest

from solar_resource.exceedance import (
    SolarExceedanceResult,
    SolarUncertaintyBudget,
    exceedance_levels_solar,
)


class TestUncertaintyBudget:
    def test_systematic_sigma_rss_baseline(self):
        b = SolarUncertaintyBudget()  # defaults
        # RSS of the 7 systematic categories (interannual excluded).
        expected = math.sqrt(
            4.0**2 + 2.5**2 + 4.0**2 + 2.0**2 + 2.0**2 + 1.5**2 + 1.0**2
        )
        assert b.systematic_sigma_pct(0.0) == pytest.approx(expected)
        assert b.systematic_sigma_pct(0.0) == pytest.approx(7.0356, abs=1e-3)

    def test_systematic_sigma_full_correlation_is_linear_sum(self):
        b = SolarUncertaintyBudget()
        linear = 4.0 + 2.5 + 4.0 + 2.0 + 2.0 + 1.5 + 1.0
        assert b.systematic_sigma_pct(1.0) == pytest.approx(linear)  # rho=1 -> sum

    def test_combined_sigma_includes_interannual_at_1yr(self):
        b = SolarUncertaintyBudget()
        sys = b.systematic_sigma_pct(0.0)
        expected = math.sqrt(sys**2 + 3.0**2)  # interannual 3.0, un-reduced at N=1
        assert b.combined_sigma_pct(1.0) == pytest.approx(expected)

    def test_combined_sigma_shrinks_interannual_over_life(self):
        b = SolarUncertaintyBudget()
        sys = b.systematic_sigma_pct(0.0)
        expected_life = math.sqrt(sys**2 + (3.0 / math.sqrt(20.0)) ** 2)
        assert b.combined_sigma_pct(20.0) == pytest.approx(expected_life)
        # Project-life sigma is smaller than 1-year sigma (interannual time-averages out).
        assert b.combined_sigma_pct(20.0) < b.combined_sigma_pct(1.0)

    def test_correlation_clamped(self):
        b = SolarUncertaintyBudget()
        assert b.systematic_sigma_pct(-5.0) == pytest.approx(
            b.systematic_sigma_pct(0.0)
        )
        assert b.systematic_sigma_pct(5.0) == pytest.approx(b.systematic_sigma_pct(1.0))

    def test_negative_component_rejected(self):
        with pytest.raises(ValueError, match="must be >= 0"):
            SolarUncertaintyBudget(soiling_pct=-1.0)

    def test_from_scenario_overrides_and_rejects_unknown(self):
        b = SolarUncertaintyBudget.from_scenario(
            {"soiling_pct": 3.5, "ghi_dataset_pct": 5.0}
        )
        assert b.soiling_pct == 3.5
        assert b.ghi_dataset_pct == 5.0
        assert b.transposition_pct == 2.5  # default retained
        with pytest.raises(KeyError, match="unknown field"):
            SolarUncertaintyBudget.from_scenario({"soling_pct": 2.0})  # typo


class TestExceedanceLevels:
    def test_ordering_p50_gt_p75_gt_p90(self):
        r = exceedance_levels_solar(100.0, SolarUncertaintyBudget())
        assert r.p50_gwh == pytest.approx(100.0)
        assert r.p50_gwh > r.p75_gwh > r.p90_1yr_gwh
        # Less uncertainty over the project life -> a HIGHER P90 than the 1-year P90.
        assert r.p90_life_gwh > r.p90_1yr_gwh

    def test_values_match_shared_formula(self):
        b = SolarUncertaintyBudget()
        r = exceedance_levels_solar(100.0, b)
        sig1 = b.combined_sigma_pct(1.0)
        # P_x = P50 * (1 - z * sigma/100), z90 = 1.2816 (shared table).
        assert r.p90_1yr_gwh == pytest.approx(100.0 * (1.0 - 1.2816 * sig1 / 100.0))

    def test_p50_haircut_applies_before_buildup(self):
        r = exceedance_levels_solar(
            100.0, SolarUncertaintyBudget(), p50_haircut_pct=2.0
        )
        assert r.p50_gwh == pytest.approx(98.0)  # haircut first
        assert r.p75_gwh < 98.0

    def test_deterministic(self):
        a = exceedance_levels_solar(87.6, SolarUncertaintyBudget())
        b = exceedance_levels_solar(87.6, SolarUncertaintyBudget())
        assert a == b  # frozen dataclass, no Date.now/random

    def test_non_positive_p50_raises(self):
        with pytest.raises(ValueError, match="p50_gwh must be > 0"):
            exceedance_levels_solar(0.0, SolarUncertaintyBudget())

    def test_result_is_frozen_dataclass(self):
        r = exceedance_levels_solar(100.0, SolarUncertaintyBudget())
        assert isinstance(r, SolarExceedanceResult)
        with pytest.raises(Exception):
            r.p50_gwh = 1.0  # frozen


class TestSharedZTableParity:
    """The wind and solar exceedance build-ups must use the ONE shared z-table."""

    def test_solar_and_wind_share_the_same_z_table(self):
        from analytics.core.exceedance import EXCEEDANCE_Z
        from wind_resource.bankable_aep import _EXCEEDANCE_Z as wind_z

        assert wind_z is EXCEEDANCE_Z  # same object, not a fork

    def test_solar_p90_fraction_equals_wind_for_equal_sigma(self):
        # For an identical combined sigma and P50, solar and wind exceedance agree exactly.
        # Wind budget with only one systematic term so its 1-yr sigma is known.
        from wind_resource.bankable_aep import UncertaintyBudget as WindBudget
        from wind_resource.bankable_aep import exceedance_levels as wind_exceedance

        wind_b = WindBudget(
            wind_measurement_pct=5.0,
            long_term_pct=0.0,
            vertical_extrapolation_pct=0.0,
            horizontal_flow_pct=0.0,
            power_curve_pct=0.0,
            wake_model_pct=0.0,
            interannual_variability_pct=3.0,
        )
        solar_b = SolarUncertaintyBudget(
            ghi_dataset_pct=5.0,
            transposition_pct=0.0,
            pv_simulation_pct=0.0,
            soiling_pct=0.0,
            module_power_tolerance_pct=0.0,
            thermal_model_pct=0.0,
            availability_pct=0.0,
            interannual_ghi_variability_pct=3.0,
        )
        w = wind_exceedance(100.0, wind_b)
        s = exceedance_levels_solar(100.0, solar_b)
        assert s.p75_gwh == pytest.approx(w.p75_gwh)
        assert s.p90_1yr_gwh == pytest.approx(w.p90_1yr_gwh)
        assert s.p90_life_gwh == pytest.approx(w.p90_life_gwh)


class TestProducerIntegration:
    """compute_solar_aep emit_exceedance — gated on the [solar] extra."""

    def test_emit_exceedance_populates_result(self):
        pytest.importorskip("pvlib")
        from solar_resource.pv_producer import SolarResourceConfig, compute_solar_aep

        cfg = SolarResourceConfig(
            latitude=8.27,
            longitude=79.75,
            annual_ghi_kwh_m2=2000.0,
            dc_capacity_mw=50.0,
        )
        # Default (P50-only) is byte-identical and carries no exceedance.
        base = compute_solar_aep(cfg)
        assert base.exceedance is None
        # With emit_exceedance the P50 is unchanged but P75/P90 are populated.
        withx = compute_solar_aep(cfg, emit_exceedance=True)
        assert withx.annual_energy_gwh == pytest.approx(base.annual_energy_gwh)
        assert withx.exceedance is not None
        assert (
            withx.exceedance.p50_gwh
            > withx.exceedance.p75_gwh
            > withx.exceedance.p90_1yr_gwh
        )
        assert withx.exceedance.p50_gwh == pytest.approx(base.annual_energy_gwh)
