#!/bin/bash
# task1_legacy_quarantine.sh
# Sprint Day 5 - Task 1: Legacy Quarantine Sweep

set -e  # Exit on any error

echo "🔄 Task 1: Legacy Quarantine Sweep - Starting..."

# Create directory structure
echo "→ Creating legacy archive structure..."
mkdir -p legacy/v14chat
mkdir -p legacy/patch_archive
mkdir -p scripts/research

# Move dutchbay_v14chat to legacy (if exists)
if [ -d "dutchbay_v14chat" ]; then
    echo "→ Quarantining dutchbay_v14chat..."
    git mv dutchbay_v14chat/* legacy/v14chat/ 2>/dev/null || true
    rmdir dutchbay_v14chat 2>/dev/null || true
fi

# Archive patch files (check existence first)
echo "→ Archiving patch files..."
[ -f "scenario_analytics_patched.py" ] && git mv scenario_analytics_patched.py legacy/patch_archive/
[ -f "scenario_analytics_fixed_debug.py" ] && git mv scenario_analytics_fixed_debug.py legacy/patch_archive/
[ -f "scenario_analytics_debug.py" ] && git mv scenario_analytics_debug.py legacy/patch_archive/
[ -f "debt_patched.py" ] && git mv debt_patched.py legacy/patch_archive/

# Move root utilities to scripts/
echo "→ Organizing utilities..."
[ -f "analyze_directory.py" ] && git mv analyze_directory.py scripts/
[ -f "make_clean_zip.py" ] && git mv make_clean_zip.py scripts/
[ -f "generate_manifest.py" ] && git mv generate_manifest.py scripts/
[ -f "check_all_py_files.py" ] && git mv check_all_py_files.py scripts/
[ -f "gh_tools.py" ] && git mv gh_tools.py scripts/
[ -f "move_v13_to_legacy.py" ] && git mv move_v13_to_legacy.py scripts/
[ -f "make_essential_zip.py" ] && git mv make_essential_zip.py scripts/

# Move research/experimental scripts
echo "→ Moving research scripts..."
[ -f "optimization.py" ] && git mv optimization.py scripts/research/

# Note: FX/risk modules stay in root for now (Task 2 will handle them)
echo "ℹ️  FX/risk modules (fx_data_processor_dual_regime.py, risk_metrics.py, returns.py) remain in root for Task 2"

echo "✅ Task 1 file moves complete!"
echo ""
echo "Next steps:"
echo "1. Review with: git status"
echo "2. Create legacy/README.md (copy from next section)"
echo "3. Create scripts/check_legacy_imports.py (copy from next section)"
echo "4. Commit with: git commit -m 'refactor(legacy): Task 1 quarantine complete'"
