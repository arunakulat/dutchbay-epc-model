from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Params:
    total_capex: float = 155.0
    project_life_years: int = 20
    nameplate_mw: float = 150.0
    cf_p50: float = 0.40
    yearly_degradation: float = 0.006
    hours_per_year: float = 8760.0
    tariff_lkr_kwh: float = 20.36
    fx_initial: float = 300.0
    fx_depr: float = 0.03
    opex_usd_mwh: float = 6.83
    opex_esc_usd: float = 0.02
    opex_esc_lkr: float = 0.05
    opex_split_usd: float = 0.30
    opex_split_lkr: float = 0.70
    sscl_rate: float = 0.025
    tax_rate: float = 0.30
    discount_rate: float = 0.12


@dataclass(frozen=True)
class DebtTerms:
    debt_ratio: float = 0.80
    usd_debt_ratio: float = 0.45
    usd_dfi_pct: float = 0.10
    usd_dfi_rate: float = 0.065
    usd_mkt_rate: float = 0.07
    lkr_rate: float = 0.075
    tenor_years: int = 15
    grace_years: int = 1
    principal_pct_1_4: float = 0.80
    principal_pct_5_on: float = 0.20


@dataclass(frozen=True)
class AnnualRow:
    year: int
    fx_rate: float
    production_mwh: float
    revenue_usd: float
    opex_usd: float
    sscl_usd: float
    ebit_usd: float
    interest_usd: float
    principal_usd: float
    ebt_usd: float
    tax_usd: float
    cfads_usd: float
    equity_fcf_usd: float
    debt_service_usd: float
    dscr: Optional[float]
