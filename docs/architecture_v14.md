# DutchBay v14 Architecture – Finance & Analytics

Status: v14 stable (0.2.x)  
Scope: Cashflow, debt, KPIs, analytics, exports

This document describes the **canonical v14 pipeline** used by the DutchBay EPC
model, from scenario configs through to Excel/board outputs.

The goals of this architecture are:

- **Predictability** – one clear path from config → DSCR/IRR → exports.
- **Separation of concerns** – finance engine, analytics orchestration, and
  exports are decoupled.
- **Testability** – each layer is covered by fast unit and smoke tests.
- **Lender friendliness** – outputs align with typical project finance
  requirements (CFADS, DSCR, LLCR, PLCR, IRR, NPV, FX behaviour).

---

## High-level data flow

```text
scenarios/*.yaml / *.json
        │
        ▼
analytics.scenario_loader.load_scenario_config
        │
        ▼
dutchbay_v14chat.finance.cashflow.build_annual_rows
        │
        ▼
dutchbay_v14chat.finance.debt.apply_debt_layer
        │
        ▼
analytics.core.metrics.calculate_scenario_kpis / compute_kpis
        │
        ▼
analytics.scenario_analytics.ScenarioAnalytics._build_dataframes
 (summary_df, timeseries_df with scenario_name everywhere)
        │
        ▼
analytics.kpi_normalizer.normalise_kpis_for_export
        │
        ▼
analytics.export_helpers.ExcelExporter / ChartExporter
        │
        ▼
analytics.executive_workbook (board / IC views)
Key points:
	•	v14 is canonical – all lender- and board-facing work should use the v14
path, not legacy v13.
	•	Scenario configs are the single source of truth – everything begins at
scenarios/*.yaml or *.json.
	•	Analytics is read-only – it calls into the finance engine but does not
mutate configs or business logic.

⸻

Layers in detail

1. Scenario configs (scenarios/)
	•	YAML / JSON files describing:
	•	Project meta: capacity, COD year, life, etc.
	•	Tariff: lkr_per_kwh, term, type.
	•	CAPEX and OPEX breakdowns.
	•	Debt structure.
	•	FX assumptions via a mapping (not a scalar).
	•	Examples:
	•	scenarios/example_a.yaml
	•	scenarios/example_a_old.yaml
	•	scenarios/dutchbay_lendercase_2025Q4.yaml
	•	scenarios/edge_extreme_stress.yaml

FX invariant
	•	No scalar fx values are allowed.
	•	Valid form:
fx:
  start_lkr_per_usd: 300.0
  annual_depr: 0.03
	•	Enforced by:
	•	Loader logic
	•	tests/test_fx_config_strictness.py
	•	Scenario fixtures

⸻

2. Scenario loader (analytics.scenario_loader)

Responsibilities:
	•	Locate and open the scenario file.
	•	Determine format (YAML vs JSON).
	•	Parse to a Python dict.
	•	Inject defaults and log key assumptions (e.g. FX).
	•	Enforce FX mapping shape and raise clear errors on invalid structure.

This is the only supported entry for configs into the v14 pipeline.

⸻

3. Finance engine (dutchbay_v14chat.finance)

cashflow.py
	•	Builds annual_rows – one dict per year with:
	•	Revenue
	•	OPEX
	•	CFADS (e.g. cfads_usd, LKR variants)
	•	Other per-period metrics
	•	Encodes all business rules about:
	•	Start-up, ramp-up, degradation
	•	Tax base interactions prior to debt

debt.py
	•	Applies the debt layer on top of CFADS.
	•	Produces:
	•	dscr_series
	•	Principal and interest schedules
	•	max_debt_usd, final_debt_usd, total_idc_usd
	•	DSCR series is intentionally raw – analytics cleans it up later.

The finance engine is treated as a black box by analytics; tests exist at
this layer as well.

⸻

4. Metrics (analytics/core/metrics.py)

Single canonical KPI surface:
	•	calculate_scenario_kpis(...) – for v14 callers.
	•	compute_kpis(config, annual_rows, debt_result) – thin adapter for
legacy/analytics callers.

Responsibilities:
	•	Clean DSCR series:
	•	Drop None, non-numeric, NaN/inf, and non-positive values.
	•	Compute DSCR stats:
	•	dscr_min, dscr_max, dscr_mean, dscr_median
	•	Build CFADS series (USD) from:
	•	Explicit cfads_series_usd, or
	•	annual_rows[*]["cfads_usd"], or
	•	A degenerate zero series of the same length as dscr_series.
	•	Compute CFADS stats and aggregates:
	•	cfads_min, cfads_max, cfads_mean, cfads_median
	•	total_cfads_usd, final_cfads_usd, mean_operational_cfads_usd
	•	Valuation logic:
	•	If valuation={"npv": ..., "irr": ...} is provided, pass through.
	•	Otherwise:
	•	Compute equity investment from CAPEX and debt raised.
	•	Build equity cashflows: time-0 equity outflow + CFADS.
	•	Use numpy_financial to compute irr and npv.

⸻

5. Scenario analytics (analytics.scenario_analytics)

ScenarioAnalytics is the batch driver.
	•	Discovers scenario files under a directory (*.yaml, *.yml, *.json).
	•	Runs the full v14 path for each scenario:
	1.	Load config via load_scenario_config.
	2.	Build annual_rows via cashflow.
	3.	Apply debt layer.
	4.	Compute KPIs via metrics.
	5.	Optionally derive EPC breakdown via epc_breakdown_from_config.
	•	Collects results into ScenarioResult objects:
	•	name (scenario name)
	•	config_path
	•	kpis (flat dict)
	•	annual_rows
	•	debt_result

DataFrame construction:
	•	summary_df:
	•	One row per scenario.
	•	Index is scenario_name.
	•	Column scenario_name is also present explicitly.
	•	timeseries_df:
	•	One row per (scenario, year).
	•	Always includes scenario_name.
	•	dscr column:
	•	If a per-period DSCR column exists (derived from CFADS/debt), use it.
	•	If not, propagate a scalar (e.g. dscr_min) as a flat line.
	•	Final normalisation:
	•	Both DataFrames pass through
kpi_normalizer.normalise_kpis_for_export(...).

⸻

6. Exports (analytics.export_helpers & analytics.executive_workbook)

analytics.export_helpers
	•	ExcelExporter:
	•	Writes a workbook with at least Summary and Timeseries sheets.
	•	When add_board_views=True, adds lender/board-specific sheets.
	•	ChartExporter (optional):
	•	Exports DSCR / IRR charts to a directory.
	•	Uses scenario_name for labels.

analytics.executive_workbook
	•	Higher-level composition for board / IC packs.
	•	Consumes the normalised DataFrames and workbook from ExcelExporter.
	•	Adds:
	•	Board-level IRR/DSCR summaries
	•	Scenario comparisons
	•	Optional charts (via ChartExporter)

⸻

Testing and CI

Key tests:
	•	tests/test_v14_pipeline_smoke.py – end-to-end v14 pipeline.
	•	tests/test_scenario_analytics_smoke.py – analytics layer.
	•	tests/test_metrics_integration.py – metrics behaviour.
	•	tests/test_fx_config_strictness.py – FX mapping enforcement.
	•	tests/test_export_smoke.py and tests/api/test_export_helpers_v14.py – exports.
	•	tests/api/test_executive_workbook_import.py – import safety.

CI (GitHub Actions):
	•	Workflow: .github/workflows/ci-v14.yml
	•	quick-smoke job:
	•	python -m pytest --no-cov -k "cli and smoke"
	•	full-regression job:
	•	Runs ./scripts/regression_smoke.sh with coverage.
	•	Coverage threshold:
	•	Currently set around 65%, with actual coverage > 75%.

