import importlib

def test_import_dutchbay_v13_report():
    importlib.import_module("dutchbay_v13.report")

def test_import_dutchbay_v13_report_pdf():
    importlib.import_module("dutchbay_v13.report_pdf")

def test_import_dutchbay_v13_charts():
    importlib.import_module("dutchbay_v13.charts")
