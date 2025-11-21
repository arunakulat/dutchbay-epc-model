import importlib

def test_import_dutchbay_v13_config():
    m = importlib.import_module("dutchbay_v13.config")
    assert m is not None
