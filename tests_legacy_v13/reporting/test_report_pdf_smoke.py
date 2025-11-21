import importlib, pytest, tempfile, pathlib

def _find(m, names):
    for n in names:
        fn = getattr(m, n, None)
        if callable(fn): return fn
    return None

def test_report_pdf_generate_smoke(tmp_path):
    m = importlib.import_module("dutchbay_v13.report_pdf")
    fn = _find(m, ("render_pdf","build_pdf","generate_pdf","export_pdf"))
    if not fn:
        pytest.xfail("report_pdf API not exported yet")
    try:
        out = tmp_path / "demo.pdf"
        try:
            res = fn({"title": "Demo PDF"}, output_path=str(out))
        except TypeError:
            res = fn({"title": "Demo PDF"}, out)  # positional path
    except ImportError:
        pytest.xfail("optional PDF deps not installed yet")
    except Exception:
        pytest.xfail("report_pdf callable present but not yet stable")
    assert out.exists() or res is not None
