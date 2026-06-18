# Legacy v14 Test Archive

This directory contains test files that were retired during the v15 architecture refactor.

## Why These Tests Were Retired

### CASPER v14 Module Tests
- **Reason (HISTORICAL, NOW SUPERSEDED)**: This README originally claimed
  `analytics.casper.casper_payload` had a syntax error (IndentationError at
  line 71) blocking CASPER test imports. Sprint 18D investigation
  (2026-05-26) determined that claim was **inaccurate** — the file parses
  cleanly via `ast.parse` and has done since commits `5c44342`, `b635f74`,
  and `434b1ff` rewrote the function. The original claim predates those
  rewrites and was never refreshed.
- **Actual blocker (Sprint 18B → 18D)**: `casper_payload._scenario_summary_to_dict`
  read attributes (`ep.downside`, `.moic`, `.dpi`, `.rvpi`, `.tvpi`,
  `.average_coc`, `.payback_period_years`) that do not exist on the canonical
  `EquityPerformance` post-Sprint-18B, raising `AttributeError` on every
  real CASPER run. This contract-shape bug is fixed on branch
  `fix/casper-equity-performance-contract-alignment` (Sprint 18D).
- **Files affected**: Originally the canonical CASPER smoke, payload,
  tail-risk and contract tests were quarantined under a false-positive
  rule ("absolute IRR band assertions"). Two are revived on the Sprint 18D
  branch: `tests/analytics_layer/test_evaluation_casper_tail_risk.py` and
  `tests/api/test_casper_contract_freeze.py`.
- **Status**: Files in `tests/legacy_v14/` (this directory) remain retired
  for the v15 refactor reasons listed below.

### Legacy API Unit Tests
- **Reason**: These tests depend on internal APIs that were removed or refactored in v15
- **Examples**:
  - `test_export_helpers_v14.py` - expects `analytics.export_helpers` (module removed)
  - `test_fx_resolver_unit.py` - expects `_resolve_fx` helper (private API removed)
  - `test_evaluate_scenario_v14.py` - expects `_deep_merge_dicts` (refactored)
  - `test_equity_v14.py` - broken imports around equity v14 wiring
- **Status**: These files were already absent from the v15 branch

### CLI/Pipeline Smoke Tests
- **Reason**: High-maintenance black-box tests for older entry points and config schemas
- **Status**: Low diagnostic value for v15; better covered by focused unit/integration tests
- **Files**: `test_cli_v14_smoke.py`, `test_scenario_analytics_cli_v14_smoke.py`, `test_export_smoke.py`, etc.
- **Status**: Already absent from v15 branch

## What Would Be Required to Resurrect

1. **CASPER tests**: Already underway on branch
   `fix/casper-equity-performance-contract-alignment` (Sprint 18D). The
   contract-shape bug has been fixed and two canonical CASPER tests have
   been resurrected (tail-risk smoke + contract freeze). No syntax fix is
   required — the original IndentationError claim was inaccurate.
2. **Legacy API tests**: Either restore compatibility shims or rewrite tests against new v15 APIs.
3. **Smoke tests**: Update YAML fixtures and entry point calls to match v15 architecture.

## Current v15 Test Suite Focus

The active test suite now focuses on:
- **Core cashflow/tax/debt API tests**: `tests/api/test_cashflow_v14.py`, `test_tax_v14_lender_golden.py`, `test_covenants_v14.py`
- **Sensitivity and Monte Carlo analytics**: `tests/analytics_layer/test_sensitivity_v14*.py`, `test_monte_carlo_v14.py`
- **New metrics and equity IRR**: `tests/api/test_metrics_core_stats.py` (includes real equity IRR calculations)
- **Contract validation and schema guards**: Type-safe contracts for all analytics outputs
- **Generation modeling**: Multi-technology renewable energy production profiles

## Known Active Issues (Sprint 9)

1. **statutory.grid_loss_pct KeyError**: Sensitivity contract tests fail because scenario YAML is missing required `statutory.grid_loss_pct` field
   - **Fix**: Add `grid_loss_pct: 0.03` to `scenarios/dutchbay_lendercase_2025Q4.yaml` under `statutory:` section
   - **Alternative**: Make field optional in `finance/dutchbay_finmodel/statutory_profile.py`

2. **CASPER payload contract-shape bug (SUPERSEDES earlier syntax-error
   claim)**: The earlier wording in this section was inaccurate.
   `analytics/casper/casper_payload.py` parses cleanly — there is no
   IndentationError. The real defect was that `_scenario_summary_to_dict`
   read pre-Sprint-18B attributes off `EquityPerformance` that no longer
   exist on the canonical dataclass, raising `AttributeError` on every
   real CASPER run.
   - **Status**: Fixed on branch
     `fix/casper-equity-performance-contract-alignment` (Sprint 18D). The
     payload now reads legacy PE metrics from `ep.metadata` with `.get()`
     guards and synthesises the downside block from `MonteCarloResult`
     when present.
   - **Priority**: Resolved by Sprint 18D.

## Directory Structure

```
tests/legacy_v14/
├── README.md                      # This file
├── api/                          # Legacy API unit tests (if any moved here)
├── analytics_layer/              # Legacy analytics layer tests (if any moved here)
└── root/                         # Legacy top-level smoke tests (if any moved here)
```

## Date Retired

- **Date**: December 15, 2025, 02:48 AM IST
- **Branch**: refactor/v15-architecture
- **Sprint**: Sprint 9
- **Commit**: Pending (awaiting pytest.ini cleanup commit)

## How to Run Legacy Tests (If Needed)

To manually run legacy tests (if files exist here):

```bash
# Run all legacy tests
pytest tests/legacy_v14/ -v

# Run specific legacy test file
pytest tests/legacy_v14/api/test_casper_v14_smoke.py -v

# Run with coverage disabled (faster)
pytest tests/legacy_v14/ --override-ini="addopts=" -v
```

**Note**: Most legacy tests will fail due to missing modules or outdated APIs. This is expected.

---

**Maintained by**: DutchBay EPC Model Team
**Last updated**: 2026-05-26 (Sprint 18D — superseded the earlier inaccurate
IndentationError claim and pointed to the contract-alignment fix branch)
