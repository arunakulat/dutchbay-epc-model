# Changelog

## v0.2.0 – 2025-11-21
- v14 CI baseline

All notable changes to this project will be documented here.

## [Unreleased]

## v0.2.3 - 2025-11-21

- Wire CI v14chat workflow



## v0.2.2 - 2025-11-21

- Fix regression_smoke date for macOS; v14-only smoke



## v0.2.1 - 2025-11-21

- Analytics exports + ScenarioAnalytics DF unit tests



## v0.2.1 - 2025-11-21

- v14 CI baseline – upstream auto




## [0.1.6] – 2025-11-20

### Added
- ExcelExporter: new `add_dataframe_sheet`, `add_conditional_formatting`, and
  `add_chart_image` helpers for richer, board-pack-friendly workbooks.
- Board-focused export: `export_summary_and_timeseries` now writes Summary/Timeseries
  plus optional DSCR/IRR views and auto-fits all sheets.
- ChartExporter: PNG chart helpers for DSCR time series and IRR histograms, safe to
  call in CLI/CI environments (no Excel dependency).
- ChartGenerator: lightweight KPI/NPV/DSCR/debt chart generator for Monte Carlo and
  sensitivity runs, returning file paths for downstream use.

### Fixed
- Tightened FX configuration validation in `scenario_loader`: scalar `fx` is now
  rejected with a clear error, enforcing the structured `fx` mapping policy in v14
  configs.
- Expanded export/analytics tests, raising coverage over the analytics and helper
  modules while keeping CLI and pipeline smokes green.

- TBD

## [1.0.0] - Initial public baseline
- CI: matrix (Ubuntu/Windows/macOS) + Python 3.10–3.12, workflow_dispatch, nightly, concurrency guard
- Pre-commit: black/flake8/isort/mypy + hygiene hooks
- Strict configs: .flake8, mypy.ini, pytest.ini (coverage ≥90% gate)
- Scenario runner: YAML → JSONL/CSV, multi-path `--scenarios`
- CLI: modes mapped (baseline/sensitivity/optimize/report/scenarios/api) + finance handlers + EPC
- Schema/docs: EPC parameters (ranges + units) in `schema.py`/`schema.md`
- Packaging: `python -m build`, smoke-install, artifact upload with versioned names
- Security/hygiene: CODEOWNERS, SECURITY.md, CONTRIBUTING.md


