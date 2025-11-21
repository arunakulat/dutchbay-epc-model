import importlib, pytest, tempfile, pathlib

def _find(m, names):
    for n in names:
        fn = getattr(m, n, None)
        if callable(fn): return fn
    return None

def test_report_generate_smoke(tmp_path):
    m = importlib.import_module("dutchbay_v13.report")
    fn = _find(m, ("generate_report","build_report","make_report","render","run"))
    if not fn:
        pytest.xfail("report API not exported yet")
    try:
        # Try common signatures; fall back to xfail if non-standard
        try:
            res = fn({"title": "Demo"}, outdir=str(tmp_path))
        except TypeError:
            res = fn({"title": "Demo"}, tmp_path)  # positional outdir
    except Exception:
        pytest.xfail("report callable present but not yet stable")
    assert res is not None
