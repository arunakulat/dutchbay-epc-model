import importlib

def test_import_dutchbay_v13_finance_utils():
    m = importlib.import_module("dutchbay_v13.finance.utils")
    assert m is not None
