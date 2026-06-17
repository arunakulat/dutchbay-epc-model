#!/usr/bin/env python
"""Wind farm revenue calculation with multi-currency PPA support.

Features:
- Currency-agnostic revenue calculations (LKR/USD/EUR/CNY)
- Annual revenue from AEP timeseries
- PPA price indexation (CPI, foreign currency)
- Production degradation (0.5%/year)
- Monte Carlo revenue distribution
- P50/P90 revenue percentiles

Usage:
    from finance.revenue_wind import calculate_wind_revenue_annual
    
    # LKR-based PPA
    revenue_20yr = calculate_wind_revenue_annual(
        aep_gwh_annual=563.0,
        ppa_price_per_mwh=20300.0,  # LKR/MWh (20.3 LKR/kWh × 1000)
        ppa_currency="LKR",
        ppa_term_years=20,
        cpi_annual_pct=2.0,
        degradation_pct_yr=0.5
    )
    
    print(f"Year 1 Revenue: LKR {revenue_20yr[0]:.2f} M")
    print(f"Year 20 Revenue: LKR {revenue_20yr[-1]:.2f} M")
    
    # EUR-based PPA (backward compatible)
    revenue_25yr = calculate_wind_revenue_annual(
        aep_gwh_annual=563.0,
        ppa_price_per_mwh=72.5,
        ppa_currency="EUR",
        ppa_term_years=25,
        cpi_annual_pct=2.0,
        degradation_pct_yr=0.5
    )

Context:
    Sprint 17 - Issue #22: Multi-Currency PPA Integration
    Part of complete wind-to-finance analytics for DutchBay 150 MW
    
Version History:
    v2.0 (2025-12-23): Multi-currency support (LKR/USD/EUR/CNY)
    v1.0 (2025-12-01): Initial EUR-only implementation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, cast

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Supported PPA currencies
SUPPORTED_CURRENCIES = {"LKR", "USD", "EUR", "CNY", "GBP", "JPY"}

# Currency display formats (for logging)
CURRENCY_FORMATS = {
    "LKR": "LKR {:.2f} M",
    "USD": "${:.2f} M",
    "EUR": "€{:.2f} M",
    "CNY": "¥{:.2f} M",
    "GBP": "£{:.2f} M",
    "JPY": "¥{:.2f} M",
}


def calculate_wind_revenue_annual(
    aep_gwh_annual: float,
    ppa_price_per_mwh: float,
    ppa_currency: str = "USD",
    ppa_term_years: int = 20,
    cpi_annual_pct: float = 2.0,
    degradation_pct_yr: float = 0.5,
    indexation_start_year: int = 2,
    tariff_type: str = "fixed",
) -> np.ndarray:
    """Calculate annual wind revenue over PPA term (multi-currency).
    
    Args:
        aep_gwh_annual: Annual energy production (GWh) in Year 1
        ppa_price_per_mwh: PPA price in Year 1 (currency/MWh)
        ppa_currency: Revenue currency ('LKR', 'USD', 'EUR', 'CNY', etc.)
        ppa_term_years: PPA term (years)
        cpi_annual_pct: Annual CPI inflation for price indexation (%)
        degradation_pct_yr: Annual production degradation (%)
        indexation_start_year: Year when indexation starts (default 2)
        tariff_type: 'fixed' or 'indexed' (controls CPI application)
    
    Returns:
        Annual revenue array (M-currency) for each year
        
    Raises:
        ValueError: If ppa_currency not in SUPPORTED_CURRENCIES
        
    Example:
        >>> # LKR PPA (Sri Lanka)
        >>> revenue = calculate_wind_revenue_annual(
        ...     aep_gwh_annual=563.0,
        ...     ppa_price_per_mwh=20300.0,  # 20.3 LKR/kWh
        ...     ppa_currency="LKR",
        ...     ppa_term_years=20
        ... )
        >>> print(f"Year 1: LKR {revenue[0]:.1f} M")
        Year 1: LKR 11428.9 M
        
        >>> # EUR PPA (legacy)
        >>> revenue = calculate_wind_revenue_annual(
        ...     aep_gwh_annual=563.0,
        ...     ppa_price_per_mwh=72.5,
        ...     ppa_currency="EUR",
        ...     ppa_term_years=25
        ... )
        >>> print(f"Year 1: €{revenue[0]:.1f} M")
        Year 1: €40.8 M
    """
    # Validate currency
    if ppa_currency not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported PPA currency: {ppa_currency}. "
            f"Supported: {', '.join(sorted(SUPPORTED_CURRENCIES))}"
        )
    
    years = np.arange(1, ppa_term_years + 1)
    
    # Production with degradation
    aep_annual = aep_gwh_annual * (1 - degradation_pct_yr / 100) ** (years - 1)
    
    # PPA price with CPI indexation (if tariff_type == 'indexed')
    ppa_price_indexed = np.full(ppa_term_years, ppa_price_per_mwh)
    
    if tariff_type == "indexed" and indexation_start_year <= ppa_term_years:
        idx_years = years >= indexation_start_year
        years_from_start = years[idx_years] - indexation_start_year + 1
        ppa_price_indexed[idx_years] = (
            ppa_price_per_mwh * (1 + cpi_annual_pct / 100) ** years_from_start
        )
    
    # Revenue calculation (currency-agnostic)
    # Revenue = AEP (GWh) × Price (currency/MWh) × 1000 (MWh/GWh) / 1e6 (M-currency)
    revenue_millions = aep_annual * ppa_price_indexed * 1000 / 1e6
    
    # Log summary
    currency_fmt = CURRENCY_FORMATS.get(ppa_currency, f"{ppa_currency} {{:.2f}} M")
    logger.info(
        "Wind Revenue Calculation (%s PPA, %d years):",
        ppa_currency,
        ppa_term_years,
    )
    logger.info("  Year 1 Revenue: %s", currency_fmt.format(revenue_millions[0]))
    logger.info("  Year %d Revenue: %s", ppa_term_years, currency_fmt.format(revenue_millions[-1]))
    logger.info("  Total Undiscounted: %s", currency_fmt.format(revenue_millions.sum()))

    return cast("np.ndarray", revenue_millions)


def calculate_wind_revenue_monte_carlo(
    mc_scenarios: pd.DataFrame,
    ppa_price_per_mwh: float,
    ppa_currency: str = "USD",
    ppa_term_years: int = 20,
    cpi_annual_pct: float = 2.0,
    degradation_pct_yr: float = 0.5,
    tariff_type: str = "fixed",
) -> Dict[str, Any]:
    """Calculate revenue distribution from Monte Carlo AEP scenarios (multi-currency).
    
    Args:
        mc_scenarios: DataFrame with 'aep_gwh' column from Monte Carlo
        ppa_price_per_mwh: PPA price in Year 1 (currency/MWh)
        ppa_currency: Revenue currency ('LKR', 'USD', 'EUR', etc.)
        ppa_term_years: PPA term (years)
        cpi_annual_pct: Annual CPI inflation (%)
        degradation_pct_yr: Annual production degradation (%)
        tariff_type: 'fixed' or 'indexed'
    
    Returns:
        Dictionary with revenue distribution statistics:
            - p50_revenue: P50 annual revenue (M-currency)
            - p90_revenue: P90 annual revenue (M-currency)
            - std: Standard deviation (M-currency)
            - cv: Coefficient of variation
            - revenue_total_p50: Total PPA-term revenue P50 (M-currency)
            - currency: PPA currency code
            
    Example:
        >>> scenarios = pd.DataFrame({'aep_gwh': [550, 560, 570, 580, 590]})
        >>> result = calculate_wind_revenue_monte_carlo(
        ...     mc_scenarios=scenarios,
        ...     ppa_price_per_mwh=20300.0,
        ...     ppa_currency="LKR",
        ...     ppa_term_years=20
        ... )
        >>> print(f"P50 Revenue: LKR {result['p50_revenue']:.1f} M")
    """
    if ppa_currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {ppa_currency}")
    
    aep_scenarios = mc_scenarios["aep_gwh"].values
    
    # Calculate Year 1 revenue for each scenario
    revenue_yr1 = aep_scenarios * ppa_price_per_mwh * 1000 / 1e6
    
    # Statistics
    p50_revenue = float(np.percentile(revenue_yr1, 50))
    p90_revenue = float(np.percentile(revenue_yr1, 90))
    std = float(revenue_yr1.std())
    cv = std / revenue_yr1.mean()
    
    # Total PPA-term revenue (undiscounted) at P50
    aep_p50 = float(np.percentile(aep_scenarios, 50))
    revenue_annual = calculate_wind_revenue_annual(
        aep_gwh_annual=aep_p50,
        ppa_price_per_mwh=ppa_price_per_mwh,
        ppa_currency=ppa_currency,
        ppa_term_years=ppa_term_years,
        cpi_annual_pct=cpi_annual_pct,
        degradation_pct_yr=degradation_pct_yr,
        tariff_type=tariff_type,
    )
    revenue_total = float(revenue_annual.sum())
    
    currency_fmt = CURRENCY_FORMATS.get(ppa_currency, f"{ppa_currency} {{:.2f}} M")
    logger.info("Wind Revenue Monte Carlo Results (%s):", ppa_currency)
    logger.info("  P50 Annual Revenue (Yr1): %s", currency_fmt.format(p50_revenue))
    logger.info("  P90 Annual Revenue (Yr1): %s", currency_fmt.format(p90_revenue))
    logger.info("  Std Dev: %s", currency_fmt.format(std))
    logger.info("  CV: %.2f%%", cv * 100)
    logger.info("  Total %d-Year Revenue (P50, undiscounted): %s",
                ppa_term_years, currency_fmt.format(revenue_total))
    
    return {
        "p50_revenue": p50_revenue,
        "p90_revenue": p90_revenue,
        "std": std,
        "cv": cv,
        "revenue_total_p50": revenue_total,
        "revenue_annual_p50": revenue_annual,
        "currency": ppa_currency,
        
        # Legacy fields (for backward compatibility)
        "p50_revenue_m_eur": p50_revenue if ppa_currency == "EUR" else None,
        "p90_revenue_m_eur": p90_revenue if ppa_currency == "EUR" else None,
        "std_m_eur": std if ppa_currency == "EUR" else None,
        "revenue_25yr_p50_m_eur": revenue_total if ppa_currency == "EUR" else None,
    }


def convert_tariff_to_mwh(
    tariff_per_kwh: float,
    currency: str = "LKR"
) -> float:
    """Convert tariff from per-kWh to per-MWh basis.
    
    Args:
        tariff_per_kwh: Tariff in currency/kWh (e.g., 20.3 LKR/kWh)
        currency: Currency code (for validation)
        
    Returns:
        Tariff in currency/MWh (e.g., 20300.0 LKR/MWh)
        
    Example:
        >>> convert_tariff_to_mwh(20.3, "LKR")
        20300.0
        >>> convert_tariff_to_mwh(0.0725, "USD")
        72.5
    """
    return tariff_per_kwh * 1000.0


__all__ = [
    "calculate_wind_revenue_annual",
    "calculate_wind_revenue_monte_carlo",
    "convert_tariff_to_mwh",
    "SUPPORTED_CURRENCIES",
]
