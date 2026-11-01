"""Tests for analytics.gis.shadow_flicker (Blue Whale siting screen).

Every calculation is checked against an oracle written independently of the module:

* shadow geometry against closed forms for a rotor disc facing the sun: the tower-base
  elevation threshold ``acos(R / H)``, and the ground-shadow ellipse (half-width ``R``
  across the sun's azimuth, half-length ``R / sin(elevation)`` along it);
* the pvlib sun path against the solar-noon elevation at the equinox, ``90 - |lat - decl|``;
* the coastal placement against the closed form for a straight coast and a hand-written
  point-to-segment distance on the committed coastline;
* the lot against a geodesic area from ``pyproj.Geod`` (Karney's algorithm, not the
  transverse Mercator frame the module uses);
* the tip-height setback against the closed-form area of a disc outside a square.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pytest

pytest.importorskip("shapely")  # CASPER: the [gis] extra
pytest.importorskip("pyproj")

from analytics.gis.shadow_flicker import (  # noqa: E402
    CoastalSetbackConfig,
    LocalFrame,
    ShadowFlickerConfig,
    SquareLot,
    SunPath,
    TipSetbackConfig,
    TurbineGeometry,
    coast_aligned_square_lot,
    coastline_lines_east_north,
    flicker_grid,
    grid_summary,
    place_at_coastal_setback,
    receptor_flicker,
    shadow_mask,
    tip_height_setback,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF = REPO_ROOT / "conf" / "blue_whale_wind_siting.yaml"
COAST = REPO_ROOT / "docs" / "blue_whale" / "osm_coastline_near_t2.geojson"
SITE = REPO_ROOT / "docs" / "blue_whale" / "site_placeholder_lot5b.geojson"
T2 = (8.2925, 79.7547)
TURBINE = TurbineGeometry(hub_height_m=130.0, rotor_diameter_m=206.0)


def _flicker_cfg(**changes: object) -> ShadowFlickerConfig:
    import yaml

    raw = dict(yaml.safe_load(CONF.read_text())["shadow_flicker"])
    raw.update(changes)
    return ShadowFlickerConfig.from_mapping(raw)


def _sun(el: List[float], az: List[float], days: List[int] | None = None) -> SunPath:
    n = len(el)
    return SunPath(
        elevation_deg=np.asarray(el, dtype=np.float64),
        azimuth_deg=np.asarray(az, dtype=np.float64),
        day_index=np.asarray(days if days is not None else [0] * n, dtype=np.int64),
        utc_hour_key=np.zeros(n, dtype=np.int64),
        step_minutes=1.0,
        n_days=1 + (max(days) if days else 0),
    )


def _mask(receptor: Tuple[float, float], sun: SunPath, z: float = 0.0) -> np.ndarray:
    return shadow_mask(
        receptor,
        turbine=TURBINE,
        receptor_height_m=z,
        max_distance_m=1e9,
        sun=sun,
    )


# ---------------------------------------------------------------------------
# Shadow geometry: closed forms
# ---------------------------------------------------------------------------
def test_tower_base_shadow_is_the_acos_elevation_threshold() -> None:
    # At the tower base the hub is straight up, so the ray to the sun passes
    # H*cos(el) from the hub: shadow iff el >= acos(R/H), whatever the azimuth.
    el = np.linspace(0.5, 89.5, 179)
    az = (np.arange(el.size) * 37.0) % 360.0
    sun = _sun(list(el), list(az))
    threshold = math.degrees(math.acos(TURBINE.rotor_radius_m / TURBINE.hub_height_m))
    np.testing.assert_array_equal(_mask((0.0, 0.0), sun), el >= threshold)


@pytest.mark.parametrize("el_deg, az_deg", [(20.0, 90.0), (35.0, 200.0), (60.0, 315.0)])
def test_ground_shadow_ellipse_matches_closed_form(
    el_deg: float, az_deg: float
) -> None:
    z = 2.0
    sun = _sun([el_deg], [az_deg])
    el, az = math.radians(el_deg), math.radians(az_deg)
    away = (-math.sin(az), -math.cos(az))  # unit vector away from the sun
    across = (math.cos(az), -math.sin(az))  # perpendicular to the sun's azimuth
    reach = (TURBINE.hub_height_m - z) / math.tan(el)
    centre = (away[0] * reach, away[1] * reach)
    r = TURBINE.rotor_radius_m
    half_len = r / math.sin(el)

    def at(along: float, side: float) -> bool:
        p = (
            centre[0] + away[0] * along + across[0] * side,
            centre[1] + away[1] * along + across[1] * side,
        )
        return bool(_mask(p, sun, z)[0])

    assert at(0.0, 0.0)
    assert at(0.0, 0.99 * r) and at(0.0, -0.99 * r)
    assert not at(0.0, 1.01 * r) and not at(0.0, -1.01 * r)
    assert at(0.99 * half_len, 0.0) and at(-0.99 * half_len, 0.0)
    assert not at(1.01 * half_len, 0.0) and not at(-1.01 * half_len, 0.0)


def test_no_shadow_on_the_sun_side_or_beyond_the_cutoff() -> None:
    sun = _sun([20.0], [90.0])  # sun due east: shadow falls west
    east_point = (300.0, 0.0)
    assert not _mask(east_point, sun)[0]
    west = ((TURBINE.hub_height_m) / math.tan(math.radians(20.0)), 0.0)
    receptor = (-west[0], 0.0)
    assert _mask(receptor, sun)[0]
    cut = shadow_mask(
        receptor,
        turbine=TURBINE,
        receptor_height_m=0.0,
        max_distance_m=west[0] - 1.0,
        sun=sun,
    )
    assert not cut.any()


def test_mirror_symmetry_of_a_symmetric_sun_path() -> None:
    el = [10.0, 25.0, 40.0, 55.0, 70.0] * 2
    az = [100.0, 120.0, 150.0, 170.0, 185.0] + [260.0, 240.0, 210.0, 190.0, 175.0]
    sun = _sun(el, az)
    for e, n in [(150.0, 40.0), (300.0, -80.0), (60.0, 200.0)]:
        assert _mask((e, n), sun).sum() == _mask((-e, n), sun).sum()


# ---------------------------------------------------------------------------
# Receptor aggregation and the expected case
# ---------------------------------------------------------------------------
def test_daily_maximum_and_annual_hours() -> None:
    sun = _sun([80.0] * 5, [0.0] * 5, days=[0, 0, 0, 1, 1])
    cfg = _flicker_cfg()
    res = receptor_flicker(
        "base",
        (0.0, 0.0),
        tower_en=(0.0, 0.0),
        turbine=TURBINE,
        cfg=cfg,
        sun=sun,
        sunny=None,
        operating_probability=None,
    )
    assert res.worst_case_hours_per_year == pytest.approx(5.0 / 60.0)
    assert res.worst_case_max_minutes_per_day == 3.0
    assert res.worst_case_days == 2
    assert res.expected_hours_per_year is None


def test_expected_case_bounds_and_linearity() -> None:
    sun = _sun([80.0, 80.0, 80.0, 1.0], [0.0, 0.0, 0.0, 0.0])
    cfg = _flicker_cfg()

    def expected(sunny: List[bool], p: float) -> float:
        res = receptor_flicker(
            "base",
            (0.0, 0.0),
            tower_en=(0.0, 0.0),
            turbine=TURBINE,
            cfg=cfg,
            sun=sun,
            sunny=np.asarray(sunny, dtype=np.bool_),
            operating_probability=p,
        )
        assert res.expected_hours_per_year is not None
        return res.expected_hours_per_year

    worst = 3.0 / 60.0
    assert expected([True] * 4, 1.0) == pytest.approx(worst)
    assert expected([False] * 4, 1.0) == 0.0
    assert expected([True, False, True, True], 0.5) == pytest.approx(0.5 * 2.0 / 60.0)
    with pytest.raises(ValueError):
        expected([True] * 4, 1.5)


def test_grid_summary_counts_cells_over_the_limit() -> None:
    sun = _sun([80.0] * 40, [0.0] * 40)
    cfg = _flicker_cfg(
        grid_half_width_m=100.0,
        grid_spacing_m=100.0,
        worst_case_hours_per_year_limit=0.5,
        sunshine_tmy_csv=None,
    )
    grid = flicker_grid(
        tower_en=(0.0, 0.0),
        turbine=TURBINE,
        cfg=cfg,
        sun=sun,
        sunny=None,
        operating_probability=None,
    )
    assert len(grid) == 9
    summary = grid_summary(grid, cfg)
    # Closed form: with the sun due north at 80 deg the ground shadow is an ellipse
    # centred (H - z)/tan(el) south of the tower, half-length R/sin(el) north-south and
    # half-width R east-west. Every node inside it sees 40 min > 0.5 h.
    el = math.radians(80.0)
    centre_n = -(TURBINE.hub_height_m - cfg.receptor_height_m) / math.tan(el)
    a, b = TURBINE.rotor_radius_m / math.sin(el), TURBINE.rotor_radius_m
    inside = sum(
        ((n - centre_n) / a) ** 2 + (e / b) ** 2 <= 1.0
        for n in (-100.0, 0.0, 100.0)
        for e in (-100.0, 0.0, 100.0)
    )
    assert 0 < inside < 9
    assert summary["area_over_worst_case_hours_limit_m2"] == inside * 100.0**2
    assert summary["max_worst_case_hours_per_year"] == pytest.approx(40.0 / 60.0)


# ---------------------------------------------------------------------------
# Sun path: pvlib against the equinox noon closed form
# ---------------------------------------------------------------------------
def test_pvlib_sun_path_noon_elevation_at_the_equinox() -> None:
    pytest.importorskip("pvlib")
    from analytics.gis.shadow_flicker import solar_path

    cfg = _flicker_cfg(time_step_minutes=5)
    sun = solar_path(T2[0], T2[1], cfg)
    day = 78  # 20 March 2026 (local), 0-based day of year
    peak = float(sun.elevation_deg[sun.day_index == day].max())
    # Declination is within 0.25 deg of zero on 20 March 2026; refraction adds < 0.02 deg.
    assert peak == pytest.approx(90.0 - T2[0], abs=0.4)
    assert sun.n_days == 365
    assert float(sun.elevation_deg.min()) >= cfg.min_sun_elevation_deg


def test_pvlib_tower_base_hours_equal_the_elevation_count() -> None:
    pytest.importorskip("pvlib")
    from analytics.gis.shadow_flicker import solar_path

    cfg = _flicker_cfg(time_step_minutes=10)
    sun = solar_path(T2[0], T2[1], cfg)
    res = receptor_flicker(
        "base",
        (0.0, 0.0),
        tower_en=(0.0, 0.0),
        turbine=TURBINE,
        cfg=cfg,
        sun=sun,
        sunny=None,
        operating_probability=None,
    )
    threshold = math.degrees(
        math.acos(
            TURBINE.rotor_radius_m / (TURBINE.hub_height_m - cfg.receptor_height_m)
        )
    )
    count = int((sun.elevation_deg >= threshold).sum())
    assert res.worst_case_hours_per_year == pytest.approx(count * 10.0 / 60.0)


# ---------------------------------------------------------------------------
# Coastal placement and the lot
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bearing_deg", [0.0, 28.0, -35.0])
def test_placement_on_a_straight_coast_matches_closed_form(bearing_deg: float) -> None:
    b = math.radians(bearing_deg)
    e0 = -300.0
    line = [
        (e0 - 2000.0 * math.sin(b), -2000.0 * math.cos(b)),
        (e0 + 2000.0 * math.sin(b), 2000.0 * math.cos(b)),
    ]
    got = place_at_coastal_setback(
        [line], north_m=0.0, min_distance_m=60.0, search_east_m=500.0
    )
    assert got.coastline_crossing_east_m == pytest.approx(e0, abs=1e-9)
    assert got.turbine_east_m == pytest.approx(e0 + 60.0 / math.cos(b), abs=0.05)
    assert got.distance_to_coastline_m == pytest.approx(60.0, abs=0.05)


def _point_segment_distance(
    p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]
) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _committed_lines() -> List[List[Tuple[float, float]]]:
    return coastline_lines_east_north(json.loads(COAST.read_text()), LocalFrame(*T2))


def _min_distance(
    p: Tuple[float, float], lines: List[List[Tuple[float, float]]]
) -> float:
    return min(
        _point_segment_distance(p, a, b) for ln in lines for a, b in zip(ln, ln[1:])
    )


def test_placement_on_the_committed_coastline_is_exactly_at_the_setback() -> None:
    lines = _committed_lines()
    setback = CoastalSetbackConfig(
        reservation_m=25.0,
        restricted_m=35.0,
        seaward_reference_offset_m=0.0,
        foundation_clearance_m=0.0,
        source="test",
    )
    got = place_at_coastal_setback(
        lines,
        north_m=0.0,
        min_distance_m=setback.tower_distance_from_coastline_m,
        search_east_m=500.0,
    )
    tower = (got.turbine_east_m, 0.0)
    assert _min_distance(tower, lines) == pytest.approx(60.0, abs=0.05)
    # One metre farther west breaches the setback: the result is the westernmost point.
    assert _min_distance((got.turbine_east_m - 1.0, 0.0), lines) < 60.0
    assert got.coastline_crossing_east_m < got.turbine_east_m < 0.0


def test_placement_moves_east_with_each_offset() -> None:
    lines = _committed_lines()
    base = place_at_coastal_setback(
        lines, north_m=0.0, min_distance_m=60.0, search_east_m=500.0
    )
    wider = place_at_coastal_setback(
        lines, north_m=0.0, min_distance_m=90.0, search_east_m=500.0
    )
    assert wider.turbine_east_m > base.turbine_east_m


def test_coast_aligned_lot_on_a_straight_coast() -> None:
    b = math.radians(28.0)
    line = [
        (-300.0 - 900.0 * math.sin(b), -900.0 * math.cos(b)),
        (-300.0 + 900.0 * math.sin(b), 900.0 * math.cos(b)),
    ]
    lot = coast_aligned_square_lot(
        [line], north_m=0.0, area_m2=93077.0, sample_step_m=5.0
    )
    assert lot.edge_bearing_deg == pytest.approx(28.0, abs=1e-6)
    assert lot.edge_max_deviation_m == pytest.approx(0.0, abs=1e-6)
    sw, se, ne, nw = lot.corners
    area = 0.5 * abs(
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(
                lot.corners, lot.corners[1:] + lot.corners[:1]
            )
        )
    )
    assert area == pytest.approx(93077.0, rel=1e-9)
    assert (sw[0] + nw[0]) / 2.0 == pytest.approx(-300.0) and (
        sw[1] + nw[1]
    ) / 2.0 == pytest.approx(0.0)
    assert se[0] > sw[0] and ne[0] > nw[0]  # landward is east


def test_committed_site_geojson_geodesic_area_and_flags() -> None:
    import pyproj

    doc = json.loads(SITE.read_text())
    lot, turbine = doc["features"]
    props = lot["properties"]
    assert props["surveyed"] is False and props["placeholder"] is True
    assert props["every_result_depends_on_this_placeholder"] is True
    ring = lot["geometry"]["coordinates"][0]
    lons, lats = zip(*ring)
    area, _ = pyproj.Geod(ellps="WGS84").polygon_area_perimeter(lons, lats)
    assert abs(area) == pytest.approx(93077.0, abs=0.05)  # 9-decimal rounding: 0.1 mm
    # The turbine is the setback point on T2's latitude, 60 m from the coastline.
    lon_t, lat_t = turbine["geometry"]["coordinates"]
    assert lat_t == pytest.approx(T2[0], abs=1e-7)
    frame = LocalFrame(*T2)
    tower = frame.to_east_north(lon_t, lat_t)
    assert _min_distance(tower, _committed_lines()) == pytest.approx(60.0, abs=0.05)


# ---------------------------------------------------------------------------
# Tip-height setback
# ---------------------------------------------------------------------------
def _centred_square(side: float) -> SquareLot:
    h = side / 2.0
    return SquareLot(
        corners=((-h, -h), (h, -h), (h, h), (-h, h)),
        edge_bearing_deg=0.0,
        side_m=side,
        edge_max_deviation_m=0.0,
    )


def test_tip_setback_disc_outside_square_closed_forms() -> None:
    side = math.sqrt(93077.0)
    h = side / 2.0
    cfg = TipSetbackConfig(tip_height_multiple=1.0, source="test")
    # r = 233 m > h*sqrt(2): the square is inside the disc, so outside = pi r^2 - A.
    res = tip_height_setback(_centred_square(side), (0.0, 0.0), TURBINE, cfg)
    r = TURBINE.tip_height_m
    assert res.setback_disc_area_outside_lot_m2 == pytest.approx(
        math.pi * r * r - side * side, rel=0.01
    )
    assert res.lot_edges_breached == ["east", "north", "south", "west"]
    assert not res.fits_within_lot
    # h < r < h*sqrt(2): four circular segments beyond the sides.
    small = TurbineGeometry(hub_height_m=120.0, rotor_diameter_m=120.0)  # tip 180 m
    r2 = small.tip_height_m
    res2 = tip_height_setback(_centred_square(side), (0.0, 0.0), small, cfg)
    seg = r2 * r2 * math.acos(h / r2) - h * math.sqrt(r2 * r2 - h * h)
    assert res2.setback_disc_area_outside_lot_m2 == pytest.approx(4.0 * seg, rel=0.02)
    assert res2.min_distance_to_lot_edge_m == pytest.approx(h)


def test_tip_setback_fits_when_small() -> None:
    tiny = TurbineGeometry(hub_height_m=50.0, rotor_diameter_m=40.0)  # tip 70 m
    res = tip_height_setback(
        _centred_square(305.0), (0.0, 0.0), tiny, TipSetbackConfig(1.0, "test")
    )
    assert res.fits_within_lot and res.lot_edges_breached == []
    assert res.rotor_overhang_beyond_lot_m == 0.0


# ---------------------------------------------------------------------------
# Strict configuration (FRAMEWORK-02)
# ---------------------------------------------------------------------------
def test_config_refuses_missing_and_unknown_keys() -> None:
    import yaml

    raw = dict(yaml.safe_load(CONF.read_text())["shadow_flicker"])
    ShadowFlickerConfig.from_mapping(raw)
    missing: Dict[str, object] = {
        k: v for k, v in raw.items() if k != "receptor_height_m"
    }
    with pytest.raises(ValueError, match="missing"):
        ShadowFlickerConfig.from_mapping(missing)
    with pytest.raises(ValueError, match="unknown"):
        ShadowFlickerConfig.from_mapping({**raw, "surprise": 1})
    no_source = {**raw, "threshold_sources": {}}
    with pytest.raises(ValueError, match="threshold_sources"):
        ShadowFlickerConfig.from_mapping(no_source)
    coastal = dict(yaml.safe_load(CONF.read_text())["coastal_setback"])
    assert CoastalSetbackConfig.from_mapping(coastal).total_setback_m == 60.0
    with pytest.raises(ValueError):
        CoastalSetbackConfig.from_mapping({**coastal, "reservation_m": -1.0})


def test_turbine_geometry_guards() -> None:
    assert TURBINE.tip_height_m == 233.0 and TURBINE.rotor_radius_m == 103.0
    with pytest.raises(ValueError):
        TurbineGeometry(hub_height_m=100.0, rotor_diameter_m=206.0)
