"""Single-turbine siting screen: coastal setback placement, tip-height setback, shadow flicker.

Three calculations for one wind turbine on a small coastal lot, all driven by config
(``conf/blue_whale_wind_siting.yaml``; ``ARCH-01``, ``FRAMEWORK-02``):

1. **Coastal placement.** The westernmost point on a given latitude whose distance from a
   coastline polyline is at least the coastal setback, found by buffering the coastline with
   :func:`analytics.gis.exclusion_mask.build_setback_zone` and cutting the latitude line
   with that zone.
2. **Tip-height setback.** The distance from the turbine to each edge of the lot against
   a setback of a configured multiple of tip height, and the area of the setback disc
   that falls outside the lot. The disc is again built by
   :func:`~analytics.gis.exclusion_mask.build_setback_zone`.
3. **Shadow flicker.** Hours per year and minutes per day of rotor shadow at receptors,
   for the astronomical worst case and, where a sunshine record is supplied, an expected
   case. The worst case follows the usual convention: the sun is always unobstructed, the
   rotor always turns, and the rotor disc always faces the sun. A receptor is in shadow
   when the ray from it towards the sun passes within one rotor radius of the hub.
   Sun position comes from ``pvlib``.

The expected case keeps the worst-case rotor orientation, which is conservative. It counts
a time step only when the hour's direct normal irradiance meets the WMO sunshine threshold,
and scales the result by the probability that the rotor is turning. The caller supplies
that probability.

Geometry is computed in a local transverse Mercator frame (``+proj=tmerc``, scale 1 at the
origin, axes east and true north). Over the few hundred metres of a lot, its scale error is
below one part in a million.

``FRAMEWORK-01``: ``pyproj``, ``shapely`` and ``pvlib`` are optional extras and are imported
at call time, each behind a guard that raises an actionable ``ImportError``. Nothing here
reads a power curve. The screen is KPI-neutral: it feeds no finance path.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from analytics.gis.exclusion_mask import _require_shapely, build_setback_zone

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
EastNorth = Tuple[float, float]


def _require_pyproj() -> Any:
    """Return the ``pyproj`` module or raise an actionable error if it is absent."""
    try:
        import pyproj

        return pyproj
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The siting screen needs pyproj from the [gis] extra: "
            "pip install -e '.[gis]'."
        ) from exc


def _require_pvlib() -> Any:
    """Return the ``pvlib`` module or raise an actionable error if it is absent."""
    try:
        import pvlib

        return pvlib
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Shadow flicker needs pvlib from the [solar] extra: "
            "pip install -e '.[solar]'."
        ) from exc


# ---------------------------------------------------------------------------
# Configuration (strict: every key required, no extra keys)
# ---------------------------------------------------------------------------
def _strict_kwargs(cls: type, raw: Mapping[str, Any], where: str) -> Dict[str, Any]:
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


@dataclass(frozen=True)
class TurbineGeometry:
    """Rotor geometry of one turbine.

    Attributes:
        hub_height_m: Hub height above ground.
        rotor_diameter_m: Rotor diameter.
    """

    hub_height_m: float
    rotor_diameter_m: float

    def __post_init__(self) -> None:
        """Reject non-physical geometry."""
        if self.rotor_diameter_m <= 0 or self.hub_height_m <= 0:
            raise ValueError("hub height and rotor diameter must be positive")
        if self.rotor_diameter_m / 2.0 >= self.hub_height_m:
            raise ValueError("rotor radius must be below hub height (tip clearance)")

    @property
    def rotor_radius_m(self) -> float:
        """Rotor radius (half the diameter)."""
        return self.rotor_diameter_m / 2.0

    @property
    def tip_height_m(self) -> float:
        """Blade tip height at the top of its sweep."""
        return self.hub_height_m + self.rotor_radius_m


@dataclass(frozen=True)
class CoastalSetbackConfig:
    """Coastal setback inputs.

    Attributes:
        reservation_m: Width of the no-build reservation area.
        restricted_m: Width of the restricted (soft) area landward of the reservation.
        seaward_reference_offset_m: Distance from the mapped coastline landward to the
            line the setback is measured from. Zero places that line on the coastline.
        foundation_clearance_m: Extra distance between the setback line and the tower
            centre. Zero puts the tower centre on the setback line.
        source: Citation for the setback widths.
    """

    reservation_m: float
    restricted_m: float
    seaward_reference_offset_m: float
    foundation_clearance_m: float
    source: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CoastalSetbackConfig":
        """Build from a config mapping, refusing missing or unknown keys."""
        kw = _strict_kwargs(cls, raw, "coastal_setback")
        for key in (
            "reservation_m",
            "restricted_m",
            "seaward_reference_offset_m",
            "foundation_clearance_m",
        ):
            kw[key] = float(kw[key])
            if kw[key] < 0:
                raise ValueError(f"coastal_setback.{key} must be >= 0")
        kw["source"] = str(kw["source"])
        return cls(**kw)

    @property
    def total_setback_m(self) -> float:
        """Reservation plus restricted width."""
        return self.reservation_m + self.restricted_m

    @property
    def tower_distance_from_coastline_m(self) -> float:
        """Minimum distance from the mapped coastline to the tower centre."""
        return (
            self.seaward_reference_offset_m
            + self.total_setback_m
            + self.foundation_clearance_m
        )


@dataclass(frozen=True)
class TipSetbackConfig:
    """Tip-height setback to the lot boundary.

    Attributes:
        tip_height_multiple: Setback distance as a multiple of tip height.
        source: Basis of the multiple.
    """

    tip_height_multiple: float
    source: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TipSetbackConfig":
        """Build from a config mapping, refusing missing or unknown keys."""
        kw = _strict_kwargs(cls, raw, "tip_setback")
        kw["tip_height_multiple"] = float(kw["tip_height_multiple"])
        if kw["tip_height_multiple"] <= 0:
            raise ValueError("tip_setback.tip_height_multiple must be positive")
        kw["source"] = str(kw["source"])
        return cls(**kw)


@dataclass(frozen=True)
class ShadowFlickerConfig:
    """Shadow-flicker inputs. Thresholds and their sources live in config.

    Attributes:
        year: Calendar year of the sun path.
        timezone: IANA zone used to group time steps into local days.
        time_step_minutes: Time step of the sun path.
        min_sun_elevation_deg: Sun elevation below which no shadow is counted.
        max_shadow_distance_rotor_diameters: Receptors farther from the tower than this
            many rotor diameters are not counted.
        receptor_height_m: Height of the receptor point above ground.
        grid_half_width_m: Half-width of the square receptor grid around the turbine.
        grid_spacing_m: Grid spacing.
        worst_case_hours_per_year_limit: Worst-case annual threshold.
        worst_case_minutes_per_day_limit: Worst-case daily threshold.
        expected_hours_per_year_limit: Expected-case annual threshold.
        sunshine_dni_threshold_wm2: Direct normal irradiance at or above which an hour
            counts as sunny in the expected case.
        sunshine_tmy_csv: Hourly UTC record with a ``dni`` column, or ``None`` to skip
            the expected case.
        threshold_sources: Citation for each threshold, keyed by field name.
    """

    year: int
    timezone: str
    time_step_minutes: int
    min_sun_elevation_deg: float
    max_shadow_distance_rotor_diameters: float
    receptor_height_m: float
    grid_half_width_m: float
    grid_spacing_m: float
    worst_case_hours_per_year_limit: float
    worst_case_minutes_per_day_limit: float
    expected_hours_per_year_limit: float
    sunshine_dni_threshold_wm2: float
    sunshine_tmy_csv: Optional[str]
    threshold_sources: Dict[str, str]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ShadowFlickerConfig":
        """Build from a config mapping, refusing missing or unknown keys."""
        kw = _strict_kwargs(cls, raw, "shadow_flicker")
        kw["year"] = int(kw["year"])
        kw["time_step_minutes"] = int(kw["time_step_minutes"])
        if kw["time_step_minutes"] <= 0 or 1440 % kw["time_step_minutes"]:
            raise ValueError("shadow_flicker.time_step_minutes must divide 1440")
        for key in (
            "min_sun_elevation_deg",
            "max_shadow_distance_rotor_diameters",
            "receptor_height_m",
            "grid_half_width_m",
            "grid_spacing_m",
            "worst_case_hours_per_year_limit",
            "worst_case_minutes_per_day_limit",
            "expected_hours_per_year_limit",
            "sunshine_dni_threshold_wm2",
        ):
            kw[key] = float(kw[key])
        if kw["grid_spacing_m"] <= 0 or kw["grid_half_width_m"] < 0:
            raise ValueError("shadow_flicker grid spacing must be > 0, half-width >= 0")
        kw["timezone"] = str(kw["timezone"])
        tmy = kw["sunshine_tmy_csv"]
        kw["sunshine_tmy_csv"] = None if tmy in (None, "") else str(tmy)
        sources = dict(kw["threshold_sources"])
        needed = {
            "worst_case_hours_per_year_limit",
            "worst_case_minutes_per_day_limit",
            "expected_hours_per_year_limit",
            "min_sun_elevation_deg",
            "max_shadow_distance_rotor_diameters",
            "sunshine_dni_threshold_wm2",
            "receptor_height_m",
        }
        absent = sorted(needed - set(sources))
        if absent:
            raise ValueError(f"shadow_flicker.threshold_sources lacks {absent}")
        kw["threshold_sources"] = {str(k): str(v) for k, v in sources.items()}
        return cls(**kw)


# ---------------------------------------------------------------------------
# Local metric frame
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LocalFrame:
    """Transverse Mercator frame with scale 1 at its origin, axes east and true north.

    Attributes:
        origin_lat_deg: Latitude of the origin (WGS84).
        origin_lon_deg: Longitude of the origin (WGS84).
    """

    origin_lat_deg: float
    origin_lon_deg: float

    def _crs(self) -> str:
        return (
            f"+proj=tmerc +lat_0={self.origin_lat_deg} +lon_0={self.origin_lon_deg} "
            "+k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
        )

    def _transformer(self, *, inverse: bool) -> Any:
        pyproj = _require_pyproj()
        src, dst = ("EPSG:4326", self._crs())
        if inverse:
            src, dst = dst, src
        return pyproj.Transformer.from_crs(src, dst, always_xy=True)

    def to_east_north(self, lon_deg: float, lat_deg: float) -> EastNorth:
        """Project WGS84 longitude and latitude to local east and north metres."""
        east, north = self._transformer(inverse=False).transform(lon_deg, lat_deg)
        return float(east), float(north)

    def to_lon_lat(self, east_m: float, north_m: float) -> Tuple[float, float]:
        """Unproject local east and north metres to WGS84 longitude and latitude."""
        lon, lat = self._transformer(inverse=True).transform(east_m, north_m)
        return float(lon), float(lat)


def coastline_lines_east_north(
    geojson: Mapping[str, Any], frame: LocalFrame
) -> List[List[EastNorth]]:
    """Project every LineString in a coastline FeatureCollection to the local frame.

    Args:
        geojson: FeatureCollection of ``LineString`` features in ``[lon, lat]`` order.
        frame: Local frame to project into.

    Returns:
        One list of ``(east, north)`` vertices per feature, in feature order.

    Raises:
        ValueError: If a feature is not a LineString with at least two vertices.
    """
    lines: List[List[EastNorth]] = []
    for feature in geojson.get("features", []):
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") != "LineString" or len(coords) < 2:
            raise ValueError("coastline features must be LineStrings of >= 2 vertices")
        lines.append([frame.to_east_north(float(c[0]), float(c[1])) for c in coords])
    if not lines:
        raise ValueError("coastline FeatureCollection has no features")
    return lines


# ---------------------------------------------------------------------------
# 1. Coastal placement
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoastalPlacement:
    """Result of placing the turbine at the coastal setback.

    Attributes:
        coastline_crossing_east_m: East coordinate where the latitude line meets the
            westernmost coastline (local frame).
        turbine_east_m: East coordinate of the placed tower centre.
        turbine_north_m: North coordinate of the placed tower centre.
        distance_to_coastline_m: Shortest distance from the tower to the coastline.
    """

    coastline_crossing_east_m: float
    turbine_east_m: float
    turbine_north_m: float
    distance_to_coastline_m: float


def _latitude_crossings(
    lines: Sequence[Sequence[EastNorth]], north_m: float
) -> List[float]:
    """East coordinates where any coastline segment crosses ``north = north_m``."""
    out: List[float] = []
    for line in lines:
        for (e1, n1), (e2, n2) in zip(line, line[1:], strict=False):
            if n1 == n2:
                continue
            if (n1 - north_m) * (n2 - north_m) <= 0:
                t = (north_m - n1) / (n2 - n1)
                out.append(e1 + t * (e2 - e1))
    return sorted(out)


def place_at_coastal_setback(
    lines: Sequence[Sequence[EastNorth]],
    *,
    north_m: float,
    min_distance_m: float,
    search_east_m: float,
) -> CoastalPlacement:
    """Find the westernmost point east of the coast that clears the setback.

    The search runs along the line ``north = north_m`` from the westernmost coastline
    crossing to ``search_east_m``, and returns the first point whose distance from every
    coastline is at least ``min_distance_m``.

    Args:
        lines: Coastline polylines in the local frame, with sea to the west of the
            westernmost crossing.
        north_m: North coordinate of the search line.
        min_distance_m: Required distance from the coastline to the tower centre.
        search_east_m: East limit of the search.

    Returns:
        The placement.

    Raises:
        ValueError: If no coastline crosses the search line, or no compliant point lies
            within the search range.
    """
    _require_shapely()
    from shapely.geometry import LineString, MultiLineString, Point

    crossings = _latitude_crossings(lines, north_m)
    if not crossings:
        raise ValueError(f"no coastline crosses north={north_m} m")
    west = crossings[0]
    zone = build_setback_zone(
        [MultiLineString([list(map(tuple, ln)) for ln in lines])], min_distance_m
    )
    ray = LineString([(west, north_m), (search_east_m, north_m)])
    free = ray.difference(zone)
    parts = list(getattr(free, "geoms", [free]))
    starts = sorted(
        min(c[0] for c in part.coords)
        for part in parts
        if not part.is_empty and part.length > 0
    )
    if not starts:
        raise ValueError("no point on the search line clears the coastal setback")
    east = float(starts[0])
    coast = MultiLineString([list(map(tuple, ln)) for ln in lines])
    return CoastalPlacement(
        coastline_crossing_east_m=float(west),
        turbine_east_m=east,
        turbine_north_m=float(north_m),
        distance_to_coastline_m=float(Point(east, north_m).distance(coast)),
    )


# ---------------------------------------------------------------------------
# Placeholder lot: a square whose west edge lies along the coastline
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SquareLot:
    """A square lot in the local frame.

    Attributes:
        corners: ``(east, north)`` corners, counter-clockwise, first not repeated, in the
            order: south-west, south-east, north-east, north-west of the lot's own axes.
        edge_bearing_deg: Bearing of the west edge, clockwise from true north.
        side_m: Side length.
        edge_max_deviation_m: Largest perpendicular distance between the west edge and
            the coastline points it was fitted to.
    """

    corners: Tuple[EastNorth, EastNorth, EastNorth, EastNorth]
    edge_bearing_deg: float
    side_m: float
    edge_max_deviation_m: float

    def receptors(self) -> Dict[str, EastNorth]:
        """Corner and edge-midpoint receptors, keyed by name."""
        sw, se, ne, nw = self.corners

        def mid(a: EastNorth, b: EastNorth) -> EastNorth:
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

        return {
            "corner_sw": sw,
            "corner_se": se,
            "corner_ne": ne,
            "corner_nw": nw,
            "mid_south": mid(sw, se),
            "mid_east": mid(se, ne),
            "mid_north": mid(ne, nw),
            "mid_west": mid(nw, sw),
        }


def _sample_polyline(line: Sequence[EastNorth], step_m: float) -> FloatArray:
    """Points every ``step_m`` along a polyline, vertices included."""
    pts: List[EastNorth] = [line[0]]
    for (e1, n1), (e2, n2) in zip(line, line[1:], strict=False):
        seg = math.hypot(e2 - e1, n2 - n1)
        k = max(int(math.ceil(seg / step_m)), 1)
        for i in range(1, k + 1):
            pts.append((e1 + (e2 - e1) * i / k, n1 + (n2 - n1) * i / k))
    return np.asarray(pts, dtype=np.float64)


def coast_aligned_square_lot(
    lines: Sequence[Sequence[EastNorth]],
    *,
    north_m: float,
    area_m2: float,
    sample_step_m: float,
) -> SquareLot:
    """Square lot whose west edge is the straight-line fit of the coast beside it.

    The coastline points within half a side of the west crossing at ``north_m`` are fitted
    with a total-least-squares line. The lot's west edge is parallel to that line and
    passes through the crossing, which is its midpoint; the lot extends landward (east).

    Args:
        lines: Coastline polylines in the local frame.
        north_m: North coordinate of the crossing that the west edge is centred on.
        area_m2: Lot area.
        sample_step_m: Spacing at which the coastline is sampled for the fit.

    Returns:
        The lot.

    Raises:
        ValueError: If the coastline does not cross ``north_m`` or the fit is degenerate.
    """
    if area_m2 <= 0 or sample_step_m <= 0:
        raise ValueError("area and sample step must be positive")
    crossings = _latitude_crossings(lines, north_m)
    if not crossings:
        raise ValueError(f"no coastline crosses north={north_m} m")
    anchor = np.array([crossings[0], north_m])
    side = math.sqrt(area_m2)
    pts = np.vstack([_sample_polyline(ln, sample_step_m) for ln in lines])
    near = pts[np.hypot(*(pts - anchor).T) <= side / 2.0]
    if len(near) < 3:
        raise ValueError("too few coastline points beside the lot to fit an edge")
    centred = near - near.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    direction = vt[0]
    if direction[1] < 0:  # point the edge direction northwards
        direction = -direction
    normal = np.array(
        [direction[1], -direction[0]]
    )  # direction rotated 90 deg clockwise
    if normal[0] < 0:  # landward = east
        normal = -normal
    half = side / 2.0
    sw = anchor - direction * half
    nw = anchor + direction * half
    se = sw + normal * side
    ne = nw + normal * side
    bearing = math.degrees(math.atan2(direction[0], direction[1])) % 360.0
    deviation = float(np.abs((near - anchor) @ normal).max())

    def pt(v: FloatArray) -> EastNorth:
        return (float(v[0]), float(v[1]))

    return SquareLot(
        corners=(pt(sw), pt(se), pt(ne), pt(nw)),
        edge_bearing_deg=bearing,
        side_m=side,
        edge_max_deviation_m=deviation,
    )


def site_feature_collection(
    *,
    frame: LocalFrame,
    lot: SquareLot,
    placement: CoastalPlacement,
    properties: Mapping[str, Any],
    turbine_properties: Mapping[str, Any],
    decimals: int,
) -> Dict[str, Any]:
    """Placeholder site as an RFC 7946 FeatureCollection (lot polygon and turbine point).

    Args:
        frame: Local frame the lot and placement are expressed in.
        lot: The lot.
        placement: The turbine placement.
        properties: Properties of the lot feature.
        turbine_properties: Properties of the turbine feature.
        decimals: Decimal places for longitude and latitude.

    Returns:
        A JSON-serialisable FeatureCollection.
    """
    ring = [frame.to_lon_lat(e, n) for e, n in lot.corners]
    ring.append(ring[0])
    lon_t, lat_t = frame.to_lon_lat(placement.turbine_east_m, placement.turbine_north_m)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": dict(properties),
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[round(lo, decimals), round(la, decimals)] for lo, la in ring]
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": dict(turbine_properties),
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(lon_t, decimals), round(lat_t, decimals)],
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# 2. Tip-height setback
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TipSetbackResult:
    """Tip-height setback against the lot boundary.

    Attributes:
        setback_m: Tip-height multiple times tip height.
        tip_height_m: Tip height.
        distance_to_lot_edges_m: Perpendicular distance from the tower to each edge.
        min_distance_to_lot_edge_m: Smallest of the above.
        lot_edges_breached: Edges closer to the tower than the setback.
        setback_disc_area_m2: Area of the setback disc (polygonal buffer).
        setback_disc_area_outside_lot_m2: Part of that area outside the lot.
        rotor_overhang_beyond_lot_m: How far the blade tip can reach past the nearest
            edge (rotor radius minus distance to that edge; zero if it cannot).
        fits_within_lot: True when the whole setback disc lies inside the lot.
    """

    setback_m: float
    tip_height_m: float
    distance_to_lot_edges_m: Dict[str, float]
    min_distance_to_lot_edge_m: float
    lot_edges_breached: List[str]
    setback_disc_area_m2: float
    setback_disc_area_outside_lot_m2: float
    rotor_overhang_beyond_lot_m: float
    fits_within_lot: bool


def tip_height_setback(
    lot: SquareLot,
    tower_en: EastNorth,
    turbine: TurbineGeometry,
    cfg: TipSetbackConfig,
) -> TipSetbackResult:
    """Screen the tip-height setback against the lot boundary.

    Args:
        lot: The lot.
        tower_en: Tower centre in the local frame.
        turbine: Rotor geometry.
        cfg: Setback multiple and its basis.

    Returns:
        The screen result.
    """
    _require_shapely()
    from shapely.geometry import LineString, Point, Polygon

    sw, se, ne, nw = lot.corners
    poly = Polygon([sw, se, ne, nw])
    edges = {
        "south": LineString([sw, se]),
        "east": LineString([se, ne]),
        "north": LineString([ne, nw]),
        "west": LineString([nw, sw]),
    }
    tower = Point(tower_en)
    distances = {name: float(tower.distance(e)) for name, e in edges.items()}
    setback = cfg.tip_height_multiple * turbine.tip_height_m
    disc = build_setback_zone([tower_en], setback)
    nearest = min(distances.values())
    return TipSetbackResult(
        setback_m=setback,
        tip_height_m=turbine.tip_height_m,
        distance_to_lot_edges_m=distances,
        min_distance_to_lot_edge_m=nearest,
        lot_edges_breached=sorted(n for n, d in distances.items() if d < setback),
        setback_disc_area_m2=float(disc.area),
        setback_disc_area_outside_lot_m2=float(disc.difference(poly).area),
        rotor_overhang_beyond_lot_m=max(turbine.rotor_radius_m - nearest, 0.0),
        fits_within_lot=bool(poly.contains(disc)),
    )


# ---------------------------------------------------------------------------
# 3. Shadow flicker
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SunPath:
    """Sun positions at the steps where the sun is above the elevation floor.

    Attributes:
        elevation_deg: Apparent sun elevation.
        azimuth_deg: Sun azimuth, clockwise from true north.
        day_index: Local day number (0-based) of each step.
        utc_hour_key: ``month * 10000 + day * 100 + hour`` in UTC, for joining an hourly
            record.
        step_minutes: Duration represented by each step.
        n_days: Number of local days in the period.
    """

    elevation_deg: FloatArray
    azimuth_deg: FloatArray
    day_index: npt.NDArray[np.int64]
    utc_hour_key: npt.NDArray[np.int64]
    step_minutes: float
    n_days: int

    def unit_vectors(self) -> Tuple[FloatArray, FloatArray, FloatArray]:
        """East, north and up components of the unit vector towards the sun."""
        el = np.radians(self.elevation_deg)
        az = np.radians(self.azimuth_deg)
        return np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)


def solar_path(lat_deg: float, lon_deg: float, cfg: ShadowFlickerConfig) -> SunPath:
    """Sun path for one year at a point, from ``pvlib``.

    Args:
        lat_deg: Latitude of the turbine.
        lon_deg: Longitude of the turbine.
        cfg: Year, time step, zone and elevation floor.

    Returns:
        Steps with apparent elevation at or above the floor.
    """
    pvlib = _require_pvlib()
    import pandas as pd

    times = pd.date_range(
        start=f"{cfg.year}-01-01",
        end=f"{cfg.year + 1}-01-01",
        freq=f"{cfg.time_step_minutes}min",
        tz=cfg.timezone,
        inclusive="left",
    )
    pos = pvlib.solarposition.get_solarposition(times, lat_deg, lon_deg)
    el = pos["apparent_elevation"].to_numpy(dtype=np.float64)
    az = pos["azimuth"].to_numpy(dtype=np.float64)
    keep = el >= cfg.min_sun_elevation_deg
    utc = times.tz_convert("UTC")
    key = (utc.month * 10000 + utc.day * 100 + utc.hour).to_numpy(dtype=np.int64)
    day = (times.dayofyear - 1).to_numpy(dtype=np.int64)
    return SunPath(
        elevation_deg=el[keep],
        azimuth_deg=az[keep],
        day_index=day[keep],
        utc_hour_key=key[keep],
        step_minutes=float(cfg.time_step_minutes),
        n_days=int(day.max()) + 1,
    )


def shadow_mask(
    receptor_en: EastNorth,
    *,
    turbine: TurbineGeometry,
    receptor_height_m: float,
    max_distance_m: float,
    sun: SunPath,
    tower_en: EastNorth = (0.0, 0.0),
) -> BoolArray:
    """Steps at which the receptor sees the rotor disc in front of the sun.

    The rotor is a disc of one rotor radius centred on the hub and facing the sun, so
    the receptor is in shadow when the ray from it towards the sun passes within one
    rotor radius of the hub.

    Args:
        receptor_en: Receptor position in the local frame.
        turbine: Rotor geometry.
        receptor_height_m: Receptor height above ground.
        max_distance_m: Horizontal distance beyond which no shadow is counted.
        sun: Sun path.
        tower_en: Tower position in the local frame.

    Returns:
        Boolean array aligned with the sun path.
    """
    dx = tower_en[0] - receptor_en[0]
    dy = tower_en[1] - receptor_en[1]
    dz = turbine.hub_height_m - receptor_height_m
    if math.hypot(dx, dy) > max_distance_m:
        return np.zeros(sun.elevation_deg.shape, dtype=np.bool_)
    sx, sy, sz = sun.unit_vectors()
    along = dx * sx + dy * sy + dz * sz
    perp_sq = dx * dx + dy * dy + dz * dz - along * along
    mask: BoolArray = (along > 0.0) & (perp_sq <= turbine.rotor_radius_m**2)
    return mask


def sunny_steps(sun: SunPath, tmy_csv: str, dni_threshold_wm2: float) -> BoolArray:
    """Steps whose UTC hour in an hourly record has DNI at or above the threshold.

    The record is matched on UTC month, day and hour, so a typical-meteorological-year
    file with mixed source years can be used for any year.

    Args:
        sun: Sun path.
        tmy_csv: CSV with a UTC ``time`` column and a ``dni`` column (W/m2).
        dni_threshold_wm2: Sunshine threshold.

    Returns:
        Boolean array aligned with the sun path.

    Raises:
        ValueError: If an hour of the sun path is missing from the record.
    """
    import pandas as pd

    rec = pd.read_csv(tmy_csv)
    t = pd.to_datetime(rec["time"], utc=True)
    keys = (t.dt.month * 10000 + t.dt.day * 100 + t.dt.hour).to_numpy(dtype=np.int64)
    sunny = rec["dni"].to_numpy(dtype=np.float64) >= dni_threshold_wm2
    lookup = dict(zip(keys.tolist(), sunny.tolist(), strict=True))
    missing = sorted(set(sun.utc_hour_key.tolist()) - set(lookup))
    if missing:
        raise ValueError(
            f"sunshine record lacks {len(missing)} hours, e.g. {missing[:3]}"
        )
    return np.array([lookup[k] for k in sun.utc_hour_key.tolist()], dtype=np.bool_)


@dataclass(frozen=True)
class ReceptorFlicker:
    """Shadow flicker at one receptor.

    Attributes:
        name: Receptor name.
        east_m: East offset from the tower.
        north_m: North offset from the tower.
        distance_m: Horizontal distance from the tower.
        worst_case_hours_per_year: Astronomical worst-case hours per year.
        worst_case_max_minutes_per_day: Largest worst-case minutes on any local day.
        worst_case_days: Days with any worst-case flicker.
        expected_hours_per_year: Expected-case hours per year, or ``None``.
        exceeds_worst_case_hours_limit: Annual worst-case threshold exceeded.
        exceeds_worst_case_daily_limit: Daily worst-case threshold exceeded.
        exceeds_expected_hours_limit: Expected-case threshold exceeded, or ``None``.
    """

    name: str
    east_m: float
    north_m: float
    distance_m: float
    worst_case_hours_per_year: float
    worst_case_max_minutes_per_day: float
    worst_case_days: int
    expected_hours_per_year: Optional[float]
    exceeds_worst_case_hours_limit: bool
    exceeds_worst_case_daily_limit: bool
    exceeds_expected_hours_limit: Optional[bool]


def receptor_flicker(
    name: str,
    receptor_en: EastNorth,
    *,
    tower_en: EastNorth,
    turbine: TurbineGeometry,
    cfg: ShadowFlickerConfig,
    sun: SunPath,
    sunny: Optional[BoolArray],
    operating_probability: Optional[float],
) -> ReceptorFlicker:
    """Worst-case and expected shadow flicker at one receptor.

    Args:
        name: Receptor name.
        receptor_en: Receptor position in the local frame.
        tower_en: Tower position in the local frame.
        turbine: Rotor geometry.
        cfg: Thresholds and receptor height.
        sun: Sun path.
        sunny: Sunshine flags aligned with ``sun``, or ``None`` to skip the expected case.
        operating_probability: Probability the rotor turns, required with ``sunny``.

    Returns:
        The receptor result.

    Raises:
        ValueError: If only one of ``sunny`` and ``operating_probability`` is given, or
            the probability lies outside ``[0, 1]``.
    """
    if (sunny is None) != (operating_probability is None):
        raise ValueError("sunny and operating_probability go together")
    mask = shadow_mask(
        receptor_en,
        turbine=turbine,
        receptor_height_m=cfg.receptor_height_m,
        max_distance_m=cfg.max_shadow_distance_rotor_diameters
        * turbine.rotor_diameter_m,
        sun=sun,
        tower_en=tower_en,
    )
    per_day = np.bincount(sun.day_index[mask], minlength=sun.n_days)
    hours = float(mask.sum()) * sun.step_minutes / 60.0
    max_min = float(per_day.max()) * sun.step_minutes if per_day.size else 0.0
    expected: Optional[float] = None
    exceeds_expected: Optional[bool] = None
    if sunny is not None and operating_probability is not None:
        if not 0.0 <= operating_probability <= 1.0:
            raise ValueError("operating_probability must lie in [0, 1]")
        expected = (
            float((mask & sunny).sum())
            * sun.step_minutes
            / 60.0
            * operating_probability
        )
        exceeds_expected = expected > cfg.expected_hours_per_year_limit
    de = receptor_en[0] - tower_en[0]
    dn = receptor_en[1] - tower_en[1]
    return ReceptorFlicker(
        name=name,
        east_m=de,
        north_m=dn,
        distance_m=math.hypot(de, dn),
        worst_case_hours_per_year=hours,
        worst_case_max_minutes_per_day=max_min,
        worst_case_days=int((per_day > 0).sum()),
        expected_hours_per_year=expected,
        exceeds_worst_case_hours_limit=hours > cfg.worst_case_hours_per_year_limit,
        exceeds_worst_case_daily_limit=max_min > cfg.worst_case_minutes_per_day_limit,
        exceeds_expected_hours_limit=exceeds_expected,
    )


def flicker_grid(
    *,
    tower_en: EastNorth,
    turbine: TurbineGeometry,
    cfg: ShadowFlickerConfig,
    sun: SunPath,
    sunny: Optional[BoolArray],
    operating_probability: Optional[float],
) -> List[ReceptorFlicker]:
    """Shadow flicker on a square receptor grid centred on the tower.

    Args:
        tower_en: Tower position in the local frame.
        turbine: Rotor geometry.
        cfg: Grid extent and spacing, thresholds.
        sun: Sun path.
        sunny: Sunshine flags, or ``None``.
        operating_probability: Probability the rotor turns, or ``None``.

    Returns:
        One result per grid node, west to east within south to north rows.
    """
    n = int(round(cfg.grid_half_width_m / cfg.grid_spacing_m))
    offsets = [i * cfg.grid_spacing_m for i in range(-n, n + 1)]
    out: List[ReceptorFlicker] = []
    for dn in offsets:
        for de in offsets:
            out.append(
                receptor_flicker(
                    f"grid_{de:+.0f}_{dn:+.0f}",
                    (tower_en[0] + de, tower_en[1] + dn),
                    tower_en=tower_en,
                    turbine=turbine,
                    cfg=cfg,
                    sun=sun,
                    sunny=sunny,
                    operating_probability=operating_probability,
                )
            )
    return out


def grid_summary(
    grid: Sequence[ReceptorFlicker], cfg: ShadowFlickerConfig
) -> Dict[str, Any]:
    """Summarise a flicker grid: maxima and the area over each threshold.

    Args:
        grid: Grid results from :func:`flicker_grid`.
        cfg: Grid spacing and thresholds.

    Returns:
        A JSON-serialisable summary.
    """
    cell = cfg.grid_spacing_m**2
    hours = [g.worst_case_hours_per_year for g in grid]
    minutes = [g.worst_case_max_minutes_per_day for g in grid]
    expected = [g.expected_hours_per_year for g in grid]
    summary: Dict[str, Any] = {
        "nodes": len(grid),
        "spacing_m": cfg.grid_spacing_m,
        "half_width_m": cfg.grid_half_width_m,
        "max_worst_case_hours_per_year": max(hours),
        "max_worst_case_minutes_per_day": max(minutes),
        "area_over_worst_case_hours_limit_m2": cell
        * sum(g.exceeds_worst_case_hours_limit for g in grid),
        "area_over_worst_case_daily_limit_m2": cell
        * sum(g.exceeds_worst_case_daily_limit for g in grid),
        "farthest_node_over_worst_case_hours_limit_m": max(
            (g.distance_m for g in grid if g.exceeds_worst_case_hours_limit),
            default=0.0,
        ),
    }
    if all(e is not None for e in expected):
        summary["max_expected_hours_per_year"] = max(float(e or 0.0) for e in expected)
        summary["area_over_expected_hours_limit_m2"] = cell * sum(
            bool(g.exceeds_expected_hours_limit) for g in grid
        )
    return summary


def receptor_as_dict(result: ReceptorFlicker) -> Dict[str, Any]:
    """JSON-serialisable form of a receptor result."""
    return asdict(result)


__all__ = [
    "CoastalPlacement",
    "CoastalSetbackConfig",
    "LocalFrame",
    "ReceptorFlicker",
    "ShadowFlickerConfig",
    "SquareLot",
    "SunPath",
    "TipSetbackConfig",
    "TipSetbackResult",
    "TurbineGeometry",
    "coast_aligned_square_lot",
    "coastline_lines_east_north",
    "flicker_grid",
    "grid_summary",
    "place_at_coastal_setback",
    "receptor_as_dict",
    "receptor_flicker",
    "shadow_mask",
    "site_feature_collection",
    "solar_path",
    "sunny_steps",
    "tip_height_setback",
]
