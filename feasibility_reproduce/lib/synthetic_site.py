#!/usr/bin/env python3
"""Derive a SYNTHETIC micro-siting geometry from committed scenario parameters.

`optimize_layout()` needs a boundary polygon and baseline turbine coordinates in
metres. Neither is committed anywhere in the repository (see
``cache/micrositing_synthetic_site.yaml`` for the full account), so this module
builds both from parameters that ARE committed — the array centroid, turbine
count, spacing and orientation — projected into the scenario's declared UTM zone.

The result is explicitly synthetic. :func:`load_synthetic_site` refuses any config
whose ``provenance`` is not ``synthetic_derived``, so this module can never be
pointed at a real site block and silently pass it through: a real polygon deserves
a real loader, not this one.

CASPER: ``pyproj`` is an optional dependency, imported at call-time with an
actionable message rather than at import-time.
CESSPIT: every geometric parameter is read from the config; nothing is defaulted
silently. A missing or malformed field raises with the field named.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

#: The only provenance token this loader accepts. A real site boundary must not be
#: routed through a module whose entire purpose is fabricating a plausible one.
SYNTHETIC_PROVENANCE = "synthetic_derived"


@dataclass(frozen=True)
class SyntheticSite:
    """A derived, explicitly-synthetic site geometry in projected metres."""

    boundary_m: list[tuple[float, float]]
    baseline_x_m: list[float]
    baseline_y_m: list[float]
    min_spacing_diameters: float
    random_seed: int
    use_smart_start: bool
    max_iterations: int
    utm_epsg: int
    provenance: str

    @property
    def n_turbines(self) -> int:
        return len(self.baseline_x_m)

    @property
    def array_span_m(self) -> float:
        """North-south extent of the baseline array."""
        return max(self.baseline_y_m) - min(self.baseline_y_m)


def _require_pyproj() -> Any:
    """Return ``pyproj`` or raise an actionable error (CASPER: fail at call-time)."""
    try:
        import pyproj
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "pyproj is required to project the synthetic site geometry into the "
            "scenario's UTM zone. It ships with the [gis] extra: "
            'pip install -e ".[dev,feasibility]"'
        ) from exc
    return pyproj


def _require(block: Mapping[str, Any], key: str, path: str) -> Any:
    """Fetch a required config value or raise naming the full path (CESSPIT)."""
    if key not in block or block[key] is None:
        raise ValueError(f"{path}.{key} is required and must not be null.")
    return block[key]


def _require_positive(block: Mapping[str, Any], key: str, path: str) -> float:
    value = _require(block, key, path)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}.{key} must be a number; got {value!r}.") from exc
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{path}.{key} must be finite and > 0; got {value!r}.")
    return number


def _utm_epsg(utm_zone: str) -> int:
    """EPSG code for a WGS84 UTM zone string such as ``"44N"``."""
    zone_text = str(utm_zone).strip().upper()
    if not zone_text or zone_text[-1] not in {"N", "S"}:
        raise ValueError(f"utm_zone must end in N or S (e.g. '44N'); got {utm_zone!r}.")
    try:
        zone = int(zone_text[:-1])
    except ValueError as exc:
        raise ValueError(f"utm_zone has no numeric zone; got {utm_zone!r}.") from exc
    if not 1 <= zone <= 60:
        raise ValueError(f"utm_zone must be 1-60; got {zone}.")
    # WGS84 UTM: 326xx northern hemisphere, 327xx southern.
    return (32600 if zone_text[-1] == "N" else 32700) + zone


def _circle(
    cx: float, cy: float, radius_m: float, n_vertices: int
) -> list[tuple[float, float]]:
    """Closed-polygon approximation of a circle, counter-clockwise."""
    if n_vertices < 3:
        raise ValueError(f"boundary.n_vertices must be >= 3; got {n_vertices}.")
    return [
        (
            cx + radius_m * math.cos(2.0 * math.pi * i / n_vertices),
            cy + radius_m * math.sin(2.0 * math.pi * i / n_vertices),
        )
        for i in range(n_vertices)
    ]


def _linear_north_south(
    cx: float, cy: float, n_turbines: int, spacing_m: float
) -> tuple[list[float], list[float]]:
    """Turbines on a north-south line, centred on ``(cx, cy)``."""
    if n_turbines < 1:
        raise ValueError(f"baseline_layout.n_turbines must be >= 1; got {n_turbines}.")
    span = (n_turbines - 1) * spacing_m
    y0 = cy - span / 2.0
    return (
        [cx] * n_turbines,
        [y0 + i * spacing_m for i in range(n_turbines)],
    )


def build_synthetic_site(config: Mapping[str, Any]) -> SyntheticSite:
    """Build the synthetic geometry from a ``micrositing_synthetic`` block."""
    block = config.get("micrositing_synthetic")
    if not isinstance(block, Mapping):
        raise ValueError(
            "config has no 'micrositing_synthetic' mapping — this loader only "
            "builds the derived synthetic geometry."
        )

    provenance = str(_require(block, "provenance", "micrositing_synthetic"))
    if provenance != SYNTHETIC_PROVENANCE:
        raise ValueError(
            f"micrositing_synthetic.provenance must be '{SYNTHETIC_PROVENANCE}'; got "
            f"{provenance!r}. A real site geometry must not be loaded through the "
            "synthetic-site builder — give it a real loader so its provenance survives."
        )

    derived = _require(block, "derived_from", "micrositing_synthetic")
    if not isinstance(derived, Mapping):
        raise ValueError("micrositing_synthetic.derived_from must be a mapping.")
    lat = float(
        _require(derived, "centroid_lat_deg", "micrositing_synthetic.derived_from")
    )
    lon = float(
        _require(derived, "centroid_lon_deg", "micrositing_synthetic.derived_from")
    )
    utm_zone = _require(derived, "utm_zone", "micrositing_synthetic.derived_from")
    epsg = _utm_epsg(str(utm_zone))

    boundary_cfg = _require(block, "boundary", "micrositing_synthetic")
    shape = str(_require(boundary_cfg, "shape", "micrositing_synthetic.boundary"))
    if shape != "circle":
        raise ValueError(
            f"micrositing_synthetic.boundary.shape only supports 'circle'; got {shape!r}."
        )
    radius_m = _require_positive(
        boundary_cfg, "radius_m", "micrositing_synthetic.boundary"
    )
    n_vertices = int(
        _require(boundary_cfg, "n_vertices", "micrositing_synthetic.boundary")
    )

    layout_cfg = _require(block, "baseline_layout", "micrositing_synthetic")
    orientation = str(
        _require(layout_cfg, "orientation", "micrositing_synthetic.baseline_layout")
    )
    if orientation != "linear_north_south":
        raise ValueError(
            "micrositing_synthetic.baseline_layout.orientation only supports "
            f"'linear_north_south'; got {orientation!r}."
        )
    n_turbines = int(
        _require(layout_cfg, "n_turbines", "micrositing_synthetic.baseline_layout")
    )
    spacing_m = _require_positive(
        layout_cfg, "spacing_m", "micrositing_synthetic.baseline_layout"
    )

    min_spacing_d = _require_positive(
        block, "min_spacing_diameters", "micrositing_synthetic"
    )

    opt = block.get("optimizer") or {}
    if not isinstance(opt, Mapping):
        raise ValueError(
            "micrositing_synthetic.optimizer must be a mapping when present."
        )
    seed = int(opt.get("random_seed", 42))
    smart_start = bool(opt.get("use_smart_start", False))
    max_iterations = int(opt.get("max_iterations", 200))

    # Project the centroid into the declared UTM zone so the geometry is in real
    # metres, consistent with the spacing/rotor figures the scenario declares.
    pyproj = _require_pyproj()
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    cx, cy = to_utm.transform(lon, lat)

    span = (n_turbines - 1) * spacing_m
    if span > 2.0 * radius_m:
        raise ValueError(
            f"baseline array spans {span:,.0f} m but the boundary circle is only "
            f"{2.0 * radius_m:,.0f} m across — the layout cannot fit. Raise "
            "micrositing_synthetic.boundary.radius_m or lower n_turbines/spacing_m."
        )

    baseline_x, baseline_y = _linear_north_south(cx, cy, n_turbines, spacing_m)
    return SyntheticSite(
        boundary_m=_circle(cx, cy, radius_m, n_vertices),
        baseline_x_m=baseline_x,
        baseline_y_m=baseline_y,
        min_spacing_diameters=min_spacing_d,
        random_seed=seed,
        use_smart_start=smart_start,
        max_iterations=max_iterations,
        utm_epsg=epsg,
        provenance=provenance,
    )


def load_synthetic_site(path: str | Path) -> SyntheticSite:
    """Load and build the synthetic geometry from a YAML file."""
    site_path = Path(path)
    if not site_path.is_file():
        raise FileNotFoundError(f"synthetic site config not found: {site_path}")
    with open(site_path, encoding="utf-8") as handle:
        return build_synthetic_site(yaml.safe_load(handle) or {})


def turbine_spec_from_power_curve(
    curve_key: str,
    rotor_diameter_m: float,
    hub_height_m: float,
    curves_path: str | Path = "wind_resource/config/power_curves.yaml",
) -> Any:
    """Build a :class:`TurbineSpec` from the COMMITTED OEM power curve.

    The power/thrust arrays come from ``wind_resource/config/power_curves.yaml`` —
    the same curve the AEP chain uses — so the synthetic siting run is driven by
    real turbine physics even though the geometry around it is fabricated.
    """
    from wind_resource.layout_optimizer import TurbineSpec

    with open(Path(curves_path), encoding="utf-8") as handle:
        curves = yaml.safe_load(handle) or {}
    curve = curves.get(curve_key)
    if not isinstance(curve, Mapping):
        raise ValueError(
            f"power curve {curve_key!r} not found in {curves_path}; "
            f"available: {sorted(curves)}"
        )
    power = curve.get("power_curve") or {}
    thrust = curve.get("thrust_curve") or {}
    ws: Sequence[float] = power.get("ws") or []
    # The committed schema names the ordinate `power` (kW); accept `kw` as an alias
    # so a curve authored either way loads rather than failing on a key name.
    kw: Sequence[float] = power.get("power") or power.get("kw") or []
    ct: Sequence[float] = thrust.get("ct") or []
    if not ws or len(ws) != len(kw):
        raise ValueError(
            f"{curve_key}.power_curve must supply matching ws and power/kw arrays; "
            f"got ws[{len(ws)}] and power[{len(kw)}]."
        )
    if len(ct) != len(ws):
        # The thrust grid is declared on its own ws axis; resample onto the power axis.
        thrust_ws: Sequence[float] = thrust.get("ws") or []
        if len(thrust_ws) != len(ct) or not ct:
            raise ValueError(
                f"{curve_key}.thrust_curve must supply matching ws/ct arrays."
            )
        ct = [_interp(float(w), thrust_ws, ct) for w in ws]
    return TurbineSpec(
        rotor_diameter_m=float(rotor_diameter_m),
        hub_height_m=float(hub_height_m),
        wind_speed_ms=[float(w) for w in ws],
        power_kw=[float(p) for p in kw],
        thrust_coefficient=[float(c) for c in ct],
        name=str(curve.get("model", curve_key)),
    )


def _interp(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Linear interpolation with flat extrapolation at both ends."""
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    for i in range(1, len(xs)):
        if x <= xs[i]:
            span = xs[i] - xs[i - 1]
            if span == 0:
                return float(ys[i])
            w = (x - xs[i - 1]) / span
            return float(ys[i - 1] + w * (ys[i] - ys[i - 1]))
    return float(ys[-1])
