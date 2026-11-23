#!/usr/bin/env python
"""Tests for the TopFarm micro-siting layout optimizer (wind_resource.layout_optimizer).

Issue #835 Deliverable A (KPI-neutral candidate generator).

Structure:
    * Pure unit tests cover geometry validation, turbine-curve validation,
      boundary-aware smart-start grids, shrink/grow initial-position seeding,
      post-optimization constraint verification, driver iteration extraction, and
      uplift math — they run EVEN when TopFarm is absent.
    * The CASPER ``_require_topfarm`` guard test asserts an actionable error
      naming the ``[micrositing]`` extra when ``topfarm`` is unavailable.
    * The TopFarm+PyWake integration tests each carry a ``@requires_topfarm``
      skip marker (CASPER) so the base finance stack never depends on TopFarm.
"""

from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace

import numpy as np
import pytest

import wind_resource.layout_optimizer as lo
from wind_resource.layout_optimizer import (
    LayoutOptimizationResult,
    TurbineSpec,
    _build_wind_farm_model,
    _compute_uplift,
    _extract_converged,
    _extract_iteration_count,
    _farm_aep_gwh,
    _is_convex_polygon,
    _points_signed_distance_to_buildable_area,
    _prepare_initial_positions,
    _require_topfarm,
    _smart_start_grid,
    _validate_polygon,
    _validate_turbine_spec,
    _verify_post_optimization_constraints,
    optimize_layout,
)

#: True when the [micrositing] extra (TopFarm) is importable in this environment.
_HAS_TOPFARM = importlib.util.find_spec("topfarm") is not None

#: Skip marker for tests that actually run the optimizer (need the real TopFarm).
requires_topfarm = pytest.mark.skipif(
    not _HAS_TOPFARM, reason="requires the optional [micrositing] extra (TopFarm)"
)


# ── The CASPER optional-dep guard — ALWAYS runs (even without the extra) ──────────
def test_require_topfarm_raises_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force ``import topfarm`` to fail even if it happens to be installed, by shadowing
    # it with None in sys.modules — mirrors the solar/_require_pvlib guard test.
    monkeypatch.setitem(sys.modules, "topfarm", None)
    with pytest.raises(RuntimeError, match=r"\[micrositing\] extra"):
        _require_topfarm()


# ---------------------------------------------------------------------------
# A small synthetic reference case (generic 2 MW-ish turbine, 100 m rotor).
# All numbers are test fixtures — nothing here is a committed scenario or headline.
# ---------------------------------------------------------------------------
_WS = np.arange(3.0, 26.0)
# Smooth cubic-then-rated power curve (kW) and a flat-ish Ct — enough for wake physics.
_POWER_KW = np.clip((_WS / 12.0) ** 3, 0.0, 1.0) * 2000.0
_CT = np.full_like(_WS, 0.8)

# 2 km square buildable boundary (local planar metres).
_BOUNDARY = [[0.0, 0.0], [2000.0, 0.0], [2000.0, 2000.0], [0.0, 2000.0]]
# Non-convex L-shaped polygon (missing the [1000..2000] x [1000..2000] quadrant).
_L_BOUNDARY = [
    [0.0, 0.0],
    [2000.0, 0.0],
    [2000.0, 1000.0],
    [1000.0, 1000.0],
    [1000.0, 2000.0],
    [0.0, 2000.0],
]
# One central exclusion (e.g. a wetland / no-build parcel).
_EXCLUSION = [[800.0, 800.0], [1200.0, 800.0], [1200.0, 1200.0], [800.0, 1200.0]]

_ROTOR_D = 100.0
_MIN_SPACING_D = 4.0  # 4 rotor diameters -> 400 m


def _turbine() -> TurbineSpec:
    return TurbineSpec(
        rotor_diameter_m=_ROTOR_D,
        hub_height_m=100.0,
        wind_speed_ms=_WS,
        power_kw=_POWER_KW,
        thrust_coefficient=_CT,
        name="synthetic_2mw",
    )


def _tight_baseline() -> tuple[list[float], list[float]]:
    """A deliberately BAD, tightly-clustered baseline (lots of wake) in one corner."""
    xs = [200.0, 350.0, 500.0, 650.0]
    ys = [200.0, 350.0, 500.0, 650.0]
    return xs, ys


def _point_in_polygon(x: float, y: float, poly: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon (independent of TopFarm's own check)."""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def _min_pairwise_distance(x: np.ndarray, y: np.ndarray) -> float:
    best = np.inf
    for i in range(len(x)):
        for k in range(i + 1, len(x)):
            d = float(np.hypot(x[i] - x[k], y[i] - y[k]))
            best = min(best, d)
    return best


# ---------------------------------------------------------------------------
# Pure unit tests (no TopFarm / PyWake required)
# ---------------------------------------------------------------------------
def test_compute_uplift_identical_and_positive() -> None:
    uplift_gwh, uplift_pct = _compute_uplift(123.45, 123.45)
    assert uplift_gwh == 0.0
    assert uplift_pct == 0.0

    pos_gwh, pos_pct = _compute_uplift(110.0, 100.0)
    assert pos_gwh == pytest.approx(10.0)
    assert pos_pct == pytest.approx(10.0)

    zero_base_gwh, zero_base_pct = _compute_uplift(5.0, 0.0)
    assert zero_base_gwh == pytest.approx(5.0)
    assert zero_base_pct == 0.0


def test_validate_turbine_spec_physical_checks() -> None:
    # Valid baseline curve + valid curve with post-cut-out drop to 0.
    _validate_turbine_spec(_turbine())
    _validate_turbine_spec(
        TurbineSpec(
            rotor_diameter_m=100.0,
            hub_height_m=100.0,
            wind_speed_ms=[0.0, 3.0, 12.0, 25.0, 30.0],
            power_kw=[0.0, 0.0, 2000.0, 0.0, 0.0],
            thrust_coefficient=[0.0, 0.8, 0.8, 0.1, 0.0],
        )
    )

    with pytest.raises(ValueError, match="rotor_diameter_m"):
        _validate_turbine_spec(TurbineSpec(0.0, 100.0, _WS, _POWER_KW, _CT))
    with pytest.raises(ValueError, match="strictly increasing"):
        _validate_turbine_spec(
            TurbineSpec(
                100.0, 100.0, [3.0, 3.0, 5.0], [0.0, 100.0, 500.0], [0.8, 0.8, 0.8]
            )
        )
    with pytest.raises(ValueError, match="monotonically non-decreasing"):
        _validate_turbine_spec(
            TurbineSpec(
                100.0,
                100.0,
                [3.0, 6.0, 9.0, 12.0],
                [100.0, 800.0, 400.0, 2000.0],
                [0.8] * 4,
            )
        )
    with pytest.raises(ValueError, match="thrust_coefficient"):
        _validate_turbine_spec(
            TurbineSpec(
                100.0, 100.0, [3.0, 6.0, 9.0], [100.0, 800.0, 2000.0], [0.8, 1.2, 0.5]
            )
        )


def test_validate_polygon_and_convexity() -> None:
    sq = _validate_polygon(_BOUNDARY, name="boundary")
    assert sq.shape == (4, 2)
    assert _is_convex_polygon(sq) is True

    # Closed input strips duplicate closing vertex.
    closed_sq = _validate_polygon(_BOUNDARY + [_BOUNDARY[0]], name="boundary")
    assert closed_sq.shape == (4, 2)

    l_poly = _validate_polygon(_L_BOUNDARY, name="boundary")
    assert l_poly.shape == (6, 2)
    assert _is_convex_polygon(l_poly) is False

    # Bowtie self-intersecting polygon rejected.
    with pytest.raises(ValueError, match="simple polygon"):
        _validate_polygon(
            [[0.0, 0.0], [100.0, 100.0], [100.0, 0.0], [0.0, 100.0]],
            name="boundary",
        )

    # Collinear zero-area polygon rejected.
    with pytest.raises(ValueError, match="non-zero area"):
        _validate_polygon([[0.0, 0.0], [50.0, 0.0], [100.0, 0.0]], name="boundary")

    # Duplicate consecutive vertices rejected.
    with pytest.raises(ValueError, match="duplicate consecutive"):
        _validate_polygon(
            [[0.0, 0.0], [100.0, 0.0], [100.0, 0.0], [0.0, 100.0]],
            name="boundary",
        )


def test_points_signed_distance_to_buildable_area() -> None:
    l_poly = _validate_polygon(_L_BOUNDARY, name="boundary")
    excl = _validate_polygon(
        [[200.0, 200.0], [400.0, 200.0], [400.0, 400.0], [200.0, 400.0]], name="excl"
    )
    # Point 1: interior of L-shape outside exclusion -> positive
    # Point 2: inside concavity [1500, 1500] -> negative (-500)
    # Point 3: inside exclusion [300, 300] -> negative (-100)
    # Point 4: on boundary edge [0, 500] -> 0.0
    xs = np.array([500.0, 1500.0, 300.0, 0.0])
    ys = np.array([500.0, 1500.0, 300.0, 500.0])
    d = _points_signed_distance_to_buildable_area(xs, ys, l_poly, [excl])
    assert d[0] > 0.0
    assert d[1] == pytest.approx(-500.0)
    assert d[2] == pytest.approx(-100.0)
    assert d[3] == pytest.approx(0.0)


def test_smart_start_grid_is_boundary_aware_and_seeded() -> None:
    l_poly = _validate_polygon(_L_BOUNDARY, name="boundary")
    excl = _validate_polygon(_EXCLUSION, name="exclusion")
    xs1, ys1 = _smart_start_grid(
        l_poly, exclusion_zones=[excl], n_turbines=8, random_seed=42
    )
    xs2, ys2 = _smart_start_grid(
        l_poly, exclusion_zones=[excl], n_turbines=8, random_seed=42
    )
    assert xs1.size > 0
    np.testing.assert_array_equal(xs1, xs2)
    np.testing.assert_array_equal(ys1, ys2)
    dists = _points_signed_distance_to_buildable_area(xs1, ys1, l_poly, [excl])
    assert np.all(dists >= 0.0)

    # Thin diagonal sliver (< 2% of bbox area) still produces feasible points via rejection sampling.
    sliver = _validate_polygon(
        [[0.0, 0.0], [5000.0, 4950.0], [5000.0, 5000.0], [0.0, 50.0]],
        name="sliver",
    )
    sx, sy = _smart_start_grid(sliver, n_turbines=5, random_seed=7)
    assert sx.size >= 5
    assert np.all(_points_signed_distance_to_buildable_area(sx, sy, sliver) >= 0.0)


def test_prepare_initial_positions_shrink_and_grow() -> None:
    sq = _validate_polygon(_BOUNDARY, name="boundary")
    excl = _validate_polygon(_EXCLUSION, name="exclusion")
    bx = np.array([200.0, 600.0, 1500.0, 1800.0])
    by = np.array([200.0, 600.0, 400.0, 1700.0])

    # Shrinking: takes the first n baseline points.
    sx, sy = _prepare_initial_positions(
        n=2,
        baseline_x=bx,
        baseline_y=by,
        initial_x_m=None,
        initial_y_m=None,
        boundary_arr=sq,
        exclusion_arrs=[excl],
        min_spacing_m=400.0,
        random_seed=42,
    )
    np.testing.assert_array_equal(sx, bx[:2])
    np.testing.assert_array_equal(sy, by[:2])

    # Growing: keeps baseline and pads interior spacing-respecting points deterministically.
    gx1, gy1 = _prepare_initial_positions(
        n=6,
        baseline_x=bx,
        baseline_y=by,
        initial_x_m=None,
        initial_y_m=None,
        boundary_arr=sq,
        exclusion_arrs=[excl],
        min_spacing_m=400.0,
        random_seed=42,
    )
    gx2, gy2 = _prepare_initial_positions(
        n=6,
        baseline_x=bx,
        baseline_y=by,
        initial_x_m=None,
        initial_y_m=None,
        boundary_arr=sq,
        exclusion_arrs=[excl],
        min_spacing_m=400.0,
        random_seed=42,
    )
    assert gx1.size == 6
    np.testing.assert_array_equal(gx1, gx2)
    np.testing.assert_array_equal(gy1, gy2)
    np.testing.assert_array_equal(gx1[:4], bx)
    np.testing.assert_array_equal(gy1[:4], by)
    # Padded points must lie inside buildable area (not inside exclusion or stacked on centroid).
    pad_dists = _points_signed_distance_to_buildable_area(gx1[4:], gy1[4:], sq, [excl])
    assert np.all(pad_dists >= 0.0)
    assert _min_pairwise_distance(gx1, gy1) >= 400.0 - 1e-6

    with pytest.raises(ValueError, match="must both be provided"):
        _prepare_initial_positions(
            n=4,
            baseline_x=bx,
            baseline_y=by,
            initial_x_m=[100.0],
            initial_y_m=None,
            boundary_arr=sq,
            exclusion_arrs=[],
            min_spacing_m=400.0,
            random_seed=None,
        )


def test_verify_post_optimization_constraints_catches_drift() -> None:
    sq = _validate_polygon(_BOUNDARY, name="boundary")
    excl = _validate_polygon(_EXCLUSION, name="exclusion")

    # Feasible layout passes.
    ok, bv, sv = _verify_post_optimization_constraints(
        opt_x=np.array([100.0, 1900.0]),
        opt_y=np.array([100.0, 1900.0]),
        boundary_arr=sq,
        exclusion_arrs=[excl],
        min_spacing_m=400.0,
        constraint_tolerance_m=1.0,
        strict_constraints=True,
    )
    assert ok is True
    assert bv == 0.0
    assert sv == 0.0

    # Boundary drift beyond tolerance raises when strict_constraints=True.
    with pytest.raises(RuntimeError, match="Post-optimization constraint check failed"):
        _verify_post_optimization_constraints(
            opt_x=np.array([-5.0, 1900.0]),
            opt_y=np.array([100.0, 1900.0]),
            boundary_arr=sq,
            exclusion_arrs=[],
            min_spacing_m=400.0,
            constraint_tolerance_m=1.0,
            strict_constraints=True,
        )

    # Exclusion-zone violation and spacing violation reported when strict_constraints=False.
    ok2, bv2, sv2 = _verify_post_optimization_constraints(
        opt_x=np.array([1000.0, 1050.0]),
        opt_y=np.array([1000.0, 1000.0]),
        boundary_arr=sq,
        exclusion_arrs=[excl],
        min_spacing_m=400.0,
        constraint_tolerance_m=1.0,
        strict_constraints=False,
    )
    assert ok2 is False
    assert bv2 == pytest.approx(200.0)
    assert sv2 == pytest.approx(350.0)


def test_extract_iteration_count_and_converged() -> None:
    drv_with_result = SimpleNamespace(
        result=SimpleNamespace(iter_count=17, success=True), iter_count=99, fail=True
    )
    rec = SimpleNamespace(num_cases=25)
    cc = SimpleNamespace(counter=150)
    assert _extract_iteration_count(drv_with_result, rec, cc) == 17
    assert _extract_converged(drv_with_result, rec) is True

    drv_no_result = SimpleNamespace(result=None, iter_count=12, fail=True)
    assert _extract_iteration_count(drv_no_result, rec, cc) == 12
    assert _extract_converged(drv_no_result, rec) is False

    drv_empty = SimpleNamespace(result=None)
    assert _extract_iteration_count(drv_empty, rec, cc) == 25
    assert _extract_iteration_count(drv_empty, None, cc) == 150


def test_optimize_layout_identical_baseline_uplift_mocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pure unit test verifying zero uplift when optimizer returns baseline unchanged."""
    bx = np.array([200.0, 1500.0, 200.0, 1500.0])
    by = np.array([200.0, 200.0, 1500.0, 1500.0])

    class _FakeDriver:
        def __init__(self, **kwargs: object) -> None:
            self.result = SimpleNamespace(iter_count=5, success=True)

    class _FakeCostComp:
        def __init__(self, **kwargs: object) -> None:
            self.counter = 99

    class _FakeProblem:
        def __init__(
            self, design_vars: dict[str, np.ndarray], **kwargs: object
        ) -> None:
            self._x = design_vars["x"]
            self._y = design_vars["y"]

        def optimize(self) -> tuple[float, dict[str, np.ndarray], SimpleNamespace]:
            return (
                -50.0,
                {"x": self._x.copy(), "y": self._y.copy()},
                SimpleNamespace(num_cases=5),
            )

    fake_api = lo._TopFarmAPI(
        TopFarmProblem=_FakeProblem,  # type: ignore[arg-type]
        XYBoundaryConstraint=lambda *a, **kw: object(),  # type: ignore[arg-type]
        SpacingConstraint=lambda *a, **kw: object(),  # type: ignore[arg-type]
        CostModelComponent=_FakeCostComp,  # type: ignore[arg-type]
        EasyScipyOptimizeDriver=_FakeDriver,  # type: ignore[arg-type]
        NoPlot=lambda: object(),  # type: ignore[arg-type]
        InclusionZone=None,
        ExclusionZone=None,
    )
    monkeypatch.setattr(lo, "_load_topfarm_api", lambda: fake_api)
    monkeypatch.setattr(
        lo,
        "_build_wind_farm_model",
        lambda *a, **kw: (
            lambda x, y: SimpleNamespace(aep=lambda: np.full_like(x, 12.5))
        ),
    )

    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        use_smart_start=False,
    )
    assert res.baseline_aep_gwh == pytest.approx(50.0)
    assert res.optimized_aep_gwh == pytest.approx(50.0)
    assert res.uplift_gwh == 0.0
    assert res.uplift_pct == 0.0
    assert res.n_iterations == 5
    assert res.converged is True
    assert res.constraints_satisfied is True


# ---------------------------------------------------------------------------
# Integration tests (require TopFarm + PyWake)
# ---------------------------------------------------------------------------
@requires_topfarm
def test_optimize_layout_returns_result_type() -> None:
    bx, by = _tight_baseline()
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=40,
        use_smart_start=False,  # deterministic from the baseline seed
    )
    assert isinstance(res, LayoutOptimizationResult)
    assert res.n_turbines == len(bx)
    assert res.min_spacing_m == pytest.approx(_MIN_SPACING_D * _ROTOR_D)
    assert res.driver == "SLSQP"
    assert res.constraints_satisfied is True
    assert res.n_iterations <= 45


@requires_topfarm
def test_optimized_turbines_lie_inside_boundary() -> None:
    bx, by = _tight_baseline()
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=60,
        use_smart_start=False,
    )
    # A tiny numerical tolerance on the boundary (SLSQP satisfies constraints to a tol).
    tol = 1.0  # metres
    padded = [
        [-tol, -tol],
        [2000.0 + tol, -tol],
        [2000.0 + tol, 2000.0 + tol],
        [-tol, 2000.0 + tol],
    ]
    for x, y in zip(res.optimized_x_m, res.optimized_y_m, strict=True):
        assert _point_in_polygon(float(x), float(y), padded), (x, y)


@requires_topfarm
def test_optimized_layout_respects_min_spacing() -> None:
    bx, by = _tight_baseline()
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=80,
        use_smart_start=False,
    )
    min_d = _min_pairwise_distance(res.optimized_x_m, res.optimized_y_m)
    # SLSQP satisfies the spacing constraint to a small numerical tolerance.
    assert min_d >= res.min_spacing_m - 1.0, (min_d, res.min_spacing_m)


@requires_topfarm
def test_optimized_aep_at_least_baseline() -> None:
    """The optimizer must not do WORSE than the (bad, clustered) baseline."""
    bx, by = _tight_baseline()
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=80,
        use_smart_start=False,
    )
    # >= within a tiny numerical tolerance; a clustered baseline should actually improve.
    assert res.optimized_aep_gwh >= res.baseline_aep_gwh - 1e-6
    assert res.uplift_gwh == pytest.approx(res.optimized_aep_gwh - res.baseline_aep_gwh)


@requires_topfarm
def test_uplift_positive_for_clustered_baseline() -> None:
    """A tightly-clustered, wake-heavy baseline should be strictly improved."""
    bx, by = _tight_baseline()
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=100,
        use_smart_start=False,
    )
    assert res.uplift_gwh > 0.0
    assert res.uplift_pct > 0.0


@requires_topfarm
def test_exclusion_zone_is_respected() -> None:
    """No optimized turbine may sit inside the central exclusion parcel."""
    bx, by = _tight_baseline()
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        exclusion_zones=[_EXCLUSION],
        max_iterations=80,
        use_smart_start=False,
    )
    for x, y in zip(res.optimized_x_m, res.optimized_y_m, strict=True):
        # Strictly-inside the exclusion is forbidden (a small negative tol = on-edge ok).
        inset = [
            [801.0, 801.0],
            [1199.0, 801.0],
            [1199.0, 1199.0],
            [801.0, 1199.0],
        ]
        assert not _point_in_polygon(float(x), float(y), inset), (x, y)


@requires_topfarm
def test_non_convex_l_boundary_respected() -> None:
    """A non-convex boundary must exclude its concave notch (not expand to convex hull)."""
    bx = [200.0, 400.0, 600.0]
    by = [200.0, 600.0, 200.0]
    res = optimize_layout(
        boundary=_L_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=60,
        use_smart_start=True,
        random_seed=42,
    )
    assert res.constraints_satisfied is True
    assert res.max_boundary_violation_m <= 1.0
    # Verify no turbine entered the concave notch [1001..2000] x [1001..2000].
    for x, y in zip(res.optimized_x_m, res.optimized_y_m, strict=True):
        assert not (x > 1001.0 and y > 1001.0), (x, y)


@requires_topfarm
def test_shrink_and_grow_n_turbines_integration() -> None:
    """Shrinking and growing n_turbines vs baseline produce feasible layouts."""
    bx, by = _tight_baseline()
    res_shrink = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        n_turbines=3,
        max_iterations=50,
        use_smart_start=False,
    )
    assert res_shrink.n_turbines == 3
    assert res_shrink.optimized_x_m.size == 3
    assert res_shrink.constraints_satisfied is True

    res_grow = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        n_turbines=5,
        max_iterations=50,
        use_smart_start=False,
        random_seed=42,
    )
    assert res_grow.n_turbines == 5
    assert res_grow.optimized_x_m.size == 5
    assert res_grow.constraints_satisfied is True


@requires_topfarm
def test_single_turbine_identical_aep_zero_uplift() -> None:
    """With 1 turbine on a UniformWeibullSite, every interior point has identical AEP."""
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=[1000.0],
        baseline_y_m=[1000.0],
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=10,
        use_smart_start=False,
    )
    assert res.optimized_aep_gwh == pytest.approx(res.baseline_aep_gwh, rel=1e-9)
    assert res.uplift_gwh == pytest.approx(0.0, abs=1e-9)
    assert res.uplift_pct == pytest.approx(0.0, abs=1e-9)


@requires_topfarm
def test_post_optimization_constraint_violation_raises_or_reports() -> None:
    """Infeasible spacing on a 2 km square fails loudly or reports violations."""
    bx, by = _tight_baseline()
    # 25 D = 2500 m > max possible 4-point separation on a 2000 m square (2000 m).
    with pytest.raises(RuntimeError, match="Post-optimization constraint check failed"):
        optimize_layout(
            boundary=_BOUNDARY,
            turbine=_turbine(),
            weibull_a=9.0,
            weibull_k=2.0,
            baseline_x_m=bx,
            baseline_y_m=by,
            min_spacing_diameters=25.0,
            max_iterations=10,
            use_smart_start=False,
            strict_constraints=True,
        )

    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=25.0,
        max_iterations=10,
        use_smart_start=False,
        strict_constraints=False,
    )
    assert res.constraints_satisfied is False
    assert res.max_spacing_violation_m > 1.0


@requires_topfarm
def test_scored_aep_reconciles_with_pywake_model() -> None:
    """The reported baseline AEP equals a direct PyWake score on the same model."""
    bx, by = _tight_baseline()
    wfm = _build_wind_farm_model(
        _turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        wind_rose_freq=None,
        turbulence_intensity=0.10,
        default_sectors=12,
    )
    direct = _farm_aep_gwh(wfm, bx, by)
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        max_iterations=10,
        use_smart_start=False,
    )
    assert res.baseline_aep_gwh == pytest.approx(direct, rel=1e-9)


@requires_topfarm
def test_directional_wind_rose_is_accepted() -> None:
    """A supplied (non-omnidirectional) wind rose is honoured without error."""
    bx, by = _tight_baseline()
    rose = np.zeros(12)
    rose[6] = 0.6  # a dominant sector
    rose[5] = 0.2
    rose[7] = 0.2
    res = optimize_layout(
        boundary=_BOUNDARY,
        turbine=_turbine(),
        weibull_a=9.0,
        weibull_k=2.0,
        baseline_x_m=bx,
        baseline_y_m=by,
        min_spacing_diameters=_MIN_SPACING_D,
        wind_rose_freq=rose,
        max_iterations=40,
        use_smart_start=False,
    )
    assert res.optimized_aep_gwh > 0.0


@requires_topfarm
def test_bad_baseline_arrays_rejected() -> None:
    with pytest.raises(ValueError, match="equal length"):
        optimize_layout(
            boundary=_BOUNDARY,
            turbine=_turbine(),
            weibull_a=9.0,
            weibull_k=2.0,
            baseline_x_m=[0.0, 1.0, 2.0],
            baseline_y_m=[0.0, 1.0],
            min_spacing_diameters=_MIN_SPACING_D,
        )
