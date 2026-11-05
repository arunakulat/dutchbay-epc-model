"""Fixed-tilt PV array and BESS pad: module, strings, tables, row pitch, land and site fit.

Sizes the photovoltaic array of a solar + BESS unit and checks whether it fits a lot, all
driven by config (``conf/blue_whale_solar_bess.yaml``; ``ARCH-01``, ``FRAMEWORK-02``):

1. **Module and strings.** The module's warranted degradation path, and the longest
   string whose open-circuit voltage at the design minimum cell temperature stays within
   the module's maximum system voltage.
2. **Array.** The DC peak is the AC export capacity times the DC/AC ratio, rounded up to
   whole tables. Tables hold a fixed number of strings, modules in portrait.
3. **Row pitch.** The pitch at which no row shades the next over a clock-time window on
   one day (usually the winter solstice), from ``pvlib`` solar position, with a floor
   from a minimum clear aisle. The ground coverage ratio is slant height over pitch.
4. **Land.** The fenced area of a compact rectangular array block, with a perimeter road,
   north-south roads, MV stations and a containerised BESS pad.
5. **Site fit.** The lot less the coastal setback strip, the turbine foundation and its
   crane hardstand, packed with east-west rows of tables at the computed pitch around the
   BESS and MV group. The array fits when the packing places every table.

Shadow geometry: a row of slant height ``L`` at tilt ``b`` and facing azimuth ``g`` casts
its top edge's shadow ``L sin(b) cos(sun_az - g) / tan(sun_el)`` beyond its own footprint
``L cos(b)`` along the row normal, so rows ``P`` apart do not shade when
``P >= L cos(b) + L sin(b) max(0, cos(sun_az - g)) / tan(sun_el)`` at every instant of the
window. Flat ground is assumed.

Geometry is computed in the local transverse Mercator frame of
:class:`analytics.gis.shadow_flicker.LocalFrame`, and the coastal zone is built with
:func:`analytics.gis.exclusion_mask.build_setback_zone`, as the wind siting screen does.

``FRAMEWORK-01``: ``pyproj``, ``shapely`` and ``pvlib`` are optional extras imported at call
time behind guards with actionable errors. The module is KPI-neutral: it feeds no finance
path directly.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from analytics.gis.exclusion_mask import _require_shapely, build_setback_zone
from analytics.gis.shadow_flicker import (
    CoastalSetbackConfig,
    LocalFrame,
    coastline_lines_east_north,
)

EastNorth = Tuple[float, float]

_STC_CELL_TEMP_C = 25.0


def _require_pvlib() -> Any:
    """Return the ``pvlib`` module or raise an actionable error if it is absent."""
    try:
        import pvlib

        return pvlib
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The row-pitch rule needs pvlib from the [solar] extra: "
            "pip install -e '.[solar]'."
        ) from exc


def _strict(cls: type, raw: Mapping[str, Any], where: str) -> Dict[str, Any]:
    """Return ``raw`` as constructor kwargs, refusing missing or unknown keys."""
    names = {f.name for f in fields(cls)}
    missing = sorted(names - set(raw))
    extra = sorted(set(raw) - names)
    if missing or extra:
        raise ValueError(
            f"{where}: missing keys {missing} and unknown keys {extra}; "
            f"expected exactly {sorted(names)}."
        )
    return {name: raw[name] for name in names}


def _positive(value: Any, where: str) -> float:
    """Coerce to float and require it to be finite and positive."""
    out = float(value)
    if not math.isfinite(out) or out <= 0:
        raise ValueError(f"{where} must be a positive number; got {value!r}")
    return out


def _non_negative(value: Any, where: str) -> float:
    """Coerce to float and require it to be finite and non-negative."""
    out = float(value)
    if not math.isfinite(out) or out < 0:
        raise ValueError(f"{where} must be a non-negative number; got {value!r}")
    return out


def _whole(value: Any, where: str) -> int:
    """Require a positive whole number."""
    if isinstance(value, bool) or float(value) != int(value) or int(value) < 1:
        raise ValueError(f"{where} must be a positive whole number; got {value!r}")
    return int(value)


# ---------------------------------------------------------------------------
# 1. Module and strings
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModuleSpec:
    """A PV module datasheet, as config.

    Attributes:
        name: Product and model code.
        pmax_w: STC maximum power.
        vmp_v, imp_a, voc_v, isc_a: STC maximum-power voltage and current, open-circuit
            voltage and short-circuit current.
        efficiency_pct: STC module efficiency.
        temp_coeff_pmax_pct_per_c, temp_coeff_voc_pct_per_c, temp_coeff_isc_pct_per_c:
            Temperature coefficients, percent per degree C.
        cells: Cell count.
        length_mm, width_mm, thickness_mm, weight_kg: Mechanical data.
        bifaciality_pct: Rear-to-front power ratio (reported, not modelled here).
        max_system_voltage_v: Maximum DC system voltage.
        max_series_fuse_a: Maximum series fuse rating.
        first_year_degradation_pct: Warranted power loss in year 1.
        annual_degradation_pct: Warranted linear loss per year after year 1.
        year_30_power_pct: Warranted power at the end of year 30.
        product_warranty_years, power_warranty_years: Warranty terms.
        nmot_c: Nominal module operating temperature, or ``None`` if not stated.
    """

    name: str
    pmax_w: float
    vmp_v: float
    imp_a: float
    voc_v: float
    isc_a: float
    efficiency_pct: float
    temp_coeff_pmax_pct_per_c: float
    temp_coeff_voc_pct_per_c: float
    temp_coeff_isc_pct_per_c: float
    cells: int
    length_mm: float
    width_mm: float
    thickness_mm: float
    weight_kg: float
    bifaciality_pct: float
    max_system_voltage_v: float
    max_series_fuse_a: float
    first_year_degradation_pct: float
    annual_degradation_pct: float
    year_30_power_pct: float
    product_warranty_years: int
    power_warranty_years: int
    nmot_c: Optional[float]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ModuleSpec":
        """Build from config, refusing missing or unknown keys and an inconsistent warranty.

        Raises:
            ValueError: On a missing, unknown or non-physical key, or when the year-30
                warranted power does not follow from the first-year and annual rates.
        """
        kw = _strict(cls, raw, "module")
        kw["name"] = str(kw["name"])
        for key in (
            "pmax_w",
            "vmp_v",
            "imp_a",
            "voc_v",
            "isc_a",
            "efficiency_pct",
            "length_mm",
            "width_mm",
            "thickness_mm",
            "weight_kg",
            "max_system_voltage_v",
            "max_series_fuse_a",
            "year_30_power_pct",
        ):
            kw[key] = _positive(kw[key], f"module.{key}")
        for key in (
            "temp_coeff_pmax_pct_per_c",
            "temp_coeff_voc_pct_per_c",
            "temp_coeff_isc_pct_per_c",
        ):
            kw[key] = float(kw[key])
        for key in (
            "bifaciality_pct",
            "first_year_degradation_pct",
            "annual_degradation_pct",
        ):
            kw[key] = _non_negative(kw[key], f"module.{key}")
        for key in ("cells", "product_warranty_years", "power_warranty_years"):
            kw[key] = _whole(kw[key], f"module.{key}")
        kw["nmot_c"] = None if kw["nmot_c"] is None else float(kw["nmot_c"])
        spec = cls(**kw)
        if spec.vmp_v >= spec.voc_v or spec.imp_a >= spec.isc_a:
            raise ValueError("module: Vmp must be below Voc and Imp below Isc")
        if abs(spec.vmp_v * spec.imp_a - spec.pmax_w) > 0.01 * spec.pmax_w:
            raise ValueError("module: Vmp x Imp must equal Pmax within 1%")
        implied = spec.warranted_power_fraction(30) * 100.0
        if abs(implied - spec.year_30_power_pct) > 1e-6:
            raise ValueError(
                f"module: year_30_power_pct {spec.year_30_power_pct} does not follow from "
                f"the first-year and annual rates ({implied:.6f})"
            )
        return spec

    @property
    def area_m2(self) -> float:
        """Module area."""
        return self.length_mm * self.width_mm / 1.0e6

    def warranted_power_fraction(self, year: int) -> float:
        """Warranted power at the end of operating ``year`` (1-based), as a fraction of STC.

        ``1 - first/100 - annual/100 * (year - 1)``: the first-year loss, then the linear
        annual loss.

        Raises:
            ValueError: If ``year`` is below 1.
        """
        if year < 1:
            raise ValueError("year is 1-based")
        return (
            1.0
            - self.first_year_degradation_pct / 100.0
            - self.annual_degradation_pct / 100.0 * (year - 1)
        )


@dataclass(frozen=True)
class StringDesignConfig:
    """Design cell temperatures for the string-voltage checks.

    Attributes:
        design_min_cell_temp_c: Coldest cell temperature, for the open-circuit voltage.
        design_max_cell_temp_c: Hottest cell temperature, for the low-voltage check.
    """

    design_min_cell_temp_c: float
    design_max_cell_temp_c: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "StringDesignConfig":
        """Build from config, refusing missing or unknown keys."""
        kw = _strict(cls, raw, "string_design")
        out = cls(**{k: float(v) for k, v in kw.items()})
        if out.design_min_cell_temp_c >= out.design_max_cell_temp_c:
            raise ValueError("string_design: minimum must be below maximum")
        return out


@dataclass(frozen=True)
class StringDesign:
    """The string the module's voltage limit allows.

    Attributes:
        modules_per_string: Longest string within the maximum system voltage.
        voc_cold_module_v: Module Voc at the design minimum cell temperature.
        string_voc_cold_v: String Voc at the design minimum cell temperature.
        string_vmp_stc_v: String Vmp at STC.
        string_vmp_hot_v: String Vmp at the design maximum cell temperature, scaled by the
            Voc coefficient (the datasheet gives no Vmp coefficient).
        string_isc_a: String short-circuit current at STC.
        string_power_w: String power at STC.
    """

    modules_per_string: int
    voc_cold_module_v: float
    string_voc_cold_v: float
    string_vmp_stc_v: float
    string_vmp_hot_v: float
    string_isc_a: float
    string_power_w: float


def design_string(module: ModuleSpec, cfg: StringDesignConfig) -> StringDesign:
    """Longest string whose cold open-circuit voltage stays within the system voltage.

    ``Voc_cold = Voc * (1 + tc_voc/100 * (T_min - 25))`` and
    ``n = floor(V_max / Voc_cold)``.

    Raises:
        ValueError: If not even one module fits the voltage limit.
    """
    tc = module.temp_coeff_voc_pct_per_c / 100.0
    voc_cold = module.voc_v * (
        1.0 + tc * (cfg.design_min_cell_temp_c - _STC_CELL_TEMP_C)
    )
    n = math.floor(module.max_system_voltage_v / voc_cold)
    if n < 1:
        raise ValueError("no module fits the maximum system voltage")
    vmp_hot = module.vmp_v * (
        1.0 + tc * (cfg.design_max_cell_temp_c - _STC_CELL_TEMP_C)
    )
    return StringDesign(
        modules_per_string=n,
        voc_cold_module_v=voc_cold,
        string_voc_cold_v=n * voc_cold,
        string_vmp_stc_v=n * module.vmp_v,
        string_vmp_hot_v=n * vmp_hot,
        string_isc_a=module.isc_a,
        string_power_w=n * module.pmax_w,
    )


# ---------------------------------------------------------------------------
# 2. Array and tables
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ArrayConfig:
    """Array sizing and table format.

    Attributes:
        ac_capacity_mw: AC nameplate of the PV inverters (the unit's export capacity).
        dc_ac_ratio: Target DC peak over AC nameplate.
        tilt_deg: Fixed tilt.
        azimuth_deg: Facing azimuth, clockwise from north (180 = south).
        modules_high_portrait: Modules stacked up the slope, in portrait.
        strings_per_table: Strings per table.
        module_gap_m: Gap between adjacent modules on a table.
        table_gap_ew_m: Gap between adjacent tables along a row.
    """

    ac_capacity_mw: float
    dc_ac_ratio: float
    tilt_deg: float
    azimuth_deg: float
    modules_high_portrait: int
    strings_per_table: int
    module_gap_m: float
    table_gap_ew_m: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ArrayConfig":
        """Build from config, refusing missing, unknown or non-physical keys."""
        kw = _strict(cls, raw, "array")
        for key in ("ac_capacity_mw", "dc_ac_ratio"):
            kw[key] = _positive(kw[key], f"array.{key}")
        for key in ("tilt_deg", "azimuth_deg", "module_gap_m", "table_gap_ew_m"):
            kw[key] = _non_negative(kw[key], f"array.{key}")
        for key in ("modules_high_portrait", "strings_per_table"):
            kw[key] = _whole(kw[key], f"array.{key}")
        out = cls(**kw)
        if not 0.0 <= out.tilt_deg < 90.0 or out.azimuth_deg > 360.0:
            raise ValueError("array: tilt must be in [0, 90) and azimuth in [0, 360]")
        return out


@dataclass(frozen=True)
class ArraySizing:
    """Module, string and table counts and table geometry.

    Attributes:
        modules_per_table: Modules on one table.
        modules_per_row_ew: Modules side by side along a table.
        table_slant_m: Table length up the slope.
        table_depth_m: Horizontal north-south footprint of a table (slant x cos tilt).
        table_length_ew_m: Table length along the row.
        table_power_w: STC power of one table.
        tables: Table count.
        strings: String count.
        modules: Module count.
        dc_capacity_mw: Installed DC peak.
        ac_capacity_mw: AC nameplate.
        dc_ac_ratio: Installed DC over AC.
        module_area_m2: Total module area.
    """

    modules_per_table: int
    modules_per_row_ew: int
    table_slant_m: float
    table_depth_m: float
    table_length_ew_m: float
    table_power_w: float
    tables: int
    strings: int
    modules: int
    dc_capacity_mw: float
    ac_capacity_mw: float
    dc_ac_ratio: float
    module_area_m2: float


def size_array(
    module: ModuleSpec, strings: StringDesign, cfg: ArrayConfig
) -> ArraySizing:
    """Count tables, strings and modules for the target DC peak, rounding up to tables.

    Raises:
        ValueError: If a table's modules cannot be arranged in whole portrait rows.
    """
    per_table = strings.modules_per_string * cfg.strings_per_table
    if per_table % cfg.modules_high_portrait:
        raise ValueError(
            "array: modules per table must divide evenly into the portrait rows"
        )
    per_row = per_table // cfg.modules_high_portrait
    slant = (
        cfg.modules_high_portrait * module.length_mm / 1000.0
        + (cfg.modules_high_portrait - 1) * cfg.module_gap_m
    )
    length = per_row * module.width_mm / 1000.0 + (per_row - 1) * cfg.module_gap_m
    table_w = per_table * module.pmax_w
    target_w = cfg.ac_capacity_mw * 1.0e6 * cfg.dc_ac_ratio
    tables = math.ceil(target_w / table_w - 1e-12)
    modules = tables * per_table
    dc_mw = modules * module.pmax_w / 1.0e6
    return ArraySizing(
        modules_per_table=per_table,
        modules_per_row_ew=per_row,
        table_slant_m=slant,
        table_depth_m=slant * math.cos(math.radians(cfg.tilt_deg)),
        table_length_ew_m=length,
        table_power_w=table_w,
        tables=tables,
        strings=tables * cfg.strings_per_table,
        modules=modules,
        dc_capacity_mw=dc_mw,
        ac_capacity_mw=cfg.ac_capacity_mw,
        dc_ac_ratio=dc_mw / cfg.ac_capacity_mw,
        module_area_m2=modules * module.area_m2,
    )


# ---------------------------------------------------------------------------
# 3. Row pitch
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ShadingRuleConfig:
    """The no-shading rule for row pitch.

    Attributes:
        date: Day the rule applies to (ISO date).
        start_local, end_local: Clock-time window (``HH:MM``).
        timezone: IANA zone of the clock times.
        step_minutes: Sampling step.
        min_clear_aisle_m: Minimum clear distance between rows, a floor on the pitch.
    """

    date: str
    start_local: str
    end_local: str
    timezone: str
    step_minutes: int
    min_clear_aisle_m: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ShadingRuleConfig":
        """Build from config, refusing missing or unknown keys."""
        kw = _strict(cls, raw, "shading_rule")
        for key in ("date", "start_local", "end_local", "timezone"):
            kw[key] = str(kw[key])
        kw["step_minutes"] = _whole(kw["step_minutes"], "shading_rule.step_minutes")
        kw["min_clear_aisle_m"] = _non_negative(
            kw["min_clear_aisle_m"], "shading_rule.min_clear_aisle_m"
        )
        return cls(**kw)


@dataclass(frozen=True)
class RowPitch:
    """Row pitch and ground coverage ratio.

    Attributes:
        no_shade_pitch_m: Smallest pitch with no inter-row shading in the window.
        aisle_floor_pitch_m: Table depth plus the minimum clear aisle.
        pitch_m: The larger of the two: the design pitch.
        governing: ``"shading"`` or ``"aisle"``.
        gcr: Table slant height over pitch.
        no_shade_gcr: The ground coverage ratio the shading rule alone would allow.
        clear_aisle_m: Pitch less table depth.
        worst_sun_elevation_deg: Sun elevation at the binding instant.
        worst_sun_azimuth_deg: Sun azimuth at the binding instant.
        worst_time_local: The binding instant, local ISO time.
        min_window_elevation_deg: Lowest sun elevation in the window.
    """

    no_shade_pitch_m: float
    aisle_floor_pitch_m: float
    pitch_m: float
    governing: str
    gcr: float
    no_shade_gcr: float
    clear_aisle_m: float
    worst_sun_elevation_deg: float
    worst_sun_azimuth_deg: float
    worst_time_local: str
    min_window_elevation_deg: float


def shadow_reach_m(
    slant_m: float,
    tilt_deg: float,
    facing_azimuth_deg: float,
    sun_elevation_deg: float,
    sun_azimuth_deg: float,
) -> float:
    """Horizontal reach of a row's top-edge shadow beyond its footprint, along the row normal.

    ``L sin(b) max(0, cos(sun_az - g)) / tan(sun_el)``, which is zero when the sun is
    behind the row's facing direction.

    Raises:
        ValueError: If the sun is not above the horizon.
    """
    if sun_elevation_deg <= 0:
        raise ValueError("sun must be above the horizon")
    along = math.cos(math.radians(sun_azimuth_deg - facing_azimuth_deg))
    height = slant_m * math.sin(math.radians(tilt_deg))
    return height * max(0.0, along) / math.tan(math.radians(sun_elevation_deg))


def row_pitch(
    *,
    lat_deg: float,
    lon_deg: float,
    sizing: ArraySizing,
    array: ArrayConfig,
    rule: ShadingRuleConfig,
) -> RowPitch:
    """Design pitch from the no-shading rule and the clear-aisle floor (pvlib sun path).

    Raises:
        ValueError: If the sun is not above the horizon throughout the window.
    """
    pvlib = _require_pvlib()
    import pandas as pd

    times = pd.date_range(
        f"{rule.date} {rule.start_local}",
        f"{rule.date} {rule.end_local}",
        freq=f"{rule.step_minutes}min",
        tz=rule.timezone,
    )
    sp = pvlib.solarposition.get_solarposition(times, lat_deg, lon_deg)
    elevation = [float(v) for v in sp["apparent_elevation"]]
    azimuth = [float(v) for v in sp["azimuth"]]
    if min(elevation) <= 0:
        raise ValueError("shading_rule: the sun sets inside the window")
    reach = [
        shadow_reach_m(sizing.table_slant_m, array.tilt_deg, array.azimuth_deg, e, a)
        for e, a in zip(elevation, azimuth, strict=True)
    ]
    worst = max(range(len(reach)), key=lambda i: reach[i])
    no_shade = sizing.table_depth_m + reach[worst]
    aisle = sizing.table_depth_m + rule.min_clear_aisle_m
    pitch = max(no_shade, aisle)
    return RowPitch(
        no_shade_pitch_m=no_shade,
        aisle_floor_pitch_m=aisle,
        pitch_m=pitch,
        governing="shading" if no_shade >= aisle else "aisle",
        gcr=sizing.table_slant_m / pitch,
        no_shade_gcr=sizing.table_slant_m / no_shade,
        clear_aisle_m=pitch - sizing.table_depth_m,
        worst_sun_elevation_deg=elevation[worst],
        worst_sun_azimuth_deg=azimuth[worst],
        worst_time_local=times[worst].isoformat(),
        min_window_elevation_deg=min(elevation),
    )


# ---------------------------------------------------------------------------
# 4. Land and BESS pad
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LandConfig:
    """Allowances for the fenced area.

    Attributes:
        fence_to_array_m: Perimeter road and clearance between fence and array.
        internal_road_width_m: Width of a north-south road through the array.
        tables_between_internal_roads: Tables along a row between such roads.
        mv_station_count: Medium-voltage stations.
        mv_station_area_m2: Area of one MV station.
        equipment_clearance_m: Clearance around the BESS and MV group.
    """

    fence_to_array_m: float
    internal_road_width_m: float
    tables_between_internal_roads: int
    mv_station_count: int
    mv_station_area_m2: float
    equipment_clearance_m: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LandConfig":
        """Build from config, refusing missing or unknown keys."""
        kw = _strict(cls, raw, "land")
        for key in (
            "fence_to_array_m",
            "internal_road_width_m",
            "mv_station_area_m2",
            "equipment_clearance_m",
        ):
            kw[key] = _non_negative(kw[key], f"land.{key}")
        for key in ("tables_between_internal_roads", "mv_station_count"):
            kw[key] = _whole(kw[key], f"land.{key}")
        return cls(**kw)


@dataclass(frozen=True)
class BessFootprintConfig:
    """Containerised BESS units for the pad.

    Attributes:
        unit_energy_kwh: Energy of one unit.
        unit_power_kva: AC power of one unit.
        unit_length_m, unit_width_m: Unit plan dimensions.
        units_per_row: Units side by side on the pad.
        unit_spacing_m: Clear spacing between units and to the pad edge.
    """

    unit_energy_kwh: float
    unit_power_kva: float
    unit_length_m: float
    unit_width_m: float
    units_per_row: int
    unit_spacing_m: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "BessFootprintConfig":
        """Build from config, refusing missing or unknown keys."""
        kw = _strict(cls, raw, "bess_footprint")
        for key in (
            "unit_energy_kwh",
            "unit_power_kva",
            "unit_length_m",
            "unit_width_m",
        ):
            kw[key] = _positive(kw[key], f"bess_footprint.{key}")
        kw["units_per_row"] = _whole(
            kw["units_per_row"], "bess_footprint.units_per_row"
        )
        kw["unit_spacing_m"] = _non_negative(
            kw["unit_spacing_m"], "bess_footprint.unit_spacing_m"
        )
        return cls(**kw)


@dataclass(frozen=True)
class EquipmentArea:
    """The BESS pad and MV stations, as one rectangular group.

    Attributes:
        bess_units: Containers, enough for both the energy and the power.
        bess_units_for_energy: Containers the energy alone needs.
        bess_units_for_power: Containers the power alone needs (unit kVA read as kW).
        bess_installed_energy_mwh: Nameplate energy of the containers.
        bess_pad_length_m, bess_pad_width_m: Pad dimensions including spacing.
        bess_pad_area_m2: Pad area.
        mv_area_m2: MV stations' area.
        group_length_m, group_width_m: The group rectangle (pad plus MV strip).
        footprint_length_m, footprint_width_m: The group with its clearance all round.
        footprint_area_m2: Land the group takes.
    """

    bess_units: int
    bess_units_for_energy: int
    bess_units_for_power: int
    bess_installed_energy_mwh: float
    bess_pad_length_m: float
    bess_pad_width_m: float
    bess_pad_area_m2: float
    mv_area_m2: float
    group_length_m: float
    group_width_m: float
    footprint_length_m: float
    footprint_width_m: float
    footprint_area_m2: float


def equipment_area(
    *,
    bess_power_mw: float,
    bess_energy_mwh: float,
    bess: BessFootprintConfig,
    land: LandConfig,
) -> EquipmentArea:
    """Containers for the BESS rating, their pad, the MV stations and the clearance."""
    for_energy = math.ceil(bess_energy_mwh * 1000.0 / bess.unit_energy_kwh - 1e-12)
    for_power = math.ceil(bess_power_mw * 1000.0 / bess.unit_power_kva - 1e-12)
    units = max(for_energy, for_power)
    per_row = min(bess.units_per_row, units)
    rows = math.ceil(units / per_row)
    pad_len = per_row * bess.unit_length_m + (per_row + 1) * bess.unit_spacing_m
    pad_w = rows * bess.unit_width_m + (rows + 1) * bess.unit_spacing_m
    mv = land.mv_station_count * land.mv_station_area_m2
    group_w = pad_w + mv / pad_len
    c = land.equipment_clearance_m
    return EquipmentArea(
        bess_units=units,
        bess_units_for_energy=for_energy,
        bess_units_for_power=for_power,
        bess_installed_energy_mwh=units * bess.unit_energy_kwh / 1000.0,
        bess_pad_length_m=pad_len,
        bess_pad_width_m=pad_w,
        bess_pad_area_m2=pad_len * pad_w,
        mv_area_m2=mv,
        group_length_m=pad_len,
        group_width_m=group_w,
        footprint_length_m=pad_len + 2 * c,
        footprint_width_m=group_w + 2 * c,
        footprint_area_m2=(pad_len + 2 * c) * (group_w + 2 * c),
    )


def row_length_m(
    tables: int, sizing: ArraySizing, land: LandConfig, gap: float
) -> float:
    """Length of ``tables`` tables along a row, with gaps and north-south roads."""
    if tables < 1:
        return 0.0
    roads = (tables - 1) // land.tables_between_internal_roads
    gaps = tables - 1 - roads
    return (
        tables * sizing.table_length_ew_m
        + gaps * gap
        + roads * land.internal_road_width_m
    )


@dataclass(frozen=True)
class LandArea:
    """Fenced area of a compact rectangular array block plus the equipment group.

    Attributes:
        rows: Rows in the block.
        tables_per_row: Tables per row (the last row may be short).
        block_length_ew_m, block_depth_ns_m: The array block.
        array_block_area_m2: Block area.
        fenced_length_ew_m, fenced_depth_ns_m: The array block with the perimeter
            allowance on every side.
        fenced_array_area_m2: That rectangle's area.
        equipment_area_m2: The BESS and MV group with its clearance.
        fenced_area_m2: Total fenced land.
        fenced_area_ha: The same in hectares.
        land_per_mwp_ha: Fenced hectares per DC MWp.
    """

    rows: int
    tables_per_row: int
    block_length_ew_m: float
    block_depth_ns_m: float
    array_block_area_m2: float
    fenced_length_ew_m: float
    fenced_depth_ns_m: float
    fenced_array_area_m2: float
    equipment_area_m2: float
    fenced_area_m2: float
    fenced_area_ha: float
    land_per_mwp_ha: float


def compact_land_area(
    *,
    sizing: ArraySizing,
    pitch: RowPitch,
    array: ArrayConfig,
    land: LandConfig,
    equipment: EquipmentArea,
) -> LandArea:
    """Smallest fenced rectangle over every row count, plus the equipment footprint.

    For each row count ``R`` the block is ``ceil(tables / R)`` tables long and
    ``(R - 1) * pitch + table depth`` deep; the perimeter allowance is added on all four
    sides; the row count with the least fenced area is kept.
    """
    best: Optional[LandArea] = None
    f = land.fence_to_array_m
    for rows in range(1, sizing.tables + 1):
        per_row = math.ceil(sizing.tables / rows)
        if (rows - 1) * per_row >= sizing.tables:
            continue  # an empty last row: not a distinct layout
        length = row_length_m(per_row, sizing, land, array.table_gap_ew_m)
        depth = (rows - 1) * pitch.pitch_m + sizing.table_depth_m
        fenced = (length + 2 * f) * (depth + 2 * f)
        total = fenced + equipment.footprint_area_m2
        if best is None or total < best.fenced_area_m2:
            best = LandArea(
                rows=rows,
                tables_per_row=per_row,
                block_length_ew_m=length,
                block_depth_ns_m=depth,
                array_block_area_m2=length * depth,
                fenced_length_ew_m=length + 2 * f,
                fenced_depth_ns_m=depth + 2 * f,
                fenced_array_area_m2=fenced,
                equipment_area_m2=equipment.footprint_area_m2,
                fenced_area_m2=total,
                fenced_area_ha=total / 1.0e4,
                land_per_mwp_ha=total / 1.0e4 / sizing.dc_capacity_mw,
            )
    assert best is not None  # tables >= 1 gives at least one layout
    return best


# ---------------------------------------------------------------------------
# 5. Site fit
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SiteFitConfig:
    """Inputs of the site fit.

    Attributes:
        site_geojson: The placeholder lot and turbine (PR 1).
        coastline_geojson: Coastline the coastal setback is measured from.
        wind_siting_config: Config holding the ``site`` frame and ``coastal_setback``.
        foundation_diameter_m: Turbine foundation diameter.
        crane_pad_length_ew_m, crane_pad_width_ns_m: Crane hardstand, east of the
            foundation.
        equipment_search_step_m: Grid step of the search for the equipment position.
        geojson_decimals: Decimal places of written coordinates.
    """

    site_geojson: str
    coastline_geojson: str
    wind_siting_config: str
    foundation_diameter_m: float
    crane_pad_length_ew_m: float
    crane_pad_width_ns_m: float
    equipment_search_step_m: float
    geojson_decimals: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "SiteFitConfig":
        """Build from config, refusing missing or unknown keys."""
        kw = _strict(cls, raw, "site_fit")
        for key in ("site_geojson", "coastline_geojson", "wind_siting_config"):
            kw[key] = str(kw[key])
        for key in (
            "foundation_diameter_m",
            "crane_pad_length_ew_m",
            "crane_pad_width_ns_m",
        ):
            kw[key] = _non_negative(kw[key], f"site_fit.{key}")
        kw["equipment_search_step_m"] = _positive(
            kw["equipment_search_step_m"], "site_fit.equipment_search_step_m"
        )
        kw["geojson_decimals"] = _whole(
            kw["geojson_decimals"], "site_fit.geojson_decimals"
        )
        return cls(**kw)


@dataclass(frozen=True)
class SiteGeometry:
    """The lot and turbine in the local frame.

    Attributes:
        frame: The local frame.
        lot_ring: Lot corners ``(east, north)``, closed ring not repeated.
        turbine: Tower position.
        coastline: Coastline polylines.
    """

    frame: LocalFrame
    lot_ring: Tuple[EastNorth, ...]
    turbine: EastNorth
    coastline: Tuple[Tuple[EastNorth, ...], ...]


def site_geometry(
    site_geojson: Mapping[str, Any],
    coastline_geojson: Mapping[str, Any],
    frame: LocalFrame,
) -> SiteGeometry:
    """Read the lot polygon and turbine point of a site FeatureCollection.

    Raises:
        ValueError: If the collection lacks one Polygon and one Point.
    """
    ring: Optional[List[EastNorth]] = None
    turbine: Optional[EastNorth] = None
    for feature in site_geojson.get("features", []):
        geom = feature.get("geometry") or {}
        if geom.get("type") == "Polygon":
            outer = geom["coordinates"][0]
            ring = [frame.to_east_north(float(c[0]), float(c[1])) for c in outer[:-1]]
        elif geom.get("type") == "Point":
            c = geom["coordinates"]
            turbine = frame.to_east_north(float(c[0]), float(c[1]))
    if ring is None or turbine is None:
        raise ValueError("site GeoJSON needs one Polygon (lot) and one Point (turbine)")
    lines = coastline_lines_east_north(coastline_geojson, frame)
    return SiteGeometry(
        frame=frame,
        lot_ring=tuple(ring),
        turbine=turbine,
        coastline=tuple(tuple(line) for line in lines),
    )


@dataclass(frozen=True)
class SiteFit:
    """Whether the array and equipment fit the lot.

    Attributes:
        lot_area_m2: Lot area.
        coastal_strip_in_lot_m2: Lot area inside the coastal setback.
        foundation_in_lot_m2: Lot area under the foundation, outside the strip.
        crane_pad_in_lot_m2: Lot area under the crane pad, outside the strip and
            foundation.
        usable_area_m2: Lot less those three.
        array_region_area_m2: Usable area less the perimeter allowance.
        required_fenced_area_m2: The compact fenced area the unit needs.
        area_margin_m2: Usable area less the required fenced area.
        equipment_placed: Whether the BESS and MV group found a position.
        equipment_centre: Its centre ``(east, north)``, if placed.
        tables_required: Tables of the array.
        tables_that_fit: Tables the packing places on the lot.
        fits: ``tables_that_fit >= tables_required`` and the equipment is placed.
        max_dc_capacity_mw: DC peak of every table that fits.
        packed_rows: Rows used by the required tables.
        remaining_area_m2: Usable area less the land share of the required tables (their
            row-pitch strip and gaps) and the equipment footprint.
    """

    lot_area_m2: float
    coastal_strip_in_lot_m2: float
    foundation_in_lot_m2: float
    crane_pad_in_lot_m2: float
    usable_area_m2: float
    array_region_area_m2: float
    required_fenced_area_m2: float
    area_margin_m2: float
    equipment_placed: bool
    equipment_centre: Optional[EastNorth]
    tables_required: int
    tables_that_fit: int
    fits: bool
    max_dc_capacity_mw: float
    packed_rows: int
    remaining_area_m2: float


@dataclass(frozen=True)
class PackedLayout:
    """The site fit and its geometry, for reporting.

    Attributes:
        fit: The summary.
        tables: Every placed table as an ``(east_min, north_min, east_max, north_max)``
            box, required tables first.
        equipment_box: The group's box with clearance, if placed.
        exclusions: Name to shapely geometry of each exclusion.
        usable: The usable shapely polygon.
    """

    fit: SiteFit
    tables: Tuple[Tuple[float, float, float, float], ...]
    equipment_box: Optional[Tuple[float, float, float, float]]
    exclusions: Mapping[str, Any]
    usable: Any


def _line_interval_sets(region: Any, y: float) -> List[Tuple[float, float]]:
    """East-west intervals of the horizontal line at ``y`` inside ``region``."""
    from shapely.geometry import LineString

    minx, _, maxx, _ = region.bounds
    cut = region.intersection(LineString([(minx - 1.0, y), (maxx + 1.0, y)]))
    parts: Sequence[Any] = getattr(cut, "geoms", [cut])
    out = []
    for part in parts:
        if part.is_empty or part.geom_type != "LineString":
            continue
        xs = [c[0] for c in part.coords]
        out.append((min(xs), max(xs)))
    return sorted(out)


def _intersect_intervals(
    a: Sequence[Tuple[float, float]], b: Sequence[Tuple[float, float]]
) -> List[Tuple[float, float]]:
    """Pairwise intersection of two sorted interval lists."""
    out = []
    for lo1, hi1 in a:
        for lo2, hi2 in b:
            lo, hi = max(lo1, lo2), min(hi1, hi2)
            if hi > lo:
                out.append((lo, hi))
    return sorted(out)


def pack_tables(
    region: Any,
    *,
    sizing: ArraySizing,
    pitch_m: float,
    array: ArrayConfig,
    land: LandConfig,
) -> List[Tuple[float, float, float, float]]:
    """Fill ``region`` with east-west rows of tables at ``pitch_m``, south to north.

    Rows start at the region's southern bound. In each row, the stretches where the
    table's full depth lies inside the region are filled from the west, with the table
    gap and a north-south road after every configured number of tables. Every table box
    is checked against the region before it is kept.
    """
    from shapely.geometry import box

    if region.is_empty:
        return []
    _, miny, _, maxy = region.bounds
    depth = sizing.table_depth_m
    length = sizing.table_length_ew_m
    eps = 1e-6
    tables: List[Tuple[float, float, float, float]] = []
    y = miny
    while y + depth <= maxy + eps:
        spans = _line_interval_sets(region, y + eps)
        for frac in (0.5, 1.0):
            spans = _intersect_intervals(
                spans, _line_interval_sets(region, y + frac * depth - eps)
            )
        for lo, hi in spans:
            x = lo
            in_row = 0
            while x + length <= hi + eps:
                candidate = (x, y, x + length, y + depth)
                if region.covers(box(*candidate)):
                    tables.append(candidate)
                    in_row += 1
                    step = (
                        land.internal_road_width_m
                        if in_row % land.tables_between_internal_roads == 0
                        else array.table_gap_ew_m
                    )
                    x += length + step
                else:
                    x += 0.5
        y += pitch_m
    return tables


def place_equipment(
    region: Any, equipment: EquipmentArea, step_m: float
) -> Optional[Tuple[float, float, float, float]]:
    """Easternmost position of the equipment footprint wholly inside ``region``.

    Candidate centres lie on a ``step_m`` grid over the region's bounds; among those
    whose footprint the region covers, the easternmost wins, ties going to the one
    nearest the region's centroid latitude.
    """
    from shapely.geometry import box

    minx, miny, maxx, maxy = region.bounds
    half_l = equipment.footprint_length_m / 2.0
    half_w = equipment.footprint_width_m / 2.0
    cy = region.centroid.y
    best: Optional[Tuple[float, float, float, float]] = None
    best_key: Optional[Tuple[float, float]] = None
    nx = int((maxx - minx) / step_m) + 1
    ny = int((maxy - miny) / step_m) + 1
    for i in range(nx):
        x = minx + i * step_m
        for j in range(ny):
            y = miny + j * step_m
            candidate = (x - half_l, y - half_w, x + half_l, y + half_w)
            if region.covers(box(*candidate)):
                key = (x, -abs(y - cy))
                if best_key is None or key > best_key:
                    best, best_key = candidate, key
    return best


def fit_site(
    site: SiteGeometry,
    *,
    coastal: CoastalSetbackConfig,
    cfg: SiteFitConfig,
    sizing: ArraySizing,
    pitch: RowPitch,
    array: ArrayConfig,
    land: LandConfig,
    equipment: EquipmentArea,
    required_fenced_area_m2: float,
) -> PackedLayout:
    """Pack the array and place the equipment on the lot less the exclusions.

    Exclusions: the coastal setback (reservation and restricted area, from the mapped
    coastline plus any seaward-reference offset), the foundation disc at the tower, and
    the crane hardstand east of it. The perimeter allowance is then taken inward from the
    usable area, the equipment group is placed, and the rest is packed with tables.
    """
    _require_shapely()
    from shapely.geometry import Point, Polygon, box

    lot = Polygon(site.lot_ring)
    coast_zone = build_setback_zone(
        [list(line) for line in site.coastline],
        coastal.seaward_reference_offset_m + coastal.total_setback_m,
    )
    te, tn = site.turbine
    r = cfg.foundation_diameter_m / 2.0
    foundation = Point(te, tn).buffer(r, quad_segs=64)
    pad = box(
        te + r,
        tn - cfg.crane_pad_width_ns_m / 2.0,
        te + r + cfg.crane_pad_length_ew_m,
        tn + cfg.crane_pad_width_ns_m / 2.0,
    )
    strip = lot.intersection(coast_zone)
    after_strip = lot.difference(coast_zone)
    found_in = after_strip.intersection(foundation)
    after_found = after_strip.difference(foundation)
    pad_in = after_found.intersection(pad)
    usable = after_found.difference(pad)
    region = usable.buffer(-land.fence_to_array_m, join_style="mitre")

    eq_box = place_equipment(region, equipment, cfg.equipment_search_step_m)
    pack_region = region if eq_box is None else region.difference(box(*eq_box))
    tables = pack_tables(
        pack_region, sizing=sizing, pitch_m=pitch.pitch_m, array=array, land=land
    )
    required = tables[: sizing.tables]
    rows = len({round(t[1], 6) for t in required})
    share = sizing.tables * (sizing.table_length_ew_m + array.table_gap_ew_m)
    share *= pitch.pitch_m
    fit = SiteFit(
        lot_area_m2=float(lot.area),
        coastal_strip_in_lot_m2=float(strip.area),
        foundation_in_lot_m2=float(found_in.area),
        crane_pad_in_lot_m2=float(pad_in.area),
        usable_area_m2=float(usable.area),
        array_region_area_m2=float(region.area),
        required_fenced_area_m2=required_fenced_area_m2,
        area_margin_m2=float(usable.area) - required_fenced_area_m2,
        equipment_placed=eq_box is not None,
        equipment_centre=(
            None
            if eq_box is None
            else ((eq_box[0] + eq_box[2]) / 2.0, (eq_box[1] + eq_box[3]) / 2.0)
        ),
        tables_required=sizing.tables,
        tables_that_fit=len(tables),
        fits=eq_box is not None and len(tables) >= sizing.tables,
        max_dc_capacity_mw=len(tables) * sizing.table_power_w / 1.0e6,
        packed_rows=rows,
        remaining_area_m2=float(usable.area) - share - equipment.footprint_area_m2,
    )
    return PackedLayout(
        fit=fit,
        tables=tuple(tables),
        equipment_box=eq_box,
        exclusions={
            "coastal_setback_strip": strip,
            "turbine_foundation": found_in,
            "crane_hardstand": pad_in,
        },
        usable=usable,
    )


def _ring_lon_lat(
    frame: LocalFrame, coords: Sequence[Tuple[float, float]], decimals: int
) -> List[List[float]]:
    """Unproject a closed ring to rounded ``[lon, lat]`` pairs."""
    out = []
    for e, n in coords:
        lon, lat = frame.to_lon_lat(float(e), float(n))
        out.append([round(lon, decimals), round(lat, decimals)])
    return out


def _polygons(geom: Any) -> List[Any]:
    """The Polygon parts of a shapely geometry."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]


def layout_feature_collection(
    layout: PackedLayout, frame: LocalFrame, *, required: int, decimals: int
) -> Dict[str, Any]:
    """The packed layout as an RFC 7946 FeatureCollection (placeholder, unsurveyed)."""
    features: List[Dict[str, Any]] = []
    for name, geom in layout.exclusions.items():
        for poly in _polygons(geom):
            features.append(
                {
                    "type": "Feature",
                    "properties": {"kind": "exclusion", "name": name},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            _ring_lon_lat(frame, list(poly.exterior.coords), decimals)
                        ],
                    },
                }
            )
    if layout.equipment_box is not None:
        x0, y0, x1, y1 = layout.equipment_box
        ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "kind": "equipment",
                    "name": "BESS pad and MV stations, with clearance",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_ring_lon_lat(frame, ring, decimals)],
                },
            }
        )
    for i, (x0, y0, x1, y1) in enumerate(layout.tables[:required]):
        ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        features.append(
            {
                "type": "Feature",
                "properties": {"kind": "pv_table", "index": i},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_ring_lon_lat(frame, ring, decimals)],
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "properties": {
            "placeholder": True,
            "surveyed": False,
            "note": (
                "Indicative packing of the Blue Whale PV tables and BESS group on the "
                "PR 1 placeholder lot. Generated by scripts/run_blue_whale_solar_bess_v14.py "
                "from conf/blue_whale_solar_bess.yaml. Not a layout design."
            ),
        },
        "features": features,
    }


def as_dict(obj: Any) -> Dict[str, Any]:
    """A result dataclass as a JSON-ready dict."""
    return asdict(obj)


__all__ = [
    "ArrayConfig",
    "ArraySizing",
    "BessFootprintConfig",
    "EquipmentArea",
    "LandArea",
    "LandConfig",
    "ModuleSpec",
    "PackedLayout",
    "RowPitch",
    "ShadingRuleConfig",
    "SiteFit",
    "SiteFitConfig",
    "SiteGeometry",
    "StringDesign",
    "StringDesignConfig",
    "as_dict",
    "compact_land_area",
    "design_string",
    "equipment_area",
    "fit_site",
    "layout_feature_collection",
    "pack_tables",
    "place_equipment",
    "row_length_m",
    "row_pitch",
    "shadow_reach_m",
    "site_geometry",
    "size_array",
]
