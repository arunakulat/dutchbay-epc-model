import importlib

def test_import_dutchbay_v13_types():
    m = importlib.import_module("dutchbay_v13.types")
    assert m is not None
