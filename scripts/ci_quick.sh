#!/usr/bin/env bash
set -euo pipefail
SRC="${BASH_SOURCE[0]:-$0}"
ROOT="$(cd "$(dirname "$SRC")/.." && pwd)"
cd "$ROOT"

step() { echo ""; echo "=== $* ==="; }

# 0) Ensure venv is active (no hard fail if already active elsewhere)
if [ -d ".venv311" ] && [ -f ".venv311/bin/activate" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  # shellcheck disable=SC1091
  source ".venv311/bin/activate"
fi

step "API/adapters smoke"
if [ -x scripts/run_api_cov_smoke.sh ]; then
  bash scripts/run_api_cov_smoke.sh
else
  echo "WARN: scripts/run_api_cov_smoke.sh missing; skipping."
fi

step "Import-surface sweep"
bash scripts/run_import_surface_sweep.sh

step "Heavy modules (MC/Sens/Opt/Metrics)"
if [ -x scripts/run_heavy_with_shims.sh ]; then
  bash scripts/run_heavy_with_shims.sh
else
  echo "WARN: scripts/run_heavy_with_shims.sh missing; skipping."
fi

step "Reporting + core stacks"
if [ -x scripts/run_next_modules_suite.sh ]; then
  bash scripts/run_next_modules_suite.sh
else
  echo "WARN: scripts/run_next_modules_suite.sh missing; skipping."
fi

step "CLI scenarios fast"
bash scripts/run_cli_scenarios_fast.sh

echo ""
echo "✓ Quick CI complete."

