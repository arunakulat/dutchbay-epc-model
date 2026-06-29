"""pvlib-based solar AEP producer (optional ``[solar]`` extra).

Turns a fixed-tilt PV-system spec + a measured site irradiance level into a bankable
annual energy / capacity factor, mirroring how ``wind_resource.bankable_aep`` turns a
turbine + Weibull resource into a wind AEP. ``pvlib`` is an OPTIONAL dependency, imported
lazily behind :func:`_require_pvlib` (CASPER fail-loud guard) — exactly like ``py-wake``
in the wind producer — so the core finance stack never depends on it.

Design (GWTF / CESSPIT / CCCDIR):

* **Config-first** — every input is a typed :class:`SolarResourceConfig` field; nothing is
  hardcoded. :meth:`SolarResourceConfig.from_scenario` reads a ``resource.solar`` block.
* **Reproducible, no network / no TMY files** — a clear-sky year (pvlib Ineichen) is
  scaled to the site's **measured annual GHI** (``annual_ghi_kwh_m2`` — the single
  resource knob, a measurable site property), then Erbs/DISC decomposition →
  Hay-Davies/isotropic transposition → PVWatts DC → PVWatts inverter clip → flat system
  losses. Same config → same number (a fixed reference calendar year, no ``Date.now``).
* **VALIDATE, never overwrite** — :func:`validate_declared_solar_cf` compares the producer
  to the config-declared P50 CF and flags drift (mirrors ``wind_resource.arco_assessment``
  VALIDATE mode); it does not mutate the scenario. The declared P50 stays the default; the
  producer is the optional, physics-grounded cross-check the user opted into.

Capacity-factor convention: CF is reported against the **DC nameplate** (``MWp``), i.e.
``annual_ac_energy / (dc_capacity_mw · 8760)`` — the same basis the
``generation.technologies.solar.capacity_factor`` block uses for a ``capacity_mw`` given in
MWp.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Mapping

logger = logging.getLogger(__name__)

#: Reference (non-leap) calendar year for the clear-sky shape. A fixed constant keeps the
#: producer reproducible (``Date.now`` is unavailable / would break regression pins); it is
#: only a calendar template — the energy is set by ``annual_ghi_kwh_m2``, not by the year.
_REFERENCE_YEAR = 2021
_HOURS_PER_YEAR = 8760.0


def _require_pvlib() -> Any:
    """Import pvlib or raise a clear, actionable error (CASPER optional-dep guard)."""
    try:
        import pvlib  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised when the extra is absent
        raise RuntimeError(
            "The solar AEP producer requires pvlib (the [solar] extra). "
            "Install with: pip install -e '.[solar]'  (or: pip install pvlib)."
        ) from exc
    return pvlib


@dataclass(frozen=True)
class SolarResourceConfig:
    """Typed, config-first inputs for the PV producer.

    Resource:
        latitude, longitude: site coordinates (degrees; +N, +E).
        annual_ghi_kwh_m2: measured annual global horizontal irradiance (kWh/m²/yr) — the
            site resource knob (Puttalam ~2000). The clear-sky year is scaled to this total.
        timezone: IANA tz (e.g. ``"Asia/Colombo"``); altitude_m: site elevation.
    System (fixed-tilt PVWatts):
        dc_capacity_mw: DC nameplate (MWp). tilt_deg / azimuth_deg: array geometry
            (azimuth 180 = equator-facing in the N hemisphere). dc_ac_ratio: DC/AC (ILR).
        gamma_pdc_per_c: PVWatts power temp-coefficient (1/°C, negative).
        system_loss_pct: flat soiling/wiring/mismatch/availability derate (% of AC).
        ambient_temp_c, wind_speed_ms: Faiman cell-temperature drivers (annual means).
        inverter_eff_nom: PVWatts nominal inverter efficiency.
    """

    latitude: float
    longitude: float
    annual_ghi_kwh_m2: float
    dc_capacity_mw: float
    timezone: str = "UTC"
    altitude_m: float = 0.0
    tilt_deg: float = 10.0
    azimuth_deg: float = 180.0
    dc_ac_ratio: float = 1.2
    gamma_pdc_per_c: float = -0.0035
    system_loss_pct: float = 14.0
    ambient_temp_c: float = 25.0
    wind_speed_ms: float = 2.0
    inverter_eff_nom: float = 0.96
    reference_year: int = _REFERENCE_YEAR

    def __post_init__(self) -> None:
        if self.dc_capacity_mw <= 0:
            raise ValueError(f"dc_capacity_mw must be > 0; got {self.dc_capacity_mw}")
        if self.annual_ghi_kwh_m2 <= 0:
            raise ValueError(
                f"annual_ghi_kwh_m2 must be > 0; got {self.annual_ghi_kwh_m2}"
            )
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude out of range: {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude out of range: {self.longitude}")
        if self.dc_ac_ratio <= 0:
            raise ValueError(f"dc_ac_ratio must be > 0; got {self.dc_ac_ratio}")
        if not 0.0 <= self.system_loss_pct < 100.0:
            raise ValueError(
                f"system_loss_pct must be in [0, 100); got {self.system_loss_pct}"
            )
        if not 0.0 < self.inverter_eff_nom <= 1.0:
            raise ValueError(
                f"inverter_eff_nom must be in (0, 1]; got {self.inverter_eff_nom}"
            )
        if not 0.0 <= self.azimuth_deg <= 360.0:
            raise ValueError(f"azimuth_deg must be in [0, 360]; got {self.azimuth_deg}")
        if not 0.0 <= self.tilt_deg <= 90.0:
            raise ValueError(f"tilt_deg must be in [0, 90]; got {self.tilt_deg}")

    @classmethod
    def from_scenario(cls, scenario: Mapping[str, Any]) -> "SolarResourceConfig":
        """Build from a scenario's ``resource.solar`` block (CCCDIR: explicit keys).

        Raises:
            KeyError: if ``resource.solar`` is absent or missing a required field.
        """
        resource = scenario.get("resource")
        block = resource.get("solar") if isinstance(resource, Mapping) else None
        if not isinstance(block, Mapping):
            raise KeyError(
                "Scenario has no resource.solar block for the PV producer "
                "(needs latitude, longitude, annual_ghi_kwh_m2, dc_capacity_mw)."
            )
        required = ("latitude", "longitude", "annual_ghi_kwh_m2", "dc_capacity_mw")
        missing = [k for k in required if block.get(k) is None]
        if missing:
            raise KeyError(f"resource.solar is missing required field(s): {missing}")

        known = cls.__dataclass_fields__  # noqa: SLF001 - dataclass introspection
        # CESSPIT: reject unknown keys rather than silently dropping them, so a typo'd
        # field (e.g. system_los_pct) fails loud instead of reverting to a default.
        unknown = [k for k in block if k not in known]
        if unknown:
            raise KeyError(
                f"resource.solar has unknown field(s): {sorted(unknown)}; "
                f"valid keys: {sorted(known)}"
            )
        return cls(**block)


@dataclass(frozen=True)
class SolarAEPResult:
    """The producer's output for a PV system."""

    annual_energy_gwh: float
    capacity_factor: float  # against the DC nameplate (MWp)
    specific_yield_kwh_per_kwp: float
    poa_kwh_m2: float  # plane-of-array insolation over the year
    ghi_kwh_m2: float  # the (scaled) site GHI used
    clearsky_scale: float  # clear-sky index applied to hit annual_ghi_kwh_m2


@dataclass(frozen=True)
class SolarCfValidation:
    """VALIDATE outcome: producer CF vs a config-declared P50 CF."""

    declared_cf: float
    modelled_cf: float
    relative_diff: float  # |modelled - declared| / declared
    tolerance: float  # fractional
    within_tolerance: bool
    result: SolarAEPResult = field(repr=False)


def compute_solar_aep(config: SolarResourceConfig) -> SolarAEPResult:
    """Produce the bankable annual energy / capacity factor for a PV system.

    Pipeline (all pvlib): clear-sky GHI (Ineichen) for a reference year → scale to the
    measured ``annual_ghi_kwh_m2`` → DISC decomposition to DNI → closure DHI → Hay-Davies
    plane-of-array transposition → Faiman cell temperature → PVWatts DC → PVWatts inverter
    (clipped at the AC nameplate) → flat system-loss derate → annual AC energy.

    Raises:
        RuntimeError: if pvlib (the [solar] extra) is not installed.
    """
    pvlib = _require_pvlib()
    import numpy as np
    import pandas as pd

    loc = pvlib.location.Location(
        config.latitude,
        config.longitude,
        tz=config.timezone,
        altitude=config.altitude_m,
    )
    times = pd.date_range(
        f"{config.reference_year}-01-01 00:00",
        f"{config.reference_year}-12-31 23:00",
        freq="1h",
        tz=config.timezone,
    )

    clearsky = loc.get_clearsky(times, model="ineichen")
    clearsky_ghi_annual_kwh = float(clearsky["ghi"].sum()) / 1000.0
    # Defensive guard: pvlib clear-sky is always positive for a valid site.
    if clearsky_ghi_annual_kwh <= 0:  # pragma: no cover
        raise RuntimeError("Clear-sky GHI computed as non-positive — check site/timezone.")
    # Scale the clear-sky shape so its annual GHI equals the measured site total (the
    # clear-sky index). A sunny tropical site lands near ~0.8.
    scale = config.annual_ghi_kwh_m2 / clearsky_ghi_annual_kwh
    ghi = clearsky["ghi"] * scale

    solpos = loc.get_solarposition(times)
    dni = pvlib.irradiance.disc(ghi, solpos["zenith"], times)["dni"]
    cos_zen = np.cos(np.radians(solpos["zenith"]))
    dhi = (ghi - dni * cos_zen).clip(lower=0.0)

    dni_extra = pvlib.irradiance.get_extra_radiation(times)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=config.tilt_deg,
        surface_azimuth=config.azimuth_deg,
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        dni_extra=dni_extra,
        model="haydavies",  # anisotropic (lender-preferred over the isotropic default)
    )["poa_global"].clip(lower=0.0)

    cell_temp = pvlib.temperature.faiman(
        poa, temp_air=config.ambient_temp_c, wind_speed=config.wind_speed_ms
    )
    pdc0_w = config.dc_capacity_mw * 1.0e6
    dc_power = pvlib.pvsystem.pvwatts_dc(
        poa, cell_temp, pdc0_w, config.gamma_pdc_per_c
    )
    ac_nameplate_w = pdc0_w / config.dc_ac_ratio
    ac_power = pvlib.inverter.pvwatts(
        dc_power,
        pdc0=ac_nameplate_w / config.inverter_eff_nom,
        eta_inv_nom=config.inverter_eff_nom,
    ).clip(upper=ac_nameplate_w)

    loss_factor = 1.0 - config.system_loss_pct / 100.0
    annual_ac_wh = float(ac_power.sum()) * loss_factor
    annual_energy_gwh = annual_ac_wh / 1.0e9
    capacity_factor = annual_ac_wh / (pdc0_w * _HOURS_PER_YEAR)
    # kWh/kWp = (Wh / 1000) / (MWp * 1000) = Wh / (MWp * 1e6)
    specific_yield = annual_ac_wh / (config.dc_capacity_mw * 1.0e6)
    poa_annual_kwh = float(poa.sum()) / 1000.0

    # Defensive guard: valid PV inputs always yield a finite positive CF.
    if not math.isfinite(capacity_factor) or capacity_factor <= 0:  # pragma: no cover
        raise RuntimeError(
            f"Solar AEP produced a non-positive/NaN capacity factor ({capacity_factor}); "
            "check the resource.solar inputs."
        )

    logger.info(
        "Solar AEP: %.1f GWh, CF %.3f, yield %.0f kWh/kWp (GHI %.0f kWh/m2, scale %.3f)",
        annual_energy_gwh,
        capacity_factor,
        specific_yield,
        config.annual_ghi_kwh_m2,
        scale,
    )
    return SolarAEPResult(
        annual_energy_gwh=annual_energy_gwh,
        capacity_factor=capacity_factor,
        specific_yield_kwh_per_kwp=specific_yield,
        poa_kwh_m2=poa_annual_kwh,
        ghi_kwh_m2=float(ghi.sum()) / 1000.0,
        clearsky_scale=scale,
    )


def validate_declared_solar_cf(
    config: SolarResourceConfig,
    declared_cf: float,
    *,
    tolerance_pct: float = 10.0,
) -> SolarCfValidation:
    """VALIDATE a config-declared P50 solar CF against the pvlib producer (no overwrite).

    Computes the producer CF and compares it to ``declared_cf``; drift beyond
    ``tolerance_pct`` is flagged (``within_tolerance=False``) and logged at WARNING — the
    declared P50 is never mutated (mirrors ``wind_resource.arco_assessment`` VALIDATE).

    Raises:
        ValueError: if ``declared_cf`` is non-positive.
        RuntimeError: if pvlib (the [solar] extra) is not installed.
    """
    if declared_cf <= 0:
        raise ValueError(f"declared_cf must be > 0; got {declared_cf}")
    result = compute_solar_aep(config)
    relative = abs(result.capacity_factor - declared_cf) / declared_cf
    tolerance = tolerance_pct / 100.0
    within = relative <= tolerance
    if not within:
        logger.warning(
            "Declared solar CF %.3f differs from the pvlib producer %.3f by %.1f%% "
            "(> %.1f%% tolerance) — review the resource.solar inputs or the declared P50.",
            declared_cf,
            result.capacity_factor,
            relative * 100.0,
            tolerance_pct,
        )
    return SolarCfValidation(
        declared_cf=declared_cf,
        modelled_cf=result.capacity_factor,
        relative_diff=relative,
        tolerance=tolerance,
        within_tolerance=within,
        result=result,
    )


__all__ = [
    "SolarResourceConfig",
    "SolarAEPResult",
    "SolarCfValidation",
    "compute_solar_aep",
    "validate_declared_solar_cf",
    "_require_pvlib",
]
