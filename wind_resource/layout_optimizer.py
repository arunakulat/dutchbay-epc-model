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
from typing import Any, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# IEC-37 style omnidirectional single-turbine defaults are intentionally NOT
# provided as silent numeric fallbacks (CESSPIT: no silent defaults). The caller
# supplies turbine geometry + a power/Ct curve. What we DO default is only the
# non-physical solver knobs (max iterations, sectors for an absent rose), which
# never affect an economic headline.


# ---------------------------------------------------------------------------
# CASPER optional-dependency guard
# ---------------------------------------------------------------------------
def _require_topfarm() -> Any:
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
    return topfarm


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
) -> Any:
    """Construct the PyWake Bastankhah-Porte-Agel 2014 wind-farm model.

    Identical site/turbine/closure choices to
    :func:`wind_resource.bankable_aep.model_wake_loss`, so a candidate scored here
    reconciles with the bankable engine.
    """
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
    # Niayifar & Porte-Agel (2016) TI-based wake-expansion closure — same as the
    # bankable engine's Bastankhah-Porte-Agel 2014 default.
    k_star = 0.38 * float(turbulence_intensity) + 0.004
    return Bastankhah_PorteAgel_2014(site, wt, k=k_star)


def _farm_aep_gwh(wfm: Any, x: Any, y: Any) -> float:
    """Wake-included farm AEP (GWh/yr) on the given PyWake model + positions.

    ``x``/``y`` are position sequences or ndarrays (typed ``Any`` since callers pass
    both ``np.ndarray`` and ``Sequence[float]``).
    """
    sim = wfm(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return float(sim.aep().sum())


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
) -> LayoutOptimizationResult:
    """Generate an AEP-optimized candidate layout via DTU TopFarm on PyWake.

    Runs a boundary-, spacing- and exclusion-constrained AEP maximisation and
    returns the proposed positions plus the AEP uplift vs a caller-supplied
    baseline. **KPI-NEUTRAL** — a candidate only; nothing here touches the
    headline economics (that is Deliverable B, out of scope).

    Args:
        boundary: inclusion-zone polygon as an ordered list of ``(x, y)`` vertices
            in a local planar CRS (metres). Not auto-closed — TopFarm handles that.
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
            baseline). Ignored when ``use_smart_start`` re-seeds.
        turbulence_intensity: ambient TI for the wake closure (default 0.10).
        max_iterations: SLSQP driver ``maxiter`` (a solver knob, not physics).
        use_smart_start: seed with PyWake ``smart_start`` (greedy high-AEP,
            spacing-respecting placement) before the gradient polish.
        default_sectors: sectors for an omnidirectional rose when ``wind_rose_freq``
            is None.
        random_seed: optional seed for ``smart_start`` reproducibility.

    Returns:
        A :class:`LayoutOptimizationResult`.

    Raises:
        RuntimeError: TopFarm (the ``[micrositing]`` extra) is not installed.
        ValueError: inconsistent baseline arrays or a non-positive turbine count.
    """
    _require_topfarm()
    from topfarm import TopFarmProblem
    from topfarm.constraint_components.boundary import XYBoundaryConstraint
    from topfarm.constraint_components.spacing import SpacingConstraint
    from topfarm.cost_models.cost_model_wrappers import CostModelComponent
    from topfarm.easy_drivers import EasyScipyOptimizeDriver
    from topfarm.plotting import NoPlot

    bx = np.asarray(baseline_x_m, dtype=float)
    by = np.asarray(baseline_y_m, dtype=float)
    if bx.shape != by.shape or bx.ndim != 1:
        raise ValueError(
            "baseline_x_m and baseline_y_m must be 1-D arrays of equal length"
        )
    n = int(n_turbines) if n_turbines is not None else int(bx.size)
    if n <= 0:
        raise ValueError("n_turbines must be a positive integer")

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
    boundary_arr = np.asarray(boundary, dtype=float)
    if exclusion_zones:
        # Modern TopFarm expresses a buildable area as an inclusion zone minus
        # exclusion zones. Import lazily so an older TopFarm without InclusionZone
        # still loads for the no-exclusion path.
        from topfarm.constraint_components.boundary import (
            ExclusionZone,
            InclusionZone,
        )

        zones: list[Any] = [InclusionZone(boundary_arr)]
        for poly in exclusion_zones:
            zones.append(ExclusionZone(np.asarray(poly, dtype=float)))
        xy_boundary = XYBoundaryConstraint(zones, boundary_type="multi_polygon")
    else:
        xy_boundary = XYBoundaryConstraint(boundary_arr)

    spacing = SpacingConstraint(min_spacing_m)

    # --- Cost model: MAXIMISE farm AEP (GWh/yr). TopFarm minimises, so we return
    #     -AEP and flip the reported sign back out. ---
    def _aep_cost(x: np.ndarray, y: np.ndarray) -> float:
        return -_farm_aep_gwh(wfm, x, y)

    cost_comp = CostModelComponent(
        input_keys=["x", "y"],
        n_wt=n,
        cost_function=_aep_cost,
        objective=True,
        maximize=False,  # we already negated AEP inside _aep_cost
        output_keys=["aep_neg_gwh"],
    )

    # --- Initial positions: caller-supplied, else the baseline (trimmed/padded to n). ---
    if initial_x_m is not None and initial_y_m is not None:
        x0 = np.asarray(initial_x_m, dtype=float)
        y0 = np.asarray(initial_y_m, dtype=float)
    else:
        x0 = bx.copy()
        y0 = by.copy()
    if x0.size != n:
        # Seed from the boundary centroid so smart_start has a valid start of size n.
        cx = float(np.mean(boundary_arr[:, 0]))
        cy = float(np.mean(boundary_arr[:, 1]))
        x0 = np.full(n, cx)
        y0 = np.full(n, cy)

    problem = TopFarmProblem(
        design_vars={"x": x0, "y": y0},
        cost_comp=cost_comp,
        constraints=[xy_boundary, spacing],
        driver=EasyScipyOptimizeDriver(optimizer="SLSQP", maxiter=int(max_iterations)),
        plot_comp=NoPlot(),
    )

    if use_smart_start:
        # Greedy, spacing-respecting high-AEP seeding on a coarse grid before the
        # gradient polish (PyWake/TopFarm smart_start). Best-effort: on any solver
        # hiccup we fall back to the x0/y0 seed so a run never hard-fails on seeding.
        try:
            xs, ys = _smart_start_grid(boundary_arr)
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

    _, state, _ = problem.optimize()
    opt_x = np.asarray(state["x"], dtype=float)
    opt_y = np.asarray(state["y"], dtype=float)

    optimized_aep = _farm_aep_gwh(wfm, opt_x, opt_y)
    baseline_aep = _farm_aep_gwh(wfm, bx, by)
    uplift = optimized_aep - baseline_aep
    uplift_pct = 100.0 * uplift / baseline_aep if baseline_aep > 0 else 0.0

    n_iter = int(getattr(cost_comp, "counter", 0))

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
    )


def _smart_start_grid(
    boundary_arr: np.ndarray, points_per_axis: int = 20
) -> tuple[np.ndarray, np.ndarray]:
    """Candidate-point grid (over the boundary bbox) for TopFarm ``smart_start``.

    ``smart_start`` evaluates AEP over these candidate points and greedily picks
    high-AEP, spacing-respecting positions (spacing enforced by ``min_space``). A
    bbox grid is sufficient — the boundary constraint prunes out-of-bounds picks
    during the subsequent gradient polish.
    """
    xmin, ymin = boundary_arr[:, 0].min(), boundary_arr[:, 1].min()
    xmax, ymax = boundary_arr[:, 0].max(), boundary_arr[:, 1].max()
    gx = np.linspace(xmin, xmax, int(points_per_axis))
    gy = np.linspace(ymin, ymax, int(points_per_axis))
    xv, yv = np.meshgrid(gx, gy)
    return xv.ravel(), yv.ravel()
