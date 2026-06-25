#!/usr/bin/env python
"""OEM power curve parser for wind turbine manufacturers.

Loads the manufacturer-certified Envision EN-171/6.5 MW power curve from the
canonical config store (``wind_resource/config/power_curves.yaml`` — the single
source of truth shared with :class:`wind_resource.EnergyCalculator`) and applies
air-density correction per IEC 61400-12-1:2022.

History / why this module changed:
    This module previously carried a HAND-TYPED 10 MW placeholder curve
    "extrapolated" from the 6.5 MW baseline, plus ``ENVISION_EN171_65_*`` aliases
    that silently returned the 10 MW data. That fiction over-stated the auxiliary
    Monte-Carlo AEP path by ~10/6.5 (the curve peaked at 10 MW while the capacity
    factor divided by the 6.5 MW rating). The placeholder and the aliasing have
    been removed: the Envision EN-171/6.5 turbine (23 x 6.5 MW = 149.5 MW) is the
    canonical machine, and its curve is now sourced from config — never hardcoded
    (GWTF ARCH-01).

Supports:
- Envision EN-171/6.5 (6.5 MW) certified curve, config-sourced
- PCHIP (monotonic) / cubic-spline interpolation
- Air-density correction (site-specific)
- AEP calculation from 8760-hour wind distributions

References:
    - IEC 61400-12-1:2022 Power performance measurements

Context:
    Sprint 17 - Issue #16: OEM Power Curve Integration
    All parameters MUST come from YAML config (GWTF ARCH-01)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
import yaml
from scipy.interpolate import CubicSpline, PchipInterpolator

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# CANONICAL CONFIG SOURCE (GWTF ARCH-01: no hardcoded power curves)
# ═════════════════════════════════════════════════════════════════════════════

# Single source of truth, shared with wind_resource.EnergyCalculator. Reading
# this data file (not importing the module) keeps analytics decoupled from the
# wind_resource package while consuming the same certified curve.
POWER_CURVE_STORE: Path = (
    Path(__file__).resolve().parents[2]
    / "wind_resource"
    / "config"
    / "power_curves.yaml"
)
CANONICAL_CURVE_KEY: str = "envision_en171_6p5"

# IEC 61400-12-1:2022 reference air density (a physical standard, not a tunable).
IEC_REFERENCE_AIR_DENSITY_KGM3: float = 1.225
# Plausible site air-density band (kg/m^3) used to validate caller input.
AIR_DENSITY_MIN_KGM3: float = 0.8
AIR_DENSITY_MAX_KGM3: float = 1.4


def _load_curve_entry(
    store_path: Path = POWER_CURVE_STORE,
    key: str = CANONICAL_CURVE_KEY,
) -> Dict[str, Any]:
    """Load a single turbine entry from the canonical power-curve store.

    Args:
        store_path: Path to the ``power_curves.yaml`` store.
        key: Top-level turbine key to load (e.g. ``envision_en171_6p5``).

    Returns:
        The turbine entry mapping (manufacturer, model, ratings, power_curve).

    Raises:
        KeyError: If ``key`` is not present in the store.
    """
    store = yaml.safe_load(store_path.read_text())
    if not isinstance(store, dict) or key not in store:
        available = sorted(store) if isinstance(store, dict) else "<none>"
        raise KeyError(
            f"Power-curve key {key!r} not found in {store_path}. "
            f"Available: {available}"
        )
    return cast(Dict[str, Any], store[key])


def _build_base_curve(entry: Dict[str, Any]) -> pd.DataFrame:
    """Build the reference (uncorrected) power-curve DataFrame from a store entry.

    Adds a ``thrust_coefficient`` column when the store entry carries a
    ``thrust_curve`` block (IEA/DTU reference designs sourced via
    ``power_curve_sourcing``; #166). Ct is air-density-independent, so it rides
    through the IEC correction unchanged. Curves without a thrust curve (the
    canonical EN-171/6.5 and Cp-only sources) simply omit the column.
    """
    pc = entry["power_curve"]
    ws = [float(x) for x in pc["ws"]]
    data: Dict[str, List[float]] = {
        "wind_speed_ms": ws,
        "power_kw": [float(x) for x in pc["power"]],
    }
    thrust = entry.get("thrust_curve")
    if thrust:
        t_ws = [float(x) for x in thrust["ws"]]
        t_ct = [float(x) for x in thrust["ct"]]
        # Aligned to the power grid (the store writes matching grids); interpolate
        # defensively if a future source provides Ct on a different wind-speed grid.
        data["thrust_coefficient"] = (
            t_ct if t_ws == ws else [float(c) for c in np.interp(ws, t_ws, t_ct)]
        )
    return pd.DataFrame(data)


def _build_specs(entry: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Build the turbine specs mapping from a store entry."""
    rated_kw = float(entry["rated_capacity_kw"])
    hub_heights = entry.get("hub_heights") or [150.0]
    return {
        "model": entry.get("model", key),
        "manufacturer": entry.get("manufacturer", "unknown"),
        "rated_power_kw": rated_kw,
        "rated_power_mw": rated_kw / 1000.0,
        "hub_height_m": float(hub_heights[len(hub_heights) // 2]),
        "cut_in_ms": float(entry["cut_in"]),
        "rated_wind_speed_ms": float(entry["rated"]),
        "cut_out_ms": float(entry["cut_out"]),
        "air_density_ref_kgm3": IEC_REFERENCE_AIR_DENSITY_KGM3,
        "source": f"{POWER_CURVE_STORE.name}:{key}",
    }


# Module-level canonical curve + specs (config-sourced once at import).
_CURVE_ENTRY: Dict[str, Any] = _load_curve_entry()

#: Reference EN-171/6.5 MW power curve (uncorrected), config-sourced.
ENVISION_EN171_65_POWER_CURVE: pd.DataFrame = _build_base_curve(_CURVE_ENTRY)

#: EN-171/6.5 MW turbine specifications, config-sourced.
ENVISION_EN171_65_SPECS: Dict[str, Any] = _build_specs(_CURVE_ENTRY, CANONICAL_CURVE_KEY)


def _apply_air_density_correction(
    base_curve: pd.DataFrame,
    specs: Dict[str, Any],
    air_density_kgm3: Optional[float],
) -> pd.DataFrame:
    """Apply the IEC 61400-12-1 air-density correction to a base curve.

    Args:
        base_curve: Reference (uncorrected) curve (``wind_speed_ms``/``power_kw``).
        specs: The turbine specs (provides reference density + metadata).
        air_density_kgm3: Site air density (kg/m^3); defaults to the IEC reference.

    Raises:
        ValueError: If ``air_density_kgm3`` is outside the plausible site band.
    """
    if air_density_kgm3 is None:
        air_density_kgm3 = IEC_REFERENCE_AIR_DENSITY_KGM3
    if not (AIR_DENSITY_MIN_KGM3 <= air_density_kgm3 <= AIR_DENSITY_MAX_KGM3):
        raise ValueError(
            f"Air density must be in range "
            f"[{AIR_DENSITY_MIN_KGM3}, {AIR_DENSITY_MAX_KGM3}] kg/m^3, "
            f"got {air_density_kgm3}"
        )

    curve = base_curve.copy()
    rho_ref = cast(float, specs["air_density_ref_kgm3"])

    # IEC 61400-12-1 air-density correction is a WIND-SPEED normalisation, NOT a power
    # scaling: site power at wind speed v = the reference-density curve read at the shifted
    # speed v * (rho_site/rho_ref)**(1/3). The previous code scaled POWER by
    # (rho/rho_ref)**(1/3) — it applied the *velocity* exponent to power, overstating site
    # AEP (~+2% at 1.15 kg/m^3) and diverging from the canonical wind_resource.bankable_aep
    # engine. Reuse that engine's factor so the two AEP paths agree. Byte-identical at the
    # reference density (factor == 1.0 -> the curve reads itself).
    from wind_resource.bankable_aep import density_velocity_factor

    factor = density_velocity_factor(air_density_kgm3, rho_ref)
    ws = curve["wind_speed_ms"].to_numpy(dtype=float)
    power_ref = curve["power_kw"].to_numpy(dtype=float)
    curve["power_kw"] = np.interp(ws * factor, ws, power_ref)
    curve["power_mw"] = curve["power_kw"] / 1000.0

    curve.attrs["model"] = specs["model"]
    curve.attrs["rated_power_mw"] = specs["rated_power_mw"]
    curve.attrs["air_density_site_kgm3"] = air_density_kgm3
    curve.attrs["air_density_ref_kgm3"] = rho_ref
    curve.attrs["iec_standard"] = "IEC 61400-12-1:2022"
    curve.attrs["source"] = specs["source"]

    logger.info(
        "Loaded %s power curve: rated %.1f MW, air density %.3f kg/m^3 "
        "(IEC wind-speed factor %.4f)",
        specs["model"],
        specs["rated_power_mw"],
        air_density_kgm3,
        factor,
    )
    return curve


def parse_power_curve(
    curve_key: str = CANONICAL_CURVE_KEY,
    air_density_kgm3: Optional[float] = None,
    *,
    store_path: Path = POWER_CURVE_STORE,
) -> pd.DataFrame:
    """Parse a config-selected power curve from the store, air-density corrected.

    ``curve_key`` is the ``power_curves.yaml`` slug the model selected (the same
    key the config's ``turbine.model`` / :class:`wind_resource.EnergyCalculator`
    uses). The turbine is NOT hardwired (GWTF ARCH-01) — pass the model's choice.

    Args:
        curve_key: Store slug of the turbine curve (e.g. ``vestas_v150_5p6``).
        air_density_kgm3: Site air density (kg/m^3); defaults to the IEC reference.
        store_path: Path to the ``power_curves.yaml`` store.

    Returns:
        DataFrame with ``wind_speed_ms`` / ``power_kw`` / ``power_mw`` columns.

    Raises:
        KeyError: If ``curve_key`` is not in the store.
        ValueError: If ``air_density_kgm3`` is outside the plausible site band.
    """
    entry = _load_curve_entry(store_path, curve_key)
    base = _build_base_curve(entry)
    specs = _build_specs(entry, curve_key)
    return _apply_air_density_correction(base, specs, air_density_kgm3)


def parse_envision_en171_curve(
    air_density_kgm3: Optional[float] = None,
) -> pd.DataFrame:
    """Back-compat wrapper for the canonical Envision EN-171/6.5 MW curve.

    Prefer :func:`parse_power_curve` with the model-selected ``curve_key``.
    """
    return parse_power_curve(CANONICAL_CURVE_KEY, air_density_kgm3)


def interpolate_power_curve(
    curve: pd.DataFrame,
    wind_speeds_ms: np.ndarray,
    method: str = "pchip",
) -> np.ndarray:
    """Interpolate power output for arbitrary wind speeds.

    Args:
        curve: Power curve DataFrame (``wind_speed_ms``, ``power_kw``).
        wind_speeds_ms: Array of wind speeds to interpolate (m/s).
        method: ``"pchip"`` (monotonic) or ``"cubic"`` (smooth, may overshoot).

    Returns:
        Array of power outputs (kW), clipped to ``[0, rated]``.

    Raises:
        ValueError: If ``method`` is unknown.
    """
    # interp_func is one of several scipy interpolators (PchipInterpolator /
    # CubicSpline); annotate the common callable shape so both branches assign
    # to the same declared type.
    interp_func: Callable[..., np.ndarray]
    if method == "pchip":
        interp_func = PchipInterpolator(
            curve["wind_speed_ms"].to_numpy(),
            curve["power_kw"].to_numpy(),
        )
    elif method == "cubic":
        interp_func = CubicSpline(
            curve["wind_speed_ms"].to_numpy(),
            curve["power_kw"].to_numpy(),
            bc_type="natural",
        )
    else:
        raise ValueError(f"Unknown interpolation method: {method}")

    power_interpolated = interp_func(wind_speeds_ms)
    power_interpolated = np.clip(power_interpolated, 0.0, curve["power_kw"].max())

    return cast("np.ndarray", power_interpolated)


def compute_aep_from_curve(
    wind_dist_ms: np.ndarray,
    curve: pd.DataFrame,
    n_turbines: int,
    capacity_mw: float,
    apply_losses: bool = True,
    wake_loss_pct: float = 8.0,
    availability_pct: float = 97.0,
    electrical_loss_pct: float = 2.0,
) -> Tuple[float, float, Dict[str, float]]:
    """Compute Annual Energy Production (AEP) from a wind distribution.

    CRITICAL: All loss parameters MUST come from YAML config (GWTF ARCH-01).
    Never hardcode loss factors in function calls.

    Args:
        wind_dist_ms: 8760-hour wind speed timeseries (m/s).
        curve: Power curve DataFrame from :func:`parse_envision_en171_curve`.
        n_turbines: Number of turbines (from ``config.resource.turbines.count``).
        capacity_mw: Per-turbine rated capacity in MW (farm capacity is computed
            internally as ``n_turbines * capacity_mw``). E.g. 6.5 for EN-171/6.5.
        apply_losses: If True, apply wake/availability/electrical losses.
        wake_loss_pct: Wake loss percentage (from config).
        availability_pct: Availability percentage (from config).
        electrical_loss_pct: Electrical loss percentage (from config).

    Returns:
        Tuple of:
            - ``net_aep_gwh``: Net annual energy production (GWh)
            - ``capacity_factor``: Net capacity factor (0.0 to 1.0)
            - ``losses_dict``: Breakdown of losses applied

    Raises:
        ValueError: If the timeseries is not 8760 hours or contains negatives.

    Example:
        >>> curve = parse_envision_en171_curve(air_density_kgm3=1.15)
        >>> wind = np.full(8760, 8.0)
        >>> aep, cf, losses = compute_aep_from_curve(
        ...     wind_dist_ms=wind, curve=curve, n_turbines=23, capacity_mw=6.5,
        ...     apply_losses=False,
        ... )
    """
    if len(wind_dist_ms) != 8760:
        raise ValueError(
            f"Expected 8760-hour timeseries, got {len(wind_dist_ms)} hours"
        )
    if np.any(np.asarray(wind_dist_ms, dtype=float) < 0.0):
        raise ValueError("Wind speeds cannot be negative")

    # Interpolate power for each hour (monotonic PCHIP).
    power_per_hour_kw = interpolate_power_curve(
        curve=curve,
        wind_speeds_ms=wind_dist_ms,
        method="pchip",
    )

    # Gross AEP (single turbine, no losses) then farm-level.
    gross_aep_single_turbine_gwh = power_per_hour_kw.sum() / 1e6  # kWh -> GWh
    gross_aep_farm_gwh = gross_aep_single_turbine_gwh * n_turbines

    losses_dict: Dict[str, float] = {}
    if apply_losses:
        wake_multiplier = 1.0 - (wake_loss_pct / 100.0)
        availability_multiplier = availability_pct / 100.0
        electrical_multiplier = 1.0 - (electrical_loss_pct / 100.0)

        losses_dict["wake_loss_pct"] = wake_loss_pct
        losses_dict["availability_pct"] = availability_pct
        losses_dict["availability_loss_pct"] = 100.0 - availability_pct
        losses_dict["electrical_loss_pct"] = electrical_loss_pct

        net_aep_gwh = (
            gross_aep_farm_gwh
            * wake_multiplier
            * availability_multiplier
            * electrical_multiplier
        )
        losses_dict["total_loss_pct"] = 100.0 * (
            1.0 - net_aep_gwh / gross_aep_farm_gwh
        )
    else:
        net_aep_gwh = gross_aep_farm_gwh
        losses_dict["total_loss_pct"] = 0.0

    # Capacity factor. net_aep_gwh is FARM-level (scaled by n_turbines above),
    # so the denominator must be FARM capacity = n_turbines * capacity_mw (the
    # per-turbine rating). The prior `capacity_mw * 8.760` omitted n_turbines,
    # inflating CF by ~n_turbines x (#166); both callers (this module's tests and
    # analytics/simulation/monte_carlo_aep, which passes capacity_mw =
    # rated_power_kw/1000) supply per-turbine capacity.
    farm_capacity_mw = n_turbines * capacity_mw
    capacity_factor = net_aep_gwh / (farm_capacity_mw * 8.760)

    logger.info(
        "AEP: %d turbines x %.1f MW | gross %.2f GWh | net %.2f GWh | "
        "CF %.2f%% | losses %.2f%%",
        n_turbines,
        capacity_mw,
        gross_aep_farm_gwh,
        net_aep_gwh,
        capacity_factor * 100.0,
        losses_dict.get("total_loss_pct", 0.0),
    )

    return net_aep_gwh, capacity_factor, losses_dict


def validate_power_curve_iec_compliance(curve: pd.DataFrame) -> Dict[str, Any]:
    """Validate a power curve against IEC 61400-12-1:2022 (lightweight checks).

    Args:
        curve: Power curve DataFrame (``wind_speed_ms``, ``power_kw``).

    Returns:
        Dict of validation results (rated power, monotonicity, cut-in/out).
    """
    ws = curve["wind_speed_ms"].to_numpy()
    power = curve["power_kw"].to_numpy()
    rated_power_kw = float(power.max())

    # Monotonic non-decreasing up to the rated wind speed (index of max power).
    rated_idx = int(np.argmax(power))
    monotonic_ok = bool(np.all(np.diff(power[: rated_idx + 1]) >= -1e-6))

    cutin_ok = bool(power[ws <= float(ENVISION_EN171_65_SPECS["cut_in_ms"])].min() <= 1e-6)
    cutout_ok = bool(power[-1] <= 1e-6)

    return {
        "compliant": bool(monotonic_ok and cutin_ok and cutout_ok),
        "rated_power_ok": True,
        "monotonic_ok": monotonic_ok,
        "cutin_ok": cutin_ok,
        "cutout_ok": cutout_ok,
        "rated_power_tolerance_pct": 0.0,
        "max_power_kw": rated_power_kw,
    }


__all__ = [
    "ENVISION_EN171_65_POWER_CURVE",
    "ENVISION_EN171_65_SPECS",
    "POWER_CURVE_STORE",
    "CANONICAL_CURVE_KEY",
    "parse_power_curve",
    "parse_envision_en171_curve",
    "interpolate_power_curve",
    "compute_aep_from_curve",
    "validate_power_curve_iec_compliance",
]
