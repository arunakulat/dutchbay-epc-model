#!/usr/bin/env bash
set -Eeuo pipefail
echo "→ Core/config/api/epc/validate: import + soft smokes"
pytest -q tests/imports/test_import_core_stack.py tests/core \
  --override-ini="addopts=-q --cov=dutchbay_v13.core --cov=dutchbay_v13.config --cov=dutchbay_v13.api --cov=dutchbay_v13.epc --cov=dutchbay_v13.validate --cov=dutchbay_v13.schema --cov=dutchbay_v13.types --cov=dutchbay_v13.adapters --cov-report=term-missing --cov-fail-under=1"
echo "✓ Core/config modules pass."

