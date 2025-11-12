#!/usr/bin/env bash
set -Eeuo pipefail
echo "→ Reporting modules: import + soft smokes"
pytest -q tests/imports/test_import_reporting_stack.py tests/reporting \
  --override-ini="addopts=-q --cov=dutchbay_v13.report --cov=dutchbay_v13.report_pdf --cov=dutchbay_v13.charts --cov-report=term-missing --cov-fail-under=1"
echo "✓ Reporting modules pass."

