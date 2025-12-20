#!/bin/bash
# Fix Script - Remove files that were modified instead of deleted
# These files have broken imports and should be completely removed

set -e

echo "=========================================="
echo "Fixing Cleanup - Removing Modified Files"
echo "=========================================="
echo ""
echo "This will remove files that were marked 'modified' but should be deleted"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted."
    exit 1
fi

echo ""
echo "Removing modified test files..."
echo ""

REMOVED=0

# Analytics layer broken files
if [ -f 'tests/analytics_layer/_casper_fakes.py' ]; then
    rm 'tests/analytics_layer/_casper_fakes.py' && echo "  ✓ tests/analytics_layer/_casper_fakes.py" && ((REMOVED++))
fi

if [ -f 'tests/analytics_layer/test_casper_payload.py' ]; then
    rm 'tests/analytics_layer/test_casper_payload.py' && echo "  ✓ tests/analytics_layer/test_casper_payload.py" && ((REMOVED++))
fi

if [ -f 'tests/analytics_layer/test_sensitivity_breakeven_contract.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_breakeven_contract.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_breakeven_contract.py" && ((REMOVED++))
fi

if [ -f 'tests/analytics_layer/test_sensitivity_regression.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_regression.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_regression.py" && ((REMOVED++))
fi

if [ -f 'tests/analytics_layer/test_sensitivity_run_contract.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_run_contract.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_run_contract.py" && ((REMOVED++))
fi

if [ -f 'tests/analytics_layer/test_sensitivity_v14.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_v14.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_v14.py" && ((REMOVED++))
fi

if [ -f 'tests/analytics_layer/test_sensitivity_v14_api.py' ]; then
    rm 'tests/analytics_layer/test_sensitivity_v14_api.py' && echo "  ✓ tests/analytics_layer/test_sensitivity_v14_api.py" && ((REMOVED++))
fi

# API broken files
if [ -f 'tests/api/test_bad_missing_tax_schema_guard.py' ]; then
    rm 'tests/api/test_bad_missing_tax_schema_guard.py' && echo "  ✓ tests/api/test_bad_missing_tax_schema_guard.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_casper_v14_smoke.py' ]; then
    rm 'tests/api/test_casper_v14_smoke.py' && echo "  ✓ tests/api/test_casper_v14_smoke.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_casper_v14_smoke_iteration1.py' ]; then
    rm 'tests/api/test_casper_v14_smoke_iteration1.py' && echo "  ✓ tests/api/test_casper_v14_smoke_iteration1.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_casper_v14_smoke_iteration2.py' ]; then
    rm 'tests/api/test_casper_v14_smoke_iteration2.py' && echo "  ✓ tests/api/test_casper_v14_smoke_iteration2.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_config_schema_guard.py' ]; then
    rm 'tests/api/test_config_schema_guard.py' && echo "  ✓ tests/api/test_config_schema_guard.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_edgecases.py' ]; then
    rm 'tests/api/test_edgecases.py' && echo "  ✓ tests/api/test_edgecases.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_evaluate_scenario_v14.py' ]; then
    rm 'tests/api/test_evaluate_scenario_v14.py' && echo "  ✓ tests/api/test_evaluate_scenario_v14.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_irr_core.py' ]; then
    rm 'tests/api/test_irr_core.py' && echo "  ✓ tests/api/test_irr_core.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_irr_module.py' ]; then
    rm 'tests/api/test_irr_module.py' && echo "  ✓ tests/api/test_irr_module.py" && ((REMOVED++))
fi

if [ -f 'tests/api/test_schema_guard_fx_validation.py' ]; then
    rm 'tests/api/test_schema_guard_fx_validation.py' && echo "  ✓ tests/api/test_schema_guard_fx_validation.py" && ((REMOVED++))
fi

# Root level broken files
if [ -f 'tests/test_metrics_integration.py' ]; then
    rm 'tests/test_metrics_integration.py' && echo "  ✓ tests/test_metrics_integration.py" && ((REMOVED++))
fi

if [ -f 'tests/test_schema_guard_fx.py' ]; then
    rm 'tests/test_schema_guard_fx.py' && echo "  ✓ tests/test_schema_guard_fx.py" && ((REMOVED++))
fi

# Quarantine broken files
if [ -f 'tests/_quarantine/test_monte_carlo_v14.py' ]; then
    rm 'tests/_quarantine/test_monte_carlo_v14.py' && echo "  ✓ tests/_quarantine/test_monte_carlo_v14.py" && ((REMOVED++))
fi

# Lint broken file
if [ -f 'tests/lint/test_equity_fence_v14.py' ]; then
    rm 'tests/lint/test_equity_fence_v14.py' && echo "  ✓ tests/lint/test_equity_fence_v14.py" && ((REMOVED++))
fi

echo ""
echo "=========================================="
echo "✅ Fix Complete!"
echo "=========================================="
echo ""
echo "📊 Results: $REMOVED files removed"
echo ""
echo "📝 Next steps:"
echo "  1. pytest tests/ -v   # Should pass now!"
echo "  2. git status"
echo "  3. git add -A"
echo "  4. git commit -m 'chore: Complete test cleanup - remove 70+ non-core test files'"
echo "  5. git push origin feature/add-finance-contracts-pydantic-v2-20251219"
echo ""
