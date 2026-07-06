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

from analytics.wind.wind_rose import (
    DEFAULT_CALM_LIMIT_MS,
    ROSE_PROVENANCE_NOTE,
    build_wind_rose,
)


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


# ---------------------------------------------------------------------------
# Issue #826 — optional wind-speed enrichment (KPI-neutral, additive).
# ---------------------------------------------------------------------------


def _legacy_direction_only_rose(
    wd_series: list[float], n_sectors: int
) -> dict[str, object]:
    """Reference copy of the pre-#826 direction-only algorithm.

    This is an intentional, frozen duplicate of the original ``build_wind_rose``
    body (verbatim binning) so the byte-identity test does not depend on hand-
    counting: if the refactor ever changes the direction-only binning, the two
    dicts diverge and the test fails.
    """
    compass_16 = (
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

    def _label(center_deg: float) -> str:
        if n_sectors in (8, 16):
            step = 16 // n_sectors
            idx = int(round(center_deg / 22.5)) % 16
            if idx % step == 0:
                return compass_16[idx]
        return ""

    arr = np.asarray(list(wd_series), dtype=float)
    arr = arr[~np.isnan(arr)]
    n_samples = int(arr.size)
    width = 360.0 / n_sectors
    wrapped = np.mod(arr, 360.0)
    idx = np.floor(np.mod(wrapped + width / 2.0, 360.0) / width).astype(int)
    idx = np.clip(idx, 0, n_sectors - 1)
    counts = np.bincount(idx, minlength=n_sectors)[:n_sectors].astype(int)
    freq = counts.astype(float) / float(n_samples)
    centers = [round(i * width, 4) for i in range(n_sectors)]
    return {
        "n_sectors": int(n_sectors),
        "sector_width_deg": round(width, 4),
        "sector_deg": centers,
        "sector_label": [_label(c) for c in centers],
        "count": [int(c) for c in counts.tolist()],
        "frequency": [round(f, 6) for f in freq.tolist()],
        "n_samples": n_samples,
        "prevailing_sector_deg": centers[int(np.argmax(counts))],
        "provenance_note": ROSE_PROVENANCE_NOTE,
    }


def test_direction_only_path_is_byte_identical_to_before() -> None:
    """With NO speed series, the output is EXACTLY the pre-#826 direction-only rose.

    Guards backward-compatibility: the enrichment keys must be entirely absent and
    the whole dict must equal the frozen reference algorithm, across several inputs
    and sector counts (8 / 12 / 16).
    """
    cases = [
        ([0.0, 45.0, 90.0, 180.0, 270.0, 359.0, float("nan"), 720.0], 12),
        (list(np.arange(0.0, 360.0, 1.0)), 12),
        ([225.0] * 100 + [40.0] * 10, 8),
        ([355.0, 5.0, 359.9, 0.1, -10.0], 16),
    ]
    for directions, n_sectors in cases:
        rose = build_wind_rose(directions, n_sectors=n_sectors)
        # No #826 enrichment key leaks in on the direction-only path.
        for enrichment_key in (
            "calm_limit_ms",
            "n_calm",
            "mean_speed_ms",
            "energy_frequency",
            "sector_weibull",
        ):
            assert enrichment_key not in rose
        # Whole-dict byte-identity against the frozen legacy algorithm.
        assert rose == _legacy_direction_only_rose(directions, n_sectors)


def test_default_calm_limit_is_two_metres_per_second() -> None:
    """The disclosed calm convention is 2.0 m/s (independent of any windrose lib)."""
    assert DEFAULT_CALM_LIMIT_MS == 2.0


def test_calm_samples_excluded_before_binning() -> None:
    """Samples at/below the calm limit are dropped (fewer n_samples, counted)."""
    directions = [0.0, 0.0, 0.0, 0.0]
    speeds = [1.0, 2.0, 8.0, 9.0]  # first two are calm (<= 2.0)
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds)

    assert rose["n_samples"] == 2  # only the two non-calm samples survive
    assert rose["n_calm"] == 2
    assert rose["calm_limit_ms"] == 2.0
    # Both survivors are due North.
    assert rose["count"][0] == 2
    assert rose["mean_speed_ms"][0] == pytest.approx(8.5, abs=1e-9)


def test_custom_calm_limit_respected() -> None:
    """A caller-supplied calm_limit overrides the default threshold."""
    directions = [0.0, 0.0, 0.0]
    speeds = [3.0, 5.0, 7.0]
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds, calm_limit=4.0)
    assert rose["calm_limit_ms"] == 4.0
    assert rose["n_calm"] == 1  # the 3.0 m/s sample is now calm
    assert rose["n_samples"] == 2


def test_mean_speed_per_sector() -> None:
    """Per-sector mean speed is reported; empty sectors report 0.0."""
    # North gets {10, 20}; East (90) gets {6}; all else empty.
    directions = [0.0, 0.0, 90.0]
    speeds = [10.0, 20.0, 6.0]
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds)
    assert rose["mean_speed_ms"][0] == pytest.approx(15.0, abs=1e-9)
    # 90 deg -> sector 3 for a 12-sector rose (30 deg width).
    east_idx = rose["sector_deg"].index(90.0)
    assert rose["mean_speed_ms"][east_idx] == pytest.approx(6.0, abs=1e-9)
    # An empty sector reports 0.0 mean speed and 0.0 energy share.
    empty_idx = rose["sector_deg"].index(180.0)
    assert rose["mean_speed_ms"][empty_idx] == 0.0
    assert rose["energy_frequency"][empty_idx] == 0.0


def test_energy_rose_differs_from_frequency_and_sums_to_one() -> None:
    """The energy rose reweights sectors by f*<v^3> and normalises to ~1.

    Two equally-frequent sectors with very different speeds must have equal
    FREQUENCY but unequal ENERGY frequency — the high-speed sector dominating.
    """
    directions = [0.0] * 50 + [90.0] * 50  # equal frequency N vs E
    speeds = [4.0] * 50 + [12.0] * 50  # E is 3x faster -> ~27x the energy flux
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds)

    north_idx = rose["sector_deg"].index(0.0)
    east_idx = rose["sector_deg"].index(90.0)

    # Frequencies are equal...
    assert rose["frequency"][north_idx] == pytest.approx(
        rose["frequency"][east_idx], abs=1e-9
    )
    # ...but energy frequencies are NOT — the fast (east) sector dominates.
    assert rose["energy_frequency"][east_idx] > rose["energy_frequency"][north_idx]
    # Energy rose is a proper distribution over sectors (~1 after 6dp rounding).
    assert sum(rose["energy_frequency"]) == pytest.approx(1.0, abs=1e-5)

    # Analytic check: energy weight ratio = (12^3)/(4^3) = 27, so energy freq ~ 27/28.
    expected_east = (12.0**3) / (12.0**3 + 4.0**3)
    assert rose["energy_frequency"][east_idx] == pytest.approx(expected_east, abs=1e-4)


def test_energy_rose_equals_frequency_when_speeds_uniform() -> None:
    """When every sector shares one speed, the energy rose collapses to frequency."""
    rng = np.random.default_rng(7)
    directions = list(rng.uniform(0.0, 360.0, size=400))
    speeds = [7.5] * len(directions)  # uniform speed everywhere
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds)
    for f_freq, f_energy in zip(
        rose["frequency"], rose["energy_frequency"], strict=True
    ):
        assert f_energy == pytest.approx(f_freq, abs=1e-6)


def test_sectorwise_weibull_returns_per_sector_ak() -> None:
    """A well-populated sector yields a plausible per-sector Weibull (A, k)."""
    rng = np.random.default_rng(42)
    # 500 Weibull-distributed speeds all coming from due North.
    speeds = rng.weibull(2.2, size=500) * 8.0  # k~2.2, A~8
    directions = [0.0] * len(speeds)
    rose = build_wind_rose(directions, n_sectors=12, ws_series=list(speeds))

    north_fit = rose["sector_weibull"][0]
    assert north_fit is not None
    assert set(north_fit.keys()) == {"weibull_a", "weibull_k"}
    # Fit should recover the generating params to a loose tolerance.
    assert north_fit["weibull_a"] == pytest.approx(8.0, rel=0.2)
    assert north_fit["weibull_k"] == pytest.approx(2.2, rel=0.25)
    # Empty sectors report None rather than crashing.
    assert rose["sector_weibull"][6] is None


def test_sparse_sector_weibull_is_none() -> None:
    """A sector with fewer than ~10 points reports None (no unstable MLE)."""
    # 5 north samples (sparse) + 40 east samples (well-populated).
    directions = [0.0] * 5 + [90.0] * 40
    speeds = [8.0 + i * 0.1 for i in range(5)] + [6.0 + (i % 7) for i in range(40)]
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds)
    north_idx = rose["sector_deg"].index(0.0)
    east_idx = rose["sector_deg"].index(90.0)
    assert rose["sector_weibull"][north_idx] is None  # too sparse
    assert rose["sector_weibull"][east_idx] is not None  # enough points


def test_length_mismatch_fails_loud() -> None:
    """A speed series of a different length than the directions raises."""
    with pytest.raises(ValueError, match="same length"):
        build_wind_rose([0.0, 90.0, 180.0], n_sectors=12, ws_series=[5.0, 6.0])


def test_all_calm_series_fails_loud() -> None:
    """If every sample is calm, nothing survives -> the empty-rose guard fires."""
    with pytest.raises(ValueError, match="at least one non-NaN"):
        build_wind_rose([0.0, 90.0], n_sectors=12, ws_series=[0.5, 1.0])


def test_speed_nans_dropped_alongside_direction() -> None:
    """A NaN speed drops its sample even if the direction is valid."""
    directions = [0.0, 90.0, 180.0]
    speeds = [8.0, float("nan"), 9.0]
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds)
    assert rose["n_samples"] == 2  # the NaN-speed middle sample is gone
    assert rose["n_calm"] == 0  # a NaN speed is not counted as calm
