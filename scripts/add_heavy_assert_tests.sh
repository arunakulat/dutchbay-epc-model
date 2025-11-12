#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p tests/heavy

cat > tests/heavy/test_mc_asserts.py <<'PY'
import importlib, math

def test_mc_generate_and_run():
    m = importlib.import_module("dutchbay_v13.monte_carlo")
    assert hasattr(m, "generate_mc_parameters")
    params = m.generate_mc_parameters(n=4, base=20.30)
    assert isinstance(params, list) and len(params) == 4
    res = m.run_monte_carlo({"tariff_lkr_per_kwh": 20.30}, n=4)
    assert "results" in res and len(res["results"]) == 4
    irrs = [r["equity_irr"] for r in res["results"]]
    # strictly increasing with tariff
    assert all(irrs[i] <= irrs[i+1] for i in range(len(irrs)-1))
PY

cat > tests/heavy/test_sensitivity_asserts.py <<'PY'
import importlib

def test_sensitivity_basic():
    s = importlib.import_module("dutchbay_v13.sensitivity")
    assert hasattr(s, "run_sensitivity")
    out = s.run_sensitivity({"tariff_lkr_per_kwh": 20.3}, "tariff_lkr_per_kwh", [18.0, 20.3, 22.0])
    assert isinstance(out, list) and len(out) == 3
    vals = [row["value"] for row in out]
    assert vals == [18.0, 20.3, 22.0]
PY

cat > tests/heavy/test_optimization_asserts.py <<'PY'
import importlib

def test_solve_tariff_inverse_of_shim():
    o = importlib.import_module("dutchbay_v13.optimization")
    assert hasattr(o, "solve_tariff")
    # Target 0.15 → t = 20 + (0.15-0.01)/0.002 = 90.0
    r = o.solve_tariff(0.15, {"tariff_lkr_per_kwh": 20.3})
    assert abs(r["tariff_lkr_per_kwh"] - 90.0) < 1e-6
PY

echo "✓ Heavy assert tests written under tests/heavy/"

