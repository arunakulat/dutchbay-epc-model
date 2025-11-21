import importlib

def test_import_dutchbay_v13_core():
    m = importlib.import_module("dutchbay_v13.core")
    assert m is not None
