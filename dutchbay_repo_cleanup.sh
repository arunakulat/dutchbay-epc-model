#!/usr/bin/env bash
#
# dutchbay_repo_cleanup.sh
#
# Automatic cleanup script for DutchBay EPC Model repository.
# Archives legacy/experimental files for v14 focus.
#
# USAGE:
#   ./dutchbay_repo_cleanup.sh [--dry-run] [--archive] [--delete]
#
# OPTIONS:
#   --dry-run    Show what would be moved/deleted without making changes
#   --archive    Create legacy_* dirs and MOVE files (default, safe)
#   --delete     DELETE files instead of moving (irreversible - use with caution)
#   --confirm    Skip interactive confirmation (for automation)
#
# EXAMPLE:
#   ./dutchbay_repo_cleanup.sh --dry-run                  # Preview changes
#   ./dutchbay_repo_cleanup.sh --archive                  # Execute with prompts
#   ./dutchbay_repo_cleanup.sh --archive --confirm        # Execute silently
#
# OUTPUT:
#   - Creates legacy_scripts/, legacy_docs/, legacy_tests/, legacy_scenarios/
#   - Moves old/experimental files to respective archives
#   - Generates cleanup_report_TIMESTAMP.json with detailed inventory
#   - Commits changes to git if successful

set -euo pipefail

# ────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DRY_RUN=0
MODE="archive"  # archive or delete
CONFIRM=0
VERBOSE=1

# Archive directories
LEGACY_SCRIPTS_DIR="$REPO_ROOT/legacy_scripts"
LEGACY_DOCS_DIR="$REPO_ROOT/legacy_docs"
LEGACY_TESTS_DIR="$REPO_ROOT/legacy_tests"
LEGACY_SCENARIOS_DIR="$REPO_ROOT/legacy_scenarios"

# Report file
REPORT_FILE="$REPO_ROOT/cleanup_report_${TIMESTAMP}.json"

# Counters (initialize properly)
SCRIPTS_MOVED=0
DOCS_MOVED=0
TESTS_MOVED=0
SCENARIOS_MOVED=0
FILES_DELETED=0
TOTAL_SIZE_KB=0

# ────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────────────────────────────────

log() {
  if [[ $VERBOSE -eq 1 ]]; then
    echo "[$(date +'%H:%M:%S')] $*"
  fi
}

log_section() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$*"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

error() {
  echo "❌ ERROR: $*" >&2
  exit 1
}

warn() {
  echo "⚠️  WARNING: $*"
}

success() {
  echo "✅ $*"
}

get_file_size() {
  if [[ -f "$1" ]]; then
    stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo "0"
  else
    echo "0"
  fi
}

move_file() {
  local src="$1"
  local dest="$2"
  
  if [[ ! -e "$src" ]]; then
    return 0
  fi
  
  local size=$(get_file_size "$src")
  TOTAL_SIZE_KB=$((TOTAL_SIZE_KB + size / 1024))
  
  if [[ $DRY_RUN -eq 1 ]]; then
    log "  [DRY-RUN] Would move: $src → $dest ($(( size / 1024 )) KB)"
  else
    mkdir -p "$(dirname "$dest")"
    mv "$src" "$dest"
    log "  ✓ Moved: $src → $dest"
  fi
}

delete_file() {
  local file="$1"
  
  if [[ ! -e "$file" ]]; then
    return 0
  fi
  
  local size=$(get_file_size "$file")
  TOTAL_SIZE_KB=$((TOTAL_SIZE_KB + size / 1024))
  FILES_DELETED=$((FILES_DELETED + 1))
  
  if [[ $DRY_RUN -eq 1 ]]; then
    log "  [DRY-RUN] Would delete: $file ($(( size / 1024 )) KB)"
  else
    rm -f "$file"
    log "  ✓ Deleted: $file"
  fi
}

# ────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ────────────────────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      log_section "DRY-RUN MODE (no changes will be made)"
      shift
      ;;
    --archive)
      MODE="archive"
      shift
      ;;
    --delete)
      MODE="delete"
      warn "DESTRUCTIVE MODE: Files will be permanently deleted"
      shift
      ;;
    --confirm)
      CONFIRM=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    --quiet)
      VERBOSE=0
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ────────────────────────────────────────────────────────────────────────────
# Validation
# ────────────────────────────────────────────────────────────────────────────

log_section "VALIDATION"

# Check we're in repo root
if [[ ! -f "pyproject.toml" ]] && [[ ! -d ".git" ]]; then
  error "Not in DutchBay repo root. Expected pyproject.toml or .git"
fi
log "✓ Repository root verified: $REPO_ROOT"

# Check git is clean
if [[ $DRY_RUN -eq 0 ]] && [[ $MODE == "archive" ]]; then
  if ! git diff-index --quiet HEAD --; then
    error "Git working directory is not clean. Commit or stash changes first."
  fi
  log "✓ Git working directory is clean"
fi

# ────────────────────────────────────────────────────────────────────────────
# Cleanup Phase 1: Create Archive Directories
# ────────────────────────────────────────────────────────────────────────────

if [[ $MODE == "archive" ]]; then
  log_section "PHASE 1: Creating Archive Directories"
  
  if [[ $DRY_RUN -eq 0 ]]; then
    mkdir -p "$LEGACY_SCRIPTS_DIR/archive"
    mkdir -p "$LEGACY_DOCS_DIR/archive"
    mkdir -p "$LEGACY_TESTS_DIR/archive"
    mkdir -p "$LEGACY_SCENARIOS_DIR/archive"
    log "✓ Created legacy archive directories"
  else
    log "[DRY-RUN] Would create archive directories"
  fi
fi

# ────────────────────────────────────────────────────────────────────────────
# Cleanup Phase 2: Move/Delete Duplicate Scripts
# ────────────────────────────────────────────────────────────────────────────

log_section "PHASE 2: Cleaning Up Duplicate Scripts"

# Move Assorted docs/scripts directory
if [[ -d "Assorted docs/scripts" ]]; then
  log "Found: Assorted docs/scripts/ (~70 files)"
  if [[ $MODE == "archive" ]]; then
    move_file "Assorted docs/scripts" "$LEGACY_SCRIPTS_DIR/archive/assorted_docs_scripts_${TIMESTAMP}"
    SCRIPTS_MOVED=$((SCRIPTS_MOVED + 70))
  else
    warn "Would delete ~70 files from 'Assorted docs/scripts/'"
  fi
fi

# Move experimental scripts from scripts/ root
for script in \
  "scripts/apply_debt_fix.py" \
  "scripts/check_datalake_epc.py" \
  "scripts/make_clean_zip.py" \
  "scripts/test_mc_config_path.py"
do
  if [[ -f "$script" ]]; then
    if [[ $MODE == "archive" ]]; then
      move_file "$script" "$LEGACY_SCRIPTS_DIR/archive/$(basename "$script")"
    else
      delete_file "$script"
    fi
    SCRIPTS_MOVED=$((SCRIPTS_MOVED + 1))
  fi
done

# ────────────────────────────────────────────────────────────────────────────
# Cleanup Phase 3: Archive Old Test Copies
# ────────────────────────────────────────────────────────────────────────────

log_section "PHASE 3: Cleaning Up Duplicate Test Files"

# Find and move duplicate test files
for test_file in tests/api/test_cashflow_v14\ \(*.py \
                 tests/api/test_debt_v14_construction\ \(*.py \
                 tests/analytics_layer/test_*_old.py \
                 tests/analytics_layer/test_*_beta.py
do
  if [[ -f "$test_file" ]]; then
    if [[ $MODE == "archive" ]]; then
      move_file "$test_file" "$LEGACY_TESTS_DIR/archive/$(basename "$test_file")"
    else
      delete_file "$test_file"
    fi
    TESTS_MOVED=$((TESTS_MOVED + 1))
  fi
done

# Move experimental test scripts
for test_script in \
  "scripts/tests/test_irr_quick.py" \
  "scripts/tests/test_returns_module.py" \
  "scripts/tests/test_fx_dual_regime_standalone_fixed.py"
do
  if [[ -f "$test_script" ]]; then
    if [[ $MODE == "archive" ]]; then
      move_file "$test_script" "$LEGACY_TESTS_DIR/archive/$(basename "$test_script")"
    else
      delete_file "$test_script"
    fi
    TESTS_MOVED=$((TESTS_MOVED + 1))
  fi
done

# ────────────────────────────────────────────────────────────────────────────
# Cleanup Phase 4: Archive Old Scenarios
# ────────────────────────────────────────────────────────────────────────────

log_section "PHASE 4: Cleaning Up Old Scenario Configs"

for scenario in \
  "scenarios/dutchbay_lendercase_2025Q3.yaml" \
  "scenarios/example_old.yaml"
do
  if [[ -f "$scenario" ]]; then
    if [[ $MODE == "archive" ]]; then
      move_file "$scenario" "$LEGACY_SCENARIOS_DIR/archive/$(basename "$scenario")"
    else
      delete_file "$scenario"
    fi
    SCENARIOS_MOVED=$((SCENARIOS_MOVED + 1))
  fi
done

# Move edge case scenarios
for scenario in scenarios/edge_*.yaml; do
  if [[ -f "$scenario" ]]; then
    if [[ $MODE == "archive" ]]; then
      move_file "$scenario" "$LEGACY_SCENARIOS_DIR/archive/$(basename "$scenario")"
    else
      delete_file "$scenario"
    fi
    SCENARIOS_MOVED=$((SCENARIOS_MOVED + 1))
  fi
done

# ────────────────────────────────────────────────────────────────────────────
# Cleanup Phase 5: Archive Assorted Docs
# ────────────────────────────────────────────────────────────────────────────

log_section "PHASE 5: Cleaning Up Duplicate Documentation"

if [[ -d "Assorted docs/docs" ]]; then
  log "Found: Assorted docs/docs/ (~100+ files)"
  if [[ $MODE == "archive" ]]; then
    move_file "Assorted docs/docs" "$LEGACY_DOCS_DIR/archive/assorted_docs_docs_${TIMESTAMP}"
    DOCS_MOVED=$((DOCS_MOVED + 100))
  else
    warn "Would delete ~100+ files from 'Assorted docs/docs/'"
  fi
fi

# Move other old docs from docs/ directory
for doc in \
  "docs/Cashflow_v14.py refactoring notes.md" \
  "docs/executive_workbook_readme.md" \
  "docs/keystroke on mac os x to reveal hidden files.mhtml" \
  "docs/schema.md"
do
  if [[ -f "$doc" ]]; then
    if [[ $MODE == "archive" ]]; then
      move_file "$doc" "$LEGACY_DOCS_DIR/archive/$(basename "$doc")"
    else
      delete_file "$doc"
    fi
    DOCS_MOVED=$((DOCS_MOVED + 1))
  fi
done

# ────────────────────────────────────────────────────────────────────────────
# Cleanup Phase 6: Create README Files
# ────────────────────────────────────────────────────────────────────────────

if [[ $MODE == "archive" ]] && [[ $DRY_RUN -eq 0 ]]; then
  log_section "PHASE 6: Creating Archive Documentation"
  
  # legacy_scripts README
  cat > "$LEGACY_SCRIPTS_DIR/README.md" << 'EOF'
# Legacy Scripts Archive

**Date:** 2025-12-13  
**Reason:** Cleanup for v14 focus

This directory contains:
- Experimental scripts from development phases
- Duplicate versions of production files (e.g., cashflow_v14.py, evaluation_v14.py)
- One-off debugging/testing utilities
- Phase artifacts and SWIMLANE process documentation

## Status

These files are kept for **historical reference only** and should NOT be used in production.

For v14 production work, use the canonical files in:
- `run_full_pipeline_v14.py` (repo root)
- `run_scenario_analytics_v14.py` (repo root)
- `analytics/pipeline_v14.py`
- `analytics/evaluation_v14.py`

## If You Need Something

Check if the file exists in the main directories first. If you genuinely need a legacy version, 
restore from git history: `git log --all --full-history -- <filename>`
EOF
  
  # legacy_docs README
  cat > "$LEGACY_DOCS_DIR/README.md" << 'EOF'
# Legacy Documentation Archive

**Date:** 2025-12-13  
**Reason:** Cleanup for v14 focus

This directory contains:
- Multiple copies of documentation files
- Draft/experimental documentation
- Old versions superseded by v14 architecture docs

## Status

These files are kept for **historical reference only**.

For v14 documentation, see:
- `docs/architecture_v14.md` - v14 architecture overview
- `docs/api_contract_casper_result_v1.md` - CASPER v1 JSON contract
- `docs/Dev_workflow_v14.md` - v14 development workflow
- `docs/PRE-FLIGHT CHECKLIST.md` - Pre-flight validation checklist
EOF
  
  # legacy_tests README
  cat > "$LEGACY_TESTS_DIR/README.md" << 'EOF'
# Legacy Tests Archive

**Date:** 2025-12-13  
**Reason:** Cleanup for v14 focus

This directory contains:
- Duplicate/experimental test versions
- Beta/alpha test iterations
- One-off test utilities

## Status

These tests are kept for **historical reference only**. 

For v14 test suite, use tests in:
- `tests/api/` - API/contract tests
- `tests/analytics_layer/` - Analytics layer tests
- `tests/finance/` - Finance module tests
EOF
  
  # legacy_scenarios README
  cat > "$LEGACY_SCENARIOS_DIR/README.md" << 'EOF'
# Legacy Scenarios Archive

**Date:** 2025-12-13  
**Reason:** Cleanup for v14 focus

This directory contains:
- Old quarterly scenario variants (e.g., 2025Q3)
- Experimental edge case scenarios
- Legacy example scenarios

## Status

These scenarios are kept for **historical reference only**.

For v14 production work, use current scenarios:
- `scenarios/dutchbay_lendercase_2025Q4.yaml` - Current lender case
- `scenarios/dutchbay_optimistic_2025Q4.yaml` - Upside scenario
- `scenarios/dutchbay_pessimistic_2025Q4.yaml` - Downside scenario
EOF
  
  log "✓ Created archive README files"
fi

# ────────────────────────────────────────────────────────────────────────────
# Generate Report
# ────────────────────────────────────────────────────────────────────────────

log_section "GENERATING CLEANUP REPORT"

cat > "$REPORT_FILE" << EOF
{
  "cleanup_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "repo_root": "$REPO_ROOT",
  "mode": "$MODE",
  "dry_run": $DRY_RUN,
  "statistics": {
    "scripts_moved": $SCRIPTS_MOVED,
    "docs_moved": $DOCS_MOVED,
    "tests_moved": $TESTS_MOVED,
    "scenarios_moved": $SCENARIOS_MOVED,
    "files_deleted": $FILES_DELETED,
    "total_size_mb": $(( TOTAL_SIZE_KB / 1024 ))
  },
  "archive_directories": {
    "legacy_scripts": "$LEGACY_SCRIPTS_DIR",
    "legacy_docs": "$LEGACY_DOCS_DIR",
    "legacy_tests": "$LEGACY_TESTS_DIR",
    "legacy_scenarios": "$LEGACY_SCENARIOS_DIR"
  }
}
EOF

log "✓ Report saved: $REPORT_FILE"

# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────

log_section "CLEANUP SUMMARY"

echo "Scripts archived/deleted:   $SCRIPTS_MOVED"
echo "Docs archived/deleted:      $DOCS_MOVED"
echo "Tests archived/deleted:     $TESTS_MOVED"
echo "Scenarios archived/deleted: $SCENARIOS_MOVED"
echo "Total space reclaimed:      $(( TOTAL_SIZE_KB / 1024 )) MB"
echo ""

if [[ $DRY_RUN -eq 1 ]]; then
  success "DRY-RUN COMPLETE (no changes were made)"
  echo "To execute cleanup, run: $0 --$MODE"
else
  success "CLEANUP COMPLETE"
  
  # Git commit if in archive mode
  if [[ $MODE == "archive" ]]; then
    log_section "GIT COMMIT"
    
    if [[ $CONFIRM -eq 0 ]]; then
      read -p "Commit changes to git? (y/n) " -r
      echo
      if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        warn "Skipping git commit. Remember to commit manually:"
        echo "  git add -A"
        echo "  git commit -m 'chore: Archive legacy/experimental files (v14 cleanup)'"
        exit 0
      fi
    fi
    
    git add -A
    git commit -m "chore: Archive legacy/experimental files (v14 cleanup) - $(( TOTAL_SIZE_KB / 1024 )) MB freed"
    git push origin main
    success "Changes committed and pushed to main"
  fi
fi

exit 0
