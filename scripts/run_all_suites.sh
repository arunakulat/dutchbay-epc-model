#!/usr/bin/env bash
set -Eeuo pipefail

echo "→ Phase A: CLI smoke"
pytest -q tests/test_cli_smoke_direct.py \
  --override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"

echo "→ Phase B: scenarios multi-file emit"
pytest -q tests/test_cli_scenarios_more.py \
  --override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"

echo "→ Phase C: matrix + strict validator"
pytest -q tests/test_scenarios_jsonl_and_validator.py \
  --override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"

echo "→ Phase D: heavy modules (deterministic MC + shims)"
bash scripts/run_heavy_with_shims.sh

echo "✓ All suites executed."


