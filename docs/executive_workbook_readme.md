# DutchBay EPC Model — Executive Workbook (v14)

The Executive Workbook is the Excel-based presentation layer for boards, ICs, and lenders. It assembles the analytics outputs into a compact, human-readable workbook.

SECTION: Generation flow

scenario.yaml / .json
  → analytics.scenario_loader.load_scenario_config
  → dutchbay_v14chat.finance (cashflow, debt, irr, v14 helpers)
  → analytics.scenario_analytics.ScenarioAnalytics.run
  → analytics.kpi_normalizer
  → analytics.export_helpers
  → Executive workbook (.xlsx)

SECTION: Core sheets (target layout)

Summary sheet
- Columns:
  - scenario_name
  - project_irr
  - equity_irr
  - dscr_min
  - llcr
  - plcr
  - capex_usd
  - tariff_lkr
- Purpose:
  - One row per scenario.
  - Snapshot view for boards and lenders.

Timeseries sheet
- Columns:
  - scenario_name
  - year
  - dscr
  - cfads_lkr
  - debt_service_lkr
- Purpose:
  - Per-year DSCR and cash coverage picture.
  - Input for DSCR charts in the workbook.

SECTION: Export rules

- All workbook exports must go through analytics.export_helpers.
- File naming convention: executive_workbook_<scenario>_v14.xlsx
- IRRs should be formatted as percentages in Excel.
- DSCR values should be rounded to 2–3 decimals for presentation.
- Scenario names must be stable and match summary_df/timeseries_df.

SECTION: Tests and validation

Current tests:
- tests/api/test_export_helpers_v14.py
- tests/test_export_smoke.py

These ensure:
- Workbook can be generated end-to-end for key scenarios.
- Core sheets are present and non-empty.
- Basic schema expectations are met.

Planned extensions (v14.2+):
- Sheet-level contract tests for column names.
- Golden-sample workbook comparison for the lender case.

SECTION: Developer notes

- Keep workbook code thin; heavy logic belongs in analytics and finance layers.
- Do not implement IRR, DSCR, or FX logic inside the workbook module.
- Any new sheet should ship with at least a smoke test.
- When changing KPI names in analytics, update both tests and this document.

Status: v14 stable
