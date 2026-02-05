#!/usr/bin/env python
"""Comprehensive test suite for OEM power curve parser.

Tests Envision EN-171-6.5 MW power curve processing, interpolation,
AEP calculations, and IEC 61400-12-1:2022 compliance validation.

Run:
    pytest tests/analytics/test_oem_parser.py -v --cov=analytics.power_curves.oem_parser

Coverage Target: >90%
Test Count: 15 test cases

Context:
    Sprint 17 - Issue #16: OEM Power Curve Parser
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.power_curves.oem_parser import (
    ENVISION_EN171_65_POWER_CURVE,
    ENVISION_EN171_65_SPECS,
    compute_aep_from_curve,
    interpolate_power_curve,
    parse_envision_en171_curve,
    validate_power_curve_iec_compliance,
)


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def reference_curve():
    """Load power curve at reference air density."""
    return parse_envision_en171_curve(air_density_kgm3=None)


@pytest.fixture
def site_curve():
    """Load power curve at site air density (1.15 kg/m³)."""
    return parse_envision_en171_curve(air_density_kgm3=1.15)


@pytest.fixture
def weibull_wind_8760():
    """Generate 8760-hour wind speed timeseries from Weibull distribution."""
    np.random.seed(42)  # Reproducible
    # Weibull: k=2.0, A=7.5 m/s (typical for good wind site)
    wind_speeds = np.random.weibull(2.0, 8760) * 7.5
    return wind_speeds


@pytest.fixture
def constant_wind_8760():
    """Generate 8760-hour constant wind speed timeseries."""
    return np.full(8760, 8.0)  # 8 m/s constant


@pytest.fixture
def low_wind_8760():
    """Generate 8760-hour low wind speed timeseries."""
    np.random.seed(43)
    return np.random.weibull(1.5, 8760) * 4.5  # Mean ~4 m/s


@pytest.fixture
def turbine_config():
    """Standard turbine configuration for testing."""
    return {
        "n_turbines": 23,
        "capacity_mw": 6.5,
        "hub_height_m": 150,
    }


# ══════════════════════════════════════════════════════════════════════════════
# POWER CURVE LOADING TESTS
# ══════════════════════════════════════════════════════════════════════════════


def test_load_reference_power_curve(reference_curve):
    """Test loading power curve at reference air density."""
    assert len(reference_curve) == 46  # 46 data points
    assert "wind_speed_ms" in reference_curve.columns
    assert "power_kw" in reference_curve.columns
    assert "thrust_coefficient" in reference_curve.columns
    assert "capacity_factor" in reference_curve.columns

    # Check wind speed range
    assert reference_curve["wind_speed_ms"].min() == 3.0
    assert reference_curve["wind_speed_ms"].max() == 25.0

    # Check max power near rated
    max_power = reference_curve["power_kw"].max()
    rated_power = ENVISION_EN171_65_SPECS["rated_power_kw"]
    assert abs(max_power - rated_power) / rated_power < 0.01  # Within 1%


def test_air_density_correction(reference_curve, site_curve):
    """Test air density correction from 1.225 to 1.15 kg/m³."""
    rho_ref = 1.225
    rho_site = 1.15
    correction_factor = rho_site / rho_ref

    # Power should scale with air density (below rated)
    ws_test = 8.0  # m/s, below rated wind speed

    power_ref = reference_curve.loc[
        reference_curve["wind_speed_ms"] == ws_test, "power_kw"
    ].iloc[0]

    power_site = site_curve.loc[
        site_curve["wind_speed_ms"] == ws_test, "power_kw"
    ].iloc[0]

    # Check if correction applied correctly
    expected_power_site = power_ref * correction_factor
    assert abs(power_site - expected_power_site) / expected_power_site < 0.01


def test_invalid_air_density():
    """Test that invalid air density raises ValueError."""
    with pytest.raises(ValueError, match="Air density must be in range"):
        parse_envision_en171_curve(air_density_kgm3=0.5)  # Too low

    with pytest.raises(ValueError, match="Air density must be in range"):
        parse_envision_en171_curve(air_density_kgm3=1.5)  # Too high


# ══════════════════════════════════════════════════════════════════════════════
# INTERPOLATION TESTS
# ══════════════════════════════════════════════════════════════════════════════


def test_interpolate_power_curve(reference_curve):
    """Test cubic spline interpolation at arbitrary wind speeds."""
    wind_speeds = np.array([7.3, 9.2, 11.8, 14.5])

    powers = interpolate_power_curve(reference_curve, wind_speeds, method="cubic")

    # All powers should be non-negative
    assert np.all(powers >= 0)

    # All powers should be <= rated power
    rated_power = ENVISION_EN171_65_SPECS["rated_power_kw"]
    assert np.all(powers <= rated_power)

    # Power should increase monotonically (below rated)
    assert powers[0] < powers[1] < powers[2]


def test_interpolation_at_cut_in(reference_curve):
    """Test interpolation behavior at cut-in wind speed."""
    cut_in = ENVISION_EN171_65_SPECS["cut_in_ms"]

    # Slightly below cut-in
    wind_speeds_below = np.array([cut_in - 0.5])
    powers_below = interpolate_power_curve(reference_curve, wind_speeds_below)
    assert powers_below[0] == 0.0  # Should be zero

    # At cut-in
    wind_speeds_at = np.array([cut_in])
    powers_at = interpolate_power_curve(reference_curve, wind_speeds_at)
    assert powers_at[0] > 0  # Should produce some power


def test_interpolation_at_cut_out(reference_curve):
    """Test interpolation behavior at cut-out wind speed."""
    cut_out = ENVISION_EN171_65_SPECS["cut_out_ms"]

    # At cut-out
    wind_speeds_at = np.array([cut_out])
    powers_at = interpolate_power_curve(reference_curve, wind_speeds_at)
    assert powers_at[0] > 0  # Still producing power

    # Above cut-out
    wind_speeds_above = np.array([cut_out + 0.5])
    powers_above = interpolate_power_curve(reference_curve, wind_speeds_above)
    assert powers_above[0] == 0.0  # Should be zero


def test_interpolation_zero_wind(reference_curve):
    """Test interpolation with zero wind speed."""
    wind_speeds = np.array([0.0])
    powers = interpolate_power_curve(reference_curve, wind_speeds)
    assert powers[0] == 0.0


def test_interpolation_extreme_wind(reference_curve):
    """Test interpolation with extreme wind speeds."""
    wind_speeds = np.array([30.0, 40.0])  # Far above cut-out
    powers = interpolate_power_curve(reference_curve, wind_speeds)
    assert np.all(powers == 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# AEP CALCULATION TESTS
# ══════════════════════════════════════════════════════════════════════════════


def test_aep_from_weibull_distribution(
    reference_curve, weibull_wind_8760, turbine_config
):
    """Test AEP calculation from Weibull wind distribution."""
    aep_gwh, cf, losses = compute_aep_from_curve(
        wind_dist_ms=weibull_wind_8760,
        curve=reference_curve,
        n_turbines=turbine_config["n_turbines"],
        capacity_mw=turbine_config["capacity_mw"],
        apply_losses=True,
    )

    # AEP should be positive
    assert aep_gwh > 0

    # Capacity factor should be in realistic range [0.25, 0.45]
    assert 0.25 <= cf <= 0.45

    # Losses should be applied
    assert losses["total_loss_pct"] > 0
    assert losses["wake_loss_pct"] == 8.0
    assert losses["availability_loss_pct"] == 3.0  # 100 - 97
    assert losses["electrical_loss_pct"] == 2.0


def test_aep_from_constant_wind(reference_curve, constant_wind_8760, turbine_config):
    """Test AEP calculation from constant wind speed."""
    aep_gwh, cf, losses = compute_aep_from_curve(
        wind_dist_ms=constant_wind_8760,
        curve=reference_curve,
        n_turbines=turbine_config["n_turbines"],
        capacity_mw=turbine_config["capacity_mw"],
        apply_losses=False,  # No losses
    )

    # With constant 8 m/s, power should be ~3185 kW (from curve)
    # Expected AEP = 3185 kW * 8760 h * 23 turbines / 1e6 = 639.5 GWh
    expected_aep_gwh = 3.185 * 8.760 * 23
    assert abs(aep_gwh - expected_aep_gwh) / expected_aep_gwh < 0.05  # Within 5%


def test_aep_with_loss_factors(reference_curve, weibull_wind_8760, turbine_config):
    """Test that loss factors are correctly applied."""
    # Without losses
    aep_gross, _, _ = compute_aep_from_curve(
        wind_dist_ms=weibull_wind_8760,
        curve=reference_curve,
        n_turbines=turbine_config["n_turbines"],
        capacity_mw=turbine_config["capacity_mw"],
        apply_losses=False,
    )

    # With losses
    aep_net, _, losses = compute_aep_from_curve(
        wind_dist_ms=weibull_wind_8760,
        curve=reference_curve,
        n_turbines=turbine_config["n_turbines"],
        capacity_mw=turbine_config["capacity_mw"],
        apply_losses=True,
        wake_loss_pct=8.0,
        availability_pct=97.0,
        electrical_loss_pct=2.0,
    )

    # Net should be less than gross
    assert aep_net < aep_gross

    # Calculate expected net factor
    wake_factor = 1.0 - 0.08
    avail_factor = 0.97
    elec_factor = 1.0 - 0.02
    expected_net_factor = wake_factor * avail_factor * elec_factor

    expected_aep_net = aep_gross * expected_net_factor
    assert abs(aep_net - expected_aep_net) / expected_aep_net < 0.01


def test_aep_low_wind_site(reference_curve, low_wind_8760, turbine_config):
    """Test AEP calculation for low wind speed site."""
    aep_gwh, cf, _ = compute_aep_from_curve(
        wind_dist_ms=low_wind_8760,
        curve=reference_curve,
        n_turbines=turbine_config["n_turbines"],
        capacity_mw=turbine_config["capacity_mw"],
        apply_losses=True,
    )

    # Low wind site should have low capacity factor
    assert 0.10 <= cf <= 0.30

    # AEP should be positive but lower
    assert aep_gwh > 0


def test_aep_invalid_wind_distribution(reference_curve, turbine_config):
    """Test AEP with invalid wind distribution."""
    # Not 8760 hours
    with pytest.raises(ValueError, match="must be 8760 hours"):
        compute_aep_from_curve(
            wind_dist_ms=np.array([7.5] * 1000),
            curve=reference_curve,
            n_turbines=turbine_config["n_turbines"],
            capacity_mw=turbine_config["capacity_mw"],
        )

    # Negative wind speeds
    with pytest.raises(ValueError, match="cannot be negative"):
        compute_aep_from_curve(
            wind_dist_ms=np.array([-1.0] * 8760),
            curve=reference_curve,
            n_turbines=turbine_config["n_turbines"],
            capacity_mw=turbine_config["capacity_mw"],
        )


# ══════════════════════════════════════════════════════════════════════════════
# IEC COMPLIANCE TESTS
# ══════════════════════════════════════════════════════════════════════════════


def test_iec_compliance_validation(reference_curve):
    """Test IEC 61400-12-1:2022 compliance validation."""
    validation = validate_power_curve_iec_compliance(reference_curve)

    assert validation["compliant"] is True
    assert validation["rated_power_ok"] is True
    assert validation["monotonic_ok"] is True
    assert validation["cutin_ok"] is True
    assert validation["cutout_ok"] is True

    # Rated power tolerance should be within 3%
    assert validation["rated_power_tolerance_pct"] <= 3.0

    # Max power should be close to rated
    rated_power = ENVISION_EN171_65_SPECS["rated_power_kw"]
    assert abs(validation["max_power_kw"] - rated_power) / rated_power < 0.01


def test_thrust_coefficient_values(reference_curve):
    """Test that thrust coefficients are in valid range."""
    ct_values = reference_curve["thrust_coefficient"].values

    # All CT values should be in [0, 1]
    assert np.all(ct_values >= 0)
    assert np.all(ct_values <= 1)

    # CT should generally decrease after rated wind speed
    rated_ws = ENVISION_EN171_65_SPECS["rated_wind_speed_ms"]
    ct_below_rated = reference_curve[reference_curve["wind_speed_ms"] <= rated_ws][
        "thrust_coefficient"
    ].values

    ct_above_rated = reference_curve[reference_curve["wind_speed_ms"] > rated_ws][
        "thrust_coefficient"
    ].values

    # Mean CT above rated should be less than below rated
    assert ct_above_rated.mean() < ct_below_rated.mean()


# ══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ══════════════════════════════════════════════════════════════════════════════


def test_single_turbine_aep(reference_curve, weibull_wind_8760):
    """Test AEP calculation for a single turbine."""
    aep_gwh, cf, _ = compute_aep_from_curve(
        wind_dist_ms=weibull_wind_8760,
        curve=reference_curve,
        n_turbines=1,  # Single turbine
        capacity_mw=6.5,
        apply_losses=False,
    )

    # AEP should be positive
    assert aep_gwh > 0

    # For single turbine, AEP should be in reasonable range [10, 30] GWh
    assert 10 <= aep_gwh <= 30


def test_power_curve_dataframe_structure(reference_curve):
    """Test that power curve DataFrame has correct structure."""
    assert isinstance(reference_curve, pd.DataFrame)

    required_cols = [
        "wind_speed_ms",
        "power_kw",
        "thrust_coefficient",
        "capacity_factor",
    ]

    for col in required_cols:
        assert col in reference_curve.columns

    # Check data types
    assert reference_curve["wind_speed_ms"].dtype == np.float64
    assert reference_curve["power_kw"].dtype == np.float64
    assert reference_curve["thrust_coefficient"].dtype == np.float64
    assert reference_curve["capacity_factor"].dtype == np.float64


# ══════════════════════════════════════════════════════════════════════════════
# PARAMETRIZED TESTS
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "air_density,expected_cf_range",
    [
        (1.225, (0.30, 0.40)),  # Sea level
        (1.15, (0.28, 0.38)),  # 150m elevation
        (1.05, (0.26, 0.36)),  # 500m elevation
        (0.95, (0.24, 0.34)),  # 1000m elevation
    ],
)
def test_aep_at_different_elevations(
    weibull_wind_8760, turbine_config, air_density, expected_cf_range
):
    """Test AEP calculation at different site elevations (air densities)."""
    curve = parse_envision_en171_curve(air_density_kgm3=air_density)

    _, cf, _ = compute_aep_from_curve(
        wind_dist_ms=weibull_wind_8760,
        curve=curve,
        n_turbines=turbine_config["n_turbines"],
        capacity_mw=turbine_config["capacity_mw"],
        apply_losses=True,
    )

    # Capacity factor should be in expected range
    assert expected_cf_range[0] <= cf <= expected_cf_range[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=analytics.power_curves.oem_parser"])
