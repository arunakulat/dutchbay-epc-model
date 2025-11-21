import importlib, types, pytest, math

def test_import_metrics():
    m = importlib.import_module("dutchbay_v13.finance.metrics")
    assert isinstance(m, types.ModuleType)

def test_optional_basic_funcs_if_present():
    m = importlib.import_module("dutchbay_v13.finance.metrics")
    npv = getattr(m, "npv", None)
    if callable(npv):
        r = npv(0.1, [-100.0, 60.0, 60.0])
        assert isinstance(r, (int, float))
    else:
        pytest.xfail("npv not exported; import-only smoke.")
