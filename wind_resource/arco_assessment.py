"""ARCO single-point ERA5 -> fitted Weibull -> VALIDATE the declared lender baseline.

Wires the ARCO single-point retrieval (:mod:`wind_resource.era5_retrieval`) into the
canonical analytic AEP chain. The pieces (one scenario file drives both):

1. :func:`era5_config_from_scenario` maps the scenario's ``resource.era5`` + ``turbine``
   blocks into an :class:`wind_resource.era5_retrieval.ERA5RequestConfig` — with NO
   masking defaults for site/turbine identity, and a hard cross-assertion that
   ``resource.era5.hub_height_m == turbine.hub_height_m`` so the ERA5 extrapolation
   height can never silently diverge from the finance hub height.
2. :func:`build_arco_assessment` takes a hub-height wind-speed *series*, fits a Weibull,
   and computes the **implied** AEP by running the analytic engine
   (:func:`analytics.wind.aep_summary_builder.build_aep_summary_from_config`) on the
   *fitted* ``(A, k)`` — then reports the drift of the fit vs the scenario's declared
   ``wind_resource.weibull_a/k``. It does NOT overwrite the declared baseline (VALIDATE
   mode): the auditable 483.6 GWh headline stays the analytic engine on the declared
   Weibull. Adopting a fitted ``(A, k)`` is a deliberate, dated config edit.
3. :func:`assess` is the live end-to-end orchestrator (retrieve -> hub series -> coverage
   guard -> assessment). The CDS/xarray imports stay call-time guarded (CASPER), so this
   module imports cleanly without the ``[wind]`` extra and CI can exercise (2) on
   synthetic data with no live CDS calls.
"""

from __future__ import annotations

import copy
import datetime as _dt
import logging
from typing import Any, Dict, Mapping

import pandas as pd

from wind_resource.era5_retrieval import ERA5RequestConfig
from wind_resource.weibull_fit import (WeibullFit, fit_weibull_on_series,
                                       weibull_drift)

logger = logging.getLogger(__name__)

# Physical ERA5-product constants (the dataset ships 10 m and 100 m winds); these are
# NOT site identity, so they carry standard defaults rather than being required config.
_ERA5_REF_HEIGHT_LOW_M = 10.0
_ERA5_REF_HEIGHT_HIGH_M = 100.0
_DEFAULT_DRIFT_TOLERANCE_PCT = 5.0


def _require(d: Mapping[str, Any], *keys: str) -> Any:
    """Fetch a nested key, raising a precise KeyError instead of defaulting silently."""
    cur: Any = d
    trail = []
    for k in keys:
        trail.append(k)
        if not isinstance(cur, Mapping) or k not in cur:
            raise KeyError(
                "Missing required config key '" + ".".join(trail) + "' for the ARCO "
                "ERA5 assessment (no silent default — fix the scenario)."
            )
        cur = cur[k]
    return cur


def _resolve_reference_window(era5: Mapping[str, Any]) -> tuple[int, int, str]:
    """Resolve ``(start_year, end_year, mode)`` from ``resource.era5.reference``.

    ``mode: fixed`` requires explicit ``start_year``/``end_year`` (reproducible, the
    default for lender runs). ``mode: latest`` resolves ``end_year = today - end_year_lag``
    and ``start_year = end_year - n_years + 1`` (rolling — exploratory only).
    """
    ref = _require(era5, "reference")
    mode = str(_require(ref, "mode"))
    if mode == "fixed":
        return int(_require(ref, "start_year")), int(_require(ref, "end_year")), "fixed"
    if mode == "latest":
        n_years = int(ref.get("n_years", 20))
        lag = int(ref.get("end_year_lag", 2))
        end_year = _dt.date.today().year - lag
        return end_year - n_years + 1, end_year, "latest"
    raise ValueError(f"resource.era5.reference.mode must be 'fixed' or 'latest', got {mode!r}.")


def era5_config_from_scenario(scenario: Mapping[str, Any]) -> ERA5RequestConfig:
    """Build an :class:`ERA5RequestConfig` from a v14 scenario (single source of truth).

    Site identity (lat/lon/hub-height) and turbine identity (curve slug, count) are
    REQUIRED — there are no masking defaults. ``resource.era5.hub_height_m`` is
    cross-asserted against ``turbine.hub_height_m``.

    Raises:
        KeyError: if any required ``resource.era5`` / ``turbine`` field is absent.
        ValueError: if the two hub heights disagree, or the reference mode is invalid.
    """
    resource = _require(scenario, "resource")
    era5 = _require(resource, "era5")
    turbine = _require(scenario, "turbine")
    power_curve = _require(resource, "power_curve")

    hub_era5 = float(_require(era5, "hub_height_m"))
    hub_turbine = float(_require(turbine, "hub_height_m"))
    if abs(hub_era5 - hub_turbine) > 1e-6:
        raise ValueError(
            f"resource.era5.hub_height_m ({hub_era5}) != turbine.hub_height_m "
            f"({hub_turbine}); the ERA5 extrapolation height must match the finance "
            "hub height (single source of truth)."
        )

    start_year, end_year, mode = _resolve_reference_window(era5)

    return ERA5RequestConfig(
        project_name=str(era5.get("project_name", scenario.get("name", "site"))),
        latitude=float(_require(era5, "latitude")),
        longitude=float(_require(era5, "longitude")),
        start_year=start_year,
        end_year=end_year,
        hub_height_m=hub_era5,
        reference_height_low_m=float(era5.get("reference_height_low_m", _ERA5_REF_HEIGHT_LOW_M)),
        reference_height_high_m=float(era5.get("reference_height_high_m", _ERA5_REF_HEIGHT_HIGH_M)),
        alpha_min=float(era5.get("alpha_min", 0.05)),
        alpha_max=float(era5.get("alpha_max", 0.40)),
        output_dir=str(era5.get("output_dir", "outputs/era5_cache")),
        turbine_model=str(_require(power_curve, "curve_key")),
        num_turbines=int(_require(turbine, "n_turbines")),
        reference_mode=mode,
        resolved_at=_dt.datetime.now().isoformat(timespec="seconds"),
        strict_coverage=bool(_require(era5, "strict_coverage")),
    )


def _implied_aep(scenario: Mapping[str, Any], fit: WeibullFit) -> Dict[str, Any]:
    """Run the canonical analytic engine on the FITTED Weibull (a cross-check).

    Substitutes ``(A_fit, k_fit)`` into a copy of the scenario and regenerates the AEP
    summary, so the caller sees what the lender headline WOULD be on ARCO-fitted data —
    without mutating the real scenario.
    """
    from analytics.wind.aep_summary_builder import \
        build_aep_summary_from_config

    probe = copy.deepcopy(dict(scenario))
    probe.setdefault("wind_resource", {})
    probe["wind_resource"] = dict(probe.get("wind_resource", {}))
    probe["wind_resource"]["weibull_a"] = fit.weibull_a
    probe["wind_resource"]["weibull_k"] = fit.weibull_k
    summary = build_aep_summary_from_config(probe)
    return {
        "net_aep_gwh": summary["net_site_aep_gwh"],
        "gross_aep_gwh": summary["gross_aep_gwh"],
        "capacity_factor": summary["capacity_factor"],
    }


def build_arco_assessment(
    series: pd.DataFrame,
    scenario: Mapping[str, Any],
    ws_column: str,
    *,
    drift_tolerance_pct: float | None = None,
    vintage: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Fit a Weibull on an ARCO hub-height series and VALIDATE the declared baseline.

    Returns a structured assessment: the fit, the implied analytic AEP on that fit, the
    drift vs the scenario's declared ``wind_resource.weibull_a/k``, and an
    ``implied_wind_block`` (the ``resource.wind`` contract the fit WOULD produce if
    adopted). Nothing is mutated; ``mode`` is always ``"validate"``.

    Raises:
        KeyError: if the declared Weibull / source identity is absent from the scenario.
    """
    wind_resource = _require(scenario, "wind_resource")
    a_declared = float(_require(wind_resource, "weibull_a"))
    k_declared = float(_require(wind_resource, "weibull_k"))
    wind_block = _require(_require(scenario, "resource"), "wind")
    tol = (
        float(drift_tolerance_pct)
        if drift_tolerance_pct is not None
        else float(
            _require(scenario, "resource").get("era5", {}).get("weibull_fit", {}).get(
                "drift_tolerance_pct", _DEFAULT_DRIFT_TOLERANCE_PCT
            )
        )
    )

    fit = fit_weibull_on_series(series, ws_column)
    drift = weibull_drift(fit.weibull_a, fit.weibull_k, a_declared, k_declared, tol)
    implied = _implied_aep(scenario, fit)

    implied_wind_block = {
        "ws150_mean_ms": round(fit.mean_ws_ms, 4),
        "ws150_std_ms": round(fit.std_ws_ms, 4),
        "weibull_a": round(fit.weibull_a, 4),
        "weibull_k": round(fit.weibull_k, 4),
        "capacity_factor": implied["capacity_factor"],
        "aep_gwh": implied["net_aep_gwh"],
        "source_id": _require(wind_block, "source_id"),
        "source_type": _require(wind_block, "source_type"),
    }

    if not drift.within_tolerance:
        logger.warning(
            "ARCO Weibull drift exceeds %.1f%%: A %+.2f%% / k %+.2f%% vs declared "
            "(A=%.2f,k=%.2f). Declared baseline UNCHANGED (VALIDATE mode); adopt only "
            "via a deliberate dated re-baseline.",
            tol,
            drift.a_drift_pct,
            drift.k_drift_pct,
            a_declared,
            k_declared,
        )

    return {
        "mode": "validate",
        "weibull_fit": fit.as_dict(),
        "drift": drift.as_dict(),
        "implied_aep": implied,
        "implied_wind_block": implied_wind_block,
        "declared_wind_block": dict(wind_block),
        "vintage": dict(vintage) if vintage is not None else None,
    }


def assess(scenario: Mapping[str, Any]) -> Dict[str, Any]:
    """Live end-to-end: retrieve ARCO ERA5 -> hub series -> coverage guard -> assessment.

    The CDS/xarray imports are call-time guarded inside :mod:`wind_resource.era5_retrieval`
    (CASPER), so importing this module never requires the ``[wind]`` extra. CI exercises
    :func:`build_arco_assessment` on synthetic series instead of calling this.
    """
    from wind_resource.era5_retrieval import (build_hub_height_series,
                                              retrieve_era5_timeseries,
                                              validate_coverage)

    cfg = era5_config_from_scenario(scenario)
    nc_path = retrieve_era5_timeseries(cfg)
    series = build_hub_height_series(nc_path, cfg)
    coverage = validate_coverage(series, cfg)
    vintage = {
        "reference_mode": cfg.reference_mode,
        "start_year": cfg.start_year,
        "end_year": cfg.end_year,
        "resolved_at": cfg.resolved_at,
        "latitude": cfg.latitude,
        "longitude": cfg.longitude,
        "expected_hours": cfg.expected_hours,
        "actual_hours": coverage["actual_hours"],
        "coverage_complete": coverage["coverage_complete"],
    }
    result = build_arco_assessment(
        series, scenario, ws_column=f"ws_{int(cfg.hub_height_m)}m", vintage=vintage
    )
    result["coverage"] = coverage
    return result


__all__ = ["era5_config_from_scenario", "build_arco_assessment", "assess"]
