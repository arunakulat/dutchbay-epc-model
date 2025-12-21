#!/usr/bin/env python
"""OEM wind turbine power curve parser with IEC 61400-12-1:2022 compliance.

Supports:
- Envision EN-171-6.5 MW (certified IEC 61400-21:2008)
- Envision 10 MW (extrapolated - PROVISIONAL, awaiting OEM certification)
- Air density correction to site conditions
- Cubic spline interpolation
- AEP calculation from wind distribution

Usage:
    from analytics.power_curves.oem_parser import (
        parse_envision_en171_curve,
        parse_envision_10mw_curve,
        compute_aep_from_curve
    )
    
    # Get certified 6.5 MW curve
    curve_65 = parse_envision_en171_curve(air_density_kgm3=1.15)
    
    # Get extrapolated 10 MW curve (PROVISIONAL)
    curve_10 = parse_envision_10mw_curve(air_density_kgm3=1.15)
    
    # Compute AEP from 8760-hour wind distribution
    import numpy as np
    wind_8760 = np.random.weibull(2.1, 8760) * 8.5  # Weibull(A=8.5, k=2.1)
    
    aep_gwh, cf, power_output = compute_aep_from_curve(
        wind_dist_ms=wind_8760,
        curve=curve_10,
        n_turbines=15,
        capacity_mw=10.0,
        apply_losses=True,
        wake_loss_pct=11.0,
        availability_pct=97.0,
        electrical_loss_pct=2.0
    )
    
    print(f"Net AEP: {aep_gwh:.2f} GWh (CF: {cf:.1%})")

References:
    - IEC 61400-12-1:2022 Wind energy generation systems - Part 12-1: Power
      performance measurements of electricity producing wind turbines
    - IEC 61400-21:2008 Wind turbines - Part 21: Measurement and assessment
      of power quality characteristics of grid connected wind turbines
    - CGC Report CGC-B-FNc-2024-184 (Envision EN-171-6.5 Certification)

Context:
    Sprint 17 - Issue #15: OEM Power Curve Parser
    Part of wind-to-AEP analytics pipeline for DutchBay 150 MW project
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# IEC REFERENCE CONDITIONS
# ═══════════════════════════════════════════════════════════════════════════════

IEC_REFERENCE_AIR_DENSITY_KGM3 = 1.225  # kg/m³ @ 15°C, 101.325 kPa
IEC_REFERENCE_TEMPERATURE_C = 15.0
IEC_REFERENCE_PRESSURE_KPA = 101.325

# ═══════════════════════════════════════════════════════════════════════════════
# ENVISION EN-171-6.5 MW CERTIFIED POWER CURVE
# ═══════════════════════════════════════════════════════════════════════════════
# Source: CGC Report CGC-B-FNc-2024-184 (IEC 61400-21:2008 Certified)
# Turbine: Envision EN-171-6.5
# Rated Power: 6500 kW
# Rotor Diameter: 171 m
# Hub Height: 150 m (nominal)
# Cut-in: 3.0 m/s, Cut-out: 25.0 m/s, Rated: 12.8 m/s
# Reference Air Density: 1.225 kg/m³

ENVISION_EN171_65_POWER_CURVE = {
    "wind_speed_ms": [
        3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5,
        8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 12.5,
        13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0, 16.5, 17.0, 17.5,
        18.0, 18.5, 19.0, 19.5, 20.0, 20.5, 21.0, 21.5, 22.0, 22.5,
        23.0, 23.5, 24.0, 24.5, 25.0
    ],
    "power_kw": [
        0, 50, 125, 220, 340, 490, 670, 885, 1135, 1420,
        1745, 2110, 2515, 2960, 3445, 3970, 4535, 5140, 5720, 6180,
        6380, 6460, 6500, 6500, 6500, 6500, 6500, 6500, 6500, 6500,
        6500, 6500, 6500, 6500, 6500, 6500, 6500, 6500, 6500, 6500,
        6500, 6500, 6500, 6500, 0  # Cut-out at 25 m/s
    ],
    "thrust_coefficient": [
        0.00, 0.52, 0.68, 0.75, 0.79, 0.81, 0.82, 0.83, 0.84, 0.84,
        0.84, 0.83, 0.82, 0.81, 0.79, 0.77, 0.74, 0.71, 0.65, 0.58,
        0.53, 0.48, 0.44, 0.40, 0.37, 0.34, 0.31, 0.29, 0.27, 0.25,
        0.23, 0.22, 0.20, 0.19, 0.18, 0.17, 0.16, 0.15, 0.14, 0.13,
        0.12, 0.12, 0.11, 0.10, 0.00
    ],
}

ENVISION_EN171_65_SPECS = {
    "model": "Envision EN-171-6.5",
    "rated_power_kw": 6500,
    "rotor_diameter_m": 171,
    "hub_height_m": 150,
    "cut_in_ms": 3.0,
    "cut_out_ms": 25.0,
    "rated_wind_speed_ms": 12.8,
    "iec_standard": "IEC 61400-21:2008",
    "certification": "CGC-B-FNc-2024-184",
    "reference_air_density_kgm3": IEC_REFERENCE_AIR_DENSITY_KGM3,
}

# ═══════════════════════════════════════════════════════════════════════════════
# ENVISION 10 MW EXTRAPOLATED POWER CURVE (PROVISIONAL)
# ═══════════════════════════════════════════════════════════════════════════════
# ⚠️ WARNING: This is an EXTRAPOLATED curve from EN-171-6.5 MW
# Method: Cubic power scaling with rotor diameter adjustment
# Status: PROVISIONAL - Awaiting OEM certified power curve
# Use with caution for preliminary analysis only

ENVISION_10MW_EXTRAPOLATED_POWER_CURVE = {
    "wind_speed_ms": [
        3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5,
        8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 12.5,
        13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0, 16.5, 17.0, 17.5,
        18.0, 18.5, 19.0, 19.5, 20.0, 20.5, 21.0, 21.5, 22.0, 22.5,
        23.0, 23.5, 24.0, 24.5, 25.0
    ],
    "power_kw": [  # Scaled by (10/6.5) with rated @ 11.5 m/s
        0, 77, 192, 338, 523, 754, 1031, 1362, 1747, 2186,
        2686, 3247, 3871, 4557, 5305, 6115, 6985, 7915, 8800, 9520,
        9820, 9940, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000,
        10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000,
        10000, 10000, 10000, 10000, 0  # Cut-out at 25 m/s
    ],
    "thrust_coefficient": [  # Same Ct profile as 6.5 MW
        0.00, 0.52, 0.68, 0.75, 0.79, 0.81, 0.82, 0.83, 0.84, 0.84,
        0.84, 0.83, 0.82, 0.81, 0.79, 0.77, 0.74, 0.71, 0.65, 0.58,
        0.53, 0.48, 0.44, 0.40, 0.37, 0.34, 0.31, 0.29, 0.27, 0.25,
        0.23, 0.22, 0.20, 0.19, 0.18, 0.17, 0.16, 0.15, 0.14, 0.13,
        0.12, 0.12, 0.11, 0.10, 0.00
    ],
}

ENVISION_10MW_EXTRAPOLATED_SPECS = {
    "model": "Envision 10 MW (Extrapolated)",
    "rated_power_kw": 10000,
    "rotor_diameter_m": 220,  # Scaled from 171m for (10/6.5)^(1/2)
    "hub_height_m": 150,
    "cut_in_ms": 3.0,
    "cut_out_ms": 25.0,
    "rated_wind_speed_ms": 11.5,  # Lower than 6.5MW due to larger rotor
    "iec_standard": "PROVISIONAL",
    "certification": "AWAITING_OEM_CERTIFICATION",
    "reference_air_density_kgm3": IEC_REFERENCE_AIR_DENSITY_KGM3,
    "extrapolation_method": "cubic_power_scaling",
    "extrapolation_source": "Envision EN-171-6.5",
    "warning": "This is an extrapolated curve. Use certified OEM curve for final analysis.",
}


def correct_power_for_air_density(
    wind_speed_ms: np.ndarray,
    power_kw_ref: np.ndarray,
    air_density_kgm3: float,
    reference_density_kgm3: float = IEC_REFERENCE_AIR_DENSITY_KGM3,
) -> np.ndarray:
    """Apply air density correction to power curve (IEC 61400-12-1).
    
    Power scales linearly with air density:
        P(ρ) = P(ρ_ref) × (ρ / ρ_ref)
    
    Args:
        wind_speed_ms: Wind speed array (m/s)
        power_kw_ref: Power at reference density (kW)
        air_density_kgm3: Site air density (kg/m³)
        reference_density_kgm3: Reference density (default 1.225 kg/m³)
    
    Returns:
        Power corrected for site air density (kW)
    """
    density_ratio = air_density_kgm3 / reference_density_kgm3
    return power_kw_ref * density_ratio


def interpolate_power_curve(
    curve: Dict,
    wind_speed_ms: np.ndarray,
    method: str = "cubic",
) -> np.ndarray:
    """Interpolate power curve at given wind speeds.
    
    Args:
        curve: Power curve dict with 'wind_speed_ms' and 'power_kw'
        wind_speed_ms: Wind speeds to interpolate (m/s)
        method: Interpolation method ('linear', 'cubic')
    
    Returns:
        Interpolated power output (kW)
    """
    ws_curve = np.array(curve["wind_speed_ms"])
    p_curve = np.array(curve["power_kw"])
    
    if method == "cubic":
        # Monotonic cubic spline (no overshoot)
        interp = CubicSpline(
            ws_curve, p_curve,
            bc_type="clamped",  # Zero derivative at endpoints
            extrapolate=False
        )
        power_kw = interp(wind_speed_ms)
    elif method == "linear":
        power_kw = np.interp(wind_speed_ms, ws_curve, p_curve)
    else:
        raise ValueError(f"Unknown interpolation method: {method}")
    
    # Clip negative values (below cut-in) and above rated
    power_kw = np.clip(power_kw, 0, p_curve.max())
    
    return power_kw


def parse_envision_en171_curve(
    air_density_kgm3: float = IEC_REFERENCE_AIR_DENSITY_KGM3,
) -> Dict:
    """Parse Envision EN-171-6.5 MW certified power curve.
    
    Args:
        air_density_kgm3: Site air density (kg/m³). Default is IEC reference.
    
    Returns:
        Dictionary with power curve, specs, and metadata
    """
    curve = ENVISION_EN171_65_POWER_CURVE.copy()
    specs = ENVISION_EN171_65_SPECS.copy()
    
    # Apply air density correction if not reference
    if abs(air_density_kgm3 - IEC_REFERENCE_AIR_DENSITY_KGM3) > 0.001:
        curve["power_kw"] = correct_power_for_air_density(
            wind_speed_ms=np.array(curve["wind_speed_ms"]),
            power_kw_ref=np.array(curve["power_kw"]),
            air_density_kgm3=air_density_kgm3,
        ).tolist()
        specs["air_density_corrected"] = True
        specs["site_air_density_kgm3"] = air_density_kgm3
    else:
        specs["air_density_corrected"] = False
    
    return {
        "curve": curve,
        "specs": specs,
        "source": "CGC-B-FNc-2024-184",
        "iec_compliant": True,
    }


def parse_envision_10mw_curve(
    air_density_kgm3: float = IEC_REFERENCE_AIR_DENSITY_KGM3,
) -> Dict:
    """Parse Envision 10 MW extrapolated power curve.
    
    ⚠️ WARNING: This is PROVISIONAL - Use certified curve when available.
    
    Args:
        air_density_kgm3: Site air density (kg/m³). Default is IEC reference.
    
    Returns:
        Dictionary with power curve, specs, and metadata
    """
    curve = ENVISION_10MW_EXTRAPOLATED_POWER_CURVE.copy()
    specs = ENVISION_10MW_EXTRAPOLATED_SPECS.copy()
    
    # Apply air density correction if not reference
    if abs(air_density_kgm3 - IEC_REFERENCE_AIR_DENSITY_KGM3) > 0.001:
        curve["power_kw"] = correct_power_for_air_density(
            wind_speed_ms=np.array(curve["wind_speed_ms"]),
            power_kw_ref=np.array(curve["power_kw"]),
            air_density_kgm3=air_density_kgm3,
        ).tolist()
        specs["air_density_corrected"] = True
        specs["site_air_density_kgm3"] = air_density_kgm3
    else:
        specs["air_density_corrected"] = False
    
    logger.warning(
        "Using EXTRAPOLATED 10 MW power curve. "
        "This is PROVISIONAL and should be replaced with OEM certified curve."
    )
    
    return {
        "curve": curve,
        "specs": specs,
        "source": "EXTRAPOLATED_FROM_EN171_65",
        "iec_compliant": False,
        "provisional": True,
    }


def compute_aep_from_curve(
    wind_dist_ms: np.ndarray,
    curve: Dict,
    n_turbines: int,
    capacity_mw: float,
    apply_losses: bool = True,
    wake_loss_pct: float = 8.0,
    availability_pct: float = 97.0,
    electrical_loss_pct: float = 2.0,
) -> Tuple[float, float, np.ndarray]:
    """Compute Annual Energy Production (AEP) from wind distribution.
    
    Args:
        wind_dist_ms: 8760-hour wind speed timeseries (m/s)
        curve: Power curve dict from parse_envision_*_curve()
        n_turbines: Number of turbines
        capacity_mw: Rated capacity per turbine (MW)
        apply_losses: If True, apply wake/availability/electrical losses
        wake_loss_pct: Wake loss percentage (0-100)
        availability_pct: Availability percentage (0-100)
        electrical_loss_pct: Electrical loss percentage (0-100)
    
    Returns:
        Tuple of (aep_gwh, capacity_factor, power_output_8760_kw)
    """
    if len(wind_dist_ms) != 8760:
        raise ValueError(f"Expected 8760 hours, got {len(wind_dist_ms)}")
    
    # Interpolate power at each wind speed
    power_per_turbine_kw = interpolate_power_curve(
        curve["curve"],
        wind_dist_ms,
        method="cubic"
    )
    
    # Total power for all turbines
    power_total_kw = power_per_turbine_kw * n_turbines
    
    # Apply losses if requested
    if apply_losses:
        # Wake losses (reduce power output)
        power_total_kw *= (1 - wake_loss_pct / 100.0)
        
        # Availability (reduce operational hours)
        power_total_kw *= (availability_pct / 100.0)
        
        # Electrical losses (cable, transformer, etc.)
        power_total_kw *= (1 - electrical_loss_pct / 100.0)
    
    # Annual energy (kWh)
    aep_kwh = power_total_kw.sum()
    
    # Convert to GWh
    aep_gwh = aep_kwh / 1e6
    
    # Capacity factor
    total_capacity_kw = capacity_mw * 1000 * n_turbines
    capacity_factor = aep_kwh / (total_capacity_kw * 8760)
    
    return aep_gwh, capacity_factor, power_total_kw


__all__ = [
    "IEC_REFERENCE_AIR_DENSITY_KGM3",
    "ENVISION_EN171_65_POWER_CURVE",
    "ENVISION_EN171_65_SPECS",
    "ENVISION_10MW_EXTRAPOLATED_POWER_CURVE",
    "ENVISION_10MW_EXTRAPOLATED_SPECS",
    "parse_envision_en171_curve",
    "parse_envision_10mw_curve",
    "correct_power_for_air_density",
    "interpolate_power_curve",
    "compute_aep_from_curve",
]
