#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 VALIDATION SCRIPT (Shell-based, no argparse, no AST)
# ═══════════════════════════════════════════════════════════════════════════
#
# Go-with-the-Flow Compliant Validation
# - No argparse (banned in CLI-01)
# - No AST/LibCST (reserved for linting/tests)
# - Simple shell grep checks only
# - Exits 0 for success, 1 for failure
#
# Usage:
#   bash validate_sensitivity_v14_gwtf.sh [path_to_file]
#
# Default:
#   analytics/sensitivity_v14.py
#
# Checks (7 total):
#   1) No run_v14_pipeline imports/calls
#   2) No load_scenario_config imports/calls
#   3) Has evaluate_scenario import
#   4) Has SensitivityResult dataclass
#   5) Has _evaluate_base_kpis helper
#   6) Uses evaluate_scenario at least once
#   7) File is non-empty and under 3000 lines
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

CHECKS_PASSED=0
CHECKS_FAILED=0
ERRORS=()

fail() {
    echo "❌ FAILED: $1"
    ERRORS+=("$1")
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
}

pass() {
    echo "✅ PASSED: $1"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
}

print_summary() {
    echo ""
    echo "────────────────────────────────────────────────────────────────────────"
    echo "Validation complete:"
    echo "  Passed: ${CHECKS_PASSED}"
    echo "  Failed: ${CHECKS_FAILED}"
    if [ "${CHECKS_FAILED}" -ne 0 ]; then
        echo ""
        echo "Errors:"
        for err in "${ERRORS[@]}"; do
            echo "  - ${err}"
        done
        echo "────────────────────────────────────────────────────────────────────────"
        echo "Result: ❌ Phase 1 validation FAILED"
        exit 1
    else
        echo "────────────────────────────────────────────────────────────────────────"
        echo "Result: ✅ ALL CHECKS PASSED – File is Phase 1 compliant!"
        exit 0
    fi
}

TARGET_FILE="${1:-analytics/sensitivity_v14.py}"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║ PHASE 1 SENSITIVITY_V14 VALIDATION (Go-with-the-Flow v3.0)     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Target file: ${TARGET_FILE}"
echo ""

if [ ! -f "${TARGET_FILE}" ]; then
    echo "❌ File not found: ${TARGET_FILE}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────
# CHECK 1: No forbidden imports/calls for run_v14_pipeline
# ─────────────────────────────────────────────────────────────────────────
echo "[CHECK 1/7] Forbidden imports/calls: run_v14_pipeline"

if grep -q "from[[:space:]]\+analytics\.pipeline_v14[[:space:]]\+import[[:space:]]\+run_v14_pipeline" "${TARGET_FILE}"; then
    fail "Found forbidden import: from analytics.pipeline_v14 import run_v14_pipeline"
elif grep -q "run_v14_pipeline" "${TARGET_FILE}" && ! grep -q "#.*run_v14_pipeline" "${TARGET_FILE}"; then
    fail "Found forbidden direct call to run_v14_pipeline"
else
    pass "No forbidden run_v14_pipeline imports/calls"
fi

# ─────────────────────────────────────────────────────────────────────────
# CHECK 2: No forbidden imports/calls for load_scenario_config
# ─────────────────────────────────────────────────────────────────────────
echo "[CHECK 2/7] Forbidden imports/calls: load_scenario_config"

if grep -q "from[[:space:]]\+analytics\.scenario_loader[[:space:]]\+import[[:space:]]\+load_scenario_config" "${TARGET_FILE}"; then
    fail "Found forbidden import: from analytics.scenario_loader import load_scenario_config"
elif grep -q "load_scenario_config" "${TARGET_FILE}" && ! grep -q "#.*load_scenario_config" "${TARGET_FILE}"; then
    fail "Found forbidden direct call to load_scenario_config"
else
    pass "No forbidden load_scenario_config imports/calls"
fi

# ─────────────────────────────────────────────────────────────────────────
# CHECK 3: Required evaluate_scenario import present
# ─────────────────────────────────────────────────────────────────────────
echo "[CHECK 3/7] Required import: evaluate_scenario"

if grep -q "from[[:space:]]\+analytics\.evaluation_v14[[:space:]]\+import[[:space:]]\+evaluate_scenario" "${TARGET_FILE}"; then
    pass "Found required import: from analytics.evaluation_v14 import evaluate_scenario"
else
    fail "Missing required import: from analytics.evaluation_v14 import evaluate_scenario"
fi

# ─────────────────────────────────────────────────────────────────────────
# CHECK 4: SensitivityResult dataclass exists
# ─────────────────────────────────────────────────────────────────────────
echo "[CHECK 4/7] SensitivityResult dataclass"

if grep -q "@dataclass" "${TARGET_FILE}" && grep -q "class[[:space:]]\+SensitivityResult" "${TARGET_FILE}"; then
    pass "Found SensitivityResult dataclass"
else
    fail "Missing SensitivityResult dataclass definition"
fi

# ─────────────────────────────────────────────────────────────────────────
# CHECK 5: _evaluate_base_kpis helper exists
# ─────────────────────────────────────────────────────────────────────────
echo "[CHECK 5/7] _evaluate_base_kpis helper"

if grep -q "def[[:space:]]\+_evaluate_base_kpis"_
