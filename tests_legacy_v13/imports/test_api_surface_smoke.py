import importlib, pytest

def test_import_api_module():
    m = importlib.import_module("dutchbay_v13.api")
    assert m is not None

# These are *optional* exports; mark xfail if not wired yet.
@pytest.mark.parametrize("name", [
    "run_irr_demo",
    "run_sensitivity",
    "run_monte_carlo",
    "generate_report",     # may be proxied or absent
    "build_pdf_report",    # may be proxied or absent
])
def test_api_optional_exports_present_or_xfail(name):
    m = importlib.import_module("dutchbay_v13.api")
    if not hasattr(m, name):
        pytest.xfail(f"{name} not exported yet")
    obj = getattr(m, name)
    assert callable(obj) or isinstance(obj, str)
