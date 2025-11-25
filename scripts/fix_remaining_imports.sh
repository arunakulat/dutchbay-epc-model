#!/bin/bash
# Direct fix for remaining module alias imports
# Go with the Flow compliant: preserves formatting, precise replacements

set -e

echo "🔄 Fixing remaining module alias imports..."

# Fix: from dutchbay_v14chat.finance import cashflow as X
# To:   from finance import cashflow_v14 as X
find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's/from dutchbay_v14chat\.finance import cashflow as/from finance import cashflow_v14 as/g' {} \;

# Fix: from dutchbay_v14chat.finance import debt as X
# To:   from finance import debt_v14 as X
find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's/from dutchbay_v14chat\.finance import debt as/from finance import debt_v14 as/g' {} \;

# Fix: from dutchbay_v14chat.finance import irr as X
# To:   from finance import irr as X (no suffix for IRR)
find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's/from dutchbay_v14chat\.finance import irr as/from finance import irr as/g' {} \;

echo "✅ Fixed module alias imports"

# Also fix comments and docstrings mentioning the old path
find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's/dutchbay_v14chat\.finance\.cashflow/finance.cashflow_v14/g' {} \;

find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's/dutchbay_v14chat\.finance\.debt/finance.debt_v14/g' {} \;

find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's/dutchbay_v14chat\.finance\.irr/finance.irr/g' {} \;

find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's/dutchbay_v14chat\.finance\.v14\./analytics./g' {} \;

echo "✅ Fixed docstring references"

# Fix path assertions in tests
find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's|dutchbay_v14chat/finance/cashflow\.py|finance/cashflow_v14.py|g' {} \;

find tests/api/ -name "test_*.py" -type f -exec sed -i '' \
  's|dutchbay_v14chat/finance/debt|finance/debt_v14|g' {} \;

echo "✅ Fixed path assertions"

echo ""
echo "📋 Verification:"
echo "  python scripts/check_legacy_imports.py"
