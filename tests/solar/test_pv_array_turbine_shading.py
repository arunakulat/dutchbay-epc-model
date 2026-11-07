"""Tests for solar_resource.pv_array_turbine_shading (Blue Whale input B33).

The oracles do not come from the code under test:

* hand-computed shadow geometry for one sun position: the tower strip ``(h - panel) /
  tan(elevation)`` long behind the tower, and a vertical rotor disc that casts nothing
  when edge-on to the sun and covers the hub's shadow point when facing it;
* #1520's :func:`solar_resource.turbine_shading.accumulate_shading`, which predates this
  module, for the annual tower and rotor removal on the same points and sun positions;
* arithmetic on the hourly roll-up (sub-steps summed into their hour, the first ``n``
  tables' mean, ``1 - multiplier x loss``);
* the producer's own hourly chain for the POA retention (all ones changes nothing, all
  zeros leaves no output);
* hostile configs: missing and unknown keys, a block that is not applied, a multiplier
  below the optical floor.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pytest
import yaml

from solar_resource import pv_array_turbine_shading as pats
from solar_resource import turbine_shading as ts
from solar_resource.pv_bess_dispatch import hourly_pv, with_array

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess.yaml"
WIND_SITING = REPO_ROOT / "conf" / "blue_whale_wind_siting.yaml"

HUB = 130.0
ROTOR = 206.0
PANEL = 1.0
TOWER_W = 6.4375  # 1/16 of the 103 m rotor radius


def _unit() -> Dict[str, Any]:
    data = yaml.safe_load(CONF.read_text())
    assert isinstance(data, dict)
    return data


def _solar() -> Any:
    return with_array(
        _unit()["pv_yield"]["resource_solar"],
        dc_capacity_mw=5.0,
        dc_ac_ratio=1.2,
        tilt_deg=8.0,
        azimuth_deg=180.0,
        gamma_pdc_per_c=-0.0026,
    )


def _cfg(**over: Any) -> pats.ArrayShadingConfig:
    base: Dict[str, Any] = dict(
        hub_height_m=HUB,
        rotor_diameter_m=ROTOR,
        tower_diameter_m=TOWER_W,
        blade_solidity=0.04,
        panel_height_m=PANEL,
        substeps_per_hour=1,
        min_sun_elevation_deg=1.0,
        samples_per_table=(2, 2),
        yaw_basis="uniform",
        yaw_deg=(0.0,),
        yaw_weight=(1.0,),
        electrical_mismatch_multiplier=1.0,
        electrical_mismatch_basis="test",
    )
    base.update(over)
    return pats.ArrayShadingConfig(**base)


def _steps(
    elevation: list[float], azimuth: list[float], beam: list[float], glob: list[float]
) -> Tuple[Any, ...]:
    return (
        np.asarray(elevation, dtype=float),
        np.asarray(azimuth, dtype=float),
        np.asarray(beam, dtype=float),
        np.asarray(glob, dtype=float),
        "synthetic",
    )


def _block(**over: Any) -> Dict[str, Any]:
    block: Dict[str, Any] = {
        "samples_per_table_ew": 8,
        "samples_per_table_ns": 2,
        "yaw_basis": "wind_rose",
        "wind_rose_csv": "docs/blue_whale/met_mast_wind_rose_130m.csv",
        "electrical_mismatch_multiplier": 1.0,
        "electrical_mismatch_basis": "optical floor",
        "method_overrides": {},
    }
    block.update(over)
    return block


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text()


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def test_wind_rose_folds_opposite_sectors_and_normalises() -> None:
    text = "# comment\nsector,centre_deg,frequency\n0,0,0.2\n1,90,0.1\n2,180,0.3\n3,270,0.4\n"
    yaws, weights = pats.read_wind_rose(text)
    assert yaws == (0.0, 90.0)
    assert weights == pytest.approx((0.5, 0.5))
    with pytest.raises(ValueError, match="centre_deg"):
        pats.read_wind_rose("a,b\n1,2\n")
    with pytest.raises(ValueError, match="sum to zero"):
        pats.read_wind_rose("centre_deg,frequency\n0,0\n")
    with pytest.raises(ValueError, match=">= 0"):
        pats.read_wind_rose("centre_deg,frequency\n0,-1\n")


def test_the_committed_wind_rose_gives_eight_orientations() -> None:
    cfg = pats.ArrayShadingConfig.from_mapping(
        _block(),
        turbine=yaml.safe_load(WIND_SITING.read_text())["turbine"],
        read_text=_read,
    )
    assert len(cfg.yaw_deg) == 8 and sum(cfg.yaw_weight) == pytest.approx(1.0)
    assert cfg.hub_height_m == HUB and cfg.rotor_diameter_m == ROTOR
    # The tower width comes from config/defaults.yaml (1/16 of the rotor radius).
    assert cfg.tower_diameter_m == pytest.approx(ROTOR / 2.0 / 16.0)
    # NE (45) and SW (225) fold together: 0.111771 + 0.265876 of the sector total.
    rose = [
        ln.split(",")
        for ln in _read("docs/blue_whale/met_mast_wind_rose_130m.csv").splitlines()[2:]
    ]
    total = sum(float(r[3]) for r in rose)
    i = cfg.yaw_deg.index(45.0)
    assert cfg.yaw_weight[i] == pytest.approx((0.111771 + 0.265876) / total)


def test_table_sample_points_are_cell_centres_relative_to_the_tower() -> None:
    pts = pats.table_sample_points([(10.0, 20.0, 14.0, 22.0)], (1.0, 2.0), (2, 2))
    assert sorted(map(tuple, pts.tolist())) == [
        (10.0, 18.5),
        (10.0, 19.5),
        (12.0, 18.5),
        (12.0, 19.5),
    ]


# ---------------------------------------------------------------------------
# Geometry against hand-computed shadows
# ---------------------------------------------------------------------------
def test_tower_strip_removes_all_the_beam_behind_the_tower() -> None:
    # Sun due south at 45 degrees: the tower's shadow runs due north for h - panel.
    length = HUB - PANEL
    half = TOWER_W / 2.0
    in_strip = (-half * 0.9, 0.3 * length, half * 0.9, 0.6 * length)
    south = (-half, -60.0, half, -40.0)  # behind the sun: never shaded
    beyond = (-half, length * 1.2, half, length * 1.3)  # past the strip, outside rotor
    # The rotor is edge-on to a southern sun at yaw 90, so only the tower acts.
    cfg = _cfg(yaw_deg=(90.0,))
    sh = pats.table_shading(
        [in_strip, south, beyond],
        (0.0, 0.0),
        _solar(),
        cfg,
        steps=_steps([45.0], [180.0], [500.0], [800.0]),
    )
    removed = np.diff(sh.cum_removed_wh[:, 0])
    assert removed == pytest.approx([500.0, 0.0, 0.0])
    assert sh.tower_wh == pytest.approx([500.0, 0.0, 0.0])
    assert sh.rotor_wh == pytest.approx([0.0, 0.0, 0.0])
    # Optical loss of the first table alone: 500 / 800.
    assert sh.optical_loss_hourly(1) == pytest.approx([0.625])
    assert sh.optical_loss_hourly(3) == pytest.approx([500.0 / 3.0 / 800.0])


def test_rotor_follows_the_yaw_weights() -> None:
    # Sun due south at 45 degrees: the hub's shadow falls at (0, h - panel). A disc in
    # the east-west plane (axis azimuth 0) faces the sun and covers that point; a disc in
    # the north-south plane (axis 90) is edge-on and casts nothing.
    centre_n = HUB - PANEL
    table = (12.0, centre_n - 1.0, 14.0, centre_n + 1.0)  # east of the tower strip
    for weights, share in (((1.0, 0.0), 1.0), ((0.0, 1.0), 0.0), ((0.3, 0.7), 0.3)):
        sh = pats.table_shading(
            [table],
            (0.0, 0.0),
            _solar(),
            _cfg(yaw_deg=(0.0, 90.0), yaw_weight=weights),
            steps=_steps([45.0], [180.0], [500.0], [800.0]),
        )
        assert sh.tower_wh == pytest.approx([0.0])
        assert sh.rotor_wh == pytest.approx([500.0 * 0.04 * share])
        assert sh.rotor_yawed_to_sun_wh == pytest.approx([500.0 * 0.04])
        assert sh.cum_removed_wh[1, 0] == pytest.approx(500.0 * 0.04 * share)


def test_sub_steps_fold_into_their_hour_and_low_sun_is_ignored() -> None:
    half = TOWER_W / 2.0
    table = (-half * 0.5, 10.0, half * 0.5, 20.0)
    # Two hours x two sub-steps, block order (all hours at offset 0, then offset 30 min).
    # Hour 0: the sun is shading at offset 0 and below the cut-off at offset 30.
    steps = _steps(
        [45.0, -5.0, 0.5, 45.0],
        [180.0, 180.0, 180.0, 180.0],
        [400.0, 0.0, 300.0, 200.0],
        [600.0, 0.0, 600.0, 400.0],
    )
    sh = pats.table_shading(
        [table],
        (0.0, 0.0),
        _solar(),
        _cfg(substeps_per_hour=2, yaw_deg=(90.0,)),
        steps=steps,
    )
    assert sh.poa_global_wh == pytest.approx([1200.0, 400.0])
    assert sh.cum_removed_wh[1] == pytest.approx([400.0, 200.0])
    assert sh.retention(1, 1.0) == pytest.approx([1.0 - 400.0 / 1200.0, 0.5])
    assert sh.retention(1, 3.0) == pytest.approx([0.0, 0.0])  # clipped at zero
    annual = sh.annual(1, 1.0)
    assert annual["optical_loss"] == pytest.approx(600.0 / 1600.0)
    assert annual["poa_loss_after_multiplier"] == pytest.approx(600.0 / 1600.0)


def test_annual_tower_and_rotor_match_1520s_accumulator() -> None:
    # The same points and sun positions through #1520's accumulate_shading (uniform yaw).
    tables = [
        (-20.0, 30.0, 12.0, 34.7),
        (40.0, -50.0, 72.0, -45.3),
        (-5.0, 150.0, 27.0, 154.7),
    ]
    rng = np.random.default_rng(7)
    n = 40
    el = rng.uniform(5.0, 85.0, n)
    az = rng.uniform(0.0, 360.0, n)
    beam = rng.uniform(50.0, 800.0, n)
    glob = beam + rng.uniform(50.0, 200.0, n)
    cfg = _cfg(
        samples_per_table=(4, 2),
        yaw_deg=(0.0, 45.0, 90.0, 135.0),
        yaw_weight=(0.25, 0.25, 0.25, 0.25),
    )
    sh = pats.table_shading(
        tables,
        (0.0, 0.0),
        _solar(),
        cfg,
        steps=(el, az, beam, glob, "synthetic"),
    )
    pts = pats.table_sample_points(tables, (0.0, 0.0), (4, 2))
    acc = ts.accumulate_shading(
        pts,
        el,
        az,
        beam,
        glob,
        hub_height_m=HUB - PANEL,
        rotor_radius_m=ROTOR / 2.0,
        tower_diameter_m=TOWER_W,
        blade_solidity=0.04,
        yaw_samples=4,
        min_sun_elevation_deg=1.0,
    )
    per = 8
    assert sh.tower_wh == pytest.approx(acc.tower_wh.reshape(3, per).mean(axis=1))
    assert sh.rotor_wh == pytest.approx(acc.rotor_low_wh.reshape(3, per).mean(axis=1))
    # #1520's sun-facing "high" disc is the shadow of the sphere around the hub, which
    # contains every disc of that radius, so the rotor yawed to the sun's azimuth can
    # never exceed it at any point.
    high = acc.rotor_high_wh.reshape(3, per).mean(axis=1)
    assert (sh.rotor_yawed_to_sun_wh <= high + 1e-9).all()
    assert (sh.rotor_yawed_to_sun_wh < high).any()
    assert any(sh.tower_wh > 0) and any(sh.rotor_wh > 0)


# ---------------------------------------------------------------------------
# Config strictness (FRAMEWORK-02)
# ---------------------------------------------------------------------------
def test_config_is_strict() -> None:
    turbine = {"hub_height_m": HUB, "rotor_diameter_m": ROTOR}
    with pytest.raises(KeyError, match="missing"):
        pats.ArrayShadingConfig.from_mapping(
            {k: v for k, v in _block().items() if k != "yaw_basis"},
            turbine=turbine,
            read_text=_read,
        )
    with pytest.raises(KeyError, match="unknown"):
        pats.ArrayShadingConfig.from_mapping(
            _block(extra=1), turbine=turbine, read_text=_read
        )
    with pytest.raises(KeyError, match="method_overrides"):
        pats.ArrayShadingConfig.from_mapping(
            _block(method_overrides={"grid_step_m": 1.0}),
            turbine=turbine,
            read_text=_read,
        )
    with pytest.raises(ValueError, match="takes no wind_rose_csv"):
        pats.ArrayShadingConfig.from_mapping(
            _block(yaw_basis="uniform"), turbine=turbine, read_text=_read
        )
    with pytest.raises(ValueError, match="electrical_mismatch_multiplier"):
        pats.ArrayShadingConfig.from_mapping(
            _block(electrical_mismatch_multiplier=0.5), turbine=turbine, read_text=_read
        )
    with pytest.raises(ValueError, match="electrical_mismatch_basis"):
        pats.ArrayShadingConfig.from_mapping(
            _block(electrical_mismatch_basis=" "), turbine=turbine, read_text=_read
        )
    with pytest.raises(KeyError, match="hub_height_m"):
        pats.ArrayShadingConfig.from_mapping(
            _block(), turbine={"rotor_diameter_m": ROTOR}, read_text=_read
        )
    uniform = pats.ArrayShadingConfig.from_mapping(
        _block(
            yaw_basis="uniform", wind_rose_csv=None, method_overrides={"yaw_samples": 6}
        ),
        turbine=turbine,
        read_text=_read,
    )
    assert uniform.yaw_deg == pytest.approx([0.0, 30.0, 60.0, 90.0, 120.0, 150.0])


def test_the_switch_and_the_block_must_agree() -> None:
    turbine = {"hub_height_m": HUB, "rotor_diameter_m": ROTOR}
    off = {"turbine_shading_modelled": False, "turbine_shading": None}
    assert (
        pats.shading_source_from_unit(
            off, turbine=turbine, turbine_en=(0, 0), read_text=_read
        )
        is None
    )
    with pytest.raises(KeyError, match="null when not modelled"):
        pats.shading_source_from_unit(
            {"turbine_shading_modelled": False, "turbine_shading": _block()},
            turbine=turbine,
            turbine_en=(0, 0),
            read_text=_read,
        )
    with pytest.raises(KeyError, match="mapping when modelled"):
        pats.shading_source_from_unit(
            {"turbine_shading_modelled": True, "turbine_shading": None},
            turbine=turbine,
            turbine_en=(0, 0),
            read_text=_read,
        )
    with pytest.raises(KeyError, match="required"):
        pats.shading_source_from_unit(
            {"turbine_shading_modelled": False},
            turbine=turbine,
            turbine_en=(0, 0),
            read_text=_read,
        )
    with pytest.raises(TypeError, match="true or false"):
        pats.shading_source_from_unit(
            {"turbine_shading_modelled": "yes", "turbine_shading": None},
            turbine=turbine,
            turbine_en=(0, 0),
            read_text=_read,
        )
    src = pats.shading_source_from_unit(
        {"turbine_shading_modelled": True, "turbine_shading": _block()},
        turbine=turbine,
        turbine_en=(3, 4),
        read_text=_read,
    )
    assert src is not None and src.turbine_en == (3.0, 4.0)


def test_the_committed_unit_config_models_the_shadow() -> None:
    pv_yield = _unit()["pv_yield"]
    assert pv_yield["turbine_shading_modelled"] is True
    assert set(pv_yield["turbine_shading"]) == set(pats.BLOCK_KEYS)
    # Optical floor, declared (the stress case is reported, not pinned).
    assert pv_yield["turbine_shading"]["electrical_mismatch_multiplier"] == 1.0


# ---------------------------------------------------------------------------
# The derate in the producer's hourly chain
# ---------------------------------------------------------------------------
def test_poa_retention_scales_the_dc_input() -> None:
    pytest.importorskip("pvlib")
    solar = _solar()
    plain = hourly_pv(solar)
    same = hourly_pv(solar, poa_retention=np.ones(len(plain.ac_mw)))
    np.testing.assert_array_equal(same.ac_mw, plain.ac_mw)
    dark = hourly_pv(solar, poa_retention=np.zeros(len(plain.ac_mw)))
    assert float(dark.ac_mw.max()) <= 0.0
    half = hourly_pv(solar, poa_retention=np.full(len(plain.ac_mw), 0.5))
    assert 0.4 * plain.annual_mwh < half.annual_mwh < 0.55 * plain.annual_mwh
    with pytest.raises(ValueError, match="shape"):
        hourly_pv(solar, poa_retention=np.ones(10))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        hourly_pv(solar, poa_retention=np.full(len(plain.ac_mw), 1.5))


def test_source_caches_one_result_per_packing() -> None:
    cfg = _cfg()
    src = pats.ArrayShadingSource(cfg=cfg, turbine_en=(0.0, 0.0))
    solar = _solar()
    packing = [(-3.0, 10.0, 3.0, 14.0), (20.0, 10.0, 26.0, 14.0)]
    pats._STEPS_CACHE[
        (
            solar.latitude,
            solar.longitude,
            solar.timezone,
            solar.altitude_m,
            solar.tilt_deg,
            solar.azimuth_deg,
            str(solar.tmy_path),
            cfg.substeps_per_hour,
        )
    ] = _steps([45.0], [180.0], [500.0], [800.0])
    first = src.shading(packing, solar)
    assert src.shading(list(packing), solar) is first
    keep = src.retention(packing, 1, solar)
    assert keep == pytest.approx([1.0 - 500.0 / 800.0])
    report = src.report(packing, 2, solar)
    assert report["tables"] == 2 and report["electrical_mismatch_multiplier"] == 1.0
    assert math.isclose(report["optical_loss"], 250.0 / 800.0)


# ---------------------------------------------------------------------------
# #1520 lane findings carried to this PR
# ---------------------------------------------------------------------------
def _ray_hits_disc(
    points: np.ndarray, sun: np.ndarray, height: float, radius: float, yaw_deg: float
) -> np.ndarray:
    """Independent ray trace: does the ray from each ground point to the sun cross the disc?

    The disc is vertical, centred on the hub at ``height``, with its axis (normal) pointing
    to azimuth ``yaw_deg``: n = (sin yaw, cos yaw, 0) in (east, north, up).
    """
    yaw = math.radians(yaw_deg)
    n = np.array([math.sin(yaw), math.cos(yaw), 0.0])
    hub = np.array([0.0, 0.0, height])
    p3 = np.column_stack([points, np.zeros(len(points))])
    denom = float(sun @ n)
    t = ((hub - p3) @ n) / denom
    hit = p3 + t[:, None] * sun[None, :]
    return (t > 0) & (np.linalg.norm(hit - hub, axis=1) <= radius)


@pytest.mark.parametrize(
    ("sun_az", "sun_el", "yaw"),
    [
        (120.0, 35.0, 120.0),
        (120.0, 35.0, 60.0),
        (250.0, 20.0, 200.0),
        (60.0, 60.0, 75.0),
    ],
)
def test_yaw_convention_matches_a_ray_trace_for_an_oblique_sun(
    sun_az: float, sun_el: float, yaw: float
) -> None:
    # #1520 domain finding D-5: a mirrored yaw convention passed every #1520 test. With an
    # oblique sun and yaw, the mirrored disc casts a different ellipse, so this pins the
    # convention against a ray trace that shares no code with rotor_shadow_mask.
    sun = ts.sun_unit_vectors(np.array([sun_el]), np.array([sun_az]))[0]
    height, radius = HUB - PANEL, ROTOR / 2.0
    rng = np.random.default_rng(11)
    centre = -height * sun[:2] / sun[2]
    pts = centre + rng.uniform(-260.0, 260.0, size=(6000, 2))
    want = _ray_hits_disc(pts, sun, height, radius, yaw)
    got = ts.rotor_shadow_mask(pts, sun, height, radius, yaw)
    assert want.sum() > 200  # the disc casts a real shadow in every case
    # Points within a hair of the rim may round either way.
    assert (want != got).mean() < 1e-3
    mirrored = ts.rotor_shadow_mask(pts, sun, height, radius, -yaw)
    if (yaw % 90.0) != 0.0:
        assert (want != mirrored).mean() > 0.02


def test_blades_take_only_the_beam_the_tower_left() -> None:
    # #1520 assurance finding A-1: a point under both shadows loses its beam once.
    centre_n = HUB - PANEL
    half = TOWER_W / 2.0
    under_both = (-half * 0.5, centre_n - 5.0, half * 0.5, centre_n - 1.0)
    sh = pats.table_shading(
        [under_both],
        (0.0, 0.0),
        _solar(),
        _cfg(
            yaw_deg=(0.0,)
        ),  # the disc faces the southern sun and covers the strip's end
        steps=_steps([45.0], [180.0], [1000.0], [1200.0]),
    )
    assert sh.cum_removed_wh[1, 0] == pytest.approx(1000.0)  # not 1000 + 40
    assert sh.tower_wh == pytest.approx([1000.0]) and sh.rotor_wh == pytest.approx(
        [0.0]
    )
    acc = ts.accumulate_shading(
        pats.table_sample_points([under_both], (0.0, 0.0), (2, 2)),
        np.array([45.0]),
        np.array([180.0]),
        np.array([1000.0]),
        np.array([1200.0]),
        hub_height_m=HUB - PANEL,
        rotor_radius_m=ROTOR / 2.0,
        tower_diameter_m=TOWER_W,
        blade_solidity=0.04,
        yaw_samples=4,
        min_sun_elevation_deg=1.0,
    )
    assert (acc.tower_wh + acc.rotor_high_wh).max() == pytest.approx(1000.0)
    assert (acc.tower_wh + acc.rotor_low_wh).max() == pytest.approx(1000.0)


@pytest.mark.parametrize("bad", [2.7, True, "3", None])
def test_whole_number_inputs_are_not_truncated(bad: Any) -> None:
    # #1520 assurance finding A-2: int() would turn 2.7 into 2 and true into 1.
    with pytest.raises((TypeError, ValueError), match="whole number"):
        ts.strict_int(bad, "x")
    assert ts.strict_int(4, "x") == 4 and ts.strict_int(4.0, "x") == 4
    turbine = {"hub_height_m": HUB, "rotor_diameter_m": ROTOR}
    with pytest.raises((TypeError, ValueError), match="whole number"):
        pats.ArrayShadingConfig.from_mapping(
            _block(samples_per_table_ew=bad), turbine=turbine, read_text=_read
        )


def test_the_1520_scenario_parser_refuses_truncation_and_a_non_mapping_block() -> None:
    scen = yaml.safe_load(
        (REPO_ROOT / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml").read_text()
    )
    solar = scen["resource"]["solar"]
    for block, err in (
        ([], TypeError),
        ({"yaw_samples": 2.9}, ValueError),
        ({"substeps_per_hour": True}, TypeError),
        (
            {"array": {"turbines_within_array": 2.7, "land_area_m2": 1.0e5}},
            ValueError,
        ),
        ({"array": {"turbines_within_array": True, "land_area_m2": 1.0e5}}, TypeError),
    ):
        solar["turbine_shading"] = block
        with pytest.raises(err):
            ts.TurbineShadingConfig.from_scenario(scen)
    solar["turbine_shading"] = {
        "array": {"turbines_within_array": 2.0, "land_area_m2": 1.0e5}
    }
    assert ts.TurbineShadingConfig.from_scenario(scen).turbines_within_array == 2
