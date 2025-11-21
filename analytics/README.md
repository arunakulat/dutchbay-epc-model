# DutchBay v14 Analytics Layer

Status: Stable (v0.2.x)  
Maintained by: DutchBay EPC Model Core Team

This package contains the **v14 analytics layer** for the DutchBay EPC model.

It sits on top of the v14 finance/cashflow engine and provides:

- Batch scenario analytics (multiple YAML/JSON configs)
- KPI calculation (NPV, IRR, DSCR, CFADS stats)
- Normalised summary/timeseries DataFrames
- Excel and chart exports for the executive workbook

The heavy lifting for cashflows and debt remains in `dutchbay_v14chat.finance`.
Analytics is **read-only**: it orchestrates, summarises and exports.

---

## Module overview

### `analytics.scenario_loader`

Shared loader for scenario configs.

- Accepts both YAML (`*.yaml`, `*.yml`) and JSON (`*.json`) files.
- Normalises the config, applies defaults and logging.
- Enforces the **FX mapping** rule:
  - `fx` must be a mapping/dict, not a scalar.
  - Expected keys:
    - `fx.start_lkr_per_usd` (float)
    - `fx.annual_depr` (float, depreciation rate)
- Tests: see `tests/test_fx_config_strictness.py`.

### `analytics.scenario_analytics`

Batch orchestrator for v14 analytics.

- Discovers scenarios under a directory (`*.yaml`, `*.yml`, `*.json`).
- Loads each config via `load_scenario_config`.
- Runs:
  - `dutchbay_v14chat.finance.cashflow.build_annual_rows`
  - `dutchbay_v14chat.finance.debt.apply_debt_layer`
  - `analytics.core.metrics.compute_kpis`
- Aggregates results into:
  - `summary_df` (one row per scenario)
  - `timeseries_df` (one row per scenario-year)
- Ensures **scenario naming is canonical**:
  - `summary_df` index = `scenario_name`
  - `summary_df["scenario_name"]` is also an explicit column
  - `timeseries_df["scenario_name"]` present for all rows
- DSCR handling:
  - Uses DSCR series from the debt layer when available.
  - If not available, falls back to a scalar like `dscr_min` to populate a flat `dscr` line per scenario.
- Hands off to exporters:
  - Excel: `analytics.export_helpers.ExcelExporter`
  - Charts: `analytics.export_helpers.ChartExporter` (optional, degrades gracefully if not available)

### `analytics/core/metrics.py`

Core KPI calculator.

- Single canonical entry point:
  - `calculate_scenario_kpis(...)`
- Responsibilities:
  - Clean DSCR series (drop `None`, non-finite, zero or negative).
  - Compute DSCR summary stats:
    - `dscr_min`, `dscr_max`, `dscr_mean`, `dscr_median`
  - Build CFADS series (from `annual_rows` or explicit series).
  - Compute CFADS stats:
    - `cfads_min`, `cfads_max`, `cfads_mean`, `cfads_median`
    - `total_cfads_usd`, `final_cfads_usd`, `mean_operational_cfads_usd`
  - Compute valuation if not provided:
    - Equity investment = CAPEX – debt raised
    - `npv` and `irr` via `numpy_financial` on equity cashflows
  - Pass through selected debt stats:
    - `max_debt_usd`, `final_debt_usd`, `total_idc_usd`
- Backwards compatibility adapter:
  - `compute_kpis(config, annual_rows, debt_result)` wraps
    `calculate_scenario_kpis(...)` for legacy callers.

### `analytics/kpi_normalizer.py`

Final “shape and naming” normaliser.

- Accepts:
  - `summary_df`, `timeseries_df`
- Responsibilities:
  - Ensure canonical column names (e.g. `scenario_name`, `project_irr`, `equity_irr`, `dscr_min`, `llcr`, `plcr`).
  - Apply any per-scenario KPI renames or shims so that:
    - The executive workbook
    - The CLI
    - The tests  
    all see a consistent schema.

### `analytics/export_helpers.py`

Helpers for exporting analytics outputs.

- `ExcelExporter`:
  - Writes a multi-sheet workbook with at least:
    - `Summary`
    - `Timeseries`
  - When called with `add_board_views=True`, adds board-friendly views
    (e.g. IRR/DSCR slices) used by the executive workbook.
- `ChartExporter` (optional):
  - Exports DSCR/IRR charts (and other visuals) to a directory.
  - Scenario labels come from `scenario_name`.

### `analytics/executive_workbook.py`

High-level workbook builder for board/IC packs.

- Consumes the **normalised** `summary_df` and `timeseries_df`.
- Adds board-oriented sheets and views (e.g. IRR/DSCR dashboards).
- Uses `analytics.export_helpers.ExcelExporter` as the primary backend.

---

## Config & FX invariants

The analytics layer assumes:

- **Config schema**
  - Scenarios live in `scenarios/` as YAML or JSON.
  - Key blocks: `project`, `tariff`, `capex`, `opex`, `debt`, `fx`, etc.
- **FX rule (strict)**
  - No scalar `fx` values anywhere (e.g. `fx: 375.0` is invalid).
  - Only the mapping form is allowed:
    ```yaml
    fx:
      start_lkr_per_usd: 300.0
      annual_depr: 0.03
    ```
  - Enforced via:
    - `analytics.scenario_loader`
    - Tests in `tests/test_fx_config_strictness.py`
    - Scenario fixtures in `scenarios/*.yaml`

---

## Running analytics

**Batch analytics via CLI:**

```bash
python -m analytics.scenario_analytics \
  --scenarios-dir scenarios \
  --output exports/v14_analytics.xlsx \
  --charts
	•	--no-excel: skip Excel export, just run analytics.
	•	--charts: also export DSCR/IRR charts (if ChartExporter is available).
	•	--strict (default): fail fast on first scenario error.

Programmatic use:
from pathlib import Path
from analytics.scenario_analytics import ScenarioAnalytics

sa = ScenarioAnalytics(
    scenarios_dir=Path("scenarios"),
    output_path=Path("exports/v14_analytics.xlsx"),
    strict=True,
)

summary_df, timeseries_df = sa.run(
    export_excel=True,
    export_charts=False,
)
Tests & coverage

Key tests:
	•	tests/test_scenario_analytics_smoke.py
	•	tests/test_metrics_integration.py
	•	tests/test_fx_config_strictness.py
	•	tests/api/test_kpi_normalizer.py
	•	tests/api/test_export_helpers_v14.py
	•	tests/api/test_executive_workbook_import.py (import safety)

Full v14 regression smoke:
./scripts/regression_smoke.sh
# or
python -m pytest
Current coverage (v0.2.x):
	•	Overall: ~75%
	•	Analytics modules: substantially covered, with remaining gaps focused on
workbook/charts “nice-to-have” paths rather than core lender flows.

