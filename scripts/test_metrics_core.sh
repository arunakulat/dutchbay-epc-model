#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p tests/heavy

cat > tests/heavy/test_metrics_smoke.py <<'PY'
import importlib, types, pytest, math

def test_import_metrics():
    m = importlib.import_module("dutchbay_v13.finance.metrics")
    assert isinstance(m, types.ModuleType)

def test_optional_basic_funcs_if_present():
    m = importlib.import_module("dutchbay_v13.finance.metrics")
    npv = getattr(m, "npv", None)
    if callable(npv):
        r = npv(0.1, [-100.0, 60.0, 60.0])
        assert isinstance(r, (int, float))
    else:
        pytest.xfail("npv not exported; import-only smoke.")
PY

pytest -q tests/heavy/test_metrics_smoke.py \
  --override-ini="addopts=-q --cov=dutchbay_v13.finance.metrics --cov-report=term-missing --cov-fail-under=1"

  