# DutchBay_EPC_Model – v14 Analytics & Executive Report Snapshot

**Snapshot date:** 2025-11-20 16:58:27  
**Branch:** `v14chat-upgrade`  
**Context:** Hardening the v14 analytics layer, exports, and executive report wrapper (`make_executive_report.py`).

---

## 1. What’s now in place (this round)

### 1.1 Core analytics & FX strictness

- **Scenario loader**
  - `analytics/scenario_loader.py` is now the canonical entry for configs (YAML/JSON).
  - FX config tightened:
    - Scalar `fx: 300.0` is **explicitly rejected**.
    - Required mapping structure:  
      `fx: { start_lkr_per_usd: <float>, annual_depr: <float> }`  
    - Clear error messaging enforced via `tests/test_fx_config_strictness.py`:
      - Asserts `"Invalid FX configuration"` and mapping vs scalar guidance.
  - `load_scenario_config(path)` is the single, test‑covered loader used by the analytics layer.

- **Analytics versioning**
  - `analytics/__init__.py` minor version bumped to reflect the v14 analytics/export changes.

### 1.2 Export helpers (Excel + charts)

- **File:** `analytics/export_helpers.py`
- **ExcelExporter**
  - Lazily creates a `pandas.ExcelWriter` using `openpyxl` (no empty files).
  - Key methods:
    - `add_dataframe_sheet(sheet_name, df, freeze_panes=None, format_headers=True, auto_filter=True)`  
      - Writes a DataFrame to a sheet.
      - Optional header bolding, auto-filter, and freeze panes.
    - `export_summary_and_timeseries(summary_df, timeseries_df, summary_sheet="Summary", timeseries_sheet="Timeseries", add_board_views=True)`  
      - Main high‑level entry for ScenarioAnalytics.
      - Writes summary + timeseries sheets.
      - Optionally adds board‑friendly views.
      - Calls `autofit_all()` then saves workbook.
    - `autofit_all()`
      - Best‑effort column width adjustment using `openpyxl.utils.get_column_letter`.
      - Fully defensive; logs and continues if anything goes wrong.
  - **Board‑pack views** (`_add_board_friendly_views`):
    - DSCR view:
      - If columns include `scenario_name` and `dscr` (plus optional `year`/`period`), writes a `DSCR_View` sheet.
      - Renames `year` → `Year` or `period` → `Period` where present.
    - IRR view:
      - Auto‑detects IRR‑like columns in `summary_df` (any column whose name contains `"irr"`).
      - Writes `IRR_View` sheet if such columns exist and `scenario_name` is available.
      - Failure paths are logged, not raised (keeps CI/CLI robust).

- **ChartExporter**
  - Chart‑only helper that **does not touch Excel**.
  - Constructed with an **output directory**, e.g.  
    `ChartExporter(output_dir="exports/Executive_..._charts")`
  - Methods:
    - `_get_plt()` – lazy `matplotlib` import; logs and returns `None` if unavailable.
    - `export_dscr_chart(timeseries_df, scenario_name_column="scenario_name", dscr_column="dscr", output_file="dscr_series.png")`
      - Groups by scenario, plots DSCR by period.
      - Draws DSCR=1.0 reference line.
      - Logs and returns `None` if required columns or matplotlib are missing.
    - `export_irr_histogram(summary_df, irr_column="project_irr", output_file="project_irr_hist.png", bins=20)`
      - Simple histogram for IRR values from `summary_df`.
      - Logs and returns `None` when IRR column missing or data empty.
  - Behaviour is **environment‑tolerant**: in headless/no‑matplotlib environments, it no‑ops with logs rather than breaking the pipeline.

- **ChartGenerator**
  - Separate class for KPI‑style PNGs (used by API tests):
    - `plot_kpi_comparison(kpi_data, kpi_name, output_file)` – bar chart by scenario.
    - `plot_npv_distribution(npv_values, output_file, bins=20)` – NPV histogram.
  - Paths are resolved relative to an `output_dir` root.

### 1.3 Scenario analytics & v14 pipeline

- **Scenario analytics**
  - `analytics/scenario_analytics.py` is the v14 analytics coordinator.
  - Uses `load_scenario_config()` from `analytics.scenario_loader` for all scenario files.
  - Processes all YAML/JSON configs in a directory (e.g. `scenarios/`) and returns:
    - `summary_df`
    - `timeseries_df`
  - Integrated with the new `ExcelExporter` via test `tests/test_scenario_analytics_smoke.py`.

- **v14 finance surface**
  - v14 layer continues to be reached through:
    - `dutchbay_v14chat/finance/v14/scenario_manager.py` (patched in this round).
    - `dutchbay_v14chat/finance/v14/epc_helper.py` (now tracked and tested via `tests/api/test_epc_helper_v14.py`).
  - Debt, cashflow, metrics modules are still the core workhorses; we’ve hardened the surface and added tests but not changed core financial logic in this pass.

### 1.4 make_executive_report.py – thin wrapper

- **File:** `make_executive_report.py`
- Current behaviour:
  - CLI arguments:
    - `-c/--config` – path to a single scenario config (default `scenarios/dutchbay_lendercase_2025Q4.yaml`).
    - `-o/--excel-output` – output Excel path (defaults to `exports/Executive_<stem>.xlsx`).
    - `--allow-legacy-fx` – toggles `strict_fx_config` (default is **strict**).
  - Workflow:
    1. Resolve `config_path`, `scenario_id` (= stem of config), and `scenarios_dir` (= parent of config).
    2. Instantiate `ScenarioAnalytics` with:
       - `scenarios_dir=str(scenarios_dir)`  
       - `output_path=None`  
       - `strict=args.strict_fx_config`
    3. Run analytics: `summary_df, timeseries_df = analytics.run()`.
    4. Filter both DataFrames **by `scenario_id` if `scenario_name` exists**; else log warnings and fall back to unfiltered DataFrames.
    5. Use `ExcelExporter(excel_output)` to write:
       - `Summary` sheet
       - `Timeseries` sheet
       - Optional `DSCR_View` / `IRR_View` sheets.
    6. Create charts using a separate directory:
       - `charts_dir = exports/Executive_<stem>_charts`
       - `ChartExporter(output_dir=charts_dir)`
       - Call low‑level chart methods (`export_dscr_chart`, `export_irr_histogram`).
  - Result (current run):
    - Excel is successfully generated:  
      `exports/Executive_dutchbay_lendercase_2025Q4.xlsx`
    - Chart exporter currently logs that DSCR/IRR columns are missing, so no PNGs yet (see TODOs).

### 1.5 Tests, coverage & CI

- **New / key tests added**
  - `tests/api/test_export_helpers_v14.py`
    - E2E smoke for `ExcelExporter` (sheets, conditional formatting, chart image embedding hooks).
    - ChartGenerator smokes for DSCR/debt plotters.
  - `tests/test_export_smoke.py`
    - High‑level smoke over the export layer and its integration with analytics results.
  - `tests/test_scenario_analytics_smoke.py`
    - Validates the v14 analytics pipeline (summary + timeseries creation).
  - `tests/test_fx_config_strictness.py`
    - Enforces scalar‑FX rejection and clear error messages.
  - A full suite of v14 finance tests (already committed this round):
    - `tests/api/test_cashflow_module.py`
    - `tests/api/test_cashflow_tax_and_life.py`
    - `tests/api/test_epc_helper_v14.py`
    - `tests/api/test_irr_core.py`
    - `tests/api/test_irr_module.py`
    - `tests/api/test_metrics_module.py`
    - `tests/api/test_scenario_manager_smoke.py`
    - `tests/api/test_tax_calculator_v14.py`
    - `tests/api/test_v14_lender_suite.py`
    - `tests/test_cli_v14_smoke.py`
    - `tests/test_v14_pipeline_smoke.py`
- **Coverage snapshot (last full run)**  
  - Total coverage ≈ **69%** with a required threshold of **60%** (per `pytest.ini`).  
  - v14 analytics and export helpers are covered by multiple smokes and API tests.

- **CI / fast-lane**
  - `.github/workflows/ci_v14_fastlane.yml` added:
    - Fast regression path for v14 analytics and CLI smokes.
    - Intended to run before any heavier full-matrix CI.
  - `pytest.ini` updated to:
    - Include `tests` and `dutchbay_v14chat/tests` under `testpaths`.
    - Enforce a minimum coverage threshold.

---

## 2. Current workflows (how to run things)

### 2.1 Local analytics & tests

From repo root:

```bash
# Full v14 + legacy test suite with coverage
pytest

# Focused v14 analytics & export layer smokes
pytest -k "export or scenario_analytics" --maxfail=1
```

### 2.2 Lender-case pipeline run

```bash
# Using canonical v14 lender case
python run_full_pipeline.py --config scenarios/dutchbay_lendercase_2025Q4.yaml
```

(Exact CLI flags may evolve; this reflects the current script semantics.)

### 2.3 Executive report generation

```bash
# Default lender case
python make_executive_report.py

# Explicit config and output
python make_executive_report.py   --config scenarios/dutchbay_lendercase_2025Q4.yaml   --excel-output exports/Executive_dutchbay_lendercase_2025Q4.xlsx
```

Outputs:
- Excel: `exports/Executive_dutchbay_lendercase_2025Q4.xlsx`
- Charts (directory): `exports/Executive_dutchbay_lendercase_2025Q4_charts/` (currently structured but not yet populated with DSCR/IRR due to missing columns).

---

## 3. Files & paths that matter for v14 analytics

This is the “where to look” map for the next refactor round.

### 3.1 Analytics layer

- `analytics/__init__.py` – version, public exports.
- `analytics/scenario_loader.py` – canonical config loader, FX strictness.
- `analytics/scenario_analytics.py` – v14 scenario aggregation & KPI computation.
- `analytics/export_helpers.py` – ExcelExporter, ChartExporter, ChartGenerator.

### 3.2 v14 finance surface

- `dutchbay_v14chat/finance/v14/epc_helper.py` – EPC helpers for v14.
- `dutchbay_v14chat/finance/v14/scenario_manager.py` – orchestrates cashflow/debt/metrics in v14.

### 3.3 Scenarios

- Canonical lender case:
  - `scenarios/dutchbay_lendercase_2025Q4.yaml`  (renamed from `full_model_variables_updated.yaml`)
- Supporting cases:
  - `scenarios/edge_extreme_stress.yaml`
  - `scenarios/example_a.yaml`
  - `scenarios/example_a_old.yaml`
  - `scenarios/example_b.json`

### 3.4 Tests

- API & unit tests under `tests/api/` (cashflow, debt, metrics, export helpers, tax, v14 scenario manager, etc.).
- Smokes and integration:
  - `tests/test_export_smoke.py`
  - `tests/test_scenario_analytics_smoke.py`
  - `tests/test_v14_pipeline_smoke.py`
  - `tests/test_cli_v14_smoke.py`
  - `tests/test_fx_config_strictness.py`

### 3.5 CI / docs

- `.github/workflows/ci_v14_fastlane.yml` – fast CI job for v14.
- `pytest.ini` – testpaths, coverage thresholds.
- `DutchBay_v14_Analytics_README.md` – high-level doc for this surface.
- `README_v14_analytics_layer.md` – additional analytics-layer documentation.

---

## 4. Known rough edges / behaviour to fix next

This is the state you observed in the latest run of `make_executive_report.py`:

1. **No `scenario_name` column in analytics outputs**
   - `summary_df` does *not* yet carry a `scenario_name` column.
   - `timeseries_df` also lacks `scenario_name` in your current run.
   - Consequences:
     - `make_executive_report.py` falls back to unfiltered data for export.
     - `ExcelExporter`’s IRR view logs: `IRR view export failed: "['scenario_name'] not in index"`.
     - ChartExporter complains about missing `dscr` / `project_irr` columns.

2. **KPI column naming not yet canonical**
   - IRR:
     - The intended canonical column is `project_irr` (and possibly `equity_irr`), but some code/tests may still rely on other names.
   - DSCR:
     - We conceptually want a clear DSCR time-series column (e.g. `dscr` or `dscr_period`) in `timeseries_df`.
     - Summary DF should expose at least a `min_dscr`/`dscr_min` style KPI for one-line views.
   - Until the analytics layer standardises these, ChartExporter and the executive wrapper have to guess and currently give up.

3. **ChartExporter integration**
   - `make_executive_report.py` currently calls low-level chart methods directly.
   - There is **no high-level `export_charts(...)` method** implemented on `ChartExporter` yet, so we can’t encapsulate DSCR/IRR auto-detection and naming logic in one place.

4. **Duplicate “batch analysis complete” logging**
   - You see two “Batch analysis complete” messages in the latest run because both the analytics layer and the wrapper emit summary logs.
   - Cosmetic, but worth cleaning once we touch `ScenarioAnalytics.run()` again.

---

## 5. Prioritised TODO list for the next refactor round

### P0 – Make analytics outputs board- and chart-ready

1. **Inject `scenario_name` into analytics outputs**
   - In `ScenarioAnalytics.process_scenario()` (or equivalent):
     - Add a `scenario_name` column with the scenario id (e.g. stem of yaml filename) to:
       - The per-scenario summary rows.
       - The per-scenario timeseries rows.
   - Ensure `ScenarioAnalytics.run()` concatenates these while preserving `scenario_name`.
   - Update / add tests:
     - Extend `tests/test_scenario_analytics_smoke.py` to assert the presence and correctness of `scenario_name` in both DataFrames.

2. **Standardise KPI column names at the analytics layer**
   - Decide and enforce:
     - `summary_df` should expose, at minimum:
       - `scenario_name`
       - `project_irr` (and optionally `equity_irr`)
       - `min_dscr` or `dscr_min`
       - NPV, LLCR, PLCR etc. as currently modelled.
     - `timeseries_df` should include:
       - `scenario_name`
       - A DSCR timeseries column, canonically named `dscr` (or a clearly mapped equivalent).
   - Once agreed:
     - Update the analytics computations to emit these canonical names.
     - Adjust tests under `tests/api/test_metrics_module.py`, `tests/api/test_v14_lender_suite.py`, and smokes as needed.

3. **Harden ExcelExporter’s IRR view**
   - In `_add_board_friendly_views`:
     - Handle IRR view robustly when `scenario_name` is present:
       - Use `["scenario_name", *irr_candidates]` safely.
     - If `scenario_name` is missing (temporary), consider:
       - Either skip the IRR view with a clear log, or
       - Emit an IRR view without scenario labels using index as a fallback (temporary).

### P1 – Chart exporter ergonomics & executive wrapper clean-up

4. **Add a high-level `export_charts` method to ChartExporter**
   - Signature idea:  
     `export_charts(summary_df, timeseries_df, scenario_id=None)`
   - Responsibilities:
     - Resolve which IRR column to use:
       - Prefer `project_irr`, fall back to any `"irr"`-like column if needed.
     - Resolve which DSCR column to use:
       - Prefer `dscr` in timeseries; optionally accept `"dscr_period"`, etc.
     - Filter by `scenario_id` when a `scenario_name` column exists.
     - Call `export_dscr_chart()` and `export_irr_histogram()` with resolved parameters.
   - Add tests to `tests/api/test_export_helpers_v14.py` to use this high-level API.

5. **Update `make_executive_report.py` to use `export_charts`**
   - Replace the direct calls:
     - `chart_exporter.export_dscr_chart(filtered_timeseries)`  
     - `chart_exporter.export_irr_histogram(filtered_summary)`  
   - With a single call:
     - `chart_exporter.export_charts(filtered_summary, filtered_timeseries, scenario_id=scenario_id)`
   - This keeps the wrapper wafer-thin and pushes the KPI detection logic into the export helper.

6. **Tidy analytic logging**
   - Remove or de-duplicate the double “Batch analysis complete” logs by centralising them in either:
     - `ScenarioAnalytics.run()`, or
     - The CLI wrapper (but not both).

### P2 – Future polish and xlwings-based template path (optional later)

7. **(Later) Introduce an xlwings-powered executive template path**
   - Separate script, e.g. `make_executive_template_report.py`:
     - Use xlwings to populate a pre-formatted board template with:
       - Summary KPIs
       - DSCR & IRR charts wired to Excel tables
       - Printable PDF export.
   - Treat the current XlsxWriter/openpyxl-based `make_executive_report.py` as the “standardised, CI-safe” path and xlwings as the “presentation-grade” path.

8. **(Later) Expand ChartGenerator for more board KPIs**
   - NPV vs. tariff curves.
   - IRR sensitivity waterfalls.
   - DSCR heatmaps by year vs. scenario.

---

## 6. Git / tagging notes for this snapshot

- Branch in use: `v14chat-upgrade`
- Staged key changes include:
  - New analytics tests and helpers (`analytics/export_helpers.py`, `analytics/scenario_loader.py`, v14 tests).
  - New CI workflow: `.github/workflows/ci_v14_fastlane.yml`.
  - Lender case scenario renamed to `scenarios/dutchbay_lendercase_2025Q4.yaml`.
  - New documentation: `DutchBay_v14_Analytics_README.md`, `README_v14_analytics_layer.md`.
  - v14 finance helper: `dutchbay_v14chat/finance/v14/epc_helper.py`.
  - New smokes and API tests under `tests/` and `tests/api/`.

**Suggested tagging pattern after commit & push:**
- Commit message: e.g.  
  `feat(v14): analytics/export layer + executive report wrapper`
- Tag (annotated): e.g.  
  `git tag -a v14-analytics-0.1.0 -m "v14 analytics + export + executive report alpha"`  
  `git push origin v14chat-upgrade --tags`

You can now re-upload this document into a fresh ChatGPT thread and treat it as the authoritative “state of play” for the v14 analytics/export/executive layer.
