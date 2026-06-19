#!/usr/bin/env python
"""Test suite for the OEM power-curve parser (Envision EN-171/6.5 MW).

These tests assert the *honest* behaviour of ``analytics.power_curves.oem_parser``
after the 10 MW placeholder curve and the ``EN171_65 -> 10 MW`` aliasing were
removed (the curve is now config-sourced from
``wind_resource/config/power_curves.yaml``). The suite previously carried a
module-level ``xfail`` because it was written against an *aspirational* parser
(thrust-coefficient/Ct data, a 46-point curve, capacity-factor columns) that was
never built; that aspiration has been dropped in favour of testing what exists.

Run:
    pytest tests/analytics/test_oem_parser.py -v

Context:
    Sprint 17 - Issue #16 (OEM Power Curve); de-fictioned per the #176-#182 AEP
    re-baseline (6.5 MW canonical).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.power_curves.oem_parser import (
    CANONICAL_CURVE_KEY,
    ENVISION_EN171_65_POWER_CURVE,
    ENVISION_EN171_65_SPECS,
    compute_aep_from_curve,
    interpolate_power_curve,
    parse_envision_en171_curve,
    parse_power_curve,
    validate_power_curve_iec_compliance,
)

# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def reference_curve() -> pd.DataFrame:
    """Power curve at the IEC reference air density."""
    return parse_envision_en171_curve(air_density_kgm3=None)


@pytest.fixture
def site_curve() -> pd.DataFrame:
    """Power curve at a site air density of 1.15 kg/m^3."""
    return parse_envision_en171_curve(air_density_kgm3=1.15)


@pytest.fixture
def weibull_wind_8760() -> np.ndarray:
    """Deterministic 8760-hour Weibull wind timeseries (A=7.5, k=2.0)."""
    rng = np.random.RandomState(42)
    return rng.weibull(2.0, 8760) * 7.5


@pytest.fixture
def constant_wind_8760() -> np.ndarray:
    """8760-hour constant 8 m/s wind timeseries."""
    return np.full(8760, 8.0)


@pytest.fixture
def low_wind_8760() -> np.ndarray:
    """Deterministic 8760-hour low-wind timeseries (mean ~4 m/s)."""
    rng = np.random.RandomState(43)
    return rng.weibull(1.5, 8760) * 4.5


@pytest.fixture
def turbine_config() -> dict:
    """Canonical DutchBay turbine configuration (23 x 6.5 MW)."""
    return {"n_turbines": 23, "capacity_mw": 6.5, "hub_height_m": 150}


# ══════════════════════════════════════════════════════════════════════════════
# ANTI-FICTION GUARD + CURVE STRUCTURE
# ══════════════════════════════════════════════════════════════════════════════


def test_specs_are_canonical_6p5() -> None:
    """Specs must describe the 6.5 MW machine, not the retired 10 MW placeholder."""
    assert ENVISION_EN171_65_SPECS["rated_power_kw"] == 6500.0
    assert ENVISION_EN171_65_SPECS["rated_power_mw"] == 6.5
    assert "6.5" in str(ENVISION_EN171_65_SPECS["model"])
    assert str(ENVISION_EN171_65_SPECS["source"]).endswith("envision_en171_6p5")


def test_base_curve_peaks_at_rated() -> None:
    """The config-sourced base curve peaks at the 6.5 MW rating."""
    assert abs(ENVISION_EN171_65_POWER_CURVE["power_kw"].max() - 6500.0) < 1.0


def test_reference_curve_structure(reference_curve: pd.DataFrame) -> None:
    """Reference curve has the expected columns and wind-speed span."""
    assert list(reference_curve.columns) == ["wind_speed_ms", "power_kw", "power_mw"]
    assert reference_curve["wind_speed_ms"].min() == 0.0
    assert reference_curve["wind_speed_ms"].max() == 30.0
    assert abs(reference_curve["power_kw"].max() - 6500.0) < 1.0
    assert reference_curve["wind_speed_ms"].dtype == np.float64
    assert reference_curve["power_kw"].dtype == np.float64


# ══════════════════════════════════════════════════════════════════════════════
# AIR-DENSITY CORRECTION
# ══════════════════════════════════════════════════════════════════════════════


def test_air_density_correction(
    reference_curve: pd.DataFrame, site_curve: pd.DataFrame
) -> None:
    """Power scales with (rho_site/rho_ref)^(1/3) per IEC 61400-12-1."""
    p_ref = reference_curve.loc[
        reference_curve["wind_speed_ms"] == 8.0, "power_kw"
    ].iloc[0]
    p_site = site_curve.loc[site_curve["wind_speed_ms"] == 8.0, "power_kw"].iloc[0]
    expected_ratio = (1.15 / 1.225) ** (1.0 / 3.0)
    assert p_site / p_ref == pytest.approx(expected_ratio, rel=1e-3)


def test_invalid_air_density() -> None:
    """Out-of-band air densities raise a clear ValueError."""
    with pytest.raises(ValueError, match="Air density must be in range"):
        parse_envision_en171_curve(air_density_kgm3=0.5)
    with pytest.raises(ValueError, match="Air density must be in range"):
        parse_envision_en171_curve(air_density_kgm3=1.5)


# ══════════════════════════════════════════════════════════════════════════════
# INTERPOLATION
# ══════════════════════════════════════════════════════════════════════════════


def test_interpolation_monotonic_below_rated(reference_curve: pd.DataFrame) -> None:
    """Interpolated power rises monotonically through the below-rated region."""
    powers = interpolate_power_curve(reference_curve, np.array([5.0, 7.0, 9.0, 11.0]))
    assert np.all(np.diff(powers) > 0)
    assert np.all(powers >= 0)
    assert np.all(powers <= ENVISION_EN171_65_SPECS["rated_power_kw"] + 1e-6)


def test_interpolation_cut_in_cut_out(reference_curve: pd.DataFrame) -> None:
    """Zero below cut-in, positive above cut-in, zero above cut-out."""
    assert interpolate_power_curve(reference_curve, np.array([2.5]))[0] == 0.0
    assert interpolate_power_curve(reference_curve, np.array([6.0]))[0] > 0.0
    assert interpolate_power_curve(reference_curve, np.array([26.0]))[0] == 0.0


def test_interpolation_zero_and_extreme(reference_curve: pd.DataFrame) -> None:
    """Zero and far-above-cut-out wind speeds produce zero power."""
    assert interpolate_power_curve(reference_curve, np.array([0.0]))[0] == 0.0
    assert np.all(
        interpolate_power_curve(reference_curve, np.array([30.0, 40.0])) == 0.0
    )


# ══════════════════════════════════════════════════════════════════════════════
# AEP CALCULATION
# ══════════════════════════════════════════════════════════════════════════════


def test_aep_weibull(
    reference_curve: pd.DataFrame, weibull_wind_8760: np.ndarray, turbine_config: dict
) -> None:
    """AEP/CF from a realistic Weibull site land in the honest 6.5 MW range."""
    aep, cf, losses = compute_aep_from_curve(
        wind_dist_ms=weibull_wind_8760,
        curve=reference_curve,
        n_turbines=turbine_config["n_turbines"],
        capacity_mw=turbine_config["capacity_mw"],
        apply_losses=True,
    )
    assert aep > 0
    # Honest 6.5 MW curve at A=7.5/k=2.0 with the default loss stack -> ~0.245.
    assert 0.20 <= cf <= 0.30
    assert losses["wake_loss_pct"] == 8.0
    assert losses["availability_loss_pct"] == pytest.approx(3.0)
    assert losses["electrical_loss_pct"] == 2.0
    assert losses["total_loss_pct"] > 0


def test_aep_constant_wind(
    reference_curve: pd.DataFrame, constant_wind_8760: np.ndarray
) -> None:
    """Constant 8 m/s -> 2150 kW/turbine (a curve node) gives a closed-form AEP."""
    aep, cf, _ = compute_aep_from_curve(
        wind_dist_ms=constant_wind_8760,
        curve=reference_curve,
        n_turbines=23,
        capacity_mw=6.5,
        apply_losses=False,
    )
    expected_aep = 2.150 * 8.760 * 23  # 2150 kW * 8760 h * 23 turbines / 1e6
    assert aep == pytest.approx(expected_aep, rel=0.01)
    assert cf == pytest.approx(2150.0 / 6500.0, rel=0.01)


def test_aep_losses_multiplicative(
    reference_curve: pd.DataFrame, weibull_wind_8760: np.ndarray
) -> None:
    """Net AEP equals gross times the multiplicative loss factor."""
    gross, _, _ = compute_aep_from_curve(
        weibull_wind_8760, reference_curve, 23, 6.5, apply_losses=False
    )
    net, _, _ = compute_aep_from_curve(
        weibull_wind_8760,
        reference_curve,
        23,
        6.5,
        apply_losses=True,
        wake_loss_pct=8.0,
        availability_pct=97.0,
        electrical_loss_pct=2.0,
    )
    assert net < gross
    factor = (1.0 - 0.08) * 0.97 * (1.0 - 0.02)
    assert net == pytest.approx(gross * factor, rel=0.01)


def test_aep_low_wind(
    reference_curve: pd.DataFrame, low_wind_8760: np.ndarray
) -> None:
    """A low-wind site yields a low (but positive) capacity factor."""
    aep, cf, _ = compute_aep_from_curve(
        low_wind_8760, reference_curve, 23, 6.5, apply_losses=True
    )
    assert aep > 0
    assert 0.05 <= cf <= 0.15


def test_aep_invalid_distribution(reference_curve: pd.DataFrame) -> None:
    """Wrong-length and negative wind series raise clear ValueErrors."""
    with pytest.raises(ValueError, match="Expected 8760-hour timeseries"):
        compute_aep_from_curve(np.full(1000, 7.5), reference_curve, 23, 6.5)
    with pytest.raises(ValueError, match="cannot be negative"):
        compute_aep_from_curve(np.full(8760, -1.0), reference_curve, 23, 6.5)


def test_single_turbine_aep(
    reference_curve: pd.DataFrame, weibull_wind_8760: np.ndarray
) -> None:
    """A single 6.5 MW turbine produces a sane standalone AEP."""
    aep, _, _ = compute_aep_from_curve(
        weibull_wind_8760, reference_curve, 1, 6.5, apply_losses=False
    )
    assert 10.0 <= aep <= 25.0


# ══════════════════════════════════════════════════════════════════════════════
# IEC COMPLIANCE + AIR-DENSITY SWEEP
# ══════════════════════════════════════════════════════════════════════════════


def test_iec_compliance(reference_curve: pd.DataFrame) -> None:
    """Lightweight IEC 61400-12-1 structural checks pass for the real curve."""
    validation = validate_power_curve_iec_compliance(reference_curve)
    assert validation["compliant"] is True
    assert validation["monotonic_ok"] is True
    assert validation["cutin_ok"] is True
    assert validation["cutout_ok"] is True
    assert abs(validation["max_power_kw"] - 6500.0) < 1.0


@pytest.mark.parametrize("air_density", [1.225, 1.15, 1.05, 0.95])
def test_aep_air_density_band(
    weibull_wind_8760: np.ndarray, air_density: float
) -> None:
    """CF stays in a plausible band across site elevations (air densities)."""
    curve = parse_envision_en171_curve(air_density_kgm3=air_density)
    _, cf, _ = compute_aep_from_curve(
        weibull_wind_8760, curve, 23, 6.5, apply_losses=True
    )
    assert 0.18 <= cf <= 0.28


def test_aep_increases_with_air_density(weibull_wind_8760: np.ndarray) -> None:
    """Denser air yields a higher capacity factor."""
    cf_high = compute_aep_from_curve(
        weibull_wind_8760, parse_envision_en171_curve(1.225), 23, 6.5
    )[1]
    cf_low = compute_aep_from_curve(
        weibull_wind_8760, parse_envision_en171_curve(0.95), 23, 6.5
    )[1]
    assert cf_high > cf_low


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG-SELECTABLE CURVE (GWTF ARCH-01 — not hardwired to one turbine)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "curve_key,expected_peak_kw",
    [
        ("envision_en171_6p5", 6500.0),
        ("vestas_v150_5p6", 5600.0),
        ("ge_cypress_5p5", 5500.0),
    ],
)
def test_parse_power_curve_selects_by_key(curve_key: str, expected_peak_kw: float) -> None:
    """parse_power_curve loads whichever store curve the model selected."""
    curve = parse_power_curve(curve_key)
    assert abs(curve["power_kw"].max() - expected_peak_kw) < 1.0
    assert str(curve.attrs["source"]).endswith(curve_key)


def test_parse_power_curve_unknown_key_raises() -> None:
    with pytest.raises(KeyError, match="not found"):
        parse_power_curve("not_a_real_turbine")


def test_envision_wrapper_matches_canonical_key() -> None:
    """The legacy wrapper equals parse_power_curve at the canonical key."""
    wrapper = parse_envision_en171_curve(1.15)
    explicit = parse_power_curve(CANONICAL_CURVE_KEY, 1.15)
    assert list(wrapper["power_kw"]) == list(explicit["power_kw"])


def test_monte_carlo_uses_summary_curve_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The auxiliary MC path picks the curve recorded in the AEP summary."""
    import analytics.simulation.monte_carlo_aep as mc

    seen: dict = {}
    original = mc.parse_power_curve

    def _spy(key, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["key"] = key
        return original(key, *args, **kwargs)

    monkeypatch.setattr(mc, "parse_power_curve", _spy)
    mc.run_monte_carlo_aep("tests/mocks/aep_summary_dutchbay.json", n_scenarios=20, seed=1)
    assert seen["key"] == "envision_en171_6p5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
