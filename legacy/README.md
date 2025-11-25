# Legacy Code Archive

**Status:** Reference Only - DO NOT IMPORT IN PRODUCTION CODE

## Directory Structure

### `dutchbay_v13/`
Complete v13 codebase - **FULLY REPLACED by analytics/ and finance/ v14**

- `finance/` - Old cashflow, debt, IRR, metrics engines
- `cli.py` - Old CLI (replaced by `run_full_pipeline_v14.py`)
- `old_scenario_runner.py` - Old orchestrator (replaced by `analytics/scenario_analytics.py`)
- `visualization/` - Old charting (replaced by `analytics/export_helpers.py`)
- `reporting/` - Old markdown generation (replaced by `analytics/export_helpers.py`)

### `v14chat/`
Transitional v14 code - **SHADOWED by canonical v14 in analytics/ and finance/**

- Contains experimental modules now superseded by production v14
- All logic has been reviewed and integrated where appropriate

### `patch_archive/`
Temporary patch files - **FUNCTIONALITY MERGED INTO MAIN MODULES**

- `scenario_analytics_patched.py` - Improvements merged into `analytics/scenario_analytics.py`
- `debt_patched.py` - Improvements merged into `finance/debt_v14.py`
- Debug variants archived after validation

## Import Policy

❌ **FORBIDDEN:** No production code may import from `legacy/`

✅ **ALLOWED:** Compatibility tests marked with `@pytest.mark.legacy`

## Verification

Run this to ensure no forbidden imports:


python scripts/check_legacy_imports.py


Or manually:

rg "from legacy" analytics/ finance/ || echo "✅ No legacy imports"
rg "import dutchbay_v14chat" analytics/ finance/ || echo "✅ No v14chat imports"

## Removal Timeline

- **After v14 freeze** + 1 sprint of production stability
- **Requires:** All tests passing without legacy dependencies
- **Final check:** Coverage >65%, no regression in v14 suite

## History

- 2025-11-25: v14chat quarantined, patch files archived, utilities organized (Task 1, Sprint Day 5)
- 2025-11-11: v13 moved to legacy/ (initial migration)

## Note

FX/risk analytics modules (`fx_data_processor_dual_regime.py`, `risk_metrics.py`, `returns.py`) 
will be moved to `analytics/fx/` as part of Task 2 (modularization sprint).
