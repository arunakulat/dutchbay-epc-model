#!/usr/bin/env bash
set -Eeuo pipefail

echo "→ Installing non-intrusive API shims (only if missing)…"
bash scripts/patch_heavy_api_shims.sh

echo "→ Adding assertive tests…"
bash scripts/add_heavy_assert_tests.sh

echo "→ Running the heavy suite (MC, Sensitivity, Optimization, Metrics)…"
pytest -q tests/heavy \
  --override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"

  