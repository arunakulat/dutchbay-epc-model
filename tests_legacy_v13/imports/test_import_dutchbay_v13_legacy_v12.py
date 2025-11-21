import importlib

def test_import_dutchbay_v13_legacy_v12():
    m = importlib.import_module("dutchbay_v13.legacy_v12")
    assert m is not None
