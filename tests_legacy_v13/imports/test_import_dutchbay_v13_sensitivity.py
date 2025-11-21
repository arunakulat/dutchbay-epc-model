import importlib

def test_import_dutchbay_v13_sensitivity():
    m = importlib.import_module("dutchbay_v13.sensitivity")
    assert m is not None
