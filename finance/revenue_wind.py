#!/usr/bin/env python
"""Wind farm revenue calculation with PPA price indexation.

Features:
- Annual revenue from AEP timeseries
- PPA price indexation (CPI, foreign currency)
- Production degradation (0.5%/year)
- Monte Carlo revenue distribution
- P50/P90 revenue percentiles

Usage:
    from finance.revenue_wind import calculate_wind_revenue_annual
    
    revenue_25yr = calculate_wind_revenue_annual(
        aep_gwh_annual=563.0,
        ppa_price_eur_mwh=72.5,
        ppa_term_years=25,
        cpi_annual_pct=2.0,
        degradation_pct_yr=0.5
    )
    
    print(f"Year 1 Revenue: €{revenue_25yr[0]:.2f} M")
    print(f"Year 25 Revenue: €{revenue_25yr[-1]:.2f} M")

Context:
    Sprint 17 - Issue #22: Finance Integration
    Part of complete wind-to-finance analytics for DutchBay 150 MW
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_wind_revenue_annual(
    aep_gwh_annual: float,
    ppa_price_eur_mwh: float,
    ppa_term_years: int = 25,
    cpi_annual_pct: float = 2.0,
    degradation_pct_yr: float = 0.5,
    indexation_start_year: int = 2,
) -> np.ndarray:
    """Calculate annual wind revenue over PPA term.
    
    Args:
        aep_gwh_annual: Annual energy production (GWh) in Year 1
        ppa_price_eur_mwh: PPA price in Year 1 (€/MWh)
        ppa_term_years: PPA term (years)
        cpi_annual_pct: Annual CPI inflation for price indexation (%)
        degradation_pct_yr: Annual production degradation (%)
        indexation_start_year: Year when indexation starts (default 2)
    
    Returns:
        Annual revenue array (M€) for each year
    """
    years = np.arange(1, ppa_term_years + 1)
    
    # Production with degradation
    aep_annual = aep_gwh_annual * (1 - degradation_pct_yr / 100) ** (years - 1)
    
    # PPA price with CPI indexation
    ppa_price_indexed = np.full(ppa_term_years, ppa_price_eur_mwh)
    if indexation_start_year <= ppa_term_years:
        idx_years = years >= indexation_start_year
        years_from_start = years[idx_years] - indexation_start_year + 1
        ppa_price_indexed[idx_years] = ppa_price_eur_mwh * (1 + cpi_annual_pct / 100) ** years_from_start
    
    # Revenue = AEP (GWh) × Price (€/MWh) × 1000 (MWh/GWh) / 1e6 (M€)
    revenue_m_eur = aep_annual * ppa_price_indexed * 1000 / 1e6
    
    return revenue_m_eur


def calculate_wind_revenue_monte_carlo(
    mc_scenarios: pd.DataFrame,
    ppa_price_eur_mwh: float,
    ppa_term_years: int = 25,
    cpi_annual_pct: float = 2.0,
    degradation_pct_yr: float = 0.5,
) -> Dict:
    """Calculate revenue distribution from Monte Carlo AEP scenarios.
    
    Args:
        mc_scenarios: DataFrame with 'aep_gwh' column from Monte Carlo
        ppa_price_eur_mwh: PPA price in Year 1 (€/MWh)
        ppa_term_years: PPA term (years)
        cpi_annual_pct: Annual CPI inflation (%)
        degradation_pct_yr: Annual production degradation (%)
    
    Returns:
        Dictionary with revenue distribution statistics:
            - p50_revenue_m_eur: P50 annual revenue (M€)
            - p90_revenue_m_eur: P90 annual revenue (M€)
            - std_m_eur: Standard deviation (M€)
            - cv: Coefficient of variation
            - revenue_25yr_p50_m_eur: Total 25-year revenue P50 (M€)
    """
    aep_scenarios = mc_scenarios["aep_gwh"].values
    
    # Calculate Year 1 revenue for each scenario
    revenue_yr1_m_eur = aep_scenarios * ppa_price_eur_mwh * 1000 / 1e6
    
    # Statistics
    p50_revenue = float(np.percentile(revenue_yr1_m_eur, 50))
    p90_revenue = float(np.percentile(revenue_yr1_m_eur, 90))
    std = float(revenue_yr1_m_eur.std())
    cv = std / revenue_yr1_m_eur.mean()
    
    # Total 25-year revenue (undiscounted) at P50
    aep_p50 = float(np.percentile(aep_scenarios, 50))
    revenue_25yr = calculate_wind_revenue_annual(
        aep_gwh_annual=aep_p50,
        ppa_price_eur_mwh=ppa_price_eur_mwh,
        ppa_term_years=ppa_term_years,
        cpi_annual_pct=cpi_annual_pct,
        degradation_pct_yr=degradation_pct_yr,
    )
    revenue_25yr_total = float(revenue_25yr.sum())
    
    logger.info("Wind Revenue Monte Carlo Results:")
    logger.info(f"  P50 Annual Revenue (Yr1): €{p50_revenue:.2f} M")
    logger.info(f"  P90 Annual Revenue (Yr1): €{p90_revenue:.2f} M")
    logger.info(f"  Std Dev: €{std:.2f} M")
    logger.info(f"  CV: {cv:.2%}")
    logger.info(f"  Total 25-Year Revenue (P50, undiscounted): €{revenue_25yr_total:.1f} M")
    
    return {
        "p50_revenue_m_eur": p50_revenue,
        "p90_revenue_m_eur": p90_revenue,
        "std_m_eur": std,
        "cv": cv,
        "revenue_25yr_p50_m_eur": revenue_25yr_total,
        "revenue_annual_25yr_p50": revenue_25yr,
    }


__all__ = [
    "calculate_wind_revenue_annual",
    "calculate_wind_revenue_monte_carlo",
]
