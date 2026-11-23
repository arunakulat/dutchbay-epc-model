"""Reproduce selective OCR text-coverage QC in private storage.

Uses --manifest (private selection of 98 pages), original and OCR PDFs.
NO PDF, OCR text or MarkItDown extraction is ever written inside public Git.
An optional MarkItDown markdown output is stored only under an explicit
out-of-repository path and never committed. Does not perform OCR itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]


def check_private_destination(path: Path, repo: Path) -> Path:
    target = path.resolve()
    if target.is_relative_to(repo.resolve()):
        raise ValueError("Refusing to write private OCR material to a Git checkout")
    return target


def verify(source: Path, ocr: Path, selected_pages: list[int]) -> dict:
    selection = set(int(x) for x in selected_pages)
    if len(selection) != 98:
        raise ValueError(
            "Expected exactly 98 selected PDF pages, refusing alternate recipe"
        )
    improvement = 0
    weak_pages = []
    unchanged_untargeted = 0
    with pymupdf.open(source) as original, pymupdf.open(ocr) as search_pdf:
        if len(original) != len(search_pdf) or len(original) != 292:
            raise ValueError("Annex volume page count does not match 292-page source")
        for idx in range(len(original)):
            old = original[idx].get_text("text", sort=True)
            new = search_pdf[idx].get_text("text", sort=True)
            if idx + 1 in selection:
                if len(new.strip()) >= 100:
                    improvement += 1
                else:
                    weak_pages.append(idx + 1)
            elif old == new:
                unchanged_untargeted += 1
    return {
        "status": "PRIVATE_SOURCE_QC_ONLY",
        "source_annex_pages": 292,
        "selected_pages": len(selection),
        "pages_with_substantial_text": improvement,
        "weak_page_count": len(weak_pages),
        "untargeted_pages_retained": unchanged_untargeted,
        "expected_control": {
            "substantial_text": 93,
            "weak_pages": 5,
            "untargeted_pages": 194,
        },
        "holds": [
            "OCR cannot prove authenticity or regulatory approval",
            "No original pages/source text published",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-pdf", type=Path, required=True)
    ap.add_argument("--ocr-pdf", type=Path, required=True)
    ap.add_argument("--selection-manifest", type=Path, required=True)
    ap.add_argument("--qc-output", type=Path, required=True)
    ap.add_argument("--private-markitdown-output", type=Path)
    args = ap.parse_args()
    dest = check_private_destination(args.qc_output, REPO)
    selection = json.loads(args.selection_manifest.read_text())["pages_1based"]
    result = verify(args.source_pdf, args.ocr_pdf, selection)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    if args.private_markitdown_output:
        md = check_private_destination(args.private_markitdown_output, REPO)
        from markitdown import MarkItDown

        md.parent.mkdir(parents=True, exist_ok=True)
        text = MarkItDown(enable_plugins=False).convert(str(args.ocr_pdf)).text_content
        md.write_text(text, encoding="utf-8")
        print("Private MarkItDown completed", len(text), "characters")


if __name__ == "__main__":
    main()
