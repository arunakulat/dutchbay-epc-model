#!/usr/bin/env python
"""Tests for the TopFarm micro-siting layout optimizer (wind_resource.layout_optimizer).

Issue #835 Deliverable A (KPI-neutral candidate generator).

Structure:
    * ONE always-runnable test asserts the CASPER ``_require_topfarm`` guard raises an
      actionable ImportError-derived error naming the ``[micrositing]`` extra — it runs
      EVEN when TopFarm is absent (it monkeypatches ``sys.modules['topfarm'] = None``),
      so the guard is covered on a bare CI install.
    * The optimizer tests each carry a ``@requires_topfarm`` skip marker (CASPER) — like
      the [wind] PyWake tests and the [solar] pvlib tests they SKIP when the optional
      [micrositing] extra is absent, so the base finance stack never depends on TopFarm.
      (A module-level ``pytest.importorskip`` would skip the ENTIRE file, taking the
      always-runnable guard test with it — hence the per-test marker instead.)

``layout_optimizer`` imports TopFarm lazily (only inside the run functions), so every
public symbol below imports fine on a bare install; only the tests that actually invoke
the optimizer are skipped.
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pytest

from wind_resource.layout_optimizer import (
    LayoutOptimizationResult,
    TurbineSpec,
    _build_wind_farm_model,
    _farm_aep_gwh,
    _require_topfarm,
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
