"""RIX / ΔRIX terrain-ruggedness diagnostic tests (issue #831).

Fully synthetic slope arrays (degrees): a flat plane -> RIX 0, a steep ridge -> RIX high,
a mixed field -> RIX between; plus the ΔRIX arithmetic and the >threshold disclosure flag.
No network, no real tiles, no optional dependency for the core (the raster export test is
CASPER-skipped when the ``[gis]`` extra is absent).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from analytics.gis.rix import (
    DEFAULT_CRITICAL_SLOPE,
    DEFAULT_DELTA_RIX_THRESHOLD,
    RixDisclosure,
    RixReport,
    assess_delta_rix,
    build_rix_report,
    critical_slope_ratio_to_degrees,
    delta_rix,
    export_rix_raster,
    rix_at_point,
    rix_field,
)

# The default 0.3 ratio critical slope is ~16.7 deg; steep test cells sit above it, gentle
# ones below it.
CRIT_DEG = critical_slope_ratio_to_degrees(DEFAULT_CRITICAL_SLOPE)  # ~16.699 deg
STEEP_DEG = 30.0  # > CRIT_DEG -> counts as "rugged"
GENTLE_DEG = 5.0  # < CRIT_DEG -> not rugged


def test_critical_slope_ratio_to_degrees():
    """The conventional 0.3 critical slope is atan(0.3) ~ 16.7 deg (~17 deg)."""
    assert math.isclose(critical_slope_ratio_to_degrees(0.3), 16.699, abs_tol=1e-3)
    # Round-trips a degree value: tan(deg) is the ratio.
    assert math.isclose(critical_slope_ratio_to_degrees(1.0), 45.0, abs_tol=1e-9)


def test_flat_plane_rix_zero():
    """A perfectly flat slope raster (0 deg everywhere) -> RIX 0."""
    slope = np.zeros((21, 21), dtype="float32")
    rix = rix_at_point(slope, (10, 10), radius=8.0)
    assert rix == 0.0


def test_gentle_plane_below_critical_rix_zero():
    """A uniformly GENTLE slope (below the critical slope) still gives RIX 0."""
    slope = np.full((21, 21), GENTLE_DEG, dtype="float32")
    rix = rix_at_point(slope, (10, 10), radius=8.0)
    assert rix == 0.0


def test_steep_ridge_rix_high():
    """A slope raster that is everywhere STEEP -> RIX 1.0 (whole neighbourhood rugged)."""
    slope = np.full((21, 21), STEEP_DEG, dtype="float32")
    rix = rix_at_point(slope, (10, 10), radius=8.0)
    assert rix == 1.0


def test_mixed_field_rix_between():
    """A half-steep / half-gentle field -> RIX strictly between 0 and 1.

    Left columns steep, right columns gentle; the RIX window centred at the middle spans
    both, so the steep FRACTION is ~0.5.
    """
    slope = np.full((21, 21), GENTLE_DEG, dtype="float32")
    slope[:, :10] = STEEP_DEG  # left half steep
    slope[:, 10] = GENTLE_DEG  # center column gentle -> clean split around col 10
    rix = rix_at_point(slope, (10, 10), radius=8.0)
    assert 0.0 < rix < 1.0
    # Symmetric window split roughly in half -> close to 0.5.
    assert abs(rix - 0.5) < 0.1


def test_rix_at_point_matches_manual_count():
    """RIX equals the exact steep-fraction over the disc, verified by an independent count."""
    rng = np.random.default_rng(831)
    slope = rng.uniform(0.0, 40.0, size=(15, 15)).astype("float32")
    center = (7, 7)
    radius = 5.0
    rix = rix_at_point(slope, center, radius=radius)

    rows = np.arange(15)[:, None]
    cols = np.arange(15)[None, :]
    dist = np.hypot(rows - 7, cols - 7)
    window = dist <= radius
    steep = window & (slope > CRIT_DEG)
    expected = steep.sum() / window.sum()
    assert math.isclose(rix, expected, abs_tol=1e-12)


def test_rix_radius_shrinks_window():
    """A tiny radius sees only the local cell(s); a steep isolated cell reads RIX 1.0."""
    slope = np.full((11, 11), GENTLE_DEG, dtype="float32")
    slope[5, 5] = STEEP_DEG
    # radius 0.5 -> only the center cell is in-window.
    assert rix_at_point(slope, (5, 5), radius=0.5) == 1.0
    # A larger radius dilutes it with the gentle surround.
    assert rix_at_point(slope, (5, 5), radius=4.0) < 0.1


def test_rix_excludes_nan_nodata():
    """NaN (DEM nodata) cells are excluded from BOTH numerator and denominator."""
    slope = np.full((11, 11), STEEP_DEG, dtype="float32")
    slope[0:11, 0:5] = np.nan  # half the grid is nodata
    rix = rix_at_point(slope, (5, 8), radius=20.0)  # window covers whole grid
    # Only the valid (steep) half counts -> RIX 1.0, not diluted to 0.5 by the NaNs.
    assert rix == 1.0


def test_rix_empty_window_is_nan():
    """A center off the grid with a radius reaching no cell -> nan (honest undefined)."""
    slope = np.zeros((5, 5), dtype="float32")
    rix = rix_at_point(slope, (100.0, 100.0), radius=1.0)
    assert math.isnan(rix)


def test_rix_pixel_size_scales_radius():
    """A metre pixel_size lets a metre radius address a coarser grid correctly."""
    slope = np.full((11, 11), GENTLE_DEG, dtype="float32")
    slope[5, 5] = STEEP_DEG
    # 30 m pixels: a 45 m radius reaches the 8 immediate neighbours (1 pixel = 30 m,
    # diagonal = ~42 m < 45 m) but not 2 pixels out (60 m).
    rix = rix_at_point(slope, (5, 5), radius=45.0, pixel_size=(30.0, 30.0))
    # 1 steep of 9 in-window cells.
    assert math.isclose(rix, 1.0 / 9.0, abs_tol=1e-9)


def test_rix_degree_threshold_passthrough():
    """critical_slope_is_degrees compares the raster directly against a degree threshold."""
    slope = np.full((11, 11), 20.0, dtype="float32")  # 20 deg everywhere
    # Threshold 25 deg -> nothing steeper -> RIX 0.
    assert (
        rix_at_point(
            slope,
            (5, 5),
            radius=4.0,
            critical_slope=25.0,
            critical_slope_is_degrees=True,
        )
        == 0.0
    )
    # Threshold 15 deg -> everything steeper -> RIX 1.
    assert (
        rix_at_point(
            slope,
            (5, 5),
            radius=4.0,
            critical_slope=15.0,
            critical_slope_is_degrees=True,
        )
        == 1.0
    )


def test_rix_rejects_non_2d():
    with pytest.raises(ValueError):
        rix_at_point(np.zeros((2, 2, 2)), (0, 0))


def test_rix_rejects_nonpositive_radius():
    with pytest.raises(ValueError):
        rix_at_point(np.zeros((5, 5)), (2, 2), radius=0.0)


def test_delta_rix_arithmetic():
    """ΔRIX = RIX(target) − RIX(predictor); sign follows the target."""
    assert delta_rix(0.10, 0.25) == pytest.approx(0.15)
    assert delta_rix(0.25, 0.10) == pytest.approx(-0.15)
    assert delta_rix(0.20, 0.20) == 0.0


def test_disclosure_flag_fires_above_threshold():
    """|ΔRIX| just above the 5% threshold FIRES the envelope flag."""
    d = assess_delta_rix(0.02, 0.10)  # ΔRIX = 0.08 > 0.05
    assert isinstance(d, RixDisclosure)
    assert d.delta_rix == pytest.approx(0.08)
    assert d.exceeds_threshold is True
    assert "EXCEEDS" in d.note
    assert d.threshold == DEFAULT_DELTA_RIX_THRESHOLD


def test_disclosure_flag_silent_within_threshold():
    """|ΔRIX| within the envelope does NOT fire, and the note confirms adequacy."""
    d = assess_delta_rix(0.10, 0.12)  # ΔRIX = 0.02 < 0.05
    assert d.exceeds_threshold is False
    assert "within" in d.note.lower()


def test_disclosure_flag_fires_on_negative_delta():
    """A large NEGATIVE ΔRIX (turbine flatter than the mast) still trips |ΔRIX|."""
    d = assess_delta_rix(0.20, 0.05)  # ΔRIX = -0.15, |ΔRIX| = 0.15 > 0.05
    assert d.delta_rix == pytest.approx(-0.15)
    assert d.exceeds_threshold is True


def test_disclosure_boundary_not_strictly_exceeded():
    """Exactly at the threshold is NOT '>' -> flag stays down (strict inequality)."""
    d = assess_delta_rix(0.0, DEFAULT_DELTA_RIX_THRESHOLD)  # ΔRIX == threshold
    assert d.exceeds_threshold is False


def test_custom_threshold_respected():
    """A config-supplied threshold overrides the 5% default."""
    d = assess_delta_rix(0.0, 0.03, threshold=0.02)  # 0.03 > 0.02
    assert d.exceeds_threshold is True


def test_build_rix_report_flat_all_within_envelope():
    """A flat site: reference and all turbines read RIX 0 -> nothing outside the envelope."""
    slope = np.zeros((21, 21), dtype="float32")
    report = build_rix_report(
        slope,
        reference=(10, 10),
        turbines=[(3, 3), (17, 17), (10, 3)],
        turbine_labels=["WTG01", "WTG02", "WTG03"],
        radius=6.0,
    )
    assert isinstance(report, RixReport)
    assert report.reference_rix == 0.0
    assert len(report.disclosures) == 3
    assert report.any_exceeds is False
    assert all(d.delta_rix == 0.0 for d in report.disclosures)
    assert report.disclosures[0].target_label == "WTG01"
    assert math.isclose(report.critical_slope_deg, CRIT_DEG, abs_tol=1e-6)


def test_build_rix_report_ridge_turbine_trips_envelope():
    """A turbine parked on a steep ridge, mast on a flat plain -> its ΔRIX trips the flag."""
    slope = np.zeros((41, 41), dtype="float32")
    # A steep ridge band in the north (rows 0-8), turbine there; mast on the flat south.
    slope[0:9, :] = STEEP_DEG
    report = build_rix_report(
        slope,
        reference=(35, 20),  # flat plain -> RIX ~0
        turbines=[(4, 20), (35, 10)],  # ridge turbine, plain turbine
        turbine_labels=["RIDGE", "PLAIN"],
        radius=5.0,
    )
    ridge = report.disclosures[0]
    plain = report.disclosures[1]
    assert ridge.rix_target > 0.5  # deep in the ridge band
    assert ridge.exceeds_threshold is True
    assert plain.exceeds_threshold is False
    assert report.any_exceeds is True
    # The report dict is JSON-friendly and carries the roll-up flag.
    d = report.as_dict()
    assert d["any_exceeds_threshold"] is True
    assert len(d["disclosures"]) == 2


def test_rix_field_shape_and_bounds():
    """rix_field returns a same-shape raster in [0, 1]; flat -> all zeros."""
    slope = np.zeros((9, 9), dtype="float32")
    field_arr = rix_field(slope, radius=3.0)
    assert field_arr.shape == (9, 9)
    assert np.all(field_arr == 0.0)

    slope2 = np.full((9, 9), STEEP_DEG, dtype="float32")
    field2 = rix_field(slope2, radius=3.0)
    assert np.all(field2 == 1.0)


def test_rix_field_mixed_gradient_monotone():
    """A steep-north / gentle-south field: RIX is higher in the north than the south."""
    slope = np.full((21, 21), GENTLE_DEG, dtype="float32")
    slope[0:10, :] = STEEP_DEG
    field_arr = rix_field(slope, radius=4.0)
    assert field_arr[2, 10] > field_arr[18, 10]


def test_export_rix_raster_roundtrip(tmp_path):
    """OPTIONAL export: a RIX GeoTIFF + prov sidecar round-trips (CASPER-skipped w/o gis)."""
    rasterio = pytest.importorskip("rasterio")
    import json
    from pathlib import Path

    slope = np.full((11, 11), GENTLE_DEG, dtype="float32")
    slope[0:5, :] = STEEP_DEG
    bbox = (79.40, 7.90, 79.46, 7.96)
    out = tmp_path / "rix.tif"
    path = export_rix_raster(slope, bbox, str(out), radius=3.0)

    assert Path(path).exists()
    with rasterio.open(path) as src:
        assert src.shape == (11, 11)
        data = src.read(1)
    assert np.nanmin(data) >= 0.0
    assert np.nanmax(data) <= 1.0

    prov = json.loads(Path(f"{path}.prov.json").read_text())
    assert prov["variable"] == "rix"
    assert prov["method"] == "ruggedness_index_fraction_steeper_than_critical_slope"
    assert prov["critical_slope_ratio"] == DEFAULT_CRITICAL_SLOPE
    assert math.isclose(prov["critical_slope_deg"], CRIT_DEG, abs_tol=1e-6)
    assert prov["delta_rix_threshold"] == DEFAULT_DELTA_RIX_THRESHOLD
