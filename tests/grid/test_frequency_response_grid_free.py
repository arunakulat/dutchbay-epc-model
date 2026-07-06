"""Grid-FREE coverage for the D7 frequency-response de-load headroom sizing (#883).

These tests import NO grid library and are NOT marked ``grid``, so they run in the default
``-m 'not grid'`` coverage lane and carry the real coverage for
:mod:`analytics.grid.frequency_response` (which is pure Python — there is no optional-dep
path in that module). They exercise every helper + the sizing function, including their
ValueError branches and the SCR-independent droop/energy math.
"""

from __future__ import annotations

import pytest

from analytics.grid.frequency_response import (
    DEFAULT_DROOP,
    DEFAULT_FREQ_BAND_HZ,
    DEFAULT_RESPONSE_BAND_HZ,
    HOURS_PER_YEAR,
    NOMINAL_FREQ_HZ,
    FrequencyResponseHeadroom,
    droop_reserve_fraction,
    freq_band_from_gridcode,
    size_frequency_response_headroom,
)

# --------------------------------------------------------------------------- freq band


def test_freq_band_from_gridcode_none_defaults() -> None:
    lo, hi, source = freq_band_from_gridcode(None)
    assert (lo, hi) == DEFAULT_FREQ_BAND_HZ
    assert "defaults" in source


def test_freq_band_from_freq_ride_through_continuous() -> None:
    gc = {"freq_ride_through": {"continuous_hz": [47.0, 52.0]}}
    lo, hi, source = freq_band_from_gridcode(gc)
    assert (lo, hi) == (47.0, 52.0)
    assert "freq_ride_through" in source


def test_freq_band_from_freq_continuous_hz() -> None:
    lo, hi, source = freq_band_from_gridcode({"freq_continuous_hz": [47.6, 51.4]})
    assert (lo, hi) == (47.6, 51.4)
    assert "freq_continuous_hz" in source


def test_freq_band_from_trip_table_longest_clearing() -> None:
    # The continuous edge in each direction is the setpoint with the LONGEST clearing time.
    gc = {
        "freq_trip_hz": {
            "underfrequency": [[47.5, 1800.0], [47.0, 0.1]],
            "overfrequency": [[51.5, 1800.0], [52.0, 0.1]],
        }
    }
    lo, hi, source = freq_band_from_gridcode(gc)
    assert (lo, hi) == (47.5, 51.5)
    assert "freq_trip_hz" in source


def test_freq_band_continuous_hz_ignored_when_not_increasing() -> None:
    # A degenerate [hi, lo] pair is ignored → falls through to defaults.
    lo, hi, source = freq_band_from_gridcode(
        {"freq_ride_through": {"continuous_hz": [52.0, 47.0]}}
    )
    assert (lo, hi) == DEFAULT_FREQ_BAND_HZ


def test_freq_band_present_gridcode_no_band() -> None:
    lo, hi, source = freq_band_from_gridcode({"pf_range": [-0.95, 0.95]})
    assert (lo, hi) == DEFAULT_FREQ_BAND_HZ
    assert "no frequency band" in source


def test_freq_band_ignores_malformed_trip_rows() -> None:
    gc = {
        "freq_trip_hz": {"overfrequency": [["x", 1.0], [51.2]], "underfrequency": "bad"}
    }
    lo, hi, source = freq_band_from_gridcode(gc)
    # No valid rows → both directions keep defaults.
    assert (lo, hi) == DEFAULT_FREQ_BAND_HZ


# --------------------------------------------------------------------------- droop frac


def test_droop_reserve_fraction_capped_at_response_band() -> None:
    # A far trip edge (51.5) is CAPPED at the response band (0.2 Hz beyond deadband):
    # frac = (0.2/50)/0.04 = 0.1 (10 %), NOT the unphysical (1.5-0.15)/50/0.04.
    frac = droop_reserve_fraction(over_freq_edge_hz=51.5, droop=0.04)
    assert frac == pytest.approx(0.1)


def test_droop_reserve_fraction_small_excursion_not_capped() -> None:
    # Excursion (0.1 Hz beyond deadband) below the response band → not capped.
    frac = droop_reserve_fraction(
        over_freq_edge_hz=50.25, droop=0.04, deadband_hz=0.15, response_band_hz=0.2
    )
    assert frac == pytest.approx((0.1 / 50.0) / 0.04)


def test_droop_reserve_fraction_within_deadband_is_zero() -> None:
    # An over-frequency edge inside the dead-band demands no de-load.
    assert (
        droop_reserve_fraction(over_freq_edge_hz=50.1, droop=0.04, deadband_hz=0.15)
        == 0.0
    )


def test_droop_reserve_fraction_clamped_to_one() -> None:
    # A huge response band + tiny droop saturates the reserve at 100 %.
    frac = droop_reserve_fraction(
        over_freq_edge_hz=55.0, droop=0.001, deadband_hz=0.0, response_band_hz=10.0
    )
    assert frac == 1.0


@pytest.mark.parametrize("bad_droop", [0.0, -0.04])
def test_droop_reserve_fraction_bad_droop_raises(bad_droop: float) -> None:
    with pytest.raises(ValueError, match="droop must be > 0"):
        droop_reserve_fraction(over_freq_edge_hz=51.5, droop=bad_droop)


def test_droop_reserve_fraction_bad_nominal_raises() -> None:
    with pytest.raises(ValueError, match="nominal_hz must be > 0"):
        droop_reserve_fraction(over_freq_edge_hz=51.5, droop=0.04, nominal_hz=0.0)


# --------------------------------------------------------------------------- sizing


def test_size_headroom_droop_default_and_energy() -> None:
    hr = size_frequency_response_headroom(
        rated_mw=150.0,
        gridcode={"freq_ride_through": {"continuous_hz": [47.5, 51.5], "droop": 0.04}},
        capacity_factor=0.35,
        droop=0.04,
    )
    assert isinstance(hr, FrequencyResponseHeadroom)
    # 10 % reserve on 150 MW = 15 MW; energy = 15 * 0.35 * 8760.
    assert hr.reserve_fraction == pytest.approx(0.1)
    assert hr.headroom_mw == pytest.approx(15.0)
    assert hr.energy_foregone_mwh_yr == pytest.approx(15.0 * 0.35 * HOURS_PER_YEAR)
    assert hr.over_freq_edge_hz == 51.5
    assert hr.droop == 0.04


def test_size_headroom_mandated_reserve_dominates() -> None:
    # A mandated 20 % reserve overrides the 10 % droop-implied figure.
    hr = size_frequency_response_headroom(
        rated_mw=100.0,
        gridcode={"freq_ride_through": {"continuous_hz": [47.5, 51.5]}},
        capacity_factor=0.4,
        droop=0.04,
        mandated_reserve_fraction=0.2,
    )
    assert hr.reserve_fraction == pytest.approx(0.2)
    assert hr.headroom_mw == pytest.approx(20.0)


def test_size_headroom_droop_none_uses_default() -> None:
    hr = size_frequency_response_headroom(
        rated_mw=100.0, gridcode=None, capacity_factor=0.3, droop=None
    )
    assert hr.droop == DEFAULT_DROOP
    assert hr.over_freq_edge_hz == DEFAULT_FREQ_BAND_HZ[1]


@pytest.mark.parametrize("bad_rated", [0.0, -1.0])
def test_size_headroom_bad_rated_raises(bad_rated: float) -> None:
    with pytest.raises(ValueError, match="rated_mw must be > 0"):
        size_frequency_response_headroom(
            rated_mw=bad_rated, gridcode=None, capacity_factor=0.3
        )


@pytest.mark.parametrize("bad_cf", [-0.1, 1.5])
def test_size_headroom_bad_cf_raises(bad_cf: float) -> None:
    with pytest.raises(ValueError, match="capacity_factor must be in"):
        size_frequency_response_headroom(
            rated_mw=100.0, gridcode=None, capacity_factor=bad_cf
        )


@pytest.mark.parametrize("bad_reserve", [-0.1, 1.5])
def test_size_headroom_bad_mandated_reserve_raises(bad_reserve: float) -> None:
    with pytest.raises(ValueError, match="mandated_reserve_fraction must be in"):
        size_frequency_response_headroom(
            rated_mw=100.0,
            gridcode=None,
            capacity_factor=0.3,
            mandated_reserve_fraction=bad_reserve,
        )


def test_module_constants() -> None:
    assert NOMINAL_FREQ_HZ == 50.0
    assert DEFAULT_RESPONSE_BAND_HZ == 0.2
    assert HOURS_PER_YEAR == 8760.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
