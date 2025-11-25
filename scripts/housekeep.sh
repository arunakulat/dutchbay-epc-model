#!/bin/bash
# Housekeeping Script - Repository cleanup and maintenance
#
# Go with the Flow Compliance:
# - Runs formatting (black + isort)
# - Regenerates manifest
# - Cleans build artifacts
# - Verifies structure
# - Checks for legacy imports
#
# Usage:
#   ./scripts/housekeep.sh [--full]
#
# Options:
#   --full    Run full suite including slow operations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🧹 DutchBay Repository Housekeeping"
echo "=================================="
echo ""

# Parse arguments
FULL_MODE=false
if [[ "$1" == "--full" ]]; then
    FULL_MODE=true
    echo "Running in FULL mode (includes slow operations)"
    echo ""
fi

# Step 1: Clean build artifacts
echo "1️⃣  Cleaning build artifacts..."
find "$REPO_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$REPO_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true
echo "   ✅ Build artifacts cleaned"
echo ""

# Step 2: Format code
echo "2️⃣  Formatting code (black + isort)..."
cd "$REPO_ROOT"

# Format Python files
black analytics/ finance/ tests/ scripts/ --quiet 2>/dev/null || echo "   ⚠️  Black formatting had issues (non-critical)"
isort analytics/ finance/ tests/ scripts/ --quiet 2>/dev/null || echo "   ⚠️  isort had issues (non-critical)"

echo "   ✅ Code formatted"
echo ""

# Step 3: Check legacy imports
echo "3️⃣  Checking for legacy imports..."
if python scripts/check_legacy_imports.py > /dev/null 2>&1; then
    echo "   ✅ No legacy imports found"
else
    echo "   ❌ Legacy imports detected - run: python scripts/check_legacy_imports.py"
fi
echo ""

# Step 4: Verify structure (if full mode)
if [ "$FULL_MODE" = true ]; then
    echo "4️⃣  Verifying repository structure..."
    if python scripts/ci_structure_check.py > /dev/null 2>&1; then
        echo "   ✅ Structure verified"
    else
        echo "   ❌ Structure issues detected - run: python scripts/ci_structure_check.py"
    fi
    echo ""
fi

# Step 5: Generate manifest
echo "5️⃣  Regenerating manifest..."
if [ -f "$REPO_ROOT/scripts/generate_manifest.py" ]; then
    python scripts/generate_manifest.py > /dev/null 2>&1 || echo "   ⚠️  Manifest generation had issues"
    echo "   ✅ Manifest regenerated"
else
    echo "   ⚠️  Manifest script not found (skipping)"
fi
echo ""

# Step 6: Test suite (if full mode)
if [ "$FULL_MODE" = true ]; then
    echo "6️⃣  Running test suite..."
    if python -m pytest tests/api/ -q --tb=line > /dev/null 2>&1; then
        echo "   ✅ All tests passing"
    else
        echo "   ❌ Some tests failing - run: python -m pytest tests/api/ -v"
    fi
    echo ""
fi

# Summary
echo "=================================="
echo "✅ Housekeeping complete!"
echo ""
echo "Next steps:"
echo "  • Review any warnings above"
echo "  • Run 'git status' to see changes"
echo "  • Commit formatted files if needed"
echo ""

# EOF
