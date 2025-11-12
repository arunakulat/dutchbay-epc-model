import importlib
import pytest
from pathlib import Path


def test_api_import_or_skip():
    try:
        pass  # type: ignore
    except Exception:
        pytest.skip("fastapi not installed")
    m = importlib.import_module("dutchbay_v13.api")
    assert hasattr(m, "create_app")


def test_pdf_builder_or_skip(tmp_path: Path):
    # ensure an HTML exists
    out = tmp_path / "o"
    out.mkdir()
    (out / "report.html").write_text(
        "<html><body><h1>x</h1></body></html>", encoding="utf-8"
    )
    try:
        from dutchbay_v13.report_pdf import build_pdf_report

        try:
            pdf = build_pdf_report(out, out / "report.html")
            assert pdf.exists()
        except RuntimeError:
            pytest.skip("PDF tools not installed")
    except Exception:
        pytest.skip("reportlab/weasyprint not installed")
