"""Hourly turbine-shadow loss on a laid-out PV array (optional ``[solar]`` extra).

:mod:`solar_resource.turbine_shading` estimates the optical loss on a ground grid around a
turbine, averaged over a year. This module applies the same geometry to the tables of an
actual PV layout and keeps the result HOURLY, so the loss can derate an hourly PV series
before a battery dispatch sees it.

Inputs, all read from configuration so the code serves any site:

* the PV tables, as axis-aligned rectangles in a local east/north frame (metres), in the
  order a layout packs them (``analytics.gis.pv_array_layout.fit_site``);
* the tower position in the same frame (the site GeoJSON's turbine point);
* the turbine's hub height and rotor diameter (the wind siting YAML's ``turbine`` block);
* the irradiance year and module plane (a :class:`SolarResourceConfig` with ``tmy_path``);
* the method block (``pv_yield.turbine_shading`` of a unit config), whose missing method
  keys fall back to ``config/defaults.yaml`` ``defaults.solar_resource.turbine_shading``.

Method, per sub-hourly step with the sun above ``min_sun_elevation_deg``:

1. Each table is sampled at a regular grid of points on the module plane
   (``samples_per_table_ew`` x ``samples_per_table_ns``, cell centres).
2. A sample in the tower's shadow strip loses all of the step's beam POA. A sample inside
   the rotor disc's shadow ellipse loses ``blade_solidity`` of it. Their sum is capped at
   the beam, so a sample under both is not charged twice.
3. The rotor's yaw follows the wind. With ``yaw_basis: wind_rose`` each sector of the wind
   rose CSV is a rotor-axis azimuth weighted by its frequency (a disc looks the same from
   either side, so opposite sectors share one orientation). ``uniform`` spreads
   ``yaw_samples`` azimuths evenly over 180 degrees. The wind rose is an annual aggregate,
   so direction is taken as independent of the hour.
4. Per hour, the array's optical loss is the mean beam removed over all samples divided
   by the unshaded global POA. Beside it, annual only, a high case: the rotor yawed to the
   sun's azimuth at every step, the largest shadow area a horizontal-axis rotor can cast.
   It is a sensitivity, not a pointwise bound. #1520's sun-facing ``high`` disc tilts
   with the sun, which a horizontal-axis rotor cannot, so it is not quoted.

The derate is ``1 - electrical_mismatch_multiplier x optical loss``, applied to the POA
that drives the DC model (:func:`solar_resource.pv_bess_dispatch.hourly_pv`), so inverter
clipping sees the shaded power. A multiplier of 1 is the optical floor: moving blade
shadows also disturb string currents and inverter MPPT, which the multiplier stands for.

Limits, stated with every result: diffuse and circumsolar light are unshaded; terrain is
flat; the nacelle, hub overhang and tower taper are ignored; shaded modules are not
credited with a lower cell temperature; one turbine casts the shadow.
"""

from __future__ import annotations

import csv
import io
import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray

from solar_resource.pv_producer import SolarResourceConfig
from solar_resource.turbine_shading import (
    _method_defaults,
    irradiance_steps,
    rotor_shadow_mask,
    strict_int,
    sun_unit_vectors,
    tower_shadow_mask,
)

FloatArray = NDArray[np.float64]
Table = Tuple[float, float, float, float]

#: Keys of a unit config's ``pv_yield.turbine_shading`` block (all required).
BLOCK_KEYS: Tuple[str, ...] = (
    "samples_per_table_ew",
    "samples_per_table_ns",
    "yaw_basis",
    "wind_rose_csv",
    "electrical_mismatch_multiplier",
    "electrical_mismatch_basis",
    "method_overrides",
)
#: Method keys a unit config may override (the rest of the defaults are grid settings).
OVERRIDE_KEYS: Tuple[str, ...] = (
    "tower_diameter_m",
    "tower_diameter_to_rotor_radius",
    "blade_solidity",
    "panel_height_m",
    "yaw_samples",
    "substeps_per_hour",
    "min_sun_elevation_deg",
)
YAW_BASES: Tuple[str, ...] = ("wind_rose", "uniform")

LIMITATIONS: Tuple[str, ...] = (
    "Diffuse and circumsolar irradiance are treated as unshaded; terrain is flat; the "
    "nacelle, hub overhang and tower taper are ignored.",
    "Rotor yaw follows the annual wind rose, taken as independent of the hour and season.",
    "Shaded modules are not credited with a lower cell temperature.",
    "The blade solidity is a time average of the turning rotor; no blade planform is used.",
    "The electrical multiplier is a declared treatment, not a string-level simulation.",
)


def read_wind_rose(text: str) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Rotor-axis azimuths and weights from a wind rose CSV.

    The CSV needs ``centre_deg`` and ``frequency`` columns; lines starting with ``#`` are
    comments. Opposite sectors are folded onto one azimuth in [0, 180), because a rotor
    disc casts the same shadow whichever way it faces.

    Raises:
        ValueError: On missing columns, a negative frequency or a zero total.
    """
    rows = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(rows)))
    if reader.fieldnames is None or not {"centre_deg", "frequency"} <= set(
        reader.fieldnames
    ):
        raise ValueError("wind rose CSV needs centre_deg and frequency columns")
    folded: Dict[float, float] = {}
    for row in reader:
        freq = float(row["frequency"])
        if freq < 0.0 or not math.isfinite(freq):
            raise ValueError(f"wind rose frequency must be >= 0: {freq}")
        yaw = round(float(row["centre_deg"]) % 180.0, 9)
        folded[yaw] = folded.get(yaw, 0.0) + freq
    total = sum(folded.values())
    if total <= 0.0:
        raise ValueError("wind rose frequencies sum to zero")
    yaws = tuple(sorted(folded))
    return yaws, tuple(folded[y] / total for y in yaws)


@dataclass(frozen=True)
class ArrayShadingConfig:
    """Typed inputs for :func:`table_shading`.

    Attributes:
        hub_height_m: Hub height above ground, metres.
        rotor_diameter_m: Rotor diameter, metres.
        tower_diameter_m: Width of the tower shadow strip, metres.
        blade_solidity: Share of the swept disc the blades cover (0-1).
        panel_height_m: Mean module height above ground, metres.
        substeps_per_hour: Sun positions per hour.
        min_sun_elevation_deg: Steps with a lower sun are ignored.
        samples_per_table: Sample points per table, (east-west, north-south).
        yaw_basis: ``wind_rose`` or ``uniform``.
        yaw_deg: Rotor-axis azimuths, degrees clockwise from north.
        yaw_weight: Their weights (sum 1).
        electrical_mismatch_multiplier: Multiplier on the optical loss (>= 1).
        electrical_mismatch_basis: Why that multiplier (stated with every result).
        wind_rose_csv: The wind rose read, or None for ``uniform``.
    """

    hub_height_m: float
    rotor_diameter_m: float
    tower_diameter_m: float
    blade_solidity: float
    panel_height_m: float
    substeps_per_hour: int
    min_sun_elevation_deg: float
    samples_per_table: Tuple[int, int]
    yaw_basis: str
    yaw_deg: Tuple[float, ...]
    yaw_weight: Tuple[float, ...]
    electrical_mismatch_multiplier: float
    electrical_mismatch_basis: str
    wind_rose_csv: Optional[str] = None

    def __post_init__(self) -> None:
        checks = {
            "hub_height_m": self.hub_height_m > 0.0,
            "rotor_diameter_m": self.rotor_diameter_m > 0.0,
            "tower_diameter_m": self.tower_diameter_m > 0.0,
            "blade_solidity": 0.0 < self.blade_solidity <= 1.0,
            "panel_height_m": 0.0 <= self.panel_height_m < self.hub_height_m,
            "substeps_per_hour": self.substeps_per_hour >= 1,
            "min_sun_elevation_deg": 0.0 <= self.min_sun_elevation_deg < 90.0,
            "samples_per_table": min(self.samples_per_table) >= 1,
            "yaw_basis": self.yaw_basis in YAW_BASES,
            "yaw": len(self.yaw_deg) == len(self.yaw_weight) >= 1
            and abs(sum(self.yaw_weight) - 1.0) <= 1e-9
            and min(self.yaw_weight) >= 0.0,
            "electrical_mismatch_multiplier": math.isfinite(
                self.electrical_mismatch_multiplier
            )
            and self.electrical_mismatch_multiplier >= 1.0,
            "electrical_mismatch_basis": bool(self.electrical_mismatch_basis.strip()),
        }
        bad = [name for name, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"array turbine-shading inputs out of range: {bad}")
        if self.rotor_diameter_m / 2.0 >= self.hub_height_m - self.panel_height_m:
            raise ValueError("rotor tip would reach the module plane: check hub height")

    @classmethod
    def from_mapping(
        cls,
        block: Mapping[str, Any],
        *,
        turbine: Mapping[str, Any],
        read_text: Callable[[str], str],
    ) -> "ArrayShadingConfig":
        """Build from a ``pv_yield.turbine_shading`` block and a ``turbine`` block.

        Args:
            block: The method block; every key of :data:`BLOCK_KEYS` is required.
            turbine: A mapping with ``hub_height_m`` and ``rotor_diameter_m``.
            read_text: Reads a repository-relative file (the wind rose CSV).

        Raises:
            KeyError: A key is missing or unknown.
            ValueError: A value is out of range.
        """
        missing = sorted(set(BLOCK_KEYS) - set(block))
        unknown = sorted(set(block) - set(BLOCK_KEYS))
        if missing or unknown:
            raise KeyError(
                f"pv_yield.turbine_shading: missing {missing}, unknown {unknown}"
            )
        overrides = dict(block["method_overrides"] or {})
        bad = sorted(set(overrides) - set(OVERRIDE_KEYS))
        if bad:
            raise KeyError(
                f"pv_yield.turbine_shading.method_overrides has unknown keys: {bad}"
            )
        for key in ("hub_height_m", "rotor_diameter_m"):
            if turbine.get(key) is None:
                raise KeyError(f"turbine block is missing {key}")
        params = {**_method_defaults(), **overrides}
        rotor_d = float(turbine["rotor_diameter_m"])
        tower_d = params.get("tower_diameter_m")
        if tower_d is None:
            tower_d = float(params["tower_diameter_to_rotor_radius"]) * rotor_d / 2.0
        basis = str(block["yaw_basis"])
        rose = block["wind_rose_csv"]
        if basis == "wind_rose":
            if not rose:
                raise KeyError("yaw_basis wind_rose needs wind_rose_csv")
            yaws, weights = read_wind_rose(read_text(str(rose)))
        elif basis == "uniform":
            if rose:
                raise ValueError("yaw_basis uniform takes no wind_rose_csv")
            n = strict_int(params["yaw_samples"], "yaw_samples")
            if n < 1:
                raise ValueError("yaw_samples must be >= 1")
            yaws = tuple(180.0 * k / n for k in range(n))
            weights = tuple(1.0 / n for _ in range(n))
        else:
            raise ValueError(f"yaw_basis must be one of {YAW_BASES}")
        return cls(
            hub_height_m=float(turbine["hub_height_m"]),
            rotor_diameter_m=rotor_d,
            tower_diameter_m=float(tower_d),
            blade_solidity=float(params["blade_solidity"]),
            panel_height_m=float(params["panel_height_m"]),
            substeps_per_hour=strict_int(
                params["substeps_per_hour"], "substeps_per_hour"
            ),
            min_sun_elevation_deg=float(params["min_sun_elevation_deg"]),
            samples_per_table=(
                strict_int(block["samples_per_table_ew"], "samples_per_table_ew"),
                strict_int(block["samples_per_table_ns"], "samples_per_table_ns"),
            ),
            yaw_basis=basis,
            yaw_deg=yaws,
            yaw_weight=weights,
            electrical_mismatch_multiplier=float(
                block["electrical_mismatch_multiplier"]
            ),
            electrical_mismatch_basis=str(block["electrical_mismatch_basis"]),
            wind_rose_csv=str(rose) if rose else None,
        )


def table_sample_points(
    tables: Sequence[Table], turbine_en: Tuple[float, float], samples: Tuple[int, int]
) -> FloatArray:
    """Sample points of every table relative to the tower, table-major, shape (m, 2).

    Args:
        tables: ``(x0, y0, x1, y1)`` rectangles in the local frame, metres.
        turbine_en: The tower position in the same frame.
        samples: Points per table (east-west, north-south), at cell centres.
    """
    nx, ny = samples
    fx = (np.arange(nx) + 0.5) / nx
    fy = (np.arange(ny) + 0.5) / ny
    mx, my = np.meshgrid(fx, fy, indexing="ij")
    ux, uy = mx.ravel(), my.ravel()
    t = np.asarray(tables, dtype=float).reshape(-1, 4)
    x = t[:, 0:1] + ux[None, :] * (t[:, 2:3] - t[:, 0:1]) - turbine_en[0]
    y = t[:, 1:2] + uy[None, :] * (t[:, 3:4] - t[:, 1:2]) - turbine_en[1]
    return np.column_stack([x.ravel(), y.ravel()])


@dataclass(frozen=True)
class TableShading:
    """Hourly beam removed from each table of a packing, and the unshaded POA.

    Attributes:
        cum_removed_wh: Cumulative sum over tables (in packing order) of each table's
            mean beam POA removed per hour, Wh/m²; shape ``(n_tables + 1, n_hours)``,
            row 0 all zero. The first ``n`` tables' mean is ``row[n] / n``.
        poa_global_wh: Unshaded global POA per hour summed over the sub-steps, Wh/m².
        tower_wh: Per table, annual mean beam removed by the tower alone.
        rotor_wh: Per table, annual mean beam removed by the rotor (the yaw basis),
            outside the tower strip.
        rotor_yawed_to_sun_wh: Per table, the same for a disc yawed to the sun's azimuth
            at every step (the largest shadow area a horizontal-axis rotor casts; a
            sensitivity, not a pointwise bound).
        basis: ``TMY`` or ``clear-sky`` (the irradiance year).
    """

    cum_removed_wh: FloatArray
    poa_global_wh: FloatArray
    tower_wh: FloatArray
    rotor_wh: FloatArray
    rotor_yawed_to_sun_wh: FloatArray
    basis: str

    @property
    def n_tables(self) -> int:
        """Tables in the packing."""
        return int(self.cum_removed_wh.shape[0] - 1)

    def optical_loss_hourly(self, n_tables: int) -> FloatArray:
        """Per hour, the first ``n_tables`` tables' mean optical loss (share of POA)."""
        if not 1 <= n_tables <= self.n_tables:
            raise ValueError(f"n_tables must be 1..{self.n_tables}, got {n_tables}")
        removed = self.cum_removed_wh[n_tables] / n_tables
        glob = self.poa_global_wh
        out = np.zeros_like(glob)
        lit = glob > 0.0
        out[lit] = np.minimum(1.0, removed[lit] / glob[lit])
        return out

    def retention(self, n_tables: int, multiplier: float) -> FloatArray:
        """Per hour, the share of POA the first ``n_tables`` keep after the derate."""
        return np.clip(1.0 - multiplier * self.optical_loss_hourly(n_tables), 0.0, 1.0)

    def annual(self, n_tables: int, multiplier: float) -> Dict[str, float]:
        """Annual losses of the first ``n_tables`` tables, as shares of annual POA."""
        if not 1 <= n_tables <= self.n_tables:
            raise ValueError(f"n_tables must be 1..{self.n_tables}, got {n_tables}")
        total = float(self.poa_global_wh.sum())
        tower = float(self.tower_wh[:n_tables].mean()) / total
        rotor = float(self.rotor_wh[:n_tables].mean()) / total
        facing = float(self.rotor_yawed_to_sun_wh[:n_tables].mean()) / total
        optical = float((self.cum_removed_wh[n_tables] / n_tables).sum()) / total
        derated = 1.0 - float(
            (self.retention(n_tables, multiplier) * self.poa_global_wh).sum() / total
        )
        return {
            "optical_loss": optical,
            "optical_tower": tower,
            "optical_rotor": rotor,
            "optical_rotor_yawed_to_sun": facing,
            "optical_loss_rotor_yawed_to_sun": tower + facing,
            "electrical_mismatch_multiplier": multiplier,
            "poa_loss_after_multiplier": derated,
        }


def table_shading(
    tables: Sequence[Table],
    turbine_en: Tuple[float, float],
    solar: SolarResourceConfig,
    cfg: ArrayShadingConfig,
    *,
    steps: Optional[Tuple[FloatArray, FloatArray, FloatArray, FloatArray, str]] = None,
) -> TableShading:
    """Hourly turbine-shadow beam loss on every table of a packing.

    Args:
        tables: The packing's tables in order (a layout of ``n`` tables is the first ``n``).
        turbine_en: The tower position in the tables' frame.
        solar: The module plane and irradiance year (``tmy_path`` required).
        cfg: The method inputs.
        steps: Precomputed :func:`~solar_resource.turbine_shading.irradiance_steps` for
            ``solar`` and ``cfg.substeps_per_hour`` (a cache; computed when omitted).

    Raises:
        ValueError: If ``solar`` has no ``tmy_path`` or there are no tables.
    """
    if solar.tmy_path is None:
        raise ValueError("table_shading needs resource.solar.tmy_path (hourly TMY)")
    if not tables:
        raise ValueError("table_shading needs at least one table")
    elevation, azimuth, beam, glob, basis = (
        steps if steps is not None else irradiance_steps(solar, cfg.substeps_per_hour)
    )
    n_steps = len(beam)
    n_sub = cfg.substeps_per_hour
    if n_steps % n_sub:
        raise ValueError("irradiance steps are not a whole number of hours")
    n_hours = n_steps // n_sub
    points = table_sample_points(tables, turbine_en, cfg.samples_per_table)
    per_table = cfg.samples_per_table[0] * cfg.samples_per_table[1]
    n_tables = len(tables)
    height = cfg.hub_height_m - cfg.panel_height_m
    radius = cfg.rotor_diameter_m / 2.0
    suns = sun_unit_vectors(elevation, azimuth)
    removed = np.zeros((n_tables, n_hours))
    tower_t = np.zeros(n_tables)
    rotor_t = np.zeros(n_tables)
    facing_t = np.zeros(n_tables)
    azimuth = np.asarray(azimuth, dtype=float)
    weights = np.asarray(cfg.yaw_weight)
    active = np.nonzero((elevation >= cfg.min_sun_elevation_deg) & (beam > 0.0))[0]
    for i in active:
        sun = suns[i]
        b = float(beam[i])
        tower = tower_shadow_mask(points, sun, height, cfg.tower_diameter_m)
        rotor = np.zeros(len(points))
        for yaw, w in zip(cfg.yaw_deg, weights, strict=True):
            rotor += w * rotor_shadow_mask(points, sun, height, radius, yaw)
        facing = rotor_shadow_mask(points, sun, height, radius, float(azimuth[i]))
        # Union per point: the blades take beam only where the tower has not.
        open_sky = 1.0 - tower
        blades = cfg.blade_solidity * rotor * open_sky
        removed[:, i % n_hours] += b * (tower + blades).reshape(
            n_tables, per_table
        ).mean(1)
        tower_t += b * tower.reshape(n_tables, per_table).mean(axis=1)
        rotor_t += b * blades.reshape(n_tables, per_table).mean(1)
        facing_t += (
            b
            * cfg.blade_solidity
            * (facing * open_sky).reshape(n_tables, per_table).mean(1)
        )
    glob_h = np.asarray(glob, dtype=float).reshape(n_sub, n_hours).sum(axis=0)
    cum = np.vstack([np.zeros((1, n_hours)), np.cumsum(removed, axis=0)])
    return TableShading(
        cum_removed_wh=cum,
        poa_global_wh=glob_h,
        tower_wh=tower_t,
        rotor_wh=rotor_t,
        rotor_yawed_to_sun_wh=facing_t,
        basis=basis,
    )


#: Process-wide caches: irradiance steps per module plane, and results per packing (a
#: sizing run revisits the same few packings for every PV and BESS size it tries).
_STEPS_CACHE: Dict[Tuple[Any, ...], Any] = {}
_SHADING_CACHE: "OrderedDict[Tuple[Any, ...], TableShading]" = OrderedDict()
_SHADING_CACHE_SIZE = 16


@dataclass(frozen=True)
class ArrayShadingSource:
    """Turbine-shadow derates for any layout of one site (cached per packing).

    Attributes:
        cfg: The method inputs.
        turbine_en: The tower position in the layout frame.
    """

    cfg: ArrayShadingConfig
    turbine_en: Tuple[float, float]

    def shading(
        self, packing: Sequence[Table], solar: SolarResourceConfig
    ) -> TableShading:
        """The :class:`TableShading` of a packing (computed once per packing and plane)."""
        plane = (
            solar.latitude,
            solar.longitude,
            solar.timezone,
            solar.altitude_m,
            solar.tilt_deg,
            solar.azimuth_deg,
            str(solar.tmy_path),
            self.cfg.substeps_per_hour,
        )
        if plane not in _STEPS_CACHE:
            _STEPS_CACHE[plane] = irradiance_steps(solar, self.cfg.substeps_per_hour)
        key = (
            plane,
            self.cfg,
            self.turbine_en,
            tuple(tuple(float(v) for v in t) for t in packing),
        )
        if key in _SHADING_CACHE:
            _SHADING_CACHE.move_to_end(key)
            return _SHADING_CACHE[key]
        result = table_shading(
            packing, self.turbine_en, solar, self.cfg, steps=_STEPS_CACHE[plane]
        )
        _SHADING_CACHE[key] = result
        while len(_SHADING_CACHE) > _SHADING_CACHE_SIZE:
            _SHADING_CACHE.popitem(last=False)
        return result

    def retention(
        self, packing: Sequence[Table], n_tables: int, solar: SolarResourceConfig
    ) -> FloatArray:
        """Hourly POA retention of the first ``n_tables`` tables of ``packing``."""
        return self.shading(packing, solar).retention(
            n_tables, self.cfg.electrical_mismatch_multiplier
        )

    def report(
        self, packing: Sequence[Table], n_tables: int, solar: SolarResourceConfig
    ) -> Dict[str, Any]:
        """Annual losses and the declared method, JSON-ready."""
        sh = self.shading(packing, solar)
        cfg = self.cfg
        return {
            **sh.annual(n_tables, cfg.electrical_mismatch_multiplier),
            "tables": n_tables,
            "irradiance_basis": sh.basis,
            "yaw_basis": cfg.yaw_basis,
            "wind_rose_csv": cfg.wind_rose_csv,
            "electrical_mismatch_basis": cfg.electrical_mismatch_basis,
            "hub_height_m": cfg.hub_height_m,
            "rotor_diameter_m": cfg.rotor_diameter_m,
            "tower_diameter_m": cfg.tower_diameter_m,
            "blade_solidity": cfg.blade_solidity,
            "panel_height_m": cfg.panel_height_m,
            "substeps_per_hour": cfg.substeps_per_hour,
            "samples_per_table": list(cfg.samples_per_table),
            "limitations": list(LIMITATIONS),
        }


def shading_source_from_unit(
    pv_yield: Mapping[str, Any],
    *,
    turbine: Mapping[str, Any],
    turbine_en: Tuple[float, float],
    read_text: Callable[[str], str],
) -> Optional[ArrayShadingSource]:
    """The shading source a unit config declares, or None when it is not modelled.

    ``pv_yield.turbine_shading_modelled`` (bool) switches it; the ``turbine_shading``
    block is then required. When it is false, the block must be null, so a config cannot
    carry a method it does not apply.

    Raises:
        TypeError: If ``turbine_shading_modelled`` is not a bool.
        KeyError: If the block is missing when modelled, or present when not.
    """
    flag = pv_yield.get("turbine_shading_modelled")
    if not isinstance(flag, bool):
        raise TypeError("pv_yield.turbine_shading_modelled must be true or false")
    if "turbine_shading" not in pv_yield:
        raise KeyError("pv_yield.turbine_shading is required (null when not modelled)")
    block = pv_yield["turbine_shading"]
    if not flag:
        if block is not None:
            raise KeyError("pv_yield.turbine_shading must be null when not modelled")
        return None
    if not isinstance(block, Mapping):
        raise KeyError("pv_yield.turbine_shading must be a mapping when modelled")
    cfg = ArrayShadingConfig.from_mapping(block, turbine=turbine, read_text=read_text)
    return ArrayShadingSource(
        cfg=cfg, turbine_en=(float(turbine_en[0]), float(turbine_en[1]))
    )


__all__ = [
    "ArrayShadingConfig",
    "ArrayShadingSource",
    "BLOCK_KEYS",
    "LIMITATIONS",
    "OVERRIDE_KEYS",
    "TableShading",
    "YAW_BASES",
    "read_wind_rose",
    "shading_source_from_unit",
    "table_sample_points",
    "table_shading",
]
