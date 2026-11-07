"""Tests for solar_resource.turbine_shading (#1518).

The geometry tests use closed-form shadow shapes as the oracle: a tower shadow is a strip
``h / tan(elevation)`` long, a disc facing the sun casts an ellipse with semi-axes ``R`` and
``R / sin(elevation)``, and a vertical disc facing the sun's azimuth casts one with
``R`` and ``R / tan(elevation)``. None of these come from the module under test. The
end-to-end tests need pvlib (the ``[solar]`` extra) and use coarse settings for speed.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from solar_resource.loss_model import (
    DEFAULT_SOLAR_LOSS_TAXONOMY,
    default_solar_loss_taxonomy,
)
from solar_resource.pv_producer import SolarResourceConfig
from solar_resource.turbine_shading import (
    TurbineShadingConfig,
    accumulate_shading,
    compute_turbine_shading,
    rotor_shadow_mask,
    summarise_shading,
    sun_unit_vectors,
    tower_shadow_mask,
)

REPO = Path(__file__).resolve().parents[2]
HYBRID = REPO / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml"
WIND_ONLY = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


def _pts(*xy: tuple[float, float]) -> np.ndarray:
    return np.array(xy, dtype=float)


def _sun(elevation_deg: float, azimuth_deg: float) -> np.ndarray:
    return sun_unit_vectors(np.array([elevation_deg]), np.array([azimuth_deg]))[0]


# ─────────────────────────────── geometry ────────────────────────────────


class TestSunVectors:
    def test_cardinal_directions(self) -> None:
        east = _sun(0.0, 90.0)
        south = _sun(0.0, 180.0)
        zenith = _sun(90.0, 0.0)
        np.testing.assert_allclose(east, [1.0, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(south, [0.0, -1.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(zenith, [0.0, 0.0, 1.0], atol=1e-12)

    def test_unit_length(self) -> None:
        vecs = sun_unit_vectors(
            np.array([5.0, 33.0, 71.0]), np.array([12.0, 200.0, 359.0])
        )
        np.testing.assert_allclose(np.linalg.norm(vecs, axis=1), 1.0)


class TestTowerShadow:
    H, W, EL = 100.0, 6.0, 30.0
    L = H / math.tan(math.radians(EL))  # closed-form shadow length

    def test_strip_points_away_from_sun_with_closed_form_length(self) -> None:
        sun = _sun(self.EL, 90.0)  # sun in the east, shadow to the west
        pts = _pts(
            (-(self.L - 0.5), 0.0),  # just inside the tip
            (-(self.L + 0.5), 0.0),  # just past the tip
            (5.0, 0.0),  # on the sunward side
            (-10.0, self.W / 2 - 0.1),  # just inside the edge
            (-10.0, self.W / 2 + 0.1),  # just outside the edge
        )
        mask = tower_shadow_mask(pts, sun, self.H, self.W)
        assert mask.tolist() == [True, False, False, True, False]

    def test_no_strip_with_sun_overhead_or_down(self) -> None:
        pts = _pts((0.5, 0.5), (-3.0, 0.0))
        assert not tower_shadow_mask(pts, _sun(90.0, 0.0), self.H, self.W).any()
        assert not tower_shadow_mask(pts, _sun(-5.0, 90.0), self.H, self.W).any()


class TestRotorShadow:
    H, R, EL = 100.0, 40.0, 40.0

    def _centre(self) -> float:
        # Sun due south: the hub shadow falls due north at H / tan(elevation).
        return self.H / math.tan(math.radians(self.EL))

    def test_sun_facing_disc_casts_r_by_r_over_sin_ellipse(self) -> None:
        sun = _sun(self.EL, 180.0)
        c = self._centre()
        along = self.R / math.sin(math.radians(self.EL))
        inside = _pts(
            (0.0, c + 0.999 * along), (0.0, c - 0.999 * along), (0.999 * self.R, c)
        )
        outside = _pts(
            (0.0, c + 1.001 * along), (0.0, c - 1.001 * along), (1.001 * self.R, c)
        )
        assert rotor_shadow_mask(inside, sun, self.H, self.R, None).all()
        assert not rotor_shadow_mask(outside, sun, self.H, self.R, None).any()

    def test_vertical_disc_facing_sun_azimuth_casts_r_by_r_over_tan_ellipse(
        self,
    ) -> None:
        sun = _sun(self.EL, 180.0)
        c = self._centre()
        along = self.R / math.tan(math.radians(self.EL))
        for yaw in (0.0, 180.0):  # axis north-south: disc faces the sun's azimuth
            inside = _pts((0.0, c + 0.999 * along), (0.999 * self.R, c))
            outside = _pts((0.0, c + 1.001 * along), (1.001 * self.R, c))
            assert rotor_shadow_mask(inside, sun, self.H, self.R, yaw).all()
            assert not rotor_shadow_mask(outside, sun, self.H, self.R, yaw).any()

    def test_edge_on_disc_casts_no_area(self) -> None:
        sun = _sun(self.EL, 180.0)
        grid = np.stack(
            np.meshgrid(np.arange(-60, 61, 2.0), np.arange(0, 200, 2.0)), -1
        )
        pts = grid.reshape(-1, 2).astype(float)
        assert not rotor_shadow_mask(pts, sun, self.H, self.R, 90.0).any()


class TestAccumulation:
    def _grid(self, half: float, step: float) -> np.ndarray:
        axis = np.arange(-half, half + step / 2, step)
        xx, yy = np.meshgrid(axis, axis)
        return np.column_stack([xx.ravel(), yy.ravel()])

    def test_single_step_footprints_match_closed_form_areas(self) -> None:
        h, r, w, sigma, el = 50.0, 20.0, 4.0, 0.05, 45.0
        step = 0.5
        pts = self._grid(130.0, step)
        acc = accumulate_shading(
            pts,
            np.array([el]),
            np.array([180.0]),
            np.array([800.0]),
            np.array([1000.0]),
            hub_height_m=h,
            rotor_radius_m=r,
            tower_diameter_m=w,
            blade_solidity=sigma,
            yaw_samples=4,
            min_sun_elevation_deg=1.0,
        )
        cell = step**2
        tower_area = w * h / math.tan(math.radians(el))
        ellipse_area = math.pi * r * r / math.sin(math.radians(el))
        assert acc.tower_wh.sum() * cell / 800.0 == pytest.approx(tower_area, rel=0.03)
        # The blades take beam only outside the tower strip, so the sun-facing rotor's
        # footprint is the ellipse less the part of the strip inside it. The strip runs
        # due north from the tower to the hub's shadow, the ellipse's centre (0, c), whose
        # north-south semi-axis is b and east-west a; integrate the strip's width inside
        # the ellipse over its last b metres.
        a_ew, b_ns = r, r / math.sin(math.radians(el))
        c = h / math.tan(math.radians(el))
        ys = np.linspace(c - b_ns, c, 200001)
        widths = np.minimum(
            w, 2.0 * a_ew * np.sqrt(np.clip(1 - ((ys - c) / b_ns) ** 2, 0, 1))
        )
        overlap = float(np.trapezoid(widths, ys))
        assert overlap > 0.0
        assert acc.rotor_high_wh.sum() * cell / (800.0 * sigma) == pytest.approx(
            ellipse_area - overlap, rel=0.03
        )
        # No point loses more than its beam.
        removed = acc.tower_wh + acc.rotor_high_wh
        assert removed.max() <= 800.0 + 1e-9
        # The yaw-averaged disc is never larger than the sun-facing one.
        assert acc.rotor_low_wh.sum() <= acc.rotor_high_wh.sum()
        assert acc.poa_global_wh == 1000.0 and acc.poa_beam_wh == 800.0

    def test_low_sun_and_zero_beam_steps_are_ignored(self) -> None:
        pts = self._grid(60.0, 2.0)
        acc = accumulate_shading(
            pts,
            np.array([0.5, 30.0]),
            np.array([90.0, 90.0]),
            np.array([500.0, 0.0]),
            np.array([600.0, 100.0]),
            hub_height_m=50.0,
            rotor_radius_m=20.0,
            tower_diameter_m=4.0,
            blade_solidity=0.05,
            yaw_samples=2,
            min_sun_elevation_deg=1.0,
        )
        assert not acc.tower_wh.any() and not acc.rotor_low_wh.any()
        assert acc.poa_global_wh == 700.0

    def test_mirror_symmetry_between_hemispheres(self) -> None:
        # Reflecting the sun's azimuth north-south must reflect the loss field. This is
        # the property that lets one implementation serve both hemispheres.
        step, half = 4.0, 200.0
        pts = self._grid(half, step)
        mirrored = pts * np.array([1.0, -1.0])
        el = np.array([20.0, 45.0, 70.0, 35.0])
        az = np.array([100.0, 150.0, 200.0, 260.0])
        common = dict(
            hub_height_m=80.0,
            rotor_radius_m=35.0,
            tower_diameter_m=4.0,
            blade_solidity=0.04,
            yaw_samples=4,
            min_sun_elevation_deg=1.0,
        )
        beam = np.full(4, 500.0)
        glob = np.full(4, 700.0)
        north = accumulate_shading(pts, el, az, beam, glob, **common)
        south = accumulate_shading(
            mirrored, el, (180.0 - az) % 360.0, beam, glob, **common
        )
        np.testing.assert_allclose(north.tower_wh, south.tower_wh)
        np.testing.assert_allclose(north.rotor_high_wh, south.rotor_high_wh)
        np.testing.assert_allclose(north.rotor_low_wh, south.rotor_low_wh)


# ─────────────────────────── configuration ───────────────────────────────


class TestConfigFromYaml:
    def test_reads_turbine_and_solar_blocks_from_the_hybrid_scenario(self) -> None:
        sc = _load(HYBRID)
        cfg = TurbineShadingConfig.from_scenario(sc)
        assert cfg.hub_height_m == float(sc["turbine"]["hub_height_m"])
        assert cfg.rotor_diameter_m == float(sc["turbine"]["rotor_diameter_m"])
        solar = sc["resource"]["solar"]
        assert cfg.solar.latitude == solar["latitude"]
        assert cfg.solar.tilt_deg == solar["tilt_deg"]
        assert cfg.solar.azimuth_deg == solar["azimuth_deg"]
        assert cfg.solar.tmy_path == solar["tmy_path"]
        # Method defaults come from config/defaults.yaml and scale with the rotor.
        assert cfg.tower_diameter_m == pytest.approx(0.0625 * cfg.rotor_diameter_m / 2)
        assert cfg.grid_extent_m == pytest.approx(3.5 * cfg.rotor_diameter_m)
        assert cfg.turbines_within_array is None and cfg.array_land_area_m2 is None

    def test_a_wind_only_scenario_says_what_is_missing(self) -> None:
        with pytest.raises(KeyError, match="resource.solar"):
            TurbineShadingConfig.from_scenario(_load(WIND_ONLY))

    def test_overrides_and_array_roll_up_inputs(self) -> None:
        sc = _load(HYBRID)
        sc["resource"]["solar"]["turbine_shading"] = {
            "tower_diameter_m": 5.0,
            "blade_solidity": 0.035,
            "array": {
                "turbines_within_array": 3,
                "land_use_mwp_per_ha": 1.0,
                "setback_m": 75,
            },
        }
        cfg = TurbineShadingConfig.from_scenario(sc)
        assert cfg.tower_diameter_m == 5.0 and cfg.blade_solidity == 0.035
        dc = float(sc["resource"]["solar"]["dc_capacity_mw"])
        assert cfg.array_land_area_m2 == pytest.approx(dc / 1.0 * 10_000)
        assert cfg.turbines_within_array == 3
        assert 75.0 in cfg.setbacks_m  # the array setback is always computed

    @pytest.mark.parametrize(
        "block, error",
        [
            ({"blade_soldity": 0.04}, KeyError),
            ({"array": {"turbines_within_array": 2}}, ValueError),
            (
                {
                    "array": {
                        "turbines_within_array": 2,
                        "land_area_m2": 1e5,
                        "land_use_mwp_per_ha": 1.0,
                    }
                },
                ValueError,
            ),
            ({"array": {"land_area_m2": 1e5}}, KeyError),
            (
                {"array": {"turbines_within_array": 2, "land_area_m2": 1e5, "x": 1}},
                KeyError,
            ),
            ({"blade_solidity": 0.0}, ValueError),
        ],
    )
    def test_bad_blocks_fail_loud(self, block: dict[str, Any], error: type) -> None:
        sc = _load(HYBRID)
        sc["resource"]["solar"]["turbine_shading"] = block
        with pytest.raises(error):
            TurbineShadingConfig.from_scenario(sc)

    def test_pv_producer_still_accepts_the_block(self) -> None:
        sc = _load(HYBRID)
        sc["resource"]["solar"]["turbine_shading"] = {"blade_solidity": 0.04}
        assert SolarResourceConfig.from_scenario(sc).tilt_deg == 8.0

    def test_loss_taxonomy_carries_the_line(self) -> None:
        assert DEFAULT_SOLAR_LOSS_TAXONOMY["turbine_shading_pct"] == "reduction"
        assert default_solar_loss_taxonomy()["turbine_shading_pct"] == "reduction"


class TestRollUp:
    def test_plant_loss_is_turbines_times_footprint_over_land(self) -> None:
        solar = SolarResourceConfig(
            latitude=0.0, longitude=0.0, annual_ghi_kwh_m2=1800.0, dc_capacity_mw=10.0
        )
        cfg = TurbineShadingConfig(
            solar=solar,
            hub_height_m=100.0,
            rotor_diameter_m=100.0,
            tower_diameter_m=4.0,
            blade_solidity=0.04,
            panel_height_m=1.0,
            yaw_samples=2,
            grid_step_m=10.0,
            grid_extent_m=100.0,
            substeps_per_hour=1,
            min_sun_elevation_deg=1.0,
            setbacks_m=(0.0, 50.0),
            distance_bands_m=(0.0, 50.0, 100.0),
            turbines_within_array=4,
            array_land_area_m2=200_000.0,
            array_setback_m=50.0,
        )
        dist = np.array([20.0, 60.0, 80.0])
        from solar_resource.turbine_shading import _Accumulated

        acc = _Accumulated(
            tower_wh=np.array([100.0, 50.0, 10.0]),
            rotor_high_wh=np.array([40.0, 30.0, 20.0]),
            rotor_low_wh=np.array([20.0, 10.0, 5.0]),
            poa_global_wh=1000.0,
            poa_beam_wh=700.0,
        )
        res = summarise_shading(acc, dist, cfg, "synthetic")
        fp = res.footprint(50.0)
        # Beyond 50 m: tower (50+10), rotor low (10+5), high (30+20); cell 100 m²; /1000.
        assert fp.tower_m2 == pytest.approx(6.0)
        assert fp.total_low_m2 == pytest.approx(7.5)
        assert fp.total_high_m2 == pytest.approx(11.0)
        assert res.turbine_shading_pct_low == pytest.approx(100 * 4 * 7.5 / 200_000)
        assert res.turbine_shading_pct_high == pytest.approx(100 * 4 * 11.0 / 200_000)
        assert res.array_status == "RUN"
        inner = res.bands[0]
        assert inner.tower_loss_pct == pytest.approx(10.0)
        assert inner.total_high_pct == pytest.approx(14.0)

    def test_roll_up_is_not_run_without_the_array_block(self) -> None:
        solar = SolarResourceConfig(
            latitude=0.0, longitude=0.0, annual_ghi_kwh_m2=1800.0, dc_capacity_mw=10.0
        )
        cfg = TurbineShadingConfig(
            solar=solar,
            hub_height_m=100.0,
            rotor_diameter_m=100.0,
            tower_diameter_m=4.0,
            blade_solidity=0.04,
            panel_height_m=1.0,
            yaw_samples=2,
            grid_step_m=10.0,
            grid_extent_m=100.0,
            substeps_per_hour=1,
            min_sun_elevation_deg=1.0,
            setbacks_m=(0.0,),
            distance_bands_m=(0.0, 100.0),
        )
        from solar_resource.turbine_shading import _Accumulated

        acc = _Accumulated(
            tower_wh=np.array([1.0]),
            rotor_high_wh=np.array([1.0]),
            rotor_low_wh=np.array([1.0]),
            poa_global_wh=10.0,
            poa_beam_wh=5.0,
        )
        res = summarise_shading(acc, np.array([30.0]), cfg, "synthetic")
        assert res.array_status.startswith("NOT-RUN")
        assert "turbines_within_array" in res.array_status
        assert (
            res.turbine_shading_pct_low is None and res.turbine_shading_pct_high is None
        )
        assert any("Optical floor" in c for c in res.caveats)


# ─────────────────────────── end to end (pvlib) ───────────────────────────


@pytest.fixture(scope="module")
def pvlib_available() -> None:
    pytest.importorskip("pvlib")


def _coarse(cfg: TurbineShadingConfig) -> TurbineShadingConfig:
    return replace(cfg, grid_step_m=20.0, substeps_per_hour=1, yaw_samples=2)


@pytest.mark.usefixtures("pvlib_available")
class TestEndToEnd:
    def test_hybrid_scenario_runs_unchanged_and_decays_with_distance(self) -> None:
        cfg = _coarse(TurbineShadingConfig.from_scenario(_load(HYBRID)))
        res = compute_turbine_shading(cfg)
        assert res.resource_basis == "TMY"
        assert res.array_status.startswith("NOT-RUN")
        highs = [b.total_high_pct for b in res.bands]
        assert highs == sorted(highs, reverse=True)
        assert 0.0 < highs[-1] < highs[0] < 10.0
        for band in res.bands:
            assert 0.0 <= band.total_low_pct <= band.total_high_pct
        totals = [f.total_high_m2 for f in res.footprints]
        assert totals == sorted(totals, reverse=True)
        assert res.poa_beam_kwh_m2 < res.poa_global_kwh_m2

    def test_southern_hemisphere_site_with_equator_facing_modules_is_comparable(
        self,
    ) -> None:
        # Latitude negated and modules turned to face the equator. The answer is not an exact
        # mirror end to end: pvlib's Ineichen model looks up the Linke turbidity climatology at
        # the site itself, so the beam/diffuse split differs between the two latitudes (about
        # 12% on the tower footprint here). The exact geometric mirror is pinned on identical
        # irradiance in TestAccumulation.test_mirror_symmetry_between_hemispheres; this test
        # pins that nothing in the YAML-to-result path assumes a northern-hemisphere site.
        base = _load(HYBRID)
        solar = dict(base["resource"]["solar"])
        solar.pop("tmy_path")
        north = {**base, "resource": {**base["resource"], "solar": solar}}
        south_solar = {**solar, "latitude": -solar["latitude"], "azimuth_deg": 0.0}
        south = {**base, "resource": {**base["resource"], "solar": south_solar}}
        res_n = compute_turbine_shading(
            _coarse(TurbineShadingConfig.from_scenario(north))
        )
        res_s = compute_turbine_shading(
            _coarse(TurbineShadingConfig.from_scenario(south))
        )
        assert res_n.resource_basis == res_s.resource_basis == "clear-sky"
        assert res_s.poa_global_kwh_m2 == pytest.approx(
            res_n.poa_global_kwh_m2, rel=0.05
        )
        for fp_n, fp_s in zip(res_n.footprints, res_s.footprints, strict=True):
            assert fp_s.total_high_m2 == pytest.approx(fp_n.total_high_m2, rel=0.20)
            assert fp_s.tower_m2 == pytest.approx(fp_n.tower_m2, rel=0.20)
        for band_n, band_s in zip(res_n.bands, res_s.bands, strict=True):
            assert band_s.total_high_pct == pytest.approx(
                band_n.total_high_pct, rel=0.20
            )
