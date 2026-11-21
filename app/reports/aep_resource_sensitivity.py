"""Wind-resource AEP sensitivity for the lender report (#1615 step B).

The owner ruled on #1615 (2026-11-16) to wire the AEP analytics cluster into reports rather
than retire it. This module is the one report seam that consumes the cluster: the
resource-side AEP tornado (:mod:`analytics.wind.aep_tornado`) and the Monte Carlo AEP
(:mod:`analytics.wind.mc_aep_weibull`). The boundary guard
(``tests/lint/test_aep_analytics_cluster_boundary.py``) allows this file, and no other live
file, to import those two modules.

What the section is, and is not:

* It is a **labelled resource sensitivity**, a model output beside the report's basis. The
  energy and every financial figure stay on the committed IEC P50/P90 from the frozen export
  (``run_result['yield_reconciliation']``); nothing here feeds finance.
* Every input comes from the scenario: the Weibull ``wind_resource.weibull_a/k``, the turbine
  count and hub height, the selected power curve and its air-density basis, the loss stack and
  ``monte_carlo.weibull_uncertainty_pct``. Nothing is site-specific in code.
* It reconciles the cluster against the committed basis and says why the two differ, so the
  report never shows two AEP figures that disagree without a reason.
* There is no measured site wind data and no P90 evidence, so the section supports no
  bankable resource claim (#1110 L04). F-5 holds.

GWTF:
    - FRAMEWORK-03: one seam; the report model holds the typed block, this module fills it.
    - FRAMEWORK-01: a scenario that cannot build the section gets a stated reason, listed
      under "sections not run", never a silent omission or a default figure.
"""

from __future__ import annotations

from math import gamma
from typing import Any, Mapping, Optional, Tuple, Union

from analytics.wind.aep_tornado import tornado_from_config
from analytics.wind.mc_aep_weibull import WeibullFit, run_mc_aep
from app.reports.report_model import (
    AepResourceSensitivityBlock,
    AepTornadoRow,
)

__all__ = [
    "AEP_MC_N_SAMPLES",
    "AEP_MC_SEED",
    "SECTION_AEP_RESOURCE",
    "build_aep_resource_sensitivity",
]

#: The section's name in the report's "sections not run" list.
SECTION_AEP_RESOURCE = "Wind resource sensitivity: AEP tornado and Monte Carlo"

#: Monte Carlo draws and seed. Fixed so the section is reproducible run to run; the spread
#: reflects the Weibull uncertainty, not sampling noise (2,000 draws).
AEP_MC_N_SAMPLES = 2000
AEP_MC_SEED = 42

_DRIVER_LABELS = {
    "wind_speed_bias": "Mean wind speed",
    "shear_exponent": "Shear exponent",
    "losses": "Loss stack (relative)",
    "power_curve": "Power curve",
}


def _float(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _committed_basis(
    run_result: Mapping[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    """The committed net P50 and P90 (GWh) the finance run used, from its reconciliation."""
    record = run_result.get("yield_reconciliation")
    if not isinstance(record, Mapping):
        return None, None
    p50 = _float(record.get("implied_net_aep_gwh"))
    p90_block = record.get("p90")
    p90 = (
        _float(p90_block.get("frozen_net_aep_p90_gwh"))
        if isinstance(p90_block, Mapping)
        else None
    )
    return p50, p90


def _pct_diff(value: float, reference: float) -> float:
    return 100.0 * (value - reference) / reference


def build_aep_resource_sensitivity(
    scenario: Mapping[str, Any],
    run_result: Mapping[str, Any],
    *,
    n_samples: int = AEP_MC_N_SAMPLES,
    seed: int = AEP_MC_SEED,
) -> Union[AepResourceSensitivityBlock, str]:
    """Build the wind-resource AEP sensitivity block, or say why it cannot be built.

    Args:
        scenario: The parsed scenario config the run used.
        run_result: The finance run's result (for the committed P50/P90).
        n_samples: Monte Carlo draws.
        seed: Monte Carlo seed.

    Returns:
        The typed block, or a ``"not run: ..."`` reason string for the report's
        "sections not run" list.
    """
    wr = scenario.get("wind_resource")
    resource = scenario.get("resource")
    if not isinstance(wr, Mapping) or not isinstance(resource, Mapping):
        return (
            "not run: the scenario declares no wind_resource and resource blocks "
            "(no wind Weibull to sweep)"
        )
    weibull_a = _float(wr.get("weibull_a"))
    weibull_k = _float(wr.get("weibull_k"))
    if weibull_a is None or weibull_k is None:
        return "not run: the scenario declares no wind_resource.weibull_a and weibull_k"
    if not isinstance(resource.get("losses"), Mapping):
        return "not run: the scenario declares no resource.losses stack"
    turbines = resource.get("turbines") or {}
    n_turbines = turbines.get("count") if isinstance(turbines, Mapping) else None
    if n_turbines is None:
        return "not run: the scenario declares no resource.turbines.count"
    power_curve = resource.get("power_curve") or {}
    curve_key = (
        power_curve.get("curve_key") if isinstance(power_curve, Mapping) else None
    )
    if not curve_key:
        return "not run: the scenario declares no resource.power_curve.curve_key"
    mc_block = scenario.get("monte_carlo")
    sigma_pct = (
        _float(mc_block.get("weibull_uncertainty_pct"))
        if isinstance(mc_block, Mapping)
        else None
    )
    if sigma_pct is None:
        return "not run: the scenario declares no monte_carlo.weibull_uncertainty_pct"

    try:
        frame = tornado_from_config(scenario)
    except (KeyError, ValueError) as exc:
        return f"not run: the AEP tornado could not run ({type(exc).__name__}: {exc})"

    rho_site = _float(power_curve.get("air_density_site_kgm3"))
    if rho_site is None:
        rho_site = _float(wr.get("air_density_kgm3"))
    fit = WeibullFit(
        a=weibull_a,
        k=weibull_k,
        mean_ws=weibull_a * gamma(1.0 + 1.0 / weibull_k),
        n_obs=0,
    )
    mc_kwargs: dict[str, Any] = {}
    if rho_site is not None:
        mc_kwargs["air_density_kgm3"] = rho_site
    try:
        mc = run_mc_aep(
            fit,
            n_turbines=int(n_turbines),
            capacity_mw=_float(turbines.get("rated_power_mw")) or 0.0,
            losses=resource["losses"],
            curve_key=str(curve_key),
            n_samples=n_samples,
            weibull_uncertainty_pct=sigma_pct,
            seed=seed,
            **mc_kwargs,
        )
    except (KeyError, ValueError) as exc:
        return (
            f"not run: the AEP Monte Carlo could not run ({type(exc).__name__}: {exc})"
        )

    base_gwh = float(frame["base_aep_gwh"].iloc[0])
    rows = [
        AepTornadoRow(
            driver=_DRIVER_LABELS.get(str(r["driver"]), str(r["driver"])),
            low_label=str(r["minus_label"]),
            high_label=str(r["plus_label"]),
            low_gwh=float(r["aep_minus_gwh"]),
            high_gwh=float(r["aep_plus_gwh"]),
            swing_gwh=float(r["abs_swing_gwh"]),
            swing_pct=float(r["swing_pct"]),
        )
        for r in frame.to_dict("records")
    ]
    pct = mc["percentiles"]
    committed_p50, committed_p90 = _committed_basis(run_result)
    uncertainty = resource.get("uncertainty") or {}
    haircut_pct = (
        _float(uncertainty.get("p50_haircut_pct"))
        if isinstance(uncertainty, Mapping)
        else None
    )

    notes = [
        (
            "The cluster's base net AEP integrates the scenario's Weibull "
            f"(A {weibull_a:g} m/s, k {weibull_k:g}) over the {curve_key} power curve"
            + (" with the site air-density correction" if rho_site is not None else "")
            + " and applies the scenario's loss stack. It is an analytic integral, not the "
            "timeseries engine that wrote the committed figure."
        )
    ]
    if committed_p50 is not None:
        line = (
            f"Against the net P50 the finance run uses, {committed_p50:,.1f} GWh, the cluster "
            f"base differs by {_pct_diff(base_gwh, committed_p50):+.1f}%."
        )
        if haircut_pct:
            pre = committed_p50 / (1.0 - haircut_pct / 100.0)
            line += (
                f" The committed P50 carries a {haircut_pct:g}% pre-construction "
                "over-prediction haircut that the cluster does not apply; before it the "
                f"committed basis is about {pre:,.1f} GWh, a difference of "
                f"{_pct_diff(base_gwh, pre):+.1f}%."
            )
        notes.append(line)
    if committed_p90 is not None:
        notes.append(
            f"The Monte Carlo P90 of {pct['p90']:,.1f} GWh differs from the committed P90 of "
            f"{committed_p90:,.1f} GWh by {_pct_diff(pct['p90'], committed_p90):+.1f}%. "
            f"The Monte Carlo spread comes from a {sigma_pct:g}% one-sigma on the Weibull A "
            "and k alone (monte_carlo.weibull_uncertainty_pct); the committed P90 comes from "
            "the IEC 61400-15-2 uncertainty budget in the frozen AEP summary. They are "
            "different uncertainty models, and the report basis stays the committed figure."
        )

    return AepResourceSensitivityBlock(
        base_net_aep_gwh=round(base_gwh, 1),
        tornado=rows,
        mc_p50_gwh=round(pct["p50"], 1),
        mc_p75_gwh=round(pct["p75"], 1),
        mc_p90_gwh=round(pct["p90"], 1),
        mc_p99_gwh=round(pct["p99"], 1),
        mc_mean_gwh=round(float(mc["mean"]), 1),
        mc_cv=round(float(mc["cv"]), 4),
        mc_n_samples=int(mc["n_samples"]),
        mc_seed=seed,
        weibull_uncertainty_pct=sigma_pct,
        committed_p50_gwh=None if committed_p50 is None else round(committed_p50, 1),
        committed_p90_gwh=None if committed_p90 is None else round(committed_p90, 1),
        reconciliation=notes,
    )
