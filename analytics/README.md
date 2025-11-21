# DutchBay EPC Model — Analytics Layer (v14)

The analytics layer provides the high-level KPIs, scenario aggregation, FX normalization, DSCR/LLCR/PLCR extraction, summary tables, and export interfaces above the v14 finance engine.

It is the bridge between scenario configs (YAML/JSON) and presentation outputs (CSV, JSONL, Excel).

SECTION: Modules
- scenario_loader.py: strict FX, canonical scenario config loading.
- scenario_analytics.py: runs the full pipeline, producing summary_df and timeseries_df.
- kpi_normalizer.py: KPI naming and extraction in a lender-friendly schema.
- export_helpers.py: CSV/JSONL/Excel exporters.
- executive_workbook.py: workbook orchestration (low coverage, v14.2 hardening target).

SECTION: Data flow (high level)
scenario.yaml / .json
  → analytics.scenario_loader.load_scenario_config
  → dutchbay_v14chat.finance (cashflow, debt, irr, v14 helpers)
  → analytics.scenario_analytics.ScenarioAnalytics.run
  → analytics.kpi_normalizer
  → analytics.export_helpers
  → CSV / JSONL / Excel / Executive workbook

SECTION: FX requirements
The analytics layer assumes **only structured FX mappings** at the top level:

fx:
  start_lkr_per_usd: 375.0
  annual_depr: 0.03

Scalar FX values (fx: 375.0) are rejected by tests and should never appear in v14 configs.

SECTION: Testing
Core analytics behaviour is covered by:
- tests/test_scenario_analytics_smoke.py
- tests/test_metrics_integration.py
- tests/api/test_kpi_normalizer.py
- tests/api/test_fx_resolver_unit.py
- tests/test_fx_config_strictness.py

These enforce:
- Strict FX schema (mapping only).
- Stable KPI column names for both summary_df and timeseries_df.
- End-to-end pipeline continuity under v14.

SECTION: Developer guidelines
- All KPI logic lives in analytics/core/metrics.py and analytics/kpi_normalizer.py.
- IRR/NPV logic is isolated in dutchbay_v14chat/finance/irr.py.
- Export logic stays in analytics/export_helpers.py (not in analytics or finance modules).
- New analytics features must ship with at least a smoke test and, ideally, a contract-style test on the DataFrame schema.

Status: Stable (v0.2.x)
Maintained by: DutchBay EPC Model Core Team
