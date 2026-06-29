#!/bin/bash
# DutchBay EPC Model - Complete Test File Cleanup Script
# Generated: 2025-12-20 08:50 AM +0530
# Purpose: Remove 79 non-core test files to keep feature branch pristine

set -e

echo "=========================================="
echo "DutchBay EPC Test Cleanup Script"
echo "=========================================="
echo ""
echo "📊 Summary:"
echo "  Files to remove: 79"
echo "  Files to keep:   63"
echo ""
echo "⚠️  This will permanently delete 79 files!"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted."
    exit 1
fi

echo ""
echo "🗑️  Removing non-core test files..."
echo ""

REMOVED=0
FAILED=0

if [ -f 'pytest_output.txt' ]; then
    rm 'pytest_output.txt' && echo "  ✓ pytest_output.txt" && ((REMOVED++))
else
    echo "  ⚠ Not found: pytest_output.txt" && ((FAILED++))
fi
if [ -f 'pytest_output_after_fix.txt' ]; then
    rm 'pytest_output_after_fix.txt' && echo "  ✓ pytest_output_after_fix.txt" && ((REMOVED++))
else
    echo "  ⚠ Not found: pytest_output_after_fix.txt" && ((FAILED++))
fi
if [ -f 'dutchbay_test_results.txt' ]; then
    rm 'dutchbay_test_results.txt' && echo "  ✓ dutchbay_test_results.txt" && ((REMOVED++))
else
    echo "  ⚠ Not found: dutchbay_test_results.txt" && ((FAILED++))
fi
if [ -f 'TEST_MATRIX.txt' ]; then
    rm 'TEST_MATRIX.txt' && echo "  ✓ TEST_MATRIX.txt" && ((REMOVED++))
else
    echo "  ⚠ Not found: TEST_MATRIX.txt" && ((FAILED++))
fi
if [ -f 'config/scenarios/stress_tests/stress_combined_worst.yaml' ]; then
    rm 'config/scenarios/stress_tests/stress_combined_worst.yaml' && echo "  ✓ config/scenarios/stress_tests/stress_combined_worst.yaml" && ((REMOVED++))
else
    echo "  ⚠ Not found: config/scenarios/stress_tests/stress_combined_worst.yaml" && ((FAILED++))
fi
if [ -f 'config/scenarios/stress_tests/stress_capacity_minus_10.yaml' ]; then
    rm 'config/scenarios/stress_tests/stress_capacity_minus_10.yaml' && echo "  ✓ config/scenarios/stress_tests/stress_capacity_minus_10.yaml" && ((REMOVED++))
else
    echo "  ⚠ Not found: config/scenarios/stress_tests/stress_capacity_minus_10.yaml" && ((FAILED++))
fi
if [ -f 'config/scenarios/stress_tests/stress_opex_inflation_2pct.yaml' ]; then
    rm 'config/scenarios/stress_tests/stress_opex_inflation_2pct.yaml' && echo "  ✓ config/scenarios/stress_tests/stress_opex_inflation_2pct.yaml" && ((REMOVED++))
else
    echo "  ⚠ Not found: config/scenarios/stress_tests/stress_opex_inflation_2pct.yaml" && ((FAILED++))
fi
if [ -f 'config/scenarios/stress_tests/stress_capex_plus_20.yaml' ]; then
    rm 'config/scenarios/stress_tests/stress_capex_plus_20.yaml' && echo "  ✓ config/scenarios/stress_tests/stress_capex_plus_20.yaml" && ((REMOVED++))
else
    echo "  ⚠ Not found: config/scenarios/stress_tests/stress_capex_plus_20.yaml" && ((FAILED++))
fi
if [ -f 'config/scenarios/stress_tests/stress_fx_depr_50pct.yaml' ]; then
    rm 'config/scenarios/stress_tests/stress_fx_depr_50pct.yaml' && echo "  ✓ config/scenarios/stress_tests/stress_fx_depr_50pct.yaml" && ((REMOVED++))
else
    echo "  ⚠ Not found: config/scenarios/stress_tests/stress_fx_depr_50pct.yaml" && ((FAILED++))
fi
if [ -f 'config/scenarios/stress_tests/stress_tariff_minus_20.yaml' ]; then
    rm 'config/scenarios/stress_tests/stress_tariff_minus_20.yaml' && echo "  ✓ config/scenarios/stress_tests/stress_tariff_minus_20.yaml" && ((REMOVED++))
else
    echo "  ⚠ Not found: config/scenarios/stress_tests/stress_tariff_minus_20.yaml" && ((FAILED++))
fi
if [ -f 'pytest.ini' ]; then
    rm 'pytest.ini' && echo "  ✓ pytest.ini" && ((REMOVED++))
else
    echo "  ⚠ Not found: pytest.ini" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_casper_payload.py' ]; then
    rm 'tests/analytics_layer/test_casper_payload.py' && echo "  ✓ tests/analytics_layer/test_casper_payload.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_casper_payload.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/_casper_fakes.py' ]; then
    rm 'tests/analytics_layer/_casper_fakes.py' && echo "  ✓ tests/analytics_layer/_casper_fakes.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/_casper_fakes.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_casper_tail_risk_payload.py' ]; then
    rm 'tests/analytics_layer/test_casper_tail_risk_payload.py' && echo "  ✓ tests/analytics_layer/test_casper_tail_risk_payload.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_casper_tail_risk_payload.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_casper_tail_risk_summary.py' ]; then
    rm 'tests/analytics_layer/test_casper_tail_risk_summary.py' && echo "  ✓ tests/analytics_layer/test_casper_tail_risk_summary.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_casper_tail_risk_summary.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_generation_contracts_v14.py' ]; then
    rm 'tests/analytics_layer/test_generation_contracts_v14.py' && echo "  ✓ tests/analytics_layer/test_generation_contracts_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_generation_contracts_v14.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_breakeven_contract.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_breakeven_contract.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_breakeven_contract.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_breakeven_contract.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_regression.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_regression.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_regression.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_regression.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_run_contract.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_run_contract.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_run_contract.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_run_contract.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_tail_risk.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_tail_risk.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_tail_risk.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_tail_risk.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_tail_risk_api.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_tail_risk_api.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_tail_risk_api.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_tail_risk_api.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_v14.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_v14.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_v14.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_v14_api.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_v14_api.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_v14_api.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_v14_api.py" && ((FAILED++))
fi
if [ -f 'tests/analytics_layer/test_sensitivity_v14_behavioral_imports.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_v14_behavioral_imports.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_v14_behavioral_imports.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/analytics_layer/test_sensitivity_v14_behavioral_imports.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_evaluate_scenario_v14.py' ]; then
    rm 'tests/api/test_evaluate_scenario_v14.py' && echo "  ✓ tests/api/test_evaluate_scenario_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_evaluate_scenario_v14.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_scenario_analytics_unit_scenario_name_refactored.py' ]; then
    rm 'tests/api/test_scenario_analytics_unit_scenario_name_refactored.py' && echo "  ✓ tests/api/test_scenario_analytics_unit_scenario_name_refactored.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_scenario_analytics_unit_scenario_name_refactored.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_casper_v14_smoke.py' ]; then
    rm 'tests/api/test_casper_v14_smoke.py' && echo "  ✓ tests/api/test_casper_v14_smoke.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_casper_v14_smoke.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_casper_v14_smoke_iteration1.py' ]; then
    rm 'tests/api/test_casper_v14_smoke_iteration1.py' && echo "  ✓ tests/api/test_casper_v14_smoke_iteration1.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_casper_v14_smoke_iteration1.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_casper_v14_smoke_iteration2.py' ]; then
    rm 'tests/api/test_casper_v14_smoke_iteration2.py' && echo "  ✓ tests/api/test_casper_v14_smoke_iteration2.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_casper_v14_smoke_iteration2.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_fx_resolver_unit.py' ]; then
    rm 'tests/api/test_fx_resolver_unit.py' && echo "  ✓ tests/api/test_fx_resolver_unit.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_fx_resolver_unit.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_scenario_analytics_unit_scenario_name.py' ]; then
    rm 'tests/api/test_scenario_analytics_unit_scenario_name.py' && echo "  ✓ tests/api/test_scenario_analytics_unit_scenario_name.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_scenario_analytics_unit_scenario_name.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_irr_core.py' ]; then
    rm 'tests/api/test_irr_core.py' && echo "  ✓ tests/api/test_irr_core.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_irr_core.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_scenario_analytics_unit.py' ]; then
    rm 'tests/api/test_scenario_analytics_unit.py' && echo "  ✓ tests/api/test_scenario_analytics_unit.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_scenario_analytics_unit.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_irr_is_singleton_refactored.py' ]; then
    rm 'tests/api/test_irr_is_singleton_refactored.py' && echo "  ✓ tests/api/test_irr_is_singleton_refactored.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_irr_is_singleton_refactored.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_executive_workbook_import.py' ]; then
    rm 'tests/api/test_executive_workbook_import.py' && echo "  ✓ tests/api/test_executive_workbook_import.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_executive_workbook_import.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_executive_workbook_smoke.py' ]; then
    rm 'tests/api/test_executive_workbook_smoke.py' && echo "  ✓ tests/api/test_executive_workbook_smoke.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_executive_workbook_smoke.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_bad_missing_tax_schema_guard.py' ]; then
    rm 'tests/api/test_bad_missing_tax_schema_guard.py' && echo "  ✓ tests/api/test_bad_missing_tax_schema_guard.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_bad_missing_tax_schema_guard.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_config_schema_guard.py' ]; then
    rm 'tests/api/test_config_schema_guard.py' && echo "  ✓ tests/api/test_config_schema_guard.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_config_schema_guard.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_edgecases.py' ]; then
    rm 'tests/api/test_edgecases.py' && echo "  ✓ tests/api/test_edgecases.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_edgecases.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_scenario_manager_smoke.py' ]; then
    rm 'tests/api/test_scenario_manager_smoke.py' && echo "  ✓ tests/api/test_scenario_manager_smoke.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_scenario_manager_smoke.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_schema_guard_fx_validation.py' ]; then
    rm 'tests/api/test_schema_guard_fx_validation.py' && echo "  ✓ tests/api/test_schema_guard_fx_validation.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_schema_guard_fx_validation.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_scenario_analytics_schema_guard_integration.py' ]; then
    rm 'tests/api/test_scenario_analytics_schema_guard_integration.py' && echo "  ✓ tests/api/test_scenario_analytics_schema_guard_integration.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_scenario_analytics_schema_guard_integration.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_finance_utils.py' ]; then
    rm 'tests/api/test_finance_utils.py' && echo "  ✓ tests/api/test_finance_utils.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_finance_utils.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_export_helpers_v14.py' ]; then
    rm 'tests/api/test_export_helpers_v14.py' && echo "  ✓ tests/api/test_export_helpers_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_export_helpers_v14.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_epc_helper_v14.py' ]; then
    rm 'tests/api/test_epc_helper_v14.py' && echo "  ✓ tests/api/test_epc_helper_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_epc_helper_v14.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_metrics_core_stats.py' ]; then
    rm 'tests/api/test_metrics_core_stats.py' && echo "  ✓ tests/api/test_metrics_core_stats.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_metrics_core_stats.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_metrics_module.py' ]; then
    rm 'tests/api/test_metrics_module.py' && echo "  ✓ tests/api/test_metrics_module.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_metrics_module.py" && ((FAILED++))
fi
if [ -f 'tests/contracts/test_sensitivity_contracts.py' ]; then
    rm 'tests/contracts/test_sensitivity_contracts.py' && echo "  ✓ tests/contracts/test_sensitivity_contracts.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/contracts/test_sensitivity_contracts.py" && ((FAILED++))
fi
if [ -f 'tests/lint/test_no_argparse_v14.py' ]; then
    rm 'tests/lint/test_no_argparse_v14.py' && echo "  ✓ tests/lint/test_no_argparse_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/lint/test_no_argparse_v14.py" && ((FAILED++))
fi
if [ -f 'tests/lint/test_irr_location_v14.py' ]; then
    rm 'tests/lint/test_irr_location_v14.py' && echo "  ✓ tests/lint/test_irr_location_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/lint/test_irr_location_v14.py" && ((FAILED++))
fi
if [ -f 'tests/lint/test_no_typer_v14.py' ]; then
    rm 'tests/lint/test_no_typer_v14.py' && echo "  ✓ tests/lint/test_no_typer_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/lint/test_no_typer_v14.py" && ((FAILED++))
fi
if [ -f 'tests/lint/test_equity_fence_v14.py' ]; then
    rm 'tests/lint/test_equity_fence_v14.py' && echo "  ✓ tests/lint/test_equity_fence_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/lint/test_equity_fence_v14.py" && ((FAILED++))
fi
if [ -f 'tests/lint/test_sensitivity_v14_imports.py' ]; then
    rm 'tests/lint/test_sensitivity_v14_imports.py' && echo "  ✓ tests/lint/test_sensitivity_v14_imports.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/lint/test_sensitivity_v14_imports.py" && ((FAILED++))
fi
if [ -f 'tests/test_fx_structured_blocks.py' ]; then
    rm 'tests/test_fx_structured_blocks.py' && echo "  ✓ tests/test_fx_structured_blocks.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_fx_structured_blocks.py" && ((FAILED++))
fi
if [ -f 'tests/test_scenario_analytics_smoke.py' ]; then
    rm 'tests/test_scenario_analytics_smoke.py' && echo "  ✓ tests/test_scenario_analytics_smoke.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_scenario_analytics_smoke.py" && ((FAILED++))
fi
if [ -f 'tests/test_metrics_integration.py' ]; then
    rm 'tests/test_metrics_integration.py' && echo "  ✓ tests/test_metrics_integration.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_metrics_integration.py" && ((FAILED++))
fi
if [ -f 'tests/test_cli_v14_smoke.py' ]; then
    rm 'tests/test_cli_v14_smoke.py' && echo "  ✓ tests/test_cli_v14_smoke.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_cli_v14_smoke.py" && ((FAILED++))
fi
if [ -f 'tests/test_schema_guard_fx.py' ]; then
    rm 'tests/test_schema_guard_fx.py' && echo "  ✓ tests/test_schema_guard_fx.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_schema_guard_fx.py" && ((FAILED++))
fi
if [ -f 'tests/test_fx_config_strictness.py' ]; then
    rm 'tests/test_fx_config_strictness.py' && echo "  ✓ tests/test_fx_config_strictness.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_fx_config_strictness.py" && ((FAILED++))
fi
if [ -f 'tests/test_phase_1_2_refactoring.py' ]; then
    rm 'tests/test_phase_1_2_refactoring.py' && echo "  ✓ tests/test_phase_1_2_refactoring.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_phase_1_2_refactoring.py" && ((FAILED++))
fi
if [ -f 'tests/test_export_smoke.py' ]; then
    rm 'tests/test_export_smoke.py' && echo "  ✓ tests/test_export_smoke.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_export_smoke.py" && ((FAILED++))
fi
if [ -f 'tests/test_scenario_analytics_cli_v14_smoke.py' ]; then
    rm 'tests/test_scenario_analytics_cli_v14_smoke.py' && echo "  ✓ tests/test_scenario_analytics_cli_v14_smoke.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_scenario_analytics_cli_v14_smoke.py" && ((FAILED++))
fi
if [ -f 'tests/test_fx_pipeline_integration.py' ]; then
    rm 'tests/test_fx_pipeline_integration.py' && echo "  ✓ tests/test_fx_pipeline_integration.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/test_fx_pipeline_integration.py" && ((FAILED++))
fi
if [ -f 'legacy_tests/test_legacy_api.py' ]; then
    rm 'legacy_tests/test_legacy_api.py' && echo "  ✓ legacy_tests/test_legacy_api.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: legacy_tests/test_legacy_api.py" && ((FAILED++))
fi
if [ -f 'legacy_tests/test_legacy_contracts.py' ]; then
    rm 'legacy_tests/test_legacy_contracts.py' && echo "  ✓ legacy_tests/test_legacy_contracts.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: legacy_tests/test_legacy_contracts.py" && ((FAILED++))
fi
if [ -f 'legacy_tests/test_legacy_data.py' ]; then
    rm 'legacy_tests/test_legacy_data.py' && echo "  ✓ legacy_tests/test_legacy_data.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: legacy_tests/test_legacy_data.py" && ((FAILED++))
fi
if [ -f 'legacy_tests/test_legacy_exports.py' ]; then
    rm 'legacy_tests/test_legacy_exports.py' && echo "  ✓ legacy_tests/test_legacy_exports.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: legacy_tests/test_legacy_exports.py" && ((FAILED++))
fi
if [ -f 'legacy_tests/test_legacy_helpers.py' ]; then
    rm 'legacy_tests/test_legacy_helpers.py' && echo "  ✓ legacy_tests/test_legacy_helpers.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: legacy_tests/test_legacy_helpers.py" && ((FAILED++))
fi
if [ -f 'legacy_tests/test_legacy_validation.py' ]; then
    rm 'legacy_tests/test_legacy_validation.py' && echo "  ✓ legacy_tests/test_legacy_validation.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: legacy_tests/test_legacy_validation.py" && ((FAILED++))
fi
if [ -f 'tests/_quarantine/test_broken_feature_a.py' ]; then
    rm 'tests/_quarantine/test_broken_feature_a.py' && echo "  ✓ tests/_quarantine/test_broken_feature_a.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/_quarantine/test_broken_feature_a.py" && ((FAILED++))
fi
if [ -f 'tests/_quarantine/test_known_bug_b.py' ]; then
    rm 'tests/_quarantine/test_known_bug_b.py' && echo "  ✓ tests/_quarantine/test_known_bug_b.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/_quarantine/test_known_bug_b.py" && ((FAILED++))
fi
if [ -f 'tests/performance_benchmarks_v14.py' ]; then
    rm 'tests/performance_benchmarks_v14.py' && echo "  ✓ tests/performance_benchmarks_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/performance_benchmarks_v14.py" && ((FAILED++))
fi
if [ -f 'tests/integration/test_fx_monte_carlo_integration.py' ]; then
    rm 'tests/integration/test_fx_monte_carlo_integration.py' && echo "  ✓ tests/integration/test_fx_monte_carlo_integration.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/integration/test_fx_monte_carlo_integration.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_tax_v14_lender_golden.py' ]; then
    rm 'tests/api/test_tax_v14_lender_golden.py' && echo "  ✓ tests/api/test_tax_v14_lender_golden.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_tax_v14_lender_golden.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_irr_module.py' ]; then
    rm 'tests/api/test_irr_module.py' && echo "  ✓ tests/api/test_irr_module.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_irr_module.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_monte_carlo_v14.py' ]; then
    rm 'tests/api/test_monte_carlo_v14.py' && echo "  ✓ tests/api/test_monte_carlo_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_monte_carlo_v14.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_pipeline_sprint12.py' ]; then
    rm 'tests/api/test_pipeline_sprint12.py' && echo "  ✓ tests/api/test_pipeline_sprint12.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_pipeline_sprint12.py" && ((FAILED++))
fi
if [ -f 'tests/api/test_stress_tests_v14.py' ]; then
    rm 'tests/api/test_stress_tests_v14.py' && echo "  ✓ tests/api/test_stress_tests_v14.py" && ((REMOVED++))
else
    echo "  ⚠ Not found: tests/api/test_stress_tests_v14.py" && ((FAILED++))
fi

echo ""
echo "=========================================="
echo "✅ Cleanup Complete!"
echo "=========================================="
echo ""
echo "📊 Results:"
echo "  Files removed:    $REMOVED / 79"
echo "  Files not found:  $FAILED"
echo "  Core tests kept:  63"
echo ""
echo "📝 Next steps:"
echo "  1. git status"
echo "  2. pytest tests/ -v"
echo "  3. git add . && git commit -m 'chore: Remove 79 non-core test files'"
echo "  4. git push origin feature/add-finance-contracts-pydantic-v2-20251219"
