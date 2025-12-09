#!/bin/bash
# Fix pre-commit hook violations for Sprint 9
# Generated: 2025-12-08 17:55 IST

set -e

echo "🔧 Fixing Pre-Commit Hook Violations..."
echo "══════════════════════════════════════════════════════════════════"

# Step 1: Apply isort formatting
echo ""
echo "📝 Step 1: Running isort to fix import ordering..."
python -m isort analytics/evaluation_v14.py
python -m isort finance/cashflow_v14.py
python -m isort finance/cashflow_v14_fx.py
echo "✅ isort complete"

# Step 2: Run flake8/ruff to check E402
echo ""
echo "📝 Step 2: Checking for import order issues..."
python -m ruff check --select E402 analytics/evaluation_v14.py --fix || true
echo "ℹ️  Note: E402 errors need manual fix if they persist"

# Step 3: Remove trailing whitespace using sed
echo ""
echo "📝 Step 3: Removing trailing whitespace..."
# macOS-compatible sed
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' 's/[[:space:]]*$//' fix_monte_carlo.patch
    sed -i '' 's/[[:space:]]*$//' commit_sprint9.sh
else
    sed -i 's/[[:space:]]*$//' fix_monte_carlo.patch
    sed -i 's/[[:space:]]*$//' commit_sprint9.sh
fi
echo "✅ Trailing whitespace removed"

# Step 4: Stage the fixed files
echo ""
echo "📝 Step 4: Staging fixed files..."
git add analytics/evaluation_v14.py
git add finance/cashflow_v14.py
git add finance/cashflow_v14_fx.py
git add fix_monte_carlo.patch
git add commit_sprint9.sh
echo "✅ Files staged"

# Step 5: Run pre-commit again
echo ""
echo "📝 Step 5: Running pre-commit checks again..."
if pre-commit run --all-files; then
    echo ""
    echo "✅ All pre-commit checks passed!"
    echo ""
    echo "📊 Current status:"
    git status --short
    echo ""
    echo "🎉 Ready to commit!"
    echo ""
    echo "Next: Run git commit with Sprint 9 message"
else
    echo ""
    echo "⚠️  Some checks still failing. Review errors above."
    echo ""
    echo "Common fixes:"
    echo "  1. E402: Move docstring after imports in evaluation_v14.py"
    echo "  2. Check line lengths (max 100 chars)"
    echo "  3. Ensure no trailing spaces: git diff --check"
    exit 1
fi

echo "══════════════════════════════════════════════════════════════════"
