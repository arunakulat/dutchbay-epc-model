import importlib

def test_sensitivity_basic():
    s = importlib.import_module("dutchbay_v13.sensitivity")
    assert hasattr(s, "run_sensitivity")
    out = s.run_sensitivity({"tariff_lkr_per_kwh": 20.3}, "tariff_lkr_per_kwh", [18.0, 20.3, 22.0])
    assert isinstance(out, list) and len(out) == 3
    vals = [row["value"] for row in out]
    assert vals == [18.0, 20.3, 22.0]
