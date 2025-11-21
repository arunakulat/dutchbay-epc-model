# Executive Workbook (v14) – Overview

Status: v14 stable (0.2.x)  
Owner: Analytics & Reporting

The **Executive Workbook** is the main Excel artifact produced by the v14
analytics pipeline for:

- Investment committees
- Lenders and credit teams
- Project boards / sponsors

It sits on top of the v14 analytics layer and presents:

- Clean, normalised KPIs per scenario
- Year-by-year DSCR and CFADS profiles
- Board-oriented views for quick comparison and stress interpretation

---

## Inputs

The workbook is built from two canonical pandas DataFrames:

1. **Summary layer (`summary_df`)**
   - One row per scenario.
   - Index: `scenario_name`.
   - Required columns (post-normalisation):
     - `scenario_name`
     - `project_irr`
     - `equity_irr`
     - `dscr_min`
     - `dscr_mean`
     - `llcr`
     - `plcr`
     - `total_cfads_usd`
     - `max_debt_usd`
     - `final_debt_usd`
     - `total_idc_usd`
     - `tariff_lkr` (or similar)
   - Optional but common:
     - COD year, project life, leverage ratio, etc.

2. **Timeseries layer (`timeseries_df`)**
   - One row per (scenario, year).
   - Required columns:
     - `scenario_name`
     - `year` (or `period_index` that can be mapped to year)
     - `dscr`
     - `cfads_lkr` (or equivalent)
     - `debt_service_lkr` (or equivalent)
   - May also include:
     - Principal/interest split
     - Tax flows
     - Other lender-relevant metrics.

Both DataFrames are expected to have been normalised via:

```python
from analytics.kpi_normalizer import normalise_kpis_for_export
summary_df, timeseries_df = normalise_kpis_for_export(summary_df, timeseries_df)
How the workbook is generated

The primary entrypoint is:
from analytics.executive_workbook import build_executive_workbook  # (see module)
from analytics.export_helpers import ExcelExporter

exporter = ExcelExporter("exports/v14_executive_workbook.xlsx")
build_executive_workbook(
    exporter=exporter,
    summary_df=summary_df,
    timeseries_df=timeseries_df,
)
Under the hood:
	•	analytics.executive_workbook:
	•	Assumes normalised schemas for summary_df and timeseries_df.
	•	Delegates low-level Excel mechanics to ExcelExporter.
	•	Adds board/IC views on top of the “raw” analytics exports.
	•	analytics.export_helpers.ExcelExporter:
	•	Writes:
	•	Summary sheet (scenario-level KPIs)
	•	Timeseries sheet (scenario-year DSCR/CFADS)
	•	When called with add_board_views=True, also adds:
	•	Board IRR/DSCR view(s)
	•	Optional chart-ready tables

The ScenarioAnalytics helper wires this together via:
from analytics.scenario_analytics import ScenarioAnalytics

sa = ScenarioAnalytics(
    scenarios_dir="scenarios",
    output_path="exports/v14_analytics.xlsx",
    strict=True,
)
summary_df, timeseries_df = sa.run(
    export_excel=True,
    export_charts=False,
)
When an output_path is provided:
	•	The Excel workbook is written to the given path.
	•	ExcelExporter may also add board-specific sheets depending on flags.

⸻

Sheet design (guidelines)

Summary sheet

Purpose: one-glance view of scenario quality.

Row = scenario; columns include:
	•	Identification:
	•	scenario_name
	•	Scenario description (if present)
	•	IRR / NPV:
	•	project_irr
	•	equity_irr
	•	Leverage / coverage:
	•	dscr_min
	•	dscr_mean
	•	llcr
	•	plcr
	•	Scale & tariff:
	•	capex_usd (or equivalent)
	•	tariff_lkr (or equivalent)
	•	Key debt stats:
	•	max_debt_usd
	•	final_debt_usd
	•	total_idc_usd

Sort order is typically by scenario_name, but board packs may filter/highlight
the current lender case.

Timeseries sheet

Purpose: enable DSCR/CFADS trend analysis.

Row = (scenario, year); columns include:
	•	scenario_name
	•	year (or period index)
	•	dscr (per-period)
	•	cfads_lkr
	•	debt_service_lkr
	•	Optional: principal/interest components

This sheet is intentionally “wide” and machine-friendly; it backs DSCR charts
and covenant checks.

⸻

Board / IC views

Board views are derived from the Summary/Timeseries layers and may include:
	•	DSCR heatmaps or traffic-light tables by scenario/year
	•	IRR vs tariff scatter plots
	•	One-pagers for the primary lender case

Implementation details (sheet names, chart layouts) are encapsulated inside
analytics.executive_workbook and analytics.export_helpers. The tests focus
on:
	•	Workbook creation (file exists, sheets are present)
	•	Schema expectations for Summary and Timeseries sheets

See:
	•	tests/test_export_smoke.py
	•	tests/api/test_export_helpers_v14.py

⸻

Usage patterns

Full lender case generation
python -m analytics.scenario_analytics \
  --scenarios-dir scenarios \
  --output exports/dutchbay_lendercase_v14.xlsx
Internal sandbox / what-if
	•	Duplicate an existing scenario YAML.
	•	Adjust tariff, leverage, or CAPEX.
	•	Run ScenarioAnalytics and open the resulting workbook.
	•	Compare IRR/DSCR profiles against the lender case.

⸻

Contract / stability

The executive workbook layer assumes:
	•	ScenarioAnalytics remains the canonical analytics entry point.
	•	summary_df and timeseries_df schemas remain compatible with
kpi_normalizer and exporter expectations.
	•	New metrics are added in a backwards compatible way (add columns, do not
rename or drop existing ones without updating tests and docs).

If you change:
	•	Column names, or
	•	The presence/shape of Summary / Timeseries sheets,

then you must:
	1.	Update this document.
	2.	Update tests (tests/test_export_smoke.py, related API tests).
	3.	Confirm CI (ci-v14.yml) is green.

