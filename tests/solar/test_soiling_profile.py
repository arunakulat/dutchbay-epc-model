"""Tests for solar_resource.soiling_profile (#743 — OPTIONAL time-varying soiling).

Default-off byte-identical: a scenario WITHOUT a ``resource.solar.soiling_profile`` block runs
the flat-soiling loss chain exactly as before. WITH the block, the producer substitutes the
profile's energy-weighted effective soiling — a change confined to the producer/loss path.
"""

from __future__ import annotations

import pytest

from solar_resource.soiling_profile import (
    SoilingProfile,
    compute_soiling_profile_effective_pct,
    soiling_profile_from_config,
)


def test_none_config_returns_none() -> None:
    assert soiling_profile_from_config(None) is None


def test_effective_soiling_mean_over_cycle() -> None:
    # floor 0, rate 0.2%/day, 5-day wash: mean of 0.0,0.2,0.4,0.6,0.8 = 0.4
    p = SoilingProfile(accumulation_rate_pct_per_day=0.2, wash_interval_days=5)
    assert p.effective_soiling_pct() == pytest.approx(0.4)
    assert compute_soiling_profile_effective_pct(p) == pytest.approx(0.4)


def test_clean_floor_offsets_the_mean() -> None:
    p = SoilingProfile(
        accumulation_rate_pct_per_day=0.2, wash_interval_days=5, clean_floor_pct=1.0
    )
    assert p.effective_soiling_pct() == pytest.approx(1.4)


def test_saturation_cap_limits_accumulation() -> None:
    # rate 1%/day, 10-day wash, cap 3% -> days 0..3 accumulate (0,1,2,3), days 4..9 capped at 3
    p = SoilingProfile(
        accumulation_rate_pct_per_day=1.0,
        wash_interval_days=10,
        saturation_cap_pct=3.0,
    )
    expected = (0 + 1 + 2 + 3 + 3 + 3 + 3 + 3 + 3 + 3) / 10.0
    assert p.effective_soiling_pct() == pytest.approx(expected)


def test_config_roundtrip_and_optional_fields() -> None:
    p = soiling_profile_from_config(
        {
            "accumulation_rate_pct_per_day": 0.15,
            "wash_interval_days": 20,
            "clean_floor_pct": 0.5,
            "saturation_cap_pct": 6.0,
        }
    )
    assert p is not None
    assert p.wash_interval_days == 20
    assert p.saturation_cap_pct == 6.0


@pytest.mark.parametrize(
    "block,exc",
    [
        (
            {"accumulation_rate_pct_per_day": 0.2},
            KeyError,
        ),  # missing wash_interval_days
        ({"wash_interval_days": 10}, KeyError),  # missing rate
        (
            {"accumulaton_rate_pct_per_day": 0.2, "wash_interval_days": 10},
            KeyError,
        ),  # typo'd key
    ],
)
def test_bad_config_raises(block: dict, exc: type[Exception]) -> None:
    with pytest.raises(exc):
        soiling_profile_from_config(block)


def test_non_mapping_raises() -> None:
    with pytest.raises(TypeError):
        soiling_profile_from_config([1, 2, 3])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"accumulation_rate_pct_per_day": -0.1, "wash_interval_days": 10},
        {"accumulation_rate_pct_per_day": 0.1, "wash_interval_days": 0},
        {
            "accumulation_rate_pct_per_day": 0.1,
            "wash_interval_days": 10,
            "clean_floor_pct": -1.0,
        },
        {
            "accumulation_rate_pct_per_day": 0.1,
            "wash_interval_days": 10,
            "clean_floor_pct": 5.0,
            "saturation_cap_pct": 2.0,  # cap below floor
        },
    ],
)
def test_validation_rejects_bad_values(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        SoilingProfile(**kwargs)


# --- byte-identity + producer-path integration (pvlib-gated) ----------------

_BASE = dict(
    latitude=8.27,
    longitude=79.75,
    timezone="Asia/Colombo",
    altitude_m=5.0,
    annual_ghi_kwh_m2=2000.0,
    dc_capacity_mw=50.0,
    tilt_deg=8.0,
    azimuth_deg=180.0,
    dc_ac_ratio=1.2,
    system_loss_pct=14.0,
)


def test_config_accepts_and_preflights_the_profile() -> None:
    """A SolarResourceConfig with a valid profile builds; a typo'd one fails at construction."""
    from solar_resource.pv_producer import SolarResourceConfig

    ok = SolarResourceConfig(
        **_BASE,
        soiling_profile={
            "accumulation_rate_pct_per_day": 0.2,
            "wash_interval_days": 15,
        },
    )
    assert ok.soiling_profile is not None
    with pytest.raises(KeyError):
        SolarResourceConfig(
            **_BASE,
            soiling_profile={
                "accumulaton_rate_pct_per_day": 0.2,
                "wash_interval_days": 15,
            },
        )


def test_absent_profile_is_byte_identical_and_present_changes_producer_path() -> None:
    """No profile -> byte-identical CF; a profile -> CF changes, confined to the producer."""
    pytest.importorskip("pvlib")
    from solar_resource.pv_producer import SolarResourceConfig, compute_solar_aep

    r_absent = compute_solar_aep(SolarResourceConfig(**_BASE))
    r_absent_again = compute_solar_aep(SolarResourceConfig(**_BASE))
    # Reproducible byte-identity for the default (no-profile) path.
    assert r_absent.capacity_factor == r_absent_again.capacity_factor

    # Net soiling out of the flat stack (14 -> 12) and add a profile whose effective soiling
    # differs from the 2% flat baseline -> the producer CF moves.
    profiled = dict(_BASE, system_loss_pct=12.0)
    r_profile = compute_solar_aep(
        SolarResourceConfig(
            **profiled,
            soiling_profile={
                "accumulation_rate_pct_per_day": 0.2,
                "wash_interval_days": 15,
                "clean_floor_pct": 0.5,
            },
        )
    )
    assert r_profile.capacity_factor != r_absent.capacity_factor
