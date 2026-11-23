"""Area -> optimized-layout micro-siting tool (DTU TopFarm on PyWake).

Issue #835 **Deliverable A ONLY** — a KPI-NEUTRAL *candidate* generator.

Today :mod:`wind_resource.bankable_aep` can only *score* a supplied turbine
layout (``model_wake_loss``). This module adds the missing **area -> optimized
layout** capability: given a site **boundary polygon**, optional **exclusion
zones**, a **wind rose**, a **turbine geometry** (rotor diameter, hub height,
power/Ct curve) and a **minimum spacing** (in rotor diameters), it runs the DTU
TopFarm gradient optimizer (built directly on the PyWake this repo already runs)
to propose an AEP-maximising layout that respects the **boundary, minimum-spacing
and exclusion** constraints.

It is a **pure library tool** (no CLI / scenario / finance wiring) that returns a
*candidate* layout and its AEP, plus the uplift versus a **caller-supplied
baseline** layout (e.g. the committed T1-T15 positions). Feeding an optimized
layout into the headline economics is Deliverable B — KPI-MOVING, oracle-gated,
and explicitly OUT OF SCOPE here.

Design notes
------------
* **Config-first (GWTF ARCH-01):** nothing is hardcoded — turbine geometry, the
  wind rose, the Weibull scale/shape, the boundary and exclusion polygons and the
  spacing rule are all caller inputs.
* **CASPER optional-dep guard:** TopFarm is an OPT-IN extra (``[micrositing]``);
  the import is guarded by :func:`_require_topfarm`, which raises an actionable
  error naming the extra when TopFarm is absent, so the base install and the CI
  toolchain never need it.
* The PyWake wind-farm model, site and turbine objects are built exactly as in
  :mod:`wind_resource.bankable_aep` (Bastankhah-Porte-Agel 2014 Gaussian, the
  Niayifar & Porte-Agel TI-based ``k*`` closure) so a scored candidate reconciles
  with the bankable engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Any, Optional, Protocol, Sequence, cast

import numpy as np

from wind_resource.bankable_aep import gaussian_k_star

if TYPE_CHECKING:
    from topfarm import TopFarmProblem
    from topfarm.constraint_components.boundary import (
        ExclusionZone,
        InclusionZone,
        XYBoundaryConstraint,
    )
    from topfarm.constraint_components.spacing import SpacingConstraint
    from topfarm.cost_models.cost_model_wrappers import CostModelComponent
    from topfarm.easy_drivers import EasyScipyOptimizeDriver
    from topfarm.plotting import NoPlot

logger = logging.getLogger(__name__)

# IEC-37 style omnidirectional single-turbine defaults are intentionally NOT
# provided as silent numeric fallbacks (CESSPIT: no silent defaults). The caller
# supplies turbine geometry + a power/Ct curve. What we DO default is only the
# non-physical solver knobs (max iterations, sectors for an absent rose), which
# never affect an economic headline.

_DEFAULT_CONSTRAINT_TOLERANCE_M = 1.0
_MAX_GRID_POINTS = 40_000
_MAX_REJECTION_SAMPLES = 20_000


class _SupportsSum(Protocol):
    """Minimal protocol for PyWake's DataArray returned by ``sim.aep()``."""

    def sum(self) -> Any: ...


class _SimulationResult(Protocol):
    """Minimal protocol for PyWake's simulation result."""

    def aep(self) -> _SupportsSum: ...


class _WindFarmModel(Protocol):
    """Minimal callable protocol for a PyWake wind-farm model."""

    def __call__(self, x: np.ndarray, y: np.ndarray) -> _SimulationResult: ...


@dataclass(frozen=True)
class _TopFarmAPI:
    """Bundle of lazily imported TopFarm classes."""

    TopFarmProblem: type[TopFarmProblem]
    XYBoundaryConstraint: type[XYBoundaryConstraint]
    SpacingConstraint: type[SpacingConstraint]
    CostModelComponent: type[CostModelComponent]
    EasyScipyOptimizeDriver: type[EasyScipyOptimizeDriver]
    NoPlot: type[NoPlot]
    InclusionZone: Optional[type[InclusionZone]]
    ExclusionZone: Optional[type[ExclusionZone]]


# ---------------------------------------------------------------------------
# CASPER optional-dependency guard
# ---------------------------------------------------------------------------
def _require_topfarm() -> ModuleType:
    """Import TopFarm or raise a clear, actionable error (CASPER optional-dep guard).

    TopFarm (``topfarm``) is the OPT-IN ``[micrositing]`` extra — it is NOT in the
    ``[wind]`` extra or the CI toolchain, to keep CI light. Producers of an
    optimized candidate layout require it; every existing consumer (the bankable
    AEP engine, finance) does not.
    """
    try:
        import topfarm  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised when the extra is absent
        raise RuntimeError(
            "The micro-siting layout optimizer requires DTU TopFarm (the "
            "[micrositing] extra). Install with: pip install -e '.[micrositing]'  "
            "(or: pip install topfarm)."
        ) from exc
    return cast(ModuleType, topfarm)


def _load_topfarm_api() -> _TopFarmAPI:
    """Validate TopFarm availability and import all TopFarm classes consistently."""
    _require_topfarm()
    from topfarm import TopFarmProblem
    from topfarm.constraint_components.boundary import XYBoundaryConstraint
    from topfarm.constraint_components.spacing import SpacingConstraint
    from topfarm.cost_models.cost_model_wrappers import CostModelComponent
    from topfarm.easy_drivers import EasyScipyOptimizeDriver
    from topfarm.plotting import NoPlot

    try:
        from topfarm.constraint_components.boundary import (
            ExclusionZone,
            InclusionZone,
        )
    except ImportError:  # pragma: no cover - older TopFarm without InclusionZone
        InclusionZone = None
        ExclusionZone = None

    return _TopFarmAPI(
        TopFarmProblem=TopFarmProblem,
        XYBoundaryConstraint=XYBoundaryConstraint,
        SpacingConstraint=SpacingConstraint,
        CostModelComponent=CostModelComponent,
        EasyScipyOptimizeDriver=EasyScipyOptimizeDriver,
        NoPlot=NoPlot,
        InclusionZone=InclusionZone,
        ExclusionZone=ExclusionZone,
    )


# ---------------------------------------------------------------------------
# Typed inputs / result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TurbineSpec:
    """Turbine geometry + reference power/Ct curve (config-first, no defaults)."""

    rotor_diameter_m: float
    hub_height_m: float
    wind_speed_ms: Sequence[float]
    power_kw: Sequence[float]
    thrust_coefficient: Sequence[float]
    name: str = "ref"


@dataclass(frozen=True)
class LayoutOptimizationResult:
    """Result of a TopFarm micro-siting run.

    ``optimized_*`` are the proposed candidate positions (m, in the same local
    planar CRS as the boundary). ``*_aep_gwh`` are the wake-included farm AEPs
    scored on the SAME PyWake model. ``uplift_gwh`` / ``uplift_pct`` are the
    optimized-vs-baseline gain (positive = the candidate beats the baseline).
    """

    optimized_x_m: np.ndarray
    optimized_y_m: np.ndarray
    optimized_aep_gwh: float
    baseline_aep_gwh: float
    uplift_gwh: float
    uplift_pct: float
    n_turbines: int
    min_spacing_m: float
    driver: str
    n_iterations: int
    converged: bool = True
    constraints_satisfied: bool = True
    max_boundary_violation_m: float = 0.0
    max_spacing_violation_m: float = 0.0


# ---------------------------------------------------------------------------
# Input & geometry validation helpers
# ---------------------------------------------------------------------------
def _validate_turbine_spec(turbine: TurbineSpec) -> None:
    """Validate turbine geometry and physical sanity of power/Ct curves."""
    rotor_d = float(turbine.rotor_diameter_m)
    hub_h = float(turbine.hub_height_m)
    if not np.isfinite(rotor_d) or rotor_d <= 0.0:
        raise ValueError(
            f"turbine.rotor_diameter_m must be finite and > 0; got {turbine.rotor_diameter_m!r}"
        )
    if not np.isfinite(hub_h) or hub_h <= 0.0:
        raise ValueError(
            f"turbine.hub_height_m must be finite and > 0; got {turbine.hub_height_m!r}"
        )

    ws = np.asarray(turbine.wind_speed_ms, dtype=float)
    power = np.asarray(turbine.power_kw, dtype=float)
    ct = np.asarray(turbine.thrust_coefficient, dtype=float)

    if ws.ndim != 1 or power.ndim != 1 or ct.ndim != 1:
        raise ValueError("turbine power/Ct curve arrays must be 1-D")
    if not (ws.size == power.size == ct.size):
        raise ValueError(
            "turbine wind_speed_ms, power_kw, and thrust_coefficient must have equal length"
        )
    if ws.size < 2:
        raise ValueError("turbine power/Ct curve must contain at least 2 points")
    if not (
        np.all(np.isfinite(ws))
        and np.all(np.isfinite(power))
        and np.all(np.isfinite(ct))
    ):
        raise ValueError(
            "turbine power/Ct curve arrays must contain only finite values"
        )

    if np.any(ws < 0.0) or np.any(np.diff(ws) <= 0.0):
        raise ValueError(
            "turbine.wind_speed_ms must be non-negative and strictly increasing"
        )
    if np.any(power < 0.0) or float(np.max(power)) <= 0.0:
        raise ValueError("turbine.power_kw must be non-negative with a positive peak")

    # Power must be monotonically non-decreasing up to rated peak (post-cut-out drops to 0 are valid).
    peak_idx = int(np.argmax(power))
    if peak_idx > 0 and np.any(np.diff(power[: peak_idx + 1]) < -1e-6):
        raise ValueError(
            "turbine.power_kw must be monotonically non-decreasing up to rated power"
        )

    if np.any((ct < 0.0) | (ct > 1.0)):
        raise ValueError("turbine.thrust_coefficient values must lie within [0.0, 1.0]")


def _segments_intersect(
    p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray, tol: float = 1e-12
) -> bool:
    """Return True if closed 2-D segments p1-p2 and p3-p4 intersect or touch."""
    if (
        max(p1[0], p2[0]) < min(p3[0], p4[0]) - tol
        or max(p3[0], p4[0]) < min(p1[0], p2[0]) - tol
        or max(p1[1], p2[1]) < min(p3[1], p4[1]) - tol
        or max(p3[1], p4[1]) < min(p1[1], p2[1]) - tol
    ):
        return False

    def _orient(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))

    def _on_segment(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> bool:
        return bool(
            min(a[0], b[0]) - tol <= c[0] <= max(a[0], b[0]) + tol
            and min(a[1], b[1]) - tol <= c[1] <= max(a[1], b[1]) + tol
        )

    o1 = _orient(p1, p2, p3)
    o2 = _orient(p1, p2, p4)
    o3 = _orient(p3, p4, p1)
    o4 = _orient(p3, p4, p2)

    if (o1 > tol and o2 < -tol or o1 < -tol and o2 > tol) and (
        o3 > tol and o4 < -tol or o3 < -tol and o4 > tol
    ):
        return True
    if abs(o1) <= tol and _on_segment(p1, p2, p3):
        return True
    if abs(o2) <= tol and _on_segment(p1, p2, p4):
        return True
    if abs(o3) <= tol and _on_segment(p3, p4, p1):
        return True
    if abs(o4) <= tol and _on_segment(p3, p4, p2):
        return True
    return False


def _polygon_area(poly: np.ndarray) -> float:
    """Return unsigned area of a 2-D polygon via the shoelace formula."""
    x = poly[:, 0]
    y = poly[:, 1]
    return 0.5 * float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _validate_polygon(vertices: Sequence[Sequence[float]], *, name: str) -> np.ndarray:
    """Validate that ``vertices`` defines a simple, non-degenerate 2-D polygon."""
    arr = np.asarray(vertices, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(f"{name} must be a 2-D array of (x, y) vertices")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite coordinates")
    if arr.shape[0] >= 2 and np.allclose(arr[0], arr[-1], atol=1e-12, rtol=0.0):
        arr = arr[:-1]
    n_verts = arr.shape[0]
    if n_verts < 3:
        raise ValueError(f"{name} must have at least 3 distinct vertices")

    edges = np.roll(arr, -1, axis=0) - arr
    edge_lengths = np.hypot(edges[:, 0], edges[:, 1])
    if np.any(edge_lengths <= 1e-12):
        raise ValueError(f"{name} contains duplicate consecutive vertices")

    # Check non-adjacent edge intersections first so a symmetric bowtie (which
    # has zero signed shoelace area) still reports self-intersection.
    for i in range(n_verts):
        p1 = arr[i]
        p2 = arr[(i + 1) % n_verts]
        for j in range(i + 2, n_verts):
            if i == 0 and j == n_verts - 1:
                continue
            p3 = arr[j]
            p4 = arr[(j + 1) % n_verts]
            if _segments_intersect(p1, p2, p3, p4):
                raise ValueError(
                    f"{name} must be a simple polygon (self-intersection detected)"
                )

    if _polygon_area(arr) <= 1e-9:
        raise ValueError(f"{name} must be a non-degenerate polygon with non-zero area")

    # Reject 180-degree foldbacks between adjacent edges (zero-width spikes).
    for i in range(n_verts):
        e1 = edges[i]
        e2 = edges[(i + 1) % n_verts]
        cross = float(e1[0] * e2[1] - e1[1] * e2[0])
        dot = float(e1[0] * e2[0] + e1[1] * e2[1])
        if (
            abs(cross) <= 1e-12 * edge_lengths[i] * edge_lengths[(i + 1) % n_verts]
            and dot < 0.0
        ):
            raise ValueError(
                f"{name} must be a simple polygon (adjacent edges fold back)"
            )

    return arr


def _is_convex_polygon(poly: np.ndarray) -> bool:
    """Return True if an open simple polygon ``poly`` is convex."""
    edges = np.roll(poly, -1, axis=0) - poly
    next_edges = np.roll(edges, -1, axis=0)
    crosses = edges[:, 0] * next_edges[:, 1] - edges[:, 1] * next_edges[:, 0]
    scale = np.maximum(
        1.0,
        np.hypot(edges[:, 0], edges[:, 1])
        * np.hypot(next_edges[:, 0], next_edges[:, 1]),
    )
    nonzero = crosses[np.abs(crosses) > 1e-12 * scale]
    if nonzero.size == 0:
        return False
    return bool(np.all(nonzero > 0.0) or np.all(nonzero < 0.0))


def _points_signed_distance_to_polygon(
    x: np.ndarray, y: np.ndarray, poly: np.ndarray
) -> np.ndarray:
    """Signed Euclidean distance from points ``(x, y)`` to ``poly`` (+ inside, - outside)."""
    px_pts = np.asarray(x, dtype=float)
    py_pts = np.asarray(y, dtype=float)
    if px_pts.size == 0:
        return np.empty(0, dtype=float)

    a = poly
    b = np.roll(poly, -1, axis=0)
    ab = b - a
    ab_sq = np.sum(ab * ab, axis=1)

    dx_a = px_pts[:, None] - a[None, :, 0]
    dy_a = py_pts[:, None] - a[None, :, 1]
    t = np.clip(
        (dx_a * ab[None, :, 0] + dy_a * ab[None, :, 1]) / ab_sq[None, :], 0.0, 1.0
    )
    dx = dx_a - t * ab[None, :, 0]
    dy = dy_a - t * ab[None, :, 1]
    min_dist = np.sqrt(np.min(dx * dx + dy * dy, axis=1))

    # Ray casting to the right (+x); cond_y guarantees b_y != a_y.
    ay = a[None, :, 1]
    by = b[None, :, 1]
    ax = a[None, :, 0]
    bx = b[None, :, 0]
    cond_y = (ay > py_pts[:, None]) != (by > py_pts[:, None])
    denom = np.where(cond_y, by - ay, 1.0)
    x_intersect = ax + (py_pts[:, None] - ay) * (bx - ax) / denom
    inside = (np.sum(cond_y & (px_pts[:, None] < x_intersect), axis=1) % 2) == 1

    return np.where(min_dist <= 1e-12, 0.0, np.where(inside, min_dist, -min_dist))


def _points_signed_distance_to_buildable_area(
    x: np.ndarray,
    y: np.ndarray,
    boundary: np.ndarray,
    exclusion_zones: Sequence[np.ndarray] = (),
) -> np.ndarray:
    """Signed distance to buildable area (inside ``boundary`` and outside ``exclusion_zones``)."""
    dist = _points_signed_distance_to_polygon(x, y, boundary)
    for excl in exclusion_zones:
        dist = np.minimum(dist, -_points_signed_distance_to_polygon(x, y, excl))
    return dist


# ---------------------------------------------------------------------------
# PyWake model construction (mirrors bankable_aep.model_wake_loss)
# ---------------------------------------------------------------------------
def _build_wind_farm_model(
    turbine: TurbineSpec,
    *,
    weibull_a: float,
    weibull_k: float,
    wind_rose_freq: Optional[Sequence[float]],
    turbulence_intensity: float,
    default_sectors: int,
) -> _WindFarmModel:
    """Construct the PyWake Bastankhah-Porte-Agel 2014 wind-farm model.

    Matches :func:`wind_resource.bankable_aep.model_wake_loss` on its default
    ``Bastankhah_PorteAgel_2014`` branch (``deficit_model="bastankhah"`` / ``"bpa"``)
    via the shared :func:`wind_resource.bankable_aep.gaussian_k_star` closure. The
    non-default ``TurboGaussianDeficit`` branch uses TurbOPark turbulence propagation
    rather than ``k*`` and is outside this optimizer (#1434).
    """
    _validate_turbine_spec(turbine)

    from py_wake.literature.gaussian_models import Bastankhah_PorteAgel_2014
    from py_wake.site import UniformWeibullSite
    from py_wake.wind_turbines import WindTurbine
    from py_wake.wind_turbines.power_ct_functions import PowerCtTabular

    ws = np.asarray(turbine.wind_speed_ms, dtype=float)
    wt = WindTurbine(
        name=turbine.name,
        diameter=float(turbine.rotor_diameter_m),
        hub_height=float(turbine.hub_height_m),
        powerCtFunction=PowerCtTabular(
            ws,
            np.asarray(turbine.power_kw, dtype=float) * 1000.0,  # kW -> W
            "w",
            np.asarray(turbine.thrust_coefficient, dtype=float),
        ),
    )

    n_sectors = (
        len(wind_rose_freq) if wind_rose_freq is not None else int(default_sectors)
    )
    freq = (
        np.asarray(wind_rose_freq, dtype=float)
        if wind_rose_freq is not None
        else np.full(n_sectors, 1.0 / n_sectors)
    )
    freq = freq / freq.sum()
    site = UniformWeibullSite(
        p_wd=freq,
        a=[float(weibull_a)] * n_sectors,
        k=[float(weibull_k)] * n_sectors,
        ti=float(turbulence_intensity),
    )
    # Niayifar & Porte-Agel (2016) TI-based wake-expansion closure via the single
    # source of truth in wind_resource.bankable_aep (#1434).
    k_star = gaussian_k_star(float(turbulence_intensity))
    wfm: _WindFarmModel = Bastankhah_PorteAgel_2014(site, wt, k=k_star)
    return wfm


def _farm_aep_gwh(
    wfm: _WindFarmModel,
    x: Sequence[float] | np.ndarray,
    y: Sequence[float] | np.ndarray,
) -> float:
    """Wake-included farm AEP (GWh/yr) on the given PyWake model + positions."""
    sim = wfm(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return float(sim.aep().sum())


# ---------------------------------------------------------------------------
# Seeding, uplift, driver metadata & post-optimization verification helpers
# ---------------------------------------------------------------------------
def _compute_uplift(
    optimized_aep_gwh: float, baseline_aep_gwh: float
) -> tuple[float, float]:
    """Compute absolute (GWh) and percentage uplift of optimized layout over baseline."""
    uplift = float(optimized_aep_gwh - baseline_aep_gwh)
    uplift_pct = 100.0 * uplift / baseline_aep_gwh if baseline_aep_gwh > 0.0 else 0.0
    return uplift, uplift_pct


def _smart_start_grid(
    boundary_arr: np.ndarray,
    points_per_axis: int = 20,
    *,
    exclusion_zones: Sequence[np.ndarray] = (),
    n_turbines: Optional[int] = None,
    random_seed: Optional[int] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate boundary-aware candidate points for TopFarm ``smart_start`` and padding.

    Adapts grid resolution to the bounding box aspect ratio and polygon fill ratio,
    filters candidates to the buildable area (inside ``boundary_arr`` and outside
    ``exclusion_zones``), and supplements sparse/sliver polygons via deterministic
    rejection sampling.
    """
    poly = np.asarray(boundary_arr, dtype=float)
    if poly.shape[0] >= 2 and np.allclose(poly[0], poly[-1], atol=1e-12, rtol=0.0):
        poly = poly[:-1]

    xmin, ymin = float(poly[:, 0].min()), float(poly[:, 1].min())
    xmax, ymax = float(poly[:, 0].max()), float(poly[:, 1].max())
    dx = max(xmax - xmin, 1e-9)
    dy = max(ymax - ymin, 1e-9)

    base_pts = max(2, int(points_per_axis))
    target_points = max(base_pts * base_pts, 25 * max(1, int(n_turbines or 1)))
    bbox_area = dx * dy
    poly_area = _polygon_area(poly)
    excl_area = sum(
        _polygon_area(np.asarray(ez, dtype=float)) for ez in exclusion_zones
    )
    buildable_area = max(0.0, poly_area - excl_area)
    fill_ratio = max(0.02, min(1.0, buildable_area / max(bbox_area, 1e-9)))

    total_grid = min(_MAX_GRID_POINTS, int(np.ceil(target_points / fill_ratio)))
    aspect = max(0.1, min(10.0, dx / dy))
    nx = max(base_pts, int(np.ceil(np.sqrt(total_grid * aspect))))
    ny = max(base_pts, int(np.ceil(np.sqrt(total_grid / aspect))))
    if nx * ny > _MAX_GRID_POINTS:
        scale = np.sqrt(_MAX_GRID_POINTS / float(nx * ny))
        nx = max(2, int(nx * scale))
        ny = max(2, int(ny * scale))

    gx = np.linspace(xmin, xmax, nx)
    gy = np.linspace(ymin, ymax, ny)
    xv, yv = np.meshgrid(gx, gy)
    cand_x = xv.ravel()
    cand_y = yv.ravel()

    inside_mask = (
        _points_signed_distance_to_buildable_area(cand_x, cand_y, poly, exclusion_zones)
        >= 0.0
    )
    interior_x = cand_x[inside_mask]
    interior_y = cand_y[inside_mask]

    min_needed = max(1, int(n_turbines or 1))
    if interior_x.size < min_needed:
        rng = np.random.default_rng(random_seed)
        sampled_x: list[np.ndarray] = [interior_x]
        sampled_y: list[np.ndarray] = [interior_y]
        drawn = 0
        batch_size = 2_000
        while (
            sum(arr.size for arr in sampled_x) < target_points
            and drawn < _MAX_REJECTION_SAMPLES
        ):
            rx = rng.uniform(xmin, xmax, size=batch_size)
            ry = rng.uniform(ymin, ymax, size=batch_size)
            drawn += batch_size
            mask = (
                _points_signed_distance_to_buildable_area(rx, ry, poly, exclusion_zones)
                >= 0.0
            )
            if np.any(mask):
                sampled_x.append(rx[mask])
                sampled_y.append(ry[mask])
        interior_x = np.concatenate(sampled_x)
        interior_y = np.concatenate(sampled_y)

    return interior_x, interior_y


def _prepare_initial_positions(
    *,
    n: int,
    baseline_x: np.ndarray,
    baseline_y: np.ndarray,
    initial_x_m: Optional[Sequence[float]],
    initial_y_m: Optional[Sequence[float]],
    boundary_arr: np.ndarray,
    exclusion_arrs: Sequence[np.ndarray],
    min_spacing_m: float,
    random_seed: Optional[int],
) -> tuple[np.ndarray, np.ndarray]:
    """Build size-``n`` initial coordinates by trimming or boundary-aware padding."""
    if (initial_x_m is None) != (initial_y_m is None):
        raise ValueError(
            "initial_x_m and initial_y_m must both be provided or both be None"
        )

    if initial_x_m is not None and initial_y_m is not None:
        x0 = np.asarray(initial_x_m, dtype=float)
        y0 = np.asarray(initial_y_m, dtype=float)
        if x0.shape != y0.shape or x0.ndim != 1:
            raise ValueError(
                "initial_x_m and initial_y_m must be 1-D arrays of equal length"
            )
        if not (np.all(np.isfinite(x0)) and np.all(np.isfinite(y0))):
            raise ValueError(
                "initial_x_m and initial_y_m must contain only finite values"
            )
    else:
        x0 = baseline_x.copy()
        y0 = baseline_y.copy()

    if x0.size == n:
        return x0, y0
    if x0.size > n:
        return x0[:n].copy(), y0[:n].copy()

    # Grow from x0/y0 by padding with feasible interior points.
    cand_x, cand_y = _smart_start_grid(
        boundary_arr,
        exclusion_zones=exclusion_arrs,
        n_turbines=n,
        random_seed=random_seed,
    )
    if cand_x.size == 0:
        cx = float(np.mean(boundary_arr[:, 0]))
        cy = float(np.mean(boundary_arr[:, 1]))
        pad_n = n - x0.size
        return (
            np.concatenate([x0, np.full(pad_n, cx)]),
            np.concatenate([y0, np.full(pad_n, cy)]),
        )

    rng = np.random.default_rng(random_seed)
    order = rng.permutation(cand_x.size)

    xs_list = x0.tolist()
    ys_list = y0.tolist()
    used_indices: set[int] = set()

    # Pass 1: greedy spacing-respecting selection among interior candidates.
    for idx in order:
        if len(xs_list) >= n:
            break
        px = float(cand_x[idx])
        py = float(cand_y[idx])
        if not xs_list or all(
            np.hypot(px - sx, py - sy) >= min_spacing_m
            for sx, sy in zip(xs_list, ys_list, strict=True)
        ):
            xs_list.append(px)
            ys_list.append(py)
            used_indices.add(int(idx))

    # Pass 2: if site is too tight for strict spacing, pick farthest interior points.
    while len(xs_list) < n:
        if xs_list:
            sx_arr = np.asarray(xs_list, dtype=float)
            sy_arr = np.asarray(ys_list, dtype=float)
            dists_sq = (cand_x[:, None] - sx_arr[None, :]) ** 2 + (
                cand_y[:, None] - sy_arr[None, :]
            ) ** 2
            min_dists_sq = np.min(dists_sq, axis=1)
            if len(used_indices) < cand_x.size:
                for u_idx in used_indices:
                    min_dists_sq[u_idx] = -1.0
            best_idx = int(np.argmax(min_dists_sq))
        else:
            best_idx = int(order[0])
        xs_list.append(float(cand_x[best_idx]))
        ys_list.append(float(cand_y[best_idx]))
        used_indices.add(best_idx)

    return np.asarray(xs_list, dtype=float), np.asarray(ys_list, dtype=float)


def _extract_iteration_count(driver: Any, recorder: Any, cost_comp: Any) -> int:
    """Extract driver iteration count cleanly, falling back to recorder/cost counter."""
    result = getattr(driver, "result", None)
    if result is not None and getattr(result, "iter_count", None) is not None:
        return int(result.iter_count)
    if getattr(driver, "iter_count", None) is not None:
        return int(driver.iter_count)
    if getattr(recorder, "num_cases", None) is not None:
        return int(recorder.num_cases)
    return int(getattr(cost_comp, "counter", 0))


def _extract_converged(driver: Any, recorder: Any) -> bool:
    """Extract optimizer convergence flag from OpenMDAO driver/recorder."""
    result = getattr(driver, "result", None)
    if result is not None and getattr(result, "success", None) is not None:
        return bool(result.success)
    if getattr(driver, "fail", None) is not None:
        return not bool(driver.fail)
    if recorder is not None and hasattr(recorder, "keys"):
        try:
            if "success" in recorder.keys() and len(recorder["success"]) > 0:
                return bool(recorder["success"][-1])
        except (KeyError, IndexError, TypeError) as exc:
            logger.debug("Unable to read convergence status from recorder: %s", exc)
    return True


def _verify_post_optimization_constraints(
    *,
    opt_x: np.ndarray,
    opt_y: np.ndarray,
    boundary_arr: np.ndarray,
    exclusion_arrs: Sequence[np.ndarray],
    min_spacing_m: float,
    constraint_tolerance_m: float,
    strict_constraints: bool,
) -> tuple[bool, float, float]:
    """Verify final coordinates satisfy boundary, exclusion, and spacing constraints."""
    if not (np.all(np.isfinite(opt_x)) and np.all(np.isfinite(opt_y))):
        raise RuntimeError("Optimizer produced non-finite turbine coordinates")

    signed_dist = _points_signed_distance_to_buildable_area(
        opt_x, opt_y, boundary_arr, exclusion_arrs
    )
    max_boundary_violation_m = float(max(0.0, -np.min(signed_dist)))

    if opt_x.size >= 2 and min_spacing_m > 0.0:
        dx = opt_x[:, None] - opt_x[None, :]
        dy = opt_y[:, None] - opt_y[None, :]
        pair_dists = np.hypot(dx, dy)
        np.fill_diagonal(pair_dists, np.inf)
        min_actual_spacing = float(np.min(pair_dists))
        max_spacing_violation_m = float(max(0.0, min_spacing_m - min_actual_spacing))
    else:
        max_spacing_violation_m = 0.0

    tol = float(constraint_tolerance_m)
    satisfied = max_boundary_violation_m <= tol and max_spacing_violation_m <= tol
    if not satisfied:
        msg = (
            f"Post-optimization constraint check failed (tol={tol:.3g} m): "
            f"max_boundary_violation_m={max_boundary_violation_m:.3f}, "
            f"max_spacing_violation_m={max_spacing_violation_m:.3f}"
        )
        if strict_constraints:
            raise RuntimeError(msg)
        logger.warning(msg)

    return satisfied, max_boundary_violation_m, max_spacing_violation_m


# ---------------------------------------------------------------------------
# The optimizer
# ---------------------------------------------------------------------------
def optimize_layout(
    *,
    boundary: Sequence[Sequence[float]],
    turbine: TurbineSpec,
    weibull_a: float,
    weibull_k: float,
    baseline_x_m: Sequence[float],
    baseline_y_m: Sequence[float],
    min_spacing_diameters: float,
    wind_rose_freq: Optional[Sequence[float]] = None,
    exclusion_zones: Optional[Sequence[Sequence[Sequence[float]]]] = None,
    n_turbines: Optional[int] = None,
    initial_x_m: Optional[Sequence[float]] = None,
    initial_y_m: Optional[Sequence[float]] = None,
    turbulence_intensity: float = 0.10,
    max_iterations: int = 200,
    use_smart_start: bool = True,
    default_sectors: int = 12,
    random_seed: Optional[int] = None,
    constraint_tolerance_m: float = _DEFAULT_CONSTRAINT_TOLERANCE_M,
    strict_constraints: bool = True,
) -> LayoutOptimizationResult:
    """Generate an AEP-optimized candidate layout via DTU TopFarm on PyWake.

    Runs a boundary-, spacing- and exclusion-constrained AEP maximisation and
    returns the proposed positions plus the AEP uplift vs a caller-supplied
    baseline. **KPI-NEUTRAL** — a candidate only; nothing here touches the
    headline economics (that is Deliverable B, out of scope).

    Args:
        boundary: inclusion-zone polygon as an ordered list of ``(x, y)`` vertices
            in a local planar CRS (metres). Must be a simple, non-degenerate polygon.
        turbine: :class:`TurbineSpec` (rotor D, hub height, power/Ct curve).
        weibull_a, weibull_k: site Weibull scale/shape (as in the bankable engine).
        baseline_x_m, baseline_y_m: the reference layout (e.g. committed T1-T15) the
            uplift is measured against; scored on the SAME PyWake model.
        min_spacing_diameters: minimum inter-turbine spacing in rotor diameters
            (physical spacing = ``min_spacing_diameters * rotor_diameter_m``).
        wind_rose_freq: directional frequency per equal sector (summed to 1); when
            None an omnidirectional rose over ``default_sectors`` sectors is used.
        exclusion_zones: optional list of exclusion polygons (each an ordered list
            of ``(x, y)`` vertices) subtracted from the buildable area.
        n_turbines: how many turbines to site. Defaults to the baseline count so
            the uplift is a like-for-like N comparison.
        initial_x_m, initial_y_m: optional starting positions (default: the
            baseline, trimmed or padded to ``n_turbines``). Ignored when
            ``use_smart_start`` re-seeds.
        turbulence_intensity: ambient TI for the wake closure (default 0.10).
        max_iterations: SLSQP driver ``maxiter`` (a solver knob, not physics).
        use_smart_start: seed with PyWake ``smart_start`` (greedy high-AEP,
            spacing-respecting placement) before the gradient polish.
        default_sectors: sectors for an omnidirectional rose when ``wind_rose_freq``
            is None.
        random_seed: optional seed for ``smart_start`` and stochastic padding
            reproducibility.
        constraint_tolerance_m: numerical tolerance (m) for post-optimization
            boundary, exclusion-zone, and minimum-spacing verification.
        strict_constraints: when True (default), raise ``RuntimeError`` if the
            final layout violates boundary, exclusion, or spacing constraints
            beyond ``constraint_tolerance_m``.

    Returns:
        A :class:`LayoutOptimizationResult`.

    Raises:
        RuntimeError: TopFarm (the ``[micrositing]`` extra) is not installed, or
            post-optimization constraints are violated when ``strict_constraints``
            is True.
        ValueError: invalid turbine curves, polygons, baseline arrays, or
            non-positive turbine count.
    """
    tf = _load_topfarm_api()

    bx = np.asarray(baseline_x_m, dtype=float)
    by = np.asarray(baseline_y_m, dtype=float)
    if bx.shape != by.shape or bx.ndim != 1:
        raise ValueError(
            "baseline_x_m and baseline_y_m must be 1-D arrays of equal length"
        )
    if bx.size == 0:
        raise ValueError("baseline_x_m and baseline_y_m must not be empty")
    if not (np.all(np.isfinite(bx)) and np.all(np.isfinite(by))):
        raise ValueError(
            "baseline_x_m and baseline_y_m must contain only finite values"
        )

    n = int(n_turbines) if n_turbines is not None else int(bx.size)
    if n <= 0:
        raise ValueError("n_turbines must be a positive integer")

    _validate_turbine_spec(turbine)

    if not np.isfinite(float(weibull_a)) or float(weibull_a) <= 0.0:
        raise ValueError(f"weibull_a must be finite and > 0; got {weibull_a!r}")
    if not np.isfinite(float(weibull_k)) or float(weibull_k) <= 0.0:
        raise ValueError(f"weibull_k must be finite and > 0; got {weibull_k!r}")
    if (
        not np.isfinite(float(min_spacing_diameters))
        or float(min_spacing_diameters) < 0.0
    ):
        raise ValueError(
            f"min_spacing_diameters must be finite and >= 0; got {min_spacing_diameters!r}"
        )
    if not np.isfinite(float(turbulence_intensity)) or not (
        0.0 <= float(turbulence_intensity) < 1.0
    ):
        raise ValueError(
            f"turbulence_intensity must lie in [0.0, 1.0); got {turbulence_intensity!r}"
        )
    if int(max_iterations) < 1:
        raise ValueError(f"max_iterations must be >= 1; got {max_iterations!r}")
    if int(default_sectors) < 1:
        raise ValueError(f"default_sectors must be >= 1; got {default_sectors!r}")
    if (
        not np.isfinite(float(constraint_tolerance_m))
        or float(constraint_tolerance_m) < 0.0
    ):
        raise ValueError(
            f"constraint_tolerance_m must be finite and >= 0; got {constraint_tolerance_m!r}"
        )

    if wind_rose_freq is not None:
        freq_arr = np.asarray(wind_rose_freq, dtype=float)
        if freq_arr.ndim != 1 or freq_arr.size == 0:
            raise ValueError("wind_rose_freq must be a non-empty 1-D sequence")
        if (
            not np.all(np.isfinite(freq_arr))
            or np.any(freq_arr < 0.0)
            or float(freq_arr.sum()) <= 0.0
        ):
            raise ValueError(
                "wind_rose_freq must contain finite non-negative weights with a positive sum"
            )

    boundary_arr = _validate_polygon(boundary, name="boundary")
    exclusion_arrs: list[np.ndarray] = [
        _validate_polygon(poly, name=f"exclusion_zones[{idx}]")
        for idx, poly in enumerate(exclusion_zones or ())
    ]

    rotor_d = float(turbine.rotor_diameter_m)
    min_spacing_m = float(min_spacing_diameters) * rotor_d

    wfm = _build_wind_farm_model(
        turbine,
        weibull_a=weibull_a,
        weibull_k=weibull_k,
        wind_rose_freq=wind_rose_freq,
        turbulence_intensity=turbulence_intensity,
        default_sectors=default_sectors,
    )

    # --- Constraints (boundary inclusion + optional exclusion, + min spacing) ---
    if exclusion_arrs:
        if tf.InclusionZone is None or tf.ExclusionZone is None:
            raise RuntimeError(
                "Installed TopFarm version does not provide InclusionZone/ExclusionZone "
                "required for exclusion_zones."
            )
        zones: list[InclusionZone | ExclusionZone] = [tf.InclusionZone(boundary_arr)]
        for excl_arr in exclusion_arrs:
            zones.append(tf.ExclusionZone(excl_arr))
        xy_boundary = tf.XYBoundaryConstraint(zones, boundary_type="multi_polygon")
    elif _is_convex_polygon(boundary_arr):
        xy_boundary = tf.XYBoundaryConstraint(boundary_arr, boundary_type="convex_hull")
    else:
        xy_boundary = tf.XYBoundaryConstraint(boundary_arr, boundary_type="polygon")

    constraints: list[XYBoundaryConstraint | SpacingConstraint] = [xy_boundary]
    if n > 1:
        constraints.append(tf.SpacingConstraint(min_spacing_m))

    # --- Cost model: MAXIMISE farm AEP (GWh/yr). TopFarm minimises, so we return
    #     -AEP and flip the reported sign back out. ---
    def _aep_cost(x: np.ndarray, y: np.ndarray) -> float:
        return -_farm_aep_gwh(wfm, x, y)

    cost_comp = tf.CostModelComponent(
        input_keys=["x", "y"],
        n_wt=n,
        cost_function=_aep_cost,
        objective=True,
        maximize=False,  # we already negated AEP inside _aep_cost
        output_keys=["aep_neg_gwh"],
    )

    x0, y0 = _prepare_initial_positions(
        n=n,
        baseline_x=bx,
        baseline_y=by,
        initial_x_m=initial_x_m,
        initial_y_m=initial_y_m,
        boundary_arr=boundary_arr,
        exclusion_arrs=exclusion_arrs,
        min_spacing_m=min_spacing_m,
        random_seed=random_seed,
    )

    driver = tf.EasyScipyOptimizeDriver(optimizer="SLSQP", maxiter=int(max_iterations))
    problem = tf.TopFarmProblem(
        design_vars={"x": x0, "y": y0},
        cost_comp=cost_comp,
        constraints=constraints,
        driver=driver,
        plot_comp=tf.NoPlot(),
    )

    if use_smart_start:
        # Greedy, spacing-respecting high-AEP seeding on a boundary-aware grid before
        # the gradient polish (PyWake/TopFarm smart_start). Best-effort: on any solver
        # hiccup we fall back to the x0/y0 seed so a run never hard-fails on seeding.
        try:
            xs, ys = _smart_start_grid(
                boundary_arr,
                exclusion_zones=exclusion_arrs,
                n_turbines=n,
                random_seed=random_seed,
            )
            problem.smart_start(
                xs,
                ys,
                min_space=min_spacing_m,
                random_pct=0.0,
                seed=random_seed,
                show_progress=False,
            )
        except Exception as exc:  # pragma: no cover - smart_start is a best-effort seed
            logger.warning("smart_start seeding skipped (%s); using x0/y0 seed", exc)

    _, state, recorder = problem.optimize()
    opt_x = np.asarray(state["x"], dtype=float)
    opt_y = np.asarray(state["y"], dtype=float)

    constraints_ok, max_boundary_viol, max_spacing_viol = (
        _verify_post_optimization_constraints(
            opt_x=opt_x,
            opt_y=opt_y,
            boundary_arr=boundary_arr,
            exclusion_arrs=exclusion_arrs,
            min_spacing_m=min_spacing_m,
            constraint_tolerance_m=constraint_tolerance_m,
            strict_constraints=strict_constraints,
        )
    )

    optimized_aep = _farm_aep_gwh(wfm, opt_x, opt_y)
    baseline_aep = _farm_aep_gwh(wfm, bx, by)
    uplift, uplift_pct = _compute_uplift(optimized_aep, baseline_aep)

    n_iter = _extract_iteration_count(driver, recorder, cost_comp)
    converged = _extract_converged(driver, recorder)

    return LayoutOptimizationResult(
        optimized_x_m=opt_x,
        optimized_y_m=opt_y,
        optimized_aep_gwh=optimized_aep,
        baseline_aep_gwh=baseline_aep,
        uplift_gwh=uplift,
        uplift_pct=uplift_pct,
        n_turbines=n,
        min_spacing_m=min_spacing_m,
        driver="SLSQP",
        n_iterations=n_iter,
        converged=converged,
        constraints_satisfied=constraints_ok,
        max_boundary_violation_m=max_boundary_viol,
        max_spacing_violation_m=max_spacing_viol,
    )
