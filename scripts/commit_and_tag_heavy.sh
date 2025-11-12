#!/usr/bin/env bash
set -Eeuo pipefail

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
TAG="${2:-v13-heavy-$(date +%Y%m%d-%H%M%S)}"

echo "→ Staging updated files…"
git add \
  dutchbay_v13/monte_carlo.py \
  dutchbay_v13/sensitivity.py \
  dutchbay_v13/optimization.py \
  tests/heavy || true

echo "→ Commit…"
git commit -m "tests(heavy): deterministic MC + API shims + assertive tests" || true

echo "→ Push branch '$BRANCH'…"
git push origin "$BRANCH"

echo "→ Create tag '$TAG' and push…"
git tag -a "$TAG" -m "Heavy modules suite green: MC/SENS/OPT shims + tests"
git push origin "$TAG"

echo "✓ Done."

