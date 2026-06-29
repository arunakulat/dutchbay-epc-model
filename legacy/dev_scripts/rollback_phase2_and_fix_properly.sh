#!/bin/bash
# Emergency rollback + proper fix

set -e

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Emergency Rollback + Proper Fix"
echo "  Phase 2 made things worse - fixing properly now"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Step 1: Revert the bad changes from Phase 2
echo "📦 Step 1: Reverting Phase 2 changes..."
git diff HEAD~3..HEAD analytics/sensitivity_v14.py tests/ > /tmp/phase2_changes.patch
git checkout HEAD~3 -- tests/finance/test_contracts.py
git checkout HEAD~3 -- tests/analytics_layer/
git checkout HEAD~3 -- tests/contracts/
git checkout HEAD~3 -- tests/_quarantine/
echo "✅ Reverted test changes"
echo ""

# Step 2: Fix sensitivity_v14.py line 489 PROPERLY
echo "🔧 Step 2: Fixing sensitivity_v14.py line 489..."
python3 << 'PYTHON_FIX'
from pathlib import Path

# Read the file
sensitivity_file = Path("analytics/sensitivity_v14.py")
content = sensitivity_file.read_text()

# The problem is line 489: return TornadoResult({...})
# TornadoResult is a dataclass, needs: TornadoResult(metric_name=..., base_metric=..., shock_results=...)

# Find the problematic pattern
# Original (broken): return TornadoResult({...})
# Should be: return TornadoResult(metric_name=..., base_metric=..., shock_results=[...])

# Strategy: Replace the dict constructor with proper dataclass instantiation
import re

# Pattern to find: TornadoResult( followed by dict
pattern = r'return TornadoResult\(\s*\{'

if re.search(pattern, content):
    print("Found TornadoResult dict constructor at line ~489")
    
    # Find the exact block (it's around line 480-495)
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'return TornadoResult(' in line and '{' in line:
            print(f"  Line {i}: {line.strip()}")
            
            # Find the closing brace
            start_line = i - 1
            brace_count = line.count('{') - line.count('}')
            end_line = start_line
            
            for j in range(start_line + 1, len(lines)):
                brace_count += lines[j].count('{') - lines[j].count('}')
                if brace_count == 0:
                    end_line = j
                    break
            
            # Extract the dict block
            dict_block = '\n'.join(lines[start_line:end_line+1])
            print(f"  Spans lines {start_line+1}-{end_line+1}")
            
            # The dict should have: "metric_name", "base_metric", "shock_results"
            # Extract these values
            
            # Replace with proper dataclass call
            # For now, just convert dict syntax to kwarg syntax
            fixed_block = dict_block.replace('return TornadoResult({', 'return TornadoResult(')
            fixed_block = fixed_block.replace('"})', '")') # Remove closing dict brace
            
            # Replace in content
            content = content.replace(dict_block, fixed_block)
            
            print("  ✅ Fixed!")
            break
    
    sensitivity_file.write_text(content)
    print("✅ Updated sensitivity_v14.py")
else:
    print("⚠️  Pattern not found - may already be fixed")

PYTHON_FIX

echo ""

# Step 3: Run contracts test to verify
echo "🧪 Step 3: Testing contracts..."
if pytest tests/finance/test_contracts.py::TestTornadoResult::test_basic_creation -xvs; then
    echo "✅ TornadoResult tests PASS"
else
    echo "❌ Still failing - need manual fix"
    echo ""
    echo "Manual fix needed for analytics/sensitivity_v14.py line 489:"
    echo ""
    echo "Change from:"
    echo '  return TornadoResult({'
    echo '      "metric_name": metric_name,'
    echo '      "base_metric": base_irr,'
    echo '      "shock_results": ranked_shocks'
    echo '  })'
    echo ""
    echo "To:"
    echo '  return TornadoResult('
    echo '      metric_name=metric_name,'
    echo '      base_metric=base_irr,'
    echo '      shock_results=ranked_shocks'
    echo '  )'
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Rollback + Fix Complete"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Next: Run full test suite"
echo "  pytest tests/finance/test_contracts.py -v"
echo ""
