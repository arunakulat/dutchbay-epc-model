#!/bin/bash
# GWTF R25 Daily Compliance Audit

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  DAILY GWTF R25 COMPLIANCE AUDIT"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check for direct commits to main today
echo "📅 Checking for direct commits to main today..."
TODAY=$(date +%Y-%m-%d)
MAIN_COMMITS=$(git log main --since="$TODAY 00:00" --oneline 2>/dev/null | wc -l)

if [[ $MAIN_COMMITS -gt 0 ]]; then
    echo "⚠️  WARNING: $MAIN_COMMITS commit(s) to main today!"
    echo ""
    git log main --since="$TODAY 00:00" --oneline
    echo ""
    echo "🔴 GWTF R25 Violation? (If not via PR)"
else
    echo "✅ No direct commits to main today"
fi
echo ""

# Check override log
if [[ -f .gwtf-overrides.log ]]; then
    OVERRIDES_TODAY=$(grep "$TODAY" .gwtf-overrides.log 2>/dev/null | wc -l)
    if [[ $OVERRIDES_TODAY -gt 0 ]]; then
        echo "⚠️  GWTF R25 overrides today: $OVERRIDES_TODAY"
        echo ""
        grep "$TODAY" .gwtf-overrides.log
        echo ""
    fi
fi

# Check current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" == "feature/add-finance-contracts-pydantic-v2-20251219" ]]; then
    echo "✅ Currently on correct feature branch"
elif [[ "$CURRENT_BRANCH" == "main" ]]; then
    echo "🔴 WARNING: Currently on main branch!"
else
    echo "📍 Current branch: $CURRENT_BRANCH"
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "  AUDIT COMPLETE"
echo "═══════════════════════════════════════════════════════════════"
echo ""

exit 0
