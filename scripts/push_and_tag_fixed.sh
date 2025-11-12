#!/usr/bin/env bash
set -Eeuo pipefail

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
TAG="${2:-v13-phaseC-$(date +%Y%m%d-%H%M%S)}"

echo "→ Branch: $BRANCH"
echo "→ Tag   : $TAG"

git fetch -p
git status --porcelain
if ! git diff --quiet; then
  echo "→ Local changes detected. Commit before pushing:"
  echo "   git add -A && git commit -m 'wip: phase C'"
  exit 1
fi

git push origin "$BRANCH"
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "→ Tag exists; creating incremental suffix…"
  TAG="${TAG}-$(date +%s)"
fi
git tag "$TAG"
git push origin "$TAG"
echo "✓ Pushed $BRANCH and tag $TAG"

