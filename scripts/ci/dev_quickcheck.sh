#!/usr/bin/env bash
set -euo pipefail

# Go with the Flow dev quickcheck:
# 1) Format touched analytics/finance files with black + isort
# 2) Run mypy on v14 surfaces
# 3) Run focused analytics-layer tests
# 4) Run full pytest suite

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Formatting with black ==="
black \
  analytics/contracts_v14.py \
  analytics/monte_carlo_v14.py \
  analytics/evaluate_scenario.py \
  analytics/sensitivity_v14.py \
  tests/analytics_layer/test_mc_integration.py \
  tests/analytics/test_sensitivity_runner.py

echo "=== Sorting imports with isort ==="
isort \
  analytics/contracts_v14.py \
  analytics/monte_carlo_v14.py \
  analytics/evaluate_scenario.py \
  analytics/sensitivity_v14.py \
  tests/analytics_layer/test_mc_integration.py \
  tests/analytics/test_sensitivity_runner.py

echo
echo "=== mypy (analytics + finance + run_full_pipeline_v14.py) ==="
python -m mypy analytics finance run_full_pipeline_v14.py

echo
echo "=== pytest (focused analytics-layer checks) ==="
# Repointed in the 2026-06-21 audit: the old targets (test_monte_carlo_v14.py /
# test_sensitivity_v14_all.py) were quarantine tombstones that collected ZERO tests, so
# under `set -e` this step exited 5 and halted the script before the full suite ever ran.
pytest \
  tests/analytics_layer/test_mc_integration.py \
  tests/analytics/test_sensitivity_runner.py

echo
echo "=== pytest (full suite) ==="
pytest

echo
echo "✅ dev_quickcheck.sh complete."
#EOF
