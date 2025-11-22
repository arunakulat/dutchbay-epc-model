import importlib

def test_import_dutchbay_v13_schema():
    m = importlib.import_module("dutchbay_v13.schema")
    assert m is not None
