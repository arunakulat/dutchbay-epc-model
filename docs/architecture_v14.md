# DutchBay EPC Model — v14 Architecture Overview

This document captures the canonical v14 architecture as enforced by CI, pytest, and lender-facing contract tests.

SECTION: Design philosophy
- Predictability: deterministic outputs for a given scenario config.
- Separation of concerns: loader → engine → analytics → exports.
- Testability: no silent defaults; schema and FX must be explicit.
- Lender confidence: IRR/DSCR/LLCR/PLCR definitions are stable and tested.

SECTION: High-level pipeline

scenarios/*.yaml / *.json
  |
  v
analytics.scenario_loader.load_scenario_config
  |
  v
dutchbay_v14chat.finance
  - cashflow.py
  - debt.py
  - irr.py
  - v14/epc_helper.py
  - v14/tax_calculator.py
  - v14/scenario_manager.py
  |
  v
analytics.scenario_analytics.ScenarioAnalytics
  |
  v
analytics.kpi_normalizer
  |
  v
analytics.export_helpers
  |
  v
CSV / JSONL / Excel / Executive Workbook

SECTION: Module responsibilities

analytics.scenario_loader
- Loads YAML/JSON scenario configs.
- Validates structure and FX mapping shape.
- Provides a canonical config dict to v14 finance modules.

dutchbay_v14chat.finance.cashflow
- Builds annual cashflow rows.
- Produces CFADS (Cash Flow Available for Debt Service).
- Handles tariff, opex, capex, and tax inputs via v14 helpers.

dutchbay_v14chat.finance.debt
- Builds amortization schedules.
- Computes interest, principal, and outstanding balances.
- Supports lender-style sculpting in the v14 layer.

dutchbay_v14chat.finance.irr
- Isolated IRR/NPV implementation for project and equity cashflows.
- Only module allowed to define IRR/NPV functions.

dutchbay_v14chat.finance.v14.epc_helper
- v14-specific helper logic around EPC and capex.
- Keeps engine-side transformations separate from analytics layer.

dutchbay_v14chat.finance.v14.tax_calculator
- Encapsulates tax calculations.
- Keep rules explicit and test-backed.

dutchbay_v14chat.finance.v14.scenario_manager
- Orchestrates the v14 finance pipeline for a single scenario.
- Acts as the “engine façade” for analytics.scenario_analytics.

analytics.scenario_analytics
- Wraps scenario_manager and the finance layer.
- Produces summary_df (one row per scenario) and timeseries_df (one row per year per scenario).

analytics.kpi_normalizer
- Normalizes raw metrics into stable KPI column names.
- Ensures that DSCR, LLCR, PLCR, IRR, and other board-facing metrics are consistently labelled.

analytics.export_helpers
- Handles all CSV, JSONL, and Excel exports.
- Responsible for wiring DataFrames into the Executive Workbook.

SECTION: Schema (v14 canonical sketch)

project:
  capacity_mw: float
  construction_months: int

tariff:
  lkr_per_kwh: float
  ppa_term_years: int

fx:
  start_lkr_per_usd: float
  annual_depr: float

capex:
  usd_total: float
  breakdown:
    epc_usd: float
    development_usd: float
    financing_fees_usd: float
    contingency_usd: float

opex:
  usd_per_year: float

debt:
  usd_amount: float
  tenure_years: int
  margin: float
  base_rate: float
  sculpt: str  # where applicable

SECTION: Versioning and legacy

- v14: Canonical path for all new work.
- v13: Legacy code, quarantined from CI for core flows.
- CI: GitHub Actions workflow ci-v14.yml runs regression smoke and coverage.

Status: v14 stable
Maintainers: DutchBay EPC Model Core Team
