"""Build / validate the AEP summary from a scenario config — closes the
curve-selection two-stage gap.

Previously, switching the power curve meant editing the config AND separately
re-running the AEP computation, with three identifiers free to drift:
the store slug (``power_curves.yaml`` key), the manifest ``source_id``
(``aep_loader.APPROVED_SOURCES``), and the display model.

This module:
- :func:`validate_curve_selection` — asserts the three identifiers agree
  (config ``curve_key`` == manifest ``curve_key`` for the chosen ``source_id``,
  and the slug exists in the store).
- :func:`build_aep_summary_from_config` / :func:`write_aep_summary` — regenerate
  a consistent AEP summary from the config in one call, so switching curves is
  one config edit + one run.

AEP basis: analytic Weibull integral on the selected curve with the IEC
61400-12-1 velocity-cube air-density correction (config ``air_density_site/ref``,
falling back to no correction) + the #23 multiplicative loss stack. For the
15 x IEA-10MW lender case this reproduces net 473.8 GWh / CF 0.339 (ERA5-fitted
Weibull A=8.199/k=2.665), matching the bankable engine; the legacy 23 x EN-171/6.5
base (402.6 / 0.307) still regenerates from its own config.

Context:
    Sprint 11 follow-up — power-curve sourcing wiring (#181 thread).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pandas as pd

from analytics.loader.aep_loader import (
    APPROVED_SOURCES,
    assert_source_in_manifest,
    build_provenance_aep_block,
)
from analytics.power_curves.oem_parser import (
    IEC_REFERENCE_AIR_DENSITY_KGM3,
    parse_power_curve,
)
from analytics.wind.aep_tornado import gross_aep_farm_gwh
from analytics.wind.losses_model import apply_losses, net_capacity_factor
from wind_resource.bankable_aep import (
    UncertaintyBudget,
    density_velocity_factor,
    exceedance_levels,
)


def validate_curve_selection(
    config: Mapping[str, Any],
    *,
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Assert the curve-selection identifiers agree; return the resolved selection.

    Checks ``resource.power_curve.{source_id, curve_key}``:
      - ``source_id`` is in the approved manifest,
      - ``curve_key`` matches the manifest entry's ``curve_key`` (when recorded),
      - ``curve_key`` exists in the power-curve store.

    Returns:
        ``{"source_id", "curve_key", "source_type"}``.

    Raises:
        ValueError: If an identifier is missing or they disagree.
        KeyError: If ``source_id`` is not in the manifest or ``curve_key`` is not
            in the store.
    """
    sources = manifest if manifest is not None else APPROVED_SOURCES
    resource = config.get("resource", {}) or {}
    power_curve = resource.get("power_curve", {}) or {}
    source_id = power_curve.get("source_id")
    curve_key = power_curve.get("curve_key")
    if not source_id:
        raise ValueError("Config is missing resource.power_curve.source_id.")
    if not curve_key:
        raise ValueError(
            "Config is missing resource.power_curve.curve_key (the power_curves.yaml store slug)."
        )

    assert_source_in_manifest(source_id, sources)
    manifest_curve_key = sources[source_id].get("curve_key")
    if manifest_curve_key is not None and manifest_curve_key != curve_key:
        raise ValueError(
            f"Curve identifier mismatch: config curve_key {curve_key!r} != "
            f"manifest[{source_id!r}].curve_key {manifest_curve_key!r}."
        )

    # Confirms the slug resolves in the store (raises KeyError otherwise).
    parse_power_curve(curve_key)

    source_type = power_curve.get("source_type") or sources[source_id].get(
        "type", "Unknown"
    )
    return {
        "source_id": str(source_id),
        "curve_key": str(curve_key),
        "source_type": str(source_type),
    }


def _uncertainty_from_config(
    resource: Mapping[str, Any],
) -> "tuple[UncertaintyBudget, float, float, int]":
    """Build the IEC 61400-15-2 uncertainty budget + knobs from ``resource.uncertainty``.

    All fields are optional; category sigmas default to the UncertaintyBudget defaults,
    and the two knobs (p50_haircut_pct, correlation) default to 0 -> the IEC RSS baseline
    with no haircut, so scenarios without an `uncertainty` block are unchanged.
    """
    unc: Dict[str, Any] = dict(resource.get("uncertainty", {}) or {})
    d = UncertaintyBudget()
    budget = UncertaintyBudget(
        wind_measurement_pct=float(
            unc.get("wind_measurement_pct", d.wind_measurement_pct)
        ),
        long_term_pct=float(unc.get("long_term_pct", d.long_term_pct)),
        vertical_extrapolation_pct=float(
            unc.get("vertical_extrapolation_pct", d.vertical_extrapolation_pct)
        ),
        horizontal_flow_pct=float(
            unc.get("horizontal_flow_pct", d.horizontal_flow_pct)
        ),
        power_curve_pct=float(unc.get("power_curve_pct", d.power_curve_pct)),
        wake_model_pct=float(unc.get("wake_model_pct", d.wake_model_pct)),
        interannual_variability_pct=float(
            unc.get("interannual_variability_pct", d.interannual_variability_pct)
        ),
    )
    haircut_pct = float(unc.get("p50_haircut_pct", 0.0))
    correlation = float(unc.get("correlation", 0.0))
    life_years = int(unc.get("life_years", 20))
    return budget, haircut_pct, correlation, life_years


def _resolve_wake_loss(
    resource: Mapping[str, Any],
    curve: "pd.DataFrame",
    *,
    weibull_a: float,
    weibull_k: float,
    hub_height_m: float,
) -> "tuple[float, str]":
    """Resolve the wake loss % and disclose its SOURCE (WIND-2, #478).

    Returns ``(wake_loss_pct, wake_source)``. By default the headline uses the documented
    FROZEN ``resource.losses.wake_loss_pct`` — which for the canonical lender case IS the
    granular PyWake Bastankhah result computed offline with the real 15-turbine layout and the
    SW-dominant wind rose, then frozen (the dependency-light frozen-export pattern; py_wake, like
    pvlib, is in zero CI lanes). A scenario can instead drive the wake LIVE by setting
    ``resource.wake.model_live: true`` AND supplying the complete, faithful inputs
    (``coordinates.x_m``/``y_m`` and ``wind_rose_freq``); the curve must carry a thrust (Ct)
    column. The live path FAILS LOUD on any missing input rather than silently degrading to a
    uniform-rose computation that would be LESS faithful than the frozen value — and
    ``model_wake_loss`` itself raises a clear error when py_wake is not installed (CASPER).
    """
    losses = resource.get("losses", {}) or {}
    wake_cfg = resource.get("wake", {}) or {}
    live = (
        bool(wake_cfg.get("model_live", False))
        if isinstance(wake_cfg, Mapping)
        else False
    )

    if not live:
        frozen = losses.get("wake_loss_pct")
        if frozen is None:
            raise ValueError(
                "resource.losses.wake_loss_pct is required when resource.wake.model_live is "
                "false (the frozen wake path); supply it or enable model_live with a full "
                "layout + wind rose."
            )
        return float(frozen), "frozen_config_pct"

    coords = wake_cfg.get("coordinates") or {}
    rose = wake_cfg.get("wind_rose_freq")
    x_m, y_m = coords.get("x_m"), coords.get("y_m")
    if x_m is None or y_m is None or rose is None:
        raise ValueError(
            "resource.wake.model_live is true but the live-wake inputs are incomplete: need "
            "coordinates.x_m, coordinates.y_m AND wind_rose_freq. Without the wind rose the "
            "wake defaults to a uniform direction distribution, which is LESS faithful than the "
            "frozen offline PyWake value — so this fails loud rather than degrading the headline."
        )
    if "thrust_coefficient" not in curve.columns:
        raise ValueError(
            "live wake (resource.wake.model_live) needs a power curve carrying a "
            "thrust_coefficient (Ct) column; the selected curve has none."
        )
    rotor_d = wake_cfg.get("rotor_diameter_m") or (
        resource.get("turbines", {}) or {}
    ).get("rotor_diameter_m")
    if rotor_d is None:
        raise ValueError(
            "live wake needs rotor_diameter_m (resource.wake or resource.turbines)."
        )

    # Local import: py_wake is optional and must not be imported at module load (CASPER).
    from wind_resource.bankable_aep import model_wake_loss

    res = model_wake_loss(
        wind_speed_ms=[float(v) for v in curve["wind_speed_ms"].tolist()],
        power_kw=[float(v) for v in curve["power_kw"].tolist()],
        thrust_coefficient=[float(v) for v in curve["thrust_coefficient"].tolist()],
        rotor_diameter_m=float(rotor_d),
        hub_height_m=float(hub_height_m),
        layout_x_m=[float(v) for v in x_m],
        layout_y_m=[float(v) for v in y_m],
        weibull_a=float(weibull_a),
        weibull_k=float(weibull_k),
        wind_rose_freq=[float(v) for v in rose],
        deficit_model=str(wake_cfg.get("deficit_model", "bastankhah")),
    )
    return float(res.wake_loss_pct), f"pywake_live:{res.deficit_model}"


def build_aep_summary_from_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Regenerate a consistent AEP summary from a scenario config.

    Validates the curve selection, then computes gross/net AEP on the selected
    curve (analytic Weibull integral at the IEC reference density) + the loss
    stack. The returned dict matches the AEP-summary schema (incl. the standardized
    ``provenance.aep`` block and ``power_curve_key``), consistent by construction.

    Raises:
        ValueError/KeyError: If the curve selection is invalid (see
            :func:`validate_curve_selection`).
    """
    selection = validate_curve_selection(config)
    resource = config["resource"]
    power_curve_cfg = resource["power_curve"]
    wind = config.get("wind_resource", {}) or {}
    turbines = resource.get("turbines", {}) or {}
    losses = dict(resource.get("losses", {}) or {})

    weibull_a = float(wind["weibull_a"])
    weibull_k = float(wind["weibull_k"])
    n_turbines = int(turbines["count"])
    rated_power_kw = float(turbines["rated_power_mw"]) * 1000.0
    capacity_mw = rated_power_kw / 1000.0
    # ARCH-01: hub height is config-required (consistent with count/rated above) —
    # no silent 150.0 that would mask a wrong/absent turbine hub height.
    hub_height_m = float(turbines["hub_height_m"])

    # Parse the reference (uncorrected) curve, then apply the IEC 61400-12-1
    # velocity-cube air-density correction so the regen reproduces the canonical
    # bankable basis. Dividing the curve's wind-speed axis by the velocity factor
    # is equivalent to the bankable engine's density shift (thinner air -> higher
    # speed needed per power level). Falls back to no correction when the density
    # fields are absent, preserving pre-10MW scenarios.
    curve = parse_power_curve(
        selection["curve_key"], air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    rho_site = power_curve_cfg.get(
        "air_density_site_kgm3", wind.get("air_density_kgm3")
    )
    rho_ref = power_curve_cfg.get(
        "air_density_ref_kgm3", wind.get("air_density_ref_kgm3")
    )
    density_factor = (
        density_velocity_factor(float(rho_site), float(rho_ref))
        if rho_site is not None and rho_ref is not None
        else 1.0
    )
    gross_gwh = gross_aep_farm_gwh(
        weibull_a,
        weibull_k,
        curve["wind_speed_ms"].to_numpy() / density_factor,
        curve["power_kw"].to_numpy(),
        n_turbines,
    )
    # WIND-2 (#478): resolve the wake loss and DISCLOSE its source. Default = the documented
    # frozen config % (the offline granular PyWake value); opt-in live PyWake when a scenario
    # supplies a full layout + wind rose (fail-loud otherwise). Committed lender -> frozen ->
    # byte-identical headline.
    wake_loss_pct, wake_source = _resolve_wake_loss(
        resource,
        curve,
        weibull_a=weibull_a,
        weibull_k=weibull_k,
        hub_height_m=hub_height_m,
    )
    losses["wake_loss_pct"] = wake_loss_pct
    loss_result = apply_losses(gross_gwh, losses)
    modelled_p50_gwh = loss_result.net_aep_gwh  # net P50 before any bankability haircut

    # IEC 61400-15-2 exceedance build-up, with two optional config-driven knobs
    # (resource.uncertainty): a P50 over-prediction haircut and an inter-category
    # correlation for the systematic-sigma combination. Both default to 0 -> the
    # bankable P50 == modelled net AEP and the RSS baseline is preserved.
    budget, haircut_pct, correlation, life_years = _uncertainty_from_config(resource)
    exceedance = exceedance_levels(
        modelled_p50_gwh,
        budget,
        life_years=life_years,
        p50_haircut_pct=haircut_pct,
        correlation=correlation,
    )
    net_gwh = exceedance.p50_gwh  # bankable P50 (haircut applied; == modelled if 0)
    cf = net_capacity_factor(net_gwh, n_turbines * capacity_mw)

    losses["total_loss_pct"] = round(loss_result.total_loss_pct, 2)
    provenance = build_provenance_aep_block(
        selection["source_id"], derived_from=power_curve_cfg.get("derived_from")
    )

    return {
        "capacity_factor": round(cf, 4),
        "net_site_aep_gwh": round(net_gwh, 2),
        "gross_aep_gwh": round(gross_gwh, 2),
        "n_turbines": n_turbines,
        "rated_power_kw": rated_power_kw,
        "hub_height_m": hub_height_m,
        "source_id": selection["source_id"],
        "source_type": selection["source_type"],
        "power_curve_key": selection["curve_key"],
        "iec_standard": power_curve_cfg.get("iec_standard", "IEC 61400-12-1:2022"),
        "losses": losses,
        # WIND-2 (#478): which path produced the wake loss in `losses.wake_loss_pct` —
        # "frozen_config_pct" (the documented offline PyWake value) or "pywake_live:<model>".
        "wake_source": wake_source,
        "exceedance": {
            "net_aep_p50_gwh": round(exceedance.p50_gwh, 1),
            "net_aep_p75_gwh": round(exceedance.p75_gwh, 1),
            "net_aep_p90_1yr_gwh": round(exceedance.p90_1yr_gwh, 1),
            "net_aep_p90_life_gwh": round(exceedance.p90_life_gwh, 1),
            "sigma_1yr_pct": round(exceedance.sigma_1yr_pct, 2),
            "sigma_life_pct": round(exceedance.sigma_life_pct, 2),
        },
        "uncertainty": {
            "p50_haircut_pct": haircut_pct,
            "correlation": correlation,
            "life_years": life_years,
            "modelled_p50_gwh": round(modelled_p50_gwh, 2),
        },
        "provenance": {"aep": provenance},
        "generated_by": "analytics.wind.aep_summary_builder",
    }


def write_aep_summary(config: Mapping[str, Any], output_path: str) -> Path:
    """Regenerate the AEP summary from ``config`` and write it as JSON."""
    summary = build_aep_summary_from_config(config)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    return out


__all__ = [
    "validate_curve_selection",
    "build_aep_summary_from_config",
    "write_aep_summary",
]
