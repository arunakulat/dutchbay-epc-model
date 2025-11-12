import importlib

def test_import_dutchbay_v13_finance_metrics():
    m = importlib.import_module("dutchbay_v13.finance.metrics")
    assert m is not None
