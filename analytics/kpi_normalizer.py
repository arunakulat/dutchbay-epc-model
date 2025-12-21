"""KPI normalization for cross-project benchmarking.

This module provides normalization functions to make KPIs comparable across
projects of different sizes, technologies, and jurisdictions. Essential for
portfolio analytics and competitive benchmarking.

Architecture / Go-with-the-Flow rules
-------------------------------------
- Normalizes by capacity (MW), capex ($/MW), and revenue ($/kWh)
- Handles missing/optional fields gracefully (returns None)
- All outputs are Pydantic V2 frozen contracts
- No side effects - pure transformation functions

Framework Compliance
--------------------
- GWTF: Evidence-based normalization (industry standards)
- CESSPIT: Config-driven normalization factors
- CASPER: All outputs as Pydantic V2 contracts
- CCCDIR: Single responsibility - normalization only

Sprint 16 Features
------------------
- Per-MW metrics (NPV/MW, capex/MW, debt/MW)
- Per-kWh metrics (tariff, LCOE)
- Covenant normalization (DSCR, LLCR, PLCR)
- Industry percentile rankings
- Portfolio aggregation functions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic V2 Contracts for Normalized KPIs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedKPIs:
    """Normalized KPIs for cross-project comparison.

    All per-MW metrics are in USD/MW.
    All per-kWh metrics are in USD/kWh or LKR/kWh (as specified).
    """

    # Per-MW metrics (size-normalized)
    project_npv_per_mw: Optional[float] = None  # USD/MW
    equity_npv_per_mw: Optional[float] = None  # USD/MW
    capex_per_mw: Optional[float] = None  # USD/MW
    debt_per_mw: Optional[float] = None  # USD/MW

    # Per-kWh metrics (energy-normalized)
    tariff_usd_per_kwh: Optional[float] = None  # USD/kWh
    lcoe_usd_per_kwh: Optional[float] = None  # USD/kWh (Levelized Cost of Energy)

    # Covenant ratios (already dimensionless)
    dscr_min: Optional[float] = None
    llcr_min: Optional[float] = None
    plcr: Optional[float] = None

    # Return metrics (already dimensionless)
    project_irr: Optional[float] = None
    equity_irr: Optional[float] = None
    equity_multiple: Optional[float] = None

    # Original capacity for reference
    capacity_mw: Optional[float] = None


@dataclass(frozen=True)
class BenchmarkRanking:
    """Industry percentile ranking for a KPI."""

    kpi_name: str
    kpi_value: float
    percentile: float  # 0.0 - 1.0 (e.g., 0.75 = 75th percentile)
    industry_p25: Optional[float] = None  # 25th percentile benchmark
    industry_p50: Optional[float] = None  # Median
    industry_p75: Optional[float] = None  # 75th percentile
    interpretation: Optional[str] = None  # "Above average", "Top quartile", etc.


@dataclass(frozen=True)
class PortfolioAggregation:
    """Aggregated KPIs for a portfolio of projects."""

    total_capacity_mw: float
    total_capex_usd: float
    total_debt_usd: float

    # Weighted average KPIs
    weighted_avg_project_irr: Optional[float] = None
    weighted_avg_equity_irr: Optional[float] = None
    weighted_avg_dscr_min: Optional[float] = None

    # Portfolio-level metrics
    portfolio_npv_per_mw: Optional[float] = None
    portfolio_capex_per_mw: Optional[float] = None
    portfolio_debt_per_mw: Optional[float] = None

    project_count: int = 0


@dataclass
class IndustryBenchmarks:
    """Industry benchmark data for solar PV projects.

    Sources:
    - IRENA Renewable Power Generation Costs 2023
    - BNEF Solar PV Market Outlook 2024
    - World Bank PPP in Infrastructure Resource Center
    """

    # Capex benchmarks (USD/MW)
    capex_solar_p25: float = 800_000.0  # 25th percentile (low cost)
    capex_solar_p50: float = 1_000_000.0  # Median
    capex_solar_p75: float = 1_200_000.0  # 75th percentile (high cost)

    # Project IRR benchmarks (decimal)
    project_irr_p25: float = 0.08  # 8% (conservative)
    project_irr_p50: float = 0.12  # 12% (typical)
    project_irr_p75: float = 0.16  # 16% (strong)

    # Equity IRR benchmarks (decimal)
    equity_irr_p25: float = 0.12  # 12%
    equity_irr_p50: float = 0.18  # 18%
    equity_irr_p75: float = 0.25  # 25%

    # DSCR benchmarks
    dscr_p25: float = 1.20  # Tight covenant
    dscr_p50: float = 1.35  # Typical
    dscr_p75: float = 1.50  # Conservative

    # LLCR benchmarks
    llcr_p25: float = 1.30
    llcr_p50: float = 1.50
    llcr_p75: float = 1.75


# ---------------------------------------------------------------------------
# Core normalization functions
# ---------------------------------------------------------------------------


def normalize_kpis(
    kpis: Dict[str, Any],
    capacity_mw: float,
    capex_usd: Optional[float] = None,
    annual_generation_kwh: Optional[float] = None,
) -> NormalizedKPIs:
    """Normalize KPIs for cross-project comparison.

    Args:
        kpis:
            Raw KPI dictionary from pipeline (project_irr, project_npv, etc.).
        capacity_mw:
            Project capacity in MW.
        capex_usd:
            Total capex in USD (optional, for LCOE calculation).
        annual_generation_kwh:
            Annual generation in kWh (optional, for per-kWh metrics).

    Returns:
        NormalizedKPIs with all size-adjusted metrics.
    """
    if capacity_mw <= 0:
        logger.warning("Invalid capacity_mw=%.2f, returning None metrics", capacity_mw)
        return NormalizedKPIs(capacity_mw=capacity_mw)

    # Per-MW normalization
    project_npv = kpis.get("project_npv")
    project_npv_per_mw = project_npv / capacity_mw if project_npv is not None else None

    equity_npv = kpis.get("equity_npv")
    equity_npv_per_mw = equity_npv / capacity_mw if equity_npv is not None else None

    capex_per_mw = capex_usd / capacity_mw if capex_usd is not None else None

    debt_amount = kpis.get("debt_amount_usd")
    debt_per_mw = debt_amount / capacity_mw if debt_amount is not None else None

    # Per-kWh normalization
    tariff_lkr = kpis.get("tariff_lkr_per_kwh")
    fx_rate = kpis.get("fx_rate_lkr_usd", 320.0)  # Default if missing
    tariff_usd_per_kwh = (tariff_lkr / fx_rate) if tariff_lkr is not None else None

    # LCOE calculation (if capex and generation available)
    lcoe_usd_per_kwh = None
    if capex_usd is not None and annual_generation_kwh is not None and annual_generation_kwh > 0:
        # Simplified LCOE = Capex / (Annual Gen * Project Life)
        project_life_years = 25.0  # Standard assumption
        lifetime_generation = annual_generation_kwh * project_life_years
        lcoe_usd_per_kwh = capex_usd / lifetime_generation

    # Covenant ratios (pass through, already normalized)
    dscr_min = kpis.get("dscr_min")
    llcr_min = kpis.get("llcr_min")
    plcr = kpis.get("plcr")

    # Return metrics (pass through, already normalized)
    project_irr = kpis.get("project_irr")
    equity_irr = kpis.get("equity_irr")
    equity_multiple = kpis.get("equity_multiple")

    return NormalizedKPIs(
        project_npv_per_mw=project_npv_per_mw,
        equity_npv_per_mw=equity_npv_per_mw,
        capex_per_mw=capex_per_mw,
        debt_per_mw=debt_per_mw,
        tariff_usd_per_kwh=tariff_usd_per_kwh,
        lcoe_usd_per_kwh=lcoe_usd_per_kwh,
        dscr_min=dscr_min,
        llcr_min=llcr_min,
        plcr=plcr,
        project_irr=project_irr,
        equity_irr=equity_irr,
        equity_multiple=equity_multiple,
        capacity_mw=capacity_mw,
    )


def rank_kpi_against_industry(
    kpi_name: str,
    kpi_value: float,
    benchmarks: Optional[IndustryBenchmarks] = None,
) -> BenchmarkRanking:
    """Rank a KPI value against industry benchmarks.

    Args:
        kpi_name:
            Name of KPI (e.g., "project_irr", "capex_per_mw", "dscr_min").
        kpi_value:
            Actual KPI value from project.
        benchmarks:
            Industry benchmark data (uses defaults if None).

    Returns:
        BenchmarkRanking with percentile and interpretation.
    """
    if benchmarks is None:
        benchmarks = IndustryBenchmarks()

    # Map KPI name to benchmark percentiles
    benchmark_map = {
        "project_irr": (benchmarks.project_irr_p25, benchmarks.project_irr_p50, benchmarks.project_irr_p75),
        "equity_irr": (benchmarks.equity_irr_p25, benchmarks.equity_irr_p50, benchmarks.equity_irr_p75),
        "capex_per_mw": (benchmarks.capex_solar_p25, benchmarks.capex_solar_p50, benchmarks.capex_solar_p75),
        "dscr_min": (benchmarks.dscr_p25, benchmarks.dscr_p50, benchmarks.dscr_p75),
        "llcr_min": (benchmarks.llcr_p25, benchmarks.llcr_p50, benchmarks.llcr_p75),
    }

    if kpi_name not in benchmark_map:
        logger.warning("No industry benchmarks available for %s", kpi_name)
        return BenchmarkRanking(
            kpi_name=kpi_name,
            kpi_value=kpi_value,
            percentile=0.5,  # Default to median
            interpretation="No benchmark data",
        )

    p25, p50, p75 = benchmark_map[kpi_name]

    # Calculate percentile (linear interpolation)
    if kpi_value <= p25:
        percentile = 0.25 * (kpi_value / p25) if p25 > 0 else 0.0
        interpretation = "Below average"
    elif kpi_value <= p50:
        percentile = 0.25 + 0.25 * ((kpi_value - p25) / (p50 - p25))
        interpretation = "Below median"
    elif kpi_value <= p75:
        percentile = 0.50 + 0.25 * ((kpi_value - p50) / (p75 - p50))
        interpretation = "Above median"
    else:
        percentile = 0.75 + 0.25 * ((kpi_value - p75) / p75)
        interpretation = "Top quartile"

    return BenchmarkRanking(
        kpi_name=kpi_name,
        kpi_value=kpi_value,
        percentile=min(percentile, 1.0),  # Cap at 100th percentile
        industry_p25=p25,
        industry_p50=p50,
        industry_p75=p75,
        interpretation=interpretation,
    )


def aggregate_portfolio_kpis(
    projects: List[Dict[str, Any]],
    capacity_key: str = "capacity_mw",
    capex_key: str = "capex_usd",
    debt_key: str = "debt_amount_usd",
) -> PortfolioAggregation:
    """Aggregate KPIs across a portfolio of projects.

    Args:
        projects:
            List of project KPI dictionaries.
        capacity_key:
            Key for capacity in MW.
        capex_key:
            Key for capex in USD.
        debt_key:
            Key for debt amount in USD.

    Returns:
        PortfolioAggregation with weighted averages.
    """
    if not projects:
        return PortfolioAggregation(
            total_capacity_mw=0.0,
            total_capex_usd=0.0,
            total_debt_usd=0.0,
            project_count=0,
        )

    total_capacity_mw = sum(p.get(capacity_key, 0.0) for p in projects)
    total_capex_usd = sum(p.get(capex_key, 0.0) for p in projects)
    total_debt_usd = sum(p.get(debt_key, 0.0) for p in projects)

    # Weighted average IRRs (by capacity)
    total_weighted_project_irr = 0.0
    total_weighted_equity_irr = 0.0
    total_weighted_dscr = 0.0
    valid_project_irr_count = 0
    valid_equity_irr_count = 0
    valid_dscr_count = 0

    for project in projects:
        capacity = project.get(capacity_key, 0.0)
        if capacity > 0:
            if "project_irr" in project:
                total_weighted_project_irr += project["project_irr"] * capacity
                valid_project_irr_count += 1
            if "equity_irr" in project:
                total_weighted_equity_irr += project["equity_irr"] * capacity
                valid_equity_irr_count += 1
            if "dscr_min" in project:
                total_weighted_dscr += project["dscr_min"] * capacity
                valid_dscr_count += 1

    weighted_avg_project_irr = (
        total_weighted_project_irr / total_capacity_mw if total_capacity_mw > 0 and valid_project_irr_count > 0 else None
    )
    weighted_avg_equity_irr = (
        total_weighted_equity_irr / total_capacity_mw if total_capacity_mw > 0 and valid_equity_irr_count > 0 else None
    )
    weighted_avg_dscr_min = (
        total_weighted_dscr / total_capacity_mw if total_capacity_mw > 0 and valid_dscr_count > 0 else None
    )

    # Portfolio-level per-MW metrics
    portfolio_capex_per_mw = total_capex_usd / total_capacity_mw if total_capacity_mw > 0 else None
    portfolio_debt_per_mw = total_debt_usd / total_capacity_mw if total_capacity_mw > 0 else None

    # Portfolio NPV (sum of individual NPVs)
    total_portfolio_npv = sum(p.get("project_npv", 0.0) for p in projects if "project_npv" in p)
    portfolio_npv_per_mw = total_portfolio_npv / total_capacity_mw if total_capacity_mw > 0 else None

    return PortfolioAggregation(
        total_capacity_mw=total_capacity_mw,
        total_capex_usd=total_capex_usd,
        total_debt_usd=total_debt_usd,
        weighted_avg_project_irr=weighted_avg_project_irr,
        weighted_avg_equity_irr=weighted_avg_equity_irr,
        weighted_avg_dscr_min=weighted_avg_dscr_min,
        portfolio_npv_per_mw=portfolio_npv_per_mw,
        portfolio_capex_per_mw=portfolio_capex_per_mw,
        portfolio_debt_per_mw=portfolio_debt_per_mw,
        project_count=len(projects),
    )
