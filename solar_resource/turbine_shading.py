"""Wind-turbine shadow loss on co-located PV (optional ``[solar]`` extra).

Estimates how much plane-of-array (POA) irradiance the tower and rotor of a wind turbine
remove from photovoltaic modules placed around it, over a full year, at any location. It is
the generation-loss counterpart of the residential shadow-flicker screen: what matters here
is beam irradiance lost on the modules, not hours of nuisance at a window.

Inputs come only from existing scenario YAML, so the same code serves any site:

* ``turbine.rotor_diameter_m`` and ``turbine.hub_height_m`` give the machine;
* the ``resource.solar`` block (read through
  :meth:`solar_resource.pv_producer.SolarResourceConfig.from_scenario`) gives latitude,
  longitude, timezone, altitude, module tilt and azimuth, and the irradiance year — the
  frozen hourly TMY when ``tmy_path`` is set, else the clear-sky year scaled to
  ``annual_ghi_kwh_m2`` exactly as the PV producer builds it;
* the optional ``resource.solar.turbine_shading`` block overrides the method defaults held
  in ``config/defaults.yaml`` (``defaults.solar_resource.turbine_shading``) and may declare
  an ``array`` sub-block for the plant-level roll-up.

Method (all vector geometry, so it holds in either hemisphere and for any module azimuth):

1. For each sub-hourly step with the sun above ``min_sun_elevation_deg``, pvlib gives the
   sun's elevation and azimuth and the beam and global POA on an unshaded module.
2. The tower is projected onto the module plane (a horizontal plane at ``panel_height_m``)
   as a strip ``tower_diameter_m`` wide and ``(hub height - panel height) / tan(elevation)``
   long, pointing away from the sun.
3. The rotor disc is projected along the sun ray onto the same plane, which gives an
   ellipse. Two orientations bracket the yaw: ``high`` keeps the disc facing the sun (DNV
   WindFarmer's conservative sphere case; a horizontal-axis rotor cannot tilt to face a
   high sun, so this exceeds the attainable maximum, which is the disc yawed to the sun's
   azimuth); ``low`` averages ``yaw_samples`` yaw angles spread evenly over 180 degrees
   (wind from every direction equally often). Inside the ellipse the turning blades remove
   ``blade_solidity`` of the beam on average, but only where the tower has not already
   taken it, so a point under both shadows loses its beam once.
4. Beam POA removed, summed over the year and divided by the annual global POA, is the
   optical loss at each grid point around the turbine.

Outputs (:class:`TurbineShadingResult`): the loss averaged over distance bands, the
loss-equivalent PV land area per turbine for each setback (layout-independent), and, when
``resource.solar.turbine_shading.array`` declares the PV land area and the number of
turbines standing inside the array, a plant-level ``turbine_shading_pct`` range that a
scenario can carry in ``resource.solar.losses``. Without that block the roll-up is NOT-RUN
and names the missing keys (CASPER: say what was not computed).

Scope and limits, stated on every result:

* Optical floor only. Moving blade shadows also disturb string electrical behaviour and
  inverter MPPT, so measured losses can be several times the optical figure (Dekker et al.
  2023, J. Renewable Sustainable Energy 15, 063703). No electrical multiplier is applied.
* Diffuse light and circumsolar irradiance are treated as unshaded. Terrain is flat. The
  nacelle, hub overhang and tower taper are ignored. Energy is taken as proportional to
  POA, so clipping and temperature interactions are not resolved.
* The per-turbine footprint assumes PV covers all land around the turbine out to the grid
  extent, which is an upper bound for a turbine on the edge of an array.

Nothing in the finance path reads this module; carrying a non-zero
``turbine_shading_pct`` in a committed scenario moves the solar P50 and is a USER GATE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
from numpy.typing import NDArray

from solar_resource.pv_producer import SolarResourceConfig, _load_tmy, _require_pvlib

__all__ = [
    "CAVEATS",
    "ShadingBand",
    "ShadingFootprint",
    "TurbineShadingConfig",
    "TurbineShadingResult",
    "accumulate_shading",
    "compute_turbine_shading",
    "irradiance_steps",
    "rotor_shadow_mask",
    "strict_int",
    "summarise_shading",
    "sun_unit_vectors",
    "tower_shadow_mask",
    "turbine_shading_from_scenario",
]

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"

#: Keys of ``resource.solar.turbine_shading`` that override a method default.
_METHOD_KEYS: tuple[str, ...] = (
    "tower_diameter_m",
    "tower_diameter_to_rotor_radius",
    "blade_solidity",
    "panel_height_m",
    "yaw_samples",
    "grid_step_m",
    "grid_extent_rotor_diameters",
    "substeps_per_hour",
    "min_sun_elevation_deg",
    "setbacks_m",
    "distance_bands_m",
)
#: Keys of ``resource.solar.turbine_shading.array`` (the plant roll-up).
_ARRAY_KEYS: tuple[str, ...] = (
    "turbines_within_array",
    "land_area_m2",
    "land_use_mwp_per_ha",
    "setback_m",
)

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def strict_int(value: Any, name: str) -> int:
    """A whole-number config value, refusing what ``int()`` would silently change.

    Accepts an ``int`` or an integral ``float`` (``4.0``); rejects booleans, fractional
    numbers (``2.7`` would truncate to 2) and anything else.

    Raises:
        TypeError: If ``value`` is a boolean or not a number.
        ValueError: If ``value`` is not a whole number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a whole number, got {value!r}")
    if isinstance(value, float) and not (math.isfinite(value) and value.is_integer()):
        raise ValueError(f"{name} must be a whole number, got {value!r}")
    return int(value)


@lru_cache(maxsize=1)
def _method_defaults() -> dict[str, Any]:
    """Method defaults from ``config/defaults.yaml`` (config-first; fails loud if absent)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        block = data["defaults"]["solar_resource"]["turbine_shading"]
    except (KeyError, TypeError) as exc:
        raise KeyError(
            "config/defaults.yaml has no defaults.solar_resource.turbine_shading block; "
            "the turbine-shading method defaults live there."
        ) from exc
    if not isinstance(block, Mapping):
        raise TypeError("defaults.solar_resource.turbine_shading must be a mapping")
    unknown = sorted(set(block) - set(_METHOD_KEYS))
    if unknown:
        raise KeyError(
            f"defaults.solar_resource.turbine_shading has unknown keys: {unknown}"
        )
    return dict(block)


# ─────────────────────────────────────────────────────────────────────────────
# Pure geometry (numpy only; no pvlib) — every function works in local east-north-up
# metres with the tower base at the origin and the module plane at height zero.
# ─────────────────────────────────────────────────────────────────────────────


def sun_unit_vectors(elevation_deg: FloatArray, azimuth_deg: FloatArray) -> FloatArray:
    """Unit vectors pointing at the sun, shape ``(n, 3)`` as (east, north, up).

    Args:
        elevation_deg: Sun elevation above the horizon, degrees.
        azimuth_deg: Sun azimuth, degrees clockwise from north (pvlib convention).

    Returns:
        Array of unit vectors, one row per input.
    """
    el = np.radians(np.asarray(elevation_deg, dtype=float))
    az = np.radians(np.asarray(azimuth_deg, dtype=float))
    return np.column_stack(
        [np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)]
    )


def tower_shadow_mask(
    points: FloatArray, sun: FloatArray, tower_height_m: float, tower_diameter_m: float
) -> BoolArray:
    """Which points lie in the tower's shadow for one sun position.

    Args:
        points: ``(m, 2)`` east/north coordinates on the module plane, metres.
        sun: Unit vector to the sun (east, north, up), with ``up > 0``.
        tower_height_m: Tower height above the module plane, metres.
        tower_diameter_m: Width of the shadow strip, metres.

    Returns:
        Boolean mask of length ``m``.
    """
    horiz = math.hypot(float(sun[0]), float(sun[1]))
    if horiz < 1e-9 or sun[2] <= 0.0:  # sun overhead or below the horizon: no strip
        return np.zeros(len(points), dtype=bool)
    away = -np.array([sun[0], sun[1]]) / horiz
    across = np.array([-away[1], away[0]])
    length = tower_height_m * horiz / float(sun[2])
    along = points @ away
    off = np.abs(points @ across)
    result: BoolArray = (
        (along >= 0.0) & (along <= length) & (off <= tower_diameter_m / 2.0)
    )
    return result


def _project(vec: FloatArray, sun: FloatArray) -> FloatArray:
    """Project a 3-D vector onto the module plane along the sun ray."""
    return np.array(
        [vec[0] - vec[2] * sun[0] / sun[2], vec[1] - vec[2] * sun[1] / sun[2]]
    )


def rotor_shadow_mask(
    points: FloatArray,
    sun: FloatArray,
    hub_height_m: float,
    rotor_radius_m: float,
    yaw_deg: Optional[float] = None,
) -> BoolArray:
    """Which points lie inside the rotor disc's shadow ellipse for one sun position.

    Args:
        points: ``(m, 2)`` east/north coordinates on the module plane, metres.
        sun: Unit vector to the sun (east, north, up), with ``up > 0``.
        hub_height_m: Hub height above the module plane, metres.
        rotor_radius_m: Rotor radius, metres.
        yaw_deg: Azimuth of the rotor axis, degrees clockwise from north. ``None`` turns the
            disc to face the sun (the conservative sphere case; larger than any yaw of a
            horizontal-axis rotor can reach).

    Returns:
        Boolean mask of length ``m``. An edge-on disc casts no area and returns all False.
    """
    if sun[2] <= 0.0:
        return np.zeros(len(points), dtype=bool)
    up = np.array([0.0, 0.0, 1.0])
    if yaw_deg is None:
        normal = np.asarray(sun, dtype=float)
        first = np.cross(normal, up)
        if np.linalg.norm(first) < 1e-9:  # sun at the zenith: any horizontal axis works
            first = np.array([1.0, 0.0, 0.0])
        first = first / np.linalg.norm(first)
        second = np.cross(normal, first)
    else:
        yaw = math.radians(yaw_deg)
        first = np.array(
            [math.cos(yaw), -math.sin(yaw), 0.0]
        )  # horizontal, in the disc
        second = up
    basis = np.column_stack([_project(first, sun), _project(second, sun)])
    if abs(float(np.linalg.det(basis))) < 1e-9:
        return np.zeros(len(points), dtype=bool)
    centre = _project(np.array([0.0, 0.0, hub_height_m]), sun)
    coords = np.linalg.solve(basis, (points - centre).T)
    result: BoolArray = (coords**2).sum(axis=0) <= rotor_radius_m**2
    return result


@dataclass(frozen=True)
class _Accumulated:
    """Per-point beam energy removed, Wh/m², and the annual totals it is divided by."""

    tower_wh: FloatArray
    rotor_high_wh: FloatArray
    rotor_low_wh: FloatArray
    poa_global_wh: float
    poa_beam_wh: float


def accumulate_shading(
    points: FloatArray,
    elevation_deg: FloatArray,
    azimuth_deg: FloatArray,
    poa_beam_wh: FloatArray,
    poa_global_wh: FloatArray,
    *,
    hub_height_m: float,
    rotor_radius_m: float,
    tower_diameter_m: float,
    blade_solidity: float,
    yaw_samples: int,
    min_sun_elevation_deg: float,
) -> _Accumulated:
    """Sum the beam energy each point loses to the tower and rotor over a set of time steps.

    Heights are measured from the module plane. The arrays ``elevation_deg``,
    ``azimuth_deg``, ``poa_beam_wh`` and ``poa_global_wh`` are aligned per time step, with
    the irradiance already multiplied by the step length (Wh/m²).

    Returns:
        Per-point removed energy for the tower, the sun-facing rotor (``high``) and the
        yaw-averaged rotor (``low``), plus the annual beam and global POA totals.
    """
    elevation = np.asarray(elevation_deg, dtype=float)
    beam = np.asarray(poa_beam_wh, dtype=float)
    glob = np.asarray(poa_global_wh, dtype=float)
    suns = sun_unit_vectors(elevation, np.asarray(azimuth_deg, dtype=float))
    yaws = [180.0 * k / yaw_samples for k in range(yaw_samples)]
    tower = np.zeros(len(points))
    high = np.zeros(len(points))
    low = np.zeros(len(points))
    active = np.nonzero((elevation >= min_sun_elevation_deg) & (beam > 0.0))[0]
    for i in active:
        sun = suns[i]
        in_tower = tower_shadow_mask(points, sun, hub_height_m, tower_diameter_m)
        # The blades only take beam that the tower has not already taken, so a point
        # under both shadows loses its beam once, not more than once.
        open_sky = ~in_tower
        tower += beam[i] * in_tower
        high += (
            beam[i]
            * blade_solidity
            * (
                rotor_shadow_mask(points, sun, hub_height_m, rotor_radius_m, None)
                & open_sky
            )
        )
        hits = np.zeros(len(points))
        for yaw in yaws:
            hits += (
                rotor_shadow_mask(points, sun, hub_height_m, rotor_radius_m, yaw)
                & open_sky
            )
        low += beam[i] * blade_solidity * hits / yaw_samples
    return _Accumulated(
        tower_wh=tower,
        rotor_high_wh=high,
        rotor_low_wh=low,
        poa_global_wh=float(glob.sum()),
        poa_beam_wh=float(beam.sum()),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Configuration (read from scenario YAML) and results
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TurbineShadingConfig:
    """Typed inputs for :func:`compute_turbine_shading`, built from scenario YAML.

    Attributes:
        solar: The site, module geometry and irradiance year (``resource.solar``).
        hub_height_m: Turbine hub height above ground, metres (``turbine.hub_height_m``).
        rotor_diameter_m: Rotor diameter, metres (``turbine.rotor_diameter_m``).
        tower_diameter_m: Width of the tower shadow strip, metres. When the scenario gives
            none, it is ``tower_diameter_to_rotor_radius`` times the rotor radius.
        blade_solidity: Share of the swept disc the blades cover (0-1).
        panel_height_m: Mean module height above ground, metres.
        yaw_samples: Rotor yaw angles averaged for the ``low`` case.
        grid_step_m: Grid spacing around the turbine, metres.
        grid_extent_m: Half-width of the square grid, metres.
        substeps_per_hour: Sun positions evaluated per hour of the irradiance year.
        min_sun_elevation_deg: Steps with a lower sun are ignored.
        setbacks_m: Setbacks for which the per-turbine footprint is reported, metres.
        distance_bands_m: Band edges for the distance profile, metres (ascending).
        turbines_within_array: Turbines standing inside the PV array (roll-up), or None.
        array_land_area_m2: PV land area, m² (roll-up), or None.
        array_setback_m: Setback kept between towers and modules (roll-up), metres.
    """

    solar: SolarResourceConfig
    hub_height_m: float
    rotor_diameter_m: float
    tower_diameter_m: float
    blade_solidity: float
    panel_height_m: float
    yaw_samples: int
    grid_step_m: float
    grid_extent_m: float
    substeps_per_hour: int
    min_sun_elevation_deg: float
    setbacks_m: tuple[float, ...]
    distance_bands_m: tuple[float, ...]
    turbines_within_array: Optional[int] = None
    array_land_area_m2: Optional[float] = None
    array_setback_m: float = 0.0

    def __post_init__(self) -> None:
        checks = {
            "hub_height_m": self.hub_height_m > 0.0,
            "rotor_diameter_m": self.rotor_diameter_m > 0.0,
            "tower_diameter_m": self.tower_diameter_m > 0.0,
            "blade_solidity": 0.0 < self.blade_solidity <= 1.0,
            "panel_height_m": 0.0 <= self.panel_height_m < self.hub_height_m,
            "yaw_samples": self.yaw_samples >= 1,
            "grid_step_m": self.grid_step_m > 0.0,
            "grid_extent_m": self.grid_extent_m > self.grid_step_m,
            "substeps_per_hour": self.substeps_per_hour >= 1,
            "min_sun_elevation_deg": 0.0 <= self.min_sun_elevation_deg < 90.0,
            "array_setback_m": self.array_setback_m >= 0.0,
        }
        bad = [name for name, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"turbine shading inputs out of range: {bad}")
        if self.rotor_diameter_m / 2.0 >= self.hub_height_m - self.panel_height_m:
            raise ValueError("rotor tip would reach the module plane: check hub height")
        bands = self.distance_bands_m
        if len(bands) < 2 or any(
            later <= earlier for earlier, later in zip(bands, bands[1:], strict=False)
        ):
            raise ValueError(
                f"distance_bands_m must be ascending with 2+ edges: {bands}"
            )
        if any(s < 0.0 for s in self.setbacks_m):
            raise ValueError(f"setbacks_m must be non-negative: {self.setbacks_m}")
        if (self.turbines_within_array is None) != (self.array_land_area_m2 is None):
            raise ValueError(
                "array roll-up needs both turbines_within_array and a land area"
            )
        if self.turbines_within_array is not None and self.turbines_within_array < 0:
            raise ValueError("turbines_within_array must be >= 0")
        if self.array_land_area_m2 is not None and self.array_land_area_m2 <= 0.0:
            raise ValueError("array land area must be > 0")

    @classmethod
    def from_scenario(cls, scenario: Mapping[str, Any]) -> "TurbineShadingConfig":
        """Build from a scenario's ``turbine`` and ``resource.solar`` blocks.

        Raises:
            KeyError: a required key is missing, or a ``turbine_shading`` key is unknown.
            ValueError: a value is out of range or the array block is ambiguous.
        """
        turbine = scenario.get("turbine")
        if not isinstance(turbine, Mapping):
            raise KeyError(
                "scenario has no turbine block (needs rotor_diameter_m, hub_height_m)"
            )
        missing = [
            k for k in ("rotor_diameter_m", "hub_height_m") if turbine.get(k) is None
        ]
        if missing:
            raise KeyError(f"turbine block is missing: {missing}")
        solar = SolarResourceConfig.from_scenario(scenario)
        block_raw = scenario["resource"]["solar"].get("turbine_shading")
        if block_raw is None:
            block_raw = {}
        if not isinstance(block_raw, Mapping):
            raise TypeError("resource.solar.turbine_shading must be a mapping")
        block = dict(block_raw)
        array_raw = block.pop("array", None)
        unknown = sorted(set(block) - set(_METHOD_KEYS))
        if unknown:
            raise KeyError(
                f"resource.solar.turbine_shading has unknown keys: {unknown}; "
                f"valid keys: {sorted(_METHOD_KEYS) + ['array']}"
            )
        params = {**_method_defaults(), **block}
        rotor_d = float(turbine["rotor_diameter_m"])
        tower_d = params.get("tower_diameter_m")
        if tower_d is None:
            tower_d = float(params["tower_diameter_to_rotor_radius"]) * rotor_d / 2.0

        turbines_in: Optional[int] = None
        land_m2: Optional[float] = None
        setback = 0.0
        if array_raw is not None:
            if not isinstance(array_raw, Mapping):
                raise TypeError(
                    "resource.solar.turbine_shading.array must be a mapping"
                )
            bad_keys = sorted(set(array_raw) - set(_ARRAY_KEYS))
            if bad_keys:
                raise KeyError(
                    f"turbine_shading.array has unknown keys: {bad_keys}; "
                    f"valid keys: {sorted(_ARRAY_KEYS)}"
                )
            has_area = array_raw.get("land_area_m2") is not None
            has_use = array_raw.get("land_use_mwp_per_ha") is not None
            if has_area == has_use:
                raise ValueError(
                    "turbine_shading.array needs exactly one of land_area_m2 or "
                    "land_use_mwp_per_ha"
                )
            if array_raw.get("turbines_within_array") is None:
                raise KeyError("turbine_shading.array is missing turbines_within_array")
            turbines_in = strict_int(
                array_raw["turbines_within_array"],
                "turbine_shading.array.turbines_within_array",
            )
            if has_area:
                land_m2 = float(array_raw["land_area_m2"])
            else:
                density = float(array_raw["land_use_mwp_per_ha"])
                if density <= 0.0:
                    raise ValueError("land_use_mwp_per_ha must be > 0")
                land_m2 = solar.dc_capacity_mw / density * 10_000.0
            setback = float(array_raw.get("setback_m") or 0.0)

        setbacks = tuple(float(s) for s in params["setbacks_m"])
        if setback not in setbacks:
            setbacks = tuple(sorted(setbacks + (setback,)))
        return cls(
            solar=solar,
            hub_height_m=float(turbine["hub_height_m"]),
            rotor_diameter_m=rotor_d,
            tower_diameter_m=float(tower_d),
            blade_solidity=float(params["blade_solidity"]),
            panel_height_m=float(params["panel_height_m"]),
            yaw_samples=strict_int(params["yaw_samples"], "yaw_samples"),
            grid_step_m=float(params["grid_step_m"]),
            grid_extent_m=float(params["grid_extent_rotor_diameters"]) * rotor_d,
            substeps_per_hour=strict_int(
                params["substeps_per_hour"], "substeps_per_hour"
            ),
            min_sun_elevation_deg=float(params["min_sun_elevation_deg"]),
            setbacks_m=setbacks,
            distance_bands_m=tuple(float(b) for b in params["distance_bands_m"]),
            turbines_within_array=turbines_in,
            array_land_area_m2=land_m2,
            array_setback_m=setback,
        )


@dataclass(frozen=True)
class ShadingBand:
    """Optical loss averaged over a ring of land around the turbine, % of annual POA."""

    lower_m: float
    upper_m: float
    tower_loss_pct: float
    rotor_loss_low_pct: float
    rotor_loss_high_pct: float

    @property
    def total_low_pct(self) -> float:
        """Tower plus yaw-averaged rotor."""
        return self.tower_loss_pct + self.rotor_loss_low_pct

    @property
    def total_high_pct(self) -> float:
        """Tower plus sun-facing rotor."""
        return self.tower_loss_pct + self.rotor_loss_high_pct


@dataclass(frozen=True)
class ShadingFootprint:
    """Loss-equivalent PV land area per turbine beyond a setback, m².

    Multiply by the number of turbines inside an array and divide by the array's land area
    to get the plant-level optical loss.
    """

    setback_m: float
    tower_m2: float
    rotor_low_m2: float
    rotor_high_m2: float

    @property
    def total_low_m2(self) -> float:
        """Tower plus yaw-averaged rotor."""
        return self.tower_m2 + self.rotor_low_m2

    @property
    def total_high_m2(self) -> float:
        """Tower plus sun-facing rotor."""
        return self.tower_m2 + self.rotor_high_m2


#: Limits stated on every result (CASPER: the caveat travels with the number).
CAVEATS: tuple[str, ...] = (
    "Optical floor: electrical mismatch and inverter MPPT disturbance from moving blade "
    "shadows are not modelled and can make measured losses several times larger.",
    "Diffuse and circumsolar irradiance are treated as unshaded; terrain is flat; the "
    "nacelle, hub overhang and tower taper are ignored.",
    "Energy is taken as proportional to plane-of-array irradiance (no clipping or "
    "temperature interaction).",
    "The per-turbine footprint assumes PV surrounds the turbine out to the grid extent; "
    "for a turbine on the array edge it is an upper bound.",
)


@dataclass(frozen=True)
class TurbineShadingResult:
    """Optical PV loss from one turbine's shadow, plus the optional plant roll-up."""

    latitude: float
    longitude: float
    hub_height_m: float
    rotor_diameter_m: float
    tower_diameter_m: float
    blade_solidity: float
    tilt_deg: float
    azimuth_deg: float
    resource_basis: str
    poa_global_kwh_m2: float
    poa_beam_kwh_m2: float
    grid_extent_m: float
    bands: tuple[ShadingBand, ...]
    footprints: tuple[ShadingFootprint, ...]
    array_status: str
    turbine_shading_pct_low: Optional[float]
    turbine_shading_pct_high: Optional[float]
    basis: str = "optical"
    caveats: tuple[str, ...] = CAVEATS

    def footprint(self, setback_m: float) -> ShadingFootprint:
        """The footprint computed for ``setback_m`` (raises KeyError if not computed)."""
        for fp in self.footprints:
            if math.isclose(fp.setback_m, setback_m):
                return fp
        raise KeyError(f"no footprint computed for setback {setback_m} m")


# ─────────────────────────────────────────────────────────────────────────────
# Irradiance year (pvlib) and the end-to-end calculation
# ─────────────────────────────────────────────────────────────────────────────


def _irradiance_steps(
    config: TurbineShadingConfig,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, str]:
    """Sun position and beam/global POA for ``config`` (see :func:`irradiance_steps`)."""
    return irradiance_steps(config.solar, config.substeps_per_hour)


def irradiance_steps(
    solar: SolarResourceConfig, substeps_per_hour: int
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, str]:
    """Sun position and beam/global POA (Wh/m² per step) for every sub-hourly step.

    The hourly irradiance year is the one the PV producer uses: the frozen TMY when
    ``tmy_path`` is set, otherwise the Ineichen clear-sky year scaled to
    ``annual_ghi_kwh_m2`` with DISC decomposition. Each hour's irradiance is held over its
    sub-steps while the sun position is evaluated at each sub-step, starting on the hour
    (so one sub-step reproduces the producer's own timing).
    """
    pvlib = _require_pvlib()
    import pandas as pd

    loc = pvlib.location.Location(
        solar.latitude, solar.longitude, tz=solar.timezone, altitude=solar.altitude_m
    )
    if solar.tmy_path is not None:
        tmy = _load_tmy(solar.tmy_path)
        hours = pd.DatetimeIndex(tmy.index)
        ghi_h = tmy["ghi"].to_numpy(dtype=float)
        dni_h = tmy["dni"].to_numpy(dtype=float)
        dhi_h = tmy["dhi"].to_numpy(dtype=float)
        basis = "TMY"
    else:
        hours = pd.date_range(
            f"{solar.reference_year}-01-01 00:00",
            f"{solar.reference_year}-12-31 23:00",
            freq="1h",
            tz=solar.timezone,
        )
        clearsky = loc.get_clearsky(hours, model="ineichen")
        scale = solar.annual_ghi_kwh_m2 / (float(clearsky["ghi"].sum()) / 1000.0)
        ghi_s = clearsky["ghi"] * scale
        solpos_h = loc.get_solarposition(hours)
        dni_s = pvlib.irradiance.disc(ghi_s, solpos_h["zenith"], hours)["dni"]
        cos_zen = np.cos(np.radians(solpos_h["zenith"]))
        ghi_h = ghi_s.to_numpy(dtype=float)
        dni_h = dni_s.to_numpy(dtype=float)
        dhi_h = (ghi_s - dni_s * cos_zen).clip(lower=0.0).to_numpy(dtype=float)
        basis = "clear-sky"

    n = substeps_per_hour
    offsets = [pd.Timedelta(minutes=60.0 * k / n) for k in range(n)]
    # One block of hours per sub-step offset, in the same order as np.tile below.
    times = hours.append([hours + off for off in offsets[1:]]) if n > 1 else hours
    ghi = np.tile(ghi_h, n)
    dni = np.tile(dni_h, n)
    dhi = np.tile(dhi_h, n)
    solpos = loc.get_solarposition(times)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=solar.tilt_deg,
        surface_azimuth=solar.azimuth_deg,
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=pd.Series(dni, index=times),
        ghi=pd.Series(ghi, index=times),
        dhi=pd.Series(dhi, index=times),
        dni_extra=pvlib.irradiance.get_extra_radiation(times),
        model="haydavies",  # same transposition as the PV producer
    )
    step_h = 1.0 / n
    beam = poa["poa_direct"].fillna(0.0).clip(lower=0.0).to_numpy(dtype=float) * step_h
    glob = poa["poa_global"].fillna(0.0).clip(lower=0.0).to_numpy(dtype=float) * step_h
    return (
        solpos["apparent_elevation"].to_numpy(dtype=float),
        solpos["azimuth"].to_numpy(dtype=float),
        beam,
        glob,
        basis,
    )


def _grid(config: TurbineShadingConfig) -> tuple[FloatArray, FloatArray]:
    """Square grid of module-plane points around the tower, and their distances."""
    step = config.grid_step_m
    half = math.floor(config.grid_extent_m / step) * step
    axis = np.arange(-half, half + step / 2.0, step)
    xx, yy = np.meshgrid(axis, axis)
    points = np.column_stack([xx.ravel(), yy.ravel()])
    dist = np.hypot(points[:, 0], points[:, 1])
    keep = (dist > config.tower_diameter_m / 2.0) & (dist <= half)
    return points[keep], dist[keep]


def summarise_shading(
    acc: _Accumulated, dist: FloatArray, config: TurbineShadingConfig, basis: str
) -> TurbineShadingResult:
    """Turn per-point removed energy into bands, footprints and the plant roll-up."""
    total = acc.poa_global_wh
    if total <= 0.0:
        raise ValueError("annual POA is zero: check the irradiance year")
    cell_m2 = config.grid_step_m**2

    bands = []
    for lower, upper in zip(
        config.distance_bands_m, config.distance_bands_m[1:], strict=False
    ):
        ring = (dist >= lower) & (dist < upper)
        if not ring.any():
            continue
        bands.append(
            ShadingBand(
                lower_m=lower,
                upper_m=upper,
                tower_loss_pct=100.0 * float(acc.tower_wh[ring].mean()) / total,
                rotor_loss_low_pct=100.0 * float(acc.rotor_low_wh[ring].mean()) / total,
                rotor_loss_high_pct=100.0
                * float(acc.rotor_high_wh[ring].mean())
                / total,
            )
        )

    footprints = []
    for setback in config.setbacks_m:
        beyond = dist >= setback
        footprints.append(
            ShadingFootprint(
                setback_m=setback,
                tower_m2=cell_m2 * float(acc.tower_wh[beyond].sum()) / total,
                rotor_low_m2=cell_m2 * float(acc.rotor_low_wh[beyond].sum()) / total,
                rotor_high_m2=cell_m2 * float(acc.rotor_high_wh[beyond].sum()) / total,
            )
        )

    pct_low: Optional[float] = None
    pct_high: Optional[float] = None
    if config.turbines_within_array is None or config.array_land_area_m2 is None:
        status = (
            "NOT-RUN: declare resource.solar.turbine_shading.array with "
            "turbines_within_array and land_area_m2 (or land_use_mwp_per_ha)"
        )
    else:
        fp = next(
            f for f in footprints if math.isclose(f.setback_m, config.array_setback_m)
        )
        n = config.turbines_within_array
        pct_low = min(100.0, 100.0 * n * fp.total_low_m2 / config.array_land_area_m2)
        pct_high = min(100.0, 100.0 * n * fp.total_high_m2 / config.array_land_area_m2)
        status = "RUN"

    return TurbineShadingResult(
        latitude=config.solar.latitude,
        longitude=config.solar.longitude,
        hub_height_m=config.hub_height_m,
        rotor_diameter_m=config.rotor_diameter_m,
        tower_diameter_m=config.tower_diameter_m,
        blade_solidity=config.blade_solidity,
        tilt_deg=config.solar.tilt_deg,
        azimuth_deg=config.solar.azimuth_deg,
        resource_basis=basis,
        poa_global_kwh_m2=acc.poa_global_wh / 1000.0,
        poa_beam_kwh_m2=acc.poa_beam_wh / 1000.0,
        grid_extent_m=float(dist.max()),
        bands=tuple(bands),
        footprints=tuple(footprints),
        array_status=status,
        turbine_shading_pct_low=pct_low,
        turbine_shading_pct_high=pct_high,
    )


def compute_turbine_shading(config: TurbineShadingConfig) -> TurbineShadingResult:
    """Optical PV loss from one turbine's tower and rotor shadow over a full year.

    Args:
        config: Inputs, normally from :meth:`TurbineShadingConfig.from_scenario`.

    Returns:
        Bands, per-turbine footprints and (when the array is declared) the plant roll-up.
    """
    elevation, azimuth, beam, glob, basis = _irradiance_steps(config)
    points, dist = _grid(config)
    acc = accumulate_shading(
        points,
        elevation,
        azimuth,
        beam,
        glob,
        hub_height_m=config.hub_height_m - config.panel_height_m,
        rotor_radius_m=config.rotor_diameter_m / 2.0,
        tower_diameter_m=config.tower_diameter_m,
        blade_solidity=config.blade_solidity,
        yaw_samples=config.yaw_samples,
        min_sun_elevation_deg=config.min_sun_elevation_deg,
    )
    return summarise_shading(acc, dist, config, basis)


def turbine_shading_from_scenario(
    scenario: Mapping[str, Any], overrides: Optional[Mapping[str, Any]] = None
) -> TurbineShadingResult:
    """Convenience wrapper: build the config from a scenario and compute.

    Args:
        scenario: A loaded scenario mapping.
        overrides: Optional ``TurbineShadingConfig`` field overrides (for coarse runs).
    """
    config = TurbineShadingConfig.from_scenario(scenario)
    if overrides:
        from dataclasses import replace

        config = replace(config, **dict(overrides))
    return compute_turbine_shading(config)
