#!/bin/bash
# test_after_cleanup.sh
# Verify repository integrity after root directory cleanup
# Generated: 2025-11-29

set -e

echo "=========================================="
echo "🧪 POST-CLEANUP TEST SUITE"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Testing: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if eval "$test_command"; then
        echo "${GREEN}✅ PASSED${NC}: $test_name"
        ((TESTS_PASSED++))
    else
        echo "${RED}❌ FAILED${NC}: $test_name"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# ========================================================================
# Phase 1: Verify directory structure
# ========================================================================
echo "📁 PHASE 1: Verifying directory structure..."
echo ""

run_test "inputs/fxdata/ exists" "[ -d 'inputs/fxdata' ]"
run_test "legacy/ exists" "[ -d 'legacy' ]"
run_test "scripts/ exists" "[ -d 'scripts' ]"

# ========================================================================
# Phase 2: Verify critical files still exist
# ========================================================================
echo "📄 PHASE 2: Verifying critical files..."
echo ""

run_test "run_full_pipeline_v14.py exists" "[ -f 'run_full_pipeline_v14.py' ]"
run_test "requirements.txt exists" "[ -f 'requirements.txt' ]"
run_test "scripts/go_with_the_flow_ci.py exists" "[ -f 'scripts/go_with_the_flow_ci.py' ]"
run_test "README.md exists" "[ -f 'README.md' ]"
run_test "pyproject.toml exists" "[ -f 'pyproject.toml' ]"

# ========================================================================
# Phase 3: Verify FX data files moved correctly
# ========================================================================
echo "📊 PHASE 3: Verifying FX data files moved to inputs/fxdata/..."
echo ""

run_test "FX Decade 4 data exists" "[ -f 'inputs/fxdata/fx_data_historical_Decade4_2005_2014.yaml' ]"
run_test "FX Decade 5 data exists" "[ -f 'inputs/fxdata/fx_data_historical_Decade5_2015_2025.yaml' ]"
run_test "FX Period 1 data exists" "[ -f 'inputs/fxdata/fx_data_recent_Period1_2016_2017.yaml' ]"

# ========================================================================
# Phase 4: Verify fx_correlation_module.py moved to scripts/
# ========================================================================
echo "🐍 PHASE 4: Verifying FX correlation module moved to scripts/..."
echo ""

run_test "fx_correlation_module.py in scripts/" "[ -f 'scripts/fx_correlation_module.py' ]"
run_test "No fx_correlation_module.py in root" "[ ! -f 'fx_correlation_module.py' ] && [ ! -f 'fx_correlation_module.py ' ]"

# ========================================================================
# Phase 5: Verify legacy files moved correctly
# ========================================================================
echo "📦 PHASE 5: Verifying legacy files moved..."
echo ""

run_test "Old CI variants moved" "[ -f 'legacy/ci_variants/go_with_the_flow_ci_enhanced.py' ]"
run_test "v14 migration scripts moved" "[ -f 'legacy/v14_migration/fix_v14chat_imports.py' ]"
run_test "Old v13 pipeline moved" "[ -f 'legacy/run_full_pipeline.py' ]"
run_test "No run_full_pipeline.py in root" "[ ! -f 'run_full_pipeline.py' ]"

# ========================================================================
# Phase 6: Python syntax checks
# ========================================================================
echo "🐍 PHASE 6: Running Python syntax checks..."
echo ""

if command -v python &> /dev/null; then
    run_test "Python import check - finance" "python -c 'import finance.debt_v14'"
    run_test "Python import check - analytics" "python -c 'import analytics.config_schema'"
    run_test "Python syntax - run_full_pipeline_v14.py" "python -m py_compile run_full_pipeline_v14.py"
else
    echo "${YELLOW}⚠️  Python not found in PATH, skipping Python checks${NC}"
fi

# ========================================================================
# Phase 7: Run critical test suite
# ========================================================================
echo "🧪 PHASE 7: Running critical test suite..."
echo ""

if [ -f ".venv311/bin/pytest" ] || command -v pytest &> /dev/null; then
    # Run the 9 v14 API tests that were just fixed
    run_test "v14 API tests (9 tests)" "pytest tests/api/test_debt_v14_construction.py tests/api/test_scenario_analytics_schema_guard_integration.py tests/api/test_debt_construction_idc_regression_v14.py tests/api/test_config_schema_guard.py tests/api/test_covenants_lendercase_2025Q4.py -v --tb=short"
else
    echo "${YELLOW}⚠️  pytest not found, skipping test suite${NC}"
fi

# ========================================================================
# Phase 8: Git status check
# ========================================================================
echo "🔍 PHASE 8: Git status check..."
echo ""

if command -v git &> /dev/null; then
    echo "Modified/moved files:"
    git status --short | head -20
    echo ""

    if [ $(git status --short | wc -l) -gt 30 ]; then
        echo "${YELLOW}⚠️  Many files modified (>30). Expected after cleanup.${NC}"
    fi
else
    echo "${YELLOW}⚠️  Git not found, skipping git checks${NC}"
fi

# ========================================================================
# Final Summary
# ========================================================================
echo "=========================================="
echo "📊 TEST SUMMARY"
echo "=========================================="
echo ""
echo "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "${GREEN}✅ ALL TESTS PASSED!${NC}"
    echo ""
    echo "🎉 Cleanup successful - repository integrity verified!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Review git status and changes"
    echo "   2. Commit cleanup changes:"
    echo "      git add -A"
    echo "      git commit -m 'chore: reorganize root directory - move legacy files and FX data'"
    echo "   3. Push to GitHub:"
    echo "      git push origin main"
    exit 0
else
    echo "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    echo "⚠️  Please review failed tests before committing."
    echo ""
    echo "Common issues:"
    echo "   • Files not moved correctly"
    echo "   • Import paths need updating"
    echo "   • Missing dependencies"
    exit 1
fi
