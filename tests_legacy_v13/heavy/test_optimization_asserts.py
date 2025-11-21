import importlib

def test_solve_tariff_inverse_of_shim():
    o = importlib.import_module("dutchbay_v13.optimization")
    assert hasattr(o, "solve_tariff")
    # Target 0.15 → t = 20 + (0.15-0.01)/0.002 = 90.0
    r = o.solve_tariff(0.15, {"tariff_lkr_per_kwh": 20.3})
    assert abs(r["tariff_lkr_per_kwh"] - 90.0) < 1e-6
