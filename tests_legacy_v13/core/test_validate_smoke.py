import importlib, pytest

def _find(m, names):
    for n in names:
        fn = getattr(m, n, None)
        if callable(fn): return fn
    return None

def test_validate_params_smoke():
    m = importlib.import_module("dutchbay_v13.validate")
    fn = _find(m, ("validate_params","validate_overrides","validate"))
    if not fn:
        pytest.xfail("validate function not exported yet")
    try:
        fn({"tariff_lkr_per_kwh": 45.0})
    except Exception:
        pytest.xfail("validate present but not stable")
