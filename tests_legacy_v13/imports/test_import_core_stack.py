import importlib

def _imp(name): importlib.import_module(name)

def test_import_core():     _imp("dutchbay_v13.core")
def test_import_config():   _imp("dutchbay_v13.config")
def test_import_api():      _imp("dutchbay_v13.api")
def test_import_epc():      _imp("dutchbay_v13.epc")
def test_import_validate(): _imp("dutchbay_v13.validate")
def test_import_schema():   _imp("dutchbay_v13.schema")
def test_import_types():    _imp("dutchbay_v13.types")
def test_import_adapters(): _imp("dutchbay_v13.adapters")
