import importlib

def test_import_dutchbay_v13_finance_irr():
    m = importlib.import_module("dutchbay_v13.finance.irr")
    assert m is not None
