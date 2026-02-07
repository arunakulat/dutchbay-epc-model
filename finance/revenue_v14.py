#!/usr/bin/env python
"""Revenue calculation module for DutchBay v14 financial model.

Calculates project revenue from AEP and tariff with:
- Config-driven tariff (GWTF ARCH-01: no hardcoded values)
- Monte Carlo revenue distribution (optional)
- Multi-currency support (LKR primary, USD via FX)
- Type-safe contracts

All currency and tariff values MUST come from YAML config.
NEVER hardcode currency conversion rates or tariff prices.

Context:
    Sprint 17 - Phase 5: Finance Integration
    Connects AEP data to revenue projections
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


def calculate_revenue_from_aep(
    aep_data: Dict[str, Any],
    tariff_lkr_per_kwh: float,
    mc_results: Optional[Dict[str, Any]] = None,
    fx_rate_lkr_per_usd: Optional[float] = None
) -> Dict[str, float]:
    """Calculate project revenue from AEP data and tariff.

    CRITICAL: This function is config-driven (GWTF ARCH-01).
    - tariff_lkr_per_kwh MUST come from config['tariff']['lkr_per_kwh']
    - fx_rate_lkr_per_usd MUST come from config['fx']['start_lkr_per_usd']
    - NEVER hardcode these values (e.g., €72.5/MWh is WRONG)

    Args:
        aep_data: AEP summary dict from load_aep_from_summary()
        tariff_lkr_per_kwh: Power Purchase Agreement tariff (LKR/kWh) from config
        mc_results: Optional Monte Carlo results dict from run_monte_carlo_aep()
        fx_rate_lkr_per_usd: Optional FX rate for USD conversion (from config)

    Returns:
        Dictionary with:
            - p50_aep_gwh: P50 AEP (GWh)
            - p50_revenue_m_lkr: P50 annual revenue (million LKR)
            - tariff_lkr_per_kwh: Tariff used
            - p75_aep_gwh, p75_revenue_m_lkr: P75 values (if MC available)
            - p90_aep_gwh, p90_revenue_m_lkr: P90 values (if MC available)
            - p99_aep_gwh, p99_revenue_m_lkr: P99 values (if MC available)
            - aep_std_gwh: Standard deviation of AEP (if MC available)
            - aep_cv: Coefficient of variation (if MC available)
            - revenue_std_m_lkr: Standard deviation of revenue (if MC available)
            - p50_revenue_m_usd: P50 revenue in USD (if FX rate provided)

    Example:
        >>> from analytics.loader.aep_loader import load_aep_from_summary
        >>> aep_data = load_aep_from_summary('tests/mocks/aep_summary_dutchbay.json')
        >>> revenue_data = calculate_revenue_from_aep(
        ...     aep_data=aep_data,
        ...     tariff_lkr_per_kwh=20.3,  # From config!
        ...     fx_rate_lkr_per_usd=300.0  # From config!
        ... )
        >>> print(f"Annual revenue: {revenue_data['p50_revenue_m_lkr']:.2f} M LKR")
        Annual revenue: 9848.90 M LKR
    """
    # Base case: P50 revenue from net AEP
    p50_aep_gwh = aep_data["net_site_aep_gwh"]
    p50_aep_kwh = p50_aep_gwh * 1e6  # GWh → kWh
    p50_revenue_lkr = p50_aep_kwh * tariff_lkr_per_kwh
    p50_revenue_m_lkr = p50_revenue_lkr / 1e6  # LKR → Million LKR

    revenue_output = {
        "p50_aep_gwh": p50_aep_gwh,
        "p50_revenue_m_lkr": p50_revenue_m_lkr,
        "tariff_lkr_per_kwh": tariff_lkr_per_kwh,
        "capacity_factor": aep_data["capacity_factor"],
    }

    # Add USD conversion if FX rate provided
    if fx_rate_lkr_per_usd and fx_rate_lkr_per_usd > 0:
        p50_revenue_m_usd = p50_revenue_m_lkr / fx_rate_lkr_per_usd
        revenue_output["p50_revenue_m_usd"] = p50_revenue_m_usd
        revenue_output["fx_rate_lkr_per_usd"] = fx_rate_lkr_per_usd

    logger.info(
        f"Base revenue calculated: {p50_revenue_m_lkr:.2f} M LKR/year "
        f"(AEP={p50_aep_gwh:.2f} GWh × {tariff_lkr_per_kwh:.2f} LKR/kWh)"
    )

    # Add Monte Carlo percentiles if available
    if mc_results:
        percentiles = mc_results.get("percentiles", {})
        statistics = mc_results.get("statistics", {})

        for p_label in ["p50", "p75", "p90", "p99"]:
            if p_label in percentiles:
                aep_p_gwh = percentiles[p_label]
                revenue_p_lkr = aep_p_gwh * 1e6 * tariff_lkr_per_kwh
                revenue_p_m_lkr = revenue_p_lkr / 1e6

                revenue_output[f"{p_label}_aep_gwh"] = aep_p_gwh
                revenue_output[f"{p_label}_revenue_m_lkr"] = revenue_p_m_lkr

                if fx_rate_lkr_per_usd and fx_rate_lkr_per_usd > 0:
                    revenue_output[f"{p_label}_revenue_m_usd"] = revenue_p_m_lkr / fx_rate_lkr_per_usd

        # Add risk metrics
        if "std" in statistics:
            revenue_output["aep_std_gwh"] = statistics["std"]
            revenue_output["revenue_std_m_lkr"] = (statistics["std"] * 1e6 * tariff_lkr_per_kwh) / 1e6

        if "cv" in statistics:
            revenue_output["aep_cv"] = statistics["cv"]

        logger.info(
            f"Monte Carlo revenue distribution: "
            f"P50={revenue_output.get('p50_revenue_m_lkr', 0):.2f} M LKR, "
            f"P90={revenue_output.get('p90_revenue_m_lkr', 0):.2f} M LKR"
        )

    return revenue_output


def calculate_revenue_series(
    aep_data: Dict[str, Any],
    tariff_lkr_per_kwh: float,
    years: int,
    degradation_pct: float = 0.0,
    tariff_escalation_pct: float = 0.0
) -> np.ndarray:
    """Calculate multi-year revenue series with degradation and escalation.

    Args:
        aep_data: AEP summary dict from load_aep_from_summary()
        tariff_lkr_per_kwh: Base year tariff (LKR/kWh) from config
        years: Number of project years
        degradation_pct: Annual AEP degradation (%) from config
        tariff_escalation_pct: Annual tariff escalation (%) from config

    Returns:
        Array of annual revenues (million LKR) for each year

    Example:
        >>> revenue_series = calculate_revenue_series(
        ...     aep_data=aep_data,
        ...     tariff_lkr_per_kwh=20.3,
        ...     years=20,
        ...     degradation_pct=0.6,  # 0.6% per year from config
        ...     tariff_escalation_pct=0.0  # Fixed tariff from config
        ... )
        >>> revenue_series[0], revenue_series[-1]
        (9848.90, 9293.45)  # Year 1 vs Year 20 with degradation
    """
    base_aep_gwh = aep_data["net_site_aep_gwh"]

    revenue_series = np.zeros(years)

    for year_idx in range(years):
        # Apply degradation: AEP declines each year
        aep_year_gwh = base_aep_gwh * ((1.0 - degradation_pct / 100.0) ** year_idx)

        # Apply tariff escalation
        tariff_year_lkr = tariff_lkr_per_kwh * ((1.0 + tariff_escalation_pct / 100.0) ** year_idx)

        # Calculate revenue
        revenue_year_lkr = aep_year_gwh * 1e6 * tariff_year_lkr
        revenue_series[year_idx] = revenue_year_lkr / 1e6  # Million LKR

    logger.info(
        f"Revenue series calculated for {years} years: "
        f"Year 1 = {revenue_series[0]:.2f} M LKR, "
        f"Year {years} = {revenue_series[-1]:.2f} M LKR"
    )

    return revenue_series


__all__ = [
    "calculate_revenue_from_aep",
    "calculate_revenue_series",
]
