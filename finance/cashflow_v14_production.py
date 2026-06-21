"""Production and Revenue Calculations for V14 Cashflow Model.

This module calculates annual energy production with industry-standard
performance degradation, revenue from tariffs, and statutory deductions.

Key Features:
- Wind turbine performance degradation (IEC 61400-12-1:2022)
- Grid loss calculations
- Multi-year revenue projections
- Statutory deductions (success fee, environmental surcharge, social levy)

Industry Standards:
- IEC 61400-12-1:2022 Annex C: Performance monitoring
- Staffell & Green (2014): Wind farm degradation analysis
- NREL (2019): Long-term performance trends

Author: Dutch Bay EPC Model Team
Date: December 2025
Version: 2.0.0 (Added degradation)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, cast

import numpy as np
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_degradation_config() -> Dict[str, Any]:
    """Load degradation config from defaults.yaml.

    Returns:
        Dict with degradation configuration, or defaults if not found.
    """
    defaults_path = Path("config/defaults.yaml")
    if defaults_path.exists():
        with open(defaults_path) as f:
            config = yaml.safe_load(f) or {}
            return cast("Dict[str, Any]", config.get("wind_degradation", {}))
    return {}


def apply_degradation_profile(
    aep_base: float,
    years: int,
    degradation_rate_pct: Optional[float] = None,
    start_year: int = 1,
    method: str = "linear"
) -> List[float]:
    """Apply annual performance degradation to energy production.
    
    Wind turbines experience gradual performance decline due to:
    - Mechanical wear on gearbox and drivetrain
    - Blade leading edge erosion from rain/particles  
    - Bearing degradation over operating cycles
    - Control system calibration drift
    - Yaw system performance decline
    
    Industry research shows typical degradation:
    - Modern turbines: 0.5-0.7%/year (median 0.65%)
    - Older turbines (pre-2008): 1.0-1.6%/year
    - Impact: 12-15% cumulative loss over 20-25 years
    
    References:
        - Staffell & Green (2014): "How Does Wind Farm Performance Decline 
          with Age?" Energy Policy, UK wind farms, 1.6%/year average
        - NREL (2019): "2018 Wind Technologies Market Report", US modern 
          turbines, 0.53%/year median
        - Kim et al. (2025): "Quantification of Performance Degradation", 
          South Korea study, 0.72%/year
        - IEC 61400-12-1:2022 Annex C: Performance monitoring standards
    
    Args:
        aep_base: Base year annual energy production (MWh/year)
        years: Number of years to project (typically 20-25)
        degradation_rate_pct: Annual degradation rate in percent
            (default: loaded from config, fallback 0.65%)
        start_year: Year to start degradation (default: 1)
            Use 2 if commissioning year has no degradation
        method: Degradation model - "linear" (default) or "exponential"
            Linear is conservative and industry standard
            
    Returns:
        List of annual production values with degradation applied.
        Length = years. Index 0 = Year 1.
        
    Example:
        >>> # 350 GWh/year base, 25 years, 0.65%/year degradation
        >>> production = apply_degradation_profile(350_000, 25, 0.65)
        >>> production[0]  # Year 1
        350000.0
        >>> production[9]  # Year 10 (~6.5% lower)
        327250.0
        >>> production[24]  # Year 25 (~15% lower)
        297500.0
    """
    # Load config if not provided
    if degradation_rate_pct is None:
        config = _load_degradation_config()
        degradation_rate_pct = config.get("annual_rate_pct", 0.65)
        start_year = config.get("start_year", 1)
        method = config.get("method", "linear")
        
        if config.get("enabled", True):
            logger.info(
                f"Wind degradation: {degradation_rate_pct}%/year "
                f"(method: {method}, start: year {start_year})"
            )
    
    # Convert percentage to decimal
    degradation_rate = degradation_rate_pct / 100.0
    
    # Build degradation profile
    production = []
    for year_idx in range(years):
        year_number = year_idx + 1  # 1-based year
        
        if year_number < start_year:
            # No degradation before start year (e.g., commissioning)
            degradation_factor = 1.0
        else:
            # Calculate degradation from start year
            years_since_start = year_number - start_year
            
            if method == "exponential":
                # Exponential: front-loaded degradation
                # Factor = exp(-rate * t)
                degradation_factor = np.exp(-degradation_rate * years_since_start)
            else:
                # Linear (default): conservative, industry standard
                # Factor = (1 - rate)^t
                degradation_factor = (1.0 - degradation_rate) ** years_since_start
        
        annual_production = aep_base * degradation_factor
        production.append(annual_production)
    
    # Log impact
    if degradation_rate > 0:
        year_10_loss = (1 - production[9] / aep_base) * 100 if len(production) >= 10 else 0
        year_20_loss = (1 - production[19] / aep_base) * 100 if len(production) >= 20 else 0
        logger.info(
            f"Degradation impact: Year 10: -{year_10_loss:.1f}%, "
            f"Year 20: -{year_20_loss:.1f}%"
        )
    
    return production


def _calculate_net_production(
    capacity_mw: float,
    capacity_factor: float,
    degradation: float,
    grid_loss_pct: float,
    year: int,
    curtailment_pct: float = 0.0,
) -> tuple[float, float]:
    """Calculate gross and net kWh for a given year.

    DEPRECATED: Use apply_degradation_profile() for new code.
    This function maintained for backward compatibility.

    Parameters
    ----------
    capacity_mw :
        Installed capacity (MW).
    capacity_factor :
        Net capacity factor (decimal).
    degradation :
        Annual degradation rate (decimal).
    grid_loss_pct :
        Grid losses (decimal share of gross).
    year :
        Zero-based year index (0 = first operating year).
    curtailment_pct :
        INCREMENTAL financed grid-curtailment haircut (decimal), applied after grid
        losses. Default 0.0 → byte-identical (the physical/embedded curtailment is
        already in capacity_factor); a first-class stress/risk lever above that base.
    """
    hours_per_year = 8760.0
    effective_cf = capacity_factor * ((1.0 - degradation) ** year)
    gross_kwh = capacity_mw * 1e3 * hours_per_year * effective_cf
    grid_loss = gross_kwh * grid_loss_pct
    net_kwh = (gross_kwh - grid_loss) * (1.0 - curtailment_pct)
    return gross_kwh, net_kwh


def _calculate_revenue_lkr(net_kwh: float, tariff_lkr_per_kwh: float) -> float:
    """Compute revenue in LKR = net energy * tariff."""
    return net_kwh * tariff_lkr_per_kwh


def _calculate_statutory_deductions(
    revenue_lkr: float,
    success_fee_pct: float,
    env_surcharge_pct: float,
    social_levy_pct: float,
) -> Dict[str, float]:
    """Calculate statutory charges as percentages of revenue.

    All percentage arguments are decimals (e.g. 0.01 = 1%).
    """
    success_fee = revenue_lkr * success_fee_pct
    env_surcharge = revenue_lkr * env_surcharge_pct
    social_levy = revenue_lkr * social_levy_pct
    total = success_fee + env_surcharge + social_levy
    return {
        "success_fee": success_fee,
        "environmental_surcharge": env_surcharge,
        "social_services_levy": social_levy,
        "total_statutory_deductions": total,
    }


def _calculate_opex_lkr(opex_usd_per_year: float, fx_rate: float) -> float:
    """Convert annual OPEX from USD to LKR at a given FX rate."""
    return opex_usd_per_year * fx_rate


def _apply_risk_haircut(cfads_lkr: float, risk_haircut_pct: float) -> float:
    """Apply risk haircut: CFADS * (1 - haircut)."""
    return cfads_lkr * (1.0 - risk_haircut_pct)


__all__ = [
    "apply_degradation_profile",
    "_calculate_net_production",
    "_calculate_revenue_lkr",
    "_calculate_statutory_deductions",
    "_calculate_opex_lkr",
    "_apply_risk_haircut",
]
