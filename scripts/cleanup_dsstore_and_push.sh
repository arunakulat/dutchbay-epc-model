#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
TAG="${2:-}"  # optional tag name

echo "→ Branch: $BRANCH"
echo "→ Tag   : ${TAG:-<none>}"

# 1) Ensure .gitignore exists and contains .DS_Store
touch .gitignore
if ! grep -qxE '\.DS_Store' .gitignore; then
  echo "→ Appending '.DS_Store' to .gitignore"
  printf "\n# macOS Finder cruft\n.DS_Store\n" >> .gitignore
fi

# 2) Remove any tracked .DS_Store from index
echo "→ Removing tracked .DS_Store from index (if any)…"
git rm -r --cached --quiet -- '**/.DS_Store' || true

# 3) Also delete working copies to keep tree clean (optional)
echo "→ Deleting working copies of .DS_Store…"
find . -name '.DS_Store' -type f -delete || true

# 4) Commit ignore/cleanup if there are changes
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "→ Committing .DS_Store ignore/cleanup…"
  git add .gitignore || true
  git commit -m "chore: ignore macOS .DS_Store and scrub tracked instances"
else
  echo "→ Nothing to commit."
fi

# 5) Push and optionally tag
echo "→ Pushing $BRANCH…"
git push origin "$BRANCH"

if [[ -n "$TAG" ]]; then
  echo "→ Creating and pushing tag: $TAG"
  git tag -a "$TAG" -m "Tag: $TAG"
  git push origin "$TAG"
fi

echo "✓ Cleanup complete."

