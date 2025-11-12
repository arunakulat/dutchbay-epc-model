#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
TAG="${2:-v13-phaseC-$(date +%Y%m%d-%H%M%S)}"

echo "→ Phase C on branch: $BRANCH"
echo "→ Target tag       : $TAG"

# 1) run the consolidated suite (finance, scenarios, heavy, reporting, charts)
bash "$ROOT/scripts/ci_phase_c_full.sh"

# 2) add & commit any new/updated tests or shims
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "→ Staging changes…"
  git add tests/ scripts/ dutchbay_v13/report.py dutchbay_v13/report_pdf.py || true
  git commit -m "tests: Phase C suite updates (reporting/charts/heavy + smokes)"
else
  echo "→ No changes to commit."
fi

# 3) push + tag (reuses hardened helper)
bash "$ROOT/scripts/push_and_tag_fixed.sh" "$BRANCH" "$TAG"

echo "✓ Phase C run + push complete."

