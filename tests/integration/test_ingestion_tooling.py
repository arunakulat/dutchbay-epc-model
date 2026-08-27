"""Integration guards for the governed document-ingestion toolchain."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import pdfplumber
import pymupdf
from markitdown import MarkItDown


def test_governed_ingestion_versions_are_installed() -> None:
    """Pin the conversion and inspection engines cleared for Python 3.12."""

    assert version("markitdown") == "0.1.7"
    assert version("pdfplumber") == "0.11.10"
    assert version("pymupdf") == "1.28.2"
    assert version("pre-commit") == "4.6.2"


def test_pdf_conversion_extraction_and_rendering(tmp_path: Path) -> None:
    """Exercise MarkItDown, pdfplumber, and PyMuPDF on one generated PDF."""

    marker = "DutchBay governed PDF ingestion"
    pdf_path = tmp_path / "ingestion-smoke.pdf"

    document = pymupdf.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((36, 72), marker)
    document.save(pdf_path)
    document.close()

    with pdfplumber.open(pdf_path) as extracted:
        assert marker in (extracted.pages[0].extract_text() or "")

    converted = MarkItDown().convert(str(pdf_path)).text_content
    assert marker in converted

    with pymupdf.open(pdf_path) as rendered:
        pixmap = rendered[0].get_pixmap(alpha=False)
        assert pixmap.width == 300
        assert pixmap.height == 200
        assert len(pixmap.samples) > 0
