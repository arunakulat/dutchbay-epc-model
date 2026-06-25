from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CashflowParams:
    """Normalized parameter set for v14 CFADS calculations.

    This is the canonical, engine-facing parameter surface for cashflow_v14.
    It is intentionally lean and numeric, with units as follows:

    - project_life_years: int (years)
    - capacity_mw: float (MW)
    - capacity_factor: float (decimal, 0–1)
    - degradation: float (decimal per year, e.g. 0.005 = 0.5%/yr)
    - grid_loss_pct: float (decimal share of gross, 0–1)
    - tariff_lkr_per_kwh: float (LKR per kWh)
    - opex_usd_per_year: float (USD per year, base/year-1)
    - opex_escalation_pct: float (decimal per year, e.g. 0.025 = 2.5%/yr O&M inflation
      in USD terms; the LKR cost then escalates further via the FX curve). Default 0.0.
    - curtailment_pct: float (decimal, 0–1). An INCREMENTAL financed grid-curtailment
      haircut on delivered energy, applied after grid_loss_pct. Default 0.0 — the
      physical/embedded curtailment is already in the bankable net AEP / capacity_factor;
      this lever models ADDITIONAL constrained-grid curtailment for stress/risk analysis
      (see analytics.core.sensitivity_runner + the canonical scenario's monte_carlo block).
    - success_fee_pct, env_surcharge_pct, social_levy_pct: decimals (0–1)
    - corporate_tax_rate: float (decimal, 0–1)
    - risk_haircut_pct: float (decimal, 0–1)

    NOTE: the tax-detail inputs (enhanced_capital_allowance_pct, depreciation_years,
    tax_holiday_years, tax_holiday_start_year) are NOT CashflowParams fields — the live
    depreciation/holiday path resolves + validates them via finance.cashflow_v14_tax
    .TaxConfig (single source of truth). Parallel CashflowParams fields here were dead
    second sources of truth (no computation ever read them) and were removed (CCCDIR).
    """

    project_life_years: int
    capacity_mw: float
    capacity_factor: float
    degradation: float
    grid_loss_pct: float
    tariff_lkr_per_kwh: float
    opex_usd_per_year: float
    success_fee_pct: float
    env_surcharge_pct: float
    social_levy_pct: float
    corporate_tax_rate: float
    risk_haircut_pct: float
    opex_escalation_pct: float = 0.0
    curtailment_pct: float = 0.0


__all__ = ["CashflowParams"]
