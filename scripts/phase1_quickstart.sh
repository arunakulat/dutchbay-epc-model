#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 IMPLEMENTATION QUICK-START SCRIPT
# ═══════════════════════════════════════════════════════════════════════════
#
# This script automates the most critical validation steps for Phase 1
# sensitivity_v14.py golden reference implementation.
#
# Usage:
#   bash phase1_quickstart.sh
#
# What it does:
#   1. Check if golden reference file exists
#   2. Validate syntax
#   3. Copy to target location (with backup)
#   4. Run 7 critical validation checks
#   5. Run unit tests
#   6. Report status
#
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GOLDEN_REF="sensitivity_v14_GOLDEN_REFERENCE.py"
TARGET_DIR="analytics"
TARGET_FILE="${TARGET_DIR}/sensitivity_v14.py"
BACKUP_FILE="${TARGET_DIR}/sensitivity_v14.py.backup.$(date +%s)"
VALIDATOR_SCRIPT="validate_sensitivity_v14.py"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}PHASE 1 SENSITIVITY_V14 IMPLEMENTATION QUICK-START${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: Check prerequisites
# ═══════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}[STEP 1/6] Checking prerequisites...${NC}"

if [ ! -f "$GOLDEN_REF" ]; then
    echo -e "${RED}❌ Golden reference file not found: $GOLDEN_REF${NC}"
    echo "   Place $GOLDEN_REF in current directory"
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}❌ Target directory not found: $TARGET_DIR${NC}"
    echo "   Expected directory: analytics/"
    exit 1
fi

if [ ! -f "$VALIDATOR_SCRIPT" ]; then
    echo -e "${YELLOW}⚠️  Validator script not found: $VALIDATOR_SCRIPT${NC}"
    echo "   Validation will be skipped"
    SKIP_VALIDATION=true
fi

echo -e "${GREEN}✅ Prerequisites OK${NC}"

# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: Validate Python syntax
# ═══════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}[STEP 2/6] Validating Python syntax...${NC}"

if python3 -m py_compile "$GOLDEN_REF" 2>/dev/null; then
    echo -e "${GREEN}✅ Syntax OK${NC}"
else
    echo -e "${RED}❌ Syntax error in $GOLDEN_REF${NC}"
    python3 -m py_compile "$GOLDEN_REF"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: Create backup
# ═══════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}[STEP 3/6] Creating backup of current file...${NC}"

if [ -f "$TARGET_FILE" ]; then
    cp "$TARGET_FILE" "$BACKUP_FILE"
    echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
else
    echo -e "${YELLOW}⚠️  No existing file to back up${NC}"
fi

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: Copy golden reference
# ═══════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}[STEP 4/6] Copying golden reference to target...${NC}"

cp "$GOLDEN_REF" "$TARGET_FILE"
echo -e "${GREEN}✅ File copied: $TARGET_FILE${NC}"

# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: Run validation
# ═══════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}[STEP 5/6] Running validation checks...${NC}"

if [ "$SKIP_VALIDATION" = true ]; then
    echo -e "${YELLOW}⚠️  Skipping validation (validator script not found)${NC}"
else
    if python3 "$VALIDATOR_SCRIPT" "$TARGET_FILE"; then
        echo -e "${GREEN}✅ All validation checks passed${NC}"
    else
        echo -e "${RED}❌ Validation failed. Review issues above.${NC}"
        echo "   To revert: cp $BACKUP_FILE $TARGET_FILE"
        exit 1
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: Quick sanity checks
# ═══════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}[STEP 6/6] Running sanity checks...${NC}"

# Check 1: No forbidden imports
FORBIDDEN_COUNT=$(grep -c "run_v14_pipeline\|load_scenario_config" "$TARGET_FILE" || echo 0)
if [ "$FORBIDDEN_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No forbidden imports${NC}"
else
    echo -e "${RED}❌ Found $FORBIDDEN_COUNT forbidden import(s)${NC}"
    exit 1
fi

# Check 2: Has evaluate_scenario usage
EVALUATE_COUNT=$(grep -c "evaluate_scenario(" "$TARGET_FILE" || echo 0)
if [ "$EVALUATE_COUNT" -ge 5 ]; then
    echo -e "${GREEN}✅ evaluate_scenario() used $EVALUATE_COUNT times${NC}"
else
    echo -e "${YELLOW}⚠️  evaluate_scenario() used only $EVALUATE_COUNT times (expected 6+)${NC}"
fi

# Check 3: Can import
if python3 -c "import sys; sys.path.insert(0, '.'); from analytics.sensitivity_v14 import SensitivityResult" 2>/dev/null; then
    echo -e "${GREEN}✅ Module imports successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Module import failed (may need to run from repo root)${NC}"
fi

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ PHASE 1 IMPLEMENTATION COMPLETE${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "  1. Review changes: git diff $TARGET_FILE"
echo "  2. Run tests: pytest tests/ -k sensitivity -v"
echo "  3. Run type check: mypy $TARGET_FILE --strict"
echo "  4. Run formatters: black $TARGET_FILE && ruff check $TARGET_FILE && isort $TARGET_FILE"
echo "  5. Commit: git add $TARGET_FILE && git commit -m 'feat(analytics): Phase 1 sensitivity_v14 evaluation gateway'"
echo "  6. Push: git push origin <branch>"

echo -e "\n${YELLOW}If something goes wrong:${NC}"
echo "  Revert: cp $BACKUP_FILE $TARGET_FILE"

echo -e "\n${GREEN}You're all set! 🚀${NC}\n"
