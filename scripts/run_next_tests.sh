#!/usr/bin/env bash
set -euo pipefail

# Coverage gates relaxed per-file to keep the loop tight
covflags=(--override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1")

echo "→ Phase A (permissive): CLI smoke and scenarios (already green, re-assert quickly)"
export VALIDATION_MODE=permissive
pytest -q tests/test_cli_smoke_direct.py "${covflags[@]}"
pytest -q tests/test_cli_scenarios_more.py "${covflags[@]}"

echo "→ Phase B (strict): validator behaviors"
export VALIDATION_MODE=strict
if [[ -f tests/test_scenarios_jsonl_and_validator.py ]]; then
  pytest -q tests/test_scenarios_jsonl_and_validator.py "${covflags[@]}"
else
  echo "  (skipped: tests/test_scenarios_jsonl_and_validator.py not found)"
fi

echo "→ Phase C (back to permissive): CLI formatting/compat"
export VALIDATION_MODE=permissive
if [[ -f tests/test_cli_format_flag.py ]]; then
  pytest -q tests/test_cli_format_flag.py "${covflags[@]}"
fi
if [[ -f tests/test_cli_unittest.py ]]; then
  pytest -q tests/test_cli_unittest.py "${covflags[@]}"
fi

echo "✓ Next-test batch complete."

