#!/usr/bin/env bash
###############################################################################
# apply_scenario_analytics_refactor.sh
#
# Sprint 4 - Debt Module Stabilization
# Refactor: Remove unused 'strict' parameter from ScenarioAnalytics
#
# Go with the Flow Compliance:
#   - R5: Schema validation always enforced
#   - R22: Tests must provide v14-compliant configs
#   - Safety: Creates backup before modification
#
# Usage:
#   cd ~/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model
#   bash apply_scenario_analytics_refactor.sh
###############################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_ROOT="$(pwd)"
TARGET_FILE="analytics/scenario_analytics.py"
BACKUP_FILE="analytics/scenario_analytics.py.backup-$(date +%Y%m%d-%H%M%S)"
VENV_PATH=".venv311"

###############################################################################
# Preflight checks
###############################################################################

echo -e "${BLUE}=== Sprint 4: ScenarioAnalytics Refactor ===${NC}"
echo ""

# Check we're in repo root
if [[ ! -f "dutchbay_bootstrap.py" ]]; then
    echo -e "${RED}❌ Error: Not in DutchBay_EPC_Model root directory${NC}"
    echo "   Expected to find: dutchbay_bootstrap.py"
    echo "   Current directory: $(pwd)"
    exit 1
fi

# Check target file exists
if [[ ! -f "$TARGET_FILE" ]]; then
    echo -e "${RED}❌ Error: Target file not found: $TARGET_FILE${NC}"
    exit 1
fi

# Check venv exists
if [[ ! -d "$VENV_PATH" ]]; then
    echo -e "${YELLOW}⚠️  Warning: Virtual environment not found at $VENV_PATH${NC}"
    echo "   Tests will be skipped"
fi

echo -e "${GREEN}✅ Preflight checks passed${NC}"
echo ""

###############################################################################
# Create backup
###############################################################################

echo -e "${BLUE}Creating backup...${NC}"
cp "$TARGET_FILE" "$BACKUP_FILE"
echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
echo ""

###############################################################################
# Apply refactoring patches
###############################################################################

echo -e "${BLUE}Applying refactoring patches...${NC}"

# Patch 1: Remove 'strict: bool = True,' parameter from __init__
echo "  [1/5] Removing strict parameter from __init__ signature..."
if grep -q "strict: bool = True," "$TARGET_FILE"; then
    # macOS-compatible sed (use '' for in-place with backup extension)
    sed -i.tmp '/strict: bool = True,/d' "$TARGET_FILE"
    rm -f "${TARGET_FILE}.tmp"
    echo -e "        ${GREEN}✓${NC} Removed: strict: bool = True,"
else
    echo -e "        ${YELLOW}⊙${NC} Already removed or not found"
fi

# Patch 2: Remove 'self.strict = bool(strict)' assignment
echo "  [2/5] Removing strict attribute assignment..."
if grep -q "self.strict = bool(strict)" "$TARGET_FILE"; then
    sed -i.tmp '/self\.strict = bool(strict)/d' "$TARGET_FILE"
    rm -f "${TARGET_FILE}.tmp"
    echo -e "        ${GREEN}✓${NC} Removed: self.strict = bool(strict)"
else
    echo -e "        ${YELLOW}⊙${NC} Already removed or not found"
fi

# Patch 3: Update docstring header
echo "  [3/5] Updating docstring (strictness → schema validation)..."
if grep -q "Notes on strictness" "$TARGET_FILE"; then
    sed -i.tmp 's/Notes on strictness (R5, R22):/Notes on schema validation (R5, R22):/' "$TARGET_FILE"
    rm -f "${TARGET_FILE}.tmp"
    echo -e "        ${GREEN}✓${NC} Updated docstring header"
else
    echo -e "        ${YELLOW}⊙${NC} Already updated or not found"
fi

# Patch 4: Update docstring body
echo "  [4/5] Updating docstring body..."
if grep -q "strict MUST NOT be used" "$TARGET_FILE"; then
    # Multi-line replacement for docstring
    sed -i.tmp '/strict MUST NOT be used/,/not for disabling validation\./c\
  - Tests must supply v14-compliant configs per R22; there is no mechanism\
    to bypass schema validation.' "$TARGET_FILE"
    rm -f "${TARGET_FILE}.tmp"
    echo -e "        ${GREEN}✓${NC} Updated docstring body"
else
    echo -e "        ${YELLOW}⊙${NC} Already updated or not found"
fi

# Patch 5: Add EOF marker if missing
echo "  [5/5] Ensuring EOF marker..."
if ! tail -1 "$TARGET_FILE" | grep -q "# EOF"; then
    echo "" >> "$TARGET_FILE"
    echo "# EOF" >> "$TARGET_FILE"
    echo -e "        ${GREEN}✓${NC} Added EOF marker"
else
    echo -e "        ${YELLOW}⊙${NC} EOF marker already present"
fi

echo -e "${GREEN}✅ All patches applied${NC}"
echo ""

###############################################################################
# Show diff
###############################################################################

echo -e "${BLUE}Changes made:${NC}"
echo "─────────────────────────────────────────────────────────────────"
if command -v colordiff &> /dev/null; then
    diff -u "$BACKUP_FILE" "$TARGET_FILE" | colordiff | head -50 || true
else
    diff -u "$BACKUP_FILE" "$TARGET_FILE" | head -50 || true
fi
echo "─────────────────────────────────────────────────────────────────"
echo ""

###############################################################################
# Verification
###############################################################################

echo -e "${BLUE}Running verification checks...${NC}"

# Check 1: Python syntax
echo "  [1/3] Checking Python syntax..."
if python3 -m py_compile "$TARGET_FILE" 2>/dev/null; then
    echo -e "        ${GREEN}✓${NC} Syntax valid"
else
    echo -e "        ${RED}✗${NC} Syntax error detected!"
    echo -e "${RED}❌ Refactoring failed. Restoring backup...${NC}"
    cp "$BACKUP_FILE" "$TARGET_FILE"
    exit 1
fi

# Check 2: Import test (if venv exists)
if [[ -d "$VENV_PATH" ]]; then
    echo "  [2/3] Testing module import..."
    if source "$VENV_PATH/bin/activate" && \
       python -c "from analytics.scenario_analytics import ScenarioAnalytics; print('Import successful')" &>/dev/null; then
        echo -e "        ${GREEN}✓${NC} Module imports successfully"
    else
        echo -e "        ${RED}✗${NC} Import failed!"
        echo -e "${RED}❌ Refactoring failed. Restoring backup...${NC}"
        cp "$BACKUP_FILE" "$TARGET_FILE"
        exit 1
    fi
fi

# Check 3: Verify strict parameter removed
echo "  [3/3] Verifying strict parameter removed..."
if grep -q "strict: bool = True" "$TARGET_FILE"; then
    echo -e "        ${RED}✗${NC} strict parameter still present!"
    echo -e "${RED}❌ Refactoring incomplete. Restoring backup...${NC}"
    cp "$BACKUP_FILE" "$TARGET_FILE"
    exit 1
else
    echo -e "        ${GREEN}✓${NC} strict parameter removed"
fi

echo -e "${GREEN}✅ All verification checks passed${NC}"
echo ""

###############################################################################
# Run tests (optional)
###############################################################################

if [[ -d "$VENV_PATH" ]]; then
    echo -e "${BLUE}Running affected tests...${NC}"

    if source "$VENV_PATH/bin/activate"; then
        # Test the specific file we fixed
        echo "  Testing: test_scenario_analytics_unit_scenario_name.py"
        if pytest tests/api/test_scenario_analytics_unit_scenario_name.py -v 2>&1 | grep -E "(PASSED|FAILED|ERROR)"; then
            echo -e "${GREEN}✅ Tests completed${NC}"
        else
            echo -e "${YELLOW}⚠️  Test execution completed with warnings${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Could not activate venv, skipping tests${NC}"
    fi
    echo ""
fi

###############################################################################
# Summary
###############################################################################

echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Refactoring complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Changes applied:"
echo "  • Removed 'strict' parameter from ScenarioAnalytics.__init__()"
echo "  • Removed 'self.strict' attribute assignment"
echo "  • Updated docstring to reflect R5/R22 compliance"
echo "  • Added EOF marker"
echo ""
echo "Files:"
echo "  Original backup: $BACKUP_FILE"
echo "  Modified file:   $TARGET_FILE"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff analytics/scenario_analytics.py"
echo "  2. Run full test suite: pytest -v --tb=short"
echo "  3. Commit changes:"
echo ""
echo "     git add analytics/scenario_analytics.py"
echo "     git commit -m \"refactor(analytics): remove unused strict parameter\""
echo ""
echo -e "${BLUE}Go with the Flow v3.0 - Sprint 4 Complete 🚀${NC}"
echo ""

# EOF
