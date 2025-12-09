# Changelog

## v0.2.0 – 2025-11-21
- v14 CI baseline

All notable changes to this project will be documented here.

## [Unreleased]

## v0.3.0 - 2025-12-09

- Sprint 9: Complete Integration Analysis & Design (CASPER/GWTF Compliant)



## v0.3.x - 2025-12-08

- Sprint 9 – v14 Monte Carlo front door + regression guard



## v0.3.x - 2025-12-08

- Sprint 9 – v14 Monte Carlo front door + regression guard



## v0.3.0 - 2025-12-07

- Sprint 8 – v14 lender pipeline hardened (tests green, coverage 59.82%)



## v0.3.0 - 2025-12-07

- Sprint 8 – v14 lender pipeline hardened (tests green, coverage 59.82%)



## v0.3.0 - 2025-12-07

- Sprint 8 – v14 lender pipeline hardened (tests green, coverage 59.82%)



## v0.3.0 - 2025-12-05

- feat: add PySAM sandbox module (isolated, optional, validation-first)

- analytics/pysam_sandbox: Optional PySAM wrapper (mypy+ruff clean)
- scripts/validate_pysam_offline.py: Validation script (<5% deviation gate)
- Uses importlib.util.find_spec for PySAM availability (ruff-compliant)
- Compliance: ARCH-01, TYPE-01, FIN-01, FIN-02, R10, R17

Pre-commit: black/ruff/isort auto-formatted 36 files
Status: Day 1 complete - ready for Day 2-3 validation phase



## v0.3.0 - 2025-12-05

- feat: add PySAM sandbox module (isolated, optional, validation-first)

- analytics/pysam_sandbox: Optional PySAM wrapper (mypy+ruff clean)
- scripts/validate_pysam_offline.py: Validation script (<5% deviation gate)
- Uses importlib.util.find_spec for PySAM availability (ruff-compliant)
- Compliance: ARCH-01, TYPE-01, FIN-01, FIN-02, R10, R17

Status: Day 1 complete - ready for Day 2-3 validation phase



## v2.6.0 - 2025-12-04

- Sprint 8 - IRR ring-fence + v14 sensitivity API (mypy-clean core)



## v2.6.0 - 2025-12-04

- Sprint 8 - IRR ring-fence + v14 sensitivity API (mypy-clean core)



## v2.5.2 - 2025-12-04

- Sprint 8 – v14 equity + cashflow contracts + run_full_pipeline_v14 wiring



## v2.5.2 - 2025-12-04

- Sprint 8 – v14 equity + cashflow contracts + run_full_pipeline_v14 wiring



## v2.5.2 - 2025-12-04

- Sprint 8 – v14 equity + cashflow contracts + run_full_pipeline_v14 wiring



## v2.5.2 - 2025-12-04

- Sprint 8 – v14 equity + cashflow contracts + run_full_pipeline_v14 wiring



## v2.5.0 - 2025-12-04

- Sprint 7 – v14 pipeline + sensitivity + metrics typing



## v0.2.3 - 2025-11-26

- v14 pipeline surface frozen; CLI shim wired



## v0.2.3.1 - 2025-11-24

- docs: Add Thread Migration Package suite for seamless AI context restoration



## v1.0.0 - 2025-11-24

- docs: Add comprehensive Thread Migration Package



## v1.0.0 - 2025-11-24

- docs: Add comprehensive Thread Migration Package



## v0.2.3.1 - 2025-11-24

- docs: Add Thread Migration Package suite for seamless AI context restoration



## v0.2.3 - 2025-11-23

- ScenarioAnalytics batch + Excel export helpers hardening



## v0.2.2 - 2025-11-23

- IRR engine hardening + v14 KPI refactor (project NPV/IRR, DSCR sanitiser)



## v0.2.2 - 2025-11-23

- IRR engine hardening + v14 KPI refactor (project NPV/IRR, DSCR sanitiser)



## v0.2.2 - 2025-11-22

- v14 cashflow & metrics mypy-clean spine



## v0.2.2 - 2025-11-22

- Promote v14 finance modules + schema guard for bad_missing_tax



## v0.2.8 - 2025-11-22

- Document v14 analytics, architecture, and executive workbook



## v0.2.6 - 2025-11-22

- Top-up coverage with finance.utils tests



## v0.2.6 - 2025-11-21

- Docs: add v14 dev workflow



## v0.2.6 - 2025-11-21

- Docs: analytics + architecture + executive workbook



## v0.2.5 - 2025-11-21

- Lock FX schema to structured mapping + scenario guard tests



## v0.2.5 - 2025-11-21

- Tighten v14 coverage gates; CI + local green



## v0.2.5 - 2025-11-21

- CI v14chat green; v14 stack stabilized



## v0.2.4 - 2025-11-21

- CI v14chat: add .venv reset step



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
