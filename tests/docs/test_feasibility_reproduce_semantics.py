"""Keep the governed feasibility narrative and PDF on the reproduced F5-01 evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pypdfium2 as pdfium

REPO_ROOT = Path(__file__).resolve().parents[2]
KIT = REPO_ROOT / "feasibility_reproduce"
STUDY_MD = KIT / "report" / "DutchBay_Complete_Feasibility_Study.md"
STUDY_PDF = KIT / "report" / "DutchBay_Complete_Feasibility_Study.pdf"
MC_EXPECTED = KIT / "cache" / "expected" / "mc2500_summary.json"


def _normalized(text: str) -> str:
    """Normalize whitespace and Unicode minus signs for semantic comparisons."""
    return " ".join(text.replace("−", "-").split())


def _pdf_text_and_pages() -> tuple[str, int]:
    """Extract searchable text and the page count from the committed study PDF."""
    document = pdfium.PdfDocument(STUDY_PDF)
    pages: list[str] = []
    try:
        for index in range(len(document)):
            page = document[index]
            text_page = page.get_textpage()
            try:
                pages.append(text_page.get_text_range())
            finally:
                text_page.close()
                page.close()
        return _normalized("\n".join(pages)), len(document)
    finally:
        document.close()


def test_study_headline_matches_the_cod_aligned_canon() -> None:
    """The executive verdict must repeat the current headline, not the pre-F5-01 IRR."""
    markdown = _normalized(STUDY_MD.read_text(encoding="utf-8"))
    pdf_text, _ = _pdf_text_and_pages()
    current = "project returns -0.12 % against a ~10.3 % cost of capital"
    stale = "project returns ~1.5 %"
    assert current in markdown
    assert current in pdf_text
    assert stale not in markdown
    assert stale not in pdf_text


def test_mc_recipe_matches_the_distilled_expected_summary() -> None:
    """Report and HOWTO must use the percentile surface emitted by ``mc_run.distil``."""
    expected = json.loads(MC_EXPECTED.read_text(encoding="utf-8"))
    percentiles = expected["summary"]["equity_irr"]["percentiles"]
    values = tuple(float(percentiles[key]) * 100.0 for key in ("10", "50", "90"))
    assert values == (-13.01013028901385, -9.100690015173812, -4.9796478586176675)

    compact = f"{values[0]:.1f}/{values[1]:.1f}/{values[2]:.1f}%"
    spaced = f"{values[0]:.1f} / {values[1]:.1f} / {values[2]:.1f} %"
    markdown = _normalized(STUDY_MD.read_text(encoding="utf-8"))
    howto = _normalized((KIT / "HOWTO.md").read_text(encoding="utf-8"))
    pdf_text, _ = _pdf_text_and_pages()
    assert compact in markdown.replace(" ", "")
    assert spaced in howto
    assert compact in pdf_text.replace(" ", "")


def test_committed_study_page_count_matches_the_reproduce_docs() -> None:
    """The documented page count must describe the committed, parseable PDF."""
    _, page_count = _pdf_text_and_pages()
    assert page_count == 11
    assert "study 11 pp" in (KIT / "README.md").read_text(encoding="utf-8")
    assert "# 11-pp study" in (KIT / "HOWTO.md").read_text(encoding="utf-8")
