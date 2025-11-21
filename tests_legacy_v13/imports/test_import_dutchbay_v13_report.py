import importlib

def test_import_dutchbay_v13_report():
    m = importlib.import_module("dutchbay_v13.report")
    assert m is not None
