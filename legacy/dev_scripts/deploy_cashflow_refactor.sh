#!/usr/bin/env bash
# DutchBay Cashflow v14 Refactoring: Deploy & Test Script
# =========================================================
#
# This script automates the deployment of the refactored tax module.
# Run from repository root: bash deploy_cashflow_refactor.sh
#
# What it does:
# 1. Backs up current cashflow_v14_tax.py
# 2. Copies refactored version into place
# 3. Copies new test file
# 4. Runs mypy type checking
# 5. Runs unit tests
# 6. Shows integration points in cashflow_v14.py
#
# Author: DutchBay Finance Team
# Date: December 9, 2025

set -e  # Exit on any error

echo "=================================="
echo "DutchBay Cashflow v14 Refactoring"
echo "Deploy & Test Script"
echo "=================================="
echo

# Configuration
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FINANCE_DIR="${REPO_ROOT}/finance"
TESTS_DIR="${REPO_ROOT}/tests/finance"
TAX_MODULE="${FINANCE_DIR}/cashflow_v14_tax.py"
ORCHESTRATOR="${FINANCE_DIR}/cashflow_v14.py"
BACKUP_DIR="${REPO_ROOT}/.backups"

echo "✓ Repository root: ${REPO_ROOT}"
echo "✓ Finance dir: ${FINANCE_DIR}"
echo "✓ Tests dir: ${TESTS_DIR}"
echo

# ============================================================================
# STEP 1: Backup current files
# ============================================================================

echo "STEP 1: Backup current files"
echo "-----------------------------"

mkdir -p "${BACKUP_DIR}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

if [ -f "${TAX_MODULE}" ]; then
    cp "${TAX_MODULE}" "${BACKUP_DIR}/cashflow_v14_tax.py.backup.${TIMESTAMP}"
    echo "✓ Backed up: ${BACKUP_DIR}/cashflow_v14_tax.py.backup.${TIMESTAMP}"
else
    echo "⚠ No existing tax module found (first deployment)"
fi

echo

# ============================================================================
# STEP 2: Copy refactored tax module
# ============================================================================

echo "STEP 2: Deploy refactored tax module"
echo "------------------------------------"

# This assumes the refactored file is in the current directory
# Adjust SOURCE_TAX_FILE if it's elsewhere

SOURCE_TAX_FILE="./refactored_cashflow_v14_tax.py"

if [ ! -f "${SOURCE_TAX_FILE}" ]; then
    echo "❌ ERROR: ${SOURCE_TAX_FILE} not found!"
    echo "   Make sure refactored_cashflow_v14_tax.py is in the current directory"
    exit 1
fi

cp "${SOURCE_TAX_FILE}" "${TAX_MODULE}"
echo "✓ Deployed: ${SOURCE_TAX_FILE} → ${TAX_MODULE}"
echo

# ============================================================================
# STEP 3: Copy test file
# ============================================================================

echo "STEP 3: Install test suite"
echo "----------------------------"

SOURCE_TEST_FILE="./test_cashflow_v14_tax_refactored.py"

if [ ! -f "${SOURCE_TEST_FILE}" ]; then
    echo "❌ ERROR: ${SOURCE_TEST_FILE} not found!"
    echo "   Make sure test_cashflow_v14_tax_refactored.py is in the current directory"
    exit 1
fi

mkdir -p "${TESTS_DIR}"
cp "${SOURCE_TEST_FILE}" "${TESTS_DIR}/${SOURCE_TEST_FILE}"
echo "✓ Installed: ${SOURCE_TEST_FILE} → ${TESTS_DIR}"
echo

# ============================================================================
# STEP 4: Type checking with mypy
# ============================================================================

echo "STEP 4: Type checking (mypy)"
echo "-----------------------------"

if command -v mypy &> /dev/null; then
    echo "Running: mypy ${TAX_MODULE} --strict"
    if mypy "${TAX_MODULE}" --strict --ignore-missing-imports; then
        echo "✓ All type checks passed"
    else
        echo "⚠ Some type warnings found (review above)"
    fi
else
    echo "⚠ mypy not installed; skipping type check"
    echo "  Install with: pip install mypy"
fi

echo

# ============================================================================
# STEP 5: Run unit tests
# ============================================================================

echo "STEP 5: Unit tests"
echo "------------------"

if command -v pytest &> /dev/null; then
    TEST_FILE="${TESTS_DIR}/test_cashflow_v14_tax_refactored.py"
    echo "Running: pytest ${TEST_FILE} -v"
    echo

    if pytest "${TEST_FILE}" -v --tb=short; then
        echo
        echo "✓ All unit tests passed"
    else
        echo
        echo "❌ Some tests failed; review output above"
        exit 1
    fi
else
    echo "⚠ pytest not installed; skipping unit tests"
    echo "  Install with: pip install pytest"
fi

echo

# ============================================================================
# STEP 6: Check linting
# ============================================================================

echo "STEP 6: Linting (ruff)"
echo "---------------------"

if command -v ruff &> /dev/null; then
    echo "Running: ruff check ${TAX_MODULE}"
    if ruff check "${TAX_MODULE}" --select=E,W,F; then
        echo "✓ Linting passed"
    else
        echo "⚠ Some lint issues found (review above)"
    fi
else
    echo "⚠ ruff not installed; skipping lint check"
    echo "  Install with: pip install ruff"
fi

echo

# ============================================================================
# STEP 7: Summary & next steps
# ============================================================================

echo "=================================="
echo "✓ DEPLOYMENT COMPLETE"
echo "=================================="
echo

echo "NEXT STEPS:"
echo "-----------"
echo
echo "1. Review the INTEGRATION GUIDE:"
echo "   cat INTEGRATION_GUIDE_cashflow_v14.md"
echo
echo "2. Update your cashflow_v14.py with the changes from the guide:"
echo "   - Update imports (Part 1)"
echo "   - Update _prepare_cashflow_context() (Part 2)"
echo "   - Update calculate_single_year_cfads() (Part 3)"
echo "   - Update build_annual_cfads() (Part 4)"
echo "   - Update build_annual_rows() (Part 5)"
echo
echo "3. Run full test suite after integration:"
echo "   pytest tests/finance/ -k cashflow -v"
echo
echo "4. Commit changes:"
echo "   git add finance/cashflow_v14.py finance/cashflow_v14_tax.py tests/"
echo "   git commit -m 'refactor: cashflow v14 tax module with TaxProfile'"
echo
echo "FILES INSTALLED:"
echo "----------------"
echo "  • ${TAX_MODULE}"
echo "  • ${TESTS_DIR}/test_cashflow_v14_tax_refactored.py"
echo "  • Backup: ${BACKUP_DIR}/cashflow_v14_tax.py.backup.${TIMESTAMP}"
echo
echo "DOCUMENTATION:"
echo "---------------"
echo "  • refactored_cashflow_v14_tax.py (source code with full docstrings)"
echo "  • test_cashflow_v14_tax_refactored.py (16+ unit tests)"
echo "  • INTEGRATION_GUIDE_cashflow_v14.md (exact code changes needed)"
echo

echo "✓ Deployment script complete"
exit 0
