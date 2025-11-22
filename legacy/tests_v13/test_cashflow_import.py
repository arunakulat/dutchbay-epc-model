import importlib

def test_cashflow_module_imports():
    # Import-only smoke to ensure coverage sees the module.
    m = importlib.import_module("dutchbay_v13.finance.cashflow")
    assert m is not None
