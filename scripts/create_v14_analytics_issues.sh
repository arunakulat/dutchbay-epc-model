#!/usr/bin/env bash
set -euo pipefail

# Milestone name must already exist (or gh will prompt).
MILESTONE="v14 Analytics & Executive Report Upgrade – 2025-11-Cycle"

echo "Using milestone: $MILESTONE"
echo "Creating issues via gh…"
echo

############################################
# Issue 1 – scenario_name everywhere
############################################

gh issue create \
  --title "P0: Add scenario_name to ScenarioAnalytics outputs" \
  --label v14 --label analytics --label P0 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE1'
### Goal

Ensure all analytics outputs carry an explicit `scenario_name` so downstream exports, charts, and reports can filter and label scenarios deterministically.

### Tasks

- [ ] In `ScenarioAnalytics`:
  - [ ] Add `scenario_name` to `summary_df` before concat.
  - [ ] Add `scenario_name` to `timeseries_df` before concat.
  - [ ] Use config stem (filename without extension) as canonical `scenario_name`.
- [ ] Ensure `ScenarioAnalytics.run()` returns frames with `scenario_name` for all scenarios.
- [ ] Update ExcelExporter to rely on `scenario_name` (no guessing).
- [ ] Update tests (e.g. `test_scenario_analytics_smoke.py`) to assert:
  - [ ] `scenario_name` present in both frames.
  - [ ] Filtering by `scenario_name` yields non-empty slices.

### Acceptance Criteria

- `summary_df` and `timeseries_df` always include `scenario_name`.
- Executive report and Excel views filter by `scenario_name` directly.
ISSUE1
)"

echo "Created: P0: Add scenario_name to ScenarioAnalytics outputs"
echo

############################################
# Issue 2 – Canonical KPI column names
############################################

gh issue create \
  --title "P0: Canonicalise KPI column names in analytics layer" \
  --label v14 --label analytics --label KPIs --label P0 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE2'
### Goal

Freeze a canonical naming scheme for key KPIs so exports/charts can rely on stable columns.

### Canonical naming

**summary_df**
- `scenario_name`
- `project_irr`
- `equity_irr` (optional)
- `dscr_min`
- NPV / LLCR / PLCR aligned with v14 spec

**timeseries_df**
- `scenario_name`
- `year` (or `period`, but pick one as primary)
- `dscr`

### Tasks

- [ ] Update KPI logic to emit canonical names.
- [ ] Remove/deprecate ambiguous names (`irr`, `irr_project`, `dscr_period`, etc.).
- [ ] Keep temporary aliases only if absolutely needed and mark as legacy.
- [ ] Update tests (`test_metrics_module.py` + v14 lender tests) to:
  - [ ] Assert canonical columns exist.
  - [ ] Preserve numeric results.

### Acceptance Criteria

- Analytics outputs consistently use `project_irr`, `equity_irr` (if used), `dscr_min`, `dscr`.
- No new code depends on non-canonical KPI names.
ISSUE2
)"

echo "Created: P0: Canonicalise KPI column names in analytics layer"
echo

############################################
# Issue 3 – Harden ExcelExporter board views
############################################

gh issue create \
  --title "P0: Harden ExcelExporter board views (DSCR_View, IRR_View)" \
  --label v14 --label exports --label excel --label P0 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE3'
### Goal

Make `DSCR_View` and `IRR_View` deterministic and robust, aligned with canonical KPIs, and never crash when columns are missing.

### Requirements

**DSCR_View**
- Expects: `scenario_name`, `dscr`, `year` or `period`.
- Builds DSCR by period per scenario.
- Logs and skips if required columns are missing (no exceptions).

**IRR_View**
- Expects: `scenario_name`, `project_irr` (primary).
- Falls back to any `*irr*` column if `project_irr` absent.
- Logs and skips if nothing usable is found.

### Tasks

- [ ] Update ExcelExporter to use canonical names.
- [ ] Implement graceful failure (log + continue).
- [ ] Extend tests (e.g. `test_export_helpers_v14.py`) to assert:
  - [ ] `DSCR_View` created when inputs exist.
  - [ ] `IRR_View` created when `project_irr` exists.
  - [ ] Missing columns → no crash.

### Acceptance Criteria

- Exports contain `Summary`, `Timeseries`, `DSCR_View`, `IRR_View` when appropriate.
- CI smokes confirm no unhandled ExcelExporter errors.
ISSUE3
)"

echo "Created: P0: Harden ExcelExporter board views (DSCR_View, IRR_View)"
echo

############################################
# Issue 4 – ChartExporter.export_charts
############################################

gh issue create \
  --title "P1: Add ChartExporter.export_charts unified entry point" \
  --label v14 --label analytics --label charts --label P1 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE4'
### Goal

Expose a single `export_charts(...)` on ChartExporter that knows how to:
- Resolve canonical DSCR/IRR columns.
- Filter by `scenario_name`.
- Emit a minimal chart set.

### API

Target signature:

```python
def export_charts(self, summary_df, timeseries_df, scenario_id=None):
    ...
```

### Behaviour

- [ ] Filter frames by `scenario_name == scenario_id` when provided.
- [ ] Resolve:
  - [ ] DSCR from `dscr`.
  - [ ] IRR from `project_irr`, else any `*irr*` column.
- [ ] Produce:
  - [ ] DSCR line chart over time.
  - [ ] IRR histogram or bar chart.
- [ ] Log and return cleanly if required columns are missing.

### Tests

- [ ] Add tests (extend `test_export_helpers_v14.py` or new file) to cover:
  - [ ] Happy path (charts created).
  - [ ] Scenario filtering works.
  - [ ] Missing KPI columns → no crash.

### Acceptance Criteria

- `export_charts()` is the single chart entry point.
- `make_executive_report` uses it instead of custom logic.
ISSUE4
)"

echo "Created: P1: Add ChartExporter.export_charts unified entry point"
echo

############################################
# Issue 5 – Thin make_executive_report.py
############################################

gh issue create \
  --title "P1: Thin make_executive_report.py and delegate to ChartExporter" \
  --label v14 --label exports --label cli --label P1 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE5'
### Goal

Turn `make_executive_report.py` into a thin orchestration layer that delegates chart logic to ChartExporter and avoids duplicated detection heuristics.

### Tasks

- [ ] Replace direct chart calls with:
  ```python
  chart_exporter.export_charts(filtered_summary, filtered_timeseries, scenario_id=scenario_id)
  ```
- [ ] Keep column/KPI detection inside ChartExporter/analytics, not in the script.
- [ ] Preserve FX strictness (no scalar `fx`, honour strict/legacy flags).
- [ ] Add smoke test:
  - [ ] Run lender case.
  - [ ] Assert Excel file + at least one chart PNG exist.

### Acceptance Criteria

- `make_executive_report.py` mainly wires ScenarioAnalytics, ExcelExporter, ChartExporter.
- Lender case report generation passes in CI.
ISSUE5
)"

echo "Created: P1: Thin make_executive_report.py and delegate to ChartExporter"
echo

############################################
# Issue 6 – De-duplicate logging
############################################

gh issue create \
  --title "P1: De-duplicate 'Batch analysis complete' logging" \
  --label v14 --label logging --label P1 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE6'
### Goal

Remove duplicate "Batch analysis complete" (or similar) log lines emitted by both ScenarioAnalytics and CLI, leaving a single clear completion message.

### Tasks

- [ ] Choose the single owner of the completion log (ScenarioAnalytics or CLI).
- [ ] Remove duplicate log calls.
- [ ] Verify a single completion message appears in a normal run.

### Acceptance Criteria

- Logs show one clean "batch done" message.
- No behavioural change beyond reduced noise.
ISSUE6
)"

echo "Created: P1: De-duplicate 'Batch analysis complete' logging"
echo

############################################
# Issue 7 – Construction + IDC + grace tests
############################################

gh issue create \
  --title "P1.5: Construction + IDC + grace-period regression tests" \
  --label v14 --label finance-core --label tests --label P1.5 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE7'
### Goal

Lock in v14 construction, IDC capitalisation, and grace-period behaviour with explicit regression tests.

### Scope

- Construction timeline (e.g. -2, -1, 0, …).
- IDC capitalised vs expensed.
- Grace period: when principal repayments start.

### Tasks

- [ ] Create a small toy scenario (YAML/JSON) with simple capex/debt.
- [ ] Add tests (e.g. `test_debt_v14_idc_and_grace.py`) that:
  - [ ] Run v14 pipeline or relevant modules.
  - [ ] Assert:
    - [ ] Capex + IDC placement across years.
    - [ ] Total principal + IDC equals expected base.
    - [ ] First principal year matches grace rules.
- [ ] Document assumptions in test comments.

### Acceptance Criteria

- Any change in construction/IDC/grace behaviour that breaks spec fails CI immediately.
ISSUE7
)"

echo "Created: P1.5: Construction + IDC + grace-period regression tests"
echo

############################################
# Issue 8 – Tax behaviour golden test
############################################

gh issue create \
  --title "P1.5: Tax behaviour golden test for lender case" \
  --label v14 --label finance-core --label tax --label tests --label P1.5 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE8'
### Goal

Pin v14 tax logic for the lender case (holiday + depreciation) with a golden regression test.

### Tasks

- [ ] Select canonical lender case scenario config.
- [ ] Add test (e.g. `test_tax_v14_lender_golden.py`) that:
  - [ ] Runs lender case via v14 pipeline.
  - [ ] Extracts:
    - [ ] Tax holiday length/timing.
    - [ ] Depreciation schedule (method + amounts).
  - [ ] Asserts these match current v14 spec.
- [ ] Optionally store small golden snapshot (CSV/JSON) for comparison.

### Acceptance Criteria

- Lender case tax behaviour is locked.
- Any change in tax holiday or depreciation profile causes a failing test.
ISSUE8
)"

echo "Created: P1.5: Tax behaviour golden test for lender case"
echo

############################################
# Issue 9 – Docs & developer quickstart
############################################

gh issue create \
  --title "P2: v14 analytics docs & developer quickstart" \
  --label v14 --label docs --label P2 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE9'
### Goal

Document v14 analytics + export layer so contributors can run, extend, and debug without spelunking.

### Tasks

- [ ] Add/update `README_v14_analytics_layer.md` to cover:
  - [ ] ScenarioAnalytics flow (inputs → summary_df, timeseries_df).
  - [ ] Canonical KPI names.
  - [ ] Roles of ExcelExporter and ChartExporter.
- [ ] Add “Developer quickstart”:
  - [ ] Run v14 pipeline end-to-end.
  - [ ] Generate executive report for lender case.
- [ ] Cross-reference:
  - [ ] `V14_UPGRADE_SPECIFICATION.md`
  - [ ] `DutchBay_v14_Analytics_Snapshot_2025-11-20.md`
- [ ] Keep docs in sync with behaviour post-milestone.

### Acceptance Criteria

- New dev can follow docs to:
  - Run analytics.
  - Understand outputs.
  - Generate a basic executive report.
ISSUE9
)"

echo "Created: P2: v14 analytics docs & developer quickstart"
echo

############################################
# Issue 10 – CI tightening
############################################

gh issue create \
  --title "P2: CI tightening for v14 lender suite and coverage" \
  --label v14 --label ci --label tests --label P2 \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE10'
### Goal

Focus CI on v14 and ensure lender suite + analytics + export smokes run efficiently.

### Tasks

- [ ] Ensure `test_metrics_module.py` is included in v14 lender CI suite.
- [ ] Confirm fast-lane CI job (e.g. `v14-fastlane`) runs:
  - [ ] v14 CLI smokes.
  - [ ] v14 lender suite.
  - [ ] Analytics/export smokes.
- [ ] Keep coverage threshold realistic but v14-focused (not legacy v13-heavy).
- [ ] Add CHANGELOG entry (e.g. `v14-analytics-0.2.0`) summarising:
  - [ ] KPI canonicalisation.
  - [ ] scenario_name propagation.
  - [ ] Export/chart hardening.

### Acceptance Criteria

- CI clearly shows v14-specific checks.
- v14 lender + analytics + export paths run on every relevant PR.
ISSUE10
)"

echo "Created: P2: CI tightening for v14 lender suite and coverage"
echo

############################################
# Issue 11 – Optional xlwings mode
############################################

gh issue create \
  --title "P2-Optional: xlwings 'board presentation mode' executive report" \
  --label v14 --label excel --label xlwings --label enhancement --label P2-optional \
  --milestone "$MILESTONE" \
  --body "$(cat << 'ISSUE11'
### Goal

Add an optional “board presentation mode” using xlwings and a template workbook, without touching the CI-safe headless path.

### Constraints

- Headless `make_executive_report.py` remains canonical for CI.
- xlwings is optional (extra dependency only).

### Tasks

- [ ] Create separate script/module (e.g. `make_board_deck.py`) that:
  - [ ] Opens template via xlwings.
  - [ ] Writes summary KPIs and charts into curated layout.
  - [ ] Optionally exports PDF.
- [ ] Reuse ScenarioAnalytics + ExcelExporter/ChartExporter outputs.
- [ ] Keep xlwings out of CI dependencies (use extras in `pyproject.toml` / `requirements`).

### Acceptance Criteria

- Users with xlwings can generate a polished board deck.
- CI still runs fine without xlwings.
ISSUE11
)"

echo "Created: P2-Optional: xlwings 'board presentation mode' executive report"
echo
echo "All 11 issues created (assuming gh calls succeeded)."
