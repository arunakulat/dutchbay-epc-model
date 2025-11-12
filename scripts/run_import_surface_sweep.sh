#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root for both bash & zsh without tripping -u
SRC="${BASH_SOURCE[0]:-$0}"
ROOT="$(cd "$(dirname "$SRC")/.." && pwd)"
cd "$ROOT"

mkdir -p tests/imports

cat > tests/imports/test_import_surface.py <<'PY'
import importlib

MODULES = [
    # package roots
    "dutchbay_v13",
    # core surfaces
    "dutchbay_v13.api",
    "dutchbay_v13.adapters",
    "dutchbay_v13.config",
    "dutchbay_v13.core",
    "dutchbay_v13.types",
    "dutchbay_v13.schema",
    "dutchbay_v13.validate",
    "dutchbay_v13.scenario_runner",
    # finance stack
    "dutchbay_v13.finance.irr",
    "dutchbay_v13.finance.debt",
    "dutchbay_v13.finance.cashflow",
    "dutchbay_v13.finance.metrics",
    # analytics
    "dutchbay_v13.monte_carlo",
    "dutchbay_v13.sensitivity",
    "dutchbay_v13.optimization",
    # reporting
    "dutchbay_v13.charts",
    "dutchbay_v13.report",
    "dutchbay_v13.report_pdf",
    # domain
    "dutchbay_v13.epc",
]

def test_import_surface():
    for name in MODULES:
        m = importlib.import_module(name)
        assert hasattr(m, "__spec__"), f"import failed: {name}"
PY

# Only cover what we import; keep the threshold tiny; ignore repo pytest.ini
pytest -c /dev/null -q tests/imports/test_import_surface.py \
  --cov=dutchbay_v13.api \
  --cov=dutchbay_v13.adapters \
  --cov=dutchbay_v13.config \
  --cov=dutchbay_v13.core \
  --cov=dutchbay_v13.types \
  --cov=dutchbay_v13.schema \
  --cov=dutchbay_v13.validate \
  --cov=dutchbay_v13.scenario_runner \
  --cov=dutchbay_v13.finance.irr \
  --cov=dutchbay_v13.finance.debt \
  --cov=dutchbay_v13.finance.cashflow \
  --cov=dutchbay_v13.finance.metrics \
  --cov=dutchbay_v13.monte_carlo \
  --cov=dutchbay_v13.sensitivity \
  --cov=dutchbay_v13.optimization \
  --cov=dutchbay_v13.charts \
  --cov=dutchbay_v13.report \
  --cov=dutchbay_v13.report_pdf \
  --cov=dutchbay_v13.epc \
  --cov-report=term-missing \
  --cov-fail-under=1 \
  --no-header --no-summary

  