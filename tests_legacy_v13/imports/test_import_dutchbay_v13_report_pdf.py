import importlib

def test_import_dutchbay_v13_report_pdf():
    m = importlib.import_module("dutchbay_v13.report_pdf")
    assert m is not None
