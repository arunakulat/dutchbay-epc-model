#!/bin/bash
# Phase 2: Targeted fixes for remaining test failures

set -e

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Phase 2: Targeted Test Fixes"
echo "  (Based on actual pytest errors)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Fix 1: TornadoResult.model_validate() calls
echo "🔧 Fix 1/3: Replacing TornadoResult.model_validate() with direct calls..."
if [ -f "scripts/fix_sensitivity_v14_tornado.py" ]; then
    python scripts/fix_sensitivity_v14_tornado.py
else
    echo "⏭️  Already applied"
fi
echo ""

# Fix 2: Field name mismatches in tests
echo "📝 Fix 2/3: Updating deprecated field names in tests..."
if [ -f "scripts/fix_test_field_names.py" ]; then
    python scripts/fix_test_field_names.py
else
    echo "⏭️  Already applied"
fi
echo ""

# Fix 3: Inline test config tax fields
echo "⚙️  Fix 3/3: Adding tax fields to inline test configs..."
if [ -f "scripts/fix_inline_test_configs.py" ]; then
    python scripts/fix_inline_test_configs.py
else
    echo "⏭️  Already applied"
fi
echo ""

# Test critical paths
echo "🧪 Running critical test paths..."
echo ""

echo "1. Contracts (should still be 33/33)..."
if pytest tests/finance/test_contracts.py -v --tb=line -q; then
    echo "✅ Contracts: PASS"
else
    echo "❌ Contracts: FAIL (unexpected regression)"
    exit 1
fi
echo ""

echo "2. Sensitivity v14 (TornadoResult fix)..."
if pytest tests/analytics_layer/test_sensitivity_v14.py::TestAnalyzeSingleParameter::test_basic_analysis -v --tb=short; then
    echo "✅ TornadoResult fix: PASS"
else
    echo "⚠️  TornadoResult: Still failing (may need manual review)"
fi
echo ""

echo "3. Field name compatibility..."
if pytest tests/analytics_layer/test_casper_tail_risk_payload.py -v --tb=line -x; then
    echo "✅ Field names: PASS"
else
    echo "⚠️  Field names: Still failing (may need manual review)"
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "  Phase 2 Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Applied fixes:"
echo "  ✅ TornadoResult.model_validate() → TornadoResult()"
echo "  ✅ tornado_results → tornado_ranking"
echo "  ✅ technology → technology_type"
echo "  ✅ metric → metric_name"
echo ""
echo "Next: Run full test suite"
echo "  pytest --tb=short"
echo ""
echo "Expected improvement: ~20-30 more tests passing"
echo ""
