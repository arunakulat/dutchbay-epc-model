import importlib

def test_import_dutchbay_v13_monte_carlo():
    m = importlib.import_module("dutchbay_v13.monte_carlo")
    assert m is not None
