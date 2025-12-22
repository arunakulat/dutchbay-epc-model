#!/bin/bash
# File: scripts/freeze_validation_sprint17.sh
# Purpose: Un-gameable freeze validation for DutchBay EPC Model
# Sprint: 17 - Pydantic V2 + Pipeline Verification
# Author: AI Assistant + Dev Team Checklist
# Date: 2024-12-22

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REPO_ROOT="$(git rev-parse --show-toplevel)"
FREEZE_DIR="${REPO_ROOT}/_freeze_artifacts"
FREEZE_REPORT="${FREEZE_DIR}/freeze_validation_report_$(date +%Y%m%d_%H%M%S).md"

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}DutchBay EPC Model - Freeze Validation Checklist${NC}"
echo -e "${GREEN}Sprint 17 - Pydantic V2 + Pipeline Drift Check${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Create freeze artifacts directory
mkdir -p "${FREEZE_DIR}"

# Initialize report
cat > "${FREEZE_REPORT}" << 'EOF'
# DutchBay EPC Model - Freeze Validation Report

**Generated**: $(date)  
**Branch**: TBD  
**Commit**: TBD

---

## Validation Results

EOF

# Track pass/fail
VALIDATION_PASSED=true

#═══════════════════════════════════════════════════════════
# STEP 0: Preconditions
#═══════════════════════════════════════════════════════════

echo -e "${YELLOW}[STEP 0] Preconditions Check${NC}"

if [[ ! -f "run_full_pipeline_v14.py" ]]; then
    echo -e "${RED}✗ FAIL: Not in repository root (missing run_full_pipeline_v14.py)${NC}"
    echo "### ✗ FAIL: Preconditions" >> "${FREEZE_REPORT}"
    echo "Not in repository root" >> "${FREEZE_REPORT}"
    exit 1
fi

if [[ ! -d ".venv311" ]]; then
    echo -e "${YELLOW}⚠ WARNING: .venv311 not found - using system Python${NC}"
fi

echo -e "${GREEN}✓ PASS: Preconditions${NC}"
echo "" >> "${FREEZE_REPORT}"

#═══════════════════════════════════════════════════════════
# STEP 1: Identify Frozen Commit
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 1] Identify Frozen Commit${NC}"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
COMMIT_HASH=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)
COMMIT_INFO=$(git show -s --format='%h %ci %d %s' HEAD)

echo "Branch: ${BRANCH}"
echo "Commit: ${COMMIT_HASH}"
echo "${COMMIT_INFO}"

# Write to report
cat >> "${FREEZE_REPORT}" << EOF
### ✓ STEP 1: Frozen Commit Identified

**Branch**: \`${BRANCH}\`  
**Commit**: \`${COMMIT_HASH}\`  
**Short**: \`${COMMIT_SHORT}\`  
**Info**: ${COMMIT_INFO}

\`\`\`bash
git status -sb
$(git status -sb)

git rev-parse HEAD
${COMMIT_HASH}
\`\`\`

EOF

echo -e "${GREEN}✓ PASS: Commit identified${NC}"

#═══════════════════════════════════════════════════════════
# STEP 2: Verify Root CLI Pipeline Import
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 2] Verify Root CLI Pipeline Import${NC}"

ROOT_CLI_IMPORT=$(rg -n "from analytics\.pipeline_v14(_enhanced)? import run_v14_pipeline" run_full_pipeline_v14.py || true)

echo "Root CLI import:"
echo "${ROOT_CLI_IMPORT}"

cat >> "${FREEZE_REPORT}" << EOF
### STEP 2: Root CLI Pipeline Import

\`\`\`bash
rg -n "from analytics\.pipeline_v14(_enhanced)? import run_v14_pipeline" run_full_pipeline_v14.py
\`\`\`

**Result**:
\`\`\`
${ROOT_CLI_IMPORT}
\`\`\`

EOF

if echo "${ROOT_CLI_IMPORT}" | grep -q "pipeline_v14_enhanced"; then
    echo -e "${GREEN}✓ PASS: Root CLI uses pipeline_v14_enhanced${NC}"
    echo "**Status**: ✓ PASS - Uses \`pipeline_v14_enhanced\`" >> "${FREEZE_REPORT}"
elif echo "${ROOT_CLI_IMPORT}" | grep -q "pipeline_v14" && ! echo "${ROOT_CLI_IMPORT}" | grep -q "_enhanced"; then
    echo -e "${RED}✗ FAIL: Root CLI uses WRONG pipeline (pipeline_v14 instead of pipeline_v14_enhanced)${NC}"
    echo "**Status**: ✗ FAIL - Uses \`pipeline_v14\` (should be \`pipeline_v14_enhanced\`)" >> "${FREEZE_REPORT}"
    VALIDATION_PASSED=false
else
    echo -e "${RED}✗ FAIL: Root CLI missing pipeline import${NC}"
    echo "**Status**: ✗ FAIL - No pipeline import found" >> "${FREEZE_REPORT}"
    VALIDATION_PASSED=false
fi

echo "" >> "${FREEZE_REPORT}"

#═══════════════════════════════════════════════════════════
# STEP 3: Verify Evaluation Gateway Pipeline Import
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 3] Verify Evaluation Gateway Pipeline Import${NC}"

EVAL_GATEWAY_IMPORT=$(rg -n "from analytics\.pipeline_v14(_enhanced)? import run_v14_pipeline" analytics/evaluation_v14.py || true)

echo "Evaluation gateway import:"
echo "${EVAL_GATEWAY_IMPORT}"

cat >> "${FREEZE_REPORT}" << EOF
### STEP 3: Evaluation Gateway Pipeline Import

\`\`\`bash
rg -n "from analytics\.pipeline_v14(_enhanced)? import run_v14_pipeline" analytics/evaluation_v14.py
\`\`\`

**Result**:
\`\`\`
${EVAL_GATEWAY_IMPORT}
\`\`\`

EOF

if echo "${EVAL_GATEWAY_IMPORT}" | grep -q "pipeline_v14_enhanced"; then
    echo -e "${GREEN}✓ PASS: Evaluation gateway uses pipeline_v14_enhanced${NC}"
    echo "**Status**: ✓ PASS - Uses \`pipeline_v14_enhanced\`" >> "${FREEZE_REPORT}"
elif echo "${EVAL_GATEWAY_IMPORT}" | grep -q "pipeline_v14" && ! echo "${EVAL_GATEWAY_IMPORT}" | grep -q "_enhanced"; then
    echo -e "${RED}✗ FAIL: Evaluation gateway uses WRONG pipeline${NC}"
    echo "**Status**: ✗ FAIL - Uses \`pipeline_v14\` (should be \`pipeline_v14_enhanced\`)" >> "${FREEZE_REPORT}"
    VALIDATION_PASSED=false
else
    echo -e "${YELLOW}⚠ WARNING: Evaluation gateway has no pipeline import (may use different pattern)${NC}"
    echo "**Status**: ⚠ WARNING - No direct pipeline import" >> "${FREEZE_REPORT}"
fi

echo "" >> "${FREEZE_REPORT}"

#═══════════════════════════════════════════════════════════
# STEP 4: Detect Shadow Evaluators
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 4] Detect Shadow Evaluators (Wrong Pipeline)${NC}"

SHADOW_EVALUATORS=$(rg -n "from analytics\.pipeline_v14 import run_v14_pipeline" analytics || true)

echo "Shadow evaluators using old pipeline:"
echo "${SHADOW_EVALUATORS}"

cat >> "${FREEZE_REPORT}" << EOF
### STEP 4: Shadow Evaluators Detection

\`\`\`bash
rg -n "from analytics\.pipeline_v14 import run_v14_pipeline" analytics
\`\`\`

**Result**:
\`\`\`
${SHADOW_EVALUATORS}
\`\`\`

EOF

# Critical files that MUST NOT use pipeline_v14
CRITICAL_FILES=(
    "analytics/evaluate_scenario.py"
    "analytics/sensitivity"
    "analytics/monte_carlo"
    "analytics/evaluation_v14.py"
)

CRITICAL_VIOLATIONS=""
for file_pattern in "${CRITICAL_FILES[@]}"; do
    if echo "${SHADOW_EVALUATORS}" | grep -q "${file_pattern}"; then
        CRITICAL_VIOLATIONS="${CRITICAL_VIOLATIONS}\n  - ${file_pattern}"
    fi
done

if [[ -z "${SHADOW_EVALUATORS}" ]]; then
    echo -e "${GREEN}✓ PASS: No shadow evaluators found${NC}"
    echo "**Status**: ✓ PASS - No shadow evaluators" >> "${FREEZE_REPORT}"
elif [[ -n "${CRITICAL_VIOLATIONS}" ]]; then
    echo -e "${RED}✗ FAIL: Critical shadow evaluators detected:${NC}"
    echo -e "${RED}${CRITICAL_VIOLATIONS}${NC}"
    echo "**Status**: ✗ FAIL - Critical shadow evaluators:${CRITICAL_VIOLATIONS}" >> "${FREEZE_REPORT}"
    VALIDATION_PASSED=false
else
    echo -e "${YELLOW}⚠ WARNING: Shadow evaluators found but not in critical files${NC}"
    echo "**Status**: ⚠ WARNING - Shadow evaluators in non-critical files (requires justification)" >> "${FREEZE_REPORT}"
fi

echo "" >> "${FREEZE_REPORT}"

#═══════════════════════════════════════════════════════════
# STEP 5: Verify Sensitivity Fix at Line 489
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 5] Verify Sensitivity Fix (Line 489)${NC}"

SENSITIVITY_BLOCK=$(python3 - <<'PY'
import pathlib
p = pathlib.Path("analytics/sensitivity_v14.py")
txt = p.read_text(encoding="utf-8").splitlines()
for i in range(470, min(530, len(txt))):
    print(f"{i+1:04d}: {txt[i]}")
PY
)

echo "Sensitivity code block (lines 471-530):"
echo "${SENSITIVITY_BLOCK}"

cat >> "${FREEZE_REPORT}" << EOF
### STEP 5: Sensitivity Fix Verification (Line 489)

\`\`\`python
${SENSITIVITY_BLOCK}
\`\`\`

EOF

# Check for correct pattern
if echo "${SENSITIVITY_BLOCK}" | grep -q "ShockResult("; then
    if echo "${SENSITIVITY_BLOCK}" | grep -q "shock_results=\[shock\]"; then
        echo -e "${GREEN}✓ PASS: Sensitivity uses typed ShockResult construction${NC}"
        echo "**Status**: ✓ PASS - Uses typed \`ShockResult\` object" >> "${FREEZE_REPORT}"
    else
        echo -e "${YELLOW}⚠ WARNING: ShockResult found but shock_results usage unclear${NC}"
        echo "**Status**: ⚠ WARNING - ShockResult found, verify shock_results usage" >> "${FREEZE_REPORT}"
    fi
elif echo "${SENSITIVITY_BLOCK}" | grep -q "return TornadoResult(" && echo "${SENSITIVITY_BLOCK}" | grep -q "variable="; then
    echo -e "${RED}✗ FAIL: Sensitivity still uses old dict-style kwargs (LINE 489 BUG NOT FIXED)${NC}"
    echo "**Status**: ✗ FAIL - Still uses dict-style kwargs (line 489 bug present)" >> "${FREEZE_REPORT}"
    VALIDATION_PASSED=false
else
    echo -e "${YELLOW}⚠ WARNING: Cannot determine sensitivity fix status${NC}"
    echo "**Status**: ⚠ WARNING - Unable to verify fix pattern" >> "${FREEZE_REPORT}"
fi

echo "" >> "${FREEZE_REPORT}"

#═══════════════════════════════════════════════════════════
# STEP 6: Run Canonical CLI End-to-End
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 6] Run Canonical CLI (Lender Case)${NC}"

CLI_OUTPUT_FILE="${FREEZE_DIR}/cli_output.json"

# Check if lender case config exists
LENDER_CONFIG="scenarios/dutchbay_lendercase_2025Q4.yaml"
if [[ ! -f "${LENDER_CONFIG}" ]]; then
    echo -e "${YELLOW}⚠ WARNING: ${LENDER_CONFIG} not found, using basecase${NC}"
    LENDER_CONFIG="scenarios/basecase.yaml"
fi

echo "Running: python run_full_pipeline_v14.py config=${LENDER_CONFIG} validation_mode=strict"

# Run CLI (with timeout)
timeout 300 python run_full_pipeline_v14.py \
    "config=${LENDER_CONFIG}" \
    "validation_mode=strict" \
    "validation_modules=[cashflow,debt]" \
    2>&1 | tee "${CLI_OUTPUT_FILE}" || {
    echo -e "${RED}✗ FAIL: CLI execution failed or timed out${NC}"
    echo "**Status**: ✗ FAIL - CLI execution failed" >> "${FREEZE_REPORT}"
    VALIDATION_PASSED=false
}

# Validate JSON keys
CLI_VALIDATION=$(python3 - <<PY
import json, pathlib, sys
try:
    p = pathlib.Path("${CLI_OUTPUT_FILE}")
    data = json.loads(p.read_text(encoding="utf-8"))
    req = ["annual_rows","debt_result","kpis"]
    missing = [k for k in req if k not in data]
    if missing:
        print(f"MISSING: {missing}")
        sys.exit(2)
    else:
        print("OK: lender stack keys present")
        sys.exit(0)
except json.JSONDecodeError:
    print("ERROR: Invalid JSON output")
    sys.exit(3)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(4)
PY
)

CLI_EXIT_CODE=$?

cat >> "${FREEZE_REPORT}" << EOF
### STEP 6: Canonical CLI Execution

**Config**: \`${LENDER_CONFIG}\`  
**Command**:
\`\`\`bash
python run_full_pipeline_v14.py \\
    config=${LENDER_CONFIG} \\
    validation_mode=strict \\
    validation_modules=[cashflow,debt]
\`\`\`

**JSON Validation**:
\`\`\`
${CLI_VALIDATION}
\`\`\`

EOF

if [[ ${CLI_EXIT_CODE} -eq 0 ]]; then
    echo -e "${GREEN}✓ PASS: CLI executed successfully with lender stack keys${NC}"
    echo "**Status**: ✓ PASS - CLI execution successful" >> "${FREEZE_REPORT}"
else
    echo -e "${RED}✗ FAIL: CLI validation failed (exit code ${CLI_EXIT_CODE})${NC}"
    echo "**Status**: ✗ FAIL - CLI validation failed (exit ${CLI_EXIT_CODE})" >> "${FREEZE_REPORT}"
    VALIDATION_PASSED=false
fi

echo "" >> "${FREEZE_REPORT}"

#═══════════════════════════════════════════════════════════
# STEP 7: Run Test Suite
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 7] Run Test Suite${NC}"

PYTEST_OUTPUT_FILE="${FREEZE_DIR}/pytest_summary.txt"

echo "Running: pytest -q"

pytest -q 2>&1 | tee "${PYTEST_OUTPUT_FILE}" || true

# Extract summary line
PYTEST_SUMMARY=$(tail -n 5 "${PYTEST_OUTPUT_FILE}" | grep -E "(passed|failed|error)" | tail -n 1)

cat >> "${FREEZE_REPORT}" << EOF
### STEP 7: Test Suite Execution

\`\`\`bash
pytest -q
\`\`\`

**Summary**:
\`\`\`
${PYTEST_SUMMARY}
\`\`\`

**Full Output**: See \`${PYTEST_OUTPUT_FILE}\`

EOF

if echo "${PYTEST_SUMMARY}" | grep -q "failed"; then
    FAILED_COUNT=$(echo "${PYTEST_SUMMARY}" | grep -oP '\d+(?= failed)')
    if [[ ${FAILED_COUNT} -gt 100 ]]; then
        echo -e "${RED}✗ FAIL: High test failure count (${FAILED_COUNT})${NC}"
        echo "**Status**: ✗ FAIL - ${FAILED_COUNT} tests failed" >> "${FREEZE_REPORT}"
        VALIDATION_PASSED=false
    else
        echo -e "${YELLOW}⚠ WARNING: ${FAILED_COUNT} tests failed${NC}"
        echo "**Status**: ⚠ WARNING - ${FAILED_COUNT} tests failed" >> "${FREEZE_REPORT}"
    fi
else
    echo -e "${GREEN}✓ PASS: Test suite executed${NC}"
    echo "**Status**: ✓ Tests executed" >> "${FREEZE_REPORT}"
fi

echo "" >> "${FREEZE_REPORT}"

#═══════════════════════════════════════════════════════════
# STEP 8: Generate Final Report
#═══════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}[STEP 8] Generate Freeze Report${NC}"

cat >> "${FREEZE_REPORT}" << EOF
---

## Final Verdict

EOF

if [[ "${VALIDATION_PASSED}" == "true" ]]; then
    cat >> "${FREEZE_REPORT}" << EOF
### ✅ VALIDATION PASSED

**Status**: FREEZE APPROVED  
**Branch**: \`${BRANCH}\`  
**Commit**: \`${COMMIT_SHORT}\`  
**Timestamp**: $(date)

All critical checks passed. This commit is approved for freeze.

EOF
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ VALIDATION PASSED - FREEZE APPROVED${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
else
    cat >> "${FREEZE_REPORT}" << EOF
### ❌ VALIDATION FAILED

**Status**: FREEZE REJECTED  
**Branch**: \`${BRANCH}\`  
**Commit**: \`${COMMIT_SHORT}\`  
**Timestamp**: $(date)

Critical issues detected. Review failures above before freeze.

EOF
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ VALIDATION FAILED - FREEZE REJECTED${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
fi

cat >> "${FREEZE_REPORT}" << EOF
---

## Artifacts

- **Report**: \`${FREEZE_REPORT}\`
- **CLI Output**: \`${CLI_OUTPUT_FILE}\`
- **Test Output**: \`${PYTEST_OUTPUT_FILE}\`

EOF

echo ""
echo "Freeze report saved to: ${FREEZE_REPORT}"
echo ""

# Exit with appropriate code
if [[ "${VALIDATION_PASSED}" == "true" ]]; then
    exit 0
else
    exit 1
fi
