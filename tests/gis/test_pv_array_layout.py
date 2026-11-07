"""Tests for analytics.gis.pv_array_layout (Blue Whale PV array, land and site fit).

The oracles do not come from the code under test:

* the module datasheet's own warranted year-30 power (88.85%) and the STC values
  (JinkoSolar JKM650-670N-66QL6-BDV-F1-EU; pv magazine, 2025-09-05);
* closed forms worked by hand: the cold open-circuit voltage
  ``50.98 * (1 + 0.0024 * 10)``, the table count ``ceil(5e6 * 1.2 / 37,520)``, the shadow
  reach ``L sin(b) / tan(e)`` for a sun due south, and the packing count on a rectangle;
* an independent solar-position algorithm (``pvlib`` ``ephemeris``, not the default SPA
  the code uses) for the row-pitch rule, plus a hostile control showing that a pitch
  just below the rule's value does shade;
* geometric invariants: the lot area equals the exclusions plus the usable area, and no
  two placed tables overlap.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.gis import pv_array_layout as pal

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess.yaml"


@pytest.fixture(scope="module")
def cfg() -> Dict[str, Any]:
    data = yaml.safe_load(CONF.read_text())
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def module(cfg: Dict[str, Any]) -> pal.ModuleSpec:
    return pal.ModuleSpec.from_mapping(cfg["module"])


@pytest.fixture(scope="module")
def strings(cfg: Dict[str, Any], module: pal.ModuleSpec) -> pal.StringDesign:
    return pal.design_string(
        module, pal.StringDesignConfig.from_mapping(cfg["string_design"])
    )


@pytest.fixture(scope="module")
def array(cfg: Dict[str, Any]) -> pal.ArrayConfig:
    return pal.ArrayConfig.from_mapping(cfg["array"])


@pytest.fixture(scope="module")
def sizing(
    module: pal.ModuleSpec, strings: pal.StringDesign, array: pal.ArrayConfig
) -> pal.ArraySizing:
    return pal.size_array(module, strings, array)


# ---------------------------------------------------------------------------
# Module and strings
# ---------------------------------------------------------------------------
def test_module_matches_the_datasheet_and_its_warranty(module: pal.ModuleSpec) -> None:
    assert module.pmax_w == 670.0
    assert module.voc_v == 50.98 and module.isc_a == 16.22
    assert module.area_m2 == pytest.approx(2.382 * 1.134)
    # Datasheet: 99% after year 1, 88.85% after year 30.
    assert module.warranted_power_fraction(1) == pytest.approx(0.99)
    assert module.warranted_power_fraction(30) == pytest.approx(0.8885)
    # STC efficiency follows from power and area (24.80% on the datasheet).
    assert 670.0 / (module.area_m2 * 1000.0) * 100.0 == pytest.approx(24.80, abs=0.01)


def test_module_parser_refuses_bad_input(cfg: Dict[str, Any]) -> None:
    raw = dict(cfg["module"])
    with pytest.raises(ValueError, match="does not follow"):
        pal.ModuleSpec.from_mapping({**raw, "year_30_power_pct": 89.0})
    with pytest.raises(ValueError, match="unknown keys"):
        pal.ModuleSpec.from_mapping({**raw, "voc": 50.0})
    missing = dict(raw)
    del missing["isc_a"]
    with pytest.raises(ValueError, match="missing keys"):
        pal.ModuleSpec.from_mapping(missing)
    with pytest.raises(ValueError, match="Vmp x Imp"):
        pal.ModuleSpec.from_mapping({**raw, "imp_a": 14.0})
    with pytest.raises(ValueError, match="1-based"):
        pal.ModuleSpec.from_mapping(raw).warranted_power_fraction(0)


def test_string_length_closed_form(module: pal.ModuleSpec) -> None:
    sd = pal.design_string(
        module,
        pal.StringDesignConfig(
            design_min_cell_temp_c=15.0, design_max_cell_temp_c=70.0
        ),
    )
    voc_cold = 50.98 * (1.0 + 0.0024 * 10.0)
    assert sd.voc_cold_module_v == pytest.approx(voc_cold)
    assert sd.modules_per_string == 28  # 1500 / 52.2035 = 28.73
    assert sd.string_voc_cold_v <= 1500.0 < (sd.modules_per_string + 1) * voc_cold
    assert sd.string_vmp_stc_v == pytest.approx(28 * 43.09)
    assert sd.string_vmp_hot_v == pytest.approx(28 * 43.09 * (1 - 0.0024 * 45.0))
    # Responsiveness: a warmer design minimum admits a longer string.
    warm = pal.design_string(
        module,
        pal.StringDesignConfig(
            design_min_cell_temp_c=21.14, design_max_cell_temp_c=70.0
        ),
    )
    assert warm.modules_per_string == 29


def test_array_counts_closed_form(sizing: pal.ArraySizing) -> None:
    assert sizing.modules_per_table == 56
    assert sizing.table_power_w == 56 * 670.0
    assert sizing.tables == math.ceil(5.0e6 * 1.2 / 37520.0) == 160
    assert sizing.modules == 8960 and sizing.strings == 320
    assert sizing.dc_capacity_mw == pytest.approx(6.0032)
    assert sizing.dc_ac_ratio == pytest.approx(6.0032 / 5.0)
    assert sizing.table_slant_m == pytest.approx(2 * 2.382 + 0.02)
    assert sizing.table_length_ew_m == pytest.approx(28 * 1.134 + 27 * 0.02)
    assert sizing.table_depth_m == pytest.approx(4.784 * math.cos(math.radians(8.0)))


def test_array_rounds_up_to_whole_tables(
    module: pal.ModuleSpec, strings: pal.StringDesign, cfg: Dict[str, Any]
) -> None:
    raw = dict(cfg["array"])
    exact = pal.size_array(
        module,
        strings,
        pal.ArrayConfig.from_mapping({**raw, "dc_ac_ratio": 160 * 37520.0 / 5.0e6}),
    )
    assert exact.tables == 160
    over = pal.size_array(
        module,
        strings,
        pal.ArrayConfig.from_mapping(
            {**raw, "dc_ac_ratio": 160 * 37520.0 / 5.0e6 + 1e-6}
        ),
    )
    assert over.tables == 161
    with pytest.raises(ValueError, match="portrait rows"):
        pal.size_array(
            module,
            strings,
            pal.ArrayConfig.from_mapping(
                {**raw, "modules_high_portrait": 3, "strings_per_table": 1}
            ),
        )


# ---------------------------------------------------------------------------
# Row pitch
# ---------------------------------------------------------------------------
def test_shadow_reach_closed_form() -> None:
    slant, tilt = 4.784, 8.0
    h = slant * math.sin(math.radians(tilt))
    assert pal.shadow_reach_m(slant, tilt, 180.0, 45.0, 180.0) == pytest.approx(h)
    assert pal.shadow_reach_m(slant, tilt, 180.0, 30.0, 180.0) == pytest.approx(
        h / math.tan(math.radians(30.0))
    )
    # Sun behind the rows or due east casts no shadow onto the next row.
    assert pal.shadow_reach_m(slant, tilt, 180.0, 30.0, 0.0) == 0.0
    assert pal.shadow_reach_m(slant, tilt, 180.0, 30.0, 90.0) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        pal.shadow_reach_m(slant, tilt, 180.0, 0.0, 180.0)


def _pitch(
    cfg: Dict[str, Any], sizing: pal.ArraySizing, array: pal.ArrayConfig, **rule: Any
) -> pal.RowPitch:
    return pal.row_pitch(
        lat_deg=8.29185,
        lon_deg=79.75327,
        sizing=sizing,
        array=array,
        rule=pal.ShadingRuleConfig.from_mapping({**cfg["shading_rule"], **rule}),
    )


def test_row_pitch_against_an_independent_sun_position(
    cfg: Dict[str, Any], sizing: pal.ArraySizing, array: pal.ArrayConfig
) -> None:
    pvlib = pytest.importorskip("pvlib")
    import pandas as pd

    pitch = _pitch(cfg, sizing, array)
    times = pd.date_range(
        "2026-12-21 09:00", "2026-12-21 15:00", freq="1min", tz="Asia/Colombo"
    )
    sp = pvlib.solarposition.ephemeris(times, 8.29185, 79.75327)
    h = sizing.table_slant_m * math.sin(math.radians(8.0))
    reach = max(
        h * max(0.0, math.cos(math.radians(a - 180.0))) / math.tan(math.radians(e))
        for e, a in zip(sp["apparent_elevation"], sp["azimuth"], strict=True)
    )
    assert pitch.no_shade_pitch_m == pytest.approx(
        sizing.table_depth_m + reach, rel=2e-3
    )
    # The binding instant is the low morning sun, not noon (58.3 deg at 8.29 N).
    assert pitch.worst_time_local.startswith("2026-12-21T09:00")
    assert pitch.governing == "aisle"
    assert pitch.pitch_m == pytest.approx(sizing.table_depth_m + 2.0)
    assert pitch.gcr == pytest.approx(sizing.table_slant_m / pitch.pitch_m)


def test_row_pitch_hostile_control(
    cfg: Dict[str, Any], sizing: pal.ArraySizing, array: pal.ArrayConfig
) -> None:
    pytest.importorskip("pvlib")
    pitch = _pitch(cfg, sizing, array, min_clear_aisle_m=0.0)
    assert pitch.governing == "shading"
    reach = pal.shadow_reach_m(
        sizing.table_slant_m,
        8.0,
        180.0,
        pitch.worst_sun_elevation_deg,
        pitch.worst_sun_azimuth_deg,
    )
    # At the rule's pitch the shadow just reaches the next row; 5 cm closer it overlaps.
    assert pitch.pitch_m - sizing.table_depth_m == pytest.approx(reach)
    assert (pitch.pitch_m - 0.05) - sizing.table_depth_m < reach
    # A wider window (earlier start) needs a longer pitch.
    wider = _pitch(cfg, sizing, array, min_clear_aisle_m=0.0, start_local="08:00")
    assert wider.no_shade_pitch_m > pitch.no_shade_pitch_m


# ---------------------------------------------------------------------------
# Land and BESS pad
# ---------------------------------------------------------------------------
def test_equipment_area_closed_form(cfg: Dict[str, Any]) -> None:
    land = pal.LandConfig.from_mapping(cfg["land"])
    eq = pal.equipment_area(
        bess_power_mw=5.0,
        bess_energy_mwh=30.0,
        bess=pal.BessFootprintConfig.from_mapping(cfg["bess_footprint"]),
        land=land,
    )
    assert eq.bess_units_for_energy == math.ceil(30000 / 5015) == 6
    assert eq.bess_units_for_power == math.ceil(5000 / 762) == 7
    assert eq.bess_units == 7
    assert eq.bess_pad_length_m == pytest.approx(4 * 6.058 + 5 * 3.0)
    assert eq.bess_pad_width_m == pytest.approx(2 * 2.438 + 3 * 3.0)
    assert eq.footprint_area_m2 == pytest.approx(
        (eq.bess_pad_length_m + 6.0)
        * (eq.bess_pad_width_m + 80.0 / eq.bess_pad_length_m + 6.0)
    )


def test_compact_land_area_is_the_best_row_count(
    cfg: Dict[str, Any], sizing: pal.ArraySizing, array: pal.ArrayConfig
) -> None:
    pytest.importorskip("pvlib")
    land = pal.LandConfig.from_mapping(cfg["land"])
    eq = pal.equipment_area(
        bess_power_mw=5.0,
        bess_energy_mwh=30.0,
        bess=pal.BessFootprintConfig.from_mapping(cfg["bess_footprint"]),
        land=land,
    )
    pitch = _pitch(cfg, sizing, array)
    area = pal.compact_land_area(
        sizing=sizing, pitch=pitch, array=array, land=land, equipment=eq
    )
    # Independent enumeration, written out here.
    best = math.inf
    for rows in range(1, 161):
        per = math.ceil(160 / rows)
        roads = (per - 1) // 8
        length = per * sizing.table_length_ew_m + (per - 1 - roads) * 1.0 + roads * 4.0
        depth = (rows - 1) * pitch.pitch_m + sizing.table_depth_m
        best = min(best, (length + 12.0) * (depth + 12.0))
    assert area.fenced_array_area_m2 == pytest.approx(best)
    assert area.rows * area.tables_per_row >= 160
    # Lower bound: the tables' own row-pitch strips.
    assert (
        area.array_block_area_m2 > 160 * sizing.table_length_ew_m * pitch.pitch_m * 0.95
    )
    assert area.fenced_area_m2 == pytest.approx(
        area.fenced_array_area_m2 + eq.footprint_area_m2
    )


# ---------------------------------------------------------------------------
# Packing and site fit
# ---------------------------------------------------------------------------
def test_pack_tables_on_a_rectangle_closed_form(
    cfg: Dict[str, Any], sizing: pal.ArraySizing, array: pal.ArrayConfig
) -> None:
    shapely = pytest.importorskip("shapely")
    from shapely.geometry import box

    land = pal.LandConfig.from_mapping(cfg["land"])
    pitch = 6.7
    # Room for exactly 3 rows and 10 tables per row (one road after table 8).
    width = 10 * sizing.table_length_ew_m + 8 * 1.0 + 4.0 + 0.5
    height = 2 * pitch + sizing.table_depth_m + 0.1
    tables = pal.pack_tables(
        box(0.0, 0.0, width, height),
        sizing=sizing,
        pitch_m=pitch,
        array=array,
        land=land,
    )
    assert len(tables) == 30
    polys = [box(*t) for t in tables]
    region = box(0.0, 0.0, width, height)
    assert all(region.covers(p) for p in polys)
    assert all(
        polys[i].intersection(polys[j]).area < 1e-9
        for i in range(len(polys))
        for j in range(i + 1, len(polys))
    )
    assert shapely is not None


def test_site_fit_on_the_placeholder_lot(
    cfg: Dict[str, Any], sizing: pal.ArraySizing, array: pal.ArrayConfig
) -> None:
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    pytest.importorskip("pvlib")
    from analytics.gis.shadow_flicker import CoastalSetbackConfig, LocalFrame

    wind = yaml.safe_load(
        (REPO_ROOT / "conf" / "blue_whale_wind_siting.yaml").read_text()
    )
    frame = LocalFrame(
        wind["site"]["reference_lat_deg"], wind["site"]["reference_lon_deg"]
    )
    fit_cfg = pal.SiteFitConfig.from_mapping(cfg["site_fit"])
    site = pal.site_geometry(
        json.loads((REPO_ROOT / fit_cfg.site_geojson).read_text()),
        json.loads((REPO_ROOT / fit_cfg.coastline_geojson).read_text()),
        frame,
    )
    land = pal.LandConfig.from_mapping(cfg["land"])
    eq = pal.equipment_area(
        bess_power_mw=5.0,
        bess_energy_mwh=30.0,
        bess=pal.BessFootprintConfig.from_mapping(cfg["bess_footprint"]),
        land=land,
    )
    pitch = _pitch(cfg, sizing, array)
    layout = pal.fit_site(
        site,
        coastal=CoastalSetbackConfig.from_mapping(wind["coastal_setback"]),
        cfg=fit_cfg,
        sizing=sizing,
        pitch=pitch,
        array=array,
        land=land,
        equipment=eq,
        required_fenced_area_m2=41000.0,
    )
    fit = layout.fit
    assert fit.lot_area_m2 == pytest.approx(93077.0, rel=1e-4)
    parts = (
        fit.coastal_strip_in_lot_m2
        + fit.foundation_in_lot_m2
        + fit.crane_pad_in_lot_m2
        + fit.usable_area_m2
    )
    assert parts == pytest.approx(fit.lot_area_m2, rel=1e-9)
    assert fit.crane_pad_in_lot_m2 == pytest.approx(40.0 * 80.0, rel=1e-6)
    assert fit.equipment_placed and fit.fits
    assert fit.tables_that_fit >= fit.tables_required == 160
    # Every table lies in the usable area and none overlaps the equipment group.
    from shapely.geometry import box

    assert layout.equipment_box is not None
    eq_box = box(*layout.equipment_box)
    for t in layout.tables:
        b = box(*t)
        assert layout.usable.covers(b)
        assert b.intersection(eq_box).area < 1e-9
    # Hostile control: a much wider coastal strip leaves too little land.
    wide = dict(wind["coastal_setback"], restricted_m=135.0)
    tight = pal.fit_site(
        site,
        coastal=CoastalSetbackConfig.from_mapping(wide),
        cfg=fit_cfg,
        sizing=sizing,
        pitch=pitch,
        array=array,
        land=land,
        equipment=eq,
        required_fenced_area_m2=41000.0,
    )
    assert not tight.fit.fits
    assert tight.fit.tables_that_fit < 160


def test_site_fit_config_is_strict(cfg: Dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="unknown keys"):
        pal.SiteFitConfig.from_mapping({**cfg["site_fit"], "extra": 1})
    with pytest.raises(ValueError, match="missing keys"):
        pal.LandConfig.from_mapping(
            {k: v for k, v in cfg["land"].items() if k != "fence_to_array_m"}
        )
