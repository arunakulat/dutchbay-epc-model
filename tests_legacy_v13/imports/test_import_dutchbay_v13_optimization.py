import importlib

def test_import_dutchbay_v13_optimization():
    m = importlib.import_module("dutchbay_v13.optimization")
    assert m is not None
