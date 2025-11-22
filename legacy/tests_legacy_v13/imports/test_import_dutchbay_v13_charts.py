import importlib

def test_import_dutchbay_v13_charts():
    m = importlib.import_module("dutchbay_v13.charts")
    assert m is not None
