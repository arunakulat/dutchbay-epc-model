import importlib

def test_import_dutchbay_v13_cli():
    m = importlib.import_module("dutchbay_v13.cli")
    assert m is not None
