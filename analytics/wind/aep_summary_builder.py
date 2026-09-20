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
import logging
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
from analytics.wind.siting_metadata import resolve_siting_metadata
from analytics.wind.wind_rose import build_wind_rose
from wind_resource.bankable_aep import (
    DEFAULT_TURBULENCE_INTENSITY,
    RECOMMENDED_P50_HAIRCUT_PCT,
    UncertaintyBudget,
    budget_from_mapping,
    density_velocity_factor,
    exceedance_levels,
)

logger = logging.getLogger(__name__)


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


def _validated_number(
    raw: Any,
    *,
    key: str,
    low: float,
    high: float,
    high_inclusive: bool = True,
    hint: str,
) -> float:
    """Return ``raw`` as a float inside its declared band, or fail loud (#1275).

    Mirrors :func:`_resolve_wake_ti`: a KPI-moving config knob is either a real number in
    range or a config error. ``bool`` is rejected explicitly because it is an ``int``
    subclass, so ``correlation: true`` would otherwise read as ``1.0``.

    Raises:
        ValueError: If ``raw`` is not a number, or lies outside the band.
    """
    band = f"[{low}, {high}]" if high_inclusive else f"[{low}, {high})"
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(
            f"resource.uncertainty.{key} must be a number in {band} (got {raw!r}); {hint}."
        )
    value = float(raw)
    in_band = low <= value <= high if high_inclusive else low <= value < high
    if not in_band:
        raise ValueError(
            f"resource.uncertainty.{key} must be in {band} (got {value!r}); {hint}."
        )
    return value


def _validated_life_years(raw: Any) -> int:
    """Return the project life in whole years, or fail loud (#1275).

    ``life_years`` divides the interannual sigma as ``sigma/sqrt(life_years)``, so a zero
    or negative value silently became 1.0 inside
    :meth:`~wind_resource.bankable_aep.UncertaintyBudget.combined_sigma_pct` and moved the
    project-life P90 without a word.

    Raises:
        ValueError: If ``raw`` is not a positive whole number of years.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(
            "resource.uncertainty.life_years must be a positive whole number of years "
            f"(got {raw!r}); it divides the interannual sigma as sigma/sqrt(life_years)."
        )
    if raw < 1:
        raise ValueError(
            "resource.uncertainty.life_years must be >= 1 "
            f"(got {raw}); it divides the interannual sigma as sigma/sqrt(life_years)."
        )
    return int(raw)


def _resolve_density_factor(rho_site: Any, rho_ref: Any) -> float:
    """Resolve the IEC 61400-12-1 velocity-cube density factor, fail-loud on a half pair (#1275).

    Three cases, and only the first two are legitimate:

    - **Both declared** — the correction applies (the canonical lender basis).
    - **Neither declared** — no correction, preserving the documented pre-10MW scenarios.
      Logged, so a regeneration never quietly runs uncorrected.
    - **Exactly one declared** — a config error. Previously this fell through to the
      no-correction branch silently: dropping ``air_density_ref_kgm3`` from the lender
      scenario while keeping the site value moved net P50 464.4 -> 484.5 GWh (+4.33%) with
      no error and no log line.

    Raises:
        ValueError: If exactly one of the two densities is declared.
    """
    if rho_site is not None and rho_ref is not None:
        return density_velocity_factor(float(rho_site), float(rho_ref))
    if rho_site is None and rho_ref is None:
        logger.info(
            "AEP summary: no air-density pair declared (resource.power_curve."
            "air_density_site_kgm3/air_density_ref_kgm3); the IEC 61400-12-1 velocity-cube "
            "correction is NOT applied. Declare both to correct the curve to site density."
        )
        return 1.0
    declared, missing = (
        ("air_density_site_kgm3", "air_density_ref_kgm3")
        if rho_site is not None
        else ("air_density_ref_kgm3", "air_density_site_kgm3")
    )
    raise ValueError(
        f"resource.power_curve.{declared} is declared but {missing} is not. The IEC "
        "61400-12-1 density correction needs BOTH, and silently skipping it moves the "
        "headline AEP by several percent — declare the pair, or neither."
    )


def _uncertainty_from_config(
    resource: Mapping[str, Any],
) -> "tuple[UncertaintyBudget, float, float, int]":
    """Build the IEC 61400-15-2 uncertainty budget + knobs from ``resource.uncertainty``.

    All fields are optional; category sigmas default to the UncertaintyBudget defaults.
    ``correlation`` defaults to 0 (the IEC RSS baseline). ``p50_haircut_pct`` defaults to the
    recommended pre-construction over-prediction haircut
    :data:`~wind_resource.bankable_aep.RECOMMENDED_P50_HAIRCUT_PCT` (WES 2026; #587) when a
    scenario is SILENT on it — so a no-EYA scenario is corrected for the well-documented P50
    optimism rather than assuming a naive 0%. A scenario that has its own EYA sets an explicit
    value (the DutchBay lender case: 2.0%, EN220-corroborated), which overrides the default. This
    is a policy default at config-consumption; the ``exceedance_levels`` kernel stays 0.0-identity.

    CESSPIT-strict on the three policy knobs (#1275): each is range-validated here and fails
    loud, because each MOVES a lender-facing exceedance number and none of them was checked
    before — ``budget_from_mapping`` gates the sigma key NAMES, never the policy knobs' VALUES.
    Validating at this layer (rather than in the kernels) also keeps the summary's reported
    ``uncertainty`` block equal to what the maths actually used: ``correlation`` was previously
    echoed into provenance RAW while :meth:`UncertaintyBudget.systematic_sigma_pct` silently
    clamped it, so a summary could record an input that was never applied.
    """
    unc: Dict[str, Any] = dict(resource.get("uncertainty", {}) or {})
    # Sigma parsing is shared with the timeseries diagnostic path (#618):
    # budget_from_mapping is policy-free (sigmas only), so the two consumers cannot
    # drift on key names/defaults. The haircut POLICY below stays at this layer.
    budget = budget_from_mapping(unc)
    if "p50_haircut_pct" in unc:
        haircut_pct = _validated_number(
            unc["p50_haircut_pct"],
            key="p50_haircut_pct",
            low=0.0,
            high=100.0,
            high_inclusive=False,
            hint=(
                "a pre-construction P50 over-prediction haircut is a REDUCTION in percent "
                "(e.g. 2.0); a negative value would inflate the bankable P50"
            ),
        )
    else:
        # Silent-default observability (CESSPIT): a scenario that omits the knob gets the
        # recommended no-EYA default — surface it so a regeneration is never quietly haircut.
        haircut_pct = float(RECOMMENDED_P50_HAIRCUT_PCT)
        logger.info(
            "AEP summary: resource.uncertainty.p50_haircut_pct not set; applying the recommended "
            "%.1f%% pre-construction P50 over-prediction default (WES 2026). Set it explicitly to override.",
            haircut_pct,
        )
    correlation = (
        _validated_number(
            unc["correlation"],
            key="correlation",
            low=0.0,
            high=1.0,
            hint=(
                "a uniform inter-category correlation rho is a fraction in [0, 1] "
                "(0 = the IEC RSS baseline, 1 = fully correlated)"
            ),
        )
        if "correlation" in unc
        else 0.0
    )
    life_years = _validated_life_years(unc["life_years"]) if "life_years" in unc else 20
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

    Live-PyWake activation (#853.3), config-driven and DEFAULT-OFF: instead of a hand-typed
    ``wind_rose_freq`` the live path can consume the DERIVED directional rose — the per-sector
    frequencies binned by the canonical :func:`analytics.wind.wind_rose.build_wind_rose` from a
    real met-convention direction series (e.g. the #853.1 production ``wd_100m``). This is gated
    on an EXPLICIT opt-in ``resource.wake.use_derived_rose: true`` that DEFAULTS FALSE — when it is
    unset/false the resolution is byte-identical to today (an explicit ``wind_rose_freq`` is still
    required and consumed unchanged). Enabling it MOVES the headline wake loss (real sectoral
    frequencies vs the frozen offline value) and is therefore separately oracle-gated. When ON, the
    derived rose is required (from ``resource.wake.direction_deg`` or, failing that,
    ``resource.wind_rose.direction_deg``); a missing/degenerate series FAILS LOUD rather than
    silently falling back to an omnidirectional rose (which would be LESS faithful than frozen).
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
    x_m, y_m = coords.get("x_m"), coords.get("y_m")
    # Directional rose resolution. DEFAULT-OFF (#853.3): the rose is an explicit
    # ``wind_rose_freq`` UNLESS the scenario opts into deriving it from a real direction
    # series via ``use_derived_rose: true``. An unset/false flag keeps today's exact
    # behaviour (explicit freq consumed unchanged) — byte-identical.
    rose, rose_source = _resolve_live_wind_rose_freq(wake_cfg, resource)
    if x_m is None or y_m is None or rose is None:
        raise ValueError(
            "resource.wake.model_live is true but the live-wake inputs are incomplete: need "
            "coordinates.x_m, coordinates.y_m AND wind_rose_freq (or use_derived_rose with a "
            "direction series). Without the wind rose the wake defaults to a uniform direction "
            "distribution, which is LESS faithful than the frozen offline PyWake value — so this "
            "fails loud rather than degrading the headline."
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

    # Coastal-TI parametrization (#832), config-driven and DEFAULT-OFF: when a scenario
    # does not declare `resource.wake.turbulence_intensity` the live path uses the engine's
    # kernel default (0.10), i.e. today's exact k* and wake loss. A scenario MAY set a
    # coastal-appropriate (lower-roughness, lower-TI) value; CESSPIT-strict — a supplied TI
    # must be a fraction in (0, 1] or it fails loud (no silent clamp that would move the KPI).
    ti = _resolve_wake_ti(wake_cfg)

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
        turbulence_intensity=ti,
        deficit_model=str(wake_cfg.get("deficit_model", "bastankhah")),
    )
    # Disclose BOTH the deficit model and where the directional rose came from
    # (explicit config freq vs a rose DERIVED from a real direction series, #853.3),
    # so a lender report can never confuse a live-derived wake with the frozen headline.
    return float(res.wake_loss_pct), f"pywake_live:{res.deficit_model}:{rose_source}"


def _resolve_live_wind_rose_freq(
    wake_cfg: Mapping[str, Any],
    resource: Mapping[str, Any],
) -> "tuple[Optional[list[float]], str]":
    """Resolve the directional ``wind_rose_freq`` for the live wake (#853.3), DEFAULT-OFF.

    Returns ``(freq_or_None, rose_source)``.

    Two mutually-exclusive modes, gated on the explicit opt-in
    ``resource.wake.use_derived_rose`` which DEFAULTS FALSE:

    - **OFF (default)** — the rose is the explicit ``resource.wake.wind_rose_freq``
      (a list of per-sector frequencies), consumed EXACTLY as before. When the flag is
      unset/false the behaviour is byte-identical to the pre-#853.3 path: an absent
      ``wind_rose_freq`` returns ``None`` so the caller fails loud on incomplete inputs;
      supplying ``use_derived_rose: false`` alongside a ``wind_rose_freq`` is a no-op.
      ``rose_source`` is ``"config_freq"``.

    - **ON (opt-in)** — the rose is DERIVED from a real met-convention direction series by
      the canonical :func:`analytics.wind.wind_rose.build_wind_rose`: the per-sector
      ``frequency`` vector binned from ``resource.wake.direction_deg`` (preferred) or, if
      absent, ``resource.wind_rose.direction_deg`` (the #853.1 production ``wd_100m`` path).
      Sector count follows ``resource.wake.wind_rose_sectors`` (default 12, matching
      ``build_wind_rose``). This MOVES the headline wake loss and so is separately
      oracle-gated. ``rose_source`` is ``"derived:<n_sectors>sec"``.

    CESSPIT-strict when the flag is ON:
      - ``use_derived_rose`` and an explicit ``wind_rose_freq`` are mutually exclusive
        (supplying both is a contradiction — fail loud, never silently pick one);
      - a missing/empty direction series fails loud (``build_wind_rose`` also raises on an
        all-NaN series) rather than degrading to an omnidirectional rose, which would be
        LESS faithful than the frozen offline value.
    """
    use_derived = bool(wake_cfg.get("use_derived_rose", False))

    if not use_derived:
        # DEFAULT-OFF: explicit config frequency, consumed unchanged (byte-identical).
        freq = wake_cfg.get("wind_rose_freq")
        if freq is None:
            return None, "config_freq"
        return [float(v) for v in freq], "config_freq"

    # --- opt-in: derive the rose from a real direction series (#853.3) ---
    if wake_cfg.get("wind_rose_freq") is not None:
        raise ValueError(
            "resource.wake.use_derived_rose is true but an explicit wind_rose_freq is also "
            "supplied; these are mutually exclusive. Remove one — either derive the rose from a "
            "direction series (use_derived_rose) or pin the sector frequencies (wind_rose_freq)."
        )

    directions = wake_cfg.get("direction_deg")
    if directions is None:
        wind_rose_cfg = resource.get("wind_rose", {}) or {}
        if isinstance(wind_rose_cfg, Mapping):
            directions = wind_rose_cfg.get("direction_deg")
    if directions is None:
        raise ValueError(
            "resource.wake.use_derived_rose is true but no direction series was found: supply "
            "resource.wake.direction_deg (or resource.wind_rose.direction_deg) — a met-convention "
            "wind-direction series to bin into the live-PyWake directional rose. Deriving from a "
            "real series is the point of the opt-in; failing loud avoids silently falling back to "
            "an omnidirectional rose that would be LESS faithful than the frozen value."
        )

    n_sectors = int(wake_cfg.get("wind_rose_sectors", 12))
    rose = build_wind_rose(
        [float(v) for v in directions],
        n_sectors=n_sectors,
    )
    return [float(f) for f in rose["frequency"]], f"derived:{rose['n_sectors']}sec"


def _resolve_wake_ti(wake_cfg: Mapping[str, Any]) -> float:
    """Resolve the ambient turbulence intensity for the live wake (#832), CESSPIT-strict.

    An unset ``turbulence_intensity`` returns the engine kernel default (DEFAULT-OFF:
    the current 0.10 onshore closure, so behaviour is unchanged). A declared value must
    be a real number in the open-closed interval (0, 1]; anything else fails loud rather
    than being silently coerced — a bad TI would otherwise move the modelled wake loss.
    """
    raw = wake_cfg.get("turbulence_intensity")
    if raw is None:
        return DEFAULT_TURBULENCE_INTENSITY
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(
            "resource.wake.turbulence_intensity must be a number in (0, 1] "
            f"(got {raw!r})."
        )
    ti = float(raw)
    if not (0.0 < ti <= 1.0):
        raise ValueError(
            "resource.wake.turbulence_intensity must be a fraction in (0, 1] "
            f"(got {ti!r}); e.g. 0.08 for a low-roughness coastal site."
        )
    return ti


def _resolve_wind_rose(resource: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Build the optional directional wind-rose OUTPUT block (#742) — display only.

    Reads ``resource.wind_rose`` when present:
      - ``direction_deg``: a series of met-convention wind directions (e.g. an ERA5
        ``wd_100m`` column) to bin, OR
      - ``sector_deg`` + ``frequency``: a pre-binned rose to pass through (validated
        and re-normalised, so a frozen offline rose can be surfaced without the raw
        series).
      - ``n_sectors`` (optional, default 12): sector count when binning a series.

    Returns ``None`` when no ``resource.wind_rose`` is declared (the summary omits the
    block). This is a PURE OUTPUT for the provenance/diagnostics section: it never
    scales the AEP and feeds no billed quantity. Fails loud (CESSPIT) if a wind_rose is
    declared but carries neither a direction series nor a pre-binned sector/frequency
    pair.
    """
    rose_cfg = resource.get("wind_rose", {}) or {}
    if not isinstance(rose_cfg, Mapping) or not rose_cfg:
        return None

    directions = rose_cfg.get("direction_deg")
    if directions is not None:
        n_sectors = int(rose_cfg.get("n_sectors", 12))
        return build_wind_rose([float(v) for v in directions], n_sectors=n_sectors)

    sector_deg = rose_cfg.get("sector_deg")
    frequency = rose_cfg.get("frequency")
    if sector_deg is not None and frequency is not None:
        sectors = [float(v) for v in sector_deg]
        freqs = [float(v) for v in frequency]
        if len(sectors) != len(freqs):
            raise ValueError(
                "resource.wind_rose.sector_deg and frequency must be the same length "
                f"(got {len(sectors)} and {len(freqs)})."
            )
        total = sum(freqs)
        if total <= 0.0:
            raise ValueError(
                "resource.wind_rose.frequency must sum to a positive value."
            )
        return {
            "n_sectors": len(sectors),
            "sector_width_deg": round(360.0 / len(sectors), 4) if sectors else 0.0,
            "sector_deg": [round(s, 4) for s in sectors],
            "frequency": [round(f / total, 6) for f in freqs],
            "source": "config_prebinned",
            "provenance_note": (
                "Pre-binned directional frequency supplied in config (resource.wind_rose); "
                "display/provenance only, applies NO AEP correction."
            ),
        }

    raise ValueError(
        "resource.wind_rose is declared but incomplete: supply either direction_deg "
        "(a direction series to bin) or both sector_deg and frequency (a pre-binned rose)."
    )


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
    # speed needed per power level). Falls back to no correction when BOTH density
    # fields are absent, preserving pre-10MW scenarios; a half-declared pair is a
    # config error rather than a silent skip (#1275, see _resolve_density_factor).
    curve = parse_power_curve(
        selection["curve_key"], air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    rho_site = power_curve_cfg.get(
        "air_density_site_kgm3", wind.get("air_density_kgm3")
    )
    rho_ref = power_curve_cfg.get(
        "air_density_ref_kgm3", wind.get("air_density_ref_kgm3")
    )
    density_factor = _resolve_density_factor(rho_site, rho_ref)
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

    # IEC 61400-15-2 exceedance build-up, with two config-driven knobs
    # (resource.uncertainty): a P50 over-prediction haircut and an inter-category
    # correlation for the systematic-sigma combination. `correlation` defaults to 0 (RSS
    # baseline preserved); `p50_haircut_pct` defaults to RECOMMENDED_P50_HAIRCUT_PCT (5.0)
    # at this config layer for a silent scenario (#587) — the kernel default stays 0.0.
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

    # #742: optional display/diagnostic-only blocks. NEITHER touches any billed
    # quantity — they surface into provenance/diagnostics only and apply NO AEP
    # correction. A directional wind rose (single-cell ERA5, coarse) and a
    # self-declared terrain class; both default to UNSET (omitted) when absent.
    provenance_extras: Dict[str, Any] = {"aep": provenance}
    wind_rose = _resolve_wind_rose(resource)
    if wind_rose is not None:
        provenance_extras["wind_rose"] = wind_rose
    siting_metadata = resolve_siting_metadata(resource)
    if siting_metadata is not None:
        provenance_extras["siting"] = siting_metadata

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
        "provenance": provenance_extras,
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
