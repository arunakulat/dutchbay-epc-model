#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 VALIDATION SCRIPT (Shell-based, no argparse, no AST)
# ═══════════════════════════════════════════════════════════════════════════
#
# Go-with-the-Flow Compliant Validation
# - No argparse (banned in CLI-01)
# - No AST/LibCST (reserved for linting)
# - Simple shell grep/find operations
# - Exits 0 for success, 1 for failure
#
# Usage:
#   bash validate_sensitivity_v14_gwtf.sh [path_to_file]
#
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Configuration
CHECKS_PASSED=0
CHECKS_FAILED=0
ERRORS=()
WARNINGS=()

# Helper functions
fail() {
    echo "❌ FAILED: $1"
    ERRORS+=("$1")
    ((CHECKS_FAILED++))
}

pass() {
    echo "✅ PASSED: $1"
    ((CHECKS_PASSED++))
}

warn() {
    echo "⚠️  WARNING: $1"
    WARNINGS+=("$1")
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

TARGET_FILE="${1:-analytics/sensitivity_v14.py}"

if [ ! -f "$TARGET_FILE" ]; then
    echo "❌ File not found: $TARGET_FILE"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║ PHASE 1 SENSITIVITY_V14 VALIDATION (Go-with-the-Flow v3.0)   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "File: $TARGET_FILE"
echo ""

# ───────────────────────────────────────────────────────────────────────────
# CHECK 1: No forbidden imports (run_v14_pipeline)
# ───────────────────────────────────────────────────────────────────────────
echo "[CHECK 1/7] Forbidden imports..."

if grep -q "from analytics.pipeline_v14 import run_v14_pipeline" "$TARGET_FILE"; then
    fail "Found forbidden import: run_v14_pipeline"
elif grep -q "run_v14_pipeline" "$TARGET_FILE" && ! grep -q "# run_v14_pipeline" "$TARGET_FILE"; then
    fail "Found direct call to run_v14_pipeline"
else
    pass "No run_v14_pipeline imports/calls"
fi

# ───────────────────────────────────────────────────────────────────────────
# CHECK 2: No forbidden imports (load_scenario_config)
# ───────────────────────────────────────────────────────────────────────────
echo "[CHECK 2/7] Forbidden scenario loader imports..."

if grep -q "from analytics.scenario_loader import load_scenario_config" "$TARGET_FILE"; then
    fail "Found forbidden import: load_scenario_config"
elif grep -q "load_scenario_config" "$TARGET_FILE" && ! grep -q "# load_scenario_config" "$TARGET_FILE"; then
    fail "Found direct call to load_scenario_config"
else
    pass "No load_scenario_config imports/calls"
fi

# ───────────────────────────────────────────────────────────────────────────
# CHECK 3: Required import present (evaluate_scenario)
# ───────────────────────────────────────────────────────────────────────────
echo "[CHECK 3/7] Required imports..."

if grep -q "from analytics.evaluation_v14 import evaluate_scenario" "$TARGET_FILE"; then
    pass "evaluate_scenario import present"
else
    fail "Missing required import: evaluate_scenario from analytics.evaluation_v14"
fi

# ───────────────────────────────────────────────────────────────────────────
# CHECK 4: SensitivityResult dataclass exists
# ───────────────────────────────────────────────────────────────────────────
echo "[CHECK 4/7] SensitivityResult dataclass..."

if grep -q "class SensitivityResult" "$TARGET_FILE"; then
    if grep -q "@dataclass" "$TARGET_FILE"; then
        pass "SensitivityResult dataclass defined"
    else
        warn "SensitivityResult exists but may not have @dataclass decorator"
    fi
else
    fail "SensitivityResult dataclass not found"
fi

# ───────────────────────────────────────────────────────────────────────────
# CHECK 5: _evaluate_base_kpis helper exists
# ───────────────────────────────────────────────────────────────────────────
echo "[CHECK 5/7] _evaluate_base_kpis helper..."

if grep -q "def _evaluate_base_kpis" "$TARGET_FILE"; then
    pass "_evaluate_base_kpis helper function defined"
else
    fail "_evaluate_base_kpis helper not found"
fi

# ───────────────────────────────────────────────────────────────────────────
# CHECK 6: Public APIs unchanged (backwards compatibility)
# ───────────────────────────────────────────────────────────────────────────
echo "[CHECK 6/7] Public API backwards compatibility..."

MISSING_APIS=0

for api in "run_tornado_sensitivity" "run_multi_metric_tornado" "run_breakeven_parameter"; do
    if grep -q "def $api" "$TARGET_FILE"; then
        true
    else
        fail "Missing public API: $api"
        ((MISSING_APIS++))
    fi
done

if [ $MISSING_APIS -eq 0 ]; then
    pass "All public APIs present (backwards compatible)"
fi

# ───────────────────────────────────────────────────────────────────────────
# CHECK 7: No direct pipeline calls
# ───────────────────────────────────────────────────────────────────────────
echo "[CHECK 7/7] No direct pipeline calls..."

PIPELINE_CALL_COUNT=$(grep -c "run_v14_pipeline(" "$TARGET_FILE" || echo 0)

if [ "$PIPELINE_CALL_COUNT" -eq 0 ]; then
    pass "No direct run_v14_pipeline calls"
else
    fail "Found $PIPELINE_CALL_COUNT direct run_v14_pipeline call(s)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "SUMMARY"
echo "═════════════════════════════════════════════════════════════════"
echo "Checks Passed: $CHECKS_PASSED/7"
echo "Checks Failed: $CHECKS_FAILED/7"

if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo ""
    echo "Warnings (${#WARNINGS[@]}):"
    for w in "${WARNINGS[@]}"; do
        echo "  ⚠️  $w"
    done
fi

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo ""
    echo "Errors (${#ERRORS[@]}):"
    for e in "${ERRORS[@]}"; do
        echo "  ❌ $e"
    done
    echo ""
    echo "═════════════════════════════════════════════════════════════════"
    echo "❌ VALIDATION FAILED"
    echo "═════════════════════════════════════════════════════════════════"
    exit 1
fi

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "✅ ALL CHECKS PASSED"
echo "═════════════════════════════════════════════════════════════════"
echo ""

exit 0
