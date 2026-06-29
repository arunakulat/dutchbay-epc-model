#!/bin/bash
# Apply the correct fix for Pydantic v2 migration

set -e

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Pydantic v2 Migration - Correct Fix Application"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "📦 Step 1: Reverting Phase 2 bad changes..."
echo ""

# Rollback to before Phase 2
git checkout 39f61d2 -- tests/finance/test_contracts.py 2>/dev/null || true
git checkout 39f61d2 -- tests/analytics_layer/ 2>/dev/null || true
git checkout 39f61d2 -- tests/contracts/ 2>/dev/null || true
git checkout 39f61d2 -- tests/_quarantine/ 2>/dev/null || true

echo "✅ Reverted Phase 2 test changes"
echo ""

echo "⚠️  Step 2: Manual fix required for analytics/sensitivity_v14.py"
echo ""
echo "The script CANNOT automatically fix line 489 safely."
echo "You MUST manually edit the file."
echo ""
echo "See: FIX_SENSITIVITY_LINE_489.py for exact code to paste"
echo "See: PYDANTIC_V2_FINAL_FIX_GUIDE.md for full instructions"
echo ""
echo "Quick summary:"
echo ""
echo "  1. Open: analytics/sensitivity_v14.py"
echo "  2. Find: line ~489 with 'return TornadoResult({'"
echo "  3. Replace with code from FIX_SENSITIVITY_LINE_489.py"
echo ""
echo "Press ENTER after you've made the edit..."
read -r

echo ""
echo "🧪 Step 3: Testing the fix..."
echo ""

echo "Testing TornadoResult construction..."
if pytest tests/finance/test_contracts.py::TestTornadoResult::test_basic_creation -xvs --tb=short; then
    echo ""
    echo "✅ TornadoResult fix works!"
    echo ""
else
    echo ""
    echo "❌ TornadoResult still failing"
    echo ""
    echo "Check that you:"
    echo "  1. Imported ShockResult at top of file"
    echo "  2. Used exact code from FIX_SENSITIVITY_LINE_489.py"
    echo "  3. All variables are in scope (variable_name, base_value, etc)"
    echo ""
    exit 1
fi

echo "Testing all TornadoResult tests..."
if pytest tests/finance/test_contracts.py::TestTornadoResult -xvs --tb=line; then
    echo ""
    echo "✅ All TornadoResult tests pass!"
    echo ""
else
    echo ""
    echo "⚠️  Some TornadoResult tests still failing"
    echo ""
fi

echo "Testing full contracts suite..."
if pytest tests/finance/test_contracts.py -v --tb=line; then
    PASSED=$(pytest tests/finance/test_contracts.py -v --tb=line 2>&1 | grep -o '[0-9]* passed' | grep -o '[0-9]*')
    echo ""
    echo "✅ Contracts: $PASSED/33 passing"
    echo ""
else
    echo ""
    echo "⚠️  Some contract tests failing"
    echo ""
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Fix Application Complete"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
echo "1. Run full test suite:"
echo "   pytest --tb=short -q"
echo ""
echo "2. Expected: ~520-530 tests passing (up from 494)"
echo ""
echo "3. Commit the fix:"
echo "   git add -A"
echo "   git commit -m 'fix: correct TornadoResult construction'"
echo "   git push origin feature/add-finance-contracts-pydantic-v2-20251219"
echo ""
echo "4. Address remaining ~50-60 failures (tax config, field names)"
echo ""
