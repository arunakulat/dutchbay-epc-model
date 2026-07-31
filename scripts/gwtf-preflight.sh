#!/bin/bash
# GWTF R25 Pre-Flight Checklist
# Run before ANY git merge, pull, or push operation

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  GWTF R25 PRE-FLIGHT CHECKLIST"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# 1. Check current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "📍 Current branch: $CURRENT_BRANCH"
echo ""

if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    echo "⚠️  WARNING: You are on protected branch '$CURRENT_BRANCH'!"
    echo ""
    echo "🔴 GWTF R25 VIOLATION RISK:"
    echo "   - Direct commits to main are forbidden"
    echo "   - All work must go through feature branch + PR"
    echo ""
    echo "✅ CORRECT WORKFLOW:"
    echo "   git fetch origin"
    echo "   git worktree add -b <type>/<descriptive-name> <worktree-path> origin/main"
    echo ""
    echo "🚨 Continue on main anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo ""
        echo "✅ Aborting. Please switch to feature branch."
        echo ""
        exit 1
    fi
    echo ""
    echo "⚠️  Proceeding on main (override acknowledged)"
    echo ""
fi

# 2. GWTF R25 reminder
echo "📋 GWTF R25 Requirements:"
echo "   ✅ Start a short-lived branch from current origin/main"
echo "   ✅ Use a dedicated worktree for each concurrent writing session"
echo "   ✅ Push the current feature/fix/docs branch only"
echo "   ✅ Merge to main ONLY via Pull Request"
echo "   ✅ Merge only after required CI is green and the branch is current"
echo ""

# 3. Show uncommitted changes
UNCOMMITTED=$(git status --porcelain | wc -l)
if [[ $UNCOMMITTED -gt 0 ]]; then
    echo "📝 Uncommitted changes: $UNCOMMITTED files"
    echo ""
fi

# 4. Show unpushed commits
UNPUSHED=$(git log @{u}.. --oneline 2>/dev/null | wc -l)
if [[ $UNPUSHED -gt 0 ]]; then
    echo "📤 Unpushed commits: $UNPUSHED"
    echo ""
    echo "Recent commits:"
    git log @{u}.. --oneline | head -5
    echo ""
fi

# 5. Final confirmation
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Pre-flight checklist complete"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Proceed with git operation? (y/N)"
read -r proceed
if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
    echo ""
    echo "❌ Aborted by user"
    echo ""
    exit 1
fi

echo ""
echo "✅ Proceeding with git operation..."
echo ""
exit 0
