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

from .bess_revenue import BESS_TYPE

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
    """Calculate gross and net kWh for a given year from capacity + capacity factor.

    This is the LIVE production primitive: the cashflow (via
    ``calculate_net_production_for_year``) computes each year's gross/net energy
    here, including grid losses and the financed curtailment lever. ``M3`` reuses
    it per technology to sum a multi-tech plant. (It is distinct from
    ``apply_degradation_profile``, which applies a degradation *curve* to an
    already-computed AEP base and does not model grid loss/curtailment — the two
    are not interchangeable; the earlier "DEPRECATED" note was incorrect.)

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


def resolve_tech_generation_specs(
    config: Dict[str, Any],
    params: Dict[str, Any],
    *,
    tolerance: float = 0.01,
) -> Optional[List[Dict[str, Any]]]:
    """Resolve per-technology generation specs from ``generation.technologies``.

    Returns a list of ``{technology, capacity_mw, capacity_factor, degradation}``
    when the multi-tech block is present (so the cashflow sums per-tech generation,
    each with its **own** degradation), or ``None`` for the legacy single-tech path
    (which then runs byte-identically). Per-tech ``degradation_pct`` falls back to
    the project degradation; it is a free per-tech input (there is no project-level
    per-tech-degradation counterpart, so only year-1 *capacity* is reconciled).

    CESSPIT/CCCDIR fail-loud contract:

    * A technology that declares ANY generation intent (``aep_gwh`` — the reporting
      key — or ``capacity_mw``/``capacity_factor`` — the finance keys) MUST declare
      both finance keys, or this raises. This prevents a tech that is mis-keyed for
      one of the two consumers (the cashflow here vs. the reporting aggregator) from
      being silently dropped from generation.
    * A technology with no generation keys at all (e.g. storage: ``power_mw`` /
      ``energy_mwh``) contributes no generation and is skipped silently.
    * The per-tech year-1 generation must reconcile with the project headline
      (``capacity_mw × capacity_factor``) within ``tolerance``; a non-positive
      headline, or a mismatch, raises (so ``project.capacity_factor`` is a
      cross-checked input, never decorative).
    """
    generation = config.get("generation")
    techs = generation.get("technologies") if isinstance(generation, dict) else None
    if not isinstance(techs, dict) or not techs:
        return None

    project_degradation = float(params.get("degradation", 0.0))
    specs: List[Dict[str, Any]] = []
    for name, block in techs.items():
        if not isinstance(block, dict):
            continue
        # `type` is authoritative: a storage block (type: bess) is NOT a generation
        # technology even if it (mis-)carries a capacity_factor, so it never earns
        # tariff revenue here — only its BESS capacity charge (finance.bess_revenue).
        # This closes the double-count: generation tariff AND capacity charge.
        if block.get("type") == BESS_TYPE:
            continue
        cap = block.get("capacity_mw")
        cap_factor = block.get("capacity_factor")
        if cap is None or cap_factor is None:
            # aep_gwh (the reporting key) or capacity_factor signals a *generation*
            # tech; capacity_mw alone does not (storage carries a power rating).
            declares_generation = (
                block.get("aep_gwh") is not None
                or block.get("capacity_factor") is not None
            )
            if declares_generation:
                raise ValueError(
                    f"generation.technologies['{name}'] declares generation "
                    "(aep_gwh / capacity_factor) but is missing capacity_mw and/or "
                    "capacity_factor — the cashflow needs both to model its output. "
                    "Declare both, or remove the generation keys if this is a "
                    "non-generating technology (e.g. storage)."
                )
            continue  # not a generation tech (e.g. storage) -> intentionally skipped
        # Unit convention MUST match the single-tech path: _build_cashflow_params
        # reads project.degradation(_pct) as a PERCENT and divides by 100. So a
        # per-tech degradation_pct here is also a percent (e.g. 0.6 -> 0.6%/yr).
        # The project fallback comes from params["degradation"], which is ALREADY
        # the divided decimal, so it is used as-is (no second /100).
        deg_raw = block.get("degradation_pct", block.get("degradation"))
        if deg_raw is not None:
            deg_value = float(deg_raw)
            if deg_value < 0:
                raise ValueError(
                    f"generation.technologies['{name}'].degradation_pct={deg_value} "
                    "is invalid (must be >= 0, percent)."
                )
            degradation = deg_value / 100.0
        else:
            degradation = project_degradation  # already a decimal (post /100)
        specs.append(
            {
                "technology": str(name),
                "capacity_mw": float(cap),
                "capacity_factor": float(cap_factor),
                "degradation": degradation,
            }
        )
    if not specs:
        return None

    expected = float(params["capacity_mw"]) * float(params["capacity_factor"])
    if expected <= 0:
        raise ValueError(
            "Cannot reconcile generation.technologies: the project headline "
            f"capacity_mw*capacity_factor={expected:.4f} is non-positive."
        )
    actual = sum(s["capacity_mw"] * s["capacity_factor"] for s in specs)
    if abs(actual - expected) / expected > tolerance:
        raise ValueError(
            "generation.technologies year-1 capacity (sum capacity_mw*capacity_factor"
            f"={actual:.4f}) does not reconcile with project capacity_mw*capacity_factor"
            f"={expected:.4f} within {tolerance:.0%}. Align the hybrid scenario."
        )
    return specs


def calculate_net_production_for_year(
    params: Dict[str, Any], year_index: int
) -> tuple[float, float]:
    """Gross/net kWh for a year — multi-tech sum if specs are present, else single.

    With ``params["tech_generation_specs"]`` set (by ``_prepare_cashflow_context``)
    the result is the sum over technologies of :func:`_calculate_net_production`,
    each with its own capacity / capacity factor / degradation. Absent that key, it
    is exactly the legacy single-tech call (byte-identical wind-only behaviour).
    """
    grid_loss = float(params["grid_loss_pct"])
    curtailment = float(params.get("curtailment_pct", 0.0))
    specs = params.get("tech_generation_specs")
    if specs:
        gross_total = 0.0
        net_total = 0.0
        for spec in specs:
            gross, net = _calculate_net_production(
                spec["capacity_mw"],
                spec["capacity_factor"],
                spec["degradation"],
                grid_loss,
                year_index,
                curtailment_pct=curtailment,
            )
            gross_total += gross
            net_total += net
        return gross_total, net_total
    return _calculate_net_production(
        float(params["capacity_mw"]),
        float(params["capacity_factor"]),
        float(params["degradation"]),
        grid_loss,
        year_index,
        curtailment_pct=curtailment,
    )


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
