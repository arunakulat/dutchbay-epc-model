#!/usr/bin/env python
"""Tests for the directional wind-rose OUTPUT builder (issue #742).

Display/provenance only — the rose bins met-convention wind directions into
sectors and is surfaced into the AEP-summary provenance block. It touches NO
billed quantity. These tests pin the binning against synthetic direction data
(all-north -> single sector; uniform -> even) and the fail-loud contract.
"""

from __future__ import annotations

import numpy as np
import pytest

from analytics.wind.wind_rose import ROSE_PROVENANCE_NOTE, build_wind_rose


def test_all_north_single_sector() -> None:
    """A pure-north series concentrates entirely in the North (0 deg) sector."""
    rose = build_wind_rose([0.0, 0.0, 0.0, 0.0], n_sectors=12)
    assert rose["n_sectors"] == 12
    assert rose["sector_width_deg"] == 30.0
    assert rose["n_samples"] == 4
    assert rose["frequency"][0] == 1.0
    assert sum(rose["frequency"][1:]) == 0.0
    assert rose["prevailing_sector_deg"] == 0.0
    assert pytest.approx(sum(rose["frequency"]), abs=1e-9) == 1.0


def test_north_sector_straddles_zero() -> None:
    """The North sector is CENTRED on 0 deg, so 355 and 5 deg both land in it."""
    rose = build_wind_rose([355.0, 5.0, 359.9, 0.1], n_sectors=12)
    assert rose["count"][0] == 4
    assert rose["frequency"][0] == 1.0


def test_uniform_directions_even_frequency() -> None:
    """A uniform sweep over the compass gives an even 1/n across all sectors."""
    rose = build_wind_rose(list(np.arange(0.0, 360.0, 1.0)), n_sectors=12)
    freqs = rose["frequency"]
    assert len(freqs) == 12
    expected = 1.0 / 12.0
    for f in freqs:
        assert f == pytest.approx(expected, abs=1e-3)
    # Display frequencies are rounded to 6 dp, so they sum to ~1 (not bit-exact).
    assert sum(freqs) == pytest.approx(1.0, abs=1e-4)


def test_prevailing_sector_is_most_frequent() -> None:
    """The prevailing sector is the centre bearing of the modal sector (SW ~ 225)."""
    directions = [225.0] * 100 + [40.0] * 10  # SW-dominant
    rose = build_wind_rose(directions, n_sectors=8)
    assert rose["prevailing_sector_deg"] == 225.0
    idx = rose["sector_deg"].index(225.0)
    assert rose["sector_label"][idx] == "SW"


def test_compass_labels_for_16_sectors() -> None:
    """16-sector centres map onto the full 16-point compass labels."""
    rose = build_wind_rose([0.0], n_sectors=16)
    assert rose["sector_label"] == list(
        (
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        )
    )


def test_non_compass_sector_count_has_blank_labels() -> None:
    """A 12-sector rose does not align with the 16-point compass -> blank labels."""
    rose = build_wind_rose([0.0], n_sectors=12)
    assert all(label == "" for label in rose["sector_label"])


def test_wraps_out_of_range_directions() -> None:
    """Directions outside [0, 360) are wrapped (e.g. 720 == 0, -10 == 350)."""
    rose = build_wind_rose([720.0, -10.0], n_sectors=12)
    assert rose["n_samples"] == 2
    # 720 -> 0 (North sector), -10 -> 350 (also within the North sector +/-15)
    assert rose["count"][0] == 2


def test_nans_dropped() -> None:
    """NaN directions are filtered before binning."""
    rose = build_wind_rose([0.0, float("nan"), 180.0], n_sectors=12)
    assert rose["n_samples"] == 2


def test_provenance_note_stamped() -> None:
    """The honest single-cell ERA5 caveat is always present."""
    rose = build_wind_rose([90.0], n_sectors=8)
    assert rose["provenance_note"] == ROSE_PROVENANCE_NOTE
    assert "single grid-cell" in rose["provenance_note"]
    assert "not directionally mast-validated" in rose["provenance_note"]


def test_empty_series_fails_loud() -> None:
    """An all-NaN / empty series raises rather than emitting an empty rose."""
    with pytest.raises(ValueError, match="at least one non-NaN"):
        build_wind_rose([float("nan")], n_sectors=12)


def test_bad_sector_count_fails_loud() -> None:
    with pytest.raises(ValueError, match="n_sectors must be >= 1"):
        build_wind_rose([0.0], n_sectors=0)
