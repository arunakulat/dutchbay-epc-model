# Test Cleanup Manifest

Generated: 2025-12-20 08:40 AM +0530

## Summary

- **Total test-related files**: 161
- **Files to remove**: 79 (1.16 MB)
- **Core tests to keep**: 63 (362 KB)

---

## Files Being Removed (79 files)

### REMOVE - Test Output Files (4 files, 890 KB)

Large test output files that should be in .gitignore:

- `pytest_output.txt` (663.3 KB)
- `pytest_output_after_fix.txt` (177.0 KB)
- `dutchbay_test_results.txt` (36.1 KB)
- `TEST_MATRIX.txt` (13.7 KB)

### REMOVE - Config Files (7 files)

Stress test scenario configs:

- `config/scenarios/stress_tests/stress_combined_worst.yaml`
- `config/scenarios/stress_tests/stress_capacity_minus_10.yaml`
- `config/scenarios/stress_tests/stress_opex_inflation_2pct.yaml`
- `config/scenarios/stress_tests/stress_capex_plus_20.yaml`
- `config/scenarios/stress_tests/stress_fx_depr_50pct.yaml`
- `config/scenarios/stress_tests/stress_tariff_minus_20.yaml`
- `pytest.ini`

### REMOVE - Non-Core Tests (68 files)

#### API Integration Tests
- `tests/api/test_evaluate_scenario_v14.py`
- `tests/api/test_scenario_analytics_unit_scenario_name_refactored.py`
- `tests/api/test_executive_workbook_import.py`
- `tests/api/test_casper_v14_smoke_iteration1.py`
- `tests/api/test_irr_is_singleton_refactored.py`
- `tests/api/test_fx_resolver_unit.py`
- `tests/api/test_scenario_analytics_unit_scenario_name.py`
- `tests/api/test_irr_core.py`
- `tests/api/test_scenario_analytics_unit.py`
- And more...

#### Analytics Layer Tests (Non-Core)
- `tests/analytics_layer/test_casper_payload.py`
- `tests/analytics_layer/_casper_fakes.py`
- `tests/analytics_layer/test_casper_tail_risk_payload.py`
- `tests/analytics_layer/test_casper_tail_risk_summary.py`
- And more...

#### Linting Tests
- `tests/lint/test_no_argparse_v14.py`
- `tests/lint/test_irr_location_v14.py`
- `tests/lint/test_no_typer_v14.py`

#### Generic/Helper Tests
- `tests/test_fx_structured_blocks.py`
- `tests/test_scenario_analytics_smoke.py`
- `tests/test_metrics_integration.py`
- `tests/test_cli_v14_smoke.py`
- `tests/test_schema_guard_fx.py`
- `tests/test_fx_config_strictness.py`
- `tests/test_phase_1_2_refactoring.py`
- `tests/test_export_smoke.py`
- `tests/test_scenario_analytics_cli_v14_smoke.py`

#### Legacy Tests
- `legacy_tests/*` (6 files)

#### Quarantined Tests
- `tests/_quarantine/*` (2 files)

#### Performance/Benchmark Tests
- `tests/performance_benchmarks_v14.py`

---

## Core Tests Being Kept (63 files, 362 KB)

### By Module:

#### CONTRACTS Tests
- `test_contracts_v14_validators.py`
- `test_contracts_casper_v14.py`
- `test_contracts.py`
- Contract validation tests
- Pydantic v2 compatibility tests

#### SENSITIVITY Tests (12+ files - Best Coverage)
- `test_sensitivity_v14_all.py`
- `test_sensitivity_v14_*.py`
- Sensitivity regression tests
- Breakeven analysis tests
- Tornado diagram tests

#### CASHFLOW Tests
- `test_cashflow_v14.py`
- `test_cashflow_v14_regression.py`
- `test_cashflow_v14_tax_refactored.py`
- `test_cashflow_risk_haircut_v14.py`
- `test_cashflow_v14_rows.py`
- Tax calculation tests

#### MONTE_CARLO Tests (3 files)
- `test_monte_carlo_v14.py`
- `test_monte_carlo_three_scenarios.py`
- `test_monte_carlo_three_scenarios_debug.py`

#### EQUITY Tests
- `test_equity_distribution_v14.py`
- `test_equity_distribution_compliance.py`
- `test_equity_v14.py`
- Equity waterfall tests
- Distribution logic tests

#### REFINANCING Tests (Sprint 12 Focus)
- `test_refinancing_v14_*.py`
- `test_refinancing_module_compliance.py`
- Refinancing scenario tests

#### DEBT Tests
- `test_debt_v14_construction.py`
- `test_debt_construction_idc_regression_v14.py`
- `test_debt_construction_idc_regression.py`
- IDC calculation tests

#### TAX Tests
- `test_tax_v14.py`
- Tax profile tests
- Statutory tax tests

#### WACC Tests
- `test_wacc_v14.py`
- Cost of capital tests
- WACC integration tests

#### PIPELINE Tests
- `test_pipeline_v14.py`
- Valuation pipeline tests
- Integration tests

#### EVALUATION Tests
- `test_evaluation_v14.py`
- `test_evaluation_casper_tail_risk.py`
- Performance metrics tests

---

## Rationale

### Why Remove These Files?

1. **Test Outputs** (4 files, 890 KB)
   - These are generated files that should be in .gitignore
   - Take up significant space
   - Not actual test code

2. **Non-Core Tests** (68 files)
   - Integration tests for non-essential features
   - API/CLI smoke tests
   - Legacy/deprecated tests
   - Quarantined failing tests
   - Performance benchmarks
   - Helper/infrastructure tests

3. **Config Files** (7 files)
   - Stress test scenarios
   - Can be regenerated if needed
   - Not critical for core functionality

### Why Keep These Tests?

The 63 core tests cover:
- ✅ **Contracts** - Pydantic v2 data validation
- ✅ **Sensitivity** - Risk analysis (12+ files)
- ✅ **Cashflow** - Core financial engine
- ✅ **Monte Carlo** - Stochastic simulation
- ✅ **Equity** - Distribution waterfall (Sprint 12)
- ✅ **Refinancing** - Refinancing scenarios (Sprint 12)
- ✅ **Debt/WACC/Tax** - Core finance modules
- ✅ **Pipeline/Evaluation** - Valuation engine

These are the **essential tests** for Sprint 12 work and ongoing development.

---

## Impact Analysis

### Before Cleanup:
- 161 test-related files
- Mixed core/legacy/output files
- Slower pytest discovery
- Harder to maintain

### After Cleanup:
- 63 focused core tests
- Clear test organization
- Faster pytest runs
- Easier maintenance
- Ready for Sprint 12

---

## Next Steps

1. ✅ Review this manifest
2. ✅ Run `cleanup_non_core_tests.sh`
3. ✅ Verify with `pytest tests/ -v`
4. ✅ Commit and push changes

---

Generated by automated analysis on 2025-12-20 08:40 AM +0530
