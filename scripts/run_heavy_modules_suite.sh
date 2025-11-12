#!/usr/bin/env bash
set -Eeuo pipefail

echo "→ Patching Monte Carlo for deterministic RNG…"
bash scripts/patch_monte_carlo_rng.sh

echo "→ Running Monte Carlo smoke…"
bash scripts/test_monte_carlo.sh || true

echo "→ Running Sensitivity smoke…"
bash scripts/test_sensitivity.sh || true

echo "→ Running Optimization smoke…"
bash scripts/test_optimization.sh || true

echo "→ Running Metrics smoke…"
bash scripts/test_metrics_core.sh || true

echo
echo "=== Heavier Modules Suite Complete ==="
echo "Check the above sections for any xfails (expected if API not exported yet)."

