#!/usr/bin/env bash
set -Eeuo pipefail
pytest -q tests/imports/test_import_core_stack.py tests/core \
  --override-ini="addopts=-q --cov=dutchbay_v13.config --cov=dutchbay_v13.validate --cov-report=term-missing --cov-fail-under=2"
echo "✓ Core/config hardened pass."

