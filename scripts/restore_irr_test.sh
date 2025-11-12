#!/usr/bin/env bash
set -euo pipefail

FILE="tests/test_finance_irr_debt.py"

echo "→ Checking repo..."
git rev-parse --show-toplevel >/dev/null

# Safety: stash a copy of whatever is on disk right now
if [[ -f "$FILE" ]]; then
  TS=$(date +%s)
  cp "$FILE" "${FILE}.oops.${TS}"
  echo "→ Saved current working copy to ${FILE}.oops.${TS}"
fi

# If the file is tracked in HEAD, restore that version
if git ls-tree -r --name-only HEAD -- "$FILE" | grep -q .; then
  # If staged, unstage it first (keeps working tree intact)
  if ! git diff --cached --quiet -- "$FILE"; then
    echo "→ Unstaging $FILE"
    git restore --staged -- "$FILE" 2>/dev/null || git reset HEAD -- "$FILE"
  fi
  echo "→ Restoring $FILE from HEAD"
  git restore --source=HEAD --worktree -- "$FILE" 2>/dev/null || git checkout -- "$FILE"
  echo "✓ Restored from HEAD"
  exit 0
fi

# If not found at HEAD, try the most recent commit that touched the file
LAST_COMMIT=$(git rev-list -n 1 HEAD -- "$FILE" || true)
if [[ -n "${LAST_COMMIT:-}" ]]; then
  echo "→ Restoring $FILE from last commit that touched it: $LAST_COMMIT"
  git restore --source="$LAST_COMMIT" --worktree -- "$FILE" 2>/dev/null \
    || git show "${LAST_COMMIT}:${FILE}" > "$FILE"
  echo "✓ Restored from $LAST_COMMIT"
  exit 0
fi

# Fallback: use any .bak made earlier
BAK=$(ls -1t "${FILE}.bak"* 2>/dev/null | head -n1 || true)
if [[ -n "${BAK:-}" ]]; then
  echo "→ Restoring from backup: $BAK"
  cp "$BAK" "$FILE"
  echo "✓ Restored from backup"
  exit 0
fi

echo "✗ Could not find a prior committed or backup copy of $FILE."
echo "  Try: git reflog --pretty=oneline | head -n 20  # identify a good commit"
echo "       git restore --source=<GOOD_COMMIT> -- $FILE"
exit 1

